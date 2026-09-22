import { Injectable, UnauthorizedException, BadRequestException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcryptjs';
import { PrismaService } from '../../prisma/prisma.service';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {}

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

  // Refresh token: verify → tạo cặp tokens mới
  async refreshToken(refreshTokenStr: string) {
    try {
      const payload = this.jwtService.verify(refreshTokenStr, {
        secret: this.configService.get('JWT_REFRESH_SECRET', 'wanderai-dev-refresh-secret-2026'),
      });
      return this.generateTokens(payload.sub, payload.email);
    } catch {
      throw new UnauthorizedException('Refresh token không hợp lệ');
    }
  }

  // Tạo cặp access + refresh tokens
  private generateTokens(userId: string, email: string) {
    const payload = { sub: userId, email };

    const accessToken = this.jwtService.sign(payload, {
      secret: this.configService.get('JWT_SECRET', 'wanderai-dev-jwt-secret-2026'),
      expiresIn: '15m',
    });

    const refreshToken = this.jwtService.sign(payload, {
      secret: this.configService.get('JWT_REFRESH_SECRET', 'wanderai-dev-refresh-secret-2026'),
      expiresIn: '7d',
    });

    return { access_token: accessToken, refresh_token: refreshToken };
  }
}
