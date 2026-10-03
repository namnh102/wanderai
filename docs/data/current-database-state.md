# Current Database State (snapshot 2026-10-04, after TASK 07.5)

Source: live queries on DB `wanderai` (PostgreSQL via Docker `wanderai-postgres`) after applying migration `20261004010000_provenance_remediation`. Before/after counts and method: `docs/audit/task-07.3-provenance-remediation.md`; raw output: `docs/audit/evidence/db-counts-*.txt`. Baseline users 5, trips 2 (1 live), itinerary_items 2, itineraries 2.

## Totals

| Table | Rows | Notes |
|---|---|---|
| destinations | 50 | 14 popular |
| places | 480 | 357 verified (with an `osm` place_source) + 123 unsourced dev/synthetic (hidden by default); 0 soft-deleted; `rating` is NULL for all |
| place_sources | 357 | all `osm`, all verified upstream |
| place_source_quarantine | 13 | removed non-genuine OSM sources (11 invalid ids + 2 nodes mismatching their place; audit trail) |
| reviews | 9 | all `source='synthetic'`, `trusted=false`; 16 `review_aspects` |
| documents (RAG) | 821 | 464 wikivoyage + 357 osm (one document per verified place; TASK 07.5) |
| document_quarantine | 164 | 67 chunks on unsourced places (TASK 07.3) + 97 superseded old-format OSM documents (TASK 07.5) |
| users / trips | 5 / 2 | |
| Prisma migrations | 4 | adds `provenance_remediation` |

## Places: what the 480 are

| Group | Count | Explanation |
|---|---|---|
| Places with `place_sources` ("verified", default `/places`) | 357 (TASK 07.4: 97 + 260 enrichment) | every source confirmed on Overpass; audit PASS 2026-10-04: 97 sources, 0 violations |
| Places without `place_sources` | 123 | 112 synthetic/legacy seed (56 distinct places loaded twice, 2026-09-22 and 2026-09-29) + 11 places whose OSM source was non-genuine and was quarantined |

Verified-place categories now (357, TASK 07.4 enrichment): culture 111, attraction 111, cafe 55, hotel 25, nature 21, restaurant 15, beach 14, entertainment 5. Verified places by destination: Đà Nẵng 114, Hà Nội 110, Hội An 50, Huế 50, Nha Trang 33. (Before TASK 07.4 only 97 places were verified and none was an `attraction` or `beach`.)

Ratings: `rating IS NULL` for all 220 places and `review_count = 0` for all. There is no real rating data; the earlier 4.5 (100 places) and 0 (111) values were fabricated defaults, and the remaining 9 values were derived from mock reviews.

## Reviews

9 reviews from the tracked mock fixture `data/raw/vietnam_travel_reviews.json` ("Internal Development Test Mock Fixture (Unverified)"): 8 by `curator@wanderai.vn`, 1 by `test@wanderai.vn`. They are kept only as evidence/tests, labelled `source=synthetic`, `trusted=false`, hidden from `/places/:id` and excluded from rating aggregation.

## RAG documents (821)

| Source | Chunks | License |
|---|---|---|
| wikivoyage | 464 (10 docs) | CC BY-SA 3.0 |
| osm | 357 | ODbL 1.0 (every document is linked to a place with a verified OSM source; 357/357 verified places covered) |

## Reconciling earlier numbers

| Earlier claim | Reality now |
|---|---|
| "108 verified OSM places" | 108 had `place_sources`; 11 were non-genuine and quarantined, leaving **97** |
| 628 RAG chunks | 561 after TASK 07.3 (+67 quarantined); **821 after TASK 07.5** (464 wikivoyage + 357 osm), 164 quarantined in total |
| 100 places with rating 4.5 | 0; all ratings are NULL |
| `dataset_registry.osm_places` = 10 | UPDATED in TASK 07.4 to 357 (matches place_sources); earlier value differed from 97; the registry was not updated |

## Schema drift (unchanged)

The `init` migration defines `documents` with 6 columns; the live table has 21 columns plus `embedding`, an HNSW cosine index and a unique (content_hash, embedding_model) index, all applied by raw SQL outside Prisma migrations (`docs/ai/rag-pipeline.md`). The remediation migration guards its `documents` step on the `place_id` column existing, so it is safe on a fresh database.