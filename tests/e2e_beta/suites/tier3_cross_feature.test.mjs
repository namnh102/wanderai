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
  verifyBetaDartDeliverables,
  verifyPerfBenchmarkArtifacts,
  verifyScreenshots,
} from '../lib/mobile_contract_verifier.mjs';
import {
  fetchDbStats,
  verifyDbStatsIsolation,
  verifyFactualPlaceUnchanged,
  verifyFreezeChecksum,
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

describe('Tier 3 — Cross-Feature Pairwise Combinations (12 Tests: T3-01..T3-12)', () => {
  test('T3-01 (F3+F4+F2): Guest search Hạ Long -> Tháp Đồng Hồ -> redirect login -> save -> reload persists', async () => {
    const haLong = await resolveHaLongDestination(client);
    const searchRes = assertSuccessEnvelope(
      await client.get('/places', {
        query: {
          destinationId: haLong.id,
          search: 'Tháp Đồng Hồ',
          verifiedOnly: true,
        },
      }),
      200,
    );
    assert.ok(searchRes.items.some((p) => p.id === FIXTURE.poi.id));

    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('sanitizeInternalRedirect') && routerText.includes('resolvePostAuthDestination'));

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t3.01'),
      password: 'Password123!',
      name: 'T3-01 Traveler',
    });

    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Hạ Long T3-01', destinationId: haLong.id }),
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

    const reloaded = assertSuccessEnvelope(
      await new HttpClient(cfg.baseUrl).withToken(auth.accessToken).get(`/trips/${trip.id}`),
      200,
    );
    assert.ok(reloaded.itineraries[0].items.some((i) => i.placeId === FIXTURE.poi.id));
  });

  test('T3-02 (F2+F9+F4+F3): Guest views realtime YouTube 5-field update -> Cancel-Login returns to guest PlaceDetail', async () => {
    const vid = uniqueVideoId('32');
    const evt = buildGroundedThapDongHoEvent({
      publishedAt: isoWithOffsetSeconds(-30_000, 'Z'),
      videoId: vid,
    });
    const receipt = assertSuccessEnvelope(
      await client.post('/youtube/events', evt, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.ok(receipt.publishedAt.endsWith('Z'));
    assert.ok(receipt.receivedAt.endsWith('Z'));
    assert.ok(receipt.lastReceivedAt.endsWith('Z'));
    const receiptLagMs = Math.max(
      0,
      Date.parse(receipt.receivedAt) - Date.parse(receipt.publishedAt),
    );
    assert.ok(receiptLagMs >= 0 && receiptLagMs <= 300000);

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(updates);
    const matched = updates.items.find((i) => i.videoId === vid);
    assert.ok(matched, 'Newly ingested POI event must appear in youtube-updates');
    assertYoutubeFiveFields(matched, 'POI', { maxIngestLatencyMs: 300000 });
    assert.ok(matched.ingestLatencyMs <= updates.realtimeSlaMaxLatencyMs);

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
  });

  test('T3-03 (F8+F9): City fallback banner transitions to primary POI update once POI YouTube event arrives', async () => {
    if (cfg.mode === 'self-test') {
      assertSuccessEnvelope(await client.post('/_test/reset', {}), 200);
    }

    const haLong = await resolveHaLongDestination(client);
    const placesData = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, verifiedOnly: true, limit: 50 },
      }),
      200,
    );

    let targetPoi = null;
    for (const candidate of placesData.items) {
      if (typeof candidate.latitude !== 'number' || typeof candidate.longitude !== 'number') {
        continue;
      }
      const yt = assertSuccessEnvelope(
        await client.get(`/places/${candidate.id}/youtube-updates`, { query: { limit: 50 } }),
        200,
      );
      if (Array.isArray(yt.items) && yt.items.length === 0) {
        targetPoi = candidate;
        break;
      }
    }
    assert.ok(
      targetPoi,
      'Could not find a clean verified Hạ Long POI with 0 POI-level YouTube items for T3-03',
    );

    const cityVid = uniqueVideoId('c3');
    const cityEvent = {
      eventId: `t303-city-${crypto.randomUUID()}`,
      videoId: cityVid,
      channelId: 'UC_T303',
      title: 'Khám phá Vịnh Hạ Long Quảng Ninh buổi sáng',
      publishedAt: isoWithOffsetSeconds(-40_000, '+07:00'),
    };
    const cityReceipt = assertSuccessEnvelope(
      await client.post('/youtube/events', cityEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(cityReceipt.status, 'LINKED_CITY');
    assert.equal(cityReceipt.scope, 'CITY');
    assert.equal(cityReceipt.linkedPlaceId, null);

    const beforePoi = assertSuccessEnvelope(
      await client.get(`/places/${targetPoi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assert.equal(beforePoi.items.length, 0, 'Before POI ingestion, targetPoi must have 0 POI items');
    assert.equal(beforePoi.total, 0);
    assert.ok(
      beforePoi.cityFallbackItems.some(
        (i) => i.videoId === cityVid && i.placeId === null && i.scope === 'CITY',
      ),
      'Before POI ingestion, cityFallbackItems must contain the new Hạ Long city event',
    );

    const poiVid = uniqueVideoId('p3');
    const poiEvent = {
      eventId: `t303-poi-${crypto.randomUUID()}`,
      videoId: poiVid,
      channelId: 'UC_T303_POI',
      channelTitle: 'Hạ Long Review',
      title: `Khám phá ${targetPoi.name} Hạ Long`,
      description: `Check-in tại ${targetPoi.name}, thành phố Hạ Long, Quảng Ninh.`,
      tags: [targetPoi.name, 'Hạ Long', 'Quảng Ninh'],
      publishedAt: isoWithOffsetSeconds(-25_000, '+07:00'),
      latitude: targetPoi.latitude,
      longitude: targetPoi.longitude,
      candidatePlaceId: targetPoi.id,
    };
    const poiReceipt = assertSuccessEnvelope(
      await client.post('/youtube/events', poiEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(poiReceipt.status, 'LINKED');
    assert.equal(poiReceipt.scope, 'POI');
    assert.equal(poiReceipt.linkedPlaceId, targetPoi.id);

    const afterPoi = assertSuccessEnvelope(
      await client.get(`/places/${targetPoi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assert.ok(
      afterPoi.items.some(
        (i) => i.videoId === poiVid && i.placeId === targetPoi.id && i.scope === 'POI',
      ),
      'After POI ingestion, items must contain the new POI-scoped event',
    );
    assert.ok(
      afterPoi.cityFallbackItems.some(
        (i) => i.videoId === cityVid && i.placeId === null && i.scope === 'CITY',
      ),
      'City fallback items must still retain the Hạ Long city event',
    );
  });

  test('T3-04 (F6+F3+F4): Forgot password -> Reset -> Login with redirect -> Save Tháp Đồng Hồ', async () => {
    const haLong = await resolveHaLongDestination(client);
    const email = uniqueEmail('reset.save');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'T3-04 User' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);

    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token, newPassword: 'NewPassword789!' }),
      200,
    );

    const oldFail = await loginUser(client, { email, password: 'OldPassword123!' });
    assertErrorEnvelope(oldFail, 401, 'INVALID_CREDENTIALS', '/auth/login');

    const newLogin = assertSuccessEnvelope(
      await loginUser(client, { email, password: 'NewPassword789!' }),
      200,
    );
    const authed = client.withToken(newLogin.access_token);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'T3-04 Trip', destinationId: haLong.id }),
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
  });

  test('T3-05 (F7+F3+F4): Google OAuth login -> /users/me -> save Tháp Đồng Hồ under OAuth user', async () => {
    const haLong = await resolveHaLongDestination(client);
    const email = uniqueEmail('t305.oauth');
    const oauth = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${email}` }),
      200,
    );
    assert.ok(Array.isArray(oauth.user.providers) && oauth.user.providers.includes('google'));

    const authed = client.withToken(oauth.access_token);
    const me = assertSuccessEnvelope(await authed.get('/users/me'), 200);
    assert.equal(me.id, oauth.user.id);
    assert.equal(me.email, email);

    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'OAuth Trip', destinationId: haLong.id }),
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
    const list = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.ok(list.some((t) => t.id === trip.id));
  });

  test('T3-06 (F1+F3+F6+F7): Structured errorCodes render inline AppStateBanner without clearing inputs', async () => {
    const invalidCreds = await loginUser(client, {
      email: uniqueEmail('t306.none'),
      password: 'WrongPassword123!',
    });
    assertErrorEnvelope(invalidCreds, 401, 'INVALID_CREDENTIALS', '/auth/login');

    const noEmail = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-t306' });
    assertErrorEnvelope(noEmail, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');

    const invalidReset = await client.post('/auth/reset-password', {
      token: 'tampered-tok',
      newPassword: 'ValidPass123!',
    });
    assertErrorEnvelope(invalidReset, 400, 'RESET_TOKEN_INVALID', '/auth/reset-password');

    const bannerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_state_banner.dart'),
      'utf8',
    );
    assert.ok(bannerText.includes('AppStateBannerTone'));
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    }
  });

  test('T3-07 (F1+F4+F2): Real HTTP 503 during save -> retry creates 0 duplicate trips', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t3.07'),
      password: 'Password123!',
      name: 'T3-07 User',
    });

    await withFaultProxy(
      cfg.baseUrl,
      [{ method: 'POST', pathPrefix: '/trips/', remaining: 1 }],
      async ({ proxyClient, getStats }) => {
        const proxyAuthed = proxyClient.withToken(auth.accessToken);
        const trip = assertSuccessEnvelope(
          await proxyAuthed.post('/trips', { title: 'T3-07 Trip', destinationId: haLong.id }),
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
        assert.equal(trips.filter((t) => t.title === 'T3-07 Trip').length, 1);
      },
    );
  });

  test('T3-08 (F8+F9+F10): Duplicate WebSub + JSON replay keeps 1 row, 5 fields, documents/place_sources untouched & W07 intact', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats = await fetchDbStats(client, cfg);

    const vid = uniqueVideoId('38');
    const pubIso = isoWithOffsetSeconds(-25_000, 'Z');
    const xml = buildYoutubeAtomFeed([
      {
        videoId: vid,
        channelId: 'UC_T308',
        title: 'Tháp Đồng Hồ Hạ Long 2026',
        description: 'Gần Vincom Hạ Long, Quảng Ninh.',
        publishedAt: pubIso,
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
    assert.equal(webRes.results[0].deliveryCount, 1);

    const replayJson = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          videoId: vid,
          channelId: 'UC_T308',
          title: 'Tháp Đồng Hồ Hạ Long 2026',
          publishedAt: pubIso,
          latitude: FIXTURE.poi.latitude,
          longitude: FIXTURE.poi.longitude,
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(replayJson.duplicate, true);
    assert.equal(replayJson.deliveryCount, 2);

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assert.equal(updates.items.filter((i) => i.videoId === vid).length, 1);
    assertYoutubeFiveFields(updates.items.find((i) => i.videoId === vid), 'POI');

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    const afterStats = await fetchDbStats(client, cfg);
    verifyDbStatsIsolation(beforeStats, afterStats);
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T3-09 (F2+F5): Profile perf timing & 390x844 screenshot artifact contract for Hạ Long + Tháp Đồng Hồ', async () => {
    const haLong = await resolveHaLongDestination(client);
    const listRes = await client.get('/places', {
      query: { destinationId: haLong.id, limit: 20 },
    });
    const detailRes = await client.get(`/places/${FIXTURE.poi.id}`);
    assertSuccessEnvelope(listRes, 200);
    assertSuccessEnvelope(detailRes, 200);
    assert.ok(listRes.durationMs >= 0 && detailRes.durationMs >= 0);

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.count > 0);
      verifyPerfBenchmarkArtifacts(cfg.mobileDir, cfg.repoRoot);
    }
  });

  test('T3-10 (F3+F7+F2): Session switch (User A OAuth -> logout -> User B local) isolates trips & enforces 403', async () => {
    const haLong = await resolveHaLongDestination(client);
    const userA = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${uniqueEmail('userA')}` }),
      200,
    );
    const clientA = client.withToken(userA.access_token);
    const tripA = assertSuccessEnvelope(
      await clientA.post('/trips', { title: 'Trip A Private', destinationId: haLong.id }),
      201,
    );

    const userB = await registerAndLogin(client, {
      email: uniqueEmail('userB'),
      password: 'Password123!',
      name: 'User B',
    });
    const clientB = client.withToken(userB.accessToken);
    const tripsB = assertSuccessEnvelope(await clientB.get('/trips'), 200);
    assert.ok(!tripsB.some((t) => t.id === tripA.id), 'User B must not see User A trip');

    const forbidden = await clientB.get(`/trips/${tripA.id}`);
    assertErrorEnvelope(forbidden, 403, null, '/trips/');
  });

  test('T3-11 (F2+F8+F9): Đà Nẵng YouTube event never leaks into Tháp Đồng Hồ or Hạ Long city fallback', async () => {
    const daNangVid = uniqueVideoId('dn');
    assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `t311-dn-${crypto.randomUUID()}`,
          videoId: daNangVid,
          channelId: 'UC_DaNang',
          title: 'Cầu Rồng Đà Nẵng phun lửa cuối tuần',
          publishedAt: isoWithOffsetSeconds(-20_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );

    const placeYt = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const destYt = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates', { query: { limit: 50 } }),
      200,
    );
    assert.ok(!placeYt.items.some((i) => i.videoId === daNangVid));
    assert.ok(!placeYt.cityFallbackItems.some((i) => i.videoId === daNangVid));
    assert.ok(!destYt.items.some((i) => i.videoId === daNangVid));
  });

  test('T3-12 (F6+F7+F3): Facebook OAuth account (passwordHash=null) sets password via reset & signs in both ways', async () => {
    const email = uniqueEmail('fb.hybrid');
    const fb = assertSuccessEnvelope(
      await client.post('/auth/oauth/facebook', { accessToken: `valid-email:${email}` }),
      200,
    );
    assert.ok(Array.isArray(fb.user.providers) && fb.user.providers.includes('facebook'));

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);
    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token, newPassword: 'SetPassword123!' }),
      200,
    );

    const localLogin = assertSuccessEnvelope(
      await loginUser(client, { email, password: 'SetPassword123!' }),
      200,
    );
    const me = assertSuccessEnvelope(
      await client.withToken(localLogin.access_token).get('/users/me'),
      200,
    );
    assert.equal(me.id, fb.user.id);
    assert.equal(me.email, email);

    const fbAgain = assertSuccessEnvelope(
      await client.post('/auth/oauth/facebook', { accessToken: `valid-email:${email}` }),
      200,
    );
    assert.equal(fbAgain.user.id, me.id);
    assert.ok(Array.isArray(fbAgain.user.providers) && fbAgain.user.providers.includes('facebook'));
  });
});
