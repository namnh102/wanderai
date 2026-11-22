import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { MatchStatus, TravelStyle } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';

export interface SafeBuddyPeerView {
  id: string;
  displayName: string;
  avatar: string | null;
  bio: string | null;
  nationality: string | null;
  languages: string[];
  travelStyle: TravelStyle | null;
  interests: string[];
}

export interface ComputedCompatibility {
  score: number;
  band: 'HIGH' | 'MEDIUM' | 'LOW';
  sharedInterests: string[];
  sharedDestinationIds: string[];
  sharedDestinationNames: string[];
  hasOverlappingTripWindow: boolean;
  explanation: string;
}

const INTEREST_LABELS_VI: Record<string, string> = {
  food_cuisine: 'Ẩm thực',
  culture_history: 'Văn hóa & Lịch sử',
  nature_outdoor: 'Thiên nhiên',
  coffee_culture: 'Cà phê',
  beach_island: 'Biển & Đảo',
  shopping_local: 'Chợ & Mua sắm',
  nightlife_entertainment: 'Giải trí đêm',
};

function normalizeInterests(raw: string[] | null | undefined): string[] {
  if (!raw) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const item of raw) {
    const clean = item.trim().toLowerCase();
    if (clean && !seen.has(clean)) {
      seen.add(clean);
      out.push(clean);
    }
  }
  return out;
}

function datesOverlap(
  aStart: Date | null,
  aEnd: Date | null,
  bStart: Date | null,
  bEnd: Date | null,
): boolean {
  if (!aStart || !aEnd || !bStart || !bEnd) return false;
  return aStart.getTime() <= bEnd.getTime() && bStart.getTime() <= aEnd.getTime();
}

export function scoreBuddyCompatibility(params: {
  viewerInterests: string[];
  viewerStyle: TravelStyle | null;
  viewerTrips: Array<{ destinationId: string | null; startDate: Date | null; endDate: Date | null; destinationName?: string | null }>;
  peerInterests: string[];
  peerStyle: TravelStyle | null;
  peerTrips: Array<{ destinationId: string | null; startDate: Date | null; endDate: Date | null; destinationName?: string | null }>;
}): ComputedCompatibility {
  const aInt = normalizeInterests(params.viewerInterests);
  const bInt = new Set(normalizeInterests(params.peerInterests));
  const sharedInterests = aInt.filter((k) => bInt.has(k));
  const unionSize = new Set([...aInt, ...bInt]).size;

  // 0..50 pts from canonical travel interest overlap
  const interestScore =
    unionSize > 0 ? Math.round((sharedInterests.length / unionSize) * 50) : 0;

  // 0 or 20 pts for shared travel style
  const styleMatches =
    params.viewerStyle != null &&
    params.peerStyle != null &&
    params.viewerStyle === params.peerStyle;
  const styleScore = styleMatches ? 20 : 0;

  // 0..30 pts for shared destination + overlapping travel dates
  const sharedDestMap = new Map<string, string>();
  let overlapWindow = false;
  for (const vt of params.viewerTrips) {
    if (!vt.destinationId) continue;
    for (const pt of params.peerTrips) {
      if (pt.destinationId !== vt.destinationId) continue;
      sharedDestMap.set(
        vt.destinationId,
        pt.destinationName || vt.destinationName || 'điểm đến chung',
      );
      if (datesOverlap(vt.startDate, vt.endDate, pt.startDate, pt.endDate)) {
        overlapWindow = true;
      }
    }
  }
  const destScore = sharedDestMap.size > 0 ? 20 : 0;
  const windowScore = overlapWindow ? 10 : 0;

  const total = Math.min(100, interestScore + styleScore + destScore + windowScore);
  const band: 'HIGH' | 'MEDIUM' | 'LOW' =
    total >= 65 ? 'HIGH' : total >= 35 ? 'MEDIUM' : 'LOW';

  const parts: string[] = [];
  if (sharedInterests.length > 0) {
    const labels = sharedInterests
      .slice(0, 3)
      .map((k) => INTEREST_LABELS_VI[k] ?? k);
    parts.push(`Cùng sở thích: ${labels.join(', ')}`);
  }
  if (styleMatches) {
    parts.push(`Cùng phong cách ${params.peerStyle}`);
  }
  if (sharedDestMap.size > 0) {
    const destNames = Array.from(sharedDestMap.values()).slice(0, 2).join(', ');
    parts.push(
      overlapWindow
        ? `Cùng kế hoạch đến ${destNames} trùng khung thời gian`
        : `Cùng quan tâm điểm đến ${destNames}`,
    );
  }
  const explanation =
    parts.length > 0
      ? parts.join(' · ')
      : 'Hồ sơ du lịch mở kết nối bạn đồng hành an toàn.';

  return {
    score: total,
    band,
    sharedInterests,
    sharedDestinationIds: Array.from(sharedDestMap.keys()),
    sharedDestinationNames: Array.from(sharedDestMap.values()),
    hasOverlappingTripWindow: overlapWindow,
    explanation,
  };
}

