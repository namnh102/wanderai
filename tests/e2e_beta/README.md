# WanderAI Beta Opaque-Box E2E Suite (`tests/e2e_beta`)

Zero-dependency **Node.js 22** ES module (`.mjs`) opaque-box E2E suite covering Requirements `R1`–`R5` and Features `F1`–`F10` across 4 Tiers (**118 tests total**), using Tháp Đồng Hồ (`65562a67-84ff-44a0-990d-31917a2a9bd0`, Hạ Long) as the reference journey.

## Design Rules
- Built strictly on Node.js 22 built-in modules (`node:test`, `node:assert/strict`, `node:http`, `fetch`, `node:crypto`, `node:fs`, `node:path`, `node:child_process`).
- Intentionally contains **no `package.json`** (avoids `pnpm` workspace interference) and **no `*.py`** files (avoids `pytest tests` discovery in `ci.yml`).
- Enforces **R4 W07 Governance**: never modifies `data/curated/gomate_places_freeze_v2.json`, `data/curated/w07/`, or `w07_offline_retrieval_prep`.
- Enforces **Strict No-Skip Policy**: missing Beta mobile deliverables, missing `390×844` Before/After screenshots, missing `w07_offline_retrieval_prep`, or missing live test hooks **fail** `--mode=live` instead of silently passing.

## Quick Start

### 1. Self-Test Mode (Offline Contract & Stateful Server Verification)
```powershell
node tests/e2e_beta/run_e2e.mjs --mode=self-test
```
Also execute `flutter test` once before the suites:
```powershell
node tests/e2e_beta/run_e2e.mjs --mode=self-test --run-flutter --tier=1
```
Run individual tiers:
```powershell
node tests/e2e_beta/run_e2e.mjs --mode=self-test --tier=1
node tests/e2e_beta/run_e2e.mjs --mode=self-test --tier=2
node tests/e2e_beta/run_e2e.mjs --mode=self-test --tier=3
node tests/e2e_beta/run_e2e.mjs --mode=self-test --tier=4
```

### 2. Live Integration Mode (`M5`)
```powershell
node tests/e2e_beta/run_e2e.mjs --mode=live --base-url=http://127.0.0.1:3000 --repo-root=. --mobile-dir=apps/mobile --w07-prep-dir=../w07_offline_retrieval_prep --youtube-secret=<secret> --websub-secret=<secret>
```
CLI flags:
- `--run-flutter` — runs `flutter test` once in `--mode=self-test` (in `--mode=live`, `flutter test` runs automatically by default)
- `--skip-flutter` — skips automatic `flutter test` execution in `--mode=live`
- `--report=<path>` — writes a JSON summary report
- `--tier=1|2|3|4|all` — selects a subset tier or all tiers

Required `M5` `--mode=live` environment hooks (fail-fast if omitted):
- `E2E_MAIL_OUTBOX_URL` (or `E2E_TEST_RESET_TOKEN`) — `GET ?email=<email>` returns `{ token }` or `{ success: true, data: { items: [{ rawToken }] } }`
- `E2E_EXPIRED_RESET_SEED_URL` (or `E2E_EXPIRED_RESET_TOKEN`) — `POST { email }` seeds an expired `password_reset_tokens` row (`expires_at < NOW()`, `used_at = NULL`), returning `{ token }`
- `E2E_DB_STATS_URL` — `GET` queries PostgreSQL and returns `{ documentsCount, placeSourcesCount }` for R4 table-isolation assertions
- `E2E_GOOGLE_TEST_ID_TOKEN` / `E2E_FACEBOOK_TEST_ACCESS_TOKEN` — test OAuth tokens (alongside DI mock verifier support for `valid-email:<email>`, `no-email-*`, `provider-error-502`)

## Suite Breakdown (118 Tests)
| Tier | File | Count | Scope |
|---|---|---:|---|
| Tier 1 | `suites/tier1_feature_coverage.test.mjs` | 50 | 5 happy-path tests per feature `F1`–`F10` |
| Tier 2 | `suites/tier2_boundary_corners.test.mjs` | 50 | 5 boundary/negative/corner tests per feature `F1`–`F10` |
| Tier 3 | `suites/tier3_cross_feature.test.mjs` | 12 | Pairwise & multi-feature combinations (`T3-01`..`T3-12`) |
| Tier 4 | `suites/tier4_real_world_journeys.test.mjs` | 6 | Full Hạ Long / Tháp Đồng Hồ journeys (`T4-01`..`T4-06`) |
