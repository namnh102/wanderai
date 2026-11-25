import {
  BadRequestException,
  ExecutionContext,
  ForbiddenException,
  NotFoundException,
  UnauthorizedException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import {
  Prisma,
  YoutubeUpdateScope,
  YoutubeUpdateStatus,
} from "@prisma/client";
import * as crypto from "crypto";
import { YOUTUBE_ERROR_CODES } from "../../common/constants/youtube-error-codes";
import { PrismaService } from "../../prisma/prisma.service";
import { YoutubeInternalSecretGuard } from "./guards/youtube-internal-secret.guard";
import {
  computeYoutubeDedupeKey,
  evaluatePoiGrounding,
  extractVerifiedAliasesFromDescription,
  parseYoutubeAtomFeed,
  VerifiedDestinationCandidate,
  VerifiedPlaceCandidate,
  verifyWebSubSignature,
} from "./youtube-grounding";
import { YoutubeService } from "./youtube.service";

const HA_LONG_DESTINATION: VerifiedDestinationCandidate = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Hạ Long",
  nameEn: "Ha Long",
  slug: "ha-long",
  province: "Quảng Ninh",
  latitude: 20.95,
  longitude: 107.08,
};

const PHU_QUOC_DESTINATION: VerifiedDestinationCandidate = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Phú Quốc",
  nameEn: "Phu Quoc",
  slug: "phu-quoc",
  province: "Kiên Giang",
  latitude: 10.227,
  longitude: 103.957,
};

const THAP_DONG_HO_CANDIDATE: VerifiedPlaceCandidate = {
  id: "65562a67-84ff-44a0-990d-31917a2a9bd0",
  destinationId: HA_LONG_DESTINATION.id,
  name: "Tháp Đồng Hồ",
  nameEn: null,
  address: null,
  latitude: 20.9516105,
  longitude: 107.0851999,
  destinationName: "Hạ Long",
  destinationSlug: "ha-long",
  province: "Quảng Ninh",
  provenanceSources: [
    {
      sourceName: "osm",
      sourceId: "way/674228542",
      canonicalUrl: "https://www.openstreetmap.org/way/674228542",
    },
  ],
  verifiedAliases: extractVerifiedAliasesFromDescription(
    "Tháp Đồng Hồ",
    "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long cạnh Vincom.",
  ),
};

