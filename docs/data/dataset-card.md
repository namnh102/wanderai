# Dataset Card — GoMate Travel Data Ingestion

## 1. Dataset Summary
- **Dataset Name:** GoMate Canonical Vietnam POIs & Travel Reviews Dataset
- **Version:** 1.0.0
- **Curated Date:** October 2026
- **Domain:** Vietnam Tourism, Travel POIs, Accommodations, and Dining
- **Language:** Vietnamese (`vi`), with English transliterations (`en`)
- **Intended Use:** AI trip itinerary generation, PostGIS nearby search, destination catalog, aspect sentiment analysis, and companion matching recommendations.

---

## 2. Licensing and Compliance
| Sub-dataset | Primary Source | License | Attribution Requirement |
| :--- | :--- | :--- | :--- |
| **Geographic POIs** | OpenStreetMap (OSM) via Overpass API | **ODbL 1.0** | "© OpenStreetMap contributors" |
| **Travel Reviews** | Academic Vietnamese Sentiment Benchmark | **CC BY 4.0** | "UIT-VSFC & Mendeley Open Research Data (2023)" |
| **Synthetic Baseline** | Development Mock Data | Internal Dev Only | Quarantined in `data/seed/` (`generated: true, trusted: false`) |

> [!IMPORTANT]
> **Scraping Prohibition:** GoMate strictly abides by ethical data policies. No unauthorized scraping of Google Maps, Booking.com, TripAdvisor, or TikTok is performed or allowed in the pipeline.

---

## 3. Dataset Composition & Statistics
- **Total Canonical Places:** 108 places across Da Nang, Hanoi, Hoi An, Hue, Nha Trang
- **External Source Provenance Records:** 110 linked OSM nodes/ways
- **Curated Linked Reviews:** 8 authentic reviews linked to canonical places, 1 quarantined unmatched review
- **Aspect Ratings:** 16 tagged aspect ratings (`cleanliness`, `location`, `service`, `value`, `food`)
- **Geographic Bounding Box:**
  - Latitude: $[8.18, 23.39]$
  - Longitude: $[102.14, 109.46]$
  - Coordinate Validity Rate: 100%

---

## 4. Entity Resolution Methodology
The ingestion pipeline resolves duplicate representations across disparate data sources into a canonical UUID entity:

```
Raw OSM POI + External Review Target
                ↓
    Text Normalization & Accent Stripping
                ↓
    Category Stopword Removal (bai, bien, chua, hotel...)
                ↓
    Multi-Signal Matching:
      • Name Token Jaccard / Substring: 50%
      • Haversine Geographic Distance:  35%
      • Taxonomy Category Alignment:   15%
                ↓
    Thresholding Classification:
      • Score ≥ 0.80  → Auto-Merge into Canonical Entity
      • 0.60 ≤ s < 0.80 → Flag for Human Review Queue
      • Score < 0.60  → Create New Canonical Place / Unmatched
```

---

## 5. Maintenance & Reproducibility
- **Pipeline Scripts:**
  - `data/pipelines/osm/collect_osm.py` — Overpass data extraction
  - `data/pipelines/osm/parse_osm.py` — Normalization and validation
  - `data/pipelines/entity_resolution/resolve.py` — Multi-signal deduplication
  - `data/pipelines/reviews/clean_reviews.py` — Text cleaning and privacy filter
  - `data/pipelines/reviews/link_reviews.py` — Review to canonical place linking
  - `data/pipelines/quality_checker.py` — Quality assurance gate
  - `apps/backend/prisma/import-curated.ts` — Idempotent PostgreSQL import
