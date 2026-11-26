import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { Prisma, TravelStyle } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import {
  SAFE_BUDDY_USER_SELECT,
  SafeBuddyPeerView,
  toSafeBuddyPeerView,
} from '../matches/matches.service';
import { CreateGroupDto } from './dto/create-group.dto';
import { UpdateGroupDto } from './dto/update-group.dto';
import { AddGroupMemberDto } from './dto/add-group-member.dto';
import { GroupExpensesService } from './group-expenses.service';
import {
  GROUP_ERROR_CODES,
  GROUP_ROLES,
  GroupRole,
  normalizeUuid,
} from './groups.constants';

export interface SafeGroupMemberView {
  id: string;
  groupId: string;
  userId: string;
  role: GroupRole;
  isTripOwner: boolean;
  user: SafeBuddyPeerView;
}

export interface GroupResponseView {
  id: string;
  name: string;
  description: string | null;
  tripId: string | null;
  tripTitle: string | null;
  tripOwnerId: string | null;
  createdAt: Date;
  myRole: GroupRole;
  memberCount: number;
  members: SafeGroupMemberView[];
}

interface LinkedTripSummary {
  id: string;
  title: string;
  userId: string;
}

interface SelectedGroupMemberRow {
  id: string;
  groupId: string;
  userId: string;
  role: string;
  user: {
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
  } | null;
}

interface SelectedGroupRow {
  id: string;
  name: string;
  description: string | null;
  tripId: string | null;
  createdAt: Date;
  members: SelectedGroupMemberRow[];
}

