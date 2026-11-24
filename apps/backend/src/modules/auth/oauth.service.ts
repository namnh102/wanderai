import {
  BadRequestException,
  Inject,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { OAuthProvider, Prisma } from '@prisma/client';
import { AUTH_ERROR_CODES } from '../../common/constants/auth-error-codes';
import { PrismaService } from '../../prisma/prisma.service';
import { AuthService } from './auth.service';
import {
  FACEBOOK_OAUTH_VERIFIER,
  FacebookOAuthVerifier,
  GOOGLE_OAUTH_VERIFIER,
  GoogleOAuthVerifier,
  VerifiedOAuthIdentity,
} from './verifiers/oauth-verifier.interface';

export interface OAuthUserSummary {
  id: string;
  email: string;
  name: string;
  role: string;
  isVerified: boolean;
  providers: string[];
}

export interface OAuthLoginResponse {
  access_token: string;
  refresh_token: string;
  user: OAuthUserSummary;
}

const OAUTH_USER_INCLUDE = {
  profile: true,
  oauthAccounts: {
    select: {
      provider: true,
    },
  },
} as const;

type UserWithProfileAndProviders = Prisma.UserGetPayload<{
  include: typeof OAUTH_USER_INCLUDE;
}>;

function isPrismaUniqueError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    (error as { code?: unknown }).code === 'P2002'
  );
}

