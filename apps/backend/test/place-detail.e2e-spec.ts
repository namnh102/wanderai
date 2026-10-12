import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { osmAddress, osmTag } from '../src/modules/places/osm-tags';
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
      const raw = (r.rawData ?? {}) as Record<string, unknown>;
      return present.every((k) => !!osmTag(raw, k)) && absent.every((k) => !osmTag(raw, k));
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

  it('PDG-004: legacy unverified place is not publicly servable (404)', async () => {
    const place = await prisma.place.findFirst({
      where: { deletedAt: null, placeSources: { none: {} } },
    });
    expect(place).toBeTruthy();
    await request(app.getHttpServer()).get(`/places/${place!.id}`).expect(404);
  });

  it('PDG-004: detail never exposes legacy priceMin/priceMax', async () => {
    const legacyPriced = await prisma.place.findFirst({
      where: { deletedAt: null, priceMin: { not: null }, placeSources: { some: {} } },
    });
    const src = await prisma.placeSource.findFirst({ where: { sourceName: 'osm' } });
    for (const id of [legacyPriced?.id, src!.placeId].filter(Boolean) as string[]) {
      const p = await getDetail(id);
      expect(p).not.toHaveProperty('priceMin');
      expect(p).not.toHaveProperty('priceMax');
    }
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
    expect(h.openingHours).toBe(osmTag(withHours!.rawData as any, 'opening_hours'));

    const withSite = await osmSourceWith(['website'], []);
    expect(withSite).toBeTruthy();
    const w = await getDetail(withSite!.placeId);
    expect(w.website).toBe(osmTag(withSite!.rawData as any, 'website'));

    const withPhone = await osmSourceWith(['phone'], []);
    expect(withPhone).toBeTruthy();
    const ph = await getDetail(withPhone!.placeId);
    expect(ph.phone).toBe(osmTag(withPhone!.rawData as any, 'phone'));
  });

  it('never exposes untrusted (synthetic) reviews', async () => {
    const synthetic = await prisma.review.findFirst({ where: { trusted: false } });
    if (!synthetic) return; // no synthetic reviews present — nothing to leak
    const res = await request(app.getHttpServer()).get(`/places/${synthetic.placeId}`);
    if (res.status === 404) return; // legacy unverified place: not publicly servable (W3-04)
    expect(res.status).toBe(200);
    const p = res.body.data;
    expect(p.reviews.map((r: any) => r.id)).not.toContain(synthetic.id);
    for (const r of p.reviews) expect(r.trusted).toBe(true);
  });

  it('verifiedOnly list semantics unchanged: default list excludes unsourced places', async () => {
    const res = await request(app.getHttpServer()).get('/places?limit=50').expect(200);
    for (const item of res.body.data.items) expect(item.isVerified).toBe(true);
  });

  describe('factual address semantics (list = nearby = detail)', () => {
    it('osmAddress joins only real addr:* tags and never invents', () => {
      expect(osmAddress({})).toBeNull();
      expect(osmAddress(null)).toBeNull();
      expect(osmAddress({ name: 'Chùa X', amenity: 'x' })).toBeNull();
      expect(osmAddress({ 'addr:city': '  ' })).toBeNull();
      expect(
        osmAddress({
          'addr:housenumber': '46',
          'addr:street': 'Thanh Niên',
          'addr:suburb': 'Tây Hồ',
          'addr:city': 'Hà Nội',
        }),
      ).toBe('46 Thanh Niên, Tây Hồ, Hà Nội');
      expect(osmAddress({ 'addr:street': 'Thanh Niên' })).toBe('Thanh Niên');
    });

    it('detail never serves the importer-generated "<name>, <city>" address', async () => {
      const place = await prisma.place.findFirst({
        where: { deletedAt: null, address: { not: null }, placeSources: { some: {} } },
      });
      expect(place).toBeTruthy();
      expect(place!.address).toContain(','); // stored column is importer text
      const p = await getDetail(place!.id);
      const src = await prisma.placeSource.findFirst({ where: { placeId: place!.id, sourceName: 'osm' } });
      expect(p.address).toBe(osmAddress((src?.rawData ?? null) as any));
      if (p.address) expect(p.address).not.toBe(place!.address);
    });

    it('nearby (SQL) address equals the shared osmAddress for every verified place in range', async () => {
      const res = await request(app.getHttpServer())
        .get('/places/nearby?lat=21.0285&lng=105.8542&radius=100&limit=100')
        .expect(200);
      const items: any[] = res.body.data;
      expect(items.length).toBeGreaterThan(0);
      for (const it of items) {
        const src = await prisma.placeSource.findFirst({ where: { placeId: it.id, sourceName: 'osm' } });
        expect(it.address).toBe(osmAddress((src?.rawData ?? null) as any));
        if (it.address) expect(it.address).not.toBe(`${it.name}, ${it.destinationName}`);
      }
    });

    it('list address equals detail address and never exposes rawData', async () => {
      const res = await request(app.getHttpServer()).get('/places?limit=30').expect(200);
      for (const it of res.body.data.items) {
        for (const s of it.placeSources) expect(s).not.toHaveProperty('rawData');
        const d = await getDetail(it.id);
        expect(it.address).toBe(d.address);
      }
    });

    it('unverified place has null address and no price in list (verifiedOnly=false)', async () => {
      const unverified: any[] = [];
      for (let page = 1; page <= 20; page++) {
        const res = await request(app.getHttpServer())
          .get(`/places?verifiedOnly=false&limit=100&page=${page}`)
          .expect(200);
        if (res.body.data.items.length === 0) break;
        unverified.push(...res.body.data.items.filter((i: any) => !i.isVerified));
      }
      expect(unverified.length).toBeGreaterThan(0);
      for (const it of unverified) {
        expect(it.address).toBeNull();
        expect(it).not.toHaveProperty('priceMin');
        expect(it).not.toHaveProperty('priceMax');
      }
    });
  });
});
