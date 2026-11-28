# Developer Runbook (W3 — Reconciled Post-PR #90/#91/#92)

## Prerequisites
- **Runtime & Tooling:** Node.js 22 + `pnpm` 10, Python 3.11, Flutter (stable channel; Android SDK API 35 for Android builds), Git.
- **Local Services:** PostgreSQL 16 with `postgis`, `vector` (`pgvector`), and `uuid-ossp` extensions (`database/init.sql`) + Redis 7 (see `docker-compose.yml`).
- **Workspace Layout Note:** There is **no** root `pnpm-workspace.yaml`. Do not run `pnpm --filter wanderai-backend ...` from the repository root (`ERR_PNPM_NO_PROJECTS_FOUND`); either `cd apps/backend` first or run `pnpm --dir apps/backend <script>` from the repo root.

## Git / Line Endings & Frozen Artifacts
- `.gitattributes` enforces LF; you do not need to change `core.autocrlf`. Do not run mass `git add --renormalize`.
- Freeze V1/V2 artifacts and W06/W07 scientific records are immutable — never edit them. Verify tracked freeze checksums from the repo root with:
  ```bash
  python -m scripts.freeze_checksum --skip-missing-prefix=data/restricted/
  ```
  *(Omit `--skip-missing-prefix=data/restricted/` only when licensed git-ignored ViHoRec CSVs are present locally.)*

## Environment Variables
Copy `.env.example` from the repo root to `apps/backend/.env` and `apps/ai-service/.env` (`cp .env.example apps/backend/.env && cp .env.example apps/ai-service/.env`, or `cp ../../.env.example .env` from inside either service directory). Real secrets stay out of Git.

| Variable | Read by | Requirement & Fail-Closed Behavior |
|---|---|---|
| `DATABASE_URL` | `backend` (Prisma), `ai-service` (`asyncpg` in `app/rag/retriever.py` & `app/tools/search_places.py`), `scripts/` (`asyncpg`) | **Required** for runtime, RAG retrieval (`asyncpg` pool; SQLAlchemy/`psycopg2` are **not** used by `ai-service`), and DB-backed tests. Never point destructive CI scripts at the development `wanderai` database. |
| `JWT_SECRET`, `JWT_REFRESH_SECRET` (+ `JWT_EXPIRES_IN`, `JWT_REFRESH_EXPIRES_IN`) | `backend` (`jwt-config.ts`) | **Required (fail-closed at startup).** Each secret must be `>= 32` chars, have `>= 8` unique chars, reject placeholders/dev literals, and be strictly distinct from the other. |
| `AI_INTERNAL_AUTH_SECRET` | `backend` (`internal-auth.ts`), `ai-service` (`internal_auth.py`) | **Required for AI Chat (fail-closed `503` if missing/weak).** Must match across `backend` and `ai-service`, be `>= 32` chars with `>= 8` unique chars, non-placeholder, and strictly distinct from both `JWT_SECRET` and `JWT_REFRESH_SECRET`. Signs `X-WanderAI-Internal-Assertion` (`v1.*` HMAC-SHA256). |
| `AI_SERVICE_URL` | `backend` | **Required** (default `http://localhost:8000`). Keep FastAPI internal-only; never expose `:8000` publicly or to mobile clients. |
| `HOST`, `PORT` | `backend` (`network.config.ts`) | Optional in dev. `PORT` defaults to `3000` (`1..65535`). `.env.example` sets `HOST=127.0.0.1` for local loopback safety; set `HOST=0.0.0.0` when testing from a physical LAN device in debug mode. |
| `BACKEND_CORS_ORIGINS`, `CORS_ORIGINS` | `backend` (`network.config.ts`) | `BACKEND_CORS_ORIGINS` takes precedence over `CORS_ORIGINS`. Optional in `development` (defaults to local `:3000/:4200/:5000` origins; rejects `*`, `null`, paths, queries, credentials, trailing slashes). **Required in `NODE_ENV=production`** with explicit `https://` non-loopback/non-`10.0.2.2` origins (fails closed on startup otherwise). Native mobile requests without an `Origin` header pass CORS and are governed by `JwtAuthGuard`. |
| `GEMINI_API_KEY` / `LLM_PROVIDER` / `OPENAI_API_KEY` | `ai-service` | Required only for live LLM generation (`chat` fails closed with `503` if `GEMINI_API_KEY` is missing/placeholder at call time). A dummy value (`dummy-key-not-used-in-ci`) is sufficient to import the service, run offline/CI tests, and export OpenAPI. |
| `REDIS_HOST`, `REDIS_PORT` | `backend`, `ai-service` | Optional / where Redis is used (default `localhost:6379`). |
| `PLANNER_MODEL`, `PLANNER_MAX_OUTPUT_TOKENS`, `PLANNER_TIMEOUT_MS`, `AI_PORT`, `WEATHER_API_URL` | `ai-service` | Optional runtime tuning. |
| `SUPABASE_*`, `CLOUDINARY_*`, `GOOGLE_MAPS_API_KEY` | Not read by current runtime code paths | No. |

