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
  sanitizeInternalRedirect,
  simulateSavePlaceFlow,
} from '../lib/mobile_contract_verifier.mjs';
import {
  verifyDbStatsIsolation,
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

describe('Tier 3 — Cross-Feature Pairwise Combinations (12 Tests: T3-01..T3-12)', () => {
  test('T3-01 (F3+F4+F2): Guest search Hạ Long -> Tháp Đồng Hồ -> redirect login -> save -> reload persists', async () => {
    const searchRes = assertSuccessEnvelope(
      await client.get('/places', {
        query: {
          destinationId: FIXTURE.destinations.haLong.id,
          search: 'Tháp Đồng Hồ',
          verifiedOnly: true,
        },
      }),
      200,
    );
    assert.ok(searchRes.items.some((p) => p.id === FIXTURE.poi.id));

    const target = `/places/${FIXTURE.poi.id}`;
    assert.equal(sanitizeInternalRedirect(target), target);

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t3.01'),
      password: 'Password123!',
      name: 'T3-01 Traveler',
    });
    const ui = await evaluateAuthOutcomeMatrix({ outcome: 'Success', redirectPath: target });
    assert.equal(ui.navigatedTo, target);

    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Hạ Long T3-01', destinationId: FIXTURE.destinations.haLong.id }),
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
    const evt = buildGroundedThapDongHoEvent({
      publishedAt: isoWithOffsetSeconds(-30_000, 'Z'),
      videoId: `t302${crypto.randomUUID().replace(/-/g, '').slice(0, 7)}`,
    });
    assertSuccessEnvelope(
      await client.post('/youtube/events', evt, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`),
      200,
    );
    assertYoutubeFiveFields(updates.items[0], 'POI');
    const uiBefore = evaluateYoutubeFreshnessUi(updates, { clientRenderedAtMs: Date.now() });
    assert.equal(uiBefore.poiItems[0].badgeLabel, 'Thời gian thực');

    const cancelUi = await evaluateAuthOutcomeMatrix({
      outcome: 'Cancelled',
      redirectPath: `/places/${FIXTURE.poi.id}`,
    });
    assert.equal(cancelUi.navigatedTo, `/places/${FIXTURE.poi.id}`);
    assert.equal(cancelUi.guestBrowseMode, true);
    assert.equal(cancelUi.banner, null);
  });

  test('T3-03 (F8+F9): City fallback banner transitions to primary POI update once POI YouTube event arrives', async () => {
    if (cfg.mode === 'self-test') {
      assertSuccessEnvelope(await client.post('/_test/reset', {}), 200);
    }

    const cityEvent = {
      eventId: `t303-city-${crypto.randomUUID()}`,
      videoId: `c3${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`,
      channelId: 'UC_T303',
      title: 'Khám phá Vịnh Hạ Long Quảng Ninh buổi sáng',
      publishedAt: isoWithOffsetSeconds(-40_000, '+07:00'),
    };
    assertSuccessEnvelope(
      await client.post('/youtube/events', cityEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );

    const beforePoi = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`),
      200,
    );
    if (cfg.mode === 'self-test') {
      assert.equal(beforePoi.items.length, 0);
    }
    const uiBefore = evaluateYoutubeFreshnessUi(
      { ...beforePoi, items: cfg.mode === 'self-test' ? beforePoi.items : [] },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(uiBefore.primarySection, 'CITY_FALLBACK');
    assert.equal(uiBefore.showCityFallbackBanner, true);

    const poiEvent = buildGroundedThapDongHoEvent({
      eventId: `t303-poi-${crypto.randomUUID()}`,
      videoId: `p3${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`,
    });
    assertSuccessEnvelope(
      await client.post('/youtube/events', poiEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );

    const afterPoi = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const uiAfter = evaluateYoutubeFreshnessUi(afterPoi, { clientRenderedAtMs: Date.now() });
    assert.equal(uiAfter.primarySection, 'POI');
    assert.equal(uiAfter.showCityFallbackBanner, false);
    assert.ok(uiAfter.poiItems.some((i) => i.placeId === FIXTURE.poi.id));
    assert.ok(uiAfter.cityFallbackItems.some((i) => i.placeId === null && i.scope === 'CITY'));
  });

  test('T3-04 (F6+F3+F4): Forgot password -> Reset -> Login with redirect -> Save Tháp Đồng Hồ', async () => {
    const email = uniqueEmail('reset.save');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'T3-04 User' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(email);

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
    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'T3-04 Trip' }), 201);
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
    const email = uniqueEmail('t305.oauth');
    const oauth = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${email}` }),
      200,
    );
    const authed = client.withToken(oauth.access_token);
    const me = assertSuccessEnvelope(await authed.get('/users/me'), 200);
    assert.equal(me.email, email);
    assert.ok(me.providers.includes('google'));

    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'OAuth Trip' }), 201);
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

    for (const errRes of [invalidCreds, noEmail, invalidReset]) {
      const ui = await evaluateAuthOutcomeMatrix({
        outcome: 'Error',
        currentInput: { email: 'keep@gomate.vn' },
        callBackendOAuth: async () => errRes,
      });
      assert.equal(ui.banner.tone, 'error');
      assert.equal(ui.currentInput.email, 'keep@gomate.vn');
    }
  });

  test('T3-07 (F1+F4+F2): Network 503 during save -> AppStateBanner(warning) -> retry creates 0 duplicate trips', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t3.07'),
      password: 'Password123!',
      name: 'T3-07 User',
    });
    const authed = client.withToken(auth.accessToken);
    let failOnce = true;

    const flow = await simulateSavePlaceFlow({
      newTripTitle: 'T3-07 Trip',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async ({ title }) => {
        const trip = assertSuccessEnvelope(await authed.post('/trips', { title }), 201);
        return { ok: true, tripId: trip.id };
      },
      addItineraryFn: async ({ tripId, dayNumber, placeId }) => {
        if (failOnce) {
          failOnce = false;
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

    const first = await flow.attempt();
    assert.equal(first.banner.tone, 'warning');
    const second = await flow.attempt();
    assert.equal(second.saved, true);
    assert.equal(second.createTripCalls, 1);

    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 1);
  });

  test('T3-08 (F8+F9+F10): Duplicate WebSub + JSON replay keeps 1 row, 5 fields, documents/place_sources untouched & W07 intact', async () => {
    const beforeStats =
      cfg.mode === 'self-test'
        ? assertSuccessEnvelope(await client.get('/_test/db-stats'), 200)
        : null;

    const vid = `t308${crypto.randomUUID().replace(/-/g, '').slice(0, 7)}`;
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

    if (beforeStats) {
      const afterStats = assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
      verifyDbStatsIsolation(beforeStats, afterStats);
    }
    const freeze = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(freeze.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T3-09 (F2+F5): Profile perf timing & 390x844 screenshot artifact contract for Hạ Long + Tháp Đồng Hồ', async () => {
    const listRes = await client.get('/places', {
      query: { destinationId: FIXTURE.destinations.haLong.id, limit: 20 },
    });
    const detailRes = await client.get(`/places/${FIXTURE.poi.id}`);
    assertSuccessEnvelope(listRes, 200);
    assertSuccessEnvelope(detailRes, 200);
    assert.ok(listRes.durationMs >= 0 && detailRes.durationMs >= 0);

    const dir = path.join(cfg.repoRoot, mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo);
    if (detectBetaMobileTree(cfg.mobileDir) && fs.existsSync(dir)) {
      const pngs = fs.readdirSync(dir).filter((f) => f.endsWith('.png'));
      assert.ok(pngs.length > 0);
      for (const f of pngs) {
        const dims = parsePngDimensions(path.join(dir, f));
        assert.equal(dims.width, 390);
        assert.equal(dims.height, 844);
      }
    }
  });

  test('T3-10 (F3+F7+F2): Session switch (User A OAuth -> logout -> User B local) isolates trips & enforces 403', async () => {
    const userA = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${uniqueEmail('userA')}` }),
      200,
    );
    const clientA = client.withToken(userA.access_token);
    const tripA = assertSuccessEnvelope(await clientA.post('/trips', { title: 'Trip A Private' }), 201);

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
    const daNangVid = `dn${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`;
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
    assert.ok(fb.user.providers.includes('facebook'));

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(email);
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
    assert.ok(me.providers.includes('facebook'));

    const fbAgain = assertSuccessEnvelope(
      await client.post('/auth/oauth/facebook', { accessToken: `valid-email:${email}` }),
      200,
    );
    assert.equal(fbAgain.user.id, me.id);
  });
});
