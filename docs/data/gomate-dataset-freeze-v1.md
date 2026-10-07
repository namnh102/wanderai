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

Every artifact referenced in [`data/manifests/dataset-freeze-v1.yaml`](file:///d:/Do_an/wanderai/data/manifests/dataset-freeze-v1.yaml) and [`data/manifests/dataset-freeze-v1.sha256`](file:///d:/Do_an/wanderai/data/manifests/dataset-freeze-v1.sha256) is cryptographically locked:

| Relative File Path | Size (Bytes) | Category | Cryptographic SHA-256 Checksum |
| :--- | :---: | :---: | :--- |
| `data/queries/osm/hanoi_v1.overpassql` | 2,168 | Query | `677ac053d278d6e1bb7720098777e95bdaaf49f8604b34c1f41627a37ed4bb00` |
| `data/queries/osm/halong_v1.overpassql` | 2,058 | Query | `66db973efa5479a8f9f369c5e13784985cfbe299d5014bd15db28f323622051d` |
| `data/raw/osm/hanoi_2026-10-07.json` | 2,504,861 | Raw OSM | `469417955e76d9f4eab8eab11401f13405e2d38a7d46027101013db4b0e0e9ea` |
| `data/raw/osm/halong_2026-10-07.json` | 120,946 | Raw OSM | `de27ec3d3db00974c44725d01578c955d790a90bdc7da356d9098401fdb654f6` |
| `data/raw/osm/collection_metadata_2026-10-07.json` | 868 | Raw Meta | `7ee17315987643457128ec79cc9f1eb72a98bc29c5f1d860cb7fd0e872531b66` |
| `data/raw/overture/overture_halong_2026-09-23.1.parquet` | 1,762,323 | Overture | `b8946680034deb7bcfd77eeb9412ea88249cddf44c30680d12f246b01e59e811` |
| `data/raw/overture/overture_hanoi_2026-09-23.1.parquet` | 32,312,042 | Overture | `9ee7d9eadfa4ac29e6494e13df02e802da8f2c041de408085a79a2d5da8eddc7` |
| `data/processed/osm/hanoi_normalized_v1.json` | 3,363,782 | Processed | `a71fd59b8f0f741359dffb49fcda50fcc8fc9618a19b7e718ad903ca39c88bf3` |
| `data/processed/osm/halong_normalized_v1.json` | 134,817 | Processed | `35dd75a73023868739b6874b9879025984b39ab58fc0fb206517f2372634521a` |
| `data/processed/osm/normalization_quality_stats_2026-10-07.json` | 1,842 | Quality | `2ed161e45597156ff6518f8431952ea47e9ccf1ddad6fc53e6fe361320bbbfbb` |
| `data/curated/overture/halong_overture_crosscheck_v1.json` | 51,927 | Curated | `3267b1ee1bf38f76023057c395a0cb9171f7b3c5b3326a6cb6b8f232c8ae88e2` |
| `data/curated/overture/hanoi_overture_crosscheck_v1.json` | 1,228,881 | Curated | `454e8cc378c7f16e79d9aca280c7d294f16554c835434e06d65936e11cb50c6b` |
| `data/curated/overture/overture_crosscheck_summary_2026-10-07.json` | 442 | Curated | `68401a1945a594355fe892dcdd88f19b4a205aeb3f19fa80900e512a75ce7545` |
| `data/curated/gomate_places_freeze_v1.json` | 467,780 | Curated | `d687b08cd6f3ef2f1ea0bdeb41d5b2647f848add70ddfed5144d55fcb0b23d4b` |
| `data/research/preferences/synthetic_preferences_v1.jsonl` | 108,124 | Research | `f33af6cb91189b1b43d0a8a229c364fe41fab6f392250617a3d77d2b7824ff92` |
| `data/evaluation/synthetic/preferences_n300_seed42.json` | 114,874 | Research | `1e883266bf6b145de0b7debf02d4881fc2f5293c9cf693ed34cd01715f6ab21a` |
| `data/research/preferences/synthetic_preferences_distribution_v1.json` | 2,758 | Research | `4175db65e33e14b6c540bf57bc899e35a0d3c83f243abd4b32faef4c00ca01dd` |
| `data/restricted/vihorec/hotels.csv` | 27,214 | Benchmark | `64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16` |
| `data/restricted/vihorec/interactions.csv` | 776,686 | Benchmark | `6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb` |
| `data/restricted/vihorec/users.csv` | 109,476 | Benchmark | `02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3` |
| `data/restricted/vihorec/train.csv` | 196,724 | Benchmark | `781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e` |
| `data/restricted/vihorec/val.csv` | 18,229 | Benchmark | `dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948` |
| `data/restricted/vihorec/test.csv` | 18,217 | Benchmark | `eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc` |

---

## 4. Disaster Recovery & Rollback Evidence

Prior to the DATA-02 mutation, full database snapshot state was archived to [`data/manifests/pre_data02_rollback_state.json`](file:///d:/Do_an/wanderai/data/manifests/pre_data02_rollback_state.json) (`c1f0f517899ffab5a231797eb148d1c16810deb0596659ac9d655d3bf277b20e`), preserving all 357 original verified POI associations, primary keys, and timestamps.

---

## 5. Acceptance Gate Checklist

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
- [x] No Overture canonical ID replacement
- [x] Synthetic preferences $N = 300$ generated
- [x] Seed 42 deterministic reproducibility passed bit-for-bit
- [x] ViHoRec checksums passed
- [x] DB dry-run documented (`data/manifests/db_import_plan_v1.json`)
- [x] Local import preserves all prior 357 verified records
- [x] Ha Long OSM RAG documents generated (188 chunks embedded with MiniLM-L12-v2)
- [x] Wikivoyage pinned docs (464 chunks) 100% preserved
- [x] Dataset registry updated in PostgreSQL
- [x] `dataset-freeze-v1.yaml` manifest generated
- [x] `dataset-freeze-v1.sha256` generated
- [x] Zero Google dataset content
- [x] `schema.prisma` completely unchanged
- [x] Product feature code in `apps/` completely unchanged
- [x] No recommender training launched
- [x] No merge or git push executed
