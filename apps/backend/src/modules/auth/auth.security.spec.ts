import {
  Controller,
  Get,
  INestApplication,
  InternalServerErrorException,
  UnauthorizedException,
  UseGuards,
  ValidationPipe,
} from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { Test, TestingModule } from '@nestjs/testing';
import { randomBytes } from 'crypto';
import * as bcrypt from 'bcryptjs';
import * as request from 'supertest';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { HttpExceptionFilter } from '../../common/filters/http-exception.filter';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { TransformInterceptor } from '../../common/interceptors/transform.interceptor';
import { PrismaModule } from '../../prisma/prisma.module';
import { PrismaService } from '../../prisma/prisma.service';
import { AuthModule } from './auth.module';
import { AuthService } from './auth.service';
import {
  getValidatedJwtConfig,
  JwtTokenPayload,
  validateEnvironmentJwtConfig,
  validateJwtSecrets,
} from './jwt-config';
import { JwtStrategy } from './strategies/jwt.strategy';

// Ephemeral per-run dummy test secrets (>=32 chars, high diversity, distinct, never logged).
const TEST_JWT_ACCESS_SECRET = `test-access-${randomBytes(24).toString('hex')}`;
const TEST_JWT_REFRESH_SECRET = `test-refresh-${randomBytes(24).toString('hex')}`;

interface MockUserRecord {
  id: string;
  email: string;
  passwordHash: string;
  deletedAt: Date | null;
  profile?: {
    displayName: string;
  };
}

@Controller('protected-probe')
class ProtectedProbeController {
  @UseGuards(JwtAuthGuard)
  @Get('me')
  getMe(@CurrentUser() user: { id: string; email: string }) {
    return { id: user.id, email: user.email };
  }
}

