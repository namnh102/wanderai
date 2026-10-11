# TASK 07.4 — Real OSM Data Enrichment & Verified Place Serving

Branch `feat/osm-enrichment-verified-serving` (from `develop` @ `df904b7`, which contains TASK 07.3 and was pushed).

## What changed

| Area | Change |
|---|---|
| Data | `data/pipelines/osm/enrich_osm.py` queries Overpass for named tourism/historic/natural/worship/park objects in the 5 pilot regions, snapshots the raw response (`data/raw/osm_enrichment.json`, with exact query, endpoint, `osm_base_timestamp`) and builds `data/curated/places_osm_enrichment.json`. No OSM id is typed or generated: each source id is the `type/id` of an element Overpass returned. Place ids are `uuid5(namespace, osm id)` (idempotent). Ratings stay NULL. |
| Import | `apps/backend/prisma/import-osm-enrichment.ts` (idempotent upsert of places + `place_sources`; denylist honoured). |
| API | `GET /places` and `GET /places/nearby`: `verifiedOnly` now **defaults to true**. `verifiedOnly=false` returns unsourced dev/test records. `GET /places/:id` is unchanged (itineraries reference places). |
| Registry | `data/manifests/update_dataset_registry.sql` sets `dataset_registry.osm_places.record_count` and `wikivoyage_vn.record_count` from real counts. |
| Audit tool | `provenance_audit.py` now checks only `overpass-api.de` (see finding below). |

## Finding: stale Overpass mirror

The first collection let `enrich_osm.py` fall back to `overpass.kumi.systems`; it served **Đà Nẵng** (data base 2026-07-15) and **Nha Trang** (2026-06-01) from stale snapshots. The independent audit against the authoritative host then flagged 6 Đà Nẵng sources as "does not exist upstream" (`way/302618031`, `way/1520886786`, `node/4245947689`, `node/13505819201`, `node/12566759201`, `node/12566755701`). Fix: both regions were re-collected with `--primary-only` (base timestamps 2026-10-03T18:55Z), the 8 superseded places (6 failing + 2 Nha Trang) were deleted (they were enrichment rows created minutes earlier, no references) and 5 new ones added; the audit then passed. The audit tool was pinned to the primary host so a stale mirror cannot produce a false PASS or FAIL.

## Counts (Before → After)

| | Before (07.3) | After |
|---|---|---|
| places total | 220 | 480 |
| verified places (`place_sources` ≥ 1) | 97 | **357** |
| unsourced (dev/test only, hidden by default) | 123 | 123 |
| `place_sources` | 97 | 357 |
| `GET /places` default total | 220 | 357 |
| `GET /places?verifiedOnly=false` total | 220 | 480 |
| `dataset_registry.osm_places.record_count` | 10 | 357 |
| `dataset_registry.wikivoyage_vn.record_count` | 0 | 464 |

Verified by category: culture 111, attraction 111, cafe 55, hotel 25, nature 21, restaurant 15, beach 14, entertainment 5 (was: cafe 55, hotel 25, restaurant 15, culture 2, no attraction/beach).
Verified by destination: Đà Nẵng 114, Hà Nội 110, Hội An 50, Huế 50, Nha Trang 33.

## Provenance verification

`python data/pipelines/provenance_audit.py --out docs/audit/evidence/provenance-07.4.json` (live API + Overpass primary host): **357 verified places, 357 OSM sources checked, 0 violations, 0 name differences — PASS.**

## Browser test (Flutter web, fresh build, Map tab)

Chips: Tất cả, Tham quan, Nhà hàng, Khách sạn, Văn hóa, Biển, Thiên nhiên, Giải trí, Cà phê. Badge counts near the default map centre (limit 100): Tất cả 100, Tham quan 24, Nhà hàng 13, Khách sạn 25, Văn hóa 24, Biển 1, Thiên nhiên 8, Cà phê 5, **Giải trí 0** ("Không tìm thấy địa điểm" — only 5 entertainment places exist, none near the default centre). Search "Chùa" → 9 results (e.g. Chùa Trấn Quốc). Preview sheet shows `Đã xác minh` and `Chưa có đánh giá`.

Defects found by the browser test and fixed in this task: (1) map chips used keys with no data (`temple`, `museum`, `park`, `market`) → replaced by the real taxonomy (`culture`, `nature`, `entertainment`); (2) preview sheet showed raw `culture`/`nature` → Vietnamese labels (+ Flutter test). Not fixed (pre-existing / out of scope): preview sheet stays open when switching chips; Flutter `Multiple widgets used the same GlobalKey` console error (2 occurrences, pre-dates 07.4); map tiles from tile.openstreetmap.org fail on this network.

## Limitations

- Categories are capped per region (attraction/culture 25, nature 15, beach/entertainment 10) and ranked by documentation (wikidata, wikipedia, name:en, website...). It is a curated sample, not full OSM coverage.
- Some OSM names are generic ("Museum", "View point"); they are genuine objects but low quality for end users.
- The 123 unsourced/synthetic places stay in the DB (use `verifiedOnly=false`); `GET /places/:id` still returns them by id.
- RAG/Wikivoyage documents were **not** re-ingested for the 260 new places (no RAG change in this task); `documents` stays 561.
- `ODbL` attribution is shown only in docs/registry; no in-app attribution beyond the map tile credit.
- Enriched places have no rating/reviews (NULL, shown as "Chưa có đánh giá").