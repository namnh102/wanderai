# PROJECT AUDIT — WANDERAI (GoMate)

**Date:** 2026-10-01
**Auditor:** AI Technical Lead
**Branch:** `develop` (8 commits)

---

## 1. Repository State

- **Branch:** `develop` (current), `main` (protected)
- **Status:** 33 deleted files in working tree (Flutter lib/ was intentionally cleared)
- **Commits:** 8 total on develop
- **Remote:** `origin/main` only — develop not pushed yet

## 2. Existing Technologies

| Layer | Technology | Version | Status |
|-------|-----------|---------|--------|
| Mobile | Flutter + Dart | SDK ^3.1.0 | ❌ lib/ deleted — needs rebuild |
| Backend | NestJS + TypeScript | @nestjs/common ^10.0.0 | ⚠️ Code exists, needs verification |
| Database | PostgreSQL + Prisma | prisma ^5.22.0 | ✅ Schema defined |
| AI | FastAPI + Python | fastapi (latest) | ⚠️ Code exists, needs verification |
| Cache | Redis | via Docker | ❌ Docker not running |
| Infra | Docker Compose | v3.8 | ❌ Docker Desktop not running |

## 3. Existing Files/Modules

### Backend (34 files in `apps/backend/src/`)
```
app.module.ts, main.ts
common/decorators/current-user.decorator.ts
common/filters/http-exception.filter.ts
common/guards/jwt-auth.guard.ts
common/interceptors/transform.interceptor.ts
modules/auth/ (controller, service, module, dto/login, dto/register, strategies/jwt)
modules/destinations/ (controller, service, module)
modules/health/ (controller, module)
modules/reviews/ (controller, service, module)
modules/trips/ (controller, service, module)
modules/users/ (controller, service, module)
modules/videos/ (controller, service, module)
modules/ai-proxy/ (controller, service, module)
prisma/ (service, module)
```

### AI Service (15 source files in `apps/ai-service/app/`)
```
main.py, config.py
llm/ (base.py, gemini.py, openai_provider.py)
routers/ (chat.py, health.py, planner.py)
schemas/ (chat.py, planner.py)
services/ (agent.py, cache.py, rag.py)
tools/ (base.py, search_places.py, get_weather.py, calculate_budget.py,
        calculate_route.py, search_hotels.py, search_reviews.py)
prompts/ (system_prompt.py)
```

### Mobile (0 files — lib/ deleted)
```
pubspec.yaml exists with dependencies:
  flutter_riverpod, go_router, dio, shared_preferences,
  google_fonts, cached_network_image, flutter_map, latlong2,
  shimmer, fl_chart
```

### Database
```
database/prisma/schema.prisma — 30 models
database/seed/destinations.json — 50 records (AI-GENERATED, NOT REAL)
database/seed/places.json — 56 records (AI-GENERATED, NOT REAL)
database/seed/categories.json — 10 records
database/init.sql — PostGIS + pgvector extensions
```

## 4. Existing Functionality

| Feature | Backend | AI | Mobile | Test |
|---------|---------|-----|--------|------|
| Health check | ✅ GET /health | ✅ GET /health | ❌ | ❌ |
| Auth (register/login) | ✅ JWT | N/A | ❌ | ❌ |
| Destinations CRUD | ✅ GET /destinations | N/A | ❌ | ❌ |
| Trips CRUD | ⚠️ Partial | N/A | ❌ | ❌ |
| Reviews CRUD | ⚠️ Partial | N/A | ❌ | ❌ |
| Videos CRUD | ⚠️ Partial | N/A | ❌ | ❌ |
| AI Chat | ✅ Proxy | ✅ gemini-3.5-flash | ❌ | ❌ |
| AI Planner | ✅ Proxy | ⚠️ Endpoint exists | ❌ | ❌ |
| AI Tools | N/A | ⚠️ 6 tools defined, untested | ❌ | ❌ |
| RAG | N/A | ⚠️ Skeleton only | ❌ | ❌ |
| Matching | ❌ | ❌ | ❌ | ❌ |
| Booking | ❌ | ❌ | ❌ | ❌ |
| Safety | ❌ | ❌ | ❌ | ❌ |
| Map | N/A | N/A | ❌ | ❌ |
| Video Feed | ⚠️ Partial | ❌ | ❌ | ❌ |

## 5. Missing Functionality

