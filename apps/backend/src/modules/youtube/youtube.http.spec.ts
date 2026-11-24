import { INestApplication, ValidationPipe } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { Test, TestingModule } from "@nestjs/testing";
import {
  Prisma,
  YoutubeUpdateScope,
  YoutubeUpdateStatus,
} from "@prisma/client";
import * as crypto from "crypto";
import * as request from "supertest";
import { YOUTUBE_ERROR_CODES } from "../../common/constants/youtube-error-codes";
import { HttpExceptionFilter } from "../../common/filters/http-exception.filter";
import { TransformInterceptor } from "../../common/interceptors/transform.interceptor";
import { PrismaModule } from "../../prisma/prisma.module";
import { PrismaService } from "../../prisma/prisma.service";
import { YoutubeModule } from "./youtube.module";

const HA_LONG_DEST_ID = "11111111-1111-4111-8111-111111111111";
const PHU_QUOC_DEST_ID = "22222222-2222-4222-8222-222222222222";
const THAP_DONG_HO_ID = "65562a67-84ff-44a0-990d-31917a2a9bd0";
const UNSOURCED_PLACE_ID = "77777777-7777-4777-8777-777777777777";
const MISSING_PLACE_ID = "88888888-8888-4888-8888-888888888888";

const TEST_INTERNAL_SECRET = "test-youtube-internal-secret";
const TEST_WEBSUB_SECRET = "test-youtube-websub-secret";
const TEST_VERIFY_TOKEN = "test-youtube-verify-token";

interface StoredDestination {
  id: string;
  name: string;
  nameEn: string | null;
  slug: string;
  province: string | null;
  latitude: number | null;
  longitude: number | null;
  deletedAt: Date | null;
}

interface StoredPlace {
  id: string;
  destinationId: string;
  name: string;
  nameEn: string | null;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  deletedAt: Date | null;
  placeSources: Array<{
    sourceName: string;
    sourceId: string;
    rawData: Record<string, unknown>;
  }>;
}

interface StoredYoutubeUpdate {
  id: string;
  dedupeKey: string;
  videoId: string;
  channelId: string;
  channelTitle: string | null;
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
  groundingEvidence: unknown;
  rawPayload: unknown;
}

class InMemoryYoutubePrisma {
  private destinations: StoredDestination[] = [];
  private places: StoredPlace[] = [];
  private updates: StoredYoutubeUpdate[] = [];
  private seq = 1;
  public simulateFindUniqueMissOnce = false;

  reset(): void {
    this.seq = 1;
    this.simulateFindUniqueMissOnce = false;
    this.destinations = [
      {
        id: HA_LONG_DEST_ID,
        name: "Hạ Long",
        nameEn: "Ha Long",
        slug: "ha-long",
        province: "Quảng Ninh",
        latitude: 20.95,
        longitude: 107.08,
        deletedAt: null,
      },
      {
        id: PHU_QUOC_DEST_ID,
        name: "Phú Quốc",
        nameEn: "Phu Quoc",
        slug: "phu-quoc",
        province: "Kiên Giang",
        latitude: 10.227,
        longitude: 103.957,
        deletedAt: null,
      },
    ];

    this.places = [
      {
        id: THAP_DONG_HO_ID,
        destinationId: HA_LONG_DEST_ID,
        name: "Tháp Đồng Hồ",
        nameEn: null,
        description:
          "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long cạnh Vincom.",
        latitude: 20.9516105,
        longitude: 107.0851999,
        deletedAt: null,
        placeSources: [
          {
            sourceName: "osm",
            sourceId: "way/674228542",
            rawData: {
              tags: {
                name: "Tháp Đồng Hồ",
                amenity: "clock",
              },
            },
          },
        ],
      },
      {
        id: UNSOURCED_PLACE_ID,
        destinationId: HA_LONG_DEST_ID,
        name: "Địa điểm chưa xác minh nguồn",
        nameEn: null,
        description: null,
        latitude: 20.952,
        longitude: 107.086,
        deletedAt: null,
        placeSources: [],
      },
    ];
    this.updates = [];
  }

  getAllUpdates(): StoredYoutubeUpdate[] {
    return [...this.updates];
  }

  destination = {
    findMany: async ({
      where,
    }: {
      where?: { deletedAt?: null };
    } = {}) => {
      return this.destinations.filter((d) =>
        where?.deletedAt === null ? d.deletedAt === null : true,
      );
    },
    findUnique: async ({
      where,
    }: {
      where: { id?: string; slug?: string };
    }) => {
      return (
        this.destinations.find(
          (d) =>
            (where.id && d.id === where.id) ||
            (where.slug && d.slug === where.slug),
        ) ?? null
      );
    },
  };

