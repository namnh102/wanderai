# Current Database State (snapshot 2026-10-03, TASK 07.1)

Source: live queries on DB `wanderai` (PostgreSQL via Docker `wanderai-postgres`) after removing the audit's own test rows. Baseline: users 5, trips 2 (1 live), itinerary_items 2, itineraries 2.

## Totals

| Table | Rows | Notes |
|---|---|---|
| destinations | 50 | 14 popular |
| places | 220 | 0 soft-deleted |
| place_sources | 110 | all `osm`, single batch 2026-10-01 |
| reviews | 9 | 2 users; 16 `review_aspects` |
| documents (RAG) | 628 | 384-dim embeddings, 0 null |
| users / trips | 5 / 2 | |
| Prisma migrations | 3 | `init`, `add_place_sources`, `add_trip_context_fields` |

## Places: what the 220 are

| Group | Count | Explanation |
|---|---|---|
| Places with `place_sources` ("verified" in the API) | 108 | 2 places have 2 sources (110 source rows). |
| - of which ≥1 source confirmed on Overpass (ID exists, coords within 50 m, same name) | 97 | genuine |
| - of which source NOT genuine | 11 | 5 IDs point to unrelated nodes 9,800–20,400 km away; 6 IDs do not exist. All 11 come from hand-written entries in `data/raw/osm_vietnam_sample.json`. |
| Places without `place_sources` (synthetic/legacy seed) | 112 | The seed of 56 distinct places loaded twice (2026-09-22 and 2026-09-29): every name+coordinate duplicated. Default rating 0.0. |
| Test places (by name pattern) | 0 | |

Verified-place categories (108): cafe 55, hotel 25, restaurant 15, attraction 9, culture 3, beach 1. Synthetic places span 10 categories (temple, market, park, museum, nightlife exist only as synthetic). Verified places lie in 5 destinations: Đà Nẵng 55, Hà Nội 50, Hội An 1, Nha Trang 1, Huế 1. All 108 have coordinates inside the Vietnam bounding box.

Ratings: 100 of the 108 verified places have rating exactly 4.5 and review_count 0. This is a fabricated default (`data/pipelines/entity_resolution/resolve.py`, `source_record.get("rating", 4.5)`), not collected data.

## Reviews

9 reviews from tracked `data/raw/vietnam_travel_reviews.json` (self-labelled "Internal Development Test Mock Fixture (Unverified)"): 8 on the 11 non-genuine places, 1 on synthetic "Cầu Vàng". They are synthetic and affect `rating`/`reviewCount` of those places.

## RAG documents (628)

| Source | Chunks | License |
|---|---|---|
| wikivoyage | 464 (10 docs) | CC BY-SA 3.0 |
| osm | 164 (164 docs) | ODbL |

515 chunks link to a destination, 164 to a place: 108 to sourced places, **56 to unsourced synthetic places** (mislabelled as OSM/ODbL), of which 11 chunks sit on the 11 non-genuine places.

## Reconciling earlier numbers

| Earlier claim | Reality now |
|---|---|
| "112 places" (status row 15, 2026-10-01) | 112 was the synthetic seed count at that time; the table now holds 220 (112 synthetic + 108 sourced). |
| "108 verified OSM places" | 108 have `place_sources`; only 97 are confirmed genuine on Overpass. |
| `dataset_registry.osm_places` = 10 | Differs from 108 places / 110 source rows; the registry was not updated. Not changed in this audit. |
| "37 tables" | 38 relations in `public` (adds `_prisma_migrations`, PostGIS objects). |
| "1 user" | 5 users. |

## Schema drift

The `init` migration defines `documents` with 6 columns; the live table has 21 columns plus `embedding`, an HNSW cosine index and a unique (content_hash, embedding_model) index, all applied by raw SQL outside Prisma migrations (`docs/ai/rag-pipeline.md`). `prisma migrate deploy` on a fresh DB reproduces only the 6-column table (verified on a throwaway DB, since dropped).
