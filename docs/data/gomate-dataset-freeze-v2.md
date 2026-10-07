# GoMate Dataset Freeze Specification (v2.0.0)

**Thesis Week:** W3 Closure → Data Scope Normalization  
**Task:** MVP-SCOPE-01  
**Freeze Date:** 2026-10-07  
**Branch:** `feature/mvp-three-city-freeze-v2`  
**Base Commit:** `b661c6b`  
**Parent Release:** Dataset Freeze V1 (`dataset-freeze-v1.yaml`, SHA-256 locked)  

---

## 1. Executive Summary & Scope

Dataset Freeze V2 expands the official GoMate Research and Product MVP scope from two destinations (Hanoi + Ha Long) to three destinations: **Hanoi + Da Nang + Ha Long**. 

Freeze V2 locks:
1. All canonical verified POIs for the three MVP destinations (`REC-A-CORE-V2`, N = 626).
2. The secondary exploratory research corpus (Hoi An, Hue, Nha Trang, N = 133).
3. The factual RAG knowledge corpus (N = 1,223 documents: 759 OSM place documents + 464 pinned Wikivoyage chunks).
4. All associated raw, processed, and curated query, geometry, and cross-check artifacts under cryptographic SHA-256 manifests.

---

## 2. Locked Database & Evaluation State

| Metric / Evaluation Scope | Freeze V1 Baseline | Freeze V2 Locked Value | Delta / Notes |
| :--- | :--- | :--- | :--- |
| **Total Places in DB** | 703 | **882** | +179 curated Da Nang POIs. |
| **Total Verified OSM Sources** | 580 | **759** | +179 verified OSM sources. |
| **Hà Nội Verified POIs** | 145 | **145** | 100% frozen and preserved from V1. |
| **Hạ Long Verified POIs** | 188 | **188** | 100% frozen and preserved from V1. |
| **Đà Nẵng Verified POIs** | 114 | **293** | +179 curated new POIs, 109 updated, 5 unchanged. |
| **`REC-A-CORE-V2` Total** | 333 (2 cities) | **626 (3 cities)** | Primary offline recommender evaluation universe. |
| **Secondary Research POIs** | 247 | **133** | Hoi An (50), Hue (50), Nha Trang (33). Excluded from 3-city metrics. |
| **Auxiliary Overture Sources** | 89 | **247** | Dual-source verified auxiliary records. |
| **Total RAG Documents** | 1,044 | **1,223** | +179 new Da Nang OSM knowledge chunks. |
| **Wikivoyage Chunks** | 464 | **464** | Pinned and 100% byte-for-byte identical. |
| **Places with Non-Null Rating** | 0 | **0** | Strict invariant: zero fabricated ratings. |
| **Places with Fake Reviews** | 0 | **0** | Strict invariant: zero fake reviews. |

---

## 3. Cryptographic Artifact Manifest (Freeze V2)

The authoritative checksum manifest is stored at [`data/manifests/dataset-freeze-v2.sha256`](file:///d:/Do_an/wanderai/data/manifests/dataset-freeze-v2.sha256).

### 3.1. Da Nang V2 Artifacts
| Artifact Path | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- |
| `data/queries/osm/danang_v2.overpassql` | 2,010 | `0c7e57898f5c7c0f16f3fe72605eb80ae32488a0b0d3fb0b3558f62c0fc4fc86` |
| `data/raw/osm/danang_2026-10-07_v2.json` | 1,016,599 | `f73b49124e5a09a834d5381febf3f5c5bcc5f5d6e343ef85d0650e3996cbcb47` |
| `data/raw/osm/danang_collection_metadata_2026-10-07_v2.json` | 564 | `21e1c4435115e5728a3070499e71ec26a8d7904018b76c8cba799d54e532b274` |
| `data/processed/osm/danang_normalized_v2.json` | 2,142,724 | `950a2b120ae3791a823ee9caae412d2746cba7b16548cfa0b32fbbeeaaebeaa1` |
| `data/processed/osm/danang_normalization_quality_stats_v2.json` | 1,236 | `a146fac815af0007fe1f787f71b9cf3e2cf44026dd6146eaebfc6da62a8c0d9c` |
| `data/curated/overture/danang_overture_crosscheck_v2.json` | 814,936 | `c1e7d47c62e7845dc72f88cf50fc23971948ae1537ae55ba2e7eebcbca1fc357` |
| `data/curated/overture/danang_overture_crosscheck_summary_v2.json` | 396 | `439c6a587508859de674a2752b57fa2b694b29bb86f9ca54db4d3f3f278ebdd9` |
| `data/manifests/danang_coordinate_drift_stats_v2.json` | 158 | `8cefe81512e4aa06114a8dbcc94bfbe03f71c4c15330ce4f62bf9fba4d3cbca0` |
| `data/manifests/db_import_plan_danang_v2.json` | 403,075 | `2e52d58e3480c97e1481b7e0bb0f8ec8a0cbe43b46955a8286a524a875a6be46` |
| `data/curated/gomate_places_freeze_v2.json` | 1,058,734 | `2e4f95e7ec576d15b02ec3b749d2906eb4cc96cba8c227f2f11eb1cfc12f205c` |

### 3.2. Freeze V1 Immutability Audit
All 23 original Freeze V1 artifacts recorded in `data/manifests/dataset-freeze-v1.sha256` were audited via SHA-256 verification and confirmed 100% byte-for-byte identical.
