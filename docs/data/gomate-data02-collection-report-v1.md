# GoMate Fresh OSM Collection Report (DATA-02 V1)

**Document Version:** 1.0.0  
**Collection Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-02 (OSM Fresh Collection & Normalization)  
**Endpoint Used:** `https://overpass-api.de/api/interpreter`  
*(Canonical Overpass query endpoint for GoMate DATA-02 collection; upstream authority remains OpenStreetMap)*

---

## 1. Executive Summary

This report documents the fresh, reproducible OpenStreetMap (OSM) data collection executed on **2026-10-07** for the GoMate MVP geographic corridor: **Hà Nội** and **Hạ Long**. 

All queries utilized reproducible Overpass QL files committed to version control, capturing response-level replication metadata (`osm_base: 2026-10-07T09:52:02Z`) and element-level version tracking (`osm_version`, `osm_changeset`, `osm_timestamp`).

---

## 2. Regional Collection Summary

| Metric | Hà Nội (`hanoi`) | Hạ Long (`halong`) | Total Corridor |
| :--- | :---: | :---: | :---: |
| **Bounding Box (`south, west, north, east`)** | `20.95, 105.75, 21.15, 105.95` | `20.85, 106.95, 21.05, 107.25` | — |
| **Query Specification File** | [`hanoi_v1.overpassql`](file:///d:/Do_an/wanderai/data/queries/osm/hanoi_v1.overpassql) | [`halong_v1.overpassql`](file:///d:/Do_an/wanderai/data/queries/osm/halong_v1.overpassql) | 2 QL files |
| **Raw Snapshot Artifact** | [`hanoi_2026-10-07.json`](file:///d:/Do_an/wanderai/data/raw/osm/hanoi_2026-10-07.json) | [`halong_2026-10-07.json`](file:///d:/Do_an/wanderai/data/raw/osm/halong_2026-10-07.json) | 2 JSON files |
| **Raw Snapshot Size** | 2,504,861 bytes (2.50 MB) | 120,946 bytes (121 KB) | 2.62 MB |
| **Cryptographic SHA-256** | `469417955e76d9f4eab8eab11401f13405e2d38a7d46027101013db4b0e0e9ea` | `de27ec3d3db00974c44725d01578c955d790a90bdc7da356d9098401fdb654f6` | Immutable |
| **Upstream `osm_base` Timestamp** | `2026-10-07T09:52:02Z` | `2026-10-07T09:52:02Z` | Synchronized |
| **Total Raw Elements** | **4,898** | **191** | **5,089** |
| **Normalized Candidate POIs** | **4,889** | **188** | **5,077** |
| **Filtered / Rejected Elements** | 9 | 3 | 12 |
| **Target Coverage Goal** | ~120 POIs | ~60 POIs | ~180 POIs |
| **Verified POIs Frozen in DB** | **145 POIs** (110 baseline + 35 new) | **188 POIs** (newly established) | **333 Corridor POIs** |
| **Corridor Target Satisfaction** | **121% of Target** (145 vs ~120) | **313% of Target** (188 vs ~60) | **PASS** |

---

## 3. Candidate Extraction Pool vs. Canonical Verified POI Universe

A critical methodological distinction is established between the upstream extraction pool and the canonical research universe:

1. **Normalized Candidate Extraction Pool ($N = 5,077$):**
   - Stored in [`data/processed/osm/hanoi_normalized_v1.json`](file:///d:/Do_an/wanderai/data/processed/osm/hanoi_normalized_v1.json) (4,889 POIs) and [`data/processed/osm/halong_normalized_v1.json`](file:///d:/Do_an/wanderai/data/processed/osm/halong_normalized_v1.json) (188 POIs).
   - Represents the complete spatial extraction of normalized OSM amenities within the bounding boxes conforming to Taxonomy V1.1.
   - Serves as an immutable reference corpus for future research expansions and density studies.

2. **Canonical Verified POI Universe ($N = 580$):**
   - Stored in [`data/curated/gomate_places_freeze_v1.json`](file:///d:/Do_an/wanderai/data/curated/gomate_places_freeze_v1.json) and mirrored in the active PostgreSQL `places` table.
   - Comprises the 580 verified tourism POIs with active OSM provenance records across all 6 research destinations (188 Ha Long, 145 Hanoi, 89 Da Nang, 80 Hoi An, 41 Nha Trang, 37 Hue).
   - In Hanoi, 35 high-confidence tourism candidates (prioritizing culture, heritage, attractions, nature, and Overture AUTO-LINK confirmed places) were added to the existing 110 verified baseline places, reaching 145 POIs (satisfying the ~120 target).
   - In Ha Long, all 188 normalized candidates were verified and imported to overcome the zero-POI baseline.
   - **Strict Governance Rule:** Recommender evaluation track REC-A operates strictly on the 580 canonical verified POIs, not the 5,077 raw extraction pool.

---

## 4. Freshness & Provenance Metadata Envelope

Every collected raw response and parsed record preserves the full upstream provenance envelope:

```json
{
  "query_metadata": {
    "endpoint": "https://overpass-api.de/api/interpreter",
    "query_timestamp_utc": "2026-10-07T09:53:44Z",
    "osm_base": "2026-10-07T09:52:02Z",
    "license": "ODbL 1.0",
    "attribution": "© OpenStreetMap contributors"
  },
  "element_sample": {
    "type": "node",
    "id": 995292144,
    "version": 4,
    "changeset": 142058319,
    "timestamp": "2023-10-02T14:15:30Z",
    "lat": 20.9542018,
    "lon": 107.0345021,
    "tags": {
      "name": "BMC Thăng Long Hotel",
      "tourism": "hotel",
      "addr:city": "Hạ Long"
    }
  }
}
```

---

## 5. Ha Long Verified POI Corpus Establishment

Prior to DATA-02, the Ha Long destination in GoMate contained zero verified OSM POIs. DATA-02 successfully resolves this deficit:

- **188 verified POIs established** spanning all essential tourism categories:
  - **Hospitality (58 POIs):** BMC Thăng Long Hotel, Halong Plaza Hotel, Wyndham Legend, Muong Thanh Luxury, etc.
  - **Food & Beverage (58 POIs):** Cua Vàng, Hương Duyên Seafood, Cơm niêu Cựu Lục, 1958 Restaurant, etc.
  - **Attractions & Landmarks (18 POIs):** Sun World Ha Long, Dragon Park, Typhoon Water Park, Cầu Bãi Cháy.
  - **Culture & Heritage (16 POIs):** Đền Cửa Ông, Chùa Lôi Âm, Chùa Long Tiên, Bảo tàng Quảng Ninh.
  - **Shopping & Commerce (15 POIs):** Chợ Hạ Long 1, Chợ Cái Dăm, Vincom Plaza Hạ Long, Chợ đêm Bãi Cháy.
  - **Nature & Coastal (13 POIs):** Hang Sửng Sốt, Động Thiên Cung, Hang Đầu Gỗ, Bãi tắm Bãi Cháy, Đảo Ti Tốp.
  - **Transport Hubs (10 POIs):** Cảng tàu khách quốc tế Hạ Long, Bến phà Tuần Châu, Cảng tàu du lịch Quốc tế Tuần Châu.

---

## 6. Architectural & Reproducibility Guarantees

1. **Deterministic Queries:** Both `.overpassql` query scripts are version-controlled in [`data/queries/osm/`](file:///d:/Do_an/wanderai/data/queries/osm/).
2. **Immutable Raw Snapshots:** Raw response bytes are committed to [`data/raw/osm/`](file:///d:/Do_an/wanderai/data/raw/osm/) and verified against cryptographic SHA-256 hashes.
3. **No Schema Invasions:** All OSM metadata is stored within standard JSONB fields (`place_sources.raw_data`), maintaining `schema.prisma` completely untouched.
