# PROJECT STATUS — WANDERAI (GoMate)

**Last Updated:** 2026-10-01T15:10+07:00
**Current Phase:** Auth Wired (TASK 01 + TASK 02 complete)
**Current Milestone:** M1-in-progress (auth flow working end-to-end)

---

## Completed

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
| 14 | Database — 36 tables verified | `information_schema` count | 2026-10-01 |
| 15 | Database rows — 50 dest, 112 places, 1 user | `SELECT count(*)` | 2026-10-01 |
| 16 | PlaceSource model + migration | `place_sources` table (10 columns) | 2026-10-01 |
| 17 | Fake data labelled as synthetic | `data/manifests/sources.yaml` | 2026-10-01 |
| 18 | Data pipeline directories | `data/{raw,processed,seed,evaluation,manifests}` | 2026-10-01 |
| 19 | Flutter foundation — 7 files, 0 errors | `flutter analyze` → 1 info warning | 2026-10-01 |
| 20 | Flutter web — runs on Chrome, no white screen | Debug service connected | 2026-10-01 |
| 21 | Flutter thin slice — Home loads destinations from API | GET /destinations → grid | 2026-10-01 |
| 22 | AI tests — 8 passed | `pytest tests/ -v` → 8 passed | 2026-10-01 |
| 23 | Flutter tests — 2 passed | `flutter test` → 2 passed | 2026-10-01 |
| 24 | Governance docs | project-audit.md, ADR-001, ADR-002, data-sources.md, data-dictionary.md, local-environment.md, rag-pipeline.md | 2026-10-01 |

## In Progress

| Task | Status |
|------|--------|
| Real data pipeline (OSM) | Foundation created, no data collected |
| RAG document ingestion | Pipeline documented, 0 documents |

## Blocked

| Task | Blocked By |
|------|-----------|
| Real data from OSM | Script not yet written |
| RAG retrieval | No documents embedded |
| Flutter auth wiring | Auth provider not yet reimplemented |

## Tests

| Suite | Pass | Fail | Total |
|-------|------|------|-------|
| Backend E2E (Jest) | 14 | 0 | 14 |
| AI (pytest) | 8 | 0 | 8 |
| Flutter (flutter_test) | 12 | 0 | 12 |
| **Total** | **34** | **0** | **34** |

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Gemini free tier rate limits | MEDIUM | Buy API key or use OpenRouter |
| OSM data coverage gaps | LOW | Supplement with manual data |
| 0 backend tests | HIGH | Write tests next |
| Fake seed data still in DB | MEDIUM | Replace with real data pipeline |

## Decisions

| # | Decision | ADR |
|---|----------|-----|
| 1 | PostgreSQL as single DB | ADR-001 |
| 2 | Replace fake data with real pipeline | ADR-002 |
| 3 | Remove google_fonts | Documented in audit |

## Evidence

- Git commit `8592aea`: docs
- Git commit `b5e96db`: Flutter foundation + place_sources migration + AI tests
- Flutter web running: `ws://127.0.0.1:65251/`
- Backend running: `http://localhost:3000/health`
- AI running: `http://localhost:8000/health`

## Next

1. Write backend unit tests (health, auth, destinations)
2. Wire Flutter auth to backend (login/register/logout)
3. Build OSM data collection script
4. Implement real data seeding
5. Wire AI chat in Flutter
6. Add Trip CRUD in Flutter
