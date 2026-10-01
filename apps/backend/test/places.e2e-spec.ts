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
          expect(res.body.data.total).toBeGreaterThanOrEqual(100);

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
        .get('/places?search=Rồng')
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
