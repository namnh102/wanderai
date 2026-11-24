import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { OAuthProvider } from '@prisma/client';
import * as bcrypt from 'bcryptjs';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { AUTH_ERROR_CODES } from '../src/common/constants/auth-error-codes';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { InMemoryTestMailTransport } from '../src/modules/mail/transports/in-memory-test-mail.transport';
import { MAIL_TRANSPORT } from '../src/modules/mail/transports/mail-transport.interface';
import {
  FACEBOOK_OAUTH_VERIFIER,
  FacebookOAuthVerifier,
  GOOGLE_OAUTH_VERIFIER,
  GoogleOAuthVerifier,
} from '../src/modules/auth/verifiers/oauth-verifier.interface';
import { PrismaService } from '../src/prisma/prisma.service';

describe('Auth Recovery & OAuth (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let mailTransport: InMemoryTestMailTransport;
  let mockGoogleVerifier: jest.Mocked<GoogleOAuthVerifier>;
  let mockFacebookVerifier: jest.Mocked<FacebookOAuthVerifier>;

  const suffix = Date.now();
  const resetEmail = `e2e_reset_${suffix}@wanderai.test`;
  const oauthEmail = `e2e_oauth_${suffix}@wanderai.test`;

  beforeAll(async () => {
    mailTransport = new InMemoryTestMailTransport();
    mockGoogleVerifier = { verifyIdToken: jest.fn() };
    mockFacebookVerifier = { verifyAccessToken: jest.fn() };

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(MAIL_TRANSPORT)
      .useValue(mailTransport)
      .overrideProvider(GOOGLE_OAUTH_VERIFIER)
      .useValue(mockGoogleVerifier)
      .overrideProvider(FACEBOOK_OAUTH_VERIFIER)
      .useValue(mockFacebookVerifier)
      .compile();

    app = moduleFixture.createNestApplication();
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

    prisma = app.get(PrismaService);
    const hash = await bcrypt.hash('OldE2EPass123!', 12);
    await prisma.user.create({
      data: {
        email: resetEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'E2E Reset User' } },
      },
    });
  });

  afterAll(async () => {
    for (const email of [resetEmail, oauthEmail]) {
      const user = await prisma.user.findUnique({ where: { email } });
      if (user) {
        await prisma.user.delete({ where: { id: user.id } });
      }
    }
    await app.close();
  });

  it('completes real-DB password reset lifecycle and rejects token replay', async () => {
    await request(app.getHttpServer())
      .post('/auth/forgot-password')
      .send({ email: resetEmail })
      .expect(200);

    const mail = mailTransport.getLastMessageFor(resetEmail);
    expect(mail).toBeDefined();
    const match = mail!.text.match(/token=([a-zA-Z0-9_-]+)/);
    expect(match).toBeTruthy();
    const rawToken = decodeURIComponent(match![1]);

    await request(app.getHttpServer())
      .get('/auth/reset-password/validate')
      .query({ token: rawToken })
      .expect(200);

    await request(app.getHttpServer())
      .post('/auth/reset-password')
      .send({ token: rawToken, newPassword: 'NewE2EPass123!' })
      .expect(200);

    await request(app.getHttpServer())
      .post('/auth/login')
      .send({ email: resetEmail, password: 'NewE2EPass123!' })
      .expect(200);

    const replayRes = await request(app.getHttpServer())
      .post('/auth/reset-password')
      .send({ token: rawToken, newPassword: 'AnotherE2EPass123!' })
      .expect(400);
    expect(replayRes.body.errorCode).toBe(AUTH_ERROR_CODES.RESET_TOKEN_USED);
  });

  it('persists passwordless Google + linked Facebook OAuth user in PostgreSQL and guards password login', async () => {
    mockGoogleVerifier.verifyIdToken.mockResolvedValueOnce({
      provider: OAuthProvider.GOOGLE,
      providerUserId: `e2e-google-${suffix}`,
      email: oauthEmail,
      emailVerified: true,
      name: 'E2E OAuth User',
    });

    const googleRes = await request(app.getHttpServer())
      .post('/auth/oauth/google')
      .send({ idToken: 'e2e-google-token' })
      .expect(200);

    expect(googleRes.body.data.user.providers).toEqual(['google']);

    const passwordLoginRes = await request(app.getHttpServer())
      .post('/auth/login')
      .send({ email: oauthEmail, password: 'SomePassword123!' })
      .expect(401);
    expect(passwordLoginRes.body.errorCode).toBe(
      AUTH_ERROR_CODES.INVALID_CREDENTIALS,
    );

    mockFacebookVerifier.verifyAccessToken.mockResolvedValueOnce({
      provider: OAuthProvider.FACEBOOK,
      providerUserId: `e2e-fb-${suffix}`,
      email: oauthEmail,
      emailVerified: true,
      name: 'E2E OAuth User',
    });

    const fbRes = await request(app.getHttpServer())
      .post('/auth/oauth/facebook')
      .send({ accessToken: 'e2e-fb-token' })
      .expect(200);

    expect(fbRes.body.data.user.id).toBe(googleRes.body.data.user.id);
    expect(fbRes.body.data.user.providers).toEqual(['facebook', 'google']);
  });
});
