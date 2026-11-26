import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { Prisma, TravelStyle, TripStatus } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import {
  SAFE_BUDDY_USER_SELECT,
  SafeBuddyPeerView,
  toSafeBuddyPeerView,
} from '../matches/matches.service';
import { ReorderItineraryDto } from '../trips/dto/reorder-itinerary.dto';
import {
  ProposeGroupItineraryItemDto,
  VoteItineraryItemDto,
} from './dto/group-itinerary.dto';
import {
  GROUP_ERROR_CODES,
  GROUP_ROLES,
  GroupRole,
  normalizeUuid,
} from './groups.constants';

type DbClient = PrismaService | Prisma.TransactionClient;

interface SelectedSafeUser {
  id: string;
  deletedAt: Date | null;
  profile: {
    displayName: string | null;
    avatar: string | null;
    bio: string | null;
    nationality: string | null;
    languages: string[];
  } | null;
  preferences: {
    travelStyle: TravelStyle | null;
    interests: string[];
  } | null;
}

interface LinkedTripRow {
  id: string;
  title: string;
  userId: string;
  status: TripStatus;
}

export interface GroupItineraryItemView {
  id: string;
  itineraryId: string;
  dayNumber: number;
  placeId: string | null;
  place: { id: string; name: string; address: string | null } | null;
  orderIndex: number;
  startTime: string | null;
  endTime: string | null;
  activity: string;
  notes: string | null;
  estimatedCost: number | null;
  transportMode: string | null;
  createdByUserId: string | null;
  createdBy: SafeBuddyPeerView | null;
  upvotes: number;
  downvotes: number;
  score: number;
  myVote: boolean | null;
  canDelete: boolean;
}

export interface GroupItineraryDayView {
  itineraryId: string;
  dayNumber: number;
  date: Date | null;
  title: string | null;
  items: GroupItineraryItemView[];
}

export interface GroupItineraryStateView {
  groupId: string;
  tripLinked: boolean;
  tripId: string | null;
  tripTitle: string | null;
  tripStatus: TripStatus | null;
  canAttachTrip: boolean;
  canReorder: boolean;
  guidanceMessage?: string;
  days: GroupItineraryDayView[];
}

export interface VoteResultView {
  itemId: string;
  upvotes: number;
  downvotes: number;
  score: number;
  myVote: boolean | null;
}

@Injectable()
export class GroupItineraryService {
  constructor(private readonly prisma: PrismaService) {}

  private async _lockGroup(
    tx: Prisma.TransactionClient,
    groupId: string,
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    await tx.$queryRaw`SELECT id FROM "groups" WHERE id = ${groupId}::uuid FOR UPDATE`;
  }

  private async _assertVerifiedPlace(
    db: DbClient,
    placeId: string,
  ): Promise<void> {
    const found = await db.place.findMany({
      where: {
        id: placeId,
        deletedAt: null,
        placeSources: { some: {} },
      },
      select: { id: true },
    });
    if (found.length === 0) {
      throw new NotFoundException({
        errorCode: GROUP_ERROR_CODES.PLACE_NOT_FOUND,
        message: `Địa điểm "${placeId}" không tồn tại hoặc chưa xác thực`,
      });
    }
  }