  place = {
    findMany: async () => {
      return this.places
        .filter((p) => p.deletedAt === null && p.placeSources.length > 0)
        .map((p) => {
          const dest = this.destinations.find((d) => d.id === p.destinationId)!;
          return {
            ...p,
            destination: {
              id: dest.id,
              name: dest.name,
              slug: dest.slug,
              province: dest.province,
            },
          };
        });
    },
    findUnique: async ({ where }: { where: { id: string } }) => {
      const p = this.places.find((item) => item.id === where.id);
      if (!p) return null;
      const dest = this.destinations.find((d) => d.id === p.destinationId);
      return {
        ...p,
        destination: dest
          ? { id: dest.id, slug: dest.slug, name: dest.name }
          : null,
        _count: { placeSources: p.placeSources.length },
      };
    },
  };

  youtubePoiUpdate = {
    findUnique: async ({ where }: { where: { dedupeKey: string } }) => {
      if (this.simulateFindUniqueMissOnce) {
        this.simulateFindUniqueMissOnce = false;
        return null;
      }
      return (
        this.updates.find((u) => u.dedupeKey === where.dedupeKey) ?? null
      );
    },
    create: async ({
      data,
    }: {
      data: Omit<StoredYoutubeUpdate, "id">;
    }) => {
      const exists = this.updates.some((u) => u.dedupeKey === data.dedupeKey);
      if (exists) {
        throw new Prisma.PrismaClientKnownRequestError(
          "Unique constraint failed on the fields: (`dedupe_key`)",
          { code: "P2002", clientVersion: "5.0.0" },
        );
      }
      const row: StoredYoutubeUpdate = {
        ...data,
        id: `00000000-0000-4000-8000-${String(this.seq++).padStart(12, "0")}`,
      };
      this.updates.push(row);
      return row;
    },
    update: async ({
      where,
      data,
    }: {
      where: { dedupeKey: string };
      data: {
        deliveryCount?: { increment: number };
        lastReceivedAt?: Date;
      };
    }) => {
      const idx = this.updates.findIndex(
        (u) => u.dedupeKey === where.dedupeKey,
      );
      if (idx < 0) {
        throw new Error(`Row not found for dedupeKey ${where.dedupeKey}`);
      }
      const current = this.updates[idx];
      const updated: StoredYoutubeUpdate = {
        ...current,
        deliveryCount:
          current.deliveryCount + (data.deliveryCount?.increment ?? 0),
        lastReceivedAt: data.lastReceivedAt ?? current.lastReceivedAt,
      };
      this.updates[idx] = updated;
      return updated;
    },
    findMany: async ({
      where,
      take,
    }: {
      where: {
        placeId?: string | null;
        destinationId?: string;
        status?: YoutubeUpdateStatus | { in: YoutubeUpdateStatus[] };
        scope?: YoutubeUpdateScope;
      };
      take?: number;
    }) => {
      const filtered = this.updates.filter((u) => {
        if (where.placeId !== undefined && u.placeId !== where.placeId) {
          return false;
        }
        if (
          where.destinationId !== undefined &&
          u.destinationId !== where.destinationId
        ) {
          return false;
        }
        if (where.scope !== undefined && u.scope !== where.scope) {
          return false;
        }
        if (where.status !== undefined) {
          if (typeof where.status === "object" && "in" in where.status) {
            if (!where.status.in.includes(u.status)) return false;
          } else if (u.status !== where.status) {
            return false;
          }
        }
        return true;
      });

      filtered.sort((a, b) => {
        const pDiff = b.publishedAt.getTime() - a.publishedAt.getTime();
        if (pDiff !== 0) return pDiff;
        const sA = a.sourceUpdatedAt?.getTime() ?? 0;
        const sB = b.sourceUpdatedAt?.getTime() ?? 0;
        if (sB !== sA) return sB - sA;
        return b.receivedAt.getTime() - a.receivedAt.getTime();
      });

      return typeof take === "number" ? filtered.slice(0, take) : filtered;
    },
  };

  // Poisoned R4 guards: YoutubeModule MUST NEVER write to documents or placeSources
  private _rejectR4Write(target: string): never {
    throw new Error(
      `R4 VIOLATION: YoutubeModule attempted forbidden write to ${target}`,
    );
  }

