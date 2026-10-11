# TASK 07.3 — Provenance & Data Integrity Remediation

Date: 2026-10-04. Branch `fix/data-provenance-remediation`. Closes R2, R3, R4, R5 from the TASK 07.1 audit.
Scope: data integrity only. No AI provider, planner, recommendation, Place Detail, Google Maps or 9Router changes.

Mechanism: Prisma migration `20261004010000_provenance_remediation` (schema + idempotent data remediation, applied with `prisma migrate deploy`), plus code guards so a re-import cannot reintroduce the problems. Nothing was deleted without a copy in an audit table.

Raw evidence: `docs/audit/evidence/` (`db-counts-before.txt`, `db-counts-after.txt`, `verified-places-before.json`, `provenance-before.json`, `provenance-after.json`).

## A. OSM provenance (R2)

| | Before | Action | After |
|---|---|---|---|
| `place_sources` rows | 110 | 11 rows with non-genuine OSM ids moved to `place_source_quarantine` (raw row + reason + evidence), plus 2 more found by the live audit (see E) | 97 |
| Places with ≥1 source (`verifiedOnly=true`) | 108 | the 11 places lost their only source | **97** |
| Quarantine rows | 0 | | 13 (11 + 2) |

The 11 ids are listed in `data/manifests/osm-invalid-sources.json`. Reasons: 5 ids point to unrelated OSM nodes (`osm_id_points_to_unrelated_object`: Hồ Hoàn Kiếm, Ngũ Hành Sơn, Lăng Chủ tịch Hồ Chí Minh, Chùa Cầu Hội An, Cầu Rồng) and 6 ids do not exist upstream (`osm_id_not_found_upstream`: Chùa Linh Ứng, Mỹ Khê, Văn Miếu, Đại Nội Huế, Tháp Bà Ponagar, Bảo tàng Điêu khắc Chăm). Verified with the Overpass API on 2026-10-03 (TASK 07.1).

No replacement ids were invented and no re-ingestion was attempted. The 11 places stay in `places` as unsourced records (not exposed by `verifiedOnly=true`). Re-ingesting them from genuine OSM objects is a separate, optional task.

Code guards: `import-curated.ts` skips denylisted sources; the 11 sources were removed from `data/curated/places_canonical.json` (those places now have `sources: []`).

## B. Fabricated ratings (R3)

| | Before | After |
|---|---|---|
| `rating = 4.5` and `review_count = 0` | 100 | 0 |
| `rating = 0` (default for unrated) | 111 | 0 |
| `rating IS NULL` | 0 | 220 |
| places with `review_count > 0` | 9 | 0 |

Ratings are now derived only from trusted, non-deleted reviews; with none the value is NULL (not 0, not a default). Changes:
- DB: `places.rating` is nullable with no default (migration).
- Pipeline: `resolve.py` no longer defaults to 4.5; `clean_reviews.py` drops a review with a missing or invalid rating instead of defaulting to 5.0; `quality_checker.py` accepts a NULL rating.
- Importer: `rating ?? null`; aggregates only trusted reviews.
- API: `/places` orders `rating DESC NULLS LAST`; `/places` and `/places/nearby` return `rating: null`.
- Flutter: `PlaceModel.rating` is `double?`; the preview sheet shows "Chưa có đánh giá" instead of a star value.

## C. Synthetic reviews (R5)

| | Before | After |
|---|---|---|
| reviews | 9 (8 by `curator@wanderai.vn`, 1 by `test@wanderai.vn`) | 9 (kept as evidence/tests) |
| `source = 'synthetic'`, `trusted = false` | 0 | 9 |
| trusted reviews | 9 (all presented as real) | 0 |

`reviews` gained `source` (default `user`) and `trusted` (default `true`). `/places/:id` exposes only trusted reviews and the place review count/rating ignore untrusted ones. The importer labels curated-fixture reviews synthetic/untrusted.

## D. RAG provenance (R4)

| | Before | After |
|---|---|---|
| `documents` rows | 628 | 561 |
| `source_name = osm` | 164 | 97 (all on places with a verified source) |
| `wikivoyage` | 464 | 464 (unchanged) |
| OSM-labelled chunks on places without a verified source | 56 synthetic + 11 now-unverified = 67 | 0 |
| `document_quarantine` | 0 | 67 (original row as JSON, minus the embedding vector) |

Chunks were removed from production retrieval and quarantined, not relabelled. `ingest_canonical_places` now ingests only places with an OSM `place_sources` row.

## E. Verification

- `python data/pipelines/provenance_audit.py` checks every place exposed by `verifiedOnly=true` against Overpass (existence, ≤150 m coordinates) and the API invariants. Results (Overpass API, run 2026-10-04):

| Run | verified places | OSM sources checked | violations | result |
|---|---|---|---|---|
| BEFORE (snapshot `verified-places-before.json`) | 108 | 110 | 113 (100 fabricated 4.5 ratings, 6 not upstream, 7 coordinates far from the node) | FAIL |
| AFTER first run (live API) | 97 | 99 | 2 | FAIL |
| AFTER follow-up migration | 97 | 97 | 0 | **PASS** |

The first AFTER run found 2 real OSM nodes attached to the wrong hotels (`node/708488382` Khách Sạn Classic, 307 m from `Khách Sạn Classic 2`; `node/708488342` Khách Sạn Little Hanoi, 156 m from `Khách Sạn Little Hanoi Diamond`; name differs and distance > 150 m). They were quarantined with reason `osm_node_mismatches_place` (migration `20261004020000_provenance_remediation_followup`, also added to the denylist and `places_canonical.json`). Both places have a second source and stay verified, so verifiedOnly stays 97 and no RAG chunk changed. place_sources 99 -> 97, quarantine 11 -> 13. Evidence: `docs/audit/evidence/provenance-before.json`, `provenance-after.json`.
- New tests: `apps/backend/test/provenance.e2e-spec.ts` (6) and `apps/ai-service/tests/test_provenance_integrity.py` (6); Flutter `map_test.dart` +1. `places.e2e-spec.ts` now expects 97.

## Limitations (not fixed here)

- 112 synthetic + 11 demoted places still exist and appear in default `/places` (no `verifiedOnly`).
- The 11 demoted places could be re-ingested from real OSM objects; not done.
- `data/raw/osm_vietnam_sample.json`, `data/processed/osm_places.json` and the `collect_osm.py` fallback still contain the hand-written entries (kept as evidence; the denylist guards the import).
- The `documents` column drift (raw SQL outside migrations) is unchanged.
