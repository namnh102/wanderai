# Backend Test Strategy

## Framework
- **Runner:** Jest 29 (`ts-jest`)
- **HTTP Testing:** Supertest 7
- **NestJS Integration:** `@nestjs/testing`
- **Unit & Security Config:** `apps/backend/package.json` (`jest`, `rootDir: "src"`, `testRegex: ".*\\.spec\\.ts$"`)
- **E2E Config:** `apps/backend/test/jest-e2e.json` (`testRegex: ".e2e-spec.ts$"`)

## Test Types

### 1. Unit & Security Specs (`src/**/*.spec.ts`)
Fast, database-free unit tests covering security-critical configuration and authentication invariants:
- Fail-closed `JWT_SECRET` / `JWT_REFRESH_SECRET` startup validation, token type separation (`access` vs `refresh`), and active-user verification (`deletedAt == null`).
- Signed NestJS-to-FastAPI internal service assertions (`X-WanderAI-Internal-Assertion`, HMAC-SHA256 `v1.*`) and upstream error mapping.
- NestJS `HOST` / `PORT` binding and strict `BACKEND_CORS_ORIGINS` / `CORS_ORIGINS` validation across `development` and `production` modes.

### 2. E2E Integration Specs (`test/*.e2e-spec.ts`)
Full NestJS application bootstrap against an isolated PostgreSQL 16 (`postgis`, `vector`, `uuid-ossp`) database and local internal FastAPI AI service (`127.0.0.1:8000` with offline/stubbed LLM config in CI):
- Request routing and `ValidationPipe` DTO enforcement (`class-validator`)
- `JwtAuthGuard` authentication and per-user resource ownership
- Prisma queries, verified-only serving rules, and provenance contracts
- AI Chat (`POST /ai/chat`, `DELETE /ai/chat/:sessionId`), Trip Planner, and REC-A Place Recommendations proxying
- Response wrapping (`TransformInterceptor` → `{success, data, timestamp}`) and `HttpExceptionFilter` error normalization

## Database Isolation & CI Strategy

### Isolated CI PostgreSQL (`wanderai_ci_test`)
Backend E2E tests **do not** share the development database in CI. In [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) (`backend` job; see also [Developer Runbook](../w3/developer-runbook.md)):
1. GitHub Actions provisions an ephemeral `postgres:16` service container with `postgresql-16-postgis-3` and `postgresql-16-pgvector` and dedicated database `wanderai_ci_test`.
2. CI applies `database/init.sql` followed by all migrations in `apps/backend/prisma/migrations` via `pnpm exec prisma migrate deploy`.
3. CI loads deterministic engineering fixtures (`destinations`, verified/unverified `places`, `place_sources`) using `scripts/seed_ci_database.py`.
4. Per-suite user mutations (`auth`, `preferences`, `trips`, `planner`, `ai-chat`) create unique timestamped `@wanderai.test` accounts and clean up created rows in `afterAll`.

### Fail-Closed CI Seed Guard & Windows Docker Desktop NAT Limitation
Because `scripts/seed_ci_database.py` executes `TRUNCATE ... CASCADE`, it enforces strict fail-closed guards before running any destructive SQL:
- `CI_DATABASE_URL` must target a database matching `^wanderai_ci(_[a-z0-9_]+)?$` on loopback (`localhost`, `127.0.0.1`, `::1`).
- Requires `ALLOW_DESTRUCTIVE_CI_SEED=1` and `CI=true` (or `GITHUB_ACTIONS=true`), and rejects `NODE_ENV` / `APP_ENV` / `ENVIRONMENT` / `DEPLOY_ENV` in `{production, prod, staging, development, dev}`.
- Queries live PostgreSQL (`current_database()`, `pg_is_in_recovery() = false`, and `host(inet_server_addr())`) to confirm a primary loopback database connection.

> **Windows Docker Desktop NAT limitation:** Connecting from a Windows host to a Docker Desktop port-forwarded PostgreSQL container (`127.0.0.1:5432`) causes PostgreSQL `inet_server_addr()` to report a Docker bridge IP (`172.18.0.x`), so `seed_ci_database.py` intentionally aborts fail-closed. **Do NOT bypass, patch out, or weaken this guard.**

**DO NOT:**
- Point `scripts/seed_ci_database.py` or destructive test runs at the development database (`wanderai`) or any staging/production database
- Weaken or bypass `seed_ci_database.py` safety guards
- Hard-code real credentials or invoke paid external LLM APIs in CI (`GEMINI_API_KEY` uses a dummy non-live placeholder in CI)

## Commands

Run from `apps/backend` (or prefix with `pnpm --dir apps/backend` from the repository root; there is no root `pnpm-workspace.yaml`):

