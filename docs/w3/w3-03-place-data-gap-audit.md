# W3-03 — Place / Data Gap Audit

- Base: `develop` @ `5b76dd6a2c43845393c2e18603d2874d580b1159`
- Branch: `audit/w3-place-data-gap`
- Type: AUDIT ONLY. No production behaviour, Freeze artefact, REC-A math or schema was changed.
- Machine-readable summary: [`evidence/w3-03-place-data-summary.json`](evidence/w3-03-place-data-summary.json)

## 1. Executive summary

- Counts match the authoritative expectations exactly: Freeze V2 = 759 (core 622, secondary 137); DB = 882 places (759 OSM-verified = Freeze, 123 legacy unverified).
- Freeze ↔ DB is fully consistent (0 missing, 0 name/coord/category/destination mismatches, 0 duplicate IDs).
- REC-A never leaks secondary places: 364 unique recommended IDs (4 profiles × 3 destinations × topK 50) are all core; 0 fail `GET /places/:id`.
- No fake rating exists on places (0 non-null `places.rating`; app shows "Chưa có đánh giá"). **Destinations** carry synthetic seed ratings (all 50 non-zero) that Home displays.
- Main real gaps are contract bugs, not data collection:
  - Backend ignores nested `rawData.tags` → 253 available addresses (all core), 124 websites and 125 phones are never served.
  - `GET /places` pagination is unstable (ties, no tiebreaker) → duplicates and missing places across pages.
  - Legacy unverified places remain reachable and expose price ranges.
  - Input validation returns 500 for bad query values.
- Result: **0 P0, 4 P1, 7 P2, 6 P3** gaps (see section 10).

## 2. Audit scope

Path audited: authoritative datasets → seed/import → PostgreSQL/Prisma → NestJS Place APIs → Flutter models → list/cards → Place Detail.
Method: read-only SQL on local Docker Postgres, full 882-record API comparison (list + detail), pagination iteration, REC-A smoke over 4 profiles × 3 destinations, Android emulator smoke (login, recommendation → Place Detail).
Out of scope (not touched): Freeze V1/V2, POI recollection, REC-A math, TravelPreference schema, UI redesign, TECH-DEBT-MOB-01, ANDROID-RELEASE-01, CI-ANDROID-01, W4.

## 3. Authoritative counts

| Item | Count |
|---|---|
| Freeze V2 total | 759 |
| REC-A core | 622 (Hà Nội 145, Hạ Long 188, Đà Nẵng 289) |
| Secondary | 137 (hoi-an 50, hue 50, nha-trang 33, da-nang boundary 4) |
| DB places | 882 (0 soft-deleted) |
| DB OSM-verified | 759 (= Freeze) |
| DB legacy no-source | 123 |
| place_sources | 1006 (osm 759, overture 247; overture only on OSM-verified places) |
| destinations / categories | 50 / 13 |
| quarantine rows | 13 |
| reviews | 9 (all untrusted, none on verified places) |

DB verified/total per destination: da-nang 293/306, ha-long 188/194, ha-noi 145/160, hoi-an 50/59, hue 50/59, nha-trang 33/40. 33 of 50 destinations have zero places.

The 4 secondary "da-nang" POIs (outside the Da Nang bbox): `db61c6ab-1fde-51fe-ac20-0deef2fc5981`, `6489aeb0-fb3d-584d-9ca9-d6172e9cc63f`, `4c4ca7e8-2586-57cb-af5d-5e2b72c7bd4d`, `5e1ca20e-b579-59b8-b243-9f13aa43c65f`. They are `core=false` and never appear in REC-A results.

## 4. Place field mapping

| Field | Source (Freeze/OSM) | DB | API (detail) | Flutter | Class |
|---|---|---|---|---|---|
| id | place_id | places.id | id | PlaceModel.id | PRESENT |
| name | name | name | name | shown | PRESENT |
| name_en | tags.name:en | name_en | nameEn | model only | OPTIONAL |
| lat/lon | latitude/longitude | lat/lon | lat/lon | map + detail | PRESENT |
| category | category | category_id | category{name,icon,color} | shown | PRESENT |
| destination | destination(_slug) | destination_id | destination | shown | PRESENT |
| address | tags.addr:* (nested) | address column is importer-generated "<name>, <city>" | masked/flat `addr:*` only | "Chưa có thông tin địa chỉ." | DROPPED_IN_PIPELINE (253 lost) |
| opening_hours | opening_hours / tags | opening_hours (101) | column fallback + flat tag | shown or unavailable text | OPTIONAL (OK) |
| website / phone | tags.website / phone | rawData.tags | flat keys only | shown if present | DROPPED_IN_PIPELINE (124 / 125 lost) |
| description | none on verified | 112, all legacy | masked if unverified | shown if present | OPTIONAL (absent for core) |
| price_min/max | none | 62/64, all legacy | priceMin/Max leaked (64 legacy) | ignored | NOT_APPLICABLE for verified; leak for legacy |
| rating / review_count | NULL / 0 | NULL / 0 | null / 0 | "Chưa có đánh giá" | MISSING (honest) |
| cover_image / images | tags.image (≈7 core) | 0 / 0 | null / [] | ignored | MISSING (enrichment gap) |
| core flag | is_rec_a_core_v2 | not stored | not exposed | not used | MISSING in DB/API |