## Commands
### Backend (`apps/backend`)
Authoritative Prisma schema and migrations live in `apps/backend/prisma/` (`schema.prisma`, `migrations/`). See also [Backend Test Strategy](../testing/backend-test-strategy.md), [AI Chat Architecture](../ai/ai-chat.md), and [AI Chat API Contract](../api/ai-chat-api.md).
```bash
cd apps/backend
pnpm install --frozen-lockfile
pnpm exec prisma generate
pnpm exec prisma migrate status   # inspect pending migrations and target DB first
pnpm exec prisma migrate deploy   # applies pending SQL migrations (can alter schema & data!)
pnpm run typecheck
pnpm run lint:check               # non-mutating (pnpm run lint auto-fixes!)
pnpm test                         # unit & security specs (no DB needed)
pnpm run build
pnpm start:dev                    # or from repo root: pnpm --dir apps/backend start:dev
pnpm run test:e2e                 # requires isolated test PostgreSQL + internal FastAPI on AI_SERVICE_URL
```
> **Migration safety & pre-flight requirements:** `prisma migrate deploy` skips interactive `migrate dev` resets, **but it is NOT inherently non-destructive** — pending `migration.sql` scripts can modify schemas, constraints, indexes, and existing table data. Before running `prisma migrate deploy` on any shared, research, or non-disposable database: (1) verify the active environment and exact target `DATABASE_URL` (host + database name), (2) inspect `pnpm exec prisma migrate status` and review the SQL and [`ROLLBACK_AND_RECOVERY.md`](../../apps/backend/prisma/migrations/20261110000000_sync_schema_drift/ROLLBACK_AND_RECOVERY.md), and (3) take a verified backup (`pg_dump`) with a confirmed roll-forward/recovery plan. **Never auto-run or manually execute migrations against a production database without explicit Project Owner authorization.**

