# W3-04 — Place Contract & Data Trust Hardening

## 1. Base commit
`develop` @ `9572c11de0852542996137cbfa0d67b552a612e0` · branch `feature/w3-place-contract-hardening`.

## 2. Gaps targeted
PDG-001, PDG-002, PDG-003, PDG-004 (P1); PDG-005, PDG-006 (P2); PDG-013 (P3).
Not touched: PDG-007…012, 014…017, TECH-DEBT-MOB-01, ANDROID-RELEASE-01, CI-ANDROID-01.

## 3. Root causes
| Gap | Root cause |
|---|---|
| PDG-001 | `PlaceSource.rawData` is stored in two shapes: canonical nested `rawData.tags.*` (621 OSM rows) and historical flat `rawData.*` (~34 rows). The service, and the SQL in `findNearby`, read only the flat shape. |
| PDG-002 | `ORDER BY rating DESC NULLS LAST, review_count DESC` ties for every verified POI (rating NULL, 0 reviews); with no unique last key, OFFSET paging is non-deterministic. |
| PDG-003 | `destinations.rating` is seeded from `synthetic_destinations.json` (non-zero, `review_count = 0`) and returned verbatim by every destination endpoint (and embedded in place detail). |
| PDG-004 | `GET /places/:id` served any non-deleted place, including 123 legacy seed places with no provenance; list/detail spread the whole Prisma row, leaking seed `priceMin/priceMax`. |
| PDG-005/006/013 | Controllers did `Number(query)`; `NaN` reached Prisma/PostGIS (500 or empty 200); `limit` had no range. |

## 4. Files changed
- New [`osm-tags.ts`](../../apps/backend/src/modules/places/osm-tags.ts) — one TS extractor + SQL mirror (`osmTagSql`, `osmAddressSql`).
- New [`dto/place-query.dto.ts`](../../apps/backend/src/modules/places/dto/place-query.dto.ts) — `PlaceListQueryDto`, `NearbyQueryDto`.
- [`places.controller.ts`](../../apps/backend/src/modules/places/places.controller.ts), [`places.service.ts`](../../apps/backend/src/modules/places/places.service.ts).
- New [`destination-trust.ts`](../../apps/backend/src/modules/destinations/destination-trust.ts); [`destinations.service.ts`](../../apps/backend/src/modules/destinations/destinations.service.ts) (R1: nested place addresses).
- Tests: new `test/place-contract.e2e-spec.ts`; updated `place-detail`, `places`, `provenance` e2e specs (contract changes below).
- No Prisma schema change, no mobile change, no Freeze/REC-A change.

## 5. Contract before / after
| Surface | Before | After |
|---|---|---|
| address / website / phone | flat keys only | nested `tags` first, flat fallback; `places.address` never used |
| `findNearby` SQL address | flat keys | nested-first, flat fallback (generated from the same key lists as TS) |
| `GET /places` order | rating, reviewCount | rating, reviewCount, **`id ASC`** |
| `GET /places/nearby` order | distance | distance, **`p.id ASC`** |
| `GET /places` limit | any (100000 allowed) | integer 1..100 |
| `GET /places/:id` unverified | 200 | **404** |
| `priceMin/priceMax` | exposed (list, detail, destination detail) | removed |
| destination `rating` | seed value | `null` unless `reviewCount > 0` (none today) |
| `GET /destinations/:id` places | all non-deleted, stored `address` served | only provenance-backed places; `address = osmAddress(OSM rawData)` (R1); no price, `rawData` or `placeSources` |

## 6. OSM metadata recovery (live DB, all 759 verified places, via `GET /places/:id`)
Expected value computed independently in Python from the raw `place_sources.raw_data`.

| Field | Available | Served | Lost |
|---|---|---|---|
| address | 284 | 284 | **0** |
| website | 130 | 130 | **0** |
| phone | 131 | 131 | **0** |
| opening hours (tag or column) | 124 | 124 | **0** |

W3-03 baseline was address 31 / website 6 / phone 6 served. List address mismatches: 0 of 759. Nearby SQL vs TS: 300 results checked in 3 areas, 0 mismatches. Detail never exposes `priceMin/priceMax` (759/759).

Factual-address handling now covers `GET /places`, `GET /places/:id`, `GET /places/nearby` and `GET /destinations/:id` -> `places[]` (all via `osm-tags.ts`; stored `places.address` is never served).

## 7. Pagination proof (live)
| verifiedOnly | limit | total | unique | duplicates | missing |
|---|---|---|---|---|---|
| true | 10 / 20 / 50 / 100 | 759 | 759 | 0 | 0 |
| false | 10 / 20 / 50 / 100 | 882 | 882 | 0 | 0 |

W3-03 baseline: up to 43 missing + 1 duplicate. Regression tests walk verified at 10/50/100, all at 20, and assert disjoint/identical pages.

## 8. Validation matrix (live, HTTP status)
| Request | Result |
|---|---|
| `page=0`, `page=abc` | 400 |
| `limit=0`, `-5`, `101`, `abc` | 400 |
| `destinationId=ha-noi` / `not-a-uuid` | 400 |
| `verifiedOnly=maybe` | 400 |
| `nearby?lat=abc`, `lat=91`, `lat=-91` | 400 |
| `nearby?lng=181`, `lng=-181` | 400 |
| `nearby` without lat/lng, missing lat or lng | 400 |
| `nearby radius=0`, `radius=abc`, `limit=0`, `limit=101` | 400 |
| defaults, `limit=1`, `limit=100`, UUID destination, `verifiedOnly=false`, nearby valid | 200 |

