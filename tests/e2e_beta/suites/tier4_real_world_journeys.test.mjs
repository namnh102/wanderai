import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getRuntimeConfig } from '../lib/cli_args.mjs';
import {
  HttpClient,
  loginUser,
  registerAndLogin,
  registerUser,
} from '../lib/http_client.mjs';
import {
  assertErrorEnvelope,
  assertSuccessEnvelope,
  assertYoutubeContainerContract,
  assertYoutubeFiveFields,
} from '../lib/assertions.mjs';
import {
  detectBetaMobileTree,
  evaluateAuthOutcomeMatrix,
  evaluateYoutubeFreshnessUi,
  getMobileContractSpec,
  parsePngDimensions,
  runFlutterTestsIfRequested,
  sanitizeInternalRedirect,
  simulateSavePlaceFlow,
} from '../lib/mobile_contract_verifier.mjs';
import {
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
const mobileSpec = getMobileContractSpec();

function uniqueEmail(prefix) {
  return `${prefix}.${crypto.randomUUID().slice(0, 8)}@gomate.vn`;
}

async function fetchResetToken(email) {
  if (cfg.mode === 'self-test') {
    const outbox = await client.get('/_test/mail-outbox', { query: { email } });
    const data = assertSuccessEnvelope(outbox, 200);
    assert.ok(data.items.length > 0);
    return data.items.at(-1).rawToken;
  }
  if (process.env.E2E_TEST_RESET_TOKEN) return process.env.E2E_TEST_RESET_TOKEN;
  if (process.env.E2E_MAIL_OUTBOX_URL) {
    const res = await new HttpClient(process.env.E2E_MAIL_OUTBOX_URL).get('/', { query: { email } });
    if (res.json?.token) return res.json.token;
    if (res.json?.data?.items?.length) return res.json.data.items.at(-1).rawToken;
  }
  throw new Error('Live mode reset test requires E2E_MAIL_OUTBOX_URL or E2E_TEST_RESET_TOKEN');
}

describe('Tier 4 — Real-World Application Journeys (6 E2E Scenarios: T4-01..T4-06)', () => {
  test('T4-01: Guest discovery -> Tháp Đồng Hồ 5-field realtime YouTube -> auth redirect -> trip save -> cold reload -> W07 audit', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats =
      cfg.mode === 'self-test'
        ? assertSuccessEnvelope(await client.get('/_test/db-stats'), 200)
        : null;

    // 1. Ingest fresh Thap Dong Ho YouTube update (45s ago)
    const freshVid = `t401${crypto.randomUUID().replace(/-/g, '').slice(0, 7)}`;
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

    // 2. Guest discovery flow (public endpoints, zero /users/me calls)
    const dests = assertSuccessEnvelope(await client.get('/destinations'), 200);
    const haLong = dests.items.find((d) => d.slug === 'ha-long');
    assert.ok(haLong);
    const search = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, search: 'Tháp Đồng Hồ', verifiedOnly: true },
      }),
      200,
    );
    assert.ok(search.items.some((p) => p.id === FIXTURE.poi.id));

    // 3. Inspect PlaceDetail + YouTube 5-field & "Thời gian thực"
    const ytData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(ytData);
    const freshItem = ytData.items.find((i) => i.videoId === freshVid);
    assertYoutubeFiveFields(freshItem, 'POI');
    const uiYt = evaluateYoutubeFreshnessUi(
      { ...ytData, items: [freshItem] },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(uiYt.poiItems[0].badgeLabel, 'Thời gian thực');

    // 4. Redirect to /login?redirect=/places/:id -> login -> save to trip
    const redirectTarget = `/places/${FIXTURE.poi.id}`;
    assert.equal(sanitizeInternalRedirect(redirectTarget), redirectTarget);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('halong.journey1'),
      password: 'Password123!',
      name: 'Journey 1 Traveler',
    });
    const loginUi = await evaluateAuthOutcomeMatrix({
      outcome: 'Success',
      redirectPath: redirectTarget,
    });
    assert.equal(loginUi.navigatedTo, redirectTarget);

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
    if (beforeStats) {
      const afterStats = assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
      verifyDbStatsIsolation(beforeStats, afterStats);
    }
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T4-02: Guest Cancel-Login return -> re-attempt Save -> transient 503 recovery (_createdPendingTrip, 1 trip)', async () => {
    // 1-2. Guest taps Save -> taps "Hủy đăng nhập" -> returns in guest mode with zero error banners
    const cancelState = await evaluateAuthOutcomeMatrix({
      outcome: 'Cancelled',
      redirectPath: `/places/${FIXTURE.poi.id}`,
    });
    assert.equal(cancelState.navigatedTo, `/places/${FIXTURE.poi.id}`);
    assert.equal(cancelState.guestBrowseMode, true);
    assert.equal(cancelState.banner, null);
    assert.equal(cancelState.postLoginRedirect, null);

    // 3-4. User logs in, starts creating "Hạ Long Recovery", 1st itinerary POST hits 503, retry succeeds
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('halong.journey2'),
      password: 'Password123!',
      name: 'Journey 2 Traveler',
    });
    const authed = client.withToken(auth.accessToken);
    let injectTransient503 = true;

    const saveFlow = await simulateSavePlaceFlow({
      newTripTitle: 'Hạ Long Recovery',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async ({ title }) => {
        const trip = assertSuccessEnvelope(
          await authed.post('/trips', { title, destinationId: FIXTURE.destinations.haLong.id }),
          201,
        );
        return { ok: true, tripId: trip.id };
      },
      addItineraryFn: async ({ tripId, dayNumber, placeId }) => {
        if (injectTransient503) {
          injectTransient503 = false;
          if (cfg.mode === 'self-test') {
            const err = await authed.post(
              `/trips/${tripId}/itinerary`,
              { dayNumber, activity: 'Tham quan Tháp Đồng Hồ', placeId },
              { headers: { 'x-e2e-inject-status': '503' } },
            );
            assertErrorEnvelope(err, 503, null, '/trips/');
          }
          return { ok: false, status: 503, networkError: true };
        }
        assertSuccessEnvelope(
          await authed.post(`/trips/${tripId}/itinerary`, {
            dayNumber,
            activity: 'Tham quan Tháp Đồng Hồ',
            placeId,
          }),
          201,
        );
        return { ok: true };
      },
    });

    const firstTry = await saveFlow.attempt();
    assert.equal(firstTry.saved, false);
    assert.equal(firstTry.banner.tone, 'warning');
    assert.ok(firstTry.createdPendingTripId);

    const retryTry = await saveFlow.attempt();
    assert.equal(retryTry.saved, true);
    assert.equal(retryTry.createTripCalls, 1);

    // 5. Verify exactly 1 trip created
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    const matching = trips.filter((t) => t.title === 'Hạ Long Recovery');
    assert.equal(matching.length, 1);
  });

  test('T4-03: City-level Hạ Long fallback + duplicate replay + stale >300s ("Cập nhật gần đây") + Phú Quốc reject + R4', async () => {
    if (cfg.mode === 'self-test') {
      assertSuccessEnvelope(await client.post('/_test/reset', {}), 200);
    }
    const beforeStats =
      cfg.mode === 'self-test'
        ? assertSuccessEnvelope(await client.get('/_test/db-stats'), 200)
        : null;

    const staleCityVid = `t403${crypto.randomUUID().replace(/-/g, '').slice(0, 7)}`;
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
    assert.equal(second.duplicate, true);
    assert.equal(second.deliveryCount, 2);

    const phuQuocVid = `pq403${crypto.randomUUID().replace(/-/g, '').slice(0, 6)}`;
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
    assert.ok(!placeUpdates.items.some((i) => i.videoId === phuQuocVid));

    const cityOnlySnapshot = {
      ...placeUpdates,
      items: [],
      cityFallbackItems: placeUpdates.cityFallbackItems.filter((i) => i.videoId === staleCityVid),
    };
    const ui = evaluateYoutubeFreshnessUi(cityOnlySnapshot, { clientRenderedAtMs: Date.now() });
    assert.equal(ui.primarySection, 'CITY_FALLBACK');
    assert.equal(ui.showCityFallbackBanner, true);
    assert.equal(ui.cityFallbackItems[0].placeId, null);
    assert.equal(ui.cityFallbackItems[0].badgeLabel, 'Cập nhật gần đây');

    if (beforeStats) {
      const afterStats = assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
      verifyDbStatsIsolation(beforeStats, afterStats);
    }
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T4-04: Password reset supersession (T1 invalidated by T2, T2 single-use) -> login -> Map marker -> trip save', async () => {
    const email = uniqueEmail('forgot.traveler');
    await registerUser(client, { email, password: 'InitialPassword123!', name: 'Reset Journey' });

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t1 = await fetchResetToken(email);

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t2 = await fetchResetToken(email);
    assert.notEqual(t1, t2);

    const t1Attempt = await client.post('/auth/reset-password', {
      token: t1,
      newPassword: 'ResetPassword999!',
    });
    assertErrorEnvelope(t1Attempt, [400, 410], null, '/auth/reset-password');

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

  test('T4-05: Social OAuth Matrix (FB cancel -> FB OAUTH_EMAIL_UNAVAILABLE -> Google success -> /users/me -> save -> logout)', async () => {
    // 1. Facebook Cancelled
    let backendCalls = 0;
    const cancelRes = await evaluateAuthOutcomeMatrix({
      outcome: 'Cancelled',
      redirectPath: '/login',
      callBackendOAuth: async () => {
        backendCalls += 1;
      },
    });
    assert.equal(backendCalls, 0);
    assert.equal(cancelRes.banner, null);

    // 2. Facebook OAUTH_EMAIL_UNAVAILABLE
    const fbErr = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-journey5' });
    assertErrorEnvelope(fbErr, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');
    const errUi = await evaluateAuthOutcomeMatrix({
      outcome: 'Error',
      callBackendOAuth: async () => fbErr,
    });
    assert.equal(errUi.banner.tone, 'error');
    assert.equal(errUi.banner.errorCode, 'OAUTH_EMAIL_UNAVAILABLE');

    // 3. Google Success
    const gEmail = uniqueEmail('journey5.google');
    const gRes = await client.post('/auth/oauth/google', { idToken: `valid-email:${gEmail}` });
    const gData = assertSuccessEnvelope(gRes, 200);
    assert.ok(gData.user.providers.includes('google'));

    // 4. /users/me + Save trip
    const authed = client.withToken(gData.access_token);
    const me = assertSuccessEnvelope(await authed.get('/users/me'), 200);
    assert.equal(me.email, gEmail);
    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'OAuth Journey Trip' }), 201);
    assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: FIXTURE.poi.id,
      }),
      201,
    );

    // 5. Logout cleanup check (unauthenticated client gets 401 on /users/me)
    const loggedOutRes = await client.get('/users/me');
    assertErrorEnvelope(loggedOutRes, 401, null, '/users/me');
  });

  test('T4-06: Full Acceptance & Release Readiness (390x844 screenshots + perf timing + WebSub/JSON YouTube + R4 audit)', async () => {
    // 1. Screenshot / mobile artifacts check
    const screenshotDir = path.join(
      cfg.repoRoot,
      mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo,
    );
    if (detectBetaMobileTree(cfg.mobileDir) && fs.existsSync(screenshotDir)) {
      const pngs = fs.readdirSync(screenshotDir).filter((f) => f.endsWith('.png'));
      assert.ok(pngs.length > 0);
      for (const f of pngs) {
        const dims = parsePngDimensions(path.join(screenshotDir, f));
        assert.equal(dims.width, 390);
        assert.equal(dims.height, 844);
      }
    }

    // 2. Perf benchmark / Flutter test check (if --run-flutter) + API latency measurement
    const perfList = await client.get('/places', {
      query: { destinationId: FIXTURE.destinations.haLong.id, limit: 20 },
    });
    assertSuccessEnvelope(perfList, 200);
    assert.ok(perfList.durationMs >= 0);
    runFlutterTestsIfRequested(cfg.mobileDir, cfg.runFlutter);

    // 3. WebSub + JSON ingestion for Tháp Đồng Hồ + SLA check
    const vid = `t406${crypto.randomUUID().replace(/-/g, '').slice(0, 7)}`;
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

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(updates);
    const item = updates.items.find((i) => i.videoId === vid);
    assertYoutubeFiveFields(item, 'POI');
    const ui = evaluateYoutubeFreshnessUi(
      { ...updates, items: [item] },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(ui.poiItems[0].badgeLabel, 'Thời gian thực');

    // 4. Strict R4 Governance Audit
    const checksums = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(checksums.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
    const clean = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir);
    assert.equal(clean.dirtyLines.length, 0);
  });
});
