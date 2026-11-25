import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { MatchStatus, Prisma, TravelStyle } from "@prisma/client";
import { PrismaService } from "../../prisma/prisma.service";

export type HandshakeState = "PENDING" | "MATCHED" | "REJECTED" | "WITHDRAWN";

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
  band: "HIGH" | "MEDIUM" | "LOW";
  sharedInterests: string[];
  sharedDestinationIds: string[];
  sharedDestinationNames: string[];
  hasOverlappingTripWindow: boolean;
  explanation: string;
}

export interface RankedBuddyCandidateItem {
  peer: SafeBuddyPeerView;
  compatibilityScore: number;
  compatibilityBand: "HIGH" | "MEDIUM" | "LOW";
  sharedInterests: string[];
  sharedDestinationIds: string[];
  sharedDestinationNames: string[];
  hasOverlappingTripWindow: boolean;
  explanation: string;
  matchId: string | null;
  matchStatus: MatchStatus | null;
  handshakeState: HandshakeState | null;
  isMatched: boolean;
  matchDirection: "SENT" | "RECEIVED" | null;
  privacyNotice: string;
}

const SYSTEM_CURATOR_EMAIL = "curator@wanderai.vn";
const PRIVACY_NOTICE_TEXT =
  "Thông tin liên hệ cá nhân (email, số điện thoại, tọa độ và danh bạ khẩn cấp) luôn được ẩn bảo mật.";

const INTEREST_LABELS_VI: Record<string, string> = {
  food_cuisine: "Ẩm thực",
  culture_history: "Văn hóa & Lịch sử",
  nature_outdoor: "Thiên nhiên",
  coffee_culture: "Cà phê",
  beach_island: "Biển & Đảo",
  shopping_local: "Chợ & Mua sắm",
  nightlife_entertainment: "Giải trí đêm",
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
  return (
    aStart.getTime() <= bEnd.getTime() && bStart.getTime() <= aEnd.getTime()
  );
}

export function toHandshakeState(status: MatchStatus): HandshakeState {
  if (status === MatchStatus.ACCEPTED) return "MATCHED";
  return status;
}

