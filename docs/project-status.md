# PROJECT STATUS — WANDERAI (GoMate)

**Last Updated:** 2026-10-04T04:45+07:00  
**Current Phase:** END-OF-DAY VERIFIED BASELINE — TASK 07.6 + 07.6.1 merged to develop (`57b3ed4`), synchronized with `origin/develop`  
**Current Milestone:** GoMate Design System & UI Foundation Established; Clean OpenStreetMap Humanitarian Basemap Stable; Database Invariants Verified (821 prod docs, 357 verified places); Ready for TASK 08 (Place Detail Screen)  

---

## Completed Tasks

| # | Task | Evidence | Date |
|---|------|----------|------|
| 1 | Security check — .env in .gitignore, no secrets in history | `.gitignore` line 4 | 2026-10-01 |
| 2 | Docker Compose — PostgreSQL + Redis running | `docker ps`: healthy | 2026-10-01 |
| 3 | PostgreSQL 16.15 verified | `SELECT version()` | 2026-10-01 |
| 4 | PostGIS 3.4 verified | `SELECT PostGIS_Version()` | 2026-10-01 |
| 5 | pgvector 0.8.6 verified | `SELECT extversion FROM pg_extension` | 2026-10-01 |
| 6 | Redis verified | `redis-cli ping` → PONG | 2026-10-01 |
| 7 | NestJS backend — build OK, 0 errors | `npx nest build` exit 0 | 2026-10-01 |
| 8 | Backend health — GET /health | `{"status":"ok"}` | 2026-10-01 |
| 9 | Backend auth — POST /auth/login | JWT token 224 chars | 2026-10-01 |
| 10 | Backend destinations — GET /destinations | 20 items returned | 2026-10-01 |
| 11 | FastAPI AI service — startup OK | port 8000 | 2026-10-01 |
| 12 | AI health — GET /health | `{"status":"ok","llm_provider":"gemini"}` | 2026-10-01 |
| 13 | AI chat — POST /chat | Wandy replied (865 chars) | 2026-10-01 |
| 14 | Database — 37 tables verified on 2026-10-01 (2026-10-03: 38 relations in `public`, incl. `_prisma_migrations` and PostGIS objects) | `information_schema` count | 2026-10-01 |
| 15 | Database rows — 2026-10-01: 50 dest, 112 places, 1 user. **Current (2026-10-04): 50 dest, 480 places (357 verified + 123 without verified source), 357 place_sources (13 quarantined), 5 users** | `SELECT count(*)`; `docs/data/current-database-state.md` | 2026-10-03 |
| 16 | PlaceSource model + migration | `place_sources` table (10 columns) | 2026-10-01 |
| 17 | Fake data labelled as synthetic | `data/manifests/sources.yaml` | 2026-10-01 |
| 18 | Data pipeline directories | `data/{raw,processed,seed,evaluation,manifests,restricted}` | 2026-10-01 |
| 19 | Flutter foundation — 0 errors | `flutter analyze` clean | 2026-10-01 |
| 20 | Flutter web — runs on Chrome | Debug service connected port 5000 | 2026-10-01 |
| 21 | Flutter thin slice — Home loads destinations from API | GET /destinations → grid | 2026-10-01 |
| 22 | AI tests — 37 passed | `pytest tests/ -v` → 37 passed | 2026-10-01 |
| 23 | Flutter tests — 39 passed | `flutter test` → 39 passed | 2026-10-01 |
| 24 | Backend E2E tests — 42 passed | `npm run test:e2e` → 42 passed | 2026-10-01 |
| 25 | NestJS /ai/chat protected with JwtAuthGuard | Returns 401 without token, 200 with JWT | 2026-10-01 |
| 26 | Flutter AI chat models, repo, provider, UI screen | Connected to /ai route in app_router.dart | 2026-10-01 |
| 27 | AI Chat API & Architecture documentation | `docs/api/ai-chat-api.md`, `docs/ai/ai-chat.md` | 2026-10-01 |
| 28 | ADR-003 Trip Context Attributes Schema Extension | `docs/architecture/decisions/ADR-003-trip-context-schema.md` | 2026-10-01 |
| 29 | Prisma migration for Trip Context | `20261001083200_add_trip_context_fields` | 2026-10-01 |
| 30 | Trips backend authorization & validation | 11 E2E security & CRUD tests | 2026-10-01 |
| 31 | Flutter Trips flow & TripContext abstraction | 11 Flutter unit & widget tests | 2026-10-01 |
| 32 | Trips API & Flow documentation | `docs/api/trips-api.md`, `docs/architecture/trip-flow.md` | 2026-10-01 |
| 33 | AI Trip Planner via TripContext | `POST /trips/:id/ai-plan`, prompt `TRAVEL_PLANNER_V1` — live call restored in TASK 07.2 (model `gemini-3.5-flash`, 16384 output tokens); see R1 | 2026-10-01 |
| 34 | Bulk Itinerary Atomic Persistence | `POST /trips/:id/itinerary/bulk` via `prisma.$transaction` | 2026-10-01 |
| 35 | Deterministic Validation & Budget Arithmetic | Day cost & budget comparison computed by code | 2026-10-01 |
| 36 | AI Planner Evaluation Dataset | `data/evaluation/planner/` (3 scenarios + evaluator) | 2026-10-01 |
| 37 | AI Planner Mobile Preview & Overwrite Warning | Dialog + DraggableScrollableSheet preview modal | 2026-10-01 |
| 38 | AI Planner API & Architecture Documentation | `docs/api/ai-planner-api.md`, `docs/ai/ai-planner.md` | 2026-10-01 |
| 39 | Real Data Pipeline — OSM Collection & Parser | `data/pipelines/osm/`, ODbL 1.0 compliant | 2026-10-01 |
| 40 | Multi-signal Entity Resolution Engine | `data/pipelines/entity_resolution/`, canonical places | 2026-10-01 |
| 41 | Review Cleaner & Canonical Linking | `data/pipelines/reviews/`, quarantined synthetic reviews | 2026-10-01 |
| 42 | Data Quality Audit & Reporting | `data/pipelines/quality_checker.py`, 100% bounds check | 2026-10-01 |
| 43 | Idempotent PostgreSQL Import | `apps/backend/prisma/import-curated.ts` (`npm run db:import-curated`) | 2026-10-01 |
| 44 | Backend Places Module & PostGIS Spatial API | `GET /places`, `GET /places/nearby` (ST_DWithin), `GET /places/:id` | 2026-10-01 |
| 45 | Task 06.1 Review Provenance & Synthetic Audit | `review-provenance.json`, `database-provenance-audit.md` | 2026-10-01 |
| 46 | Task 06.2 Review Dataset Discovery Matrix | `review-dataset-candidates.md`, `review-dataset-candidates.yaml` | 2026-10-01 |
| 47 | Task 06.3 Dataset Acquisition Clearance | `vlsp2018-access-request.md`, `vimacsa-access.md`, `dataset-role-matrix.md` | 2026-10-01 |
| 48 | Task 06.4 Track A: RAG Ingestion & pgvector | 10 Wikivoyage destinations + OSM places: 628 chunks in pgvector (384-dim HNSW); now 821 documents after TASK 07.5 | 2026-10-01 |
| 49 | Task 06.4 Track A: Frozen Retrieval Evaluation | Da Nang culinary test (`RAG-EVAL-01`) verified with 0.68 similarity (4 frozen queries rerun in 07.1; only EVAL-01 documented) | 2026-10-01 |
| 50 | Task 06.4 Track B: ViHoRec Recommendation Pipeline | 17,911 interactions audited, MostPop baseline evaluated on 798 test users | 2026-10-01 |
| 51 | Task 07: Map Feature — flutter_map + PostGIS | 97 places with a genuine OSM source on the map (11 non-genuine sources quarantined in TASK 07.3; rating shown as unavailable), category filter, nearby search, preview | 2026-10-02 |
| 52 | ADR-005 Map Provider (flutter_map + OSM tiles) | `docs/architecture/decisions/ADR-005-map-provider.md` | 2026-10-02 |
| 53 | Task 07.4: OSM Data Enrichment & Verified Serving | 357 verified places & sources (ODbL), verifiedOnly default | 2026-10-04 |
| 54 | Task 07.5: RAG Ingestion & Grounding Contract | 821 documents (464 Wikivoyage + 357 OSM); grounding contracts | 2026-10-04 |
| 55 | Task 07.5.1: Live Wandy Grounding & Source UI | Source chips in Flutter UI, e2e contract tests | 2026-10-04 |
| 56 | Task 07.6: GoMate Design System + Map UX Stability | Central tokens, shared widgets, clean OSM HOT tiles, GlobalKey fix, honest rating | 2026-10-04 |
| 57 | ADR-006 Map Tile Provider (OpenStreetMap Humanitarian) | `docs/architecture/decisions/ADR-006-map-tile-provider.md` | 2026-10-04 |
| 58 | Task 07.6.2 & End-of-Day Verified Baseline | Merged to `develop` (`57b3ed4`), pushed to `origin/develop`; 231 tests pass; 821 docs / 357 verified places verified | 2026-10-04 |

