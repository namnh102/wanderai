# GoMate Current Data Inventory & Audit Report (V1)

**Document Version:** 1.0.0  
**Audit Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01A (Current Data Inventory & External Source Candidate Preparation)  
**Compliance Mandate:** Zero external dataset downloads; zero website scraping; zero production code modification; zero Prisma schema changes.

---

## 1. Executive Summary

This document presents a comprehensive audit and empirical inventory of all travel data assets, ingestion pipelines, database schemas, and knowledge corpora currently residing in the WanderAI (GoMate) repository. 

### Key Audit Findings
1. **POI Reality:** The database contains **480 places**, of which **357 places are verified** with upstream OpenStreetMap provenance across 5 pilot tourism regions (Đà Nẵng, Hà Nội, Hội An, Huế, Nha Trang). 123 places are unsourced development/synthetic records (112 legacy synthetic seed duplicates + 11 quarantined invalid OSM sources).
2. **Review Data Reality:** Exactly **9 review records** exist in the repository fixtures and database. All 9 are **handcrafted synthetic mock fixtures** (`source='synthetic'`, `trusted=false`, `rating IS NULL` on places, excluded from production queries). There is **zero real user review text** in the active database.
3. **Restricted Research Benchmark (ViHoRec):** The local repository contains the ViHoRec hotel recommendation dataset (`data/restricted/vihorec/`) comprising **17,911 interactions**, **6,822 users**, and **560 hotels** across Vietnam under CC BY-NC 4.0. Crucially, ViHoRec is a **pure numerical rating & interaction log**; it contains **zero textual reviews**.
4. **RAG Knowledge Base:** 821 knowledge documents exist in PostgreSQL pgvector (464 chunks from official Wikivoyage English articles for 10 pilot destinations under CC BY-SA 3.0, and 357 OSM place knowledge documents under ODbL 1.0). No static Wikivoyage dump file is committed to disk; ingestion is executed via the MediaWiki Action API.
5. **Preference Representation Gap:** While `TravelPreference` exists in `schema.prisma`, it lacks an update API endpoint in NestJS (`PUT /users/me/preferences` is missing). Furthermore, critical travel dimensions such as **travel pace** and **dynamic constraints** are absent from the database schema.

---

## 2. Comprehensive Repository Data Inventory

The following table itemizes every data file, fixture, seed, and database table currently present in the repository.

