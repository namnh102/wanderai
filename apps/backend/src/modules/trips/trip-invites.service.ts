import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import {
  NotificationType,
  Prisma,
  TripInviteStatus,
  TripStatus,
} from '@prisma/client';
import { randomUUID } from 'crypto';
import { PrismaService } from '../../prisma/prisma.service';

export interface TripInviteUserSummary {
  id: string;
  email?: string;
  displayName: string;
  avatar: string | null;
}

export interface TripInviteView {
  id: string;
  tripId: string;
  tripTitle: string;
  tripDescription: string | null;
  destinationName: string | null;
  startDate: Date | null;
  endDate: Date | null;
  status: TripInviteStatus;
  notificationId: string | null;
  inviter: TripInviteUserSummary;
  invitee: TripInviteUserSummary;
  createdAt: Date;
  respondedAt: Date | null;
  revokedAt: Date | null;
  idempotentDuplicate?: boolean;
}

export interface AcceptTripInviteResult {
  invite: TripInviteView;
  tripId: string;
}

interface SelectedInviteRow {
  id: string;
  tripId: string;
  inviterId: string;
  inviteeId: string;
  notificationId: string | null;
  status: TripInviteStatus;
  respondedAt: Date | null;
  revokedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
  trip: {
    id: string;
    title: string;
    description: string | null;
    startDate: Date | null;
    endDate: Date | null;
    status: TripStatus;
    deletedAt: Date | null;
    destination: { name: string } | null;
  };
  inviter: {
    id: string;
    email: string;
    profile: { displayName: string; avatar: string | null } | null;
  };
  invitee: {
    id: string;
    email: string;
    profile: { displayName: string; avatar: string | null } | null;
  };
}

const INVITE_INCLUDE = {
  trip: {
    select: {
      id: true,
      title: true,
      description: true,
      startDate: true,
      endDate: true,
      status: true,
      deletedAt: true,
      destination: { select: { name: true } },
    },
  },
  inviter: {
    select: {
      id: true,
      email: true,
      profile: { select: { displayName: true, avatar: true } },
    },
  },
  invitee: {
    select: {
      id: true,
      email: true,
      profile: { select: { displayName: true, avatar: true } },
    },
  },
} as const;

@Injectable()
export class TripInvitesService {
  constructor(private readonly prisma: PrismaService) {}

  private async _lockTripIfSupported(
    tx: Prisma.TransactionClient,
    tripId: string,
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    await tx.$queryRaw`SELECT id FROM "trips" WHERE id = ${tripId}::uuid FOR UPDATE`;
  }

  private _displayNameOf(user: {
    email: string;
    profile: { displayName: string; avatar: string | null } | null;
  }): string {
    const raw = user.profile?.displayName?.trim();
    if (raw && raw.length > 0) {
      return raw;
    }
    const prefix = user.email.split('@')[0]?.trim();
    return prefix && prefix.length > 0 ? prefix : 'Người dùng GoMate';
  }

  private _toInviteView(
    row: SelectedInviteRow,
    opts?: { includeInviteeEmail?: boolean; idempotentDuplicate?: boolean },
  ): TripInviteView {
    return {
      id: row.id,
      tripId: row.tripId,
      tripTitle: row.trip.title,
      tripDescription: row.trip.description ?? null,
      destinationName: row.trip.destination?.name ?? null,
      startDate: row.trip.startDate ?? null,
      endDate: row.trip.endDate ?? null,
      status: row.status,
      notificationId: row.notificationId ?? null,
      inviter: {
        id: row.inviter.id,
        displayName: this._displayNameOf(row.inviter),
        avatar: row.inviter.profile?.avatar ?? null,
      },
      invitee: {
        id: row.invitee.id,
        ...(opts?.includeInviteeEmail ? { email: row.invitee.email } : {}),
        displayName: this._displayNameOf(row.invitee),
        avatar: row.invitee.profile?.avatar ?? null,
      },
      createdAt: row.createdAt,
      respondedAt: row.respondedAt ?? null,
      revokedAt: row.revokedAt ?? null,
      ...(opts?.idempotentDuplicate !== undefined
        ? { idempotentDuplicate: opts.idempotentDuplicate }
        : {}),
    };
  }

