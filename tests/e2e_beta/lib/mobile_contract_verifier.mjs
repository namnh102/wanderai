import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { computeFreshnessBadge } from './assertions.mjs';

const SPEC_PATH = new URL('../fixtures/mobile_contract_spec.json', import.meta.url);
const MOBILE_SPEC = JSON.parse(fs.readFileSync(SPEC_PATH, 'utf8'));

export function getMobileContractSpec() {
  return MOBILE_SPEC;
}

export function sanitizeInternalRedirect(raw) {
  if (raw === null || raw === undefined) return null;
  const trimmed = String(raw).trim();
  if (!trimmed || !trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return null;
  }
  try {
    const parsed = new URL(trimmed, 'http://local.internal');
    if (parsed.origin !== 'http://local.internal') {
      return null;
    }
    if (
      parsed.pathname === '/login' ||
      parsed.pathname === '/register' ||
      trimmed.includes('://')
    ) {
      return null;
    }
    return trimmed;
  } catch {
    return null;
  }
}

export function validateApiBaseUrl(
  rawUrl,
  { isProfileMode = false, isReleaseMode = false, benchmarkAdapterEnabled = false } = {},
) {
  const trimmed = String(rawUrl || '').trim();
  if (!trimmed) {
    if (isProfileMode && benchmarkAdapterEnabled) {
      return { url: 'benchmark://local-adapter', mode: 'profile-benchmark-adapter' };
    }
    if (isProfileMode || isReleaseMode) {
      throw new Error('StateError: API_BASE_URL is required in release/profile mode');
    }
    return { url: 'http://localhost:3000', mode: 'debug-default' };
  }

  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(`FormatException: Invalid API_BASE_URL "${trimmed}"`);
  }

  if ((isReleaseMode || isProfileMode) && !benchmarkAdapterEnabled) {
    if (parsed.protocol !== 'https:') {
      throw new Error(`StateError: API_BASE_URL must use https:// in release/profile mode (${trimmed})`);
    }
    if (['localhost', '127.0.0.1', '10.0.2.2'].includes(parsed.hostname)) {
      throw new Error(`StateError: Loopback host "${parsed.hostname}" is forbidden in release/profile mode`);
    }
  }

  return { url: trimmed.replace(/\/+$/, ''), mode: isReleaseMode ? 'release' : isProfileMode ? 'profile' : 'debug' };
}

export async function evaluateAuthOutcomeMatrix({
  outcome,
  redirectPath = null,
  currentInput = {},
  callBackendOAuth = null,
}) {
  const state = {
    authenticated: false,
    guestBrowseMode: true,
    postLoginRedirect: sanitizeInternalRedirect(redirectPath),
    currentInput: { ...currentInput },
    banner: null,
    navigatedTo: null,
    backendCalled: false,
  };

  if (outcome === 'Cancelled') {
    const target = state.postLoginRedirect || '/login';
    state.postLoginRedirect = null;
    state.navigatedTo = target;
    return state;
  }

  if (outcome === 'Error') {
    if (callBackendOAuth) {
      state.backendCalled = true;
      const errRes = await callBackendOAuth();
      state.banner = {
        tone: errRes.networkError ? 'warning' : 'error',
        errorCode: errRes.json?.errorCode || (errRes.networkError ? 'NETWORK_ERROR' : 'AUTH_ERROR'),
        message: errRes.json?.message || 'Đăng nhập thất bại',
      };
    } else {
      state.banner = { tone: 'error', errorCode: 'AUTH_ERROR', message: 'Đăng nhập thất bại' };
    }
    return state;
  }

  if (outcome === 'Success') {
    if (callBackendOAuth) {
      state.backendCalled = true;
      await callBackendOAuth();
    }
    state.authenticated = true;
    state.guestBrowseMode = false;
    state.navigatedTo = state.postLoginRedirect || '/';
    state.postLoginRedirect = null;
    return state;
  }

  throw new Error(`Unknown auth outcome: ${outcome}`);
}

