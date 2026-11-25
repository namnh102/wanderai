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
  });
});