describe('PROD-AUTH-02A — JWT Fail-Closed Security & Auth Regression Suite', () => {
  describe('1. Startup & Secret Configuration Validation (jwt-config)', () => {
    const originalJwtSecret = process.env.JWT_SECRET;
    const originalJwtRefreshSecret = process.env.JWT_REFRESH_SECRET;

    beforeEach(() => {
      delete process.env.JWT_SECRET;
      delete process.env.JWT_REFRESH_SECRET;
    });

    afterAll(() => {
      if (originalJwtSecret === undefined) {
        delete process.env.JWT_SECRET;
      } else {
        process.env.JWT_SECRET = originalJwtSecret;
      }
      if (originalJwtRefreshSecret === undefined) {
        delete process.env.JWT_REFRESH_SECRET;
      } else {
        process.env.JWT_REFRESH_SECRET = originalJwtRefreshSecret;
      }
    });

    it('T-CFG-01: fails fast when JWT_SECRET or JWT_REFRESH_SECRET is missing or blank', () => {
      expect(() => validateJwtSecrets(undefined, TEST_JWT_REFRESH_SECRET)).toThrow(
        /JWT_SECRET is required/,
      );
      expect(() => validateJwtSecrets('   ', TEST_JWT_REFRESH_SECRET)).toThrow(
        /JWT_SECRET is required/,
      );
      expect(() => validateJwtSecrets(TEST_JWT_ACCESS_SECRET, undefined)).toThrow(
        /JWT_REFRESH_SECRET is required/,
      );
      expect(() => validateJwtSecrets(TEST_JWT_ACCESS_SECRET, '')).toThrow(
        /JWT_REFRESH_SECRET is required/,
      );
      expect(() => validateEnvironmentJwtConfig({})).toThrow(/JWT_SECRET is required/);
    });

    it('T-CFG-02: fails fast when legacy fallback literals or .env.example placeholders are used', () => {
      const disallowedValues = [
        'super-secret',
        'wanderai-dev-jwt-secret-2026',
        'wanderai-dev-refresh-secret-2026',
        'wanderai-jwt-secret-change-in-production',
        'wanderai-refresh-secret-change-in-production',
        '<REPLACE_WITH_STRONG_JWT_SECRET_MIN_32_CHARS>',
        '<REPLACE_WITH_DISTINCT_JWT_REFRESH_SECRET_MIN_32_CHARS>',
      ];

      for (const badValue of disallowedValues) {
        expect(() => validateJwtSecrets(badValue, TEST_JWT_REFRESH_SECRET)).toThrow(
          /disallowed fallback or placeholder/,
        );
        expect(() => validateJwtSecrets(TEST_JWT_ACCESS_SECRET, badValue)).toThrow(
          /disallowed fallback or placeholder/,
        );
      }
    });

    it('T-CFG-03: fails fast when secrets are shorter than 32 chars or lack character diversity', () => {
      expect(() => validateJwtSecrets('short-secret-12345', TEST_JWT_REFRESH_SECRET)).toThrow(
        /at least 32 characters/,
      );
      expect(() => validateJwtSecrets(TEST_JWT_ACCESS_SECRET, 'short-refresh-12345')).toThrow(
        /at least 32 characters/,
      );
      expect(() => validateJwtSecrets('a'.repeat(40), TEST_JWT_REFRESH_SECRET)).toThrow(
        /insufficient character diversity/,
      );
    });

    it('T-CFG-04: fails fast when JWT_SECRET and JWT_REFRESH_SECRET are equal', () => {
      expect(() =>
        validateJwtSecrets(TEST_JWT_ACCESS_SECRET, TEST_JWT_ACCESS_SECRET),
      ).toThrow(/must be distinct/);
    });

    it('T-CFG-05: AuthService and JwtStrategy constructors fail fast on invalid config and succeed on valid config', () => {
      const badConfigService = new ConfigService({
        JWT_SECRET: 'super-secret',
        JWT_REFRESH_SECRET: 'wanderai-dev-refresh-secret-2026',
      });
      const mockPrisma = {
        user: { findUnique: jest.fn(), create: jest.fn() },
      } as unknown as PrismaService;
      const jwtService = new JwtService();

      expect(() => getValidatedJwtConfig(badConfigService)).toThrow();
      expect(() => new AuthService(mockPrisma, jwtService, badConfigService)).toThrow();
      expect(() => new JwtStrategy(badConfigService, mockPrisma)).toThrow();

      const validConfigService = new ConfigService({
        JWT_SECRET: TEST_JWT_ACCESS_SECRET,
        JWT_REFRESH_SECRET: TEST_JWT_REFRESH_SECRET,
      });

      const validated = getValidatedJwtConfig(validConfigService);
      expect(validated.accessSecret).toBe(TEST_JWT_ACCESS_SECRET);
      expect(validated.refreshSecret).toBe(TEST_JWT_REFRESH_SECRET);
      expect(() => new AuthService(mockPrisma, jwtService, validConfigService)).not.toThrow();
      expect(() => new JwtStrategy(validConfigService, mockPrisma)).not.toThrow();
    });

    it('T-CFG-06: NestJS TestingModule compilation with AuthModule fails fast when secrets are missing or equal', async () => {
      const mockPrisma = {
        user: { findUnique: jest.fn(), create: jest.fn() },
      };

      await expect(
        Test.createTestingModule({
          imports: [
            ConfigModule.forRoot({
              isGlobal: true,
              ignoreEnvFile: true,
              load: [() => ({ JWT_SECRET: '', JWT_REFRESH_SECRET: '' })],
              validate: validateEnvironmentJwtConfig,
            }),
            PrismaModule,
            AuthModule,
          ],
        })
          .overrideProvider(PrismaService)
          .useValue(mockPrisma)
          .compile(),
      ).rejects.toThrow(/JWT_SECRET is required/);

      await expect(
        Test.createTestingModule({
          imports: [
            ConfigModule.forRoot({
              isGlobal: true,
              ignoreEnvFile: true,
              load: [
                () => ({
                  JWT_SECRET: TEST_JWT_ACCESS_SECRET,
                  JWT_REFRESH_SECRET: TEST_JWT_ACCESS_SECRET,
                }),
              ],
              validate: (env) =>
                validateEnvironmentJwtConfig({
                  ...env,
                  JWT_SECRET: TEST_JWT_ACCESS_SECRET,
                  JWT_REFRESH_SECRET: TEST_JWT_ACCESS_SECRET,
                }),
            }),
            PrismaModule,
            AuthModule,
          ],
        })
          .overrideProvider(PrismaService)
          .useValue(mockPrisma)
          .compile(),
      ).rejects.toThrow(/must be distinct/);
    });
  });

  describe('2. JwtStrategy, AuthService & Guard HTTP Integration (Offline Mocked Prisma)', () => {
    let app: INestApplication;
    let authService: AuthService;
    let jwtStrategy: JwtStrategy;
    let jwtService: JwtService;
    let mockUserFindUnique: jest.Mock;
    let mockUserCreate: jest.Mock;

    const activeUserId = '11111111-2222-3333-4444-555555555555';
    const activeUserEmail = 'active.user@wanderai.test';
    const plainPassword = 'CorrectHorseBatteryStaple!23';
    let activePasswordHash = '';
    const originalJwtSecret = process.env.JWT_SECRET;
    const originalJwtRefreshSecret = process.env.JWT_REFRESH_SECRET;

    beforeAll(async () => {
      process.env.JWT_SECRET = TEST_JWT_ACCESS_SECRET;
      process.env.JWT_REFRESH_SECRET = TEST_JWT_REFRESH_SECRET;
      activePasswordHash = await bcrypt.hash(plainPassword, 10);
      mockUserFindUnique = jest.fn();
      mockUserCreate = jest.fn();

      const mockPrismaService = {
        user: {
          findUnique: mockUserFindUnique,
          create: mockUserCreate,
        },
      };

      const moduleRef: TestingModule = await Test.createTestingModule({
        imports: [
          ConfigModule.forRoot({
            isGlobal: true,
            ignoreEnvFile: true,
            load: [
              () => ({
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
          AuthModule,
        ],
        controllers: [ProtectedProbeController],
      })
        .overrideProvider(PrismaService)
        .useValue(mockPrismaService)
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

      authService = moduleRef.get<AuthService>(AuthService);
      jwtStrategy = moduleRef.get<JwtStrategy>(JwtStrategy);
      jwtService = moduleRef.get<JwtService>(JwtService);
    });

    afterAll(async () => {
      if (app) {
        await app.close();
      }
      if (originalJwtSecret === undefined) {
        delete process.env.JWT_SECRET;
      } else {
        process.env.JWT_SECRET = originalJwtSecret;
      }
      if (originalJwtRefreshSecret === undefined) {
        delete process.env.JWT_REFRESH_SECRET;
      } else {
        process.env.JWT_REFRESH_SECRET = originalJwtRefreshSecret;
      }
    });

    beforeEach(() => {
      jest.clearAllMocks();
    });

    it('T-ACC-01: active user with validly signed access token is authenticated on protected route', async () => {
      const activeUser: MockUserRecord = {
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: null,
      };
      mockUserFindUnique.mockResolvedValue(activeUser);

      const tokens = await authService.login({
        email: activeUserEmail,
        password: plainPassword,
      });

      const res = await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${tokens.access_token}`)
        .expect(200);

      expect(res.body).toMatchObject({
        success: true,
        data: {
          id: activeUserId,
          email: activeUserEmail,
        },
      });
    });

    it('T-ACC-02: expired, malformed, or wrong-secret access tokens are denied with 401', async () => {
      const expiredToken = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'access' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: -10 },
      );
      const wrongSecretToken = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'access' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '15m' },
      );

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${expiredToken}`)
        .expect(401);

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${wrongSecretToken}`)
        .expect(401);

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', 'Bearer malformed.jwt.token')
        .expect(401);

      expect(mockUserFindUnique).not.toHaveBeenCalled();
    });

    it('T-ACC-03: validly signed access token for non-existent user is denied with 401 (no fallback identity)', async () => {
      mockUserFindUnique.mockResolvedValue(null);

      const validTokenForMissingUser = jwtService.sign(
        { sub: 'missing-user-id', email: 'ghost@wanderai.test', type: 'access' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: '15m' },
      );

      await expect(
        jwtStrategy.validate({
          sub: 'missing-user-id',
          email: 'ghost@wanderai.test',
          type: 'access',
        }),
      ).rejects.toThrow(UnauthorizedException);

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${validTokenForMissingUser}`)
        .expect(401);
    });

    it('T-ACC-04: validly signed access token for soft-deleted user (deletedAt != null) is denied with 401', async () => {
      const deletedUser: MockUserRecord = {
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: new Date('2026-11-01T00:00:00.000Z'),
      };
      mockUserFindUnique.mockResolvedValue(deletedUser);

      const validTokenForDeletedUser = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'access' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: '15m' },
      );

      await expect(
        jwtStrategy.validate({
          sub: activeUserId,
          email: activeUserEmail,
          type: 'access',
        }),
      ).rejects.toThrow(UnauthorizedException);

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${validTokenForDeletedUser}`)
        .expect(401);
    });

    it('T-ACC-05: Prisma lookup exception in JwtStrategy.validate fails closed (500) and never fabricates identity', async () => {
      mockUserFindUnique.mockRejectedValue(new Error('Database connection refused'));

      await expect(
        jwtStrategy.validate({
          sub: activeUserId,
          email: activeUserEmail,
          type: 'access',
        }),
      ).rejects.toThrow(InternalServerErrorException);

      const validToken = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'access' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: '15m' },
      );

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(500);
    });

    it('T-ACC-06: refresh token or payload with type="refresh" is rejected by JwtStrategy and JwtAuthGuard with 401', async () => {
      mockUserFindUnique.mockResolvedValue({
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: null,
      });

      await expect(
        jwtStrategy.validate({
          sub: activeUserId,
          email: activeUserEmail,
          type: 'refresh',
        }),
      ).rejects.toThrow(UnauthorizedException);

      const tokenWithRefreshTypeOnAccessSecret = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'refresh' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: '15m' },
      );

      await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${tokenWithRefreshTypeOnAccessSecret}`)
        .expect(401);
    });

    it('T-ACC-07: untyped access token from JwtService.sign({ sub, email }) remains compatible for active users', async () => {
      mockUserFindUnique.mockResolvedValue({
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: null,
      });

      const untypedAccessToken = jwtService.sign({
        sub: activeUserId,
        email: activeUserEmail,
      });

      const res = await request(app.getHttpServer())
        .get('/protected-probe/me')
        .set('Authorization', `Bearer ${untypedAccessToken}`)
        .expect(200);

      expect(res.body.data).toEqual({
        id: activeUserId,
        email: activeUserEmail,
      });
    });

    it('T-REF-01: POST /auth/refresh succeeds for active user and issues new access and refresh tokens', async () => {
      const activeUser: MockUserRecord = {
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: null,
      };
      mockUserFindUnique.mockResolvedValue(activeUser);

      const initialTokens = await authService.login({
        email: activeUserEmail,
        password: plainPassword,
      });

      const res = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: initialTokens.refresh_token })
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(typeof res.body.data.access_token).toBe('string');
      expect(typeof res.body.data.refresh_token).toBe('string');

      const decodedAccess = jwtService.verify<JwtTokenPayload>(res.body.data.access_token, {
        secret: TEST_JWT_ACCESS_SECRET,
      });
      const decodedRefresh = jwtService.verify<JwtTokenPayload>(res.body.data.refresh_token, {
        secret: TEST_JWT_REFRESH_SECRET,
      });

      expect(decodedAccess.sub).toBe(activeUserId);
      expect(decodedAccess.type).toBe('access');
      expect(decodedRefresh.sub).toBe(activeUserId);
      expect(decodedRefresh.type).toBe('refresh');
    });

    it('T-REF-02: refresh rejects non-existent user with 401', async () => {
      const refreshForMissingUser = jwtService.sign(
        { sub: 'non-existent-id', email: 'missing@wanderai.test', type: 'refresh' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '7d' },
      );
      mockUserFindUnique.mockResolvedValue(null);

      await expect(authService.refreshToken(refreshForMissingUser)).rejects.toThrow(
        UnauthorizedException,
      );

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: refreshForMissingUser })
        .expect(401);
    });

    it('T-REF-03: refresh rejects soft-deleted user (deletedAt != null) with 401', async () => {
      const refreshForDeletedUser = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'refresh' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '7d' },
      );
      mockUserFindUnique.mockResolvedValue({
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: new Date('2026-11-05T00:00:00.000Z'),
      });

      await expect(authService.refreshToken(refreshForDeletedUser)).rejects.toThrow(
        UnauthorizedException,
      );

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: refreshForDeletedUser })
        .expect(401);
    });

    it('T-REF-04: refresh rejects malformed, empty, wrong-secret, or expired refresh tokens with 401', async () => {
      const expiredRefresh = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'refresh' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: -10 },
      );
      const wrongSecretRefresh = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'refresh' },
        { secret: TEST_JWT_ACCESS_SECRET, expiresIn: '7d' },
      );

      await expect(authService.refreshToken('')).rejects.toThrow(UnauthorizedException);
      await expect(authService.refreshToken('malformed.token')).rejects.toThrow(
        UnauthorizedException,
      );
      await expect(authService.refreshToken(expiredRefresh)).rejects.toThrow(
        UnauthorizedException,
      );
      await expect(authService.refreshToken(wrongSecretRefresh)).rejects.toThrow(
        UnauthorizedException,
      );

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: expiredRefresh })
        .expect(401);

      expect(mockUserFindUnique).not.toHaveBeenCalled();
    });

    it('T-REF-05: refresh rejects tokens with wrong or missing token type claim with 401', async () => {
      const accessTypedOnRefreshSecret = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'access' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '7d' },
      );
      const untypedOnRefreshSecret = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '7d' },
      );

      await expect(authService.refreshToken(accessTypedOnRefreshSecret)).rejects.toThrow(
        UnauthorizedException,
      );
      await expect(authService.refreshToken(untypedOnRefreshSecret)).rejects.toThrow(
        UnauthorizedException,
      );
      expect(mockUserFindUnique).not.toHaveBeenCalled();
    });

    it('T-REF-06: refresh propagates database errors without issuing tokens', async () => {
      const validRefresh = jwtService.sign(
        { sub: activeUserId, email: activeUserEmail, type: 'refresh' },
        { secret: TEST_JWT_REFRESH_SECRET, expiresIn: '7d' },
      );
      mockUserFindUnique.mockRejectedValue(new Error('DB read timeout'));

      await expect(authService.refreshToken(validRefresh)).rejects.toThrow('DB read timeout');
    });

    it('T-COMPAT-01: POST /auth/register preserves request/response contract and rejects duplicate email', async () => {
      mockUserFindUnique.mockResolvedValueOnce(null);
      mockUserCreate.mockResolvedValueOnce({
        id: 'new-user-uuid',
        email: 'newuser@wanderai.test',
        passwordHash: activePasswordHash,
        deletedAt: null,
        profile: { displayName: 'New User' },
      });

      const res = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'NewUser@wanderai.test',
          password: plainPassword,
          name: 'New User',
        })
        .expect(201);

      expect(res.body).toMatchObject({
        success: true,
        data: {
          access_token: expect.any(String),
          refresh_token: expect.any(String),
        },
      });

      mockUserFindUnique.mockResolvedValueOnce({
        id: 'new-user-uuid',
        email: 'newuser@wanderai.test',
        passwordHash: activePasswordHash,
        deletedAt: null,
      });

      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: 'newuser@wanderai.test',
          password: plainPassword,
          name: 'Duplicate User',
        })
        .expect(400);
    });

    it('T-COMPAT-02: POST /auth/login preserves contract and rejects wrong password or soft-deleted user with 401', async () => {
      mockUserFindUnique.mockResolvedValueOnce({
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: null,
      });

      await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: activeUserEmail, password: 'WrongPassword999' })
        .expect(401);

      mockUserFindUnique.mockResolvedValueOnce({
        id: activeUserId,
        email: activeUserEmail,
        passwordHash: activePasswordHash,
        deletedAt: new Date('2026-11-01T00:00:00.000Z'),
      });

      await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: activeUserEmail, password: plainPassword })
        .expect(401);
    });
  });
});