  private async _resolveAccess(
    db: DbClient,
    rawGroupId: string,
    rawActorId: string,
    options: { requireLinkedTrip: boolean },
  ): Promise<{
    groupId: string;
    actorId: string;
    myGroupRole: GroupRole;
    trip: LinkedTripRow | null;
    isTripOwner: boolean;
    eligibleVoterIds: Set<string>;
    safeUserById: Map<string, SafeBuddyPeerView>;
  }> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);

    const group = await db.group.findUnique({
      where: { id: groupId },
      include: {
        members: {
          where: { user: { deletedAt: null } },
          include: { user: { select: SAFE_BUDDY_USER_SELECT } },
        },
      },
    });

    if (!group) {
      throw new NotFoundException({
        errorCode: GROUP_ERROR_CODES.GROUP_NOT_FOUND,
        message: 'Nhóm đồng hành không tồn tại',
      });
    }

    const activeMembers = (group.members ?? []).filter(
      (m) => m.user !== null && m.user.deletedAt === null,
    );
    const actorMembership = activeMembers.find(
      (m) => normalizeUuid(m.userId) === actorId,
    );
    if (!actorMembership) {
      throw new ForbiddenException({
        errorCode: GROUP_ERROR_CODES.GROUP_FORBIDDEN,
        message: 'Bạn không phải thành viên của nhóm này',
      });
    }

    let trip: LinkedTripRow | null = null;
    if (group.tripId) {
      trip = await db.trip.findFirst({
        where: { id: group.tripId, deletedAt: null },
        select: { id: true, title: true, userId: true, status: true },
      });
    }

    const isTripOwner =
      trip !== null && normalizeUuid(trip.userId) === actorId;
    const myGroupRole: GroupRole =
      actorMembership.role === GROUP_ROLES.ADMIN || isTripOwner
        ? GROUP_ROLES.ADMIN
        : GROUP_ROLES.MEMBER;

    const safeUserById = new Map<string, SafeBuddyPeerView>();
    for (const m of activeMembers) {
      const safeUser = m.user as SelectedSafeUser | null;
      if (safeUser) {
        safeUserById.set(normalizeUuid(m.userId), toSafeBuddyPeerView(safeUser));
      }
    }

    if (!trip) {
      if (options.requireLinkedTrip) {
        throw new ConflictException({
          errorCode: GROUP_ERROR_CODES.GROUP_TRIP_NOT_LINKED,
          message:
            'Nhóm chưa được gắn với chuyến đi hợp lệ để lập và bình chọn lịch trình',
        });
      }
      return {
        groupId: group.id,
        actorId,
        myGroupRole,
        trip: null,
        isTripOwner: false,
        eligibleVoterIds: new Set<string>(),
        safeUserById,
      };
    }

    // Gate 2: Dual-gate check — caller must ALSO be Trip Owner or valid TripMember
    const tripMembers = await db.tripMember.findMany({
      where: { tripId: trip.id },
      select: { userId: true },
    });
    const tripMemberIdSet = new Set(
      tripMembers.map((tm) => normalizeUuid(tm.userId)),
    );
    const tripOwnerNormalized = normalizeUuid(trip.userId);

    const hasTripAccess = isTripOwner || tripMemberIdSet.has(actorId);
    if (!hasTripAccess) {
      throw new ForbiddenException({
        errorCode: GROUP_ERROR_CODES.TRIP_ACCESS_FORBIDDEN,
        message:
          'Bạn cần được chủ chuyến đi cấp quyền thành viên chuyến đi để xem và bình chọn lịch trình',
      });
    }

    const eligibleVoterIds = new Set<string>();
    for (const m of activeMembers) {
      const uid = normalizeUuid(m.userId);
      if (uid === tripOwnerNormalized || tripMemberIdSet.has(uid)) {
        eligibleVoterIds.add(uid);
      }
    }

    return {
      groupId: group.id,
      actorId,
      myGroupRole,
      trip,
      isTripOwner,
      eligibleVoterIds,
      safeUserById,
    };
  }

  private _computeVoteSummary(
    votes: ReadonlyArray<{ userId: string; vote: boolean }>,
    eligibleVoterIds: Set<string>,
    actorId: string,
  ): {
    upvotes: number;
    downvotes: number;
    score: number;
    myVote: boolean | null;
  } {
    let upvotes = 0;
    let downvotes = 0;
    let myVote: boolean | null = null;

    for (const v of votes) {
      const uid = normalizeUuid(v.userId);
      if (!eligibleVoterIds.has(uid)) {
        continue;
      }
      if (v.vote) {
        upvotes += 1;
      } else {
        downvotes += 1;
      }
      if (uid === actorId) {
        myVote = v.vote;
      }
    }

    return {
      upvotes,
      downvotes,
      score: upvotes - downvotes,
      myVote,
    };
  }

  private async _buildFullItineraryState(
    db: DbClient,
    ctx: {
      groupId: string;
      actorId: string;
      myGroupRole: GroupRole;
      trip: LinkedTripRow | null;
      isTripOwner: boolean;
      eligibleVoterIds: Set<string>;
      safeUserById: Map<string, SafeBuddyPeerView>;
    },
  ): Promise<GroupItineraryStateView> {
    if (!ctx.trip) {
      return {
        groupId: ctx.groupId,
        tripLinked: false,
        tripId: null,
        tripTitle: null,
        tripStatus: null,
        canAttachTrip: ctx.myGroupRole === GROUP_ROLES.ADMIN,
        canReorder: false,
        guidanceMessage:
          ctx.myGroupRole === GROUP_ROLES.ADMIN
            ? 'Nhóm chưa được gắn với chuyến đi hợp lệ. Hãy mở màn Chi tiết chuyến đi để tạo hoặc mở nhóm đồng hành gắn với chuyến đi đó.'
            : 'Nhóm chưa được gắn với chuyến đi hợp lệ. Vui lòng chờ chủ chuyến hoặc trưởng nhóm gắn chuyến đi trước khi đề xuất và bình chọn.',
        days: [],
      };
    }

    const itineraries = await db.itinerary.findMany({
      where: { tripId: ctx.trip.id },
      orderBy: { dayNumber: 'asc' },
      include: {
        items: {
          orderBy: { orderIndex: 'asc' },
          include: {
            place: { select: { id: true, name: true, address: true } },
            createdBy: { select: SAFE_BUDDY_USER_SELECT },
            votes: { select: { userId: true, vote: true } },
          },
        },
      },
    });

    const isCancelled = ctx.trip.status === TripStatus.CANCELLED;

    const days: GroupItineraryDayView[] = itineraries.map((day) => ({
      itineraryId: day.id,
      dayNumber: day.dayNumber,
      date: day.date ?? null,
      title: day.title ?? null,
      items: (day.items ?? []).map((item) => {
        const voteSummary = this._computeVoteSummary(
          item.votes ?? [],
          ctx.eligibleVoterIds,
          ctx.actorId,
        );
        const creatorIdNorm = item.createdByUserId
          ? normalizeUuid(item.createdByUserId)
          : null;
        const createdBySafe =
          (creatorIdNorm ? ctx.safeUserById.get(creatorIdNorm) : null) ??
          (item.createdBy
            ? toSafeBuddyPeerView(item.createdBy as SelectedSafeUser)
            : null);

        const canDelete =
          !isCancelled &&
          (ctx.isTripOwner ||
            ctx.myGroupRole === GROUP_ROLES.ADMIN ||
            (creatorIdNorm !== null && creatorIdNorm === ctx.actorId));

        return {
          id: item.id,
          itineraryId: item.itineraryId,
          dayNumber: day.dayNumber,
          placeId: item.placeId ?? null,
          place: item.place
            ? {
                id: item.place.id,
                name: item.place.name,
                address: item.place.address ?? null,
              }
            : null,
          orderIndex: item.orderIndex,
          startTime: item.startTime ?? null,
          endTime: item.endTime ?? null,
          activity: item.activity,
          notes: item.notes ?? null,
          estimatedCost: item.estimatedCost ?? null,
          transportMode: item.transportMode ?? null,
          createdByUserId: item.createdByUserId ?? null,
          createdBy: createdBySafe,
          upvotes: voteSummary.upvotes,
          downvotes: voteSummary.downvotes,
          score: voteSummary.score,
          myVote: voteSummary.myVote,
          canDelete,
        };
      }),
    }));

    return {
      groupId: ctx.groupId,
      tripLinked: true,
      tripId: ctx.trip.id,
      tripTitle: ctx.trip.title,
      tripStatus: ctx.trip.status,
      canAttachTrip: false,
      canReorder: ctx.isTripOwner && !isCancelled,
      days,
    };
  }

  async getItinerary(
    groupId: string,
    actorId: string,
  ): Promise<GroupItineraryStateView> {
    const ctx = await this._resolveAccess(this.prisma, groupId, actorId, {
      requireLinkedTrip: false,
    });
    return this._buildFullItineraryState(this.prisma, ctx);
  }

  async proposeItem(
    rawGroupId: string,
    rawActorId: string,
    dto: ProposeGroupItineraryItemDto,
    idempotencyKey?: string,
  ): Promise<GroupItineraryItemView> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);

    const rawReqId = dto.clientRequestId?.trim() || idempotencyKey?.trim();
    const effectiveClientRequestId =
      rawReqId && rawReqId.length > 0 ? rawReqId.slice(0, 128) : undefined;

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveAccess(tx, groupId, actorId, {
        requireLinkedTrip: true,
      });
      const trip = ctx.trip!;

      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.TRIP_CANCELLED,
          message: 'Chuyến đi đã hủy không thể đề xuất thêm hoạt động',
        });
      }

      if (dto.placeId) {
        await this._assertVerifiedPlace(tx, dto.placeId);
      }

      const itinerary = await tx.itinerary.upsert({
        where: {
          tripId_dayNumber: { tripId: trip.id, dayNumber: dto.dayNumber },
        },
        create: { tripId: trip.id, dayNumber: dto.dayNumber },
        update: {},
      });

      const formatItem = (
        row: {
          id: string;
          itineraryId: string;
          placeId: string | null;
          orderIndex: number;
          startTime: string | null;
          endTime: string | null;
          activity: string;
          notes: string | null;
          estimatedCost: number | null;
          transportMode: string | null;
          createdByUserId?: string | null;
          place?: { id: string; name: string; address: string | null } | null;
          votes?: Array<{ userId: string; vote: boolean }>;
        },
      ): GroupItineraryItemView => {
        const creatorIdNorm = row.createdByUserId
          ? normalizeUuid(row.createdByUserId)
          : null;
        const voteSummary = this._computeVoteSummary(
          row.votes ?? [],
          ctx.eligibleVoterIds,
          ctx.actorId,
        );
        return {
          id: row.id,
          itineraryId: row.itineraryId,
          dayNumber: itinerary.dayNumber,
          placeId: row.placeId ?? null,
          place: row.place
            ? {
                id: row.place.id,
                name: row.place.name,
                address: row.place.address ?? null,
              }
            : null,
          orderIndex: row.orderIndex,
          startTime: row.startTime ?? null,
          endTime: row.endTime ?? null,
          activity: row.activity,
          notes: row.notes ?? null,
          estimatedCost: row.estimatedCost ?? null,
          transportMode: row.transportMode ?? null,
          createdByUserId: row.createdByUserId ?? null,
          createdBy: creatorIdNorm
            ? (ctx.safeUserById.get(creatorIdNorm) ?? null)
            : null,
          upvotes: voteSummary.upvotes,
          downvotes: voteSummary.downvotes,
          score: voteSummary.score,
          myVote: voteSummary.myVote,
          canDelete:
            ctx.isTripOwner ||
            ctx.myGroupRole === GROUP_ROLES.ADMIN ||
            (creatorIdNorm !== null && creatorIdNorm === ctx.actorId),
        };
      };

      if (effectiveClientRequestId) {
        const existing = await tx.itineraryItem.findFirst({
          where: {
            itineraryId: itinerary.id,
            clientRequestId: effectiveClientRequestId,
          },
          include: {
            place: { select: { id: true, name: true, address: true } },
            votes: { select: { userId: true, vote: true } },
          },
        });
        if (existing) {
          if (existing.activity !== dto.activity.trim()) {
            throw new ConflictException({
              errorCode: GROUP_ERROR_CODES.IDEMPOTENCY_PAYLOAD_MISMATCH,
              message:
                'clientRequestId đã được sử dụng cho một hoạt động đề xuất khác',
            });
          }
          return formatItem(existing);
        }
      }

      const lastItem = await tx.itineraryItem.findFirst({
        where: { itineraryId: itinerary.id },
        orderBy: { orderIndex: 'desc' },
        select: { orderIndex: true },
      });
      const nextOrderIndex = (lastItem?.orderIndex ?? 0) + 1;

      try {
        const created = await tx.itineraryItem.create({
          data: {
            itineraryId: itinerary.id,
            placeId: dto.placeId,
            createdByUserId: actorId,
            ...(effectiveClientRequestId
              ? { clientRequestId: effectiveClientRequestId }
              : {}),
            orderIndex: nextOrderIndex,
            startTime: dto.startTime,
            endTime: dto.endTime,
            activity: dto.activity.trim(),
            notes: dto.notes?.trim(),
            estimatedCost: dto.estimatedCost,
            transportMode: dto.transportMode,
          },
          include: {
            place: { select: { id: true, name: true, address: true } },
          },
        });

        return formatItem({ ...created, votes: [] });
      } catch (error) {
        const code =
          typeof error === 'object' && error !== null && 'code' in error
            ? (error as { code?: unknown }).code
            : undefined;
        if (code === 'P2002' && effectiveClientRequestId) {
          const existing = await tx.itineraryItem.findFirst({
            where: {
              itineraryId: itinerary.id,
              clientRequestId: effectiveClientRequestId,
            },
            include: {
              place: { select: { id: true, name: true, address: true } },
              votes: { select: { userId: true, vote: true } },
            },
          });
          if (existing) {
            return formatItem(existing);
          }
        }
        throw error;
      }
    });
  }

  async deleteItem(
    rawGroupId: string,
    rawItemId: string,
    rawActorId: string,
  ): Promise<{ deleted: boolean; groupId: string; itemId: string }> {
    const groupId = normalizeUuid(rawGroupId);
    const itemId = normalizeUuid(rawItemId);
    const actorId = normalizeUuid(rawActorId);

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveAccess(tx, groupId, actorId, {
        requireLinkedTrip: true,
      });
      const trip = ctx.trip!;

      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.TRIP_CANCELLED,
          message: 'Chuyến đi đã hủy không thể xóa hoạt động',
        });
      }

      const item = await tx.itineraryItem.findFirst({
        where: { id: itemId, itinerary: { tripId: trip.id } },
        select: { id: true, createdByUserId: true },
      });
      if (!item) {
        throw new NotFoundException({
          errorCode: GROUP_ERROR_CODES.ITINERARY_ITEM_NOT_FOUND,
          message: 'Hoạt động không tồn tại trong lịch trình chuyến đi',
        });
      }

      const creatorIdNorm = item.createdByUserId
        ? normalizeUuid(item.createdByUserId)
        : null;
      const canDelete =
        ctx.isTripOwner ||
        ctx.myGroupRole === GROUP_ROLES.ADMIN ||
        (creatorIdNorm !== null && creatorIdNorm === actorId);

      if (!canDelete) {
        throw new ForbiddenException({
          errorCode: GROUP_ERROR_CODES.ITINERARY_ITEM_DELETE_FORBIDDEN,
          message:
            'Thành viên chỉ có thể xóa mục lịch trình do chính mình đề xuất',
        });
      }

      await tx.itineraryVote.deleteMany({ where: { itemId: item.id } });
      await tx.itineraryItem.delete({ where: { id: item.id } });

      return {
        deleted: true,
        groupId: ctx.groupId,
        itemId: item.id,
      };
    });
  }

  async reorderItems(
    rawGroupId: string,
    rawActorId: string,
    dto: ReorderItineraryDto,
  ): Promise<GroupItineraryStateView> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveAccess(tx, groupId, actorId, {
        requireLinkedTrip: true,
      });
      const trip = ctx.trip!;

      if (!ctx.isTripOwner) {
        throw new ForbiddenException({
          errorCode: GROUP_ERROR_CODES.TRIP_OWNER_REQUIRED,
          message: 'Chỉ chủ chuyến đi mới có quyền đổi thứ tự lịch trình',
        });
      }

      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.TRIP_CANCELLED,
          message: 'Chuyến đi đã hủy không thể đổi thứ tự lịch trình',
        });
      }

      const seenItemIds = new Set<string>();
      for (const entry of dto.items) {
        const normId = normalizeUuid(entry.itemId);
        if (seenItemIds.has(normId)) {
          throw new BadRequestException({
            errorCode: 'VALIDATION_ERROR',
            message: 'Danh sách itemId bị trùng lặp',
          });
        }
        seenItemIds.add(normId);
      }

      const existingTripItems = await tx.itineraryItem.findMany({
        where: { itinerary: { tripId: trip.id } },
        select: {
          id: true,
          itineraryId: true,
          itinerary: { select: { dayNumber: true } },
        },
      });
      const existingById = new Map(
        existingTripItems.map((row) => [normalizeUuid(row.id), row]),
      );

      const submittedByItinerary = new Map<
        string,
        Array<{ id: string; orderIndex: number }>
      >();

      for (const entry of dto.items) {
        const normId = normalizeUuid(entry.itemId);
        const existing = existingById.get(normId);
        if (!existing) {
          throw new NotFoundException({
            errorCode: GROUP_ERROR_CODES.ITINERARY_ITEM_NOT_FOUND,
            message: 'Hoạt động không tồn tại trong lịch trình',
          });
        }
        if (
          dto.dayNumber !== undefined &&
          existing.itinerary.dayNumber !== dto.dayNumber
        ) {
          throw new BadRequestException({
            errorCode: 'VALIDATION_ERROR',
            message: `Hoạt động "${entry.itemId}" không thuộc ngày ${dto.dayNumber}`,
          });
        }
        const list = submittedByItinerary.get(existing.itineraryId) ?? [];
        list.push({ id: existing.id, orderIndex: entry.orderIndex });
        submittedByItinerary.set(existing.itineraryId, list);
      }

      for (const [itineraryId, submittedList] of submittedByItinerary.entries()) {
        const totalInDay = existingTripItems.filter(
          (row) => row.itineraryId === itineraryId,
        ).length;
        if (submittedList.length !== totalInDay) {
          throw new BadRequestException({
            errorCode: GROUP_ERROR_CODES.REORDER_INCOMPLETE_DAY,
            message:
              'Phải gửi đầy đủ tất cả hoạt động trong ngày khi đổi thứ tự',
          });
        }
        const sortedIndices = submittedList
          .map((x) => x.orderIndex)
          .sort((a, b) => a - b);
        for (let idx = 0; idx < sortedIndices.length; idx++) {
          if (sortedIndices[idx] !== idx + 1) {
            throw new BadRequestException({
              errorCode: GROUP_ERROR_CODES.REORDER_NON_CONTIGUOUS_INDEX,
              message: 'Thứ tự orderIndex trong mỗi ngày phải liên tục từ 1 đến N',
            });
          }
        }
      }

      for (const [, submittedList] of submittedByItinerary.entries()) {
        for (const entry of submittedList) {
          await tx.itineraryItem.update({
            where: { id: entry.id },
            data: { orderIndex: entry.orderIndex },
          });
        }
      }

      return this._buildFullItineraryState(tx, ctx);
    });
  }

  async voteItem(
    rawGroupId: string,
    rawItemId: string,
    rawActorId: string,
    dto: VoteItineraryItemDto,
  ): Promise<VoteResultView> {
    const groupId = normalizeUuid(rawGroupId);
    const itemId = normalizeUuid(rawItemId);
    const actorId = normalizeUuid(rawActorId);

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveAccess(tx, groupId, actorId, {
        requireLinkedTrip: true,
      });
      const trip = ctx.trip!;

      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.TRIP_CANCELLED,
          message: 'Chuyến đi đã hủy không thể bình chọn lịch trình',
        });
      }

      const item = await tx.itineraryItem.findFirst({
        where: { id: itemId, itinerary: { tripId: trip.id } },
        select: { id: true },
      });
      if (!item) {
        throw new NotFoundException({
          errorCode: GROUP_ERROR_CODES.ITINERARY_ITEM_NOT_FOUND,
          message: 'Hoạt động không tồn tại trong lịch trình',
        });
      }

      await tx.itineraryVote.upsert({
        where: {
          itemId_userId: { itemId: item.id, userId: actorId },
        },
        create: {
          itemId: item.id,
          userId: actorId,
          vote: dto.vote,
        },
        update: {
          vote: dto.vote,
        },
      });

      const votes = await tx.itineraryVote.findMany({
        where: { itemId: item.id },
        select: { userId: true, vote: true },
      });
      const summary = this._computeVoteSummary(
        votes,
        ctx.eligibleVoterIds,
        actorId,
      );

      return {
        itemId: item.id,
        ...summary,
      };
    });
  }

  async withdrawVote(
    rawGroupId: string,
    rawItemId: string,
    rawActorId: string,
  ): Promise<VoteResultView> {
    const groupId = normalizeUuid(rawGroupId);
    const itemId = normalizeUuid(rawItemId);
    const actorId = normalizeUuid(rawActorId);

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveAccess(tx, groupId, actorId, {
        requireLinkedTrip: true,
      });
      const trip = ctx.trip!;

      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.TRIP_CANCELLED,
          message: 'Chuyến đi đã hủy không thể rút phiếu lịch trình',
        });
      }

      const item = await tx.itineraryItem.findFirst({
        where: { id: itemId, itinerary: { tripId: trip.id } },
        select: { id: true },
      });
      if (!item) {
        throw new NotFoundException({
          errorCode: GROUP_ERROR_CODES.ITINERARY_ITEM_NOT_FOUND,
          message: 'Hoạt động không tồn tại trong lịch trình',
        });
      }

      await tx.itineraryVote.deleteMany({
        where: { itemId: item.id, userId: actorId },
      });

      const votes = await tx.itineraryVote.findMany({
        where: { itemId: item.id },
        select: { userId: true, vote: true },
      });
      const summary = this._computeVoteSummary(
        votes,
        ctx.eligibleVoterIds,
        actorId,
      );

      return {
        itemId: item.id,
        ...summary,
        myVote: null,
      };
    });
  }
}