---

## Blocked Tasks & Dataset Clearances

| Task | Blocked By | Clearance Status | Action Required |
|------|-----------|------------------|-----------------|
| **Review Intelligence (future task)** | VLSP 2018 ABSA Hotel DUA | `REQUEST_NOT_SENT` | Human members must sign `DUA_VLSP2018.pdf` and email `vlsp.resources@gmail.com` |
| **Multimodal Review AI** | ViMACSA Research Access | `REQUEST_NOT_SENT` | Academic request to UIT NLP Group (`kietnv@uit.edu.vn`) |

---

## Automated Test Suites

| Suite | Pass | Fail | Total |
|-------|------|------|-------|
| Backend Integration (Jest / Supertest) | 62 | 0 | 62 |
| AI Service (pytest — tools, chat, planner, pipeline, RAG, recommendation, provenance, RAG ingestion, grounding contract; +2 opt-in live tests skipped by default) | 87 | 0 | 87 |
| Mobile App (Flutter Widget & Unit Tests) | 82 | 0 | 82 |
| **Total Automated Baseline** | **231** | **0** | **231** |

---

## Architectural Decisions (ADRs)

| # | Title | Status |
|---|-------|--------|
| ADR-001 | Single PostgreSQL Instance with PostGIS + pgvector | ACCEPTED |
| ADR-002 | Real Travel Data Pipeline from OSM with Entity Resolution | ACCEPTED |
| ADR-003 | Trip Context Schema Extension for Deterministic Validation | ACCEPTED |
| ADR-004 | Domain-Segregated Dataset Matrix (ViHoRec for RecSys, VLSP for ABSA, Wikivoyage for RAG) | ACCEPTED |
| ADR-005 | Map Provider: flutter_map + OpenStreetMap tiles (no API keys, thesis-friendly) | SUPERSEDED by ADR-006 |
| ADR-006 | Map Tile Provider: OpenStreetMap Humanitarian (HOT) with OSM-FR Fallback (resolves blocked upstream OSM and eliminates watermark, zero API key) | ACCEPTED |

