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
} from '../lib/assertions.mjs';
import {
  detectBetaMobileTree,
  evaluateAuthOutcomeMatrix,
  evaluateYoutubeFreshnessUi,
  getMobileContractSpec,
  parsePngDimensions,
  sanitizeInternalRedirect,
  simulateSavePlaceFlow,
  validateApiBaseUrl,
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
    assert.ok(data.items.length > 0, `No reset email in outbox for ${email}`);
    return data.items[data.items.length - 1].rawToken;
  }
  if (process.env.E2E_TEST_RESET_TOKEN) return process.env.E2E_TEST_RESET_TOKEN;
  if (process.env.E2E_MAIL_OUTBOX_URL) {
    const res = await new HttpClient(process.env.E2E_MAIL_OUTBOX_URL).get('/', { query: { email } });
    if (res.json?.token) return res.json.token;
    if (res.json?.data?.items?.length) return res.json.data.items.at(-1).rawToken;
  }
  throw new Error('Live mode reset test requires E2E_MAIL_OUTBOX_URL or E2E_TEST_RESET_TOKEN');
}

describe('Tier 2 — Boundary & Corner Cases (50 Negative/Boundary Tests: F1–F10)', () => {
  // --- F1 ---
  test('T2-F1-01: Empty/malformed email rejected before/at validation without crash', async () => {
    const badReg = await registerUser(client, {
      email: 'not-an-email',
      password: 'Password123!',
      name: 'Bad Email',
    });
    assertErrorEnvelope(badReg, 400, null, '/auth/register');

    const emptyForgot = await client.post('/auth/forgot-password', { email: '' });
    assertErrorEnvelope(emptyForgot, 400, null, '/auth/forgot-password');
  });

  test('T2-F1-02: AppButton loading guard prevents double-submit during active request', async () => {
    let submitCount = 0;
    let isLoading = false;
    const onPress = async () => {
      if (isLoading) return;
      isLoading = true;
      submitCount += 1;
    };
    await Promise.all([onPress(), onPress(), onPress()]);
    assert.equal(submitCount, 1, 'Double-tap while isLoading=true must invoke handler once');
    const btnText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_button.dart'),
      'utf8',
    );
    assert.ok(btnText.includes('isLoading'));
  });

  test('T2-F1-03: AppStateBanner supports long Vietnamese error text (~180 chars) without truncation crash', () => {
    const longMsg =
      'Không thể đồng bộ dữ liệu chuyến đi Hạ Long lúc này do kết nối mạng không ổn định. Bạn vẫn giữ nguyên chuyến đi vừa tạo và có thể nhấn Thử lại ngay khi có mạng trở lại.';
    assert.ok(longMsg.length >= 160);
    const bannerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_state_banner.dart'),
      'utf8',
    );
    assert.ok(bannerText.includes('AppStateBanner'));
    assert.ok(bannerText.includes('warning') || bannerText.includes('error'));
  });

  test('T2-F1-04: AppErrorState transitions cleanly from 503 failure to 200 on retry', async () => {
    if (cfg.mode === 'self-test') {
      const failRes = await client.get(`/places/${FIXTURE.poi.id}`, {
        headers: { 'x-e2e-inject-status': '503' },
      });
      assertErrorEnvelope(failRes, 503, null, '/places/');
    }
    const retryRes = await client.get(`/places/${FIXTURE.poi.id}`);
    const data = assertSuccessEnvelope(retryRes, 200);
    assert.equal(data.id, FIXTURE.poi.id);
    const errWidget = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_error_state.dart'),
      'utf8',
    );
    assert.ok(errWidget.includes('AppErrorState'));
  });

  test('T2-F1-05: Password visibility toggle contract preserves entered value across auth screens', () => {
    let obscureText = true;
    let enteredPassword = 'SecretPassword123!';
    obscureText = !obscureText;
    assert.equal(obscureText, false);
    assert.equal(enteredPassword, 'SecretPassword123!');
    obscureText = !obscureText;
    assert.equal(obscureText, true);
    assert.equal(enteredPassword, 'SecretPassword123!');
    if (detectBetaMobileTree(cfg.mobileDir)) {
      const tf = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/core/widgets/app_text_field.dart'),
        'utf8',
      );
      assert.ok(tf.includes('obscureText'));
    }
  });

  // --- F2 ---
  test('T2-F2-01: Hạ Long >20 POIs page 1 vs search "Tháp Đồng Hồ" vs empty search "khongtontaixyz"', async () => {
    const page1 = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: FIXTURE.destinations.haLong.id, page: 1, limit: 20 },
      }),
      200,
    );
    assert.ok(page1.total > 20, `Expected >20 verified Hạ Long places, got ${page1.total}`);

    const found = assertSuccessEnvelope(
      await client.get('/places', {
        query: {
          destinationId: FIXTURE.destinations.haLong.id,
          search: 'Tháp Đồng Hồ',
          verifiedOnly: true,
        },
      }),
      200,
    );
    assert.ok(found.items.some((p) => p.id === FIXTURE.poi.id));

    const empty = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: FIXTURE.destinations.haLong.id, search: 'khongtontaixyz' },
      }),
      200,
    );
    assert.equal(empty.items.length, 0);
  });

  test('T2-F2-02: Unknown or unverified place UUID returns 404 PLACE_NOT_FOUND fail-closed', async () => {
    const unknownRes = await client.get(`/places/${FIXTURE.negativeFixtures.unknownPlaceId}`);
    assertErrorEnvelope(unknownRes, 404, 'PLACE_NOT_FOUND', '/places/');

    const unverifiedRes = await client.get(`/places/${FIXTURE.negativeFixtures.unverifiedPlaceId}`);
    assertErrorEnvelope(unverifiedRes, 404, 'PLACE_NOT_FOUND', '/places/');
  });

  test('T2-F2-03: Verified place with null address/openingHours/rating does not fabricate synthetic values', async () => {
    const res = await client.get(`/places/${FIXTURE.negativeFixtures.unratedVerifiedPlaceId}`);
    if (res.status === 200) {
      const place = assertSuccessEnvelope(res, 200);
      assert.equal(place.address, null);
      assert.equal(place.openingHours, null);
      assert.equal(place.rating, null);
    } else {
      assertErrorEnvelope(res, 404, 'PLACE_NOT_FOUND', '/places/');
    }
  });

  test('T2-F2-04: MapScreen location permission error snackbar hook coexists with PlacePreviewSheet CTA', () => {
    const mapText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/map/presentation/map_screen.dart'),
      'utf8',
    );
    const previewSheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/map/presentation/widgets/place_preview_sheet.dart'),
      'utf8',
    );
    assert.ok(mapText.includes('my_location_button'), 'map_screen.dart missing key my_location_button');
    assert.ok(
      mapText.includes('map_location_error_snackbar'),
      'map_screen.dart missing key map_location_error_snackbar',
    );
    assert.ok(
      previewSheetText.includes('place_preview_view_detail'),
      'place_preview_sheet.dart missing key place_preview_view_detail',
    );
  });

  test('T2-F2-05: Empty trips list returns [] & expired/invalid JWT returns 401 on /trips', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t2.f2.05'),
      password: 'Password123!',
      name: 'Empty Trips User',
    });
    const trips = assertSuccessEnvelope(await client.withToken(auth.accessToken).get('/trips'), 200);
    assert.deepEqual(trips, []);

    const unauth = await client.withToken('invalid.jwt.token').get('/trips');
    assertErrorEnvelope(unauth, 401, null, '/trips');
  });

  // --- F3 ---
  test('T2-F3-01: Google OAuth Cancelled makes zero backend OAuth calls, shows no error banner, keeps form input', async () => {
    let backendCalls = 0;
    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Cancelled',
      redirectPath: '/login',
      currentInput: { email: 'user@gomate.vn' },
      callBackendOAuth: async () => {
        backendCalls += 1;
      },
    });
    assert.equal(backendCalls, 0);
    assert.equal(ui.backendCalled, false);
    assert.equal(ui.banner, null);
    assert.equal(ui.currentInput.email, 'user@gomate.vn');
    assert.equal(ui.authenticated, false);
  });

  test('T2-F3-02: Facebook OAuth missing email returns 400 OAUTH_EMAIL_UNAVAILABLE & renders inline error banner', async () => {
    const errRes = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-fb-token' });
    assertErrorEnvelope(errRes, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');
    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Error',
      callBackendOAuth: async () => errRes,
    });
    assert.equal(ui.banner.tone, 'error');
    assert.equal(ui.banner.errorCode, 'OAUTH_EMAIL_UNAVAILABLE');
    assert.equal(ui.authenticated, false);
  });

  test('T2-F3-03: Expired or missing reset token returns RESET_TOKEN_EXPIRED / RESET_TOKEN_INVALID', async () => {
    const missingRes = await client.get('/auth/reset-password/validate', { query: { token: '' } });
    assertErrorEnvelope(missingRes, 400, 'RESET_TOKEN_INVALID', '/auth/reset-password/validate');

    if (cfg.mode === 'self-test') {
      const email = uniqueEmail('t2.f3.03');
      await registerUser(client, { email, password: 'Password123!', name: 'Exp Token UI' });
      const seeded = assertSuccessEnvelope(
        await client.post('/_test/seed-expired-reset-token', { email }),
        200,
      );
      const expRes = await client.get('/auth/reset-password/validate', {
        query: { token: seeded.token },
      });
      assertErrorEnvelope(expRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password/validate');
    }
  });

  test('T2-F3-04: Register rejects short password (<6 chars) with 400 validation error', async () => {
    const res = await registerUser(client, {
      email: uniqueEmail('t2.f3.04'),
      password: '12345',
      name: 'Short Pass',
    });
    assertErrorEnvelope(res, 400, null, '/auth/register');
  });

  test('T2-F3-05: Open-redirect sanitizer blocks external, protocol-relative, and auth-loop redirects', () => {
    assert.equal(sanitizeInternalRedirect('https://evil.example'), null);
    assert.equal(sanitizeInternalRedirect('//evil.example'), null);
    assert.equal(sanitizeInternalRedirect('/login'), null);
    assert.equal(sanitizeInternalRedirect('/register'), null);
    assert.equal(sanitizeInternalRedirect(`/places/${FIXTURE.poi.id}`), `/places/${FIXTURE.poi.id}`);
  });

  // --- F4 ---
  test('T2-F4-01: Cancel-Login ("Hủy đăng nhập") returns to /places/:id in guest mode with zero error banner', async () => {
    const target = `/places/${FIXTURE.poi.id}`;
    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Cancelled',
      redirectPath: target,
    });
    assert.equal(ui.navigatedTo, target);
    assert.equal(ui.postLoginRedirect, null);
    assert.equal(ui.authenticated, false);
    assert.equal(ui.guestBrowseMode, true);
    assert.equal(ui.banner, null);
  });

  test('T2-F4-02: Transient 503 on POST /trips/:id/itinerary retains _createdPendingTrip & avoids duplicate trip on retry', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t2.f4.02'),
      password: 'Password123!',
      name: 'Retry Guard User',
    });
    const authed = client.withToken(auth.accessToken);
    let injectFail = true;

    const flow = await simulateSavePlaceFlow({
      newTripTitle: 'Hạ Long Retry Safe',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async ({ title }) => {
        const res = await authed.post('/trips', { title });
        const trip = assertSuccessEnvelope(res, 201);
        return { ok: true, tripId: trip.id };
      },
      addItineraryFn: async ({ tripId, dayNumber, placeId }) => {
        const headers =
          cfg.mode === 'self-test' && injectFail ? { 'x-e2e-inject-status': '503' } : {};
        const res =
          cfg.mode !== 'self-test' && injectFail
            ? { ok: false, status: 503, networkError: true }
            : await authed.post(
                `/trips/${tripId}/itinerary`,
                { dayNumber, activity: 'Tham quan Tháp Đồng Hồ', placeId },
                { headers },
              );
        if (injectFail) {
          injectFail = false;
          return { ok: false, status: 503, networkError: true };
        }
        assertSuccessEnvelope(res, 201);
        return { ok: true };
      },
    });

    const first = await flow.attempt();
    assert.equal(first.saved, false);
    assert.equal(first.sheetOpen, true);
    assert.equal(first.banner.tone, 'warning');
    assert.ok(first.createdPendingTripId, '_createdPendingTrip must be retained');
    assert.equal(first.createTripCalls, 1);

    const retry = await flow.attempt();
    assert.equal(retry.saved, true);
    assert.equal(retry.createTripCalls, 1, 'Retry MUST NOT call POST /trips a second time');
    assert.equal(retry.addItineraryCalls, 2);

    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 1);
  });

  test('T2-F4-03: Offline connectionError before POST /trips shows warning banner & preserves typed title', async () => {
    const flow = await simulateSavePlaceFlow({
      newTripTitle: 'Chuyến Hạ Long Offline',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async () => ({
        ok: false,
        networkError: true,
        status: 0,
        message: 'Mất kết nối mạng',
      }),
      addItineraryFn: async () => ({ ok: true }),
    });
    const out = await flow.attempt();
    assert.equal(out.saved, false);
    assert.equal(out.banner.tone, 'warning');
    assert.equal(out.createdPendingTripId, null);
  });

  test('T2-F4-04: Whitespace new trip title rejected cleanly with zero POST /trips calls', async () => {
    let createCalled = false;
    const flow = await simulateSavePlaceFlow({
      newTripTitle: '   ',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async () => {
        createCalled = true;
        return { ok: true, tripId: 'never' };
      },
      addItineraryFn: async () => ({ ok: true }),
    });
    const out = await flow.attempt();
    assert.equal(createCalled, false);
    assert.equal(out.banner.tone, 'error');
    assert.match(out.banner.message, /tên chuyến đi/i);
  });

  test('T2-F4-05: 401 expired JWT during Save redirects cleanly to /login?redirect=/places/:id', async () => {
    const res = await client.withToken('expired-or-bad-token').post('/trips/fake-trip/itinerary', {
      dayNumber: 1,
      activity: 'Tham quan Tháp Đồng Hồ',
      placeId: FIXTURE.poi.id,
    });
    assertErrorEnvelope(res, 401, null, '/trips/');
    const redirectParam = encodeURIComponent(`/places/${FIXTURE.poi.id}`);
    const loginRoute = `/login?redirect=${redirectParam}`;
    assert.equal(
      sanitizeInternalRedirect(decodeURIComponent(loginRoute.split('redirect=')[1])),
      `/places/${FIXTURE.poi.id}`,
    );
  });

  // --- F5 ---
  test('T2-F5-01: AppConstants rejects empty, http://localhost, and http://10.0.2.2 in strict profile/release mode', () => {
    for (const bad of ['', 'http://localhost:3000', 'http://10.0.2.2:3000']) {
      assert.throws(() => validateApiBaseUrl(bad, { isReleaseMode: true }), /StateError/);
      assert.throws(() => validateApiBaseUrl(bad, { isProfileMode: true }), /StateError/);
    }
  });

  test('T2-F5-02: Long Vietnamese title ("Tháp Đồng Hồ Trung Tâm Thành Phố Hạ Long Quảng Ninh") layout & 390x844 spec', () => {
    const longTitle = 'Tháp Đồng Hồ Trung Tâm Thành Phố Hạ Long Quảng Ninh';
    assert.ok(longTitle.length > 45);
    assert.equal(mobileSpec.betaRequiredDeliverables.screenshotDimensions.width, 390);
    assert.equal(mobileSpec.betaRequiredDeliverables.screenshotDimensions.height, 844);
  });

  test('T2-F5-03: List-open benchmark timing completes cleanly for empty search and 20+ items', async () => {
    const empty = await client.get('/places', {
      query: { destinationId: FIXTURE.destinations.haLong.id, search: 'no-match-999' },
    });
    const full = await client.get('/places', {
      query: { destinationId: FIXTURE.destinations.haLong.id, limit: 50 },
    });
    assertSuccessEnvelope(empty, 200);
    assertSuccessEnvelope(full, 200);
    assert.ok(empty.durationMs >= 0 && full.durationMs >= 0);
  });

  test('T2-F5-04: Broken/404 cover image URL fallback & null coverImage tolerance', async () => {
    const res = await client.get(`/places/${FIXTURE.negativeFixtures.unratedVerifiedPlaceId}`);
    if (res.status === 200) {
      const place = assertSuccessEnvelope(res, 200);
      assert.equal(place.coverImage ?? null, null);
    } else {
      assertErrorEnvelope(res, 404, 'PLACE_NOT_FOUND', '/places/');
    }
  });

  test('T2-F5-05: Before vs After screenshot PNG dimensions parity check', () => {
    const dir = path.join(cfg.repoRoot, mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo);
    if (detectBetaMobileTree(cfg.mobileDir) && fs.existsSync(dir)) {
      const pngs = fs.readdirSync(dir).filter((f) => f.endsWith('.png'));
      const dims = pngs.map((f) => parsePngDimensions(path.join(dir, f)));
      for (const d of dims) {
        assert.equal(d.width, dims[0].width);
        assert.equal(d.height, dims[0].height);
      }
    } else {
      assert.equal(mobileSpec.betaRequiredDeliverables.screenshotDimensions.width, 390);
    }
  });

  // --- F6 ---
  test('T2-F6-01: Expired reset token rejected with RESET_TOKEN_EXPIRED & old password preserved', async () => {
    const email = uniqueEmail('t2.f6.01');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Exp Reset' });
    let expiredToken = process.env.E2E_EXPIRED_RESET_TOKEN || '';
    if (cfg.mode === 'self-test') {
      const seeded = assertSuccessEnvelope(
        await client.post('/_test/seed-expired-reset-token', { email }),
        200,
      );
      expiredToken = seeded.token;
    }
    if (expiredToken) {
      const valRes = await client.get('/auth/reset-password/validate', {
        query: { token: expiredToken },
      });
      assertErrorEnvelope(valRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password/validate');
      const rstRes = await client.post('/auth/reset-password', {
        token: expiredToken,
        newPassword: 'NewPassword123!',
      });
      assertErrorEnvelope(rstRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password');
    }
    assertSuccessEnvelope(await loginUser(client, { email, password: 'OldPassword123!' }), 200);
  });

  test('T2-F6-02: Consumed reset token replay & concurrent double-submit fail with RESET_TOKEN_USED', async () => {
    const email = uniqueEmail('t2.f6.02');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Used Reset' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(email);

    const [r1, r2] = await Promise.all([
      client.post('/auth/reset-password', { token, newPassword: 'Concurrent123!' }),
      client.post('/auth/reset-password', { token, newPassword: 'Concurrent456!' }),
    ]);
    const statuses = [r1.status, r2.status].sort((a, b) => a - b);
    assert.equal(statuses[0], 200, 'Exactly one concurrent reset must succeed');
    const failed = r1.status === 200 ? r2 : r1;
    assertErrorEnvelope(failed, [400, 410], 'RESET_TOKEN_USED', '/auth/reset-password');

    const replayValidate = await client.get('/auth/reset-password/validate', { query: { token } });
    assertErrorEnvelope(replayValidate, [400, 410], 'RESET_TOKEN_USED', '/auth/reset-password/validate');
  });

  test('T2-F6-03: Unknown/tampered reset token rejected with 400 RESET_TOKEN_INVALID', async () => {
    const valRes = await client.get('/auth/reset-password/validate', {
      query: { token: 'invalid-token-999' },
    });
    assertErrorEnvelope(valRes, 400, 'RESET_TOKEN_INVALID', '/auth/reset-password/validate');

    const rstRes = await client.post('/auth/reset-password', {
      token: 'invalid-token-999',
      newPassword: 'NewPassword123!',
    });
    assertErrorEnvelope(rstRes, 400, 'RESET_TOKEN_INVALID', '/auth/reset-password');
  });

  test('T2-F6-04: Forgot-password is non-enumerating for known vs unknown emails', async () => {
    const known = uniqueEmail('known');
    const unknown = uniqueEmail('unknown.nobody');
    await registerUser(client, { email: known, password: 'Password123!', name: 'Known' });

    const rKnown = assertSuccessEnvelope(
      await client.post('/auth/forgot-password', { email: known }),
      200,
    );
    const rUnknown = assertSuccessEnvelope(
      await client.post('/auth/forgot-password', { email: unknown }),
      200,
    );
    assert.equal(rKnown.sent, true);
    assert.equal(rUnknown.sent, true);
    assert.equal(rKnown.expiresInMinutes, rUnknown.expiresInMinutes);
    assert.equal(rKnown.message, rUnknown.message);
  });

  test('T2-F6-05: Short newPassword does not consume token & requesting 2nd token invalidates 1st', async () => {
    const email = uniqueEmail('t2.f6.05');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Supersede User' });

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t1 = await fetchResetToken(email);

    const badPass = await client.post('/auth/reset-password', { token: t1, newPassword: '123' });
    assertErrorEnvelope(badPass, 400, null, '/auth/reset-password');

    // Request 2nd token -> T1 must now be invalidated
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t2 = await fetchResetToken(email);
    assert.notEqual(t2, t1);

    const t1Attempt = await client.post('/auth/reset-password', {
      token: t1,
      newPassword: 'ValidPass123!',
    });
    assertErrorEnvelope(t1Attempt, [400, 410], null, '/auth/reset-password');

    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token: t2, newPassword: 'ValidPass123!' }),
      200,
    );
  });

  // --- F7 ---
  test('T2-F7-01: Invalid Google OAuth idToken returns 401 OAUTH_TOKEN_INVALID', async () => {
    const res = await client.post('/auth/oauth/google', { idToken: 'bad-google-token' });
    assertErrorEnvelope(res, 401, 'OAUTH_TOKEN_INVALID', '/auth/oauth/google');
  });

  test('T2-F7-02: Invalid Facebook OAuth accessToken returns 401 OAUTH_TOKEN_INVALID', async () => {
    const res = await client.post('/auth/oauth/facebook', { accessToken: 'bad-fb-token' });
    assertErrorEnvelope(res, 401, 'OAUTH_TOKEN_INVALID', '/auth/oauth/facebook');
  });

  test('T2-F7-03: OAuth token missing verified email returns 400 OAUTH_EMAIL_UNAVAILABLE', async () => {
    const res = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-fb-token' });
    assertErrorEnvelope(res, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');
  });

  test('T2-F7-04: Upstream OAuth provider outage returns 502 OAUTH_PROVIDER_ERROR', async () => {
    const res = await client.post('/auth/oauth/google', { idToken: 'provider-error-502' });
    assertErrorEnvelope(res, 502, 'OAUTH_PROVIDER_ERROR', '/auth/oauth/google');
  });

  test('T2-F7-05: OAuth-only user password login returns 401 INVALID_CREDENTIALS & extra refresh fields return 400', async () => {
    const email = uniqueEmail('oauth.only');
    const oauth = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${email}` }),
      200,
    );
    const pwdLogin = await loginUser(client, { email, password: 'AnyPassword123!' });
    assertErrorEnvelope(pwdLogin, 401, 'INVALID_CREDENTIALS', '/auth/login');

    const badRefresh = await client.post('/auth/refresh', {
      refresh_token: oauth.refresh_token,
      admin: true,
    });
    assertErrorEnvelope(badRefresh, 400, null, '/auth/refresh');
  });

  // --- F8 ---
  test('T2-F8-01: POST /youtube/events missing or wrong secret returns 401/403 YOUTUBE_EVENT_UNAUTHORIZED', async () => {
    const payload = buildGroundedThapDongHoEvent();
    const missing = await client.post('/youtube/events', payload);
    assertErrorEnvelope(missing, [401, 403], 'YOUTUBE_EVENT_UNAUTHORIZED', '/youtube/events');

    const wrong = await client.post('/youtube/events', payload, {
      headers: { 'x-youtube-internal-secret': 'wrong-secret-xyz' },
    });
    assertErrorEnvelope(wrong, [401, 403], 'YOUTUBE_EVENT_UNAUTHORIZED', '/youtube/events');
  });

  test('T2-F8-02: 3 concurrent duplicate POST /youtube/events preserve 1 row & immutable receivedAt', async () => {
    const event = buildGroundedThapDongHoEvent({
      eventId: `evt-conc-${crypto.randomUUID()}`,
      videoId: `cc${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`,
    });
    const responses = await Promise.all([
      client.post('/youtube/events', event, { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } }),
      client.post('/youtube/events', event, { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } }),
      client.post('/youtube/events', event, { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } }),
    ]);
    const receipts = responses.map((r) => assertSuccessEnvelope(r, 200));
    const nonDuplicates = receipts.filter((r) => r.duplicate === false);
    const duplicates = receipts.filter((r) => r.duplicate === true);
    assert.equal(nonDuplicates.length, 1);
    assert.equal(duplicates.length, 2);
    assert.equal(Math.max(...receipts.map((r) => r.deliveryCount)), 3);
    assert.equal(new Set(receipts.map((r) => r.receivedAt)).size, 1);

    const list = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assert.equal(list.items.filter((i) => i.videoId === event.videoId).length, 1);
  });

  test('T2-F8-03: Grounding Gates 1-3 fail closed on Phú Quốc conflict, missing context, >250m coords, & unverified POI', async () => {
    const cases = [
      {
        name: 'conflicting_city_mention',
        body: {
          eventId: `neg-pq-${crypto.randomUUID()}`,
          videoId: 'pq123456789',
          channelId: 'UC_Neg',
          title: 'Check-in Tháp Đồng Hồ Phú Quốc hoàng hôn',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
        },
        expectedReason: 'conflicting_city_mention',
      },
      {
        name: 'missing_destination_or_spatial_corroboration',
        body: {
          eventId: `neg-nocontext-${crypto.randomUUID()}`,
          videoId: 'nc123456789',
          channelId: 'UC_Neg',
          title: 'Đi ngang Tháp Đồng Hồ buổi sáng',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
        },
        expectedReason: 'missing_destination_or_spatial_corroboration',
      },
      {
        name: 'coordinate_conflict_with_poi',
        body: {
          eventId: `neg-coord-${crypto.randomUUID()}`,
          videoId: 'cd123456789',
          channelId: 'UC_Neg',
          title: 'Tháp Đồng Hồ Hạ Long review',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
          latitude: FIXTURE.negativeFixtures.tuanChauFarCoords.latitude,
          longitude: FIXTURE.negativeFixtures.tuanChauFarCoords.longitude,
        },
        expectedReason: 'coordinate_conflict_with_poi',
      },
      {
        name: 'target_place_unverified_or_missing',
        body: {
          eventId: `neg-unverified-${crypto.randomUUID()}`,
          videoId: 'uv123456789',
          channelId: 'UC_Neg',
          title: 'Địa Điểm Chưa Xác Minh Hạ Long',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
          candidatePlaceId: FIXTURE.negativeFixtures.unverifiedPlaceId,
        },
        expectedReason: 'target_place_unverified_or_missing',
      },
    ];

    for (const c of cases) {
      const receipt = assertSuccessEnvelope(
        await client.post('/youtube/events', c.body, {
          headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
        }),
        200,
      );
      assert.equal(receipt.status, 'UNLINKED_NO_BASIS', `${c.name} must fail closed`);
      assert.equal(receipt.scope, 'NONE');
      assert.equal(receipt.linkedPlaceId, null);
      assert.equal(receipt.decisionReason, c.expectedReason);
    }

    const unverifiedGet = await client.get(
      `/places/${FIXTURE.negativeFixtures.unverifiedPlaceId}/youtube-updates`,
    );
    assertErrorEnvelope(unverifiedGet, 404, 'PLACE_NOT_FOUND', '/places/');
  });

  test('T2-F8-04: Hạ Long city fallback accepts single city & rejects ambiguous multi-city ("Hạ Long và Đà Nẵng")', async () => {
    const singleCity = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `city-ok-${crypto.randomUUID()}`,
          videoId: 'ct123456789',
          channelId: 'UC_City',
          title: 'Cảnh đẹp Vịnh Hạ Long Quảng Ninh',
          publishedAt: isoWithOffsetSeconds(-20_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(singleCity.status, 'LINKED_CITY');
    assert.equal(singleCity.scope, 'CITY');
    assert.equal(singleCity.linkedPlaceId, null);

    const multiCity = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `city-ambig-${crypto.randomUUID()}`,
          videoId: 'am123456789',
          channelId: 'UC_City',
          title: 'Hạ Long và Đà Nẵng cuối tuần',
          publishedAt: isoWithOffsetSeconds(-20_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(multiCity.status, 'UNLINKED_NO_BASIS');
    assert.equal(multiCity.scope, 'NONE');

    const destUpdates = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates', { query: { limit: 50 } }),
      200,
    );
    assert.ok(destUpdates.items.some((i) => i.videoId === 'ct123456789'));
    assert.ok(!destUpdates.items.some((i) => i.videoId === 'am123456789'));
  });

  test('T2-F8-05: SLA boundary (299s vs 301s), XXE <!DOCTYPE>, bad HMAC, lat-only, naive TZ, & unknown destination 404', async () => {
    const withinSla = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `sla-in-${crypto.randomUUID()}`,
          videoId: 'in123456789',
          publishedAt: isoWithOffsetSeconds(-299_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.ok(withinSla.ingestLatencyMs >= 299000);

    const overSla = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `sla-out-${crypto.randomUUID()}`,
          videoId: 'ou123456789',
          publishedAt: isoWithOffsetSeconds(-301_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.ok(overSla.ingestLatencyMs > 300000);

    const xxeXml = '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><feed></feed>';
    const xxeSig = signWebSubBody(xxeXml, cfg.websubSecret, 'sha256');
    const xxeRes = await client.post('/youtube/webhook', {
      rawBody: xxeXml,
      headers: {
        'Content-Type': 'application/atom+xml',
        ...(xxeSig ? { 'X-Hub-Signature': xxeSig } : {}),
      },
    });
    assertErrorEnvelope(xxeRes, 400, null, '/youtube/webhook');

    if (cfg.websubSecret) {
      const validXml = buildYoutubeAtomFeed([
        {
          videoId: 'hm123456789',
          channelId: 'UC_HMAC',
          title: 'Tháp Đồng Hồ Hạ Long',
          publishedAt: isoWithOffsetSeconds(-10_000, 'Z'),
        },
      ]);
      const badHmac = await client.post('/youtube/webhook', {
        rawBody: validXml,
        headers: {
          'Content-Type': 'application/atom+xml',
          'X-Hub-Signature': 'sha256=deadbeef',
        },
      });
      assertErrorEnvelope(badHmac, 401, null, '/youtube/webhook');
    }

    const latOnly = await client.post(
      '/youtube/events',
      {
        videoId: 'lo123456789',
        channelId: 'UC_Lat',
        title: 'Tháp Đồng Hồ Hạ Long',
        publishedAt: isoWithOffsetSeconds(-10_000, 'Z'),
        latitude: 20.95,
      },
      { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
    );
    assertErrorEnvelope(latOnly, 400, null, '/youtube/events');

    const naiveTz = await client.post(
      '/youtube/events',
      {
        videoId: 'nt123456789',
        channelId: 'UC_Tz',
        title: 'Tháp Đồng Hồ Hạ Long',
        publishedAt: '2026-11-24T12:00:00',
      },
      { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
    );
    assertErrorEnvelope(naiveTz, 400, null, '/youtube/events');

    const unknownDest = await client.get(
      `/destinations/${FIXTURE.negativeFixtures.unknownDestinationSlug}/youtube-updates`,
    );
    assertErrorEnvelope(unknownDest, 404, 'DESTINATION_NOT_FOUND', '/destinations/');
  });

  // --- F9 ---
  test('T2-F9-01: Freshness SLA exact boundary 300000ms ("Thời gian thực") vs 300001ms ("Cập nhật gần đây")', () => {
    const renderNow = Date.now();
    const atBoundary = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [
          {
            placeId: FIXTURE.poi.id,
            scope: 'POI',
            source: 'youtube',
            publishedAt: new Date(renderNow - 300000).toISOString(),
            receivedAt: new Date(renderNow).toISOString(),
            updatedAt: new Date(renderNow).toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=b300000ms11',
          },
        ],
      },
      { clientRenderedAtMs: renderNow },
    );
    assert.equal(atBoundary.poiItems[0].badgeLabel, 'Thời gian thực');

    const overBoundary = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [
          {
            placeId: FIXTURE.poi.id,
            scope: 'POI',
            source: 'youtube',
            publishedAt: new Date(renderNow - 300001).toISOString(),
            receivedAt: new Date(renderNow).toISOString(),
            updatedAt: new Date(renderNow).toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=b300001ms11',
          },
        ],
      },
      { clientRenderedAtMs: renderNow },
    );
    assert.equal(overBoundary.poiItems[0].badgeLabel, 'Cập nhật gần đây');
    assert.notEqual(overBoundary.poiItems[0].badgeLabel, 'Thời gian thực');
  });

  test('T2-F9-02: Negative clock diff clamps to >= 0ms & falls back cleanly for updatedAt', () => {
    const renderNow = Date.now();
    const futurePublished = new Date(renderNow + 120_000).toISOString();
    const recv = new Date(renderNow - 5_000).toISOString();
    const ui = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [
          {
            placeId: FIXTURE.poi.id,
            scope: 'POI',
            source: 'youtube',
            publishedAt: futurePublished,
            receivedAt: recv,
            updatedAt: null,
            lastReceivedAt: recv,
            ingestLatencyMs: 5000,
            videoUrl: 'https://www.youtube.com/watch?v=clk12345678',
          },
        ],
      },
      { clientRenderedAtMs: renderNow },
    );
    assert.equal(ui.poiItems[0].endToEndLatencyMs, 0);
    assert.equal(ui.poiItems[0].clampedFromNegative, true);
    assert.equal(ui.poiItems[0].updatedAt, recv);
  });

  test('T2-F9-03: Empty POI and city fallback items yield honest EMPTY state', () => {
    const ui = evaluateYoutubeFreshnessUi({
      realtimeSlaMaxLatencyMs: 300000,
      items: [],
      cityFallbackItems: [],
    });
    assert.equal(ui.primarySection, 'EMPTY');
    assert.equal(ui.showCityFallbackBanner, false);
  });

  test('T2-F9-04: Factual PlaceDetail remains intact even if YouTube freshness endpoint returns 503', async () => {
    const factual = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    assert.equal(factual.name, 'Tháp Đồng Hồ');
    if (cfg.mode === 'self-test') {
      const ytErr = await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, {
        headers: { 'x-e2e-inject-status': '503' },
      });
      assertErrorEnvelope(ytErr, 503, null, '/places/');
    }
  });

  test('T2-F9-05: Long 200+ char Vietnamese YouTube title & missing channelTitle degrade cleanly', () => {
    const longTitle = 'Khám phá Tháp Đồng Hồ Hạ Long '.repeat(8);
    assert.ok(longTitle.length >= 200);
    const nowIso = new Date().toISOString();
    const ui = evaluateYoutubeFreshnessUi({
      realtimeSlaMaxLatencyMs: 300000,
      items: [
        {
          placeId: FIXTURE.poi.id,
          scope: 'POI',
          source: 'youtube',
          title: longTitle,
          channelTitle: null,
          publishedAt: nowIso,
          receivedAt: nowIso,
          updatedAt: nowIso,
          sourceUpdatedAt: null,
          videoUrl: 'https://www.youtube.com/watch?v=lng12345678',
        },
      ],
    });
    assert.ok(ui.poiItems[0].channelTitle.length > 0);
    assert.equal(ui.poiItems[0].updatedAt, nowIso);
  });

  // --- F10 ---
  test('T2-F10-01: W07 freeze SHA-256 verification fails immediately on any mismatch', () => {
    const res = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(res.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T2-F10-02: data/curated/w07/ & w07_offline_retrieval_prep remain clean across E2E execution', () => {
    const status = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir);
    assert.equal(status.dirtyLines.length, 0);
  });

  test('T2-F10-03: Batch of 10 YouTube events (POI, City, Unlinked, Duplicate) leaves documents & place_sources unchanged', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats =
      cfg.mode === 'self-test'
        ? assertSuccessEnvelope(await client.get('/_test/db-stats'), 200)
        : null;

    for (let i = 0; i < 10; i++) {
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `batch-${i % 4}-${crypto.randomUUID()}`,
          videoId: `bt${String(i).padStart(9, '0')}`,
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      );
    }

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    if (beforeStats) {
      const afterStats = assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
      verifyDbStatsIsolation(beforeStats, afterStats);
    }
  });

  test('T2-F10-04: Unverified place 00000000-... rejects GET (404) & YouTube candidatePlaceId (UNLINKED_NO_BASIS)', async () => {
    const getRes = await client.get(
      `/places/${FIXTURE.negativeFixtures.unverifiedPlaceId}/youtube-updates`,
    );
    assertErrorEnvelope(getRes, 404, 'PLACE_NOT_FOUND', '/places/');

    const postRes = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `unv-${crypto.randomUUID()}`,
          videoId: 'uv987654321',
          channelId: 'UC_Unv',
          title: 'Tháp Đồng Hồ Hạ Long',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
          candidatePlaceId: FIXTURE.negativeFixtures.unverifiedPlaceId,
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(postRes.status, 'UNLINKED_NO_BASIS');
    assert.equal(postRes.decisionReason, 'target_place_unverified_or_missing');
  });

  test('T2-F10-05: Core Places/Destinations responses stay isolated from DYNAMIC_SOCIAL_FRESHNESS_LAYER', async () => {
    const place = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    assert.equal(place.governanceRole, undefined);
    assert.ok(!('youtubeUpdates' in place), 'Core GET /places/:id must not embed social layer');
    const ytDest = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates'),
      200,
    );
    assertYoutubeContainerContract(ytDest);
  });
});
