import {
  BadGatewayException,
  BadRequestException,
  INestApplication,
  UnauthorizedException,
  ValidationPipe,
} from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { Test, TestingModule } from '@nestjs/testing';
import { OAuthProvider, UserRole } from '@prisma/client';
import axios from 'axios';
import { createHash, randomBytes, randomUUID } from 'crypto';
import * as request from 'supertest';
import { AUTH_ERROR_CODES } from '../../common/constants/auth-error-codes';
import { HttpExceptionFilter } from '../../common/filters/http-exception.filter';
import { TransformInterceptor } from '../../common/interceptors/transform.interceptor';
import { PrismaModule } from '../../prisma/prisma.module';
import { PrismaService } from '../../prisma/prisma.service';
import { MailModule } from '../mail/mail.module';
import { MailService } from '../mail/mail.service';
import { InMemoryTestMailTransport } from '../mail/transports/in-memory-test-mail.transport';
import { AuthModule } from './auth.module';
import { validateEnvironmentJwtConfig } from './jwt-config';
import { HttpFacebookOAuthVerifier } from './verifiers/facebook-oauth.verifier';
import { HttpGoogleOAuthVerifier } from './verifiers/google-oauth.verifier';
import {
  FACEBOOK_OAUTH_VERIFIER,
  FacebookOAuthVerifier,
  GOOGLE_OAUTH_VERIFIER,
  GoogleOAuthVerifier,
  VerifiedOAuthIdentity,
} from './verifiers/oauth-verifier.interface';

const TEST_JWT_ACCESS_SECRET = `test-access-${randomBytes(24).toString('hex')}`;
const TEST_JWT_REFRESH_SECRET = `test-refresh-${randomBytes(24).toString('hex')}`;

interface InMemoryUserRow {
  id: string;
  email: string;
  passwordHash: string | null;
  role: UserRole;
  isVerified: boolean;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

interface InMemoryProfileRow {
  id: string;
  userId: string;
  displayName: string;
  avatar: string | null;
}

interface InMemoryResetTokenRow {
  id: string;
  userId: string;
  tokenHash: string;
  expiresAt: Date;
  usedAt: Date | null;
  createdAt: Date;
}

interface InMemoryOAuthAccountRow {
  id: string;
  userId: string;
  provider: OAuthProvider;
  providerUserId: string;
  email: string | null;
  createdAt: Date;
  updatedAt: Date;
}

class StatefulInMemoryPrisma {
  readonly users = new Map<string, InMemoryUserRow>();
  readonly profiles = new Map<string, InMemoryProfileRow>();
  readonly resetTokens = new Map<string, InMemoryResetTokenRow>();
  readonly oauthAccounts = new Map<string, InMemoryOAuthAccountRow>();

  clear(): void {
    this.users.clear();
    this.profiles.clear();
    this.resetTokens.clear();
    this.oauthAccounts.clear();
  }

  private hydrateUser(
    row: InMemoryUserRow,
    include?: Record<string, unknown>,
  ) {
    const profile =
      Array.from(this.profiles.values()).find((p) => p.userId === row.id) ??
      null;
    const oauthAccounts = Array.from(this.oauthAccounts.values()).filter(
      (a) => a.userId === row.id,
    );

    return {
      ...row,
      ...(include?.profile ? { profile } : {}),
      ...(include?.oauthAccounts ? { oauthAccounts } : {}),
    };
  }

  readonly user = {
    findUnique: async (args: {
      where: { id?: string; email?: string };
      include?: Record<string, unknown>;
    }) => {
      let found: InMemoryUserRow | undefined;
      if (args.where.id) {
        found = this.users.get(args.where.id);
      } else if (args.where.email) {
        for (const u of this.users.values()) {
          if (u.email === args.where.email) {
            found = u;
            break;
          }
        }
      }
      return found ? this.hydrateUser(found, args.include) : null;
    },

    create: async (args: {
      data: {
        email: string;
        passwordHash?: string | null;
        role?: UserRole;
        isVerified?: boolean;
        deletedAt?: Date | null;
        profile?: { create: { displayName: string; avatar?: string | null } };
        oauthAccounts?: {
          create: {
            provider: OAuthProvider;
            providerUserId: string;
            email?: string | null;
          };
        };
      };
      include?: Record<string, unknown>;
    }) => {
      for (const existing of this.users.values()) {
        if (existing.email === args.data.email) {
          throw Object.assign(new Error('Unique constraint failed on email'), {
            code: 'P2002',
          });
        }
      }

      const now = new Date();
      const userId = randomUUID();
      const userRow: InMemoryUserRow = {
        id: userId,
        email: args.data.email,
        passwordHash: args.data.passwordHash ?? null,
        role: args.data.role ?? UserRole.USER,
        isVerified: args.data.isVerified ?? false,
        createdAt: now,
        updatedAt: now,
        deletedAt: args.data.deletedAt ?? null,
      };
      this.users.set(userId, userRow);

      if (args.data.profile?.create) {
        const profileId = randomUUID();
        this.profiles.set(profileId, {
          id: profileId,
          userId,
          displayName: args.data.profile.create.displayName,
          avatar: args.data.profile.create.avatar ?? null,
        });
      }

      if (args.data.oauthAccounts?.create) {
        await this.oAuthAccount.create({
          data: {
            userId,
            provider: args.data.oauthAccounts.create.provider,
            providerUserId: args.data.oauthAccounts.create.providerUserId,
            email: args.data.oauthAccounts.create.email ?? null,
          },
        });
      }

      return this.hydrateUser(userRow, args.include);
    },

    update: async (args: {
      where: { id: string };
      data: { passwordHash?: string | null; isVerified?: boolean };
      include?: Record<string, unknown>;
    }) => {
      const existing = this.users.get(args.where.id);
      if (!existing) {
        throw new Error(`User ${args.where.id} not found`);
      }
      if (args.data.passwordHash !== undefined) {
        existing.passwordHash = args.data.passwordHash;
      }
      if (args.data.isVerified !== undefined) {
        existing.isVerified = args.data.isVerified;
      }
      existing.updatedAt = new Date();
      return this.hydrateUser(existing, args.include);
    },
  };