---

## TASK 07.1 — Regression Audit (2026-10-03, verification only)

Full report: `docs/audit/task-07.1-regression-audit.md`. DB counts: `docs/data/current-database-state.md`. The project is **NOT fully healthy**.

### Known Regressions

| # | Subsystem | Problem | Evidence |
|---|-----------|---------|----------|
| R1 | AI Planner — **FIXED in TASK 07.2 (2026-10-04)**, see `docs/ai/ai-planner.md` §8. Original problem: | `apps/ai-service/app/routers/planner.py` hardcodes retired model `gemini-2.0-flash` (404) and `max_output_tokens=4096` is exhausted by thinking tokens on `gemini-3.5-flash`. Live `POST /trips/:id/ai-plan` returns 500. The 37 pytest tests still pass (mock/no-key fallback = false green). | live call + direct Gemini probe |
| R2 | Provenance — **FIXED in TASK 07.3**: 11 non-genuine sources moved to `place_source_quarantine`; verifiedOnly = 97. Original problem: | 11 of 108 "verified" places have a `place_sources` OSM ID that is not a genuine matching OSM node (5 point to unrelated nodes, 6 do not exist on Overpass). Genuine: 97 places. The 8 reviews all sit on these 11 places. | Overpass check of 110 source IDs |
| R3 | Data — **FIXED in TASK 07.3**: `places.rating` nullable, all ratings NULL, UI shows "Chưa có đánh giá". Original problem: | 100 of 108 verified places have a fabricated default rating 4.5 (`resolve.py` default); the map preview shows it. | DB query |
| R4 | RAG — **FIXED in TASK 07.3** | 56 chunks on synthetic places (+11 on demoted places) labelled OSM/ODbL: 67 moved to `document_quarantine`; `documents` 628 -> 561 (later 821 after TASK 07.5 re-ingestion) | `docs/audit/task-07.3-provenance-remediation.md` |
| R5 | Reviews — **FIXED in TASK 07.3** | 9 mock reviews now `source=synthetic`, `trusted=false`, hidden and excluded from aggregates | same |

