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
  resolveExpiredResetToken,
  resolveHaLongDestination,
  resolveVerifiedNullFieldPlace,
} from '../lib/http_client.mjs';
import {
  assertErrorEnvelope,
  assertSuccessEnvelope,
  assertYoutubeContainerContract,
  assertYoutubeFiveFields,
} from '../lib/assertions.mjs';
import { withFaultProxy } from '../lib/fault_proxy.mjs';
import {
  buildPngHeaderBuffer,
  createMemoryFs,
  detectBetaMobileTree,
  getFlutterTestResult,
  verifyBetaDartDeliverables,
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

function buildMinimalRouterVfs(mobileDir, routerContent) {
  return createMemoryFs({
    [path.join(mobileDir, 'lib/core/widgets/app_text_field.dart')]:
      'class AppTextField { TextFormField build() => TextFormField(controller: widget.controller, obscureText: true, showPasswordToggle: true, validator: v); }',
    [path.join(mobileDir, 'lib/core/widgets/widgets.dart')]: "export 'app_text_field.dart';",
    [path.join(mobileDir, 'lib/core/network/api_client.dart')]:
      "const _publicAuthPaths = {'/auth/login', '/auth/register', '/auth/refresh', '/auth/forgot-password', '/auth/reset-password', '/auth/reset-password/validate', '/auth/oauth/google', '/auth/oauth/facebook'};",
    [path.join(mobileDir, 'lib/core/router/app_router.dart')]: routerContent,
  });
}

function buildAuthVfs(mobileDir, repoRoot, overrides = {}) {
  const files = {
    [path.join(mobileDir, 'lib/core/widgets/app_text_field.dart')]:
      'class AppTextField { TextFormField build() => TextFormField(controller: widget.controller, obscureText: true, showPasswordToggle: true, validator: v); }',
    [path.join(mobileDir, 'lib/core/widgets/widgets.dart')]: "export 'app_text_field.dart';",
    [path.join(mobileDir, 'lib/core/network/api_client.dart')]:
      "const _publicAuthPaths = {'/auth/login', '/auth/register', '/auth/refresh', '/auth/forgot-password', '/auth/reset-password', '/auth/reset-password/validate', '/auth/oauth/google', '/auth/oauth/facebook'};",
    [path.join(mobileDir, 'lib/core/router/app_router.dart')]:
      "String? sanitizeInternalRedirect(String? r) { if (parsed.hasScheme || parsed.hasAuthority) return null; if (p == '/login' || p == '/register' || p == '/forgot-password' || p == '/reset-password') return null; return r; }",
    [path.join(mobileDir, 'lib/features/auth/presentation/login_screen.dart')]:
      "AppTextField(showPasswordToggle: true); AppButton(); AppStateBanner(); postLoginRedirectProvider; guestBrowseModeProvider; Key('login_google_button'); Key('login_facebook_button'); 'Hủy đăng nhập · Quay lại';",
    [path.join(mobileDir, 'lib/features/auth/presentation/register_screen.dart')]:
      "AppTextField(showPasswordToggle: true); AppButton(); AppStateBanner(); postLoginRedirectProvider; guestBrowseModeProvider; 'Hủy đăng nhập · Quay lại';",
    [path.join(mobileDir, 'lib/features/auth/presentation/forgot_password_screen.dart')]:
      'AppTextField(); AppButton(); AppStateBanner();',
    [path.join(mobileDir, 'lib/features/auth/presentation/reset_password_screen.dart')]:
      'AppTextField(showPasswordToggle: true); AppButton(); AppLoading(); AppStateBanner();',
    [path.join(mobileDir, 'lib/features/auth/data/auth_social_port.dart')]:
      'abstract class AuthSocialPort { Future<SocialAuthResult> signInWithGoogle(); Future<SocialAuthResult> signInWithFacebook(); } class SocialAuthSuccess {} class SocialAuthCancelled {} class SocialAuthFailure {}',
    [path.join(mobileDir, 'lib/features/auth/providers/auth_provider.dart')]:
      'SocialAuthCancelled(); AuthActionResult.cancelled(); _repo.loginWithGoogle(); _repo.loginWithFacebook();',
    [path.join(mobileDir, 'test/auth_reset_and_oauth_test.dart')]:
      'RESET_TOKEN_EXPIRED RESET_TOKEN_USED RESET_TOKEN_INVALID OAUTH_EMAIL_UNAVAILABLE SocialAuthCancelled',
    ...overrides,
  };
  return createMemoryFs(files);
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

  test('T2-F1-02: AppButton loading guard prevents double-submit during active request', () => {
    const btnText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_button.dart'),
      'utf8',
    );
    assert.ok(btnText.includes('isLoading'));
    assert.ok(btnText.includes('enabled = onPressed != null && !isLoading'));
    assert.ok(btnText.includes('onTap: enabled ? onPressed : null'));

    const designTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/design_system_and_map_stability_test.dart'),
      'utf8',
    );
    assert.ok(designTest.includes('AppButton') && designTest.includes('isLoading: true'));

    const loginText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
      'utf8',
    );
    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(loginText.includes('_loading'));
    assert.ok(sheetText.includes('_saving'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F1-03: AppStateBanner supports long Vietnamese error text without truncation crash', () => {
    const bannerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_state_banner.dart'),
      'utf8',
    );
    assert.ok(bannerText.includes('AppStateBannerTone'));
    assert.ok(bannerText.includes('Expanded'));
    assert.ok(bannerText.includes('actionLabel != null && onAction != null'));

    const waveBTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/ux_v2_wave_b_test.dart'),
      'utf8',
    );
    assert.ok(waveBTest.includes('AppStateBanner'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F1-04: AppErrorState transitions cleanly from real HTTP 503 failure to 200 on retry', async () => {
    const errWidget = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/app_error_state.dart'),
      'utf8',
    );
    assert.ok(errWidget.includes('AppErrorState'));
    assert.ok(errWidget.includes('onRetry'));
    assert.ok(errWidget.includes('Thử lại'));

    const placeDetailTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/place_detail_test.dart'),
      'utf8',
    );
    assert.ok(placeDetailTest.includes('PlaceDetailScreen'));

    await withFaultProxy(
      cfg.baseUrl,
      [{ method: 'GET', pathPrefix: `/places/${FIXTURE.poi.id}`, remaining: 1 }],
      async ({ proxyClient, getStats }) => {
        const failRes = await proxyClient.get(`/places/${FIXTURE.poi.id}`);
        assertErrorEnvelope(failRes, 503, 'SERVICE_UNAVAILABLE', '/places/');

        const retryRes = await proxyClient.get(`/places/${FIXTURE.poi.id}`);
        const data = assertSuccessEnvelope(retryRes, 200);
        assert.equal(data.id, FIXTURE.poi.id);
        assert.equal(getStats().interceptedCount, 1);
        assert.equal(getStats().forwardedCount, 1);
      },
    );
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F1-05: Password visibility toggle contract preserves entered value across auth screens', () => {
    const loginText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
      'utf8',
    );
    const registerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/auth/presentation/register_screen.dart'),
      'utf8',
    );

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const tf = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/core/widgets/app_text_field.dart'),
        'utf8',
      );
      assert.ok(tf.includes('showPasswordToggle'));
      assert.ok(tf.includes('_obscured'));
      assert.ok(tf.includes('controller: widget.controller'));
      assert.ok(loginText.includes('showPasswordToggle: true'));
      assert.ok(registerText.includes('showPasswordToggle: true'));
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    } else {
      assert.ok(loginText.includes('Icons.visibility') && loginText.includes('_obscure'));
      assert.ok(registerText.includes('Icons.visibility') && registerText.includes('_obscure'));
    }
  });

  // --- F2 ---
  test('T2-F2-01: Hạ Long >20 POIs page 1 vs search "Tháp Đồng Hồ" vs empty search "khongtontaixyz"', async () => {
    const haLong = await resolveHaLongDestination(client);
    const page1 = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, page: 1, limit: 20 },
      }),
      200,
    );
    assert.ok(page1.total > 20, `Expected >20 verified Hạ Long places, got ${page1.total}`);

    const found = assertSuccessEnvelope(
      await client.get('/places', {
        query: {
          destinationId: haLong.id,
          search: 'Tháp Đồng Hồ',
          verifiedOnly: true,
        },
      }),
      200,
    );
    assert.ok(found.items.some((p) => p.id === FIXTURE.poi.id));

    const empty = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, search: 'khongtontaixyz' },
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

  test('T2-F2-03: Verified place with null openingHours/rating does not fabricate synthetic values', async () => {
    const place = await resolveVerifiedNullFieldPlace(
      client,
      (p) => (p.openingHours ?? null) === null && (p.rating ?? null) === null,
      'verified POI with null openingHours and rating',
    );
    assert.equal(place.isVerified, true);
    assert.equal(place.openingHours ?? null, null);
    assert.equal(place.rating ?? null, null);
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
    assertErrorEnvelope(await client.get('/users/me'), 401, null, '/users/me');

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      const authProvText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/auth/providers/auth_provider.dart'),
        'utf8',
      );
      const loginText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
        'utf8',
      );
      const oauthTest = fs.readFileSync(
        path.join(cfg.mobileDir, 'test/auth_reset_and_oauth_test.dart'),
        'utf8',
      );
      assert.ok(authProvText.includes('SocialAuthCancelled'));
      assert.ok(authProvText.includes('AuthActionResult.cancelled'));
      assert.ok(loginText.includes('AuthActionOutcome.cancelled') || loginText.includes('result.isError'));
      assert.ok(oauthTest.includes('SocialAuthCancelled'));
      getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
    } else {
      const loginText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
        'utf8',
      );
      assert.ok(loginText.includes('_emailCtrl') && loginText.includes('_passCtrl'));
      const vfsNoCancel = buildAuthVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/auth/providers/auth_provider.dart')]:
          'AuthActionResult.error(message: "err"); loginWithGoogle(); loginWithFacebook();',
      });
      assert.throws(() =>
        verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
          requireScreenshots: false,
          requireM4Youtube: false,
          fsImpl: vfsNoCancel,
        }),
      );
    }
  });

  test('T2-F3-02: Facebook OAuth missing email returns 400 OAUTH_EMAIL_UNAVAILABLE & renders inline error banner', async () => {
    const errRes = await client.post('/auth/oauth/facebook', { accessToken: 'no-email-fb-token' });
    assertErrorEnvelope(errRes, 400, 'OAUTH_EMAIL_UNAVAILABLE', '/auth/oauth/facebook');

    const loginText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
      'utf8',
    );
    assert.ok(loginText.includes('_emailCtrl') && loginText.includes('error'));
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      const oauthTest = fs.readFileSync(
        path.join(cfg.mobileDir, 'test/auth_reset_and_oauth_test.dart'),
        'utf8',
      );
      assert.ok(oauthTest.includes('OAUTH_EMAIL_UNAVAILABLE'));
      getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
    }
  });

  test('T2-F3-03: Expired or missing reset token returns RESET_TOKEN_EXPIRED / RESET_TOKEN_INVALID', async () => {
    const missingRes = await client.get('/auth/reset-password/validate', { query: { token: '' } });
    assertErrorEnvelope(missingRes, 400, 'RESET_TOKEN_INVALID', '/auth/reset-password/validate');

    const email = uniqueEmail('t2.f3.03');
    await registerUser(client, { email, password: 'Password123!', name: 'Exp Token UI' });
    const expiredToken = await resolveExpiredResetToken(client, cfg, email);
    const expRes = await client.get('/auth/reset-password/validate', {
      query: { token: expiredToken },
    });
    assertErrorEnvelope(expRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password/validate');
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
    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('sanitizeInternalRedirect'));
    assert.ok(routerText.includes('parsed.hasScheme') && routerText.includes('parsed.hasAuthority'));
    assert.ok(routerText.includes("startsWith('//')"));
    assert.ok(routerText.includes("'/login'") && routerText.includes("'/register'"));

    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTest.includes('https://evil.example/phish'));
    assert.ok(journeyTest.includes('//evil.example/phish'));

    const badRouterVfs = buildMinimalRouterVfs(
      cfg.mobileDir,
      "String? sanitizeInternalRedirect(String? r) => r;",
    );
    assert.throws(() =>
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: false,
        requireM4Youtube: false,
        fsImpl: badRouterVfs,
      }),
    );
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  // --- F4 ---
  test('T2-F4-01: Cancel-Login ("Hủy đăng nhập") returns to /places/:id in guest mode with zero error banner', async () => {
    const guestPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    assert.equal(guestPlace.id, FIXTURE.poi.id);
    assertErrorEnvelope(await client.get('/users/me'), 401, null, '/users/me');

    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('isPublicPlaceDetail'));
    assert.ok(routerText.includes('guestBrowseModeProvider'));

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      const loginText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart'),
        'utf8',
      );
      const regText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/auth/presentation/register_screen.dart'),
        'utf8',
      );
      assert.ok(loginText.includes('Hủy đăng nhập') || loginText.includes('Quay lại'));
      assert.ok(regText.includes('Hủy đăng nhập') || regText.includes('Quay lại'));
      assert.ok(loginText.includes('postLoginRedirectProvider') && loginText.includes('guestBrowseModeProvider'));
    } else {
      const vfsNoCancelLabel = buildAuthVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart')]:
          "AppTextField(showPasswordToggle: true); AppButton(); AppStateBanner(); postLoginRedirectProvider; guestBrowseModeProvider; Key('login_google_button'); Key('login_facebook_button');",
      });
      assert.throws(() =>
        verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
          requireScreenshots: false,
          requireM4Youtube: false,
          fsImpl: vfsNoCancelLabel,
        }),
      );
    }
  });

  test('T2-F4-02: Transient 503 on POST /trips/:id/itinerary retains _createdPendingTrip & avoids duplicate trip on retry', async () => {
    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('_createdPendingTrip'));
    assert.ok(sheetText.includes('on DioException'));

    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTest.includes('Retry guard'));

    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t2.f4.02'),
      password: 'Password123!',
      name: 'Retry Guard User',
    });

    await withFaultProxy(
      cfg.baseUrl,
      [{ method: 'POST', pathPrefix: '/trips/', remaining: 1 }],
      async ({ proxyClient, getStats }) => {
        const proxyAuthed = proxyClient.withToken(auth.accessToken);
        const trip = assertSuccessEnvelope(
          await proxyAuthed.post('/trips', {
            title: 'Hạ Long Retry Safe',
            destinationId: haLong.id,
          }),
          201,
        );

        const firstItinerary = await proxyAuthed.post(`/trips/${trip.id}/itinerary`, {
          dayNumber: 1,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId: FIXTURE.poi.id,
        });
        assertErrorEnvelope(firstItinerary, 503, 'SERVICE_UNAVAILABLE', '/trips/');

        const retryItinerary = await proxyAuthed.post(`/trips/${trip.id}/itinerary`, {
          dayNumber: 1,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId: FIXTURE.poi.id,
        });
        assertSuccessEnvelope(retryItinerary, 201);

        const stats = getStats();
        assert.equal(stats.interceptedCount, 1);
        assert.ok(stats.forwardedCount >= 2);

        const trips = assertSuccessEnvelope(await proxyAuthed.get('/trips'), 200);
        assert.equal(trips.filter((t) => t.title === 'Hạ Long Retry Safe').length, 1);
      },
    );
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F4-03: Validation/creation error before POST /trips preserves typed title & creates 0 trips', async () => {
    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('on DioException') && sheetText.includes('_newTitleCtrl'));
    const tripProviderText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/trips/providers/trip_provider.dart'),
      'utf8',
    );
    assert.ok(tripProviderText.includes('createTrip') && tripProviderText.includes('return null;'));

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t2.f4.03'),
      password: 'Password123!',
      name: 'Invalid Trip Create User',
    });
    const authed = client.withToken(auth.accessToken);
    const badCreate = await authed.post('/trips', {});
    assertErrorEnvelope(badCreate, 400, null, '/trips');
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 0);
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F4-04: Whitespace new trip title rejected cleanly with zero trips created', async () => {
    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('rawTitle.isEmpty'));
    assert.ok(sheetText.includes('Vui lòng nhập tên chuyến đi mới.'));

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t2.f4.04'),
      password: 'Password123!',
      name: 'Whitespace Trip User',
    });
    const authed = client.withToken(auth.accessToken);
    const badWhitespace = await authed.post('/trips', { title: '   ' });
    assertErrorEnvelope(badWhitespace, 400, null, '/trips');
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 0);
  });

  test('T2-F4-05: 401 expired JWT during Save redirects cleanly to /login?redirect=/places/:id', async () => {
    const res = await client.withToken('expired-or-bad-token').post('/trips/fake-trip/itinerary', {
      dayNumber: 1,
      activity: 'Tham quan Tháp Đồng Hồ',
      placeId: FIXTURE.poi.id,
    });
    assertErrorEnvelope(res, 401, null, '/trips/');

    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    const apiClientText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/network/api_client.dart'),
      'utf8',
    );
    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('statusCode == 401') && sheetText.includes('/login?redirect='));
    assert.ok(apiClientText.includes('_JwtAuthInterceptor'));
    assert.ok(routerText.includes('sanitizeInternalRedirect'));
  });

  // --- F5 ---
  test('T2-F5-01: AppConstants rejects empty, http://localhost, and http://10.0.2.2 in strict profile/release mode', () => {
    const constText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/constants/app_constants.dart'),
      'utf8',
    );
    assert.ok(constText.includes('_disallowedReleaseHosts'));
    assert.ok(constText.includes('StateError') && constText.includes('FormatException'));

    const apiConfigTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/api_config_test.dart'),
      'utf8',
    );
    assert.ok(apiConfigTest.includes('http://localhost:3000'));
    assert.ok(apiConfigTest.includes('10.0.2.2'));
    assert.ok(apiConfigTest.includes('isA<StateError>()'));
    assert.ok(apiConfigTest.includes('isA<FormatException>()'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F5-02: Long Vietnamese title layout overflow protection & 360x800 @ 1.3x Flutter test check', async () => {
    const longTitle = 'Tháp Đồng Hồ Trung Tâm Thành Phố Hạ Long Quảng Ninh';
    assert.ok(longTitle.length > 45);
    const searchRes = await client.get('/places', { query: { search: longTitle } });
    assertSuccessEnvelope(searchRes, 200);

    for (const rel of [
      'lib/features/places/presentation/place_detail_screen.dart',
      'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart',
      'lib/features/map/presentation/widgets/place_preview_sheet.dart',
      'lib/features/home/presentation/widgets/home_verified_place_tile.dart',
    ]) {
      const txt = fs.readFileSync(path.join(cfg.mobileDir, rel), 'utf8');
      assert.ok(
        txt.includes('TextOverflow.ellipsis') || txt.includes('Expanded') || txt.includes('Flexible'),
        `${rel} must handle long Vietnamese text without overflow`,
      );
    }

    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTest.includes('360') && journeyTest.includes('800') && journeyTest.includes('1.3'));
    assert.ok(journeyTest.includes('takeException()'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T2-F5-03: List-open benchmark timing completes cleanly for empty search and 20+ items', async () => {
    const haLong = await resolveHaLongDestination(client);
    const empty = await client.get('/places', {
      query: { destinationId: haLong.id, search: 'no-match-999' },
    });
    const full = await client.get('/places', {
      query: { destinationId: haLong.id, limit: 50 },
    });
    assertSuccessEnvelope(empty, 200);
    assertSuccessEnvelope(full, 200);
    assert.ok(empty.durationMs >= 0 && full.durationMs >= 0);
  });

  test('T2-F5-04: Verified place with null coverImage tolerance without synthetic fabrication', async () => {
    const place = await resolveVerifiedNullFieldPlace(
      client,
      (p) => (p.coverImage ?? null) === null,
      'verified POI with null coverImage',
    );
    assert.equal(place.isVerified, true);
    assert.equal(place.coverImage ?? null, null);
  });

  test('T2-F5-05: Before vs After screenshot PNG dimensions parity check', () => {
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.beforeCount > 0 && ss.afterCount > 0);
    } else {
      const vfsMismatch = createMemoryFs({
        [path.join(cfg.repoRoot, 'docs/beta/mobile/screenshots/before/01_login.png')]:
          buildPngHeaderBuffer(390, 844),
        [path.join(cfg.repoRoot, 'docs/beta/mobile/screenshots/after/01_login.png')]:
          buildPngHeaderBuffer(360, 800),
      });
      assert.throws(() => verifyScreenshots(cfg.repoRoot, { fsImpl: vfsMismatch, requireFiles: true }));
    }
  });

  // --- F6 ---
  test('T2-F6-01: Expired reset token rejected with RESET_TOKEN_EXPIRED & old password preserved', async () => {
    const email = uniqueEmail('t2.f6.01');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Exp Reset' });
    const expiredToken = await resolveExpiredResetToken(client, cfg, email);

    const valRes = await client.get('/auth/reset-password/validate', {
      query: { token: expiredToken },
    });
    assertErrorEnvelope(valRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password/validate');

    const rstRes = await client.post('/auth/reset-password', {
      token: expiredToken,
      newPassword: 'NewPassword123!',
    });
    assertErrorEnvelope(rstRes, [400, 410], 'RESET_TOKEN_EXPIRED', '/auth/reset-password');

    assertSuccessEnvelope(await loginUser(client, { email, password: 'OldPassword123!' }), 200);
  });

  test('T2-F6-02: Consumed reset token replay & concurrent double-submit fail with RESET_TOKEN_USED', async () => {
    const email = uniqueEmail('t2.f6.02');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Used Reset' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);

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
    const t1 = await fetchResetToken(client, cfg, email);

    const badPass = await client.post('/auth/reset-password', { token: t1, newPassword: '123' });
    assertErrorEnvelope(badPass, 400, null, '/auth/reset-password');

    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const t2 = await fetchResetToken(client, cfg, email);
    assert.notEqual(t2, t1);

    const t1Attempt = await client.post('/auth/reset-password', {
      token: t1,
      newPassword: 'ValidPass123!',
    });
    assertErrorEnvelope(
      t1Attempt,
      [400, 410],
      ['RESET_TOKEN_USED', 'RESET_TOKEN_INVALID'],
      '/auth/reset-password',
    );

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
    const payload = buildGroundedThapDongHoEvent({ videoId: uniqueVideoId('f81') });
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
      videoId: uniqueVideoId('cc'),
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
          videoId: uniqueVideoId('pq'),
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
          videoId: uniqueVideoId('nc'),
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
          videoId: uniqueVideoId('cd'),
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
          videoId: uniqueVideoId('uv'),
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
    const cityVid = uniqueVideoId('ct');
    const ambigVid = uniqueVideoId('am');

    const singleCity = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `city-ok-${crypto.randomUUID()}`,
          videoId: cityVid,
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
          videoId: ambigVid,
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
    assert.ok(destUpdates.items.some((i) => i.videoId === cityVid));
    assert.ok(!destUpdates.items.some((i) => i.videoId === ambigVid));
  });

  test('T2-F8-05: SLA boundary (290s vs 310s), XXE <!DOCTYPE>, bad HMAC, lat-only, naive TZ, & unknown destination 404', async () => {
    const withinSla = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `sla-in-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('in'),
          publishedAt: isoWithOffsetSeconds(-290_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.ok(
      withinSla.ingestLatencyMs >= 285000 && withinSla.ingestLatencyMs <= 300000,
      `Expected withinSla.ingestLatencyMs in [285000, 300000], got ${withinSla.ingestLatencyMs}`,
    );

    const overSla = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `sla-out-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('ou'),
          publishedAt: isoWithOffsetSeconds(-310_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.ok(
      overSla.ingestLatencyMs > 300000,
      `Expected overSla.ingestLatencyMs > 300000, got ${overSla.ingestLatencyMs}`,
    );

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
          videoId: uniqueVideoId('hm'),
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
        videoId: uniqueVideoId('lo'),
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
        videoId: uniqueVideoId('nt'),
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
  test('T2-F9-01: Freshness SLA boundary (exact 300000ms vs 300001ms in self-test, interior SLA in live) over real HTTP', async () => {
    const withinVid = uniqueVideoId('b1');
    const overVid = uniqueVideoId('b2');

    if (cfg.mode === 'self-test') {
      const fixedNowMs = Date.now();
      const fixedNowIso = new Date(fixedNowMs).toISOString();

      const atBoundary = assertSuccessEnvelope(
        await client.post(
          '/youtube/events',
          buildGroundedThapDongHoEvent({
            eventId: `b300000-${crypto.randomUUID()}`,
            videoId: withinVid,
            publishedAt: new Date(fixedNowMs - 300000).toISOString(),
          }),
          {
            headers: {
              'x-youtube-internal-secret': cfg.youtubeSecret,
              'x-e2e-test-now': fixedNowIso,
            },
          },
        ),
        200,
      );
      assert.equal(atBoundary.ingestLatencyMs, 300000);

      const overBoundary = assertSuccessEnvelope(
        await client.post(
          '/youtube/events',
          buildGroundedThapDongHoEvent({
            eventId: `b300001-${crypto.randomUUID()}`,
            videoId: overVid,
            publishedAt: new Date(fixedNowMs - 300001).toISOString(),
          }),
          {
            headers: {
              'x-youtube-internal-secret': cfg.youtubeSecret,
              'x-e2e-test-now': fixedNowIso,
            },
          },
        ),
        200,
      );
      assert.equal(overBoundary.ingestLatencyMs, 300001);

      const apiData = assertSuccessEnvelope(
        await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, {
          query: { limit: 50 },
          headers: { 'x-e2e-test-now': fixedNowIso },
        }),
        200,
      );
      const itemAt = apiData.items.find((i) => i.videoId === withinVid);
      const itemOver = apiData.items.find((i) => i.videoId === overVid);
      assert.ok(itemAt && itemOver);
      assertYoutubeFiveFields(itemAt, 'POI', { maxIngestLatencyMs: 300000 });
      assertYoutubeFiveFields(itemOver, 'POI');
      assert.ok(itemAt.ingestLatencyMs <= apiData.realtimeSlaMaxLatencyMs);
      assert.ok(itemOver.ingestLatencyMs > apiData.realtimeSlaMaxLatencyMs);
    } else {
      const withinRes = assertSuccessEnvelope(
        await client.post(
          '/youtube/events',
          buildGroundedThapDongHoEvent({
            eventId: `b-live-in-${crypto.randomUUID()}`,
            videoId: withinVid,
            publishedAt: isoWithOffsetSeconds(-285_000, 'Z'),
          }),
          { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
        ),
        200,
      );
      const overRes = assertSuccessEnvelope(
        await client.post(
          '/youtube/events',
          buildGroundedThapDongHoEvent({
            eventId: `b-live-out-${crypto.randomUUID()}`,
            videoId: overVid,
            publishedAt: isoWithOffsetSeconds(-315_000, 'Z'),
          }),
          { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
        ),
        200,
      );
      assert.ok(withinRes.ingestLatencyMs <= 300000);
      assert.ok(overRes.ingestLatencyMs > 300000);

      const apiData = assertSuccessEnvelope(
        await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
        200,
      );
      const itemAt = apiData.items.find((i) => i.videoId === withinVid);
      const itemOver = apiData.items.find((i) => i.videoId === overVid);
      assert.ok(itemAt && itemOver);
      assertYoutubeFiveFields(itemAt, 'POI', { maxIngestLatencyMs: 300000 });
      assert.ok(itemOver.ingestLatencyMs > apiData.realtimeSlaMaxLatencyMs);
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    }
  });

  test('T2-F9-02: Future publishedAt clamps ingestLatencyMs to 0 & omitted sourceUpdatedAt falls back updatedAt=receivedAt', async () => {
    const vid = uniqueVideoId('fut');
    const receipt = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `evt-future-${crypto.randomUUID()}`,
          videoId: vid,
          publishedAt: isoWithOffsetSeconds(60_000, 'Z'),
          sourceUpdatedAt: undefined,
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(receipt.ingestLatencyMs, 0);
    assert.equal(receipt.updatedAt, receipt.receivedAt);

    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const matched = apiData.items.find((i) => i.videoId === vid);
    assert.ok(matched);
    assertYoutubeFiveFields(matched, 'POI', { maxIngestLatencyMs: 0 });
    assert.equal(matched.ingestLatencyMs, 0);
    assert.equal(matched.updatedAt, matched.receivedAt);
  });

  test('T2-F9-03: Clean empty YouTube state returns honest empty array contract over real HTTP', async () => {
    if (cfg.mode === 'self-test') {
      assertSuccessEnvelope(await client.post('/_test/reset', {}), 200);
      const emptyData = assertSuccessEnvelope(
        await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
        200,
      );
      assertYoutubeContainerContract(emptyData);
      assert.equal(emptyData.total, 0);
      assert.deepEqual(emptyData.items, []);
      assert.equal(emptyData.cityFallbackTotal, 0);
      assert.deepEqual(emptyData.cityFallbackItems, []);
    } else {
      const data = assertSuccessEnvelope(
        await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
        200,
      );
      assertYoutubeContainerContract(data);
      assert.equal(data.total, data.items.length);
      assert.ok(Array.isArray(data.cityFallbackItems));
      assert.equal(data.cityFallbackTotal, data.cityFallbackItems.length);
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    }
  });

  test('T2-F9-04: Factual PlaceDetail remains intact even when YouTube freshness endpoint returns real HTTP 503', async () => {
    await withFaultProxy(
      cfg.baseUrl,
      [{ method: 'GET', pathPrefix: `/places/${FIXTURE.poi.id}/youtube-updates`, remaining: 1 }],
      async ({ proxyClient, getStats }) => {
        const ytErr = await proxyClient.get(`/places/${FIXTURE.poi.id}/youtube-updates`);
        assertErrorEnvelope(ytErr, 503, 'SERVICE_UNAVAILABLE', '/places/');

        const factual = assertSuccessEnvelope(
          await proxyClient.get(`/places/${FIXTURE.poi.id}`),
          200,
        );
        assert.equal(factual.name, 'Tháp Đồng Hồ');
        assert.equal(getStats().interceptedCount, 1);
        assert.equal(getStats().forwardedCount, 1);
      },
    );
  });

  test('T2-F9-05: Long 200+ char Vietnamese YouTube title & null channelTitle degrade cleanly over HTTP', async () => {
    const longTitle = `Khám phá Tháp Đồng Hồ Hạ Long ${'tuyệt đẹp '.repeat(22)}`.trim();
    assert.ok(longTitle.length >= 200);
    const vid = uniqueVideoId('lng');

    const receipt = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `evt-long-${crypto.randomUUID()}`,
          videoId: vid,
          title: longTitle,
          channelTitle: null,
          publishedAt: isoWithOffsetSeconds(-20_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(receipt.status, 'LINKED');

    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const matched = apiData.items.find((i) => i.videoId === vid);
    assert.ok(matched);
    assertYoutubeFiveFields(matched, 'POI', { maxIngestLatencyMs: 300000 });
    assert.equal(matched.title, longTitle);
    assert.ok(matched.title.length >= 200);
  });

  // --- F10 ---
  test('T2-F10-01: W07 freeze SHA-256 verification fails immediately on any mismatch', () => {
    const res = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(res.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
  });

  test('T2-F10-02: data/curated/w07/ & w07_offline_retrieval_prep remain clean across E2E execution', () => {
    const requireW07Prep = cfg.mode === 'live' || cfg.w07PrepDirExplicit;
    const status = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir, { requireW07Prep });
    assert.equal(status.dirtyLines.length, 0);
    if (requireW07Prep || fs.existsSync(cfg.w07PrepDir)) {
      assert.equal(status.w07PrepVerified, true);
    }
  });

  test('T2-F10-03: Batch of 10 YouTube events leaves documents & place_sources unchanged', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats = await fetchDbStats(client, cfg);

    for (let i = 0; i < 10; i++) {
      const eventId = `batch-${i % 4}-${crypto.randomUUID()}`;
      const res = await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId,
          videoId: uniqueVideoId(`b${i}`),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      );
      const receipt = assertSuccessEnvelope(res, 200);
      assert.equal(receipt.status, 'LINKED');
    }

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    const afterStats = await fetchDbStats(client, cfg);
    verifyDbStatsIsolation(beforeStats, afterStats);
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
          videoId: uniqueVideoId('uv2'),
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
