# W3-01 — Runtime Contract & Preference Integration Audit

- Base: `develop` @ `69ba3524786d9c774f0061c59e6b173d67c31fb4`
- Branch: `feature/w3-runtime-contract-audit`
- Scope: AUDIT ONLY. No application code, schema, frozen data or recommender math changed.
- Audit date: 2026-10-12. Live smoke ran against local PostgreSQL/Redis, NestJS (`:3000`) and FastAPI (`:8000`). No LLM was called.

## 1. Architecture trace

```
Flutter PreferencesScreen (profile/presentation/preferences_screen.dart)
  -> ProfileNotifier (profile/providers/profile_provider.dart)       StateNotifier, non-autoDispose
  -> ProfileRepository (profile/data/profile_repository.dart:13,20)  Dio + Bearer interceptor (core/network/api_client.dart:16-19)
  -> NestJS UsersController  GET /users/me | PUT /users/me/preferences (users.controller.ts:15,21; JwtAuthGuard)
  -> UpdatePreferencesDto (class-validator, global ValidationPipe whitelist+forbidNonWhitelisted)
  -> UsersService.findById / updatePreferences (users.service.ts:10,63)
  -> Prisma TravelPreference -> PostgreSQL table travel_preferences (schema.prisma:91)

Recommendation (backend side only; NO Flutter caller):
  NestJS GET /places/recommendations?destination&topK&model (places.controller.ts:61, JwtAuthGuard)
  -> PlacesService.getRecommendations (places.service.ts:258) reads TravelPreference from PostgreSQL
  -> AiProxyService.getPlaceRecommendations (ai-proxy.service.ts:101) POST {AI_SERVICE_URL}/recommendations/places, timeout 15 s
  -> FastAPI recommendations.py:72 -> PlaceRecommender (recommendation/reca/engine.py)
  -> Freeze V2 artifact data/curated/gomate_places_freeze_v2.json, filtered to is_rec_a_core_v2 == true (622)
```

Runtime dependency on `pace` / `presence`: **none**. `git grep -w pace|presence` over `apps/backend/src`, `apps/mobile/lib`, `apps/ai-service/app` returns zero hits. The API actively rejects both (e2e Cases 12, 13; live check: `PUT {"pace":"slow"}` -> 400).

## 2. Preference contract matrix

| Field | Flutter model | Editable in UI | Request key | NestJS DTO | Prisma | Read back | After re-login | Null/default | Validation / risk |
|---|---|---|---|---|---|---|---|---|---|
| `travelStyle` | `TravelStyle` enum (`profile_models.dart:3`) | yes (`preferences_screen.dart:217`) | `travelStyle` | `@IsEnum(TravelStyle)` | enum, default `COMFORT` | yes | yes | no row -> UI default `comfort` | values match Prisma enum exactly |
| `budgetMin` | `int`, default 0 | yes (`:242`) | `budgetMin` | `@IsInt @Min(0)` | Int default 0 | yes | yes | 0 | service enforces min<=max (`users.service.ts:76-87`); client duplicates it |
| `budgetMax` | `int`, default 10,000,000 | yes (`:259`) | `budgetMax` | `@IsInt @Min(0)` | Int default 10000000 | yes | yes | 10,000,000 | same |
| `preferredGroup` | `GroupSize` enum | yes (`:280`) | `preferredGroup` | `@IsEnum(GroupSize)` | enum default `SOLO` | yes | yes | UI default `solo` | enum values match |
| `interests[]` | `List<String>` | yes (`:296`, 7 canonical chips from `kCanonicalInterests`) | `interests` | `@IsIn(CANONICAL_INTERESTS, each)` + service re-check | `String[]` | yes | yes | `[]` | canonical set identical in Flutter, DTO and `reca/contract.py`; dedup + trim in DTO and service |
| `avoidances[]` | `List<String>` | yes (chips + free text `:316-339`) | `avoidances` | `@IsString each` only | `String[]` | yes | yes | `[]` | **free-form, Vietnamese display strings stored as values** (e.g. `Đông đúc`), while API docs/seed use `crowds`. Not consumed by REC-A V1 |
| `dietaryNeeds[]` | `List<String>` | yes (`:364-387`) | `dietaryNeeds` | `@IsString each` only | `String[]` | yes | yes | `[]` | same free-form risk. Not consumed by REC-A V1 |

