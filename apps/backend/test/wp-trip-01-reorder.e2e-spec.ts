import './e2e-harness/harness-env';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { PrismaService } from '../src/prisma/prisma.service';

const PLACE_A_THAP_DONG_HO = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const PLACE_B_BAO_TANG_QN = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';

describe('WP-TRIP-01 Itinerary Reorder Persistence (PostgreSQL E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    process.env.JWT_SECRET =
      process.env.JWT_SECRET ||
      'wp-trip-01-e2e-access-secret-key-at-least-32-chars!!';
    process.env.JWT_REFRESH_SECRET =
      process.env.JWT_REFRESH_SECRET ||
      'wp-trip-01-e2e-refresh-secret-key-at-least-32-chars!';

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
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('persists A -> B reordered to B -> A in PostgreSQL and returns B -> A on fresh GET /trips/:id', async () => {
    const stamp = Date.now();
    const email = `wp_trip_01_e2e_${stamp}@gomate.vn`;
    const password = 'WpTrip01#Password';

    const regRes = await request(app.getHttpServer())
      .post('/auth/register')
      .send({
        name: 'WP-TRIP-01 Tester',
        email,
        password,
      })
      .expect(201);

    const token = regRes.body.data.access_token as string;
    expect(token).toBeTruthy();

    const destsRes = await request(app.getHttpServer())
      .get('/destinations')
      .expect(200);
    const haLong = (destsRes.body.data.items as Array<{ id: string; slug: string }>).find(
      (d) => d.slug === 'ha-long',
    );
    expect(haLong).toBeDefined();

    const tripRes = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${token}`)
      .send({
        title: `Nghiệm thu WP-TRIP-01 ${stamp}`,
        destinationId: haLong!.id,
      })
      .expect(201);
    const tripId = tripRes.body.data.id as string;

    const itemARes = await request(app.getHttpServer())
      .post(`/trips/${tripId}/itinerary`)
      .set('Authorization', `Bearer ${token}`)
      .send({
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: PLACE_A_THAP_DONG_HO,
      })
      .expect(201);
    const itemBRes = await request(app.getHttpServer())
      .post(`/trips/${tripId}/itinerary`)
      .set('Authorization', `Bearer ${token}`)
      .send({
        dayNumber: 1,
        activity: 'Tham quan Bảo tàng Quảng Ninh',
        placeId: PLACE_B_BAO_TANG_QN,
      })
      .expect(201);

    const itemAId = itemARes.body.data.id as string;
    const itemBId = itemBRes.body.data.id as string;

    // Initial order must be A -> B
    const initialGet = await request(app.getHttpServer())
      .get(`/trips/${tripId}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(
      initialGet.body.data.itineraries[0].items.map(
        (i: { placeId: string; orderIndex: number }) => i.placeId,
      ),
    ).toEqual([PLACE_A_THAP_DONG_HO, PLACE_B_BAO_TANG_QN]);

    // Reorder A -> B to B -> A
    const reorderRes = await request(app.getHttpServer())
      .put(`/trips/${tripId}/itinerary/reorder`)
      .set('Authorization', `Bearer ${token}`)
      .send({
        dayNumber: 1,
        items: [
          { itemId: itemBId, orderIndex: 1 },
          { itemId: itemAId, orderIndex: 2 },
        ],
      })
      .expect(200);

    expect(
      reorderRes.body.data.itineraries[0].items.map(
        (i: { placeId: string; orderIndex: number }) => ({
          placeId: i.placeId,
          orderIndex: i.orderIndex,
        }),
      ),
    ).toEqual([
      { placeId: PLACE_B_BAO_TANG_QN, orderIndex: 1 },
      { placeId: PLACE_A_THAP_DONG_HO, orderIndex: 2 },
    ]);

    // Verify fresh GET /trips/:id returns B -> A
    const reopenedGet = await request(app.getHttpServer())
      .get(`/trips/${tripId}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(
      reopenedGet.body.data.itineraries[0].items.map(
        (i: { placeId: string; orderIndex: number }) => ({
          placeId: i.placeId,
          orderIndex: i.orderIndex,
        }),
      ),
    ).toEqual([
      { placeId: PLACE_B_BAO_TANG_QN, orderIndex: 1 },
      { placeId: PLACE_A_THAP_DONG_HO, orderIndex: 2 },
    ]);

    // Verify PostgreSQL table rows directly
    const dbRows = await prisma.itineraryItem.findMany({
      where: { itinerary: { tripId } },
      orderBy: { orderIndex: 'asc' },
      select: { id: true, placeId: true, orderIndex: true },
    });
    expect(dbRows).toEqual([
      { id: itemBId, placeId: PLACE_B_BAO_TANG_QN, orderIndex: 1 },
      { id: itemAId, placeId: PLACE_A_THAP_DONG_HO, orderIndex: 2 },
    ]);
  });
});
