# Data Pipeline Reproducibility Guide

## 1. Prerequisites
- **Python:** 3.11+ (with `httpx`, `pytest`)
- **Node.js:** 20+ (with `pnpm` or `npm`)
- **Docker & Databases:**
  - PostgreSQL 16 (port 5432) with PostGIS extension enabled
  - Redis 7 (port 6379)

---

## 2. End-to-End Pipeline Execution

All commands are run from the repository root: `d:\Do_an\wanderai\`

### Step 1: OpenStreetMap POI Collection
Queries the Overpass API with pilot bounding boxes for Da Nang, Hanoi, Hoi An, Hue, Nha Trang.
```bash
python data/pipelines/osm/collect_osm.py
```
- **Input:** Overpass API or verified fallback baseline
- **Output:** `data/raw/osm_vietnam_sample.json` (~111 raw elements)

### Step 2: OSM Parsing & Coordinate Validation
Validates coordinates within Vietnam bounding box ($8.18 \le \text{lat} \le 23.39$, $102.14 \le \text{lon} \le 109.46$), standardizes categories and addresses.
```bash
python data/pipelines/osm/parse_osm.py
```
- **Input:** `data/raw/osm_vietnam_sample.json`
- **Output:** `data/processed/osm_places.json` (110 validated places)

### Step 3: Entity Resolution & Canonicalization
Applies multi-signal matching (name $50\%$, distance $35\%$, category $15\%$) to generate canonical GoMate entities.
```bash
python data/pipelines/entity_resolution/resolve.py
```
- **Input:** `data/processed/osm_places.json`
- **Output:** `data/curated/places_canonical.json` (108 canonical places) & `data/curated/entity_resolution_report.json`

### Step 4: Review Dataset Cleaning
Normalizes review test fixtures, clamps ratings ($1.0-5.0$), and structures aspect tags. (Note: These are internal test fixtures for pipeline mechanics; authentic dataset acquisition is pending before Task 07).
```bash
python data/pipelines/reviews/clean_reviews.py
```
- **Input:** `data/raw/vietnam_travel_reviews.json`
- **Output:** `data/processed/reviews_normalized.json`

### Step 5: Review to Canonical Place Linking
Deterministically links reviews to canonical places using token similarity and city alignment.
```bash
python data/pipelines/reviews/link_reviews.py
```
- **Input:** `data/processed/reviews_normalized.json`, `data/curated/places_canonical.json`
- **Output:** `data/curated/reviews_curated.json` (8 auto-linked, 1 isolated unmatched)

### Step 6: Data Quality Audit
Validates all data integrity constraints and outputs quality report.
```bash
python data/pipelines/quality_checker.py
```
- **Output:** `docs/data/data-quality-report.md` (100% pass)

### Step 7: Database Import (Idempotent)
Imports curated places, sources, and linked reviews into PostgreSQL.
```bash
cd apps/backend
npm run db:import-curated
```
- **Database Tables Updated:** `places`, `place_sources`, `reviews`, `review_aspects`

---

## 3. Regression Testing & Verification

Run all test suites across the stack to ensure zero regressions:

```bash
# 1. Backend E2E Tests (39 tests)
cd apps/backend
npm run test:e2e

# 2. AI Service Unit Tests (28 tests)
cd apps/ai-service
python -m pytest tests/ -v

# 3. Flutter Mobile Tests (39 tests)
cd apps/mobile
D:\flutter\bin\flutter.bat test
```

**Expected Result:** 106 tests PASS.
