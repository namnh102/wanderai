import { INestApplication, ValidationPipe } from "@nestjs/common";
import { Test, TestingModule } from "@nestjs/testing";
import { MatchStatus, TravelStyle, TripStatus } from "@prisma/client";
import * as bcrypt from "bcryptjs";
import * as fs from "fs";
import * as path from "path";
import * as request from "supertest";
import { AppModule } from "../src/app.module";
import { HttpExceptionFilter } from "../src/common/filters/http-exception.filter";
import { TransformInterceptor } from "../src/common/interceptors/transform.interceptor";
import { PrismaService } from "../src/prisma/prisma.service";

jest.setTimeout(120_000);

interface PersonaTripFixture {
  destinationSlug: string;
  startDate: string;
  endDate: string;
  status: "DRAFT" | "PLANNED" | "ONGOING";
}

interface PersonaCanaryFixture {
  email: string;
  phone: string;
  dateOfBirth: string;
  dietaryNeeds: string[];
  avoidances: string[];
  budgetMin: number;
  budgetMax: number;
  safetyContactName: string;
  safetyContactPhone: string;
  safetyCheckinLat: number;
  safetyCheckinLng: number;
  safetyCheckinNote: string;
  privateTripNote: string;
  privateTripBudget: number;
}

interface PersonaFixture {
  code: string;
  id: string;
  displayName: string;
  bio: string;
  nationality: string;
  languages: string[];
  isDiscoverable: boolean;
  travelStyle: TravelStyle;
  interests: string[];
  trips: PersonaTripFixture[];
  privateCanaries: PersonaCanaryFixture;
}

interface QueryFixture {
  queryId: string;
  viewerCode: string;
  destinationSlug: string | null;
  expectedCohort:
    | "FULL_POOL"
    | "UNDERFILLED_POOL"
    | "ZERO_RELEVANT_LABELS"
    | "OPTED_OUT_VIEWER";
  description: string;
}

interface MatchEvalFixtureFile {
  evaluationId: string;
  version: string;
  seed: number;
  frozenBeforeMeasurement: boolean;
  rankingSpecification: {
    k: number;
    binaryRelevanceCutoff: number;
    precisionAt5Formula: string;
    ndcgAt5Formula: string;
    approvedRoadmapThreshold: number | null;
    approvedRoadmapThresholdNote: string;
  };
  requiredDestinations: Array<{ slug: string; name: string; region: string }>;
  initialBlocks: Array<{
    blockerCode: string;
    blockedCode: string;
    reason: string;
  }>;
  personas: PersonaFixture[];
  queries: QueryFixture[];
  relevanceMatrix: Record<string, Record<string, number>>;
}

interface PerQueryMetricRow {
  queryId: string;
  viewerCode: string;
  destinationSlug: string | null;
  cohort: QueryFixture["expectedCohort"];
  eligiblePoolSize: number;
  positiveBinaryLabelCount: number;
  positiveGradedLabelCount: number;
  returnedCount: number;
  returnedTop5Codes: string[];
  returnedTop5Grades: number[];
  returnedTop5Scores: number[];
  dcgAt5: number;
  idcgAt5: number;
  ndcgAt5: number | null;
  precisionAt5Strict: number | null;
  precisionAtMin5Pool: number | null;
  ineligibleReturnedCount: number;
}

interface PrivacyLeakFinding {
  requestIndex: number;
  category: string;
  method: string;
  endpoint: string;
  httpStatus: number;
  reason: string;
}

interface ConsentViolationFinding {
  requestIndex: number;
  endpoint: string;
  matchId: string;
  actorCode: string;
  reason: string;
}

/**
 * Deterministic 32-bit Mulberry32 PRNG seeded with fixture.seed (20261125).
 */
function createMulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function datesOverlapIso(
  aStart: string,
  aEnd: string,
  bStart: string,
  bEnd: string,
): boolean {
  return (
    new Date(aStart).getTime() <= new Date(bEnd).getTime() &&
    new Date(bStart).getTime() <= new Date(aEnd).getTime()
  );
}

/**
 * Computes ground-truth relevance grade (0..3) directly from the documented rubric
 * so we verify the frozen relevanceMatrix in match-eval-01.personas.json has zero label drift.
 */
function computeRubricGrade(
  viewer: PersonaFixture,
  peer: PersonaFixture,
): number {
  const viewerInterests = new Set(viewer.interests);
  const sharedInterestCount = peer.interests.filter((i) =>
    viewerInterests.has(i),
  ).length;
  const sameStyle = viewer.travelStyle === peer.travelStyle;

  let hasSharedDest = false;
  let hasOverlappingDestDates = false;
  for (const vt of viewer.trips) {
    for (const pt of peer.trips) {
      if (vt.destinationSlug === pt.destinationSlug) {
        hasSharedDest = true;
        if (
          datesOverlapIso(vt.startDate, vt.endDate, pt.startDate, pt.endDate)
        ) {
          hasOverlappingDestDates = true;
        }
      }
    }
  }

  if (hasOverlappingDestDates && (sameStyle || sharedInterestCount >= 1)) {
    return 3;
  }
  if (
    hasOverlappingDestDates ||
    (hasSharedDest && (sameStyle || sharedInterestCount >= 1)) ||
    (sameStyle && sharedInterestCount >= 2)
  ) {
    return 2;
  }
  if (sameStyle || sharedInterestCount >= 1 || hasSharedDest) {
    return 1;
  }
  return 0;
}

function computeDcg(grades: number[], k: number): number {
  let sum = 0;
  const limit = Math.min(k, grades.length);
  for (let i = 0; i < limit; i++) {
    const rel = grades[i];
    if (rel > 0) {
      sum += (Math.pow(2, rel) - 1) / Math.log2(i + 2);
    }
  }
  return sum;
}

const FORBIDDEN_RESPONSE_KEYS = new Set([
  "email",
  "phone",
  "passwordHash",
  "password_hash",
  "dateOfBirth",
  "date_of_birth",
  "dietaryNeeds",
  "dietary_needs",
  "avoidances",
  "budgetMin",
  "budget_min",
  "budgetMax",
  "budget_max",
  "totalBudget",
  "total_budget",
  "safetyContacts",
  "safety_contacts",
  "safetyCheckins",
  "safety_checkins",
  "latitude",
  "longitude",
]);

function findForbiddenKeys(value: unknown, currentPath = "$"): string[] {
  if (value === null || typeof value !== "object") {
    return [];
  }
  if (Array.isArray(value)) {
    const out: string[] = [];
    for (let i = 0; i < value.length; i++) {
      out.push(...findForbiddenKeys(value[i], `${currentPath}[${i}]`));
    }
    return out;
  }
  const findings: string[] = [];
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_RESPONSE_KEYS.has(key)) {
      findings.push(`${currentPath}.${key}`);
    }
    findings.push(...findForbiddenKeys(child, `${currentPath}.${key}`));
  }
  return findings;
}

