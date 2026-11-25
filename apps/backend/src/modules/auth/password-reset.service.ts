import {
  BadRequestException,
  Injectable,
  Logger,
} from '@nestjs/common';
import * as bcrypt from 'bcryptjs';
import { createHash, randomBytes } from 'crypto';
import { AUTH_ERROR_CODES } from '../../common/constants/auth-error-codes';
import { PrismaService } from '../../prisma/prisma.service';
import { MailService } from '../mail/mail.service';
import { ForgotPasswordDto } from './dto/forgot-password.dto';
import { ResetPasswordDto } from './dto/reset-password.dto';

export const PASSWORD_RESET_TTL_MINUTES = 30;

export interface ForgotPasswordResponse {
  sent: true;
  message: string;
  expiresInMinutes: number;
}

export interface ValidateResetTokenResponse {
  valid: true;
  expiresAt: string;
}

export interface ResetPasswordResponse {
  reset: true;
  message: string;
}

@Injectable()
export class PasswordResetService {
  private readonly logger = new Logger(PasswordResetService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly mailService: MailService,
  ) {}

  private hashToken(rawToken: string): string {
    return createHash('sha256').update(rawToken).digest('hex');
  }

  async forgotPassword(
    dto: ForgotPasswordDto,
  ): Promise<ForgotPasswordResponse> {
    const normalizedEmail = dto.email.toLowerCase().trim();
    const genericResponse: ForgotPasswordResponse = {
      sent: true,
      message:
        'Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi.',
      expiresInMinutes: PASSWORD_RESET_TTL_MINUTES,
    };

    const user = await this.prisma.user.findUnique({
      where: { email: normalizedEmail },
      include: { profile: true },
    });

    if (!user || user.deletedAt) {
      return genericResponse;
    }

    const rawToken = randomBytes(32).toString('hex');
    const tokenHash = this.hashToken(rawToken);
    const now = new Date();
    const expiresAt = new Date(
      now.getTime() + PASSWORD_RESET_TTL_MINUTES * 60 * 1000,
    );

    await this.prisma.$transaction(async (tx) => {
      await tx.passwordResetToken.updateMany({
        where: {
          userId: user.id,
          usedAt: null,
        },
        data: {
          usedAt: now,
        },
      });

      await tx.passwordResetToken.create({
        data: {
          userId: user.id,
          tokenHash,
          expiresAt,
        },
      });
    });

    try {
      await this.mailService.sendPasswordResetEmail({
        to: user.email,
        displayName: user.profile?.displayName,
        rawToken,
        expiresInMinutes: PASSWORD_RESET_TTL_MINUTES,
      });
    } catch (error) {
      const errorMsg =
        error instanceof Error ? error.message : 'Unknown mail transport error';
      // Log failure server-side without leaking user existence or reset tokens.
      this.logger.error(
        `Failed to dispatch password reset email for user ${user.id}: ${errorMsg}`,
      );
    }

    return genericResponse;
  }

  async validateResetToken(
    rawToken?: string,
  ): Promise<ValidateResetTokenResponse> {
    const token = typeof rawToken === 'string' ? rawToken.trim() : '';
    if (!token) {
      throw new BadRequestException({
        message: 'Liên kết đặt lại mật khẩu không hợp lệ.',
        errorCode: AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      });
    }

    const tokenHash = this.hashToken(token);
    const record = await this.prisma.passwordResetToken.findUnique({
      where: { tokenHash },
      include: { user: true },
    });

    if (!record || !record.user || record.user.deletedAt) {
      throw new BadRequestException({
        message: 'Liên kết đặt lại mật khẩu không hợp lệ.',
        errorCode: AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      });
    }

    if (record.usedAt !== null) {
      throw new BadRequestException({
        message: 'Liên kết đặt lại mật khẩu đã được sử dụng.',
        errorCode: AUTH_ERROR_CODES.RESET_TOKEN_USED,
      });
    }

    if (record.expiresAt.getTime() <= Date.now()) {
      throw new BadRequestException({
        message: 'Liên kết đặt lại mật khẩu đã hết hạn.',
        errorCode: AUTH_ERROR_CODES.RESET_TOKEN_EXPIRED,
      });
    }

    return {
      valid: true,
      expiresAt: record.expiresAt.toISOString(),
    };
  }

  async resetPassword(dto: ResetPasswordDto): Promise<ResetPasswordResponse> {
    const token = typeof dto.token === 'string' ? dto.token.trim() : '';
    if (!token) {
      throw new BadRequestException({
        message: 'Liên kết đặt lại mật khẩu không hợp lệ.',
        errorCode: AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      });
    }

    const tokenHash = this.hashToken(token);
    const hashedPassword = await bcrypt.hash(dto.newPassword, 12);
    const now = new Date();

    await this.prisma.$transaction(async (tx) => {
      const claimed = await tx.passwordResetToken.updateMany({
        where: {
          tokenHash,
          usedAt: null,
          expiresAt: { gt: now },
        },
        data: {
          usedAt: now,
        },
      });

      if (claimed.count === 0) {
        const existing = await tx.passwordResetToken.findUnique({
          where: { tokenHash },
        });

        if (!existing) {
          throw new BadRequestException({
            message: 'Liên kết đặt lại mật khẩu không hợp lệ.',
            errorCode: AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
          });
        }

        if (existing.usedAt !== null) {
          throw new BadRequestException({
            message: 'Liên kết đặt lại mật khẩu đã được sử dụng.',
            errorCode: AUTH_ERROR_CODES.RESET_TOKEN_USED,
          });
        }

        throw new BadRequestException({
          message: 'Liên kết đặt lại mật khẩu đã hết hạn.',
          errorCode: AUTH_ERROR_CODES.RESET_TOKEN_EXPIRED,
        });
      }

      const record = await tx.passwordResetToken.findUnique({
        where: { tokenHash },
        include: { user: true },
      });

      if (!record || !record.user || record.user.deletedAt) {
        throw new BadRequestException({
          message: 'Liên kết đặt lại mật khẩu không hợp lệ.',
          errorCode: AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
        });
      }

      await tx.user.update({
        where: { id: record.userId },
        data: {
          passwordHash: hashedPassword,
          tokenVersion: { increment: 1 },
        },
      });

      await tx.passwordResetToken.updateMany({
        where: {
          userId: record.userId,
          usedAt: null,
        },
        data: {
          usedAt: now,
        },
      });
    });

    return {
      reset: true,
      message: 'Đặt lại mật khẩu thành công.',
    };
  }
}
