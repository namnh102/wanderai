# Developer Runbook (W3)

## Prerequisites
Node 22 + pnpm 10, Python 3.11, Flutter (stable), Git. Optional for DB-backed tests: PostgreSQL with PostGIS and Redis (e.g. Docker).

## Git / line endings
`.gitattributes` forces LF; you do not need to change `core.autocrlf`. Do not run mass `git add --renormalize`.
Freeze V1/V2 artifacts are immutable - never edit them. Verify with `python -m scripts.freeze_checksum`.

## Environment variables
Copy `.env.example` → `.env` (backend: `apps/backend/.env`) and `apps/ai-service/.env`. Real keys stay out of Git.

| Variable | Read by | Required |
|---|---|---|
| `DATABASE_URL` | backend (Prisma), ai-service | yes (runtime/e2e) |
| `JWT_SECRET`, `JWT_REFRESH_SECRET` (+ `*_EXPIRES_IN`) | backend | yes - change placeholders |
| `AI_SERVICE_URL` | backend | yes (default `http://localhost:8000`) |
| `GEMINI_API_KEY` / `LLM_PROVIDER` / `OPENAI_API_KEY` | ai-service | for live chat/planner; **dummy value is enough to import the service, run tests and export OpenAPI** |
| `REDIS_HOST`, `REDIS_PORT` | backend, ai-service | where Redis is used |
| `PLANNER_MODEL`, `PLANNER_MAX_OUTPUT_TOKENS`, `PLANNER_TIMEOUT_MS` | ai-service | optional |
| `PORT`, `AI_PORT`, `NODE_ENV`, `WEATHER_API_URL` | backend / ai-service | optional |
| `SUPABASE_*`, `CLOUDINARY_*`, `GOOGLE_MAPS_API_KEY` | not read by current code paths | no |

## Commands
Backend (`apps/backend`):
```
pnpm install --frozen-lockfile
pnpm exec prisma generate
pnpm run typecheck
pnpm run lint:check        # non-mutating (pnpm run lint auto-fixes!)
pnpm run build
pnpm run test:e2e          # needs PostgreSQL
```
AI service / data (repo root):
```
pip install -r apps/ai-service/requirements-dev.txt
ruff check .
python scripts/export_openapi_ai.py --check
python -m pytest tests -q                          # root data/REC-A tests
cd apps/ai-service && python -m pytest tests -q    # AI tests
```
Mobile (`apps/mobile`): `flutter pub get && flutter analyze && flutter test`.

## Known environment-dependent tests (BLOCKED_BY_ENVIRONMENT without PostgreSQL)
`tests/test_data03_danang_freeze_v2.py::test_live_database_invariants`,
`apps/ai-service/tests/test_rag.py::test_rag_retrieval_da_nang_culinary`,
`apps/ai-service/tests/test_grounding_contract.py::test_synthetic_documents_never_reach_the_provider`, backend e2e specs.
Licensed ViHoRec CSVs (`data/restricted/vihorec/`) are git-ignored; without them seven root integrity tests fail with "file missing". CI covers all tracked artifacts via
`python -m scripts.freeze_checksum --skip-missing-prefix=data/restricted/`.

## CI
`.github/workflows/ci.yml`: jobs `backend`, `ai-service`, `mobile`, `data-contract`. No LLM calls, no database. Not yet run on GitHub.
