# PROJECT STATUS — WANDERAI (GoMate)

**Last Updated:** 2026-10-03T16:00+07:00  
**Current Phase:** TASK 07.1 regression audit done — 2 regressions found (AI Planner, provenance of 11 places); see "Known Regressions"  
**Current Milestone:** Flutter Map with verified OSM places from PostGIS; Review Intelligence Blocked on DUA  

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
| 15 | Database rows — 2026-10-01: 50 dest, 112 places, 1 user. **Current (2026-10-03): 50 dest, 220 places (108 sourced + 112 synthetic), 5 users** | `SELECT count(*)`; `docs/data/current-database-state.md` | 2026-10-03 |
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
| 33 | AI Trip Planner via TripContext | `POST /trips/:id/ai-plan`, prompt `TRAVEL_PLANNER_V1` — **live call currently broken, see R1** | 2026-10-01 |
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
| 48 | Task 06.4 Track A: RAG Ingestion & pgvector | 10 Wikivoyage destinations + OSM places: 628 chunks in pgvector (384-dim HNSW) | 2026-10-01 |
| 49 | Task 06.4 Track A: Frozen Retrieval Evaluation | Da Nang culinary test (`RAG-EVAL-01`) verified with 0.68 similarity (4 frozen queries rerun in 07.1; only EVAL-01 documented) | 2026-10-01 |
| 50 | Task 06.4 Track B: ViHoRec Recommendation Pipeline | 17,911 interactions audited, MostPop baseline evaluated on 798 test users | 2026-10-01 |
| 51 | Task 07: Map Feature — flutter_map + PostGIS | 108 places with place_sources on map (97 with a genuine OSM source, 11 unverifiable — see TASK 07.1 R2), category filter, nearby search, preview | 2026-10-02 |
| 52 | ADR-005 Map Provider (flutter_map + OSM tiles) | `docs/architecture/decisions/ADR-005-map-provider.md` | 2026-10-02 |

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
| Backend Integration (Jest / Supertest) | 42 | 0 | 42 |
| AI Service (pytest — tools, chat, planner, pipeline, RAG, recommendation) | 37 | 0 | 37 |
| Mobile App (Flutter Widget & Unit Tests) | 60 | 0 | 60 |
| **Total Automated Baseline** | **139** | **0** | **139** |

---

## Architectural Decisions (ADRs)

| # | Title | Status |
|---|-------|--------|
| ADR-001 | Single PostgreSQL Instance with PostGIS + pgvector | ACCEPTED |
| ADR-002 | Real Travel Data Pipeline from OSM with Entity Resolution | ACCEPTED |
| ADR-003 | Trip Context Schema Extension for Deterministic Validation | ACCEPTED |
| ADR-004 | Domain-Segregated Dataset Matrix (ViHoRec for RecSys, VLSP for ABSA, Wikivoyage for RAG) | ACCEPTED |
| ADR-005 | Map Provider: flutter_map + OpenStreetMap tiles (no API keys, thesis-friendly) | ACCEPTED |

---

## TASK 07.1 — Regression Audit (2026-10-03, verification only)

Full report: `docs/audit/task-07.1-regression-audit.md`. DB counts: `docs/data/current-database-state.md`. The project is **NOT fully healthy**.

### Known Regressions

| # | Subsystem | Problem | Evidence |
|---|-----------|---------|----------|
| R1 | AI Planner | `apps/ai-service/app/routers/planner.py` hardcodes retired model `gemini-2.0-flash` (404) and `max_output_tokens=4096` is exhausted by thinking tokens on `gemini-3.5-flash`. Live `POST /trips/:id/ai-plan` returns 500. The 37 pytest tests still pass (mock/no-key fallback = false green). | live call + direct Gemini probe |
| R2 | Provenance | 11 of 108 "verified" places have a `place_sources` OSM ID that is not a genuine matching OSM node (5 point to unrelated nodes, 6 do not exist on Overpass). Genuine: 97 places. The 8 reviews all sit on these 11 places. | Overpass check of 110 source IDs |
| R3 | Data | 100 of 108 verified places have a fabricated default rating 4.5 (`resolve.py` default); the map preview shows it. | DB query |

### Known Limitations

- No `/auth/logout` endpoint (client-side logout only); JWT secret fallback literals differ between `auth.service.ts` and `jwt.strategy.ts`.
- JWT is not forwarded to FastAPI (NestJS validates, sends `user_id`); FastAPI has CORS `*` and no auth.
- AI chat memory is in FastAPI process memory (`ai_sessions`/`ai_messages` have 0 rows); `search_places` tool reads `destinations`.
- `GET /places/not-a-uuid` returns 500; `/places/nearby` with invalid lat/lng returns 200.
- 112 unsourced synthetic/legacy places are the seed loaded twice (2 x 56); default `/places` (no `verifiedOnly`) returns them.
- 56 RAG chunks labelled OSM/ODbL are attached to unsourced synthetic places; `documents` extra columns/HNSW index exist only via raw SQL, not Prisma migrations (fresh `migrate deploy` lacks them).
- RAG: only RAG-EVAL-01 documented (the other 3 queries were rerun; EVAL-04 has no `safety` topic chunk). No Precision@K.
- RecSys split is per-user leave-last-one-out, not globally temporal; MostPop is the only baseline.
- Map tiles do not load on the author's network (OSM hosts blocked/DNS-poisoned); CARTO and OpenFreeMap are reachable. Not fixed.
- Flutter: "An toàn" tab is a placeholder; some UI strings lack diacritics.
- Test-count history (47/69/86/106/110/118/139) = cumulative totals at successive merges; current baseline is 139.
