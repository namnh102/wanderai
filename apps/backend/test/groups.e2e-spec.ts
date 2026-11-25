import { INestApplication, ValidationPipe } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { Test, TestingModule } from '@nestjs/testing';
import * as bcrypt from 'bcryptjs';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { PrismaService } from '../src/prisma/prisma.service';

describe('GroupsController (Real PostgreSQL E2E — W09-A)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let jwtService: JwtService;

  let adminUserId: string;
  let memberUserId: string;
  let outsiderUserId: string;
  let blockedUserId: string;
  let adminToken: string;
  let memberToken: string;
  let outsiderToken: string;
  let adminTripId: string;
  let sharedGroupId: string;

  const stamp = Date.now();
  const adminEmail = `w09a_admin_${stamp}@wanderai.test`;
  const memberEmail = `w09a_member_${stamp}@wanderai.test`;
  const outsiderEmail = `w09a_outsider_${stamp}@wanderai.test`;
  const blockedEmail = `w09a_blocked_${stamp}@wanderai.test`;

  const adminPhone = '+84901111111';
  const memberPhone = '+84902222222';
  const adminEmergencyPhone = '+84909999999';
  const memberEmergencyPhone = '+84908888888';

  beforeAll(async () => {
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
    jwtService = app.get(JwtService);

    const passwordHash = await bcrypt.hash('TestPass123!', 10);

    const adminUser = await prisma.user.create({
      data: {
        email: adminEmail,
        passwordHash,
        isVerified: true,
        profile: {
          create: {
            displayName: 'Trưởng Nhóm Hạ Long',
            phone: adminPhone,
            bio: 'Thích biển đảo',
            nationality: 'VN',
            languages: ['vi', 'en'],
          },
        },
        safetyContacts: {
          create: {
            name: 'Người thân Admin',
            phone: adminEmergencyPhone,
            relation: 'family',
          },
        },
      },
    });
    adminUserId = adminUser.id;
    adminToken = jwtService.sign({
      sub: adminUser.id,
      email: adminUser.email,
      tokenVersion: adminUser.tokenVersion,
    });

    const memberUser = await prisma.user.create({
      data: {
        email: memberEmail,
        passwordHash,
        isVerified: true,
        profile: {
          create: {
            displayName: 'Thành Viên Minh',
            phone: memberPhone,
            bio: 'Nhiếp ảnh du lịch',
            nationality: 'VN',
            languages: ['vi'],
          },
        },
        safetyContacts: {
          create: {
            name: 'Người thân Member',
            phone: memberEmergencyPhone,
            relation: 'friend',
          },
        },
      },
    });
    memberUserId = memberUser.id;
    memberToken = jwtService.sign({
      sub: memberUser.id,
      email: memberUser.email,
      tokenVersion: memberUser.tokenVersion,
    });

    const outsiderUser = await prisma.user.create({
      data: {
        email: outsiderEmail,
        passwordHash,
        isVerified: true,
        profile: {
          create: {
            displayName: 'Người Ngoài Nhóm',
            phone: '+84903333333',
          },
        },
      },
    });
    outsiderUserId = outsiderUser.id;
    outsiderToken = jwtService.sign({
      sub: outsiderUser.id,
      email: outsiderUser.email,
      tokenVersion: outsiderUser.tokenVersion,
    });

    const blockedUser = await prisma.user.create({
      data: {
        email: blockedEmail,
        passwordHash,
        isVerified: true,
        profile: {
          create: {
            displayName: 'Người Dùng Bị Chặn',
          },
        },
      },
    });
    blockedUserId = blockedUser.id;

    await prisma.userBlock.create({
      data: {
        blockerId: adminUserId,
        blockedId: blockedUserId,
      },
    });

    const trip = await prisma.trip.create({
      data: {
        userId: adminUserId,
        title: 'Chuyến đi Hạ Long W09-A',
        members: {
          create: {
            userId: adminUserId,
            role: 'owner',
          },
        },
      },
    });
    adminTripId = trip.id;
  });

  afterAll(async () => {
    const userIds = [adminUserId, memberUserId, outsiderUserId, blockedUserId].filter(
      Boolean,
    );
    if (sharedGroupId) {
      await prisma.groupMember.deleteMany({
        where: { groupId: sharedGroupId },
      });
      await prisma.group.deleteMany({
        where: { id: sharedGroupId },
      });
    }
    if (userIds.length > 0) {
      await prisma.userBlock.deleteMany({
        where: {
          OR: [
            { blockerId: { in: userIds } },
            { blockedId: { in: userIds } },
          ],
        },
      });
      await prisma.tripMember.deleteMany({
        where: { userId: { in: userIds } },
      });
      await prisma.trip.deleteMany({
        where: { userId: { in: userIds } },
      });
      await prisma.safetyContact.deleteMany({
        where: { userId: { in: userIds } },
      });
      await prisma.profile.deleteMany({
        where: { userId: { in: userIds } },
      });
      await prisma.user.deleteMany({
        where: { id: { in: userIds } },
      });
    }
    await app.close();
  });

  it('1. requires authentication (401) on unauthenticated calls', async () => {
    await request(app.getHttpServer()).get('/groups').expect(401);
    await request(app.getHttpServer())
      .post('/groups')
      .send({ name: 'Nhóm không token' })
      .expect(401);
  });

  it('2. creates a group as admin (201), persists in PostgreSQL, and enforces 1 Trip <-> 0..1 Group (409)', async () => {
    // Non-owner cannot create group for someone else's trip
    await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${outsiderToken}`)
      .send({ name: 'Nhóm lậu', tripId: adminTripId })
      .expect(403);

    const res = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${adminToken}`)
      .send({
        name: 'Nhóm Khám Phá Hạ Long',
        description: 'Nhóm thử nghiệm W09-A',
        tripId: adminTripId,
      })
      .expect(201);

    expect(res.body.success).toBe(true);
    sharedGroupId = res.body.data.id;
    expect(res.body.data.myRole).toBe('admin');
    expect(res.body.data.memberCount).toBe(1);
    expect(res.body.data.tripId).toBe(adminTripId);
    expect(res.body.data.tripTitle).toBe('Chuyến đi Hạ Long W09-A');
    expect(res.body.data.tripOwnerId).toBe(adminUserId);

    // Verify directly in PostgreSQL
    const dbGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    expect(dbGroup.name).toBe('Nhóm Khám Phá Hạ Long');
    expect(dbGroup.tripId).toBe(adminTripId);

    const dbMembers = await prisma.groupMember.findMany({
      where: { groupId: sharedGroupId },
    });
    expect(dbMembers).toHaveLength(1);
    expect(dbMembers[0].userId).toBe(adminUserId);
    expect(dbMembers[0].role).toBe('admin');

    // Duplicate group for same tripId -> 409 Conflict
    await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${adminToken}`)
      .send({
        name: 'Nhóm trùng trip',
        tripId: adminTripId,
      })
      .expect(409);

    const groupsForTrip = await prisma.group.findMany({
      where: { tripId: adminTripId },
    });
    expect(groupsForTrip).toHaveLength(1);
  });

  it('3. admin adds memberUser by userId (201) and enforces DTO whitelist + two-way block + duplicate checks', async () => {
    // Reject role injection & email lookup with 400
    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ userId: memberUserId, role: 'admin' })
      .expect(400);

    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ email: memberEmail })
      .expect(400);

    // Reject blocked user with 403
    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ userId: blockedUserId })
      .expect(403);

    // Add memberUser
    const addRes = await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ userId: memberUserId })
      .expect(201);

    expect(addRes.body.data.memberCount).toBe(2);

    // Verify PostgreSQL member row
    const dbMember = await prisma.groupMember.findUniqueOrThrow({
      where: {
        groupId_userId: {
          groupId: sharedGroupId,
          userId: memberUserId,
        },
      },
    });
    expect(dbMember.role).toBe('member');

    // Duplicate add -> 409
    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ userId: memberUserId })
      .expect(409);
  });

  it('4. verifies 3-actor reads on the same group and proves zero PII leakage', async () => {
    // Actor 1: admin
    const adminRes = await request(app.getHttpServer())
      .get(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .expect(200);
    expect(adminRes.body.data.myRole).toBe('admin');
    expect(adminRes.body.data.members).toHaveLength(2);

    // Actor 2: member
    const memberRes = await request(app.getHttpServer())
      .get(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${memberToken}`)
      .expect(200);
    expect(memberRes.body.data.myRole).toBe('member');
    expect(memberRes.body.data.members).toHaveLength(2);

    const memberListRes = await request(app.getHttpServer())
      .get('/groups')
      .set('Authorization', `Bearer ${memberToken}`)
      .expect(200);
    expect(memberListRes.body.data.some((g: { id: string }) => g.id === sharedGroupId)).toBe(
      true,
    );

    // Actor 3: outsider -> 403 on detail, excluded from list
    await request(app.getHttpServer())
      .get(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${outsiderToken}`)
      .expect(403);

    const outsiderListRes = await request(app.getHttpServer())
      .get('/groups')
      .set('Authorization', `Bearer ${outsiderToken}`)
      .expect(200);
    expect(
      outsiderListRes.body.data.some((g: { id: string }) => g.id === sharedGroupId),
    ).toBe(false);

    // Strict PII non-leakage check across both detail and list responses
    const combinedPayload = JSON.stringify({
      adminDetail: adminRes.body,
      memberDetail: memberRes.body,
      memberList: memberListRes.body,
    });
    for (const forbidden of [
      adminEmail,
      memberEmail,
      outsiderEmail,
      adminPhone,
      memberPhone,
      adminEmergencyPhone,
      memberEmergencyPhone,
      'passwordHash',
      'safetyContacts',
      'safetyCheckins',
      'tokenVersion',
      'dateOfBirth',
    ]) {
      expect(combinedPayload).not.toContain(forbidden);
    }
  });

  it('5. denies member and outsider privileged mutations (403) and leaves PostgreSQL rows 100% unchanged', async () => {
    const beforeGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    const beforeMembers = await prisma.groupMember.findMany({
      where: { groupId: sharedGroupId },
      orderBy: { id: 'asc' },
    });

    // Under-privileged member rejections
    await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${memberToken}`)
      .send({ name: 'Hacked By Member' })
      .expect(403);

    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${memberToken}`)
      .send({ userId: outsiderUserId })
      .expect(403);

    await request(app.getHttpServer())
      .delete(`/groups/${sharedGroupId}/members/${adminUserId}`)
      .set('Authorization', `Bearer ${memberToken}`)
      .expect(403);

    // Outsider rejections
    await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${outsiderToken}`)
      .send({ name: 'Hacked By Outsider' })
      .expect(403);

    await request(app.getHttpServer())
      .post(`/groups/${sharedGroupId}/members`)
      .set('Authorization', `Bearer ${outsiderToken}`)
      .send({ userId: outsiderUserId })
      .expect(403);

    await request(app.getHttpServer())
      .delete(`/groups/${sharedGroupId}/members/${memberUserId}`)
      .set('Authorization', `Bearer ${outsiderToken}`)
      .expect(403);

    // Re-query PostgreSQL directly and assert 0 mutations
    const afterGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    const afterMembers = await prisma.groupMember.findMany({
      where: { groupId: sharedGroupId },
      orderBy: { id: 'asc' },
    });

    expect(afterGroup).toEqual(beforeGroup);
    expect(afterMembers).toEqual(beforeMembers);
  });

  it('6. enforces sole-admin / trip-owner protection (409) and allows admin update + member removal persisted in PostgreSQL', async () => {
    // Admin cannot remove self (sole admin + trip owner) -> 409
    await request(app.getHttpServer())
      .delete(`/groups/${sharedGroupId}/members/${adminUserId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .expect(409);

    // Reject PATCH { name: null } with 400 Bad Request and leave PostgreSQL groups.name unchanged
    const beforeNullNameGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ name: null })
      .expect(400);
    const afterNullNameGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    expect(afterNullNameGroup.name).toBe(beforeNullNameGroup.name);

    // Verify description: null and description: "" clear description (200 OK, description: null)
    const clearDescNullRes = await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ description: null })
      .expect(200);
    expect(clearDescNullRes.body.data.description).toBeNull();

    const clearDescEmptyRes = await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ description: '' })
      .expect(200);
    expect(clearDescEmptyRes.body.data.description).toBeNull();

    // Admin updates group -> 200 & persisted in PostgreSQL
    const patchRes = await request(app.getHttpServer())
      .patch(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({
        name: 'Nhóm Hạ Long (Đã cập nhật)',
        description: 'Chuyến đi cùng Tháp Đồng Hồ',
      })
      .expect(200);
    expect(patchRes.body.data.name).toBe('Nhóm Hạ Long (Đã cập nhật)');

    const updatedDbGroup = await prisma.group.findUniqueOrThrow({
      where: { id: sharedGroupId },
    });
    expect(updatedDbGroup.name).toBe('Nhóm Hạ Long (Đã cập nhật)');
    expect(updatedDbGroup.description).toBe('Chuyến đi cùng Tháp Đồng Hồ');

    // Admin removes memberUser -> 200 & deleted in PostgreSQL
    await request(app.getHttpServer())
      .delete(`/groups/${sharedGroupId}/members/${memberUserId}`)
      .set('Authorization', `Bearer ${adminToken}`)
      .expect(200);

    const remainingMembers = await prisma.groupMember.findMany({
      where: { groupId: sharedGroupId },
    });
    expect(remainingMembers).toHaveLength(1);
    expect(remainingMembers[0].userId).toBe(adminUserId);

    // Removed member now gets 403 on GET /groups/:id
    await request(app.getHttpServer())
      .get(`/groups/${sharedGroupId}`)
      .set('Authorization', `Bearer ${memberToken}`)
      .expect(403);

    // Non-existent group -> 404; invalid UUID -> 400
    await request(app.getHttpServer())
      .get('/groups/00000000-0000-4000-8000-000000000000')
      .set('Authorization', `Bearer ${adminToken}`)
      .expect(404);
    await request(app.getHttpServer())
      .get('/groups/invalid-uuid')
      .set('Authorization', `Bearer ${adminToken}`)
      .expect(400);
  });
});
