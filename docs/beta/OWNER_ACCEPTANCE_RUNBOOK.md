# WanderAI / GoMate Beta — Owner Acceptance Runbook & Whole-Project Verification Summary

**Integration Repository**: `D:\Do_an\wanderai_beta_integration`  
**Integration Branch**: `feat/beta-integration`  
**Verified Code Baseline**: `28b028bf1ba37a8c2a369bdfd38f88cf75702aa9` (`28b028b`) *(code baseline; followed only by documentation commit(s) for `docs/beta/OWNER_ACCEPTANCE_RUNBOOK.md`)*  
**Reference POI Journey**: `Tháp Đồng Hồ` (`65562a67-84ff-44a0-990d-31917a2a9bd0`, Hạ Long — `20.9516105, 107.0851999`, OSM `way/674228542`)

This runbook separates **(A) Automated & Emulator Proof already verified on `feat/beta-integration`** from **(B) Owner Real-Device, Real-Database & Real-Credential Acceptance Steps** required when connecting live PostgreSQL, SMTP, Google/Facebook OAuth projects, YouTube WebSub secrets, and physical Android hardware.

---

## Section A — Verified Automated Proof (on `feat/beta-integration`)

All checks in Section A were executed directly against `D:\Do_an\wanderai_beta_integration` at `28b028bf1ba37a8c2a369bdfd38f88cf75702aa9`.

### 1. Backend Verification (`apps/backend`)

| Check | Exact Command (from `apps/backend`) | Verified Result |
|---|---|---|
| Prisma schema validation | `$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/wanderai"; pnpm exec prisma validate` | **PASS** — `The schema at prisma\schema.prisma is valid` (`DATABASE_URL` env var required) |
| TypeScript typecheck | `pnpm run typecheck` (`tsc --noEmit -p tsconfig.json`) | **PASS** — `0` errors |
| Backend ESLint | `pnpm run lint:check` (`eslint "{src,apps,libs,test}/**/*.ts" --max-warnings=-1`) | **PASS** — `0` errors (`89` pre-existing warnings outside `test/e2e-harness/`) |
| Harness ESLint (strict) | `pnpm exec eslint "test/e2e-harness/*.ts" --max-warnings=0` | **PASS** — `0` errors, `0` warnings |
| Production NestJS build | `pnpm run build` (`nest build`) | **PASS** — exit `0` |
| Unit & security Jest suites | `pnpm test` (`jest`) | **PASS** — **`12/12` suites**, **`127/127` tests** passed |

Verified Jest unit/security suites (`12/12`):
- `src/common/validation-hardening.spec.ts`
- `src/config/network.config.spec.ts`
- `src/modules/ai-proxy/ai-proxy.security.spec.ts`
- `src/modules/auth/auth-recovery-oauth.spec.ts`
- `src/modules/auth/auth.security.spec.ts`
- `src/modules/mail/mail.service.spec.ts`
- `src/modules/matches/matches.security.spec.ts`
- `src/modules/places/places.service.spec.ts`
- `src/modules/reviews/reviews.security.spec.ts`
- `src/modules/trips/trips.service.spec.ts`
- `src/modules/youtube/youtube.http.spec.ts`
- `src/modules/youtube/youtube.service.spec.ts`

### 2. Python Pilot Enrichment Verification

- **Command (from repo root)**: `python -m pytest tests/test_halong_pilot_enrichment.py`
- **Verified Result**: **PASS** — **`2/2` tests passed** (`test_pilot_60_schema_and_halong_provenance`, `test_coordinate_and_identity_gate_fails_closed`).

### 3. Mobile Verification (`apps/mobile`)

| Check | Exact Command (from `apps/mobile`) | Verified Result |
|---|---|---|
| Static analysis | `flutter analyze` | **PASS** — `No issues found!` (`0` issues) |
| Automated Flutter tests | `flutter test` | **PASS** — **`+315 ~3`** across **`27` test files** |
| Debug Android APK | `flutter build apk --debug` | **PASS** — `apps/mobile/build/app/outputs/flutter-apk/app-debug.apk` (`195,979,704` bytes) |

**Opt-in Live Skipped Tests (`~3` of `+315 ~3`)**:
- `apps/mobile/test/live_halong_trip_save_e2e_test.dart` (2 tests, gated on `LIVE_HALONG_E2E=1`)
- `apps/mobile/test/live_tc_w3_01_test.dart` (1 test, gated on `LIVE_W3=1`)

**Shared UI Components (`apps/mobile/lib/core/widgets/`)**:
- Enforced shared components (`AppTextField`, `AppButton`, `AppLoading`, `AppErrorState`, `AppStateBanner`) across all **4 core screens (+ sheets)** and **4 auth screens** with **`0` raw `TextFormField`, `ElevatedButton`, or `FilledButton` widgets**:
  - **Core Screens**: `HomeScreen` (`home_screen.dart`, `destination_places_sheet.dart`, `home_search_sheet.dart`), `MapScreen` (`map_screen.dart`, `place_preview_sheet.dart`), `PlaceDetailScreen` (`place_detail_screen.dart`, `save_place_to_trip_sheet.dart`, `youtube_freshness_section.dart`), `TripListScreen` / `TripDetailScreen` / `TripFormScreen` (`trip_list_screen.dart`, `trip_detail_screen.dart`, `trip_form_screen.dart`).
  - **Auth Screens**: `LoginScreen` (`login_screen.dart`), `RegisterScreen` (`register_screen.dart`), `ForgotPasswordScreen` (`forgot_password_screen.dart`), `ResetPasswordScreen` (`reset_password_screen.dart`).

**Key Automated Flutter Test Coverage**:
- **Save Success, Cancel Login & Network Loss during Save** (`apps/mobile/test/halong_trip_save_journey_test.dart`):
  - Save Success (authenticated + guest redirect `/login?redirect=...` -> save -> cold restart persistence).
  - Cancel Login (`login_cancel_button` `"Hủy đăng nhập · Quay lại"` returns cleanly to `PlaceDetailScreen` in guest mode with `0` created trips and `0` error banners).
  - Network Loss during Save (`DioException.connectionError` renders warning `AppStateBanner`, preserves `_createdPendingTrip` and `clientRequestId`, and retry `"Thử lại"` completes without duplicating `POST /trips`).
- **Password Reset & OAuth Contract** (`apps/mobile/test/auth_reset_and_oauth_test.dart`):
  - Deep-link normalization, Forgot/Validate/Reset happy path, `RESET_TOKEN_EXPIRED`, `RESET_TOKEN_USED`, `RESET_TOKEN_INVALID`, Google & Facebook `Success` / `Cancelled` / `Error` (`OAUTH_EMAIL_UNAVAILABLE`, `OAUTH_PROVIDER_ERROR`), transient validation retry, `clearError()` transitions, and logout `signOutAll()` race hardening.
