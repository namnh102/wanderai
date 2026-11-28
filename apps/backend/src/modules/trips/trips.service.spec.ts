import {
  BadRequestException,
  ExecutionContext,
  ForbiddenException,
  INestApplication,
  NotFoundException,
  ValidationPipe,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import * as request from 'supertest';
import { HttpExceptionFilter } from '../../common/filters/http-exception.filter';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { TransformInterceptor } from '../../common/interceptors/transform.interceptor';
import { PrismaService } from '../../prisma/prisma.service';
import { InMemoryPrismaService } from '../../../test/e2e-harness/in-memory-prisma.service';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';
import { AddItineraryDto } from './dto/add-itinerary.dto';
import { BulkItineraryDto } from './dto/bulk-itinerary.dto';
import { CreateTripDto } from './dto/create-trip.dto';
import { ReorderItineraryDto } from './dto/reorder-itinerary.dto';
import { UpdateTripDto } from './dto/update-trip.dto';
import { TripsController } from './trips.controller';
import { TripsService } from './trips.service';

describe('TripsService & Trip DTO Validation', () => {
  let tripsService: TripsService;
  let prismaMock: {
    trip: { findFirst: jest.Mock; update: jest.Mock };
    place: { findMany: jest.Mock };
    itinerary: { upsert: jest.Mock; deleteMany: jest.Mock };
    itineraryItem: {
      count: jest.Mock;
      findFirst: jest.Mock;
      findMany: jest.Mock;
      create: jest.Mock;
      update: jest.Mock;
      deleteMany: jest.Mock;
    };
    $transaction: jest.Mock;
  };
  let aiProxyMock: jest.Mocked<Pick<AiProxyService, 'planWithTripContext'>>;

  beforeEach(() => {
    prismaMock = {
      trip: { findFirst: jest.fn(), update: jest.fn() },
      place: { findMany: jest.fn() },
      itinerary: { upsert: jest.fn(), deleteMany: jest.fn() },
      itineraryItem: {
        count: jest.fn(),
        findFirst: jest.fn(),
        findMany: jest.fn(),
        create: jest.fn(),
        update: jest.fn(),
        deleteMany: jest.fn(),
      },
      $transaction: jest.fn(async (fn: (tx: unknown) => Promise<unknown>) =>
        fn(prismaMock),
      ),
    };
    aiProxyMock = {
      planWithTripContext: jest.fn(),
    };
    tripsService = new TripsService(
      prismaMock as unknown as PrismaService,
      aiProxyMock as unknown as AiProxyService,
    );
  });

  describe('addItineraryItem', () => {
    const tripId = '11111111-1111-4111-8111-111111111111';
    const ownerId = '22222222-2222-4222-8222-222222222222';
    const placeId = '65562a67-84ff-44a0-990d-31917a2a9bd0';

    it('returns created ItineraryItem with top-level dayNumber: 3, computed orderIndex from MAX+1, trimmed fields, and place inclusion', async () => {
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        userId: ownerId,
        members: [{ userId: ownerId, role: 'owner' }],
      });
      prismaMock.place.findMany.mockResolvedValue([{ id: placeId }]);
      prismaMock.itinerary.upsert.mockResolvedValue({
        id: 'itin-day-3',
        tripId,
        dayNumber: 3,
      });
      prismaMock.itineraryItem.findFirst.mockResolvedValue({ orderIndex: 1 });
      prismaMock.itineraryItem.create.mockResolvedValue({
        id: 'item-1',
        itineraryId: 'itin-day-3',
        placeId,
        orderIndex: 2,
        startTime: '09:00',
        endTime: '11:00',
        activity: 'Tham quan Tháp Đồng Hồ',
        notes: 'Mang máy ảnh',
        estimatedCost: null,
        transportMode: null,
        place: {
          id: placeId,
          name: 'Tháp Đồng Hồ',
          address: null,
        },
      });

      const result = await tripsService.addItineraryItem(tripId, ownerId, {
        dayNumber: 3,
        placeId,
        startTime: '09:00',
        endTime: '11:00',
        activity: '  Tham quan Tháp Đồng Hồ  ',
        notes: '  Mang máy ảnh  ',
      });

      expect(prismaMock.itinerary.upsert).toHaveBeenCalledWith({
        where: { tripId_dayNumber: { tripId, dayNumber: 3 } },
        create: { tripId, dayNumber: 3 },
        update: {},
      });
      expect(prismaMock.itineraryItem.create).toHaveBeenCalledWith({
        data: {
          itineraryId: 'itin-day-3',
          placeId,
          createdByUserId: '22222222-2222-4222-8222-222222222222',
          orderIndex: 2,
          startTime: '09:00',
          endTime: '11:00',
          activity: 'Tham quan Tháp Đồng Hồ',
          notes: 'Mang máy ảnh',
          estimatedCost: undefined,
          transportMode: undefined,
        },
        include: {
          place: { select: { id: true, name: true, address: true } },
        },
      });
      expect(result.dayNumber).toBe(3);
      expect(result.orderIndex).toBe(2);
      expect(result.activity).toBe('Tham quan Tháp Đồng Hồ');
      expect(result.notes).toBe('Mang máy ảnh');
      expect(result.place).toEqual({
        id: placeId,
        name: 'Tháp Đồng Hồ',
        address: null,
      });
    });

    it('throws NotFoundException when findById does not find the trip', async () => {
      prismaMock.trip.findFirst.mockResolvedValue(null);

      await expect(
        tripsService.addItineraryItem(tripId, ownerId, {
          dayNumber: 3,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId,
        }),
      ).rejects.toBeInstanceOf(NotFoundException);

      expect(prismaMock.itinerary.upsert).not.toHaveBeenCalled();
    });

    it('throws ForbiddenException when caller is neither trip owner nor member', async () => {
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        userId: 'other-owner',
        members: [{ userId: 'other-owner', role: 'owner' }],
      });

      await expect(
        tripsService.addItineraryItem(tripId, ownerId, {
          dayNumber: 3,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId,
        }),
      ).rejects.toBeInstanceOf(ForbiddenException);

      expect(prismaMock.itinerary.upsert).not.toHaveBeenCalled();
    });

    it('GAP-04: rejects nonexistent or unverified placeId with 404 PLACE_NOT_FOUND in addItineraryItem and bulkSaveItinerary', async () => {
      const missingPlaceId = '99999999-9999-4999-8999-999999999999';
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        userId: ownerId,
        members: [{ userId: ownerId, role: 'owner' }],
      });
      prismaMock.place.findMany.mockResolvedValue([]);

      let caughtAdd: unknown;
      try {
        await tripsService.addItineraryItem(tripId, ownerId, {
          dayNumber: 1,
          activity: 'Tham quan',
          placeId: missingPlaceId,
        });
      } catch (err) {
        caughtAdd = err;
      }
      expect(caughtAdd).toBeInstanceOf(NotFoundException);
      expect((caughtAdd as NotFoundException).getResponse()).toMatchObject({
        errorCode: 'PLACE_NOT_FOUND',
      });
      expect(prismaMock.itinerary.upsert).not.toHaveBeenCalled();

      let caughtBulk: unknown;
      try {
        await tripsService.bulkSaveItinerary(tripId, ownerId, {
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              items: [
                {
                  orderIndex: 1,
                  activity: 'Tham quan',
                  placeId: missingPlaceId,
                },
              ],
            },
          ],
        });
      } catch (err) {
        caughtBulk = err;
      }
      expect(caughtBulk).toBeInstanceOf(NotFoundException);
      expect((caughtBulk as NotFoundException).getResponse()).toMatchObject({
        errorCode: 'PLACE_NOT_FOUND',
      });
    });

    it('GAP-04: bulkSaveItinerary enforces ownership (403) and rejects duplicate dayNumber (400)', async () => {
      prismaMock.trip.findFirst.mockResolvedValueOnce({
        id: tripId,
        userId: 'other-owner',
      });

      await expect(
        tripsService.bulkSaveItinerary(tripId, ownerId, {
          days: [{ dayNumber: 1, items: [] }],
        }),
      ).rejects.toBeInstanceOf(ForbiddenException);

      prismaMock.trip.findFirst.mockResolvedValueOnce({
        id: tripId,
        userId: ownerId,
      });

      await expect(
        tripsService.bulkSaveItinerary(tripId, ownerId, {
          days: [
            { dayNumber: 1, items: [] },
            { dayNumber: 1, items: [] },
          ],
        }),
      ).rejects.toBeInstanceOf(BadRequestException);
    });
  });

  describe('DTO whitespace & adversarial validation (ValidationPipe)', () => {
    const validationPipe = new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    });

    it('rejects whitespace-only title in CreateTripDto with BadRequestException (400)', async () => {
      await expect(
        validationPipe.transform(
          { title: '   ' },
          { type: 'body', metatype: CreateTripDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);
    });

    it('trims valid CreateTripDto title during transform', async () => {
      const dto = (await validationPipe.transform(
        { title: '  Hành trình Hạ Long  ' },
        { type: 'body', metatype: CreateTripDto },
      )) as CreateTripDto;

      expect(dto.title).toBe('Hành trình Hạ Long');
    });

    it('rejects whitespace-only title in UpdateTripDto with BadRequestException (400) while allowing omitted title', async () => {
      await expect(
        validationPipe.transform(
          { title: ' \t\n ' },
          { type: 'body', metatype: UpdateTripDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      const emptyUpdate = (await validationPipe.transform(
        {},
        { type: 'body', metatype: UpdateTripDto },
      )) as UpdateTripDto;
      expect(emptyUpdate.title).toBeUndefined();
    });

    it('rejects whitespace-only activity in AddItineraryDto with BadRequestException (400) and trims valid activity', async () => {
      await expect(
        validationPipe.transform(
          { dayNumber: 1, activity: '   ' },
          { type: 'body', metatype: AddItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      const validDto = (await validationPipe.transform(
        { dayNumber: 3, activity: '  Tháp Đồng Hồ  ' },
        { type: 'body', metatype: AddItineraryDto },
      )) as AddItineraryDto;
      expect(validDto.activity).toBe('Tháp Đồng Hồ');
    });

    it('GAP-04: BulkItineraryDto rejects whitespace activity, non-UUID placeId, empty days, and >30 days', async () => {
      await expect(
        validationPipe.transform(
          {
            days: [
              {
                dayNumber: 1,
                items: [{ orderIndex: 1, activity: '   ' }],
              },
            ],
          },
          { type: 'body', metatype: BulkItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      await expect(
        validationPipe.transform(
          {
            days: [
              {
                dayNumber: 1,
                items: [
                  {
                    orderIndex: 1,
                    activity: 'Visit',
                    placeId: 'not-a-uuid',
                  },
                ],
              },
            ],
          },
          { type: 'body', metatype: BulkItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      await expect(
        validationPipe.transform(
          { days: [] },
          { type: 'body', metatype: BulkItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      const tooManyDays = Array.from({ length: 31 }, (_, idx) => ({
        dayNumber: idx + 1,
        items: [],
      }));
      await expect(
        validationPipe.transform(
          { days: tooManyDays },
          { type: 'body', metatype: BulkItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);
    });

    it('WP-TRIP-01: ReorderItineraryDto validates UUID itemId, integer bounds, and non-empty items array', async () => {
      await expect(
        validationPipe.transform(
          { items: [] },
          { type: 'body', metatype: ReorderItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      await expect(
        validationPipe.transform(
          { items: [{ itemId: 'not-a-uuid', orderIndex: 1 }] },
          { type: 'body', metatype: ReorderItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      await expect(
        validationPipe.transform(
          {
            items: [
              {
                itemId: '94f73104-7bb8-457b-a023-8927663b50c1',
                orderIndex: 0,
              },
            ],
          },
          { type: 'body', metatype: ReorderItineraryDto },
        ),
      ).rejects.toBeInstanceOf(BadRequestException);

      const validDto = (await validationPipe.transform(
        {
          dayNumber: 1,
          items: [
            {
              itemId: '94f73104-7bb8-457b-a023-8927663b50c1',
              orderIndex: 1,
            },
          ],
        },
        { type: 'body', metatype: ReorderItineraryDto },
      )) as ReorderItineraryDto;
      expect(validDto.dayNumber).toBe(1);
      expect(validDto.items).toHaveLength(1);
    });
  });

  describe('TripsController + InMemoryPrismaService Adversarial Behavior (GAP-04 & GAP-05)', () => {
    let app: INestApplication;
    let inMemoryPrisma: InMemoryPrismaService;
    const ownerId = '33333333-3333-4333-8333-333333333333';
    const verifiedPlaceId = '65562a67-84ff-44a0-990d-31917a2a9bd0';

    beforeAll(async () => {
      inMemoryPrisma = new InMemoryPrismaService();
      await inMemoryPrisma.onModuleInit();

      const moduleRef = await Test.createTestingModule({
        controllers: [TripsController],
        providers: [
          TripsService,
          { provide: PrismaService, useValue: inMemoryPrisma },
          { provide: AiProxyService, useValue: { planWithTripContext: jest.fn() } },
        ],
      })
        .overrideGuard(JwtAuthGuard)
        .useValue({
          canActivate: (ctx: ExecutionContext) => {
            const req = ctx.switchToHttp().getRequest();
            req.user = { id: ownerId, email: 'owner@wanderai.test' };
            return true;
          },
        })
        .compile();

      app = moduleRef.createNestApplication();
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
    });

    afterAll(async () => {
      if (app) await app.close();
    });

    it('GAP-04: rejects malformed UUID params on TripsController routes with 400', async () => {
      await request(app.getHttpServer()).get('/trips/not-a-uuid').expect(400);
      await request(app.getHttpServer())
        .post('/trips/not-a-uuid/itinerary')
        .send({ dayNumber: 1, activity: 'Test' })
        .expect(400);
      await request(app.getHttpServer())
        .delete(`/trips/${ownerId}/itinerary/not-a-uuid`)
        .expect(400);
    });

    it('GAP-05: computes orderIndex from MAX+1 after deletion (no collision) and deduplicates retry via clientRequestId', async () => {
      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({ title: 'Hạ Long Adversarial Trip' })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const item1 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Điểm 1',
          placeId: verifiedPlaceId,
          clientRequestId: 'req-item-1',
        })
        .expect(201);
      expect(item1.body.data.orderIndex).toBe(1);

      // Replay with same clientRequestId returns existing item without duplicating
      const replay1 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Điểm 1',
          placeId: verifiedPlaceId,
          clientRequestId: 'req-item-1',
        })
        .expect(201);
      expect(replay1.body.data.id).toBe(item1.body.data.id);

      const item2 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Điểm 2',
          placeId: verifiedPlaceId,
        })
        .expect(201);
      expect(item2.body.data.orderIndex).toBe(2);

      // Delete item 1, then add item 3 -> orderIndex must be 3 (never colliding with 2)
      await request(app.getHttpServer())
        .delete(`/trips/${tripId}/itinerary/${item1.body.data.id}`)
        .expect(200);

      const item3 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Điểm 3',
          placeId: verifiedPlaceId,
        })
        .expect(201);
      expect(item3.body.data.orderIndex).toBe(3);

      // bulkSaveItinerary with replaceExisting: false appends after MAX(orderIndex)
      const bulkAppend = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: false,
          days: [
            {
              dayNumber: 1,
              items: [
                {
                  orderIndex: 1,
                  activity: 'Điểm 4 (append)',
                  placeId: verifiedPlaceId,
                },
              ],
            },
          ],
        })
        .expect(201);
      const day1Items = bulkAppend.body.data.itineraries[0].items as Array<{
        orderIndex: number;
      }>;
      expect(day1Items.map((i) => i.orderIndex)).toEqual([2, 3, 4]);
    });

    it('rejects soft-deleted destinationId in create and update with 404 NotFoundException', async () => {
      const deletedDestId = 'd2222222-2222-4222-8222-222222222222';
      await inMemoryPrisma.destination.update({
        where: { id: deletedDestId },
        data: { deletedAt: new Date() },
      });

      await request(app.getHttpServer())
        .post('/trips')
        .send({ title: 'Trip with deleted dest', destinationId: deletedDestId })
        .expect(404);

      const createdTrip = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'Trip with valid dest',
          destinationId: 'd1111111-1111-4111-8111-111111111111',
        })
        .expect(201);

      await request(app.getHttpServer())
        .put(`/trips/${createdTrip.body.data.id}`)
        .send({ destinationId: deletedDestId })
        .expect(404);
    });

    it('addMember normalizes memberEmail (trim + lowercase) and rejects soft-deleted users with 404 NotFoundException', async () => {
      await inMemoryPrisma.user.create({
        data: {
          email: 'active-member@wanderai.test',
          passwordHash: null,
          isVerified: true,
        },
      });
      await inMemoryPrisma.user.create({
        data: {
          email: 'deleted-member@wanderai.test',
          passwordHash: null,
          isVerified: true,
          deletedAt: new Date(),
        },
      });

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({ title: 'Trip for members' })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const added = await request(app.getHttpServer())
        .post(`/trips/${tripId}/members`)
        .send({ email: '  Active-Member@WanderAI.Test  ' })
        .expect(201);
      expect(added.body.data.user.email).toBe('active-member@wanderai.test');

      await request(app.getHttpServer())
        .post(`/trips/${tripId}/members`)
        .send({ email: '  DELETED-Member@WanderAI.Test  ' })
        .expect(404);
    });

    it('WP-TRIP-01: PUT /trips/:id/itinerary/reorder swaps A -> B into B -> A atomically, persists across GET /trips/:id, and enforces day/index invariants', async () => {
      const placeA = '65562a67-84ff-44a0-990d-31917a2a9bd0';
      const placeB = '75562a67-84ff-44a0-990d-31917a2a9bd1';

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'WP-TRIP-01 Reorder Trip',
          destinationId: 'd1111111-1111-4111-8111-111111111111',
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const addA = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Tham quan Tháp Đồng Hồ (A)',
          placeId: placeA,
        })
        .expect(201);
      const addB = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary`)
        .send({
          dayNumber: 1,
          activity: 'Tham quan điểm B',
          placeId: placeB,
        })
        .expect(201);

      const itemAId = addA.body.data.id as string;
      const itemBId = addB.body.data.id as string;

      const beforeReload = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(
        beforeReload.body.data.itineraries[0].items.map(
          (i: { placeId: string; orderIndex: number }) => ({
            placeId: i.placeId,
            orderIndex: i.orderIndex,
          }),
        ),
      ).toEqual([
        { placeId: placeA, orderIndex: 1 },
        { placeId: placeB, orderIndex: 2 },
      ]);

      // Reject partial day submission (missing itemA)
      await request(app.getHttpServer())
        .put(`/trips/${tripId}/itinerary/reorder`)
        .send({
          dayNumber: 1,
          items: [{ itemId: itemBId, orderIndex: 1 }],
        })
        .expect(400);

      // Reject duplicate orderIndex [1, 1]
      await request(app.getHttpServer())
        .put(`/trips/${tripId}/itinerary/reorder`)
        .send({
          dayNumber: 1,
          items: [
            { itemId: itemBId, orderIndex: 1 },
            { itemId: itemAId, orderIndex: 1 },
          ],
        })
        .expect(400);

      // Reject duplicate itemId
      await request(app.getHttpServer())
        .put(`/trips/${tripId}/itinerary/reorder`)
        .send({
          dayNumber: 1,
          items: [
            { itemId: itemBId, orderIndex: 1 },
            { itemId: itemBId, orderIndex: 2 },
          ],
        })
        .expect(400);

      // Valid swap A -> B into B -> A
      const reorderRes = await request(app.getHttpServer())
        .put(`/trips/${tripId}/itinerary/reorder`)
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
          (i: { id: string; placeId: string; orderIndex: number }) => ({
            id: i.id,
            placeId: i.placeId,
            orderIndex: i.orderIndex,
          }),
        ),
      ).toEqual([
        { id: itemBId, placeId: placeB, orderIndex: 1 },
        { id: itemAId, placeId: placeA, orderIndex: 2 },
      ]);

      // Cold GET /trips/:id returns B -> A
      const afterReload = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(
        afterReload.body.data.itineraries[0].items.map(
          (i: { id: string; placeId: string; orderIndex: number }) => ({
            id: i.id,
            placeId: i.placeId,
            orderIndex: i.orderIndex,
          }),
        ),
      ).toEqual([
        { id: itemBId, placeId: placeB, orderIndex: 1 },
        { id: itemAId, placeId: placeA, orderIndex: 2 },
      ]);
    });

    it('C4 Supplement Cases B1, B2, C: surfaces closed-POI & overlap in Preview, rejects them at Apply while preserving old itinerary, and preserves unknown null prices without false surplus', async () => {
      const cafeId = '70c3326e-1b53-45bf-a210-6c43a076e95b';
      const choCaiDamId = '96523873-1b85-4d2f-b85c-cb3f5593091b';
      const baoTangId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
      const destId = 'd1111111-1111-4111-8111-111111111111';
      const now = new Date('2026-11-27T00:00:00.000Z');

      const rawStore = inMemoryPrisma as unknown as {
        places: Map<string, Record<string, unknown>>;
        placeSources: Array<Record<string, unknown>>;
      };

      for (const poi of [
        { id: cafeId, name: 'Cafe ban mê', openingHours: 'Mo-Su 06:30-23:30' },
        { id: choCaiDamId, name: 'Chợ Cái Dăm', openingHours: 'Mo-Sa 08:00-16:00' },
        { id: baoTangId, name: 'Bảo tàng Quảng Ninh', openingHours: null },
      ]) {
        rawStore.places.set(poi.id, {
          id: poi.id,
          destinationId: destId,
          categoryId: 'c1111111-1111-4111-8111-111111111111',
          name: poi.name,
          nameEn: null,
          description: null,
          address: 'Hạ Long, Quảng Ninh',
          latitude: 20.95,
          longitude: 107.08,
          priceMin: null,
          priceMax: null,
          openingHours: poi.openingHours,
          coverImage: null,
          images: [],
          rating: null,
          reviewCount: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        });
        rawStore.placeSources.push({
          id: `ps-c4-${poi.id}`,
          placeId: poi.id,
          sourceName: 'osm',
          sourceId: `node/${poi.id.slice(0, 6)}`,
          rawName: poi.name,
          confidenceScore: 1.0,
          rawData: { tags: { name: poi.name } },
          createdAt: now,
        });
      }

      const aiProxy = app.get(AiProxyService) as { planWithTripContext: jest.Mock };

      // 1) Seed trip with an existing valid itinerary ("lịch cũ") on Sunday 2026-11-22
      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'C4 Protected Trip',
          destinationId: destId,
          startDate: '2026-11-22',
          endDate: '2026-11-22',
          totalBudget: 500000,
          currency: 'VND',
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              date: '2026-11-22',
              title: 'Lịch cũ hợp lệ',
              items: [
                {
                  orderIndex: 1,
                  startTime: '08:00',
                  endTime: '09:30',
                  activity: 'Hoạt động lịch cũ cần bảo toàn',
                  placeId: cafeId,
                  estimatedCost: 50000,
                },
              ],
            },
          ],
        })
        .expect(201);

      // 2) Case B1: Closed POI on Sunday (Chợ Cái Dăm Mo-Sa 08:00-16:00)
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-22',
            title: 'Ngày 1 (Chủ nhật)',
            items: [
              {
                order_index: 1,
                start_time: '08:30',
                end_time: '10:00',
                activity: 'Cà phê sáng tại Cafe ban mê',
                place_name: 'Cafe ban mê',
                estimated_cost: 60000,
              },
              {
                order_index: 2,
                start_time: '10:30',
                end_time: '12:00',
                activity: 'Mua sắm tại Chợ Cái Dăm',
                place_name: 'Chợ Cái Dăm',
                estimated_cost: 100000,
              },
            ],
          },
        ],
      });

      const previewB1 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({})
        .expect(201);
      expect(previewB1.body.data.hasScheduleViolations).toBe(true);
      expect(previewB1.body.data.canApply).toBe(false);
      expect(previewB1.body.data.scheduleViolations).toHaveLength(1);
      expect(previewB1.body.data.scheduleViolations[0]).toMatchObject({
        code: 'OPENING_HOURS_CLOSED',
        reasonCode: 'CLOSED_ON_WEEKDAY',
        orderIndex: 2,
        placeId: choCaiDamId,
      });

      const applyB1 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              date: '2026-11-22',
              items: [
                {
                  orderIndex: 1,
                  startTime: '08:30',
                  endTime: '10:00',
                  activity: 'Cà phê sáng tại Cafe ban mê',
                  placeId: cafeId,
                  estimatedCost: 60000,
                },
                {
                  orderIndex: 2,
                  startTime: '10:30',
                  endTime: '12:00',
                  activity: 'Mua sắm tại Chợ Cái Dăm',
                  placeId: choCaiDamId,
                  estimatedCost: 100000,
                },
              ],
            },
          ],
        })
        .expect(400);
      expect(applyB1.body.errorCode).toBe('ITINERARY_SCHEDULE_VIOLATION');

      // Verify old itinerary remains 100% intact after B1 rejection!
      const afterB1Trip = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(afterB1Trip.body.data.itineraries).toHaveLength(1);
      expect(afterB1Trip.body.data.itineraries[0].items[0].activity).toBe(
        'Hoạt động lịch cũ cần bảo toàn',
      );

      // 3) Case B2: Overlapping schedule on Monday 2026-11-23 (09:00-11:00 vs 10:30-12:00)
      const applyB2 = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              date: '2026-11-23',
              items: [
                {
                  orderIndex: 1,
                  startTime: '09:00',
                  endTime: '11:00',
                  activity: 'Cà phê sáng tại Cafe ban mê',
                  placeId: cafeId,
                  estimatedCost: 60000,
                },
                {
                  orderIndex: 2,
                  startTime: '10:30',
                  endTime: '12:00',
                  activity: 'Mua sắm tại Chợ Cái Dăm',
                  placeId: choCaiDamId,
                  estimatedCost: 100000,
                },
              ],
            },
          ],
        })
        .expect(400);
      expect(applyB2.body.errorCode).toBe('ITINERARY_SCHEDULE_VIOLATION');

      // Old itinerary STILL intact after B2 rejection!
      const afterB2Trip = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(afterB2Trip.body.data.itineraries[0].items[0].activity).toBe(
        'Hoạt động lịch cũ cần bảo toàn',
      );

      // 4) Case C: Null/omitted price + missing openingHours (Bảo tàng Quảng Ninh)
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-23',
            title: 'Ngày 1: Hạ Long',
            items: [
              {
                order_index: 1,
                start_time: '08:30',
                end_time: '10:00',
                activity: 'Cà phê tại Cafe ban mê',
                place_name: 'Cafe ban mê',
                estimated_cost: null,
              },
              {
                order_index: 2,
                start_time: '10:30',
                end_time: '12:00',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_name: 'Bảo tàng Quảng Ninh',
                // estimated_cost omitted, openingHours null (UNKNOWN -> NOT closed!)
              },
            ],
          },
        ],
      });

      const previewC = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({})
        .expect(201);
      expect(previewC.body.data.hasScheduleViolations).toBe(false);
      expect(previewC.body.data.canApply).toBe(true);
      expect(previewC.body.data.budgetAnalysis).toMatchObject({
        totalBudget: 500000,
        knownCostTotal: 0,
        unknownCostItemCount: 2,
        costStatus: 'ALL_UNKNOWN',
        hasSufficientBudgetBasis: false,
        isOverBudget: false,
        variance: null,
      });
      expect(previewC.body.data.days[0].items[0].estimatedCost).toBeNull();
      expect(previewC.body.data.days[0].items[1].openingHoursStatus).toBe('UNKNOWN');

      // Applying Case C succeeds (201) and persists estimatedCost: null ("chưa biết")
      const applyC = await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              date: '2026-11-23',
              title: 'Ngày 1: Hạ Long',
              items: [
                {
                  orderIndex: 1,
                  startTime: '08:30',
                  endTime: '10:00',
                  activity: 'Cà phê tại Cafe ban mê',
                  placeId: cafeId,
                  estimatedCost: null,
                },
                {
                  orderIndex: 2,
                  startTime: '10:30',
                  endTime: '12:00',
                  activity: 'Tham quan Bảo tàng Quảng Ninh',
                  placeId: baoTangId,
                  estimatedCost: null,
                },
              ],
            },
          ],
        })
        .expect(201);
      expect(applyC.body.data.itineraries[0].items[0].estimatedCost).toBeNull();
      expect(applyC.body.data.itineraries[0].items[1].estimatedCost).toBeNull();
    });

    it('C4 Wandy-to-Preview & Double-Tap Apply: preserves party/time/budget/interests, formats "Đã biết 80.000đ; còn khoản chưa xác minh", and prevents duplicate items on double Apply', async () => {
      const baoTangId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
      const thapDongHoId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
      const destId = 'd1111111-1111-4111-8111-111111111111';
      const now = new Date('2026-11-27T00:00:00.000Z');

      const rawStore = inMemoryPrisma as unknown as {
        places: Map<string, Record<string, unknown>>;
        placeSources: Array<Record<string, unknown>>;
      };
      for (const poi of [
        { id: baoTangId, name: 'Bảo tàng Quảng Ninh', openingHours: 'Mo-Su 08:00-12:00,13:00-17:00' },
        { id: thapDongHoId, name: 'Tháp Đồng Hồ', openingHours: null },
      ]) {
        rawStore.places.set(poi.id, {
          id: poi.id,
          destinationId: destId,
          categoryId: 'c1111111-1111-4111-8111-111111111111',
          name: poi.name,
          nameEn: null,
          description: null,
          address: 'Hạ Long, Quảng Ninh',
          latitude: 20.95,
          longitude: 107.09,
          priceMin: null,
          priceMax: null,
          openingHours: poi.openingHours,
          coverImage: null,
          images: [],
          rating: null,
          reviewCount: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        });
        rawStore.placeSources.push({
          id: `ps-wandy-${poi.id}`,
          placeId: poi.id,
          sourceName: 'osm',
          sourceId: `node/${poi.id.slice(0, 6)}`,
          rawName: poi.name,
          confidenceScore: 1.0,
          rawData: { tags: { name: poi.name } },
          createdAt: now,
        });
      }

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'Chuyến Hạ Long từ Wandy',
          destinationId: destId,
          startDate: '2026-11-28',
          endDate: '2026-11-28',
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const aiProxy = app.get(AiProxyService) as { planWithTripContext: jest.Mock };
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        overview: 'Lịch trình bảo tàng Hạ Long 8h-12h.',
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Buổi sáng Hạ Long',
            items: [
              {
                order_index: 1,
                start_time: '08:00',
                end_time: '10:30',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_id: baoTangId,
                place_name: 'Bảo tàng Quảng Ninh',
                estimated_cost: 80000,
              },
              {
                order_index: 2,
                start_time: '10:30',
                end_time: '12:00',
                activity: 'Check-in Tháp Đồng Hồ',
                place_name: 'Tháp Đồng Hồ',
                estimated_cost: null,
              },
            ],
          },
        ],
      });

      const wandyPrompt =
        'Hai người lớn đi Hạ Long từ 8h đến 12h, tổng ngân sách 500.000 đồng, ưu tiên bảo tàng. Lập giúp tôi một lịch và ghi rõ khoản nào chưa biết giá.';
      const previewRes = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({ additionalPrompt: wandyPrompt })
        .expect(201);

      expect(previewRes.body.data.preservedContext).toEqual({
        partySize: 2,
        partyDescription: '2 người lớn',
        timeWindowStart: '08:00',
        timeWindowEnd: '12:00',
        totalBudget: 500000,
        interests: ['museum'],
      });
      expect(previewRes.body.data.budgetAnalysis).toMatchObject({
        totalBudget: 500000,
        knownCostTotal: 80000,
        unknownCostItemCount: 1,
        costStatus: 'PARTIAL_UNKNOWN',
        hasSufficientBudgetBasis: false,
        variance: null,
        summaryText: 'Đã xác minh 80.000đ · 1 khoản chưa biết giá',
      });
      expect(previewRes.body.data.days[0].items[0].costStatus).toBe('VERIFIED');
      expect(previewRes.body.data.days[0].items[1].costStatus).toBe('UNKNOWN');

      // Preview must NOT persist anything to DB
      const beforeApply = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(beforeApply.body.data.itineraries).toHaveLength(0);

      // Fire TWO simultaneous Apply requests with the same idempotency key (double-tap simulation)
      const bulkPayload = {
        replaceExisting: true,
        clientRequestId: 'wandy-apply-double-tap-001',
        days: [
          {
            dayNumber: 1,
            date: '2026-11-28',
            title: 'Buổi sáng Hạ Long',
            items: [
              {
                orderIndex: 1,
                startTime: '08:00',
                endTime: '10:30',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                placeId: baoTangId,
                notes: previewRes.body.data.days[0].items[0].notes,
                estimatedCost: 80000,
              },
              {
                orderIndex: 2,
                startTime: '10:30',
                endTime: '12:00',
                activity: 'Check-in Tháp Đồng Hồ',
                placeId: thapDongHoId,
                estimatedCost: null,
              },
            ],
          },
        ],
      };

      const [r1, r2] = await Promise.all([
        request(app.getHttpServer())
          .post(`/trips/${tripId}/itinerary/bulk`)
          .set('Idempotency-Key', 'wandy-apply-double-tap-001')
          .send(bulkPayload),
        request(app.getHttpServer())
          .post(`/trips/${tripId}/itinerary/bulk`)
          .set('Idempotency-Key', 'wandy-apply-double-tap-001')
          .send(bulkPayload),
      ]);
      expect(r1.status).toBe(201);
      expect(r2.status).toBe(201);

      const afterDoubleApply = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(afterDoubleApply.body.data.itineraries).toHaveLength(1);
      expect(afterDoubleApply.body.data.itineraries[0].items).toHaveLength(2);
      expect(afterDoubleApply.body.data.itineraries[0].items[0]).toMatchObject({
        estimatedCost: 80000,
        costStatus: 'VERIFIED',
        costSourceVerified: true,
      });
      expect(afterDoubleApply.body.data.itineraries[0].items[1]).toMatchObject({
        estimatedCost: null,
        costStatus: 'UNKNOWN',
      });
      expect(afterDoubleApply.body.data.costSummaryText).toBe(
        'Đã xác minh 80.000đ · 1 khoản chưa biết giá',
      );
    });

    it('Preview timing & 3-cost demo regression: propagates X-Request-Id across NestJS->FastAPI (503 retry mock) and formats "Đã xác minh 80.000đ · Tạm tính 120.000đ · 1 khoản chưa biết giá"', async () => {
      const baoTangId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
      const thapDongHoId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
      const destId = 'd1111111-1111-4111-8111-111111111111';
      const now = new Date('2026-11-27T00:00:00.000Z');

      const rawStore = inMemoryPrisma as unknown as {
        places: Map<string, Record<string, unknown>>;
        placeSources: Array<Record<string, unknown>>;
      };
      for (const poi of [
        { id: baoTangId, name: 'Bảo tàng Quảng Ninh', openingHours: 'Mo-Su 08:00-12:00,13:00-17:00' },
        { id: thapDongHoId, name: 'Tháp Đồng Hồ Hạ Long', openingHours: null },
      ]) {
        rawStore.places.set(poi.id, {
          id: poi.id,
          destinationId: destId,
          categoryId: 'c2222222-2222-4222-8222-222222222222',
          name: poi.name,
          nameEn: null,
          description: null,
          address: 'Hạ Long, Quảng Ninh',
          latitude: 20.95,
          longitude: 107.09,
          priceMin: null,
          priceMax: null,
          openingHours: poi.openingHours,
          coverImage: null,
          images: [],
          rating: null,
          reviewCount: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        });
        rawStore.placeSources.push({
          id: `ps-reg-${poi.id}`,
          placeId: poi.id,
          sourceName: 'osm',
          sourceId: `node/${poi.id.slice(0, 6)}`,
          rawName: poi.name,
          confidenceScore: 1.0,
          rawData: { tags: { name: poi.name } },
          createdAt: now,
        });
      }

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'Hạ Long 3 Khoản Chi Phí Demo',
          destinationId: destId,
          startDate: '2026-11-28',
          endDate: '2026-11-28',
          totalBudget: 500000,
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const reqId = 'req-halong-demo-503-retry-corr-01';
      const aiProxy = app.get(AiProxyService) as { planWithTripContext: jest.Mock };
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        overview: 'Hành trình nửa ngày Hạ Long 8h-12h.',
        timing_telemetry: {
          request_id: reqId,
          fastapi_total_ms: 44980.5,
          rag_retrieval_ms: 35.2,
          model_attempts: [
            {
              attempt: 1,
              started_offset_ms: 36.1,
              duration_ms: 32210.0,
              status: 'error_503',
              error_code: 'PROVIDER_503_UNAVAILABLE',
            },
            {
              attempt: 2,
              started_offset_ms: 34248.4,
              duration_ms: 10730.4,
              status: 'ok',
              error_code: null,
            },
          ],
          model_total_ms: 42940.4,
          retry_count: 1,
          retry_wait_ms: 2002.3,
          post_ai_schedule_validation_ms: 1.7,
        },
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Khám phá Văn hóa & Lịch sử Hạ Long',
            items: [
              {
                order_index: 1,
                start_time: '08:00',
                end_time: '10:30',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_id: baoTangId,
                place_name: 'Bảo tàng Quảng Ninh',
                estimated_cost: 80000,
              },
              {
                order_index: 2,
                start_time: '10:30',
                end_time: '11:15',
                activity: 'Check-in và tham quan Tháp Đồng Hồ Hạ Long',
                place_name: 'Tháp Đồng Hồ Hạ Long',
                estimated_cost: null,
              },
              {
                order_index: 3,
                start_time: '11:15',
                end_time: '12:00',
                activity: 'Thưởng thức bún bề bề/bún hải sản Hòn Gai',
                place_name: 'Khu vực ẩm thực Hòn Gai',
                estimated_cost: 120000,
              },
            ],
          },
        ],
      });

      const res = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .set('X-Request-Id', reqId)
        .send({
          additionalPrompt:
            'Hai người lớn đi Hạ Long từ 8h đến 12h, tổng ngân sách 500.000 đồng, ưu tiên bảo tàng. Lập giúp tôi một lịch và ghi rõ khoản nào chưa biết giá.',
          partySize: 2,
          partyDescription: '2 người lớn',
          timeWindowStart: '08:00',
          timeWindowEnd: '12:00',
          budgetOverride: 500000,
          interestsOverride: ['museum'],
        })
        .expect(201);

      expect(aiProxy.planWithTripContext).toHaveBeenCalledWith(
        expect.objectContaining({ requestId: reqId }),
      );
      expect(res.body.data.requestId).toBe(reqId);
      expect(res.body.data.timingTelemetry).toMatchObject({
        requestId: reqId,
        fastapiTotalMs: 44980.5,
        fastapiRagRetrievalMs: 35.2,
        retryCount: 1,
        retryWaitMs: 2002.3,
        modelTotalMs: 42940.4,
        fastapiPostAiScheduleValidationMs: 1.7,
      });
      expect(res.body.data.timingTelemetry.modelAttempts).toHaveLength(2);
      expect(res.body.data.timingTelemetry.nestjsAiCallTotalMs).toBeGreaterThanOrEqual(0);
      expect(
        res.body.data.timingTelemetry.nestjsPostAiScheduleValidationMs,
      ).toBeGreaterThanOrEqual(0);

      expect(res.body.data.days[0].items[0].costStatus).toBe('VERIFIED');
      expect(res.body.data.days[0].items[1].costStatus).toBe('UNKNOWN');
      expect(res.body.data.days[0].items[2].costStatus).toBe('ESTIMATED');

      expect(res.body.data.budgetAnalysis).toMatchObject({
        totalBudget: 500000,
        knownCostTotal: 200000,
        unknownCostItemCount: 1,
        costStatus: 'PARTIAL_UNKNOWN',
        variance: null,
        summaryText: 'Đã xác minh 80.000đ · Tạm tính 120.000đ · 1 khoản chưa biết giá',
        costProvenanceBreakdown: {
          verifiedPlaceCostTotal: 80000,
          verifiedPlaceCostItemCount: 1,
          verifiedFreeItemCount: 0,
          unverifiedAiEstimatedCostTotal: 120000,
          unverifiedAiEstimatedItemCount: 1,
          unknownCostItemCount: 1,
        },
      });
    });

    it('C4 Strict Cost Provenance: placeId-only never verifies price, enforces exact price+audience, verifies sourced free tickets (0đ), and classifies legacy places/itineraries lacking price provenance as ESTIMATED', async () => {
      const baoTangId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
      const thapDongHoId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
      const cauRongId = '9974ff88-5418-5867-ae49-1b72e0f0861f';
      const legacySeedPoiId = 'aaaaaaaa-1111-4111-8111-aaaaaaaa1111';
      const unverifiedParkId = 'bbbbbbbb-2222-4222-8222-bbbbbbbb2222';
      const destId = 'd1111111-1111-4111-8111-111111111111';
      const now = new Date('2026-11-28T00:00:00.000Z');

      const rawStore = inMemoryPrisma as unknown as {
        places: Map<string, Record<string, unknown>>;
        placeSources: Array<Record<string, unknown>>;
      };

      for (const poi of [
        {
          id: baoTangId,
          name: 'Bảo tàng Quảng Ninh',
          priceMin: 10000,
          priceMax: 40000,
        },
        {
          id: thapDongHoId,
          name: 'Tháp Đồng Hồ Hạ Long',
          priceMin: null,
          priceMax: null,
        },
        {
          id: cauRongId,
          name: 'Cầu Rồng',
          priceMin: 0,
          priceMax: 0,
        },
        {
          id: legacySeedPoiId,
          name: 'Bảo tàng Cũ Thiếu Nguồn Giá',
          // Historical seed priceMin/priceMax in DB WITHOUT curated price provenance!
          priceMin: 20000,
          priceMax: 40000,
        },
        {
          id: unverifiedParkId,
          name: 'Công viên Lán Bè',
          priceMin: null,
          priceMax: null,
        },
      ]) {
        rawStore.places.set(poi.id, {
          id: poi.id,
          destinationId: destId,
          categoryId: 'c3333333-3333-4333-8333-333333333333',
          name: poi.name,
          nameEn: null,
          description: null,
          address: 'Việt Nam',
          latitude: 20.95,
          longitude: 107.09,
          priceMin: poi.priceMin,
          priceMax: poi.priceMax,
          openingHours: null,
          coverImage: null,
          images: [],
          rating: null,
          reviewCount: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        });
        rawStore.placeSources.push({
          id: `ps-prov-${poi.id}`,
          placeId: poi.id,
          sourceName: 'osm',
          sourceId: `node/${poi.id.slice(0, 6)}`,
          rawName: poi.name,
          confidenceScore: 1.0,
          rawData: { tags: { name: poi.name } },
          createdAt: now,
        });
      }

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'Kiểm định nguồn gốc chi phí C4',
          destinationId: destId,
          startDate: '2026-11-28',
          endDate: '2026-11-28',
          totalBudget: 500000,
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;
      const aiProxy = app.get(AiProxyService) as { planWithTripContext: jest.Mock };

      // 1) Matching placeId does NOT verify wrong amount, wrong audience, unverified POI, or legacy seed POI!
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Ngày 1',
            items: [
              {
                // Bảo tàng Quảng Ninh matched by placeId, but 40.000đ != 2 adults * 40.000đ (80.000đ) -> ESTIMATED!
                order_index: 1,
                start_time: '08:00',
                end_time: '09:30',
                activity: 'Bảo tàng sai mức giá cho 2 người lớn',
                place_id: baoTangId,
                estimated_cost: 40000,
              },
              {
                // Tháp Đồng Hồ matched by placeId, AI guessed 30.000đ, no verified price source -> ESTIMATED!
                order_index: 2,
                start_time: '09:30',
                end_time: '10:15',
                activity: 'Tháp Đồng Hồ giá tự đoán',
                place_id: thapDongHoId,
                estimated_cost: 30000,
              },
              {
                // Legacy POI with seed priceMin=20000, priceMax=40000 but NO price provenance -> ESTIMATED!
                order_index: 3,
                start_time: '10:15',
                end_time: '11:15',
                activity: 'Bảo tàng Cũ Thiếu Nguồn Giá',
                place_id: legacySeedPoiId,
                estimated_cost: 80000,
              },
              {
                // Sourced FREE ticket (Cầu Rồng, 0đ) -> VERIFIED!
                order_index: 4,
                start_time: '11:15',
                end_time: '11:45',
                activity: 'Tham quan Cầu Rồng miễn phí có nguồn',
                place_id: cauRongId,
                estimated_cost: 0,
              },
              {
                // Unverified 0đ at Công viên Lán Bè -> ESTIMATED (never VERIFIED free)!
                order_index: 5,
                start_time: '11:45',
                end_time: '12:00',
                activity: 'Dạo Công viên Lán Bè chưa có nguồn miễn phí',
                place_id: unverifiedParkId,
                estimated_cost: 0,
              },
            ],
          },
        ],
      });

      const resStrict = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({
          additionalPrompt: 'Hai người lớn đi tham quan từ 8h đến 12h.',
          partySize: 2,
          partyDescription: '2 người lớn',
        })
        .expect(201);

      const strictItems = resStrict.body.data.days[0].items;
      // placeId is still resolved (confirming the place!), while costStatus is ESTIMATED for 1, 2, 3, 5!
      expect(strictItems[0]).toMatchObject({
        placeId: baoTangId,
        estimatedCost: 40000,
        costStatus: 'ESTIMATED',
        costSourceVerified: false,
      });
      expect(strictItems[1]).toMatchObject({
        placeId: thapDongHoId,
        estimatedCost: 30000,
        costStatus: 'ESTIMATED',
        costSourceVerified: false,
      });
      expect(strictItems[2]).toMatchObject({
        placeId: legacySeedPoiId,
        estimatedCost: 80000,
        costStatus: 'ESTIMATED',
        costSourceVerified: false,
      });
      expect(strictItems[3]).toMatchObject({
        placeId: cauRongId,
        estimatedCost: 0,
        costStatus: 'VERIFIED',
        isVerifiedFree: true,
        costSourceVerified: true,
      });
      expect(strictItems[4]).toMatchObject({
        placeId: unverifiedParkId,
        estimatedCost: 0,
        costStatus: 'ESTIMATED',
        isVerifiedFree: false,
      });
      expect(resStrict.body.data.budgetAnalysis).toMatchObject({
        summaryText: 'Đã xác minh 0đ (miễn phí) · Tạm tính 150.000đ',
        costProvenanceBreakdown: {
          verifiedPlaceCostTotal: 0,
          verifiedPlaceCostItemCount: 1,
          verifiedFreeItemCount: 1,
          unverifiedAiEstimatedCostTotal: 150000,
          unverifiedAiEstimatedItemCount: 4,
          unknownCostItemCount: 0,
        },
      });

      // 2) Audience match check: 2 sinh viên * 20.000đ = 40.000đ IS verified, whereas unspecified audience ("2 người") is ESTIMATED!
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Sinh viên đi bảo tàng',
            items: [
              {
                order_index: 1,
                start_time: '08:00',
                end_time: '10:00',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_id: baoTangId,
                estimated_cost: 40000,
              },
            ],
          },
        ],
      });
      const resStudent = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({ additionalPrompt: 'Hai sinh viên đi Hạ Long từ 8h đến 10h.' })
        .expect(201);
      expect(resStudent.body.data.days[0].items[0].costStatus).toBe('VERIFIED');
      expect(resStudent.body.data.budgetAnalysis.summaryText).toBe(
        'Đã xác minh 40.000đ',
      );

      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Chưa rõ đối tượng',
            items: [
              {
                order_index: 1,
                start_time: '08:00',
                end_time: '10:00',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_id: baoTangId,
                estimated_cost: 80000,
              },
            ],
          },
        ],
      });
      const resNoAudience = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({ additionalPrompt: '2 người đi Hạ Long từ 8h đến 10h.' })
        .expect(201);
      expect(resNoAudience.body.data.days[0].items[0].costStatus).toBe('ESTIMATED');
      expect(resNoAudience.body.data.budgetAnalysis.summaryText).toBe(
        'Tạm tính 80.000đ',
      );

      // 3) Legacy saved itinerary_items lacking price+audience provenance in DB -> GET /trips/:id classifies as ESTIMATED!
      await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .send({
          replaceExisting: true,
          days: [
            {
              dayNumber: 1,
              date: '2026-11-28',
              title: 'Lịch trình cũ thiếu nguồn giá',
              items: [
                {
                  orderIndex: 1,
                  startTime: '08:00',
                  endTime: '10:00',
                  activity: 'Bảo tàng lưu từ lịch cũ không có nguồn giá',
                  placeId: baoTangId,
                  notes: 'Tham quan buổi sáng',
                  estimatedCost: 80000,
                },
                {
                  orderIndex: 2,
                  startTime: '10:15',
                  endTime: '11:30',
                  activity: 'Bảo tàng Cũ Thiếu Nguồn Giá',
                  placeId: legacySeedPoiId,
                  estimatedCost: 40000,
                },
                {
                  orderIndex: 3,
                  startTime: '11:30',
                  endTime: '12:00',
                  activity: 'Cầu Rồng miễn phí có nguồn',
                  placeId: cauRongId,
                  estimatedCost: 0,
                },
              ],
            },
          ],
        })
        .expect(201);

      const legacyReload = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      const reloadedItems = legacyReload.body.data.itineraries[0].items;
      expect(reloadedItems[0]).toMatchObject({
        placeId: baoTangId,
        estimatedCost: 80000,
        costStatus: 'ESTIMATED',
        costSourceVerified: false,
      });
      expect(reloadedItems[1]).toMatchObject({
        placeId: legacySeedPoiId,
        estimatedCost: 40000,
        costStatus: 'ESTIMATED',
        costSourceVerified: false,
      });
      expect(reloadedItems[2]).toMatchObject({
        placeId: cauRongId,
        estimatedCost: 0,
        costStatus: 'VERIFIED',
        isVerifiedFree: true,
      });
      expect(legacyReload.body.data.costSummaryText).toBe(
        'Đã xác minh 0đ (miễn phí) · Tạm tính 120.000đ',
      );
    });

    it('C4 Verified Over-Budget + Unknown Cost Case: reports exact minimum overrun, keeps Preview unwritten, and preserves C4 Apply rule (canApply=true when schedule valid, persists & reopens cleanly)', async () => {
      const baoTangId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
      const vinhHaLongId = 'ade2140c-7945-4044-b99a-b1a028edce9e';
      const thapDongHoId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
      const destId = 'd1111111-1111-4111-8111-111111111111';
      const now = new Date('2026-11-28T00:00:00.000Z');

      const rawStore = inMemoryPrisma as unknown as {
        places: Map<string, Record<string, unknown>>;
        placeSources: Array<Record<string, unknown>>;
      };

      for (const poi of [
        { id: baoTangId, name: 'Bảo tàng Quảng Ninh', openingHours: 'Mo-Su 08:00-12:00,13:00-17:00' },
        { id: vinhHaLongId, name: 'Vịnh Hạ Long', openingHours: null },
        { id: thapDongHoId, name: 'Tháp Đồng Hồ', openingHours: null },
      ]) {
        rawStore.places.set(poi.id, {
          id: poi.id,
          destinationId: destId,
          categoryId: 'c4444444-4444-4444-8444-444444444444',
          name: poi.name,
          nameEn: null,
          description: null,
          address: 'Hạ Long, Quảng Ninh',
          latitude: 20.95,
          longitude: 107.09,
          priceMin: null,
          priceMax: null,
          openingHours: poi.openingHours,
          coverImage: null,
          images: [],
          rating: null,
          reviewCount: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        });
        rawStore.placeSources.push({
          id: `ps-over-${poi.id}`,
          placeId: poi.id,
          sourceName: 'osm',
          sourceId: `node/${poi.id.slice(0, 6)}`,
          rawName: poi.name,
          confidenceScore: 1.0,
          rawData: { tags: { name: poi.name } },
          createdAt: now,
        });
      }

      const tripRes = await request(app.getHttpServer())
        .post('/trips')
        .send({
          title: 'Hạ Long Vượt Ngân Sách Đã Xác Minh',
          destinationId: destId,
          startDate: '2026-11-28',
          endDate: '2026-11-28',
          totalBudget: 500000,
        })
        .expect(201);
      const tripId = tripRes.body.data.id as string;

      const aiProxy = app.get(AiProxyService) as { planWithTripContext: jest.Mock };
      aiProxy.planWithTripContext.mockResolvedValueOnce({
        destination: 'Hạ Long',
        total_days: 1,
        days: [
          {
            day_number: 1,
            date: '2026-11-28',
            title: 'Ngày 1: Bảo tàng & Vịnh Hạ Long',
            items: [
              {
                order_index: 1,
                start_time: '08:00',
                end_time: '09:30',
                activity: 'Tham quan Bảo tàng Quảng Ninh',
                place_name: 'Bảo tàng Quảng Ninh',
                estimated_cost: 80000,
              },
              {
                order_index: 2,
                start_time: '09:45',
                end_time: '11:15',
                activity: 'Tham quan Vịnh Hạ Long Tuyến VHL1',
                place_name: 'Vịnh Hạ Long',
                estimated_cost: 500000,
              },
              {
                order_index: 3,
                start_time: '11:20',
                end_time: '12:00',
                activity: 'Check-in Tháp Đồng Hồ Hạ Long',
                place_name: 'Tháp Đồng Hồ Hạ Long',
                estimated_cost: null,
              },
            ],
          },
        ],
      });

      const previewRes = await request(app.getHttpServer())
        .post(`/trips/${tripId}/ai-plan`)
        .send({
          additionalPrompt:
            'Hai người lớn đi Hạ Long từ 8h đến 12h, tổng ngân sách 500.000 đồng.',
          partySize: 2,
          partyDescription: '2 người lớn',
          budgetOverride: 500000,
        })
        .expect(201);

      // Verified portion alone = 80.000 + 500.000 = 580.000đ (> 500.000đ budget -> minimum overrun = 80.000đ) + 1 unknown item
      expect(previewRes.body.data.hasScheduleViolations).toBe(false);
      expect(previewRes.body.data.canApply).toBe(true);
      expect(previewRes.body.data.days[0].items[0]).toMatchObject({
        placeId: baoTangId,
        estimatedCost: 80000,
        costStatus: 'VERIFIED',
      });
      expect(previewRes.body.data.days[0].items[1]).toMatchObject({
        placeId: vinhHaLongId,
        estimatedCost: 500000,
        costStatus: 'VERIFIED',
      });
      expect(previewRes.body.data.days[0].items[2]).toMatchObject({
        placeId: thapDongHoId,
        estimatedCost: null,
        costStatus: 'UNKNOWN',
      });
      expect(previewRes.body.data.budgetAnalysis).toMatchObject({
        totalBudget: 500000,
        knownCostTotal: 580000,
        unknownCostItemCount: 1,
        costStatus: 'PARTIAL_UNKNOWN',
        hasSufficientBudgetBasis: false,
        isOverBudget: true,
        variance: -80000,
        summaryText:
          'Đã xác minh 580.000đ · 1 khoản chưa biết giá (vượt ngân sách ít nhất 80.000đ)',
        costProvenanceBreakdown: {
          verifiedPlaceCostTotal: 580000,
          verifiedPlaceCostItemCount: 2,
          verifiedFreeItemCount: 0,
          unverifiedAiEstimatedCostTotal: 0,
          unverifiedAiEstimatedItemCount: 0,
          unknownCostItemCount: 1,
        },
      });

      // Preview still writes 0 items to DB
      const beforeApply = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(beforeApply.body.data.itineraries).toHaveLength(0);

      // C4 Apply rule: schedule is valid (canApply=true), so explicit user Apply succeeds (201) & persists over-budget summary on reopen
      await request(app.getHttpServer())
        .post(`/trips/${tripId}/itinerary/bulk`)
        .set('Idempotency-Key', 'overbudget-verified-apply-001')
        .send({
          replaceExisting: true,
          clientRequestId: 'overbudget-verified-apply-001',
          days: [
            {
              dayNumber: 1,
              date: '2026-11-28',
              title: 'Ngày 1: Bảo tàng & Vịnh Hạ Long',
              items: previewRes.body.data.days[0].items.map((it: any) => ({
                orderIndex: it.orderIndex,
                startTime: it.startTime,
                endTime: it.endTime,
                activity: it.activity,
                placeId: it.placeId,
                notes: it.notes,
                estimatedCost: it.estimatedCost,
              })),
            },
          ],
        })
        .expect(201);

      const reopened = await request(app.getHttpServer())
        .get(`/trips/${tripId}`)
        .expect(200);
      expect(reopened.body.data.itineraries[0].items).toHaveLength(3);
      expect(reopened.body.data.costSummaryText).toBe(
        'Đã xác minh 580.000đ · 1 khoản chưa biết giá (vượt ngân sách ít nhất 80.000đ)',
      );
    });
  });
});
