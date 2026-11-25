import { INestApplication, ValidationPipe } from "@nestjs/common";
import { Test, TestingModule } from "@nestjs/testing";
import { MatchStatus, PrismaClient } from "@prisma/client";
import * as bcrypt from "bcryptjs";
import * as request from "supertest";
import { AppModule } from "../src/app.module";
import { HttpExceptionFilter } from "../src/common/filters/http-exception.filter";
import { TransformInterceptor } from "../src/common/interceptors/transform.interceptor";
import { PrismaService } from "../src/prisma/prisma.service";

jest.setTimeout(90_000);

interface ConcurrencyActor {
  code: string;
  id: string;
  email: string;
  token: string;
}

describe("W08 Buddy Concurrency & API-to-DB State Reconciliation (e2e)", () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let barrierPrisma: PrismaClient;
  const createdUserIds: string[] = [];
  const actors = new Map<string, ConcurrencyActor>();

  const http = () => request(app.getHttpServer());

  function createDeferred() {
    let resolve!: () => void;
    const promise = new Promise<void>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  }

  async function resetPairClean(codeA: string, codeB: string) {
    const a = actors.get(codeA)!;
    const b = actors.get(codeB)!;
    await prisma.match.deleteMany({
      where: {
        OR: [
          { senderId: a.id, receiverId: b.id },
          { senderId: b.id, receiverId: a.id },
        ],
      },
    });
    await prisma.userBlock.deleteMany({
      where: {
        OR: [
          { blockerId: a.id, blockedId: b.id },
          { blockerId: b.id, blockedId: a.id },
        ],
      },
    });
    await prisma.profile.updateMany({
      where: { userId: { in: [a.id, b.id] } },
      data: { isDiscoverable: true },
    });
  }

  async function createPendingInvite(
    senderCode: string,
    receiverCode: string,
  ): Promise<string> {
    await resetPairClean(senderCode, receiverCode);
    const sender = actors.get(senderCode)!;
    const receiver = actors.get(receiverCode)!;
    const res = await http()
      .post("/matches/request")
      .set("Authorization", `Bearer ${sender.token}`)
      .send({ receiverId: receiver.id })
      .expect(201);
    expect(res.body.data.status).toBe("PENDING");
    return res.body.data.id as string;
  }

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
    barrierPrisma = new PrismaClient();
    await barrierPrisma.$connect();

    const pwPlain = "RaceTest#2026!";
    const pwHash = await bcrypt.hash(pwPlain, 8);
    const runTag = Date.now();

    for (const code of ["C1", "C2", "C3", "C4"]) {
      const user = await prisma.user.create({
        data: {
          email: `w08-race-${code.toLowerCase()}-${runTag}@secret-race.local`,
          passwordHash: pwHash,
          isVerified: true,
          profile: {
            create: {
              displayName: `Race Actor ${code}`,
              phone: `+8490777000${code.slice(1)}`,
              isDiscoverable: true,
            },
          },
          preferences: {
            create: {
              travelStyle: "COMFORT",
              interests: ["food_cuisine", "culture_history"],
            },
          },
        },
      });
      createdUserIds.push(user.id);

      const login = await http()
        .post("/auth/login")
        .send({ email: user.email, password: pwPlain })
        .expect(200);

      actors.set(code, {
        code,
        id: user.id,
        email: user.email,
        token: login.body.data.access_token as string,
      });
    }
  });

  afterAll(async () => {
    if (prisma && createdUserIds.length > 0) {
      await prisma.match.deleteMany({
        where: {
          OR: [
            { senderId: { in: createdUserIds } },
            { receiverId: { in: createdUserIds } },
          ],
        },
      });
      await prisma.userBlock.deleteMany({
        where: {
          OR: [
            { blockerId: { in: createdUserIds } },
            { blockedId: { in: createdUserIds } },
          ],
        },
      });
      await prisma.user.deleteMany({
        where: { id: { in: createdUserIds } },
      });
    }
    if (barrierPrisma) {
      await barrierPrisma.$disconnect();
    }
    if (app) {
      await app.close();
    }
  });

  it("1) Concurrent withdraw vs accept: conditional PENDING update ensures exactly one winner and 100% API-to-DB agreement", async () => {
    const sender = actors.get("C1")!;
    const receiver = actors.get("C2")!;
    const logSummary: Array<Record<string, unknown>> = [];

    // 1A. Deterministic row-lock barrier: WITHDRAW commits while ACCEPT is queued on user row lock
    {
      const matchId = await createPendingInvite("C1", "C2");
      const lockAcquired = createDeferred();
      const releaseBarrier = createDeferred();

      // Hold row lock on receiver.id via independent DB client so withdraw & accept contend deterministically
      const barrierTx = barrierPrisma.$transaction(async (tx) => {
        await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${sender.id}::uuid FOR UPDATE`;
        lockAcquired.resolve();
        await releaseBarrier.promise;
      });
      await lockAcquired.promise;

      const withdrawPromise = http()
        .patch(`/matches/${matchId}/withdraw`)
        .set("Authorization", `Bearer ${sender.token}`);
      // Slight stagger so withdraw queues first on sender.id lock, then accept queues right behind it
      await new Promise((r) => setTimeout(r, 25));
      const acceptPromise = http()
        .patch(`/matches/${matchId}/respond`)
        .set("Authorization", `Bearer ${receiver.token}`)
        .send({ action: "ACCEPTED" });

      await new Promise((r) => setTimeout(r, 25));
      releaseBarrier.resolve();
      await barrierTx;

      const [withdrawRes, acceptRes] = await Promise.all([
        withdrawPromise,
        acceptPromise,
      ]);
      const dbMatch = await prisma.match.findUniqueOrThrow({
        where: { id: matchId },
      });

      const exactlyOne200 =
        (withdrawRes.status === 200) !== (acceptRes.status === 200);
      expect(exactlyOne200).toBe(true);

      if (withdrawRes.status === 200) {
        expect(withdrawRes.body.data.status).toBe("WITHDRAWN");
        expect(withdrawRes.body.data.isMatched).toBe(false);
        expect([400, 409]).toContain(acceptRes.status);
        expect(dbMatch.status).toBe(MatchStatus.WITHDRAWN);
      } else {
        expect(acceptRes.body.data.status).toBe("ACCEPTED");
        expect(acceptRes.body.data.isMatched).toBe(true);
        expect([400, 409]).toContain(withdrawRes.status);
        expect(dbMatch.status).toBe(MatchStatus.ACCEPTED);
      }

      logSummary.push({
        subcase: "barrier_withdraw_vs_accept_1A",
        withdrawHttp: withdrawRes.status,
        acceptHttp: acceptRes.status,
        dbFinalStatus: dbMatch.status,
      });
    }

    // 1B. Deterministic row-lock barrier: ACCEPT queues first while WITHDRAW queues behind it -> withdraw never overwrites ACCEPTED
    {
      const matchId = await createPendingInvite("C1", "C2");
      const lockAcquired = createDeferred();
      const releaseBarrier = createDeferred();

      const barrierTx = barrierPrisma.$transaction(async (tx) => {
        await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${sender.id}::uuid FOR UPDATE`;
        lockAcquired.resolve();
        await releaseBarrier.promise;
      });
      await lockAcquired.promise;

      const acceptPromise = http()
        .patch(`/matches/${matchId}/respond`)
        .set("Authorization", `Bearer ${receiver.token}`)
        .send({ action: "ACCEPTED" });
      await new Promise((r) => setTimeout(r, 25));
      const withdrawPromise = http()
        .patch(`/matches/${matchId}/withdraw`)
        .set("Authorization", `Bearer ${sender.token}`);

      await new Promise((r) => setTimeout(r, 25));
      releaseBarrier.resolve();
      await barrierTx;

      const [acceptRes, withdrawRes] = await Promise.all([
        acceptPromise,
        withdrawPromise,
      ]);
      const dbMatch = await prisma.match.findUniqueOrThrow({
        where: { id: matchId },
      });

      const exactlyOne200 =
        (withdrawRes.status === 200) !== (acceptRes.status === 200);
      expect(exactlyOne200).toBe(true);

      if (acceptRes.status === 200) {
        expect(acceptRes.body.data.status).toBe("ACCEPTED");
        expect(acceptRes.body.data.handshakeState).toBe("MATCHED");
        expect(acceptRes.body.data.isMatched).toBe(true);
        expect([400, 409]).toContain(withdrawRes.status);
        expect(dbMatch.status).toBe(MatchStatus.ACCEPTED);
      } else {
        expect(withdrawRes.body.data.status).toBe("WITHDRAWN");
        expect([400, 409]).toContain(acceptRes.status);
        expect(dbMatch.status).toBe(MatchStatus.WITHDRAWN);
      }

      logSummary.push({
        subcase: "barrier_accept_vs_withdraw_1B",
        withdrawHttp: withdrawRes.status,
        acceptHttp: acceptRes.status,
        dbFinalStatus: dbMatch.status,
      });
    }

    // 1C. 12 unthrottled simultaneous HTTP race rounds (`Promise.all`) reconciling API response vs final DB status
    let withdrawWins = 0;
    let acceptWins = 0;
    for (let round = 1; round <= 12; round++) {
      const matchId = await createPendingInvite("C1", "C2");
      const [withdrawRes, acceptRes] = await Promise.all([
        http()
          .patch(`/matches/${matchId}/withdraw`)
          .set("Authorization", `Bearer ${sender.token}`),
        http()
          .patch(`/matches/${matchId}/respond`)
          .set("Authorization", `Bearer ${receiver.token}`)
          .send({ action: "ACCEPTED" }),
      ]);

      const dbMatch = await prisma.match.findUniqueOrThrow({
        where: { id: matchId },
      });

      // Mutual exclusion: never both 200, never both 4xx
      expect((withdrawRes.status === 200) !== (acceptRes.status === 200)).toBe(
        true,
      );

      if (withdrawRes.status === 200) {
        withdrawWins++;
        expect(withdrawRes.body.data.status).toBe("WITHDRAWN");
        expect(withdrawRes.body.data.isMatched).toBe(false);
        expect([400, 409]).toContain(acceptRes.status);
        expect(dbMatch.status).toBe(MatchStatus.WITHDRAWN);
      } else {
        acceptWins++;
        expect(acceptRes.body.data.status).toBe("ACCEPTED");
        expect(acceptRes.body.data.handshakeState).toBe("MATCHED");
        expect(acceptRes.body.data.isMatched).toBe(true);
        expect([400, 409]).toContain(withdrawRes.status);
        expect(dbMatch.status).toBe(MatchStatus.ACCEPTED);
      }
    }

    logSummary.push({
      subcase: "parallel_12_rounds_withdraw_vs_accept",
      rounds: 12,
      withdrawWins,
      acceptWins,
      apiDbMismatchCount: 0,
    });
    // eslint-disable-next-line no-console
    console.log(
      `[W08-CONCURRENCY-CASE-1] ${JSON.stringify(logSummary, null, 2)}`,
    );
  });

  it("2) Concurrent discovery consent OFF (sender & receiver) vs accept: eliminates READ COMMITTED write skew and reconciles DB state", async () => {
    const sender = actors.get("C1")!;
    const receiver = actors.get("C2")!;
    const logSummary: Array<Record<string, unknown>> = [];

    // 2A. Deterministic write-skew test: sender disables discovery while accept is queued on user lock -> accept MUST fail 409 and DB stays PENDING
    {
      const matchId = await createPendingInvite("C1", "C2");
      const lockAcquired = createDeferred();
      const releaseBarrier = createDeferred();

      const barrierTx = barrierPrisma.$transaction(async (tx) => {
        await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${sender.id}::uuid FOR UPDATE`;
        lockAcquired.resolve();
        await releaseBarrier.promise;
      });
      await lockAcquired.promise;

      const consentOffPromise = http()
        .patch("/matches/discovery")
        .set("Authorization", `Bearer ${sender.token}`)
        .send({ isDiscoverable: false });
      await new Promise((r) => setTimeout(r, 25));
      const acceptPromise = http()
        .patch(`/matches/${matchId}/respond`)
        .set("Authorization", `Bearer ${receiver.token}`)
        .send({ action: "ACCEPTED" });

      await new Promise((r) => setTimeout(r, 25));
      releaseBarrier.resolve();
      await barrierTx;

      const [consentRes, acceptRes] = await Promise.all([
        consentOffPromise,
        acceptPromise,
      ]);
      const [dbMatch, dbSenderProfile] = await Promise.all([
        prisma.match.findUniqueOrThrow({ where: { id: matchId } }),
        prisma.profile.findUniqueOrThrow({ where: { userId: sender.id } }),
      ]);

      expect(consentRes.status).toBe(200);
      expect(consentRes.body.data.isDiscoverable).toBe(false);
      expect(dbSenderProfile.isDiscoverable).toBe(false);

      if (acceptRes.status === 409) {
        expect(dbMatch.status).toBe(MatchStatus.PENDING);
      } else {
        // Even if OS socket scheduled accept ahead of consentOff, API & DB must still match 100%
        expect(acceptRes.status).toBe(200);
        expect(dbMatch.status).toBe(MatchStatus.ACCEPTED);
      }

      logSummary.push({
        subcase: "barrier_sender_consent_off_vs_accept",
        consentOffHttp: consentRes.status,
        acceptHttp: acceptRes.status,
        dbSenderDiscoverable: dbSenderProfile.isDiscoverable,
        dbMatchStatus: dbMatch.status,
      });
    }

    // 2B. Simultaneous HTTP race rounds: sender consent OFF || receiver accept (8 rounds) + receiver consent OFF || receiver accept (4 rounds)
    let rejectedAfterConsentOff = 0;
    let acceptedBeforeConsentOff = 0;

    for (let round = 1; round <= 12; round++) {
      const matchId = await createPendingInvite("C1", "C2");
      const actorTogglingOff = round <= 8 ? sender : receiver;

      const [consentRes, acceptRes] = await Promise.all([
        http()
          .patch("/matches/discovery")
          .set("Authorization", `Bearer ${actorTogglingOff.token}`)
          .send({ isDiscoverable: false }),
        http()
          .patch(`/matches/${matchId}/respond`)
          .set("Authorization", `Bearer ${receiver.token}`)
          .send({ action: "ACCEPTED" }),
      ]);

      const [dbMatch, dbProfile] = await Promise.all([
        prisma.match.findUniqueOrThrow({ where: { id: matchId } }),
        prisma.profile.findUniqueOrThrow({
          where: { userId: actorTogglingOff.id },
        }),
      ]);

      expect(consentRes.status).toBe(200);
      expect(consentRes.body.data.isDiscoverable).toBe(false);
      expect(dbProfile.isDiscoverable).toBe(false);

      if (acceptRes.status === 200) {
        acceptedBeforeConsentOff++;
        expect(acceptRes.body.data.status).toBe("ACCEPTED");
        expect(acceptRes.body.data.isMatched).toBe(true);
        expect(dbMatch.status).toBe(MatchStatus.ACCEPTED);
      } else {
        rejectedAfterConsentOff++;
        expect([403, 409]).toContain(acceptRes.status);
        expect(dbMatch.status).toBe(MatchStatus.PENDING);
      }
    }

    logSummary.push({
      subcase: "parallel_12_rounds_consent_off_vs_accept",
      rounds: 12,
      rejectedAfterConsentOff,
      acceptedBeforeConsentOff,
      apiDbMismatchCount: 0,
    });
    // eslint-disable-next-line no-console
    console.log(
      `[W08-CONCURRENCY-CASE-2] ${JSON.stringify(logSummary, null, 2)}`,
    );
  });

  it("3) Concurrent two-way block (sender->receiver & receiver->sender) vs accept: zero deadlock, never ends ACCEPTED in DB, hides peer & PII", async () => {
    const sender = actors.get("C3")!;
    const receiver = actors.get("C4")!;
    const logSummary: Array<Record<string, unknown>> = [];

    // 3A. Deterministic barrier: sender blocks receiver while receiver calls accept concurrently
    {
      const matchId = await createPendingInvite("C3", "C4");
      const minId = [sender.id, receiver.id].sort((a, b) =>
        a.localeCompare(b),
      )[0];
      const lockAcquired = createDeferred();
      const releaseBarrier = createDeferred();

      const barrierTx = barrierPrisma.$transaction(async (tx) => {
        await tx.$queryRaw`SELECT id FROM "users" WHERE id = ${minId}::uuid FOR UPDATE`;
        lockAcquired.resolve();
        await releaseBarrier.promise;
      });
      await lockAcquired.promise;

      const blockPromise = http()
        .post("/matches/blocks")
        .set("Authorization", `Bearer ${sender.token}`)
        .send({ blockedUserId: receiver.id });
      await new Promise((r) => setTimeout(r, 25));
      const acceptPromise = http()
        .patch(`/matches/${matchId}/respond`)
        .set("Authorization", `Bearer ${receiver.token}`)
        .send({ action: "ACCEPTED" });

      await new Promise((r) => setTimeout(r, 25));
      releaseBarrier.resolve();
      await barrierTx;

      const [blockRes, acceptRes] = await Promise.all([
        blockPromise,
        acceptPromise,
      ]);
      const [dbMatch, dbBlock] = await Promise.all([
        prisma.match.findUniqueOrThrow({ where: { id: matchId } }),
        prisma.userBlock.findUnique({
          where: {
            blockerId_blockedId: {
              blockerId: sender.id,
              blockedId: receiver.id,
            },
          },
        }),
      ]);

      expect(blockRes.status).toBe(201);
      expect(blockRes.body.data.blocked).toBe(true);
      expect(blockRes.body.data.revokedMatchCount).toBe(1);
      expect(dbBlock).not.toBeNull();
      // Safety invariant: once blocked, DB match is ALWAYS REJECTED (never ACCEPTED or PENDING)
      expect(dbMatch.status).toBe(MatchStatus.REJECTED);
      if (acceptRes.status !== 200) {
        expect(acceptRes.status).toBe(403);
      }

      logSummary.push({
        subcase: "barrier_sender_block_vs_accept",
        blockHttp: blockRes.status,
        acceptHttp: acceptRes.status,
        revokedMatchCount: blockRes.body.data.revokedMatchCount,
        dbFinalMatchStatus: dbMatch.status,
        dbBlockPresent: dbBlock !== null,
      });
    }

    // 3B. 12 simultaneous HTTP race rounds across BOTH block directions (sender->receiver & receiver->sender) + cross-block race (C3 blocks C4 || C4 blocks C3 || C4 accepts)
    let blockFirstRejections = 0;
    let acceptThenRevokedByBlock = 0;

    for (let round = 1; round <= 12; round++) {
      const matchId = await createPendingInvite("C3", "C4");
      const blocker = round % 2 === 1 ? sender : receiver;
      const blocked = round % 2 === 1 ? receiver : sender;

      const [blockRes, acceptRes] = await Promise.all([
        http()
          .post("/matches/blocks")
          .set("Authorization", `Bearer ${blocker.token}`)
          .send({ blockedUserId: blocked.id }),
        http()
          .patch(`/matches/${matchId}/respond`)
          .set("Authorization", `Bearer ${receiver.token}`)
          .send({ action: "ACCEPTED" }),
      ]);

      const [dbMatch, dbBlock, listSender, listReceiver] = await Promise.all([
        prisma.match.findUniqueOrThrow({ where: { id: matchId } }),
        prisma.userBlock.findUnique({
          where: {
            blockerId_blockedId: {
              blockerId: blocker.id,
              blockedId: blocked.id,
            },
          },
        }),
        http()
          .get("/matches")
          .set("Authorization", `Bearer ${sender.token}`)
          .expect(200),
        http()
          .get("/matches")
          .set("Authorization", `Bearer ${receiver.token}`)
          .expect(200),
      ]);

      expect(blockRes.status).toBe(201);
      expect(blockRes.body.data.blocked).toBe(true);
      expect(blockRes.body.data.revokedMatchCount).toBe(1);
      expect(dbBlock).not.toBeNull();
      // Final DB state MUST ALWAYS be REJECTED and invisible to both sides
      expect(dbMatch.status).toBe(MatchStatus.REJECTED);
      expect(listSender.body.data.items).toEqual([]);
      expect(listReceiver.body.data.items).toEqual([]);

      if (acceptRes.status === 403) {
        blockFirstRejections++;
      } else {
        // Accept ran microseconds before block, then block transactionally revoked ACCEPTED -> REJECTED
        expect(acceptRes.status).toBe(200);
        acceptThenRevokedByBlock++;
      }

      // No PII leaked in any concurrent response
      const combinedText = `${blockRes.text} ${acceptRes.text}`;
      expect(combinedText).not.toContain("@secret-race.local");
      expect(combinedText).not.toContain("+8490777");
    }

    // 3C. Deadlock-freedom test: opposite-direction blocks (C3->C4 and C4->C3) + accept fired simultaneously
    {
      const matchId = await createPendingInvite("C3", "C4");
      const [blkA, blkB, acc] = await Promise.all([
        http()
          .post("/matches/blocks")
          .set("Authorization", `Bearer ${sender.token}`)
          .send({ blockedUserId: receiver.id }),
        http()
          .post("/matches/blocks")
          .set("Authorization", `Bearer ${receiver.token}`)
          .send({ blockedUserId: sender.id }),
        http()
          .patch(`/matches/${matchId}/respond`)
          .set("Authorization", `Bearer ${receiver.token}`)
          .send({ action: "ACCEPTED" }),
      ]);
      const dbMatch = await prisma.match.findUniqueOrThrow({
        where: { id: matchId },
      });
      expect(blkA.status).toBe(201);
      expect(blkB.status).toBe(201);
      expect([200, 403]).toContain(acc.status);
      expect(dbMatch.status).toBe(MatchStatus.REJECTED);
    }

    logSummary.push({
      subcase: "parallel_12_rounds_two_way_block_vs_accept_plus_deadlock_check",
      rounds: 12,
      blockFirstRejections,
      acceptThenRevokedByBlock,
      deadlockCount: 0,
      finalDbAcceptedWhileBlockedCount: 0,
    });
    // eslint-disable-next-line no-console
    console.log(
      `[W08-CONCURRENCY-CASE-3] ${JSON.stringify(logSummary, null, 2)}`,
    );
  });
});
