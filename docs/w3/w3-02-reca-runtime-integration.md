# W3-02 — REC-A Runtime Integration & Contract Hardening

- Base: `develop` @ `63d6e8e6e205f507ded5ebdcfb81be2c6edaf352`
- Branch: `feature/w3-reca-runtime-integration`
- Closes W3-01 gaps: G-01, G-02, G-03, G-04, G-05, G-06, G-07, G-09. Deferred: G-08, G-10, G-11.
- Not changed: REC-A scoring/tie-breaking, Dataset Freeze V1/V2, lineage, REC-A benchmark artifacts, Prisma schema, POI set.

## 1. Final runtime architecture

```
Flutter RecommendationScreen
  -> recommendationProvider (StateNotifier: initial/loading/success/empty/error)
  -> RecommendationRepository (Dio + Bearer)  GET /places/recommendations?destination&topK=10&model=rec-a1
  -> NestJS PlacesController (JwtAuthGuard) + RecommendationQueryDto   <- public contract, validated here
  -> PlacesService reads TravelPreference from PostgreSQL (source of truth)
  -> AiProxyService POST FastAPI /recommendations/places (15 s timeout)
  -> FastAPI request validators (defensive) -> PlaceRecommender (REC-A, unchanged)
  -> Freeze V2 core candidate set (622 = HN 145 + HL 188 + DN 289)
```

Flutter never calls FastAPI, never ranks, never reads PostgreSQL. No LLM is involved.

## 2. Public NestJS contract — `GET /places/recommendations`

Auth: JWT Bearer (401 without). DTO: [recommendation-query.dto.ts](../../apps/backend/src/modules/places/dto/recommendation-query.dto.ts).

| Param | Rule | Violation |
|---|---|---|
| `destination` | optional; accepts `ha-noi`/`da-nang`/`ha-long` and the existing aliases (`hanoi`, `hn`, `Hà Nội`, `danang`, `Đà Nẵng`, `halong`, `Hạ Long`, ...). Canonicalised to the slug before forwarding. Empty value = not provided | unknown (e.g. `Paris`) -> **400** `Điểm đến không được hỗ trợ...` |
| `topK` | optional, default 10, integer 1..50 | `0`, `51`, `-3`, `2.5`, `abc` -> **400** `topK phải là số nguyên từ 1 đến 50` (no `NaN`) |
| `model` | optional, default `rec-a1`; `rec-a0` or `rec-a1` (case-insensitive) | other -> **400** `model không hợp lệ...` |

Omitting `destination` is an explicit "all REC-A core" request (622 candidates), not a silent fallback for bad input.

Response envelope (unchanged): `{success, data:{recommendations[], metadata, unsupported_user_features[]}, timestamp}`.

## 3. FastAPI defensive validation

[recommendations.py](../../apps/ai-service/app/routers/recommendations.py) adds Pydantic validators (HTTP 422):
- unsupported `destination` is rejected (previously `Paris` -> all 622 candidates); supported aliases normalise via the existing `normalize_destination`;
- unsupported `model` is rejected (previously `zzz` -> `rec-a1`);
- `top_k` 1..50 unchanged. Engine, scoring and ordering untouched.

## 4. Error contract

`formatUpstreamDetail` (ai-proxy.service.ts) flattens FastAPI/Pydantic `detail` lists into a readable string, so NestJS always returns `message` as a string. Mobile `RecommendationRepository.mapRecommendationError` and the profile `_mapError` show only string messages; map/object payloads fall back to a generic Vietnamese message. No stack traces reach the client.

## 5. Mobile path

| Layer | File |
|---|---|
| Models (typed, snake_case envelope) | `features/recommendations/data/recommendation_models.dart` |
| Repository + `RecommendationException` | `.../data/recommendation_repository.dart` |
| State (stale-response guard via request sequence; destination change clears result) | `.../providers/recommendation_provider.dart` |
| UI | `.../presentation/recommendation_screen.dart` |
| Session isolation | `core/session/session_reset.dart`, wired in `RouterNotifier` |

