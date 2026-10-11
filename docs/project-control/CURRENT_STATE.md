# CURRENT STATE (after W3-00 integration)

_Last updated: 2026-10-12, branch `chore/w3-engineering-baseline` (from local `develop` `ab55856`). Not pushed._

## Repository
- `develop` (local) = PR #2 → #3 → #4 → #5 merged with merge commits, plus three verification-only fixes (FIX1–FIX3).
  `origin/develop` is still `1befc68`; nothing has been pushed. PR #1 (visual mockups) and `main` untouched.
- Integration phase: **PASS** (deterministic tests green; DB-dependent tests `BLOCKED_BY_ENVIRONMENT`).

## Implemented (evidence in EVIDENCE.md)
| Area | State |
|---|---|
| Backend (NestJS) | auth (register/login/refresh), users (`GET /users/me`, `PUT /users/me`, `PUT /users/me/preferences` validated), destinations, places (list/nearby/detail/`recommendations`), reviews, trips (+itinerary, AI plan), ai-proxy, videos, health. Typecheck + build pass. |
| AI service (FastAPI) | `/health`, `/chat`, `/planner`, `/recommendations/places` (REC-A content baseline). OpenAPI snapshot in `docs/contracts/`. |
| Mobile (Flutter) | auth, home, map, place detail, Wandy chat, trips, travel-preferences screen. `flutter analyze` clean; 160 tests pass. |
| Data | Freeze V1 (23 artifacts) and Freeze V2 (Hà Nội 145 / Hạ Long 188 / Đà Nẵng 289; REC-A-CORE-V2 622, secondary 137, total verified 759) with lineage; cross-platform checksum verifier. |
| Research | REC-A content-based baseline + synthetic benchmark outputs (n=300, seed 42). |

## Incomplete / not started
- No Buddy Matching, Group, Shared Itinerary, Shared Expense, RAG-eval, REC-B, REC-EVAL implementation.
- NestJS OpenAPI snapshot not exported (app boot needs PostgreSQL via Prisma) - deferred.
- Backend: 57 ESLint warnings (0 errors); Prettier not conformant in 44 files (not gated; no mass reformat).
- Backend has no unit tests; only e2e specs (need PostgreSQL).
- CI workflow written and its commands validated locally, but **not yet executed on GitHub**.

## Blocked (BLOCKED_BY_ENVIRONMENT)
- PostgreSQL/Redis not available (Docker engine not running): `tests/test_data03_danang_freeze_v2.py::test_live_database_invariants`,
  `apps/ai-service/tests/test_rag.py::test_rag_retrieval_da_nang_culinary`,
  `apps/ai-service/tests/test_grounding_contract.py::test_synthetic_documents_never_reach_the_provider`,
  backend `preferences.e2e-spec` and other e2e specs.
- Licensed ViHoRec files are git-ignored: absent in clean clones, so 7 root freeze/integrity tests cannot run in CI (verified locally; CI uses `scripts.freeze_checksum --skip-missing-prefix=data/restricted/`).