```bash
# Run unit & security specs (no database required)
pnpm test --verbose

# Non-mutating lint & TypeScript checks
pnpm run lint:check
pnpm run typecheck

# Run all E2E specs (requires isolated test PostgreSQL + internal FastAPI on AI_SERVICE_URL)
pnpm run test:e2e

# Run a single E2E spec file
pnpm exec jest --config ./test/jest-e2e.json test/health.e2e-spec.ts
```

## Baseline Test Inventory Snapshot

> **Snapshot metadata:** Verified on **2026-11-11** at `develop@5b13ceb1d97bd9769ca51ea3db02a1643e283de6` (GitHub Actions run `#42968497101`, `backend` job `#130351203034`). Counts below are a point-in-time baseline snapshot and will evolve as new suites and cases are added — do not treat them as fixed constants.

### Unit & Security Suites (`3` suites, `48` tests at baseline `5b13ceb1`)

| File | Tests (Snapshot) | Scope |
|------|------------------|-------|
| `src/modules/auth/auth.security.spec.ts` | 21 | Fail-closed JWT secret strength/uniqueness, token-type isolation, active-user & soft-delete checks |
| `src/config/network.config.spec.ts` | 15 | `PORT`/`HOST` parsing, strict dev/prod CORS origin validation, fail-closed production HTTPS CORS |
| `src/modules/ai-proxy/ai-proxy.security.spec.ts` | 12 | `X-WanderAI-Internal-Assertion` HMAC signing, secret separation, session/user binding & error mapping |
| **Total (Snapshot)** | **48** | |

### E2E Integration Suites (`13` suites, `155` tests at baseline `5b13ceb1`)

| File | Tests (Snapshot) | Scope |
|------|------------------|-------|
| `test/place-contract.e2e-spec.ts` | 42 | `/places` & `/places/nearby` pagination, query validation (`it.each`), destination UUID/slug & verified-only contracts |
| `test/recommendations.e2e-spec.ts` | 19 | REC-A `/places/recommendations` contract, `topK` bounds (`it.each`), model selection & upstream error handling |
| `test/place-detail.e2e-spec.ts` | 15 | `/places/:id` detail schema, provenance visibility, unverified rejection & 404/400 handling |
| `test/preferences.e2e-spec.ts` | 13 | Authenticated user travel preferences CRUD, DTO validation & per-user isolation |
| `test/trips.e2e-spec.ts` | 11 | Authenticated trips & itinerary items lifecycle, ownership checks & status transitions |
| `test/places.e2e-spec.ts` | 10 | Places listing, category/destination filters & spatial nearby search |
| `test/verified-serving.e2e-spec.ts` | 10 | Verified-only place serving invariants across public endpoints & category filters (`it.each`) |
| `test/planner.e2e-spec.ts` | 8 | Authenticated trip planner generation & `TripContext` proxy integration |
| `test/auth.e2e-spec.ts` | 7 | Registration, login, duplicate rejection, DTO validation & unauthorized guards |
| `test/provenance.e2e-spec.ts` | 7 | Place source provenance attribution & invalid-source exclusion invariants |
| `test/ai-chat.e2e-spec.ts` | 6 | Authenticated `POST /ai/chat` & `DELETE /ai/chat/:sessionId` internal-assertion flow & cross-user `403` isolation |
| `test/destinations.e2e-spec.ts` | 5 | Destinations list, limit, region filter & popular endpoint |
| `test/health.e2e-spec.ts` | 2 | `/health` HTTP 200 & `{success, data, timestamp}` envelope |
| **Total (Snapshot)** | **155** | |

## Current Boundaries & Lint Snapshot

1. **ESLint snapshot (`2026-11-11`, `develop@5b13ceb1`):** `pnpm run lint:check` exits cleanly with `0` errors and `85` warnings (`--max-warnings=-1`, primarily legacy `@typescript-eslint/no-explicit-any` annotations). This count is a point-in-time snapshot, not a target ceiling.
2. **Internal AI service dependency for proxy E2E suites:** `ai-chat.e2e-spec.ts`, `planner.e2e-spec.ts`, and `recommendations.e2e-spec.ts` require the internal FastAPI service listening on `AI_SERVICE_URL` (`http://127.0.0.1:8000`) with matching `AI_INTERNAL_AUTH_SECRET` (started automatically in `.github/workflows/ci.yml`).
3. **Engineering fixtures vs scientific evaluation:** CI E2E suites run against compact deterministic engineering fixtures and offline/dummy LLM configuration — they verify API, auth, DB, and grounding contracts, not W07 scientific factuality gates (`G1.5..G6` remain `HOLD`).
