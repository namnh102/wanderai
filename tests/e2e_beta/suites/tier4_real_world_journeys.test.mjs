import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getRuntimeConfig } from '../lib/cli_args.mjs';
import {
  HttpClient,
  fetchResetToken,
  loginUser,
  registerAndLogin,
  registerUser,
  resolveHaLongDestination,
} from '../lib/http_client.mjs';
import {
  assertErrorEnvelope,
  assertSuccessEnvelope,
  assertYoutubeContainerContract,
  assertYoutubeFiveFields,
} from '../lib/assertions.mjs';
import { withFaultProxy } from '../lib/fault_proxy.mjs';
import {
  detectBetaMobileTree,
  getFlutterTestResult,
  verifyBetaDartDeliverables,
  verifyPerfBenchmarkArtifacts,
  verifyScreenshots,
} from '../lib/mobile_contract_verifier.mjs';
import {
  fetchDbStats,
  verifyDbStatsIsolation,
  verifyFactualPlaceUnchanged,
  verifyFreezeChecksum,
  verifyProtectedPathsClean,
} from '../lib/w07_governance_verifier.mjs';
import {
  buildGroundedThapDongHoEvent,
  buildYoutubeAtomFeed,
  isoWithOffsetSeconds,
  signWebSubBody,
} from '../fixtures/youtube_atom_feeds.mjs';

const FIXTURE = JSON.parse(
  fs.readFileSync(new URL('../fixtures/halong_thap_dong_ho.json', import.meta.url), 'utf8'),
);

const cfg = getRuntimeConfig();
const client = new HttpClient(cfg.baseUrl);

function uniqueEmail(prefix) {
  return `${prefix}.${crypto.randomUUID().slice(0, 8)}@gomate.vn`;
}

function uniqueVideoId(prefix = 'v') {
  const cleanPrefix = prefix.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 3) || 'v';
  const suffix = crypto.randomUUID().replace(/-/g, '').slice(0, 11 - cleanPrefix.length);
  return `${cleanPrefix}${suffix}`;
}

