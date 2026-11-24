import { Test, TestingModule } from "@nestjs/testing";
import { INestApplication, ValidationPipe } from "@nestjs/common";
import * as request from "supertest";
import * as bcrypt from "bcryptjs";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { TransformInterceptor } from "../src/common/interceptors/transform.interceptor";
import { HttpExceptionFilter } from "../src/common/filters/http-exception.filter";

describe("Wave C Enrichment, Reviews Trust & W08 Buddy Matching (e2e)", () => {
  let app: INestApplication;
  let prisma: PrismaService;
  const createdUserIds: string[] = [];
  const createdPlaceReviewIds: string[] = [];
  let tokenA = "";
  let tokenB = "";
  let userAId = "";
  let userBId = "";
  let verifiedPlaceId = "";
  let syntheticReviewId = "";

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

    const placeWithMedia = await prisma.place.findFirst({
      where: {
        deletedAt: null,
        placeSources: { some: {} },
        coverImage: { not: null },
      },
      orderBy: { id: "asc" },
    });
    const fallbackPlace =
      placeWithMedia ??
      (await prisma.place.findFirst({
        where: { deletedAt: null, placeSources: { some: {} } },
        orderBy: { id: "asc" },
      }));
    if (!fallbackPlace) {
      throw new Error("No verified place available in DB for e2e test");
    }
    verifiedPlaceId = fallbackPlace.id;

    const pwHash = await bcrypt.hash("TestPass#2026", 10);
    const suffix = Date.now();
    const uA = await prisma.user.create({
      data: {
        email: `wavec-a-${suffix}@test.local`,
        passwordHash: pwHash,
        isVerified: true,
        profile: { create: { displayName: "WaveC User A" } },
        preferences: {
          create: {
            travelStyle: "COMFORT",
            interests: ["food_cuisine", "culture_history"],
          },
        },
      },
    });
    const uB = await prisma.user.create({
      data: {
        email: `wavec-b-${suffix}@test.local`,
        passwordHash: pwHash,
        isVerified: true,
        profile: {
          create: { displayName: "WaveC User B", bio: "Thích ẩm thực" },
        },
        preferences: {
          create: {
            travelStyle: "COMFORT",
            interests: ["food_cuisine", "beach_island"],
          },
        },
      },
    });
    userAId = uA.id;
    userBId = uB.id;
    createdUserIds.push(uA.id, uB.id);

    // Seed an untrusted synthetic review on verifiedPlaceId to prove fail-closed isolation
    const synRev = await prisma.review.create({
      data: {
        userId: uB.id,
        placeId: verifiedPlaceId,
        rating: 1.0,
        content: "Synthetic untrusted fixture review must stay hidden",
        source: "synthetic",
        trusted: false,
      },
    });
    syntheticReviewId = synRev.id;
    createdPlaceReviewIds.push(synRev.id);

    const loginA = await http()
      .post("/auth/login")
      .send({ email: uA.email, password: "TestPass#2026" })
      .expect(200);
    tokenA = loginA.body.data.access_token;

    const loginB = await http()
      .post("/auth/login")
      .send({ email: uB.email, password: "TestPass#2026" })
      .expect(200);
    tokenB = loginB.body.data.access_token;
  });

  afterAll(async () => {
    if (createdUserIds.length > 0) {
      await prisma.match.deleteMany({
        where: {
          OR: [
            { senderId: { in: createdUserIds } },
            { receiverId: { in: createdUserIds } },
          ],
        },
      });
    }
    if (createdPlaceReviewIds.length > 0) {
      await prisma.review.deleteMany({
        where: { id: { in: createdPlaceReviewIds } },
      });
    }
    await prisma.review.deleteMany({
      where: { userId: { in: createdUserIds } },
    });
    await prisma.place.update({
      where: { id: verifiedPlaceId },
      data: { rating: null, reviewCount: 0 },
    });
    if (createdUserIds.length > 0) {
      await prisma.user.deleteMany({ where: { id: { in: createdUserIds } } });
    }
    await app.close();
  });

  it("GET /places/trending returns verified places ordered by real enrichment & activity without synthetic metrics", async () => {
    const res = await http().get("/places/trending?limit=10").expect(200);
    const items = res.body.data.items;
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThan(0);
    expect(items.length).toBeLessThanOrEqual(10);
    for (const it of items) {
      expect(it.isVerified).toBe(true);
      expect(it).not.toHaveProperty("priceMin");
      expect(it).not.toHaveProperty("priceMax");
      expect(it.freshness.rankingBasis).toBe(
        "verified_activity_and_enrichment_completeness",
      );
    }
  });

  it("Reviews pipeline isolates trusted=false, hides reviewer email in place detail, and resets zero rating to null", async () => {
    // 1. Untrusted synthetic review never appears on GET /reviews?placeId= or GET /reviews/:id
    const revListBefore = await http()
      .get(`/reviews?placeId=${verifiedPlaceId}`)
      .expect(200);
    expect(revListBefore.body.data.items.map((r: any) => r.id)).not.toContain(
      syntheticReviewId,
    );
    await http().get(`/reviews/${syntheticReviewId}`).expect(404);

    // 2. Post a real trusted review via User A
    const createdRes = await http()
      .post("/reviews")
      .set("Authorization", `Bearer ${tokenA}`)
      .send({
        placeId: verifiedPlaceId,
        rating: 5,
        content: "Cảnh quan đẹp, thông tin mở cửa chính xác.",
      })
      .expect(201);
    const realRevId = createdRes.body.data.id;
    createdPlaceReviewIds.push(realRevId);

    // 3. Place detail reflects trusted rating (5) and omits reviewer PII email
    const placeDetail = (
      await http().get(`/places/${verifiedPlaceId}`).expect(200)
    ).body.data;
    expect(placeDetail.reviewCount).toBe(1);
    expect(placeDetail.rating).toBe(5);
    expect(placeDetail.reviews).toHaveLength(1);
    expect(placeDetail.reviews[0].id).toBe(realRevId);
    expect(placeDetail.reviews[0].user).not.toHaveProperty("email");
    expect(placeDetail.reviews[0].user.profile.displayName).toBe(
      "WaveC User A",
    );

    // 4. Delete trusted review -> synthetic review remains excluded, place.rating resets to null (not 0)
    await http()
      .delete(`/reviews/${realRevId}`)
      .set("Authorization", `Bearer ${tokenA}`)
      .expect(200);

    const placeDetailAfter = (
      await http().get(`/places/${verifiedPlaceId}`).expect(200)
    ).body.data;
    expect(placeDetailAfter.reviewCount).toBe(0);
    expect(placeDetailAfter.rating).toBeNull();
  });

  it("W08 Buddy Matching enforces opt-in, discovers candidates without PII, opens masked profile, prevents self-accept, and updates ACCEPTED", async () => {
    // Before opt-in: candidates list is empty with isDiscoverable=false
    const preOptIn = await http()
      .get("/matches/candidates?limit=20")
      .set("Authorization", `Bearer ${tokenA}`)
      .expect(200);
    expect(preOptIn.body.data.isDiscoverable).toBe(false);
    expect(preOptIn.body.data.items).toEqual([]);

    // Explicit opt-in by both A and B
    await http()
      .patch("/matches/discovery")
      .set("Authorization", `Bearer ${tokenA}`)
      .send({ isDiscoverable: true })
      .expect(200);
    await http()
      .patch("/matches/discovery")
      .set("Authorization", `Bearer ${tokenB}`)
      .send({ isDiscoverable: true })
      .expect(200);

    const candRes = await http()
      .get("/matches/candidates?limit=20")
      .set("Authorization", `Bearer ${tokenA}`)
      .expect(200);
    const items: any[] = candRes.body.data.items;
    const foundB = items.find((c) => c.peer.id === userBId);
    expect(foundB).toBeTruthy();
    expect(foundB.compatibilityScore).toBeGreaterThan(0);
    expect(foundB.peer).not.toHaveProperty("email");
    expect(foundB.peer).not.toHaveProperty("phone");
    expect(foundB.peer.displayName).toBe("WaveC User B");

    // Masked profile view hides PII
    const maskedProfileRes = await http()
      .get(`/matches/peers/${userBId}`)
      .set("Authorization", `Bearer ${tokenA}`)
      .expect(200);
    expect(maskedProfileRes.body.data.peer.id).toBe(userBId);
    expect(maskedProfileRes.body.data.peer).not.toHaveProperty("email");
    expect(maskedProfileRes.body.data.peer).not.toHaveProperty("phone");

    // Request from A -> B
    const reqRes = await http()
      .post("/matches/request")
      .set("Authorization", `Bearer ${tokenA}`)
      .send({ receiverId: userBId })
      .expect(201);
    const matchId = reqRes.body.data.id;
    expect(reqRes.body.data.status).toBe("PENDING");

    // Sender A cannot self-accept -> 403 Forbidden
    await http()
      .patch(`/matches/${matchId}/respond`)
      .set("Authorization", `Bearer ${tokenA}`)
      .send({ action: "ACCEPTED" })
      .expect(403);

    // Receiver B accepts -> ACCEPTED, PII still hidden
    const acceptRes = await http()
      .patch(`/matches/${matchId}/respond`)
      .set("Authorization", `Bearer ${tokenB}`)
      .send({ action: "ACCEPTED" })
      .expect(200);
    expect(acceptRes.body.data.status).toBe("ACCEPTED");
    expect(acceptRes.body.data.peer.id).toBe(userAId);
    expect(acceptRes.body.data.peer).not.toHaveProperty("email");
  });
});
