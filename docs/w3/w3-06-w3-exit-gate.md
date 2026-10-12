# W3-06 — W3 Exit Gate / Regression Freeze

## 1. Executive result

**W3 EXIT = PASS** (audit/regression only; no production source, schema, data, CI, or Android config changed).

- Open P0 = 0, open P1 (W3 scope) = 0.
- Every required gate passed (sections 4–10), with the labelled limitations in section 12.
- One pre-existing, environment-dependent ai-service test failure is reported honestly (section 6); it is not a W3 regression.

## 2. Base / environment

| Item | Value |
|---|---|
| Base | `develop` @ `92b982e79b7fb5ccbb243ab73b8ac0247beebd80` |
| Branch | `audit/w3-exit-gate` |
| `main` | `5f6ae8ca6ede40d40114be5617f53a4a0c0b9fce` (unchanged) |
| OS / shell | Windows / PowerShell |
| Flutter | 3.47.5 (stable, rev `6a19cca564`) |
| Emulator | AVD `GoMate_W3_Test` (`emulator-5554`), `adb reverse tcp:3000 tcp:3000` |
| Services | real PostgreSQL + Redis (Docker), NestJS `:3000`, FastAPI `:8000` |
| Date | 2026-10-12 |

## 3. W3 merged-task history

| Task | PR | Merge commit |
|---|---|---|
| W3-00 | #6 | `69ba352` |
| W3-01 | #7 | `63d6e8e` |
| W3-02 | #8 | `5b76dd6a2c43845393c2e18603d2874d580b1159` |
| W3-03 | #9 | `9572c11de0852542996137cbfa0d67b552a612e0` |
| W3-04 | #10 | `af0c8b39c76b8b8042600a449a7304f0fe3d9733` |
| W3-05 | #11 | `92b982e79b7fb5ccbb243ab73b8ac0247beebd80` |

## 4. Freeze / data integrity

- `python -m scripts.freeze_checksum` (V1 and V2, restricted files present locally): all `PASS` / `LEGACY_EOL_COMPAT_PASS`, no FAIL.
- Root `tests/` (data + REC-A contract + live DB invariants, no deselects): **65 passed, 0 failed**.
- Live DB (psql): total places **882**, verified (has ≥1 `place_sources`) **759**, legacy unverified 123.
- Map / general verified discovery per destination (DB and UI): Hà Nội **145**, Đà Nẵng **293**, Hạ Long **188**.
- REC-A core 622 = HN 145 + DN 289 + HL 188; secondary 137. Secondary leakage into REC-A = **0** (REC-A contract tests).
- DN 293 (map) vs 289 (REC-A) is intentional: 4 Điện Bàn POIs are secondary for REC-A but available in general discovery. Data and counts untouched.

## 5. Backend regression (`apps/backend`)

| Check | Result |
|---|---|
| `pnpm run typecheck` | PASS |
| `pnpm run lint:check` | PASS (used instead of `lint` so no autofix touches source) |
| `pnpm run build` | PASS |
| `pnpm run test:e2e` (full, real PostgreSQL/Redis) | **13 suites / 153 tests, 153 passed, 0 failed, 0 skipped** |

Live W3-04 trust assertions (script against running NestJS):
- Verified place detail → 200; `priceMin`/`priceMax` null; no price leak in `/places` list (0 of 100) or `/destinations/:id` (0 of 293).
- Unverified legacy place detail → 404.
- Invalid place query values (`limit=0|101|abc`, `page=0|-1`, `minRating=zzz`) → 400.
- Invalid nearby coordinates (non-numeric, out of range, missing lng, negative radius) → 400; valid nearby → 200.
- Deterministic pagination over all verified places: 759 rows, 759 unique, 0 duplicates.
- Destination ratings: 0 destinations expose a non-null rating (synthetic ratings not shown as factual).
- Importer-generated `places.address` no longer exposed through destination detail (covered by W3-04 e2e, in the 153 passing tests).

## 6. AI / REC-A regression (`apps/ai-service`)

