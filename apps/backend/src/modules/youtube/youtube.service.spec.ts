import {
  BadRequestException,
  ForbiddenException,
  UnauthorizedException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { Prisma, YoutubeUpdateStatus } from "@prisma/client";
import * as crypto from "crypto";
import { PrismaService } from "../../prisma/prisma.service";
import {
  computeYoutubeDedupeKey,
  evaluatePoiGrounding,
  extractVerifiedAliasesFromDescription,
  parseYoutubeAtomFeed,
  VerifiedPlaceCandidate,
  verifyWebSubSignature,
} from "./youtube-grounding";
import { YoutubeService } from "./youtube.service";

const THAP_DONG_HO_CANDIDATE: VerifiedPlaceCandidate = {
  id: "65562a67-84ff-44a0-990d-31917a2a9bd0",
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
    const validSig =
      "sha256=" +
      crypto.createHmac("sha256", secret).update(atomXml, "utf8").digest("hex");
    expect(() =>
      verifyWebSubSignature(atomXml, validSig, secret),
    ).not.toThrow();
    expect(() =>
      verifyWebSubSignature(atomXml, "sha256=deadbeef", secret),
    ).toThrow(UnauthorizedException);
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
      placeId: THAP_DONG_HO_CANDIDATE.id,
      groundingBasis: "UNIQUE_NAME_AND_DESTINATION_CONTEXT",
      decisionReason: "verified_poi_grounding_passed",
      groundingEvidence: {},
      rawPayload: {},
    };

    const findUnique = jest
      .fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(storedRow)
      .mockResolvedValueOnce(null);
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
            name: THAP_DONG_HO_CANDIDATE.name,
            nameEn: null,
            description:
              "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long.",
            latitude: THAP_DONG_HO_CANDIDATE.latitude,
            longitude: THAP_DONG_HO_CANDIDATE.longitude,
            destination: {
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
  });
});