### AI Service & Data Contracts (from repo root)
```bash
pip install -r apps/ai-service/requirements-dev.txt
ruff check .
python scripts/export_openapi_ai.py --check
python -m scripts.freeze_checksum --skip-missing-prefix=data/restricted/

# Exact CI data-contract command (works on clean clones without git-ignored ViHoRec CSVs or live DB):
python -m pytest tests -q \
  --deselect tests/test_data02_contract.py::test_vihorec_integrity_pass \
  --deselect tests/test_data02_contract.py::test_freeze_manifest_sha256_integrity \
  --deselect tests/test_data03_danang_freeze_v2.py::test_freeze_v1_immutability \
  --deselect tests/test_data03_danang_freeze_v2.py::test_freeze_v2_checksum_integrity \
  --deselect tests/test_data03_danang_freeze_v2.py::test_live_database_invariants \
  --deselect tests/test_data04_lineage_r1.py::test_assertion_14_freeze_v1_sha_integrity \
  --deselect tests/test_freeze_checksum_compat.py::test_real_freeze_v1_verification_reports_statuses \
  --deselect tests/test_reca_baseline.py::test_assertion_12_freeze_v1_and_v2_sha_integrity

# Optional local convenience filter when restricted ViHoRec CSVs are present on disk:
# python -m pytest tests -m "not live_llm" -k "not vihorec and not test_live_database_invariants" -q

# AI service unit, RAG, and grounding suites:
cd apps/ai-service && python -m pytest tests -q
```
*(Note: `.github/workflows/ci.yml` uses `python -m pytest tests -q` with the 8 explicit `--deselect` flags above rather than `-m "not live_llm"`; opt-in live Gemini smoke files `test_chat_live.py` and `test_planner_live.py` in `apps/ai-service/tests/` are gated by `pytest.mark.skipif` unless `CHAT_LIVE_TEST=1` or `PLANNER_LIVE_TEST=1` is set.)*
To run FastAPI locally for development (keep bound to loopback):
```bash
cd apps/ai-service
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Mobile (`apps/mobile`)
```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test
```

### Mobile API Target Configuration (`--dart-define=API_BASE_URL=...`)
All Flutter mobile traffic routes exclusively through the NestJS backend (`API_BASE_URL`). Never point `API_BASE_URL` at the internal FastAPI service (`:8000`).

- **Local desktop / web debug (default when omitted in debug mode):**
  ```bash
  flutter run --dart-define=API_BASE_URL=http://localhost:3000
  ```
- **Android Emulator debug (standard AVD maps host loopback to `10.0.2.2`):**
  ```bash
  flutter run --dart-define=API_BASE_URL=http://10.0.2.2:3000
  ```
- **Physical Android device on the same Wi-Fi / LAN (debug build only):**
  1. Start NestJS bound to `0.0.0.0:3000` (from repo root):
     - Bash / macOS / Linux: `HOST=0.0.0.0 PORT=3000 pnpm --dir apps/backend start:dev`
     - PowerShell (Windows): `$env:HOST="0.0.0.0"; $env:PORT="3000"; pnpm --dir apps/backend start:dev`
  2. Ensure the host firewall allows inbound TCP `3000` on the private LAN profile and the phone is on the same Wi-Fi subnet (`localhost` on a phone refers to the phone itself).
  3. Run Flutter in debug mode with your machine's LAN IPv4 address:
     ```bash
     flutter run --dart-define=API_BASE_URL=http://<DEV_MACHINE_LAN_IP>:3000
     ```
- **Release / Profile builds (HTTPS non-loopback mandatory):**
  `AppConstants.resolveApiBaseUrl` fails closed at runtime if `API_BASE_URL` is omitted, malformed, `http://`, `localhost`/`127.0.0.1`/`::1`, or `10.0.2.2`, and `apps/mobile/android/app/src/main/AndroidManifest.xml` enforces `android:usesCleartextTraffic="false"`:
  ```bash
  flutter build apk --release --dart-define=API_BASE_URL=https://<YOUR_BACKEND_DOMAIN>
  ```

### Android Verification & Release Boundaries
Do not treat documentation or debug/emulator checks as production release sign-off:
- **Android 15 Emulator smoke:** Agent-reported `PASS`; independent raw-evidence verification is currently being supplemented (`pending independent raw-evidence verification`).
- **Physical Android device smoke:** `BLOCKED_BY_ENVIRONMENT` (no physical Android device attached in the verification environment — never report as `PASS`).
- **Release / Profile URL validation:** Runtime fail-closed validation is implemented (`AppConstants.resolveApiBaseUrl` + `usesCleartextTraffic="false"`); compile-time Gradle validation of `-Pdart-defines` is **not** yet implemented.
- **Release APK signing:** `apps/mobile/android/app/build.gradle.kts` currently signs `release` builds with `signingConfigs.getByName("debug")` — **not** ready for production distribution.
- **HTTPS staging handshake:** Live TLS handshake against a deployed staging endpoint has **not** yet been verified.
- **AI Chat smoke scope:** Emulator smoke used an offline-stubbed LLM client (zero paid API calls); it is **not** a W07 scientific factuality `PASS` (`W07` gates `G1.5..G6` remain `HOLD`).

