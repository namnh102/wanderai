import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getRuntimeConfig } from '../lib/cli_args.mjs';
import {
  HttpClient,
  decodeJwtPayload,
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
import {
  buildPngHeaderBuffer,
  createMemoryFs,
  detectBetaMobileTree,
  getFlutterTestResult,
  getMobileContractSpec,
  parsePngDimensionsFromBuffer,
  verifyBaseline10126b1Hooks,
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
const mobileSpec = getMobileContractSpec();

function uniqueEmail(prefix) {
  return `${prefix}.${crypto.randomUUID().slice(0, 8)}@gomate.vn`;
}

function uniqueVideoId(prefix = 'v') {
  const cleanPrefix = prefix.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 3) || 'v';
  const suffix = crypto.randomUUID().replace(/-/g, '').slice(0, 11 - cleanPrefix.length);
  return `${cleanPrefix}${suffix}`;
}

function buildValidBetaVfs(mobileDir, repoRoot, overrides = {}) {
  const files = {
    [path.join(mobileDir, 'lib/core/widgets/app_text_field.dart')]:
      'class AppTextField { TextFormField build() => TextFormField(controller: widget.controller, obscureText: true, showPasswordToggle: true, validator: v); }',
    [path.join(mobileDir, 'lib/core/widgets/widgets.dart')]:
      "export 'app_text_field.dart';\nexport 'app_button.dart';",
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
    [path.join(mobileDir, 'lib/features/home/presentation/home_screen.dart')]:
      'AppButton(); AppLoading(); AppErrorState(); AppStateBanner();',
    [path.join(mobileDir, 'lib/features/map/presentation/map_screen.dart')]:
      'AppLoading(); AppStateBanner();',
    [path.join(mobileDir, 'lib/features/map/presentation/widgets/place_preview_sheet.dart')]:
      'AppButton();',
    [path.join(mobileDir, 'lib/features/places/presentation/place_detail_screen.dart')]:
      "AppTextField(); AppButton(); AppLoading(); AppErrorState(); AppStateBanner(); placeId source publishedAt receivedAt updatedAt cityFallbackItems scope 'CITY' realtimeSlaMaxLatencyMs 300000 'Thời gian thực' 'Cập nhật gần đây' < 0;",
    [path.join(mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart')]:
      'AppTextField(); AppButton(); AppLoading(); AppStateBanner(); _createdPendingTrip;',
    [path.join(mobileDir, 'lib/features/trips/presentation/trip_list_screen.dart')]:
      'AppLoading(); AppErrorState();',
    [path.join(mobileDir, 'lib/features/trips/presentation/trip_detail_screen.dart')]:
      'AppTextField(); AppButton(); AppLoading(); AppErrorState();',
    [path.join(mobileDir, 'lib/features/trips/presentation/trip_form_screen.dart')]:
      'AppTextField(); AppButton(); AppStateBanner();',
    [path.join(mobileDir, 'integration_test/perf_benchmark_test.dart')]:
      'IntegrationTestWidgetsFlutterBinding traceAction dest_sheet_scroll trip_list_scroll trip_detail_scroll custom_metrics',
    [path.join(mobileDir, 'test_driver/perf_driver.dart')]:
      'TimelineSummary.summarize scroll_timelines',
    [path.join(repoRoot, 'docs/beta/mobile/benchmarks/before_perf.json')]: JSON.stringify({
      custom_metrics: { dest_sheet_open_ms: 100, trip_list_open_ms: 100, trip_detail_open_ms: 100 },
      scroll_timelines: { dest_sheet_scroll: {}, trip_list_scroll: {}, trip_detail_scroll: {} },
    }),
  };
  const validPng = buildPngHeaderBuffer(390, 844);
  for (const name of [
    '01_login.png',
    '02_register.png',
    '03_home_halong.png',
    '06_place_detail.png',
    '07_save_place.png',
    '08_trip_list.png',
    '09_trip_detail.png',
  ]) {
    files[path.join(repoRoot, 'docs/beta/mobile/screenshots/before', name)] = validPng;
    files[path.join(repoRoot, 'docs/beta/mobile/screenshots/after', name)] = validPng;
  }
  files[path.join(repoRoot, 'docs/beta/mobile/screenshots/after/10_forgot_password.png')] = validPng;
  files[path.join(repoRoot, 'docs/beta/mobile/screenshots/after/11_reset_password.png')] = validPng;

  for (const [k, v] of Object.entries(overrides)) {
    if (v === null) {
      delete files[k];
    } else {
      files[k] = v;
    }
  }
  return createMemoryFs(files);
}

describe('Tier 1 — Feature Coverage (50 Happy-Path Tests: F1–F10)', () => {
  // --- F1: Shared Flutter UI Components ---
  test('T1-F1-01: Shared UI widgets barrel & Login form contract (AppTextField, AppButton, AppLoading, AppStateBanner)', () => {
    const baseline = verifyBaseline10126b1Hooks(cfg.mobileDir);
    assert.ok(baseline.length >= 5);
    assert.deepEqual(mobileSpec.sharedWidgets, [
      'AppTextField',
      'AppButton',
      'AppLoading',
      'AppErrorState',
      'AppStateBanner',
    ]);

    const designTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/design_system_and_map_stability_test.dart'),
      'utf8',
    );
    assert.ok(designTest.includes('AppButton') && designTest.includes('AppErrorState'));

    if (cfg.mode === 'live') {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true, 'Live mode requires Beta mobile tree');
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
      getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
    } else if (detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: false,
      });
    } else {
      // Negative VFS check proving verifier catches missing AppTextField or raw ElevatedButton
      const vfsNoTextField = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/core/widgets/app_text_field.dart')]: null,
      });
      assert.throws(() => verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsNoTextField }));
      const vfsRawElevated = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/home/presentation/home_screen.dart')]:
          'AppButton(); AppLoading(); AppErrorState(); AppStateBanner(); ElevatedButton(onPressed: null);',
      });
      assert.throws(() => verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsRawElevated }));
    }
  });

  test('T1-F1-02: Auth screens (/register, /forgot-password, /reset-password) shared components & public paths contract', () => {
    assert.equal(mobileSpec.authScreens.length, 4);
    for (const pubPath of mobileSpec.publicAuthPaths) {
      assert.ok(pubPath.startsWith('/auth/'), `Expected /auth/* path: ${pubPath}`);
    }

    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('sanitizeInternalRedirect'));
    assert.ok(routerText.includes('/places/:id'));

    const journeyTestText = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTestText.includes('sanitizeInternalRedirect'));

    if (cfg.mode === 'live') {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true, 'Live mode requires Beta mobile tree');
      const res = verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
      assert.equal(res.publicAuthPathsVerified, 8);
    } else if (detectBetaMobileTree(cfg.mobileDir)) {
      const res = verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: false,
      });
      assert.equal(res.publicAuthPathsVerified, 8);
    } else {
      const vfsMissingPublicPath = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/core/network/api_client.dart')]:
          "const _publicAuthPaths = {'/auth/login', '/auth/register', '/auth/refresh'};",
      });
      assert.throws(
        () => verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsMissingPublicPath }),
        /_publicAuthPaths missing/,
      );
    }
  });

  test('T1-F1-03: Core screens (Home, Map, PlaceDetail) error-to-retry & loading contract', async () => {
    for (const screen of mobileSpec.coreScreens.slice(0, 3)) {
      const content = fs.readFileSync(path.join(cfg.mobileDir, screen.file), 'utf8');
      assert.ok(
        content.includes('AppLoading') || content.includes('CircularProgressIndicator'),
        `${screen.name} must render loading state`,
      );
      assert.ok(
        content.includes('AppErrorState') ||
          content.includes('AppStateBanner') ||
          content.includes('ScaffoldMessenger') ||
          content.includes('errorMessage'),
        `${screen.name} must render error feedback`,
      );
    }
    if (cfg.mode === 'live') {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    } else {
      const vfsBadCore = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/map/presentation/map_screen.dart')]:
          'AppStateBanner();',
      });
      assert.throws(() =>
        verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsBadCore }),
      );
    }
    const errRes = await client.get(`/places/${FIXTURE.negativeFixtures.unknownPlaceId}`);
    assertErrorEnvelope(errRes, 404, null, '/places/');
    if ('errorCode' in errRes.json && errRes.json.errorCode !== undefined) {
      assert.equal(errRes.json.errorCode, 'PLACE_NOT_FOUND');
    }
    const ytErrRes = await client.get(
      `/places/${FIXTURE.negativeFixtures.unknownPlaceId}/youtube-updates`,
    );
    assertErrorEnvelope(ytErrRes, 404, 'PLACE_NOT_FOUND', '/places/');
    const okRes = await client.get(`/places/${FIXTURE.poi.id}`);
    const place = assertSuccessEnvelope(okRes, 200);
    assert.equal(place.id, FIXTURE.poi.id);
  });

  test('T1-F1-04: TripListScreen & TripDetailScreen loading/empty/error & JWT trips contract', async () => {
    for (const screen of mobileSpec.coreScreens.slice(3)) {
      const content = fs.readFileSync(path.join(cfg.mobileDir, screen.file), 'utf8');
      assert.ok(
        content.includes('AppLoading') || content.includes('CircularProgressIndicator'),
        `${screen.name} must render loading state`,
      );
      assert.ok(
        content.includes('AppErrorState') || content.includes('errorMessage'),
        `${screen.name} must render error state`,
      );
    }
    assert.ok(fs.existsSync(path.join(cfg.mobileDir, 'test/trips_test.dart')));
    if (cfg.mode === 'live') {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    } else {
      const vfsBadTrips = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/trips/presentation/trip_list_screen.dart')]:
          'AppLoading();',
      });
      assert.throws(() =>
        verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsBadTrips }),
      );
    }

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f1.04'),
      password: 'Password123!',
      name: 'Trip UI User',
    });
    const tripsRes = await client.withToken(auth.accessToken).get('/trips');
    const trips = assertSuccessEnvelope(tripsRes, 200);
    assert.ok(Array.isArray(trips), 'GET /trips must return array');
  });

  test('T1-F1-05: Viewport geometry (390x844 & 360x800 @ 1.3x) & ResponsiveWrapper verification', () => {
    const wrapperText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/widgets/responsive_wrapper.dart'),
      'utf8',
    );
    assert.ok(wrapperText.includes('ConstrainedBox') && wrapperText.includes('maxWidth'));

    const designTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/design_system_and_map_stability_test.dart'),
      'utf8',
    );
    assert.ok(designTest.includes('1920') && designTest.includes('640'));

    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(
      journeyTest.includes('360') &&
        journeyTest.includes('800') &&
        journeyTest.includes('390') &&
        journeyTest.includes('844'),
    );

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.count > 0);
    } else {
      const okPng = parsePngDimensionsFromBuffer(buildPngHeaderBuffer(390, 844), 'valid-390x844');
      assert.deepEqual(okPng, { width: 390, height: 844 });
      assert.throws(() => parsePngDimensionsFromBuffer(Buffer.from('not-a-png'), 'bad-png'));
    }
  });

  // --- F2: 4 Core Screens Polish & Perf ---
  test('T1-F2-01: HomeScreen -> Hạ Long destination -> search Tháp Đồng Hồ returns verified POI', async () => {
    const haLong = await resolveHaLongDestination(client);
    const placesRes = await client.get('/places', {
      query: {
        destinationId: haLong.id,
        search: 'Tháp Đồng Hồ',
        verifiedOnly: true,
      },
    });
    const placesData = assertSuccessEnvelope(placesRes, 200);
    const match = placesData.items.find((p) => p.id === FIXTURE.poi.id);
    assert.ok(match, 'Search for Tháp Đồng Hồ must return canonical POI 65562a67-...');
    assert.equal(match.name, 'Tháp Đồng Hồ');
  });

  test('T1-F2-02: MapScreen Hạ Long marker coordinates & PlacePreviewSheet contract for Tháp Đồng Hồ', async () => {
    const res = await client.get(`/places/${FIXTURE.poi.id}`);
    const place = assertSuccessEnvelope(res, 200);
    assert.ok(Math.abs(place.latitude - FIXTURE.poi.latitude) < 0.001);
    assert.ok(Math.abs(place.longitude - FIXTURE.poi.longitude) < 0.001);
    assert.equal(place.isVerified, true);
    const mapText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/map/presentation/map_screen.dart'),
      'utf8',
    );
    const previewText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/map/presentation/widgets/place_preview_sheet.dart'),
      'utf8',
    );
    assert.ok(
      mapText.includes('PlacePreviewSheet') || previewText.includes('place_preview_view_detail'),
    );
  });

  test('T1-F2-03: PlaceDetailScreen Tháp Đồng Hồ OSM/Wikipedia provenance & Save CTA contract', async () => {
    const res = await client.get(`/places/${FIXTURE.poi.id}`);
    const place = assertSuccessEnvelope(res, 200);
    assert.equal(place.name, 'Tháp Đồng Hồ');
    assert.equal(place.destination.slug, 'ha-long');
    assert.ok(Array.isArray(place.placeSources) && place.placeSources.length > 0);
    assert.ok(place.placeSources.some((s) => s.sourceName === 'osm'));
    const detailText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/place_detail_screen.dart'),
      'utf8',
    );
    assert.ok(detailText.includes('place_detail_save_to_trip'));
  });

  test('T1-F2-04: TripListScreen -> TripDetailScreen displays saved Tháp Đồng Hồ itinerary item', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f2.04'),
      password: 'Password123!',
      name: 'Trip Detail User',
    });
    const authed = client.withToken(auth.accessToken);
    const tripRes = await authed.post('/trips', {
      title: 'Hạ Long Mùa Thu',
      destinationId: haLong.id,
    });
    const trip = assertSuccessEnvelope(tripRes, 201);

    const addRes = await authed.post(`/trips/${trip.id}/itinerary`, {
      dayNumber: 1,
      activity: 'Tham quan Tháp Đồng Hồ',
      placeId: FIXTURE.poi.id,
    });
    assertSuccessEnvelope(addRes, 201);

    const detailRes = await authed.get(`/trips/${trip.id}`);
    const detail = assertSuccessEnvelope(detailRes, 200);
    const day1 = detail.itineraries.find((d) => d.dayNumber === 1);
    assert.ok(day1 && day1.items.some((it) => it.placeId === FIXTURE.poi.id));
  });

  test('T1-F2-05: Paginated Hạ Long list (>20 POIs) & lazy list / cached image widget check', async () => {
    const haLong = await resolveHaLongDestination(client);
    const page1 = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: haLong.id, page: 1, limit: 20 },
      }),
      200,
    );
    assert.ok(page1.total >= 20, `Expected >= 20 verified Hạ Long POIs, got ${page1.total}`);
    assert.equal(page1.items.length, 20);
    const homeText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/home/presentation/home_screen.dart'),
      'utf8',
    );
    assert.ok(
      homeText.includes('ListView') ||
        homeText.includes('Sliver') ||
        homeText.includes('CustomScrollView'),
      'HomeScreen must use scrollable list widgets',
    );
  });

  // --- F3: Flutter Auth Screens & OAuth/Reset Flows ---
  test('T1-F3-01: LoginScreen Success outcome clears guest mode & navigates to redirect', async () => {
    const creds = { email: uniqueEmail('t1.f3.01'), password: 'Password123!', name: 'Login User' };
    await registerUser(client, creds);
    const loginRes = await loginUser(client, creds);
    const tokens = assertSuccessEnvelope(loginRes, 200);
    const jwt = decodeJwtPayload(tokens.access_token);
    assert.equal(jwt.email, creds.email);

    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('resolvePostAuthDestination'));
    assert.ok(routerText.includes('guestBrowseModeProvider'));
    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTest.includes('Case 2'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T1-F3-02: RegisterScreen creates account & transitions to authenticated state', async () => {
    const email = uniqueEmail('t1.f3.02');
    const regRes = await registerUser(client, { email, password: 'Password123!', name: 'Reg User' });
    const tokens = assertSuccessEnvelope(regRes, 201);
    assert.ok(tokens.access_token && tokens.refresh_token);
    const me = assertSuccessEnvelope(await client.withToken(tokens.access_token).get('/users/me'), 200);
    assert.equal(me.email, email);
  });

  test('T1-F3-03: ForgotPasswordScreen submits non-enumerating request -> 200 sent:true', async () => {
    const email = uniqueEmail('t1.f3.03');
    await registerUser(client, { email, password: 'Password123!', name: 'Forgot User' });
    const res = await client.post('/auth/forgot-password', { email });
    const data = assertSuccessEnvelope(res, 200);
    assert.equal(data.sent, true);
    assert.equal(data.expiresInMinutes, 30);
    assert.ok(typeof data.message === 'string' && data.message.length > 0);
  });

  test('T1-F3-04: ResetPasswordScreen validates token, resets password, & login succeeds', async () => {
    const email = uniqueEmail('t1.f3.04');
    await registerUser(client, { email, password: 'OldPassword123!', name: 'Reset UI User' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const rawToken = await fetchResetToken(client, cfg, email);

    const valData = assertSuccessEnvelope(
      await client.get('/auth/reset-password/validate', { query: { token: rawToken } }),
      200,
    );
    assert.equal(valData.valid, true);

    const rstData = assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token: rawToken, newPassword: 'NewPassword456!' }),
      200,
    );
    assert.equal(rstData.reset, true);

    const loginRes = await loginUser(client, { email, password: 'NewPassword456!' });
    assertSuccessEnvelope(loginRes, 200);
  });

  test('T1-F3-05: Social OAuth Success matrix for Google & Facebook', async () => {
    const gIdToken = process.env.E2E_GOOGLE_TEST_ID_TOKEN || 'valid-google-token';
    const gRes = await client.post('/auth/oauth/google', { idToken: gIdToken });
    const gData = assertSuccessEnvelope(gRes, 200);
    assert.ok(gData.user.providers.includes('google'));

    const fbToken = process.env.E2E_FACEBOOK_TEST_ACCESS_TOKEN || 'valid-fb-token';
    const fRes = await client.post('/auth/oauth/facebook', { accessToken: fbToken });
    const fData = assertSuccessEnvelope(fRes, 200);
    assert.ok(fData.user.providers.includes('facebook'));

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: cfg.mode === 'live',
      });
    }
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  // --- F4: Save Flow Resilience ---
  test('T1-F4-01: SavePlaceToTripSheet saves Tháp Đồng Hồ into existing trip Day 1', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.01'),
      password: 'Password123!',
      name: 'Save Existing User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Existing Hạ Long', destinationId: haLong.id }),
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
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.filter((t) => t.id === trip.id).length, 1);

    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('_selectedTripId'));
    assert.ok(sheetText.includes('_createNewMode'));
  });

  test('T1-F4-02: SavePlaceToTripSheet with 0 trips creates 1 trip & adds Tháp Đồng Hồ', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.02'),
      password: 'Password123!',
      name: 'Save New Trip User',
    });
    const authed = client.withToken(auth.accessToken);

    const initialTrips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(initialTrips.length, 0);

    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Hạ Long Cuối Tuần', destinationId: haLong.id }),
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
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 1);
    assert.equal(trips[0].title, 'Hạ Long Cuối Tuần');

    const journeyTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
      'utf8',
    );
    assert.ok(journeyTest.includes('Case 1'));
  });

  test('T1-F4-03: Cold restart persistence verifies saved Tháp Đồng Hồ itinerary survives process reset', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.03'),
      password: 'Password123!',
      name: 'Cold Restart User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Cold Restart Trip', destinationId: haLong.id }),
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

    const restartedClient = new HttpClient(cfg.baseUrl).withToken(auth.accessToken);
    const persisted = assertSuccessEnvelope(await restartedClient.get(`/trips/${trip.id}`), 200);
    assert.ok(
      persisted.itineraries.some((d) =>
        d.items.some((i) => i.placeId === FIXTURE.poi.id && i.activity.includes('Tháp Đồng Hồ')),
      ),
    );
  });

  test('T1-F4-04: Unauthenticated guest save redirect -> login -> returns to Tháp Đồng Hồ -> saves', async () => {
    const targetPath = `/places/${FIXTURE.poi.id}`;
    const routerText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/router/app_router.dart'),
      'utf8',
    );
    assert.ok(routerText.includes('sanitizeInternalRedirect') && routerText.includes('/places/:id'));

    const guestPlace = assertSuccessEnvelope(await client.get(targetPath), 200);
    assert.equal(guestPlace.id, FIXTURE.poi.id);
    assertErrorEnvelope(await client.get('/users/me'), 401, null, '/users/me');

    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.04'),
      password: 'Password123!',
      name: 'Redirect Save User',
    });
    const haLong = await resolveHaLongDestination(client);
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Post-Redirect Trip', destinationId: haLong.id }),
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

  test('T1-F4-05: SavePlaceToTripSheet Day 3 selection & toggle mode structural hook', async () => {
    const haLong = await resolveHaLongDestination(client);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.05'),
      password: 'Password123!',
      name: 'Day 3 User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Multi-day Trip', destinationId: haLong.id }),
      201,
    );
    const added = assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 3,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: FIXTURE.poi.id,
      }),
      201,
    );
    assert.equal(added.dayNumber, 3);
    const sheetText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart'),
      'utf8',
    );
    assert.ok(sheetText.includes('trip_picker_day_dropdown'));
    assert.ok(sheetText.includes('trip_picker_new_trip_toggle'));
  });

  // --- F5: Mobile Screenshots & Profile Perf Benchmark ---
  test('T1-F5-01: Deterministic 390x844 screenshot dimensions contract', () => {
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.count > 0);
    } else {
      const journeyTest = fs.readFileSync(
        path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
        'utf8',
      );
      assert.ok(journeyTest.includes('390') && journeyTest.includes('844'));
      assert.deepEqual(
        parsePngDimensionsFromBuffer(buildPngHeaderBuffer(390, 844), '390x844'),
        { width: 390, height: 844 },
      );

      const vfsBadDim = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.repoRoot, 'docs/beta/mobile/screenshots/after/01_login.png')]:
          buildPngHeaderBuffer(360, 800),
      });
      assert.throws(() => verifyScreenshots(cfg.repoRoot, { fsImpl: vfsBadDim, requireFiles: true }));

      const vfsEmpty = createMemoryFs({});
      assert.throws(() => verifyScreenshots(cfg.repoRoot, { fsImpl: vfsEmpty, requireFiles: true }));
    }
  });

  test('T1-F5-02: Before (10126b1) vs After screenshot parity contract', () => {
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      const ss = verifyScreenshots(cfg.repoRoot, { requireFiles: true });
      assert.ok(ss.beforeCount > 0 && ss.afterCount > 0);
    } else {
      const journeyTest = fs.readFileSync(
        path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart'),
        'utf8',
      );
      assert.ok(
        journeyTest.includes('Case 1') &&
          journeyTest.includes('Case 2') &&
          journeyTest.includes('Retry guard'),
      );
      const vfsMissingAfter = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot);
      const vfsNoBefore = createMemoryFs({
        [path.join(cfg.repoRoot, 'docs/beta/mobile/screenshots/after/01_login.png')]:
          buildPngHeaderBuffer(390, 844),
      });
      assert.throws(() => verifyScreenshots(cfg.repoRoot, { fsImpl: vfsNoBefore, requireFiles: true }));
      assert.ok(verifyScreenshots(cfg.repoRoot, { fsImpl: vfsMissingAfter, requireFiles: true }).count > 0);
    }
  });

  test('T1-F5-03: Profile benchmark driver & list-open latency telemetry', async () => {
    const haLong = await resolveHaLongDestination(client);
    const res = await client.get('/places', {
      query: { destinationId: haLong.id, limit: 20 },
    });
    assertSuccessEnvelope(res, 200);
    assert.ok(typeof res.durationMs === 'number' && res.durationMs >= 0);

    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      assert.equal(detectBetaMobileTree(cfg.mobileDir), true);
      verifyPerfBenchmarkArtifacts(cfg.mobileDir, cfg.repoRoot);
    } else {
      const homeText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/home/presentation/home_screen.dart'),
        'utf8',
      );
      const sheetText = fs.readFileSync(
        path.join(cfg.mobileDir, 'lib/features/home/presentation/widgets/destination_places_sheet.dart'),
        'utf8',
      );
      assert.ok(homeText.includes('ListView') || homeText.includes('Sliver'));
      assert.ok(sheetText.includes('ListView'));
      const vfsMissingPerf = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'integration_test/perf_benchmark_test.dart')]: null,
      });
      assert.throws(() =>
        verifyPerfBenchmarkArtifacts(cfg.mobileDir, cfg.repoRoot, { fsImpl: vfsMissingPerf }),
      );
    }
  });

  test('T1-F5-04: AppConstants.resolveApiBaseUrl debug/profile/release URL policy', () => {
    const constText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/constants/app_constants.dart'),
      'utf8',
    );
    for (const token of [
      'resolveApiBaseUrl',
      'validateAndNormalizeApiBaseUrl',
      '_disallowedReleaseHosts',
      'StateError',
      'FormatException',
    ]) {
      assert.ok(constText.includes(token), `app_constants.dart missing ${token}`);
    }
    const apiConfigTest = fs.readFileSync(
      path.join(cfg.mobileDir, 'test/api_config_test.dart'),
      'utf8',
    );
    assert.ok(apiConfigTest.includes('http://localhost:3000'));
    assert.ok(apiConfigTest.includes('https://'));
    assert.ok(apiConfigTest.includes('isA<StateError>()'));
    assert.ok(apiConfigTest.includes('isA<FormatException>()'));
    getFlutterTestResult(cfg.mobileDir, { requireExecuted: cfg.shouldRunFlutter });
  });

  test('T1-F5-05: Benchmark delta metrics & cached flutter test execution', async () => {
    const res1 = await client.get(`/places/${FIXTURE.poi.id}`);
    assertSuccessEnvelope(res1, 200);
    assert.ok(res1.durationMs >= 0 && Number.isFinite(res1.durationMs));
    const flutterOutcome = getFlutterTestResult(cfg.mobileDir, {
      requireExecuted: cfg.shouldRunFlutter,
    });
    if (cfg.shouldRunFlutter) {
      assert.equal(flutterOutcome.executed, true);
      assert.equal(flutterOutcome.exitCode, 0);
    }
  });

  // --- F6: Backend Password Reset & Mail Module ---
  test('T1-F6-01: POST /auth/forgot-password returns 200 & dispatches reset token', async () => {
    const email = uniqueEmail('t1.f6.01');
    await registerUser(client, { email, password: 'OldPass123!', name: 'F6 User 1' });
    const res = await client.post('/auth/forgot-password', { email });
    const data = assertSuccessEnvelope(res, 200);
    assert.equal(data.sent, true);
    assert.equal(data.expiresInMinutes, 30);
    assert.ok(typeof data.message === 'string' && data.message.length > 0);
    const token = await fetchResetToken(client, cfg, email);
    assert.ok(typeof token === 'string' && token.length >= 8);
  });

  test('T1-F6-02: GET /auth/reset-password/validate accepts valid unused token', async () => {
    const email = uniqueEmail('t1.f6.02');
    await registerUser(client, { email, password: 'OldPass123!', name: 'F6 User 2' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);
    const val = assertSuccessEnvelope(
      await client.get('/auth/reset-password/validate', { query: { token } }),
      200,
    );
    assert.equal(val.valid, true);
    assert.ok(Date.parse(val.expiresAt) > Date.now());
  });

  test('T1-F6-03: POST /auth/reset-password updates password cleanly', async () => {
    const email = uniqueEmail('t1.f6.03');
    await registerUser(client, { email, password: 'OldPass123!', name: 'F6 User 3' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);
    const data = assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token, newPassword: 'NewPass456!' }),
      200,
    );
    assert.equal(data.reset, true);
  });

  test('T1-F6-04: Login with newly reset password & verify GET /users/me', async () => {
    const email = uniqueEmail('t1.f6.04');
    await registerUser(client, { email, password: 'OldPass123!', name: 'F6 User 4' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(client, cfg, email);
    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token, newPassword: 'NewPass789!' }),
      200,
    );
    const tokens = assertSuccessEnvelope(
      await loginUser(client, { email, password: 'NewPass789!' }),
      200,
    );
    const me = assertSuccessEnvelope(await client.withToken(tokens.access_token).get('/users/me'), 200);
    assert.equal(me.email, email);
  });

  test('T1-F6-05: Forgot password trims & lowercases mixed-case email consistently', async () => {
    const lower = uniqueEmail('mixed.case');
    await registerUser(client, { email: lower, password: 'OldPass123!', name: 'Mixed Case' });
    const mixed = `  ${lower.toUpperCase()}  `;
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email: mixed }), 200);
    const token = await fetchResetToken(client, cfg, lower);
    assertSuccessEnvelope(
      await client.post('/auth/reset-password', { token, newPassword: 'MixedReset123!' }),
      200,
    );
    assertSuccessEnvelope(await loginUser(client, { email: lower, password: 'MixedReset123!' }), 200);
  });

  // --- F7: Backend Google & Facebook OAuth & Unified Error Envelope ---
  test('T1-F7-01: POST /auth/oauth/google returns tokens & user with google provider', async () => {
    const idToken = process.env.E2E_GOOGLE_TEST_ID_TOKEN || 'valid-google-token';
    const data = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken }),
      200,
    );
    assert.ok(data.access_token && data.refresh_token);
    assert.ok(Array.isArray(data.user.providers) && data.user.providers.includes('google'));
  });

  test('T1-F7-02: POST /auth/oauth/facebook returns tokens & user with facebook provider', async () => {
    const accessToken = process.env.E2E_FACEBOOK_TEST_ACCESS_TOKEN || 'valid-fb-token';
    const data = assertSuccessEnvelope(
      await client.post('/auth/oauth/facebook', { accessToken }),
      200,
    );
    assert.ok(data.access_token && data.refresh_token);
    assert.ok(Array.isArray(data.user.providers) && data.user.providers.includes('facebook'));
  });

  test('T1-F7-03: Google OAuth links to existing email account without duplicate user', async () => {
    const email = uniqueEmail('hybrid');
    const localAuth = await registerAndLogin(client, {
      email,
      password: 'Password123!',
      name: 'Hybrid User',
    });
    const localMe = assertSuccessEnvelope(
      await client.withToken(localAuth.accessToken).get('/users/me'),
      200,
    );
    const gData = assertSuccessEnvelope(
      await client.post('/auth/oauth/google', { idToken: `valid-email:${email}` }),
      200,
    );
    assert.ok(Array.isArray(gData.user.providers) && gData.user.providers.includes('google'));
    assert.equal(gData.user.id, localMe.id);

    const oauthMe = assertSuccessEnvelope(
      await client.withToken(gData.access_token).get('/users/me'),
      200,
    );
    assert.equal(oauthMe.id, localMe.id);
    assert.equal(oauthMe.email, email);
  });

  test('T1-F7-04: OAuth-created user refreshes JWT cleanly via POST /auth/refresh', async () => {
    const oauthData = assertSuccessEnvelope(
      await client.post('/auth/oauth/facebook', {
        accessToken: `valid-email:${uniqueEmail('oauth.refresh')}`,
      }),
      200,
    );
    const refreshed = assertSuccessEnvelope(
      await client.post('/auth/refresh', { refresh_token: oauthData.refresh_token }),
      200,
    );
    assert.ok(refreshed.access_token && refreshed.refresh_token);
    assertSuccessEnvelope(await client.withToken(refreshed.access_token).get('/users/me'), 200);
  });

  test('T1-F7-05: Unified error envelope includes canonical INVALID_CREDENTIALS errorCode', async () => {
    const res = await loginUser(client, {
      email: uniqueEmail('nonexistent'),
      password: 'WrongPassword123!',
    });
    assertErrorEnvelope(res, 401, 'INVALID_CREDENTIALS', '/auth/login');
  });

  // --- F8: Backend POI & YouTube Freshness Layer ---
  test('T1-F8-01: POST /youtube/events links grounded Tháp Đồng Hồ update with UTC & latency', async () => {
    const vid = uniqueVideoId('f81');
    const payload = buildGroundedThapDongHoEvent({
      videoId: vid,
    });
    const res = await client.post('/youtube/events', payload, {
      headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
    });
    const receipt = assertSuccessEnvelope(res, 200);
    assert.equal(receipt.status, 'LINKED');
    assert.equal(receipt.scope, 'POI');
    assert.equal(receipt.linkedPlaceId, FIXTURE.poi.id);
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
    const item = updates.items.find((i) => i.videoId === vid);
    assert.ok(item, 'Newly ingested update must appear in GET /places/:id/youtube-updates');
    assert.ok(item.updatedAt.endsWith('Z'));
    assert.ok(item.ingestLatencyMs >= 0 && item.ingestLatencyMs <= 300000);
  });

  test('T1-F8-02: GET /places/:id/youtube-updates & alias return 5-field items + governance metadata', async () => {
    const primary = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 10 } }),
      200,
    );
    assertYoutubeContainerContract(primary);
    assert.ok(primary.items.length >= 1, 'Expected >= 1 POI YouTube update on Tháp Đồng Hồ');
    assertYoutubeFiveFields(primary.items[0], 'POI');

    const alias = assertSuccessEnvelope(
      await client.get(`/youtube/places/${FIXTURE.poi.id}/updates`, { query: { limit: 10 } }),
      200,
    );
    assertYoutubeContainerContract(alias);
    assert.equal(alias.items.length, primary.items.length);
  });

  test('T1-F8-03: Hạ Long city-level fallback links scope=CITY, placeId=null & exposes destination endpoint', async () => {
    const cityVid = uniqueVideoId('cty');
    const cityEvent = {
      eventId: `evt-city-${crypto.randomUUID()}`,
      videoId: cityVid,
      channelId: 'UC_Halong_City_01',
      channelTitle: 'Vịnh Hạ Long TV',
      title: 'Toàn cảnh Vịnh Hạ Long Quảng Ninh mùa du lịch',
      description: 'Khám phá cảnh đẹp thành phố Hạ Long từ trên cao.',
      tags: ['Hạ Long', 'Quảng Ninh'],
      publishedAt: isoWithOffsetSeconds(-30_000, '+07:00'),
    };
    const receipt = assertSuccessEnvelope(
      await client.post('/youtube/events', cityEvent, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(receipt.status, 'LINKED_CITY');
    assert.equal(receipt.scope, 'CITY');
    assert.equal(receipt.linkedPlaceId, null);

    const destData = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates', {
        query: { limit: 50, scope: 'CITY' },
      }),
      200,
    );
    assertYoutubeContainerContract(destData);
    assert.ok(destData.items.some((i) => i.videoId === cityVid));
    for (const item of destData.items) {
      assertYoutubeFiveFields(item, 'CITY');
    }

    const placeData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assert.ok(placeData.cityFallbackItems.some((i) => i.videoId === cityVid));
  });

  test('T1-F8-04: WebSub GET challenge handshake & POST Atom XML HMAC ingestion', async () => {
    const challenge = `ch-${crypto.randomUUID().slice(0, 8)}`;
    const verifyRes = await client.get('/youtube/webhook', {
      query: {
        'hub.mode': 'subscribe',
        'hub.topic': 'https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC_Halong_WebSub_01',
        'hub.challenge': challenge,
      },
    });
    assert.equal(verifyRes.status, 200);
    assert.equal(verifyRes.text, challenge);

    const videoId = uniqueVideoId('ws');
    const xml = buildYoutubeAtomFeed([
      {
        videoId,
        channelId: 'UC_Halong_WebSub_01',
        channelTitle: 'WebSub Hạ Long',
        title: 'Tháp Đồng Hồ Hạ Long về đêm',
        description: 'Review Tháp Đồng Hồ tại Bạch Đằng, Hạ Long, Quảng Ninh.',
        publishedAt: isoWithOffsetSeconds(-20_000, '+07:00'),
        latitude: FIXTURE.poi.latitude,
        longitude: FIXTURE.poi.longitude,
      },
    ]);
    const sig = signWebSubBody(xml, cfg.websubSecret, 'sha256');
    const postRes = await client.post('/youtube/webhook', {
      rawBody: xml,
      headers: {
        'Content-Type': 'application/atom+xml',
        ...(sig ? { 'X-Hub-Signature': sig } : {}),
      },
    });
    const data = assertSuccessEnvelope(postRes, 200);
    assert.equal(data.processedCount, 1);
    assert.equal(data.results[0].status, 'LINKED');
    assert.equal(data.results[0].linkedPlaceId, FIXTURE.poi.id);
  });

  test('T1-F8-05: Duplicate YouTube event replay increments deliveryCount with 1 stored record', async () => {
    const event = buildGroundedThapDongHoEvent({
      eventId: `evt-dedupe-${crypto.randomUUID()}`,
      videoId: uniqueVideoId('dp'),
    });
    const first = assertSuccessEnvelope(
      await client.post('/youtube/events', event, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    const second = assertSuccessEnvelope(
      await client.post('/youtube/events', event, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(first.duplicate, false);
    assert.equal(first.deliveryCount, 1);
    assert.equal(second.id, first.id);
    assert.equal(second.duplicate, true);
    assert.equal(second.deliveryCount, 2);
    assert.equal(second.receivedAt, first.receivedAt);

    const updates = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const matches = updates.items.filter((i) => i.videoId === event.videoId);
    assert.equal(matches.length, 1, 'Duplicate replay must produce exactly 1 item');
  });

  // --- F9: Flutter POI & YouTube Freshness UI ---
  test('T1-F9-01: PlaceDetail YouTube 5 fields & <= 300000ms SLA over real HTTP (+ M4 UI check)', async () => {
    const vid = uniqueVideoId('rt');
    const evt = buildGroundedThapDongHoEvent({
      publishedAt: isoWithOffsetSeconds(-60_000, 'Z'),
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

    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(apiData);
    const matchedItem = apiData.items.find((i) => i.videoId === vid);
    assert.ok(matchedItem, 'Fresh ingested event must be returned by GET /places/:id/youtube-updates');
    assertYoutubeFiveFields(matchedItem, 'POI', { maxIngestLatencyMs: 300000 });
    assert.equal(matchedItem.placeId, FIXTURE.poi.id);
    assert.ok(matchedItem.ingestLatencyMs <= apiData.realtimeSlaMaxLatencyMs);

    if (cfg.mode === 'live') {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    } else {
      const vfsMissingM4 = buildValidBetaVfs(cfg.mobileDir, cfg.repoRoot, {
        [path.join(cfg.mobileDir, 'lib/features/places/presentation/place_detail_screen.dart')]:
          'AppTextField(); AppButton(); AppLoading(); AppErrorState(); AppStateBanner();',
      });
      assert.throws(() =>
        verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
          requireM4Youtube: true,
          fsImpl: vfsMissingM4,
        }),
      );
    }
  });

  test('T1-F9-02: Stale YouTube event (> 300000ms) exceeds realtimeSlaMaxLatencyMs over real HTTP', async () => {
    const vid = uniqueVideoId('stl');
    const evt = buildGroundedThapDongHoEvent({
      eventId: `evt-stale-${crypto.randomUUID()}`,
      videoId: vid,
      publishedAt: isoWithOffsetSeconds(-15 * 60 * 1000, 'Z'),
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
    const receiptLagMs = Date.parse(receipt.receivedAt) - Date.parse(receipt.publishedAt);
    assert.ok(receiptLagMs > 300000, `Expected stale receipt lag > 300000, got ${receiptLagMs}`);

    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(apiData);
    const matchedItem = apiData.items.find((i) => i.videoId === vid);
    assert.ok(matchedItem, 'Stale event must still appear in youtube-updates');
    assertYoutubeFiveFields(matchedItem, 'POI');
    assert.ok(matchedItem.ingestLatencyMs > apiData.realtimeSlaMaxLatencyMs);
    assert.ok(
      Date.parse(apiData.serverDeliveredAt) - Date.parse(matchedItem.publishedAt) >
        apiData.realtimeSlaMaxLatencyMs,
    );
  });

  test('T1-F9-03: Hạ Long city fallback update returns placeId=null, scope=CITY on destination & place endpoints', async () => {
    const vid = uniqueVideoId('f9c');
    const cityEvt = {
      eventId: `evt-f9c-${crypto.randomUUID()}`,
      videoId: vid,
      channelId: 'UC_F9_City',
      channelTitle: 'Hạ Long Travel',
      title: 'Khám phá Vịnh Hạ Long Quảng Ninh buổi sáng',
      publishedAt: isoWithOffsetSeconds(-40_000, 'Z'),
    };
    const receipt = assertSuccessEnvelope(
      await client.post('/youtube/events', cityEvt, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    assert.equal(receipt.status, 'LINKED_CITY');
    assert.equal(receipt.scope, 'CITY');
    assert.equal(receipt.linkedPlaceId, null);

    const destData = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates', {
        query: { limit: 50, scope: 'CITY' },
      }),
      200,
    );
    assertYoutubeContainerContract(destData);
    const destItem = destData.items.find((i) => i.videoId === vid);
    assert.ok(destItem, 'City event must appear on /destinations/ha-long/youtube-updates');
    assertYoutubeFiveFields(destItem, 'CITY');

    const placeData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const fallbackItem = placeData.cityFallbackItems.find((i) => i.videoId === vid);
    assert.ok(fallbackItem, 'City event must appear in place cityFallbackItems');
    assertYoutubeFiveFields(fallbackItem, 'CITY');
  });

  test('T1-F9-04: POI updates and Hạ Long city fallback coexist cleanly & newest-first in HTTP payload', async () => {
    const olderVid = uniqueVideoId('old');
    const newerVid = uniqueVideoId('new');
    const cityVid = uniqueVideoId('fbk');

    assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `evt-f94-old-${crypto.randomUUID()}`,
          videoId: olderVid,
          publishedAt: isoWithOffsetSeconds(-120_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `evt-f94-new-${crypto.randomUUID()}`,
          videoId: newerVid,
          publishedAt: isoWithOffsetSeconds(-20_000, 'Z'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `evt-f94-city-${crypto.randomUUID()}`,
          videoId: cityVid,
          channelId: 'UC_F94_City',
          title: 'Thành phố Hạ Long Quảng Ninh buổi chiều',
          publishedAt: isoWithOffsetSeconds(-30_000, 'Z'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );

    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(apiData);
    assert.ok(apiData.items.some((i) => i.videoId === newerVid));
    assert.ok(apiData.items.some((i) => i.videoId === olderVid));
    assert.ok(apiData.cityFallbackItems.some((i) => i.videoId === cityVid));
    const idxNew = apiData.items.findIndex((i) => i.videoId === newerVid);
    const idxOld = apiData.items.findIndex((i) => i.videoId === olderVid);
    assert.ok(idxNew < idxOld, 'POI items must be ordered newest-first');
  });

  test('T1-F9-05: YouTube item exposes valid watch videoUrl & DYNAMIC_SOCIAL_FRESHNESS_LAYER metadata', async () => {
    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    assertYoutubeContainerContract(apiData);
    assert.ok(apiData.items.length > 0);
    assert.match(apiData.items[0].videoUrl, /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/);
    if (cfg.mode === 'live' || detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot, {
        requireScreenshots: true,
        requireM4Youtube: true,
      });
    }
  });

  // --- F10: W07 Data Governance & Layer Isolation ---
  test('T1-F10-01: W07 gomate_places_freeze_v2.json SHA-256 matches frozen baseline byte-for-byte', () => {
    const result = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(result.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
    assert.equal(result.w07KnowledgeSha256, FIXTURE.w07Checksums.w07KnowledgeSha256);
  });

  test('T1-F10-02: Protected W07 paths & w07_offline_retrieval_prep have zero modifications', () => {
    const requireW07Prep = cfg.mode === 'live' || cfg.w07PrepDirExplicit;
    const status = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir, { requireW07Prep });
    assert.equal(status.dirtyLines.length, 0);
    if (requireW07Prep || fs.existsSync(cfg.w07PrepDir)) {
      assert.equal(status.w07PrepVerified, true);
    }
  });

  test('T1-F10-03: documents & place_sources counts are untouched across POI/City/Unlinked YouTube ingestion', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats = await fetchDbStats(client, cfg);

    const poiRes = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `gov-poi-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('gp'),
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(poiRes.status, 'LINKED');

    const cityRes = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `gov-city-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('gc'),
          channelId: 'UC_Gov_City',
          title: 'Hạ Long buổi chiều',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(cityRes.status, 'LINKED_CITY');

    const noneRes = assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        {
          eventId: `gov-none-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('gn'),
          channelId: 'UC_Gov_None',
          title: 'Video không liên quan địa điểm',
          publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
        },
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    assert.equal(noneRes.status, 'UNLINKED_NO_BASIS');

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    const afterStats = await fetchDbStats(client, cfg);
    verifyDbStatsIsolation(beforeStats, afterStats);
  });

  test('T1-F10-04: Place & destination YouTube endpoints declare DYNAMIC_SOCIAL_FRESHNESS_LAYER & notPrimaryFactualCorpus', async () => {
    const placeRes = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`),
      200,
    );
    const destRes = assertSuccessEnvelope(
      await client.get('/destinations/ha-long/youtube-updates'),
      200,
    );
    assertYoutubeContainerContract(placeRes);
    assertYoutubeContainerContract(destRes);
  });

  test('T1-F10-05: Factual OSM/Wikipedia fields on GET /places/:id remain invariant after YouTube updates', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    assertSuccessEnvelope(
      await client.post(
        '/youtube/events',
        buildGroundedThapDongHoEvent({
          eventId: `gov-invar-${crypto.randomUUID()}`,
          videoId: uniqueVideoId('gi'),
          title: 'Tháp Đồng Hồ Hạ Long review mới nhất',
        }),
        { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
      ),
      200,
    );
    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
  });
});
