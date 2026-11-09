import { Injectable, UnauthorizedException, BadRequestException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcryptjs';
import { PrismaService } from '../../prisma/prisma.service';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';
import {
  getValidatedJwtConfig,
  JwtTokenPayload,
  ValidatedJwtConfig,
} from './jwt-config';

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
  async register(dto: RegisterDto) {
    const existingUser = await this.prisma.user.findUnique({
      where: { email: dto.email.toLowerCase().trim() },
    });

    if (existingUser) {
      throw new BadRequestException('Email đã được sử dụng');
    }

    const hashedPassword = await bcrypt.hash(dto.password, 12);

    const user = await this.prisma.user.create({
      data: {
        email: dto.email.toLowerCase().trim(),
        passwordHash: hashedPassword,
        profile: {
          create: { displayName: dto.name.trim() },
        },
      },
      include: { profile: true },
    });

    return this.generateTokens(user.id, user.email);
  }

  // Đăng nhập: tìm user → compare password → trả tokens
  async login(dto: LoginDto) {
    const user = await this.prisma.user.findUnique({
      where: { email: dto.email.toLowerCase().trim() },
      include: { profile: true },
    });

    if (!user || user.deletedAt) {
      throw new UnauthorizedException('Email hoặc mật khẩu không đúng');
    }

    const isValid = await bcrypt.compare(dto.password, user.passwordHash);
    if (!isValid) {
      throw new UnauthorizedException('Email hoặc mật khẩu không đúng');
    }

    return this.generateTokens(user.id, user.email);
  }

  // Refresh token: verify signature/expiry/type → kiểm tra tài khoản active → tạo cặp tokens mới
  async refreshToken(refreshTokenStr: string) {
    if (!refreshTokenStr || typeof refreshTokenStr !== 'string' || !refreshTokenStr.trim()) {
      throw new UnauthorizedException('Refresh token không hợp lệ');
    }

    let payload: JwtTokenPayload;
    try {
      payload = this.jwtService.verify<JwtTokenPayload>(refreshTokenStr, {
        secret: this.jwtConfig.refreshSecret,
      });
    } catch {
      throw new UnauthorizedException('Refresh token không hợp lệ');
    }

    if (
      !payload ||
      typeof payload.sub !== 'string' ||
      !payload.sub.trim() ||
      payload.type !== 'refresh'
    ) {
      throw new UnauthorizedException('Refresh token không hợp lệ');
    }

    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
    });

    if (!user || user.deletedAt) {
      throw new UnauthorizedException('Refresh token không hợp lệ');
    }

    return this.generateTokens(user.id, user.email);
  }

  // Tạo cặp access + refresh tokens
  private generateTokens(userId: string, email: string) {
    const accessPayload: JwtTokenPayload = { sub: userId, email, type: 'access' };
    const refreshPayload: JwtTokenPayload = { sub: userId, email, type: 'refresh' };

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