  readonly profile = {
    create: async (args: {
      data: { userId: string; displayName: string; avatar?: string | null };
    }) => {
      const row: InMemoryProfileRow = {
        id: randomUUID(),
        userId: args.data.userId,
        displayName: args.data.displayName,
        avatar: args.data.avatar ?? null,
      };
      this.profiles.set(row.id, row);
      return row;
    },
  };

  readonly passwordResetToken = {
    findUnique: async (args: {
      where: { tokenHash: string };
      include?: { user?: boolean };
    }) => {
      for (const row of this.resetTokens.values()) {
        if (row.tokenHash === args.where.tokenHash) {
          return {
            ...row,
            ...(args.include?.user
              ? { user: this.users.get(row.userId) ?? null }
              : {}),
          };
        }
      }
      return null;
    },

    create: async (args: {
      data: { userId: string; tokenHash: string; expiresAt: Date };
    }) => {
      for (const existing of this.resetTokens.values()) {
        if (existing.tokenHash === args.data.tokenHash) {
          throw Object.assign(new Error('Unique constraint on tokenHash'), {
            code: 'P2002',
          });
        }
      }
      const row: InMemoryResetTokenRow = {
        id: randomUUID(),
        userId: args.data.userId,
        tokenHash: args.data.tokenHash,
        expiresAt: args.data.expiresAt,
        usedAt: null,
        createdAt: new Date(),
      };
      this.resetTokens.set(row.id, row);
      return { ...row };
    },

    updateMany: async (args: {
      where: {
        userId?: string;
        tokenHash?: string;
        usedAt?: null;
        expiresAt?: { gt: Date };
      };
      data: { usedAt: Date };
    }) => {
      let count = 0;
      for (const row of this.resetTokens.values()) {
        if (args.where.userId && row.userId !== args.where.userId) continue;
        if (args.where.tokenHash && row.tokenHash !== args.where.tokenHash) {
          continue;
        }
        if (args.where.usedAt === null && row.usedAt !== null) continue;
        if (
          args.where.expiresAt?.gt &&
          row.expiresAt.getTime() <= args.where.expiresAt.gt.getTime()
        ) {
          continue;
        }
        row.usedAt = args.data.usedAt;
        count += 1;
      }
      return { count };
    },
  };

  readonly oAuthAccount = {
    findUnique: async (args: {
      where: {
        provider_providerUserId?: {
          provider: OAuthProvider;
          providerUserId: string;
        };
      };
      include?: { user?: { include?: Record<string, unknown> } };
    }) => {
      const key = args.where.provider_providerUserId;
      if (!key) return null;

      for (const row of this.oauthAccounts.values()) {
        if (
          row.provider === key.provider &&
          row.providerUserId === key.providerUserId
        ) {
          const user = this.users.get(row.userId);
          return {
            ...row,
            ...(args.include?.user
              ? {
                  user: user
                    ? this.hydrateUser(user, args.include.user.include)
                    : null,
                }
              : {}),
          };
        }
      }
      return null;
    },

    create: async (args: {
      data: {
        userId: string;
        provider: OAuthProvider;
        providerUserId: string;
        email?: string | null;
      };
    }) => {
      for (const existing of this.oauthAccounts.values()) {
        if (
          existing.provider === args.data.provider &&
          existing.providerUserId === args.data.providerUserId
        ) {
          throw Object.assign(
            new Error('Unique constraint on provider+providerUserId'),
            { code: 'P2002' },
          );
        }
      }

      const now = new Date();
      const row: InMemoryOAuthAccountRow = {
        id: randomUUID(),
        userId: args.data.userId,
        provider: args.data.provider,
        providerUserId: args.data.providerUserId,
        email: args.data.email ?? null,
        createdAt: now,
        updatedAt: now,
      };
      this.oauthAccounts.set(row.id, row);
      return { ...row };
    },

    update: async (args: {
      where: { id: string };
      data: { email?: string | null };
    }) => {
      const existing = this.oauthAccounts.get(args.where.id);
      if (!existing) {
        throw new Error(`OAuthAccount ${args.where.id} not found`);
      }
      if (args.data.email !== undefined) {
        existing.email = args.data.email;
      }
      existing.updatedAt = new Date();
      return { ...existing };
    },
  };