@Injectable()
export class GroupsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly groupExpensesService?: GroupExpensesService,
  ) {}

  private async _lockTrip(
    tx: Prisma.TransactionClient,
    tripId: string,
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    await tx.$queryRaw`SELECT id FROM "trips" WHERE id = ${tripId}::uuid FOR UPDATE`;
  }

  private async _lockGroup(
    tx: Prisma.TransactionClient,
    groupId: string,
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    await tx.$queryRaw`SELECT id FROM "groups" WHERE id = ${groupId}::uuid FOR UPDATE`;
  }

  private async _lockUsersInOrder(
    tx: Prisma.TransactionClient,
    userIds: string[],
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    const uniqueSorted = Array.from(new Set(userIds)).sort((a, b) =>
      a.localeCompare(b),
    );
    for (const uid of uniqueSorted) {
      await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${uid}::uuid FOR UPDATE`;
    }
  }

  private _normalizeRole(rawRole: string): GroupRole {
    return rawRole === GROUP_ROLES.ADMIN ? GROUP_ROLES.ADMIN : GROUP_ROLES.MEMBER;
  }

  private _formatGroupResponse(
    group: SelectedGroupRow,
    actorId: string,
    trip: LinkedTripSummary | null,
  ): GroupResponseView {
    const activeMembers = (group.members ?? []).filter(
      (m) => m.user !== null && m.user.deletedAt === null,
    );

    const formattedMembers: SafeGroupMemberView[] = activeMembers.map((m) => {
      const isTripOwner = trip !== null && trip.userId === m.userId;
      const role = isTripOwner
        ? GROUP_ROLES.ADMIN
        : this._normalizeRole(m.role);
      return {
        id: m.id,
        groupId: m.groupId,
        userId: m.userId,
        role,
        isTripOwner,
        user: toSafeBuddyPeerView(m.user!),
      };
    });

    const actorMember = formattedMembers.find((m) => m.userId === actorId);
    const myRole: GroupRole =
      actorMember?.role === GROUP_ROLES.ADMIN ||
      (trip !== null && trip.userId === actorId)
        ? GROUP_ROLES.ADMIN
        : GROUP_ROLES.MEMBER;

    return {
      id: group.id,
      name: group.name,
      description: group.description ?? null,
      tripId: group.tripId ?? null,
      tripTitle: trip?.title ?? null,
      tripOwnerId: trip?.userId ?? null,
      createdAt: group.createdAt,
      myRole,
      memberCount: formattedMembers.length,
      members: formattedMembers,
    };
  }

  private async _assertGroupAdmin(
    tx: Prisma.TransactionClient,
    groupId: string,
    actorId: string,
  ): Promise<{ group: SelectedGroupRow; trip: LinkedTripSummary | null }> {
    const group = (await tx.group.findUnique({
      where: { id: groupId },
      include: {
        members: {
          where: { user: { deletedAt: null } },
          include: { user: { select: SAFE_BUDDY_USER_SELECT } },
        },
      },
    })) as SelectedGroupRow | null;

    if (!group) {
      throw new NotFoundException('Nhóm đồng hành không tồn tại');
    }

    const activeMembers = group.members.filter(
      (m) => m.user !== null && m.user.deletedAt === null,
    );
    const actorMembership = activeMembers.find((m) => m.userId === actorId);
    if (!actorMembership) {
      throw new ForbiddenException('Bạn không phải thành viên của nhóm này');
    }

    let trip: LinkedTripSummary | null = null;
    if (group.tripId) {
      trip = await tx.trip.findFirst({
        where: { id: group.tripId, deletedAt: null },
        select: { id: true, title: true, userId: true },
      });
    }

    const isAdmin =
      actorMembership.role === GROUP_ROLES.ADMIN ||
      (trip !== null && trip.userId === actorId);
    if (!isAdmin) {
      throw new ForbiddenException(
        'Chỉ quản trị viên nhóm mới có quyền thực hiện thao tác này',
      );
    }

    return { group, trip };
  }

  /**
   * Pluggable eligibility hook for W09-A Decision #3/#4 (direct add vs invite consent / TripMember prerequisite).
   * In W09-A beta, existence + non-deleted + no two-way UserBlock are enforced in addMember.
   */
  private async _assertMemberAddEligibility(
    _tx: Prisma.TransactionClient,
    _group: SelectedGroupRow,
    _trip: LinkedTripSummary | null,
    _actorId: string,
    _targetUserId: string,
  ): Promise<void> {
    return;
  }

  async create(actorId: string, dto: CreateGroupDto): Promise<GroupResponseView> {
    return this.prisma.$transaction(async (tx) => {
      let trip: LinkedTripSummary | null = null;
      if (dto.tripId) {
        await this._lockTrip(tx, dto.tripId);
        trip = await tx.trip.findFirst({
          where: { id: dto.tripId, deletedAt: null },
          select: { id: true, title: true, userId: true },
        });
        if (!trip) {
          throw new NotFoundException('Chuyến đi không tồn tại');
        }
        if (trip.userId !== actorId) {
          throw new ForbiddenException(
            'Chỉ chủ chuyến đi mới có quyền tạo nhóm cho chuyến đi này',
          );
        }

        const existingGroup = await tx.group.findFirst({
          where: { tripId: dto.tripId },
          select: { id: true },
        });
        if (existingGroup) {
          throw new ConflictException('Chuyến đi này đã có nhóm đồng hành');
        }
      }

      const created = (await tx.group.create({
        data: {
          name: dto.name,
          description: dto.description ?? null,
          tripId: dto.tripId ?? null,
          members: {
            create: {
              userId: actorId,
              role: GROUP_ROLES.ADMIN,
            },
          },
        },
        include: {
          members: {
            where: { user: { deletedAt: null } },
            include: { user: { select: SAFE_BUDDY_USER_SELECT } },
          },
        },
      })) as SelectedGroupRow;

      return this._formatGroupResponse(created, actorId, trip);
    });
  }

  async findAll(actorId: string): Promise<GroupResponseView[]> {
    const groups = (await this.prisma.group.findMany({
      where: {
        members: {
          some: { userId: actorId },
        },
      },
      orderBy: { createdAt: 'desc' },
      include: {
        members: {
          where: { user: { deletedAt: null } },
          include: { user: { select: SAFE_BUDDY_USER_SELECT } },
        },
      },
    })) as SelectedGroupRow[];

    const tripIds = Array.from(
      new Set(
        groups
          .map((g) => g.tripId)
          .filter((id): id is string => typeof id === 'string' && id.length > 0),
      ),
    );

    const tripMap = new Map<string, LinkedTripSummary>();
    if (tripIds.length > 0) {
      const trips = await this.prisma.trip.findMany({
        where: { id: { in: tripIds }, deletedAt: null },
        select: { id: true, title: true, userId: true },
      });
      for (const t of trips) {
        tripMap.set(t.id, t);
      }
    }

    return groups.map((g) =>
      this._formatGroupResponse(
        g,
        actorId,
        g.tripId ? (tripMap.get(g.tripId) ?? null) : null,
      ),
    );
  }

  async findById(groupId: string, actorId: string): Promise<GroupResponseView> {
    const group = (await this.prisma.group.findUnique({
      where: { id: groupId },
      include: {
        members: {
          where: { user: { deletedAt: null } },
          include: { user: { select: SAFE_BUDDY_USER_SELECT } },
        },
      },
    })) as SelectedGroupRow | null;

    if (!group) {
      throw new NotFoundException('Nhóm đồng hành không tồn tại');
    }

    const actorMembership = group.members.find(
      (m) => m.userId === actorId && m.user !== null && m.user.deletedAt === null,
    );
    if (!actorMembership) {
      throw new ForbiddenException('Bạn không phải thành viên của nhóm này');
    }

    let trip: LinkedTripSummary | null = null;
    if (group.tripId) {
      trip = await this.prisma.trip.findFirst({
        where: { id: group.tripId, deletedAt: null },
        select: { id: true, title: true, userId: true },
      });
    }

    return this._formatGroupResponse(group, actorId, trip);
  }

  async update(
    groupId: string,
    actorId: string,
    dto: UpdateGroupDto,
  ): Promise<GroupResponseView> {
    if (dto.name === undefined && dto.description === undefined) {
      throw new BadRequestException('Cần ít nhất một trường để cập nhật');
    }
    if (dto.name === null) {
      throw new BadRequestException('Tên nhóm không được để trống');
    }

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const { trip } = await this._assertGroupAdmin(tx, groupId, actorId);

      const data: Prisma.GroupUpdateInput = {};
      if (dto.name !== undefined) {
        data.name = dto.name;
      }
      if (dto.description !== undefined) {
        data.description = dto.description;
      }

      const updated = (await tx.group.update({
        where: { id: groupId },
        data,
        include: {
          members: {
            where: { user: { deletedAt: null } },
            include: { user: { select: SAFE_BUDDY_USER_SELECT } },
          },
        },
      })) as SelectedGroupRow;

      return this._formatGroupResponse(updated, actorId, trip);
    });
  }

  async addMember(
    groupId: string,
    actorId: string,
    dto: AddGroupMemberDto,
  ): Promise<GroupResponseView> {
    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const { group, trip } = await this._assertGroupAdmin(tx, groupId, actorId);

      await this._lockUsersInOrder(tx, [actorId, dto.userId]);

      const targetUser = await tx.user.findUnique({
        where: { id: dto.userId },
        select: SAFE_BUDDY_USER_SELECT,
      });
      if (!targetUser || targetUser.deletedAt !== null) {
        throw new NotFoundException('Không tìm thấy người dùng');
      }

      const block = await tx.userBlock.findFirst({
        where: {
          OR: [
            { blockerId: actorId, blockedId: dto.userId },
            { blockerId: dto.userId, blockedId: actorId },
          ],
        },
        select: { id: true },
      });
      if (block) {
        throw new ForbiddenException(
          'Không thể thêm người dùng do trạng thái chặn hai chiều',
        );
      }

      const alreadyMember = group.members.some((m) => m.userId === dto.userId);
      if (alreadyMember) {
        throw new ConflictException('Người dùng đã là thành viên của nhóm');
      }

      await this._assertMemberAddEligibility(tx, group, trip, actorId, dto.userId);

      try {
        await tx.groupMember.create({
          data: {
            groupId,
            userId: dto.userId,
            role: GROUP_ROLES.MEMBER,
          },
        });
      } catch (error) {
        if (
          error instanceof Prisma.PrismaClientKnownRequestError &&
          error.code === 'P2002'
        ) {
          throw new ConflictException('Người dùng đã là thành viên của nhóm');
        }
        throw error;
      }

      if (
        group.tripId &&
        typeof (tx.itineraryVote as { deleteMany?: unknown } | undefined)
          ?.deleteMany === 'function'
      ) {
        await tx.itineraryVote.deleteMany({
          where: {
            userId: dto.userId,
            item: { itinerary: { tripId: group.tripId } },
          },
        });
      }

      const refreshed = (await tx.group.findUnique({
        where: { id: groupId },
        include: {
          members: {
            where: { user: { deletedAt: null } },
            include: { user: { select: SAFE_BUDDY_USER_SELECT } },
          },
        },
      })) as SelectedGroupRow | null;

      if (!refreshed) {
        throw new NotFoundException('Nhóm đồng hành không tồn tại');
      }

      return this._formatGroupResponse(refreshed, actorId, trip);
    });
  }

  async removeMember(
    groupId: string,
    actorId: string,
    targetUserId: string,
  ): Promise<{ removed: boolean; groupId: string; userId: string }> {
    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const { group, trip } = await this._assertGroupAdmin(tx, groupId, actorId);

      // Include soft-deleted users in membership lookup so admin can clean up a deleted
      // account's GroupMember row AFTER its ledger balance reaches 0 VND.
      const allGroupMembers =
        typeof (tx.groupMember as { findMany?: unknown } | undefined)?.findMany ===
        'function'
          ? await tx.groupMember.findMany({ where: { groupId } })
          : group.members;
      const targetNorm = normalizeUuid(targetUserId);
      const targetMember = allGroupMembers.find(
        (m) => normalizeUuid(m.userId) === targetNorm,
      );
      if (!targetMember) {
        throw new NotFoundException('Thành viên không tồn tại trong nhóm');
      }

      if (trip !== null && normalizeUuid(trip.userId) === targetNorm) {
        throw new ConflictException(
          'Không thể xóa chủ chuyến đi khỏi nhóm đồng hành',
        );
      }

      const activeMembers = group.members.filter(
        (m) => m.user !== null && m.user.deletedAt === null,
      );
      const adminCount = activeMembers.filter(
        (m) =>
          m.role === GROUP_ROLES.ADMIN ||
          (trip !== null && normalizeUuid(trip.userId) === normalizeUuid(m.userId)),
      ).length;
      const targetIsActive = activeMembers.some(
        (m) => normalizeUuid(m.userId) === targetNorm,
      );
      const targetIsAdmin =
        targetIsActive &&
        (targetMember.role === GROUP_ROLES.ADMIN ||
          (trip !== null && normalizeUuid(trip.userId) === targetNorm));

      if (targetIsAdmin && adminCount <= 1) {
        throw new ConflictException(
          'Không thể xóa quản trị viên duy nhất của nhóm',
        );
      }

      if (this.groupExpensesService) {
        const netBalance =
          await this.groupExpensesService.getMemberNetBalanceInTx(
            tx,
            groupId,
            targetUserId,
          );
        if (netBalance !== 0n) {
          throw new ConflictException({
            errorCode: GROUP_ERROR_CODES.MEMBER_HAS_UNSETTLED_BALANCE,
            message:
              'Không thể xóa thành viên khi vẫn còn công nợ chưa quyết toán trong nhóm',
          });
        }
      }

      if (
        group.tripId &&
        typeof (tx.itineraryVote as { deleteMany?: unknown } | undefined)
          ?.deleteMany === 'function'
      ) {
        await tx.itineraryVote.deleteMany({
          where: {
            userId: targetMember.userId,
            item: { itinerary: { tripId: group.tripId } },
          },
        });
      }

      await tx.groupMember.delete({
        where: { id: targetMember.id },
      });

      return {
        removed: true,
        groupId,
        userId: targetUserId,
      };
    });
  }
}
