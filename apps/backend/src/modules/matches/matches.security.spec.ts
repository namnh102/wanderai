import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  NotFoundException,
} from "@nestjs/common";
import { MatchStatus, TravelStyle } from "@prisma/client";
import {
  compareBuddyCandidates,
  MatchesService,
  scoreBuddyCompatibility,
  toSafeBuddyPeerView,
} from "./matches.service";

function makePrismaMock() {
  const prisma: any = {
    user: {
      findUnique: jest.fn(),
      findMany: jest.fn(),
    },
    profile: {
      upsert: jest.fn(),
    },
    userBlock: {
      findMany: jest.fn().mockResolvedValue([]),
      findFirst: jest.fn().mockResolvedValue(null),
      upsert: jest.fn(),
      deleteMany: jest.fn(),
    },
    match: {
      findFirst: jest.fn(),
      findMany: jest.fn(),
      findUnique: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      updateMany: jest.fn(),
      delete: jest.fn(),
    },
    $queryRaw: jest.fn().mockResolvedValue([]),
    $transaction: jest.fn(async (cb: (tx: any) => Promise<any>) => cb(prisma)),
  };
  return prisma;
}

describe("MatchesService W08 Buddy Matching, Consent & Privacy Boundary", () => {
  it("computes deterministic explainable compatibility score without paid APIs", () => {
    const res = scoreBuddyCompatibility({
      viewerInterests: ["food_cuisine", "culture_history"],
      viewerStyle: TravelStyle.COMFORT,
      viewerTrips: [
        {
          destinationId: "dest-dn",
          destinationName: "Đà Nẵng",
          startDate: new Date("2026-12-01"),
          endDate: new Date("2026-12-05"),
        },
      ],
      peerInterests: ["food_cuisine", "beach_island", "culture_history"],
      peerStyle: TravelStyle.COMFORT,
      peerTrips: [
        {
          destinationId: "dest-dn",
          destinationName: "Đà Nẵng",
          startDate: new Date("2026-12-03"),
          endDate: new Date("2026-12-06"),
        },
      ],
    });

    expect(res.score).toBe(83);
    expect(res.band).toBe("HIGH");
    expect(res.sharedInterests).toEqual(["food_cuisine", "culture_history"]);
    expect(res.sharedDestinationIds).toEqual(["dest-dn"]);
    expect(res.hasOverlappingTripWindow).toBe(true);
    expect(res.explanation).toContain("Ẩm thực");
    expect(res.explanation).toContain("Đà Nẵng");
  });

  it("compareBuddyCandidates enforces deterministic tie-breaking (score -> window overlap -> shared dests -> shared interests -> peer.id)", () => {
    const basePeer = (id: string) => ({
      id,
      displayName: id,
      avatar: null,
      bio: null,
      nationality: "VN",
      languages: ["vi"],
      travelStyle: TravelStyle.COMFORT,
      interests: [],
    });

    const cWindow = {
      peer: basePeer("00000000-0000-4000-8000-000000000009"),
      compatibilityScore: 55,
      hasOverlappingTripWindow: true,
      sharedDestinationIds: ["d1"],
      sharedInterests: ["food_cuisine"],
    };
    const cNoWindow = {
      peer: basePeer("00000000-0000-4000-8000-000000000001"),
      compatibilityScore: 55,
      hasOverlappingTripWindow: false,
      sharedDestinationIds: ["d1", "d2"],
      sharedInterests: ["food_cuisine", "culture_history", "coffee_culture"],
    };
    const cDest = {
      peer: basePeer("00000000-0000-4000-8000-000000000005"),
      compatibilityScore: 55,
      hasOverlappingTripWindow: false,
      sharedDestinationIds: ["d1"],
      sharedInterests: ["food_cuisine"],
    };
    const cNoDestHigherId = {
      peer: basePeer("00000000-0000-4000-8000-000000000008"),
      compatibilityScore: 55,
      hasOverlappingTripWindow: false,
      sharedDestinationIds: [],
      sharedInterests: ["food_cuisine"],
    };
    const cNoDestLowerId = {
      peer: basePeer("00000000-0000-4000-8000-000000000002"),
      compatibilityScore: 55,
      hasOverlappingTripWindow: false,
      sharedDestinationIds: [],
      sharedInterests: ["food_cuisine"],
    };

    const sorted = [
      cNoDestHigherId,
      cDest,
      cWindow,
      cNoDestLowerId,
      cNoWindow,
    ].sort(compareBuddyCandidates);

    expect(sorted.map((x) => x.peer.id)).toEqual([
      "00000000-0000-4000-8000-000000000009",
      "00000000-0000-4000-8000-000000000001",
      "00000000-0000-4000-8000-000000000005",
      "00000000-0000-4000-8000-000000000002",
      "00000000-0000-4000-8000-000000000008",
    ]);
  });

  it("toSafeBuddyPeerView strips PII and private preference attributes", () => {
    const rawUser: any = {
      id: "u-2",
      email: "secret@example.com",
      phone: "+84999999999",
      passwordHash: "$2b$10$secret",
      profile: {
        displayName: "   ",
        avatar: null,
        bio: "Thích khám phá ẩm thực phố cổ",
        nationality: "VN",
        languages: ["vi", "en"],
        phone: "+84999999999",
        dateOfBirth: new Date("1999-01-01"),
      },
      preferences: {
        travelStyle: TravelStyle.BUDGET,
        interests: ["food_cuisine"],
        dietaryNeeds: ["PRIVATE_HALAL"],
        avoidances: ["PRIVATE_CROWDS"],
        budgetMin: 1000000,
        budgetMax: 5000000,
      },
    };
    const safe = toSafeBuddyPeerView(rawUser);
    expect(safe.displayName).toBe("Du khách GoMate");
    expect(safe).not.toHaveProperty("email");
    expect(safe).not.toHaveProperty("phone");
    expect(safe).not.toHaveProperty("passwordHash");
    expect(safe).not.toHaveProperty("dateOfBirth");
    expect(safe).not.toHaveProperty("dietaryNeeds");
    expect(safe).not.toHaveProperty("avoidances");
    expect(safe).not.toHaveProperty("budgetMin");
  });

  it("listCandidates returns empty list with isDiscoverable=false when viewer has not opted in", async () => {
    const prisma = makePrismaMock();
    const service = new MatchesService(prisma);

    prisma.user.findUnique.mockResolvedValueOnce({
      id: "u-viewer",
      deletedAt: null,
      profile: { isDiscoverable: false, displayName: "Viewer" },
      preferences: null,
      trips: [],
    });

    const out = await service.listCandidates("u-viewer");
    expect(out.isDiscoverable).toBe(false);
    expect(out.items).toEqual([]);
    expect(prisma.user.findMany).not.toHaveBeenCalled();
  });

  it("enforces two-way blocking (A->B and B->A) on masked profile, sendMatchRequest, and respondToMatch", async () => {
    const prisma = makePrismaMock();
    const service = new MatchesService(prisma);

    // Direction 1: A blocked B -> B cannot view A's masked profile
    prisma.userBlock.findFirst.mockResolvedValueOnce({ id: "blk-1" });
    await expect(
      service.getMaskedPeerProfile("uB", "uA"),
    ).rejects.toBeInstanceOf(ForbiddenException);

    // Direction 2: B blocked A -> A cannot send request to B
    prisma.userBlock.findFirst.mockResolvedValueOnce({ id: "blk-2" });
    await expect(service.sendMatchRequest("uA", "uB")).rejects.toBeInstanceOf(
      ForbiddenException,
    );

    // Block created after PENDING request -> respondToMatch(ACCEPTED) is rejected even if match row was concurrently marked REJECTED
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m-1",
        senderId: "uA",
        receiverId: "uB",
      })
      .mockResolvedValueOnce({
        id: "m-1",
        senderId: "uA",
        receiverId: "uB",
        status: MatchStatus.REJECTED,
        sender: {
          id: "uA",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
        receiver: {
          id: "uB",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
      });
    prisma.userBlock.findFirst.mockResolvedValueOnce({ id: "blk-3" });

    await expect(
      service.respondToMatch("m-1", "uB", "ACCEPTED"),
    ).rejects.toBeInstanceOf(ForbiddenException);
    expect(prisma.match.updateMany).not.toHaveBeenCalled();
  });

  it("blocks self-match, opted-out sender/receiver, and duplicate requests", async () => {
    const prisma = makePrismaMock();
    const service = new MatchesService(prisma);

    await expect(service.sendMatchRequest("u1", "u1")).rejects.toBeInstanceOf(
      BadRequestException,
    );

    // Sender not opted in -> 403
    prisma.user.findUnique
      .mockResolvedValueOnce({
        id: "u1",
        deletedAt: null,
        profile: { isDiscoverable: false },
        preferences: null,
        trips: [],
      })
      .mockResolvedValueOnce({
        id: "u2",
        deletedAt: null,
        email: "b@t.v",
        profile: { isDiscoverable: true },
        preferences: null,
        trips: [],
      });
    await expect(service.sendMatchRequest("u1", "u2")).rejects.toBeInstanceOf(
      ForbiddenException,
    );

    // Receiver not opted in -> 404
    prisma.user.findUnique
      .mockResolvedValueOnce({
        id: "u1",
        deletedAt: null,
        profile: { isDiscoverable: true },
        preferences: null,
        trips: [],
      })
      .mockResolvedValueOnce({
        id: "u2",
        deletedAt: null,
        email: "b@t.v",
        profile: { isDiscoverable: false },
        preferences: null,
        trips: [],
      });
    await expect(service.sendMatchRequest("u1", "u2")).rejects.toBeInstanceOf(
      NotFoundException,
    );

    // Duplicate PENDING request -> 409 Conflict
    prisma.user.findUnique
      .mockResolvedValueOnce({
        id: "u1",
        deletedAt: null,
        profile: { isDiscoverable: true },
        preferences: null,
        trips: [],
      })
      .mockResolvedValueOnce({
        id: "u2",
        deletedAt: null,
        email: "b@t.v",
        profile: { isDiscoverable: true },
        preferences: null,
        trips: [],
      });
    prisma.match.findFirst.mockResolvedValueOnce({
      id: "m1",
      senderId: "u2",
      receiverId: "u1",
      status: MatchStatus.PENDING,
    });

    await expect(service.sendMatchRequest("u1", "u2")).rejects.toBeInstanceOf(
      ConflictException,
    );
  });

  it("withdrawMatchRequest updates conditionally on status=PENDING and throws ConflictException when status changed concurrently", async () => {
    const prisma = makePrismaMock();
    const service = new MatchesService(prisma);

    // 1. Conditional update succeeds when status === PENDING (count === 1)
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.PENDING,
        score: 70,
        explanation: "Cùng sở thích",
        createdAt: new Date(),
        receiver: {
          id: "u2",
          profile: { displayName: "Thu Hà", languages: ["vi"] },
          preferences: { travelStyle: TravelStyle.COMFORT, interests: [] },
        },
      });
    prisma.match.updateMany.mockResolvedValueOnce({ count: 1 });

    const withdrawn = await service.withdrawMatchRequest("m1", "u1");
    expect(withdrawn.status).toBe(MatchStatus.WITHDRAWN);
    expect(withdrawn.handshakeState).toBe("WITHDRAWN");
    expect(withdrawn.isMatched).toBe(false);
    expect(prisma.match.update).not.toHaveBeenCalled();
    expect(prisma.match.updateMany).toHaveBeenCalledWith({
      where: {
        id: "m1",
        senderId: "u1",
        status: MatchStatus.PENDING,
      },
      data: { status: MatchStatus.WITHDRAWN },
    });

    // 2. If status changed to ACCEPTED right before conditional updateMany (count === 0) -> 409 ConflictException
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.PENDING,
        score: 70,
        explanation: "Cùng sở thích",
        createdAt: new Date(),
        receiver: {
          id: "u2",
          profile: { displayName: "Thu Hà", languages: ["vi"] },
          preferences: { travelStyle: TravelStyle.COMFORT, interests: [] },
        },
      })
      .mockResolvedValueOnce({
        status: MatchStatus.ACCEPTED,
      });
    prisma.match.updateMany.mockResolvedValueOnce({ count: 0 });

    await expect(service.withdrawMatchRequest("m1", "u1")).rejects.toThrow(
      new ConflictException(
        "Không thể rút lời mời vì trạng thái đã chuyển sang ACCEPTED",
      ),
    );
  });

  it("prevents MATCHED transition when sender withdraws invitation or disables discovery consent before accept, and handles positive + duplicate accept", async () => {
    const prisma = makePrismaMock();
    const service = new MatchesService(prisma);

    // 1. Receiver tries to accept after WITHDRAWN -> 400 BadRequest
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m1",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.WITHDRAWN,
        sender: {
          id: "u1",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
        receiver: {
          id: "u2",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
      });
    await expect(
      service.respondToMatch("m1", "u2", "ACCEPTED"),
    ).rejects.toBeInstanceOf(BadRequestException);

    // 2. Sender turns off isDiscoverable before receiver accepts -> 409 Conflict (never MATCHED)
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m2",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m2",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.PENDING,
        sender: {
          id: "u1",
          deletedAt: null,
          profile: { isDiscoverable: false },
        },
        receiver: {
          id: "u2",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
      });
    await expect(
      service.respondToMatch("m2", "u2", "ACCEPTED"),
    ).rejects.toBeInstanceOf(ConflictException);

    // 3. Sender cannot self-accept -> 403 Forbidden
    prisma.match.findUnique.mockResolvedValueOnce({
      id: "m3",
      senderId: "u1",
      receiverId: "u2",
    });
    await expect(
      service.respondToMatch("m3", "u1", "ACCEPTED"),
    ).rejects.toBeInstanceOf(ForbiddenException);

    // 4. Positive dual-consent handshake -> ACCEPTED (handshakeState = MATCHED, isMatched = true)
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m3",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m3",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.PENDING,
        score: 75,
        explanation: "Cùng sở thích",
        createdAt: new Date(),
        sender: {
          id: "u1",
          deletedAt: null,
          profile: {
            displayName: "Minh An",
            avatar: null,
            bio: null,
            nationality: "VN",
            languages: ["vi"],
            isDiscoverable: true,
          },
          preferences: {
            travelStyle: TravelStyle.COMFORT,
            interests: ["food_cuisine"],
          },
        },
        receiver: {
          id: "u2",
          deletedAt: null,
          profile: { isDiscoverable: true },
          preferences: null,
        },
      });
    prisma.match.updateMany.mockResolvedValueOnce({ count: 1 });

    const out = await service.respondToMatch("m3", "u2", "ACCEPTED");
    expect(out.status).toBe(MatchStatus.ACCEPTED);
    expect(out.handshakeState).toBe("MATCHED");
    expect(out.isMatched).toBe(true);
    expect(out.peer.displayName).toBe("Minh An");
    expect(out.peer).not.toHaveProperty("email");

    // 5. Duplicate accept on already ACCEPTED match -> 400 BadRequest
    prisma.match.findUnique
      .mockResolvedValueOnce({
        id: "m3",
        senderId: "u1",
        receiverId: "u2",
      })
      .mockResolvedValueOnce({
        id: "m3",
        senderId: "u1",
        receiverId: "u2",
        status: MatchStatus.ACCEPTED,
        sender: {
          id: "u1",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
        receiver: {
          id: "u2",
          deletedAt: null,
          profile: { isDiscoverable: true },
        },
      });
    await expect(
      service.respondToMatch("m3", "u2", "ACCEPTED"),
    ).rejects.toBeInstanceOf(BadRequestException);
  });
});