UI: destination chips limited to Hà Nội / Đà Nẵng / Hạ Long (no free text); each item shows name, category, `explanation.text`, matched-interest chips; no rating is shown (none in the response); tap -> `/places/:id` (existing Place Detail); loading, empty, error+retry; cold start is success with an informational notice.

Entry point: root route `/recommendations`, reached from the new "Gợi ý cho bạn" card on Khám phá (Home). No sixth tab; bottom nav unchanged.

### G-01 profile isolation
`RouterNotifier` already listens to `authProvider`. On every auth-status change it now calls `resetSessionScopedState`, which invalidates `profileProvider` and `recommendationProvider`. Providers re-fetch from the backend with the new session; no second store. Async completions are guarded with `mounted`.

### G-04 legacy interests
`filterCanonicalInterests` (order-preserving, de-duplicated) is applied in `TravelPreferences.fromJson` and `toJson`. The canonical set remains exactly the 7 keys.

## 6. Test evidence

| Suite | Result |
|---|---|
| Backend e2e, full (`--runInBand`) | 12 suites, 110 tests pass (new `recommendations.e2e-spec.ts`: 19) |
| Backend `tsc`, `lint:check` | 0 errors |
| FastAPI new + existing recommendation tests | pass (`test_place_recommendation_api.py`, `test_recommendation.py`) |
| REC-A baseline `tests/test_reca_baseline.py` | 19 pass |
| Flutter `flutter test` | 183 pass, 1 skipped (opt-in live test) |
| `flutter analyze` | No issues found |
| Freeze V1/V2 checksum verification | all PASS |

Pre-existing, unrelated failure: `apps/ai-service/tests/test_rag_osm_ingestion.py::test_grounding_opening_hours_only_states_source_metadata` fails identically on `develop` (verified by stashing this branch). It is a RAG retrieval check, not part of this change.

The backend e2e needs PostgreSQL and the FastAPI service on `AI_SERVICE_URL`; CI does not run it (same as the existing e2e suites).

## 7. TC-W3-01 live result

Run with PostgreSQL + Redis + NestJS + FastAPI via `LIVE_W3=1 flutter test test/live_tc_w3_01_test.dart`, which drives the real mobile `ProfileRepository` and `RecommendationRepository` over HTTP (no LLM).

| # | Check | Result |
|---|---|---|
| 1 | preferences persist (`culture_history`, `food_cuisine`) | PASS |
| 2 | re-login and re-fetch retains them | PASS |
| 3 | Da Nang returns <= 10 | PASS (10) |
| 4 | all Da Nang REC-A core (`total_candidates` 289) | PASS |
| 5 | 0 of the 4 Điện Bàn / Quảng Nam secondary POIs | PASS |
| 6 | reason from REC-A taxonomy (`PREFERENCE_TAXONOMY_MATCH`, non-empty `matched_taxonomy`) | PASS |
| 7 | no fabricated rating (`rating=null`, `reviewCount=0` for every result) | PASS |
| 8 | result opens existing Place Detail | PASS at API level (every `place_id` resolves via `GET /places/:id`) and PASS in widget test (tap -> `/places/:id`); not exercised in a live browser/emulator |

Smoke: Hà Nội (145 candidates) and Hạ Long (188) return 10 items each, all in-destination and in core. `destination=Paris` surfaces a readable error through the repository.

## 8. Known deferred gaps

- G-08: recommendation items still carry only `place_id`/name/category (no address/coords); the list navigates by `place_id`.
- G-10: `avoidances`/`dietaryNeeds` remain free-form Vietnamese strings (not used by REC-A V1).
- G-11: `apiBaseUrl` is still `http://localhost:3000`.
- The live Place Detail tap was not executed on a real device/browser in this task.
- Space-separated `Da Nang` is not an existing alias and is rejected (alias contract preserved).