export async function simulateSavePlaceFlow({
  existingTripId = null,
  newTripTitle = '',
  dayNumber = 1,
  placeId,
  createTripFn,
  addItineraryFn,
}) {
  const result = {
    createdPendingTripId: existingTripId,
    banner: null,
    saved: false,
    sheetOpen: true,
    createTripCalls: 0,
    addItineraryCalls: 0,
  };

  const runOnce = async () => {
    if (!result.createdPendingTripId) {
      const trimmedTitle = String(newTripTitle || '').trim();
      if (!trimmedTitle) {
        result.banner = {
          tone: 'error',
          message: 'Vui lòng nhập tên chuyến đi mới.',
        };
        return result;
      }
      result.createTripCalls += 1;
      const created = await createTripFn({ title: trimmedTitle });
      if (!created.ok) {
        result.banner = {
          tone: created.networkError || created.status >= 500 ? 'warning' : 'error',
          message: created.message || 'Không thể tạo chuyến đi.',
        };
        return result;
      }
      result.createdPendingTripId = created.tripId;
    }

    result.addItineraryCalls += 1;
    const added = await addItineraryFn({
      tripId: result.createdPendingTripId,
      dayNumber,
      placeId,
    });
    if (!added.ok) {
      result.banner = {
        tone: added.networkError || added.status >= 500 ? 'warning' : 'error',
        message: added.message || 'Mất kết nối khi lưu địa điểm.',
      };
      return result;
    }

    result.saved = true;
    result.sheetOpen = false;
    result.banner = null;
    return result;
  };

  return { state: result, attempt: runOnce };
}

export function evaluateYoutubeFreshnessUi(apiData, { clientRenderedAtMs = Date.now() } = {}) {
  const poiItems = Array.isArray(apiData?.items) ? apiData.items : [];
  const cityFallbackItems = Array.isArray(apiData?.cityFallbackItems)
    ? apiData.cityFallbackItems
    : [];
  const slaMaxMs = apiData?.realtimeSlaMaxLatencyMs ?? 300000;

  const mapItem = (item) => {
    const badge = computeFreshnessBadge(item.publishedAt, clientRenderedAtMs, slaMaxMs);
    return {
      placeId: item.placeId ?? null,
      scope: item.scope,
      source: item.source,
      publishedAt: item.publishedAt,
      receivedAt: item.receivedAt,
      updatedAt: item.updatedAt ?? item.sourceUpdatedAt ?? item.lastReceivedAt ?? item.receivedAt,
      channelTitle: item.channelTitle || 'Kênh YouTube du lịch',
      videoUrl: item.videoUrl,
      ingestLatencyMs: item.ingestLatencyMs ?? 0,
      endToEndLatencyMs: badge.endToEndLatencyMs,
      clampedFromNegative: badge.clampedFromNegative,
      badgeLabel: badge.label,
    };
  };

  const renderedPoiItems = poiItems.map(mapItem);
  const renderedCityItems = cityFallbackItems.map(mapItem);

  return {
    primarySection: renderedPoiItems.length > 0 ? 'POI' : renderedCityItems.length > 0 ? 'CITY_FALLBACK' : 'EMPTY',
    showCityFallbackBanner: renderedPoiItems.length === 0 && renderedCityItems.length > 0,
    poiItems: renderedPoiItems,
    cityFallbackItems: renderedCityItems,
  };
}

export function parsePngDimensions(pngPath) {
  assert.ok(fs.existsSync(pngPath), `PNG screenshot missing: ${pngPath}`);
  const buf = fs.readFileSync(pngPath);
  assert.ok(buf.length >= 24, `PNG file too small: ${pngPath}`);
  const sig = buf.subarray(0, 8);
  const expectedSig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  assert.ok(sig.equals(expectedSig), `Invalid PNG signature: ${pngPath}`);
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height };
}

export function detectBetaMobileTree(mobileDir) {
  if (!mobileDir || !fs.existsSync(mobileDir)) return false;
  const betaMarkers = [
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.sharedWidgetsFile),
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.forgotPasswordScreen),
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.resetPasswordScreen),
  ];
  return betaMarkers.every((p) => fs.existsSync(p));
}

export function verifyBaseline10126b1Hooks(mobileDir) {
  const results = [];
  for (const entry of MOBILE_SPEC.baseline10126b1Checks) {
    const absPath = path.join(mobileDir, entry.file);
    assert.ok(fs.existsSync(absPath), `Baseline Flutter file missing: ${absPath}`);
    const content = fs.readFileSync(absPath, 'utf8');
    for (const token of entry.tokens) {
      assert.ok(
        content.includes(token),
        `Baseline hook "${token}" missing from ${entry.file}`,
      );
    }
    results.push({ file: entry.file, verifiedTokens: entry.tokens.length });
  }
  return results;
}