describe("YouTube Update Ingestion, Deduplication & POI Grounding Gate", () => {
  it("extracts verified alias Cột Đồng Hồ and links Tháp Đồng Hồ when corroborated by destination or GPS", () => {
    expect(THAP_DONG_HO_CANDIDATE.verifiedAliases).toContain("Cột Đồng Hồ");

    const byCoords = evaluatePoiGrounding(
      {
        videoId: "ThapDongHo1",
        channelId: "UC_QN_TRAVEL",
        title: "Góc quay flycam Cột Đồng Hồ buổi tối",
        description: "Toàn cảnh vòng xuyến trung tâm rực rỡ ánh đèn",
        tags: ["dulich"],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        latitude: 20.95158,
        longitude: 107.08522,
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(byCoords.status).toBe("LINKED");
    expect(byCoords.placeId).toBe(THAP_DONG_HO_CANDIDATE.id);
    expect(byCoords.groundingBasis).toBe("NAME_AND_COORDINATE_CORROBORATION");

    const byDestinationContext = evaluatePoiGrounding(
      {
        videoId: "ThapDongHo2",
        channelId: "UC_QN_TRAVEL",
        title: "Check-in Tháp Đồng Hồ Hạ Long dịp cuối tuần",
        description: "Đi bộ từ Vincom qua vòng xuyến trung tâm Quảng Ninh.",
        tags: ["halong", "quangninh"],
        publishedAt: new Date("2026-11-24T13:00:00Z"),
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(byDestinationContext.status).toBe("LINKED");
    expect(byDestinationContext.placeId).toBe(THAP_DONG_HO_CANDIDATE.id);
    expect(byDestinationContext.groundingBasis).toBe(
      "UNIQUE_NAME_AND_DESTINATION_CONTEXT",
    );
  });

  it("fails closed when lacking basis: homonym wrong city, name-only, coordinate conflict, or generic city vlog", () => {
    // 1. Homonym in another city (Phú Quốc)
    const wrongCity = evaluatePoiGrounding(
      {
        videoId: "WrongCity01",
        channelId: "UC_PQ_VLOG",
        title: "Check-in Tháp Đồng Hồ Phú Quốc cực đẹp",
        description: "Khám phá Grand World Phú Quốc Kiên Giang",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(wrongCity.status).toBe("UNLINKED_NO_BASIS");
    expect(wrongCity.placeId).toBeNull();
    expect(wrongCity.decisionReason).toBe("conflicting_city_mention");

    // 2. Name-only without any city/destination or GPS corroboration
    const nameOnly = evaluatePoiGrounding(
      {
        videoId: "NameOnly001",
        channelId: "UC_VLOG",
        title: "Đi dạo quanh Tháp Đồng Hồ chiều mưa",
        description: "Một buổi chiều yên bình",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(nameOnly.status).toBe("UNLINKED_NO_BASIS");
    expect(nameOnly.placeId).toBeNull();
    expect(nameOnly.decisionReason).toBe(
      "missing_destination_or_spatial_corroboration",
    );

    // 3. Coordinate contradiction (> 250m away despite matching text)
    const coordConflict = evaluatePoiGrounding(
      {
        videoId: "CoordConf01",
        channelId: "UC_VLOG",
        title: "Tháp Đồng Hồ Hạ Long nhìn từ xa",
        description: "Quay tại Bãi Cháy Hạ Long",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        latitude: 20.95003,
        longitude: 107.0432,
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(coordConflict.status).toBe("UNLINKED_NO_BASIS");
    expect(coordConflict.placeId).toBeNull();
    expect(coordConflict.decisionReason).toBe("coordinate_conflict_with_poi");

    // 4. Generic Ha Long vlog with no POI mention
    const genericCity = evaluatePoiGrounding(
      {
        videoId: "GenericHL01",
        channelId: "UC_VLOG",
        title: "Ăn hải sản Hạ Long 2 ngày 1 đêm",
        description: "Kinh nghiệm đi du lịch tự túc Quảng Ninh",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
      },
      [THAP_DONG_HO_CANDIDATE],
    );
    expect(genericCity.status).toBe("UNLINKED_NO_BASIS");
    expect(genericCity.placeId).toBeNull();
    expect(genericCity.decisionReason).toBe("no_poi_name_or_coordinate_match");
  });

  it("parses YouTube WebSub Atom XML, rejects XXE, and verifies HMAC X-Hub-Signature", () => {
    const atomXml = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom" xmlns:georss="http://www.georss.org/georss">
  <entry>
    <id>yt:video:AbCdEfGhIjK</id>
    <yt:videoId>AbCdEfGhIjK</yt:videoId>
    <yt:channelId>UC1234567890</yt:channelId>
    <title>Tháp Đồng Hồ &amp; trung tâm Hạ Long</title>
    <author><name>Hạ Long 360</name></author>
    <published>2026-11-24T20:00:00+07:00</published>
    <updated>2026-11-24T20:05:00+07:00</updated>
    <georss:point>20.95161 107.08520</georss:point>
  </entry>
</feed>`;

    const entries = parseYoutubeAtomFeed(atomXml);
    expect(entries).toHaveLength(1);
    expect(entries[0].videoId).toBe("AbCdEfGhIjK");
    expect(entries[0].title).toBe("Tháp Đồng Hồ & trung tâm Hạ Long");
    expect(entries[0].publishedAt.toISOString()).toBe(
      "2026-11-24T13:00:00.000Z",
    );
    expect(entries[0].sourceUpdatedAt?.toISOString()).toBe(
      "2026-11-24T13:05:00.000Z",
    );
    expect(entries[0].latitude).toBeCloseTo(20.95161, 5);

    const secret = "websub-unit-secret";
    const validHex = crypto
      .createHmac("sha256", secret)
      .update(atomXml, "utf8")
      .digest("hex");
    const validSig = `sha256=${validHex}`;
    expect(() =>
      verifyWebSubSignature(atomXml, validSig, secret),
    ).not.toThrow();
    expect(() =>
      verifyWebSubSignature(atomXml, "sha256=deadbeef", secret),
    ).toThrow(UnauthorizedException);
    for (const malformedSig of [
      `sha256=${validHex}=tampered`,
      "sha256=",
      "sha256=zzzz",
      `md5=${validHex}`,
    ]) {
      expect(() =>
        verifyWebSubSignature(atomXml, malformedSig, secret),
      ).toThrow(UnauthorizedException);
    }
    expect(() =>
      parseYoutubeAtomFeed(
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><feed/>',
      ),
    ).toThrow(BadRequestException);
  });

  it("deduplicates repeated deliveries (including P2002 race) while preserving original publishedAt & receivedAt", async () => {
    const firstReceived = new Date("2026-11-24T14:00:00.000Z");
    const published = new Date("2026-11-24T13:30:00.000Z");
    const dedupeKey = computeYoutubeDedupeKey({
      videoId: "DupVideo001",
      publishedAt: published,
      sourceUpdatedAt: null,
    });

    const storedRow = {
      id: "row-1",
      dedupeKey,
      videoId: "DupVideo001",
      channelId: "UC_HL",
      channelTitle: "Hạ Long TV",
      videoUrl: "https://www.youtube.com/watch?v=DupVideo001",
      title: "Tháp Đồng Hồ Hạ Long nhìn từ trên cao",
      description: null,
      tags: [],
      latitude: null,
      longitude: null,
      publishedAt: published,
      sourceUpdatedAt: null,
      receivedAt: firstReceived,
      lastReceivedAt: firstReceived,
      deliveryCount: 1,
      status: YoutubeUpdateStatus.LINKED,
      scope: YoutubeUpdateScope.POI,
      placeId: THAP_DONG_HO_CANDIDATE.id,
      destinationId: HA_LONG_DESTINATION.id,
      groundingBasis: "UNIQUE_NAME_AND_DESTINATION_CONTEXT",
      decisionReason: "verified_poi_grounding_passed",
      groundingEvidence: {},
      rawPayload: {},
    };

    const findUnique = jest
      .fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(storedRow)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(storedRow);
    const create = jest
      .fn()
      .mockResolvedValueOnce(storedRow)
      .mockRejectedValueOnce(
        new Prisma.PrismaClientKnownRequestError("Unique constraint failed", {
          code: "P2002",
          clientVersion: "5.0.0",
        }),
      );
    const update = jest.fn().mockImplementation(async ({ data }) => ({
      ...storedRow,
      deliveryCount: storedRow.deliveryCount + 1,
      lastReceivedAt: data.lastReceivedAt,
    }));

    const mockPrisma = {
      place: {
        findMany: jest.fn().mockResolvedValue([
          {
            id: THAP_DONG_HO_CANDIDATE.id,
            destinationId: HA_LONG_DESTINATION.id,
            name: THAP_DONG_HO_CANDIDATE.name,
            nameEn: null,
            description:
              "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long.",
            latitude: THAP_DONG_HO_CANDIDATE.latitude,
            longitude: THAP_DONG_HO_CANDIDATE.longitude,
            destination: {
              id: HA_LONG_DESTINATION.id,
              name: "Hạ Long",
              slug: "ha-long",
              province: "Quảng Ninh",
            },
            placeSources: [
              {
                sourceName: "osm",
                sourceId: "way/674228542",
                rawData: {},
              },
            ],
          },
        ]),
      },
      destination: {
        findMany: jest.fn().mockResolvedValue([HA_LONG_DESTINATION]),
      },
      youtubePoiUpdate: {
        findUnique,
        create,
        update,
      },
    } as unknown as PrismaService;

    const mockConfig = {
      get: jest.fn((key: string) =>
        key === "YOUTUBE_WEBSUB_VERIFY_TOKEN" ? "expected-token" : undefined,
      ),
    } as unknown as ConfigService;

    const service = new YoutubeService(mockPrisma, mockConfig);

    expect(() =>
      service.verifyWebSubHandshake({
        "hub.mode": "subscribe",
        "hub.topic":
          "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC_HL",
        "hub.challenge": "challenge-123",
        "hub.verify_token": "wrong-token",
      }),
    ).toThrow(ForbiddenException);

    const r1 = await service.ingestJsonEvent({
      videoId: "DupVideo001",
      channelId: "UC_HL",
      title: "Tháp Đồng Hồ Hạ Long nhìn từ trên cao",
      publishedAt: "2026-11-24T13:30:00Z",
    });
    expect(r1.duplicate).toBe(false);
    expect(r1.deliveryCount).toBe(1);
    expect(r1.linkedPlaceId).toBe(THAP_DONG_HO_CANDIDATE.id);

    // Sequential duplicate
    const r2 = await service.ingestJsonEvent({
      videoId: "DupVideo001",
      channelId: "UC_HL",
      title: "Tháp Đồng Hồ Hạ Long nhìn từ trên cao",
      publishedAt: "2026-11-24T13:30:00Z",
    });
    expect(r2.duplicate).toBe(true);
    expect(r2.deliveryCount).toBe(2);
    expect(r2.publishedAt).toBe(r1.publishedAt);
    expect(r2.receivedAt).toBe(r1.receivedAt);

    // Concurrent race hitting P2002 unique constraint
    const r3 = await service.ingestJsonEvent({
      videoId: "DupVideo001",
      channelId: "UC_HL",
      title: "Tháp Đồng Hồ Hạ Long nhìn từ trên cao",
      publishedAt: "2026-11-24T13:30:00Z",
    });
    expect(r3.duplicate).toBe(true);
    expect(r3.receivedAt).toBe(r1.receivedAt);
    expect(new Date(r3.lastReceivedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(r3.receivedAt).getTime(),
    );
  });

  it("prevents concurrent P2002 race inversion so lastReceivedAt >= receivedAt and updatedAt >= receivedAt", async () => {
    const rows = new Map<string, Record<string, unknown>>();
    let candidateCalls = 0;
    let releaseFirstRequest!: () => void;
    const firstRequestPaused = new Promise<void>((resolve) => {
      releaseFirstRequest = resolve;
    });
    let firstRequestEnteredLoad!: () => void;
    const firstEnteredPromise = new Promise<void>((resolve) => {
      firstRequestEnteredLoad = resolve;
    });

    const mockPrisma = {
      place: {
        findMany: jest.fn().mockImplementation(async () => {
          candidateCalls += 1;
          if (candidateCalls === 1) {
            firstRequestEnteredLoad();
            await firstRequestPaused;
          }
          return [
            {
              id: THAP_DONG_HO_CANDIDATE.id,
              destinationId: HA_LONG_DESTINATION.id,
              name: THAP_DONG_HO_CANDIDATE.name,
              nameEn: null,
              description:
                "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long.",
              latitude: THAP_DONG_HO_CANDIDATE.latitude,
              longitude: THAP_DONG_HO_CANDIDATE.longitude,
              destination: {
                id: HA_LONG_DESTINATION.id,
                name: "Hạ Long",
                slug: "ha-long",
                province: "Quảng Ninh",
              },
              placeSources: [
                {
                  sourceName: "osm",
                  sourceId: "way/674228542",
                  rawData: {},
                },
              ],
            },
          ];
        }),
        findUnique: jest.fn().mockResolvedValue({
          id: THAP_DONG_HO_CANDIDATE.id,
          name: "Tháp Đồng Hồ",
          deletedAt: null,
          destinationId: HA_LONG_DESTINATION.id,
          destination: {
            id: HA_LONG_DESTINATION.id,
            slug: "ha-long",
            name: "Hạ Long",
          },
          _count: { placeSources: 1 },
        }),
      },
      destination: {
        findMany: jest.fn().mockResolvedValue([HA_LONG_DESTINATION]),
      },
      youtubePoiUpdate: {
        findUnique: jest.fn().mockImplementation(async ({ where }) => {
          return rows.get(where.dedupeKey) ?? null;
        }),
        create: jest.fn().mockImplementation(async ({ data }) => {
          if (rows.has(data.dedupeKey)) {
            throw new Prisma.PrismaClientKnownRequestError(
              "Unique constraint failed",
              { code: "P2002", clientVersion: "5.0.0" },
            );
          }
          const created = { id: "race-row-1", ...data };
          rows.set(data.dedupeKey, created);
          return created;
        }),
        update: jest
          .fn()
          .mockImplementation(async ({ where, data }) => {
            const current = rows.get(where.dedupeKey) as {
              deliveryCount: number;
              lastReceivedAt: Date;
            };
            const updated = {
              ...current,
              deliveryCount:
                current.deliveryCount + (data.deliveryCount?.increment ?? 0),
              lastReceivedAt: data.lastReceivedAt,
            };
            rows.set(where.dedupeKey, updated);
            return updated;
          }),
        findMany: jest.fn().mockImplementation(async ({ where }) => {
          if (where.placeId === THAP_DONG_HO_CANDIDATE.id) {
            return [...rows.values()];
          }
          return [];
        }),
      },
    } as unknown as PrismaService;

    const mockConfig = {
      get: jest.fn(() => undefined),
    } as unknown as ConfigService;

    const service = new YoutubeService(mockPrisma, mockConfig);
    const eventPayload = {
      videoId: "RaceInv0001",
      channelId: "UC_HL_RACE",
      title: "Tháp Đồng Hồ Hạ Long buổi tối",
      publishedAt: "2026-11-24T12:00:00.000Z",
    };

    // Request A enters at T1 and pauses after findUnique miss
    const reqAPromise = service.ingestJsonEvent(eventPayload);
    await firstEnteredPromise;

    // Advance clock >= 15ms so Request B enters at T2 > T1 and wins create()
    await new Promise((r) => setTimeout(r, 15));
    const reqBReceipt = await service.ingestJsonEvent(eventPayload);
    expect(reqBReceipt.duplicate).toBe(false);

    // Unblock Request A so it hits P2002 and recovers
    releaseFirstRequest();
    const reqAReceipt = await reqAPromise;
    expect(reqAReceipt.duplicate).toBe(true);
    expect(reqAReceipt.deliveryCount).toBe(2);
    expect(reqAReceipt.receivedAt).toBe(reqBReceipt.receivedAt);
    expect(new Date(reqAReceipt.lastReceivedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(reqAReceipt.receivedAt).getTime(),
    );

    const feed = await service.listGroundedUpdatesForPlace(
      THAP_DONG_HO_CANDIDATE.id,
      10,
    );
    expect(feed.items).toHaveLength(1);
    const item = feed.items[0];
    expect(item.deliveryLagMs).toBeGreaterThanOrEqual(item.ingestLatencyMs);
    expect(new Date(item.updatedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(item.receivedAt).getTime(),
    );
  });

  it("supports Hạ Long city-level fallback while keeping POI conflict gates fail-closed", () => {
    const destinations = [HA_LONG_DESTINATION, PHU_QUOC_DESTINATION];

    // Generic Hạ Long vlog -> LINKED_CITY
    const cityFallback = evaluatePoiGrounding(
      {
        videoId: "GenericHL02",
        channelId: "UC_HL_FOOD",
        title: "Ăn hải sản Hạ Long 2 ngày 1 đêm",
        description: "Kinh nghiệm du lịch tự túc Quảng Ninh",
        tags: ["halong"],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        latitude: 20.955,
        longitude: 107.09,
      },
      [THAP_DONG_HO_CANDIDATE],
      destinations,
    );
    expect(cityFallback.status).toBe("LINKED_CITY");
    expect(cityFallback.scope).toBe("CITY");
    expect(cityFallback.placeId).toBeNull();
    expect(cityFallback.destinationId).toBe(HA_LONG_DESTINATION.id);
    expect(cityFallback.groundingBasis).toBe(
      "UNIQUE_DESTINATION_CONTEXT_FALLBACK",
    );
    expect(cityFallback.decisionReason).toBe(
      "verified_destination_city_fallback_passed",
    );

    // Multi-city conflict fails closed
    const multiCity = evaluatePoiGrounding(
      {
        videoId: "MultiCity01",
        channelId: "UC_TRAVEL",
        title: "So sánh du lịch Hạ Long và Phú Quốc",
        description: "Hành trình từ Quảng Ninh tới Kiên Giang",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
      },
      [THAP_DONG_HO_CANDIDATE],
      destinations,
    );
    expect(multiCity.status).toBe("UNLINKED_NO_BASIS");
    expect(multiCity.scope).toBe("NONE");
    expect(multiCity.destinationId).toBeNull();
    expect(multiCity.decisionReason).toBe("conflicting_city_mention");

    // Destination coordinate conflict (> 50km) fails closed
    const farCoords = evaluatePoiGrounding(
      {
        videoId: "CityFar0001",
        channelId: "UC_TRAVEL",
        title: "Kinh nghiệm du lịch Hạ Long",
        description: "Gắn nhầm tọa độ GPS cách trung tâm hơn 50km",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        latitude: 21.0285,
        longitude: 105.8542,
      },
      [THAP_DONG_HO_CANDIDATE],
      destinations,
    );
    expect(farCoords.status).toBe("UNLINKED_NO_BASIS");
    expect(farCoords.scope).toBe("NONE");
    expect(farCoords.destinationId).toBeNull();
    expect(farCoords.decisionReason).toBe("coordinate_conflict_with_destination");

    // Existing POI coordinate conflict must NOT fall back to LINKED_CITY
    const poiCoordConflict = evaluatePoiGrounding(
      {
        videoId: "TDHBadCoord",
        channelId: "UC_VLOG",
        title: "Tháp Đồng Hồ Hạ Long",
        description: "Quay tại đảo Tuần Châu",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        latitude: 20.91656,
        longitude: 106.98958,
      },
      [THAP_DONG_HO_CANDIDATE],
      destinations,
    );
    expect(poiCoordConflict.status).toBe("UNLINKED_NO_BASIS");
    expect(poiCoordConflict.scope).toBe("NONE");
    expect(poiCoordConflict.decisionReason).toBe("coordinate_conflict_with_poi");

    // Existing unverified candidatePlaceId must NOT fall back to LINKED_CITY
    const unverifiedTarget = evaluatePoiGrounding(
      {
        videoId: "TDHUnverif1",
        channelId: "UC_VLOG",
        title: "Địa điểm chưa xác minh tại Hạ Long",
        tags: [],
        publishedAt: new Date("2026-11-24T12:00:00Z"),
        candidatePlaceId: "99999999-9999-4999-8999-999999999999",
      },
      [THAP_DONG_HO_CANDIDATE],
      destinations,
    );
    expect(unverifiedTarget.status).toBe("UNLINKED_NO_BASIS");
    expect(unverifiedTarget.scope).toBe("NONE");
    expect(unverifiedTarget.decisionReason).toBe(
      "target_place_unverified_or_missing",
    );
  });

  it("serializes 5-field contract, latency metrics, cityFallbackItems, and throws canonical errorCodes on 404", async () => {
    const published = new Date("2026-11-24T12:00:00.000Z");
    const sourceUpdated = new Date("2026-11-24T12:00:05.000Z");
    const received = new Date("2026-11-24T12:00:12.000Z");
    const lastReceived = new Date("2026-11-24T12:01:00.000Z");

    const poiRow = {
      id: "poi-row-1",
      dedupeKey: "yt:video:PoiItem0001:2026-11-24T12:00:05.000Z",
      videoId: "PoiItem0001",
      channelId: "UC_HL",
      channelTitle: "Hạ Long TV",
      videoUrl: "https://www.youtube.com/watch?v=PoiItem0001",
      title: "Tháp Đồng Hồ Hạ Long",
      description: "Check-in buổi tối",
      tags: ["halong"],
      latitude: 20.95161,
      longitude: 107.0852,
      publishedAt: published,
      sourceUpdatedAt: sourceUpdated,
      receivedAt: received,
      lastReceivedAt: lastReceived,
      deliveryCount: 2,
      status: YoutubeUpdateStatus.LINKED,
      scope: YoutubeUpdateScope.POI,
      placeId: THAP_DONG_HO_CANDIDATE.id,
      destinationId: HA_LONG_DESTINATION.id,
      groundingBasis: "NAME_AND_COORDINATE_CORROBORATION",
      decisionReason: "verified_poi_grounding_passed",
      groundingEvidence: {},
      rawPayload: {},
    };

    const cityRow = {
      ...poiRow,
      id: "city-row-1",
      dedupeKey: "yt:video:CityItem001:2026-11-24T12:00:00.000Z",
      videoId: "CityItem001",
      videoUrl: "https://www.youtube.com/watch?v=CityItem001",
      title: "Ẩm thực Hạ Long",
      sourceUpdatedAt: null,
      status: YoutubeUpdateStatus.LINKED_CITY,
      scope: YoutubeUpdateScope.CITY,
      placeId: null,
      groundingBasis: "UNIQUE_DESTINATION_CONTEXT_FALLBACK",
      decisionReason: "verified_destination_city_fallback_passed",
    };

    const mockPrisma = {
      place: {
        findUnique: jest.fn().mockResolvedValue({
          id: THAP_DONG_HO_CANDIDATE.id,
          name: "Tháp Đồng Hồ",
          deletedAt: null,
          destinationId: HA_LONG_DESTINATION.id,
          destination: {
            id: HA_LONG_DESTINATION.id,
            slug: "ha-long",
            name: "Hạ Long",
          },
          _count: { placeSources: 1 },
        }),
      },
      destination: {
        findUnique: jest.fn().mockResolvedValue(null),
      },
      youtubePoiUpdate: {
        findMany: jest
          .fn()
          .mockResolvedValueOnce([poiRow])
          .mockResolvedValueOnce([cityRow]),
      },
    } as unknown as PrismaService;

    const mockConfig = {
      get: jest.fn((key: string) =>
        key === "YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS" ? "300000" : undefined,
      ),
    } as unknown as ConfigService;

    const service = new YoutubeService(mockPrisma, mockConfig);
    const placeFeed = await service.listGroundedUpdatesForPlace(
      THAP_DONG_HO_CANDIDATE.id,
      10,
    );

    expect(placeFeed.destinationId).toBe(HA_LONG_DESTINATION.id);
    expect(placeFeed.destinationSlug).toBe("ha-long");
    expect(placeFeed.destinationName).toBe("Hạ Long");
    expect(placeFeed.realtimeSlaMaxLatencyMs).toBe(300000);
    expect(placeFeed.serverDeliveredAt).toBeTruthy();
    expect(placeFeed.total).toBe(1);
    expect(placeFeed.cityFallbackTotal).toBe(1);

    const item = placeFeed.items[0];
    expect(item.placeId).toBe(THAP_DONG_HO_CANDIDATE.id);
    expect(item.source).toBe("youtube");
    expect(item.publishedAt).toBe("2026-11-24T12:00:00.000Z");
    expect(item.receivedAt).toBe("2026-11-24T12:00:12.000Z");
    expect(item.updatedAt).toBe("2026-11-24T12:00:05.000Z");
    expect(item.ingestLatencyMs).toBe(12000);
    expect(item.deliveryLagMs).toBe(60000);
    expect(item.scope).toBe("POI");

    const cityItem = placeFeed.cityFallbackItems[0];
    expect(cityItem.placeId).toBeNull();
    expect(cityItem.source).toBe("youtube");
    expect(cityItem.scope).toBe("CITY");
    expect(cityItem.updatedAt).toBe("2026-11-24T12:01:00.000Z");

    await expect(
      service.listGroundedUpdatesForDestination("unknown-slug", 10),
    ).rejects.toThrow(NotFoundException);
  });

  it("passes sourceUpdatedAt nulls: 'last' orderBy and ranks non-null sourceUpdatedAt ahead of null when publishedAt ties", async () => {
    const tiedPublishedAt = new Date("2026-11-24T12:00:00.000Z");
    type SortableYoutubeRow = {
      id: string;
      dedupeKey: string;
      source: string;
      channelId: string;
      channelTitle: string | null;
      videoId: string;
      videoUrl: string;
      title: string;
      description: string | null;
      tags: string[];
      latitude: number | null;
      longitude: number | null;
      publishedAt: Date;
      sourceUpdatedAt: Date | null;
      receivedAt: Date;
      lastReceivedAt: Date;
      deliveryCount: number;
      status: YoutubeUpdateStatus;
      scope: YoutubeUpdateScope;
      placeId: string | null;
      destinationId: string | null;
      groundingBasis: string | null;
      decisionReason: string;
      groundingEvidence: Record<string, unknown>;
      rawPayload: Record<string, unknown>;
    };

    const rowWithNullSourceUpdatedAt: SortableYoutubeRow = {
      id: "poi-null-source-updated",
      dedupeKey: "yt:video:NullUpdated01:2026-11-24T12:00:00.000Z",
      source: "youtube",
      channelId: "UCtest01",
      channelTitle: "Halong Vlogs",
      videoId: "NullUpdated01",
      videoUrl: "https://www.youtube.com/watch?v=NullUpdated01",
      title: "Tháp Đồng Hồ không có sourceUpdatedAt",
      description: "Tháp Đồng Hồ",
      tags: ["Ha Long"],
      latitude: 20.9516105,
      longitude: 107.0851999,
      publishedAt: tiedPublishedAt,
      sourceUpdatedAt: null,
      receivedAt: new Date("2026-11-24T12:00:50.000Z"),
      lastReceivedAt: new Date("2026-11-24T12:00:50.000Z"),
      deliveryCount: 1,
      status: YoutubeUpdateStatus.LINKED,
      scope: YoutubeUpdateScope.POI,
      placeId: THAP_DONG_HO_CANDIDATE.id,
      destinationId: HA_LONG_DESTINATION.id,
      groundingBasis: "NAME_AND_COORDINATE_CORROBORATION",
      decisionReason: "verified_poi_grounding_passed",
      groundingEvidence: {},
      rawPayload: {},
    };

    const rowWithSourceUpdatedAt: SortableYoutubeRow = {
      ...rowWithNullSourceUpdatedAt,
      id: "poi-with-source-updated",
      dedupeKey: "yt:video:WithUpdated01:2026-11-24T12:00:00.000Z",
      videoId: "WithUpdated01",
      videoUrl: "https://www.youtube.com/watch?v=WithUpdated01",
      title: "Tháp Đồng Hồ có sourceUpdatedAt",
      sourceUpdatedAt: new Date("2026-11-24T12:00:10.000Z"),
      receivedAt: new Date("2026-11-24T12:00:15.000Z"),
      lastReceivedAt: new Date("2026-11-24T12:00:15.000Z"),
    };

    const cityWithNull: SortableYoutubeRow = {
      ...rowWithNullSourceUpdatedAt,
      id: "city-null-source-updated",
      dedupeKey: "yt:video:CityNull01:2026-11-24T12:00:00.000Z",
      videoId: "CityNull01",
      videoUrl: "https://www.youtube.com/watch?v=CityNull01",
      status: YoutubeUpdateStatus.LINKED_CITY,
      scope: YoutubeUpdateScope.CITY,
      placeId: null,
    };

    const cityWithUpdated: SortableYoutubeRow = {
      ...rowWithSourceUpdatedAt,
      id: "city-with-source-updated",
      dedupeKey: "yt:video:CityUpdated01:2026-11-24T12:00:00.000Z",
      videoId: "CityUpdated01",
      videoUrl: "https://www.youtube.com/watch?v=CityUpdated01",
      status: YoutubeUpdateStatus.LINKED_CITY,
      scope: YoutubeUpdateScope.CITY,
      placeId: null,
    };

    const sortByPrismaOrderBy = (
      rows: SortableYoutubeRow[],
      orderBy: Array<Record<string, unknown>>,
    ) => {
      return [...rows].sort((a, b) => {
        for (const clause of orderBy) {
          if ("publishedAt" in clause) {
            const diff = b.publishedAt.getTime() - a.publishedAt.getTime();
            if (diff !== 0) return diff;
          }
          if ("sourceUpdatedAt" in clause) {
            const spec = clause.sourceUpdatedAt as
              | "desc"
              | { sort: "desc"; nulls?: "first" | "last" };
            const aNull = a.sourceUpdatedAt === null;
            const bNull = b.sourceUpdatedAt === null;
            if (aNull !== bNull) {
              if (typeof spec === "object" && spec.nulls === "last") {
                return aNull ? 1 : -1;
              }
              return aNull ? -1 : 1;
            }
            if (a.sourceUpdatedAt && b.sourceUpdatedAt) {
              const diff =
                b.sourceUpdatedAt.getTime() - a.sourceUpdatedAt.getTime();
              if (diff !== 0) return diff;
            }
          }
          if ("receivedAt" in clause) {
            const diff = b.receivedAt.getTime() - a.receivedAt.getTime();
            if (diff !== 0) return diff;
          }
        }
        return 0;
      });
    };

    const findManyMock = jest.fn(
      async (args: {
        where: { scope?: unknown };
        orderBy: Array<Record<string, unknown>>;
      }) => {
        const isCityOnly = args.where.scope === YoutubeUpdateScope.CITY;
        const pool = isCityOnly
          ? [cityWithNull, cityWithUpdated]
          : [rowWithNullSourceUpdatedAt, rowWithSourceUpdatedAt];
        return sortByPrismaOrderBy(pool, args.orderBy);
      },
    );

    const mockPrisma = {
      place: {
        findUnique: jest.fn().mockResolvedValue({
          id: THAP_DONG_HO_CANDIDATE.id,
          name: "Tháp Đồng Hồ",
          deletedAt: null,
          destinationId: HA_LONG_DESTINATION.id,
          destination: {
            id: HA_LONG_DESTINATION.id,
            slug: "ha-long",
            name: "Hạ Long",
          },
          _count: { placeSources: 1 },
        }),
      },
      destination: {
        findUnique: jest.fn().mockResolvedValue({
          id: HA_LONG_DESTINATION.id,
          name: "Hạ Long",
          slug: "ha-long",
          deletedAt: null,
        }),
      },
      youtubePoiUpdate: {
        findMany: findManyMock,
      },
    } as unknown as PrismaService;

    const mockConfig = {
      get: jest.fn(() => undefined),
    } as unknown as ConfigService;

    const service = new YoutubeService(mockPrisma, mockConfig);
    const placeFeed = await service.listGroundedUpdatesForPlace(
      THAP_DONG_HO_CANDIDATE.id,
      10,
    );
    const destFeed = await service.listGroundedUpdatesForDestination(
      "ha-long",
      10,
    );

    expect(findManyMock).toHaveBeenCalledTimes(4);
    for (const call of findManyMock.mock.calls) {
      expect(call[0].orderBy).toEqual([
        { publishedAt: "desc" },
        { sourceUpdatedAt: { sort: "desc", nulls: "last" } },
        { receivedAt: "desc" },
      ]);
    }

    expect(placeFeed.items.map((item) => item.videoId)).toEqual([
      "WithUpdated01",
      "NullUpdated01",
    ]);
    expect(placeFeed.cityFallbackItems.map((item) => item.videoId)).toEqual([
      "CityUpdated01",
      "CityNull01",
    ]);
    expect(destFeed.items.map((item) => item.videoId)).toEqual([
      "WithUpdated01",
      "NullUpdated01",
    ]);
    expect(destFeed.cityFallbackItems.map((item) => item.videoId)).toEqual([
      "CityUpdated01",
      "CityNull01",
    ]);
  });

  it("enforces YoutubeInternalSecretGuard using timingSafeEqual when configured", () => {
    const makeCtx = (headers: Record<string, string | undefined>) =>
      ({
        switchToHttp: () => ({
          getRequest: () => ({ headers }),
        }),
      }) as unknown as ExecutionContext;

    const openGuard = new YoutubeInternalSecretGuard({
      get: () => "",
    } as unknown as ConfigService);
    expect(openGuard.canActivate(makeCtx({}))).toBe(true);

    const strictGuard = new YoutubeInternalSecretGuard({
      get: (k: string) =>
        k === "YOUTUBE_EVENTS_INTERNAL_SECRET" ? "super-secret-token" : "",
    } as unknown as ConfigService);

    expect(
      strictGuard.canActivate(
        makeCtx({ "x-youtube-internal-secret": "super-secret-token" }),
      ),
    ).toBe(true);

    try {
      strictGuard.canActivate(
        makeCtx({ "x-youtube-internal-secret": "wrong-token" }),
      );
      fail("Expected UnauthorizedException");
    } catch (err) {
      expect(err).toBeInstanceOf(UnauthorizedException);
      const response = (err as UnauthorizedException).getResponse() as {
        errorCode?: string;
      };
      expect(response.errorCode).toBe(
        YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
      );
    }
  });
});
