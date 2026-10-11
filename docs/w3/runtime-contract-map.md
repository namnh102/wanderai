# W3 Runtime Contract Map

Derived from route inventory and source (`apps/backend/src/**/*.controller.ts`, `apps/backend/src/modules/ai-proxy/ai-proxy.service.ts`, FastAPI OpenAPI snapshot). Request/response schemas for the backend are **not** snapshotted yet (see Deferred in `current-state-audit.md`).

```
Flutter app ──HTTP──▶ NestJS backend (:3000) ──HTTP (AI_SERVICE_URL)──▶ FastAPI ai-service (:8000)
                         │                                              │
                         └── Prisma ─▶ PostgreSQL/PostGIS ◀── asyncpg ───┘ (RAG, places)
                                         Redis (REDIS_HOST/PORT)
```

## Mobile → Backend
Base URL `http://localhost:3000` (hardcoded in `app_constants.dart`).

## Backend routes (inventory)
| Controller | Routes |
|---|---|
| auth | `POST /auth/register`, `/auth/login`, `/auth/refresh` |
| users | `GET /users/me`, `PUT /users/me`, `PUT /users/me/preferences` |
| destinations | `GET /destinations`, `/popular`, `/nearby`, `/:id` |
| places | `GET /places`, `/places/nearby`, `/places/recommendations`, `/places/:id` |
| reviews | `GET /reviews`, `/reviews/my`, `/reviews/:id`; `POST /reviews`; `DELETE /reviews/:id` |
| trips | `POST/GET /trips`, `GET/PUT/DELETE /trips/:id`, `POST /trips/:id/itinerary`, `DELETE /trips/:id/itinerary/:itemId`, `POST /trips/:id/members`, `POST /trips/:id/ai-plan`, `POST /trips/:id/itinerary/bulk` |
| ai-proxy | `POST /ai/chat`, `POST /ai/plan` |
| videos | `GET /videos/feed`, `/videos/:id`; `POST /videos` |
| health | `GET /health` |
Swagger UI is served by the backend at `/api` (`main.ts`).

## Backend → AI service (`ai-proxy.service.ts`)
| Backend call | AI endpoint |
|---|---|
| `/ai/chat` | `POST /chat` |
| `/ai/plan`, `/trips/:id/ai-plan` | `POST /planner` |
| `/places/recommendations` | `POST /recommendations/places` |

## AI service OpenAPI (`docs/contracts/ai-service.openapi.json`)
`GET /health`, `POST /chat`, `GET /chat/{session_id}`, `POST /planner`, `POST /recommendations/places`.
Refresh: `python scripts/export_openapi_ai.py`; CI guards drift with `--check`.

## Invariants carried by the contracts
- Preferences: authenticated, validated writes only (`PUT /users/me/preferences`); no presence/online fields.
- Recommendations: REC-A content baseline over canonical interests; ratings never fabricated.
- AI proposes, user decides: plans are applied only through explicit user actions.
