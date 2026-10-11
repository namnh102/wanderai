import { Test, TestingModule } from '@nestjs/testing';
import { HttpException, INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import { AiProxyService } from '../src/modules/ai-proxy/ai-proxy.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';

describe('AI Trip Planner & Bulk Itinerary (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let jwtService: JwtService;
  let aiProxyService: AiProxyService;

  let userAToken: string;
  let userBToken: string;
  let userAId: string;
  let userBId: string;
  let tripAId: string;

  const userAEmail = `test_plan_a_${Date.now()}@wanderai.test`;
  const userBEmail = `test_plan_b_${Date.now()}@wanderai.test`;
  const password = 'TestPass123!';

  const mockAiPlanResult = {
    plan_id: 'mock-plan-id',
    destination: 'Đà Nẵng',
    total_days: 2,
    overview: 'Hành trình 2 ngày tuyệt vời tại Đà Nẵng',
    best_time_to_visit: 'Tháng 3 đến tháng 8',
    general_tips: ['Mang theo kem chống nắng', 'Thuê xe máy thuận tiện'],
    days: [
      {
        day_number: 1,
        title: 'Ngày 1: Biển Mỹ Khê & Ẩm thực',
        items: [
          {
            order_index: 1,
            start_time: '08:00',
            end_time: '09:30',
            activity: 'Ăn sáng mì Quảng ếch',
            place_name: 'Mì Quảng Bếp Trang',
            notes: 'Món ngon nổi tiếng',
            estimated_cost: 55000,
            transport_mode: 'motorbike',
          },
          {
            order_index: 2,
            start_time: '10:00',
            end_time: '12:00',
            activity: 'Tắm biển Mỹ Khê',
            place_name: 'Bãi biển Mỹ Khê',
            notes: 'Bãi biển đẹp top thế giới',
            estimated_cost: 20000,
            transport_mode: 'motorbike',
          },
        ],
      },
      {
        day_number: 2,
        title: 'Ngày 2: Bán đảo Sơn Trà',
        items: [
          {
            order_index: 1,
            start_time: '08:30',
            end_time: '11:00',
            activity: 'Viếng Chùa Linh Ứng',
            place_name: 'Bán đảo Sơn Trà',
            notes: 'Chiêm bái tượng Phật Bà',
            estimated_cost: 0,
            transport_mode: 'motorbike',
          },
        ],
      },
    ],
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, transform: true, forbidNonWhitelisted: true }),
    );
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();

    prisma = app.get(PrismaService);
    jwtService = app.get(JwtService);
    aiProxyService = app.get(AiProxyService);

    // Mock planWithTripContext to guarantee fast, deterministic e2e test execution
    jest.spyOn(aiProxyService, 'planWithTripContext').mockResolvedValue(mockAiPlanResult);

    // Create User A
    const hash = await bcrypt.hash(password, 10);
    const userA = await prisma.user.create({
      data: {
        email: userAEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'Plan User A' } },
      },
    });
    userAId = userA.id;
    userAToken = jwtService.sign({ sub: userA.id, email: userA.email });

    // Create User B
    const userB = await prisma.user.create({
      data: {
        email: userBEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'Plan User B' } },
      },
    });
    userBId = userB.id;
    userBToken = jwtService.sign({ sub: userB.id, email: userB.email });

    // Create a Destination for testing
    const dest = await prisma.destination.upsert({
      where: { slug: 'da-nang-plan-test' },
      create: {
        name: 'Đà Nẵng',
        slug: 'da-nang-plan-test',
        province: 'Đà Nẵng',
        region: 'central',
      },
      update: {},
    });

    // Create Trip for User A
    const trip = await prisma.trip.create({
      data: {
        userId: userAId,
        title: 'Khám phá Đà Nẵng 2N1Đ',
        destinationId: dest.id,
        startDate: new Date('2026-10-15'),
        endDate: new Date('2026-10-16'),
        totalBudget: 2000000,
        currency: 'VND',
        travelStyle: 'BUDGET',
        interests: ['beach', 'food'],
        members: {
          create: { userId: userAId, role: 'owner' },
        },
      },
    });
    tripAId = trip.id;
  });

  afterAll(async () => {
    if (prisma) {
      await prisma.itineraryItem.deleteMany({
        where: { itinerary: { tripId: tripAId } },
      });
      await prisma.itinerary.deleteMany({ where: { tripId: tripAId } });
      await prisma.tripMember.deleteMany({ where: { tripId: tripAId } });
      await prisma.trip.deleteMany({ where: { id: tripAId } });
      await prisma.profile.deleteMany({ where: { userId: { in: [userAId, userBId] } } });
      await prisma.user.deleteMany({ where: { id: { in: [userAId, userBId] } } });
      await prisma.destination.deleteMany({ where: { slug: 'da-nang-plan-test' } });
    }
    if (app) await app.close();
  });

  describe('POST /trips/:id/ai-plan (Generate Itinerary Preview)', () => {
    it('1. Rejects unauthenticated request with 401', async () => {
      await request(app.getHttpServer())
        .post(`/trips/${tripAId}/ai-plan`)
        .expect(401);
    });

    it('2. Rejects non-member/non-owner with 403', async () => {
      await request(app.getHttpServer())
        .post(`/trips/${tripAId}/ai-plan`)
        .set('Authorization', `Bearer ${userBToken}`)
        .expect(403);
    });

    it('3. Generates structured preview and verifies INVARIANT: does not save to DB', async () => {
      const res = await request(app.getHttpServer())
        .post(`/trips/${tripAId}/ai-plan`)
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ additionalPrompt: 'Thêm quán ăn vặt' })
        .expect(201);

      expect(res.body.success).toBe(true);
      const plan = res.body.data;
      expect(plan.tripId).toBe(tripAId);
      expect(plan.destination).toBe('Đà Nẵng');
      expect(plan.totalDays).toBe(2);
      expect(plan.days).toHaveLength(2);

      // Verify deterministic arithmetic
      // Day 1: 55,000 + 20,000 = 75,000; Day 2: 0; Total: 75,000
      expect(plan.days[0].dayCost).toBe(75000);
      expect(plan.budgetAnalysis.estimatedCost).toBe(75000);
      expect(plan.budgetAnalysis.totalBudget).toBe(2000000);
      expect(plan.budgetAnalysis.isOverBudget).toBe(false);
      expect(plan.budgetAnalysis.variance).toBe(1925000);

      // CRITICAL INVARIANT: Verify NO itineraries exist in DB yet!
      const count = await prisma.itinerary.count({ where: { tripId: tripAId } });
      expect(count).toBe(0);
    });

    it('3b. Provider failure returns a controlled error with no DB write and no stack leak', async () => {
      const before = await prisma.itinerary.count({ where: { tripId: tripAId } });
      jest
        .spyOn(aiProxyService, 'planWithTripContext')
        .mockRejectedValueOnce(
          new HttpException('Nhà cung cấp AI không phản hồi. Vui lòng thử lại sau.', 502),
        );

      const res = await request(app.getHttpServer())
        .post(`/trips/${tripAId}/ai-plan`)
        .set('Authorization', `Bearer ${userAToken}`)
        .send({})
        .expect(502);

      expect(res.body.success).toBe(false);
      expect(JSON.stringify(res.body)).not.toMatch(/stack|Traceback|at .*\.(ts|js|py)/i);
      const after = await prisma.itinerary.count({ where: { tripId: tripAId } });
      expect(after).toBe(before);
    });

  });

  describe('POST /trips/:id/itinerary/bulk (Atomic Bulk Save)', () => {
    it('4. Rejects unauthenticated request with 401', async () => {
      await request(app.getHttpServer())
        .post(`/trips/${tripAId}/itinerary/bulk`)
        .send({ days: [] })
        .expect(401);
    });

    it('5. Rejects non-owner attempting to bulk save with 403', async () => {
      await request(app.getHttpServer())
        .post(`/trips/${tripAId}/itinerary/bulk`)
        .set('Authorization', `Bearer ${userBToken}`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              title: 'Ngày 1',
              items: [{ orderIndex: 1, activity: 'Hack trip' }],
            },
          ],
        })
        .expect(403);
    });

    it('6. Atomically persists itinerary days & items and updates trip status to PLANNED', async () => {
      const payload = {
        replaceExisting: true,
        days: [
          {
            dayNumber: 1,
            title: 'Ngày 1: Biển Mỹ Khê & Ẩm thực',
            date: '2026-10-15',
            items: [
              {
                orderIndex: 1,
                activity: 'Ăn sáng mì Quảng ếch',
                startTime: '08:00',
                endTime: '09:30',
                estimatedCost: 55000,
                notes: 'Bếp Trang',
                transportMode: 'motorbike',
              },
              {
                orderIndex: 2,
                activity: 'Tắm biển Mỹ Khê',
                startTime: '10:00',
                endTime: '12:00',
                estimatedCost: 20000,
                transportMode: 'motorbike',
              },
            ],
          },
          {
            dayNumber: 2,
            title: 'Ngày 2: Bán đảo Sơn Trà',
            date: '2026-10-16',
            items: [
              {
                orderIndex: 1,
                activity: 'Viếng Chùa Linh Ứng',
                startTime: '08:30',
                endTime: '11:00',
                estimatedCost: 0,
                transportMode: 'motorbike',
              },
            ],
          },
        ],
      };

      const res = await request(app.getHttpServer())
        .post(`/trips/${tripAId}/itinerary/bulk`)
        .set('Authorization', `Bearer ${userAToken}`)
        .send(payload)
        .expect(201);

      expect(res.body.success).toBe(true);
      const updatedTrip = res.body.data;
      expect(updatedTrip.id).toBe(tripAId);
      expect(updatedTrip.status).toBe('PLANNED');
      expect(updatedTrip.itineraries).toHaveLength(2);

      // Verify in Database directly
      const dbItineraries = await prisma.itinerary.findMany({
        where: { tripId: tripAId },
        include: { items: true },
        orderBy: { dayNumber: 'asc' },
      });

      expect(dbItineraries).toHaveLength(2);
      expect(dbItineraries[0].dayNumber).toBe(1);
      expect(dbItineraries[0].items).toHaveLength(2);
      expect(dbItineraries[0].items[0].activity).toBe('Ăn sáng mì Quảng ếch');
      expect(dbItineraries[0].items[0].estimatedCost).toBe(55000);
      expect(dbItineraries[1].dayNumber).toBe(2);
      expect(dbItineraries[1].items).toHaveLength(1);
    });

    it('7. Atomically replaces existing itineraries when replaceExisting=true', async () => {
      // Send a new single day itinerary
      const newPayload = {
        replaceExisting: true,
        days: [
          {
            dayNumber: 1,
            title: 'Ngày 1: Lịch trình rút gọn 1 ngày',
            items: [
              {
                orderIndex: 1,
                activity: 'Dạo phố Bạch Đằng',
                estimatedCost: 30000,
              },
            ],
          },
        ],
      };

      const res = await request(app.getHttpServer())
        .post(`/trips/${tripAId}/itinerary/bulk`)
        .set('Authorization', `Bearer ${userAToken}`)
        .send(newPayload)
        .expect(201);

      expect(res.body.success).toBe(true);
      expect(res.body.data.itineraries).toHaveLength(1);

      // Verify in DB that old 2 days are gone and only 1 day exists
      const dbItins = await prisma.itinerary.findMany({
        where: { tripId: tripAId },
        include: { items: true },
      });
      expect(dbItins).toHaveLength(1);
      expect(dbItins[0].title).toBe('Ngày 1: Lịch trình rút gọn 1 ngày');
      expect(dbItins[0].items).toHaveLength(1);
      expect(dbItins[0].items[0].activity).toBe('Dạo phố Bạch Đằng');
    });
  });
});