  async $transaction<T>(fn: (tx: StatefulInMemoryPrisma) => Promise<T>): Promise<T> {
    return fn(this);
  }
}

function extractTokenFromResetMail(text: string): string {
  const match = text.match(/token=([a-zA-Z0-9_-]+)/);
  if (!match) {
    throw new Error(`Reset token not found in email text: ${text}`);
  }
  return decodeURIComponent(match[1]);
}

describe('M1-backend-auth — Password Reset, OAuth, Error Codes & Refresh DTO', () => {
  let app: INestApplication;
  let prisma: StatefulInMemoryPrisma;
  let mailTransport: InMemoryTestMailTransport;
  let mailService: MailService;
  let mockGoogleVerifier: jest.Mocked<GoogleOAuthVerifier>;
  let mockFacebookVerifier: jest.Mocked<FacebookOAuthVerifier>;

  const originalNodeEnv = process.env.NODE_ENV;
  const originalJwtSecret = process.env.JWT_SECRET;
  const originalJwtRefreshSecret = process.env.JWT_REFRESH_SECRET;
  const originalSmtpHost = process.env.SMTP_HOST;

  beforeAll(async () => {
    process.env.NODE_ENV = 'test';
    process.env.JWT_SECRET = TEST_JWT_ACCESS_SECRET;
    process.env.JWT_REFRESH_SECRET = TEST_JWT_REFRESH_SECRET;
    delete process.env.SMTP_HOST;

    prisma = new StatefulInMemoryPrisma();
    mockGoogleVerifier = {
      verifyIdToken: jest.fn(),
    };
    mockFacebookVerifier = {
      verifyAccessToken: jest.fn(),
    };

    const moduleRef: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({
              NODE_ENV: 'test',
              SMTP_HOST: '',
              APP_RESET_PASSWORD_URL: 'https://wanderai.test/reset-password',
              JWT_SECRET: TEST_JWT_ACCESS_SECRET,
              JWT_REFRESH_SECRET: TEST_JWT_REFRESH_SECRET,
            }),
          ],
          validate: (env) =>
            validateEnvironmentJwtConfig({
              ...env,
              JWT_SECRET: TEST_JWT_ACCESS_SECRET,
              JWT_REFRESH_SECRET: TEST_JWT_REFRESH_SECRET,
            }),
        }),
        PrismaModule,
        MailModule,
        AuthModule,
      ],
    })
      .overrideProvider(PrismaService)
      .useValue(prisma)
      .overrideProvider(GOOGLE_OAUTH_VERIFIER)
      .useValue(mockGoogleVerifier)
      .overrideProvider(FACEBOOK_OAUTH_VERIFIER)
      .useValue(mockFacebookVerifier)
      .compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        transform: true,
        forbidNonWhitelisted: true,
      }),
    );
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();

    mailTransport = moduleRef.get(InMemoryTestMailTransport);
    mailService = moduleRef.get(MailService);
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
    if (originalNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = originalNodeEnv;
    if (originalJwtSecret === undefined) delete process.env.JWT_SECRET;
    else process.env.JWT_SECRET = originalJwtSecret;
    if (originalJwtRefreshSecret === undefined)
      delete process.env.JWT_REFRESH_SECRET;
    else process.env.JWT_REFRESH_SECRET = originalJwtRefreshSecret;
    if (originalSmtpHost === undefined) delete process.env.SMTP_HOST;
    else process.env.SMTP_HOST = originalSmtpHost;
  });

  beforeEach(() => {
    prisma.clear();
    mailTransport.clear();
    jest.restoreAllMocks();
    mockGoogleVerifier.verifyIdToken.mockReset();
    mockFacebookVerifier.verifyAccessToken.mockReset();
  });

  describe('1. HttpExceptionFilter, Error Codes & RefreshTokenDto', () => {
    it('emits canonical errorCode on register duplicate & invalid login while keeping backward-compatible error shape', async () => {
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'traveler@wanderai.test',
          password: 'Password123!',
          name: 'Traveler',
        })
        .expect(201);

      const dupRes = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'traveler@wanderai.test',
          password: 'Password123!',
          name: 'Duplicate',
        })
        .expect(400);

      expect(dupRes.body).toMatchObject({
        success: false,
        statusCode: 400,
        errorCode: AUTH_ERROR_CODES.EMAIL_ALREADY_EXISTS,
        message: 'Email đã được sử dụng',
        path: '/auth/register',
      });

      const badLoginRes = await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: 'traveler@wanderai.test',
          password: 'WrongPassword!',
        })
        .expect(401);

      expect(badLoginRes.body).toMatchObject({
        success: false,
        statusCode: 401,
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
        message: 'Email hoặc mật khẩu không đúng',
        path: '/auth/login',
      });

      // Validation errors (no custom errorCode) omit errorCode while keeping exact error envelope
      const validationRes = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'not-an-email', password: '123' })
        .expect(400);

      expect(validationRes.body.success).toBe(false);
      expect(validationRes.body.statusCode).toBe(400);
      expect(typeof validationRes.body.message).toBe('string');
      expect(validationRes.body.errorCode).toBeUndefined();
    });

    it('validates POST /auth/refresh via RefreshTokenDto (400 empty/missing/extra fields, 200 valid, 401 invalid)', async () => {
      const regRes = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'refresh@wanderai.test',
          password: 'Password123!',
          name: 'Refresh User',
        })
        .expect(201);

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({})
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: '' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({
          refresh_token: regRes.body.data.refresh_token,
          unexpectedField: true,
        })
        .expect(400);

      const okRes = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: regRes.body.data.refresh_token })
        .expect(200);

      expect(okRes.body).toMatchObject({
        success: true,
        data: {
          access_token: expect.any(String),
          refresh_token: expect.any(String),
        },
      });

      const badTokenRes = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: 'invalid.jwt.token' })
        .expect(401);

      expect(badTokenRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      );
    });
  });

  describe('2. Password Reset Flow (/auth/forgot-password, /reset-password/validate, /reset-password)', () => {
    it('returns non-enumerating responses, stores SHA-256 hash only, revokes prior tokens, and completes single-use reset', async () => {
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'halong.visitor@wanderai.test',
          password: 'OldPassword123!',
          name: 'Ha Long Visitor',
        })
        .expect(201);

      const unknownRes = await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'nobody@wanderai.test' })
        .expect(200);

      const firstForgotRes = await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'HaLong.Visitor@wanderai.test' })
        .expect(200);

      expect(unknownRes.body.data).toEqual(firstForgotRes.body.data);
      expect(firstForgotRes.body.data).toEqual({
        sent: true,
        message:
          'Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi.',
        expiresInMinutes: 30,
      });

      const firstMail = mailTransport.getLastMessageFor(
        'halong.visitor@wanderai.test',
      );
      expect(firstMail).toBeDefined();
      const firstRawToken = extractTokenFromResetMail(firstMail!.text);
      const firstTokenHash = createHash('sha256')
        .update(firstRawToken)
        .digest('hex');

      // Raw token is never stored in DB; only SHA-256 digest is persisted
      const storedRows = Array.from(prisma.resetTokens.values());
      expect(storedRows).toHaveLength(1);
      expect(storedRows[0].tokenHash).toBe(firstTokenHash);
      expect(storedRows[0].tokenHash).not.toBe(firstRawToken);

      // Requesting a second reset revokes the prior unused token
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'halong.visitor@wanderai.test' })
        .expect(200);

      const secondMail = mailTransport.getLastMessageFor(
        'halong.visitor@wanderai.test',
      );
      const secondRawToken = extractTokenFromResetMail(secondMail!.text);
      expect(secondRawToken).not.toBe(firstRawToken);

      const revokedValidateRes = await request(app.getHttpServer())
        .get('/auth/reset-password/validate')
        .query({ token: firstRawToken })
        .expect(400);
      expect(revokedValidateRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_USED,
      );

      const validRes = await request(app.getHttpServer())
        .get('/auth/reset-password/validate')
        .query({ token: secondRawToken })
        .expect(200);
      expect(validRes.body.data).toMatchObject({
        valid: true,
        expiresAt: expect.any(String),
      });

      // Short password validation fails without consuming token
      await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: secondRawToken, newPassword: '123' })
        .expect(400);

      // Valid reset succeeds and allows login with new password
      const resetRes = await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: secondRawToken, newPassword: 'NewStrongPassword123!' })
        .expect(200);

      expect(resetRes.body.data).toEqual({
        reset: true,
        message: 'Đặt lại mật khẩu thành công.',
      });

      await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: 'halong.visitor@wanderai.test',
          password: 'OldPassword123!',
        })
        .expect(401);

      await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: 'halong.visitor@wanderai.test',
          password: 'NewStrongPassword123!',
        })
        .expect(200);

      // Replay fails with RESET_TOKEN_USED
      const replayRes = await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: secondRawToken, newPassword: 'AnotherPassword123!' })
        .expect(400);
      expect(replayRes.body.errorCode).toBe(AUTH_ERROR_CODES.RESET_TOKEN_USED);
    });

    it('rejects missing, invalid, and expired tokens with canonical errorCodes and enforces atomic single-use under concurrency', async () => {
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'concurrent@wanderai.test',
          password: 'InitialPassword123!',
          name: 'Concurrent User',
        })
        .expect(201);

      const missingQueryRes = await request(app.getHttpServer())
        .get('/auth/reset-password/validate')
        .expect(400);
      expect(missingQueryRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      );

      const invalidValidateRes = await request(app.getHttpServer())
        .get('/auth/reset-password/validate')
        .query({ token: 'nonexistent-token-abc' })
        .expect(400);
      expect(invalidValidateRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      );

      const invalidPostRes = await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({
          token: 'nonexistent-token-abc',
          newPassword: 'ValidPassword123!',
        })
        .expect(400);
      expect(invalidPostRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_INVALID,
      );

      // Request token and force expiry in DB
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'concurrent@wanderai.test' })
        .expect(200);

      const expiredRaw = extractTokenFromResetMail(
        mailTransport.getLastMessageFor('concurrent@wanderai.test')!.text,
      );
      for (const row of prisma.resetTokens.values()) {
        row.expiresAt = new Date(Date.now() - 60_000);
      }

      const expiredValidateRes = await request(app.getHttpServer())
        .get('/auth/reset-password/validate')
        .query({ token: expiredRaw })
        .expect(400);
      expect(expiredValidateRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_EXPIRED,
      );

      const expiredPostRes = await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: expiredRaw, newPassword: 'ValidPassword123!' })
        .expect(400);
      expect(expiredPostRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.RESET_TOKEN_EXPIRED,
      );

      // Fresh token under concurrent reset attempts: exactly 1 succeeds, 1 gets RESET_TOKEN_USED
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'concurrent@wanderai.test' })
        .expect(200);
      const freshRaw = extractTokenFromResetMail(
        mailTransport.getLastMessageFor('concurrent@wanderai.test')!.text,
      );

      const [resA, resB] = await Promise.all([
        request(app.getHttpServer())
          .post('/auth/reset-password')
          .send({ token: freshRaw, newPassword: 'ConcurrentPasswordA!' }),
        request(app.getHttpServer())
          .post('/auth/reset-password')
          .send({ token: freshRaw, newPassword: 'ConcurrentPasswordB!' }),
      ]);

      const statuses = [resA.status, resB.status].sort((a, b) => a - b);
      expect(statuses).toEqual([200, 400]);
      const failedRes = resA.status === 400 ? resA : resB;
      expect(failedRes.body.errorCode).toBe(AUTH_ERROR_CODES.RESET_TOKEN_USED);
    });

    it('remains non-enumerating even if MailService fails to dispatch email', async () => {
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'smtpfail@wanderai.test',
          password: 'Password123!',
          name: 'SMTP Fail User',
        })
        .expect(201);

      jest
        .spyOn(mailService, 'sendPasswordResetEmail')
        .mockRejectedValueOnce(new Error('SMTP connection timeout'));

      const res = await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'smtpfail@wanderai.test' })
        .expect(200);

      expect(res.body.data).toEqual({
        sent: true,
        message:
          'Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được gửi.',
        expiresInMinutes: 30,
      });
    });
  });

  describe('3. Google & Facebook OAuth Flows (/auth/oauth/google & /auth/oauth/facebook)', () => {
    it('creates passwordless user on first Google login, links Facebook by email, and guards password login with 401 INVALID_CREDENTIALS', async () => {
      const googleIdentity: VerifiedOAuthIdentity = {
        provider: OAuthProvider.GOOGLE,
        providerUserId: 'google-sub-12345',
        email: 'OAuth.Traveler@wanderai.test',
        emailVerified: true,
        name: 'OAuth Traveler',
        avatarUrl: 'https://example.com/avatar.jpg',
      };
      mockGoogleVerifier.verifyIdToken.mockResolvedValue(googleIdentity);

      const firstGoogleRes = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'valid-google-id-token' })
        .expect(200);

      expect(firstGoogleRes.body.success).toBe(true);
      expect(firstGoogleRes.body.data).toMatchObject({
        access_token: expect.any(String),
        refresh_token: expect.any(String),
        user: {
          id: expect.any(String),
          email: 'oauth.traveler@wanderai.test',
          name: 'OAuth Traveler',
          role: 'USER',
          isVerified: true,
          providers: ['google'],
        },
      });

      const createdUserId = firstGoogleRes.body.data.user.id;
      const storedUser = prisma.users.get(createdUserId);
      expect(storedUser?.passwordHash).toBeNull();

      // CRITICAL: Password login on a passwordless OAuth account must return 401 INVALID_CREDENTIALS, never 500 TypeError
      const passwordAttemptRes = await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: 'oauth.traveler@wanderai.test',
          password: 'AnyPassword123!',
        })
        .expect(401);

      expect(passwordAttemptRes.body).toMatchObject({
        success: false,
        statusCode: 401,
        errorCode: AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      });

      // Subsequent Google login reuses the exact same user
      const secondGoogleRes = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'valid-google-id-token-2' })
        .expect(200);

      expect(secondGoogleRes.body.data.user.id).toBe(createdUserId);
      expect(prisma.users.size).toBe(1);

      // Cross-provider Facebook login with same verified email links FACEBOOK onto the same user
      mockFacebookVerifier.verifyAccessToken.mockResolvedValue({
        provider: OAuthProvider.FACEBOOK,
        providerUserId: 'fb-uid-67890',
        email: 'oauth.traveler@wanderai.test',
        emailVerified: true,
        name: 'OAuth Traveler FB',
      });

      const fbRes = await request(app.getHttpServer())
        .post('/auth/oauth/facebook')
        .send({ accessToken: 'valid-fb-access-token' })
        .expect(200);

      expect(fbRes.body.data.user).toMatchObject({
        id: createdUserId,
        email: 'oauth.traveler@wanderai.test',
        providers: ['facebook', 'google'],
      });
      expect(prisma.users.size).toBe(1);
      expect(prisma.oauthAccounts.size).toBe(2);

      // Passwordless user can later set a password via forgot/reset-password and then use password login
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'oauth.traveler@wanderai.test' })
        .expect(200);
      const rawToken = extractTokenFromResetMail(
        mailTransport.getLastMessageFor('oauth.traveler@wanderai.test')!.text,
      );
      await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: rawToken, newPassword: 'AddedPassword123!' })
        .expect(200);
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: 'oauth.traveler@wanderai.test',
          password: 'AddedPassword123!',
        })
        .expect(200);
    });

    it('maps invalid token, missing email, provider outages, and soft-deleted accounts to canonical errorCodes', async () => {
      await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: '' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/oauth/facebook')
        .send({})
        .expect(400);

      mockGoogleVerifier.verifyIdToken.mockRejectedValueOnce(
        new UnauthorizedException({
          message: 'Mã xác thực Google không hợp lệ hoặc đã hết hạn.',
          errorCode: AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
        }),
      );
      const invalidGoogleRes = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'bad-token' })
        .expect(401);
      expect(invalidGoogleRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.OAUTH_TOKEN_INVALID,
      );

      mockFacebookVerifier.verifyAccessToken.mockRejectedValueOnce(
        new BadRequestException({
          message: 'Tài khoản Facebook chưa cấp quyền truy cập email.',
          errorCode: AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
        }),
      );
      const noEmailFbRes = await request(app.getHttpServer())
        .post('/auth/oauth/facebook')
        .send({ accessToken: 'no-email-token' })
        .expect(400);
      expect(noEmailFbRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
      );

      // Defense-in-depth inside OAuthService if verifier returns null email
      mockGoogleVerifier.verifyIdToken.mockResolvedValueOnce({
        provider: OAuthProvider.GOOGLE,
        providerUserId: 'google-no-email',
        email: null,
        emailVerified: false,
      });
      const serviceEmailGuardRes = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'no-email-google' })
        .expect(400);
      expect(serviceEmailGuardRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.OAUTH_EMAIL_UNAVAILABLE,
      );

      mockFacebookVerifier.verifyAccessToken.mockRejectedValueOnce(
        new BadGatewayException({
          message: 'Không thể kết nối tới máy chủ xác thực Facebook.',
          errorCode: AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
        }),
      );
      const outageRes = await request(app.getHttpServer())
        .post('/auth/oauth/facebook')
        .send({ accessToken: 'timeout-token' })
        .expect(502);
      expect(outageRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.OAUTH_PROVIDER_ERROR,
      );

      // Soft-deleted user cannot log in via OAuth
      await prisma.user.create({
        data: {
          email: 'deleted.oauth@wanderai.test',
          passwordHash: null,
          deletedAt: new Date('2026-11-01T00:00:00.000Z'),
        },
      });
      mockGoogleVerifier.verifyIdToken.mockResolvedValueOnce({
        provider: OAuthProvider.GOOGLE,
        providerUserId: 'google-deleted-sub',
        email: 'deleted.oauth@wanderai.test',
        emailVerified: true,
      });
      const deletedRes = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'deleted-user-token' })
        .expect(401);
      expect(deletedRes.body.errorCode).toBe(
        AUTH_ERROR_CODES.INVALID_CREDENTIALS,
      );
    });
  });

  describe('4. HttpGoogleOAuthVerifier & HttpFacebookOAuthVerifier Unit Tests (Mocked Axios)', () => {
    it('HttpGoogleOAuthVerifier verifies audience, expiry, email_verified, and maps upstream errors', async () => {
      const unconfigured = new HttpGoogleOAuthVerifier(new ConfigService({}));
      await expect(unconfigured.verifyIdToken('token')).rejects.toThrow(
        BadGatewayException,
      );

      const verifier = new HttpGoogleOAuthVerifier(
        new ConfigService({
          GOOGLE_ANDROID_CLIENT_ID: 'android-client-1.apps.googleusercontent.com',
          GOOGLE_WEB_CLIENT_ID: 'web-client-1.apps.googleusercontent.com',
        }),
      );

      const futureExp = Math.floor(Date.now() / 1000) + 3600;
      const getSpy = jest.spyOn(axios, 'get').mockResolvedValueOnce({
        data: {
          sub: 'g-101',
          aud: 'android-client-1.apps.googleusercontent.com',
          exp: String(futureExp),
          email: 'halong@gmail.com',
          email_verified: 'true',
          name: 'Ha Long Guide',
          picture: 'https://lh3.googleusercontent.com/avatar.png',
        },
      });

      const identity = await verifier.verifyIdToken('good-id-token');
      expect(identity).toEqual({
        provider: OAuthProvider.GOOGLE,
        providerUserId: 'g-101',
        email: 'halong@gmail.com',
        emailVerified: true,
        name: 'Ha Long Guide',
        avatarUrl: 'https://lh3.googleusercontent.com/avatar.png',
      });

      // Audience mismatch -> 401 OAUTH_TOKEN_INVALID
      getSpy.mockResolvedValueOnce({
        data: {
          sub: 'g-101',
          aud: 'evil-client.apps.googleusercontent.com',
          exp: String(futureExp),
          email: 'halong@gmail.com',
          email_verified: true,
        },
      });
      await expect(verifier.verifyIdToken('wrong-aud')).rejects.toThrow(
        UnauthorizedException,
      );

      // Expired token -> 401 OAUTH_TOKEN_INVALID
      getSpy.mockResolvedValueOnce({
        data: {
          sub: 'g-101',
          aud: 'web-client-1.apps.googleusercontent.com',
          exp: String(Math.floor(Date.now() / 1000) - 60),
          email: 'halong@gmail.com',
          email_verified: true,
        },
      });
      await expect(verifier.verifyIdToken('expired')).rejects.toThrow(
        UnauthorizedException,
      );

      // Unverified email -> 400 OAUTH_EMAIL_UNAVAILABLE
      getSpy.mockResolvedValueOnce({
        data: {
          sub: 'g-101',
          aud: 'web-client-1.apps.googleusercontent.com',
          exp: String(futureExp),
          email: 'halong@gmail.com',
          email_verified: 'false',
        },
      });
      await expect(verifier.verifyIdToken('unverified-email')).rejects.toThrow(
        BadRequestException,
      );

      // Axios 400 -> 401 OAUTH_TOKEN_INVALID; network error -> 502 OAUTH_PROVIDER_ERROR
      getSpy.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 400, data: { error_description: 'Invalid Value' } },
      });
      await expect(verifier.verifyIdToken('google-400')).rejects.toThrow(
        UnauthorizedException,
      );

      getSpy.mockRejectedValueOnce(new Error('ECONNRESET'));
      await expect(verifier.verifyIdToken('network-down')).rejects.toThrow(
        BadGatewayException,
      );
    });

    it('HttpFacebookOAuthVerifier verifies debug_token + /me and maps Graph errors', async () => {
      const unconfigured = new HttpFacebookOAuthVerifier(new ConfigService({}));
      await expect(unconfigured.verifyAccessToken('fb-token')).rejects.toThrow(
        BadGatewayException,
      );

      const verifier = new HttpFacebookOAuthVerifier(
        new ConfigService({
          FACEBOOK_APP_ID: '1234567890',
          FACEBOOK_APP_SECRET: 'fb-secret-xyz',
        }),
      );

      const getSpy = jest
        .spyOn(axios, 'get')
        .mockResolvedValueOnce({
          data: {
            data: {
              app_id: '1234567890',
              is_valid: true,
              user_id: 'fb-user-42',
            },
          },
        })
        .mockResolvedValueOnce({
          data: {
            id: 'fb-user-42',
            name: 'Ha Long Explorer',
            email: 'explorer@fb.test',
            picture: { data: { url: 'https://graph.facebook.com/pic.jpg' } },
          },
        });

      const identity = await verifier.verifyAccessToken('valid-fb-token');
      expect(identity).toEqual({
        provider: OAuthProvider.FACEBOOK,
        providerUserId: 'fb-user-42',
        email: 'explorer@fb.test',
        emailVerified: true,
        name: 'Ha Long Explorer',
        avatarUrl: 'https://graph.facebook.com/pic.jpg',
      });

      // Invalid debug_token (is_valid=false) -> 401
      getSpy.mockResolvedValueOnce({
        data: { data: { app_id: '1234567890', is_valid: false } },
      });
      await expect(verifier.verifyAccessToken('invalid-fb')).rejects.toThrow(
        UnauthorizedException,
      );

      // Missing email on /me -> 400 OAUTH_EMAIL_UNAVAILABLE
      getSpy
        .mockResolvedValueOnce({
          data: {
            data: {
              app_id: '1234567890',
              is_valid: true,
              user_id: 'fb-user-43',
            },
          },
        })
        .mockResolvedValueOnce({
          data: {
            id: 'fb-user-43',
            name: 'No Email User',
          },
        });
      await expect(verifier.verifyAccessToken('no-email-fb')).rejects.toThrow(
        BadRequestException,
      );

      // Graph error 190 -> 401; network error -> 502
      getSpy.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 400, data: { error: { code: 190 } } },
      });
      await expect(verifier.verifyAccessToken('revoked-fb')).rejects.toThrow(
        UnauthorizedException,
      );

      getSpy.mockRejectedValueOnce(new Error('ETIMEDOUT'));
      await expect(verifier.verifyAccessToken('timeout-fb')).rejects.toThrow(
        BadGatewayException,
      );
    });
  });

  describe('5. DTO Whitespace Trimming & OAuth Race Hardening', () => {
    it('trims email and name on register, forgot-password, and login without trimming passwords', async () => {
      const regRes = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: '  Alice+Test@Example.COM  ',
          password: 'Password123!',
          name: '  Alice Nguyen  ',
        })
        .expect(201);

      expect(regRes.body).toMatchObject({
        success: true,
        data: {
          access_token: expect.any(String),
          refresh_token: expect.any(String),
        },
      });

      const storedUser = await prisma.user.findUnique({
        where: { email: 'alice+test@example.com' },
        include: { profile: true },
      });
      expect(storedUser).not.toBeNull();
      expect(storedUser!.email).toBe('alice+test@example.com');
      expect(storedUser!.profile?.displayName).toBe('Alice Nguyen');

      // Duplicate check still triggers after trimming email
      const dupRes = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: '  ALICE+TEST@example.com ',
          password: 'Password123!',
          name: 'Alice Duplicate',
        })
        .expect(400);
      expect(dupRes.body.errorCode).toBe(AUTH_ERROR_CODES.EMAIL_ALREADY_EXISTS);

      // Forgot-password with padded mixed-case email delivers reset mail to canonical address
      const forgotRes = await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: '  ALICE+Test@example.com  ' })
        .expect(200);
      expect(forgotRes.body.data.sent).toBe(true);

      const resetMail = mailTransport.getLastMessageFor(
        'alice+test@example.com',
      );
      expect(resetMail).toBeDefined();
      expect(resetMail!.to).toBe('alice+test@example.com');

      // Login with padded mixed-case email succeeds
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: '  alice+test@EXAMPLE.com  ',
          password: 'Password123!',
        })
        .expect(200);

      // Passwords must NOT be trimmed
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({
          email: '  alice+test@EXAMPLE.com  ',
          password: ' Password123! ',
        })
        .expect(401);
    });

    it('rejects whitespace-only name and whitespace-only tokens with 400', async () => {
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'valid@example.com',
          password: 'password123',
          name: '   ',
        })
        .expect(400);

      expect(prisma.users.size).toBe(0);

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: '   ' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/reset-password')
        .send({ token: '   ', newPassword: 'ValidPassword123!' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: '   ' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/auth/oauth/facebook')
        .send({ accessToken: '   ' })
        .expect(400);

      expect(mockGoogleVerifier.verifyIdToken).not.toHaveBeenCalled();
      expect(mockFacebookVerifier.verifyAccessToken).not.toHaveBeenCalled();
    });

    it('handles secondary P2002 race inside OAuth user creation fallback cleanly', async () => {
      const existing = await prisma.user.create({
        data: {
          email: 'race.oauth@wanderai.test',
          passwordHash: null,
          isVerified: true,
          profile: { create: { displayName: 'Race User' } },
        },
        include: { profile: true, oauthAccounts: true },
      });

      // Simulate user.create losing a race (P2002) and subsequent oAuthAccount.create also losing a race (P2002)
      const txSpy = jest
        .spyOn(prisma, '$transaction')
        .mockImplementationOnce(async () => {
          throw Object.assign(new Error('Unique constraint on email'), {
            code: 'P2002',
          });
        })
        .mockImplementationOnce(async () => {
          await prisma.oAuthAccount.create({
            data: {
              userId: existing.id,
              provider: OAuthProvider.GOOGLE,
              providerUserId: 'google-race-sub',
              email: 'race.oauth@wanderai.test',
            },
          });
          throw Object.assign(new Error('Unique constraint on provider'), {
            code: 'P2002',
          });
        });

      const findByEmailSpy = jest
        .spyOn(prisma.user, 'findUnique')
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce(existing);

      mockGoogleVerifier.verifyIdToken.mockResolvedValueOnce({
        provider: OAuthProvider.GOOGLE,
        providerUserId: 'google-race-sub',
        email: 'race.oauth@wanderai.test',
        emailVerified: true,
        name: 'Race User',
      });

      const res = await request(app.getHttpServer())
        .post('/auth/oauth/google')
        .send({ idToken: 'race-google-token' })
        .expect(200);

      expect(res.body.data.user).toMatchObject({
        id: existing.id,
        email: 'race.oauth@wanderai.test',
        providers: ['google'],
      });
      expect(txSpy).toHaveBeenCalledTimes(2);
      expect(findByEmailSpy).toHaveBeenCalled();
    });
  });
});