  document = {
    create: () => this._rejectR4Write("documents"),
    createMany: () => this._rejectR4Write("documents"),
    update: () => this._rejectR4Write("documents"),
    updateMany: () => this._rejectR4Write("documents"),
    upsert: () => this._rejectR4Write("documents"),
    delete: () => this._rejectR4Write("documents"),
    deleteMany: () => this._rejectR4Write("documents"),
  };

  placeSource = {
    create: () => this._rejectR4Write("place_sources"),
    createMany: () => this._rejectR4Write("place_sources"),
    update: () => this._rejectR4Write("place_sources"),
    updateMany: () => this._rejectR4Write("place_sources"),
    upsert: () => this._rejectR4Write("place_sources"),
    delete: () => this._rejectR4Write("place_sources"),
    deleteMany: () => this._rejectR4Write("place_sources"),
  };

  $executeRaw = () => this._rejectR4Write("raw SQL");
  $executeRawUnsafe = () => this._rejectR4Write("raw SQL");
}

describe("YoutubeModule HTTP Integration (M2-backend-youtube)", () => {
  let app: INestApplication;
  let prisma: InMemoryYoutubePrisma;

  const http = () => request(app.getHttpServer());

  beforeAll(async () => {
    prisma = new InMemoryYoutubePrisma();
    prisma.reset();

    const moduleRef: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({
              NODE_ENV: "test",
              YOUTUBE_EVENTS_INTERNAL_SECRET: TEST_INTERNAL_SECRET,
              YOUTUBE_WEBSUB_SECRET: TEST_WEBSUB_SECRET,
              YOUTUBE_WEBSUB_VERIFY_TOKEN: TEST_VERIFY_TOKEN,
              YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS: "300000",
            }),
          ],
        }),
        PrismaModule,
        YoutubeModule,
      ],
    })
      .overrideProvider(PrismaService)
      .useValue(prisma)
      .compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        transform: true,
        forbidNonWhitelisted: true,
      }),
    );
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  beforeEach(() => {
    prisma.reset();
  });

  it("enforces secret guard on POST /youtube/events and validates trimmed DTO fields", async () => {
    const validBody = {
      videoId: "SecGuard001",
      channelId: "UC_HL_SEC",
      title: "Tháp Đồng Hồ Hạ Long buổi sáng",
      publishedAt: "2026-11-24T13:00:00Z",
    };

    const missingRes = await http()
      .post("/youtube/events")
      .send(validBody)
      .expect(401);
    expect(missingRes.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    );

    const badSecretRes = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", "wrong-secret")
      .send(validBody)
      .expect(401);
    expect(badSecretRes.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    );

    // Whitespace-only title fails with 400 after DTO @Transform trim
    await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send({
        videoId: "TrimFail001",
        channelId: "   ",
        title: "   ",
        publishedAt: "2026-11-24T13:00:00Z",
      })
      .expect(400);

    // Naive timestamp without explicit TZ fails with 400
    await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send({
        videoId: "NaiveTz0001",
        channelId: "UC_HL",
        title: "Tháp Đồng Hồ Hạ Long",
        publishedAt: "2026-11-24T13:00:00",
      })
      .expect(400);
  });

  it("delivers all 5 mandated fields + latency/SLA metrics on Tháp Đồng Hồ and deduplicates replays (incl. P2002 race)", async () => {
    const payload = {
      eventId: "tdh-http-01",
      videoId: "TDHHttpOk01",
      channelId: "UC_HL_OFFICIAL",
      channelTitle: "Quảng Ninh 360",
      title: "  Vòng xuyến Cột Đồng Hồ bên cạnh Vincom Hạ Long  ",
      description: "  Quay tại trung tâm Quảng Ninh  ",
      tags: ["  halong ", "  cotdongho  "],
      publishedAt: new Date(Date.now() - 12_000).toISOString(),
      sourceUpdatedAt: new Date(Date.now() - 5_000).toISOString(),
      latitude: 20.9516,
      longitude: 107.0852,
    };

    const r1 = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send(payload)
      .expect(200);
    expect(r1.body.data.duplicate).toBe(false);
    expect(r1.body.data.deliveryCount).toBe(1);
    expect(r1.body.data.status).toBe("LINKED");
    expect(r1.body.data.scope).toBe("POI");
    expect(r1.body.data.linkedPlaceId).toBe(THAP_DONG_HO_ID);
    expect(r1.body.data.destinationId).toBe(HA_LONG_DEST_ID);

    // Replay #2 (normal findUnique hit)
    const r2 = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send(payload)
      .expect(200);
    expect(r2.body.data.duplicate).toBe(true);
    expect(r2.body.data.deliveryCount).toBe(2);
    expect(r2.body.data.publishedAt).toBe(r1.body.data.publishedAt);
    expect(r2.body.data.receivedAt).toBe(r1.body.data.receivedAt);

    // Replay #3 (simulated concurrent race hitting P2002)
    prisma.simulateFindUniqueMissOnce = true;
    const r3 = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send(payload)
      .expect(200);
    expect(r3.body.data.duplicate).toBe(true);
    expect(r3.body.data.deliveryCount).toBe(3);
    expect(prisma.getAllUpdates()).toHaveLength(1);

    // Query both place routes
    const placeRes = await http()
      .get(`/places/${THAP_DONG_HO_ID}/youtube-updates`)
      .expect(200);
    const data = placeRes.body.data;
    expect(data.placeId).toBe(THAP_DONG_HO_ID);
    expect(data.placeName).toBe("Tháp Đồng Hồ");
    expect(data.destinationId).toBe(HA_LONG_DEST_ID);
    expect(data.destinationSlug).toBe("ha-long");
    expect(data.destinationName).toBe("Hạ Long");
    expect(data.governanceRole).toBe("DYNAMIC_SOCIAL_FRESHNESS_LAYER");
    expect(data.notPrimaryFactualCorpus).toBe(true);
    expect(data.realtimeSlaMaxLatencyMs).toBe(300000);
    expect(Date.parse(data.serverDeliveredAt)).not.toBeNaN();
    expect(data.total).toBe(1);
    expect(data.cityFallbackTotal).toBe(0);

    const item = data.items[0];
    expect(item.placeId).toBe(THAP_DONG_HO_ID);
    expect(item.source).toBe("youtube");
    expect(item.publishedAt).toBe(r1.body.data.publishedAt);
    expect(item.receivedAt).toBe(r1.body.data.receivedAt);
    expect(item.updatedAt).toBe(payload.sourceUpdatedAt);
    expect(item.scope).toBe("POI");
    expect(item.destinationId).toBe(HA_LONG_DEST_ID);
    expect(item.destinationSlug).toBe("ha-long");
    expect(item.ingestLatencyMs).toBeGreaterThanOrEqual(0);
    expect(item.deliveryLagMs).toBeGreaterThanOrEqual(item.ingestLatencyMs);

    const aliasRes = await http()
      .get(`/youtube/places/${THAP_DONG_HO_ID}/updates`)
      .expect(200);
    expect(aliasRes.body.data.items).toHaveLength(1);
  });

  it("routes generic Hạ Long updates to LINKED_CITY fallback and exposes destination endpoints while rejecting POI conflicts", async () => {
    // 1. Generic Hạ Long video -> LINKED_CITY
    const cityRes = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send({
        videoId: "HLGeneric01",
        channelId: "UC_HL_CITY",
        title: "Ăn hải sản Hạ Long 2 ngày 1 đêm",
        description: "Kinh nghiệm du lịch Quảng Ninh giá rẻ",
        publishedAt: "2026-11-24T14:00:00Z",
      })
      .expect(200);
    expect(cityRes.body.data.status).toBe("LINKED_CITY");
    expect(cityRes.body.data.scope).toBe("CITY");
    expect(cityRes.body.data.linkedPlaceId).toBeNull();
    expect(cityRes.body.data.destinationId).toBe(HA_LONG_DEST_ID);

    // 2. Conflicting POI GPS -> UNLINKED_NO_BASIS (never leaks into city fallback)
    const conflictRes = await http()
      .post("/youtube/events")
      .set("x-youtube-internal-secret", TEST_INTERNAL_SECRET)
      .send({
        videoId: "TDHBadCoord",
        channelId: "UC_BAD",
        title: "Tháp Đồng Hồ Hạ Long",
        publishedAt: "2026-11-24T14:05:00Z",
        latitude: 20.91656,
        longitude: 106.98958,
      })
      .expect(200);
    expect(conflictRes.body.data.status).toBe("UNLINKED_NO_BASIS");
    expect(conflictRes.body.data.scope).toBe("NONE");
    expect(conflictRes.body.data.destinationId).toBeNull();

    // 3. Tháp Đồng Hồ endpoint shows cityFallbackItems
    const placeRes = await http()
      .get(`/places/${THAP_DONG_HO_ID}/youtube-updates`)
      .expect(200);
    expect(placeRes.body.data.total).toBe(0);
    expect(placeRes.body.data.cityFallbackTotal).toBe(1);
    expect(placeRes.body.data.cityFallbackItems[0]).toMatchObject({
      placeId: null,
      source: "youtube",
      scope: "CITY",
      destinationId: HA_LONG_DEST_ID,
      destinationSlug: "ha-long",
      videoId: "HLGeneric01",
    });

    // 4. Destination endpoints by slug and UUID
    const destBySlug = await http()
      .get("/destinations/ha-long/youtube-updates")
      .expect(200);
    expect(destBySlug.body.data.placeId).toBeNull();
    expect(destBySlug.body.data.destinationId).toBe(HA_LONG_DEST_ID);
    expect(destBySlug.body.data.destinationSlug).toBe("ha-long");
    expect(destBySlug.body.data.total).toBe(1);
    expect(destBySlug.body.data.cityFallbackTotal).toBe(1);

    const destByUuid = await http()
      .get(`/youtube/destinations/${HA_LONG_DEST_ID}/updates?scope=CITY`)
      .expect(200);
    expect(destByUuid.body.data.items).toHaveLength(1);
    expect(destByUuid.body.data.items[0].videoId).toBe("HLGeneric01");

    const destPoiOnly = await http()
      .get("/destinations/ha-long/youtube-updates?scope=POI")
      .expect(200);
    expect(destPoiOnly.body.data.total).toBe(0);
    expect(destPoiOnly.body.data.cityFallbackTotal).toBe(0);
  });

  it("verifies WebSub handshake, HMAC signature ordering (401 before 400 on empty body), and canonical 404 errorCodes", async () => {
    // Handshake 200 & 403
    const okVerify = await http()
      .get("/youtube/webhook")
      .query({
        "hub.mode": "subscribe",
        "hub.topic":
          "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC_HL",
        "hub.challenge": "chal_abc_123",
        "hub.verify_token": TEST_VERIFY_TOKEN,
      })
      .expect(200);
    expect(okVerify.text).toBe("chal_abc_123");

    const badVerify = await http()
      .get("/youtube/webhook")
      .query({
        "hub.mode": "subscribe",
        "hub.topic":
          "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC_HL",
        "hub.challenge": "chal_abc_123",
        "hub.verify_token": "wrong",
      })
      .expect(403);
    expect(badVerify.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    );

    // Empty body without signature when secret configured -> 401 YOUTUBE_EVENT_UNAUTHORIZED (not 400)
    const emptyUnauth = await http()
      .post("/youtube/webhook")
      .set("Content-Type", "application/atom+xml")
      .send("")
      .expect(401);
    expect(emptyUnauth.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    );

    // Valid Atom XML + X-Hub-Signature-256
    const atomXml = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>WebSubHmac1</yt:videoId>
    <yt:channelId>UC_HL</yt:channelId>
    <title>Tháp Đồng Hồ Hạ Long từ WebSub</title>
    <published>2026-11-24T13:15:00Z</published>
  </entry>
</feed>`;
    const sig =
      "sha256=" +
      crypto
        .createHmac("sha256", TEST_WEBSUB_SECRET)
        .update(atomXml, "utf8")
        .digest("hex");

    const xmlRes = await http()
      .post("/youtube/webhook")
      .set("Content-Type", "application/atom+xml")
      .set("x-hub-signature-256", sig)
      .send(atomXml)
      .expect(200);
    expect(xmlRes.body.data.processedCount).toBe(1);
    expect(xmlRes.body.data.results[0].status).toBe("LINKED");

    // 404 PLACE_NOT_FOUND (unsourced & missing)
    const unsourced404 = await http()
      .get(`/places/${UNSOURCED_PLACE_ID}/youtube-updates`)
      .expect(404);
    expect(unsourced404.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.PLACE_NOT_FOUND,
    );

    const missing404 = await http()
      .get(`/youtube/places/${MISSING_PLACE_ID}/updates`)
      .expect(404);
    expect(missing404.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.PLACE_NOT_FOUND,
    );

    // 404 DESTINATION_NOT_FOUND
    const dest404 = await http()
      .get("/destinations/unknown-destination-slug/youtube-updates")
      .expect(404);
    expect(dest404.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.DESTINATION_NOT_FOUND,
    );

    const destAlias404 = await http()
      .get("/youtube/destinations/unknown-destination-slug/updates")
      .expect(404);
    expect(destAlias404.body.errorCode).toBe(
      YOUTUBE_ERROR_CODES.DESTINATION_NOT_FOUND,
    );
  });
});