## 5. Completeness table (DB, 882 places)

| Field | Non-null | Notes |
|---|---|---|
| name, category, destination, lat, lon | 882 (100%) | |
| address column | 652 | importer-generated pattern, deliberately never served |
| description | 112 | all legacy; 0 verified/core |
| name_en | 301 | |
| opening_hours column | 101 | all tag-backed, all verified |
| price_min / price_max | 62 / 64 | all legacy |
| cover_image / images | 0 / 0 | |
| rating / reviews>0 | 0 / 0 | |

OSM tags available (nested), by scope:

| Scope | Places | addr | hours | website | phone | wikidata | name:en | image |
|---|---|---|---|---|---|---|---|---|
| Đà Nẵng core | 289 | 141 | 59 | 96 | 90 | 5 | 65 | 4 |
| Hạ Long core | 188 | 26 | 15 | 11 | 23 | 3 | 32 | 0 |
| Hà Nội core | 145 | 86 | 27 | 17 | 12 | 49 | 66 | 3 |
| Secondary (all) | 137 | 31 | 23 | 6 | 6 | 17 | 81 | – |

Any shape, whole DB: address 284, opening_hours 124, website 130, phone 131.

## 6. Data-quality findings

- No invalid/out-of-Vietnam coordinates, missing names, orphans, duplicate OSM source IDs; source_id formats valid; source coords == place coords; all core places inside their destination bbox and carrying an OSM source.
- OSM confidence: 746 = 1.0, 13 in 0.61–0.71.
- Duplicate POIs (name within ~30 m, same destination): 67 pairs (58 legacy-legacy, 3 verified-legacy, 6 verified-verified). Core pairs in Đà Nẵng: Chùa Linh Ứng `408aaa5a-7e34-41eb-b39f-acfa4393fc5f` / `6db09251-706a-4225-8ee5-4d22165f6b3f`; Đền Lĩnh Chúa Linh Từ `098e6a53-5ce5-4d20-b75e-4a00d00bb8cf` / `83d8e5c4-b91e-415e-9fd6-fd2a887cb4c0`. 56 exact-coordinate collisions.
- Quarantine: 13 rows (osm_id_not_found_upstream 6, osm_id_points_to_unrelated_object 5, osm_node_mismatch 2). Two quarantined Hà Nội hotels are in Freeze with valid current OSM nodes (`95e4dd6b-…`, `c693a3f8-…`); this is historical, not treated as a defect.
- 13 categories in use; `place_categories` lacks icon/color for culture, entertainment, nature.
- Destinations: all 50 have non-zero synthetic `rating` seeded from `data/seed/synthetic_destinations.json`; review_count 0.

## 7. DB → API findings

- Detail returned 200 for all 882; scalar fields match DB; reviews not exposed.
- **Nested tags ignored:** `osmAddress()/tag()` read flat `rawData['addr:*']`, `website`, `phone`, not `rawData.tags`. Address correctly served for 31 of 284 (253 lost, all core); website 124/130 lost; phone 125/131 lost. Opening hours unaffected thanks to column fallback.
- **Unstable pagination:** `GET /places` orders by `rating desc nulls last, reviewCount desc` with all keys tied. Walking all pages: verified list limit10 → 723/759 unique, limit20 → 742, limit50 → 753, limit100 → 757; all=882: limit10 → 839, limit100 → 879; each walk contains a duplicate.
- **Validation:** `page=0`, `limit=abc`, `destinationId=<slug>` / non-UUID → 500; `limit=-5` → 200; `limit=100000` → returns all 759 (no cap); `nearby?lat=abc` → 200 empty.
- List payload leaks internal fields (`placeSources`, `_count`, `deletedAt`, `categoryId`, `destinationId`, `priceMin/Max`, `images`).
- Default list (verifiedOnly=true) = 759 including 135 secondary; no core/secondary flag (da-nang API total 293 vs REC-A core 289).
- 123 legacy unverified places still return 200 on detail; 64 expose price range.
- Filters verified correct: 13 category counts match DB; destinationId filters match DB; search "Chùa" → 32; nearby OK.

## 8. API → Flutter findings

