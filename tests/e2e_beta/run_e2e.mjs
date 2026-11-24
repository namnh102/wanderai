import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { run } from 'node:test';
import { spec as SpecReporter } from 'node:test/reporters';
import { parseCliArgs } from './lib/cli_args.mjs';
import { startMockServer } from './lib/mock_server.mjs';
import { runFlutterTestsOnce } from './lib/mobile_contract_verifier.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TIER_FILES = {
  '1': path.join(__dirname, 'suites', 'tier1_feature_coverage.test.mjs'),
  '2': path.join(__dirname, 'suites', 'tier2_boundary_corners.test.mjs'),
  '3': path.join(__dirname, 'suites', 'tier3_cross_feature.test.mjs'),
  '4': path.join(__dirname, 'suites', 'tier4_real_world_journeys.test.mjs'),
};

function printHelp() {
  console.log(`WanderAI Beta Opaque-Box E2E Runner (Node 22 Zero-Dependency)

Usage:
  node tests/e2e_beta/run_e2e.mjs [options]

Options:
  --mode=self-test|live      Execution mode (default: self-test)
  --base-url=<url>           Live backend base URL (required in --mode=live)
  --tier=1|2|3|4|all         Tier selection (default: all)
  --repo-root=<path>         Repository root for W07 SHA-256 & git checks
  --mobile-dir=<path>        Flutter mobile directory (default: <repo-root>/apps/mobile)
  --w07-prep-dir=<path>      Sibling w07_offline_retrieval_prep path
  --run-flutter              Execute "flutter test" once in --mode=self-test
  --skip-flutter             Skip automatic "flutter test" in --mode=live
  --youtube-secret=<secret>  x-youtube-internal-secret header value
  --websub-secret=<secret>   YOUTUBE_WEBSUB_SECRET HMAC signing key
  --report=<path>            Write JSON summary report to file
  --help, -h                 Show this help message
`);
}

async function main() {
  let options;
  try {
    options = parseCliArgs(process.argv.slice(2));
  } catch (err) {
    console.error(`[run_e2e] Argument error: ${err.message}`);
    process.exit(1);
  }

  if (options.help) {
    printHelp();
    process.exit(0);
  }

  let mockServer = null;
  const startedAt = new Date().toISOString();
  const startMs = Date.now();

  try {
    let targetBaseUrl = options.baseUrl;
    if (options.mode === 'self-test') {
      mockServer = await startMockServer({
        youtubeSecret: options.youtubeSecret,
        websubSecret: options.websubSecret,
      });
      targetBaseUrl = mockServer.baseUrl;
    }

    process.env.E2E_MODE = options.mode;
    process.env.E2E_TIER = options.tier;
    process.env.E2E_BASE_URL = targetBaseUrl;
    process.env.E2E_REPO_ROOT = options.repoRoot;
    process.env.E2E_MOBILE_DIR = options.mobileDir;
    process.env.E2E_W07_PREP_DIR = options.w07PrepDir;
    process.env.E2E_W07_PREP_DIR_EXPLICIT = options.w07PrepDirExplicit ? '1' : '0';
    process.env.E2E_RUN_FLUTTER = options.runFlutter ? '1' : '0';
    process.env.E2E_SKIP_FLUTTER = options.skipFlutter ? '1' : '0';
    process.env.E2E_SHOULD_RUN_FLUTTER = options.shouldRunFlutter ? '1' : '0';
    process.env.E2E_YOUTUBE_SECRET = options.youtubeSecret;
    process.env.E2E_WEBSUB_SECRET = options.websubSecret;

    if (options.shouldRunFlutter) {
      console.log(`[run_e2e] Running flutter test once in ${options.mobileDir}...`);
      const flutterResult = runFlutterTestsOnce(options.mobileDir, { mode: options.mode });
      process.env.E2E_FLUTTER_TEST_RESULT = JSON.stringify(flutterResult);
      console.log(
        `[run_e2e] flutter test exit=${flutterResult.exitCode} passed=${flutterResult.passedCount} skipped=${flutterResult.skippedCount} files=${flutterResult.testedFiles}`,
      );
      if (flutterResult.exitCode !== 0) {
        console.error(`[run_e2e] flutter test failed:\n${flutterResult.stdoutTail}`);
        process.exit(1);
      }
    } else {
      process.env.E2E_FLUTTER_TEST_RESULT = JSON.stringify({ executed: false });
    }

    const files =
      options.tier === 'all'
        ? [TIER_FILES['1'], TIER_FILES['2'], TIER_FILES['3'], TIER_FILES['4']]
        : [TIER_FILES[options.tier]];

    console.log(
      `[run_e2e] mode=${options.mode} tier=${options.tier} baseUrl=${targetBaseUrl} repoRoot=${options.repoRoot}`,
    );

    const summary = {
      mode: options.mode,
      tier: options.tier,
      baseUrl: targetBaseUrl,
      startedAt,
      passed: 0,
      failed: 0,
      skipped: 0,
      total: 0,
      failures: [],
    };

    const testStream = run({ files, concurrency: false });

    testStream.on('test:pass', (evt) => {
      if (evt.nesting > 0) {
        summary.passed += 1;
        summary.total += 1;
      }
    });
    testStream.on('test:fail', (evt) => {
      if (evt.nesting > 0) {
        summary.failed += 1;
        summary.total += 1;
        summary.failures.push({
          name: evt.name,
          file: evt.file,
          error: evt.details?.error?.message || String(evt.details?.error || 'Unknown failure'),
        });
      }
    });
    testStream.on('test:skip', (evt) => {
      if (evt.nesting > 0) {
        summary.skipped += 1;
        summary.total += 1;
      }
    });

    const reporter = new SpecReporter();
    testStream.compose(reporter).pipe(process.stdout);

    await new Promise((resolve, reject) => {
      testStream.on('end', resolve);
      testStream.on('error', reject);
    });

    summary.durationMs = Date.now() - startMs;
    summary.finishedAt = new Date().toISOString();

    if (options.report) {
      const reportPath = path.resolve(options.report);
      fs.mkdirSync(path.dirname(reportPath), { recursive: true });
      fs.writeFileSync(reportPath, JSON.stringify(summary, null, 2), 'utf8');
      console.log(`[run_e2e] Wrote JSON report to ${reportPath}`);
    }

    console.log(
      `\n[run_e2e] Summary: ${summary.passed}/${summary.total} passed, ${summary.failed} failed, ${summary.skipped} skipped (${summary.durationMs} ms)`,
    );

    if (summary.failed > 0 || summary.total === 0) {
      process.exitCode = 1;
    }
  } finally {
    if (mockServer) {
      await mockServer.close();
    }
  }
}

main().catch((err) => {
  console.error('[run_e2e] Fatal error:', err);
  process.exit(1);
});
