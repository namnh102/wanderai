import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const SPEC_PATH = new URL('../fixtures/mobile_contract_spec.json', import.meta.url);
const MOBILE_SPEC = JSON.parse(fs.readFileSync(SPEC_PATH, 'utf8'));

export function getMobileContractSpec() {
  return MOBILE_SPEC;
}

function normVfsPath(p) {
  return path.resolve(p).replace(/\\/g, '/').replace(/\/+$/, '');
}

/**
 * Pure in-memory virtual filesystem matching the subset of `node:fs` used by
 * the contract verifiers (`existsSync`, `readFileSync`, `readdirSync`), so
 * negative verification tests run in memory with zero temp files on disk.
 */
export function createMemoryFs(initialFiles = {}) {
  const fileMap = new Map();
  const dirSet = new Set();

  const registerDir = (dirPath) => {
    let cur = normVfsPath(dirPath);
    while (cur && !dirSet.has(cur)) {
      dirSet.add(cur);
      const idx = cur.lastIndexOf('/');
      if (idx <= 0) break;
      const parent = cur.slice(0, idx);
      if (parent === cur || /^[A-Za-z]:$/.test(parent)) {
        dirSet.add(parent);
        break;
      }
      cur = parent;
    }
  };

  for (const [rawPath, content] of Object.entries(initialFiles)) {
    const norm = normVfsPath(rawPath);
    fileMap.set(norm, Buffer.isBuffer(content) ? content : Buffer.from(String(content), 'utf8'));
    const idx = norm.lastIndexOf('/');
    if (idx > 0) registerDir(norm.slice(0, idx));
  }

  return {
    existsSync(target) {
      const norm = normVfsPath(target);
      return fileMap.has(norm) || dirSet.has(norm);
    },
    readFileSync(target, encoding) {
      const norm = normVfsPath(target);
      if (!fileMap.has(norm)) {
        throw new Error(`ENOENT: no such file in VFS: ${target}`);
      }
      const buf = fileMap.get(norm);
      return encoding ? buf.toString(encoding) : buf;
    },
    readdirSync(target, opts = {}) {
      const norm = normVfsPath(target);
      if (!dirSet.has(norm)) {
        throw new Error(`ENOENT: no such directory in VFS: ${target}`);
      }
      const prefix = `${norm}/`;
      const children = new Map();
      for (const f of fileMap.keys()) {
        if (!f.startsWith(prefix)) continue;
        const rest = f.slice(prefix.length);
        const slash = rest.indexOf('/');
        if (slash === -1) {
          children.set(rest, { name: rest, isFile: () => true, isDirectory: () => false });
        } else {
          const dirName = rest.slice(0, slash);
          if (!children.has(dirName)) {
            children.set(dirName, { name: dirName, isFile: () => false, isDirectory: () => true });
          }
        }
      }
      for (const d of dirSet) {
        if (!d.startsWith(prefix)) continue;
        const rest = d.slice(prefix.length);
        if (rest && !rest.includes('/') && !children.has(rest)) {
          children.set(rest, { name: rest, isFile: () => false, isDirectory: () => true });
        }
      }
      const vals = [...children.values()];
      return opts && opts.withFileTypes ? vals : vals.map((e) => e.name);
    },
  };
}

export function buildPngHeaderBuffer(width, height) {
  const buf = Buffer.alloc(32);
  // PNG magic
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(buf, 0);
  // IHDR chunk length = 13
  buf.writeUInt32BE(13, 8);
  buf.write('IHDR', 12, 4, 'ascii');
  buf.writeUInt32BE(width, 16);
  buf.writeUInt32BE(height, 20);
  return buf;
}

export function parsePngDimensionsFromBuffer(buf, label = 'buffer') {
  assert.ok(Buffer.isBuffer(buf) && buf.length >= 24, `PNG file too small: ${label}`);
  const sig = buf.subarray(0, 8);
  const expectedSig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  assert.ok(sig.equals(expectedSig), `Invalid PNG signature: ${label}`);
  assert.equal(buf.toString('ascii', 12, 16), 'IHDR', `Invalid PNG IHDR chunk: ${label}`);
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  assert.ok(width > 0 && height > 0, `Invalid PNG dimensions (${width}x${height}): ${label}`);
  return { width, height };
}

