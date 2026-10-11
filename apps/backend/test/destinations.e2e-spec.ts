import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';

describe('DestinationsController (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, forbidNonWhitelisted: true }));
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /destinations', () => {
    it('should return 200 with paginated destination list', () => {
      return request(app.getHttpServer())
        .get('/destinations')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(res.body).toHaveProperty('data');
          expect(res.body.data).toHaveProperty('items');
          expect(res.body.data).toHaveProperty('total');
          expect(Array.isArray(res.body.data.items)).toBe(true);
          expect(typeof res.body.data.total).toBe('number');
        });
    });

    it('should return destinations with expected fields', () => {
      return request(app.getHttpServer())
        .get('/destinations?limit=1')
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          expect(items.length).toBeGreaterThanOrEqual(1);
          const dest = items[0];
          expect(dest).toHaveProperty('id');
          expect(dest).toHaveProperty('name');
          expect(dest).toHaveProperty('slug');
          expect(dest).toHaveProperty('province');
          expect(dest).toHaveProperty('region');
          expect(dest).toHaveProperty('latitude');
          expect(dest).toHaveProperty('longitude');
          expect(dest).toHaveProperty('rating');
        });
    });

    it('should respect limit parameter', () => {
      return request(app.getHttpServer())
        .get('/destinations?limit=5')
        .expect(200)
        .expect((res) => {
          expect(res.body.data.items.length).toBeLessThanOrEqual(5);
        });
    });

    it('should filter by region', () => {
      return request(app.getHttpServer())
        .get('/destinations?region=north')
        .expect(200)
        .expect((res) => {
          const items = res.body.data.items;
          items.forEach((dest: any) => {
            expect(dest.region).toBe('north');
          });
        });
    });
  });

  describe('GET /destinations/popular', () => {
    it('should return popular destinations', () => {
      return request(app.getHttpServer())
        .get('/destinations/popular')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('success', true);
          expect(Array.isArray(res.body.data)).toBe(true);
        });
    });
  });
});
