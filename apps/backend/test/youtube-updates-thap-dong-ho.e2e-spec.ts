import { INestApplication, ValidationPipe } from "@nestjs/common";
import { Test, TestingModule } from "@nestjs/testing";
import * as request from "supertest";
import { AppModule } from "../src/app.module";
import { HttpExceptionFilter } from "../src/common/filters/http-exception.filter";
import { TransformInterceptor } from "../src/common/interceptors/transform.interceptor";
import { PrismaService } from "../src/prisma/prisma.service";

const THAP_DONG_HO_ID = "65562a67-84ff-44a0-990d-31917a2a9bd0";
const THAP_DONG_HO_LAT = 20.9516105;
const THAP_DONG_HO_LON = 107.0851999;
const THAP_DONG_HO_OSM_ID = "way/674228542";

describe("YouTube Update Receiver Integration (Tháp Đồng Hồ POI fixture)", () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let createdThapDongHoInTest = false;
  let createdHaLongDestId: string | null = null;
  let unverifiedLegacyPlaceId = "";
  const testDedupePrefixes = [
    "yt:video:TDHWebSub01:",
    "yt:event:tdh-json-concurrent-01",
    "yt:video:TDHPhuQuoc1:",
    "yt:video:TDHNoCity01:",
    "yt:video:TDHBadCoord:",
    "yt:video:TDHUnverif1:",
  ];

  const http = () => request(app.getHttpServer());

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
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

    prisma = app.get(PrismaService);

    // Ensure Hạ Long destination and canonical Tháp Đồng Hồ Freeze V2 fixture exist
    let haLong = await prisma.destination.findUnique({
      where: { slug: "ha-long" },
    });
    if (!haLong) {
      haLong = await prisma.destination.create({
        data: {
          name: "Hạ Long",
          nameEn: "Ha Long",
          slug: "ha-long",
          province: "Quảng Ninh",
          region: "north",
          latitude: 20.95,
          longitude: 107.08,
        },
      });
      createdHaLongDestId = haLong.id;
    }

    const existingThap = await prisma.place.findUnique({
      where: { id: THAP_DONG_HO_ID },
      include: { placeSources: true },
    });
    if (!existingThap) {
      await prisma.place.create({
        data: {
          id: THAP_DONG_HO_ID,
          destinationId: haLong.id,
          name: "Tháp Đồng Hồ",
          description:
            "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long cạnh Vincom và tổ hợp Times Garden, là điểm mốc giao thông nối các tuyến đường Lê Thánh Tông, 25 Tháng 4, phố Nhà Thờ và phố Tuệ Tĩnh thuộc khu vực Bạch Đằng.",
          latitude: THAP_DONG_HO_LAT,
          longitude: THAP_DONG_HO_LON,
        },
      });
      createdThapDongHoInTest = true;
    }
    await prisma.placeSource.upsert({
      where: {
        sourceName_sourceId: {
          sourceName: "osm",
          sourceId: THAP_DONG_HO_OSM_ID,
        },
      },
      create: {
        placeId: THAP_DONG_HO_ID,
        sourceName: "osm",
        sourceId: THAP_DONG_HO_OSM_ID,
        rawName: "Tháp Đồng Hồ",
        latitude: THAP_DONG_HO_LAT,
        longitude: THAP_DONG_HO_LON,
        rawData: {
          tags: {
            name: "Tháp Đồng Hồ",
            amenity: "clock",
            tourism: "attraction",
          },
        },
        confidenceScore: 1.0,
      },
      update: {
        placeId: THAP_DONG_HO_ID,
      },
    });

    // Create an unsourced legacy place (0 place_sources) to verify fail-closed trust boundary
    const unsourced = await prisma.place.create({
      data: {
        destinationId: haLong.id,
        name: "Địa điểm giả lập chưa xác minh nguồn",
        latitude: 20.952,
        longitude: 107.086,
      },
    });
    unverifiedLegacyPlaceId = unsourced.id;

    // Clean any leftover test YouTube rows
    await prisma.youtubePoiUpdate.deleteMany({
      where: {
        OR: testDedupePrefixes.map((prefix) => ({
          dedupeKey: { startsWith: prefix },
        })),
      },
    });
  });

  afterAll(async () => {
    if (prisma) {
      await prisma.youtubePoiUpdate.deleteMany({
        where: {
          OR: testDedupePrefixes.map((prefix) => ({
            dedupeKey: { startsWith: prefix },
          })),
        },
      });
      if (unverifiedLegacyPlaceId) {
        await prisma.place.deleteMany({
          where: { id: unverifiedLegacyPlaceId },
        });
      }
      if (createdThapDongHoInTest) {
        await prisma.placeSource.deleteMany({
          where: { sourceName: "osm", sourceId: THAP_DONG_HO_OSM_ID },
        });
        await prisma.place.deleteMany({ where: { id: THAP_DONG_HO_ID } });
      }
      if (createdHaLongDestId) {
        await prisma.destination.deleteMany({
          where: { id: createdHaLongDestId },
        });
      }
    }
    if (app) {
      await app.close();
    }
  });

  it("echoes raw hub.challenge on valid YouTube WebSub verification and rejects malformed requests", async () => {
    const okRes = await http()
      .get("/youtube/webhook")
      .query({
        "hub.mode": "subscribe",
        "hub.topic":
          "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UCQuangNinhTravel",
        "hub.challenge": "websub_challenge_thap_dong_ho_2026",
      })
      .expect(200);

    expect(okRes.headers["content-type"]).toContain("text/plain");
    expect(okRes.text).toBe("websub_challenge_thap_dong_ho_2026");

    await http()
      .get("/youtube/webhook")
      .query({
        "hub.mode": "subscribe",
        "hub.topic": "https://evil.example.com/feed.xml",
        "hub.challenge": "abc",
      })
      .expect(400);
  });

  it("ingests WebSub Atom XML for Tháp Đồng Hồ, stores UTC publishedAt & receivedAt, and deduplicates repeated deliveries", async () => {
    const docsBefore = await prisma.document.count({
      where: { placeId: THAP_DONG_HO_ID },
    });
    const sourcesBefore = await prisma.placeSource.count({
      where: { placeId: THAP_DONG_HO_ID },
    });

    const atomFeed = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>YouTube video feed</title>
  <entry>
    <id>yt:video:TDHWebSub01</id>
    <yt:videoId>TDHWebSub01</yt:videoId>
    <yt:channelId>UCQuangNinhTravel</yt:channelId>
    <title>Khám phá Tháp Đồng Hồ Hạ Long về đêm</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=TDHWebSub01"/>
    <author>
      <name>Du lịch Quảng Ninh</name>
      <uri>https://www.youtube.com/channel/UCQuangNinhTravel</uri>
    </author>
    <published>2026-11-24T20:15:00+07:00</published>
    <updated>2026-11-24T20:20:00+07:00</updated>
  </entry>
</feed>`;

    const beforeSendMs = Date.now();
    const firstRes = await http()
      .post("/youtube/webhook")
      .set("Content-Type", "application/atom+xml")
      .send(atomFeed)
      .expect(200);

    const firstItem = firstRes.body.data.results[0];
    expect(firstRes.body.data.processedCount).toBe(1);
    expect(firstItem.duplicate).toBe(false);
    expect(firstItem.deliveryCount).toBe(1);
    expect(firstItem.status).toBe("LINKED");
    expect(firstItem.linkedPlaceId).toBe(THAP_DONG_HO_ID);
    expect(firstItem.groundingBasis).toBe(
      "UNIQUE_NAME_AND_DESTINATION_CONTEXT",
    );
    // Giờ đăng chuyển chuẩn về UTC: 20:15+07:00 -> 13:15:00.000Z
    expect(firstItem.publishedAt).toBe("2026-11-24T13:15:00.000Z");
    const receivedMs = Date.parse(firstItem.receivedAt);
    expect(receivedMs).toBeGreaterThanOrEqual(beforeSendMs - 1000);

    // Gửi lặp lại chính xác cùng sự kiện Atom XML lần 2
    const secondRes = await http()
      .post("/youtube/webhook")
      .set("Content-Type", "application/atom+xml")
      .send(atomFeed)
      .expect(200);

    const secondItem = secondRes.body.data.results[0];
    expect(secondItem.id).toBe(firstItem.id);
    expect(secondItem.duplicate).toBe(true);
    expect(secondItem.deliveryCount).toBe(2);
    // Giờ đăng và giờ nhận lần đầu giữ nguyên bất biến
    expect(secondItem.publishedAt).toBe(firstItem.publishedAt);
    expect(secondItem.receivedAt).toBe(firstItem.receivedAt);
    expect(Date.parse(secondItem.lastReceivedAt)).toBeGreaterThanOrEqual(
      Date.parse(firstItem.receivedAt),
    );

    const dbCount = await prisma.youtubePoiUpdate.count({
      where: { videoId: "TDHWebSub01" },
    });
    expect(dbCount).toBe(1);

    // Tuyệt đối không ghi sang bảng RAG `documents` hay `place_sources`
    const docsAfter = await prisma.document.count({
      where: { placeId: THAP_DONG_HO_ID },
    });
    const sourcesAfter = await prisma.placeSource.count({
      where: { placeId: THAP_DONG_HO_ID },
    });
    expect(docsAfter).toBe(docsBefore);
    expect(sourcesAfter).toBe(sourcesBefore);
  });

  it("handles concurrent duplicate JSON deliveries atomically and only links posts to Tháp Đồng Hồ when grounded", async () => {
    const groundedPayload = {
      eventId: "tdh-json-concurrent-01",
      videoId: "TDHCoordOk1",
      channelId: "UCHaLongCheckin",
      channelTitle: "Hạ Long Check-in",
      title: "Vòng xuyến Cột Đồng Hồ bên cạnh Vincom",
      description: "Quay trực tiếp tại nút giao Lê Thánh Tông - 25 Tháng 4.",
      tags: ["cotdongho", "halong"],
      publishedAt: "2026-11-24T15:00:00Z",
      latitude: 20.95162,
      longitude: 107.08521,
    };

    // Bắn đồng thời 3 request trùng cùng 1 sự kiện
    const burstResponses = await Promise.all([
      http().post("/youtube/events").send(groundedPayload).expect(200),
      http().post("/youtube/events").send(groundedPayload).expect(200),
      http().post("/youtube/events").send(groundedPayload).expect(200),
    ]);

    const receipts = burstResponses.map((r) => r.body.data);
    const nonDuplicates = receipts.filter((r) => r.duplicate === false);
    const duplicates = receipts.filter((r) => r.duplicate === true);
    expect(nonDuplicates).toHaveLength(1);
    expect(duplicates).toHaveLength(2);

    const persisted = await prisma.youtubePoiUpdate.findUnique({
      where: { dedupeKey: "yt:event:tdh-json-concurrent-01" },
    });
    expect(persisted).not.toBeNull();
    expect(persisted?.deliveryCount).toBe(3);
    expect(persisted?.placeId).toBe(THAP_DONG_HO_ID);
    expect(persisted?.groundingBasis).toBe("NAME_AND_COORDINATE_CORROBORATION");
    expect(persisted?.publishedAt.toISOString()).toBe(
      "2026-11-24T15:00:00.000Z",
    );

    // Các sự kiện KHÔNG đủ căn cứ -> lưu giờ đăng & giờ nhận nhưng KHÔNG gắn vào Tháp Đồng Hồ:
    // Case A: Trùng tên "Tháp Đồng Hồ" nhưng ở Phú Quốc
    const wrongCityRes = await http()
      .post("/youtube/events")
      .send({
        videoId: "TDHPhuQuoc1",
        channelId: "UCPQ",
        title: "Tháp Đồng Hồ Phú Quốc rực nắng",
        description: "Check-in Venice Phú Quốc Kiên Giang",
        publishedAt: "2026-11-24T16:00:00Z",
      })
      .expect(200);
    expect(wrongCityRes.body.data.status).toBe("UNLINKED_NO_BASIS");
    expect(wrongCityRes.body.data.linkedPlaceId).toBeNull();
    expect(wrongCityRes.body.data.decisionReason).toBe(
      "conflicting_city_mention",
    );
    expect(wrongCityRes.body.data.publishedAt).toBe("2026-11-24T16:00:00.000Z");
    expect(wrongCityRes.body.data.receivedAt).toBeTruthy();

    // Case B: Chỉ nhắc "Tháp Đồng Hồ" chung chung, không có thành phố/tọa độ
    const noContextRes = await http()
      .post("/youtube/events")
      .send({
        videoId: "TDHNoCity01",
        channelId: "UCGeneric",
        title: "Đi ngang Tháp Đồng Hồ buổi sáng",
        publishedAt: "2026-11-24T16:05:00Z",
      })
      .expect(200);
    expect(noContextRes.body.data.status).toBe("UNLINKED_NO_BASIS");
    expect(noContextRes.body.data.linkedPlaceId).toBeNull();
    expect(noContextRes.body.data.decisionReason).toBe(
      "missing_destination_or_spatial_corroboration",
    );

    // Case C: Nhắc "Tháp Đồng Hồ Hạ Long" nhưng tọa độ GPS đính kèm lệch xa (> 10km tại Tuần Châu)
    const badCoordRes = await http()
      .post("/youtube/events")
      .send({
        videoId: "TDHBadCoord",
        channelId: "UCGeneric",
        title: "Tháp Đồng Hồ Hạ Long",
        description: "Video gắn nhầm vị trí tại đảo Tuần Châu",
        publishedAt: "2026-11-24T16:10:00Z",
        latitude: 20.91656,
        longitude: 106.98958,
      })
      .expect(200);
    expect(badCoordRes.body.data.status).toBe("UNLINKED_NO_BASIS");
    expect(badCoordRes.body.data.linkedPlaceId).toBeNull();
    expect(badCoordRes.body.data.decisionReason).toBe(
      "coordinate_conflict_with_poi",
    );

    // Case D: Cố tình truyền candidatePlaceId của địa điểm chưa có nguồn xác minh (0 place_sources)
    const unverifiedPoiRes = await http()
      .post("/youtube/events")
      .send({
        videoId: "TDHUnverif1",
        channelId: "UCGeneric",
        title: "Địa điểm giả lập chưa xác minh nguồn tại Hạ Long",
        publishedAt: "2026-11-24T16:15:00Z",
        candidatePlaceId: unverifiedLegacyPlaceId,
      })
      .expect(200);
    expect(unverifiedPoiRes.body.data.status).toBe("UNLINKED_NO_BASIS");
    expect(unverifiedPoiRes.body.data.linkedPlaceId).toBeNull();
    expect(unverifiedPoiRes.body.data.decisionReason).toBe(
      "target_place_unverified_or_missing",
    );

    // Truy vấn danh sách bài đã gắn cho Tháp Đồng Hồ: chỉ trả về đúng 2 video đủ căn cứ
    const listRes = await http()
      .get(`/places/${THAP_DONG_HO_ID}/youtube-updates?limit=10`)
      .expect(200);
    const listData = listRes.body.data;
    expect(listData.placeId).toBe(THAP_DONG_HO_ID);
    expect(listData.governanceRole).toBe("DYNAMIC_SOCIAL_FRESHNESS_LAYER");
    expect(listData.notPrimaryFactualCorpus).toBe(true);

    const returnedVideoIds = listData.items.map(
      (x: { videoId: string }) => x.videoId,
    );
    expect(returnedVideoIds).toContain("TDHCoordOk1");
    expect(returnedVideoIds).toContain("TDHWebSub01");
    expect(returnedVideoIds).not.toContain("TDHPhuQuoc1");
    expect(returnedVideoIds).not.toContain("TDHNoCity01");
    expect(returnedVideoIds).not.toContain("TDHBadCoord");
    expect(returnedVideoIds).not.toContain("TDHUnverif1");

    // Địa điểm chưa xác minh nguồn phải trả 404 khi truy vấn public endpoint
    await http()
      .get(`/places/${unverifiedLegacyPlaceId}/youtube-updates`)
      .expect(404);
  });
});
