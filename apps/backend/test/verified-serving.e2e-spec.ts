import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import * as fs from 'fs';
import * as path from 'path';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';

/**
 * TASK 07.4 regression tests: verified-only default serving + real OSM enrichment.
 */
describe('Verified place serving & OSM enrichment (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const enrichment: any[] = JSON.parse(
    fs.readFileSync(path.resolve(__dirname, '../../../data/curated/places_osm_enrichment.json'), 'utf-8'),
  );

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, forbidNonWhitelisted: true }));
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();
    prisma = app.get(PrismaService);
  });

  afterAll(async () => {
    await app.close();
  });

  it('1. default GET /places returns only verified places', async () => {
    const res = await request(app.getHttpServer()).get('/places?limit=100').expect(200);
    expect(res.body.data.items.length).toBeGreaterThan(0);
    for (const p of res.body.data.items) {
      expect(p.isVerified).toBe(true);
      expect(p.placeSources.length).toBeGreaterThanOrEqual(1);
    }
    const verified = await prisma.place.count({ where: { deletedAt: null, placeSources: { some: {} } } });
    expect(res.body.data.total).toBe(verified);
  });

  it('2. verifiedOnly=false still exposes unsourced dev/test records', async () => {
    const res = await request(app.getHttpServer()).get('/places?verifiedOnly=false&limit=1').expect(200);
    const all = await prisma.place.count({ where: { deletedAt: null } });
    expect(res.body.data.total).toBe(all);
    expect(res.body.data.total).toBeGreaterThan(
      (await request(app.getHttpServer()).get('/places?limit=1').expect(200)).body.data.total,
    );
  });

  it('3. default GET /places/nearby returns only verified places', async () => {
    const res = await request(app.getHttpServer())
      .get('/places/nearby?lat=16.0612&lng=108.2272&radius=25&limit=50')
      .expect(200);
    expect(res.body.data.length).toBeGreaterThan(0);
    for (const p of res.body.data) expect(p.isVerified).toBe(true);
  });

  it.each(['attraction', 'beach', 'culture', 'nature'])(
    '4. category "%s" is populated and every item is verified OSM',
    async (cat) => {
      const res = await request(app.getHttpServer()).get(`/places?category=${cat}&limit=100`).expect(200);
      expect(res.body.data.total).toBeGreaterThan(0);
      for (const p of res.body.data.items) {
        expect(p.category.name).toBe(cat);
        expect(p.isVerified).toBe(true);
        expect(p.placeSources.every((s: any) => s.sourceName === 'osm')).toBe(true);
      }
    },
  );

  it('5. every enrichment record is stored with a well-formed real OSM source id and provenance', async () => {
    expect(enrichment.length).toBeGreaterThan(0);
    for (const e of enrichment) {
      expect(e.sources).toHaveLength(1);
      expect(e.sources[0].source_id).toMatch(/^(node|way|relation)\/\d+$/);
      expect(e.sources[0].osm_base_timestamp).toBeTruthy();
      expect(e.rating).toBeNull();
    }
    const ids = enrichment.map((e) => e.sources[0].source_id);
    expect(new Set(ids).size).toBe(ids.length);
    const inDb = await prisma.placeSource.count({ where: { sourceName: 'osm', sourceId: { in: ids } } });
    expect(inDb).toBe(ids.length);
  });

  it('6. enriched places have valid coordinates and no fabricated rating', async () => {
    const rows = await prisma.place.findMany({ where: { id: { in: enrichment.map((e) => e.id) } } });
    expect(rows.length).toBe(enrichment.length);
    for (const r of rows) {
      expect(r.latitude).toBeGreaterThan(8);
      expect(r.latitude).toBeLessThan(24);
      expect(r.longitude).toBeGreaterThan(102);
      expect(r.longitude).toBeLessThan(110);
      expect(r.rating).toBeNull();
    }
  });
});
