# GoMate Dataset Freeze Specification & Manifest (Freeze V1)

**Release Identifier:** `dataset-freeze-v1`  
**Semantic Version:** `1.0.0`  
**Freeze Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Git Commit Baseline:** `871d890722c51a632b0a98cb32a1f1e83a767f11`  
**Task Reference:** TASK DATA-02 (Fresh POI Collection, Normalization & Dataset Freeze V1)  
**Governance Invariant:** All research artifacts and benchmarks are cryptographically locked. Mutable DB states are mirrored by immutable file artifacts.

---

## 1. Executive Summary

The **GoMate Dataset Freeze V1** establishes the official, reproducible data foundation for the thesis research and recommendation evaluation tracks (REC-A and REC-B).

It locks:
1. **MVP Geographic Tourism Corpus:** Hà Nội (145 verified POIs) and Hạ Long (188 verified POIs), resolving the previous Ha Long POI deficit.
2. **Deterministic RAG Knowledge Corpus:** 1,044 vector-indexed documents (580 OSM place documents embedded with `MiniLM-L12-v2` + 464 pinned Wikivoyage chunks).
3. **Deterministic Synthetic Preference Fixture:** $N = 300$ profiles generated from `seed = 42` for offline recommender evaluation (REC-A).
4. **ViHoRec Collaborative Filtering Benchmark:** 17,911 interactions across 6,822 users and 560 hotels (REC-B benchmark, bit-exact verified).
5. **Secondary Overture Places Cross-Check:** Release `2026-09-23.1` (Schema `v2.0.0`) with 89 high-confidence auxiliary provenance links.

---

## 2. Post-Freeze Database State

| Table / Metric | Baseline Before DATA-02 | State After DATA-02 Freeze | Net Change | Governance Note |
| :--- | :---: | :---: | :---: | :--- |
| **Total Places (`places`)** | 480 | **703** | +223 | +188 Ha Long, +35 Hanoi verified tourism POIs |
| **Verified OSM Sources (`place_sources`)** | 357 | **580** | +223 | 100% traceable to upstream OpenStreetMap |
| **Auxiliary Overture Sources** | 0 | **89** | +89 | Secondary provenance only (CDLA / Apache / CC0) |
| **Places with Non-Null Rating** | 0 | **0** | 0 | **STRICT INVARIANT: ZERO FABRICATED RATINGS** |
| **RAG Documents (`documents`)** | 821 | **1,044** | +223 | 580 OSM docs + 464 pinned Wikivoyage chunks |
| **Wikivoyage Chunks** | 464 | **464** | 0 | **100% UNTOUCHED & PRESERVED** |
| **Dataset Registry Entries** | 6 | **9** | +3 | Hanoi, Ha Long, Synthetic Preferences added |

---

## 3. Cryptographic Manifest of Frozen Immutable Artifacts

