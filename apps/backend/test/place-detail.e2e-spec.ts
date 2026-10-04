import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';

// TASK 08 — GET /places/:id returns only factual, provenance-backed fields.
describe('Place Detail (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const getDetail = async (id: string) =>
    (await request(app.getHttpServer()).get(`/places/${id}`).expect(200)).body.data;

  const osmSourceWith = async (present: string[], absent: string[]) => {
    const rows = await prisma.placeSource.findMany({ where: { sourceName: 'osm' } });
    return rows.find((r) => {
      const tags = (r.rawData ?? {}) as Record<string, unknown>;
      return present.every((k) => !!tags[k]) && absent.every((k) => !tags[k]);
    });
  };

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
  });

  afterAll(async () => {
    await app.close();
  });

  it('returns a verified place with OSM provenance and canonical URL', async () => {
    const src = await prisma.placeSource.findFirst({ where: { sourceName: 'osm' } });
    expect(src).toBeTruthy();
    const p = await getDetail(src!.placeId);
    expect(p.isVerified).toBe(true);
    expect(p.provenanceCount).toBeGreaterThanOrEqual(1);
    expect(p.source).toEqual({
      name: 'OpenStreetMap',
      sourceId: src!.sourceId,
      canonicalUrl: `https://www.openstreetmap.org/${src!.sourceId}`,
      license: 'ODbL 1.0',
      attribution: '© OpenStreetMap contributors',
    });
    expect(p.placeSources[0]).not.toHaveProperty('rawData');
    expect(p.placeSources[0].canonicalUrl).toBe(`https://www.openstreetmap.org/${src!.sourceId}`);
    expect(typeof p.latitude).toBe('number');
    expect(typeof p.longitude).toBe('number');
    expect(p.category).toBeTruthy();
    expect(p.destination).toBeTruthy();
  });

  it('never fabricates rating: null rating stays null', async () => {
    const src = await prisma.placeSource.findFirst({ where: { sourceName: 'osm', place: { rating: null } } });
    expect(src).toBeTruthy();
    const p = await getDetail(src!.placeId);
    expect(p.rating).toBeNull();
    expect(p.reviewCount).toBe(0);
  });

  it('returns 400 for an invalid UUID', async () => {
    await request(app.getHttpServer()).get('/places/not-a-uuid').expect(400);
  });

  it('returns 404 for a non-existent UUID', async () => {
    await request(app.getHttpServer()).get('/places/00000000-0000-0000-0000-000000000000').expect(404);
  });

  it('unverified place gets no verified badge, no source and no descriptive facts', async () => {
    const place = await prisma.place.findFirst({
      where: { deletedAt: null, placeSources: { none: {} } },
    });
    expect(place).toBeTruthy();
    const p = await getDetail(place!.id);
    expect(p.isVerified).toBe(false);
    expect(p.provenanceCount).toBe(0);
    expect(p.source).toBeNull();
    expect(p.placeSources).toEqual([]);
    expect(p.address).toBeNull();
    expect(p.description).toBeNull();
    expect(p.openingHours).toBeNull();
    expect(p.website).toBeNull();
    expect(p.phone).toBeNull();
  });

  it('missing optional fields are null, not invented', async () => {
    const src = await osmSourceWith([], ['opening_hours', 'website', 'contact:website', 'phone', 'contact:phone']);
    expect(src).toBeTruthy();
    const p = await getDetail(src!.placeId);
    expect(p.isVerified).toBe(true);
    expect(p.openingHours).toBeNull();
    expect(p.website).toBeNull();
    expect(p.phone).toBeNull();
  });

  it('exposes opening hours, website and phone exactly as stored in OSM tags', async () => {
    const withHours = await osmSourceWith(['opening_hours'], []);
    expect(withHours).toBeTruthy();
    const h = await getDetail(withHours!.placeId);
    expect(h.openingHours).toBe(((withHours!.rawData as any).opening_hours as string).trim());

    const withSite = await osmSourceWith(['website'], []);
    expect(withSite).toBeTruthy();
    const w = await getDetail(withSite!.placeId);
    expect(w.website).toBe(((withSite!.rawData as any).website as string).trim());

    const withPhone = await osmSourceWith(['phone'], []);
    expect(withPhone).toBeTruthy();
    const ph = await getDetail(withPhone!.placeId);
    expect(ph.phone).toBe(((withPhone!.rawData as any).phone as string).trim());
  });

  it('never exposes untrusted (synthetic) reviews', async () => {
    const synthetic = await prisma.review.findFirst({ where: { trusted: false } });
    if (!synthetic) return; // no synthetic reviews present — nothing to leak
    const p = await getDetail(synthetic.placeId);
    expect(p.reviews.map((r: any) => r.id)).not.toContain(synthetic.id);
    for (const r of p.reviews) expect(r.trusted).toBe(true);
  });

  it('verifiedOnly list semantics unchanged: default list excludes unsourced places', async () => {
    const res = await request(app.getHttpServer()).get('/places?limit=50').expect(200);
    for (const item of res.body.data.items) expect(item.isVerified).toBe(true);
  });
});
