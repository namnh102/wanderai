import { Injectable, NotFoundException } from '@nestjs/common';
import { NotificationType, TripInviteStatus } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';

export interface NotificationItemView {
  id: string;
  userId: string;
  type: NotificationType;
  title: string;
  body: string | null;
  isRead: boolean;
  createdAt: Date;
  data: Record<string, unknown> | null;
  tripInvite?: {
    inviteId: string;
    tripId: string;
    tripTitle: string;
    destinationName: string | null;
    inviterId: string;
    inviterDisplayName: string;
    status: TripInviteStatus;
    respondedAt: Date | null;
    revokedAt: Date | null;
  } | null;
}

export interface NotificationsListResponse {
  items: NotificationItemView[];
  unreadCount: number;
}

@Injectable()
export class NotificationsService {
  constructor(private readonly prisma: PrismaService) {}

  private _asObject(val: unknown): Record<string, unknown> | null {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      return val as Record<string, unknown>;
    }
    return null;
  }

  private _displayNameOf(user: {
    email: string;
    profile: { displayName: string } | null;
  }): string {
    const raw = user.profile?.displayName?.trim();
    if (raw && raw.length > 0) return raw;
    const prefix = user.email.split('@')[0]?.trim();
    return prefix && prefix.length > 0 ? prefix : 'Người dùng GoMate';
  }

  async listForUser(
    userId: string,
    limit = 50,
  ): Promise<NotificationsListResponse> {
    const safeLimit = Math.min(Math.max(1, Math.trunc(limit)), 100);

    const [rows, unreadCount] = await Promise.all([
      this.prisma.notification.findMany({
        where: { userId },
        orderBy: { createdAt: 'desc' },
        take: safeLimit,
        include: {
          tripInvite: {
            include: {
              trip: {
                select: {
                  id: true,
                  title: true,
                  deletedAt: true,
                  destination: { select: { name: true } },
                },
              },
              inviter: {
                select: {
                  id: true,
                  email: true,
                  profile: { select: { displayName: true } },
                },
              },
            },
          },
        },
      }),
      this.prisma.notification.count({
        where: { userId, isRead: false },
      }),
    ]);

    const items: NotificationItemView[] = rows.map((row) => {
      const rawData = this._asObject(row.data);
      let tripInviteMeta: NotificationItemView['tripInvite'] = null;

      if (row.type === NotificationType.TRIP_INVITE) {
        if (row.tripInvite) {
          tripInviteMeta = {
            inviteId: row.tripInvite.id,
            tripId: row.tripInvite.tripId,
            tripTitle:
              row.tripInvite.trip?.title ??
              (typeof rawData?.tripTitle === 'string'
                ? rawData.tripTitle
                : 'Chuyến đi'),
            destinationName:
              row.tripInvite.trip?.destination?.name ??
              (typeof rawData?.destinationName === 'string'
                ? rawData.destinationName
                : null),
            inviterId: row.tripInvite.inviterId,
            inviterDisplayName: row.tripInvite.inviter
              ? this._displayNameOf(row.tripInvite.inviter)
              : typeof rawData?.inviterDisplayName === 'string'
                ? rawData.inviterDisplayName
                : 'Người dùng GoMate',
            status: row.tripInvite.status,
            respondedAt: row.tripInvite.respondedAt ?? null,
            revokedAt: row.tripInvite.revokedAt ?? null,
          };
        } else if (
          rawData &&
          typeof rawData.inviteId === 'string' &&
          typeof rawData.tripId === 'string'
        ) {
          const rawStatus =
            typeof rawData.status === 'string' ? rawData.status : 'PENDING';
          const normalizedStatus: TripInviteStatus =
            rawStatus === 'ACCEPTED' ||
            rawStatus === 'DECLINED' ||
            rawStatus === 'REVOKED'
              ? (rawStatus as TripInviteStatus)
              : TripInviteStatus.PENDING;
          tripInviteMeta = {
            inviteId: rawData.inviteId,
            tripId: rawData.tripId,
            tripTitle:
              typeof rawData.tripTitle === 'string'
                ? rawData.tripTitle
                : 'Chuyến đi',
            destinationName:
              typeof rawData.destinationName === 'string'
                ? rawData.destinationName
                : null,
            inviterId:
              typeof rawData.inviterId === 'string' ? rawData.inviterId : '',
            inviterDisplayName:
              typeof rawData.inviterDisplayName === 'string'
                ? rawData.inviterDisplayName
                : 'Người dùng GoMate',
            status: normalizedStatus,
            respondedAt: null,
            revokedAt: null,
          };
        }
      }

      return {
        id: row.id,
        userId: row.userId,
        type: row.type,
        title: row.title,
        body: row.body ?? null,
        isRead: row.isRead,
        createdAt: row.createdAt,
        data: rawData,
        ...(tripInviteMeta ? { tripInvite: tripInviteMeta } : {}),
      };
    });

    return { items, unreadCount };
  }

  async getUnreadCount(userId: string): Promise<{ unreadCount: number }> {
    const unreadCount = await this.prisma.notification.count({
      where: { userId, isRead: false },
    });
    return { unreadCount };
  }

  async markRead(
    notificationId: string,
    userId: string,
  ): Promise<{ id: string; isRead: boolean; unreadCount: number }> {
    const existing = await this.prisma.notification.findFirst({
      where: { id: notificationId, userId },
      select: { id: true, isRead: true },
    });
    if (!existing) {
      throw new NotFoundException('Không tìm thấy thông báo');
    }

    if (!existing.isRead) {
      await this.prisma.notification.update({
        where: { id: notificationId },
        data: { isRead: true },
      });
    }

    const unreadCount = await this.prisma.notification.count({
      where: { userId, isRead: false },
    });

    return {
      id: notificationId,
      isRead: true,
      unreadCount,
    };
  }

  async markAllRead(userId: string): Promise<{ unreadCount: number }> {
    await this.prisma.notification.updateMany({
      where: { userId, isRead: false },
      data: { isRead: true },
    });
    return { unreadCount: 0 };
  }
}