| Filename / Table | Row / Record Count | Source / Provenance | License | Snapshot Date | Geographic Scope | Quality & Integrity Issues | Usable for Thesis? |
| :--- | :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| `database.places` (PostgreSQL) | 480 | OSM Overpass API (357) + Legacy Seed (123) | ODbL 1.0 (verified) / None (synthetic) | 2026-10-04 | 5 Pilot Regions (Đà Nẵng, Hà Nội, Hội An, Huế, Nha Trang) + Synthetic National | 123 records lack verified provenance; all ratings are `NULL`; `price_min`/`max` missing on OSM places. | **YES** (Verified subset of 357 only) |
| `database.destinations` (PostgreSQL) | 50 | Synthetic Seed (`destinations.json`) | Project Internal / None | 2026-09-22 | National Vietnam (50 destinations across 30+ provinces) | AI-generated descriptions and arbitrary default ratings; coordinates are approximate. | **YES** (Prototyping & spatial bounding) |
| `database.place_sources` (PostgreSQL) | 357 | OpenStreetMap Overpass API | ODbL 1.0 | 2026-10-04 | Đà Nẵng (114), Hà Nội (110), Hội An (50), Huế (50), Nha Trang (33) | 100% verified upstream; zero violations against Overpass authoritative endpoints. | **YES** (Authoritative POI baseline) |
| `database.place_source_quarantine` | 13 | Quarantined OSM IDs | N/A (Audit Trail) | 2026-10-04 | Various | 11 non-existent upstream OSM IDs + 2 coordinate/place mismatch nodes isolated from production. | **NO** (Audit log only) |
| `database.reviews` (PostgreSQL) | 9 | Mock Fixture (`vietnam_travel_reviews.json`) | UNKNOWN / Mock | 2026-10-01 | Synthetic Đà Nẵng (4), Hà Nội (2), Hội An (1), Huế (1), Vùng sâu (1) | Fabricated mock reviews; `trusted=false`; unusable for sentiment analysis or NLP training. | **NO** (ETL pipeline smoke tests only) |
| `database.documents` (pgvector RAG) | 821 | Wikivoyage API (464) + OSM Places (357) | CC BY-SA 3.0 (Wikivoyage) / ODbL 1.0 (OSM) | 2026-10-04 | 10 Pilot Destinations (Wikivoyage) + 5 Pilot Regions (OSM) | Raw vector table drifted from Prisma schema (managed via SQL); HNSW index operational. | **YES** (Grounding & RAG retrieval) |
| `database.document_quarantine` | 164 | Quarantined RAG Chunks | N/A (Audit Trail) | 2026-10-04 | Various | 67 chunks on unsourced places + 97 superseded legacy OSM document formats. | **NO** (Audit log only) |
| `database.dataset_registry` | 2 | PostgreSQL Metadata Tracking | Internal | 2026-10-04 | National | Tracks `osm_places` (357) and `wikivoyage_vn` (464). | **YES** (Provenance metadata) |
| `data/curated/places_canonical.json` | 108 | OSM Overpass API | ODbL 1.0 | 2026-10-01 | Đà Nẵng (55), Hà Nội (50), Hội An (1), Huế (1), Nha Trang (1) | 11 records have non-genuine OSM IDs (subsequently quarantined in DB); description is 100% null; rating is 100% null. | **YES** (After filtering 11 quarantined) |
| `data/curated/places_osm_enrichment.json` | 260 | OSM Overpass API | ODbL 1.0 | 2026-10-03 | Đà Nẵng (64), Hà Nội (63), Hội An (50), Huế (50), Nha Trang (33) | 100% verified OSM sources; rating is 100% null; name_en missing 33.8%; 1 duplicate coordinate pair. | **YES** (Core POI catalog for pilot regions) |
| `data/raw/osm_vietnam_sample.json` | 111 | Raw Overpass API query | ODbL 1.0 | 2026-10-01 | Đà Nẵng, Hà Nội, Central coast | Raw JSON node elements; contains obsolete node IDs that failed downstream audit. | **NO** (Superseded raw snapshot) |
| `data/raw/osm_enrichment.json` | 485 | Raw Overpass API query (5 regions) | ODbL 1.0 | 2026-10-03 | Hà Nội (239), Huế (81), Đà Nẵng (75), Hội An (57), Nha Trang (33) | Raw Overpass responses; contains uncurated elements before applying caps and quality filtering. | **YES** (Reproducibility & raw audit) |
| `data/processed/osm_places.json` | 110 | Intermediate parsed OSM places | ODbL 1.0 | 2026-10-01 | Đà Nẵng (55), Hà Nội (52), others (3) | Intermediate pipeline artifact; 84.5% missing `name_en`; 2 duplicate brand names. | **NO** (Intermediate artifact) |
| `data/seed/synthetic_places.json` / `database/seed/places.json` | 56 | AI-generated seed sample | None / Fabricated | 2026-09-01 | 10 Destinations across Vietnam | Manually/LLM generated; rounded coordinates; fabricated price tiers and descriptions. | **NO** (Dev UI stubbing only) |
| `data/seed/synthetic_destinations.json` / `database/seed/destinations.json` | 50 | AI-generated destination seed | None / Fabricated | 2026-09-01 | 30+ Vietnamese provinces | Fabricated ratings (4.2 - 4.9); descriptions generated by LLM; approximate coordinates. | **YES** (High-level spatial routing only) |
| `data/seed/categories.json` / `database/seed/categories.json` | 10 | Curated reference taxonomy | Open Reference | 2026-09-01 | Application-wide | Base category list (restaurant, hotel, attraction, beach, temple, market, cafe, museum, park, nightlife). | **YES** (Baseline reference taxonomy) |
| `data/raw/vietnam_travel_reviews.json` | 9 | Internal mock review fixtures | UNKNOWN / UNVERIFIED | 2026-10-01 | Đà Nẵng (4), Hà Nội (2), Hội An (1), Huế (1), Vùng sâu (1) | Handcrafted test cases; previously mistakenly attributed to UIT-VSFC; zero real user provenance. | **NO** (ETL pipeline tests only) |
| `data/processed/reviews_normalized.json` | 9 | Intermediate normalized mock reviews | UNKNOWN / UNVERIFIED | 2026-10-01 | Matching raw reviews | Normalized text and aspect fixtures; non-factual. | **NO** (Test fixture) |
| `data/curated/reviews_curated.json` | 9 | Entity-linked curated mock reviews | UNKNOWN / UNVERIFIED | 2026-10-01 | Matching raw reviews | 1 review unlinked (`place_id` is null); purely for testing entity matcher mechanics. | **NO** (Test fixture) |
| `data/restricted/vihorec/hotels.csv` | 560 | ViHoRec Benchmark (Minh Hoang Nguyen) | CC BY-NC 4.0 | 2026-07 | 9 Vietnamese Cities (Đà Lạt 98, Nha Trang 78, Đà Nẵng 71, Vũng Tàu 68, Phan Thiết 60, Phú Quốc 55, Hội An 47, Huế 42, Quy Nhơn 41) | Contains only `hotel_id`, `name`, `location`. Zero coordinates (lat/long); zero street addresses. | **YES** (Academic hotel RecSys benchmark) |
| `data/restricted/vihorec/interactions.csv` | 17,911 | ViHoRec (Booking.com, Traveloka, iVIVU) | CC BY-NC 4.0 | 2026-07 | Same as hotels | Ratings on scale 1.0 to 10.0; timestamps and anonymized user IDs; **zero review text**. | **YES** (Collaborative filtering benchmark) |
| `data/restricted/vihorec/users.csv` | 6,822 | ViHoRec Benchmark | CC BY-NC 4.0 | 2026-07 | N/A | Anonymized user interaction frequencies. | **YES** (User profile analysis) |
| `data/restricted/vihorec/train.csv` | 8,645 | ViHoRec Official Train Split | CC BY-NC 4.0 | 2026-07 | Temporal train split | Rating interactions (userID, itemID, rating, timestamp). | **YES** (Offline RecSys model training) |
| `data/restricted/vihorec/val.csv` | 798 | ViHoRec Official Val Split | CC BY-NC 4.0 | 2026-07 | Temporal validation split | Leave-last-one-out validation interactions. | **YES** (Hyperparameter tuning) |
| `data/restricted/vihorec/test.csv` | 798 | ViHoRec Official Test Split | CC BY-NC 4.0 | 2026-07 | Temporal test split | Leave-last-one-out ground truth evaluation set. | **YES** (Official benchmark test metric calculation) |
| `data/evaluation/planner/*.json` | 3 | Synthetic itinerary ground truths | Internal | 2026-10-01 | Đà Nẵng 4D, Hà Giang 3D, Mộc Châu 3D | Hardcoded expected itinerary schema for evaluating LLM trip planner outputs. | **YES** (Planner regression testing) |
| `data/manifests/sources.yaml` | 6 entries | Project Provenance Registry | Internal | 2026-10-01 | Repository-wide | Provenance registry mapping raw, processed, and curated paths. | **YES** (Governance & audit trail) |
| `data/manifests/osm-invalid-sources.json` | 13 | Overpass verification audit log | Internal | 2026-10-04 | Pilot regions | Catalogues quarantined invalid OSM IDs. | **YES** (Integrity audit evidence) |