Other facts:
- Canonical interests are exactly the 7 required keys in all three layers (Flutter `profile_models.dart:60-96`, DTO `update-preferences.dto.ts:14-22`, REC-A `contract.py:13-21`).
- `PUT /users/me/preferences` is partial-update on the server (`users.service.ts:129-137`); the mobile client always sends the full object (`profile_models.dart:160-168`).
- Mobile re-fetch: `ProfileNotifier` constructor calls `loadProfile()` (`profile_provider.dart:65`), which uses `GET /users/me`. The refresh button (`preferences_screen.dart:74`) re-fetches.
- There is **no** `GET /users/me/preferences`; `GET /users/me` (embedding `preferences`, `null` when no row) is the only read path.
- Token persists in `SharedPreferences` (`auth_repository.dart:15,62`), so a restart keeps the session and the screen re-fetches from PostgreSQL.

Preference API classification: **A — mobile already uses the real endpoint correctly** (read + write, exact keys). No local-only or mock state.

## 3. Authenticated preference API (as implemented)

| Item | Value |
|---|---|
| Write | `PUT /users/me/preferences`, JWT Bearer required (401 without; e2e Case 9) |
| Read | `GET /users/me` -> `data.preferences` (object or `null`) |
| Request | `{travelStyle?, budgetMin?, budgetMax?, preferredGroup?, interests?, avoidances?, dietaryNeeds?}` all optional |
| Response | envelope `{success, data:{id,userId,travelStyle,budgetMin,budgetMax,preferredGroup,interests,avoidances,dietaryNeeds,createdAt,updatedAt}, timestamp}` |
| Whitelist | `forbidNonWhitelisted` -> unknown keys (`pace`, `presence`, `userId`) return 400 |
| Errors | 400 negative budget, min>max, non-canonical interest (live: `beach` -> 400 with accepted list); 401 unauth; 404 unknown user |
| Empty `interests: []` | accepted (200); user then gets cold-start recommendations |

## 4. REC-A runtime contract

| Item | Actual behaviour |
|---|---|
| NestJS route | `GET /places/recommendations` (declared before `:id`, so no route shadowing) |
| Auth | `JwtAuthGuard`; live 401 without token |
| Query params | `destination?` (string), `topK?` (default 10), `model?` (default `rec-a1`) |
| Preference source | server side from PostgreSQL `travel_preferences` (not from the client). Missing row -> `{interests: []}` |
| FastAPI | `POST /recommendations/places` body `{preferences, destination, top_k (1..50), model}` |
| Response | `{recommendations:[{place_id,name,destination,destination_slug,category,score,rank,matched_interests,explanation:{reason_code,matched_interests,matched_taxonomy,text},strategy}], metadata:{algorithm,model,destination_filter,total_candidates,returned_count,cold_start}, unsupported_user_features:[...]}`; NestJS wraps it in `{success,data,timestamp}` |
| Score / reason | cosine score (0.707107 for 1-of-2 match); `explanation.text` generated from canonical interest labels + taxonomy (no LLM) |
| Provenance in response | **none**: no lat/lng, address, rating, sources. Only `place_id` |
| Candidate universe | `is_rec_a_core_v2 == true`; live counts 622 = HN 145 + HL 188 + DN 289; 137 secondary excluded |
| topK | FastAPI enforces 1..50 -> 422 outside range; NestJS does not pre-validate |
| Empty prefs | cold-start diverse baseline, `metadata.cold_start=true` |
| Unsupported features | `travelStyle, budget*, preferredGroup, avoidances, dietaryNeeds` returned explicitly in `unsupported_user_features` |
| Errors | FastAPI errors forwarded with their status; unreachable -> 503; timeout 15 s |
| Flutter | **no caller** |

