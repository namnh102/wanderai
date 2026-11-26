import {
  BadRequestException,
  ConflictException,
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
import { GroupsModule } from './groups.module';
import { GroupsService } from './groups.service';

describe('GroupsService & GroupsController (W09-A Unit + In-Memory Contract)', () => {
  describe('GroupsService unit rules & FOR UPDATE lock order', () => {
    const adminId = '11111111-1111-4111-8111-111111111111';
    const memberId = '22222222-2222-4222-8222-222222222222';
    const outsiderId = '33333333-3333-4333-8333-333333333333';
    const tripId = '44444444-4444-4444-8444-444444444444';
    const groupId = '55555555-5555-4555-8555-555555555555';

    let service: GroupsService;
    let prismaMock: {
      group: {
        create: jest.Mock;
        findMany: jest.Mock;
        findUnique: jest.Mock;
        findFirst: jest.Mock;
        update: jest.Mock;
      };
      groupMember: {
        create: jest.Mock;
        delete: jest.Mock;
      };
      trip: {
        findFirst: jest.Mock;
        findMany: jest.Mock;
      };
      user: {
        findUnique: jest.Mock;
      };
      userBlock: {
        findFirst: jest.Mock;
      };
      $queryRaw: jest.Mock;
      $transaction: jest.Mock;
    };

    const makeUser = (id: string, displayName: string) => ({
      id,
      deletedAt: null,
      profile: {
        displayName,
        avatar: null,
        bio: 'Thích khám phá Hạ Long',
        nationality: 'VN',
        languages: ['vi'],
        isDiscoverable: true,
      },
      preferences: {
        travelStyle: null,
        interests: ['nature'],
      },
    });

    beforeEach(() => {
      prismaMock = {
        group: {
          create: jest.fn(),
          findMany: jest.fn(),
          findUnique: jest.fn(),
          findFirst: jest.fn(),
          update: jest.fn(),
        },
        groupMember: {
          create: jest.fn(),
          delete: jest.fn(),
        },
        trip: {
          findFirst: jest.fn(),
          findMany: jest.fn(),
        },
        user: {
          findUnique: jest.fn(),
        },
        userBlock: {
          findFirst: jest.fn().mockResolvedValue(null),
        },
        $queryRaw: jest.fn().mockResolvedValue([]),
        $transaction: jest.fn(async (cb: (tx: unknown) => Promise<unknown>) =>
          cb(prismaMock),
        ),
      };
      service = new GroupsService(prismaMock as unknown as PrismaService);
    });

    it('creates a trip-linked group only for trip owner and enforces 1 Trip <-> 0..1 Group', async () => {
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        title: 'Hạ Long 2N1Đ',
        userId: outsiderId,
      });

      await expect(
        service.create(adminId, { name: 'Nhóm test', tripId }),
      ).rejects.toBeInstanceOf(ForbiddenException);
      expect(prismaMock.$queryRaw).toHaveBeenCalledTimes(1);

      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        title: 'Hạ Long 2N1Đ',
        userId: adminId,
      });
      prismaMock.group.findFirst.mockResolvedValue({ id: groupId });

      await expect(
        service.create(adminId, { name: 'Nhóm test', tripId }),
      ).rejects.toBeInstanceOf(ConflictException);
    });

    it('rejects empty PATCH payload and null name with BadRequestException', async () => {
      await expect(
        service.update(groupId, adminId, {}),
      ).rejects.toBeInstanceOf(BadRequestException);
      await expect(
        service.update(groupId, adminId, { name: null as unknown as string }),
      ).rejects.toBeInstanceOf(BadRequestException);
    });

    it('locks group and users in ascending UUID order on addMember and blocks two-way UserBlock with 403', async () => {
      const groupRow = {
        id: groupId,
        name: 'Nhóm Hạ Long',
        description: null,
        tripId: null,
        createdAt: new Date(),
        members: [
          {
            id: 'gm-1',
            groupId,
            userId: memberId,
            role: 'admin',
            user: makeUser(memberId, 'Admin M'),
          },
        ],
      };
      prismaMock.group.findUnique.mockResolvedValue(groupRow);
      prismaMock.user.findUnique.mockResolvedValue(makeUser(adminId, 'Target A'));
      prismaMock.userBlock.findFirst.mockResolvedValue({ id: 'blk-1' });

      await expect(
        service.addMember(groupId, memberId, { userId: adminId }),
      ).rejects.toBeInstanceOf(ForbiddenException);

      // Lock order: groupId first, then sorted userIds (adminId < memberId)
      expect(prismaMock.$queryRaw).toHaveBeenCalledTimes(3);
      const calls = prismaMock.$queryRaw.mock.calls.map((c) => c[1]);
      expect(calls).toEqual([groupId, adminId, memberId]);
    });

    it('prevents removing sole admin or linked trip owner with ConflictException', async () => {
      const tripBoundGroup = {
        id: groupId,
        name: 'Nhóm Trip',
        description: null,
        tripId,
        createdAt: new Date(),
        members: [
          {
            id: 'gm-1',
            groupId,
            userId: adminId,
            role: 'admin',
            user: makeUser(adminId, 'Trip Owner'),
          },
          {
            id: 'gm-2',
            groupId,
            userId: memberId,
            role: 'admin',
            user: makeUser(memberId, 'Co-Admin'),
          },
        ],
      };
      prismaMock.group.findUnique.mockResolvedValue(tripBoundGroup);
      prismaMock.trip.findFirst.mockResolvedValue({
        id: tripId,
        title: 'Hạ Long',
        userId: adminId,
      });

      // Even with a second admin present, the Trip owner cannot be removed.
      await expect(
        service.removeMember(groupId, memberId, adminId),
      ).rejects.toBeInstanceOf(ConflictException);

      // Standalone sole admin cannot be removed.
      const standaloneGroup = {
        id: groupId,
        name: 'Nhóm Độc Lập',
        description: null,
        tripId: null,
        createdAt: new Date(),
        members: [
          {
            id: 'gm-1',
            groupId,
            userId: adminId,
            role: 'admin',
            user: makeUser(adminId, 'Sole Admin'),
          },
        ],
      };
      prismaMock.group.findUnique.mockResolvedValue(standaloneGroup);

      await expect(
        service.removeMember(groupId, adminId, adminId),
      ).rejects.toBeInstanceOf(ConflictException);
    });

    it('throws NotFoundException when target user does not exist or is soft-deleted', async () => {
      prismaMock.group.findUnique.mockResolvedValue({
        id: groupId,
        name: 'Nhóm',
        description: null,
        tripId: null,
        createdAt: new Date(),
        members: [
          {
            id: 'gm-1',
            groupId,
            userId: adminId,
            role: 'admin',
            user: makeUser(adminId, 'Admin'),
          },
        ],
      });
      prismaMock.user.findUnique.mockResolvedValue({
        ...makeUser(outsiderId, 'Deleted'),
        deletedAt: new Date(),
      });

      await expect(
        service.addMember(groupId, adminId, { userId: outsiderId }),
      ).rejects.toBeInstanceOf(NotFoundException);
    });
  });

  describe('GroupsController HTTP pipeline with InMemoryPrismaService', () => {
    let app: INestApplication;
    let prisma: InMemoryPrismaService;
    let activeActorId = '';
    let adminId = '';
    let memberId = '';
    let outsiderId = '';
    let adminTripId = '';
    let groupId = '';

    beforeAll(async () => {
      prisma = new InMemoryPrismaService();
      const moduleRef = await Test.createTestingModule({
        imports: [GroupsModule],
      })
        .overrideProvider(PrismaService)
        .useValue(prisma)
        .overrideGuard(JwtAuthGuard)
        .useValue({
          canActivate: (ctx: ExecutionContext) => {
            const req = ctx.switchToHttp().getRequest<{ user?: { id: string } }>();
            req.user = { id: activeActorId };
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

      const adminUser = await prisma.user.create({
        data: {
          email: 'admin.pii.secret@wanderai.test',
          passwordHash: 'secret_hash_value',
          profile: { create: { displayName: 'Trưởng Nhóm An' } },
        },
      });
      const memberUser = await prisma.user.create({
        data: {
          email: 'member.pii.secret@wanderai.test',
          passwordHash: 'secret_hash_value',
          profile: { create: { displayName: 'Thành Viên Bình' } },
        },
      });
      const outsiderUser = await prisma.user.create({
        data: {
          email: 'outsider.pii.secret@wanderai.test',
          passwordHash: 'secret_hash_value',
          profile: { create: { displayName: 'Người Ngoài Châu' } },
        },
      });
      adminId = String(adminUser.id);
      memberId = String(memberUser.id);
      outsiderId = String(outsiderUser.id);

      const trip = await prisma.trip.create({
        data: {
          userId: adminId,
          title: 'Hành trình Hạ Long',
          members: { create: { userId: adminId, role: 'owner' } },
        },
      });
      adminTripId = trip.id;
    });

    afterAll(async () => {
      await app.close();
    });

    it('enforces full 3-actor RBAC, DTO whitelist rejection, and zero PII leakage', async () => {
      activeActorId = adminId;
      const createRes = await request(app.getHttpServer())
        .post('/groups')
        .send({
          name: '  Nhóm Hạ Long W09-A  ',
          description: 'Khám phá Vịnh Hạ Long',
          tripId: adminTripId,
        })
        .expect(201);

      expect(createRes.body.success).toBe(true);
      expect(createRes.body.data.name).toBe('Nhóm Hạ Long W09-A');
      expect(createRes.body.data.myRole).toBe('admin');
      expect(createRes.body.data.tripTitle).toBe('Hành trình Hạ Long');
      expect(createRes.body.data.tripOwnerId).toBe(adminId);
      groupId = createRes.body.data.id;

      // Reject unknown fields (e.g. role injection / email) with 400
      await request(app.getHttpServer())
        .post(`/groups/${groupId}/members`)
        .send({ userId: memberId, role: 'admin' })
        .expect(400);

      await request(app.getHttpServer())
        .post(`/groups/${groupId}/members`)
        .send({ email: 'member.pii.secret@wanderai.test' })
        .expect(400);

      // Invalid UUID param -> 400
      await request(app.getHttpServer())
        .get('/groups/not-a-uuid')
        .expect(400);

      // Add member as admin -> 201
      const addRes = await request(app.getHttpServer())
        .post(`/groups/${groupId}/members`)
        .send({ userId: memberId })
        .expect(201);
      expect(addRes.body.data.memberCount).toBe(2);

      // Duplicate add -> 409
      await request(app.getHttpServer())
        .post(`/groups/${groupId}/members`)
        .send({ userId: memberId })
        .expect(409);

      // Member reads group -> 200 with myRole === 'member' and zero PII
      activeActorId = memberId;
      const memberGet = await request(app.getHttpServer())
        .get(`/groups/${groupId}`)
        .expect(200);
      expect(memberGet.body.data.myRole).toBe('member');
      const serialized = JSON.stringify(memberGet.body);
      expect(serialized).not.toContain('admin.pii.secret@wanderai.test');
      expect(serialized).not.toContain('member.pii.secret@wanderai.test');
      expect(serialized).not.toContain('passwordHash');

      // Member denied privileged actions -> 403
      await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ name: 'Member Hacked' })
        .expect(403);
      await request(app.getHttpServer())
        .post(`/groups/${groupId}/members`)
        .send({ userId: outsiderId })
        .expect(403);
      await request(app.getHttpServer())
        .delete(`/groups/${groupId}/members/${adminId}`)
        .expect(403);

      // Outsider denied read & write -> 403
      activeActorId = outsiderId;
      await request(app.getHttpServer()).get(`/groups/${groupId}`).expect(403);
      await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ name: 'Outsider Hacked' })
        .expect(403);
      const outsiderList = await request(app.getHttpServer())
        .get('/groups')
        .expect(200);
      expect(outsiderList.body.data).toEqual([]);

      // Admin updates name & removes member -> 200
      activeActorId = adminId;
      // Explicit null name must return 400 and keep existing name untouched
      await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ name: null })
        .expect(400);

      // Clearing description with null or "" returns 200 and sets description: null
      const clearDescNullRes = await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ description: null })
        .expect(200);
      expect(clearDescNullRes.body.data.description).toBeNull();
      expect(clearDescNullRes.body.data.name).toBe('Nhóm Hạ Long W09-A');

      const clearDescEmptyRes = await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ description: '' })
        .expect(200);
      expect(clearDescEmptyRes.body.data.description).toBeNull();

      const patchRes = await request(app.getHttpServer())
        .patch(`/groups/${groupId}`)
        .send({ name: 'Nhóm Hạ Long Đã Cập Nhật' })
        .expect(200);
      expect(patchRes.body.data.name).toBe('Nhóm Hạ Long Đã Cập Nhật');

      await request(app.getHttpServer())
        .delete(`/groups/${groupId}/members/${memberId}`)
        .expect(200);

      // Removed member now gets 403
      activeActorId = memberId;
      await request(app.getHttpServer()).get(`/groups/${groupId}`).expect(403);
    });
  });
});