Errors use the existing `HttpExceptionFilter` shape with one readable Vietnamese message, e.g. `limit phải là số nguyên từ 1 đến 100`; no stack or validation object. `RecommendationQueryDto` is unchanged.

## 9. Destination rating trust behaviour
Live: `/destinations?limit=50` → 50 items, 0 non-null ratings; `/destinations/popular` → 14, 0; `/destinations/nearby` → 20, 0; destination detail → `rating = null`; place detail's embedded `destination.rating = null`. Seed data is not rewritten; no replacement rating exists. Mobile needed no change: `home_screen.dart` passes the null to `RatingView`, which renders "Chưa có đánh giá".

## 10. Legacy dependency audit
| Reference | Count | Verdict |
|---|---|---|
| `itinerary_items` → unverified place | 0 of 2 items | none |
| `reviews` → unverified place | 9 (all `trusted = false` seed, never exposed) | data only; `/reviews` does its own place lookup, unaffected |
| `place_sources` | n/a (unverified = no sources) | – |
| Mobile | always requests `verifiedOnly=true`; no hard-coded place IDs | none |
| Backend tests | 3 specs asserted `200` for unverified detail | test-only; updated |

## 11. Legacy reachability decision
**CASE A** — no real runtime/product dependency. Public `GET /places/:id` for a place with no provenance now returns 404 (123/123 legacy IDs verified live). The 123 records are not deleted or migrated; `?verifiedOnly=false` list is retained (price stripped). Price leak: 0 (list for 123 legacy places and all detail responses).

## 12. Regression results
| Gate | Result |
|---|---|
| Backend `tsc --noEmit` | pass |
| Backend lint | 0 errors, 83 warnings (69 before; new `any` in e2e tests) |
| Backend unit tests | none exist (`jest` finds 0 files — unchanged) |
| Backend e2e (full) | all suites pass after updating the 3 specs; new spec `place-contract` passes |
| ai-service offline | 115 passed, 2 skipped; 1 deselected = known pre-existing `test_grounding_opening_hours_only_states_source_metadata` (fails identically: `Bào Tàng Alexandre Yersin not retrieved`; ai-service untouched) |
| Flutter | `flutter analyze` no issues; `flutter test` 183 passed, 1 skipped |
| Freeze checksum | exit 0 (V1/V2 unchanged) |
| data-contract `pytest tests` | 65 passed |
| REC-A | no engine/data change; ai-service REC-A suite (core 622 = HN 145 / HL 188 / DN 289, no secondary leakage) passes |
| Mobile smoke (Android emulator-5554) | Home loads; all destination cards show "Chưa có đánh giá" (no synthetic star/number); Recommendation → Place Detail works; detail with recovered OSM data renders: BaBaBa Japanese Restaurant — address "333 Đường Hồ Nghinh", hours, website, phone; no crash |

## 13. Deferred gaps
PDG-007, 008, 009, 010, 011, 012 (except price), 014, 015, 016, 017; TECH-DEBT-MOB-01, ANDROID-RELEASE-01, CI-ANDROID-01.
Note: destination ordering still uses the seeded `rating` as a sort key (value not exposed); revisit with PDG-017.

## 14. R1 - destination detail address leak (follow-up)
**Root cause:** `GET /destinations/:id` returned full Prisma place rows; W3-04 stripped only `priceMin/priceMax`, so the importer-generated `places.address` (e.g. `Bảo tàng Chiến thắng B52, hanoi`) was still public.

**Fix:** `destinations.service.ts` selects the OSM `PlaceSource.rawData` only as internal input, sets `address = osmAddress(rawData)` (existing helper, no new implementation) and strips `placeSources`/`rawData`/prices before returning. No schema or data change.

**New e2e test** (`place-contract.e2e-spec.ts`): for ha-noi, da-nang, ha-long every nested place has no `priceMin/priceMax/rawData/placeSources`, an OSM source exists, `address == osmAddress(rawData)`, and where the stored column differs from the factual result the API never serves the stored value (the test asserts such places exist).

**Live (626 nested places = 145 + 293 + 188):** API-vs-OSM mismatches 0; unsafe stored-address leaks 0; price/rawData/placeSources leaks 0. Samples:
- Hà Nội *Bảo tàng Chiến thắng B52*: stored `..., hanoi` -> API `null`.
- Hà Nội *Thai Village*: stored `3B Phố Lê Thái Tổ, Hàng Trống, Hoàn Kiếm, Hà Nội` -> API `3B Phố Lê Thái Tổ, Hoàn Kiếm, Hà Nội`.
- Đà Nẵng *CaPhe Konia*: stored `..., da_nang` -> API `null`.
- Hạ Long *Nhà Hàng Phương Nam 2*: stored `Sun Premier Village, Hạ long, Quảng Ninh` -> API `LV2, 03, Sun Premier Village, Hạ long, Quảng Ninh`.

**Re-run:** `tsc` pass; lint 0 errors (84 warnings); full e2e 13 suites / 153 tests pass.

## 15. Final status
**W3-04 candidate PASS (after R1)** — all target gaps closed, none blocked; no schema, Freeze or REC-A change.
