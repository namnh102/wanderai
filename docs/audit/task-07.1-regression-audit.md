# TASK 07.1 — Full Regression & Architecture Integrity Audit

Date: 2026-10-03. Verification only: no application code was changed. Verdict: **the project is NOT fully healthy** (AI Planner regression, provenance contradiction).

## Classification

| Subsystem | Result | Key reason |
|---|---|---|
| Auth | PASS WITH LIMITATION | No server logout/revocation; JWT secret fallbacks inconsistent |
| Backend | PASS WITH LIMITATION | `/places/not-a-uuid` → 500; nearby with invalid lat/lng → 200 |
| AI Chat | PASS WITH LIMITATION | JWT not forwarded to FastAPI; memory not persisted; `search_places` uses `destinations` |
| AI Planner | **REGRESSION FOUND** | Retired model + token limit; live call 500 |
| Trips | PASS | CRUD, 403 for other user, soft delete verified |
| Data Pipeline | PASS WITH LIMITATION | Seed duplicated; migration drift |
| Provenance | **REGRESSION FOUND** | 11 non-genuine OSM IDs counted as verified; fabricated 4.5 rating; mislabelled RAG chunks |
| RAG | PASS WITH LIMITATION | Only EVAL-01 documented; no `safety` topic chunk; no Precision@K |
| Recommendation | PASS WITH LIMITATION | Per-user (not global) temporal split; MostPop only |
| Map | PASS WITH LIMITATION | Tiles blocked on this network; shows default 4.5 rating |
| Flutter | PASS WITH LIMITATION | 60/60, analyze clean; "An toàn" placeholder; inconsistent diacritics |
| Security | PASS WITH LIMITATION | No secrets in history; hard-coded fallbacks, CORS `*`, compose password |
| VLSP / ViMACSA | BLOCKED | Human DUA/access requests not sent |

## 1. Repository
`develop` = `0997efa` = origin/develop, clean, 38 commits. Patterns (AIza, sk-, private keys, gh tokens, AKIA) → 0 hits in all history. `.env` never committed; only `.env.example`. `data/restricted/**` untracked, 0 commits touch ViHoRec. GitHub repo is private. Tracked-but-questionable: `data/raw/vietnam_travel_reviews.json` and `osm_vietnam_sample.json` (mock/hand-written, not restricted).

## 2. Test baseline (executed)
| Command | Result |
|---|---|
| `npx jest --config test/jest-e2e.json --forceExit` | 6 suites, 42/42 |
| `nest build`; `npm run lint` | exit 0; 0 errors, 36 warnings |
| `pytest tests/ -v` | 37/37 |
| `flutter analyze` | No issues found |
| `flutter test` | 60/60 |
Total 139. Historical totals (47/69/86/106/110/118/139) are cumulative at successive merges (`95353b3`, `2ac16b4`, `77089ae`, `e518b98`, `8e346e9`/`37b077e`/`c5e363a`, `bc2a487`, `b17b150`), not separate suites.

**False green:** pytest passes while the live planner fails (tests use mock/no-key fallback).

## 3–4. Backend / Flutter
Backend suite green (above). Flutter browser run (web, 127.0.0.1:5000): login/register OK, Home shows 2 destination cards (not further investigated; DB has 50), Map shows "50 địa điểm", coloured markers, preview sheet; AI Agent replied; "An toàn" placeholder; "Chuyến đi" empty state. No console errors except ~49 failed OSM tile requests.

## 5. AI chat
Path verified: Flutter → NestJS :3000 (`JwtAuthGuard`) → FastAPI :8000 `/chat` → Gemini (`gemini-3.5-flash`). 401 without token, 400 missing message. Turn 1/2 → 201; turn 3 recalls "Đà Nẵng", "3 ngày"; new session has no memory. FastAPI down → 503, no DB write. JWT is validated by NestJS and **not forwarded**; only `user_id` in body.

## 6. Auth
register 201, login 200, wrong password 401, unknown email 401 (same, no enumeration), no/garbage token 401, refresh OK, garbage refresh 401, access TTL 900 s. Duplicate email → 400. No `/auth/logout` (404, never existed).

## 7. Trips
create 201, read, update, add itinerary 201, list. User B → 403 on read/update/delete/add-itinerary/ai-plan/bulk; unauthenticated 401. Soft delete: GET → 404, row kept with `deleted_at`, hidden from list, itinerary rows retained.

