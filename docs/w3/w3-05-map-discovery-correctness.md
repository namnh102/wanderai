# W3-05 — Map Discovery Correctness & Mobile Stability

Status: **candidate for review** (PR vs `develop`; not merged).

## 1. Base commit
`develop` @ `af0c8b39c76b8b8042600a449a7304f0fe3d9733` (W3-04 merge). Branch `feature/w3-map-discovery-correctness`.

## 2. Root cause — PDG-009 (no destination browsing)
- `MapNotifier` only knew `loadNearby()` around a hardcoded Hà Nội default centre (`21.0285, 105.8542`); `MapScreen._initMap` always called it.
- `PlaceRepository.getPlaces` had no `destinationId`, so a destination could not be queried server-side at all.
- Retry always called `loadNearby()`, regardless of what had failed.

## 3. Root cause — PDG-010 (search does not move camera)
`searchPlaces` replaced `state.places` and set status, but nothing ever emitted a camera instruction; `FlutterMap` only read `state.center` as `initialCenter`. Search also had no stale-response protection.

## 4. Root cause — TECH-DEBT-MOB-01 (Home)
`_HomeScreenState._loadDestinations` called `setState` after `await dio.get(...)` (success, `DioException`, and generic catch) without a `mounted` check → `setState() called after dispose()` if the user left Home while `/destinations` was in flight. Fixed with `if (!mounted) return;` before the initial setState and after the await / in both catch branches. No architectural change.

## 5. Map mode contract
`MapMode { destination, search, nearby }` in `MapState` (existing fields/defaults unchanged).

| Mode | Source | Destination chip | Radius selector |
|---|---|---|---|
| destination | `GET /places?destinationId=<id>&verifiedOnly=true&limit=100&page=N` (paginated, deduped, + `category` server-side) | selected one highlighted | hidden |
| search | `GET /places?search=…&verifiedOnly=true&limit=100[&category]` — **global**, not limited by destination | none highlighted (neutral) | hidden |
| nearby | `GET /places/nearby` (after a successful "Vị trí của tôi") | none highlighted | shown |

`lastBrowseSlug` is remembered; clearing search returns to it (reload + recenter). Tapping a chip during search clears query + visible text and browses that destination.

## 6. Destination source of truth
Only the **slugs** `ha-noi`, `da-nang`, `ha-long` (and labels Hà Nội / Đà Nẵng / Hạ Long) are hardcoded in `destination_model.dart`. `id`, `name`, `latitude`, `longitude` come from `GET /destinations?limit=50`. A missing, duplicated, or invalid-coordinate supported destination raises `DestinationResolutionException` → readable Map error state (no silent fallback). Live values are listed in section 7.

## 7. Destination result counts (live API, 2026-10-12)
| Slug | id | API coords | pages | total | unique | dups | with coords |
|---|---|---|---|---|---|---|---|
| ha-noi | `071e1382-7972-4dde-af61-dac9ef2c3c69` | 21.0285, 105.8542 | 2 | 145 | 145 | 0 | 145 |
| da-nang | `2ba4b21c-454c-4077-b2b2-38b6044c656b` | 16.0544, 108.2022 | 3 | 293 | 293 | 0 | 293 |
| ha-long | `4eec2f30-b67d-4221-b754-8fcc7bb1160e` | 20.9101, 107.1839 | 2 | 188 | 188 | 0 | 188 |

Total 626 unique. Matches the expected 145 / 293 / 188 (DN 293 includes the 4 secondary Điện Bàn POIs — unchanged; REC-A 622 core not touched, no core filter in Map). Raw output: scratch `verify_out.txt` (summarised here).

Searches (verified only, limit 100): `Pizza Halong` → **1** result, `7a02c55f-5bfb-44f4-ab00-d9e93c48b85d`, name `14 Pizza Halong`, Hạ Long, 20.9540605 / 107.0236927 (still single). `Pizza` → 5 (Đà Nẵng ×2, Hạ Long ×3). `Chùa` → 32, `Cafe` → 17, `Bảo tàng` → 21. `zzqxwv123` → 0.

## 8. Search camera behaviour
Notifier emits a sequence-numbered `MapCameraRequest` in state; `MapScreen` applies it from a `ref.listen` listener (never from `build()`), cancelling any running camera animation first.
- **0 results**: status `empty`, search-specific copy (`Không có địa điểm đã xác minh khớp với "<q>"…`, no radius wording), **no camera request**, no selected place.
- **1 result**: camera → API lat/lng at zoom 16, place auto-selected (marker highlighted + `PlacePreviewSheet`).
- **2+ results**: `fitCamera(CameraFit.bounds(..., padding 56/250/56/150, maxZoom 17))` (flutter_map **7.0.2** API); nothing auto-selected. If all points are identical → `move(point, 16)` (no invalid bounds).
- With an injected `MapController` (tests) moves are direct; in the app single moves are animated (250 ms).