export function parsePngDimensions(pngPath, fsImpl = fs) {
  assert.ok(fsImpl.existsSync(pngPath), `PNG screenshot missing: ${pngPath}`);
  const buf = fsImpl.readFileSync(pngPath);
  return parsePngDimensionsFromBuffer(buf, pngPath);
}

function walkPngsRecursive(dir, rootDir, fsImpl, acc = []) {
  const entries = fsImpl.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkPngsRecursive(full, rootDir, fsImpl, acc);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.png')) {
      acc.push(path.relative(rootDir, full).replace(/\\/g, '/'));
    }
  }
  return acc;
}

export function verifyScreenshots(repoRoot, opts = {}) {
  const {
    fsImpl = fs,
    requireFiles = true,
    expectedWidth = MOBILE_SPEC.betaRequiredDeliverables.screenshotDimensions.width,
    expectedHeight = MOBILE_SPEC.betaRequiredDeliverables.screenshotDimensions.height,
  } = opts;

  const screenshotDir = path.join(
    repoRoot,
    MOBILE_SPEC.betaRequiredDeliverables.screenshotDirRelativeToRepo,
  );
  if (!fsImpl.existsSync(screenshotDir)) {
    if (requireFiles) {
      assert.fail(`Missing Beta mobile screenshot directory: ${screenshotDir}`);
    }
    return { count: 0, beforeCount: 0, afterCount: 0, files: [] };
  }

  const pngRelPaths = walkPngsRecursive(screenshotDir, screenshotDir, fsImpl).sort();
  assert.ok(pngRelPaths.length > 0, `No PNG screenshots found under ${screenshotDir}`);

  const beforePngs = pngRelPaths.filter((p) => p.toLowerCase().includes('before'));
  const afterPngs = pngRelPaths.filter((p) => p.toLowerCase().includes('after'));
  assert.ok(
    beforePngs.length > 0 && afterPngs.length > 0,
    `Both before and after PNG screenshots are required under ${screenshotDir} (before=${beforePngs.length}, after=${afterPngs.length})`,
  );

  for (const rel of pngRelPaths) {
    const dims = parsePngDimensions(path.join(screenshotDir, rel), fsImpl);
    assert.equal(
      dims.width,
      expectedWidth,
      `Screenshot ${rel} width ${dims.width} !== expected ${expectedWidth}`,
    );
    assert.equal(
      dims.height,
      expectedHeight,
      `Screenshot ${rel} height ${dims.height} !== expected ${expectedHeight}`,
    );
  }

  const requiredCoreFragments = [
    'login',
    'register',
    'home',
    'place_detail',
    'save_place',
    'trip_list',
    'trip_detail',
  ];
  const beforeNames = beforePngs.map((p) => path.basename(p).toLowerCase());
  const afterNames = afterPngs.map((p) => path.basename(p).toLowerCase());

  for (const frag of requiredCoreFragments) {
    assert.ok(
      beforeNames.some((n) => n.includes(frag)),
      `Before screenshots missing journey coverage for "${frag}"`,
    );
    assert.ok(
      afterNames.some((n) => n.includes(frag)),
      `After screenshots missing journey coverage for "${frag}"`,
    );
  }
  for (const authFrag of ['forgot_password', 'reset_password']) {
    assert.ok(
      afterNames.some((n) => n.includes(authFrag)),
      `After screenshots missing auth screen coverage for "${authFrag}"`,
    );
  }

  return {
    count: pngRelPaths.length,
    beforeCount: beforePngs.length,
    afterCount: afterPngs.length,
    files: pngRelPaths,
  };
}