## 8. Planner — REGRESSION
Causes: (1) `planner.py` `_MODEL = "gemini-2.0-flash"` retired (404); (2) `max_output_tokens=4096` exhausted by ~2,946 thinking tokens on `gemini-3.5-flash` (MAX_TOKENS, truncated JSON, 502). **Minimal fix (not applied):** `_MODEL = "gemini-3.5-flash"` and `max_output_tokens ≥ 16384` (or thinking budget); update stale mentions in `docs/ai/ai-planner.md:5` and `docs/api/ai-planner-api.md:25`; add a live smoke test.
Rest of flow verified **only with a runtime-only in-memory patch** (scratch wrapper, not in repo): preview 201 (3 days, 17 items, 1,910,000 of 6,000,000 VND), preview wrote 0 rows, bulk apply wrote 17 items and `replaceExisting` removed the manual item, invalid bulk → 400 and atomic.

## 9–10. Data and synthetic isolation
See `docs/data/current-database-state.md`. `GET /places?verifiedOnly=true` → 108, 0 synthetic, all with sources/coordinates, no duplicates; nearby with `verifiedOnly=true` over 6 cities × radii 5/25/100 (18 queries, 454 results) → 0 leaked. Without the flag the default returns 220 (112 synthetic); the Flutter map passes `true`. Independent Overpass check of 110 source IDs: 99 genuine, 11 not (R2).

## 11. RAG
628 chunks, real MiniLM-L12 embeddings 384-dim, HNSW index, 0 duplicates, complete metadata. 4 frozen queries rerun: EVAL-01 reproduces documented scores exactly; EVAL-02/03 topic hits at ranks [1,2,5] and [4]; EVAL-04 no `safety` chunk. No Precision@K computed → no quality claim. 56 chunks mislabelled OSM on synthetic places.

## 12. Recommendation
ViHoRec 17,911 interactions, 6,822 users, 560 hotels, sparsity 99.53%, cold-start users 69.5%, CC BY-NC 4.0; no review text. Split 8,645/798/798. MostPop rerun equals saved result exactly (P@5 0.01228, R@5 0.0614, NDCG@5 0.03793, P@10 0.01103, R@10 0.11028, NDCG@10 0.05366; 798 users). Split is per-user leave-last-one-out; 74 overlapping train/test pairs unreachable under `exclude_seen`; 15/278 test items unseen in train.

## 13. Map
Backend and Flutter tests green. Tiles: the user's LAN DNS resolves `*.openstreetmap.org` to 127.0.0.1; public DNS resolves but TCP resets. `overpass-api.de`, CARTO basemaps and `tiles.openfreemap.org` are reachable. **Correction:** an earlier statement that tiles would work on the user's own Chrome was wrong. Not fixed here. Preview shows an invented ⭐4.5 (R3).

## 14. Cross-service
Flutter → NestJS → FastAPI → Gemini confirmed (matches approved design).

## 15. Config/security (values not printed)
Fallbacks: `config.py` DATABASE_URL default; `auth.service.ts` JWT literals; `jwt.strategy.ts` `'super-secret'` (inconsistent with the service). Local `.env` files define distinct secrets, so fallbacks inactive locally. docker-compose has a literal Postgres password with 5432/6379 exposed. FastAPI CORS `*`, no auth. Flutter hardcodes localhost URLs.

## 16. Documentation inconsistencies
Corrected in `docs/project-status.md`: rows 14, 15, 33, 49, 51; header; "TASK 07 Review Intelligence" renamed (Task 07 = Map); added Known Regressions/Limitations. Not corrected (out of scope): `docs/ai/ai-planner.md`, `docs/api/ai-planner-api.md` stale model names; `dataset_registry.osm_places`.

## 17. Remaining blockers
VLSP 2018 DUA and ViMACSA access (human). Engineering: R1, R2, R3.

## 18. Regressions found
R1 AI Planner; R2 provenance of 11 places (and the 8 mock reviews on them); R3 fabricated 4.5 default rating.

## 19. Files changed
`docs/project-status.md` (edited); new: `docs/data/current-database-state.md`, `docs/audit/task-07.1-regression-audit.md`, `docs/daily-reports/2026-10-03.md`. No code changed.

## 20. Audit residue
The audit created 3 test users, 3 trips and 17 itinerary items; all were deleted and counts returned to baseline (users 5, trips 2, items 2, places 220, reviews 9, place_sources 110, documents 628). A throwaway DB `wanderai_fresh_audit` was dropped. Scratch scripts were moved out of the repo.

## 22. Recommended next task
**TASK 07.2 — AI Planner fix** (model + token limit + live smoke test), then provenance remediation (R2/R3).
