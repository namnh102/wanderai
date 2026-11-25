import {
  ExecutionContext,
  INestApplication,
  ValidationPipe,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import * as request from 'supertest';
import { HttpExceptionFilter } from './filters/http-exception.filter';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { TransformInterceptor } from './interceptors/transform.interceptor';
import { PrismaService } from '../prisma/prisma.service';
import { InMemoryPrismaService } from '../../test/e2e-harness/in-memory-prisma.service';
import { ForgotPasswordDto } from '../modules/auth/dto/forgot-password.dto';
import { LoginDto } from '../modules/auth/dto/login.dto';
import { RefreshTokenDto } from '../modules/auth/dto/refresh-token.dto';
import { RegisterDto } from '../modules/auth/dto/register.dto';
import { ResetPasswordDto } from '../modules/auth/dto/reset-password.dto';
import { DestinationsController } from '../modules/destinations/destinations.controller';
import { DestinationsService } from '../modules/destinations/destinations.service';
import { ReviewsController } from '../modules/reviews/reviews.controller';
import { ReviewsService } from '../modules/reviews/reviews.service';
import { CreateTripDto } from '../modules/trips/dto/create-trip.dto';
import { UsersController } from '../modules/users/users.controller';
import { UsersService } from '../modules/users/users.service';

describe('GAP-07: Input Validation Hardening (Users, Destinations, Reviews, Auth/Trip Bounds)', () => {
  let app: INestApplication;
  let prisma: InMemoryPrismaService;
  const activeUserId = '44444444-4444-4444-8444-444444444444';
  const verifiedPlaceId = '65562a67-84ff-44a0-990d-31917a2a9bd0';

  const validationPipe = new ValidationPipe({
    whitelist: true,
    transform: true,
    forbidNonWhitelisted: true,
  });

  beforeAll(async () => {
    prisma = new InMemoryPrismaService();
    await prisma.onModuleInit();

    const moduleRef = await Test.createTestingModule({
      controllers: [UsersController, DestinationsController, ReviewsController],
      providers: [
        UsersService,
        DestinationsService,
        ReviewsService,
        { provide: PrismaService, useValue: prisma },
      ],
    })
      .overrideGuard(JwtAuthGuard)
      .useValue({
        canActivate: (ctx: ExecutionContext) => {
          const req = ctx.switchToHttp().getRequest();
          req.user = { id: activeUserId, email: 'user@wanderai.test' };
          return true;
        },
      })
      .compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(validationPipe);
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it('rejects PUT /users/me non-string displayName, blank displayName, and unknown fields with 400 while allowing valid profile', async () => {
    await request(app.getHttpServer())
      .put('/users/me')
      .send({ displayName: 12345, unknownAdminFlag: true })
      .expect(400);

    await request(app.getHttpServer())
      .put('/users/me')
      .send({ displayName: '   ' })
      .expect(400);

    const okRes = await request(app.getHttpServer())
      .put('/users/me')
      .send({ displayName: '  Minh Hạ Long  ', bio: '  Yêu biển  ' })
      .expect(200);
    expect(okRes.body.data.displayName).toBe('Minh Hạ Long');
    expect(okRes.body.data.bio).toBe('Yêu biển');
  });

  it('rejects invalid Destinations query params and malformed UUIDs with 400 while allowing ?limit=100', async () => {
    await request(app.getHttpServer())
      .get('/destinations?page=-5&limit=99999')
      .expect(400);

    await request(app.getHttpServer())
      .get('/destinations/nearby?lat=abc&lng=def')
      .expect(400);

    await request(app.getHttpServer())
      .get('/destinations/not-a-uuid')
      .expect(400);

    const validRes = await request(app.getHttpServer())
      .get('/destinations?limit=100')
      .expect(200);
    expect(Array.isArray(validRes.body.data.items)).toBe(true);
  });

  it('rejects invalid Reviews queries, blank content, bad placeId, and malformed review :id with 400', async () => {
    await request(app.getHttpServer())
      .get('/reviews?placeId=not-a-uuid')
      .expect(400);

    await request(app.getHttpServer())
      .get('/reviews/not-a-uuid')
      .expect(400);

    await request(app.getHttpServer())
      .post('/reviews')
      .send({
        placeId: 'not-a-uuid',
        rating: 5,
        content: 'Tuyệt vời',
      })
      .expect(400);

    await request(app.getHttpServer())
      .post('/reviews')
      .send({
        placeId: verifiedPlaceId,
        rating: 5,
        content: '   ',
      })
      .expect(400);
  });

  it('enforces @MaxLength bounds on Trip and Auth DTOs', async () => {
    await expect(
      validationPipe.transform(
        { title: 'A'.repeat(201) },
        { type: 'body', metatype: CreateTripDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        {
          email: `${'a'.repeat(250)}@test.com`,
          password: 'Password123!',
          name: 'User',
        },
        { type: 'body', metatype: RegisterDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        {
          email: 'user@test.com',
          password: 'P'.repeat(129),
          name: 'User',
        },
        { type: 'body', metatype: RegisterDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        { email: 'user@test.com', password: 'P'.repeat(129) },
        { type: 'body', metatype: LoginDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        { email: `${'a'.repeat(250)}@test.com` },
        { type: 'body', metatype: ForgotPasswordDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        { token: 't'.repeat(257), newPassword: 'Password123!' },
        { type: 'body', metatype: ResetPasswordDto },
      ),
    ).rejects.toThrow();

    await expect(
      validationPipe.transform(
        { refresh_token: 'r'.repeat(4097) },
        { type: 'body', metatype: RefreshTokenDto },
      ),
    ).rejects.toThrow();
  });
});
