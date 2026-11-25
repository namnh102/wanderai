import {
  Injectable,
  UnauthorizedException,
  BadRequestException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcryptjs';
import { PrismaService } from '../../prisma/prisma.service';
import { AUTH_ERROR_CODES } from '../../common/constants/auth-error-codes';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';
import {
  getValidatedJwtConfig,
  JwtTokenPayload,
  ValidatedJwtConfig,
} from './jwt-config';

export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
}

@Injectable()
export class AuthService {
  private readonly jwtConfig: ValidatedJwtConfig;

  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {
    this.jwtConfig = getValidatedJwtConfig(this.configService);
  }

  // Đăng ký: validate → hash password → tạo user + profile → trả tokens
  async register(dto: RegisterDto): Promise<AuthTokenPair> {
    const existingUser = await this.prisma.user.findUnique({
      where: { email: dto.email.toLowerCase().trim() },
    });

    if (existingUser) {
      throw new BadRequestException({
        message: 'Email đã được sử dụng',
        errorCode: AUTH_ERROR_CODES.EMAIL_ALREADY_EXISTS,
      });
    }

    const hashedPassword = await bcrypt.hash(dto.password, 12);

    let user: Awaited<ReturnType<PrismaService['user']['create']>>;
    try {
      user = await this.prisma.user.create({
        data: {
          email: dto.email.toLowerCase().trim(),
          passwordHash: hashedPassword,
          profile: {
            create: { displayName: dto.name.trim() },
          },
        },
        include: { profile: true },
      });
    } catch (error) {
      const code =
        typeof error === 'object' && error !== null && 'code' in error
          ? (error as { code?: unknown }).code
          : undefined;
      if (code === 'P2002') {
        throw new BadRequestException({
          message: 'Email đã được sử dụng',
          errorCode: AUTH_ERROR_CODES.EMAIL_ALREADY_EXISTS,
        });
      }
      throw error;
    }

    return this.generateTokens(user.id, user.email, user.tokenVersion ?? 0);
  }

  // Đăng nhập: tìm user → compare password → trả tokens
  async login(dto: LoginDto): Promise<AuthTokenPair> {
    const user = await this.prisma.user.findUnique({
      where: { email: dto.email.toLowerCase().trim() },
      include: { profile: true },
    });

    if (!user || user.deletedAt || !user.passwordHash) {
      throw new UnauthorizedException({
        message: 'Email hoặc mật khẩu không đúng',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    const isValid = await bcrypt.compare(dto.password, user.passwordHash);
    if (!isValid) {
      throw new UnauthorizedException({
        message: 'Email hoặc mật khẩu không đúng',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    return this.generateTokens(user.id, user.email, user.tokenVersion ?? 0);
  }

  // Refresh token: verify signature/expiry/type → kiểm tra tài khoản active → tạo cặp tokens mới
  async refreshToken(refreshTokenStr: string): Promise<AuthTokenPair> {
    if (
      !refreshTokenStr ||
      typeof refreshTokenStr !== 'string' ||
      !refreshTokenStr.trim()
    ) {
      throw new UnauthorizedException({
        message: 'Refresh token không hợp lệ',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    let payload: JwtTokenPayload;
    try {
      payload = this.jwtService.verify<JwtTokenPayload>(refreshTokenStr, {
        secret: this.jwtConfig.refreshSecret,
      });
    } catch {
      throw new UnauthorizedException({
        message: 'Refresh token không hợp lệ',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    if (
      !payload ||
      typeof payload.sub !== 'string' ||
      !payload.sub.trim() ||
      payload.type !== 'refresh'
    ) {
      throw new UnauthorizedException({
        message: 'Refresh token không hợp lệ',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
    });

    if (!user || user.deletedAt) {
      throw new UnauthorizedException({
        message: 'Refresh token không hợp lệ',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    const currentVersion = user.tokenVersion ?? 0;
    if (
      (currentVersion > 0 && payload.tv !== currentVersion) ||
      (payload.tv !== undefined && payload.tv !== currentVersion)
    ) {
      throw new UnauthorizedException({
        message: 'Refresh token đã bị thu hồi',
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });
    }

    return this.generateTokens(user.id, user.email, currentVersion);
  }

  issueTokensForUser(
    userId: string,
    email: string,
    tokenVersion = 0,
  ): AuthTokenPair {
    return this.generateTokens(userId, email, tokenVersion);
  }

  // Tạo cặp access + refresh tokens
  generateTokens(
    userId: string,
    email: string,
    tokenVersion = 0,
  ): AuthTokenPair {
    const accessPayload: JwtTokenPayload = {
      sub: userId,
      email,
      type: 'access',
      tv: tokenVersion,
    };
    const refreshPayload: JwtTokenPayload = {
      sub: userId,
      email,
      type: 'refresh',
      tv: tokenVersion,
    };

    const accessToken = this.jwtService.sign(accessPayload, {
      secret: this.jwtConfig.accessSecret,
      expiresIn: '15m',
    });

    const refreshToken = this.jwtService.sign(refreshPayload, {
      secret: this.jwtConfig.refreshSecret,
      expiresIn: '7d',
    });

    return { access_token: accessToken, refresh_token: refreshToken };
  }
}