export function verifyBetaDartDeliverables(mobileDir, repoRoot) {
  const d = MOBILE_SPEC.betaRequiredDeliverables;
  const textFieldPath = path.join(mobileDir, d.sharedWidgetsFile);
  assert.ok(fs.existsSync(textFieldPath), `Missing Beta widget: ${textFieldPath}`);
  const widgetsBarrelPath = path.join(mobileDir, d.widgetsBarrel);
  const barrelText = fs.readFileSync(widgetsBarrelPath, 'utf8');
  assert.ok(barrelText.includes('app_text_field.dart'), 'widgets.dart must export app_text_field.dart');

  const apiClientText = fs.readFileSync(path.join(mobileDir, 'lib/core/network/api_client.dart'), 'utf8');
  for (const pubPath of MOBILE_SPEC.publicAuthPaths) {
    assert.ok(
      apiClientText.includes(`'${pubPath}'`) || apiClientText.includes(`"${pubPath}"`),
      `_publicAuthPaths missing ${pubPath}`,
    );
  }

  const routerText = fs.readFileSync(path.join(mobileDir, 'lib/core/router/app_router.dart'), 'utf8');
  for (const routeToken of ['/forgot-password', '/reset-password', 'sanitizeInternalRedirect']) {
    assert.ok(routerText.includes(routeToken), `app_router.dart missing ${routeToken}`);
  }

  for (const screen of [...MOBILE_SPEC.coreScreens, ...MOBILE_SPEC.authScreens]) {
    const screenPath = path.join(mobileDir, screen.file);
    assert.ok(fs.existsSync(screenPath), `Missing screen file: ${screenPath}`);
    const screenText = fs.readFileSync(screenPath, 'utf8');
    if (screen.route.startsWith('/login') || screen.route.startsWith('/register') || screen.route.startsWith('/forgot') || screen.route.startsWith('/reset')) {
      assert.ok(
        screenText.includes('AppTextField'),
        `${screen.name} must use shared AppTextField`,
      );
      assert.ok(
        screenText.includes('AppButton'),
        `${screen.name} must use shared AppButton`,
      );
      assert.ok(
        !screenText.includes('ElevatedButton('),
        `${screen.name} must not use raw ElevatedButton`,
      );
    }
  }

  const placeDetailText = fs.readFileSync(
    path.join(mobileDir, 'lib/features/places/presentation/place_detail_screen.dart'),
    'utf8',
  );
  const placeFeatureFiles = [placeDetailText];
  const youtubeSectionCandidate = path.join(
    mobileDir,
    'lib/features/places/presentation/widgets/youtube_freshness_section.dart',
  );
  if (fs.existsSync(youtubeSectionCandidate)) {
    placeFeatureFiles.push(fs.readFileSync(youtubeSectionCandidate, 'utf8'));
  }
  const combinedPlaceUi = placeFeatureFiles.join('\n');
  assert.ok(
    combinedPlaceUi.includes(d.youtubeLabels.realtime) &&
      combinedPlaceUi.includes(d.youtubeLabels.recent),
    'PlaceDetail / YoutubeFreshnessSection must distinguish Thời gian thực vs Cập nhật gần đây',
  );

  const perfTestPath = path.join(mobileDir, d.perfBenchmarkTest);
  const perfDriverPath = path.join(mobileDir, d.perfDriver);
  assert.ok(fs.existsSync(perfTestPath), `Missing perf benchmark test: ${perfTestPath}`);
  assert.ok(fs.existsSync(perfDriverPath), `Missing perf driver: ${perfDriverPath}`);

  const screenshotDir = path.join(repoRoot, d.screenshotDirRelativeToRepo);
  let screenshotCount = 0;
  if (fs.existsSync(screenshotDir)) {
    const pngs = fs.readdirSync(screenshotDir).filter((f) => f.toLowerCase().endsWith('.png'));
    for (const file of pngs) {
      const dims = parsePngDimensions(path.join(screenshotDir, file));
      assert.ok(dims.width > 0 && dims.height > 0, `Invalid PNG dimensions in ${file}`);
      screenshotCount += 1;
    }
  }

  return {
    isBetaTree: true,
    publicAuthPathsVerified: MOBILE_SPEC.publicAuthPaths.length,
    screenshotCount,
  };
}

export function runFlutterTestsIfRequested(mobileDir, runFlutter) {
  if (!runFlutter) {
    return { executed: false };
  }
  const res = spawnSync('flutter', ['test'], {
    cwd: mobileDir,
    encoding: 'utf8',
    shell: process.platform === 'win32',
  });
  assert.equal(res.status, 0, `flutter test failed in ${mobileDir}:\n${res.stdout}\n${res.stderr}`);
  return { executed: true, exitCode: res.status };
}