describe("MATCH-EVAL-01 — W08 Buddy Ranking (nDCG@5, Precision@5), Consent & 1,000-Request Privacy Audit", () => {
  const fixturePath = path.resolve(
    __dirname,
    "fixtures/match-eval-01.personas.json",
  );
  const fixture: MatchEvalFixtureFile = JSON.parse(
    fs.readFileSync(fixturePath, "utf-8"),
  ) as MatchEvalFixtureFile;

  let app: INestApplication;
  let prisma: PrismaService;
  const personaByCode = new Map<string, PersonaFixture>();
  const codeByUserId = new Map<string, string>();
  const tokenByCode = new Map<string, string>();
  const destinationIdBySlug = new Map<string, string>();
  const createdDestinationIds: string[] = [];
  let preExistingDiscoverableUserIds: string[] = [];

  const allCanarySubstrings: string[] = [];
  const vnPhoneRegex = /(?:\+84|0)(?:3|5|7|8|9)\d{8}/;
  const secretEmailRegex = /[a-z0-9._%+-]+@secret-eval\.local/i;

  let rankingRows: PerQueryMetricRow[] = [];

  const http = () => request(app.getHttpServer());

  async function purgeFixtureUsers() {
    const personaIds = fixture.personas.map((p) => p.id);
    await prisma.match.deleteMany({
      where: {
        OR: [
          { senderId: { in: personaIds } },
          { receiverId: { in: personaIds } },
        ],
      },
    });
    await prisma.userBlock.deleteMany({
      where: {
        OR: [
          { blockerId: { in: personaIds } },
          { blockedId: { in: personaIds } },
        ],
      },
    });
    await prisma.safetyCheckin.deleteMany({
      where: { userId: { in: personaIds } },
    });
    await prisma.safetyContact.deleteMany({
      where: { userId: { in: personaIds } },
    });
    await prisma.trip.deleteMany({
      where: { userId: { in: personaIds } },
    });
    await prisma.user.deleteMany({
      where: { id: { in: personaIds } },
    });
  }

  beforeAll(async () => {
    for (const p of fixture.personas) {
      personaByCode.set(p.code, p);
      codeByUserId.set(p.id, p.code);
      allCanarySubstrings.push(
        p.privateCanaries.email,
        p.privateCanaries.phone,
        p.privateCanaries.dateOfBirth,
        ...p.privateCanaries.dietaryNeeds,
        ...p.privateCanaries.avoidances,
        String(p.privateCanaries.budgetMin),
        String(p.privateCanaries.budgetMax),
        p.privateCanaries.safetyContactName,
        p.privateCanaries.safetyContactPhone,
        String(p.privateCanaries.safetyCheckinLat),
        String(p.privateCanaries.safetyCheckinLng),
        p.privateCanaries.safetyCheckinNote,
        p.privateCanaries.privateTripNote,
        String(p.privateCanaries.privateTripBudget),
      );
    }

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

    // Hermetically isolate candidate pool from any non-fixture user that might have opted in
    const personaIds = fixture.personas.map((p) => p.id);
    const existingOptedIn = await prisma.profile.findMany({
      where: {
        isDiscoverable: true,
        userId: { notIn: personaIds },
      },
      select: { userId: true },
    });
    preExistingDiscoverableUserIds = existingOptedIn.map((r) => r.userId);
    if (preExistingDiscoverableUserIds.length > 0) {
      await prisma.profile.updateMany({
        where: { userId: { in: preExistingDiscoverableUserIds } },
        data: { isDiscoverable: false },
      });
    }

    await purgeFixtureUsers();

    // Resolve required destinations by slug (creating temporary rows only if absent in minimal CI DB)
    for (const destSpec of fixture.requiredDestinations) {
      const existing = await prisma.destination.findUnique({
        where: { slug: destSpec.slug },
        select: { id: true, deletedAt: true },
      });
      if (existing && existing.deletedAt === null) {
        destinationIdBySlug.set(destSpec.slug, existing.id);
      } else {
        const created = await prisma.destination.create({
          data: {
            slug: destSpec.slug,
            name: destSpec.name,
            region: destSpec.region,
          },
          select: { id: true },
        });
        destinationIdBySlug.set(destSpec.slug, created.id);
        createdDestinationIds.push(created.id);
      }
    }

    const passwordPlain = "MatchEval#2026!";
    const passwordHash = await bcrypt.hash(passwordPlain, 8);

    for (const p of fixture.personas) {
      await prisma.user.create({
        data: {
          id: p.id,
          email: p.privateCanaries.email,
          passwordHash,
          isVerified: true,
          profile: {
            create: {
              displayName: p.displayName,
              bio: p.bio,
              nationality: p.nationality,
              languages: p.languages,
              isDiscoverable: p.isDiscoverable,
              phone: p.privateCanaries.phone,
              dateOfBirth: new Date(
                `${p.privateCanaries.dateOfBirth}T00:00:00.000Z`,
              ),
            },
          },
          preferences: {
            create: {
              travelStyle: p.travelStyle,
              interests: p.interests,
              dietaryNeeds: p.privateCanaries.dietaryNeeds,
              avoidances: p.privateCanaries.avoidances,
              budgetMin: p.privateCanaries.budgetMin,
              budgetMax: p.privateCanaries.budgetMax,
            },
          },
          safetyContacts: {
            create: {
              name: p.privateCanaries.safetyContactName,
              phone: p.privateCanaries.safetyContactPhone,
              relation: "family",
            },
          },
          safetyCheckins: {
            create: {
              latitude: p.privateCanaries.safetyCheckinLat,
              longitude: p.privateCanaries.safetyCheckinLng,
              note: p.privateCanaries.safetyCheckinNote,
            },
          },
        },
      });

      for (const t of p.trips) {
        const destId = destinationIdBySlug.get(t.destinationSlug);
        if (!destId) {
          throw new Error(
            `Missing destination ID for slug ${t.destinationSlug}`,
          );
        }
        await prisma.trip.create({
          data: {
            userId: p.id,
            destinationId: destId,
            title: `Chuyến đi ${t.destinationSlug} của ${p.code}`,
            description: p.privateCanaries.privateTripNote,
            totalBudget: p.privateCanaries.privateTripBudget,
            startDate: new Date(`${t.startDate}T00:00:00.000Z`),
            endDate: new Date(`${t.endDate}T00:00:00.000Z`),
            status: t.status as TripStatus,
            travelStyle: p.travelStyle,
            interests: p.interests,
          },
        });
      }

      const loginRes = await http()
        .post("/auth/login")
        .send({ email: p.privateCanaries.email, password: passwordPlain })
        .expect(200);
      tokenByCode.set(p.code, loginRes.body.data.access_token as string);
    }

    for (const blk of fixture.initialBlocks) {
      const blocker = personaByCode.get(blk.blockerCode)!;
      const blocked = personaByCode.get(blk.blockedCode)!;
      await prisma.userBlock.create({
        data: {
          blockerId: blocker.id,
          blockedId: blocked.id,
        },
      });
    }
  });

  afterAll(async () => {
    if (prisma) {
      await purgeFixtureUsers();
      if (createdDestinationIds.length > 0) {
        await prisma.destination.deleteMany({
          where: { id: { in: createdDestinationIds } },
        });
      }
      if (preExistingDiscoverableUserIds.length > 0) {
        await prisma.profile.updateMany({
          where: { userId: { in: preExistingDiscoverableUserIds } },
          data: { isDiscoverable: true },
        });
      }
    }
    if (app) {
      await app.close();
    }
  });

  it("1) Verifies frozen relevance matrix integrity & measures nDCG@5 and Precision@5 with transparent cohort separation", async () => {
    expect(fixture.evaluationId).toBe("MATCH-EVAL-01");
    expect(fixture.frozenBeforeMeasurement).toBe(true);
    expect(fixture.seed).toBe(20261125);
    expect(fixture.personas).toHaveLength(12);

    const initialBlockSet = new Set<string>();
    for (const b of fixture.initialBlocks) {
      initialBlockSet.add(`${b.blockerCode}:${b.blockedCode}`);
      initialBlockSet.add(`${b.blockedCode}:${b.blockerCode}`);
    }

    // Verify frozen relevanceMatrix matches documented rubric for every eligible pair
    for (const [viewerCode, row] of Object.entries(fixture.relevanceMatrix)) {
      const viewer = personaByCode.get(viewerCode)!;
      for (const peer of fixture.personas) {
        if (peer.code === viewerCode) continue;
        const isIneligible =
          !peer.isDiscoverable ||
          initialBlockSet.has(`${viewerCode}:${peer.code}`);
        if (isIneligible) {
          expect(row[peer.code]).toBeUndefined();
        } else {
          expect(row[peer.code]).toBe(computeRubricGrade(viewer, peer));
        }
      }
    }

    const k = fixture.rankingSpecification.k;
    const relCutoff = fixture.rankingSpecification.binaryRelevanceCutoff;
    rankingRows = [];

    for (const q of fixture.queries) {
      const viewer = personaByCode.get(q.viewerCode)!;
      const token = tokenByCode.get(q.viewerCode)!;
      const destId = q.destinationSlug
        ? destinationIdBySlug.get(q.destinationSlug)!
        : undefined;

      const url = destId
        ? `/matches/candidates?destinationId=${destId}&limit=${k}`
        : `/matches/candidates?limit=${k}`;
      const res = await http()
        .get(url)
        .set("Authorization", `Bearer ${token}`)
        .expect(200);

      const items = res.body.data.items as Array<{
        peer: { id: string };
        compatibilityScore: number;
      }>;

      if (!viewer.isDiscoverable) {
        expect(res.body.data.isDiscoverable).toBe(false);
        expect(items).toEqual([]);
        rankingRows.push({
          queryId: q.queryId,
          viewerCode: q.viewerCode,
          destinationSlug: q.destinationSlug,
          cohort: "OPTED_OUT_VIEWER",
          eligiblePoolSize: 0,
          positiveBinaryLabelCount: 0,
          positiveGradedLabelCount: 0,
          returnedCount: 0,
          returnedTop5Codes: [],
          returnedTop5Grades: [],
          returnedTop5Scores: [],
          dcgAt5: 0,
          idcgAt5: 0,
          ndcgAt5: null,
          precisionAt5Strict: null,
          precisionAtMin5Pool: null,
          ineligibleReturnedCount: 0,
        });
        continue;
      }

      const eligiblePeers = fixture.personas.filter((peer) => {
        if (peer.code === viewer.code) return false;
        if (!peer.isDiscoverable) return false;
        if (initialBlockSet.has(`${viewer.code}:${peer.code}`)) return false;
        if (
          q.destinationSlug &&
          !peer.trips.some((t) => t.destinationSlug === q.destinationSlug)
        ) {
          return false;
        }
        return true;
      });
      const eligibleCodeSet = new Set(eligiblePeers.map((p) => p.code));
      const matrixRow = fixture.relevanceMatrix[viewer.code] ?? {};

      let ineligibleReturnedCount = 0;
      const returnedTop5Codes: string[] = [];
      const returnedTop5Grades: number[] = [];
      const returnedTop5Scores: number[] = [];

      for (const item of items) {
        const peerCode =
          codeByUserId.get(item.peer.id) ?? `UNKNOWN:${item.peer.id}`;
        returnedTop5Codes.push(peerCode);
        returnedTop5Scores.push(item.compatibilityScore);
        if (!eligibleCodeSet.has(peerCode)) {
          ineligibleReturnedCount++;
          returnedTop5Grades.push(0);
        } else {
          returnedTop5Grades.push(matrixRow[peerCode] ?? 0);
        }
      }

      expect(ineligibleReturnedCount).toBe(0);

      const idealGradesDesc = eligiblePeers
        .map((p) => matrixRow[p.code] ?? 0)
        .sort((a, b) => b - a);
      const positiveBinaryLabelCount = idealGradesDesc.filter(
        (g) => g >= relCutoff,
      ).length;
      const positiveGradedLabelCount = idealGradesDesc.filter(
        (g) => g > 0,
      ).length;

      const dcgAt5 = computeDcg(returnedTop5Grades, k);
      const idcgAt5 = computeDcg(idealGradesDesc, k);
      const ndcgAt5 = idcgAt5 > 0 ? round4(dcgAt5 / idcgAt5) : null;

      const relevantInTop5 = returnedTop5Grades.filter(
        (g) => g >= relCutoff,
      ).length;
      const precisionAt5Strict =
        positiveBinaryLabelCount > 0 && eligiblePeers.length > 0
          ? round4(relevantInTop5 / k)
          : null;
      const precisionAtMin5Pool =
        positiveBinaryLabelCount > 0 && eligiblePeers.length > 0
          ? round4(relevantInTop5 / Math.min(k, eligiblePeers.length))
          : null;

      let actualCohort: QueryFixture["expectedCohort"] = "FULL_POOL";
      if (
        eligiblePeers.length < k &&
        (positiveBinaryLabelCount > 0 || eligiblePeers.length === 0)
      ) {
        actualCohort = "UNDERFILLED_POOL";
      }
      if (eligiblePeers.length >= k && positiveBinaryLabelCount === 0) {
        actualCohort = "ZERO_RELEVANT_LABELS";
      }
      expect(actualCohort).toBe(q.expectedCohort);

      rankingRows.push({
        queryId: q.queryId,
        viewerCode: q.viewerCode,
        destinationSlug: q.destinationSlug,
        cohort: actualCohort,
        eligiblePoolSize: eligiblePeers.length,
        positiveBinaryLabelCount,
        positiveGradedLabelCount,
        returnedCount: items.length,
        returnedTop5Codes,
        returnedTop5Grades,
        returnedTop5Scores,
        dcgAt5: round4(dcgAt5),
        idcgAt5: round4(idcgAt5),
        ndcgAt5,
        precisionAt5Strict,
        precisionAtMin5Pool,
        ineligibleReturnedCount,
      });
    }

    // Verify deterministic tie-break on Q02: P01 (UUID ...0001) must precede P12 (UUID ...0012) when both score 100
    const q02 = rankingRows.find((r) => r.queryId === "Q02")!;
    expect(q02.returnedTop5Codes.slice(0, 2)).toEqual(["P01", "P12"]);

    const fullPoolRows = rankingRows.filter((r) => r.cohort === "FULL_POOL");
    const evaluableLabeledRows = rankingRows.filter(
      (r) => r.ndcgAt5 !== null && r.precisionAt5Strict !== null,
    );
    expect(fullPoolRows).toHaveLength(7);
    expect(evaluableLabeledRows).toHaveLength(9);
  });

  it("2) Executes 1,000 simulated requests with 0 PII/private leaks and 0 non-consensual MATCHED transitions", async () => {
    const rng = createMulberry32(fixture.seed);
    const privacyLeaks: PrivacyLeakFinding[] = [];
    const consentViolations: ConsentViolationFinding[] = [];
    const authorizedDualConsentMatchIds = new Set<string>();

    let executedRequests = 0;
    let stateTransitionAttempts = 0;
    let acceptTransitionAttempts = 0;
    let unauthorizedAcceptAttemptsRejected = 0;
    let validMatchedTransitions = 0;

    const categoryCounts: Record<string, number> = {
      discovery_candidates: 0,
      discovery_consent_toggle: 0,
      matches_and_blocks_management: 0,
      masked_profile_valid: 0,
      masked_profile_opted_out: 0,
      masked_profile_blocked_or_self: 0,
      invite_send_request: 0,
      invite_withdraw: 0,
      invite_respond: 0,
    };

    const statusCounts: Record<string, number> = {};

    async function callAuditedHttp(params: {
      category: keyof typeof categoryCounts;
      method: "GET" | "POST" | "PATCH" | "DELETE";
      endpoint: string;
      actorCode: string;
      body?: Record<string, unknown>;
    }): Promise<request.Response> {
      const token = tokenByCode.get(params.actorCode)!;
      let reqBuilder = http()
        [params.method.toLowerCase() as "get" | "post" | "patch" | "delete"](
          params.endpoint,
        )
        .set("Authorization", `Bearer ${token}`);

      if (params.body !== undefined) {
        reqBuilder = reqBuilder.send(params.body);
      }

      const res = await reqBuilder;
      executedRequests++;
      categoryCounts[params.category]++;
      const statusKey = String(res.status);
      statusCounts[statusKey] = (statusCounts[statusKey] ?? 0) + 1;

      const rawText = res.text ?? JSON.stringify(res.body ?? {});

      // 1. Scan raw body against every persona canary string
      for (const canary of allCanarySubstrings) {
        if (rawText.includes(canary)) {
          privacyLeaks.push({
            requestIndex: executedRequests,
            category: params.category,
            method: params.method,
            endpoint: params.endpoint,
            httpStatus: res.status,
            reason: `Raw body contained canary value "${canary}"`,
          });
          break;
        }
      }

      // 2. Scan raw body against phone & email patterns
      if (vnPhoneRegex.test(rawText)) {
        privacyLeaks.push({
          requestIndex: executedRequests,
          category: params.category,
          method: params.method,
          endpoint: params.endpoint,
          httpStatus: res.status,
          reason: "Raw body matched Vietnamese phone number regex",
        });
      }
      if (secretEmailRegex.test(rawText)) {
        privacyLeaks.push({
          requestIndex: executedRequests,
          category: params.category,
          method: params.method,
          endpoint: params.endpoint,
          httpStatus: res.status,
          reason: "Raw body matched private canary email regex",
        });
      }

      // 3. Scan parsed JSON object tree for forbidden private keys
      const forbiddenPaths = findForbiddenKeys(res.body);
      if (forbiddenPaths.length > 0) {
        privacyLeaks.push({
          requestIndex: executedRequests,
          category: params.category,
          method: params.method,
          endpoint: params.endpoint,
          httpStatus: res.status,
          reason: `Response JSON exposed forbidden private keys: ${forbiddenPaths.join(", ")}`,
        });
      }

      return res;
    }

    /**
     * Audits a `PATCH /matches/:id/respond` call against live PostgreSQL ground-truth
     * consent & block state immediately before execution.
     */
    async function auditedRespond(
      matchId: string,
      actorCode: string,
      action: "ACCEPTED" | "REJECTED",
    ): Promise<request.Response> {
      const actor = personaByCode.get(actorCode)!;
      const preMatch = await prisma.match.findUnique({
        where: { id: matchId },
        include: {
          sender: {
            select: {
              deletedAt: true,
              profile: { select: { isDiscoverable: true } },
            },
          },
          receiver: {
            select: {
              deletedAt: true,
              profile: { select: { isDiscoverable: true } },
            },
          },
        },
      });

      let hasExplicitDualConsent = false;
      if (preMatch) {
        const blockRow = await prisma.userBlock.findFirst({
          where: {
            OR: [
              { blockerId: preMatch.senderId, blockedId: preMatch.receiverId },
              { blockerId: preMatch.receiverId, blockedId: preMatch.senderId },
            ],
          },
          select: { id: true },
        });
        hasExplicitDualConsent =
          action === "ACCEPTED" &&
          preMatch.status === MatchStatus.PENDING &&
          preMatch.receiverId === actor.id &&
          preMatch.sender.deletedAt === null &&
          Boolean(preMatch.sender.profile?.isDiscoverable) &&
          preMatch.receiver.deletedAt === null &&
          Boolean(preMatch.receiver.profile?.isDiscoverable) &&
          blockRow === null;
      }

      stateTransitionAttempts++;
      if (action === "ACCEPTED") {
        acceptTransitionAttempts++;
      }

      const res = await callAuditedHttp({
        category: "invite_respond",
        method: "PATCH",
        endpoint: `/matches/${matchId}/respond`,
        actorCode,
        body: { action },
      });

      const postMatch = await prisma.match.findUnique({
        where: { id: matchId },
        select: { status: true },
      });

      const becameMatched =
        res.body?.data?.status === "ACCEPTED" ||
        res.body?.data?.handshakeState === "MATCHED" ||
        res.body?.data?.isMatched === true ||
        (preMatch?.status !== MatchStatus.ACCEPTED &&
          postMatch?.status === MatchStatus.ACCEPTED);

      if (becameMatched) {
        if (!hasExplicitDualConsent) {
          consentViolations.push({
            requestIndex: executedRequests,
            endpoint: `/matches/${matchId}/respond`,
            matchId,
            actorCode,
            reason:
              "Transitioned to MATCHED/ACCEPTED without explicit dual consent & unblocked state",
          });
        } else {
          validMatchedTransitions++;
          authorizedDualConsentMatchIds.add(matchId);
        }
      } else if (action === "ACCEPTED" && !hasExplicitDualConsent) {
        unauthorizedAcceptAttemptsRejected++;
      }

      return res;
    }

    async function auditedSendRequest(
      senderCode: string,
      receiverCode: string,
    ): Promise<request.Response> {
      stateTransitionAttempts++;
      const receiver = personaByCode.get(receiverCode)!;
      const res = await callAuditedHttp({
        category: "invite_send_request",
        method: "POST",
        endpoint: "/matches/request",
        actorCode: senderCode,
        body: { receiverId: receiver.id },
      });

      if (
        res.body?.data?.status === "ACCEPTED" ||
        res.body?.data?.handshakeState === "MATCHED" ||
        res.body?.data?.isMatched === true
      ) {
        consentViolations.push({
          requestIndex: executedRequests,
          endpoint: "/matches/request",
          matchId: String(res.body?.data?.id ?? "unknown"),
          actorCode: senderCode,
          reason:
            "POST /matches/request jumped directly to MATCHED without receiver consent",
        });
      }
      return res;
    }

    async function auditedWithdraw(
      matchId: string,
      actorCode: string,
    ): Promise<request.Response> {
      stateTransitionAttempts++;
      return callAuditedHttp({
        category: "invite_withdraw",
        method: "PATCH",
        endpoint: `/matches/${matchId}/withdraw`,
        actorCode,
      });
    }

    const discoverableCodes = [
      "P01",
      "P02",
      "P03",
      "P04",
      "P05",
      "P06",
      "P07",
      "P08",
      "P09",
      "P10",
    ];
    const allCodes = fixture.personas.map((p) => p.code);
    const destSlugs = fixture.requiredDestinations.map((d) => d.slug);

    // =========================================================================
    // PHASE 2A: Deterministic Core Handshake & Adversarial Consent Scenarios
    // =========================================================================

    // Scenario 1 (Positive dual-opt-in path #1): P01 -> P02 -> P02 accepts -> MATCHED
    const s1Req = await auditedSendRequest("P01", "P02");
    expect(s1Req.status).toBe(201);
    const mP01P02 = s1Req.body.data.id as string;
    // Sender P01 tries to self-accept -> must fail 403
    const s1SelfAccept = await auditedRespond(mP01P02, "P01", "ACCEPTED");
    expect(s1SelfAccept.status).toBe(403);
    // Third-party P03 tries to accept P01->P02 -> must fail 403
    const s1ThirdParty = await auditedRespond(mP01P02, "P03", "ACCEPTED");
    expect(s1ThirdParty.status).toBe(403);
    // Receiver P02 accepts -> 200 MATCHED
    const s1Accept = await auditedRespond(mP01P02, "P02", "ACCEPTED");
    expect(s1Accept.status).toBe(200);
    expect(s1Accept.body.data.handshakeState).toBe("MATCHED");
    expect(s1Accept.body.data.isMatched).toBe(true);
    // Duplicate accept on already-MATCHED invite -> 400
    const s1DupAccept = await auditedRespond(mP01P02, "P02", "ACCEPTED");
    expect(s1DupAccept.status).toBe(400);
    // Duplicate send request on already-MATCHED pair (both directions) -> 409
    expect((await auditedSendRequest("P01", "P02")).status).toBe(409);
    expect((await auditedSendRequest("P02", "P01")).status).toBe(409);

    // Scenario 2 (Positive dual-opt-in path #2): P05 -> P06 -> P06 accepts -> MATCHED
    const s2Req = await auditedSendRequest("P05", "P06");
    expect(s2Req.status).toBe(201);
    const mP05P06 = s2Req.body.data.id as string;
    const s2Accept = await auditedRespond(mP05P06, "P06", "ACCEPTED");
    expect(s2Accept.status).toBe(200);
    expect(s2Accept.body.data.isMatched).toBe(true);

    // Scenario 3 (Positive dual-opt-in path #3): P07 -> P08 -> P08 accepts -> MATCHED
    const s3Req = await auditedSendRequest("P07", "P08");
    expect(s3Req.status).toBe(201);
    const mP07P08 = s3Req.body.data.id as string;
    const s3Accept = await auditedRespond(mP07P08, "P08", "ACCEPTED");
    expect(s3Accept.status).toBe(200);
    expect(s3Accept.body.data.isMatched).toBe(true);

    // Scenario 4 (Sender withdraws invite before receiver accepts -> re-send -> positive accept #4): P01 -> P03
    const s4Req = await auditedSendRequest("P01", "P03");
    expect(s4Req.status).toBe(201);
    const mP01P03First = s4Req.body.data.id as string;
    // Receiver P03 cannot withdraw sender's invite -> 403
    expect((await auditedWithdraw(mP01P03First, "P03")).status).toBe(403);
    // Sender P01 withdraws -> 200 WITHDRAWN
    expect((await auditedWithdraw(mP01P03First, "P01")).status).toBe(200);
    // Duplicate withdraw -> 400
    expect((await auditedWithdraw(mP01P03First, "P01")).status).toBe(400);
    // Receiver P03 attempts to accept withdrawn invite -> 400
    expect((await auditedRespond(mP01P03First, "P03", "ACCEPTED")).status).toBe(
      400,
    );
    // Re-sending after WITHDRAWN succeeds -> P03 accepts -> positive MATCHED #4
    const s4Resend = await auditedSendRequest("P01", "P03");
    expect(s4Resend.status).toBe(201);
    const mP01P03Second = s4Resend.body.data.id as string;
    expect(
      (await auditedRespond(mP01P03Second, "P03", "ACCEPTED")).status,
    ).toBe(200);

    // Scenario 5 (Sender turns off discovery opt-in BEFORE receiver accepts): P04 -> P09
    const s5Req = await auditedSendRequest("P04", "P09");
    expect(s5Req.status).toBe(201);
    const mP04P09 = s5Req.body.data.id as string;
    // P04 revokes discovery consent
    await callAuditedHttp({
      category: "discovery_consent_toggle",
      method: "PATCH",
      endpoint: "/matches/discovery",
      actorCode: "P04",
      body: { isDiscoverable: false },
    });
    // Receiver P09 tries to accept while sender P04 has isDiscoverable=false -> 409 Conflict!
    expect((await auditedRespond(mP04P09, "P09", "ACCEPTED")).status).toBe(409);
    // P04 re-enables discovery consent -> now both consent -> P09 accepts -> positive MATCHED #5
    await callAuditedHttp({
      category: "discovery_consent_toggle",
      method: "PATCH",
      endpoint: "/matches/discovery",
      actorCode: "P04",
      body: { isDiscoverable: true },
    });
    expect((await auditedRespond(mP04P09, "P09", "ACCEPTED")).status).toBe(200);

    // Scenario 6 (Block created while invite is PENDING): P02 -> P04, then P04 blocks P02
    const s6Req = await auditedSendRequest("P02", "P04");
    expect(s6Req.status).toBe(201);
    const mP02P04 = s6Req.body.data.id as string;
    await callAuditedHttp({
      category: "matches_and_blocks_management",
      method: "POST",
      endpoint: "/matches/blocks",
      actorCode: "P04",
      body: { blockedUserId: personaByCode.get("P02")!.id },
    });
    // Accepting after block must fail (block auto-rejected PENDING match + block check)
    expect(
      [400, 403].includes(
        (await auditedRespond(mP02P04, "P04", "ACCEPTED")).status,
      ),
    ).toBe(true);
    // Unblock P02 so clean state resumes
    await callAuditedHttp({
      category: "matches_and_blocks_management",
      method: "DELETE",
      endpoint: `/matches/blocks/${personaByCode.get("P02")!.id}`,
      actorCode: "P04",
    });

    // Scenario 7 (Explicit rejection path): P03 -> P09 -> P09 rejects -> REJECTED
    const s7Req = await auditedSendRequest("P03", "P09");
    expect(s7Req.status).toBe(201);
    const mP03P09 = s7Req.body.data.id as string;
    expect((await auditedRespond(mP03P09, "P09", "REJECTED")).status).toBe(200);
    // Attempting to accept after REJECTED -> 400
    expect((await auditedRespond(mP03P09, "P09", "ACCEPTED")).status).toBe(400);

    const knownMatchIds = [
      mP01P02,
      mP05P06,
      mP07P08,
      mP01P03First,
      mP01P03Second,
      mP04P09,
      mP02P04,
      mP03P09,
    ];

    // =========================================================================
    // PHASE 2B: Complete Remaining Quota up to Exactly 1,000 Requests
    // Target allocation:
    // - Nhóm 1 (Tìm bạn, đồng thuận & chặn): 400 requests
    //   * discovery_candidates: 240
    //   * discovery_consent_toggle: 60
    //   * matches_and_blocks_management: 100
    // - Nhóm 2 (Xem hồ sơ rút gọn): 300 requests
    //   * masked_profile_valid: 180
    //   * masked_profile_opted_out: 50
    //   * masked_profile_blocked_or_self: 70
    // - Nhóm 3 (Xử lý lời mời & đồng thuận): 300 requests
    //   * invite_send_request: 110
    //   * invite_withdraw: 40
    //   * invite_respond: 150
    // =========================================================================

    // 1. Fill `discovery_candidates` to 240
    while (categoryCounts.discovery_candidates < 240) {
      const actorCode = allCodes[Math.floor(rng() * allCodes.length)];
      const useDestFilter = rng() < 0.45;
      const limit = 5 + Math.floor(rng() * 16);
      if (useDestFilter) {
        const slug = destSlugs[Math.floor(rng() * destSlugs.length)];
        const destId = destinationIdBySlug.get(slug)!;
        await callAuditedHttp({
          category: "discovery_candidates",
          method: "GET",
          endpoint: `/matches/candidates?destinationId=${destId}&limit=${limit}`,
          actorCode,
        });
      } else {
        await callAuditedHttp({
          category: "discovery_candidates",
          method: "GET",
          endpoint: `/matches/candidates?limit=${limit}`,
          actorCode,
        });
      }
    }

    // 2. Fill `discovery_consent_toggle` to 60 (keeping P11 false & P01..P10,P12 true after pairs)
    while (categoryCounts.discovery_consent_toggle < 60) {
      const remaining = 60 - categoryCounts.discovery_consent_toggle;
      const actorCode =
        discoverableCodes[Math.floor(rng() * discoverableCodes.length)];
      if (remaining >= 3 && rng() < 0.5) {
        await callAuditedHttp({
          category: "discovery_consent_toggle",
          method: "PATCH",
          endpoint: "/matches/discovery",
          actorCode,
          body: { isDiscoverable: false },
        });
        await callAuditedHttp({
          category: "discovery_consent_toggle",
          method: "GET",
          endpoint: "/matches/discovery",
          actorCode,
        });
        await callAuditedHttp({
          category: "discovery_consent_toggle",
          method: "PATCH",
          endpoint: "/matches/discovery",
          actorCode,
          body: { isDiscoverable: true },
        });
      } else {
        const checkActor = allCodes[Math.floor(rng() * allCodes.length)];
        await callAuditedHttp({
          category: "discovery_consent_toggle",
          method: "GET",
          endpoint: "/matches/discovery",
          actorCode: checkActor,
        });
      }
    }

    // 3. Fill `matches_and_blocks_management` to 100
    while (categoryCounts.matches_and_blocks_management < 100) {
      const remaining = 100 - categoryCounts.matches_and_blocks_management;
      const actorCode = allCodes[Math.floor(rng() * allCodes.length)];
      const roll = rng();
      if (remaining >= 2 && roll < 0.25) {
        // Temporary block & unblock between P10 and P08 (disjoint pair with no active match)
        await callAuditedHttp({
          category: "matches_and_blocks_management",
          method: "POST",
          endpoint: "/matches/blocks",
          actorCode: "P10",
          body: { blockedUserId: personaByCode.get("P08")!.id },
        });
        await callAuditedHttp({
          category: "matches_and_blocks_management",
          method: "DELETE",
          endpoint: `/matches/blocks/${personaByCode.get("P08")!.id}`,
          actorCode: "P10",
        });
      } else if (roll < 0.65) {
        await callAuditedHttp({
          category: "matches_and_blocks_management",
          method: "GET",
          endpoint: "/matches",
          actorCode,
        });
      } else if (roll < 0.9) {
        await callAuditedHttp({
          category: "matches_and_blocks_management",
          method: "GET",
          endpoint: "/matches/blocks",
          actorCode,
        });
      } else {
        // Self-block negative guard (400)
        await callAuditedHttp({
          category: "matches_and_blocks_management",
          method: "POST",
          endpoint: "/matches/blocks",
          actorCode,
          body: { blockedUserId: personaByCode.get(actorCode)!.id },
        });
      }
    }

    // 4. Fill `masked_profile_valid` to 180
    while (categoryCounts.masked_profile_valid < 180) {
      const viewerCode =
        discoverableCodes[Math.floor(rng() * discoverableCodes.length)];
      let peerCode =
        discoverableCodes[Math.floor(rng() * discoverableCodes.length)];
      if (peerCode === viewerCode) {
        peerCode = viewerCode === "P01" ? "P02" : "P01";
      }
      const res = await callAuditedHttp({
        category: "masked_profile_valid",
        method: "GET",
        endpoint: `/matches/peers/${personaByCode.get(peerCode)!.id}`,
        actorCode: viewerCode,
      });
      expect(res.status).toBe(200);
    }

    // 5. Fill `masked_profile_opted_out` to 50 (viewing P11 who has isDiscoverable=false -> 404)
    while (categoryCounts.masked_profile_opted_out < 50) {
      const viewerCode =
        discoverableCodes[Math.floor(rng() * discoverableCodes.length)];
      const res = await callAuditedHttp({
        category: "masked_profile_opted_out",
        method: "GET",
        endpoint: `/matches/peers/${personaByCode.get("P11")!.id}`,
        actorCode: viewerCode,
      });
      expect(res.status).toBe(404);
    }

    // 6. Fill `masked_profile_blocked_or_self` to 70 (P01<->P12, P05<->P12 two-way blocks & self views)
    const blockedAndSelfPairs: Array<[string, string, number]> = [
      ["P01", "P12", 403],
      ["P12", "P01", 403],
      ["P05", "P12", 403],
      ["P12", "P05", 403],
      ["P01", "P01", 400],
      ["P05", "P05", 400],
      ["P08", "P08", 400],
    ];
    while (categoryCounts.masked_profile_blocked_or_self < 70) {
      const [viewerCode, targetCode, expectedStatus] =
        blockedAndSelfPairs[Math.floor(rng() * blockedAndSelfPairs.length)];
      const res = await callAuditedHttp({
        category: "masked_profile_blocked_or_self",
        method: "GET",
        endpoint: `/matches/peers/${personaByCode.get(targetCode)!.id}`,
        actorCode: viewerCode,
      });
      expect(res.status).toBe(expectedStatus);
    }

    // 7. Coordinated reversible send + withdraw cycles on (P06 <-> P08) & (P09 <-> P10)
    // plus adversarial send/withdraw/respond probes to hit exact quotas (110 / 40 / 150)
    const cyclePairs: Array<[string, string]> = [
      ["P06", "P08"],
      ["P08", "P06"],
      ["P09", "P10"],
      ["P10", "P09"],
    ];
    let cycleIdx = 0;
    while (
      categoryCounts.invite_withdraw < 28 &&
      categoryCounts.invite_send_request < 95
    ) {
      const [senderCode, receiverCode] =
        cyclePairs[cycleIdx % cyclePairs.length];
      cycleIdx++;
      const sendRes = await auditedSendRequest(senderCode, receiverCode);
      expect(sendRes.status).toBe(201);
      const tempMatchId = sendRes.body.data.id as string;
      knownMatchIds.push(tempMatchId);

      // Sender self-accept attempt while PENDING -> 403
      if (categoryCounts.invite_respond < 140) {
        const selfTry = await auditedRespond(
          tempMatchId,
          senderCode,
          "ACCEPTED",
        );
        expect(selfTry.status).toBe(403);
      }

      // Sender withdraws -> 200 WITHDRAWN
      const wdRes = await auditedWithdraw(tempMatchId, senderCode);
      expect(wdRes.status).toBe(200);

      // Receiver tries to accept after withdrawal -> 400
      if (categoryCounts.invite_respond < 140) {
        const lateAccept = await auditedRespond(
          tempMatchId,
          receiverCode,
          "ACCEPTED",
        );
        expect(lateAccept.status).toBe(400);
      }
    }

    // Create one more final positive MATCHED pair (P06 -> P10 -> P10 accepts)
    if (
      categoryCounts.invite_send_request < 110 &&
      categoryCounts.invite_respond < 150
    ) {
      const finalPosReq = await auditedSendRequest("P06", "P10");
      expect(finalPosReq.status).toBe(201);
      const mP06P10 = finalPosReq.body.data.id as string;
      knownMatchIds.push(mP06P10);
      const finalPosAcc = await auditedRespond(mP06P10, "P10", "ACCEPTED");
      expect(finalPosAcc.status).toBe(200);
      expect(finalPosAcc.body.data.isMatched).toBe(true);
    }

    // Fill remaining `invite_send_request` to 110 with adversarial / duplicate / opted-out / blocked requests
    const adversarialSendCases: Array<[string, string]> = [
      ["P01", "P12"], // outbound blocked -> 403
      ["P12", "P01"], // inbound blocked -> 403
      ["P05", "P12"], // inbound blocked -> 403
      ["P12", "P05"], // outbound blocked -> 403
      ["P01", "P11"], // receiver opted-out -> 404
      ["P11", "P01"], // sender opted-out -> 403
      ["P01", "P02"], // duplicate matched -> 409
      ["P02", "P01"], // reverse duplicate matched -> 409
      ["P01", "P01"], // self request -> 400
    ];
    while (categoryCounts.invite_send_request < 110) {
      const [sCode, rCode] =
        adversarialSendCases[Math.floor(rng() * adversarialSendCases.length)];
      const res = await auditedSendRequest(sCode, rCode);
      expect(res.status).toBeGreaterThanOrEqual(400);
      expect(res.status).toBeLessThan(500);
    }

    // Fill remaining `invite_withdraw` to 40 with unauthorized / duplicate withdraw attempts
    while (categoryCounts.invite_withdraw < 40) {
      const matchId = knownMatchIds[Math.floor(rng() * knownMatchIds.length)];
      const actorCode =
        discoverableCodes[Math.floor(rng() * discoverableCodes.length)];
      const res = await auditedWithdraw(matchId, actorCode);
      expect(res.status).toBeGreaterThanOrEqual(400);
      expect(res.status).toBeLessThan(500);
    }

    // Fill remaining `invite_respond` to 150 with unauthorized / duplicate / withdrawn / opted-out respond attempts
    while (categoryCounts.invite_respond < 150) {
      const matchId = knownMatchIds[Math.floor(rng() * knownMatchIds.length)];
      const actorCode = allCodes[Math.floor(rng() * allCodes.length)];
      const action: "ACCEPTED" | "REJECTED" =
        rng() < 0.85 ? "ACCEPTED" : "REJECTED";
      const res = await auditedRespond(matchId, actorCode, action);
      expect(res.status).toBeGreaterThanOrEqual(400);
      expect(res.status).toBeLessThan(500);
    }

    // =========================================================================
    // PHASE 2C: Final Invariant Assertions & PostgreSQL Ground-Truth Reconciliation
    // =========================================================================
    const personaIds = fixture.personas.map((p) => p.id);
    const dbAcceptedMatches = await prisma.match.findMany({
      where: {
        status: MatchStatus.ACCEPTED,
        OR: [
          { senderId: { in: personaIds } },
          { receiverId: { in: personaIds } },
        ],
      },
      select: { id: true, senderId: true, receiverId: true },
    });

    for (const row of dbAcceptedMatches) {
      if (!authorizedDualConsentMatchIds.has(row.id)) {
        consentViolations.push({
          requestIndex: executedRequests,
          endpoint: "DB_RECONCILIATION",
          matchId: row.id,
          actorCode: codeByUserId.get(row.receiverId) ?? row.receiverId,
          reason:
            "PostgreSQL contains an ACCEPTED match that was never authorized via dual consent",
        });
      }
    }

    // Compute aggregate ranking summary
    const fullPoolRows = rankingRows.filter((r) => r.cohort === "FULL_POOL");
    const underfilledWithLabels = rankingRows.filter(
      (r) => r.cohort === "UNDERFILLED_POOL" && r.ndcgAt5 !== null,
    );
    const allLabeledRows = [...fullPoolRows, ...underfilledWithLabels];

    const mean = (nums: number[]) =>
      nums.length > 0
        ? round4(nums.reduce((acc, v) => acc + v, 0) / nums.length)
        : null;

    const summaryReport = {
      evaluationId: fixture.evaluationId,
      fixturePath: "apps/backend/test/fixtures/match-eval-01.personas.json",
      seed: fixture.seed,
      personaCount: fixture.personas.length,
      queryCount: rankingRows.length,
      queryCohortCounts: {
        fullPoolGte5: fullPoolRows.length,
        underfilledPoolLt5: rankingRows.filter(
          (r) => r.cohort === "UNDERFILLED_POOL",
        ).length,
        zeroRelevantLabels: rankingRows.filter(
          (r) => r.cohort === "ZERO_RELEVANT_LABELS",
        ).length,
        optedOutViewer: rankingRows.filter(
          (r) => r.cohort === "OPTED_OUT_VIEWER",
        ).length,
      },
      rankingMetrics: {
        macroAllLabeledQueriesCount: allLabeledRows.length,
        macroAllLabeledNdcgAt5: mean(
          allLabeledRows.map((r) => r.ndcgAt5 as number),
        ),
        macroAllLabeledPrecisionAt5Strict: mean(
          allLabeledRows.map((r) => r.precisionAt5Strict as number),
        ),
        macroAllLabeledPrecisionAtMin5Pool: mean(
          allLabeledRows.map((r) => r.precisionAtMin5Pool as number),
        ),
        macroFullPoolQueriesCount: fullPoolRows.length,
        macroFullPoolNdcgAt5: mean(
          fullPoolRows.map((r) => r.ndcgAt5 as number),
        ),
        macroFullPoolPrecisionAt5Strict: mean(
          fullPoolRows.map((r) => r.precisionAt5Strict as number),
        ),
        ineligibleCandidatesReturnedTotal: rankingRows.reduce(
          (s, r) => s + r.ineligibleReturnedCount,
          0,
        ),
        approvedRoadmapThreshold:
          fixture.rankingSpecification.approvedRoadmapThreshold,
        rankingGateStatus: "MEASURED_NO_APPROVED_CUTOFF_IN_ROADMAP",
      },
      perQueryRanking: rankingRows,
      privacyAudit: {
        targetSimulatedRequests: 1000,
        executedRequests,
        requestAllocationByGroup: {
          buddyDiscoveryAndBlocks:
            categoryCounts.discovery_candidates +
            categoryCounts.discovery_consent_toggle +
            categoryCounts.matches_and_blocks_management,
          maskedProfileViews:
            categoryCounts.masked_profile_valid +
            categoryCounts.masked_profile_opted_out +
            categoryCounts.masked_profile_blocked_or_self,
          invitationHandling:
            categoryCounts.invite_send_request +
            categoryCounts.invite_withdraw +
            categoryCounts.invite_respond,
        },
        requestAllocationDetailed: categoryCounts,
        httpStatusDistribution: statusCounts,
        privacyLeakCount: privacyLeaks.length,
        privacyLeaks,
        privacyGateVerdict: privacyLeaks.length === 0 ? "PASS" : "FAIL",
      },
      consentAudit: {
        stateTransitionAttempts,
        acceptTransitionAttempts,
        unauthorizedAcceptAttemptsRejected,
        validMatchedTransitions,
        persistedMatchedRowsInDb: dbAcceptedMatches.length,
        unauthorizedMatchedTransitions: consentViolations.length,
        consentViolations,
        consentGateVerdict:
          consentViolations.length === 0 && validMatchedTransitions >= 1
            ? "PASS"
            : "FAIL",
      },
    };

    const reportOutPath = process.env.MATCH_EVAL_REPORT_PATH?.trim();
    if (reportOutPath) {
      fs.mkdirSync(path.dirname(reportOutPath), { recursive: true });
      fs.writeFileSync(
        reportOutPath,
        JSON.stringify(summaryReport, null, 2),
        "utf-8",
      );
    }

    // Print structured evidence to test log output
    // eslint-disable-next-line no-console
    console.log(
      `[MATCH-EVAL-01-SUMMARY]\n${JSON.stringify(summaryReport, null, 2)}`,
    );

    expect(executedRequests).toBe(1000);
    expect(privacyLeaks).toEqual([]);
    expect(consentViolations).toEqual([]);
    expect(validMatchedTransitions).toBeGreaterThanOrEqual(1);
    expect(dbAcceptedMatches.length).toBe(validMatchedTransitions);
    expect(stateTransitionAttempts).toBe(300);
  });
});