  private _buildNotificationPayload(params: {
    inviteId: string;
    tripId: string;
    tripTitle: string;
    destinationName: string | null;
    inviterId: string;
    inviterDisplayName: string;
    status: TripInviteStatus;
    respondedAt?: Date | null;
    revokedAt?: Date | null;
  }): Prisma.InputJsonObject {
    return {
      inviteId: params.inviteId,
      tripId: params.tripId,
      tripTitle: params.tripTitle,
      destinationName: params.destinationName,
      inviterId: params.inviterId,
      inviterDisplayName: params.inviterDisplayName,
      status: params.status,
      ...(params.respondedAt
        ? { respondedAt: params.respondedAt.toISOString() }
        : {}),
      ...(params.revokedAt
        ? { revokedAt: params.revokedAt.toISOString() }
        : {}),
    };
  }

  async createInvite(
    tripId: string,
    actorId: string,
    rawEmail: string,
  ): Promise<TripInviteView> {
    const normalizedEmail = rawEmail.trim().toLowerCase();
    if (!normalizedEmail) {
      throw new BadRequestException('Email người nhận không được để trống');
    }

    return this.prisma.$transaction(async (tx) => {
      await this._lockTripIfSupported(tx, tripId);

      const trip = await tx.trip.findFirst({
        where: { id: tripId, deletedAt: null },
        include: {
          destination: { select: { name: true } },
          user: {
            select: {
              id: true,
              email: true,
              profile: { select: { displayName: true, avatar: true } },
            },
          },
        },
      });
      if (!trip) {
        throw new NotFoundException('Chuyến đi không tồn tại');
      }
      if (trip.userId !== actorId) {
        throw new ForbiddenException(
          'Chỉ chủ chuyến đi mới có quyền gửi lời mời',
        );
      }
      if (trip.status === TripStatus.CANCELLED) {
        throw new BadRequestException(
          'Chuyến đi đã hủy không thể mời thêm thành viên',
        );
      }

      const invitee = await tx.user.findUnique({
        where: { email: normalizedEmail },
        select: {
          id: true,
          email: true,
          deletedAt: true,
          profile: { select: { displayName: true, avatar: true } },
        },
      });
      if (!invitee || invitee.deletedAt !== null) {
        throw new NotFoundException(`Không tìm thấy người dùng: ${normalizedEmail}`);
      }
      if (invitee.id === actorId) {
        throw new BadRequestException('Không thể tự mời chính mình vào chuyến đi');
      }

      const block = await tx.userBlock.findFirst({
        where: {
          OR: [
            { blockerId: actorId, blockedId: invitee.id },
            { blockerId: invitee.id, blockedId: actorId },
          ],
        },
        select: { id: true },
      });
      if (block) {
        throw new ForbiddenException(
          'Không thể gửi lời mời do trạng thái chặn hai chiều',
        );
      }

      const existingMember = await tx.tripMember.findUnique({
        where: {
          tripId_userId: {
            tripId,
            userId: invitee.id,
          },
        },
        select: { id: true },
      });
      if (existingMember) {
        throw new ConflictException({
          message: 'Người dùng này đã là thành viên của chuyến đi',
          errorCode: 'TRIP_ALREADY_MEMBER',
        });
      }

      const existingPending = (await tx.tripInvite.findFirst({
        where: {
          tripId,
          inviteeId: invitee.id,
          status: TripInviteStatus.PENDING,
        },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow | null;

      if (existingPending) {
        return this._toInviteView(existingPending, {
          includeInviteeEmail: true,
          idempotentDuplicate: true,
        });
      }

      const inviteId = randomUUID();
      const inviterDisplayName = this._displayNameOf(trip.user);
      const destinationName = trip.destination?.name ?? null;

      const notif = await tx.notification.create({
        data: {
          userId: invitee.id,
          type: NotificationType.TRIP_INVITE,
          title: 'Lời mời tham gia chuyến đi',
          body: `${inviterDisplayName} mời bạn tham gia chuyến "${trip.title}".`,
          isRead: false,
          data: this._buildNotificationPayload({
            inviteId,
            tripId: trip.id,
            tripTitle: trip.title,
            destinationName,
            inviterId: actorId,
            inviterDisplayName,
            status: TripInviteStatus.PENDING,
          }),
        },
      });

      const created = (await tx.tripInvite.create({
        data: {
          id: inviteId,
          tripId: trip.id,
          inviterId: actorId,
          inviteeId: invitee.id,
          notificationId: notif.id,
          status: TripInviteStatus.PENDING,
        },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow;

      return this._toInviteView(created, {
        includeInviteeEmail: true,
        idempotentDuplicate: false,
      });
    });
  }

  async listTripInvites(
    tripId: string,
    actorId: string,
  ): Promise<TripInviteView[]> {
    const trip = await this.prisma.trip.findFirst({
      where: { id: tripId, deletedAt: null },
      select: { id: true, userId: true },
    });
    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }
    if (trip.userId !== actorId) {
      throw new ForbiddenException(
        'Chỉ chủ chuyến đi mới có quyền xem danh sách lời mời',
      );
    }

    const rows = (await this.prisma.tripInvite.findMany({
      where: { tripId },
      orderBy: { createdAt: 'desc' },
      include: INVITE_INCLUDE,
    })) as SelectedInviteRow[];

    return rows.map((r) =>
      this._toInviteView(r, { includeInviteeEmail: true }),
    );
  }

  async getInviteById(
    inviteId: string,
    actorId: string,
  ): Promise<TripInviteView> {
    const row = (await this.prisma.tripInvite.findUnique({
      where: { id: inviteId },
      include: INVITE_INCLUDE,
    })) as SelectedInviteRow | null;

    if (!row || row.trip.deletedAt !== null) {
      throw new NotFoundException('Không tìm thấy lời mời tham gia chuyến đi');
    }

    if (row.inviterId !== actorId && row.inviteeId !== actorId) {
      throw new ForbiddenException('Bạn không có quyền xem lời mời này');
    }

    return this._toInviteView(row, {
      includeInviteeEmail: row.inviterId === actorId,
    });
  }

  async revokeInvite(
    inviteId: string,
    actorId: string,
    expectedTripId?: string,
  ): Promise<TripInviteView> {
    return this.prisma.$transaction(async (tx) => {
      const existing = (await tx.tripInvite.findUnique({
        where: { id: inviteId },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow | null;

      if (!existing || existing.trip.deletedAt !== null) {
        throw new NotFoundException('Không tìm thấy lời mời tham gia chuyến đi');
      }
      if (expectedTripId && existing.tripId !== expectedTripId) {
        throw new NotFoundException('Lời mời không thuộc chuyến đi này');
      }

      await this._lockTripIfSupported(tx, existing.tripId);

      if (existing.inviterId !== actorId) {
        throw new ForbiddenException(
          'Chỉ chủ chuyến đi mới có quyền thu hồi lời mời',
        );
      }

      if (existing.status === TripInviteStatus.REVOKED) {
        return this._toInviteView(existing, { includeInviteeEmail: true });
      }
      if (existing.status !== TripInviteStatus.PENDING) {
        throw new ConflictException({
          message: 'Chỉ có thể thu hồi lời mời đang ở trạng thái chờ phản hồi',
          errorCode: 'TRIP_INVITE_NOT_PENDING',
        });
      }

      const now = new Date();
      const updated = (await tx.tripInvite.update({
        where: { id: inviteId },
        data: {
          status: TripInviteStatus.REVOKED,
          revokedAt: now,
        },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow;

      if (updated.notificationId) {
        await tx.notification.update({
          where: { id: updated.notificationId },
          data: {
            data: this._buildNotificationPayload({
              inviteId: updated.id,
              tripId: updated.tripId,
              tripTitle: updated.trip.title,
              destinationName: updated.trip.destination?.name ?? null,
              inviterId: updated.inviterId,
              inviterDisplayName: this._displayNameOf(updated.inviter),
              status: TripInviteStatus.REVOKED,
              revokedAt: now,
            }),
          },
        });
      }

      return this._toInviteView(updated, { includeInviteeEmail: true });
    });
  }

  async acceptInvite(
    inviteId: string,
    actorId: string,
  ): Promise<AcceptTripInviteResult> {
    return this.prisma.$transaction(async (tx) => {
      const existing = (await tx.tripInvite.findUnique({
        where: { id: inviteId },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow | null;

      if (!existing || existing.trip.deletedAt !== null) {
        throw new NotFoundException('Không tìm thấy lời mời hoặc chuyến đi đã bị xóa');
      }

      await this._lockTripIfSupported(tx, existing.tripId);

      if (existing.inviteeId !== actorId) {
        throw new ForbiddenException(
          'Chỉ người được mời mới có quyền chấp nhận lời mời này',
        );
      }

      const block = await tx.userBlock.findFirst({
        where: {
          OR: [
            { blockerId: existing.inviterId, blockedId: actorId },
            { blockerId: actorId, blockedId: existing.inviterId },
          ],
        },
        select: { id: true },
      });
      if (block) {
        throw new ForbiddenException(
          'Không thể tham gia chuyến đi do trạng thái chặn hai chiều',
        );
      }

      if (existing.status === TripInviteStatus.REVOKED) {
        throw new ConflictException({
          message: 'Lời mời tham gia chuyến đi này đã được thu hồi',
          errorCode: 'TRIP_INVITE_REVOKED',
        });
      }
      if (existing.status === TripInviteStatus.DECLINED) {
        throw new ConflictException({
          message: 'Lời mời tham gia chuyến đi này đã bị từ chối',
          errorCode: 'TRIP_INVITE_DECLINED',
        });
      }

      await tx.tripMember.upsert({
        where: {
          tripId_userId: {
            tripId: existing.tripId,
            userId: actorId,
          },
        },
        update: {},
        create: {
          tripId: existing.tripId,
          userId: actorId,
          role: 'member',
        },
      });

      if (existing.status === TripInviteStatus.ACCEPTED) {
        if (existing.notificationId) {
          await tx.notification.update({
            where: { id: existing.notificationId },
            data: { isRead: true },
          });
        }
        return {
          invite: this._toInviteView(existing),
          tripId: existing.tripId,
        };
      }

      const now = new Date();
      const updated = (await tx.tripInvite.update({
        where: { id: inviteId },
        data: {
          status: TripInviteStatus.ACCEPTED,
          respondedAt: now,
        },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow;

      if (updated.notificationId) {
        await tx.notification.update({
          where: { id: updated.notificationId },
          data: {
            isRead: true,
            data: this._buildNotificationPayload({
              inviteId: updated.id,
              tripId: updated.tripId,
              tripTitle: updated.trip.title,
              destinationName: updated.trip.destination?.name ?? null,
              inviterId: updated.inviterId,
              inviterDisplayName: this._displayNameOf(updated.inviter),
              status: TripInviteStatus.ACCEPTED,
              respondedAt: now,
            }),
          },
        });
      }

      return {
        invite: this._toInviteView(updated),
        tripId: updated.tripId,
      };
    });
  }

  async declineInvite(
    inviteId: string,
    actorId: string,
  ): Promise<TripInviteView> {
    return this.prisma.$transaction(async (tx) => {
      const existing = (await tx.tripInvite.findUnique({
        where: { id: inviteId },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow | null;

      if (!existing || existing.trip.deletedAt !== null) {
        throw new NotFoundException('Không tìm thấy lời mời tham gia chuyến đi');
      }

      await this._lockTripIfSupported(tx, existing.tripId);

      if (existing.inviteeId !== actorId) {
        throw new ForbiddenException(
          'Chỉ người được mời mới có quyền từ chối lời mời này',
        );
      }

      if (existing.status === TripInviteStatus.REVOKED) {
        throw new ConflictException({
          message: 'Lời mời tham gia chuyến đi này đã được thu hồi',
          errorCode: 'TRIP_INVITE_REVOKED',
        });
      }
      if (existing.status === TripInviteStatus.ACCEPTED) {
        throw new ConflictException({
          message: 'Lời mời này đã được chấp nhận trước đó',
          errorCode: 'TRIP_INVITE_ALREADY_ACCEPTED',
        });
      }
      if (existing.status === TripInviteStatus.DECLINED) {
        return this._toInviteView(existing);
      }

      const now = new Date();
      const updated = (await tx.tripInvite.update({
        where: { id: inviteId },
        data: {
          status: TripInviteStatus.DECLINED,
          respondedAt: now,
        },
        include: INVITE_INCLUDE,
      })) as SelectedInviteRow;

      if (updated.notificationId) {
        await tx.notification.update({
          where: { id: updated.notificationId },
          data: {
            isRead: true,
            data: this._buildNotificationPayload({
              inviteId: updated.id,
              tripId: updated.tripId,
              tripTitle: updated.trip.title,
              destinationName: updated.trip.destination?.name ?? null,
              inviterId: updated.inviterId,
              inviterDisplayName: this._displayNameOf(updated.inviter),
              status: TripInviteStatus.DECLINED,
              respondedAt: now,
            }),
          },
        });
      }

      return this._toInviteView(updated);
    });
  }
}
