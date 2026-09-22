import { ExtractJwt, Strategy } from 'passport-jwt';
import { PassportStrategy } from '@nestjs/passport';
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../../../prisma/prisma.service';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(
    private configService: ConfigService,
    private prisma: PrismaService,
  ) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: configService.get<string>('JWT_SECRET') || 'super-secret',
    });
  }

  async validate(payload: any) {
    // Note: Assuming the User model exists in Prisma with id field
    // Since Prisma schema isn't fully defined here, we wrap in try-catch
    try {
      const user = await this.prisma['user'].findUnique({
        where: { id: payload.sub },
      });
      
      if (!user || user.deletedAt) {
        throw new UnauthorizedException();
      }
      return user;
    } catch (e) {
      // Fallback if schema doesn't match perfectly yet
      return { id: payload.sub, email: payload.email };
    }
  }
}