@Injectable()
export class OAuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly authService: AuthService,
    @Inject(GOOGLE_OAUTH_VERIFIER)
    private readonly googleVerifier: GoogleOAuthVerifier,
    @Inject(FACEBOOK_OAUTH_VERIFIER)
    private readonly facebookVerifier: FacebookOAuthVerifier,
  ) {}

  async loginWithGoogle(idToken: string): Promise<OAuthLoginResponse> {
    const identity = await this.googleVerifier.verifyIdToken(idToken);
    return this.resolveOrCreateOAuthUser(identity);
  }

  async loginWithFacebook(accessToken: string): Promise<OAuthLoginResponse> {
    const identity = await this.facebookVerifier.verifyAccessToken(accessToken);
    return this.resolveOrCreateOAuthUser(identity);
  }

  private async resolveOrCreateOAuthUser(
    identity: VerifiedOAuthIdentity,
  ): Promise<OAuthLoginResponse> {
    const normalizedEmail =
      typeof identity.email === 'string'
        ? identity.email.toLowerCase().trim()
        : '';

    if (!normalizedEmail || !identity.emailVerified) {
      throw new BadRequestException({
        message: 'Nhà cung cấp không trả về email đã xác minh.',
        errorCode: AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
      });
    }

    const user = await this.findOrProvisionUser(identity, normalizedEmail);
    const tokens = this.authService.issueTokensForUser(user.id, user.email);

    const providers = Array.from(
      new Set(
        (user.oauthAccounts ?? []).map((account) =>
          account.provider.toLowerCase(),
        ),
      ),
    ).sort();

    const displayName =
      user.profile?.displayName?.trim() ||
      identity.name?.trim() ||
      normalizedEmail.split('@')[0];

    return {
      ...tokens,
      user: {
        id: user.id,
        email: user.email,
        name: displayName,
        role: user.role,
        isVerified: user.isVerified,
        providers,
      },
    };
  }

  private async findOrProvisionUser(
    identity: VerifiedOAuthIdentity,
    normalizedEmail: string,
  ): Promise<UserWithProfileAndProviders> {
    const existingOAuth = await this.prisma.oAuthAccount.findUnique({
      where: {
        provider_providerUserId: {
          provider: identity.provider,
          providerUserId: identity.providerUserId,
        },
      },
      include: {
        user: {
          include: OAUTH_USER_INCLUDE,
        },
      },
    });

    if (existingOAuth) {
      if (!existingOAuth.user || existingOAuth.user.deletedAt) {
        throw new UnauthorizedException({
          message: 'Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.',
          errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
        });
      }

      if (existingOAuth.email !== normalizedEmail) {
        await this.prisma.oAuthAccount.update({
          where: { id: existingOAuth.id },
          data: { email: normalizedEmail },
        });
      }

      if (!existingOAuth.user.isVerified && identity.emailVerified) {
        return this.prisma.user.update({
          where: { id: existingOAuth.user.id },
          data: { isVerified: true },
          include: OAUTH_USER_INCLUDE,
        });
      }

      return existingOAuth.user;
    }

    const existingByEmail = await this.prisma.user.findUnique({
      where: { email: normalizedEmail },
      include: OAUTH_USER_INCLUDE,
    });

    const fallbackDisplayName =
      identity.name?.trim() || normalizedEmail.split('@')[0];

    if (existingByEmail) {
      if (existingByEmail.deletedAt) {
        throw new UnauthorizedException({
          message: 'Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.',
          errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
        });
      }

      try {
        return await this.linkProviderToExistingUser(
          existingByEmail,
          identity.provider,
          identity.providerUserId,
          normalizedEmail,
          fallbackDisplayName,
          identity.avatarUrl ?? null,
        );
      } catch (error) {
        if (isPrismaUniqueError(error)) {
          const refetched = await this.prisma.user.findUnique({
            where: { id: existingByEmail.id },
            include: OAUTH_USER_INCLUDE,
          });
          if (refetched && !refetched.deletedAt) {
            return refetched;
          }
        }
        throw error;
      }
    }

    try {
      return await this.prisma.$transaction(async (tx) => {
        return tx.user.create({
          data: {
            email: normalizedEmail,
            passwordHash: null,
            isVerified: true,
            profile: {
              create: {
                displayName: fallbackDisplayName,
                avatar: identity.avatarUrl ?? null,
              },
            },
            oauthAccounts: {
              create: {
                provider: identity.provider,
                providerUserId: identity.providerUserId,
                email: normalizedEmail,
              },
            },
          },
          include: OAUTH_USER_INCLUDE,
        });
      });
    } catch (error) {
      if (isPrismaUniqueError(error)) {
        const retriedOAuth = await this.prisma.oAuthAccount.findUnique({
          where: {
            provider_providerUserId: {
              provider: identity.provider,
              providerUserId: identity.providerUserId,
            },
          },
          include: {
            user: {
              include: OAUTH_USER_INCLUDE,
            },
          },
        });
        if (retriedOAuth?.user && !retriedOAuth.user.deletedAt) {
          return retriedOAuth.user;
        }

        const retriedByEmail = await this.prisma.user.findUnique({
          where: { email: normalizedEmail },
          include: OAUTH_USER_INCLUDE,
        });
        if (retriedByEmail && !retriedByEmail.deletedAt) {
          return this.linkProviderToExistingUser(
            retriedByEmail,
            identity.provider,
            identity.providerUserId,
            normalizedEmail,
            fallbackDisplayName,
            identity.avatarUrl ?? null,
          );
        }
      }
      throw error;
    }
  }

  private async linkProviderToExistingUser(
    existingUser: UserWithProfileAndProviders,
    provider: OAuthProvider,
    providerUserId: string,
    email: string,
    displayName: string,
    avatarUrl: string | null,
  ): Promise<UserWithProfileAndProviders> {
    return this.prisma.$transaction(async (tx) => {
      const alreadyLinked = await tx.oAuthAccount.findUnique({
        where: {
          provider_providerUserId: {
            provider,
            providerUserId,
          },
        },
      });

      if (!alreadyLinked) {
        await tx.oAuthAccount.create({
          data: {
            userId: existingUser.id,
            provider,
            providerUserId,
            email,
          },
        });
      }

      if (!existingUser.profile) {
        await tx.profile.create({
          data: {
            userId: existingUser.id,
            displayName,
            avatar: avatarUrl,
          },
        });
      }

      return tx.user.update({
        where: { id: existingUser.id },
        data: existingUser.isVerified ? {} : { isVerified: true },
        include: OAUTH_USER_INCLUDE,
      });
    });
  }
}