- IDs, names, coordinates preserved; null rating → "Chưa có đánh giá"; missing address/hours → honest unavailable text.
- Flutter ignores `priceMin/priceMax/images/placeSources`.
- `coverImage: json['coverImage'] ?? json['cover_image'] as String?` precedence quirk (cast applies only to second operand).
- Home renders synthetic destination ratings via `RatingView` (e.g. Hà Giang 4.8).
- Map loads ≤100 nearby / 50 listing places around the default Hà Nội centre and has no destination switcher.
- Map search for "Pizza Halong" returned badge "1 địa điểm" but the camera stayed on Hà Nội with no visible result (screenshot not committed).

## 9. Runtime findings

Android emulator (real app, dev accounts). Recommendation → Place Detail: **6/6 PASS** (2 per destination): detail opens, name equals card name, "Chưa có đánh giá", address/hours "Chưa có thông tin…", Back returns to recommendations.
REC-A API smoke: 364 unique IDs, all core, 0 wrong-destination, 0 detail failures.
Limitation: the discovery-path (Map marker → detail) was only partially exercised; markers are not exposed as accessibility nodes and the search result could not be surfaced without panning. Covered instead by API/code evidence. Loading state not observed.

## 10. Gap register

| ID | Sev | Owner | Description |
|---|---|---|---|
| PDG-001 | P1 | BACKEND | Nested `rawData.tags` ignored: 253 core addresses, 124 websites, 125 phones never served |
| PDG-002 | P1 | BACKEND | `GET /places` pagination unstable (no tiebreaker) → duplicates/missing |
| PDG-003 | P1 | DATA/PRODUCT | 50 destinations carry synthetic ratings shown on Home; 33 destinations have no places |
| PDG-004 | P1 | BACKEND/DATA | 123 legacy unverified places reachable via detail; 64 expose synthetic price ranges |
| PDG-005 | P2 | BACKEND | Query validation: `page=0`, `limit=abc`, bad `destinationId` → 500 |
| PDG-006 | P2 | BACKEND | No limit cap (`limit=100000` returns everything); negative limit accepted |
| PDG-007 | P2 | BACKEND/PRODUCT | No core/secondary flag in DB/API; default list includes 135 secondary (da-nang 293 vs core 289) |
| PDG-008 | P2 | DATA | Duplicate POIs inside REC-A core Đà Nẵng (2 pairs); 6 verified-verified pairs overall |
| PDG-009 | P2 | MOBILE/PRODUCT | Map has no destination switcher; only ≤100/50 places loaded around Hà Nội |
| PDG-010 | P2 | MOBILE | Map search result not recentred/surfaced (observed Hạ Long search) |
| PDG-011 | P2 | DATA | `places.address` column holds importer-generated "<name>, <city>" values (249+) — safe only because never served |
| PDG-012 | P3 | BACKEND | List payload leaks internal fields |
| PDG-013 | P3 | BACKEND | `nearby?lat=abc` returns 200 empty instead of 400 |
| PDG-014 | P3 | MOBILE | `coverImage` cast precedence quirk |
| PDG-015 | P3 | DATA | `place_categories` icon/color missing for 3 categories |
| PDG-016 | P3 | EXTERNAL-DATA | No images (cover_image/images 0; ~7 core have OSM `image` tag) |
| PDG-017 | P3 | RESEARCH | No trusted ratings/reviews source (data limitation; places honestly show none) |

## 11. Recommended closure order

1. PDG-001 (read nested tags) and PDG-002 (stable tiebreaker `id`) — pure backend, high user impact.
2. PDG-004 (hide/flag legacy unverified, strip priceMin/Max) and PDG-003 (stop showing synthetic destination ratings).
3. PDG-005/006/013 (DTO validation + limit cap).
4. PDG-007 (expose scope flag) with PDG-008 (dedupe core pairs via data task, without editing Freeze).
5. PDG-009/010 (map discovery UX).
6. P3 hygiene (PDG-012, 014, 015); PDG-016/017 only via approved external data work.

## 12. Deferred / non-bugs

- No trusted ratings: data limitation, correctly shown as "Chưa có đánh giá".
- No images: enrichment gap, not a defect.
- Overture is auxiliary (247 sources, none Overture-only).
- Historical quarantine rows are not defects.
- TECH-DEBT-MOB-01, ANDROID-RELEASE-01, CI-ANDROID-01 remain deferred.

## 13. Evidence / commands

- SQL via `docker exec wanderai-postgres psql -U postgres -d wanderai` (counts, completeness, duplicates, quarantine).
- Truth export of the DB vs full API comparison over 882 ids (list + detail), pagination walk (limits 10/20/50/100), REC-A smoke (4 profiles × 3 destinations, topK 50).
- Android emulator-5554 UI dumps for 6 recommendation → detail opens.
- Regression results: see PR description / final report.

## 14. Final W3-03 status

**PASS (audit complete)** — measurements reproducible, 0 P0, 4 P1, 7 P2, 6 P3; no locked artefact changed; no fabricated data; closure order defined. No fixes applied.
