import { INestApplication, ValidationPipe } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { Test, TestingModule } from '@nestjs/testing';
import * as bcrypt from 'bcryptjs';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { PrismaService } from '../src/prisma/prisma.service';

describe('Trip Invites & In-App Notifications Flow (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let jwtService: JwtService;

  let userAToken: string;
  let userBToken: string;
  let userAId: string;
  let userBId: string;
  const runId = Date.now();
  const userAEmail = `trip_inv_e2e_a_${runId}@wanderai.test`;
  const userBEmail = `trip_inv_e2e_b_${runId}@wanderai.test`;

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

    const hash = await bcrypt.hash('TestPass123!', 10);
    const uA = await prisma.user.create({
      data: {
        email: userAEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'Chủ chuyến A' } },
      },
    });
    userAId = uA.id;
    userAToken = jwtService.sign({ sub: uA.id, email: uA.email });

    const uB = await prisma.user.create({
      data: {
        email: userBEmail,
        passwordHash: hash,
        profile: { create: { displayName: 'Đồng hành B' } },
      },
    });
    userBId = uB.id;
    userBToken = jwtService.sign({ sub: uB.id, email: uB.email });
  });

  afterAll(async () => {
    await prisma.tripInvite.deleteMany({
      where: { OR: [{ inviterId: userAId }, { inviteeId: userBId }] },
    });
    await prisma.notification.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.tripMember.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.trip.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.profile.deleteMany({
      where: { userId: { in: [userAId, userBId] } },
    });
    await prisma.user.deleteMany({
      where: { id: { in: [userAId, userBId] } },
    });
    await app.close();
  });

  it('completes A invites B -> idempotent duplicate -> unread persists -> B accepts -> enters trip, and handles revoked invites', async () => {
    // 1. A creates Trip 1
    const trip1Res = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${userAToken}`)
      .send({ title: 'Chuyến Hạ Long Mời B' })
      .expect(201);
    const trip1Id = trip1Res.body.data.id as string;

    // Before invite: B cannot view Trip 1 (403)
    await request(app.getHttpServer())
      .get(`/trips/${trip1Id}`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(403);

    // 2. A invites B twice (duplicate test) -> only 1 invite & 1 notification
    const inv1Res = await request(app.getHttpServer())
      .post(`/trips/${trip1Id}/invites`)
      .set('Authorization', `Bearer ${userAToken}`)
      .send({ email: userBEmail })
      .expect(201);
    const invite1Id = inv1Res.body.data.id as string;
    expect(inv1Res.body.data.idempotentDuplicate).toBe(false);

    const inv1DupRes = await request(app.getHttpServer())
      .post(`/trips/${trip1Id}/invites`)
      .set('Authorization', `Bearer ${userAToken}`)
      .send({ email: `  ${userBEmail.toUpperCase()}  ` })
      .expect(201);
    expect(inv1DupRes.body.data.id).toBe(invite1Id);
    expect(inv1DupRes.body.data.idempotentDuplicate).toBe(true);

    // 3. B fetches notifications -> exact 1 notification, unreadCount = 1
    const notifRes = await request(app.getHttpServer())
      .get('/notifications')
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(notifRes.body.data.unreadCount).toBe(1);
    expect(notifRes.body.data.items).toHaveLength(1);
    expect(notifRes.body.data.items[0].type).toBe('TRIP_INVITE');
    expect(notifRes.body.data.items[0].tripInvite.inviteId).toBe(invite1Id);
    expect(notifRes.body.data.items[0].tripInvite.status).toBe('PENDING');

    // Re-query unread-count (simulating cold reopen before reading) -> still 1
    const unreadCheck = await request(app.getHttpServer())
      .get('/notifications/unread-count')
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(unreadCheck.body.data.unreadCount).toBe(1);

    // 4. B opens invite detail & accepts -> joins Trip 1 & unreadCount becomes 0
    const detailRes = await request(app.getHttpServer())
      .get(`/trips/invites/${invite1Id}`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(detailRes.body.data.tripId).toBe(trip1Id);
    expect(detailRes.body.data.status).toBe('PENDING');

    const acceptRes = await request(app.getHttpServer())
      .post(`/trips/invites/${invite1Id}/accept`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(acceptRes.body.data.tripId).toBe(trip1Id);
    expect(acceptRes.body.data.invite.status).toBe('ACCEPTED');

    // B can now open Trip 1 directly (200)
    const bTripRes = await request(app.getHttpServer())
      .get(`/trips/${trip1Id}`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(bTripRes.body.data.id).toBe(trip1Id);
    expect(bTripRes.body.data.title).toBe('Chuyến Hạ Long Mời B');

    const unreadAfterAccept = await request(app.getHttpServer())
      .get('/notifications/unread-count')
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    expect(unreadAfterAccept.body.data.unreadCount).toBe(0);

    // 5. Revoked invite case on Trip 2
    const trip2Res = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${userAToken}`)
      .send({ title: 'Chuyến Đà Nẵng Thu Hồi' })
      .expect(201);
    const trip2Id = trip2Res.body.data.id as string;

    const inv2Res = await request(app.getHttpServer())
      .post(`/trips/${trip2Id}/invites`)
      .set('Authorization', `Bearer ${userAToken}`)
      .send({ email: userBEmail })
      .expect(201);
    const invite2Id = inv2Res.body.data.id as string;

    await request(app.getHttpServer())
      .post(`/trips/${trip2Id}/invites/${invite2Id}/revoke`)
      .set('Authorization', `Bearer ${userAToken}`)
      .expect(200);

    const notifAfterRevoke = await request(app.getHttpServer())
      .get('/notifications')
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(200);
    const revokedNotif = notifAfterRevoke.body.data.items.find(
      (n: { tripInvite?: { inviteId?: string } }) =>
        n.tripInvite?.inviteId === invite2Id,
    );
    expect(revokedNotif).toBeDefined();
    expect(revokedNotif.tripInvite.status).toBe('REVOKED');

    await request(app.getHttpServer())
      .post(`/trips/invites/${invite2Id}/accept`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(409);

    await request(app.getHttpServer())
      .get(`/trips/${trip2Id}`)
      .set('Authorization', `Bearer ${userBToken}`)
      .expect(403);
  });
});
