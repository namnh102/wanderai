import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { OAuthProvider } from '@prisma/client';
import axios from 'axios';
import { AUTH_ERROR_CODES } from '../../../common/constants/auth-error-codes';
import {
  GoogleOAuthVerifier,
  VerifiedOAuthIdentity,
} from './oauth-verifier.interface';

interface GoogleTokenInfoResponse {
  sub?: string;
  aud?: string;
  exp?: string | number;
  email?: string;
  email_verified?: string | boolean;
  name?: string;
  picture?: string;
}

@Injectable()
export class HttpGoogleOAuthVerifier implements GoogleOAuthVerifier {
  private readonly tokenInfoUrl = 'https://oauth2.googleapis.com/tokeninfo';
  private readonly timeoutMs = 8000;

  constructor(private readonly configService: ConfigService) {}

  private getAllowedClientIds(): string[] {
    const rawValues = [
      this.configService.get<string>('GOOGLE_CLIENT_ID'),
      this.configService.get<string>('GOOGLE_WEB_CLIENT_ID'),
      this.configService.get<string>('GOOGLE_ANDROID_CLIENT_ID'),
    ];

    const ids = new Set<string>();
    for (const raw of rawValues) {
      if (!raw) continue;
      for (const part of raw.split(',')) {
        const trimmed = part.trim();
        if (trimmed) {
          ids.add(trimmed);
        }
      }
    }
    return Array.from(ids);
  }

  async verifyIdToken(idToken: string): Promise<VerifiedOAuthIdentity> {
    const allowedClientIds = this.getAllowedClientIds();
    if (allowedClientIds.length === 0) {
      throw new BadGatewayException({
        message: 'Google OAuth chưa được cấu hình trên máy chủ.',
        errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
      });
    }

    let data: GoogleTokenInfoResponse;
    try {
      const response = await axios.get<GoogleTokenInfoResponse>(
        this.tokenInfoUrl,
        {
          params: { id_token: idToken },
          timeout: this.timeoutMs,
        },
      );
      data = response.data ?? {};
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const status = error.response.status;
        if (status === 400 || status === 401) {
          throw new UnauthorizedException({
            message: 'Mã xác thực Google không hợp lệ hoặc đã hết hạn.',
            errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
          });
        }
      }
      throw new BadGatewayException({
        message: 'Không thể kết nối tới máy chủ xác thực Google.',
        errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
      });
    }

    const sub = typeof data.sub === 'string' ? data.sub.trim() : '';
    const aud = typeof data.aud === 'string' ? data.aud.trim() : '';
    const expSeconds = Number(data.exp);

    if (
      !sub ||
      !aud ||
      !allowedClientIds.includes(aud) ||
      !Number.isFinite(expSeconds) ||
      expSeconds * 1000 <= Date.now()
    ) {
      throw new UnauthorizedException({
        message: 'Mã xác thực Google không hợp lệ hoặc đã hết hạn.',
        errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
      });
    }

    const email = typeof data.email === 'string' ? data.email.trim() : '';
    const emailVerified =
      data.email_verified === true || data.email_verified === 'true';

    if (!email || !emailVerified) {
      throw new BadRequestException({
        message: 'Tài khoản Google chưa cung cấp email đã xác minh.',
        errorCode: AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
      });
    }

    return {
      provider: OAuthProvider.GOOGLE,
      providerUserId: sub,
      email,
      emailVerified: true,
      name: typeof data.name === 'string' ? data.name.trim() || null : null,
      avatarUrl:
        typeof data.picture === 'string' ? data.picture.trim() || null : null,
    };
  }
}
