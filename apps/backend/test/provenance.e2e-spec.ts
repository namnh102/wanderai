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
 * TASK 07.3 regression tests: provenance and data integrity of the verified place path.
 * These run against the real dev database that the other e2e suites use.
 */
describe('Provenance & data integrity (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const manifest = JSON.parse(
    fs.readFileSync(path.resolve(__dirname, '../../../data/manifests/osm-invalid-sources.json'), 'utf-8'),
  );
  const invalidIds: string[] = manifest.invalid_sources.map((s: any) => s.source_id);

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
  });

  afterAll(async () => {
    await app.close();
  });

  async function allVerified() {
    const items: any[] = [];
    for (let page = 1; page < 20; page++) {
      const res = await request(app.getHttpServer())
        .get(`/places?verifiedOnly=true&limit=100&page=${page}`)
        .expect(200);
      items.push(...res.body.data.items);
      if (page >= res.body.data.totalPages) break;
    }
    return items;
  }

  it('1. denylisted (non-genuine) OSM source ids are absent from place_sources', async () => {
    expect(invalidIds).toHaveLength(13);
    const n = await prisma.placeSource.count({
      where: { sourceName: 'osm', sourceId: { in: invalidIds } },
    });
    expect(n).toBe(0);
  });

  it('2. verifiedOnly returns only places with a source, valid coordinates and no denylisted source', async () => {
    const items = await allVerified();
    expect(items.length).toBeGreaterThan(0);
    for (const p of items) {
      expect(p.isVerified).toBe(true);
      expect(p.placeSources.length).toBeGreaterThan(0);
      expect(typeof p.latitude).toBe('number');
      expect(typeof p.longitude).toBe('number');
      for (const s of p.placeSources) {
        expect(invalidIds).not.toContain(s.sourceId);
      }
    }
  });

  it('3. no fabricated ratings: no 4.5-with-zero-reviews and no 0 default; rating is NULL or real', async () => {
    expect(await prisma.place.count({ where: { rating: 4.5, reviewCount: 0 } })).toBe(0);
    expect(await prisma.place.count({ where: { rating: 0 } })).toBe(0);
    const unrated = await prisma.place.count({ where: { rating: null } });
    expect(unrated).toBeGreaterThan(0);

    const items = await allVerified();
    for (const p of items) {
      if (p.reviewCount === 0) expect(p.rating).toBeNull();
    }
  });

  it('4. unavailable rating is serialized as null by /places/nearby', async () => {
    const res = await request(app.getHttpServer())
      .get('/places/nearby?lat=16.0612&lng=108.2272&radius=25&verifiedOnly=true&limit=50')
      .expect(200);
    const rows = res.body.data;
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) {
      expect(r.rating === null || typeof r.rating === 'number').toBe(true);
      if (r.reviewCount === 0) expect(r.rating).toBeNull();
    }
  });

  it('5. synthetic reviews are quarantined (untrusted) and never exposed or aggregated', async () => {
    expect(await prisma.review.count({ where: { source: 'synthetic', trusted: true } })).toBe(0);
    const synthetic = await prisma.review.findMany({ where: { source: 'synthetic' } });
    expect(synthetic.length).toBeGreaterThan(0);
    for (const r of synthetic) {
      expect(r.trusted).toBe(false);
      const res = await request(app.getHttpServer()).get(`/places/${r.placeId}`).expect(200);
      const ids = res.body.data.reviews.map((x: any) => x.id);
      expect(ids).not.toContain(r.id);
    }
    // no place aggregate is derived from untrusted reviews
    expect(await prisma.place.count({ where: { reviewCount: { gt: 0 } } })).toBe(
      (
        await prisma.review.groupBy({
          by: ['placeId'],
          where: { trusted: true, deletedAt: null },
        })
      ).length,
    );
  });

  it('6. no RAG chunk is linked to a place without verified provenance; quarantine keeps the evidence', async () => {
    const col = await prisma.$queryRaw<any[]>`
      SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'place_id'`;
    if (col.length === 0) return; // fresh DB without the raw-SQL RAG columns
    const bad = await prisma.$queryRaw<any[]>`
      SELECT count(*)::int AS n FROM documents d
      WHERE d.place_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = d.place_id)`;
    expect(bad[0].n).toBe(0);
    const mislabelled = await prisma.$queryRaw<any[]>`
      SELECT count(*)::int AS n FROM documents d
      WHERE d.source_name = 'osm' AND d.place_id IS NULL`;
    expect(mislabelled[0].n).toBe(0);
  });
});
