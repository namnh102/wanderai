# Data / Source Card — W1 (state at commit `2d15a64`, 2026-10-03)

> **ARTIFACT STATUS: RECONSTRUCTED FROM EXISTING REPOSITORY.**
> This card was written on 2026-10-05 by consolidating files that already existed in W1. It was **not necessarily created during W1** and must not be cited as a W1-dated artifact.
>
> **ORIGINAL W1 EVIDENCE** (created inside 27/09–03/10, citable as-is):
> | Original W1 file | Commit (date) |
> |---|---|
> | `docs/data/data-sources.md` | `8592aea` (2026-10-01), updated `ffe7b97`, `4944fae` |
> | `data/manifests/sources.yaml` | `b5e96db` (2026-10-01), updated `ffe7b97`, `4944fae` |
> | `docs/data/dataset-card.md` | `ffe7b97` (2026-10-01), updated `4944fae` |
> | `docs/data/data-quality-report.md` | `ffe7b97` (2026-10-01) |
> | `docs/data/reproducibility.md` | `ffe7b97`, `4944fae` |
> | `docs/architecture/decisions/ADR-002-real-data-pipeline.md` | `8592aea` (2026-10-01) |
> | `docs/data/current-database-state.md` (reconciliation) | `2d15a64` (2026-10-03) |

## 1. Sources

| Source | Role | License (as documented in repo) | Attribution / restriction (as documented) | Retrieved / snapshot | Verification status |
|---|---|---|---|---|---|
| OpenStreetMap via Overpass API (`https://overpass-api.de/api/interpreter`) | POI (place name, lat/lon, tags) | ODbL 1.0 — `sources.yaml`, `data-sources.md`, `dataset-card.md` | "© OpenStreetMap contributors"; Share-Alike on derivative databases | `collection_date: 2026-10-01` (manifest). Raw file has **no embedded timestamp** | License: DOCUMENTED in repo (not independently re-checked against osm.org in this task). Snapshot: PARTIALLY VERIFIED |
| Wikivoyage (MediaWiki API) | RAG text for 10 destinations (not POI) | CC BY-SA 3.0 — `docs/ai/rag-pipeline.md`, `current-database-state.md` | Attribution + share-alike | Not recorded in W1 files | DOCUMENTED; snapshot date NOT VERIFIED |
| Open-Meteo API | Runtime weather | CC BY 4.0 — `sources.yaml` | Attribution; not stored | Runtime | DOCUMENTED |
| Internal review fixtures (`data/raw/vietnam_travel_reviews.json`) | Pipeline tests only | **UNKNOWN / UNVERIFIED** — `sources.yaml` | Not for Review AI | 2026-10-01 | **LICENSE STATUS: NOT VERIFIED** (synthetic fixtures; earlier UIT-VSFC attribution retracted in `4944fae`) |
| Synthetic seed (`data/seed/synthetic_*.json`, `database/seed/*.json`) | UI/API mock data | Internal; `generated: true, trusted: false` | Quarantined | 2026-09-01 (manifest) | Synthetic by design |

## 2. How the OSM data was obtained
- Pipeline: `data/pipelines/osm/collect_osm.py` → `parse_osm.py` → `data/pipelines/entity_resolution/resolve.py` (documented in `docs/data/reproducibility.md`).
- Pilot bounding boxes (`data/pipelines/osm/config.py`): Đà Nẵng, Hà Nội, Hội An, Nha Trang, Huế. No Hạ Long box.
- `reproducibility.md` states the collector input is "Overpass API **or verified fallback baseline**". TASK 07.1 audit (`2d15a64`) found 11 of 110 source records came from hand-written entries in the raw file with non-genuine OSM IDs.

## 3. Pilot dataset (see `dataset-summary.txt`)
`data/curated/places_canonical.json`: 108 places, 110 source rows, 6 categories, 13 fields; Đà Nẵng 55, Hà Nội 50, Hội An 1, Huế 1, Nha Trang 1.

## 4. Known limitations at end of W1
1. 11/108 places have non-genuine OSM IDs (97 confirmed genuine).
2. All 108 ratings are a default 4.5 with 0 reviews (not collected data).
3. 66/108 addresses are placeholders (`<name>, <city slug>`).
4. `city` values use two label formats.
5. No opening-hours / contact fields.
6. Reviews: no authentic travel-review dataset (VLSP 2018 / ViMACSA access not obtained).

## 5. Intended use
Pilot POIs for map/search, AI itinerary generation and RAG grounding in the prototype. Not a production-quality dataset at W1.