function validatePerfJsonArtifact(jsonPath, fsImpl) {
  assert.ok(fsImpl.existsSync(jsonPath), `Missing perf benchmark JSON artifact: ${jsonPath}`);
  const parsed = JSON.parse(fsImpl.readFileSync(jsonPath, 'utf8'));
  assert.ok(parsed && typeof parsed === 'object', `Invalid perf JSON in ${jsonPath}`);
  assert.ok(
    parsed.custom_metrics && typeof parsed.custom_metrics === 'object',
    `${jsonPath} missing custom_metrics`,
  );
  for (const metricKey of ['dest_sheet_open_ms', 'trip_list_open_ms', 'trip_detail_open_ms']) {
    assert.equal(
      typeof parsed.custom_metrics[metricKey],
      'number',
      `${jsonPath} custom_metrics.${metricKey} must be numeric`,
    );
  }
  assert.ok(
    parsed.scroll_timelines && typeof parsed.scroll_timelines === 'object',
    `${jsonPath} missing scroll_timelines`,
  );
  for (const tlKey of ['dest_sheet_scroll', 'trip_list_scroll', 'trip_detail_scroll']) {
    assert.ok(
      parsed.scroll_timelines[tlKey] && typeof parsed.scroll_timelines[tlKey] === 'object',
      `${jsonPath} missing scroll_timelines.${tlKey}`,
    );
  }
  return parsed;
}

export function verifyPerfBenchmarkArtifacts(
  mobileDir,
  repoRoot,
  { requireAfterPerf = false, fsImpl = fs } = {},
) {
  const d = MOBILE_SPEC.betaRequiredDeliverables;
  const perfTestPath = path.join(mobileDir, d.perfBenchmarkTest);
  const perfDriverPath = path.join(mobileDir, d.perfDriver);
  assert.ok(fsImpl.existsSync(perfTestPath), `Missing perf benchmark test: ${perfTestPath}`);
  assert.ok(fsImpl.existsSync(perfDriverPath), `Missing perf driver: ${perfDriverPath}`);

  const perfTestText = fsImpl.readFileSync(perfTestPath, 'utf8');
  for (const token of [
    'IntegrationTestWidgetsFlutterBinding',
    'traceAction',
    'dest_sheet_scroll',
    'trip_list_scroll',
    'trip_detail_scroll',
    'custom_metrics',
  ]) {
    assert.ok(perfTestText.includes(token), `perf_benchmark_test.dart missing "${token}"`);
  }

  const perfDriverText = fsImpl.readFileSync(perfDriverPath, 'utf8');
  for (const token of ['TimelineSummary.summarize', 'scroll_timelines']) {
    assert.ok(perfDriverText.includes(token), `perf_driver.dart missing "${token}"`);
  }

  const benchDir = path.join(repoRoot, d.screenshotDirRelativeToRepo, 'benchmarks');
  const beforePerfPath = path.join(benchDir, 'before_perf.json');
  const beforePerf = validatePerfJsonArtifact(beforePerfPath, fsImpl);

  const afterPerfPath = path.join(benchDir, 'after_perf.json');
  let afterPerf = null;
  if (requireAfterPerf || fsImpl.existsSync(afterPerfPath)) {
    afterPerf = validatePerfJsonArtifact(afterPerfPath, fsImpl);
  }

  return {
    perfTestPath,
    perfDriverPath,
    beforePerf,
    afterPerf,
  };
}

export function detectBetaMobileTree(mobileDir, fsImpl = fs) {
  if (!mobileDir || !fsImpl.existsSync(mobileDir)) return false;
  const betaMarkers = [
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.sharedWidgetsFile),
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.forgotPasswordScreen),
    path.join(mobileDir, MOBILE_SPEC.betaRequiredDeliverables.resetPasswordScreen),
  ];
  return betaMarkers.every((p) => fsImpl.existsSync(p));
}

function assertFileContainsTokens(mobileDir, relFile, tokens, fsImpl = fs) {
  const absPath = path.join(mobileDir, relFile);
  assert.ok(fsImpl.existsSync(absPath), `Flutter file missing: ${absPath}`);
  const content = fsImpl.readFileSync(absPath, 'utf8');
  for (const token of tokens) {
    assert.ok(content.includes(token), `Expected token "${token}" missing from ${relFile}`);
  }
  return content;
}