- **YouTube Freshness UI** (`apps/mobile/test/place_youtube_freshness_test.dart`):
  - 5 mandated fields (`placeId`, `source`, `publishedAt`, `receivedAt`, `updatedAt`) on Tháp Đồng Hồ, Hạ Long city-level fallback (`scope: CITY`, `placeId: null`), and measured source-to-app latency SLA badge (`"Thời gian thực"` for `[0, 300000]` ms vs `"Cập nhật gần đây"` when stale, malformed, or negative clock-skew).

### 4. Full-Stack Live E2E (`tests/e2e_beta` against `e2e-live-server.ts`)

**Exact Startup Command (from `apps/backend`)**:
```powershell
$env:E2E_API_PORT="3000"
$env:E2E_HOOK_PORT="3001"
$env:YOUTUBE_EVENTS_INTERNAL_SECRET="e2e-youtube-internal-secret"
$env:YOUTUBE_WEBSUB_SECRET="e2e-websub-hmac-secret"
pnpm exec ts-node -r tsconfig-paths/register test/e2e-harness/e2e-live-server.ts
```

**Exact Runner Command (from repo root `D:\Do_an\wanderai_beta_integration`)**:
```powershell
$env:E2E_MAIL_OUTBOX_URL="http://127.0.0.1:3001/mail-outbox"
$env:E2E_EXPIRED_RESET_SEED_URL="http://127.0.0.1:3001/seed-expired-reset-token"
$env:E2E_DB_STATS_URL="http://127.0.0.1:3001/db-stats"
$env:E2E_GOOGLE_TEST_ID_TOKEN="valid-google-token"
$env:E2E_FACEBOOK_TEST_ACCESS_TOKEN="valid-fb-token"
$env:E2E_YOUTUBE_INTERNAL_SECRET="e2e-youtube-internal-secret"
$env:E2E_WEBSUB_SECRET="e2e-websub-hmac-secret"
node tests/e2e_beta/run_e2e.mjs --mode=live --tier=all --base-url=http://127.0.0.1:3000 --repo-root=. --mobile-dir=apps/mobile --w07-prep-dir=../w07_offline_retrieval_prep --youtube-secret=e2e-youtube-internal-secret --websub-secret=e2e-websub-hmac-secret
```

**Verified Results**: **`118/118` passed, `0` failed, `0` skipped** (plus embedded `flutter test` `+315 ~3`):
- **Tier 1** (`suites/tier1_feature_coverage.test.mjs`): **`50/50`** passed
- **Tier 2** (`suites/tier2_boundary_corners.test.mjs`): **`50/50`** passed
- **Tier 3** (`suites/tier3_cross_feature.test.mjs`): **`12/12`** passed
- **Tier 4** (`suites/tier4_real_world_journeys.test.mjs`): **`6/6`** passed

**Harness Boundary Disclosure**:
- `apps/backend/test/e2e-harness/e2e-live-server.ts` boots the unmodified NestJS `AppModule` (`ValidationPipe`, `HttpExceptionFilter`, `TransformInterceptor`, CORS) on `127.0.0.1:3000`, overriding only `PrismaService` (`InMemoryPrismaService`), `MAIL_TRANSPORT` (`InMemoryTestMailTransport`), `GOOGLE_OAUTH_VERIFIER` (`TestGoogleOAuthVerifier`), and `FACEBOOK_OAUTH_VERIFIER` (`TestFacebookOAuthVerifier`).
- Test-only hooks (`/mail-outbox`, `/seed-expired-reset-token`, `/db-stats`, `/reset`) run on isolated hook port `127.0.0.1:3001`.
- **`apps/backend/src/` contains zero test hooks or `E2E_` endpoints** in production source files.

### 5. Phase 2 Tier 5 Adversarial Hardening

- **5 iterations** (`92fe8c3`, `adfc939`, `63376d4`, `28b028b` + Iteration 5 confirmation) closing **`19` adversarial gaps (`GAP-01`..`GAP-19`)** across auth token revocation (`tokenVersion`), WebSub HMAC/XXE hardening, DTO/INT4/Vietnamese-search validation, soft-delete guards, sheet keyboard overflow, and Flutter notifier/dialog lifecycle safety.
- Sign-off gate status: Fresh Challenger R5 **`NO REMAINING GAPS`**, Reviewer R4 **`APPROVE`**, Whole-Project Auditor R4 **`CLEAN`**.

### 6. Before (`10126b1`) vs After `390×844` PNG Screenshots

Deterministic Flutter screenshot evidence (`apps/mobile/test/screenshots_thap_dong_ho_test.dart`): **`9` Before PNGs + `12` After PNGs = `21` PNGs total**, every image verified **`390×844`** pixels (`IHDR`):

- **`docs/beta/mobile/screenshots/before/` (`9` PNGs)**:
  1. `01_login.png` (`24,588` bytes)
  2. `02_register.png` (`17,396` bytes)
  3. `03_home_halong.png` (`107,449` bytes)
  4. `04_destination_places_halong.png` (`53,950` bytes)
  5. `05_map_place_preview.png` (`52,260` bytes)
  6. `06_place_detail_thap_dong_ho.png` (`38,839` bytes)
  7. `07_save_place_to_trip.png` (`33,792` bytes)
  8. `08_trip_list.png` (`19,187` bytes)
  9. `09_trip_detail.png` (`46,926` bytes)

- **`docs/beta/mobile/screenshots/after/` (`12` PNGs)**:
  1. `01_login.png` (`33,718` bytes)
  2. `02_register.png` (`20,979` bytes)
  3. `03_home_halong.png` (`107,449` bytes)
  4. `04_destination_places_halong.png` (`54,687` bytes)
  5. `05_map_place_preview.png` (`52,260` bytes)
  6. `06_place_detail_thap_dong_ho.png` (`39,445` bytes)
  7. `06b_place_detail_youtube_freshness.png` (`68,579` bytes)
  8. `07_save_place_to_trip.png` (`59,937` bytes)
  9. `08_trip_list.png` (`19,187` bytes)
  10. `09_trip_detail.png` (`46,640` bytes)
  11. `10_forgot_password.png` (`21,960` bytes)
  12. `11_reset_password.png` (`24,221` bytes)

### 7. Before vs After `--profile` AVD Benchmarks (`GoMate_W3_Test`)

