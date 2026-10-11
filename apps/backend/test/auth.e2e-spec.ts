import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import * as bcrypt from 'bcryptjs';

describe('AuthController (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const TEST_EMAIL = `test_auth_${Date.now()}@wanderai.test`;
  const TEST_PASSWORD = 'TestPass123!';
  const TEST_NAME = 'Test Auth User';

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, forbidNonWhitelisted: true }));
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();

    prisma = app.get(PrismaService);

    // Create a known test user for login tests
    const hash = await bcrypt.hash(TEST_PASSWORD, 12);
    await prisma.user.create({
      data: {
        email: TEST_EMAIL,
        passwordHash: hash,
        profile: { create: { displayName: TEST_NAME } },
      },
    });
  });

  afterAll(async () => {
    // Clean up test user
    const user = await prisma.user.findUnique({ where: { email: TEST_EMAIL } });
    if (user) {
      await prisma.profile.deleteMany({ where: { userId: user.id } });
      await prisma.user.delete({ where: { id: user.id } });
    }
    // Clean up registered test user
    const regEmail = `test_reg_${TEST_EMAIL}`;
    const regUser = await prisma.user.findUnique({ where: { email: regEmail } });
    if (regUser) {
      await prisma.profile.deleteMany({ where: { userId: regUser.id } });
      await prisma.user.delete({ where: { id: regUser.id } });
    }
    await app.close();
  });

  describe('POST /auth/login', () => {
    it('should login with valid credentials and return tokens', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: TEST_EMAIL, password: TEST_PASSWORD })
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(res.body.data).toHaveProperty('access_token');
          expect(res.body.data).toHaveProperty('refresh_token');
          expect(typeof res.body.data.access_token).toBe('string');
          expect(res.body.data.access_token.length).toBeGreaterThan(50);
        });
    });

    it('should return 401 for wrong password', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: TEST_EMAIL, password: 'WrongPassword123' })
        .expect(401);
    });

    it('should return 401 for non-existent email', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'nonexistent@wanderai.test', password: TEST_PASSWORD })
        .expect(401);
    });

    it('should return 400 for missing email', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ password: TEST_PASSWORD })
        .expect(400);
    });

    it('should return 400 for missing password', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: TEST_EMAIL })
        .expect(400);
    });
  });

  describe('POST /auth/register', () => {
    it('should register a new user and return tokens', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: `test_reg_${TEST_EMAIL}`,
          password: TEST_PASSWORD,
          name: 'New Test User',
        })
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(res.body.data).toHaveProperty('access_token');
          expect(res.body.data).toHaveProperty('refresh_token');
        });
    });

    it('should return 400 for duplicate email', () => {
      return request(app.getHttpServer())
        .post('/auth/register')
        .send({
          email: TEST_EMAIL,
          password: TEST_PASSWORD,
          name: 'Duplicate User',
        })
        .expect(400);
    });
  });
});