## 5. Architecture invariants

| # | Invariant | Result | Evidence |
|---|---|---|---|
| 1 | Flutter does not compute recommendations | PASS | no recommendation code in `apps/mobile/lib` (only doc comments in `trip_models.dart`) |
| 2 | NestJS is the auth/app boundary | PASS | `JwtAuthGuard` on `/places/recommendations` and `/users/*` |
| 3 | FastAPI performs recommendation logic | PASS | `recommendation/reca/engine.py` |
| 4 | PostgreSQL is source of truth for prefs | PASS | read from `travel_preferences` in `places.service.ts:264` |
| 5 | LLM not involved in REC-A ranking | PASS | engine/contract are pure Python, no LLM client; smoke ran with no LLM key use |
| 6 | No fake ratings/reviews | PASS | all 10 live results resolve to detail with `rating=null, reviewCount=0` |
| 7 | Mobile does not access PostgreSQL | PASS | only Dio -> NestJS |
| 8 | Mobile does not bypass backend | PASS | single `apiBaseUrl` (`app_constants.dart:2`) |

No BLOCKING invariant violation.

## 6. Mobile readiness matrix

| Capability | State | Evidence | Gap | Blocking? |
|---|---|---|---|---|
| authenticated session | READY | `auth_repository.dart`, `api_client.dart:16-19` | token in plaintext SharedPreferences (documented limitation) | no |
| fetch current preferences | READY | `profile_repository.dart:13`, `profile_provider.dart:68` | uses `GET /users/me` | no |
| edit preferences | READY | `preferences_screen.dart` (7 canonical interests, style, budget, group, avoidances, dietary) | free-form avoid/dietary values | no |
| save preferences | READY | `profile_provider.dart:160`, `profile_repository.dart:19` | legacy non-canonical interests in a stored row would make every save 400 (see G-04) | no |
| restore preferences | PARTIAL | `profile_provider.dart:65`; `profileProvider` is not autoDispose and not invalidated on logout (`grep invalidate` finds none for it) | stale previous-user state possible after logout/login without refresh (G-01); by code inspection, not UI-executed | yes for multi-user device (HIGH) |
| choose destination | MISSING | no destination selector bound to a recommendation request | needs selector limited to `da-nang`/`ha-noi`/`ha-long` | yes (W3-02) |
| request recommendations | MISSING | no repository/provider calls `/places/recommendations` | G-02 | yes |
| render recommendation list | MISSING | no screen | G-03 | yes |
| render recommendation reason | MISSING | API provides `explanation.text` and `matched_interests` | G-03 | yes |
| open Place Detail | READY | route `/places/:id` (`app_router.dart:115`), `place_detail_screen.dart`; all 10 live `place_id`s return 200 from `GET /places/:id` | needs navigation from list only | no |
| recover from API error | PARTIAL | preferences have `_mapError` (`profile_provider.dart:219`) | backend forwards FastAPI 422 with `message` as an object, not a string (live), so `data['message'].toString()` would show raw map text (G-07) | no |
| loading state | PARTIAL | preferences yes; recommendations n/a | needed with the new screen | no |
| empty state | PARTIAL | preferences n/a; recommendations n/a | needed (cold-start / zero interests / no result) | no |

## 7. Live runtime smoke evidence (2026-10-12, no LLM)

Fresh dev user `w301audit_*@wanderai.test`. Destination `da-nang`, interests `culture_history, food_cuisine`.

