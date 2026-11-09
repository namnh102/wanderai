import { ExtractJwt, Strategy } from 'passport-jwt';
import { PassportStrategy } from '@nestjs/passport';
import {
  Injectable,
  InternalServerErrorException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../../../prisma/prisma.service';
import { getValidatedJwtConfig, JwtTokenPayload } from '../jwt-config';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(
    private configService: ConfigService,
    private prisma: PrismaService,
  ) {
    const { accessSecret } = getValidatedJwtConfig(configService);
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: accessSecret,
    });
  }

  async validate(payload: JwtTokenPayload) {
    if (!payload || typeof payload.sub !== 'string' || !payload.sub.trim()) {
      throw new UnauthorizedException('Token không hợp lệ');
    }

    if (payload.type !== undefined && payload.type !== 'access') {
      throw new UnauthorizedException('Token không hợp lệ');
    }

    let user: Awaited<ReturnType<PrismaService['user']['findUnique']>>;
    try {
      user = await this.prisma.user.findUnique({
        where: { id: payload.sub },
      });
    } catch {
      throw new InternalServerErrorException('Không thể xác thực tài khoản lúc này');
    }

    if (!user || user.deletedAt) {
      throw new UnauthorizedException('Tài khoản không tồn tại hoặc đã bị vô hiệu hóa');
    }

    return user;
  }
}