Every artifact referenced in [`data/manifests/dataset-freeze-v1.yaml`](file:///d:/Do_an/wanderai/data/manifests/dataset-freeze-v1.yaml) and [`data/manifests/dataset-freeze-v1.sha256`](file:///d:/Do_an/wanderai/data/manifests/dataset-freeze-v1.sha256) is cryptographically locked and categorized into committed repository artifacts versus local restricted dependencies.

### 3.1 Committed Immutable Research Artifacts (17 Files)

| Relative File Path | Size (Bytes) | Category | Cryptographic SHA-256 Checksum |
| :--- | :---: | :---: | :--- |
| `data/queries/osm/hanoi_v1.overpassql` | 1,984 | Query | `677ac053d278d6e1bb7720098777e95bdaaf49f8604b34c1f41627a37ed4bb00` |
| `data/queries/osm/halong_v1.overpassql` | 1,853 | Query | `66db973efa5479a8f9f369c5e13784985cfbe299d5014bd15db28f323622051d` |
| `data/raw/osm/hanoi_2026-10-07.json` | 2,504,861 | Raw OSM | `469417955e76d9f4eab8eab11401f13405e2d38a7d46027101013db4b0e0e9ea` |
| `data/raw/osm/halong_2026-10-07.json` | 120,946 | Raw OSM | `de27ec3d3db00974c44725d01578c955d790a90bdc7da356d9098401fdb654f6` |
| `data/raw/osm/collection_metadata_2026-10-07.json` | 823 | Raw Meta | `7ee17315987643457128ec79cc9f1eb72a98bc29c5f1d860cb7fd0e872531b66` |
| `data/processed/osm/hanoi_normalized_v1.json` | 4,613,231 | Processed | `a71fd59b8f0f741359dffb49fcda50fcc8fc9618a19b7e718ad903ca39c88bf3` |
| `data/processed/osm/halong_normalized_v1.json` | 158,146 | Processed | `35dd75a73023868739b6874b9879025984b39ab58fc0fb206517f2372634521a` |
| `data/processed/osm/normalization_quality_stats_2026-10-07.json` | 2,109 | Quality | `2ed161e45597156ff6518f8431952ea47e9ccf1ddad6fc53e6fe361320bbbfbb` |
| `data/curated/overture/halong_overture_crosscheck_v1.json` | 63,014 | Curated | `3267b1ee1bf38f76023057c395a0cb9171f7b3c5b3326a6cb6b8f232c8ae88e2` |
| `data/curated/overture/hanoi_overture_crosscheck_v1.json` | 1,756,566 | Curated | `2f3477e774373ec8beb7cb24f778447ced323db57c40251ae2e3a528256161f5` |
| `data/curated/overture/overture_crosscheck_summary_2026-10-07.json` | 564 | Curated | `1c245d97b8e04fe9590466f5201f8c03e726e3ffc23131377a849c75a456f50c` |
| `data/curated/gomate_places_freeze_v1.json` | 661,993 | Curated | `d687b08cd6f3ef2f1ea0bdeb41d5b2647f848add70ddfed5144d55fcb0b23d4b` |
| `data/research/preferences/synthetic_preferences_v1.jsonl` | 102,937 | Research | `f33af6cb91189b1b43d0a8a229c364fe41fab6f392250617a3d77d2b7824ff92` |
| `data/evaluation/synthetic/preferences_n300_seed42.json` | 135,310 | Research | `1e883266bf6b145de0b7debf02d4881fc2f5293c9cf693ed34cd01715f6ab21a` |
| `data/research/preferences/synthetic_preferences_distribution_v1.json` | 3,271 | Research | `4175db65e33e14b6c540bf57bc899e35a0d3c83f243abd4b32faef4c00ca01dd` |
| `data/manifests/db_import_plan_v1.json` | 381,290 | Manifest | `18400ad20a221f4bed76c47845dec868137d4587b5c1d993af9c16f0ed8efb5e` |
| `data/manifests/pre_data02_rollback_state.json` | 337,909 | Manifest | `c1f0f517899ffab5a231797eb148d1c16810deb0596659ac9d655d3bf277b20e` |

### 3.2 Local Restricted Research Dependencies (6 Files, Git-Ignored)

The following files represent the official upstream ViHoRec 1.0.0 benchmark dataset. In accordance with GoMate data governance and open-source licensing compliance, these files are **strictly git-ignored** (via `data/restricted/.gitignore`), preventing unauthorized redistribution while maintaining cryptographic checksum integrity for thesis evaluation reproducibility.

| Relative File Path | Size (Bytes) | Category | Cryptographic SHA-256 Checksum | Governance Classification |
| :--- | :---: | :---: | :--- | :--- |
| `data/restricted/vihorec/hotels.csv` | 27,214 | Benchmark | `64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16` | LOCAL_RESTRICTED (Git-Ignored) |
| `data/restricted/vihorec/interactions.csv` | 776,686 | Benchmark | `6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb` | LOCAL_RESTRICTED (Git-Ignored) |
| `data/restricted/vihorec/users.csv` | 109,476 | Benchmark | `02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3` | LOCAL_RESTRICTED (Git-Ignored) |
| `data/restricted/vihorec/train.csv` | 196,724 | Benchmark | `781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e` | LOCAL_RESTRICTED (Git-Ignored) |
| `data/restricted/vihorec/val.csv` | 18,229 | Benchmark | `dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948` | LOCAL_RESTRICTED (Git-Ignored) |
| `data/restricted/vihorec/test.csv` | 18,217 | Benchmark | `eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc` | LOCAL_RESTRICTED (Git-Ignored) |

---

## 4. REC-A Recommender Item Universe Formal Lock

To ensure rigorous scientific validity in recommender benchmarking:

1. **Evaluation Item Universe ($I_{\text{REC-A}}$):**
   - Strictly locked to the **580 canonical verified places** contained in [`data/curated/gomate_places_freeze_v1.json`](file:///d:/Do_an/wanderai/data/curated/gomate_places_freeze_v1.json) and mirrored in the local PostgreSQL database (`places` table with verified OSM provenance in `place_sources`).
   - Distribution across destinations:
     - Hạ Long: 188 verified POIs
     - Hà Nội: 145 verified POIs
     - Đà Nẵng: 89 verified POIs
     - Hội An: 80 verified POIs
     - Nha Trang: 41 verified POIs
     - Huế: 37 verified POIs
     - **Total: 580 POIs**
2. **Distinction from Candidate Extraction Pool:**
   - The broader normalized OpenStreetMap extraction pool ($N = 5,077$ candidate POIs: 4,889 Hanoi + 188 Ha Long) documented in [`data/processed/osm/`](file:///d:/Do_an/wanderai/data/processed/osm/) constitutes an upstream candidate extraction pool for future expansions.
   - **It is NOT part of the evaluation item universe.** Recommender metrics for REC-A (NDCG@10, Precision@10, Recall@10, Coverage, Diversity) must rank and retrieve strictly from the 580 canonical verified places.

---

## 5. ViHoRec Git Tracking & Licensing Governance

1. **Git Isolation:**
   - `git ls-files data/restricted/vihorec` returns 0 entries.
   - `data/restricted/.gitignore` explicitly ignores `*.csv` and subdirectories.
2. **Offline Research Reproduction:**
   - Any external researcher replicating the REC-B track obtains the official ViHoRec release from the authors and places the files in `data/restricted/vihorec/`.
   - The automated script `python scripts/verify_vihorec_integrity.py` computes SHA-256 checksums and validates bit-for-bit equivalence against `data/manifests/dataset-freeze-v1.sha256`.

---

## 6. Disaster Recovery & Rollback Evidence

Prior to the DATA-02 mutation, full database snapshot state was archived to [`data/manifests/pre_data02_rollback_state.json`](file:///d:/Do_an/wanderai/data/manifests/pre_data02_rollback_state.json) (`c1f0f517899ffab5a231797eb148d1c16810deb0596659ac9d655d3bf277b20e`), preserving all 357 original verified POI associations, primary keys, and timestamps.

---

## 7. Acceptance Gate Checklist

- [x] Fresh Hanoi OSM raw snapshot exists (`data/raw/osm/hanoi_2026-10-07.json`)
- [x] Fresh Ha Long OSM raw snapshot exists (`data/raw/osm/halong_2026-10-07.json`)
- [x] `osm_base: 2026-10-07T09:52:02Z` recorded
- [x] Element versions/changesets/timestamps recorded
- [x] Raw snapshots immutable and checksummed
- [x] Taxonomy V1.1 applied
- [x] Quality + provenance override raw count
- [x] Ha Long verified POI corpus established (188 verified POIs)
- [x] No fabricated rating or review (`rating IS NULL`, `review_count = 0`)
- [x] Overture used as secondary cross-check only
- [x] Overture licensing tracked per provenance record (CDLA / Apache / CC0)
- [x] Strict Overture license resolution (unknown returns None; no hardcoded CDLA fallback)
- [x] All 89 DB Overture auxiliary records audited and confirmed
- [x] Canonical coordinate consistency audited across all 580 verified places (max drift < 0.08m, count > 5m = 0)
- [x] REC-A evaluation item universe locked to 580 verified POIs
- [x] ViHoRec local restricted dependency governance enforced (git-ignored, 0 tracked files)
- [x] Manifest DB state dynamically read from PostgreSQL with automated assertions
- [x] No Overture canonical ID replacement
- [x] Synthetic preferences $N = 300$ generated
- [x] Seed 42 deterministic reproducibility passed bit-for-bit
- [x] ViHoRec checksums passed
- [x] DB dry-run documented (`data/manifests/db_import_plan_v1.json`)
- [x] Local import preserves all prior 357 verified records
- [x] Ha Long OSM RAG documents generated (188 chunks embedded with MiniLM-L12-v2)
- [x] Wikivoyage pinned docs (464 chunks) 100% preserved (total RAG docs: 1,044)
- [x] Dataset registry updated in PostgreSQL
- [x] `dataset-freeze-v1.yaml` manifest generated
- [x] `dataset-freeze-v1.sha256` generated
- [x] Zero Google dataset content
- [x] `schema.prisma` completely unchanged
- [x] Product feature code in `apps/` completely unchanged
- [x] No recommender training launched
- [x] No merge or git push executed