export function verifyBaseline10126b1Hooks(mobileDir, { fsImpl = fs } = {}) {
  const results = [];
  for (const entry of MOBILE_SPEC.baseline10126b1Checks) {
    assertFileContainsTokens(mobileDir, entry.file, entry.tokens, fsImpl);
    results.push({ file: entry.file, verifiedTokens: entry.tokens.length });
  }

  const extraDartChecks = [
    {
      file: 'lib/core/widgets/app_button.dart',
      tokens: ['isLoading', 'enabled = onPressed != null && !isLoading', 'onTap: enabled ? onPressed : null'],
    },
    {
      file: 'lib/core/widgets/app_state_banner.dart',
      tokens: ['enum AppStateBannerTone', 'Expanded', 'actionLabel != null && onAction != null'],
    },
    {
      file: 'lib/core/widgets/app_error_state.dart',
      tokens: ['onRetry', 'AppButton', "'Thử lại'"],
    },
    {
      file: 'lib/core/widgets/app_loading.dart',
      tokens: ['class AppLoading', 'isCompact'],
    },
    {
      file: 'lib/core/widgets/responsive_wrapper.dart',
      tokens: ['ConstrainedBox', 'maxWidth'],
    },
    {
      file: 'lib/core/constants/app_constants.dart',
      tokens: ['resolveApiBaseUrl', 'validateAndNormalizeApiBaseUrl', '_disallowedReleaseHosts', 'StateError', 'FormatException'],
    },
    {
      file: 'lib/core/router/app_router.dart',
      tokens: ['sanitizeInternalRedirect', 'parsed.hasScheme', 'parsed.hasAuthority', "'/login'", "'/register'", 'guestBrowseModeProvider', 'postLoginRedirectProvider', 'resolvePostAuthDestination'],
    },
    {
      file: 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart',
      tokens: ['_createdPendingTrip', 'rawTitle.isEmpty', "'Vui lòng nhập tên chuyến đi mới.'", 'statusCode == 401', 'postLoginRedirectProvider'],
    },
  ];
  for (const item of extraDartChecks) {
    assertFileContainsTokens(mobileDir, item.file, item.tokens, fsImpl);
  }

  const requiredDartTests = [
    'test/api_config_test.dart',
    'test/halong_trip_save_journey_test.dart',
    'test/design_system_and_map_stability_test.dart',
    'test/auth_test.dart',
    'test/place_detail_test.dart',
    'test/trips_test.dart',
    'test/ux_v2_wave_b_test.dart',
  ];
  for (const relTest of requiredDartTests) {
    const abs = path.join(mobileDir, relTest);
    assert.ok(fsImpl.existsSync(abs), `Required Dart test missing: ${abs}`);
  }

  return results;
}

