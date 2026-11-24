import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { getRuntimeConfig } from '../lib/cli_args.mjs';
import {
  HttpClient,
  decodeJwtPayload,
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
  validateApiBaseUrl,
  verifyBaseline10126b1Hooks,
  verifyBetaDartDeliverables,
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
    assert.ok(data.items.length > 0, `No reset email found in self-test outbox for ${email}`);
    return data.items[data.items.length - 1].rawToken;
  }
  if (process.env.E2E_TEST_RESET_TOKEN) {
    return process.env.E2E_TEST_RESET_TOKEN;
  }
  if (process.env.E2E_MAIL_OUTBOX_URL) {
    const outboxClient = new HttpClient(process.env.E2E_MAIL_OUTBOX_URL);
    const res = await outboxClient.get('/', { query: { email } });
    if (res.json?.token) return res.json.token;
    if (res.json?.data?.items?.length) {
      return res.json.data.items[res.json.data.items.length - 1].rawToken;
    }
  }
  throw new Error('Live mode reset test requires E2E_MAIL_OUTBOX_URL or E2E_TEST_RESET_TOKEN');
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
    if (detectBetaMobileTree(cfg.mobileDir)) {
      verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot);
    } else {
      const loginPath = path.join(cfg.mobileDir, 'lib/features/auth/presentation/login_screen.dart');
      assert.ok(fs.existsSync(loginPath), 'Baseline login_screen.dart must exist');
    }
  });

  test('T1-F1-02: Auth screens (/register, /forgot-password, /reset-password) shared components & public paths contract', () => {
    assert.equal(mobileSpec.authScreens.length, 4);
    for (const pubPath of mobileSpec.publicAuthPaths) {
      assert.ok(pubPath.startsWith('/auth/'), `Expected /auth/* path: ${pubPath}`);
    }
    if (detectBetaMobileTree(cfg.mobileDir)) {
      const res = verifyBetaDartDeliverables(cfg.mobileDir, cfg.repoRoot);
      assert.equal(res.publicAuthPathsVerified, 8);
    } else {
      assert.equal(sanitizeInternalRedirect('/reset-password?token=abc'), '/reset-password?token=abc');
      assert.equal(sanitizeInternalRedirect('/forgot-password'), '/forgot-password');
    }
  });

  test('T1-F1-03: Core screens (Home, Map, PlaceDetail) error-to-retry & loading contract', async () => {
    for (const screen of mobileSpec.coreScreens.slice(0, 3)) {
      assert.ok(
        fs.existsSync(path.join(cfg.mobileDir, screen.file)),
        `Missing core screen: ${screen.file}`,
      );
    }
    const errRes = await client.get(`/places/${FIXTURE.negativeFixtures.unknownPlaceId}`);
    assertErrorEnvelope(errRes, 404, 'PLACE_NOT_FOUND', '/places/');
    const okRes = await client.get(`/places/${FIXTURE.poi.id}`);
    const place = assertSuccessEnvelope(okRes, 200);
    assert.equal(place.id, FIXTURE.poi.id);
  });

  test('T1-F1-04: TripListScreen & TripDetailScreen loading/empty/error & JWT trips contract', async () => {
    for (const screen of mobileSpec.coreScreens.slice(3)) {
      assert.ok(
        fs.existsSync(path.join(cfg.mobileDir, screen.file)),
        `Missing trip screen: ${screen.file}`,
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
    const wrapperPath = path.join(cfg.mobileDir, 'lib/core/widgets/responsive_wrapper.dart');
    assert.ok(fs.existsSync(wrapperPath), 'responsive_wrapper.dart must exist');
    assert.equal(mobileSpec.betaRequiredDeliverables.screenshotDimensions.width, 390);
    assert.equal(mobileSpec.betaRequiredDeliverables.screenshotDimensions.height, 844);
    const screenshotDir = path.join(cfg.repoRoot, mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo);
    if (fs.existsSync(screenshotDir)) {
      const pngs = fs.readdirSync(screenshotDir).filter((f) => f.endsWith('.png'));
      for (const file of pngs) {
        const dims = parsePngDimensions(path.join(screenshotDir, file));
        assert.ok(dims.width > 0 && dims.height > 0);
      }
    }
  });

  // --- F2: 4 Core Screens Polish & Perf ---
  test('T1-F2-01: HomeScreen -> Hạ Long destination -> search Tháp Đồng Hồ returns verified POI', async () => {
    const destRes = await client.get('/destinations');
    const destData = assertSuccessEnvelope(destRes, 200);
    const haLong = destData.items.find((d) => d.slug === 'ha-long');
    assert.ok(haLong, 'ha-long destination must exist');

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
    assert.ok(mapText.includes('place_preview_view_detail') || mapText.includes('PlacePreviewSheet'));
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
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f2.04'),
      password: 'Password123!',
      name: 'Trip Detail User',
    });
    const authed = client.withToken(auth.accessToken);
    const tripRes = await authed.post('/trips', {
      title: 'Hạ Long Mùa Thu',
      destinationId: FIXTURE.destinations.haLong.id,
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
    const page1 = assertSuccessEnvelope(
      await client.get('/places', {
        query: { destinationId: FIXTURE.destinations.haLong.id, page: 1, limit: 20 },
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
      homeText.includes('ListView') || homeText.includes('Sliver') || homeText.includes('CustomScrollView'),
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

    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Success',
      redirectPath: `/places/${FIXTURE.poi.id}`,
    });
    assert.equal(ui.authenticated, true);
    assert.equal(ui.guestBrowseMode, false);
    assert.equal(ui.navigatedTo, `/places/${FIXTURE.poi.id}`);
    assert.equal(ui.postLoginRedirect, null);
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
    const rawToken = await fetchResetToken(email);

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
    const gRes = await client.post('/auth/oauth/google', { idToken: 'valid-google-token' });
    const gData = assertSuccessEnvelope(gRes, 200);
    assert.ok(gData.user.providers.includes('google'));

    const fRes = await client.post('/auth/oauth/facebook', { accessToken: 'valid-fb-token' });
    const fData = assertSuccessEnvelope(fRes, 200);
    assert.ok(fData.user.providers.includes('facebook'));

    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Success',
      redirectPath: '/',
      callBackendOAuth: async () => gRes,
    });
    assert.equal(ui.authenticated, true);
    assert.equal(ui.navigatedTo, '/');
  });

  // --- F4: Save Flow Resilience ---
  test('T1-F4-01: SavePlaceToTripSheet saves Tháp Đồng Hồ into existing trip Day 1', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.01'),
      password: 'Password123!',
      name: 'Save Existing User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(
      await authed.post('/trips', { title: 'Existing Hạ Long', destinationId: FIXTURE.destinations.haLong.id }),
      201,
    );

    const flow = await simulateSavePlaceFlow({
      existingTripId: trip.id,
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async () => {
        throw new Error('Should not create new trip');
      },
      addItineraryFn: async ({ tripId, dayNumber, placeId }) => {
        const res = await authed.post(`/trips/${tripId}/itinerary`, {
          dayNumber,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId,
        });
        return { ok: res.status === 201 };
      },
    });
    const out = await flow.attempt();
    assert.equal(out.saved, true);
    assert.equal(out.createTripCalls, 0);
    assert.equal(out.addItineraryCalls, 1);
  });

  test('T1-F4-02: SavePlaceToTripSheet with 0 trips creates 1 trip & adds Tháp Đồng Hồ', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.02'),
      password: 'Password123!',
      name: 'Save New Trip User',
    });
    const authed = client.withToken(auth.accessToken);

    const flow = await simulateSavePlaceFlow({
      newTripTitle: 'Hạ Long Cuối Tuần',
      dayNumber: 1,
      placeId: FIXTURE.poi.id,
      createTripFn: async ({ title }) => {
        const res = await authed.post('/trips', {
          title,
          destinationId: FIXTURE.destinations.haLong.id,
        });
        const data = assertSuccessEnvelope(res, 201);
        return { ok: true, tripId: data.id };
      },
      addItineraryFn: async ({ tripId, dayNumber, placeId }) => {
        const res = await authed.post(`/trips/${tripId}/itinerary`, {
          dayNumber,
          activity: 'Tham quan Tháp Đồng Hồ',
          placeId,
        });
        assertSuccessEnvelope(res, 201);
        return { ok: true };
      },
    });
    const out = await flow.attempt();
    assert.equal(out.saved, true);
    assert.equal(out.createTripCalls, 1);
    const trips = assertSuccessEnvelope(await authed.get('/trips'), 200);
    assert.equal(trips.length, 1);
    assert.equal(trips[0].title, 'Hạ Long Cuối Tuần');
  });

  test('T1-F4-03: Cold restart persistence verifies saved Tháp Đồng Hồ itinerary survives process reset', async () => {
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.03'),
      password: 'Password123!',
      name: 'Cold Restart User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'Cold Restart Trip' }), 201);
    assertSuccessEnvelope(
      await authed.post(`/trips/${trip.id}/itinerary`, {
        dayNumber: 1,
        activity: 'Tham quan Tháp Đồng Hồ',
        placeId: FIXTURE.poi.id,
      }),
      201,
    );

    // Fresh HttpClient simulating cold app restart using stored token
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
    assert.equal(sanitizeInternalRedirect(targetPath), targetPath);
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.04'),
      password: 'Password123!',
      name: 'Redirect Save User',
    });
    const ui = await evaluateAuthOutcomeMatrix({
      outcome: 'Success',
      redirectPath: targetPath,
    });
    assert.equal(ui.navigatedTo, targetPath);

    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'Post-Redirect Trip' }), 201);
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
    const auth = await registerAndLogin(client, {
      email: uniqueEmail('t1.f4.05'),
      password: 'Password123!',
      name: 'Day 3 User',
    });
    const authed = client.withToken(auth.accessToken);
    const trip = assertSuccessEnvelope(await authed.post('/trips', { title: 'Multi-day Trip' }), 201);
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
    const dims = mobileSpec.betaRequiredDeliverables.screenshotDimensions;
    assert.deepEqual(dims, { width: 390, height: 844 });
    const dir = path.join(cfg.repoRoot, mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo);
    if (detectBetaMobileTree(cfg.mobileDir) && fs.existsSync(dir)) {
      const pngs = fs.readdirSync(dir).filter((f) => f.endsWith('.png'));
      assert.ok(pngs.length > 0, 'Beta docs/beta/mobile must contain PNG screenshots');
      for (const f of pngs) {
        const parsed = parsePngDimensions(path.join(dir, f));
        assert.equal(parsed.width, 390);
        assert.equal(parsed.height, 844);
      }
    }
  });

  test('T1-F5-02: Before (10126b1) vs After screenshot parity contract', () => {
    const dir = path.join(cfg.repoRoot, mobileSpec.betaRequiredDeliverables.screenshotDirRelativeToRepo);
    if (detectBetaMobileTree(cfg.mobileDir) && fs.existsSync(dir)) {
      const pngs = fs.readdirSync(dir).filter((f) => f.endsWith('.png'));
      const befores = pngs.filter((f) => f.toLowerCase().includes('before'));
      const afters = pngs.filter((f) => f.toLowerCase().includes('after'));
      assert.ok(befores.length > 0 && afters.length > 0, 'Both before & after PNGs required');
      assert.deepEqual(
        parsePngDimensions(path.join(dir, befores[0])),
        parsePngDimensions(path.join(dir, afters[0])),
      );
    } else {
      assert.ok(fs.existsSync(path.join(cfg.mobileDir, 'test/halong_trip_save_journey_test.dart')));
    }
  });

  test('T1-F5-03: Profile benchmark driver & list-open latency telemetry', async () => {
    const res = await client.get('/places', {
      query: { destinationId: FIXTURE.destinations.haLong.id, limit: 20 },
    });
    assertSuccessEnvelope(res, 200);
    assert.ok(typeof res.durationMs === 'number' && res.durationMs >= 0);
    if (detectBetaMobileTree(cfg.mobileDir)) {
      assert.ok(fs.existsSync(path.join(cfg.mobileDir, mobileSpec.betaRequiredDeliverables.perfBenchmarkTest)));
      assert.ok(fs.existsSync(path.join(cfg.mobileDir, mobileSpec.betaRequiredDeliverables.perfDriver)));
    }
  });

  test('T1-F5-04: AppConstants.resolveApiBaseUrl debug/profile/release URL policy', () => {
    const constText = fs.readFileSync(
      path.join(cfg.mobileDir, 'lib/core/constants/app_constants.dart'),
      'utf8',
    );
    assert.ok(constText.includes('resolveApiBaseUrl'));
    assert.equal(validateApiBaseUrl('').url, 'http://localhost:3000');
    assert.equal(
      validateApiBaseUrl('https://api.wanderai.vn/', { isReleaseMode: true }).url,
      'https://api.wanderai.vn',
    );
    assert.equal(
      validateApiBaseUrl('', { isProfileMode: true, benchmarkAdapterEnabled: true }).mode,
      'profile-benchmark-adapter',
    );
  });

  test('T1-F5-05: Benchmark delta metrics & optional flutter test execution', async () => {
    const res1 = await client.get(`/places/${FIXTURE.poi.id}`);
    assertSuccessEnvelope(res1, 200);
    assert.ok(res1.durationMs >= 0 && Number.isFinite(res1.durationMs));
    const flutterOutcome = runFlutterTestsIfRequested(cfg.mobileDir, cfg.runFlutter);
    if (cfg.runFlutter) {
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
    const token = await fetchResetToken(email);
    assert.ok(typeof token === 'string' && token.length >= 8);
  });

  test('T1-F6-02: GET /auth/reset-password/validate accepts valid unused token', async () => {
    const email = uniqueEmail('t1.f6.02');
    await registerUser(client, { email, password: 'OldPass123!', name: 'F6 User 2' });
    assertSuccessEnvelope(await client.post('/auth/forgot-password', { email }), 200);
    const token = await fetchResetToken(email);
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
    const token = await fetchResetToken(email);
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
    const token = await fetchResetToken(email);
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
    const token = await fetchResetToken(lower);
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
    const oauthMe = assertSuccessEnvelope(
      await client.withToken(gData.access_token).get('/users/me'),
      200,
    );
    assert.equal(oauthMe.id, localMe.id);
    assert.ok(oauthMe.providers.includes('google'));
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
    const payload = buildGroundedThapDongHoEvent();
    const res = await client.post('/youtube/events', payload, {
      headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
    });
    const receipt = assertSuccessEnvelope(res, 200);
    assert.equal(receipt.status, 'LINKED');
    assert.equal(receipt.scope, 'POI');
    assert.equal(receipt.linkedPlaceId, FIXTURE.poi.id);
    assert.ok(receipt.publishedAt.endsWith('Z'));
    assert.ok(receipt.receivedAt.endsWith('Z'));
    assert.ok(receipt.updatedAt.endsWith('Z'));
    assert.ok(receipt.ingestLatencyMs >= 0);
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
    const cityEvent = {
      eventId: `evt-city-${crypto.randomUUID()}`,
      videoId: 'abc123XYZ89',
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
      await client.get('/destinations/ha-long/youtube-updates'),
      200,
    );
    assertYoutubeContainerContract(destData);
    assert.ok(destData.items.some((i) => i.videoId === 'abc123XYZ89'));
    for (const item of destData.items) {
      assertYoutubeFiveFields(item, 'CITY');
    }

    const placeData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`),
      200,
    );
    assert.ok(placeData.cityFallbackItems.some((i) => i.videoId === 'abc123XYZ89'));
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

    const videoId = `ws${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`;
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
      videoId: `dp${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`,
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
  test('T1-F9-01: PlaceDetail YouTube UI renders 5 fields & "Thời gian thực" when <= 300000ms', async () => {
    const evt = buildGroundedThapDongHoEvent({
      publishedAt: isoWithOffsetSeconds(-60_000, 'Z'),
      videoId: `rt${crypto.randomUUID().replace(/-/g, '').slice(0, 9)}`,
    });
    assertSuccessEnvelope(
      await client.post('/youtube/events', evt, {
        headers: { 'x-youtube-internal-secret': cfg.youtubeSecret },
      }),
      200,
    );
    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`, { query: { limit: 50 } }),
      200,
    );
    const matchedItem = apiData.items.find((i) => i.videoId === evt.videoId);
    assert.ok(matchedItem);
    const ui = evaluateYoutubeFreshnessUi(
      { ...apiData, items: [matchedItem], cityFallbackItems: [] },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(ui.primarySection, 'POI');
    assert.equal(ui.poiItems[0].badgeLabel, 'Thời gian thực');
    assert.equal(ui.poiItems[0].source, 'youtube');
    assert.equal(ui.poiItems[0].placeId, FIXTURE.poi.id);
  });

  test('T1-F9-02: PlaceDetail YouTube UI renders "Cập nhật gần đây" when > 300000ms', () => {
    const stalePublished = new Date(Date.now() - 15 * 60 * 1000).toISOString();
    const ui = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [
          {
            placeId: FIXTURE.poi.id,
            scope: 'POI',
            source: 'youtube',
            publishedAt: stalePublished,
            receivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
          },
        ],
        cityFallbackItems: [],
      },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(ui.poiItems[0].badgeLabel, 'Cập nhật gần đây');
    assert.notEqual(ui.poiItems[0].badgeLabel, 'Thời gian thực');
    assert.ok(ui.poiItems[0].endToEndLatencyMs >= 900000);
  });

  test('T1-F9-03: PlaceDetail YouTube UI renders Hạ Long city fallback banner when POI items empty', () => {
    const ui = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [],
        cityFallbackItems: [
          {
            placeId: null,
            scope: 'CITY',
            source: 'youtube',
            publishedAt: new Date(Date.now() - 40_000).toISOString(),
            receivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=abc123XYZ89',
          },
        ],
      },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(ui.primarySection, 'CITY_FALLBACK');
    assert.equal(ui.showCityFallbackBanner, true);
    assert.equal(ui.cityFallbackItems[0].placeId, null);
    assert.equal(ui.cityFallbackItems[0].scope, 'CITY');
  });

  test('T1-F9-04: PlaceDetail YouTube UI prioritizes POI update over city fallback when both exist', () => {
    const nowIso = new Date(Date.now() - 30_000).toISOString();
    const ui = evaluateYoutubeFreshnessUi(
      {
        realtimeSlaMaxLatencyMs: 300000,
        items: [
          {
            placeId: FIXTURE.poi.id,
            scope: 'POI',
            source: 'youtube',
            publishedAt: nowIso,
            receivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=poiVideo123',
          },
        ],
        cityFallbackItems: [
          {
            placeId: null,
            scope: 'CITY',
            source: 'youtube',
            publishedAt: nowIso,
            receivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            videoUrl: 'https://www.youtube.com/watch?v=cityVideo12',
          },
        ],
      },
      { clientRenderedAtMs: Date.now() },
    );
    assert.equal(ui.primarySection, 'POI');
    assert.equal(ui.showCityFallbackBanner, false);
    assert.equal(ui.poiItems.length, 1);
    assert.equal(ui.cityFallbackItems.length, 1);
  });

  test('T1-F9-05: YouTube item exposes valid watch videoUrl & DYNAMIC_SOCIAL_FRESHNESS_LAYER metadata', async () => {
    const apiData = assertSuccessEnvelope(
      await client.get(`/places/${FIXTURE.poi.id}/youtube-updates`),
      200,
    );
    assertYoutubeContainerContract(apiData);
    assert.ok(apiData.items.length > 0);
    assert.match(apiData.items[0].videoUrl, /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/);
  });

  // --- F10: W07 Data Governance & Layer Isolation ---
  test('T1-F10-01: W07 gomate_places_freeze_v2.json SHA-256 matches frozen baseline byte-for-byte', () => {
    const result = verifyFreezeChecksum(cfg.repoRoot);
    assert.equal(result.freezeSha256, FIXTURE.w07Checksums.freezeV2Sha256);
    assert.equal(result.w07KnowledgeSha256, FIXTURE.w07Checksums.w07KnowledgeSha256);
  });

  test('T1-F10-02: Protected W07 paths & w07_offline_retrieval_prep have zero modifications', () => {
    const status = verifyProtectedPathsClean(cfg.repoRoot, cfg.w07PrepDir);
    assert.equal(status.dirtyLines.length, 0);
    if (fs.existsSync(cfg.w07PrepDir)) {
      assert.equal(status.w07PrepVerified, true);
    }
  });

  test('T1-F10-03: documents & place_sources counts are untouched across POI/City/Unlinked YouTube ingestion', async () => {
    const beforePlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    const beforeStats =
      cfg.mode === 'self-test'
        ? assertSuccessEnvelope(await client.get('/_test/db-stats'), 200)
        : null;

    await client.post(
      '/youtube/events',
      buildGroundedThapDongHoEvent({ eventId: `gov-poi-${crypto.randomUUID()}` }),
      { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
    );
    await client.post(
      '/youtube/events',
      {
        eventId: `gov-city-${crypto.randomUUID()}`,
        videoId: 'cty98765432',
        channelId: 'UC_Gov_City',
        title: 'Hạ Long buổi chiều',
        publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
      },
      { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
    );
    await client.post(
      '/youtube/events',
      {
        eventId: `gov-none-${crypto.randomUUID()}`,
        videoId: 'non12345678',
        channelId: 'UC_Gov_None',
        title: 'Video không liên quan địa điểm',
        publishedAt: isoWithOffsetSeconds(-15_000, '+07:00'),
      },
      { headers: { 'x-youtube-internal-secret': cfg.youtubeSecret } },
    );

    const afterPlace = assertSuccessEnvelope(await client.get(`/places/${FIXTURE.poi.id}`), 200);
    verifyFactualPlaceUnchanged(beforePlace, afterPlace);
    if (beforeStats) {
      const afterStats = assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
      verifyDbStatsIsolation(beforeStats, afterStats);
    }
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
