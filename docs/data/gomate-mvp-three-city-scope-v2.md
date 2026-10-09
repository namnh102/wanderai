# GoMate Three-City MVP Expansion & Scope Specification (v2)

**Thesis Week:** W3 Closure → Data Scope Normalization  
**Task:** MVP-SCOPE-01  
**Branch:** `feature/mvp-three-city-freeze-v2`  
**Base Commit:** `b661c6b`  

---

## 1. Executive Summary & Objective

In accordance with thesis milestones, the official GoMate Product MVP scope expands from two initial destinations (**Hanoi** + **Ha Long**) to three primary destinations:
$$\text{GoMate Three MVP Destinations} = \{\text{Hà Nội, Đà Nẵng, Hạ Long}\}$$

This expansion brings Da Nang POI data to the exact same freshness, provenance, taxonomy (Ratified Taxonomy V1.1), and reproducibility standards achieved in Dataset Freeze V1, while maintaining 100% byte-for-byte immutability of Freeze V1.

---

## 2. Terminology & Geographic Boundaries

Official documentation and recommender evaluation strictly use the terminology **"three MVP destinations"** (or **"three MVP cities"**), avoiding ambiguous terms such as "three provinces".

| MVP Destination | Destination Slug | Latitude Range | Longitude Range | Geographic Definition & Key Assets |
| :--- | :--- | :--- | :--- | :--- |
| **Hà Nội** | `ha-noi` | `[20.95, 21.15]` | `[105.75, 105.95]` | Urban historic core, Old Quarter, Hoan Kiem, Ba Dinh, Tay Ho. |
| **Đà Nẵng** | `da-nang` | `[15.95, 16.20]` | `[107.95, 108.35]` | Tourism-core municipality: My Khe coastal zone, Son Tra Peninsula, Ba Na Hills corridor, Marble Mountains, Han River bridges. Strictly excludes Hoi An. |
| **Hạ Long** | `ha-long` | `[20.85, 21.05]` | `[106.95, 107.25]` | Coastal bay & islands: Bai Chay, Tuan Chau, Ha Long City, marine grottos. |

---

## 3. REC-A-CORE-V2 Item Universe Specification

To ensure rigorous offline evaluation of the GoMate hybrid recommender (REC-A) in Weeks 4 and 5, Dataset Freeze V2 defines two distinct evaluation scopes derived from item-level spatial and destination membership:

### 3.1. Primary Thesis & Product MVP Universe: `REC-A-CORE-V2`
`REC-A-CORE-V2` encompasses all canonical verified tourism POIs belonging to the three MVP destinations satisfying the locked spatial bounding boxes:
- **Hà Nội:** 145 canonical verified POIs (from Freeze V1, preserved unchanged).
- **Hạ Long:** 188 canonical verified POIs (from Freeze V1, preserved unchanged).
- **Đà Nẵng (Primary Core):** 289 canonical verified POIs (110 baseline POIs inside locked bbox $[15.95, 107.95, 16.20, 108.35]$ + 179 fresh curated POIs; strictly excludes 4 baseline POIs south of $15.95^\circ\text{N}$).
$$\text{REC-A-CORE-V2 Total} = 145 + 188 + 289 = \mathbf{622} \text{ canonical POIs}$$

### 3.2. Secondary Research Corpus (Exploratory Generalization)
For broader cross-regional transfer learning and cold-start generalization analysis, verified POIs outside the three-city primary core remain preserved in PostgreSQL and `gomate_places_freeze_v2.json` (`is_rec_a_core_v2 = false`):
- **Hội An:** 50 verified POIs.
- **Huế:** 50 verified POIs.
- **Nha Trang:** 33 verified POIs.
- **Đà Nẵng / Điện Bàn (Outside MVP Core):** 4 verified POIs located south of $15.95^\circ\text{N}$ (`TASY STUDIO`, `Khu tưởng niệm Hà My`, `Đài tưởng niệm thảm sát Hà My`, `Mini-Golf Hoi An`).
$$\text{Secondary Research Total} = 50 + 50 + 33 + 4 = \mathbf{137} \text{ POIs}$$
$$\text{Total Verified Research Places} = 622 + 137 = \mathbf{759} \text{ POIs} \equiv 580 \text{ (Freeze V1)} + 179 \text{ (New Da Nang)}$$

These 137 secondary POIs are strictly quarantined from primary three-city recommendation benchmark metrics.

### 3.3. Authoritative Recommender Evaluation Metric Contract
Offline recommendation benchmarks on `REC-A-CORE-V2` must evaluate and report the complete, ratified thesis primary metrics suite:
1. **$\text{NDCG@10}$:** Normalized Discounted Cumulative Gain at Rank 10 (primary ranking quality).
2. **$\text{Recall@10}$:** Top-10 relevant item retrieval coverage.
3. **$\text{Precision@10}$:** Top-10 recommendation precision.
4. **$\text{HitRate@10}$:** Proportion of evaluation instances with at least 1 hit in Top 10.
5. **$\text{Coverage@10}$:** Catalog item coverage ratio across the 622-item universe.
6. **$\text{Diversity@10}$:** Intra-list diversity across Taxonomy V1.1 categories.

*Note on MAP:* Mean Average Precision ($\text{MAP}$) is classified as **OPTIONAL / EXPLORATORY** only; it must not replace or alter the primary 6-metric contract.

---

## 4. WP-PROF-01 Preference Contract Compatibility

All 622 primary canonical POIs map directly into the 7 ratified user preference dimensions established in WP-PROF-01:
1. `food_cuisine` $\rightarrow$ `FOOD_BEVERAGE` (restaurant_dining, seafood_dining, street_food_market)
2. `culture_history` $\rightarrow$ `CULTURE_HERITAGE` (museum_gallery, historic_monument, religious_temple)
3. `nature_outdoor` $\rightarrow$ `NATURE_SCENERY` (viewpoint_scenic, park_garden, cave_grotto)
4. `coffee_culture` $\rightarrow$ `FOOD_BEVERAGE` (cafe_tea)
5. `beach_island` $\rightarrow$ `NATURE_SCENERY` (beach_coastal, island_landmark)
6. `shopping_local` $\rightarrow$ `SHOPPING_COMMERCE` (traditional_market, shopping_mall)
7. `nightlife_entertainment` $\rightarrow$ `ATTRACTIONS_LEISURE` (nightlife_entertainment, theme_park_leisure)

---

## 5. Dataset Freeze V1 Immutability Verification

Freeze V2 is completely isolated:
- `data/manifests/dataset-freeze-v1.yaml` (100% byte-for-byte identical).
- `data/manifests/dataset-freeze-v1.sha256` (all 23 checksums match).
- Zero mutations occurred on Hanoi (145) or Ha Long (188) records.