| Check | Result |
|---|---|
| A. preference write | `PUT /users/me/preferences` -> 200, all 7 fields echoed |
| B. read-back | `GET /users/me` -> identical preferences; before write `preferences: null` |
| C. persistence across session | fresh `POST /auth/login` then `GET /users/me` -> interests retained |
| D. rec via NestJS | `GET /places/recommendations?destination=da-nang&topK=10` -> 200 |
| E. NestJS -> FastAPI | request reached FastAPI (`metadata` from engine); direct `POST :8000/recommendations/places` also 200 |
| F. actual REC-A | `algorithm="Cosine Content-Based Baseline"`, `model=rec-a1`, `total_candidates=289`, `returned_count=10`, `cold_start=false` |
| G. destination / core | 10/10 `destination_slug=da-nang`, 10/10 in Freeze V2 core; **0** of the 4 secondary Da Nang-labelled POIs (2x Hà My memorial, Mini-Golf Hoi An, TASY STUDIO) |
| H. no fabricated rating | all 10 `GET /places/{id}` -> 200 with `rating=null`, `reviewCount=0` |
| unauth | 401 |
| no preferences row | 200, `cold_start=true`, `COLD_START_DIVERSE_CATALOG_BASELINE` |
| `interests: []` | 200 on save; recs cold-start |
| non-canonical interest | 400 |
| `pace` | 400 |
| `topK=0/100/abc` | 422 forwarded from FastAPI (abc becomes `null`, so message is misleading) |
| `model=zzz` | 200, silently treated as `rec-a1` |
| `destination=Đà Nẵng` | 200, resolves to `da-nang` |
| `destination=Paris` | **200, `destination_filter=null`, 622 candidates (all destinations)** |
| no `destination` | 200, 622 candidates |

## 8. W3-02 gap list

| ID | Layer | Current | Expected | Evidence | Sev | Files | Fix | Test |
|---|---|---|---|---|---|---|---|---|
| G-01 | mobile state | `profileProvider` survives logout; no invalidate | profile/preferences state cleared when auth user changes or logs out | `profile_provider.dart:235`; no `invalidate(profileProvider)` anywhere | HIGH | `profile_provider.dart`, `auth_provider.dart` | make provider depend on auth user (autoDispose or `ref.invalidate` on logout/login) | widget/provider test: user A prefs never visible to user B |
| G-02 | mobile data | no recommendation repository/provider | `RecommendationRepository.fetch(destination, topK)` -> `GET /places/recommendations`, typed models for response | no caller in `apps/mobile/lib` | BLOCKER | new `features/recommendations/data/*`, `providers/*` | add models + repo + `FutureProvider.autoDispose.family` | repo unit test with fixture of live response |
| G-03 | mobile UI | no list/reason UI | screen: destination selector (Hà Nội, Đà Nẵng, Hạ Long), list <=10, reason text, matched-interest chips, loading/empty/error, tap -> `/places/:id` | no screen/route | BLOCKER | new `features/recommendations/presentation/*`, `app_router.dart`, entry from Home | build screen using existing design system | widget tests: list, reason, empty, error, navigation |
| G-04 | mobile/API | stored legacy non-canonical interests are preserved by `fromJson` and re-sent on save, so save 400s and the UI cannot show/remove them | client drops non-canonical interests before save (or shows them as removable) | `profile_models.dart:145-148,165`; `users.service.ts:105-111`; e2e Case 11 proves such rows can exist. Live DB has 0 today | MEDIUM | `profile_models.dart` / `profile_provider.dart` | filter to `kCanonicalInterests` on load/save | unit test with legacy row |
| G-05 | FastAPI/NestJS | unrecognised destination silently returns all 622 core POIs | unknown destination -> explicit 400/422 (or empty with flag), never fall through to all | live `destination=Paris` -> 622 candidates; `engine.py:120-124` | HIGH | `engine.py` / `recommendations.py`, `places.controller.ts` | validate destination against the 3 supported slugs at NestJS; reject others | API test: `Paris` -> 400; `da-nang`/`Đà Nẵng` -> 200 |
| G-06 | NestJS | `topK`/`model` not validated at the boundary | DTO with `@IsInt @Min(1) @Max(50)`, `@IsIn(['rec-a0','rec-a1'])` | live `topK=abc` -> 422 with `input:null`; `model=zzz` -> silently rec-a1 | MEDIUM | `places.controller.ts` (+ new query DTO) | query DTO | e2e for 400s |
| G-07 | NestJS/mobile | forwarded FastAPI 422 has object `message` | stable string error contract | live `topK=0` body | MEDIUM | `ai-proxy.service.ts:120-125`, mobile `_mapError` | map FastAPI validation detail to a string | e2e + mobile error test |
| G-08 | API contract | recommendation items have only `place_id`/name/category | list needs address/coords/rating-null badge without N+1 detail calls | `recommendations.py:38-48` | MEDIUM | NestJS `places.service.ts` (join DB rows by `place_id`), not the recommender math | enrich in NestJS from PostgreSQL (`isVerified`, address, rating=null) | e2e: every item has verified place row; no rating invented |
| G-09 | test | no backend e2e for `/places/recommendations` | e2e covering auth, DN core-only, secondary exclusion, <=10, cold start | `grep recommend apps/backend/test` -> none | HIGH | `apps/backend/test/recommendations.e2e-spec.ts` | add e2e (needs FastAPI in CI or mocked proxy) | the test itself |
| G-10 | docs/API | `avoidances`/`dietaryNeeds` stored as free-form Vietnamese display strings; docs say `crowds` | decide canonical key sets before any future use | `profile_models.dart:98-112` vs DTO example | LOW | later task | defer; not used by REC-A V1 | n/a |
| G-11 | mobile config | `apiBaseUrl = http://localhost:3000` hard-coded | per-platform/env base URL | `app_constants.dart:2` | LOW | `app_constants.dart` | `--dart-define` | n/a |

