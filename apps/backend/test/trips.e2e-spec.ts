import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';

describe('TripsController (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let jwtService: JwtService;

  let userAToken: string;
  let userBToken: string;
  let userAId: string;
  let userBId: string;
  let userATripId: string;

  const userAEmail = `test_trips_a_${Date.now()}@wanderai.test`;
  const userBEmail = `test_trips_b_${Date.now()}@wanderai.test`;
  const password = 'TestPass123!';

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
    jwtService = app.get(JwtService);

    // Setup User A
    const hash = await bcrypt.hash(password, 10);
    const userA = await prisma.user.create({
      data: {
        email: userAEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'User A' } },
      },
    });
    userAId = userA.id;
    userAToken = jwtService.sign({ sub: userA.id, email: userA.email });

    // Setup User B
    const userB = await prisma.user.create({
      data: {
        email: userBEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'User B' } },
      },
    });
    userBId = userB.id;
    userBToken = jwtService.sign({ sub: userB.id, email: userB.email });
  });

  afterAll(async () => {
    // Clean up created trips, members, and users
    await prisma.itineraryItem.deleteMany({
      where: { itinerary: { trip: { userId: { in: [userAId, userBId] } } } },
    });
    await prisma.itinerary.deleteMany({
      where: { trip: { userId: { in: [userAId, userBId] } } },
    });
    await prisma.tripMember.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.trip.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.profile.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.user.deleteMany({
      where: { id: { in: [userAId, userBId] } },
    });

    await app.close();
  });

  describe('Trip Authorization & CRUD Flow', () => {
    // 1. Create trip authenticated
    it('1. should create trip when authenticated', async () => {
      const res = await request(app.getHttpServer())
        .post('/trips')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({
          title: 'Chuyến đi Hà Giang của User A',
          startDate: '2026-11-01',
          endDate: '2026-11-05',
          totalBudget: 4000000,
          currency: 'VND',
          travelStyle: 'COMFORT',
          interests: ['nature', 'mountain'],
          description: 'Khám phá Mã Pí Lèng',
        })
        .expect(201);

      expect(res.body.success).toBe(true);
      expect(res.body.data.title).toBe('Chuyến đi Hà Giang của User A');
      expect(res.body.data.totalBudget).toBe(4000000);
      expect(res.body.data.currency).toBe('VND');
      expect(res.body.data.travelStyle).toBe('COMFORT');
      expect(res.body.data.interests).toContain('nature');
      userATripId = res.body.data.id;
      expect(userATripId).toBeDefined();
    });

    // 2. Create trip unauthenticated
    it('2. should reject trip creation when unauthenticated (401)', () => {
      return request(app.getHttpServer())
        .post('/trips')
        .send({ title: 'Chuyến đi ẩn danh' })
        .expect(401);
    });

    // 3. Invalid date range (endDate < startDate)
    it('3. should reject invalid date range (endDate < startDate) (400)', () => {
      return request(app.getHttpServer())
        .post('/trips')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({
          title: 'Ngày kết thúc trước ngày bắt đầu',
          startDate: '2026-11-10',
          endDate: '2026-11-05',
        })
        .expect(400);
    });

    // 4. Invalid budget (< 0)
    it('4. should reject negative budget (400)', () => {
      return request(app.getHttpServer())
        .post('/trips')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({
          title: 'Ngân sách âm',
          totalBudget: -500000,
        })
        .expect(400);
    });

    // 5. List own trips
    it('5. should list own trips for User A', async () => {
      const res = await request(app.getHttpServer())
        .get('/trips')
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(Array.isArray(res.body.data)).toBe(true);
      expect(res.body.data.some((t: any) => t.id === userATripId)).toBe(true);

      // User B should have 0 trips so far
      const resB = await request(app.getHttpServer())
        .get('/trips')
        .set('Authorization', `Bearer ${userBToken}`)
        .expect(200);
      expect(resB.body.data.some((t: any) => t.id === userATripId)).toBe(false);
    });

    // 6. Get own trip
    it('6. should get details of own trip', async () => {
      const res = await request(app.getHttpServer())
        .get(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(res.body.data.id).toBe(userATripId);
      expect(res.body.data.title).toBe('Chuyến đi Hà Giang của User A');
    });

    // 7. Cannot access another user's trip (403)
    it('7. should forbid User B from viewing User A trip (403)', () => {
      return request(app.getHttpServer())
        .get(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userBToken}`)
        .expect(403);
    });

    // 8. Update own trip
    it('8. should allow owner to update their trip', async () => {
      const res = await request(app.getHttpServer())
        .put(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userAToken}`)
        .send({
          title: 'Tên chuyến đi đã sửa đổi',
          totalBudget: 6000000,
        })
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(res.body.data.title).toBe('Tên chuyến đi đã sửa đổi');
      expect(res.body.data.totalBudget).toBe(6000000);
    });

    // 9. Cannot update another user's trip (403)
    it('9. should forbid User B from updating User A trip (403)', () => {
      return request(app.getHttpServer())
        .put(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userBToken}`)
        .send({ title: 'Hacker sửa đổi' })
        .expect(403);
    });

    // 10 & 11. Delete authorization
    it('11. should forbid User B from deleting User A trip (403)', () => {
      return request(app.getHttpServer())
        .delete(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userBToken}`)
        .expect(403);
    });

    it('10. should allow owner to delete their trip', async () => {
      const res = await request(app.getHttpServer())
        .delete(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);

      // Verify trip is now soft deleted (not returned by findById)
      await request(app.getHttpServer())
        .get(`/trips/${userATripId}`)
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(404);
    });
  });
});
