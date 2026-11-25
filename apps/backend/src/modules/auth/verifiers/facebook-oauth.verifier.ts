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
  FacebookOAuthVerifier,
  VerifiedOAuthIdentity,
} from './oauth-verifier.interface';

interface FacebookDebugTokenResponse {
  data?: {
    app_id?: string | number;
    is_valid?: boolean;
    user_id?: string | number;
    expires_at?: number;
  };
}

interface FacebookMeResponse {
  id?: string;
  name?: string;
  email?: string;
  picture?: {
    data?: {
      url?: string;
    };
  };
}

interface FacebookGraphErrorPayload {
  error?: {
    code?: number;
    message?: string;
  };
}

@Injectable()
export class HttpFacebookOAuthVerifier implements FacebookOAuthVerifier {
  private readonly debugTokenUrl = 'https://graph.facebook.com/debug_token';
  private readonly meUrl = 'https://graph.facebook.com/me';
  private readonly timeoutMs = 8000;

  constructor(private readonly configService: ConfigService) {}

  private getAppCredentials(): { appId: string; appSecret: string } {
    const appId = this.configService.get<string>('FACEBOOK_APP_ID')?.trim();
    const appSecret = this.configService
      .get<string>('FACEBOOK_APP_SECRET')
      ?.trim();

    if (!appId || !appSecret) {
      throw new BadGatewayException({
        message: 'Facebook OAuth chưa được cấu hình trên máy chủ.',
        errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
      });
    }

    return { appId, appSecret };
  }

  private mapGraphError(error: unknown): never {
    if (axios.isAxiosError(error) && error.response) {
      const status = error.response.status;
      const body = error.response.data as FacebookGraphErrorPayload | undefined;
      const graphCode = body?.error?.code;

      if (status === 400 || status === 401 || graphCode === 190) {
        throw new UnauthorizedException({
          message: 'Mã xác thực Facebook không hợp lệ hoặc đã hết hạn.',
          errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
        });
      }
    }

    throw new BadGatewayException({
      message: 'Không thể kết nối tới máy chủ xác thực Facebook.',
      errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
    });
  }

  async verifyAccessToken(
    accessToken: string,
  ): Promise<VerifiedOAuthIdentity> {
    const { appId, appSecret } = this.getAppCredentials();

    let debugPayload: FacebookDebugTokenResponse;
    try {
      const debugResponse = await axios.get<FacebookDebugTokenResponse>(
        this.debugTokenUrl,
        {
          params: {
            input_token: accessToken,
            access_token: `${appId}|${appSecret}`,
          },
          timeout: this.timeoutMs,
        },
      );
      debugPayload = debugResponse.data ?? {};
    } catch (error) {
      this.mapGraphError(error);
    }

    const debugData = debugPayload.data;
    if (
      !debugData ||
      debugData.is_valid !== true ||
      String(debugData.app_id ?? '') !== appId
    ) {
      throw new UnauthorizedException({
        message: 'Mã xác thực Facebook không hợp lệ hoặc đã hết hạn.',
        errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
      });
    }

    let meData: FacebookMeResponse;
    try {
      const meResponse = await axios.get<FacebookMeResponse>(this.meUrl, {
        params: {
          fields: 'id,name,email,picture.type(large)',
          access_token: accessToken,
        },
        timeout: this.timeoutMs,
      });
      meData = meResponse.data ?? {};
    } catch (error) {
      this.mapGraphError(error);
    }

    const userId = typeof meData.id === 'string' ? meData.id.trim() : '';
    const debugUserId =
      debugData.user_id !== undefined ? String(debugData.user_id).trim() : '';

    if (!userId || (debugUserId && userId !== debugUserId)) {
      throw new UnauthorizedException({
        message: 'Mã xác thực Facebook không hợp lệ.',
        errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
      });
    }

    const email = typeof meData.email === 'string' ? meData.email.trim() : '';
    if (!email) {
      throw new BadRequestException({
        message: 'Tài khoản Facebook chưa cấp quyền truy cập email.',
        errorCode: AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
      });
    }

    return {
      provider: OAuthProvider.FACEBOOK,
      providerUserId: userId,
      email,
      emailVerified: true,
      name: typeof meData.name === 'string' ? meData.name.trim() || null : null,
      avatarUrl:
        typeof meData.picture?.data?.url === 'string'
          ? meData.picture.data.url.trim() || null
          : null,
    };
  }
}
