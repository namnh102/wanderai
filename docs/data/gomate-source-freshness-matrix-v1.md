# GoMate Source Freshness Matrix & Canonical Strategy Lock (V1)

**Document Version:** 1.0.0  
**Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01B (Source Freshness, Version Reconciliation & Data Contract Lock)  
**Status:** CANONICAL DATA SOURCE STRATEGY LOCKED FOR DATA-02

---

## 1. Canonical Source Strategy Lock

To ensure that the GoMate data foundation is legally compliant, mathematically sound, reproducible for academic defense, and operationally reliable, the following canonical source hierarchy is strictly locked:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   GOMATE CANONICAL DATA SOURCE STRATEGY                  │
├────────────────────────────────┬─────────────────────────────────────────┤
│ Role                           │ Locked Canonical Source / Authority     │
├────────────────────────────────┼─────────────────────────────────────────┤
│ Primary Factual POI            │ OpenStreetMap (Overpass API) [ODbL 1.0] │
│ Secondary POI Freshness Source │ Overture Maps Places [CDLA Permissive]  │
│ RAG & Grounding Knowledge Base │ Wikivoyage API [CC BY-SA 3.0] + OSM     │
│ Collaborative RecSys Benchmark │ ViHoRec Official Upstream [CC BY-NC 4.0]│
│ Textual Aspect Reviews (ABSA)  │ VLSP 2018 (Hotel & Restaurant) [DUA]    │
│ Multimodal Review Benchmark    │ ViMACSA 2025 [Academic Agreement]       │
│ Commercial Scraped Platforms   │ Google Maps / Booking / Agoda: EXCLUDED │
└────────────────────────────────┴─────────────────────────────────────────┘
```

### 1.1. Strategic Exclusion of Google Maps
- **Status:** `GOOGLE_MAPS_DATASET_USE = EXCLUDED`.
- **Reason:** Google Maps Platform Terms of Service (Section 3.2.3) strictly prohibit:
  1. Permanent caching or persistent offline storage of place attributes beyond 30 days.
  2. Scraping review text, star ratings, or photos.
  3. Utilizing platform content to train or evaluate machine learning / recommendation models.
  4. Creating independent derivative spatial databases.
- Incorporating Google Maps data into the GoMate repository would destroy academic thesis reproducibility and create direct legal liability. Google Maps is **strictly excluded** from thesis datasets, vector indexes, and evaluation benchmarks.

---

## 2. Comprehensive Source Freshness Matrix

| Source Identifier | Role in Architecture | Provider / Endpoint | Local Snapshot Date / Version | Upstream Latest Verified Version | Freshness Status | Target DATA-02 Action |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **osm_overpass_places** | Primary Factual POI Catalog | OpenStreetMap via Overpass API (`overpass-api.de`) | 2026-10-04 (357 verified places) | Continuous live upstream | **STALE_RECOLLECT_PLANNED** | Execute fresh collection for **Hanoi + Ha Long** (and existing regions) with timestamp pinning. |
| **overture_maps_places** | Secondary Cross-Check / Freshness Verification | Overture Maps Foundation | Not yet collected | Release `2026-09-23.1` (Schema v2.0.0) | **READY_FOR_CROSSCHECK** | Plan offline entity resolution against OSM canonical places in DATA-02. |
| **wikivoyage_rag_corpus** | Knowledge Base for RAG & Planner Grounding | Wikimedia Foundation (MediaWiki Action API) | 2026-10-04 (464 chunks across 10 destinations) | Live revisions pinned (Hanoi: `5379087`, Ha Long: `5294720`) | **FRESH_PINNED** | Lock revision IDs and timestamps in database metadata; do not query unversioned text. |
| **vihorec_benchmark** | Collaborative Filtering Recommendation Benchmark | Minh Hoang Nguyen (arXiv:2607.12946) | 2026-10-01 (17,911 interactions, 560 hotels) | Current Master Release (`MinhNguyenDS/ViHoRec`) | **CURRENT_OFFICIAL** | Freeze existing local files (`data/restricted/vihorec/`); lock SHA256 checksums. Zero re-download needed. |
| **vlsp_2018_absa** | Ground Truth for Aspect-Based Sentiment Analysis | VLSP Campaign Organizers (*J. Comput. Sci. & Cybern.*) | None (Not in repo) | Release 2018 (5,600 annotated reviews) | **ACCESS_PENDING_DUA** | Human researcher signs DUA and submits to `vlsp.resources@gmail.com`. |
| **vimacsa_2025** | Multimodal Review & Image Grounding | UIT VNU-HCM (*Multimedia Systems*, 2025) | None (Not in repo) | Release 2025 (4,876 text-image pairs) | **OPTIONAL_REQUEST** | Optional academic request to UIT NLP Group (`kietnv@uit.edu.vn`). |
| **open_meteo_weather** | Real-Time Dynamic Tool for Agent Planner | Open-Meteo REST API | Dynamic runtime query | Continuous live API | **RUNTIME_API** | Ephemeral runtime querying; zero persistent disk caching required. |
| **google_maps_places** | External Commercial Map Provider | Google LLC | None | N/A | **EXCLUDED** | Strictly excluded from offline datasets and model training. |

---

## 3. OSM Freshness Audit & October 4 Limitations

The current OpenStreetMap snapshot residing in `data/curated/` and PostgreSQL (357 verified places) was assembled across October 1–4, 2026. **This snapshot cannot be accepted as the final frozen dataset for the thesis**, due to three concrete deficiencies:

1. **Total Absence of Ha Long POIs:**  
   The October 4 collection covered only 5 regions: Đà Nẵng, Hà Nội, Hội An, Huế, and Nha Trang. Ha Long (the primary travel corridor partner for Hanoi) has **0 verified places** in the repository.
2. **Missing Upstream Revision Identifiers:**  
   The October 4 pipeline stored element IDs (`node/123456`) and coordinate snapshots, but did not persist upstream OSM element version numbers (`version`), changeset IDs (`changeset`), or upstream editor timestamps (`timestamp`).
3. **Overpass Mirror Inconsistencies:**  
   During early runs, queries alternated between `overpass-api.de` and `overpass.kumi.systems`. As discovered in Task 07.3, mirror caches can lag behind the authoritative master, leading to transient discrepancies.

---

## 4. Fresh Collection Specifications for DATA-02

For the upcoming DATA-02 freeze, collections will be executed exclusively against the authoritative host `https://overpass-api.de/api/interpreter`, capturing complete upstream metadata for every element.