| Check | Result |
|---|---|
| `ruff check .` | PASS |
| `python scripts/export_openapi_ai.py --check` (repo root) | PASS (snapshot up to date) |
| Full pytest (`tests`, no deselects) | **115 passed, 2 skipped, 1 failed** |

The single failure is `tests/test_rag_osm_ingestion.py::test_grounding_opening_hours_only_states_source_metadata` (RAG retrieval: "Bào Tàng Alexandre Yersin not retrieved"). It depends on the local live DB / retrieval index state, is unrelated to W3 changes (no RAG code touched in W3), was already failing before W3-06, and was not patched. Classified **known pre-existing, non-W3, environment-dependent** (not P0/P1 for W3 exit). It is carried into deferred items.

REC-A baseline (REC-A0 / REC-A1) tests are in the 65-test root suite and unchanged.

Live behaviour:
- `POST /recommendations/places` for `ha-noi`, `da-nang`, `ha-long`, alias `hanoi` → 200, 50 results each.
- Unknown destination (`paris`) → 422, **not widened** to all candidates.
- Invalid model (`bogus`) → 422, no silent fallback.
- NestJS proxy `GET /places/recommendations`: `da-nang`, `Hà Nội`, `hl` aliases → 200 with 5 results; no rating field; unsupported destination / `topK=0` / `topK=abc` / bad model → 400.
- N300 remains labelled **SANITY / ENGINEERING DATA ONLY**.

## 7. Preference regression

Live (fresh disposable account): `GET /users/me` 200; `PUT /users/me/preferences` 200; reload returns exactly `travelStyle, budgetMin, budgetMax, preferredGroup, interests[], avoidances[], dietaryNeeds[]` (no extra keys, no pace/presence); round-trip equal. Non-canonical interest (`legacy_beach`) → 400 (strict canonical 7: `food_cuisine, culture_history, nature_outdoor, coffee_culture, beach_island, shopping_local, nightlife_entertainment`); a following valid save still works. Persistence chain Flutter → NestJS → PostgreSQL confirmed by E2E-02 (values written, app shows them after fresh login).

## 8. Mobile regression (`apps/mobile`)

- `flutter analyze`: **No issues found**.
- `flutter test`: **215 passed, 1 skipped, 0 failed** (areas: auth, session isolation, preferences, recommendations, Place Detail, Map, location/navigation, trips baseline, W3-05). No test weakened.

## 9. Android build

`flutter build apk --debug` → success, `build/app/outputs/flutter-apk/app-debug.apk` (Flutter 3.47.5, NDK 28.2.13676358, no Gradle/AGP/Kotlin change). Release signing/package config untouched.

## 10. Real E2E smoke (AVD `GoMate_W3_Test`, real backends)

| ID | Scenario | Result |
|---|---|---|
| E2E-01 | Logout, login as account A → Home | PASS |
| E2E-02 | Preferences (Tiết kiệm, Cặp đôi, Ẩm thực + Văn hóa, avoid "crowds") shown after fresh login | PASS |
| E2E-03 | Gợi ý cho bạn: HN / ĐN / HL chips; Đà Nẵng loads, no fake rating, explanation + matched-interest chips | PASS |
| E2E-04 | Opened 2 rec cards → correct Place Detail ("Art in Paradise Da Nang 3D Museum", Đã xác minh, "Chưa có đánh giá"); Back works | PASS |
| E2E-05 | Map HN 145 / DN 293 / HL 188 with camera + markers switching | PASS |
| E2E-06 | "Pizza Halong" → 1 result, camera moved, preview, detail opens; "Pizza" → 5 results, camera fits; "zzqxwv123" → "Không tìm thấy địa điểm" | PASS |
| E2E-07 | Logout A, login B: default prefs, no A preference leak, cold-start recs notice (no stale state) | PASS |
| E2E-08 | FastAPI stopped → readable error "AI Recommendation Service không phản hồi" + Thử lại; restart → retry recovers without app restart | PASS |

`REAL_GPS_EMULATOR = NOT_VERIFIED`: the emulator never delivers a fix (limitation, not a failure). Mocked-success tests are green and the unavailable path is truthful ("Khoảng cách chưa xác định").