### Known Limitations

- No `/auth/logout` endpoint (client-side logout only); JWT secret fallback literals differ between `auth.service.ts` and `jwt.strategy.ts`.
- JWT is not forwarded to FastAPI (NestJS validates, sends `user_id`); FastAPI has CORS `*` and no auth.
- AI chat memory is in FastAPI process memory (`ai_sessions`/`ai_messages` have 0 rows); `search_places` tool reads `destinations`.
- `GET /places/not-a-uuid` returns 500; `/places/nearby` with invalid lat/lng returns 200.
- 112 unsourced synthetic/legacy places are the seed loaded twice (2 x 56); default `/places` (no `verifiedOnly`) returns them.
- `documents` extra columns/HNSW index exist only via raw SQL, not Prisma migrations (fresh `migrate deploy` lacks them).
- RAG: only RAG-EVAL-01 documented (the other 3 queries were rerun; EVAL-04 has no `safety` topic chunk). No Precision@K.
- RecSys split is per-user leave-last-one-out, not globally temporal; MostPop is the only baseline.
- Map tiles: Resolved in ADR-006 using OpenStreetMap Humanitarian (HOT) with OSM-FR fallback; 100% reachable in Vietnam without VPN, zero watermark.
- Flutter: "An toàn" tab is a placeholder; some UI strings lack diacritics.
- Test-count baseline: 231 passed (Backend: 62, AI Service: 87 passed + 2 live skipped, Flutter: 82).
- Flutter web: GlobalKey duplicate-widget exception resolved in TASK 07.6 via `RouterNotifier` with persistent root/shell navigator keys.
- Planner latency ~30 s per plan (real Gemini); Flutter ai-plan request uses a 75 s timeout.
- Categories & Places: 357 verified places across categories (`culture`, `nature`, `entertainment`, `restaurant`, `hotel`) enriched in TASK 07.4; 123 unsourced places remain in the DB and are hidden by default (`verifiedOnly=true`).

## TASK 07.5 — RAG re-ingestion & grounding contract (MERGED into develop `1a2bbf2`)
- Production RAG: **821 documents = 464 Wikivoyage + 357 OSM** (357/357 verified places covered); `document_quarantine` 164; 357 verified places (480 places total, 123 unsourced hidden by default); 0 provenance violations, 0 duplicate hashes, 0 NULL embeddings; ingestion idempotent.
- A. Deterministic RAG: verified (retrieval tests, provenance audit, idempotency, frozen queries unchanged vs. before).
- B. Chat grounding (mock provider only): `/chat` injects retrieved context and returns `sources`; Wandy system prompt now forbids facts outside retrieved context/tool results, with exact fallbacks for missing price / opening hours / rating.
- C. Live Gemini: PENDING due to HTTP 429 quota.

## TASK 07.5.1 — Live Wandy Grounding Verification & Source UI (branch feat/wandy-grounding-source-ui)
- Sources API Contract: `data.sources: string[]` verified across FastAPI -> NestJS AI Proxy -> Flutter Mobile.
- NestJS E2E: 4 tests added in `test/ai-chat.e2e-spec.ts` (JWT auth check, validation, sources preservation, empty sources handling). Total backend tests: 62.
- Flutter Chat Model & Screen: `ChatResponse.sources` and `ChatMessage.sources` implemented. `AiChatScreen` renders compact, secondary source chips with links to OpenStreetMap and Wikivoyage. Hidden when empty or user message.
- Flutter Tests: 8 unit & widget tests in `test/chat_sources_test.dart` (parsing, empty sources, multiple sources, chips rendering, hidden when empty, tap behavior, long URL overflow safety, backward compatibility). Total mobile tests: 70.
- Live Gemini Grounding: PENDING (Provider returned HTTP 429 RESOURCE_EXHAUSTED on controlled check `test_chat_live.py`). Not fabricated.
- Baseline Tests: Backend 62 passed, AI 87 passed (+ 2 skipped live tests), Flutter 70 passed. All builds & linter clean.

