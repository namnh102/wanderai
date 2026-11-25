import {
  BadRequestException,
  ExecutionContext,
  INestApplication,
  ValidationPipe,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { Prisma } from '@prisma/client';
import * as request from 'supertest';
import { HttpExceptionFilter } from './filters/http-exception.filter';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { TransformInterceptor } from './interceptors/transform.interceptor';
import { PrismaService } from '../prisma/prisma.service';
import {
  InMemoryPrismaService,
  DA_NANG_DESTINATION_ID,
} from '../../test/e2e-harness/in-memory-prisma.service';
import { AiProxyController } from '../modules/ai-proxy/ai-proxy.controller';
import { AiProxyService } from '../modules/ai-proxy/ai-proxy.service';
import { AiChatProxyService } from '../modules/ai-proxy/internal-auth';
import { ForgotPasswordDto } from '../modules/auth/dto/forgot-password.dto';
import { LoginDto } from '../modules/auth/dto/login.dto';
import { RefreshTokenDto } from '../modules/auth/dto/refresh-token.dto';
import { RegisterDto } from '../modules/auth/dto/register.dto';
import { ResetPasswordDto } from '../modules/auth/dto/reset-password.dto';
import { DestinationsController } from '../modules/destinations/destinations.controller';
import { DestinationsService } from '../modules/destinations/destinations.service';
import { PlacesController } from '../modules/places/places.controller';
import { PlacesService } from '../modules/places/places.service';
import { ReviewsController } from '../modules/reviews/reviews.controller';
import { ReviewsService } from '../modules/reviews/reviews.service';
import { AddItineraryDto } from '../modules/trips/dto/add-itinerary.dto';
import { BulkItineraryDto } from '../modules/trips/dto/bulk-itinerary.dto';
import { CreateTripDto } from '../modules/trips/dto/create-trip.dto';
import { UpdateTripDto } from '../modules/trips/dto/update-trip.dto';
import { UpdatePreferencesDto } from '../modules/users/dto/update-preferences.dto';
import { UsersController } from '../modules/users/users.controller';
import { UsersService } from '../modules/users/users.service';
import { VideosController } from '../modules/videos/videos.controller';
import { VideosService } from '../modules/videos/videos.service';

describe('GAP-07 / GAP-12 / GAP-13: Input Validation & Hardening', () => {
  let app: INestApplication;
  let prisma: InMemoryPrismaService;
  let mockAiProxyService: {
    chat: jest.Mock;
    clearChatSession: jest.Mock;
    planTrip: jest.Mock;
    getPlaceRecommendations: jest.Mock;
  };
  let activeUserId = '44444444-4444-4444-8444-444444444444';
  const verifiedPlaceId = '65562a67-84ff-44a0-990d-31917a2a9bd0';

  const validationPipe = new ValidationPipe({
    whitelist: true,
    transform: true,
    forbidNonWhitelisted: true,
  });

  beforeAll(async () => {
    prisma = new InMemoryPrismaService();
    await prisma.onModuleInit();
    const createdUser = await prisma.user.create({
      data: {
        email: 'active-hardening@wanderai.test',
        passwordHash: 'hash',
        isVerified: true,
        profile: { create: { displayName: 'Test User' } },
      },
    });
    activeUserId = createdUser.id as string;

    mockAiProxyService = {
      chat: jest.fn(),
      clearChatSession: jest.fn(),
      planTrip: jest.fn().mockResolvedValue({ destination: 'Hạ Long', days: 3 }),
      getPlaceRecommendations: jest.fn().mockResolvedValue({ items: [] }),
    };

    const moduleRef = await Test.createTestingModule({
      controllers: [
        UsersController,
        DestinationsController,
        ReviewsController,
        PlacesController,
        VideosController,
        AiProxyController,
      ],
      providers: [
        UsersService,
        DestinationsService,
        ReviewsService,
        PlacesService,
        VideosService,
        { provide: PrismaService, useValue: prisma },
        { provide: AiChatProxyService, useValue: mockAiProxyService },
        { provide: AiProxyService, useValue: mockAiProxyService },
      ],
    })
      .overrideGuard(JwtAuthGuard)
      .useValue({
        canActivate: (ctx: ExecutionContext) => {
          const req = ctx.switchToHttp().getRequest();
          req.user = { id: activeUserId, email: 'active-hardening@wanderai.test' };
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

  beforeEach(() => {
    jest.clearAllMocks();
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

  describe('GAP-12: VideosController/VideosService & AiProxyController.plan hardening', () => {
    it('rejects POST /videos with arbitrary/malformed payloads (400) and persists allowlisted fields without mock fallback', async () => {
      await request(app.getHttpServer())
        .post('/videos')
        .send({ evilField: 'injection', userId: 'spoofed-user' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/videos')
        .send({ videoUrl: 'javascript:alert(1)' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/videos')
        .send({ videoUrl: 'https://cdn.example.com/v.mp4', duration: -10 })
        .expect(400);

      const created = await request(app.getHttpServer())
        .post('/videos')
        .send({
          videoUrl: 'https://cdn.example.com/halong.mp4',
          title: '  Tháp Đồng Hồ  ',
          duration: 30,
          tags: ['  halong  '],
        })
        .expect(201);

      expect(created.body.data.id).not.toBe('mock-video-id');
      expect(created.body.data.userId).toBe(activeUserId);
      expect(created.body.data.title).toBe('Tháp Đồng Hồ');
      expect(created.body.data.tags).toEqual(['halong']);

      const fetched = await request(app.getHttpServer())
        .get(`/videos/${created.body.data.id}`)
        .expect(200);
      expect(fetched.body.data.videoUrl).toBe('https://cdn.example.com/halong.mp4');
    });

    it('rejects non-UUID GET /videos/:id (400), returns 404 for missing UUID (never 200 mock-url), and validates feed bounds', async () => {
      await request(app.getHttpServer())
        .get('/videos/not-a-uuid')
        .expect(400);

      await request(app.getHttpServer())
        .get('/videos/99999999-9999-4999-8999-999999999999')
        .expect(404);

      await request(app.getHttpServer())
        .get('/videos/feed?page=-1')
        .expect(400);

      await request(app.getHttpServer())
        .get('/videos/feed?page=10001')
        .expect(400);

      await request(app.getHttpServer())
        .get('/videos/feed?limit=51')
        .expect(400);

      const feedRes = await request(app.getHttpServer())
        .get('/videos/feed?page=1&limit=10')
        .expect(200);
      expect(Array.isArray(feedRes.body.data.items)).toBe(true);
      expect(feedRes.body.data.page).toBe(1);
      expect(feedRes.body.data.limit).toBe(10);
    });

    it('propagates DB errors cleanly from VideosService instead of returning mock objects', async () => {
      const failingPrisma = {
        video: {
          findMany: jest.fn().mockRejectedValue(new Error('DB connection lost')),
          findUnique: jest.fn().mockRejectedValue(new Error('DB connection lost')),
          create: jest.fn().mockRejectedValue(
            new Prisma.PrismaClientKnownRequestError('FK violation', {
              code: 'P2003',
              clientVersion: '5.22.0',
            }),
          ),
        },
      } as unknown as PrismaService;
      const svc = new VideosService(failingPrisma);

      await expect(svc.getFeed(1, 20)).rejects.toThrow('DB connection lost');
      await expect(
        svc.findById('99999999-9999-4999-8999-999999999999'),
      ).rejects.toThrow('DB connection lost');
      await expect(
        svc.create(
          { videoUrl: 'https://cdn.example.com/halong.mp4' },
          activeUserId,
        ),
      ).rejects.toThrow(BadRequestException);
    });

    it('enforces PlanTripLegacyDto on POST /ai/plan (rejects empty/non-whitelisted/out-of-range with 400)', async () => {
      await request(app.getHttpServer())
        .post('/ai/plan')
        .send({ destination: '   ', days: 3 })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/plan')
        .send({ destination: 'Hạ Long', days: 3, evilField: true })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/plan')
        .send({ destination: 'Hạ Long', days: 15 })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/plan')
        .send({ destination: 'Hạ Long', days: 3, budget: 9999999999 })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/plan')
        .send({ destination: '  Hạ Long  ', days: 3, budget: 5000000 })
        .expect(201);
      expect(mockAiProxyService.planTrip).toHaveBeenCalledWith('Hạ Long', 3, 5000000);
    });
  });

  describe('GAP-13: PostgreSQL INT4_MAX, OFFSET, radius, and string length bounds', () => {
    it('rejects integers > 2147483647 on Trip, Itinerary, and Preferences DTOs while accepting INT4_MAX', async () => {
      await expect(
        validationPipe.transform(
          { title: 'Billionaire Trip', totalBudget: 9999999999 },
          { type: 'body', metatype: CreateTripDto },
        ),
      ).rejects.toThrow();

      await expect(
        validationPipe.transform(
          { totalBudget: 2147483648 },
          { type: 'body', metatype: UpdateTripDto },
        ),
      ).rejects.toThrow();

      const validTrip = await validationPipe.transform(
        { title: 'Max INT4 Trip', totalBudget: 2147483647 },
        { type: 'body', metatype: CreateTripDto },
      );
      expect(validTrip.totalBudget).toBe(2147483647);

      await expect(
        validationPipe.transform(
          { dayNumber: 1, activity: 'Yacht', estimatedCost: 9999999999 },
          { type: 'body', metatype: AddItineraryDto },
        ),
      ).rejects.toThrow();

      await expect(
        validationPipe.transform(
          {
            days: [
              {
                dayNumber: 1,
                items: [{ orderIndex: 1, activity: 'Yacht', estimatedCost: 9999999999 }],
              },
            ],
          },
          { type: 'body', metatype: BulkItineraryDto },
        ),
      ).rejects.toThrow();

      await expect(
        validationPipe.transform(
          { budgetMin: 9999999999 },
          { type: 'body', metatype: UpdatePreferencesDto },
        ),
      ).rejects.toThrow();

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ budgetMax: 9999999999 })
        .expect(400);
    });

    it('rejects excessive page (> 10000), nearby radius (> 1000), and oversized search/category params with 400', async () => {
      await request(app.getHttpServer())
        .get('/places?page=999999999')
        .expect(400);

      await request(app.getHttpServer())
        .get('/destinations?page=999999999')
        .expect(400);

      await request(app.getHttpServer())
        .get(`/reviews?placeId=${verifiedPlaceId}&page=10001`)
        .expect(400);

      await request(app.getHttpServer())
        .get('/reviews/my?page=10001')
        .expect(400);

      await request(app.getHttpServer())
        .get('/places/nearby?lat=20.95&lng=107.08&radius=999999')
        .expect(400);

      await request(app.getHttpServer())
        .get(`/places?search=${'a'.repeat(201)}`)
        .expect(400);

      await request(app.getHttpServer())
        .get(`/places?category=${'c'.repeat(65)}`)
        .expect(400);

      await request(app.getHttpServer())
        .get(`/places/trending?category=${'c'.repeat(65)}`)
        .expect(400);
    });
  });

  describe('GAP-17: ChatDto, UpdatePreferencesDto, and DestinationsService.findById soft-delete hardening', () => {
    it('rejects blank/oversized POST /ai/chat message and oversized session_id with 400 while trimming valid input', async () => {
      mockAiProxyService.chat.mockResolvedValue({
        reply: 'Chào bạn!',
        session_id: 'sess-1',
        tools_used: [],
        tool_calls: [],
        sources: [],
      });

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: '   ' })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: 'x'.repeat(4001) })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: 123 })
        .expect(400);

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: 'Xin chào', session_id: 's'.repeat(129) })
        .expect(400);

      expect(mockAiProxyService.chat).not.toHaveBeenCalled();

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: '  Xin chào Wandy  ', session_id: '   ' })
        .expect(201);
      expect(mockAiProxyService.chat).toHaveBeenCalledWith(
        'Xin chào Wandy',
        undefined,
        activeUserId,
      );

      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: '  Gợi ý Hạ Long  ', session_id: '  sess-1  ' })
        .expect(201);
      expect(mockAiProxyService.chat).toHaveBeenCalledWith(
        'Gợi ý Hạ Long',
        'sess-1',
        activeUserId,
      );
    });

    it('rejects non-string, blank, >30 items, >100-char items on PUT /users/me/preferences with 400 while normalizing valid arrays', async () => {
      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ avoidances: [123, 456] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ dietaryNeeds: [true] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ interests: [123] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ avoidances: ['   '] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ dietaryNeeds: [''] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ avoidances: Array(31).fill('crowds_item') })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({
          avoidances: Array.from({ length: 31 }, (_, i) => `avoid_${i}`),
        })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ dietaryNeeds: Array(31).fill('vegetarian') })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ interests: Array(21).fill('food_cuisine') })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ avoidances: ['a'.repeat(101)] })
        .expect(400);

      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ dietaryNeeds: ['b'.repeat(101)] })
        .expect(400);

      const okRes = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({
          interests: ['  food_cuisine  ', 'food_cuisine'],
          avoidances: ['  crowds  ', 'heights', 'crowds'],
          dietaryNeeds: ['  vegetarian  '],
        })
        .expect(200);
      expect(okRes.body.data.interests).toEqual(['food_cuisine']);
      expect(okRes.body.data.avoidances).toEqual(['crowds', 'heights']);
      expect(okRes.body.data.dietaryNeeds).toEqual(['vegetarian']);
    });

    it('returns 404 for soft-deleted destination in DestinationsService.findById and GET /destinations/:id', async () => {
      await prisma.destination.update({
        where: { id: DA_NANG_DESTINATION_ID },
        data: { deletedAt: new Date() },
      });
      try {
        const res = await request(app.getHttpServer())
          .get(`/destinations/${DA_NANG_DESTINATION_ID}`)
          .expect(404);
        expect(res.body.errorCode).toBe('DESTINATION_NOT_FOUND');
      } finally {
        await prisma.destination.update({
          where: { id: DA_NANG_DESTINATION_ID },
          data: { deletedAt: null },
        });
      }

      const okRes = await request(app.getHttpServer())
        .get(`/destinations/${DA_NANG_DESTINATION_ID}`)
        .expect(200);
      expect(okRes.body.data.id).toBe(DA_NANG_DESTINATION_ID);
    });
  });
});
