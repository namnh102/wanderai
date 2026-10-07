# GoMate Da Nang Data Normalization, Quality & Curation Report (v2)

**Task:** MVP-SCOPE-01  
**Destination:** Đà Nẵng  
**Artifacts:**
- [`data/processed/osm/danang_normalized_v2.json`](file:///d:/Do_an/wanderai/data/processed/osm/danang_normalized_v2.json)
- [`data/processed/osm/danang_normalization_quality_stats_v2.json`](file:///d:/Do_an/wanderai/data/processed/osm/danang_normalization_quality_stats_v2.json)
- [`data/manifests/danang_coordinate_drift_stats_v2.json`](file:///d:/Do_an/wanderai/data/manifests/danang_coordinate_drift_stats_v2.json)

---

## 1. Quality Gates & Normalization Summary

Every element in the raw Da Nang OSM snapshot (`danang_2026-10-07_v2.json`) was subjected to strict automated quality gates:
1. **OSM Identity:** Must contain valid `type` (`node`, `way`, `relation`) and positive numeric `id`.
2. **Spatial Integrity:** Coordinates must fall strictly within the locked bounding box $[15.95, 107.95, 16.20, 108.35]$.
3. **Name Validation:** Name must have length $\ge 2$ characters and cannot match generic placeholder strings (`"unnamed"`, `"chưa đặt tên"`, etc.).
4. **Taxonomy V1.1 Compatibility:** Tags must map to a valid Tier-1 and Tier-2 category.
5. **Rating Integrity Invariant:** `rating = NULL` and `review_count = 0` are enforced unconditionally.

### Quality Gate Results:
- **Raw Elements:** 2,497
- **Accepted Normalized Candidates:** 2,497 (100.0%)
- **Rejected Elements:** 0
- **Duplicate Source IDs:** 0

---

## 2. Candidate Taxonomy & Missing Field Distribution

### 2.1. Tier-1 Category Distribution (N = 2,497)
| Tier-1 Category | Candidate Count | Percentage |
| :--- | :--- | :--- |
| **FOOD_BEVERAGE** | 1,619 | 64.8% |
| **HOSPITALITY** | 534 | 21.4% |
| **ATTRACTIONS_LEISURE** | 133 | 5.3% |
| **CULTURE_HERITAGE** | 102 | 4.1% |
| **SHOPPING_COMMERCE** | 55 | 2.2% |
| **NATURE_SCENERY** | 53 | 2.1% |
| **TRANSPORT_HUBS** | 1 | 0.04% |

### 2.2. Missing Field Analysis
- **Missing Address (`addr:*`):** 1,708 (68.4%)
- **Missing Opening Hours:** 2,182 (87.4%)
- **Missing Phone:** 2,214 (88.7%)
- **Missing Website:** 2,303 (92.2%)
- **Missing English Name (`name:en`):** 2,260 (90.5%)

Factual missing values are preserved as `None`/`NULL`; no values are fabricated or imputed.

---

## 3. Reconciliation Against Baseline Da Nang Database (N = 114)

Before applying mutations, the 114 existing Da Nang OSM POIs in PostgreSQL were audited against the fresh snapshot:
- **Matched in Fresh Snapshot (109 POIs):** Upstream OSM metadata (changeset, version, base timestamp) refreshed $\rightarrow$ Classified as `UPDATE_METADATA`.
- **Unmatched in Fresh Snapshot (5 POIs):**
  - 4 POIs located south of latitude $15.95^\circ\text{N}$ in Điện Bàn / Quảng Nam (`TASY STUDIO`, `Khu tưởng niệm Hà My`, `Đài tưởng niệm thảm sát Hà My`, `Mini-Golf Hoi An`).
  - 1 POI is an OSM relation geometry (`Bãi biển Mỹ Khê`, relation/19000664).
  - All 5 POIs are **preserved without destructive deletion** $\rightarrow$ Classified as `UNCHANGED`.

---

## 4. Deterministic Curation Contract for NEW POIs (N = 179)

To ensure the Da Nang tourism corpus is balanced across travel dimensions (avoiding pure F&B skew while addressing the baseline zero-hotel and zero-market deficit), a strict, reproducible deterministic curation contract was executed across all 2,388 un-matched candidates:

| Tier-1 Category | Unmatched Pool | Selection Rule & Gates | Qualifying | Selected | Status / Tie-Break |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TRANSPORT_HUBS** | 1 | All validated ferry/boat terminals | 1 | **1** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **CULTURE_HERITAGE** | 82 | Dual Overture `AUTO_LINK` OR verified contact (`phone`/`web`) | 33 | **33** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **SHOPPING_COMMERCE** | 55 | Dual Overture `AUTO_LINK` OR verified contact (`phone`/`web`) | 21 | **21** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **ATTRACTIONS_LEISURE** | 109 | Dual Overture `AUTO_LINK` OR verified contact (`phone`/`web`) | 14 | **14** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **NATURE_SCENERY** | 38 | Dual Overture `AUTO_LINK` OR verified contact (`phone`/`web`) | 2 | **2** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **HOSPITALITY** | 534 | Dual Overture `AUTO_LINK` AND verified contact (`phone`/`web`) | 57 | **57** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **FOOD_BEVERAGE** | 1,569 | Non-cafe dining (`t2 != cafe_tea`) AND Dual `AUTO_LINK` AND contact | 51 | **51** | `ALL_QUALIFYING_SELECTED` (No truncation) |
| **TOTAL** | **2,388** | Fully deterministic multi-tier gates | **179** | **179** | **100% Deterministic (Zero arbitrary selection)** |

### Curation Determinism Guarantees:
1. **Zero Undefined "Top" Truncation:** Exactly 57 candidates in `HOSPITALITY` and 51 dining candidates in `FOOD_BEVERAGE` satisfied the rigorous dual-source and contact verification gates; 100% of qualifying candidates were accepted (`ALL_QUALIFYING_SELECTED`).
2. **Order Invariance:** Selection is mathematically independent of stream order, database physical row storage, or incidental Overpass query ordering.
3. **No Fabricated Data:** Rating remains `NULL` and `review_count = 0` for all 179 curated places.

### Resulting Da Nang Canonical Verified Corpus:
$$\text{Baseline Preserved (114)} + \text{Curated NEW (179)} = \mathbf{293} \text{ Canonical POIs}$$
- **Da Nang Primary Core (in REC-A-CORE-V2):** $293 - 4 = \mathbf{289}$ POIs (inside locked bbox $[15.95, 107.95, 16.20, 108.35]$).
- **Da Nang Outside MVP Core:** $4$ POIs south of $15.95^\circ\text{N}$ in Điện Bàn / Quảng Nam (`TASY STUDIO`, `Khu tưởng niệm Hà My`, `Đài tưởng niệm thảm sát Hà My`, `Mini-Golf Hoi An`), preserved in DB and history but excluded from `REC-A-CORE-V2`.
- **Mỹ Khê Beach Relation:** relation/19000664 (Lat 16.07561, Lon 108.254735) is inside bbox and verified as a core Da Nang POI.

---

## 5. Post-Import Coordinate Consistency Audit

Following database persistence, spatial coordinates between `places` and `place_sources(osm)` were compared across all 293 canonical Da Nang POIs:
- **Count Audited:** 293
- **Median Drift:** 0.0000 m
- **95th Percentile Drift:** 0.0000 m
- **Maximum Drift:** 0.0000 m
- **Drift > 5m:** 0
- **Drift > 20m:** 0
- **Drift > 100m:** 0
- **Status:** PASS (100% spatial consistency between places and canonical OSM sources).
