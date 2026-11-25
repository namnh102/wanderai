import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DEFAULT_REPO_ROOT = path.resolve(__dirname, '../../..');

export function parseCliArgs(argv = process.argv.slice(2), env = process.env) {
  const envW07Prep = env.WANDERAI_W07_PREP_DIR || env.E2E_W07_PREP_DIR || '';
  let cliW07PrepExplicit = false;

  const options = {
    mode: env.WANDERAI_E2E_MODE || env.E2E_MODE || 'self-test',
    baseUrl: env.WANDERAI_E2E_BASE_URL || env.E2E_BASE_URL || '',
    tier: env.WANDERAI_E2E_TIER || 'all',
    repoRoot: env.WANDERAI_REPO_ROOT || DEFAULT_REPO_ROOT,
    mobileDir: env.WANDERAI_MOBILE_DIR || '',
    w07PrepDir: envW07Prep,
    w07PrepDirExplicit: Boolean(envW07Prep),
    runFlutter: env.WANDERAI_RUN_FLUTTER === '1',
    skipFlutter: env.WANDERAI_SKIP_FLUTTER === '1',
    youtubeSecret: env.YOUTUBE_EVENTS_INTERNAL_SECRET || 'e2e-youtube-internal-secret',
    websubSecret: env.YOUTUBE_WEBSUB_SECRET || 'e2e-websub-hmac-secret',
    report: env.WANDERAI_E2E_REPORT || '',
    help: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      options.help = true;
      continue;
    }
    if (arg === '--run-flutter') {
      options.runFlutter = true;
      continue;
    }
    if (arg === '--skip-flutter') {
      options.skipFlutter = true;
      continue;
    }
    const [flag, inlineVal] = arg.includes('=')
      ? [arg.slice(0, arg.indexOf('=')), arg.slice(arg.indexOf('=') + 1)]
      : [arg, undefined];

    const consumeValue = () => {
      if (inlineVal !== undefined) return inlineVal;
      if (i + 1 < argv.length && !argv[i + 1].startsWith('--')) {
        i += 1;
        return argv[i];
      }
      throw new Error(`Missing value for CLI flag ${flag}`);
    };

    switch (flag) {
      case '--mode':
        options.mode = consumeValue();
        break;
      case '--base-url':
        options.baseUrl = consumeValue();
        break;
      case '--tier':
        options.tier = consumeValue();
        break;
      case '--repo-root':
        options.repoRoot = consumeValue();
        break;
      case '--mobile-dir':
        options.mobileDir = consumeValue();
        break;
      case '--w07-prep-dir':
        options.w07PrepDir = consumeValue();
        cliW07PrepExplicit = true;
        break;
      case '--youtube-secret':
        options.youtubeSecret = consumeValue();
        break;
      case '--websub-secret':
        options.websubSecret = consumeValue();
        break;
      case '--report':
        options.report = consumeValue();
        break;
      default:
        throw new Error(`Unknown CLI flag: ${arg}`);
    }
  }

  options.mode = String(options.mode).toLowerCase();
  if (options.mode !== 'self-test' && options.mode !== 'live') {
    throw new Error(`Invalid --mode="${options.mode}". Expected "self-test" or "live".`);
  }

  options.tier = String(options.tier).toLowerCase();
  if (!['1', '2', '3', '4', 'all'].includes(options.tier)) {
    throw new Error(`Invalid --tier="${options.tier}". Expected 1, 2, 3, 4, or all.`);
  }

  options.repoRoot = path.resolve(options.repoRoot);
  options.mobileDir = options.mobileDir
    ? path.resolve(options.mobileDir)
    : path.join(options.repoRoot, 'apps', 'mobile');
  options.w07PrepDirExplicit = Boolean(cliW07PrepExplicit || envW07Prep);
  options.w07PrepDir = options.w07PrepDir
    ? path.resolve(options.w07PrepDir)
    : path.resolve(options.repoRoot, '..', 'w07_offline_retrieval_prep');
  options.shouldRunFlutter =
    !options.skipFlutter && (options.mode === 'live' || options.runFlutter);

  if (options.mode === 'live' && !options.baseUrl) {
    throw new Error('Missing --base-url=<url> (required when --mode=live).');
  }

  if (options.baseUrl) {
    options.baseUrl = options.baseUrl.replace(/\/+$/, '');
  }

  return options;
}

export function getRuntimeConfig(env = process.env) {
  const mode = env.E2E_MODE || 'self-test';
  const repoRoot = path.resolve(env.E2E_REPO_ROOT || DEFAULT_REPO_ROOT);
  const mobileDir = path.resolve(
    env.E2E_MOBILE_DIR || path.join(repoRoot, 'apps', 'mobile'),
  );
  const w07PrepDir = path.resolve(
    env.E2E_W07_PREP_DIR || path.resolve(repoRoot, '..', 'w07_offline_retrieval_prep'),
  );
  const runFlutter = env.E2E_RUN_FLUTTER === '1';
  const skipFlutter = env.E2E_SKIP_FLUTTER === '1';
  const shouldRunFlutter =
    env.E2E_SHOULD_RUN_FLUTTER !== undefined
      ? env.E2E_SHOULD_RUN_FLUTTER === '1'
      : !skipFlutter && (mode === 'live' || runFlutter);

  return {
    mode,
    tier: env.E2E_TIER || 'all',
    baseUrl: (env.E2E_BASE_URL || '').replace(/\/+$/, ''),
    repoRoot,
    mobileDir,
    w07PrepDir,
    w07PrepDirExplicit: env.E2E_W07_PREP_DIR_EXPLICIT === '1',
    runFlutter,
    skipFlutter,
    shouldRunFlutter,
    youtubeSecret: env.YOUTUBE_EVENTS_INTERNAL_SECRET || env.E2E_YOUTUBE_SECRET || 'e2e-youtube-internal-secret',
    websubSecret: env.YOUTUBE_WEBSUB_SECRET || env.E2E_WEBSUB_SECRET || 'e2e-websub-hmac-secret',
  };
}
