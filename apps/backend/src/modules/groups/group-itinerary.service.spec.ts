import {
  ConflictException,
  ForbiddenException,
} from '@nestjs/common';
import { TripStatus } from '@prisma/client';
import { InMemoryPrismaService } from '../../../test/e2e-harness/in-memory-prisma.service';
import { PrismaService } from '../../prisma/prisma.service';
import { GroupItineraryService } from './group-itinerary.service';
import { GroupsService } from './groups.service';

describe('GroupItineraryService (W10 WP-ITIN-01 Unit)', () => {
  let mem: InMemoryPrismaService;
  let groupsService: GroupsService;
  let itinService: GroupItineraryService;

  let ownerId: string;
  let dualMemberId: string;
  let groupOnlyMemberId: string;
  let tripId: string;

  beforeEach(async () => {
    mem = new InMemoryPrismaService();
    mem.seed();
    const prisma = mem as unknown as PrismaService;
    groupsService = new GroupsService(prisma);
    itinService = new GroupItineraryService(prisma);

    const u1 = await mem.user.create({
      data: {
        email: 'u1@gomate.vn',
        passwordHash: 'hash',
        profile: { create: { displayName: 'Chủ Chuyến' } },
      },
    });
    const u2 = await mem.user.create({
      data: {
        email: 'u2@gomate.vn',
        passwordHash: 'hash',
        profile: { create: { displayName: 'Thành Viên Đủ Quyền' } },
      },
    });
    const u3 = await mem.user.create({
      data: {
        email: 'u3@gomate.vn',
        passwordHash: 'hash',
        profile: { create: { displayName: 'Chỉ GroupMember' } },
      },
    });
    ownerId = String(u1.id);
    dualMemberId = String(u2.id);
    groupOnlyMemberId = String(u3.id);

    const trip = await mem.trip.create({
      data: {
        userId: ownerId,
        title: 'Hạ Long W10',
        status: TripStatus.PLANNED,
      },
    });
    tripId = trip.id;
    await mem.tripMember.create({
      data: { tripId, userId: dualMemberId, role: 'member' },
    });
  });

  it('returns guidance state (tripLinked=false) on GET and 409 GROUP_TRIP_NOT_LINKED on writes when group has no trip', async () => {
    const g = await groupsService.create(ownerId, { name: 'Nhóm Chưa Gắn Trip' });
    const state = await itinService.getItinerary(g.id, ownerId);
    expect(state.tripLinked).toBe(false);
    expect(state.canAttachTrip).toBe(true);
    expect(state.days).toEqual([]);

    await expect(
      itinService.proposeItem(g.id, ownerId, {
        dayNumber: 1,
        activity: 'Đi ăn hải sản',
      }),
    ).rejects.toThrow(ConflictException);
  });

  it('enforces dual-gate RBAC, 1-vote/user/item switch & withdraw, self-authored delete, and trip-owner-only reorder', async () => {
    const g = await groupsService.create(ownerId, {
      name: 'Nhóm Hạ Long W10',
      tripId,
    });
    await groupsService.addMember(g.id, ownerId, { userId: dualMemberId });
    await groupsService.addMember(g.id, ownerId, { userId: groupOnlyMemberId });

    // Group-only member cannot view or propose
    await expect(itinService.getItinerary(g.id, groupOnlyMemberId)).rejects.toThrow(
      ForbiddenException,
    );
    await expect(
      itinService.proposeItem(g.id, groupOnlyMemberId, {
        dayNumber: 1,
        activity: 'Hack',
      }),
    ).rejects.toThrow(ForbiddenException);

    // Owner proposes item A, dual member proposes item B (idempotent with clientRequestId)
    const itemA = await itinService.proposeItem(g.id, ownerId, {
      dayNumber: 1,
      activity: 'Tháp Đồng Hồ',
      clientRequestId: 'req-a',
    });
    const itemB1 = await itinService.proposeItem(g.id, dualMemberId, {
      dayNumber: 1,
      activity: 'Bảo tàng Quảng Ninh',
      clientRequestId: 'req-b',
    });
    const itemB2 = await itinService.proposeItem(g.id, dualMemberId, {
      dayNumber: 1,
      activity: 'Bảo tàng Quảng Ninh',
      clientRequestId: 'req-b',
    });
    expect(itemB1.id).toBe(itemB2.id);

    // Vote, repeat same vote (idempotent), switch vote, withdraw vote
    const v1 = await itinService.voteItem(g.id, itemA.id, dualMemberId, {
      vote: true,
    });
    expect(v1).toMatchObject({ upvotes: 1, downvotes: 0, score: 1, myVote: true });
    const v1Dup = await itinService.voteItem(g.id, itemA.id, dualMemberId, {
      vote: true,
    });
    expect(v1Dup).toMatchObject({ upvotes: 1, downvotes: 0, score: 1, myVote: true });

    const v2 = await itinService.voteItem(g.id, itemA.id, dualMemberId, {
      vote: false,
    });
    expect(v2).toMatchObject({ upvotes: 0, downvotes: 1, score: -1, myVote: false });

    const v3 = await itinService.withdrawVote(g.id, itemA.id, dualMemberId);
    expect(v3).toMatchObject({ upvotes: 0, downvotes: 0, score: 0, myVote: null });

    // Dual member cannot reorder and cannot delete owner's itemA
    await expect(
      itinService.reorderItems(g.id, dualMemberId, {
        dayNumber: 1,
        items: [
          { itemId: itemB1.id, orderIndex: 1 },
          { itemId: itemA.id, orderIndex: 2 },
        ],
      }),
    ).rejects.toThrow(ForbiddenException);

    await expect(
      itinService.deleteItem(g.id, itemA.id, dualMemberId),
    ).rejects.toThrow(ForbiddenException);

    // Trip owner reorders [A, B] -> [B, A]
    const reordered = await itinService.reorderItems(g.id, ownerId, {
      dayNumber: 1,
      items: [
        { itemId: itemB1.id, orderIndex: 1 },
        { itemId: itemA.id, orderIndex: 2 },
      ],
    });
    expect(reordered.days[0].items.map((i) => i.id)).toEqual([
      itemB1.id,
      itemA.id,
    ]);

    // Dual member deletes their own itemB1
    const delB = await itinService.deleteItem(g.id, itemB1.id, dualMemberId);
    expect(delB.deleted).toBe(true);
  });
});