export function verifyBetaDartDeliverables(mobileDir, repoRoot, opts = {}) {
  const {
    requireScreenshots = true,
    requireM4Youtube = true,
    requireAfterPerf = false,
    fsImpl = fs,
  } = opts;
  const d = MOBILE_SPEC.betaRequiredDeliverables;

  // 1. AppTextField + widgets.dart barrel
  assertFileContainsTokens(
    mobileDir,
    d.sharedWidgetsFile,
    ['TextFormField', 'obscureText', 'showPasswordToggle', 'validator', 'controller: widget.controller'],
    fsImpl,
  );
  assertFileContainsTokens(mobileDir, d.widgetsBarrel, ['app_text_field.dart'], fsImpl);

  // 2. Public auth paths in ApiClient
  const apiClientText = fsImpl.readFileSync(
    path.join(mobileDir, 'lib/core/network/api_client.dart'),
    'utf8',
  );
  for (const pubPath of MOBILE_SPEC.publicAuthPaths) {
    assert.ok(
      apiClientText.includes(`'${pubPath}'`) || apiClientText.includes(`"${pubPath}"`),
      `_publicAuthPaths missing ${pubPath}`,
    );
  }

  // 3. AppRouter forgot/reset routes & auth-loop sanitizer
  assertFileContainsTokens(
    mobileDir,
    'lib/core/router/app_router.dart',
    ['/forgot-password', '/reset-password', 'sanitizeInternalRedirect', 'parsed.hasScheme', 'parsed.hasAuthority', "'/login'", "'/register'"],
    fsImpl,
  );

  // 4. All 4 Auth Screens + cancel labels + AuthSocialPort
  const authScreenRules = [
    {
      file: 'lib/features/auth/presentation/login_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppStateBanner', 'showPasswordToggle: true', 'postLoginRedirectProvider', 'guestBrowseModeProvider', 'login_google_button', 'login_facebook_button'],
      requireCancelLabel: true,
    },
    {
      file: 'lib/features/auth/presentation/register_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppStateBanner', 'showPasswordToggle: true', 'postLoginRedirectProvider', 'guestBrowseModeProvider'],
      requireCancelLabel: true,
    },
    {
      file: 'lib/features/auth/presentation/forgot_password_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppStateBanner'],
      requireCancelLabel: false,
    },
    {
      file: 'lib/features/auth/presentation/reset_password_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppLoading', 'AppStateBanner', 'showPasswordToggle: true'],
      requireCancelLabel: false,
    },
  ];
  for (const rule of authScreenRules) {
    const content = assertFileContainsTokens(mobileDir, rule.file, rule.tokens, fsImpl);
    assert.ok(!content.includes('ElevatedButton('), `${rule.file} must not use raw ElevatedButton(`);
    if (rule.requireCancelLabel) {
      assert.ok(
        d.cancelLoginLabels.some((lbl) => content.includes(lbl)),
        `${rule.file} must include cancel-login label (${d.cancelLoginLabels.join(' / ')})`,
      );
    }
  }

  assertFileContainsTokens(
    mobileDir,
    'lib/features/auth/data/auth_social_port.dart',
    ['signInWithGoogle', 'signInWithFacebook', 'SocialAuthSuccess', 'SocialAuthCancelled', 'SocialAuthFailure'],
    fsImpl,
  );
  assertFileContainsTokens(
    mobileDir,
    'lib/features/auth/providers/auth_provider.dart',
    ['SocialAuthCancelled', 'AuthActionResult.cancelled', 'loginWithGoogle', 'loginWithFacebook'],
    fsImpl,
  );
  assertFileContainsTokens(
    mobileDir,
    'test/auth_reset_and_oauth_test.dart',
    ['RESET_TOKEN_EXPIRED', 'RESET_TOKEN_USED', 'RESET_TOKEN_INVALID', 'OAUTH_EMAIL_UNAVAILABLE', 'SocialAuthCancelled'],
    fsImpl,
  );

  // 5. All 4 Core Screens + Sheets shared widget matrix (zero ElevatedButton)
  const coreScreenRules = [
    {
      file: 'lib/features/home/presentation/home_screen.dart',
      tokens: ['AppButton', 'AppLoading', 'AppErrorState', 'AppStateBanner'],
    },
    {
      file: 'lib/features/map/presentation/map_screen.dart',
      tokens: ['AppLoading', 'AppStateBanner'],
    },
    {
      file: 'lib/features/map/presentation/widgets/place_preview_sheet.dart',
      tokens: ['AppButton'],
    },
    {
      file: 'lib/features/places/presentation/place_detail_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppLoading', 'AppErrorState', 'AppStateBanner'],
    },
    {
      file: 'lib/features/places/presentation/widgets/save_place_to_trip_sheet.dart',
      tokens: ['AppTextField', 'AppButton', 'AppLoading', 'AppStateBanner', '_createdPendingTrip'],
    },
    {
      file: 'lib/features/trips/presentation/trip_list_screen.dart',
      tokens: ['AppLoading', 'AppErrorState'],
    },
    {
      file: 'lib/features/trips/presentation/trip_detail_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppLoading', 'AppErrorState'],
    },
    {
      file: 'lib/features/trips/presentation/trip_form_screen.dart',
      tokens: ['AppTextField', 'AppButton', 'AppStateBanner'],
    },
  ];
  for (const rule of coreScreenRules) {
    const content = assertFileContainsTokens(mobileDir, rule.file, rule.tokens, fsImpl);
    assert.ok(!content.includes('ElevatedButton('), `${rule.file} must not use raw ElevatedButton(`);
  }

  // 6. M4 YouTube Freshness UI (F9)
  if (requireM4Youtube) {
    const m4CandidateFiles = [
      'lib/features/places/presentation/place_detail_screen.dart',
      'lib/features/places/presentation/widgets/youtube_freshness_section.dart',
      'lib/features/places/data/youtube_models.dart',
      'lib/features/places/data/youtube_repository.dart',
    ];
    const m4Texts = [];
    for (const rel of m4CandidateFiles) {
      const abs = path.join(mobileDir, rel);
      if (fsImpl.existsSync(abs)) {
        m4Texts.push(fsImpl.readFileSync(abs, 'utf8'));
      }
    }
    const combinedM4 = m4Texts.join('\n');
    for (const field of ['placeId', 'source', 'publishedAt', 'receivedAt', 'updatedAt']) {
      assert.ok(
        combinedM4.includes(field),
        `M4 YouTube UI/models missing mandated field "${field}"`,
      );
    }
    assert.ok(
      combinedM4.includes('cityFallbackItems') &&
        (combinedM4.includes('scope') || combinedM4.includes("'CITY'")),
      'M4 YouTube UI/models missing Hạ Long city-level fallback handling',
    );
    assert.ok(
      combinedM4.includes('realtimeSlaMaxLatencyMs') || combinedM4.includes('300000'),
      'M4 YouTube UI/models missing 300000ms SLA check',
    );
    assert.ok(
      combinedM4.includes(d.youtubeLabels.realtime) &&
        combinedM4.includes(d.youtubeLabels.recent),
      'PlaceDetail / YoutubeFreshnessSection must distinguish Thời gian thực vs Cập nhật gần đây',
    );
    assert.ok(
      combinedM4.includes('< 0') || combinedM4.includes('clamp(') || combinedM4.includes('max(0'),
      'M4 YouTube UI/models must clamp negative latency to >= 0',
    );
  }

  // 7. Screenshots & Perf Benchmarks
  const screenshots = verifyScreenshots(repoRoot, {
    fsImpl,
    requireFiles: requireScreenshots,
  });
  const perf = verifyPerfBenchmarkArtifacts(mobileDir, repoRoot, {
    fsImpl,
    requireAfterPerf,
  });

  return {
    isBetaTree: true,
    publicAuthPathsVerified: MOBILE_SPEC.publicAuthPaths.length,
    screenshotCount: screenshots.count,
    beforeScreenshots: screenshots.beforeCount,
    afterScreenshots: screenshots.afterCount,
    perfVerified: Boolean(perf.beforePerf),
  };
}