describe('Tier 4 — Real-World Application Journeys (6 E2E Scenarios: T4-01..T4-06)', () => {
  test('T4-01: Guest discovery -> Tháp Đồng Hồ 5-field realtime YouTube -> auth redirect -> trip save -> cold reload -> W07 audit', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats = await fetchDbStats(client, cfg);

    // 1. Ingest fresh Thap Dong Ho YouTube update (45s ago)
    const freshVid = uniqueVideoId('41');
    const ytReceipt = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `t401-${crypto.randomUUID()}`,
          videoId: freshVid,
          publishedAt: isoWithOffsetSeconds(-45_000, '+07:00'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(ytReceipt.status, 'LINKED');
    assert.equal(ytReceipt.linkedPlaceId, FIXTURE.poi.id);
    assert.ok(ytReceipt.ingestLatencyMs >= 0 && ytReceipt.ingestLatencyMs <= 300000);

    // 2. Guest discovery flow (public endpoints, zero /users/me calls)
    const haLong = await resolveHaLongDestination(client);
    const search = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, search: 'Tháp Đồng Hồ', verifiedOnly: true },
      }),
      200,
    );
    assert.ok(search.items.some((p) => p.id === FIXTURE.poi.id));

    // 3. Inspect PlaceDetail + YouTube 5-field & SLA <= 300000ms
    const ytData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(ytData);
    const freshItem = ytData.items.find((i) => i.videoId === freshVid);
    assert.ok(freshItem, 'Freshly ingested item must be present in youtube-updates');
    assertYoutubeFiveFields(freshItem, 'POI', { maxIngestLatencyMs: 300000 });
    assert.ok(freshItem.ingestLatencyMs <= ytData.realtimeSlaMaxLatencyMs);

    // 4. Redirect to /login?redirect=/places/:id -> login -> save to trip
    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('sanitizeInternalRedirect') && routerText.includes('resolvePostAuthDestination'));
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('halong.journey1'),
      password: 'Password123!',
      name: 'Journey 1 Traveler',
    });

    // 5. Save Tháp Đồng Hồ & cold reload verification
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Hành trình Hạ Long 2N1Đ', destinationId: haLong.id }),
      201,
    );
    assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: FIXTURE.poi.id,
      }),
      201,
    );

    const coldReload = assertSuccessEnvelope(
      await new HttpClient(cfg.baseUrl).withToken(auth.accessToken).get(`/trips/${trip.id}`),
      200,
    );
    assert.ok(
      coldReload.itineraries.some((d) =>
        d.items.some((i) => i.placeId === FIXTURE.poi.id && i.activity.includes('Tháp Đồng Hồ')),
      ),
    );

    // 6. Governance audit
    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    const afterStats = await fetchDbStats(client, cfg);
    verifyDbStatsIsolation(beforeStats, afterStats);
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T4-02: Guest Cancel-Login return -> re-attempt Save -> real HTTP 503 recovery (_createdPendingTrip, 1 trip)', async () => {
    const haLong = await resolveHaLongDestination(client);
    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('isPublicPlaceDetail') && routerText.includes('guestBrowseModeProvider'));
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    }

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('halong.journey2'),
      password: 'Password123!',
      name: 'Journey 2 Traveler',
    });

    await withFaultProxy(
      cfg.baseUrl,
      [{ method: 'POST', pathPrefix: '/trips/', remaining: 1 }],
      async ({ proxyClient, getStats }) => {
        const proxyAuthed = proxyClient.withToken(auth.accessToken);
        const trip = assertSuccessEnvelope(
          await proxyAuthed.post('/trips', { title: 'Hạ Long Recovery', destinationId: haLong.id }),
          201,
        );

        const firstTry = await proxyAuthed.post(`/trips/${trip.id}/itinerary`, {
          dayNumber: 1,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId: FIXTURE.poi.id,
        });
        assertErrorEnvelope(firstTry, 503, 'SERVICE_UNAVAILABLE', '/trips/');

        const retryTry = await proxyAuthed.post(`/trips/${trip.id}/itinerary`, {
          dayNumber: 1,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId: FIXTURE.poi.id,
        });
        assertSuccessEnvelope(retryTry, 201);

        assert.equal(getStats().interceptedCount, 1);
        const trips = assertSuccessEnvelope(await proxyAuthed.get('/trips'), 200);
        const matching = trips.filter((t) => t.title === 'Hạ Long Recovery');
        assert.equal(matching.length, 1);
      },
    );
  });

  test('T4-03: City-level Hạ Long fallback + duplicate replay + stale >300s + Phú Quốc reject + R4', async () => {
    if (cfg.mode === 'self-test') {
      assertSuccessEnvelope(await client.post('/_test/reset', {}), 200);
    }
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats = await fetchDbStats(client, cfg);

    const staleCityVid = uniqueVideoId('43');
    const staleEvent = {
      eventId: `t403-city-${crypto.randomUUID()}`,
      videoId: staleCityVid,
      channelId: 'UC_Halong_Stale',
      title: 'Vịnh Hạ Long buổi sáng sương mù',
      publishedAt: isoWithOffsetSeconds(-20 * 60 * 1000, '+07:00'),
    };

    const first = assertSuccessEnvelope(
      await client.post('/youtube/events', staleEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    const second = assertSuccessEnvelope(
      await client.post('/youtube/events', staleEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(first.status, 'LINKED_CITY');
    assert.equal(first.scope, 'CITY');
    assert.equal(first.linkedPlaceId, null);
    assert.ok(first.ingestLatencyMs > 300000);
    assert.equal(second.duplicate, true);
    assert.equal(second.deliveryCount, 2);

    const phuQuocVid = uniqueVideoId('pq4');
    const conflict = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `t403-pq-${crypto.randomUUID()}`,
          videoId: phuQuocVid,
          channelId: 'UC_PQ',
          title: 'Tháp Đồng Hồ Phú Quốc về đêm',
          publishedAt: isoWithOffsetSeconds(-30_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(conflict.status, 'UNLINKED_NO_BASIS');
    assert.equal(conflict.decisionReason, 'conflicting_city_mention');

    const destUpdates = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates', { query: { limit: 50 } }),
      200,
    );
    assert.equal(destUpdates.items.filter((i) => i.videoId === staleCityVid).length, 1);
    assert.ok(!destUpdates.items.some((i) => i.videoId === phuQuocVid));

    const placeUpdates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(placeUpdates);
    assert.ok(!placeUpdates.items.some((i) => i.videoId === phuQuocVid));
    const staleItem = placeUpdates.cityFallbackItems.find((i) => i.videoId === staleCityVid);
    assert.ok(staleItem, 'Stale city update must appear in cityFallbackItems');
    assertYoutubeFiveFields(staleItem, 'CITY');
    assert.ok(staleItem.ingestLatencyMs > placeUpdates.realtimeSlaMaxLatencyMs);

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    const afterStats = await fetchDbStats(client, cfg);
    verifyDbStatsIsolation(beforeStats, afterStats);
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T4-04: Password reset supersession (T1 invalidated by T2, T2 single-use) -> login -> Map marker -> trip save', async () => {
    const email = uniqueEmail('forgot.traveler');
    await registerUser(client, { email, password: 'InitialPassword123!', name: 'Reset Journey' });

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t1 = await fetchResetToken(client, cfg, email);

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t2 = await fetchResetToken(client, cfg, email);
    assert.notEqual(t1, t2);

    const t1Attempt = await client.post('/auth/reset-password', {
      token: t1,
      newPassword: 'ResetPassword999!',
    });
    assertErrorEnvelope(
      t1Attempt,
      [400, 410],
      ['RESET_TOKEN_USED', 'RESET_TOKEN_INVALID'],
      '/auth/reset-password',
    );

    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token: t2, newPassword: 'ResetPassword999!' }),
      200,
    );
    const t2Replay = await client.post('/auth/reset-password', {
      token: t2,
      newPassword: 'ResetPassword000!',
    });
    assertErrorEnvelope(t2Replay, [400, 410], 'RESET_TOKEN_USED', '/auth/reset-password');

    const loggedIn = assertSuccessEnvelope(
      await loginUser(client, { email, password: 'ResetPassword999!' }),
      200,
    );
    const authed = client.withToken(loggedIn.access_token);
    const place = assertSuccessEnvelope(await authed.get(`/places/${FIXTURE.poi.id}`), 200);
    assert.equal(place.name, 'Tháp Đồng Hồ');

    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Map Marker Save Trip', destinationId: place.destinationId }),
      201,
    );
    assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: place.id,
      }),
      201,
    );
    const fetched = assertSuccessEnvelope(await authed.get(`/trips/${trip.id}`), 200);
    assert.ok(fetched.itineraries[0].items.some((i) => i.placeId === FIXTURE.poi.id));
  });

  test('T4-05: Social OAuth Matrix (FB OAUTH_EMAIL_UNAVAILABLE -> Google success -> /users/me -> save -> logout)', async () => {
    const haLong = await resolveHaLongDestination(client);
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    }

    // 1. Facebook OAUTH_EMAIL_UNAVAILABLE
    const fbErr = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-journey5' });
    assertErrorEnvelope(fbErr, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');

    // 2. Google Success
    const gEmail = uniqueEmail('journey5.google');
    const gRes = await client.post('/auth/oauth/google', { idToken: `valid-email:${gEmail}` });
    const gData = assertSuccessEnvelope(gRes, 200);
    assert.ok(Array.isArray(gData.user.providers) && gData.user.providers.includes('google'));

    // 3. /users/me + Save trip
    const authed = client.withToken(gData.access_token);
    const me = assertSuccessEnvelope(await authed.get('/users/me'), 200);
    assert.equal(me.id, gData.user.id);
    assert.equal(me.email, gEmail);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'OAuth Journey Trip', destinationId: haLong.id }),
      201,
    );
    assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: FIXTURE.poi.id,
      }),
      201,
    );

    // 4. Logout cleanup check (unauthenticated client gets 401 on /users/me)
    const loggedOutRes = await client.get('/users/me');
    assertErrorEnvelope(loggedOutRes, 401, null, '/users/me');
  });

  test('T4-06: Full Acceptance & Release Readiness (390x844 screenshots + perf timing + WebSub/JSON YouTube + R4 audit)', async () => {
    // 1. Screenshot / Beta mobile deliverables check
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.beforeCount > 0 && ss.afterCount > 0);
      verifyPerfBenchmarkArtifacts(cfg.mobileDir, cfg.repoRoot);
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    }

    // 2. Perf benchmark / cached Flutter test check + API latency measurement
    const haLong = await resolveHaLongDestination(client);
    const perfList = await client.get('/places', {
      query: { destinationId: haLong.id, limit: 20 },
    });
    assertSuccessEnvelope(perfList, 200);
    assert.ok(perfList.durationMs >= 0);
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });

    // 3. WebSub + JSON ingestion for Tháp Đồng Hồ + SLA check
    const vid = uniqueVideoId('46');
    const xml = buildYoutubeAtomFeed([
      {
        videoId: vid,
        channelId: 'UC_Release_Check',
        title: 'Tháp Đồng Hồ Hạ Long Release Check',
        description: 'Cột Đồng Hồ Hạ Long, Quảng Ninh.',
        publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
        latitude: FIXTURE.poi.latitude,
        longitude: FIXTURE.poi.longitude,
      },
    ]);
    const sig = signWebSubBody(xml, cfg.websubSecret, 'sha256');
    const webRes = assertSuccessEnvelope(
      await client.post('/youtube/webhook', {
        rawBody: xml,
        headers: {
          'Content-Type': 'application/atom+xml',
          ...(sig ? { 'X-Hub-Signature': sig } : {}),
        },
      }),
      200,
    );
    assert.equal(webRes.results[0].status, 'LINKED');
    assert.ok(webRes.results[0].ingestLatencyMs >= 0 && webRes.results[0].ingestLatencyMs <= 300000);

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(updates);
    const item = updates.items.find((i) => i.videoId === vid);
    assert.ok(item, 'Release-check WebSub item must be present in youtube-updates');
    assertYoutubeFiveFields(item, 'POI', { maxIngestLatencyMs: 300000 });
    assert.ok(item.ingestLatencyMs <= updates.realtimeSlaMaxLatencyMs);

    // 4. Strict R4 Governance Audit
    const checksums = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(checksums.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
    const requireW07Prep = cfg.mode === 'live' || cfg.w07PrepDirExplicit;
    const clean = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir, { requireW07Prep });
    assert.equal(clean.dirtyLines.length, 0);
    if (requireW07Prep || fs.existsSync(cfg.w07PrepDir)) {
      assert.equal(clean.w07PrepVerified, true);
    }
  });
});
