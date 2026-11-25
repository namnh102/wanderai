import {
  BadRequestException,
  ForbiddenException,
  NotFoundException,
  ValidationPipe,
} from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';
import { AddItineraryDto } from './dto/add-itinerary.dto';
import { CreateTripDto } from './dto/create-trip.dto';
import { UpdateTripDto } from './dto/update-trip.dto';
import { TripsService } from './trips.service';

describe('TripsService & Trip DTO Validation', () => {
  let tripsService: TripsService;
  let prismaMock: {
    trip: { findFirst: jest.Mock };
    itinerary: { upsert: jest.Mock };
    itineraryItem: { count: jest.Mock; create: jest.Mock };
  };
  let aiProxyMock: jest.Mocked<Pick<AiProxyService, 'planWithTripContext'>>;

  beforeEach(() => {
    prismaMock = {
      trip: { findFirst: jest.fn() },
      itinerary: { upsert: jest.fn() },
      itineraryItem: { count: jest.fn(), create: jest.fn() },
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

    it('returns created ItineraryItem with top-level dayNumber: 3, computed orderIndex, trimmed fields, and place inclusion', async () => {
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        userId: ownerId,
        members: [{ userId: ownerId, role: 'owner' }],
      });
      prismaMock.itinerary.upsert.mockResolvedValue({
        id: 'itin-day-3',
        tripId,
        dayNumber: 3,
      });
      prismaMock.itineraryItem.count.mockResolvedValue(1);
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
  });

  describe('DTO whitespace validation (ValidationPipe)', () => {
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
  });
});
