import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';

describe('PlacesController (e2e)', () => {
  let app: INestApplication;
  let samplePlaceId: string;

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
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /places', () => {
    it('should return 200 with paginated place list', () => {
      return request(app.getHttpServer())
        .get('/places')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(res.body).toHaveProperty('data');
          expect(res.body.data).toHaveProperty('items');
          expect(res.body.data).toHaveProperty('total');
          expect(Array.isArray(res.body.data.items)).toBe(true);
          expect(res.body.data.total).toBeGreaterThanOrEqual(97); // default = verified places only

          if (res.body.data.items.length > 0) {
            samplePlaceId = res.body.data.items[0].id;
          }
        });
    });

    it('should return places with canonical structure and relations', () => {
      return request(app.getHttpServer())
        .get('/places?limit=5')
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          expect(items.length).toBeGreaterThanOrEqual(1);
          const p = items[0];
          expect(p).toHaveProperty('id');
          expect(p).toHaveProperty('name');
          expect(p).toHaveProperty('latitude');
          expect(p).toHaveProperty('longitude');
          expect(p).toHaveProperty('destination');
          expect(p).toHaveProperty('category');
          expect(p).toHaveProperty('placeSources');
        });
    });

    it('should filter places by category', () => {
      return request(app.getHttpServer())
        .get('/places?category=attraction&limit=10')
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          expect(Array.isArray(items)).toBe(true);
          for (const p of items) {
            if (p.category) {
              expect(p.category.name.toLowerCase()).toBe('attraction');
            }
          }
        });
    });

    it('should search places by name', () => {
      return request(app.getHttpServer())
        .get('/places?search=Rồng&verifiedOnly=false') // legacy unsourced record: only visible when explicitly requested
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          expect(items.length).toBeGreaterThanOrEqual(1);
          const hasMatch = items.some((p: any) =>
            p.name.toLowerCase().includes('rồng') || (p.nameEn && p.nameEn.toLowerCase().includes('dragon')),
          );
          expect(hasMatch).toBe(true);
        });
    });

    it('should filter strictly by verifiedOnly=true isolating synthetic records', () => {
      return request(app.getHttpServer())
        .get('/places?verifiedOnly=true&limit=200')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(res.body.data.total).toBeGreaterThanOrEqual(97); // genuine OSM provenance only (TASK 07.3 quarantine + TASK 07.4 enrichment)
          const items = res.body.data.items;
          expect(items.length).toBeGreaterThanOrEqual(97);
          for (const item of items) {
            expect(item.isVerified).toBe(true);
            expect(item.placeSources.length).toBeGreaterThanOrEqual(1);
          }
        });
    });

    it('should accurately flag unverified legacy seed places as isVerified: false', () => {
      return request(app.getHttpServer())
        .get('/places?limit=100&verifiedOnly=false')
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          const unverifiedItems = items.filter((p: any) => p.isVerified === false);
          if (unverifiedItems.length > 0) {
            for (const item of unverifiedItems) {
              expect(item.placeSources).toHaveLength(0);
              expect(item.provenanceCount).toBe(0);
            }
          }
        });
    });
  });

  describe('GET /places/nearby (PostGIS Spatial)', () => {
    it('should return nearby places within radius using PostGIS ST_DWithin', () => {
      // Coordinates near Dragon Bridge / My Khe Beach, Da Nang
      return request(app.getHttpServer())
        .get('/places/nearby?lat=16.0612&lng=108.2272&radius=15')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(Array.isArray(res.body.data)).toBe(true);
          expect(res.body.data.length).toBeGreaterThan(0);
          const nearest = res.body.data[0];
          expect(nearest).toHaveProperty('id');
          expect(nearest).toHaveProperty('name');
          expect(nearest).toHaveProperty('distanceKm');
          expect(typeof nearest.distanceKm).toBe('number');
          expect(nearest.distanceKm).toBeLessThanOrEqual(15);
        });
    });

    it('should filter nearby places with verifiedOnly=true', () => {
      return request(app.getHttpServer())
        .get('/places/nearby?lat=16.0612&lng=108.2272&radius=15&verifiedOnly=true')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(Array.isArray(res.body.data)).toBe(true);
          for (const place of res.body.data) {
            expect(place.isVerified).toBe(true);
          }
        });
    });
  });

  describe('GET /places/:id', () => {
    it('should return detailed place with source provenance and reviews', () => {
      expect(samplePlaceId).toBeDefined();
      return request(app.getHttpServer())
        .get(`/places/${samplePlaceId}`)
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          const p = res.body.data;
          expect(p.id).toBe(samplePlaceId);
          expect(p).toHaveProperty('placeSources');
          expect(Array.isArray(p.placeSources)).toBe(true);
          expect(p).toHaveProperty('reviews');
          expect(Array.isArray(p.reviews)).toBe(true);
        });
    });

    it('should return 404 for non-existent place UUID', () => {
      return request(app.getHttpServer())
        .get('/places/00000000-0000-0000-0000-000000000000')
        .expect(404);
    });
  });
});
