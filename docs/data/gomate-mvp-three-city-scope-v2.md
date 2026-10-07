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

To ensure rigorous offline evaluation of the GoMate hybrid recommender (REC-A) in Weeks 4 and 5, Dataset Freeze V2 defines two distinct evaluation scopes:

### 3.1. Primary Thesis & Product MVP Universe: `REC-A-CORE-V2`
`REC-A-CORE-V2` encompasses all canonical verified tourism POIs belonging to the three MVP destinations:
- **Hà Nội:** 145 canonical verified POIs (from Freeze V1, preserved unchanged).
- **Hạ Long:** 188 canonical verified POIs (from Freeze V1, preserved unchanged).
- **Đà Nẵng:** 293 canonical verified POIs (expanded and verified in Freeze V2).
$$\text{REC-A-CORE-V2 Total} = 145 + 188 + 293 = \mathbf{626} \text{ canonical POIs}$$

### 3.2. Secondary Research Corpus (Exploratory Generalization)
For broader cross-regional transfer learning and cold-start generalization analysis, existing verified POIs from secondary research destinations remain accessible in PostgreSQL and `gomate_places_freeze_v2.json`:
- **Hội An:** 50 verified POIs.
- **Huế:** 50 verified POIs.
- **Nha Trang:** 33 verified POIs.
$$\text{Secondary Research Total} = 50 + 50 + 33 = \mathbf{133} \text{ POIs}$$
$$\text{Total Verified Research Places} = 626 + 133 = \mathbf{759} \text{ POIs}$$

These 133 secondary POIs are strictly quarantined from primary three-city recommendation benchmark metrics (NDCG@10, HR@10).

---

## 4. WP-PROF-01 Preference Contract Compatibility

All 626 canonical POIs map directly into the 7 ratified user preference dimensions established in WP-PROF-01:
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
