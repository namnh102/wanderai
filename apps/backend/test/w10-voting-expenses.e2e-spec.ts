process.env.JWT_SECRET ??= 'w10-e2e-jwt-secret-at-least-32-characters-long!!';
process.env.JWT_REFRESH_SECRET ??=
  'w10-e2e-jwt-refresh-secret-at-least-32-chars!!';

import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { PrismaService } from '../src/prisma/prisma.service';

describe('W10 Itinerary Voting & Shared Expenses (Real PostgreSQL E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const registerUser = async (name: string, tag: string) => {
    const email = `w10_${tag}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}@gomate.vn`;
    const res = await request(app.getHttpServer())
      .post('/auth/register')
      .send({ name, email, password: 'W10Password#2026' })
      .expect(201);
    const data = res.body.data ?? res.body;
    const token: string = data.access_token ?? data.accessToken;
    const me = await request(app.getHttpServer())
      .get('/users/me')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    const userId: string = (me.body.data ?? me.body).id;
    return { userId, email, token };
  };

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

    prisma = moduleFixture.get(PrismaService);
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  it('TC-VOT-01..07 & TC-SEC-01: enforces unlinked guidance, dual-gate RBAC (no auto-sync), 1-vote idempotent switch/withdraw, self-authored delete, trip-owner-only reorder, and ghost-vote cleanup', async () => {
    const u1 = await registerUser('Chủ Chuyến U1', 'u1');
    const u2 = await registerUser('Thành Viên Đủ Quyền U2', 'u2');
    const u3 = await registerUser('Chỉ GroupMember U3', 'u3');

    // 1. Unlinked group (TC-VOT-01)
    const unlinkedRes = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ name: 'Nhóm Chưa Gắn Trip W10' })
      .expect(201);
    const unlinkedGroupId: string = unlinkedRes.body.data.id;

    const getUnlinked = await request(app.getHttpServer())
      .get(`/groups/${unlinkedGroupId}/itinerary`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(200);
    expect(getUnlinked.body.data).toMatchObject({
      groupId: unlinkedGroupId,
      tripLinked: false,
      canAttachTrip: true,
      days: [],
    });

    const writeUnlinked = await request(app.getHttpServer())
      .post(`/groups/${unlinkedGroupId}/itinerary/items`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ dayNumber: 1, activity: 'Thử khi chưa có chuyến' })
      .expect(409);
    expect(writeUnlinked.body.errorCode).toBe('GROUP_TRIP_NOT_LINKED');

    // 2. Create Trip as U1, grant TripMember ONLY to U2 via existing POST /trips/:id/members
    const tripRes = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ title: 'Chuyến Hạ Long W10 E2E' })
      .expect(201);
    const tripId: string = tripRes.body.data.id;

    await request(app.getHttpServer())
      .post(`/trips/${tripId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ email: u2.email })
      .expect(201);

    const groupRes = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ name: 'Nhóm Hạ Long 3 Vai Trò', tripId })
      .expect(201);
    const groupId: string = groupRes.body.data.id;

    await request(app.getHttpServer())
      .post(`/groups/${groupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u2.userId })
      .expect(201);
    await request(app.getHttpServer())
      .post(`/groups/${groupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u3.userId })
      .expect(201);

    // Verify U3 was NOT auto-synced into trip_members
    const u3TripMember = await prisma.tripMember.findFirst({
      where: { tripId, userId: u3.userId },
    });
    expect(u3TripMember).toBeNull();

    // TC-VOT-04: U3 (GroupMember only) cannot view or mutate itinerary
    const u3Get = await request(app.getHttpServer())
      .get(`/groups/${groupId}/itinerary`)
      .set('Authorization', `Bearer ${u3.token}`)
      .expect(403);
    expect(u3Get.body.errorCode).toBe('TRIP_ACCESS_FORBIDDEN');

    const u3Post = await request(app.getHttpServer())
      .post(`/groups/${groupId}/itinerary/items`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({ dayNumber: 1, activity: 'U3 đề xuất trái phép' })
      .expect(403);
    expect(u3Post.body.errorCode).toBe('TRIP_ACCESS_FORBIDDEN');

    // TC-VOT-02 & TC-VOT-03: U1 creates itemA; U2 proposes itemB twice with same clientRequestId
    const itemARes = await request(app.getHttpServer())
      .post(`/groups/${groupId}/itinerary/items`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        dayNumber: 1,
        activity: 'Tháp Đồng Hồ Hạ Long',
        clientRequestId: 'w10-item-a',
      })
      .expect(201);
    const itemAId: string = itemARes.body.data.id;

    // U3 lacking Trip permission is ALSO rejected 403 when voting and withdrawing vote
    const u3Vote = await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({ vote: true })
      .expect(403);
    expect(u3Vote.body.errorCode).toBe('TRIP_ACCESS_FORBIDDEN');

    const u3Withdraw = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u3.token}`)
      .expect(403);
    expect(u3Withdraw.body.errorCode).toBe('TRIP_ACCESS_FORBIDDEN');

    // Trip owner lacking GroupMember is ALSO rejected 403 on group API, while /trips/:id/* behavior stays intact!
    const ownerNoGroup = await registerUser('Chủ Chuyến Thiếu GroupMember', 'owner_nogrp');
    const tripNoGroupRes = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${ownerNoGroup.token}`)
      .send({ title: 'Chuyến Riêng Kiểm Tra Dual-Gate' })
      .expect(201);
    const tripNoGroupId: string = tripNoGroupRes.body.data.id;
    const grpWithoutOwner = await prisma.group.create({
      data: {
        name: 'Nhóm Thiếu Chủ Chuyến',
        tripId: tripNoGroupId,
        members: { create: { userId: u2.userId, role: 'admin' } },
      },
    });
    const ownerNoGrpGet = await request(app.getHttpServer())
      .get(`/groups/${grpWithoutOwner.id}/itinerary`)
      .set('Authorization', `Bearer ${ownerNoGroup.token}`)
      .expect(403);
    expect(ownerNoGrpGet.body.errorCode).toBe('GROUP_FORBIDDEN');

    const ownerNoGrpPost = await request(app.getHttpServer())
      .post(`/groups/${grpWithoutOwner.id}/itinerary/items`)
      .set('Authorization', `Bearer ${ownerNoGroup.token}`)
      .send({ dayNumber: 1, activity: 'Thiếu GroupMember' })
      .expect(403);
    expect(ownerNoGrpPost.body.errorCode).toBe('GROUP_FORBIDDEN');

    // Existing /trips/:id/* behavior remains completely intact for ownerNoGroup!
    await request(app.getHttpServer())
      .get(`/trips/${tripNoGroupId}`)
      .set('Authorization', `Bearer ${ownerNoGroup.token}`)
      .expect(200);
    await request(app.getHttpServer())
      .post(`/trips/${tripNoGroupId}/itinerary`)
      .set('Authorization', `Bearer ${ownerNoGroup.token}`)
      .send({ dayNumber: 1, activity: 'Mục qua /trips/:id/itinerary vẫn chạy chuẩn' })
      .expect(201);

    const [itemB1, itemB2] = await Promise.all([
      request(app.getHttpServer())
        .post(`/groups/${groupId}/itinerary/items`)
        .set('Authorization', `Bearer ${u2.token}`)
        .send({
          dayNumber: 1,
          activity: 'Bảo tàng Quảng Ninh',
          clientRequestId: 'w10-item-b',
        }),
      request(app.getHttpServer())
        .post(`/groups/${groupId}/itinerary/items`)
        .set('Authorization', `Bearer ${u2.token}`)
        .send({
          dayNumber: 1,
          activity: 'Bảo tàng Quảng Ninh',
          clientRequestId: 'w10-item-b',
        }),
    ]);
    expect([200, 201]).toContain(itemB1.status);
    expect([200, 201]).toContain(itemB2.status);
    expect(itemB1.body.data.id).toBe(itemB2.body.data.id);
    const itemBId: string = itemB1.body.data.id;

    // Concurrent duplicate votes -> exactly 1 row in itinerary_votes
    const [vote1, vote2] = await Promise.all([
      request(app.getHttpServer())
        .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
        .set('Authorization', `Bearer ${u2.token}`)
        .send({ vote: true }),
      request(app.getHttpServer())
        .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
        .set('Authorization', `Bearer ${u2.token}`)
        .send({ vote: true }),
    ]);
    expect(vote1.status).toBe(200);
    expect(vote2.status).toBe(200);
    const voteCount = await prisma.itineraryVote.count({
      where: { itemId: itemAId, userId: u2.userId },
    });
    expect(voteCount).toBe(1);

    // Switch vote to false + resend switched vote, then withdraw vote + resend withdraw
    const switched = await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({ vote: false })
      .expect(200);
    expect(switched.body.data).toMatchObject({
      upvotes: 0,
      downvotes: 1,
      score: -1,
      myVote: false,
    });
    const switchedRetry = await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({ vote: false })
      .expect(200);
    expect(switchedRetry.body.data).toMatchObject({
      upvotes: 0,
      downvotes: 1,
      score: -1,
      myVote: false,
    });

    const withdrawn = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u2.token}`)
      .expect(200);
    expect(withdrawn.body.data).toMatchObject({
      upvotes: 0,
      downvotes: 0,
      score: 0,
      myVote: null,
    });
    const withdrawnRetry = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u2.token}`)
      .expect(200);
    expect(withdrawnRetry.body.data).toMatchObject({
      upvotes: 0,
      downvotes: 0,
      score: 0,
      myVote: null,
    });

    // TC-VOT-05: Member U2 cannot delete U1's itemA, CAN delete own itemB
    const u2DelA = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/itinerary/items/${itemAId}`)
      .set('Authorization', `Bearer ${u2.token}`)
      .expect(403);
    expect(u2DelA.body.errorCode).toBe('ITINERARY_ITEM_DELETE_FORBIDDEN');

    // Re-add another itemC by U2 so we have 2 items to test reorder & admin delete
    const itemCRes = await request(app.getHttpServer())
      .post(`/groups/${groupId}/itinerary/items`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({ dayNumber: 1, activity: 'Cầu Bãi Cháy' })
      .expect(201);
    const itemCId: string = itemCRes.body.data.id;

    await request(app.getHttpServer())
      .delete(`/groups/${groupId}/itinerary/items/${itemBId}`)
      .set('Authorization', `Bearer ${u2.token}`)
      .expect(200);

    // TC-VOT-06: Promote U2 to Group 'admin' in DB -> U2 STILL cannot reorder (only tripOwner U1 can!),
    // while U1 CAN reorder!
    await prisma.groupMember.updateMany({
      where: { groupId, userId: u2.userId },
      data: { role: 'admin' },
    });

    const u2Reorder = await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/reorder`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({
        dayNumber: 1,
        items: [
          { itemId: itemCId, orderIndex: 1 },
          { itemId: itemAId, orderIndex: 2 },
        ],
      })
      .expect(403);
    expect(u2Reorder.body.errorCode).toBe('TRIP_OWNER_REQUIRED');

    const u1Reorder = await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/reorder`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        dayNumber: 1,
        items: [
          { itemId: itemCId, orderIndex: 1 },
          { itemId: itemAId, orderIndex: 2 },
        ],
      })
      .expect(200);
    expect(u1Reorder.body.data.days[0].items.map((x: { id: string }) => x.id)).toEqual([
      itemCId,
      itemAId,
    ]);

    // TC-SEC-01: Zero PII in itinerary JSON
    const rawJson = JSON.stringify(u1Reorder.body);
    expect(rawJson).not.toContain(u1.email);
    expect(rawJson).not.toContain(u2.email);
    expect(rawJson).not.toContain('passwordHash');

    // TC-VOT-07: Ghost vote purged when U2 removed from group
    await request(app.getHttpServer())
      .put(`/groups/${groupId}/itinerary/items/${itemAId}/vote`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({ vote: true })
      .expect(200);

    await request(app.getHttpServer())
      .delete(`/groups/${groupId}/members/${u2.userId}`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(200);

    const afterRemove = await request(app.getHttpServer())
      .get(`/groups/${groupId}/itinerary`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(200);
    const itemAAfter = afterRemove.body.data.days[0].items.find(
      (i: { id: string }) => i.id === itemAId,
    );
    expect(itemAAfter.upvotes).toBe(0);
    expect(itemAAfter.score).toBe(0);
  });

  it('TC-EXP-01..09: enforces 100.000/3 VND split, CUSTOM validation, greedy suggestions, STRICT non-self-confirm even for admin, B1 settlement lock, 409 unsettled member protection, and soft-deleted account settlement', async () => {
    const u1 = await registerUser('Admin U1', 'exp_u1');
    const u2 = await registerUser('Member U2', 'exp_u2');
    const u3 = await registerUser('GroupOnly U3', 'exp_u3');

    const groupRes = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ name: 'Nhóm Sổ Chi Phí W10' })
      .expect(201);
    const groupId: string = groupRes.body.data.id;

    await request(app.getHttpServer())
      .post(`/groups/${groupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u2.userId })
      .expect(201);
    await request(app.getHttpServer())
      .post(`/groups/${groupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u3.userId })
      .expect(201);

    // TC-EXP-02: 2 VND / 3 members rejected
    const tooSmall = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        title: 'Quá nhỏ',
        amount: 2,
        splitType: 'EQUAL',
        participantIds: [u1.userId, u2.userId, u3.userId],
      })
      .expect(400);
    expect(tooSmall.body.errorCode).toBe('EXPENSE_AMOUNT_TOO_SMALL_FOR_SPLIT');

    // TC-EXP-01 & TC-EXP-02: Unlinked group stores tripId=null; reversing participantIds STILL gives +1 VND remainder to sortedIds[0] and sum == 100.000 VND
    const sortedIds = [u1.userId, u2.userId, u3.userId]
      .map((x) => x.toLowerCase())
      .sort();
    const exp100k = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        title: 'Taxi sân bay Hạ Long',
        amount: 100000,
        paidByUserId: u3.userId.toUpperCase(),
        splitType: 'EQUAL',
        participantIds: [
          u1.userId.toUpperCase(),
          u2.userId.toUpperCase(),
          u3.userId,
        ],
        clientRequestId: 'exp-100k-1',
      })
      .expect(201);
    expect(exp100k.body.data.tripId).toBeNull();

    const splits = exp100k.body.data.splits as Array<{
      userId: string;
      shareAmount: number;
    }>;
    expect(splits.map((s) => ({ userId: s.userId, shareAmount: s.shareAmount }))).toEqual([
      { userId: sortedIds[0], shareAmount: 33334 },
      { userId: sortedIds[1], shareAmount: 33333 },
      { userId: sortedIds[2], shareAmount: 33333 },
    ]);
    expect(splits.reduce((acc, s) => acc + s.shareAmount, 0)).toBe(100000);

    // Create a second 100.000 VND expense with REVERSED participantIds, verify exact same remainder recipient, then soft-delete it before settlements!
    const exp100kReversed = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        title: 'Taxi lượt về (đảo thứ tự đầu vào)',
        amount: 100000,
        paidByUserId: u3.userId,
        splitType: 'EQUAL',
        participantIds: [u3.userId, u2.userId, u1.userId],
        clientRequestId: 'exp-100k-reversed',
      })
      .expect(201);
    const reversedSplits = exp100kReversed.body.data.splits as Array<{
      userId: string;
      shareAmount: number;
    }>;
    expect(
      reversedSplits.map((s) => ({ userId: s.userId, shareAmount: s.shareAmount })),
    ).toEqual([
      { userId: sortedIds[0], shareAmount: 33334 },
      { userId: sortedIds[1], shareAmount: 33333 },
      { userId: sortedIds[2], shareAmount: 33333 },
    ]);
    expect(reversedSplits.reduce((acc, s) => acc + s.shareAmount, 0)).toBe(100000);
    await request(app.getHttpServer())
      .delete(`/groups/${groupId}/expenses/${exp100kReversed.body.data.id}`)
      .set('Authorization', `Bearer ${u3.token}`)
      .expect(200);

    // Verify server writes group.tripId when linked trip is active, and null once that trip is soft-deleted (while U3 lacking TripMember still uses the ledger!)
    const activeTripRes = await request(app.getHttpServer())
      .post('/trips')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ title: 'Chuyến Active Gắn Sổ Chi Phí' })
      .expect(201);
    const activeTripId: string = activeTripRes.body.data.id;
    const tripGroupRes = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ name: 'Nhóm Có Trip Active', tripId: activeTripId })
      .expect(201);
    const tripGroupId: string = tripGroupRes.body.data.id;
    await request(app.getHttpServer())
      .post(`/groups/${tripGroupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u3.userId })
      .expect(201);

    const expWithActiveTrip = await request(app.getHttpServer())
      .post(`/groups/${tripGroupId}/expenses`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        title: 'U3 ghi sổ khi trip active',
        amount: 20000,
        paidByUserId: u3.userId,
        splitType: 'CUSTOM',
        customSplits: [{ userId: u1.userId, shareAmount: 20000 }],
      })
      .expect(201);
    expect(expWithActiveTrip.body.data.tripId).toBe(activeTripId);

    const stWithActiveTrip = await request(app.getHttpServer())
      .post(`/groups/${tripGroupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: 20000,
      })
      .expect(201);
    expect(stWithActiveTrip.body.data.settlement.tripId).toBe(activeTripId);

    // Soft-delete activeTrip -> subsequent Expense and Settlement store tripId = null!
    await prisma.trip.update({
      where: { id: activeTripId },
      data: { deletedAt: new Date() },
    });
    const expAfterTripDeleted = await request(app.getHttpServer())
      .post(`/groups/${tripGroupId}/expenses`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        title: 'U3 ghi sổ sau khi trip xóa mềm',
        amount: 15000,
        paidByUserId: u3.userId,
        splitType: 'CUSTOM',
        customSplits: [{ userId: u1.userId, shareAmount: 15000 }],
      })
      .expect(201);
    expect(expAfterTripDeleted.body.data.tripId).toBeNull();
    const stAfterTripDeleted = await request(app.getHttpServer())
      .post(`/groups/${tripGroupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: 15000,
      })
      .expect(201);
    expect(stAfterTripDeleted.body.data.settlement.tripId).toBeNull();

    // TC-EXP-03: CUSTOM sum mismatch & outsider rejected
    const sumMismatch = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        title: 'Sai tổng',
        amount: 150000,
        splitType: 'CUSTOM',
        customSplits: [
          { userId: u1.userId, shareAmount: 100000 },
          { userId: u2.userId, shareAmount: 49999 },
        ],
      })
      .expect(400);
    expect(sumMismatch.body.errorCode).toBe('EXPENSE_SPLIT_SUM_MISMATCH');

    const outsiderUser = await registerUser('Outsider', 'exp_out');
    const invalidParticipant = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        title: 'Người lạ',
        amount: 50000,
        splitType: 'CUSTOM',
        customSplits: [{ userId: outsiderUser.userId, shareAmount: 50000 }],
      })
      .expect(400);
    expect(invalidParticipant.body.errorCode).toBe('EXPENSE_INVALID_PARTICIPANT');

    // TC-EXP-07: Removing U2 while netBalance != 0 is blocked with 409 MEMBER_HAS_UNSETTLED_BALANCE
    const blockedRemove = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/members/${u2.userId}`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(409);
    expect(blockedRemove.body.errorCode).toBe('MEMBER_HAS_UNSETTLED_BALANCE');

    // TC-EXP-04: STRICT NON-SELF-CONFIRM RULE!
    // Right now U3 paid 100.000 VND for [U1, U2, U3], so BOTH U1 (Admin!) and U2 (Member) owe U3!
    const planBefore = await request(app.getHttpServer())
      .get(`/groups/${groupId}/settlement-plan`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(200);
    expect(planBefore.body.data.zeroSumVerified).toBe(true);

    const u1Owed = splits.find((s) => s.userId === u1.userId.toLowerCase())!.shareAmount;
    const u2Owed = splits.find((s) => s.userId === u2.userId.toLowerCase())!.shareAmount;

    // (1) Member debtor U2 tries to self-confirm -> 403 SETTLEMENT_FORBIDDEN
    const u2SelfSettle = await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u2.token}`)
      .send({
        debtorId: u2.userId,
        creditorId: u3.userId,
        amount: u2Owed,
      })
      .expect(403);
    expect(u2SelfSettle.body.errorCode).toBe('SETTLEMENT_FORBIDDEN');

    // (2) Admin debtor U1 tries to self-confirm THEIR OWN debt -> MUST ALSO BE 403 SETTLEMENT_FORBIDDEN!
    const u1AdminSelfSettle = await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: u1Owed,
      })
      .expect(403);
    expect(u1AdminSelfSettle.body.errorCode).toBe('SETTLEMENT_FORBIDDEN');

    // (3) Creditor U3 confirms U1's debt with idempotent repeat; Admin U1 (not U2!) confirms U2's debt to U3
    const [sU1a, sU1b] = await Promise.all([
      request(app.getHttpServer())
        .post(`/groups/${groupId}/settlements`)
        .set('Authorization', `Bearer ${u3.token}`)
        .send({
          debtorId: u1.userId,
          creditorId: u3.userId,
          amount: u1Owed,
          clientRequestId: 'settle-u1-to-u3',
        }),
      request(app.getHttpServer())
        .post(`/groups/${groupId}/settlements`)
        .set('Authorization', `Bearer ${u3.token}`)
        .send({
          debtorId: u1.userId,
          creditorId: u3.userId,
          amount: u1Owed,
          clientRequestId: 'settle-u1-to-u3',
        }),
    ]);
    expect([200, 201]).toContain(sU1a.status);
    expect([200, 201]).toContain(sU1b.status);
    expect(sU1a.body.data.settlement.id).toBe(sU1b.body.data.settlement.id);
    expect(sU1a.body.data.settlement.tripId).toBeNull();

    // RBAC checked BEFORE idempotency: Admin debtor U1 retrying ALREADY-RECORDED clientRequestId 'settle-u1-to-u3' MUST STILL get 403!
    const u1AdminRetryRecordedKey = await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: u1Owed,
        clientRequestId: 'settle-u1-to-u3',
      })
      .expect(403);
    expect(u1AdminRetryRecordedKey.body.errorCode).toBe('SETTLEMENT_FORBIDDEN');

    // Same clientRequestId with DIFFERENT payload -> 409 IDEMPOTENCY_PAYLOAD_MISMATCH!
    const mismatchRes = await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: u1Owed - 1,
        clientRequestId: 'settle-u1-to-u3',
      })
      .expect(409);
    expect(mismatchRes.body.errorCode).toBe('IDEMPOTENCY_PAYLOAD_MISMATCH');

    await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        debtorId: u2.userId,
        creditorId: u3.userId,
        amount: u2Owed,
        clientRequestId: 'settle-u2-to-u3',
      })
      .expect(201);

    // TC-EXP-05: Overpayment by 1 VND rejected
    const overpay = await request(app.getHttpServer())
      .post(`/groups/${groupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: u3.userId,
        amount: 1,
      })
      .expect(400);
    expect(overpay.body.errorCode).toBe('SETTLEMENT_AMOUNT_EXCEEDS_DEBT');

    // TC-EXP-06: Deleting ANY expense across the entire group after settlement is locked (409 EXPENSE_LOCKED_BY_SETTLEMENT)
    const lockedDelete = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/expenses/${exp100k.body.data.id}`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(409);
    expect(lockedDelete.body.errorCode).toBe('EXPENSE_LOCKED_BY_SETTLEMENT');

    const expPostSettle = await request(app.getHttpServer())
      .post(`/groups/${groupId}/expenses`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        title: 'Nước suối phát sinh sau đối soát',
        amount: 10000,
        paidByUserId: u1.userId,
        splitType: 'CUSTOM',
        customSplits: [{ userId: u1.userId, shareAmount: 10000 }],
      })
      .expect(201);
    expect(expPostSettle.body.data.canDelete).toBe(false);
    const lockedDeleteNew = await request(app.getHttpServer())
      .delete(`/groups/${groupId}/expenses/${expPostSettle.body.data.id}`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(409);
    expect(lockedDeleteNew.body.errorCode).toBe('EXPENSE_LOCKED_BY_SETTLEMENT');

    // TC-EXP-08: Soft-deleted creditor + debtor is SOLE admin -> balance stays unchanged until another valid admin confirms!
    const soleAdminGroupRes = await request(app.getHttpServer())
      .post('/groups')
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ name: 'Nhóm U1 Là Admin Duy Nhất' })
      .expect(201);
    const soleAdminGroupId: string = soleAdminGroupRes.body.data.id;
    const userY = await registerUser('Sắp Xóa Mềm Y', 'exp_y');
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: userY.userId })
      .expect(201);
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/members`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({ userId: u3.userId })
      .expect(201);

    // Y pays 40.000 VND for U1 (U1 is the SOLE admin of soleAdminGroupId; U3 is just a regular member!)
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/expenses`)
      .set('Authorization', `Bearer ${userY.token}`)
      .send({
        title: 'Y trả hộ U1 (admin duy nhất)',
        amount: 40000,
        paidByUserId: userY.userId,
        splitType: 'CUSTOM',
        customSplits: [{ userId: u1.userId, shareAmount: 40000 }],
      })
      .expect(201);

    // Soft-delete creditor userY
    await prisma.user.update({
      where: { id: userY.userId },
      data: { deletedAt: new Date() },
    });

    // Neither sole-admin debtor U1 NOR regular member U3 can confirm -> both 403!
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/settlements`)
      .set('Authorization', `Bearer ${u1.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: userY.userId,
        amount: 40000,
      })
      .expect(403);
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: userY.userId,
        amount: 40000,
      })
      .expect(403);

    // Verify balances stay completely unchanged (+40.000 / -40.000) and Y cannot be removed (409)
    const planUnchanged = await request(app.getHttpServer())
      .get(`/groups/${soleAdminGroupId}/settlement-plan`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(200);
    const yBal = planUnchanged.body.data.balances.find(
      (b: { userId: string }) => b.userId === userY.userId.toLowerCase(),
    );
    const u1Bal = planUnchanged.body.data.balances.find(
      (b: { userId: string }) => b.userId === u1.userId.toLowerCase(),
    );
    expect(yBal.user.displayName).toBe('Tài khoản đã xóa');
    expect(yBal.netBalance).toBe(40000);
    expect(u1Bal.netBalance).toBe(-40000);
    expect(JSON.stringify(planUnchanged.body)).not.toContain(userY.email);

    await request(app.getHttpServer())
      .delete(`/groups/${soleAdminGroupId}/members/${userY.userId}`)
      .set('Authorization', `Bearer ${u1.token}`)
      .expect(409);

    // Once U3 becomes a valid independent admin (U3 != debtor U1), U3 confirms settlement -> balances become 0 -> Y removed cleanly!
    await prisma.groupMember.updateMany({
      where: { groupId: soleAdminGroupId, userId: u3.userId },
      data: { role: 'admin' },
    });
    await request(app.getHttpServer())
      .post(`/groups/${soleAdminGroupId}/settlements`)
      .set('Authorization', `Bearer ${u3.token}`)
      .send({
        debtorId: u1.userId,
        creditorId: userY.userId,
        amount: 40000,
      })
      .expect(201);

    await request(app.getHttpServer())
      .delete(`/groups/${soleAdminGroupId}/members/${userY.userId}`)
      .set('Authorization', `Bearer ${u3.token}`)
      .expect(200);

    // Financial history in DB remains intact!
    const settlementRows = await prisma.settlement.count({
      where: { groupId: soleAdminGroupId, creditorId: userY.userId.toLowerCase() },
    });
    expect(settlementRows).toBe(1);
  });
});
