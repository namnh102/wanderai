import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { osmAddress, osmPhone, osmTag, osmWebsite } from '../src/modules/places/osm-tags';
import { trustedDestinationRating } from '../src/modules/destinations/destination-trust';

// W3-04 — place contract & data trust hardening (PDG-001..006, PDG-013).
describe('W3-04 place contract hardening (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  const http = () => request(app.getHttpServer());

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

  describe('A. OSM tag extraction (PDG-001)', () => {
    it('reads canonical nested rawData.tags', () => {
      const raw = { tags: { 'addr:street': 'Lý Thường Kiệt', 'addr:city': 'Hà Nội', website: 'https://a.vn', phone: '+84 1' } };
      expect(osmAddress(raw)).toBe('Lý Thường Kiệt, Hà Nội');
      expect(osmWebsite(raw)).toBe('https://a.vn');
      expect(osmPhone(raw)).toBe('+84 1');
    });

    it('falls back to historical flat keys', () => {
      const raw = { 'addr:housenumber': '5', 'addr:street': 'Hàng Bài', 'contact:website': 'https://b.vn', 'contact:phone': '+84 2' };
      expect(osmAddress(raw)).toBe('5 Hàng Bài');
      expect(osmWebsite(raw)).toBe('https://b.vn');
      expect(osmPhone(raw)).toBe('+84 2');
    });

    it('nested wins when both shapes exist', () => {
      const raw = { website: 'https://flat.vn', 'addr:city': 'Flat', tags: { website: 'https://nested.vn', 'addr:city': 'Nested' } };
      expect(osmTag(raw, 'website')).toBe('https://nested.vn');
      expect(osmAddress(raw)).toBe('Nested');
    });

    it('absent / blank tags -> null (never invented)', () => {
      expect(osmAddress({})).toBeNull();
      expect(osmAddress(null)).toBeNull();
      expect(osmAddress({ tags: { name: 'X', 'addr:city': '   ' } })).toBeNull();
      expect(osmWebsite({ tags: {} })).toBeNull();
      expect(osmPhone(undefined)).toBeNull();
      expect(osmTag({ tags: 'not-an-object' as any }, 'website')).toBeNull();
    });

    it('importer-generated places.address is never served', async () => {
      const rows = await prisma.place.findMany({
        where: { deletedAt: null, address: { not: null }, placeSources: { some: {} } },
        take: 60,
      });
      expect(rows.length).toBeGreaterThan(0);
      for (const place of rows) {
        const src = await prisma.placeSource.findFirst({ where: { placeId: place.id, sourceName: 'osm' } });
        const d = (await http().get(`/places/${place.id}`).expect(200)).body.data;
        // Served address derives from OSM tags only (null when none), never from the importer column.
        expect(d.address).toBe(osmAddress((src?.rawData ?? null) as any));
      }
    });

    it('every OSM place: address/website/phone served == DB tags (nested first), none lost', async () => {
      const sources = await prisma.placeSource.findMany({ where: { sourceName: 'osm' } });
      expect(sources.length).toBeGreaterThan(100);
      let available = 0;
      for (const s of sources.slice(0, 250)) {
        const raw = (s.rawData ?? null) as any;
        const d = (await http().get(`/places/${s.placeId}`).expect(200)).body.data;
        expect(d.address).toBe(osmAddress(raw));
        expect(d.website).toBe(osmWebsite(raw));
        expect(d.phone).toBe(osmPhone(raw));
        if (osmAddress(raw)) available++;
      }
      expect(available).toBeGreaterThan(0);
    });

    it('nearby SQL extractor equals TypeScript extractor, including nested-only records', async () => {
      const res = await http().get('/places/nearby?lat=21.0285&lng=105.8542&radius=20&limit=100').expect(200);
      const items: any[] = res.body.data;
      expect(items.length).toBeGreaterThan(0);
      let withAddress = 0;
      for (const it of items) {
        const src = await prisma.placeSource.findFirst({ where: { placeId: it.id, sourceName: 'osm' } });
        expect(it.address).toBe(osmAddress((src?.rawData ?? null) as any));
        if (it.address) withAddress++;
      }
      expect(withAddress).toBeGreaterThan(0);
    });
  });

  describe('B. Deterministic pagination (PDG-002)', () => {
    const walk = async (verifiedOnly: boolean, size: number) => {
      const ids: string[] = [];
      let total = 0;
      for (let page = 1; page < 500; page++) {
        const res = await http().get(`/places?verifiedOnly=${verifiedOnly}&limit=${size}&page=${page}`).expect(200);
        total = res.body.data.total;
        if (res.body.data.items.length === 0) break;
        ids.push(...res.body.data.items.map((i: any) => i.id));
      }
      return { ids, total };
    };

    it.each([10, 50, 100])('verifiedOnly=true, limit=%i: no duplicates, no missing', async (size) => {
      const { ids, total } = await walk(true, size);
      expect(new Set(ids).size).toBe(ids.length);
      expect(ids.length).toBe(total);
    }, 60000);

    it('verifiedOnly=false, limit=20: no duplicates, no missing', async () => {
      const { ids, total } = await walk(false, 20);
      expect(new Set(ids).size).toBe(ids.length);
      expect(ids.length).toBe(total);
    }, 60000);

    it('same page requested twice is identical and pages are disjoint', async () => {
      const a = (await http().get('/places?limit=50&page=2').expect(200)).body.data.items.map((i: any) => i.id);
      const b = (await http().get('/places?limit=50&page=2').expect(200)).body.data.items.map((i: any) => i.id);
      const p1 = (await http().get('/places?limit=50&page=1').expect(200)).body.data.items.map((i: any) => i.id);
      expect(a).toEqual(b);
      expect(a.filter((x: string) => p1.includes(x))).toEqual([]);
    });
  });

  describe('C/D. Query validation (PDG-005, PDG-006, PDG-013)', () => {
    it.each([
      '/places?page=0',
      '/places?page=abc',
      '/places?limit=0',
      '/places?limit=-5',
      '/places?limit=101',
      '/places?limit=abc',
      '/places?destinationId=ha-noi',
      '/places?destinationId=not-a-uuid',
      '/places?verifiedOnly=maybe',
      '/places/nearby?lat=abc&lng=105',
      '/places/nearby?lat=91&lng=105',
      '/places/nearby?lat=-91&lng=105',
      '/places/nearby?lat=10&lng=181',
      '/places/nearby?lat=10&lng=-181',
      '/places/nearby?lat=10',
      '/places/nearby?lng=105',
      '/places/nearby',
      '/places/nearby?lat=10&lng=105&radius=0',
      '/places/nearby?lat=10&lng=105&radius=abc',
      '/places/nearby?lat=10&lng=105&limit=101',
      '/places/nearby?lat=10&lng=105&limit=0',
    ])('400 with a readable message: %s', async (url) => {
      const res = await http().get(url).expect(400);
      expect(res.body.success).toBe(false);
      expect(typeof res.body.message).toBe('string');
      expect(res.body.message.length).toBeGreaterThan(0);
      expect(JSON.stringify(res.body)).not.toMatch(/stack|constraints|Error:/);
    });

    it('valid defaults and boundaries are accepted', async () => {
      const def = (await http().get('/places').expect(200)).body.data;
      expect(def.page).toBe(1);
      expect(def.limit).toBe(20);
      expect(def.items.length).toBeLessThanOrEqual(20);
      await http().get('/places?limit=1&page=1').expect(200);
      await http().get('/places?limit=100').expect(200);
      const dest = await prisma.destination.findFirst({ where: { slug: 'ha-noi' } });
      await http().get(`/places?destinationId=${dest!.id}&limit=1`).expect(200);
      await http().get('/places?verifiedOnly=false&limit=1').expect(200);
      await http().get('/places/nearby?lat=16.0612&lng=108.2272').expect(200);
      await http().get('/places/nearby?lat=90&lng=-180&radius=0.5&limit=1').expect(200);
    });
  });

  describe('E. Destination rating trust (PDG-003)', () => {
    it('trustedDestinationRating exposes only review-backed ratings', () => {
      expect(trustedDestinationRating(4.8, 0)).toBeNull();
      expect(trustedDestinationRating(0, 10)).toBeNull();
      expect(trustedDestinationRating(null, 10)).toBeNull();
      expect(trustedDestinationRating(4.2, 3)).toBe(4.2);
    });

    it('list / popular / nearby / detail never expose a synthetic numeric rating', async () => {
      const synthetic = await prisma.destination.count({ where: { rating: { gt: 0 }, reviewCount: 0 } });
      expect(synthetic).toBeGreaterThan(0); // proves there is synthetic data to hide
      const list = (await http().get('/destinations?limit=50').expect(200)).body.data.items;
      for (const d of list) if (d.reviewCount === 0) expect(d.rating).toBeNull();
      const popular = (await http().get('/destinations/popular?limit=50').expect(200)).body.data;
      for (const d of popular) if (d.reviewCount === 0) expect(d.rating).toBeNull();
      const nearby = (await http().get('/destinations/nearby?lat=21.0285&lng=105.8542&radius=500').expect(200)).body.data;
      expect(nearby.length).toBeGreaterThan(0);
      for (const d of nearby) expect(d.rating).toBeNull();
      const hn = await prisma.destination.findFirst({ where: { slug: 'ha-noi' } });
      const detail = (await http().get(`/destinations/${hn!.id}`).expect(200)).body.data;
      expect(detail.rating).toBeNull();
      for (const p of detail.places) {
        expect(p).not.toHaveProperty('priceMin');
        expect(p).not.toHaveProperty('priceMax');
      }
    });

    it('place detail embeds a destination without a synthetic rating', async () => {
      const src = await prisma.placeSource.findFirst({ where: { sourceName: 'osm' } });
      const d = (await http().get(`/places/${src!.placeId}`).expect(200)).body.data;
      expect(d.destination.rating).toBeNull();
    });
  });

  describe('F. Legacy unverified places (PDG-004)', () => {
    it('legacy price never leaks; unverified detail is 404 (no real dependency)', async () => {
      const legacy = await prisma.place.findMany({ where: { deletedAt: null, placeSources: { none: {} } }, take: 40 });
      expect(legacy.length).toBeGreaterThan(0);
      for (const p of legacy) await http().get(`/places/${p.id}`).expect(404);
      const priced = await prisma.place.count({ where: { priceMin: { not: null } } });
      expect(priced).toBeGreaterThan(0); // legacy prices exist in DB but are never exposed
      for (let page = 1; page <= 10; page++) {
        const res = await http().get(`/places?verifiedOnly=false&limit=100&page=${page}`).expect(200);
        if (res.body.data.items.length === 0) break;
        for (const it of res.body.data.items) {
          expect(it).not.toHaveProperty('priceMin');
          expect(it).not.toHaveProperty('priceMax');
        }
      }
    });

    it('no itinerary item references an unverified place (dependency scan)', async () => {
      const n = await prisma.itineraryItem.count({ where: { place: { placeSources: { none: {} } } } });
      expect(n).toBe(0);
    });
  });
});
