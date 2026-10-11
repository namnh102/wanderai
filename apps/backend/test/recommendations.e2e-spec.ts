import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import * as fs from 'fs';
import * as path from 'path';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';

/**
 * W3-02 e2e: authenticated GET /places/recommendations (NestJS -> FastAPI REC-A).
 * Requires PostgreSQL and the FastAPI ai-service (AI_SERVICE_URL). No LLM is used.
 */
describe('GET /places/recommendations (e2e, REC-A runtime)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let prefToken: string;
  let coldToken: string;
  const createdUserIds: string[] = [];

  const freezeV2: any[] = JSON.parse(
    fs.readFileSync(path.resolve(__dirname, '../../../data/curated/gomate_places_freeze_v2.json'), 'utf-8'),
  );
  const coreIds = new Set(freezeV2.filter((p) => p.is_rec_a_core_v2 === true).map((p) => p.place_id));
  const daNangSecondary = freezeV2.filter(
    (p) => p.is_rec_a_core_v2 === false && p.destination_slug === 'da-nang',
  );

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
    const jwt = app.get(JwtService);
    const hash = await bcrypt.hash('TestPass123!', 10);
    const stamp = Date.now();

    const withPrefs = await prisma.user.create({
      data: {
        email: `test_reca_pref_${stamp}@wanderai.test`,
        passwordHash: hash,
        profile: { create: { displayName: 'RecA Pref' } },
        preferences: { create: { interests: ['culture_history', 'food_cuisine'] } },
      },
    });
    const noPrefs = await prisma.user.create({
      data: {
        email: `test_reca_cold_${stamp}@wanderai.test`,
        passwordHash: hash,
        profile: { create: { displayName: 'RecA Cold' } },
      },
    });
    createdUserIds.push(withPrefs.id, noPrefs.id);
    prefToken = jwt.sign({ sub: withPrefs.id, email: withPrefs.email });
    coldToken = jwt.sign({ sub: noPrefs.id, email: noPrefs.email });
  });

  afterAll(async () => {
    await prisma.user.deleteMany({ where: { id: { in: createdUserIds } } });
    await app.close();
  });

  const get = (qs: string, token: string | null = prefToken) => {
    const r = request(app.getHttpServer()).get(`/places/recommendations${qs}`);
    return token ? r.set('Authorization', `Bearer ${token}`) : r;
  };

  it('1. no JWT -> 401', async () => {
    await get('?destination=da-nang', null).expect(401);
  });

  describe('Da Nang with culture_history + food_cuisine', () => {
    let body: any;
    beforeAll(async () => {
      const res = await get('?destination=da-nang&topK=10').expect(200);
      body = res.body.data;
    });

    it('2/3. returns 200 with 1..topK recommendations', () => {
      expect(body.recommendations.length).toBeGreaterThan(0);
      expect(body.recommendations.length).toBeLessThanOrEqual(10);
    });

    it('4. every item belongs to da-nang and to the REC-A core', () => {
      for (const r of body.recommendations) {
        expect(r.destination_slug).toBe('da-nang');
        expect(coreIds.has(r.place_id)).toBe(true);
      }
    });

    it('5. total_candidates == 289 under the locked dataset', () => {
      expect(body.metadata.total_candidates).toBe(289);
      expect(body.metadata.destination_filter).toBe('da-nang');
      expect(body.metadata.cold_start).toBe(false);
    });

    it('6. none of the 4 Điện Bàn / Quảng Nam secondary POIs appear (even at topK=50)', async () => {
      expect(daNangSecondary).toHaveLength(4);
      const secondaryIds = new Set(daNangSecondary.map((p) => p.place_id));
      const wide = (await get('?destination=da-nang&topK=50').expect(200)).body.data;
      for (const r of [...body.recommendations, ...wide.recommendations]) {
        expect(secondaryIds.has(r.place_id)).toBe(false);
      }
    });

    it('every item carries a taxonomy-derived explanation and no fabricated rating', () => {
      for (const r of body.recommendations) {
        expect(typeof r.explanation.text).toBe('string');
        expect(r.explanation.text.length).toBeGreaterThan(0);
        expect(r.matched_interests.length).toBeGreaterThan(0);
        expect(r).not.toHaveProperty('rating');
      }
    });
  });

  it('Vietnamese alias "Đà Nẵng" resolves to da-nang', async () => {
    const res = await get(`?destination=${encodeURIComponent('Đà Nẵng')}&topK=3`).expect(200);
    expect(res.body.data.metadata.destination_filter).toBe('da-nang');
  });

  it('Hà Nội and Hạ Long return their own core candidates', async () => {
    const hn = (await get('?destination=ha-noi&topK=5').expect(200)).body.data;
    const hl = (await get('?destination=ha-long&topK=5').expect(200)).body.data;
    expect(hn.metadata.total_candidates).toBe(145);
    expect(hl.metadata.total_candidates).toBe(188);
    expect(hn.recommendations.every((r: any) => r.destination_slug === 'ha-noi')).toBe(true);
    expect(hl.recommendations.every((r: any) => r.destination_slug === 'ha-long')).toBe(true);
  });

  describe('input validation is owned by NestJS (400, readable message)', () => {
    it('7. unknown destination (Paris) -> 400, never "all destinations"', async () => {
      const res = await get('?destination=Paris').expect(400);
      expect(typeof res.body.message).toBe('string');
      expect(res.body.message).toContain('Điểm đến không được hỗ trợ');
    });

    it.each([
      ['8. topK=0', '?destination=da-nang&topK=0'],
      ['9. topK=51', '?destination=da-nang&topK=51'],
      ['10. topK=abc', '?destination=da-nang&topK=abc'],
      ['topK=-3', '?destination=da-nang&topK=-3'],
      ['topK=2.5', '?destination=da-nang&topK=2.5'],
    ])('%s -> 400', async (_n, qs) => {
      const res = await get(qs).expect(400);
      expect(typeof res.body.message).toBe('string');
      expect(res.body.message).toContain('topK');
    });

    it('11. model=zzz -> 400', async () => {
      const res = await get('?destination=da-nang&model=zzz').expect(400);
      expect(typeof res.body.message).toBe('string');
      expect(res.body.message).toContain('model');
    });

    it('12. rec-a0 accepted', async () => {
      const res = await get('?destination=da-nang&model=rec-a0&topK=3').expect(200);
      expect(res.body.data.metadata.model).toBe('rec-a0');
    });

    it('13. rec-a1 accepted (and is the default)', async () => {
      const explicit = await get('?destination=da-nang&model=rec-a1&topK=3').expect(200);
      const dflt = await get('?destination=da-nang&topK=3').expect(200);
      expect(explicit.body.data.metadata.model).toBe('rec-a1');
      expect(dflt.body.data.metadata.model).toBe('rec-a1');
    });

    it('defaults: topK=10 when omitted, destination omitted -> all 622 core candidates (explicit, not an error)', async () => {
      const res = await get('').expect(200);
      expect(res.body.data.recommendations).toHaveLength(10);
      expect(res.body.data.metadata.total_candidates).toBe(622);
    });
  });

  it('14. user without a preference row -> cold_start=true (valid 200)', async () => {
    const res = await get('?destination=da-nang&topK=5', coldToken).expect(200);
    expect(res.body.data.metadata.cold_start).toBe(true);
    expect(res.body.data.recommendations.length).toBeGreaterThan(0);
  });
});