- Matching module (backend + AI)
- Booking module (backend + mock provider)
- Safety module (backend)
- Group/Chat module (backend + WebSocket)
- Notification module (backend)
- Social features (follow, like, save, comment)
- Recommendation engine (AI)
- Review AI (sentiment + aspect extraction)
- Video AI (metadata extraction)
- RAG pipeline (documents, embedding, retrieval)
- Map integration (Flutter)
- Budget tracker
- Complete mobile app

## 6. Architecture Problems

1. **Seed data is AI-generated fake data** — destinations.json and places.json contain fabricated records, not from any real data source. No provenance metadata.
2. **No data source registry** — No `place_sources` table, no `data_sources` documentation.
3. **Flutter code was completely broken** — google_fonts dependency causing white screens, subagent conflicts, code deleted.
4. **No tests exist** — 0 backend tests, 0 AI tests, 0 mobile tests (only `test_health.py` template).
5. **AI tools are untested** — 6 tools defined but function calling never verified end-to-end.
6. **RAG has no documents** — RAG service skeleton exists but zero knowledge base documents.
7. **No data pipeline** — No ETL scripts, no data cleaning, no entity resolution.
8. **Reviews data missing** — 0 reviews in seed data, Review AI has nothing to analyze.

## 7. Dependency Problems

- `google_fonts: ^6.1.0` in pubspec.yaml — causes web rendering issues, should remove
- Prisma client generated but may be stale after schema changes
- Python packages not pinned to versions in requirements.txt
- No lock file for Python dependencies

## 8. Testing Status

- **Backend:** 0 tests (Jest configured but no test files)
- **AI:** 1 template file `tests/test_health.py` (likely skeleton)
- **Mobile:** 0 tests (default Flutter test deleted with lib/)
- **E2E:** None
- **AI Evaluation:** None — no datasets, no metrics, no benchmarks

## 9. Data Status

| Data Type | Count | Source | Quality |
|-----------|-------|--------|---------|
| Destinations | 50 | AI-generated | ❌ FAKE — coordinates approximate, ratings fabricated |
| Places | 56 | AI-generated | ❌ FAKE — prices approximate |
| Categories | 10 | Manual | ✅ OK |
| Users | 1 | Test seed | ✅ OK for testing |
| Reviews | 0 | None | ❌ MISSING |
| Videos | 0 | None | ❌ MISSING |
| Hotels | 0 | None | ❌ MISSING |
| Tours | 0 | None | ❌ MISSING |
| RAG docs | 0 | None | ❌ MISSING |
| Weather | API | Open-Meteo | ✅ Runtime |

## 10. AI Status

- **LLM:** gemini-3.5-flash confirmed working (free tier, rate limited)
- **Agent:** TravelAgent class exists with tool orchestration loop
- **Tools:** 6 tools defined (search_places, get_weather, calculate_budget, search_hotels, calculate_route, search_reviews)
- **RAG:** Skeleton only — no documents, no embeddings
- **Review AI:** Not implemented
- **Recommendation:** Not implemented
- **Matching:** Not implemented
- **Video AI:** Not implemented
- **Evaluation:** Not implemented

## 11. Documentation Status

| Document | Status |
|----------|--------|
| AGENTS.md | ✅ Created |
| CONTRIBUTING.md | ✅ Created |
| docs/AI_ARCHITECTURE.md | ✅ Created |
| README.md | ⚠️ Basic |
| .env.example | ✅ Complete |
| Swagger/OpenAPI | ⚠️ Auto-generated, not verified |
| Data dictionary | ❌ Missing |
| Data sources registry | ❌ Missing |
| ADR directory | ❌ Missing |
| Project status | ❌ Missing |
| Test plan | ❌ Missing |

## 12. Security Risks

- `.env` files exist with real credentials (Supabase URL, Gemini API key) — should be in `.gitignore`
- JWT secret is placeholder in .env.example — OK
- No rate limiting on API endpoints
- No prompt injection guards implemented
- CORS configured for localhost only — OK for dev

## 13. Immediate Blockers

1. **Docker Desktop not running** — PostgreSQL and Redis unavailable
2. **Seed data is fake** — Cannot build meaningful features on fabricated data
3. **Flutter lib/ is empty** — No mobile app to run
4. **No tests** — Cannot verify any existing functionality

## 14. Recommended Next Actions (Priority Order)

1. Start Docker Desktop → PostgreSQL + Redis
2. Verify backend compiles and APIs respond
3. Verify AI service starts and responds
4. Create real data pipeline (OSM destinations + Mendeley reviews)
5. Replace fake seed data with real data
6. Rebuild Flutter mobile app incrementally
7. Write tests for every feature as implemented
8. Create missing documentation (data sources, ADRs, project status)