## 9. TC-W3-01 feasibility

| # | Expected | Class | Reason |
|---|---|---|---|
| 1 | preferences persist | PASSABLE_NOW | proved live (A, B) and covered by backend e2e |
| 2 | re-fetch/restart retains preferences | PASSABLE_NOW | live re-login read-back; token persisted in SharedPreferences; G-01 only matters for user switching |
| 3 | recommendation returns <= 10 POIs | NEEDS_W3_02 | backend returns 10 now, but no Flutter path (G-02, G-03) |
| 4 | Da Nang REC-A core only | PASSABLE_NOW (API) / NEEDS_W3_02 (UI) | 10/10 core, `da-nang`; destination validation G-05 needed so wrong input cannot widen scope |
| 5 | none of 4 Điện Bàn/Quảng Nam POIs | PASSABLE_NOW (API) | 0 leaks live; engine only indexes `is_rec_a_core_v2==true`; needs e2e lock (G-09) |
| 6 | reason from real taxonomy/features | PASSABLE_NOW (API) / NEEDS_W3_02 (render) | `explanation.text` + `matched_interests` + `matched_taxonomy` from canonical features |
| 7 | no fabricated rating | PASSABLE_NOW | `rating=null` for all 10 |
| 8 | selecting a result opens Place Detail | NEEDS_W3_02 | `/places/:id` works for all returned ids; no list to tap from |

No item is BLOCKED.

## 10. Tests run (existing tests only, none modified)

| Suite | Result |
|---|---|
| Backend e2e `preferences.e2e-spec.ts` + `places.e2e-spec.ts` | 2 suites, 23 tests pass |
| ai-service `test_place_recommendation_api.py` + `test_recommendation.py` | 7 pass |
| Root `tests/test_reca_baseline.py` (REC-A) | 19 pass |
| Flutter `test/preferences_test.dart` | 8 pass |
| `flutter analyze` | No issues found |
| Flutter recommendation tests | none exist |
| Backend recommendation API tests | none exist (G-09) |

## 11. Recommended W3-02 scope

1. G-02 + G-03: Flutter recommendation data layer and screen (destination selector, list <= 10, reason, states, tap to Place Detail).
2. G-05 + G-06 + G-07: harden the NestJS recommendation boundary (supported-destination validation, query DTO, string errors).
3. G-08: enrich items from PostgreSQL in NestJS (address/coords/verified; rating stays null).
4. G-01 + G-04: fix mobile profile state lifecycle and legacy-interest handling.
5. G-09: add the backend recommendation e2e (TC-W3-01 steps 3-7) and a Flutter test for steps 3, 6, 8.

Out of scope: REC-B, recommender math, schema, new POIs, using `travelStyle`/budget/avoidances in ranking.