## 9. Stale-response strategy
`MapNotifier._seq` token: every loading operation (`selectDestination`, `searchPlaces`, `loadNearby`, category reload) takes a new token and checks `!mounted || token != _seq` after each await. Late responses neither write places/status nor emit camera requests. Covered: slow HN vs fast DN (final DN); rapid HN→DN→HL (final HL 188); "Pizza" late vs "Pizza Halong"; search in flight then Hạ Long chosen; rapid category change.

## 10. Category / location interaction
- Browse: category sent server-side with `destinationId`; search: global + category; nearby: existing client filter. Category change reloads the current mode (browse does **not** recenter) and clears the selected preview.
- "Vị trí của tôi": permission/fix flow unchanged. On success → `setUserLocation` → NEARBY (search cleared incl. visible text, chip neutral, nearby load, radius selector appears). Denied/unavailable keeps mode and camera untouched.
- Retry is context-aware (`MapNotifier.retry()`): destination → same destination; search → same query; nearby → nearby.

## 11. Automated tests
`flutter analyze`: no issues. `flutter test`: **215 passed, 1 skipped** (baseline 183 + 1 skipped; +32 new in `test/w3_05_map_discovery_test.dart`):
A parsing · B 3 slugs · C/C2 missing/duplicate/invalid · D/D2 pagination+dedup · E/F destinationId + camera at API coords · G HN/DN/HL 145/293/188 · H/H2 mode transitions · I global search · J zero results · K single result camera+select · L multi fit · M/M2/N/O stale races · P/P2 category · Q retry · R location→nearby · S1–S9 widget tests (initial camera, chip switch + text cleared, single/multi/identical/zero camera via injected `MapController`, marker preview, radius only in nearby, retry button) · T Home dispose safety.

Existing tests adapted: `design_system_and_map_stability_test.dart` test 12 now gives the fake **two** search results (a single result is auto-selected by spec); assertions unchanged. All other existing tests untouched and green. Home regression test T was not run red-before-fix.

## 12. Android manual acceptance (AVD `GoMate_W3_Test`, emulator-5554, real NestJS + PostgreSQL)
| # | Result |
|---|---|
| 01 initial map | PASS — Hà Nội chip selected, badge `145 địa điểm`, camera at HN, no crash |
| 02 DN / HL / HN | PASS — Đà Nẵng 293, Hạ Long 188, Hà Nội 145; no stale markers |
| 03 rapid HN→DN→HL | PARTIAL — adb taps ended on HL (188), but adb latency (~0.2 s/tap) is not truly "rapid"; the race is proven by deterministic tests M/M2 |
| 04 "Pizza Halong" from HN | PASS — SEARCH mode, no chip highlighted, `1 địa điểm`, camera moved to Hạ Long, marker highlighted, preview `14 Pizza Halong` |
| 05 detail from preview | PASS — same place; address `17 Lê Văn Lương` (OSM), `Chưa có đánh giá`, no fake rating; Back returns to Map with search/camera/preview intact |
| 06 multi ("Pizza", 5) | PASS after padding fix (first build clipped top marker under the chip overlay; padding raised and re-captured) — markers fit, nothing auto-selected |
| 07 empty ("zzqxwv123") | PASS — truthful search empty copy, camera stayed at Hà Nội, no preview; clearing the search returned to Hà Nội (145) — `09_…` |
| 08 category | PASS — Nhà hàng in Hà Nội → `21 địa điểm`; Tất cả → 145 |
| 09 My Location | **LIMITED** — emulator never delivered a fix (`adb emu geo fix` + location on + permission granted → app still reports `Không xác định được vị trí`). Verified: honest error, no camera/mode change. Success path covered by the mocked suite (location tests + R). |
| 10 Home lifecycle | PASS (limited) — cold start + fast tab switches; logcat has 0 `setState() called after dispose` / FlutterError. In-flight dispose proven by test T. |

Tile imagery in screenshots 01–03 was partly still loading (grey) at capture time; markers/camera are what is being evidenced.

## 13. Evidence files (real emulator screenshots, `docs/w3/evidence/w3-05/`)
`01_map_hanoi.png`, `02_map_danang.png`, `03_map_halong.png`, `04_search_single_recenter.png`, `05_search_place_detail.png`, `06_search_multiple_fit.png`, `07_search_empty.png`, `08_my_location_unavailable.png`, `09_search_cleared_back_to_hanoi.png`, `10_category_restaurant_hanoi_21.png`, `11_category_all_hanoi_145.png`.

## 14. Deferred items
Unchanged from W3-04: destination ordering by seeded rating (internal), PDG-007/008/011/012/014–017, ANDROID-RELEASE-01, CI-ANDROID-01. New notes: search is capped at one page of 100 results; real GPS success path not exercised on emulator; destination map zoom (12) is a fixed city overview, not derived from bounds.

## 15. Final candidate status
Code complete, analyze clean, 215/1 tests, live API counts verified, Android acceptance PASS except documented LIMITED/PARTIAL items (09, 03). No backend, schema, REC-A, Freeze, dataset, CI-workflow or Android-release changes.
