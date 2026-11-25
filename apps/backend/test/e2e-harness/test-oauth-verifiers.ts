import {
  BadGatewayException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { OAuthProvider } from '@prisma/client';
import { AUTH_ERROR_CODES } from '../../src/common/constants/auth-error-codes';
import {
  FacebookOAuthVerifier,
  GoogleOAuthVerifier,
  VerifiedOAuthIdentity,
} from '../../src/modules/auth/verifiers/oauth-verifier.interface';

function resolveTestOAuthIdentity(
  token: string,
  provider: OAuthProvider,
  configuredDefaultToken: string | undefined,
  defaultTokenLiteral: string,
  defaultUserId: string,
  defaultEmail: string,
  defaultName: string,
): VerifiedOAuthIdentity {
  const trimmed = typeof token === 'string' ? token.trim() : '';
  if (!trimmed) {
    throw new UnauthorizedException({
      message: 'Token OAuth không hợp lệ hoặc rỗng.',
      errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
    });
  }

  if (trimmed.startsWith('provider-error')) {
    throw new BadGatewayException({
      message: 'Không thể kết nối tới nhà cung cấp xác thực.',
      errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
    });
  }

  if (trimmed.startsWith('no-email')) {
    return {
      provider,
      providerUserId: `${provider.toLowerCase()}-no-email-${trimmed}`,
      email: null,
      emailVerified: false,
      name: `${defaultName} (No Email)`,
    };
  }

  if (trimmed.startsWith('valid-email:')) {
    const email = trimmed.slice('valid-email:'.length).trim().toLowerCase();
    if (!email || !email.includes('@')) {
      throw new UnauthorizedException({
        message: 'Token OAuth không chứa email hợp lệ.',
        errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
      });
    }
    return {
      provider,
      providerUserId: `${provider.toLowerCase()}:${email}`,
      email,
      emailVerified: true,
      name: email.split('@')[0],
    };
  }

  if (
    trimmed === defaultTokenLiteral ||
    (configuredDefaultToken && trimmed === configuredDefaultToken.trim())
  ) {
    return {
      provider,
      providerUserId: defaultUserId,
      email: defaultEmail,
      emailVerified: true,
      name: defaultName,
    };
  }

  throw new UnauthorizedException({
    message: 'Token OAuth không hợp lệ hoặc đã hết hạn.',
    errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
  });
}

@Injectable()
export class TestGoogleOAuthVerifier implements GoogleOAuthVerifier {
  async verifyIdToken(idToken: string): Promise<VerifiedOAuthIdentity> {
    return resolveTestOAuthIdentity(
      idToken,
      OAuthProvider.GOOGLE,
      process.env.E2E_GOOGLE_TEST_ID_TOKEN,
      'valid-google-token',
      'g-e2e-101',
      'g101@gomate.vn',
      'Google Traveler',
    );
  }
}

@Injectable()
export class TestFacebookOAuthVerifier implements FacebookOAuthVerifier {
  async verifyAccessToken(accessToken: string): Promise<VerifiedOAuthIdentity> {
    return resolveTestOAuthIdentity(
      accessToken,
      OAuthProvider.FACEBOOK,
      process.env.E2E_FACEBOOK_TEST_ACCESS_TOKEN,
      'valid-fb-token',
      'fb-e2e-202',
      'fb202@gomate.vn',
      'Facebook Traveler',
    );
  }
}