---

## 3. Deep-Dive Audit Across Required Dimensions

### 3.1. POI Datasets & Geographic Distribution
- **Total POI Count in Production Database:** 480 places.
  - **Verified Places (`place_sources` exists):** **357 places**.
  - **Unverified / Legacy / Quarantined Places:** **123 places** (112 legacy synthetic seed duplicates + 11 quarantined places).
- **Geographic Coverage of Verified POIs (357):**
  - **Đà Nẵng:** 114 places (31.9%) — Lat: [15.9863, 16.1219], Lon: [108.1328, 108.2891]
  - **Hà Nội:** 110 places (30.8%) — Lat: [20.9784, 21.0765], Lon: [105.7547, 105.8821]
  - **Hội An:** 50 places (14.0%) — Lat: [15.8654, 15.9082], Lon: [108.3142, 108.3985]
  - **Huế:** 50 places (14.0%) — Lat: [16.4321, 16.4987], Lon: [107.5521, 107.6234]
  - **Nha Trang:** 33 places (9.2%) — Lat: [12.1873, 12.2854], Lon: [109.1752, 109.2443]
- **Geographic Bounding Box (Verified Places):**
  - Latitude: $[12.1873, 21.0765]$ (covers Central and Northern pilot hubs; Southern Vietnam such as Ho Chi Minh City, Can Tho, Phu Quoc currently have **0 verified places**).
  - Longitude: $[105.7547, 109.2443]$.

### 3.2. Normalized Category Distribution
In the verified database (357 places), category representation is:
1. `culture`: 111 places (31.1%) — historical monuments, temples, pagodas, museums, archaeological sites.
2. `attraction`: 111 places (31.1%) — viewpoints, general tourist attractions, iconic landmarks.
3. `cafe`: 55 places (15.4%) — specialty Vietnamese coffee shops, historic cafes.
4. `hotel`: 25 places (7.0%) — hotels and guest houses (plus 560 hotels in ViHoRec tabular benchmark).
5. `nature`: 21 places (5.9%) — parks, natural scenic viewpoints, zoos.
6. `restaurant`: 15 places (4.2%) — restaurants, dining spots.
7. `beach`: 14 places (3.9%) — public beaches, coastal viewpoints.
8. `entertainment`: 5 places (1.4%) — theme parks, entertainment complexes.