let inProcessFlutterCache = null;

export function runFlutterTestsOnce(mobileDir, { mode = 'self-test' } = {}) {
  const hasPkgConfig = fs.existsSync(path.join(mobileDir, '.dart_tool', 'package_config.json'));
  const args = ['test', ...(hasPkgConfig ? ['--no-pub'] : []), '--reporter', 'expanded'];
  const res = spawnSync('flutter', args, {
    cwd: mobileDir,
    encoding: 'utf8',
    shell: process.platform === 'win32',
    maxBuffer: 16 * 1024 * 1024,
  });

  const combinedOut = `${res.stdout || ''}\n${res.stderr || ''}`;
  const lines = combinedOut.split(/\r?\n/).filter(Boolean);
  const tail = lines.slice(-25).join('\n');

  let passedCount = 0;
  let skippedCount = 0;
  for (const line of lines) {
    const m = line.match(/\+(\d+)(?:\s+~(\d+))?/);
    if (m) {
      passedCount = Number(m[1]);
      if (m[2]) skippedCount = Number(m[2]);
    }
  }

  const testDir = path.join(mobileDir, 'test');
  const testedFiles = fs.existsSync(testDir)
    ? fs.readdirSync(testDir).filter((f) => f.endsWith('_test.dart')).length
    : 0;

  return {
    executed: true,
    mode,
    exitCode: res.status ?? 1,
    passedCount,
    skippedCount,
    testedFiles,
    stdoutTail: tail,
  };
}

export function getFlutterTestResult(
  mobileDir,
  { requireExecuted = false, runIfMissing = false, mode = 'self-test' } = {},
) {
  let result = null;
  if (process.env.E2E_FLUTTER_TEST_RESULT) {
    result = JSON.parse(process.env.E2E_FLUTTER_TEST_RESULT);
  } else if (inProcessFlutterCache) {
    result = inProcessFlutterCache;
  } else if (runIfMissing) {
    result = runFlutterTestsOnce(mobileDir, { mode });
    inProcessFlutterCache = result;
  } else {
    result = { executed: false };
  }

  if (requireExecuted) {
    assert.equal(
      result.executed,
      true,
      'Flutter test execution is required in this mode (omit --skip-flutter or pass --run-flutter)',
    );
    assert.equal(
      result.exitCode,
      0,
      `flutter test failed in ${mobileDir}:\n${result.stdoutTail || ''}`,
    );
  }
  return result;
}
