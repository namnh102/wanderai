import { Injectable, UnauthorizedException, BadRequestException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { PrismaService } from '../../prisma/prisma.service';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
  ) {}

  async register(dto: RegisterDto) {
    try {
      // This expects a User model in schema.prisma with email, password_hash, name
      const existingUser = await this.prisma['user'].findUnique({
        where: { email: dto.email },
      });

      if (existingUser) {
        throw new BadRequestException('User with this email already exists');
      }

      const hashedPassword = await bcrypt.hash(dto.password, 10);

      const user = await this.prisma['user'].create({
        data: {
          email: dto.email,
          passwordHash: hashedPassword,
          profile: {
            create: {
              displayName: dto.name,
            },
          },
        },
      });

      return this.generateTokens(user.id, user.email);
    } catch (error) {
      if (error instanceof BadRequestException) throw error;
      throw new BadRequestException('Registration failed. Ensure Prisma schema has User model.');
    }
  }

  async login(dto: LoginDto) {
    try {
      const user = await this.prisma['user'].findUnique({
        where: { email: dto.email },
      });

      if (!user || user.deletedAt) {
        throw new UnauthorizedException('Invalid credentials');
      }

      const isPasswordValid = await bcrypt.compare(dto.password, user.passwordHash);

      if (!isPasswordValid) {
        throw new UnauthorizedException('Invalid credentials');
      }

      return this.generateTokens(user.id, user.email);
    } catch (error) {
      if (error instanceof UnauthorizedException) throw error;
      throw new BadRequestException('Login failed.');
    }
  }

  async refreshToken(userId: string, email: string) {
    return this.generateTokens(userId, email);
  }

  private generateTokens(userId: string, email: string) {
    const payload = { sub: userId, email };
    
    return {
      access_token: this.jwtService.sign(payload, { expiresIn: '15m' }),
      refresh_token: this.jwtService.sign(payload, { expiresIn: '7d' }),
    };
  }
}