/**
 * Explicitly maps a Prisma User relation to a non-PII public buddy view.
 * Email, phone, passwordHash, and safety contacts are NEVER included.
 */
export function toSafeBuddyPeerView(user: {
  id: string;
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
}): SafeBuddyPeerView {
  const display = user.profile?.displayName?.trim();
  return {
    id: user.id,
    displayName: display && display.length > 0 ? display : 'Du khách GoMate',
    avatar: user.profile?.avatar ?? null,
    bio: user.profile?.bio ?? null,
    nationality: user.profile?.nationality ?? null,
    languages: user.profile?.languages ?? [],
    travelStyle: user.preferences?.travelStyle ?? null,
    interests: user.preferences?.interests ?? [],
  };
}

const SAFE_BUDDY_USER_SELECT = {
  id: true,
  profile: {
    select: {
      displayName: true,
      avatar: true,
      bio: true,
      nationality: true,
      languages: true,
    },
  },
  preferences: {
    select: {
      travelStyle: true,
      interests: true,
    },
  },
  trips: {
    where: {
      deletedAt: null,
      status: { in: ['DRAFT' as const, 'PLANNED' as const, 'ONGOING' as const] },
    },
    select: {
      destinationId: true,
      startDate: true,
      endDate: true,
      destination: { select: { name: true } },
    },
  },
};

@Injectable()
export class MatchesService {
  constructor(private prisma: PrismaService) {}

  async listCandidates(userId: string, destinationId?: string, limit = 20) {
    const safeLimit = Math.min(Math.max(1, limit), 50);

    const [viewer, existingMatches, rawPeers] = await Promise.all([
      this.prisma.user.findUnique({
        where: { id: userId },
        select: SAFE_BUDDY_USER_SELECT,
      }),
      this.prisma.match.findMany({
        where: { OR: [{ senderId: userId }, { receiverId: userId }] },
        select: { id: true, senderId: true, receiverId: true, status: true },
      }),
      this.prisma.user.findMany({
        where: {
          id: { not: userId },
          deletedAt: null,
          // Curators/system accounts are never surfaced as human travel buddies.
          NOT: { email: 'curator@wanderai.vn' },
          ...(destinationId
            ? {
                trips: {
                  some: {
                    deletedAt: null,
                    destinationId,
                  },
                },
              }
            : {}),
        },
        select: SAFE_BUDDY_USER_SELECT,
        take: 150,
      }),
    ]);

    if (!viewer) {
      throw new NotFoundException('Không tìm thấy hồ sơ người dùng');
    }

    const matchByPeerId = new Map<
      string,
      { matchId: string; status: MatchStatus; direction: 'SENT' | 'RECEIVED' }
    >();
    for (const m of existingMatches) {
      const isSender = m.senderId === userId;
      const peerId = isSender ? m.receiverId : m.senderId;
      matchByPeerId.set(peerId, {
        matchId: m.id,
        status: m.status,
        direction: isSender ? 'SENT' : 'RECEIVED',
      });
    }

    const viewerTrips = viewer.trips.map((t) => ({
      destinationId: t.destinationId,
      startDate: t.startDate,
      endDate: t.endDate,
      destinationName: t.destination?.name ?? null,
    }));

    const candidates = rawPeers
      .filter((peer) => matchByPeerId.get(peer.id)?.status !== MatchStatus.REJECTED)
      .map((peer) => {
        const compat = scoreBuddyCompatibility({
          viewerInterests: viewer.preferences?.interests ?? [],
          viewerStyle: viewer.preferences?.travelStyle ?? null,
          viewerTrips,
          peerInterests: peer.preferences?.interests ?? [],
          peerStyle: peer.preferences?.travelStyle ?? null,
          peerTrips: peer.trips.map((t) => ({
            destinationId: t.destinationId,
            startDate: t.startDate,
            endDate: t.endDate,
            destinationName: t.destination?.name ?? null,
          })),
        });
        const existing = matchByPeerId.get(peer.id);
        return {
          peer: toSafeBuddyPeerView(peer),
          compatibilityScore: compat.score,
          compatibilityBand: compat.band,
          sharedInterests: compat.sharedInterests,
          sharedDestinationIds: compat.sharedDestinationIds,
          sharedDestinationNames: compat.sharedDestinationNames,
          hasOverlappingTripWindow: compat.hasOverlappingTripWindow,
          explanation: compat.explanation,
          matchId: existing?.matchId ?? null,
          matchStatus: existing?.status ?? null,
          matchDirection: existing?.direction ?? null,
          privacyNotice:
            'Thông tin liên hệ cá nhân (email, số điện thoại) luôn được ẩn bảo mật.',
        };
      })
      .sort(
        (a, b) =>
          b.compatibilityScore - a.compatibilityScore ||
          a.peer.id.localeCompare(b.peer.id),
      )
      .slice(0, safeLimit);

    return {
      items: candidates,
      total: candidates.length,
      scoringBasis: 'rule_based_canonical_preferences_and_trip_overlap',
    };
  }

