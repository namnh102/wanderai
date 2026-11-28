import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  NotFoundException,
} from '@nestjs/common';
import {
  NotificationType,
  TripInviteStatus,
  TripStatus,
} from '@prisma/client';
import { randomUUID } from 'crypto';
import { PrismaService } from '../../prisma/prisma.service';
import { NotificationsService } from '../notifications/notifications.service';
import { TripInvitesService } from './trip-invites.service';

interface MemNotification {
  id: string;
  userId: string;
  type: NotificationType;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  isRead: boolean;
  createdAt: Date;
}

interface MemInvite {
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
}

describe('TripInvitesService & NotificationsService (unit)', () => {
  const ownerId = '11111111-1111-4111-8111-111111111111';
  const userBId = '22222222-2222-4222-8222-222222222222';
  const userCId = '33333333-3333-4333-8333-333333333333';
  const tripId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

  let notifications: Map<string, MemNotification>;
  let invites: Map<string, MemInvite>;
  let tripMembers: Set<string>;
  let blockedPairs: Array<{ blockerId: string; blockedId: string }>;
  let tripInvitesService: TripInvitesService;
  let notificationsService: NotificationsService;

  const usersById = new Map([
    [
      ownerId,
      {
        id: ownerId,
        email: 'owner.a@wanderai.test',
        deletedAt: null as Date | null,
        profile: { displayName: 'Chủ chuyến A', avatar: null },
      },
    ],
    [
      userBId,
      {
        id: userBId,
        email: 'member.b@wanderai.test',
        deletedAt: null as Date | null,
        profile: { displayName: 'Thành viên B', avatar: null },
      },
    ],
    [
      userCId,
      {
        id: userCId,
        email: 'outsider.c@wanderai.test',
        deletedAt: null as Date | null,
        profile: { displayName: 'Người ngoài C', avatar: null },
      },
    ],
  ]);

  const tripRecord = {
    id: tripId,
    userId: ownerId,
    title: 'Chuyến Hạ Long Cuối Tuần',
    description: 'Khám phá Vịnh Hạ Long',
    startDate: new Date('2026-12-10'),
    endDate: new Date('2026-12-12'),
    status: TripStatus.PLANNED,
    deletedAt: null as Date | null,
    destination: { name: 'Hạ Long' },
    user: usersById.get(ownerId)!,
  };

  function hydrateInvite(inv: MemInvite) {
    return {
      ...inv,
      trip: tripRecord,
      inviter: usersById.get(inv.inviterId)!,
      invitee: usersById.get(inv.inviteeId)!,
    };
  }

  beforeEach(() => {
    notifications = new Map();
    invites = new Map();
    tripMembers = new Set([`${tripId}:${ownerId}`]);
    blockedPairs = [];

    const prismaStub: Record<string, unknown> = {
      $transaction: async (fn: (tx: unknown) => Promise<unknown>) =>
        fn(prismaStub),
      trip: {
        findFirst: jest.fn(async ({ where }: { where: { id: string } }) =>
          where.id === tripId && tripRecord.deletedAt === null
            ? tripRecord
            : null,
        ),
      },
      user: {
        findUnique: jest.fn(async ({ where }: { where: { email?: string } }) => {
          for (const u of usersById.values()) {
            if (u.email === where.email) return u;
          }
          return null;
        }),
      },
      userBlock: {
        findFirst: jest.fn(async () =>
          blockedPairs.length > 0 ? { id: 'blk-1' } : null,
        ),
      },
      tripMember: {
        findUnique: jest.fn(
          async ({
            where,
          }: {
            where: { tripId_userId: { tripId: string; userId: string } };
          }) => {
            const key = `${where.tripId_userId.tripId}:${where.tripId_userId.userId}`;
            return tripMembers.has(key) ? { id: key } : null;
          },
        ),
        upsert: jest.fn(
          async ({
            where,
          }: {
            where: { tripId_userId: { tripId: string; userId: string } };
          }) => {
            const key = `${where.tripId_userId.tripId}:${where.tripId_userId.userId}`;
            tripMembers.add(key);
            return { id: key };
          },
        ),
      },
      notification: {
        create: jest.fn(async ({ data }: { data: Record<string, unknown> }) => {
          const id = randomUUID();
          const row: MemNotification = {
            id,
            userId: data.userId as string,
            type: data.type as NotificationType,
            title: data.title as string,
            body: (data.body as string | undefined) ?? null,
            data: (data.data as Record<string, unknown> | undefined) ?? null,
            isRead: (data.isRead as boolean | undefined) ?? false,
            createdAt: new Date(),
          };
          notifications.set(id, row);
          return row;
        }),
        update: jest.fn(
          async ({
            where,
            data,
          }: {
            where: { id: string };
            data: Record<string, unknown>;
          }) => {
            const existing = notifications.get(where.id);
            if (!existing) throw new Error('Notification missing');
            const next: MemNotification = {
              ...existing,
              ...(data.isRead !== undefined
                ? { isRead: data.isRead as boolean }
                : {}),
              ...(data.data !== undefined
                ? { data: data.data as Record<string, unknown> }
                : {}),
            };
            notifications.set(where.id, next);
            return next;
          },
        ),
        updateMany: jest.fn(
          async ({
            where,
            data,
          }: {
            where: { userId: string; isRead?: boolean };
            data: { isRead: boolean };
          }) => {
            for (const [id, n] of notifications.entries()) {
              if (
                n.userId === where.userId &&
                (where.isRead === undefined || n.isRead === where.isRead)
              ) {
                notifications.set(id, { ...n, isRead: data.isRead });
              }
            }
            return { count: 1 };
          },
        ),
        findFirst: jest.fn(
          async ({ where }: { where: { id: string; userId: string } }) => {
            const n = notifications.get(where.id);
            return n && n.userId === where.userId ? n : null;
          },
        ),
        findMany: jest.fn(
          async ({ where }: { where: { userId: string } }) => {
            const list = Array.from(notifications.values())
              .filter((n) => n.userId === where.userId)
              .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
            return list.map((n) => {
              const linked = Array.from(invites.values()).find(
                (i) => i.notificationId === n.id,
              );
              return {
                ...n,
                tripInvite: linked ? hydrateInvite(linked) : null,
              };
            });
          },
        ),
        count: jest.fn(
          async ({
            where,
          }: {
            where: { userId: string; isRead?: boolean };
          }) => {
            return Array.from(notifications.values()).filter(
              (n) =>
                n.userId === where.userId &&
                (where.isRead === undefined || n.isRead === where.isRead),
            ).length;
          },
        ),
      },
      tripInvite: {
        findFirst: jest.fn(
          async ({
            where,
          }: {
            where: {
              tripId: string;
              inviteeId: string;
              status: TripInviteStatus;
            };
          }) => {
            const found = Array.from(invites.values()).find(
              (i) =>
                i.tripId === where.tripId &&
                i.inviteeId === where.inviteeId &&
                i.status === where.status,
            );
            return found ? hydrateInvite(found) : null;
          },
        ),
        findUnique: jest.fn(async ({ where }: { where: { id: string } }) => {
          const found = invites.get(where.id);
          return found ? hydrateInvite(found) : null;
        }),
        findMany: jest.fn(
          async ({ where }: { where: { tripId: string } }) => {
            return Array.from(invites.values())
              .filter((i) => i.tripId === where.tripId)
              .map(hydrateInvite);
          },
        ),
        create: jest.fn(async ({ data }: { data: Record<string, unknown> }) => {
          const id = (data.id as string) ?? randomUUID();
          const now = new Date();
          const row: MemInvite = {
            id,
            tripId: data.tripId as string,
            inviterId: data.inviterId as string,
            inviteeId: data.inviteeId as string,
            notificationId: (data.notificationId as string | undefined) ?? null,
            status: data.status as TripInviteStatus,
            respondedAt: null,
            revokedAt: null,
            createdAt: now,
            updatedAt: now,
          };
          invites.set(id, row);
          return hydrateInvite(row);
        }),
        update: jest.fn(
          async ({
            where,
            data,
          }: {
            where: { id: string };
            data: Record<string, unknown>;
          }) => {
            const existing = invites.get(where.id);
            if (!existing) throw new Error('Invite missing');
            const next: MemInvite = {
              ...existing,
              ...(data.status !== undefined
                ? { status: data.status as TripInviteStatus }
                : {}),
              ...(data.respondedAt !== undefined
                ? { respondedAt: data.respondedAt as Date }
                : {}),
              ...(data.revokedAt !== undefined
                ? { revokedAt: data.revokedAt as Date }
                : {}),
              updatedAt: new Date(),
            };
            invites.set(where.id, next);
            return hydrateInvite(next);
          },
        ),
      },
    };

    tripInvitesService = new TripInvitesService(
      prismaStub as unknown as PrismaService,
    );
    notificationsService = new NotificationsService(
      prismaStub as unknown as PrismaService,
    );
  });

  it('creates exactly 1 TRIP_INVITE notification, prevents duplicate pending invites, and accepts into TripMember', async () => {
    const first = await tripInvitesService.createInvite(
      tripId,
      ownerId,
      '  Member.B@WanderAI.Test ',
    );
    expect(first.status).toBe(TripInviteStatus.PENDING);
    expect(first.idempotentDuplicate).toBe(false);

    // Duplicate send while PENDING -> returns exact same invite, zero duplicate notifications
    const duplicate = await tripInvitesService.createInvite(
      tripId,
      ownerId,
      'member.b@wanderai.test',
    );
    expect(duplicate.id).toBe(first.id);
    expect(duplicate.idempotentDuplicate).toBe(true);
    expect(invites.size).toBe(1);
    expect(notifications.size).toBe(1);

    // B reads notifications -> 1 unread TRIP_INVITE
    const listBefore = await notificationsService.listForUser(userBId);
    expect(listBefore.unreadCount).toBe(1);
    expect(listBefore.items).toHaveLength(1);
    expect(listBefore.items[0].type).toBe(NotificationType.TRIP_INVITE);
    expect(listBefore.items[0].tripInvite?.inviteId).toBe(first.id);
    expect(listBefore.items[0].tripInvite?.status).toBe(
      TripInviteStatus.PENDING,
    );

    // Outsider C cannot view or accept B's invite
    await expect(
      tripInvitesService.getInviteById(first.id, userCId),
    ).rejects.toBeInstanceOf(ForbiddenException);
    await expect(
      tripInvitesService.acceptInvite(first.id, userCId),
    ).rejects.toBeInstanceOf(ForbiddenException);

    // B accepts -> added to TripMember, notification marked read (unreadCount -> 0), status -> ACCEPTED
    const accepted = await tripInvitesService.acceptInvite(first.id, userBId);
    expect(accepted.tripId).toBe(tripId);
    expect(accepted.invite.status).toBe(TripInviteStatus.ACCEPTED);
    expect(tripMembers.has(`${tripId}:${userBId}`)).toBe(true);

    const listAfter = await notificationsService.listForUser(userBId);
    expect(listAfter.unreadCount).toBe(0);
    expect(listAfter.items[0].isRead).toBe(true);
    expect(listAfter.items[0].tripInvite?.status).toBe(
      TripInviteStatus.ACCEPTED,
    );
  });

  it('revokes pending invite, exposes REVOKED status on notifications/detail, and blocks acceptance with 409', async () => {
    const inv = await tripInvitesService.createInvite(
      tripId,
      ownerId,
      'member.b@wanderai.test',
    );

    const revoked = await tripInvitesService.revokeInvite(
      inv.id,
      ownerId,
      tripId,
    );
    expect(revoked.status).toBe(TripInviteStatus.REVOKED);
    expect(revoked.revokedAt).not.toBeNull();

    const bNotifs = await notificationsService.listForUser(userBId);
    expect(bNotifs.items[0].tripInvite?.status).toBe(TripInviteStatus.REVOKED);

    const detail = await tripInvitesService.getInviteById(inv.id, userBId);
    expect(detail.status).toBe(TripInviteStatus.REVOKED);

    await expect(
      tripInvitesService.acceptInvite(inv.id, userBId),
    ).rejects.toBeInstanceOf(ConflictException);
    expect(tripMembers.has(`${tripId}:${userBId}`)).toBe(false);
  });

  it('enforces self-invite (400), missing user (404), non-owner (403), and UserBlock (403)', async () => {
    await expect(
      tripInvitesService.createInvite(tripId, ownerId, 'owner.a@wanderai.test'),
    ).rejects.toBeInstanceOf(BadRequestException);

    await expect(
      tripInvitesService.createInvite(tripId, ownerId, 'nobody@wanderai.test'),
    ).rejects.toBeInstanceOf(NotFoundException);

    await expect(
      tripInvitesService.createInvite(tripId, userBId, 'outsider.c@wanderai.test'),
    ).rejects.toBeInstanceOf(ForbiddenException);

    blockedPairs = [{ blockerId: userBId, blockedId: ownerId }];
    await expect(
      tripInvitesService.createInvite(tripId, ownerId, 'member.b@wanderai.test'),
    ).rejects.toBeInstanceOf(ForbiddenException);
  });
});