### 3.3. Ingestion Scripts & Pipelines
The repository contains a robust, reproducible ETL pipeline architecture:
- `data/pipelines/osm/collect_osm.py`: Spatial Overpass API collector using regional bounding boxes and tag queries.
- `data/pipelines/osm/parse_osm.py`: Extracts names, normalized categories, formatted addresses, and coordinate validation.
- `data/pipelines/osm/enrich_osm.py`: Curates high-value tourism POIs with per-region quality capping and deterministic UUID generation.
- `data/pipelines/entity_resolution/resolve.py` & `matcher.py`: Levenshtein distance and geospatial radius matching to prevent cross-source duplicates.
- `data/pipelines/provenance_audit.py`: Automated test runner checking every stored place against authoritative live Overpass endpoints with a 150m tolerance window.
- `data/pipelines/quality_checker.py`: Schema validation, bounding box containment, duplicate coordinate detection, and missing field auditing.
- `apps/ai-service/app/rag/ingestion.py`: Section-aware chunking and embedding pipeline for Wikivoyage API articles and OSM canonical places.

### 3.4. Missing Fields & Data Quality Issues
1. **Rating Field:** 100% of verified places in the database have `rating = NULL` and `review_count = 0`. Previous values of 4.5 were purged in TASK 07.3 because they were fabricated defaults.
2. **Price Range:** `price_min` and `price_max` are `NULL` for 100% of OSM-derived places, as OpenStreetMap rarely contains standardized VND price information.
3. **Descriptions:** `description` is `NULL` for all canonical places. Descriptive text is supplied exclusively through the RAG pgvector `documents` table.
4. **English Place Names:** Missing in 33.8% of `places_osm_enrichment.json` and 84.3% of `places_canonical.json`.
5. **Duplicates:** 
   - Name duplicates exist where chain locations or generic names appear (e.g., "Bảo tàng Hồ Chí Minh" in different cities, "Chợ Đêm", "AnhLinh Coffee").
   - 1 duplicate coordinate was identified in `places_osm_enrichment.json`.
   - The database historically suffered from double-seeding of synthetic places (56 places loaded twice = 112 records).

### 3.5. RAG / Wikivoyage Knowledge Corpus Reality
- **Ingestion Mechanism:** Live fetch from `https://en.wikivoyage.org/w/api.php` using MediaWiki Action API (`explaintext=1`).
- **Ingested Destinations (10):** Vietnam (overview), Hanoi, Da Nang, Hoi An, Hue, Nha Trang, Da Lat, Ha Long Bay, Ninh Binh, Phu Quoc.
- **pgvector State:** 464 chunks stored in `documents` table with `license='CC BY-SA 3.0'`, `source_name='wikivoyage'`.
- **OSM Knowledge State:** 357 chunks generated deterministically from verified OSM tags with `license='ODbL 1.0'`, `source_name='osm'`.
- **Limitation:** There is **no committed raw text dump** of Wikivoyage on disk. Ingestion relies on network availability during ETL execution.

### 3.6. Review Data Reality
- **Production Database Reviews:** 9 rows. All 9 are synthetic test fixtures with `trusted=false`. Zero genuine customer reviews exist in the database.
- **ViHoRec:** Contains 17,911 interactions and 560 hotels, but **zero review text** (only user ID, hotel ID, rating float 1.0–10.0, date, and source platform).
- **Conclusion:** The project currently possesses **zero real Vietnamese textual review data** for Aspect-Based Sentiment Analysis (ABSA), NLP summarization, or review-based retrieval.

---

## 4. Thesis Usability Verdict

| Asset Cluster | Academic Thesis Usability | Justification & Constraints |
| :--- | :---: | :--- |
| **Verified OSM Places (357)** | **YES** | Legally compliant (ODbL 1.0), reproducible, verified against live Overpass endpoints. Provides solid ground truth for POI search, map visualization, and spatial clustering. |
| **ViHoRec Benchmark (data/restricted/vihorec/)** | **YES** | Legally compliant for non-commercial academic research (CC BY-NC 4.0). Enables rigorous offline recommender benchmarks (MostPopular, NCF, LightGCN) with standard metrics (NDCG@10, Recall@10). |
| **Wikivoyage RAG Corpus (464 chunks)** | **YES** | Permitted under CC BY-SA 3.0 with attribution. Provides factual context for AI agent grounding and destination guides. |
| **Synthetic Seed Places (56) & Reviews (9)** | **NO** | Must remain quarantined / hidden from thesis evaluations, baseline reports, and production API serving. |
| **Unprocessed External Review Text** | **UNKNOWN / BLOCKED** | Requires formal human acquisition and licensing verification (e.g., VLSP 2018 DUA or ViMACSA academic agreement) before any ingestion. |