  async listMyMatches(userId: string) {
    const rows = await this.prisma.match.findMany({
      where: { OR: [{ senderId: userId }, { receiverId: userId }] },
      orderBy: { createdAt: 'desc' },
      include: {
        sender: { select: SAFE_BUDDY_USER_SELECT },
        receiver: { select: SAFE_BUDDY_USER_SELECT },
      },
    });

    return {
      items: rows.map((m) => {
        const isSender = m.senderId === userId;
        const peer = isSender ? m.receiver : m.sender;
        return {
          id: m.id,
          status: m.status,
          direction: isSender ? 'SENT' : 'RECEIVED',
          score: m.score,
          explanation: m.explanation,
          createdAt: m.createdAt,
          peer: toSafeBuddyPeerView(peer),
        };
      }),
      total: rows.length,
    };
  }

  async sendMatchRequest(senderId: string, receiverId: string) {
    if (senderId === receiverId) {
      throw new BadRequestException('Không thể gửi lời mời kết bạn cho chính mình');
    }

    const [sender, receiver] = await Promise.all([
      this.prisma.user.findUnique({ where: { id: senderId }, select: SAFE_BUDDY_USER_SELECT }),
      this.prisma.user.findUnique({
        where: { id: receiverId },
        select: { ...SAFE_BUDDY_USER_SELECT, deletedAt: true, email: true },
      }),
    ]);

    if (!sender) {
      throw new NotFoundException('Tài khoản người gửi không tồn tại');
    }
    if (!receiver || receiver.deletedAt !== null || receiver.email === 'curator@wanderai.vn') {
      throw new NotFoundException('Không tìm thấy bạn đồng hành phù hợp');
    }

    const existing = await this.prisma.match.findFirst({
      where: {
        OR: [
          { senderId, receiverId },
          { senderId: receiverId, receiverId: senderId },
        ],
      },
    });
    if (existing) {
      throw new ConflictException(
        existing.senderId === receiverId
          ? 'Người dùng này đã gửi lời mời cho bạn — hãy phản hồi lời mời đó.'
          : 'Bạn đã gửi lời mời kết nối với người dùng này trước đó.',
      );
    }

    const compat = scoreBuddyCompatibility({
      viewerInterests: sender.preferences?.interests ?? [],
      viewerStyle: sender.preferences?.travelStyle ?? null,
      viewerTrips: sender.trips.map((t) => ({
        destinationId: t.destinationId,
        startDate: t.startDate,
        endDate: t.endDate,
        destinationName: t.destination?.name ?? null,
      })),
      peerInterests: receiver.preferences?.interests ?? [],
      peerStyle: receiver.preferences?.travelStyle ?? null,
      peerTrips: receiver.trips.map((t) => ({
        destinationId: t.destinationId,
        startDate: t.startDate,
        endDate: t.endDate,
        destinationName: t.destination?.name ?? null,
      })),
    });

    const created = await this.prisma.match.create({
      data: {
        senderId,
        receiverId,
        status: MatchStatus.PENDING,
        score: compat.score,
        explanation: compat.explanation,
      },
      include: {
        receiver: { select: SAFE_BUDDY_USER_SELECT },
      },
    });

    return {
      id: created.id,
      status: created.status,
      direction: 'SENT' as const,
      score: created.score,
      explanation: created.explanation,
      createdAt: created.createdAt,
      peer: toSafeBuddyPeerView(created.receiver),
    };
  }

  async respondToMatch(
    matchId: string,
    actingUserId: string,
    action: 'ACCEPTED' | 'REJECTED',
  ) {
    const match = await this.prisma.match.findUnique({ where: { id: matchId } });
    if (!match) {
      throw new NotFoundException('Lời mời kết nối không tồn tại');
    }
    if (match.receiverId !== actingUserId) {
      throw new ForbiddenException('Chỉ người nhận mới có quyền phản hồi lời mời này');
    }
    if (match.status !== MatchStatus.PENDING) {
      throw new BadRequestException(`Lời mời đã ở trạng thái ${match.status}`);
    }

    const nextStatus =
      action === 'ACCEPTED' ? MatchStatus.ACCEPTED : MatchStatus.REJECTED;
    const updated = await this.prisma.match.update({
      where: { id: matchId },
      data: { status: nextStatus },
      include: {
        sender: { select: SAFE_BUDDY_USER_SELECT },
      },
    });

    return {
      id: updated.id,
      status: updated.status,
      direction: 'RECEIVED' as const,
      score: updated.score,
      explanation: updated.explanation,
      createdAt: updated.createdAt,
      peer: toSafeBuddyPeerView(updated.sender),
    };
  }
}