## 11. W3-03 gap closure matrix

| ID | Sev | Title | Status |
|---|---|---|---|
| PDG-001 | P1 | Nested OSM tags ignored | CLOSED_W3 |
| PDG-002 | P1 | Pagination unstable | CLOSED_W3 |
| PDG-003 | P1 | Synthetic destination ratings | CLOSED_W3 |
| PDG-004 | P1 | Legacy unverified / synthetic price | CLOSED_W3 |
| PDG-005 | P2 | Bad params → 500 | CLOSED_W3 |
| PDG-006 | P2 | No limit cap | CLOSED_W3 |
| PDG-007 | P2 | No core/secondary flag | DEFERRED |
| PDG-008 | P2 | Duplicate POIs in DN core | DEFERRED |
| PDG-009 | P2 | Map destination switcher | CLOSED_W3 |
| PDG-010 | P2 | Map search camera | CLOSED_W3 |
| PDG-011 | P2 | Importer-generated `places.address` | DEFERRED (column internal only; verified not leaked) |
| PDG-012 | P3 | List/detail payload exposes internal fields (`deletedAt`, `placeSources`, …) | DEFERRED |
| PDG-013 | P3 | Nearby invalid lat → 200 | CLOSED_W3 |
| PDG-014 | P3 | coverImage cast precedence | DEFERRED |
| PDG-015 | P3 | Category icon/color for 3 categories | DEFERRED |
| PDG-016 | P3 | No place images | EXTERNAL_DATA_LIMITATION |
| PDG-017 | P3 | No trusted rating/review source | EXTERNAL_DATA_LIMITATION |
| TECH-DEBT-MOB-01 | — | HomeScreen setState after dispose | CLOSED_W3 |

Required closed set (PDG-001, 002, 003, 004, 005, 006, 009, 010, 013, TECH-DEBT-MOB-01) confirmed closed.

## 12. Deferred technical debt (recorded, not fixed, not fake-closed)

- PDG-007, PDG-008, PDG-011, PDG-012, PDG-014, PDG-015, PDG-016, PDG-017.
- Destination ordering uses the historical seeded rating as an internal sort key only.
- ANDROID-RELEASE-01; CI-ANDROID-01 (no Android APK build in CI).
- W3-05 limits: global map search is capped at one 100-result page; destination overview zoom fixed at 12.
- `REAL_GPS_EMULATOR = NOT_VERIFIED`.
- Backend e2e is not run in CI (BLOCKED_BY_ENVIRONMENT there); it was run locally here.
- Pre-existing, environment-dependent ai-service RAG test `test_grounding_opening_hours_only_states_source_metadata`.

## 13. W3 exit decision

All required gates are met: open P0 = 0; open P1 = 0; Freeze integrity; REC-A contract; preference persistence; place data trust; map destination discovery; map search camera; session isolation; backend full e2e; AI offline regression (with the one labelled pre-existing failure); mobile analyze + tests; Android debug build; real E2E smoke; tree clean except W3-06 docs.

**Decision: W3 EXIT = PASS. Ready for W4 (not started).**

## 14. Commands / evidence

- `python -m scripts.freeze_checksum`
- `python -m pytest tests -q -p no:cacheprovider` (repo root)
- `docker exec wanderai-postgres psql ...` (total / verified / per-destination counts)
- `pnpm run typecheck`, `pnpm run lint:check`, `pnpm run build`, `pnpm run test:e2e` (`apps/backend`)
- `ruff check .`, `python -m pytest tests -q -p no:cacheprovider` (`apps/ai-service`), `python scripts/export_openapi_ai.py --check` (repo root)
- `flutter analyze`, `flutter test`, `flutter build apk --debug` (`apps/mobile`)
- Live API script (register/login/prefs/recommendations/places/destinations) and emulator E2E via adb.
- Machine-readable summary: [`evidence/w3-06-exit-gate.json`](evidence/w3-06-exit-gate.json). No secrets or tokens recorded. No new anomaly screenshots were needed.

## 15. Final status

**W3-06: W3 EXIT GATE PASS.** No product code changed. PR not merged; awaiting review.