Artifacts: `docs/beta/mobile/BENCHMARKS.md`, `docs/beta/mobile/benchmarks/before_perf.json` (`2026-11-24T20:29:45.188794Z`), `docs/beta/mobile/benchmarks/after_perf.json` (`2026-11-24T20:32:30.802028Z`), measured on AVD `GoMate_W3_Test` (`emulator-5554`, API 35 x86_64, headless SwiftShader OpenGLES) with `integration_test/perf_benchmark_test.dart` + `test_driver/perf_driver.dart` (40 Hạ Long POIs, 35 Trips, 36 Itinerary Items across 6 days):

**Open Latencies (`custom_metrics`, includes `pumpAndSettle(2s)` settle)**:

| Metric | Before (`10126b1`) | After | Delta |
|---|---:|---:|---:|
| `dest_sheet_open_ms` | `4045 ms` | `4055 ms` | `+10 ms` |
| `trip_list_open_ms` | `6109 ms` | `6165 ms` | `+56 ms` |
| `trip_detail_open_ms` | `4101 ms` | `4094 ms` | `-7 ms` |

**Scroll Timeline Metrics (`scroll_timelines`, `16.67 ms` 60Hz budget)**:

| Scroll Action | Metric | Before (`10126b1`) | After |
|---|---|---:|---:|
| `dest_sheet_scroll` | Avg frame build | `10.20 ms` (`10.204`) | `21.40 ms` (`21.404`) |
| | 90th pctl build | `20.21 ms` (`20.209`) | `46.30 ms` (`46.297`) |
| | Avg rasterizer | `25.54 ms` (`25.542`) | `43.25 ms` (`43.253`) |
| | Missed build / total frames | `17 / 82` | `35 / 73` |
| | Missed raster / total frames | `81 / 81` | `72 / 72` |
| `trip_list_scroll` | Avg frame build | `11.26 ms` (`11.263`) | `14.37 ms` (`14.368`) |
| | 90th pctl build | `21.95 ms` (`21.947`) | `28.14 ms` (`28.140`) |
| | Avg rasterizer | `16.52 ms` (`16.523`) | `17.02 ms` (`17.023`) |
| | Missed build / total frames | `25 / 61` | `30 / 61` |
| | Missed raster / total frames | `30 / 60` | `29 / 59` |
| `trip_detail_scroll` | Avg frame build | `11.76 ms` (`11.758`) | `21.88 ms` (`21.876`) |
| | 90th pctl build | `23.11 ms` (`23.107`) | `47.27 ms` (`47.269`) |
| | Avg rasterizer | `16.30 ms` (`16.303`) | `15.61 ms` (`15.611`, `-0.69 ms`) |
| | Missed build / total frames | `20 / 67` | `28 / 55` |
| | Missed raster / total frames | `28 / 66` | `16 / 53` (`-12` frames) |

*(Note: `trip_detail_scroll` rasterizer latency and missed rasterizer frames improved on the lazy `CustomScrollView` + `SliverList.builder` itinerary view; headless software SwiftShader CPU jitter and background Facebook SDK initialization against placeholder `0000000000000000` strings affect emulator percentiles. See Section B.6 for physical hardware GPU benchmarking.)*

### 8. R4 Data Governance & Layer Isolation

- `data/curated/gomate_places_freeze_v2.json` SHA-256: `F7517938598E3923906763F8F31334A500EE88BC06232F2992D38E2FCB28A444`
- `data/curated/w07/poi_knowledge_acquired_v1.jsonl` SHA-256: `9B0ED36E060924057872A2E8FE9941940F7BC3455F2C9CAD21CDC9A9C1141FDA`
- `git diff 880ce77..HEAD -- data/curated/`: **empty (`0` bytes changed)**
- `D:\Do_an\w07_offline_retrieval_prep`: **untouched**
- `youtube_poi_updates` (`DYNAMIC_SOCIAL_FRESHNESS_LAYER`) is strictly isolated from `documents` and `place_sources`: `apps/backend/src/modules/youtube/` contains **`0` writes** to `documents` or `place_sources` (only read-only existence/provenance checks via `place.placeSources`), and `InMemoryPrismaService` / `youtube.http.spec.ts` enforce R4 mutation traps.

### 9. Unified Commit History & Preserved Worktrees

**Commit Chain on `feat/beta-integration` (from `880ce77` / `10126b1` through `28b028b`)**:

| Track / Stage | Short SHA | Full SHA | Subject |
|---|---|---|---|
| `origin/develop` (PR #96) | `880ce77` | `880ce7763c3006aaf59eff8ad2e2ebd9688ca371` | `Merge PR #96: bootstrap trusted W07 publication gate` |
| Wave A (PR #98) | `243a7a9` | `243a7a977203de145374a054b63b4917d47241b2` | `feat(mobile,design): implement UX V2 Wave A design system and Home/Discover slice` |
| Wave B (PR #99) | `9a99107` | `9a991074332fa7830934a0db65ae9698e415618a` | `feat(mobile): UX V2 Wave B — JWT refresh, Map chip fix, Place Detail/Reco V2, Vietnamese copy` |
| Wave B (PR #99) | `19cffea` | `19cffea788cf5a23b1f5da42210c6175b04e3eee` | `fix(mobile): enforce epoch-bound JWT refresh & logout session isolation` |
| Wave C (PR #100) | `156b4d5` | `156b4d518c09049e263f62b98f2f4fcd9174a0f4` | `feat(product,data): Freeze V2 reconciliation, 60-pilot Wikimedia enrichment, review fixes & W08 buddy prep` |
| Wave C (PR #100) | `b768369` | `b76836988e25ba6fb141fd957810599a5fc322a4` | `fix(data-enrichment): move 60-POI pilot file out of data/curated into data/enrichment` |
| PR #101 (`halong_trip_save`) | `cabfa1f` | `cabfa1f7adfa98062465add5d597b1326fe35068` | `feat(mobile): wire POI save-to-trip sheet and post-login POI redirect` |
| PR #101 (Before baseline) | `10126b1` | `10126b10923b2b5b3b184a049664ac7fd5609376` | `fix(mobile): retain created trip id on save retry and add destination sheet search` |
| Backend M1 (off `b768369`) | `5eff32b` | `5eff32b392c9a7fba00b6ef55e997bf696f9ef28` | `chore(backend): import wave_c YouTube freshness and pilot-60 baseline` |
| Backend M1 | `47d4eab` | `47d4eab99fe4c5203cdb3029055a4256cdf8c7ac` | `feat(auth,mail): add password reset, SMTP/test mail module, Google/Facebook OAuth, and canonical error codes` |
| Backend M1 | `a84e0f8` | `a84e0f83005ed4dcc74cabff3deef2e307808283` | `fix(auth): trim DTO email/name/token whitespace and harden OAuth P2002 fallback` |
| Backend M2 | `4f998d3` | `4f998d348a7f9423cc0737f199c4b98aa2f79111` | `feat(youtube): add Ha Long city fallback, 5-field latency contract, destination endpoints, and ingestion guard` |
| Backend M2 | `d517a4a` | `d517a4aa63175b303831241bd82f9e348cc5cd1c` | `fix(youtube): harden P2002 monotonic timestamp, DTO coordinate parsing, and cross-scope deduplication` |
| Mobile M3 (off `10126b1`) | `7e73ca0` | `7e73ca029cae4e365165e689d0cb5f0beac45556` | `feat(mobile): polish core UX, OAuth/password-reset auth, save resilience & benchmarks (M3)` |
| Mobile M4 | `0c9f0b5` | `0c9f0b5a99d410758e78b7cb1ca23251f3f0cac1` | `feat(mobile): add YouTube freshness layer UI and M3 polish (M4)` |
| E2E Track (off `10126b1`) | `3189eb3` | `3189eb3a171fa16f705056f36a75b610d6427cce` | `test(e2e): add zero-dependency Node 22 beta opaque-box E2E suite (Tiers 1-4)` |
| E2E Track | `8a75177` | `8a751779e8ba315b764f1a4f13660f11ec1db802` | `fix(e2e): eliminate JS mobile clones, enforce --mode=live gates & HTTP fault proxy, fix SLA/destination flakiness` |
| E2E Track | `b0a420c` | `b0a420c0b15b11dd8eecdadaf280883fca7f9d6e` | `fix(e2e): align mobile M4 verifier and YouTube/Places contracts (N1-N4)` |
| Integration Merge 1 | `50fa86d` | `50fa86dfc563287dedd819ef0a6ec6924a985056` | `merge: integrate M1+M2 backend auth and YouTube freshness layer` (`10126b1` + `d517a4a`) |
| Integration Merge 2 | `6e73cea` | `6e73cea1fbe8d66477c862a6a0b0dfc062152d6a` | `merge: integrate M3+M4 mobile UX, auth, and YouTube UI` (`50fa86d` + `0c9f0b5`) |
| Integration Merge 3 | `cea007d` | `cea007d1ff3165399d3912871d4f3fdf1ae23c9c` | `merge: integrate opaque-box E2E suite (Tiers 1-4)` (`6e73cea` + `b0a420c`) |
| Integration M5-0 | `c378a01` | `c378a0120010d3839769f5abc7a728ddffaadd3f` | `chore(integration): add M2/M4 polish and test-harness-only live NestJS E2E server` |
| Integration M5-1 | `1b4bc79` | `1b4bc7976079d6ca952c176ef5692be5ad94b1a1` | `fix(m5-1): return dayNumber on itinerary items, trim trip DTOs, fold Vietnamese place search, and clear mobile auth errors` |
| M5-5 Tier 5 Iter 1 | `92fe8c3` | `92fe8c330412d1274ec23497b29736695466fbc2` | `fix(tier5): harden auth revocation, WebSub HMAC, trip/DTO validation, and mobile UX/freshness (GAP-01..GAP-11)` |
| M5-5 Tier 5 Iter 2 | `adfc939` | `adfc939383328b0fe664bf161d436eacb9075733` | `fix(hardening): close GAP-12..GAP-14 validation, INT4/query bounds, and Flutter sheet/dialog disposal` |
| M5-5 Tier 5 Iter 3 | `63376d4` | `63376d4e0f014c73ce049e0bb33d6c105675298f` | `fix(hardening): close GAP-15..GAP-17 and DestinationsService soft-delete check` |
| M5-5 Tier 5 Iter 4 | `28b028b` | `28b028bf1ba37a8c2a369bdfd38f88cf75702aa9` | `fix(hardening): resolve GAP-18 sheet keyboard overflow, GAP-19 notifier mounted guards, and TripsService checks` |

*(Code integration baseline ends at `28b028bf1ba37a8c2a369bdfd38f88cf75702aa9`; subsequent commit(s) on `feat/beta-integration` update only `docs/beta/OWNER_ACCEPTANCE_RUNBOOK.md`.)*

**Untouched Preserved Worktrees (`8` total)**:

| Worktree Path | Branch | HEAD Commit | State |
|---|---|---|---|
| `D:\Do_an\wanderai` | `ci/prod-ci-flutter-sdk-pin-01` | `9bab3e3301185124361f44ff8b41f3b0e46744b7` | Untouched (4 pre-existing untracked `docs/research/W07_B2_*.md`) |
| `D:\Do_an\wanderai_ux_v2_wave_a` | `feat/product-beta-s0-ux-v2-wave-a` | `243a7a977203de145374a054b63b4917d47241b2` | Clean |
| `D:\Do_an\wanderai_ux_v2_wave_b` | `feat/product-beta-ux-v2-wave-b` | `19cffea788cf5a23b1f5da42210c6175b04e3eee` | Clean |
| `D:\Do_an\wanderai_data_enrichment_wave_c` | `feat/product-data-enrichment-wave-c` | `b76836988e25ba6fb141fd957810599a5fc322a4` | Untouched pre-existing WIP (imported into `5eff32b`) |
| `D:\Do_an\wanderai_halong_trip_save` | `feature/halong-poi-trip-save` | `10126b10923b2b5b3b184a049664ac7fd5609376` | Clean |
| `D:\Do_an\wanderai_beta_backend` | `feat/beta-backend-auth-youtube` | `d517a4aa63175b303831241bd82f9e348cc5cd1c` | Clean |
| `D:\Do_an\wanderai_beta_mobile` | `feat/beta-mobile-ux-auth-youtube` | `0c9f0b5a99d410758e78b7cb1ca23251f3f0cac1` | Clean |
| `D:\Do_an\wanderai_beta_e2e` | `feat/beta-e2e-suite` | `b0a420c0b15b11dd8eecdadaf280883fca7f9d6e` | Clean |

---

## Section B — Owner Real-Device / Real-Credential Acceptance Steps

> **Important `.env` & Path Note**: Both `.env.example` and `docker-compose.yml` live at the **repository root** (`D:\Do_an\wanderai_beta_integration\`), **NOT** inside `apps/backend/`. However, every `pnpm --dir apps/backend ...` command runs with `cwd = apps/backend/`, where both Prisma CLI (`migrate deploy`, `db seed`, `reconcile-freeze-v2.ts`) and NestJS `ConfigModule.forRoot()` (`apps/backend/src/app.module.ts`, default `path.resolve(process.cwd(), '.env')`) resolve `.env`. You **MUST** either copy the root `.env` to `apps/backend/.env` (`Copy-Item .env apps/backend/.env` — `.gitignore` ignores `.env` everywhere so secrets are never committed) **or** export the root `.env` variables into your active PowerShell session before running backend commands.

### 1. Elevated Docker Desktop / PostgreSQL Startup, Migrations & Backend Real-DB E2E

1. **Start Docker Desktop** (run as Administrator / elevated on Windows if Hyper-V / WSL2 backend requires elevation) and verify `docker info` succeeds.
2. **Start PostgreSQL + Redis** from the **repo root**:
   ```powershell
   cd D:\Do_an\wanderai_beta_integration
   docker compose up -d postgres redis
   docker compose ps
   ```
   - `docker-compose.yml` defines:
     - `postgres` (`container_name: wanderai-postgres`, PostGIS `16-3.4` + `postgresql-16-pgvector`, `POSTGRES_DB=wanderai`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, port `5432:5432`, mounts `./database/init.sql`).
     - `redis` (`container_name: wanderai-redis`, `redis:7-alpine`, port `6379:6379`).
3. **Create root `.env` from `.env.example` and make it visible to `apps/backend`**:
   ```powershell
   cd D:\Do_an\wanderai_beta_integration
   Copy-Item .env.example .env
   ```
   Edit root `.env` and set at minimum:
   - `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wanderai`
   - `JWT_SECRET` and `JWT_REFRESH_SECRET`: per `apps/backend/src/modules/auth/jwt-config.ts`, **both are strictly required at NestJS startup**, must each be **`>= 32` characters**, have **`>= 8` distinct characters**, be **distinct from each other**, and **must not** contain placeholders (`<replace_with_...>`, `change-in-production`, `wanderai-dev-`). Generate two strong secrets:
     ```powershell
     node -e "const c=require('crypto'); console.log('JWT_SECRET=' + c.randomBytes(32).toString('hex')); console.log('JWT_REFRESH_SECRET=' + c.randomBytes(32).toString('hex'));"
     ```
   - For Step 6 (`youtube-updates-thap-dong-ho.e2e-spec.ts`), keep `YOUTUBE_WEBSUB_VERIFY_TOKEN=`, `YOUTUBE_WEBSUB_SECRET=`, and `YOUTUBE_EVENTS_INTERNAL_SECRET=` **blank** for now (as in `.env.example`); you will set strong secrets immediately afterward in Section B.4.
   - Then sync `.env` to `apps/backend/.env` (Option A — recommended) **or** export root `.env` into your current PowerShell session (Option B):
     ```powershell
     # Option A (recommended): copy root .env into apps/backend/.env and verify git still ignores it
     Copy-Item .env apps/backend/.env
     git status --short

     # Option B (alternative, per-shell): export root .env variables into the active PowerShell session
     Get-Content .env | Where-Object { $_ -match '^\s*[^#][^=]*=' } | ForEach-Object {
       $k, $v = $_ -split '=', 2
       [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
     }
     ```
     *(Whenever you edit root `.env` in Sections B.2–B.4, re-run `Copy-Item .env apps/backend/.env` or re-export into the active shell before running `prisma`, `test:e2e`, or `start:dev`.)*
4. **Apply all 10 Prisma migrations** (`apps/backend/prisma/migrations/`):
   ```powershell
   cd D:\Do_an\wanderai_beta_integration
   pnpm --dir apps/backend exec prisma migrate deploy
   ```
   All 10 migrations (5 with `down.sql` rollback scripts):
   1. `20260922161107_init` (`migration.sql`)
   2. `20261001073816_add_place_sources` (`migration.sql`)
   3. `20261001083200_add_trip_context_fields` (`migration.sql`)
   4. `20261004010000_provenance_remediation` (`migration.sql`)
   5. `20261004020000_provenance_remediation_followup` (`migration.sql`)
   6. `20261110000000_sync_schema_drift` (`migration.sql` + `down.sql` + `ROLLBACK_AND_RECOVERY.md`)
   7. `20261125000000_add_youtube_poi_updates` (`migration.sql` + `down.sql`)
   8. `20261125120000_add_password_reset_and_oauth_accounts` (`migration.sql` + `down.sql`)
   9. `20261125180000_add_youtube_destination_and_scope` (`migration.sql` + `down.sql`)
   10. `20261125200000_tier5_token_version_and_itinerary_idempotency` (`migration.sql` + `down.sql`)
5. **Seed a fresh database AND reconcile Freeze V2 POIs (required for `Tháp Đồng Hồ`)**:
   ```powershell
   cd D:\Do_an\wanderai_beta_integration
   pnpm --dir apps/backend exec prisma db seed
   # Optional legacy curated import:
   pnpm --dir apps/backend run db:import-curated
   # REQUIRED for Hạ Long / Tháp Đồng Hồ (65562a67-84ff-44a0-990d-31917a2a9bd0) & all 759 Freeze V2 POIs:
   pnpm --dir apps/backend exec ts-node prisma/reconcile-freeze-v2.ts
   ```
   - **Important**: `prisma db seed` (`database/seed/places.json`) and `db:import-curated` (`data/curated/places_canonical.json`) do **not** contain Hạ Long, `Tháp Đồng Hồ` (`65562a67-84ff-44a0-990d-31917a2a9bd0`), or `place_sources` rows (and `youtube-updates-thap-dong-ho.e2e-spec.ts` deletes its temporary `Tháp Đồng Hồ` row in `afterAll` if it created it).
   - `apps/backend/prisma/reconcile-freeze-v2.ts` non-destructively (zero `TRUNCATE`) upserts categories, 50 destinations (including `ha-long`), all **759 Freeze V2 POIs** from `data/curated/gomate_places_freeze_v2.json` (including `Tháp Đồng Hồ`) + `place_sources`, and applies factual Wikimedia/OSM descriptions & media from `data/enrichment/poi_enrichment_pilot_60_v1.json`. Without running it, Sections B.4 and B.5 fail with `404 PLACE_NOT_FOUND` on a fresh database.
6. **Run Backend Real-DB E2E (`jest-e2e.json`)**:
   - `apps/backend/test/jest-e2e.json` connects to real PostgreSQL via `DATABASE_URL`.
   - **Secret Ordering Warning**: `apps/backend/test/youtube-updates-thap-dong-ho.e2e-spec.ts` sends unauthenticated/unsigned WebSub (`GET/POST /youtube/webhook`) and internal (`POST /youtube/events`) requests and **requires `YOUTUBE_WEBSUB_VERIFY_TOKEN`, `YOUTUBE_WEBSUB_SECRET`, and `YOUTUBE_EVENTS_INTERNAL_SECRET` to be blank/unset** during the test run. Keep those 3 variables blank in `.env` / `apps/backend/.env` during this step, then configure strong non-empty secrets immediately afterward before Section B.4 live verification. *(If re-running `test:e2e` later after Section B.4, temporarily blank those 3 keys in `apps/backend/.env` or unset them in shell-only env mode without `apps/backend/.env`.)*
   - Note: `ai-chat.e2e-spec.ts` and `planner.e2e-spec.ts` expect a running AI service at `AI_SERVICE_URL` (e.g. `http://127.0.0.1:8000`). Run either the targeted Beta Auth + YouTube specs or the full E2E suite (with AI service up):
   ```powershell
   # Targeted Beta Auth + YouTube real-DB E2E:
   pnpm --dir apps/backend exec jest --config ./test/jest-e2e.json --runInBand test/auth-recovery-oauth.e2e-spec.ts test/youtube-updates-thap-dong-ho.e2e-spec.ts

   # Full backend E2E (requires PostgreSQL + AI_SERVICE_URL):
   pnpm --dir apps/backend run test:e2e
   ```
   - **Pass Criteria**: All 10 migrations apply with `0` errors; `reconcile-freeze-v2.ts` reports `missingFreezeV2Count: 0` (`759/759` Freeze V2 POIs present); `auth-recovery-oauth.e2e-spec.ts` and `youtube-updates-thap-dong-ho.e2e-spec.ts` pass against live PostgreSQL without modifying `data/curated/gomate_places_freeze_v2.json`.

---

### 2. Real SMTP Credentials & Password Reset Live Check

1. **Configure SMTP in root `.env` (and sync to `apps/backend/.env`)** (`apps/backend/src/modules/mail/mail.module.ts` & `smtp-mail.transport.ts`):
   - `SMTP_HOST`: **MUST be non-empty** (e.g., `smtp.gmail.com` or `smtp.resend.com`). **Warning**: leaving `SMTP_HOST` blank falls back to `NoopLogMailTransport` outside `NODE_ENV=test` (logs masked email only, sends no email).
   - `SMTP_PORT`: `587` (STARTTLS) or `465` (TLS)
   - `SMTP_SECURE`: `'false'` for `587`, `'true'` for `465` (defaults to `port === 465` if omitted)
   - `SMTP_USER`: SMTP username (auth omitted if blank)
   - `SMTP_PASS`: SMTP password / app password
   - `SMTP_FROM`: e.g. `WanderAI <no-reply@your-domain.com>` (defaults to `WanderAI <no-reply@wanderai.local>`)
   - `APP_RESET_PASSWORD_URL`: link prefix written into the email (`?token=<rawToken>` appended). For Android deep-link testing via ADB or clickable app link, configure `wanderai://reset-password` or `wanderai://app/reset-password` (both registered in `apps/mobile/android/app/src/main/AndroidManifest.xml`), or uncomment & host `assetlinks.json` for `https://app.gomate.vn/reset-password`.
2. **Sync `.env` and Start Backend** from repo root:
   ```powershell
   Copy-Item .env apps/backend/.env
   pnpm --dir apps/backend run start:dev
   ```
3. **Execute Live Reset & Token Security Checks**:
   - **Happy Path**: Trigger `POST /auth/forgot-password` (or tap `"Quên mật khẩu?"` in Flutter) for a real test inbox -> verify `200 { sent: true, expiresInMinutes: 30 }` -> confirm email arrives with `APP_RESET_PASSWORD_URL?token=<rawToken>`.
   - **Validate & Reset**: Open deep link on device (`adb shell am start -a android.intent.action.VIEW -d "wanderai://reset-password?token=<rawToken>" com.example.wanderai_mobile`) or call `GET /auth/reset-password/validate?token=<rawToken>` -> `200 { valid: true }`; submit new password (`>= 6` chars) via `POST /auth/reset-password` -> `200 { reset: true }`.
   - **Replay / Used Token**: Re-open or resubmit the same `<rawToken>` -> backend returns `400` with `errorCode: "RESET_TOKEN_USED"` and Flutter renders inline `AppStateBanner`.
   - **Expired Token**: Wait `> 30` minutes (TTL hardcoded `PASSWORD_RESET_TTL_MINUTES = 30`) or test with an expired token row -> returns `400` with `errorCode: "RESET_TOKEN_EXPIRED"`.
   - **JWT Revocation**: Any access/refresh token issued **before** `POST /auth/reset-password` now fails (`401`) because `password-reset.service.ts` increments `user.tokenVersion` by `1`.
   - **Non-Enumeration**: Submitting an unregistered email to `POST /auth/forgot-password` returns the identical `200` payload without sending email.

---

### 3. Real Google & Facebook OAuth Configuration & Success / Cancel / Error Checklist

#### Network Transport Prerequisite (`AndroidManifest.xml` & `AppConstants`)
- `apps/mobile/android/app/src/main/AndroidManifest.xml` sets **`android:usesCleartextTraffic="false"`**.
- In **debug builds** on a physical Android device over USB, forward the local backend port so the app uses `http://localhost:3000` (avoiding cleartext LAN IP blocks):
  ```powershell
  adb -s <DEVICE_ID> reverse tcp:3000 tcp:3000
  ```
- In **`--profile` or `--release` builds**, `apps/mobile/lib/core/constants/app_constants.dart` **requires `--dart-define=API_BASE_URL=https://<your-https-host>`** and rejects `http://`, `localhost`, `127.0.0.1`, and `10.0.2.2`.

#### A. Google OAuth Setup
1. **Android Package Name** (`apps/mobile/android/app/build.gradle.kts`): `com.example.wanderai_mobile` (update `applicationId` before store release if changed).
2. **Extract Android Signing SHA-1**:
   ```powershell
   # Option 1 (Gradle from apps/mobile/android):
   cd D:\Do_an\wanderai_beta_integration\apps\mobile\android
   .\gradlew.bat signingReport

   # Option 2 (keytool on debug keystore):
   keytool -list -v -keystore "$env:USERPROFILE\.android\debug.keystore" -alias androiddebugkey -storepass android -keypass android
   ```
3. **Google Cloud Console**:
   - Create an **Android OAuth 2.0 Client ID** with package `com.example.wanderai_mobile` and the extracted SHA-1.
   - Create a **Web application OAuth 2.0 Client ID** (needed by `google_sign_in` `serverClientId` to mint an `idToken`).
   - **Device Requirement**: Physical Android device **with Google Play Services** (or Google APIs play-store emulator signed in to a Google account).
4. **Backend `.env` (sync root `.env` -> `apps/backend/.env` & restart backend)**:
   - Set `GOOGLE_CLIENT_ID`, `GOOGLE_WEB_CLIENT_ID`, and `GOOGLE_ANDROID_CLIENT_ID` (backend `HttpGoogleOAuthVerifier` validates `idToken` `aud` against the union of these three variables; note `GOOGLE_CLIENT_SECRET` in `.env.example` is **unused** by the backend verifier).
5. **Run Flutter with `--dart-define`**:
   ```powershell
   cd D:\Do_an\wanderai_beta_integration\apps\mobile
   flutter run -d <DEVICE_ID> --dart-define=GOOGLE_SERVER_CLIENT_ID=<YOUR_WEB_CLIENT_ID>.apps.googleusercontent.com --dart-define=API_BASE_URL=http://localhost:3000
   ```

#### B. Facebook OAuth Setup
1. **Meta for Developers Console**:
   - Enable Facebook Login, add Android platform with package `com.example.wanderai_mobile`, class `com.example.wanderai_mobile.MainActivity`, and Base64 key hash (`keytool -exportcert -alias androiddebugkey -keystore "$env:USERPROFILE\.android\debug.keystore" -storepass android | openssl sha1 -binary | openssl base64`).
2. **Mobile Android Strings** (`apps/mobile/android/app/src/main/res/values/strings.xml`):
   Replace the three placeholders before building:
   - `facebook_app_id`: `<YOUR_FACEBOOK_APP_ID>` (currently `0000000000000000`)
   - `facebook_client_token`: `<YOUR_FACEBOOK_CLIENT_TOKEN>` (currently `00000000000000000000000000000000`)
   - `fb_login_protocol_scheme`: `fb<YOUR_FACEBOOK_APP_ID>` (currently `fb0000000000000000`)
   *(Already wired in `AndroidManifest.xml` via `FacebookActivity`, `CustomTabActivity`, and `<queries><package android:name="com.facebook.katana"/></queries>`.)*
3. **Backend `.env` (sync root `.env` -> `apps/backend/.env` & restart backend)**:
   - Set `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` (both required by `HttpFacebookOAuthVerifier`).

#### C. Provider Acceptance Checklist (Execute for BOTH Google and Facebook)

| Scenario | Action on Physical Device | Pass Criteria |
|---|---|---|
| **Success** | Tap provider button -> choose test account -> grant consent | Backend `POST /auth/oauth/{google,facebook}` returns `200` with `access_token`, `refresh_token`, `user.providers`; Flutter clears guest mode, navigates to `postLoginRedirect` (or `/`), and `GET /users/me` succeeds. |
| **Cancel** | Tap provider button -> press Android Back / Cancel in Google account picker or Facebook dialog | `SdkAuthSocialPort` returns `SocialAuthCancelled()`; **0** backend `/auth/oauth/*` calls fired; **no** error banner shown; user stays cleanly on `LoginScreen` with existing email/password inputs intact. |
| **Error** | Test account without verified email, revoked token, or offline network during OAuth exchange | Backend returns structured error (`OAUTH_EMAIL_UNAVAILABLE` / `OAUTH_TOKEN_INVALID` / `OAUTH_PROVIDER_ERROR`) or `DioException` network error; Flutter renders inline `AppStateBanner` without losing form state or crashing. |

---

### 4. Real YouTube WebSub Secret, Latency Measurement, Tháp Đồng Hồ 5 Fields, Hạ Long Fallback & Idempotency

1. **Configure YouTube Env Vars in root `.env` (sync to `apps/backend/.env` and restart backend)**:
   - `YOUTUBE_WEBSUB_VERIFY_TOKEN=<strong-random-verify-token>`
   - `YOUTUBE_WEBSUB_SECRET=<strong-random-hmac-secret>`
   - `YOUTUBE_EVENTS_INTERNAL_SECRET=<strong-random-internal-secret>`
   - `YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS=300000` *(5 minutes default; exact key name — do not use `YOUTUBE_REALTIME_SLA_MAX_MS`)*
   - **CRITICAL SECURITY WARNING**: In `youtube.service.ts` and `youtube-internal-secret.guard.ts`, if `YOUTUBE_WEBSUB_VERIFY_TOKEN`, `YOUTUBE_WEBSUB_SECRET`, or `YOUTUBE_EVENTS_INTERNAL_SECRET` is blank/unset, the backend **skips verification** (`return true`). Owner **MUST** set non-empty strong secrets in real/staging environments (after finishing Section B.1 Step 6 `test:e2e`), then run `Copy-Item .env apps/backend/.env` and restart `pnpm --dir apps/backend run start:dev`.
2. **Verify Guards Reject Unauthorized Requests**:
   - `GET /youtube/webhook?hub.mode=subscribe&hub.topic=https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC_TEST&hub.challenge=abc&hub.verify_token=wrong` -> `403` `YOUTUBE_EVENT_UNAUTHORIZED`.
   - `POST /youtube/webhook` without valid `X-Hub-Signature` / `X-Hub-Signature-256` -> `401`/`403` `YOUTUBE_EVENT_UNAUTHORIZED`.
   - `POST /youtube/events` without matching `x-youtube-internal-secret` -> `401` `YOUTUBE_EVENT_UNAUTHORIZED`.
3. **Live Ingestion, 5-Field Tháp Đồng Hồ Check & Real Source-to-App Latency Measurement**:
   - Send a signed Atom XML (`POST /youtube/webhook`) or internal JSON (`POST /youtube/events`) for `Tháp Đồng Hồ` (`65562a67-84ff-44a0-990d-31917a2a9bd0`) with current UTC `publishedAt`:
     - Inspect `GET /places/65562a67-84ff-44a0-990d-31917a2a9bd0/youtube-updates` and the Flutter `PlaceDetailScreen` `"Cập nhật cộng đồng từ YouTube"` section.
     - **Pass Criteria (5 fields)**: Item contains `placeId` (`65562a67-84ff-44a0-990d-31917a2a9bd0`), `source` (`"youtube"`), `publishedAt`, `receivedAt`, `updatedAt`.
     - **Pass Criteria (Latency & SLA Badge)**: Server reports `ingestLatencyMs = receivedAt - publishedAt` and `serverDeliveredAt`; Flutter measures `endToEndLatencyMs = clientRenderedAt - publishedAt` and displays `"Thời gian thực"` **only** when `0 <= endToEndLatencyMs <= 300000` ms. Send a second event with `publishedAt` `> 6` minutes old and confirm Flutter displays `"Cập nhật gần đây"` (never `"Thời gian thực"`).
4. **Hạ Long City-Level Fallback Check**:
   - Send an event mentioning `"Hạ Long"` without a specific POI match -> confirm `status: "LINKED_CITY"`, `scope: "CITY"`, `placeId: null` on `GET /destinations/ha-long/youtube-updates` (and `cityFallbackItems` on `GET /places/:id/youtube-updates`), and confirm Flutter renders the city-level fallback banner (`"Chưa có cập nhật riêng cho địa điểm này · Cập nhật cấp thành phố: Hạ Long"` when no direct POI items exist, or subheader/badge `"Cập nhật cấp thành phố: Hạ Long"` when direct POI items also exist).
5. **Duplicate Replay Idempotency & R4 Table Isolation Check**:
   - Replay the exact same event (`dedupeKey` / `videoId` + `publishedAt`) twice -> confirm `deliveryCount: 2` and **exactly 1 row** in `youtube_poi_updates` (`SELECT COUNT(*) FROM youtube_poi_updates WHERE video_id = ...` = `1`).
   - Confirm `documents` and `place_sources` row counts remain unchanged before and after YouTube ingestion.

---

### 5. Physical Android Device `adb shell screenrecord` Video Capture Instructions

**Why Emulator Video Was Delegated**:
- On headless `GoMate_W3_Test` (API 35 x86_64 SwiftShader OpenGLES), `adb shell screenrecord` failed in both probes:
  - `/sdcard/m5_probe.mp4`: `Unable to open '/sdcard/m5_probe.mp4': Operation not permitted` (exit code `1`).
  - `/data/local/tmp/m5_probe.mp4`: exit code `235` producing a `0`-byte MP4 file.
- Automated widget coverage (`halong_trip_save_journey_test.dart`) + `390×844` screenshots already cover all 3 flows; run the commands below on a **physical Android device** (`adb devices` shows `<DEVICE_ID> device`) to capture real MP4 acceptance videos.

*(Tip: `screenrecord` max duration is `180` seconds per run; press `Ctrl+C` when done and wait 1–2s before `adb pull`. Use `/sdcard/Download/` or `/data/local/tmp/` if `/sdcard/` root denies writes.)*

1. **Scenario 1 — Save Success (`Tháp Đồng Hồ`)**:
   ```powershell
   adb -s <DEVICE_ID> shell screenrecord --time-limit 120 /sdcard/Download/01_save_success.mp4
   ```
   - **Actions**: Open GoMate -> explore Hạ Long -> search `"Tháp Đồng Hồ"` -> open `PlaceDetailScreen` -> tap `"Lưu vào chuyến đi"` (if guest, sign in via `/login?redirect=/places/65562a67-84ff-44a0-990d-31917a2a9bd0` and confirm automatic redirect back to Tháp Đồng Hồ) -> choose or create trip -> tap `"Lưu"` -> open `/trips` and confirm Tháp Đồng Hồ appears in itinerary.
   - Stop with `Ctrl+C` and pull:
     ```powershell
     adb -s <DEVICE_ID> pull /sdcard/Download/01_save_success.mp4 .
     ```
2. **Scenario 2 — Cancel Login**:
   ```powershell
   adb -s <DEVICE_ID> shell screenrecord --time-limit 90 /sdcard/Download/02_cancel_login.mp4
   ```
   - **Actions**: Ensure signed out (guest mode) -> open Tháp Đồng Hồ `PlaceDetailScreen` -> tap `"Lưu vào chuyến đi"` -> confirm `/login?redirect=...` displays redirect notice -> tap `"Hủy đăng nhập · Quay lại"` -> confirm app returns cleanly to Tháp Đồng Hồ in guest mode with **0 error banners** and **0 trips created**.
   - Stop with `Ctrl+C` and pull:
     ```powershell
     adb -s <DEVICE_ID> pull /sdcard/Download/02_cancel_login.mp4 .
     ```
3. **Scenario 3 — Network Loss during Save**:
   ```powershell
   adb -s <DEVICE_ID> shell screenrecord --time-limit 120 /sdcard/Download/03_network_loss_save.mp4
   ```
   - **Actions**: Signed in on Tháp Đồng Hồ -> tap `"Lưu vào chuyến đi"` -> choose or enter new trip name -> turn on **Airplane Mode** (or disable Wi-Fi & mobile data) -> tap `"Lưu"` / `"Tạo chuyến & Lưu"` -> confirm warning `AppStateBanner` (`"Mất kết nối mạng..."`) with `"Thử lại"` CTA and preserved trip selection / `_createdPendingTrip` -> disable Airplane Mode -> tap `"Thử lại"` -> confirm single trip/item saves cleanly with **0 duplicate trips**.
   - Stop with `Ctrl+C` and pull:
     ```powershell
     adb -s <DEVICE_ID> pull /sdcard/Download/03_network_loss_save.mp4 .
     ```

---

### 6. Physical Android Device `--profile` GPU Benchmark Command

1. **Run the Automated `--profile` Scroll & Open-Latency Benchmark** against your physical device (writing to `device_after_perf.json` so existing AVD artifacts are preserved):
   ```powershell
   cd D:\Do_an\wanderai_beta_integration\apps\mobile
   $env:PERF_OUT_FILE = "D:\Do_an\wanderai_beta_integration\docs\beta\mobile\benchmarks\device_after_perf.json"
   flutter drive --no-dds --driver=test_driver/perf_driver.dart --target=integration_test/perf_benchmark_test.dart --profile -d <DEVICE_ID>
   ```
   - **Pass Criteria**: Command exits `0`, produces `device_after_perf.json` with `dest_sheet_open_ms`, `trip_list_open_ms`, `trip_detail_open_ms`, and hardware-GPU `scroll_timelines` (`dest_sheet_scroll`, `trip_list_scroll`, `trip_detail_scroll`) under the `16.67 ms` 60Hz frame budget (or device refresh budget).
2. **Launch Full App in `--profile` Mode Against Staging/HTTPS Backend**:
   ```powershell
   cd D:\Do_an\wanderai_beta_integration\apps\mobile
   flutter run --profile -d <DEVICE_ID> --dart-define=API_BASE_URL=https://<your-staging-backend> --dart-define=GOOGLE_SERVER_CLIENT_ID=<YOUR_WEB_CLIENT_ID>.apps.googleusercontent.com
   ```
   *(Reminder: `AppConstants.resolveApiBaseUrl` requires `https://` and non-loopback hosts in `--profile` and `--release` modes.)*