export function scoreBuddyCompatibility(params: {
  viewerInterests: string[];
  viewerStyle: TravelStyle | null;
  viewerTrips: Array<{
    destinationId: string | null;
    startDate: Date | null;
    endDate: Date | null;
    destinationName?: string | null;
  }>;
  peerInterests: string[];
  peerStyle: TravelStyle | null;
  peerTrips: Array<{
    destinationId: string | null;
    startDate: Date | null;
    endDate: Date | null;
    destinationName?: string | null;
  }>;
}): ComputedCompatibility {
  const aInt = normalizeInterests(params.viewerInterests);
  const bInt = new Set(normalizeInterests(params.peerInterests));
  const sharedInterests = aInt.filter((k) => bInt.has(k));
  const unionSize = new Set([...aInt, ...bInt]).size;

  // 0..50 pts from canonical travel interest Jaccard overlap
  const interestScore =
    unionSize > 0 ? Math.round((sharedInterests.length / unionSize) * 50) : 0;

  // 0 or 20 pts for shared travel style
  const styleMatches =
    params.viewerStyle != null &&
    params.peerStyle != null &&
    params.viewerStyle === params.peerStyle;
  const styleScore = styleMatches ? 20 : 0;

  // 0..30 pts for shared destination (20) + overlapping travel dates (10)
  const sharedDestMap = new Map<string, string>();
  let overlapWindow = false;
  for (const vt of params.viewerTrips) {
    if (!vt.destinationId) continue;
    for (const pt of params.peerTrips) {
      if (pt.destinationId !== vt.destinationId) continue;
      sharedDestMap.set(
        vt.destinationId,
        pt.destinationName || vt.destinationName || "điểm đến chung",
      );
      if (datesOverlap(vt.startDate, vt.endDate, pt.startDate, pt.endDate)) {
        overlapWindow = true;
      }
    }
  }
  const destScore = sharedDestMap.size > 0 ? 20 : 0;
  const windowScore = overlapWindow ? 10 : 0;

  const total = Math.min(
    100,
    interestScore + styleScore + destScore + windowScore,
  );
  const band: "HIGH" | "MEDIUM" | "LOW" =
    total >= 65 ? "HIGH" : total >= 35 ? "MEDIUM" : "LOW";

  const parts: string[] = [];
  if (sharedInterests.length > 0) {
    const labels = sharedInterests
      .slice(0, 3)
      .map((k) => INTEREST_LABELS_VI[k] ?? k);
    parts.push(`Cùng sở thích: ${labels.join(", ")}`);
  }
  if (styleMatches) {
    parts.push(`Cùng phong cách ${params.peerStyle}`);
  }
  if (sharedDestMap.size > 0) {
    const destNames = Array.from(sharedDestMap.values()).slice(0, 2).join(", ");
    parts.push(
      overlapWindow
        ? `Cùng kế hoạch đến ${destNames} trùng khung thời gian`
        : `Cùng quan tâm điểm đến ${destNames}`,
    );
  }
  const explanation =
    parts.length > 0
      ? parts.join(" · ")
      : "Hồ sơ du lịch mở kết nối bạn đồng hành an toàn.";

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
 * Deterministic multi-level ranking & tie-breaking comparator for WP-BUDDY-01 / MATCH-EVAL-01:
 * 1. Total compatibility score (0..100, DESC)
 * 2. Overlapping destination date window (`true` before `false`)
 * 3. Shared destination count (DESC)
 * 4. Shared canonical interest count (DESC)
 * 5. Canonical peer UUID (`ASC`, deterministic final tie-breaker)
 */
export function compareBuddyCandidates(
  a: Pick<
    RankedBuddyCandidateItem,
    | "compatibilityScore"
    | "hasOverlappingTripWindow"
    | "sharedDestinationIds"
    | "sharedInterests"
    | "peer"
  >,
  b: Pick<
    RankedBuddyCandidateItem,
    | "compatibilityScore"
    | "hasOverlappingTripWindow"
    | "sharedDestinationIds"
    | "sharedInterests"
    | "peer"
  >,
): number {
  if (b.compatibilityScore !== a.compatibilityScore) {
    return b.compatibilityScore - a.compatibilityScore;
  }
  if (b.hasOverlappingTripWindow !== a.hasOverlappingTripWindow) {
    return (
      Number(b.hasOverlappingTripWindow) - Number(a.hasOverlappingTripWindow)
    );
  }
  if (b.sharedDestinationIds.length !== a.sharedDestinationIds.length) {
    return b.sharedDestinationIds.length - a.sharedDestinationIds.length;
  }
  if (b.sharedInterests.length !== a.sharedInterests.length) {
    return b.sharedInterests.length - a.sharedInterests.length;
  }
  return a.peer.id.localeCompare(b.peer.id);
}

/**
 * Explicitly maps a Prisma User relation to a non-PII public buddy view.
 * Email, phone, dateOfBirth, dietaryNeeds, avoidances, budgetMin/budgetMax,
 * passwordHash, safetyContacts, and safetyCheckins are NEVER included.
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
    displayName: display && display.length > 0 ? display : "Du khách GoMate",
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
  deletedAt: true,
  profile: {
    select: {
      displayName: true,
      avatar: true,
      bio: true,
      nationality: true,
      languages: true,
      isDiscoverable: true,
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
      status: {
        in: ["DRAFT" as const, "PLANNED" as const, "ONGOING" as const],
      },
    },
    select: {
      destinationId: true,
      startDate: true,
      endDate: true,
      destination: { select: { name: true } },
    },
  },
};

type SelectedBuddyUser = {
  id: string;
  deletedAt: Date | null;
  profile: {
    displayName: string | null;
    avatar: string | null;
    bio: string | null;
    nationality: string | null;
    languages: string[];
    isDiscoverable: boolean;
  } | null;
  preferences: {
    travelStyle: TravelStyle | null;
    interests: string[];
  } | null;
  trips: Array<{
    destinationId: string | null;
    startDate: Date | null;
    endDate: Date | null;
    destination: { name: string } | null;
  }>;
};

function mapTripsForScoring(user: Pick<SelectedBuddyUser, "trips">) {
  return (user.trips ?? []).map((t) => ({
    destinationId: t.destinationId,
    startDate: t.startDate,
    endDate: t.endDate,
    destinationName: t.destination?.name ?? null,
  }));
}

@Injectable()
export class MatchesService {
  constructor(private prisma: PrismaService) {}

  /**
   * Acquires PostgreSQL row-level locks on `users` in strictly ascending UUID order
   * so concurrent mutations (`withdraw`, `respond`, `discovery consent`, `block`, `request`)
   * serialize cleanly under `READ COMMITTED` without deadlocks or two-table write skew.
   */
  private async _lockUsersInOrder(
    tx: Partial<Pick<Prisma.TransactionClient, "$queryRaw">>,
    userIds: string[],
  ): Promise<void> {
    if (typeof tx.$queryRaw !== "function") {
      return;
    }
    const uniqueSorted = Array.from(new Set(userIds)).sort((a, b) =>
      a.localeCompare(b),
    );
    for (const uid of uniqueSorted) {
      await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${uid}::uuid FOR UPDATE`;
    }
  }

  private async _getBlockedPeerIds(userId: string): Promise<Set<string>> {
    const blocks = await this.prisma.userBlock.findMany({
      where: {
        OR: [{ blockerId: userId }, { blockedId: userId }],
      },
      select: { blockerId: true, blockedId: true },
    });
    const peerIds = new Set<string>();
    for (const b of blocks) {
      peerIds.add(b.blockerId === userId ? b.blockedId : b.blockerId);
    }
    return peerIds;
  }

  private async _hasTwoWayBlock(
    userA: string,
    userB: string,
  ): Promise<boolean> {
    const row = await this.prisma.userBlock.findFirst({
      where: {
        OR: [
          { blockerId: userA, blockedId: userB },
          { blockerId: userB, blockedId: userA },
        ],
      },
      select: { id: true },
    });
    return row !== null;
  }

  async getDiscoveryConsent(userId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        deletedAt: true,
        profile: { select: { isDiscoverable: true } },
      },
    });
    if (!user || user.deletedAt !== null) {
      throw new NotFoundException("Không tìm thấy hồ sơ người dùng");
    }
    return {
      isDiscoverable: user.profile?.isDiscoverable ?? false,
      privacyNotice: PRIVACY_NOTICE_TEXT,
    };
  }

  async updateDiscoveryConsent(userId: string, isDiscoverable: boolean) {
    return this.prisma.$transaction(async (tx) => {
      await this._lockUsersInOrder(tx, [userId]);

      const user = await tx.user.findUnique({
        where: { id: userId },
        select: { id: true, deletedAt: true },
      });
      if (!user || user.deletedAt !== null) {
        throw new NotFoundException("Không tìm thấy hồ sơ người dùng");
      }

      const profile = await tx.profile.upsert({
        where: { userId },
        update: { isDiscoverable },
        create: {
          userId,
          displayName: "Du khách GoMate",
          isDiscoverable,
        },
        select: { isDiscoverable: true },
      });

      return {
        isDiscoverable: profile.isDiscoverable,
        privacyNotice: PRIVACY_NOTICE_TEXT,
      };
    });
  }

  async listCandidates(userId: string, destinationId?: string, limit = 20) {
    const safeLimit = Math.min(Math.max(1, limit), 50);

    const viewer = (await this.prisma.user.findUnique({
      where: { id: userId },
      select: SAFE_BUDDY_USER_SELECT,
    })) as SelectedBuddyUser | null;

    if (!viewer || viewer.deletedAt !== null) {
      throw new NotFoundException("Không tìm thấy hồ sơ người dùng");
    }

    const viewerDiscoverable = viewer.profile?.isDiscoverable ?? false;
    if (!viewerDiscoverable) {
      return {
        isDiscoverable: false,
        items: [] as RankedBuddyCandidateItem[],
        total: 0,
        scoringBasis:
          "rule_based_canonical_preferences_and_trip_overlap_with_deterministic_tiebreak",
      };
    }

    const [blockedPeerIds, existingMatches] = await Promise.all([
      this._getBlockedPeerIds(userId),
      this.prisma.match.findMany({
        where: { OR: [{ senderId: userId }, { receiverId: userId }] },
        select: { id: true, senderId: true, receiverId: true, status: true },
      }),
    ]);

    const excludedIds = [userId, ...Array.from(blockedPeerIds)];

    const rawPeers = (await this.prisma.user.findMany({
      where: {
        id: { notIn: excludedIds },
        deletedAt: null,
        NOT: { email: SYSTEM_CURATOR_EMAIL },
        profile: { is: { isDiscoverable: true } },
        ...(destinationId
          ? {
              trips: {
                some: {
                  deletedAt: null,
                  status: { in: ["DRAFT", "PLANNED", "ONGOING"] },
                  destinationId,
                },
              },
            }
          : {}),
      },
      select: SAFE_BUDDY_USER_SELECT,
      orderBy: { id: "asc" },
      take: 200,
    })) as SelectedBuddyUser[];

    const matchByPeerId = new Map<
      string,
      { matchId: string; status: MatchStatus; direction: "SENT" | "RECEIVED" }
    >();
    for (const m of existingMatches) {
      const isSender = m.senderId === userId;
      const peerId = isSender ? m.receiverId : m.senderId;
      matchByPeerId.set(peerId, {
        matchId: m.id,
        status: m.status,
        direction: isSender ? "SENT" : "RECEIVED",
      });
    }

    const viewerTrips = mapTripsForScoring(viewer);

    const candidates: RankedBuddyCandidateItem[] = rawPeers
      .filter((peer) => {
        if (blockedPeerIds.has(peer.id)) return false;
        if (!peer.profile?.isDiscoverable) return false;
        const existingStatus = matchByPeerId.get(peer.id)?.status;
        return existingStatus !== MatchStatus.REJECTED;
      })
      .map((peer) => {
        const compat = scoreBuddyCompatibility({
          viewerInterests: viewer.preferences?.interests ?? [],
          viewerStyle: viewer.preferences?.travelStyle ?? null,
          viewerTrips,
          peerInterests: peer.preferences?.interests ?? [],
          peerStyle: peer.preferences?.travelStyle ?? null,
          peerTrips: mapTripsForScoring(peer),
        });
        const existing = matchByPeerId.get(peer.id);
        const activeMatch =
          existing && existing.status !== MatchStatus.WITHDRAWN
            ? existing
            : undefined;

        return {
          peer: toSafeBuddyPeerView(peer),
          compatibilityScore: compat.score,
          compatibilityBand: compat.band,
          sharedInterests: compat.sharedInterests,
          sharedDestinationIds: compat.sharedDestinationIds,
          sharedDestinationNames: compat.sharedDestinationNames,
          hasOverlappingTripWindow: compat.hasOverlappingTripWindow,
          explanation: compat.explanation,
          matchId: activeMatch?.matchId ?? null,
          matchStatus: activeMatch?.status ?? null,
          handshakeState: activeMatch
            ? toHandshakeState(activeMatch.status)
            : null,
          isMatched: activeMatch?.status === MatchStatus.ACCEPTED,
          matchDirection: activeMatch?.direction ?? null,
          privacyNotice: PRIVACY_NOTICE_TEXT,
        };
      })
      .sort(compareBuddyCandidates)
      .slice(0, safeLimit);

    return {
      isDiscoverable: true,
      items: candidates,
      total: candidates.length,
      scoringBasis:
        "rule_based_canonical_preferences_and_trip_overlap_with_deterministic_tiebreak",
    };
  }

  async getMaskedPeerProfile(viewerId: string, peerId: string) {
    if (viewerId === peerId) {
      throw new BadRequestException(
        "Không thể mở hồ sơ ghép đôi của chính mình",
      );
    }

    if (await this._hasTwoWayBlock(viewerId, peerId)) {
      throw new ForbiddenException(
        "Không thể xem hồ sơ do trạng thái chặn hai chiều",
      );
    }

    const [viewer, peer, existingMatch] = await Promise.all([
      this.prisma.user.findUnique({
        where: { id: viewerId },
        select: SAFE_BUDDY_USER_SELECT,
      }) as Promise<SelectedBuddyUser | null>,
      this.prisma.user.findUnique({
        where: { id: peerId },
        select: { ...SAFE_BUDDY_USER_SELECT, email: true },
      }) as Promise<(SelectedBuddyUser & { email: string }) | null>,
      this.prisma.match.findFirst({
        where: {
          OR: [
            { senderId: viewerId, receiverId: peerId },
            { senderId: peerId, receiverId: viewerId },
          ],
        },
        select: { id: true, senderId: true, receiverId: true, status: true },
      }),
    ]);

    if (!viewer || viewer.deletedAt !== null) {
      throw new NotFoundException("Không tìm thấy hồ sơ người dùng");
    }
    if (
      !peer ||
      peer.deletedAt !== null ||
      peer.email === SYSTEM_CURATOR_EMAIL
    ) {
      throw new NotFoundException("Không tìm thấy hồ sơ bạn đồng hành");
    }

    const isAlreadyAccepted = existingMatch?.status === MatchStatus.ACCEPTED;
    const isPendingWithViewer = existingMatch?.status === MatchStatus.PENDING;
    if (
      !peer.profile?.isDiscoverable &&
      !isAlreadyAccepted &&
      !isPendingWithViewer
    ) {
      throw new NotFoundException(
        "Người dùng này hiện không bật chế độ tìm bạn đồng hành",
      );
    }

    const viewerTrips = mapTripsForScoring(viewer);
    const peerTrips = mapTripsForScoring(peer);
    const compat = scoreBuddyCompatibility({
      viewerInterests: viewer.preferences?.interests ?? [],
      viewerStyle: viewer.preferences?.travelStyle ?? null,
      viewerTrips,
      peerInterests: peer.preferences?.interests ?? [],
      peerStyle: peer.preferences?.travelStyle ?? null,
      peerTrips,
    });

    // Coarse, privacy-safe destination summary only (never exact dates, coordinates, or bookings)
    const uniqueDestinations = new Map<
      string,
      {
        destinationId: string;
        destinationName: string;
        hasOverlappingWindow: boolean;
      }
    >();
    for (const pt of peerTrips) {
      if (!pt.destinationId || !pt.destinationName) continue;
      const overlapsViewer = viewerTrips.some(
        (vt) =>
          vt.destinationId === pt.destinationId &&
          datesOverlap(vt.startDate, vt.endDate, pt.startDate, pt.endDate),
      );
      const prev = uniqueDestinations.get(pt.destinationId);
      uniqueDestinations.set(pt.destinationId, {
        destinationId: pt.destinationId,
        destinationName: pt.destinationName,
        hasOverlappingWindow:
          (prev?.hasOverlappingWindow ?? false) || overlapsViewer,
      });
    }

    const activeMatch =
      existingMatch && existingMatch.status !== MatchStatus.WITHDRAWN
        ? existingMatch
        : null;

    return {
      peer: toSafeBuddyPeerView(peer),
      compatibilityScore: compat.score,
      compatibilityBand: compat.band,
      sharedInterests: compat.sharedInterests,
      sharedDestinationIds: compat.sharedDestinationIds,
      sharedDestinationNames: compat.sharedDestinationNames,
      hasOverlappingTripWindow: compat.hasOverlappingTripWindow,
      explanation: compat.explanation,
      plannedDestinations: Array.from(uniqueDestinations.values()),
      matchId: activeMatch?.id ?? null,
      matchStatus: activeMatch?.status ?? null,
      handshakeState: activeMatch ? toHandshakeState(activeMatch.status) : null,
      isMatched: activeMatch?.status === MatchStatus.ACCEPTED,
      matchDirection: activeMatch
        ? activeMatch.senderId === viewerId
          ? ("SENT" as const)
          : ("RECEIVED" as const)
        : null,
      privacyNotice: PRIVACY_NOTICE_TEXT,
    };
  }

  async listMyMatches(userId: string) {
    const [blockedPeerIds, rows] = await Promise.all([
      this._getBlockedPeerIds(userId),
      this.prisma.match.findMany({
        where: {
          OR: [{ senderId: userId }, { receiverId: userId }],
          status: { not: MatchStatus.WITHDRAWN },
        },
        orderBy: { createdAt: "desc" },
        include: {
          sender: { select: SAFE_BUDDY_USER_SELECT },
          receiver: { select: SAFE_BUDDY_USER_SELECT },
        },
      }),
    ]);

    const visibleRows = rows.filter((m) => {
      const peerId = m.senderId === userId ? m.receiverId : m.senderId;
      return !blockedPeerIds.has(peerId);
    });

    return {
      items: visibleRows.map((m) => {
        const isSender = m.senderId === userId;
        const peer = isSender ? m.receiver : m.sender;
        const isMatched = m.status === MatchStatus.ACCEPTED;
        return {
          id: m.id,
          status: m.status,
          handshakeState: toHandshakeState(m.status),
          isMatched,
          senderConsent: true,
          receiverConsent: isMatched,
          direction: isSender ? ("SENT" as const) : ("RECEIVED" as const),
          score: m.score,
          explanation: m.explanation,
          createdAt: m.createdAt,
          peer: toSafeBuddyPeerView(peer),
        };
      }),
      total: visibleRows.length,
    };
  }

  async sendMatchRequest(senderId: string, receiverId: string) {
    if (senderId === receiverId) {
      throw new BadRequestException(
        "Không thể gửi lời mời kết bạn cho chính mình",
      );
    }

    return this.prisma.$transaction(async (tx) => {
      await this._lockUsersInOrder(tx, [senderId, receiverId]);

      const blockRow = await tx.userBlock.findFirst({
        where: {
          OR: [
            { blockerId: senderId, blockedId: receiverId },
            { blockerId: receiverId, blockedId: senderId },
          ],
        },
        select: { id: true },
      });
      if (blockRow) {
        throw new ForbiddenException(
          "Không thể gửi lời mời kết nối do trạng thái chặn hai chiều",
        );
      }

      const [sender, receiver] = await Promise.all([
        tx.user.findUnique({
          where: { id: senderId },
          select: SAFE_BUDDY_USER_SELECT,
        }) as Promise<SelectedBuddyUser | null>,
        tx.user.findUnique({
          where: { id: receiverId },
          select: { ...SAFE_BUDDY_USER_SELECT, email: true },
        }) as Promise<(SelectedBuddyUser & { email: string }) | null>,
      ]);

      if (!sender || sender.deletedAt !== null) {
        throw new NotFoundException("Tài khoản người gửi không tồn tại");
      }
      if (!sender.profile?.isDiscoverable) {
        throw new ForbiddenException(
          "Vui lòng bật chế độ tìm bạn đồng hành trước khi gửi lời mời",
        );
      }
      if (
        !receiver ||
        receiver.deletedAt !== null ||
        receiver.email === SYSTEM_CURATOR_EMAIL ||
        !receiver.profile?.isDiscoverable
      ) {
        throw new NotFoundException("Không tìm thấy bạn đồng hành phù hợp");
      }

      const existing = await tx.match.findFirst({
        where: {
          OR: [
            { senderId, receiverId },
            { senderId: receiverId, receiverId: senderId },
          ],
        },
      });

      if (existing && existing.status !== MatchStatus.WITHDRAWN) {
        throw new ConflictException(
          existing.senderId === receiverId
            ? "Người dùng này đã gửi lời mời cho bạn — hãy phản hồi lời mời đó."
            : "Bạn đã gửi lời mời kết nối với người dùng này trước đó.",
        );
      }

      const compat = scoreBuddyCompatibility({
        viewerInterests: sender.preferences?.interests ?? [],
        viewerStyle: sender.preferences?.travelStyle ?? null,
        viewerTrips: mapTripsForScoring(sender),
        peerInterests: receiver.preferences?.interests ?? [],
        peerStyle: receiver.preferences?.travelStyle ?? null,
        peerTrips: mapTripsForScoring(receiver),
      });

      if (existing) {
        await tx.match.delete({ where: { id: existing.id } });
      }

      const created = await tx.match.create({
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
        handshakeState: toHandshakeState(created.status),
        isMatched: false,
        senderConsent: true,
        receiverConsent: false,
        direction: "SENT" as const,
        score: created.score,
        explanation: created.explanation,
        createdAt: created.createdAt,
        peer: toSafeBuddyPeerView(created.receiver),
      };
    });
  }

  async withdrawMatchRequest(matchId: string, actingUserId: string) {
    return this.prisma.$transaction(async (tx) => {
      const initial = await tx.match.findUnique({
        where: { id: matchId },
        select: { id: true, senderId: true, receiverId: true },
      });
      if (!initial) {
        throw new NotFoundException("Lời mời kết nối không tồn tại");
      }
      if (initial.senderId !== actingUserId) {
        throw new ForbiddenException(
          "Chỉ người gửi mới có quyền rút lại lời mời này",
        );
      }

      await this._lockUsersInOrder(tx, [initial.senderId, initial.receiverId]);

      const match = await tx.match.findUnique({
        where: { id: matchId },
        include: {
          receiver: { select: SAFE_BUDDY_USER_SELECT },
        },
      });
      if (!match) {
        throw new NotFoundException("Lời mời kết nối không tồn tại");
      }
      if (match.status !== MatchStatus.PENDING) {
        throw new BadRequestException(
          `Không thể rút lời mời đang ở trạng thái ${match.status}`,
        );
      }

      const atomicResult = await tx.match.updateMany({
        where: {
          id: matchId,
          senderId: actingUserId,
          status: MatchStatus.PENDING,
        },
        data: { status: MatchStatus.WITHDRAWN },
      });
      if (atomicResult.count !== 1) {
        const latest = await tx.match.findUnique({
          where: { id: matchId },
          select: { status: true },
        });
        throw new ConflictException(
          latest
            ? `Không thể rút lời mời vì trạng thái đã chuyển sang ${latest.status}`
            : "Trạng thái lời mời đã thay đổi đồng thời",
        );
      }

      return {
        id: match.id,
        status: MatchStatus.WITHDRAWN,
        handshakeState: toHandshakeState(MatchStatus.WITHDRAWN),
        isMatched: false,
        senderConsent: false,
        receiverConsent: false,
        direction: "SENT" as const,
        score: match.score,
        explanation: match.explanation,
        createdAt: match.createdAt,
        peer: toSafeBuddyPeerView(match.receiver),
      };
    });
  }

  async respondToMatch(
    matchId: string,
    actingUserId: string,
    action: "ACCEPTED" | "REJECTED",
  ) {
    return this.prisma.$transaction(async (tx) => {
      const initial = await tx.match.findUnique({
        where: { id: matchId },
        select: { id: true, senderId: true, receiverId: true },
      });
      if (!initial) {
        throw new NotFoundException("Lời mời kết nối không tồn tại");
      }
      if (initial.receiverId !== actingUserId) {
        throw new ForbiddenException(
          "Chỉ người nhận mới có quyền phản hồi lời mời này",
        );
      }

      await this._lockUsersInOrder(tx, [initial.senderId, initial.receiverId]);

      const [match, blockRow] = await Promise.all([
        tx.match.findUnique({
          where: { id: matchId },
          include: {
            sender: { select: SAFE_BUDDY_USER_SELECT },
            receiver: { select: SAFE_BUDDY_USER_SELECT },
          },
        }),
        tx.userBlock.findFirst({
          where: {
            OR: [
              { blockerId: initial.senderId, blockedId: initial.receiverId },
              { blockerId: initial.receiverId, blockedId: initial.senderId },
            ],
          },
          select: { id: true },
        }),
      ]);

      if (!match) {
        throw new NotFoundException("Lời mời kết nối không tồn tại");
      }
      if (blockRow) {
        throw new ForbiddenException(
          "Không thể xử lý lời mời do trạng thái chặn hai chiều",
        );
      }
      if (match.status !== MatchStatus.PENDING) {
        throw new BadRequestException(
          `Lời mời đã ở trạng thái ${match.status}`,
        );
      }

      if (action === "ACCEPTED") {
        if (
          match.sender.deletedAt !== null ||
          !match.sender.profile?.isDiscoverable
        ) {
          throw new ConflictException(
            "Người gửi đã rút đồng thuận tìm bạn đồng hành trước khi lời mời được chấp nhận",
          );
        }
        if (
          match.receiver.deletedAt !== null ||
          !match.receiver.profile?.isDiscoverable
        ) {
          throw new ForbiddenException(
            "Vui lòng bật chế độ tìm bạn đồng hành trước khi chấp nhận kết nối",
          );
        }
      }

      const nextStatus =
        action === "ACCEPTED" ? MatchStatus.ACCEPTED : MatchStatus.REJECTED;

      const atomicResult = await tx.match.updateMany({
        where: {
          id: matchId,
          receiverId: actingUserId,
          status: MatchStatus.PENDING,
        },
        data: { status: nextStatus },
      });
      if (atomicResult.count !== 1) {
        const latest = await tx.match.findUnique({
          where: { id: matchId },
          select: { status: true },
        });
        throw new ConflictException(
          latest
            ? `Không thể phản hồi lời mời vì trạng thái đã chuyển sang ${latest.status}`
            : "Trạng thái lời mời đã thay đổi đồng thời",
        );
      }

      const isMatched = nextStatus === MatchStatus.ACCEPTED;
      return {
        id: match.id,
        status: nextStatus,
        handshakeState: toHandshakeState(nextStatus),
        isMatched,
        senderConsent: true,
        receiverConsent: isMatched,
        direction: "RECEIVED" as const,
        score: match.score,
        explanation: match.explanation,
        createdAt: match.createdAt,
        peer: toSafeBuddyPeerView(match.sender),
      };
    });
  }

  async listBlockedUsers(userId: string) {
    const rows = await this.prisma.userBlock.findMany({
      where: { blockerId: userId },
      orderBy: { createdAt: "desc" },
      include: {
        blocked: { select: SAFE_BUDDY_USER_SELECT },
      },
    });
    return {
      items: rows.map((r) => ({
        blockedAt: r.createdAt,
        peer: toSafeBuddyPeerView(r.blocked),
      })),
      total: rows.length,
    };
  }

  async blockUser(blockerId: string, blockedUserId: string) {
    if (blockerId === blockedUserId) {
      throw new BadRequestException("Không thể tự chặn chính mình");
    }

    return this.prisma.$transaction(async (tx) => {
      await this._lockUsersInOrder(tx, [blockerId, blockedUserId]);

      const target = await tx.user.findUnique({
        where: { id: blockedUserId },
        select: SAFE_BUDDY_USER_SELECT,
      });
      if (!target || target.deletedAt !== null) {
        throw new NotFoundException("Không tìm thấy người dùng cần chặn");
      }

      await tx.userBlock.upsert({
        where: {
          blockerId_blockedId: {
            blockerId,
            blockedId: blockedUserId,
          },
        },
        update: {},
        create: {
          blockerId,
          blockedId: blockedUserId,
        },
      });

      // Immediately revoke any PENDING or ACCEPTED match in either direction
      const revoked = await tx.match.updateMany({
        where: {
          OR: [
            { senderId: blockerId, receiverId: blockedUserId },
            { senderId: blockedUserId, receiverId: blockerId },
          ],
          status: { in: [MatchStatus.PENDING, MatchStatus.ACCEPTED] },
        },
        data: { status: MatchStatus.REJECTED },
      });

      return {
        blocked: true,
        revokedMatchCount: revoked.count,
        peer: toSafeBuddyPeerView(target),
      };
    });
  }

  async unblockUser(blockerId: string, blockedUserId: string) {
    await this.prisma.userBlock.deleteMany({
      where: { blockerId, blockedId: blockedUserId },
    });
    return { blocked: false, unblockedUserId: blockedUserId };
  }
}
