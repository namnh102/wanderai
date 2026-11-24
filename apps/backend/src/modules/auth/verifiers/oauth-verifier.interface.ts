import { OAuthProvider } from '@prisma/client';

export const GOOGLE_OAUTH_VERIFIER = Symbol('GOOGLE_OAUTH_VERIFIER');
export const FACEBOOK_OAUTH_VERIFIER = Symbol('FACEBOOK_OAUTH_VERIFIER');

export interface VerifiedOAuthIdentity {
  provider: OAuthProvider;
  providerUserId: string;
  email: string | null;
  emailVerified: boolean;
  name?: string | null;
  avatarUrl?: string | null;
}

export interface GoogleOAuthVerifier {
  verifyIdToken(idToken: string): Promise<VerifiedOAuthIdentity>;
}

export interface FacebookOAuthVerifier {
  verifyAccessToken(accessToken: string): Promise<VerifiedOAuthIdentity>;
}