## TASK 07.6 — GoMate Design System + UI Foundation + Map UX Stability (branch feature/ui-foundation-map-stability)
- Central GoMate Design System: `apps/mobile/lib/core/theme/` (colors, spacing, radius, typography, theme) based on `docs/design/gomate-design-system-ux-spec-v1.md`.
- Shared Reusable Widgets: `ResponsiveWrapper`, `AppButton`, `AppCard`, `AppChip`, `AppBadge`, `RatingView`, `AppLoading`, `AppEmptyState`, `AppErrorState`.
- Layout Stability: Responsive max-width container (640px phone/sheet, 720px tablet, 800px desktop) eliminated vast whitespace on desktop/web viewports.
- Router & Lifecycle Stability: Persistent root and shell navigator keys via `RouterNotifier` with `refreshListenable`, permanently eliminating the "Multiple widgets used the same GlobalKey" console exception.
- Map Provider & Grey Tiles: ADR-006 adopted OpenStreetMap Humanitarian (HOT) raster tiles (`https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png`) with OSM-FR fallback, resolving both blocked upstream OSM and the CARTO unauthenticated watermark banner.
- Map Preview Sheet & Stale State: Category marker filtering now clears `selectedPlace` (`clearSelectedPlace: true`), preventing stale preview sheet state across filter changes.
- Rating Integrity & Truth in Advertising: `RatingView` strictly displays "Chưa có đánh giá" when rating is `null` or `0.0`. Zero synthetic or fabricated ratings displayed.
- Wandy AI Chat Polish: Styled with GoMate design tokens and responsive container while preserving 100% of grounded source chips (`OpenStreetMap`, `Wikivoyage`).
- Automated Baseline: Backend 62 passed, AI 87 passed (+ 2 skipped live tests), Flutter 82 passed (12 new comprehensive tests). Total: **231 passed**. All builds, analyzer, and linter clean.

## TASK 07.6.1 — Final Map Tile Verification & Cleanup (branch feature/ui-foundation-map-stability)
- Watermark Resolution: Eliminated CARTO unauthenticated watermark banner ("API KEY REQUIRED carto.com/basemaps/apikey") by switching to OpenStreetMap Humanitarian (HOT) with OSM-FR fallback.
- Tile Reachability & Speed: 100% reachable in Vietnam without VPN (HTTP 200, ~165ms latency, CORS `*`).
- Attribution: Visible attribution updated to `OpenStreetMap contributors` and `Tiles: Humanitarian OpenStreetMap Team / OSM France`.
- Zero Key Exposure: Zero API keys or secrets required or committed.
- Documentation: Updated `docs/architecture/decisions/ADR-006-map-tile-provider.md` and `docs/architecture/ui-architecture.md`.

## TASK 07.6.2 & End-of-Day Final Verified Baseline (MERGED into develop `57b3ed4`)
- **Branch & Sync:** `develop` at commit `57b3ed4`, 100% synchronized with `origin/develop`.
- **Merge Strategy:** `feature/ui-foundation-map-stability` merged into `develop` with `--no-ff`.
- **Database Invariants Verified (PostgreSQL):**
  - Verified OSM places: **357** (Total places: 480; 123 unsourced legacy/synthetic places hidden by default).
  - OSM production documents: **357** (one document per verified place; 0 provenance violations).
  - Wikivoyage production documents: **464** (fingerprint unchanged).
  - Production documents total: **821** (464 Wikivoyage + 357 OSM).
  - Quarantined documents: **164** in `document_quarantine`.
  - NULL embeddings: **0**.
  - OSM docs without verified place_sources: **0**.
  - Trusted synthetic reviews: **0**.
  - Fabricated ratings on verified places: **0** (all verified places honestly display "Chưa có đánh giá").
- **Automated Regression Suite:**
  - Backend E2E: **62 passed** (9 suites)
  - Backend Build: clean (`nest build` exit 0)
  - Backend Lint: **0 errors**, 44 warnings
  - AI Service: **87 passed**, 2 opt-in live tests skipped, 0 failed
  - Flutter Tests: **82 passed**, 0 failed
  - Flutter Static Analysis: **No issues found!**
  - Total Passing Tests: **231 passed**
- **Browser E2E Smoke Test (7/7 PASSED):**
  - Clean HOT basemap tiles, zero "API KEY REQUIRED" watermark.
  - Zero "Multiple widgets used the same GlobalKey" exceptions.
  - Zero layout overflow (`RenderFlex`) errors.
  - Honest rating ("Chưa có đánh giá") on place preview sheet.
  - Stale preview sheet automatically dismissed on category change.
  - Wandy AI chat renders secondary source chips (`Wikivoyage`, `OpenStreetMap`).
  - Full round-trip navigation verified across tabs.
- **Next Planned Milestone:** TASK 08 — Place Detail Screen & Verified Location Experience.