## GitHub Actions CI & Remaining Skipped/Deselected Tests
`.github/workflows/ci.yml` actively runs four jobs on GitHub Actions (`backend`, `ai-service`, `mobile`, `data-contract`) on pushes and pull requests to `develop` and `main`, with **zero paid LLM API calls** (`GEMINI_API_KEY=dummy-key-not-used-in-ci`):
- **`backend` job:** Installs `postgresql-16-postgis-3`, `postgresql-16-postgis-3-scripts`, and `postgresql-16-pgvector` directly onto the `ubuntu-latest` runner via `apt-get` (`systemctl restart postgresql`), creates isolated database `wanderai_ci_test` on `localhost:5432`, applies `database/init.sql` and `apps/backend/prisma/migrations` (`prisma migrate deploy`), seeds deterministic fixtures via `scripts/seed_ci_database.py`, starts internal FastAPI on `127.0.0.1:8000`, and runs `typecheck`, `lint:check`, `pnpm run build`, `pnpm test` (unit/security specs), and `pnpm exec jest --config ./test/jest-e2e.json --runInBand --forceExit` (all 13 E2E suites).
- **`ai-service` job:** Installs PostgreSQL 16 + `postgis` + `pgvector` directly onto the `ubuntu-latest` runner (`wanderai_ci_test` on `localhost:5432`), applies `database/init.sql` and sequential `apps/backend/prisma/migrations/*/migration.sql` files via `psql`, runs `scripts/seed_ci_database.py --include-rag-docs`, checks `ruff`, OpenAPI drift (`export_openapi_ai.py --check`), CI seed/migration rollback safety (`test_prod_ci_05_corrective_safety.py`), and `python -m pytest tests -q` (including `asyncpg` PostgreSQL RAG retrieval and grounding contract suites such as `test_rag_retrieval_da_nang_culinary` and `test_synthetic_documents_never_reach_the_provider`).
- **`mobile` job:** Runs `flutter analyze` and `flutter test` across `apps/mobile`.
- **`data-contract` job:** Runs offline freeze checksum verification (`python -m scripts.freeze_checksum --skip-missing-prefix=data/restricted/`) followed by `python -m pytest tests -q` with 8 explicit `--deselect` flags for the 7 git-ignored restricted `ViHoRec` checksum tests and `test_live_database_invariants` (unlike local ad-hoc runs that may pass `-m "not live_llm"`).

**Tests that remain intentionally deselected or skipped in CI:**
1. **Licensed ViHoRec raw CSV checks (`7` root tests `--deselect`ed in `data-contract`):** `data/restricted/vihorec/` is git-ignored under dataset licensing terms.
2. **`tests/test_data03_danang_freeze_v2.py::test_live_database_invariants` (`1` root test `--deselect`ed in `data-contract`):** Requires a live Freeze V2 database load rather than the DB-less `data-contract` environment or compact CI fixtures.
3. **`apps/ai-service/tests/test_rag_osm_ingestion.py` (`2` corpus-volume assertions expecting `>= 464` Wikivoyage chunks):** Skipped against lightweight CI fixtures (`C01-F04`), where `seed_ci_database.py` loads compact deterministic RAG fixtures instead of the full historical ingestion dump.
4. **Historical W06 offline QA gate files (`qa_01`/`qa_02` via `conftest.py`) & opt-in live Gemini smoke files (`test_chat_live.py`, `test_planner_live.py` via `CHAT_LIVE_TEST=1` / `PLANNER_LIVE_TEST=1` `skipif` guards):** Skipped by default so standard local and CI runs never mutate historical QA snapshots or spend live LLM quota.

### CI Seed Safety Guard & Windows Docker Desktop NAT Limitation
`scripts/seed_ci_database.py` executes `TRUNCATE ... CASCADE` and enforces multi-layer fail-closed guards before touching PostgreSQL:
- Requires `CI_DATABASE_URL` targeting a database name matching `^wanderai_ci(_[a-z0-9_]+)?$` on loopback (`localhost`, `127.0.0.1`, `::1`).
- Requires `ALLOW_DESTRUCTIVE_CI_SEED=1` and `CI=true` (or `GITHUB_ACTIONS=true`), and rejects `NODE_ENV`/`APP_ENV`/`ENVIRONMENT`/`DEPLOY_ENV` values in `{production, prod, staging, development, dev}`.
- Queries live PostgreSQL (`current_database()`, `pg_is_in_recovery() = false`, and `host(inet_server_addr())`) to verify a primary loopback instance before truncating.

**Windows Docker Desktop NAT limitation:** When running `scripts/seed_ci_database.py` directly on a Windows host against a Docker Desktop port-forwarded PostgreSQL container (`127.0.0.1:5432`), Docker's NAT bridge causes PostgreSQL `inet_server_addr()` to report a container bridge IP (e.g. `172.18.0.x`) rather than `127.0.0.1`/`::1`, so `verify_live_ci_database_connection` intentionally aborts fail-closed. **Do NOT weaken, patch, or bypass this guard**, and never point CI seeding at the development `wanderai` database. Execute `seed_ci_database.py` only in Linux GitHub Actions or from inside the container/loopback network against a dedicated `wanderai_ci_*` database.