### 4.1. Regional Bounding Boxes & Target Quotas

| Destination | Status in Scope | Minimum Lat | Minimum Lon | Maximum Lat | Maximum Lon | Target Verified POI Quota | Core Category Focus |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Hanoi** | **MVP CORE** | 20.95 | 105.75 | 21.15 | 105.95 | $\ge 120$ POIs | Culture, historic monuments, specialty cafes, lakes, attractions |
| **Ha Long** | **MVP CORE** | 20.85 | 106.95 | 21.05 | 107.25 | $\ge 60$ POIs | Scenic viewpoints, beaches, boat stations, seafood dining, caves |
| **Đà Nẵng** | Research Baseline | 15.90 | 108.05 | 16.20 | 108.35 | $\ge 100$ POIs | Beaches, modern bridges, mountains, dining |
| **Hội An** | Research Baseline | 15.85 | 108.30 | 15.92 | 108.40 | $\ge 50$ POIs | Ancient town culture, pagodas, tailors, riverside dining |
| **Huế** | Research Baseline | 16.42 | 107.54 | 16.50 | 107.65 | $\ge 50$ POIs | Imperial citadel, royal tombs, pagodas, traditional food |
| **Nha Trang** | Research Baseline | 12.18 | 109.15 | 12.32 | 109.25 | $\ge 40$ POIs | Coastal beaches, islands, towers, seafood |

### 4.2. Mandatory Fields Recorded per OSM Element in DATA-02
Every element ingested during DATA-02 must capture:
```json
{
  "source_name": "osm",
  "osm_type": "node | way | relation",
  "osm_id": 123456789,
  "osm_version": 4,
  "osm_changeset": 154829102,
  "osm_timestamp": "2026-08-14T09:21:44Z",
  "query_timestamp_utc": "2026-10-07T16:00:00Z",
  "overpass_endpoint": "https://overpass-api.de/api/interpreter",
  "license": "ODbL 1.0 (c) OpenStreetMap contributors",
  "latitude": 21.0285,
  "longitude": 105.8542,
  "tags": { ... }
}
```
