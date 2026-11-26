import 'reflect-metadata';
import {
  BadRequestException,
  ForbiddenException,
  NotFoundException,
  ValidationPipe,
} from '@nestjs/common';
import { GUARDS_METADATA } from '@nestjs/common/constants';
import { EmergencyStatus, Prisma } from '@prisma/client';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import {
  CreateEmergencyEventDto,
  CreateSafetyCheckinDto,
  CreateSafetyContactDto,
} from './dto/safety.dto';
import { SafetyController } from './safety.controller';
import { MAX_TRUSTED_CONTACTS_PER_USER, SafetyService } from './safety.service';

function makePrismaMock() {
  const prisma: any = {
    safetyContact: {
      findMany: jest.fn(),
      count: jest.fn(),
      create: jest.fn(),
      findUnique: jest.fn(),
      delete: jest.fn(),
    },
    safetyCheckin: {
      findMany: jest.fn(),
      create: jest.fn(),
    },
    emergencyEvent: {
      findMany: jest.fn(),
      create: jest.fn(),
    },
    $transaction: jest.fn(
      async (cb: (tx: any) => Promise<any>, _opts?: any) => cb(prisma),
    ),
  };
  return prisma;
}

describe('SafetyModule Security & Ownership (WP-SAFE-01)', () => {
  it('guards every route on SafetyController with JwtAuthGuard', () => {
    const guards = Reflect.getMetadata(GUARDS_METADATA, SafetyController);
    expect(guards).toBeDefined();
    expect(guards).toContain(JwtAuthGuard);
  });

  it('scopes listContacts, listCheckins, and listEmergencyEvents strictly to userId', async () => {
    const prisma = makePrismaMock();
    prisma.safetyContact.findMany.mockResolvedValue([]);
    prisma.safetyCheckin.findMany.mockResolvedValue([]);
    prisma.emergencyEvent.findMany.mockResolvedValue([
      {
        id: 'ev-1',
        userId: 'user-a',
        latitude: 20.95,
        longitude: 107.08,
        status: EmergencyStatus.FALSE_ALARM,
        message: '[SANDBOX] Kiểm thử SOS',
        resolvedAt: new Date(),
        createdAt: new Date(),
      },
    ]);

    const service = new SafetyService(prisma);
    await service.listContacts('user-a');
    await service.listCheckins('user-a');
    const events = await service.listEmergencyEvents('user-a');

    expect(prisma.safetyContact.findMany).toHaveBeenCalledWith({
      where: { userId: 'user-a' },
      orderBy: { createdAt: 'asc' },
    });
    expect(prisma.safetyCheckin.findMany).toHaveBeenCalledWith({
      where: { userId: 'user-a' },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });
    expect(prisma.emergencyEvent.findMany).toHaveBeenCalledWith({
      where: { userId: 'user-a' },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });
    expect(events[0].isSandbox).toBe(true);
  });

  it('enforces max 3 trusted contacts per user and throws 400 when exceeded', async () => {
    const prisma = makePrismaMock();
    prisma.safetyContact.count.mockResolvedValue(MAX_TRUSTED_CONTACTS_PER_USER);
    const service = new SafetyService(prisma);

    await expect(
      service.createContact('user-a', {
        name: 'Người thứ 4',
        phone: '0909999999',
        relation: 'family',
      }),
    ).rejects.toThrow(BadRequestException);
    expect(prisma.safetyContact.create).not.toHaveBeenCalled();

    prisma.safetyContact.count.mockResolvedValue(2);
    prisma.safetyContact.create.mockResolvedValue({
      id: 'c-3',
      userId: 'user-a',
      name: 'Người thứ 3',
      phone: '0903333333',
      relation: 'friend',
      createdAt: new Date(),
    });
    const created = await service.createContact('user-a', {
      name: 'Người thứ 3',
      phone: '0903333333',
      relation: 'friend',
    });
    expect(created.id).toBe('c-3');
    expect(prisma.$transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
    });
    expect(prisma.safetyContact.create).toHaveBeenCalledWith({
      data: {
        userId: 'user-a',
        name: 'Người thứ 3',
        phone: '0903333333',
        relation: 'friend',
      },
    });
  });

  it('rejects deleteContact with 404 when missing and 403 when owned by another user', async () => {
    const prisma = makePrismaMock();
    const service = new SafetyService(prisma);

    prisma.safetyContact.findUnique.mockResolvedValueOnce(null);
    await expect(
      service.deleteContact('user-a', '00000000-0000-4000-8000-000000000001'),
    ).rejects.toThrow(NotFoundException);

    prisma.safetyContact.findUnique.mockResolvedValueOnce({
      id: '00000000-0000-4000-8000-000000000002',
      userId: 'user-b',
      name: 'B Contact',
      phone: '0911111111',
      relation: 'family',
    });
    await expect(
      service.deleteContact('user-a', '00000000-0000-4000-8000-000000000002'),
    ).rejects.toThrow(ForbiddenException);
    expect(prisma.safetyContact.delete).not.toHaveBeenCalled();

    prisma.safetyContact.findUnique.mockResolvedValueOnce({
      id: '00000000-0000-4000-8000-000000000003',
      userId: 'user-a',
      name: 'A Contact',
      phone: '0922222222',
      relation: 'family',
    });
    prisma.safetyContact.delete.mockResolvedValueOnce({});
    const res = await service.deleteContact(
      'user-a',
      '00000000-0000-4000-8000-000000000003',
    );
    expect(res).toEqual({
      deleted: true,
      id: '00000000-0000-4000-8000-000000000003',
    });
  });

  it('stores sandbox emergency events safely without altering schema', async () => {
    const prisma = makePrismaMock();
    prisma.emergencyEvent.create.mockImplementation(async ({ data }: any) => ({
      id: 'ev-sandbox-1',
      ...data,
      createdAt: new Date(),
    }));
    const service = new SafetyService(prisma);

    const created = await service.createEmergencyEvent('user-a', {
      latitude: 20.9516,
      longitude: 107.0852,
      message: 'Kiểm thử gọi 113',
      isSandbox: true,
    });

    expect(created.isSandbox).toBe(true);
    expect(created.status).toBe(EmergencyStatus.FALSE_ALARM);
    expect(created.message).toBe('[SANDBOX] Kiểm thử gọi 113');
    expect(created.resolvedAt).toBeInstanceOf(Date);
  });

  it('validates DTOs strictly via ValidationPipe whitelist and bounds', async () => {
    const pipe = new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    });

    await expect(
      pipe.transform(
        { name: '   ', phone: '0901234567', relation: 'invalid_rel' },
        { type: 'body', metatype: CreateSafetyContactDto },
      ),
    ).rejects.toThrow(BadRequestException);

    await expect(
      pipe.transform(
        { latitude: 120, longitude: 107.0, note: 'ok' },
        { type: 'body', metatype: CreateSafetyCheckinDto },
      ),
    ).rejects.toThrow(BadRequestException);

    await expect(
      pipe.transform(
        { latitude: 20.95, longitude: 107.08, isSandbox: true, extraField: 'hack' },
        { type: 'body', metatype: CreateEmergencyEventDto },
      ),
    ).rejects.toThrow(BadRequestException);
  });
});
