import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';

describe('PreferencesController (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let jwtService: JwtService;

  let userAToken: string;
  let userBToken: string;
  let userAId: string;
  let userBId: string;

  const userAEmail = `test_pref_a_${Date.now()}@wanderai.test`;
  const userBEmail = `test_pref_b_${Date.now()}@wanderai.test`;
  const password = 'TestPass123!';

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

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
    jwtService = app.get(JwtService);

    const hash = await bcrypt.hash(password, 10);

    // Setup User A (starts without travel preferences)
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
    await prisma.travelPreference.deleteMany({
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

  describe('GET /users/me - Baseline state', () => {
    it('Case 4: user with no TravelPreference does not crash and returns null preferences', async () => {
      const res = await request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(res.body.data.id).toBe(userAId);
      expect(res.body.data.email).toBe(userAEmail);
      expect(res.body.data.preferences).toBeNull();
    });
  });

  describe('PUT /users/me/preferences - Creation and Updates', () => {
    it('Case 1: authenticated user creates preferences successfully', async () => {
      const payload = {
        travelStyle: 'COMFORT',
        budgetMin: 2000000,
        budgetMax: 15000000,
        preferredGroup: 'COUPLE',
        interests: ['food_cuisine', 'culture_history'],
        avoidances: ['crowds'],
        dietaryNeeds: ['vegetarian'],
      };

      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send(payload)
        .expect(200);

      expect(res.body.success).toBe(true);
      const pref = res.body.data;
      expect(pref.userId).toBe(userAId);
      expect(pref.travelStyle).toBe('COMFORT');
      expect(pref.budgetMin).toBe(2000000);
      expect(pref.budgetMax).toBe(15000000);
      expect(pref.preferredGroup).toBe('COUPLE');
      expect(pref.interests).toEqual(['food_cuisine', 'culture_history']);
      expect(pref.avoidances).toEqual(['crowds']);
      expect(pref.dietaryNeeds).toEqual(['vegetarian']);
    });

    it('Case 3: GET /users/me returns saved preferences', async () => {
      const res = await request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${userAToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);
      const pref = res.body.data.preferences;
      expect(pref).not.toBeNull();
      expect(pref.travelStyle).toBe('COMFORT');
      expect(pref.budgetMin).toBe(2000000);
      expect(pref.budgetMax).toBe(15000000);
      expect(pref.preferredGroup).toBe('COUPLE');
      expect(pref.interests).toEqual(['food_cuisine', 'culture_history']);
      expect(pref.avoidances).toEqual(['crowds']);
      expect(pref.dietaryNeeds).toEqual(['vegetarian']);
    });

    it('Case 2: authenticated user updates existing preferences', async () => {
      const updatePayload = {
        travelStyle: 'LUXURY',
        budgetMin: 5000000,
        budgetMax: 30000000,
        preferredGroup: 'FAMILY',
        interests: ['beach_island', 'coffee_culture', 'shopping_local'],
      };

      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send(updatePayload)
        .expect(200);

      expect(res.body.success).toBe(true);
      const pref = res.body.data;
      expect(pref.travelStyle).toBe('LUXURY');
      expect(pref.budgetMin).toBe(5000000);
      expect(pref.budgetMax).toBe(30000000);
      expect(pref.preferredGroup).toBe('FAMILY');
      expect(pref.interests).toEqual(['beach_island', 'coffee_culture', 'shopping_local']);
      // Previously set avoidances/dietaryNeeds remain intact
      expect(pref.avoidances).toEqual(['crowds']);
      expect(pref.dietaryNeeds).toEqual(['vegetarian']);
    });

    it('Case 8: duplicate interests are handled consistently (deduplicated)', async () => {
      const payload = {
        interests: [
          'food_cuisine',
          'nature_outdoor',
          'food_cuisine',
          '  nature_outdoor  ',
          'culture_history',
        ],
      };

      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send(payload)
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(res.body.data.interests).toEqual([
        'food_cuisine',
        'nature_outdoor',
        'culture_history',
      ]);
    });
  });

  describe('Validation & Security Invariants', () => {
    it('Case 9: unauthenticated PUT rejected with 401', async () => {
      await request(app.getHttpServer())
        .put('/users/me/preferences')
        .send({ travelStyle: 'BUDGET' })
        .expect(401);
    });

    it('Case 5: negative budget rejected with 400', async () => {
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ budgetMin: -500 })
        .expect(400);

      expect(res.body.success).toBe(false);
    });

    it('Case 6: budgetMin > budgetMax rejected with 400', async () => {
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ budgetMin: 20000000, budgetMax: 10000000 })
        .expect(400);

      expect(res.body.success).toBe(false);
      expect(res.body.message).toContain('không được lớn hơn budgetMax');
    });

    it('Case 7: unknown interest key rejected with 400', async () => {
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ interests: ['food_cuisine', 'free_climbing_extreme'] })
        .expect(400);

      expect(res.body.success).toBe(false);
      expect(res.body.message).toBeDefined();
    });

    it('Case 10: body userId cannot mutate another user (rejected by forbidNonWhitelisted)', async () => {
      // User B tries to pass userAId in body to hijack or mutate
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userBToken}`)
        .send({
          userId: userAId,
          travelStyle: 'BACKPACKER',
        })
        .expect(400);

      expect(res.body.success).toBe(false);

      // Verify User A preferences were NOT modified
      const userAPrefs = await prisma.travelPreference.findUnique({
        where: { userId: userAId },
      });
      expect(userAPrefs?.travelStyle).not.toBe('BACKPACKER');
    });

    it('Case 12: pace is not accepted as production persistence field (rejected with 400)', async () => {
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ pace: 'MODERATE' })
        .expect(400);

      expect(res.body.success).toBe(false);
    });

    it('Case 13: unknown unsupported fields (presence, online, showActivityStatus) rejected with 400', async () => {
      const res = await request(app.getHttpServer())
        .put('/users/me/preferences')
        .set('Authorization', `Bearer ${userAToken}`)
        .send({ presence: 'ONLINE', online: true, showActivityStatus: false })
        .expect(400);

      expect(res.body.success).toBe(false);
    });

    it('Case 11: legacy free-form stored interests remain readable via GET /users/me', async () => {
      // Directly seed a legacy record in DB for User B containing unnormalized tags
      await prisma.travelPreference.create({
        data: {
          userId: userBId,
          travelStyle: 'BACKPACKER',
          budgetMin: 500000,
          budgetMax: 5000000,
          preferredGroup: 'SOLO',
          interests: ['beach', 'mountain', 'historic_architecture', 'street_food_vietnam'],
          avoidances: ['luxury_resorts'],
          dietaryNeeds: ['no_seafood'],
        },
      });

      // Query GET /users/me as User B
      const res = await request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${userBToken}`)
        .expect(200);

      expect(res.body.success).toBe(true);
      const pref = res.body.data.preferences;
      expect(pref).not.toBeNull();
      expect(pref.travelStyle).toBe('BACKPACKER');
      expect(pref.interests).toEqual([
        'beach',
        'mountain',
        'historic_architecture',
        'street_food_vietnam',
      ]);
      expect(pref.avoidances).toEqual(['luxury_resorts']);
      expect(pref.dietaryNeeds).toEqual(['no_seafood']);
    });
  });
});
