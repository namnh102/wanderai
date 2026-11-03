# W07-B1A — Existing POI Knowledge Corpus Audit

## 1. Authority & Scope

- **Task ID:** `W07-B1A-EXISTING-POI-KNOWLEDGE-CORPUS-AUDIT`
- **Version:** `1.0.0`
- **Authoritative Base:** `develop@14ce20793c74cfa711902aa97a6ebe1cad810410`
- **Previous Accepted Gate:** `W07-B0-POSTMERGE-CHATGPT-AUDIT = PASS`
- **W07-B0 Status:** `CLOSED`
- **Primary Strategy:** `EVIDENCE_GROUNDED_POI_KNOWLEDGE` (`PRIMARY_W07_CORPUS = OPEN_AND_OFFICIAL_POI_KNOWLEDGE`)
- **Next Gate:** `W07-B1A-EXISTING-POI-KNOWLEDGE-AUDIT-CHATGPT-AUDIT`
- **Frozen 60-POI Target Manifest SHA256:** `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`
- **Frozen W07-B0 Amendment SHA256:** `365b00607737f01f02753595f5ce65092e2622bfbe3a8bb4ed20e464daf7a12f`

## 2. Verified Repository Inventory & Source Lineage Counting

- `NON_REVIEW_RAG_EVIDENCE_UNITS_EXISTING`: `1223` (`OSM_METADATA_UNITS = 759` + `WIKIVOYAGE_DESTINATION_CHUNKS = 464`)
- `VERIFIED_OSM_POIS`: `759`
- `REC_A_CORE_3_CITY_POIS`: `622`
- `OVERTURE_LINKED_POIS`: `247` (stored in `place_sources`, not in the 1,223-unit `documents` table)
- `TOTAL_REPOSITORY_NON_REVIEW_UNITS_INCLUDING_OVERTURE`: `1470`
- **Independent Source Lineages in 1,223 RAG Documents:** `769` (`759` `osm:<type>/<id>` + `10` `wikivoyage:en:<page_slug>`)
- **Independent Source Lineages Including 247 Overture Links:** `1016` (`759` OSM + `10` Wikivoyage + `247` `overture:<gers_id>`)

## 3. Governance, Content-Utility Diagnostic & Ingestion Finding (`PDG-001`)

- **B0 Two-Gate Formula:** `PRIMARY_CORPUS_ELIGIBLE = CANONICAL_MAPPING_OK AND REUSE_STATUS_ALLOWED`
- **B1A RAG-Candidate Formula:** `RAG_CANDIDATE_ELIGIBLE = PRIMARY_CORPUS_ELIGIBLE AND CONTENT_UTILITY_OK`
- `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION`: `true`
- **Empirical OSM Rendered Length (60 Target POIs, unwrapped `raw_data.tags`):** min `114` chars (`17` words), median `221` chars (`31` words), max `478` chars (`73` words).
- **Critical Technical Finding (`PDG-001`):** In `gomate_places_freeze_v2.json`, 621/759 places (59/60 target POIs; all except Bãi biển Mỹ Khê) store OSM tags nested under `raw_data.tags`, whereas `apps/ai-service/app/rag/osm_documents.py` (`_tags()`) currently reads only flat top-level `raw_data` keys. Without unwrapping `raw_data.tags`, only `0/60` target POIs emit `FACT_FIELDS`; with `raw_data.tags` unwrapped, `40/60` target POIs contain `>=1` substantive factual attribute (`USEFUL_STRUCTURED_FACTS`), while `20/60` contain `0` factual attributes beyond name, category tag, and coordinates (`LOW_INFORMATION`).

## 4. Wikivoyage Audit (`464` Chunks Across `10` Lineages)

- **Total Chunks:** `464` across `10` English Wikivoyage articles (`source_tier = TIER_C`, `license = CC-BY-SA-3.0`, `reuse_storage_class = OPEN_REUSABLE`).
- **Deterministic Mapping to Frozen 60 POIs:** `0` (`WikivoyageIngester.ingest_pilot_pages()` sets `place_id = None` for all `464` chunks, and chunk text is not exported to git-tracked `data/`).
- **Classification:** `157` chunks (`Hanoi=86`, `Da Nang=57`, `Ha Long Bay=14`) are `CITY_CONTEXT_ONLY`; `307` chunks (`Vietnam=113` + 6 non-target cities) are `UNMAPPED_TO_FROZEN_POI`.

| Lineage ID | Article | Chunks | Target City | Mapping Status |
|---|---|---:|---|---|
| `wikivoyage:en:Vietnam` | Vietnam | 113 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Hanoi` | Hanoi | 86 | Hà Nội | `CITY_CONTEXT_ONLY` |
| `wikivoyage:en:Da_Nang` | Da Nang | 57 | Đà Nẵng | `CITY_CONTEXT_ONLY` |
| `wikivoyage:en:Hoi_An` | Hoi An | 44 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Hue` | Hue | 37 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Nha_Trang` | Nha Trang | 44 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Da_Lat` | Da Lat | 20 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Ha_Long_Bay` | Ha Long Bay | 14 | Hạ Long | `CITY_CONTEXT_ONLY` |
| `wikivoyage:en:Ninh_Binh` | Ninh Binh | 27 | — | `UNMAPPED_TO_FROZEN_POI` |
| `wikivoyage:en:Phu_Quoc` | Phu Quoc | 22 | — | `UNMAPPED_TO_FROZEN_POI` |

## 5. OSM & Overture Audit on the Frozen 60 POIs

- **OSM (`60/60` mapped, `TIER_C`, `ODbL-1.0`, `OPEN_REUSABLE`):** `40/60` `USEFUL_STRUCTURED_FACTS` (`RAG_CANDIDATE_ELIGIBLE = true`), `20/60` `LOW_INFORMATION` (`RAG_CANDIDATE_ELIGIBLE = false`).
- **OSM Field Coverage on 60 POIs:** `address=28`, `category_or_class=60`, `cuisine=8`, `description=1`, `email=2`, `fee=4`, `heritage=1`, `internet_access=4`, `opening_hours=18`, `operator=3`, `phone=16`, `religion=4`, `stars=2`, `website=16`, `website_or_contact_website_strict=15`, `wheelchair=7`, `wikidata=15`, `wikipedia=14`
- **Overture (`26/60` `AUTO_LINK`, `TIER_C`, `overture_theme=places`, `providers=meta,Overture`, `CDLA-Permissive-2.0`, `OPEN_REUSABLE`):** `7` Hà Nội, `10` Đà Nẵng, `9` Hạ Long. Committed Freeze v2 JSON stores only matching provenance (`CONTENT_UTILITY_STATUS = LOW_INFORMATION`, `RAG_CANDIDATE_ELIGIBLE = false`), while local git-ignored raw parquet holds `addresses=26`, `phones=22`, `websites=15`.
- **Overture Uncertain Candidates (`8/60` `MANUAL_REVIEW_CANDIDATE` -> `MAPPING_REVIEW_REQUIRED`):** Held as `CANONICAL_MAPPING_OK = false` (`REFERENCE_ONLY`), preventing false-positive joins (e.g. `Nhà thờ Lớn -> Nhà Thờ Họ Nguyễn Khắc`, `Cà Phê Nola -> Cà Phê Lâm`).

## 6. Coverage Metrics (Overall, Per City, Per Category, Per Source)

### 6.1 Overall & Per-City Coverage

| Metric | Overall (60) | Hà Nội (20) | Đà Nẵng (20) | Hạ Long (20) |
|---|---:|---:|---:|---:|
| `TARGET_POIS` | 60 | 20 | 20 | 20 |
| `POIS_WITH_ANY_EXISTING_EVIDENCE` | 60 | 20 | 20 | 20 |
| `POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE` | 60 | 20 | 20 | 20 |
| `POIS_WITH_RAG_CANDIDATE_EVIDENCE` | 40 | 18 | 15 | 7 |
| `POIS_WITH_1_INDEPENDENT_LINEAGE` | 34 | 13 | 10 | 11 |
| `POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES` | 26 | 7 | 10 | 9 |
| `POIS_WITH_1_RAG_ELIGIBLE_LINEAGE` | 40 | 18 | 15 | 7 |
| `POIS_WITH_2_PLUS_RAG_ELIGIBLE_LINEAGES` | 0 | 0 | 0 | 0 |
| `POIS_WITH_NARRATIVE_TEXT` | 0 | 0 | 0 | 0 |
| `POIS_WITH_STRUCTURED_METADATA` | 60 | 20 | 20 | 20 |
| `POIS_WITH_USEFUL_STRUCTURED_METADATA` | 40 | 18 | 15 | 7 |
| `POIS_WITH_BOTH_STRUCTURED_AND_NARRATIVE` | 0 | 0 | 0 | 0 |
| `P0_NO_RAG_ELIGIBLE_EVIDENCE` | 20 | 2 | 5 | 13 |
| `P1_SINGLE_INDEPENDENT_LINEAGE` | 19 | 11 | 7 | 1 |
| `P2_STRUCTURED_ONLY_NO_NARRATIVE` | 21 | 7 | 8 | 6 |
| `P3_PROVISIONAL_COVERAGE_MET` | 0 | 0 | 0 | 0 |

### 6.2 Coverage by Frozen Category Group

| Category Group | Target | Primary Eligible | RAG Candidate Eligible | 1 Lineage | >=2 Lineages | Narrative | Useful Structured | P0 | P1 | P2 | P3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `attractions_culture` | 21 | 21 | 15 | 17 | 4 | 0 | 15 | 6 | 12 | 3 | 0 |
| `restaurants_cafes_markets` | 21 | 21 | 15 | 6 | 15 | 0 | 15 | 6 | 2 | 13 | 0 |
| `hotels` | 6 | 6 | 4 | 0 | 6 | 0 | 4 | 2 | 0 | 4 | 0 |
| `nature_beach` | 9 | 9 | 4 | 8 | 1 | 0 | 4 | 5 | 3 | 1 | 0 |
| `other_tourism` | 3 | 3 | 2 | 3 | 0 | 0 | 2 | 1 | 2 | 0 | 0 |

## 7. Duplicate / Lineage Audit & Current B2 Readiness

- **759 OSM Records:** `759/759` unique OSM IDs, `759/759` unique content SHA-256 hashes (`0` exact duplicates).
- **247 Overture Links:** `247/247` unique GERS IDs (`0` duplicate GERS links).
- **464 Wikivoyage Chunks:** Split from `10` parent articles (`46.4` chunks/lineage average).
- **Multi-Source Entity Aliases:** `26/60` target POIs (`247/759` Freeze v2 POIs) represented in both OSM and Overture.
- **`CURRENT_LOCAL_CORPUS_READY_FOR_B2`:** `false`
  - Zero POI-mapped narrative documents (`POIS_WITH_NARRATIVE_TEXT = 0/60`); all 464 Wikivoyage chunks have `place_id = None` (`157` `CITY_CONTEXT_ONLY`, `307` `UNMAPPED_TO_FROZEN_POI`).
  - Hạ Long has only `7/20` POIs with useful structured OSM facts (`13/20` are `LOW_INFORMATION` with only name, category tag, and coordinates), failing the `>=10` POIs/city minimum.
  - Only `26/60` POIs (`7` Hà Nội, `10` Đà Nẵng, `9` Hạ Long) have `>=2` independent mapped lineages (`OSM` + `Overture AUTO_LINK`), and `0/60` have `>=2` `RAG_CANDIDATE_ELIGIBLE` document lineages.
  - Only `40` POI-mapped useful structured units exist against the `>=150` useful-chunk minimum.
  - Ingestion bug `PDG-001` in `apps/ai-service/app/rag/osm_documents.py`: `_tags()` reads flat `raw_data` keys without unwrapping `raw_data['tags']`, causing `59/60` target POIs (`621/759` Freeze v2 POIs) to drop nested OSM tags during chunk rendering unless unwrapped.

## 8. Frozen 60-POI Audit & B1B Acquisition Gap Matrix (`P0=20`, `P1=19`, `P2=21`, `P3=0`)

- **Priority Breakdown:** `P0 = 20` (no RAG-eligible evidence), `P1 = 19` (only 1 independent mapped lineage), `P2 = 21` (structured evidence only, 0 narrative evidence), `P3 = 0` (ready).

| Rank | City | Category | Name | OSM Facts | Overture Status | External Tags (`wd`/`wp`/`web`) | Lineages | RAG Eligible | Priority | Gap Reasons |
|---:|---|---|---|---:|---|---|---:|---|---|---|
| 1 | Hà Nội | `attractions_culture` | Lăng Chủ tịch Hồ Chí Minh | 5 | `UNMATCHED` | `wd:Q874234; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 2 | Hà Nội | `attractions_culture` | Hoàng thành Thăng Long | 5 | `UNMATCHED` | `wd:Q206219; wp:yes; web:yes` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,NEEDS_REUSE_EVIDENCE` |
| 3 | Hà Nội | `attractions_culture` | Nhà tù Hỏa Lò | 6 | `UNMATCHED` | `wd:Q1359941; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 4 | Hà Nội | `attractions_culture` | Đền Ngọc Sơn | 6 | `MAPPING_REVIEW_REQUIRED` | `wd:Q3517494; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 5 | Hà Nội | `attractions_culture` | Chùa Trấn Quốc | 4 | `MAPPING_REVIEW_REQUIRED` | `wd:Q864770; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 6 | Hà Nội | `attractions_culture` | Bảo tàng Dân tộc học Việt Nam | 9 | `AUTO_LINK_VERIFIED` | `wd:Q1048345; wp:yes; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 7 | Hà Nội | `attractions_culture` | Nhà thờ Lớn | 4 | `MAPPING_REVIEW_REQUIRED` | `wd:Q1923783; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 8 | Hà Nội | `restaurants_cafes_markets` | Sen Tây Hồ | 1 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 9 | Hà Nội | `restaurants_cafes_markets` | Quán Ăn Ngon - Phan Bội Châu | 5 | `MAPPING_REVIEW_REQUIRED` | `wd:-; wp:-; web:yes` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED,NEEDS_REUSE_EVIDENCE` |
| 10 | Hà Nội | `restaurants_cafes_markets` | Pho 10 | 5 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 11 | Hà Nội | `restaurants_cafes_markets` | Cửa Hàng Bánh Tôm Hồ Tây | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 12 | Hà Nội | `restaurants_cafes_markets` | Highlands Coffee | 2 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 13 | Hà Nội | `restaurants_cafes_markets` | Cà Phê Nola | 0 | `MAPPING_REVIEW_REQUIRED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 14 | Hà Nội | `restaurants_cafes_markets` | Cà Phê Kafa | 3 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 15 | Hà Nội | `hotels` | Sheraton Hanoi | 1 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 16 | Hà Nội | `hotels` | Somerset Grand Hanoi | 6 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 17 | Hà Nội | `nature_beach` | Công viên Thống Nhất | 4 | `UNMATCHED` | `wd:Q10752058; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 18 | Hà Nội | `nature_beach` | Công viên Thủ Lệ | 7 | `UNMATCHED` | `wd:Q944021; wp:yes; web:yes` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,NEEDS_REUSE_EVIDENCE` |
| 19 | Hà Nội | `nature_beach` | Công viên Lê-nin | 2 | `AUTO_LINK_VERIFIED` | `wd:Q10752053; wp:yes; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 20 | Hà Nội | `other_tourism` | Le Pub | 1 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 21 | Đà Nẵng | `attractions_culture` | Cầu Rồng | 3 | `MAPPING_REVIEW_REQUIRED` | `wd:Q5305270; wp:-; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 22 | Đà Nẵng | `attractions_culture` | Ngũ Hành Sơn | 3 | `UNMATCHED` | `wd:Q6755207; wp:yes; web:yes` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,NEEDS_REUSE_EVIDENCE` |
| 23 | Đà Nẵng | `attractions_culture` | Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng | 6 | `UNMATCHED` | `wd:Q6940790; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 24 | Đà Nẵng | `attractions_culture` | Chùa Linh Ứng | 1 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 25 | Đà Nẵng | `attractions_culture` | Cầu Sông Hàn | 0 | `MAPPING_REVIEW_REQUIRED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 26 | Đà Nẵng | `attractions_culture` | Bảo tàng Đà Nẵng | 4 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 27 | Đà Nẵng | `attractions_culture` | Chợ Cồn | 2 | `MAPPING_REVIEW_REQUIRED` | `wd:-; wp:-; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,MAPPING_REVIEW_REQUIRED` |
| 28 | Đà Nẵng | `restaurants_cafes_markets` | Bánh Xèo Bà Dưỡng | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 29 | Đà Nẵng | `restaurants_cafes_markets` | My Quang Bà Mua | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 30 | Đà Nẵng | `restaurants_cafes_markets` | Nhà hàng hải sản Bé Anh | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 31 | Đà Nẵng | `restaurants_cafes_markets` | Chợ Đêm Sơn Trà | 3 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 32 | Đà Nẵng | `restaurants_cafes_markets` | Chợ Bắc Mỹ An | 0 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 33 | Đà Nẵng | `restaurants_cafes_markets` | Vincom Plaza | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 34 | Đà Nẵng | `restaurants_cafes_markets` | Ca Phe 83 | 0 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 35 | Đà Nẵng | `hotels` | InterContinental Danang Sun Peninsula Resort | 3 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 36 | Đà Nẵng | `hotels` | Furama Resort | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 37 | Đà Nẵng | `nature_beach` | Bãi biển Mỹ Khê | 2 | `MISSING_IN_CROSSCHECK` | `wd:Q10796763; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 38 | Đà Nẵng | `nature_beach` | Bãi tắm Non Nước | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 39 | Đà Nẵng | `nature_beach` | Ban Co Peak | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 40 | Đà Nẵng | `other_tourism` | Sun World Bà Nà Hills | 1 | `UNMATCHED` | `wd:-; wp:-; web:yes` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE,NEEDS_REUSE_EVIDENCE` |
| 41 | Hạ Long | `attractions_culture` | Vịnh Hạ Long | 2 | `UNMATCHED` | `wd:Q190128; wp:yes; web:-` | 1 | `true` | **`P1`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 42 | Hạ Long | `attractions_culture` | Bảo tàng Quảng Ninh | 0 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 43 | Hạ Long | `attractions_culture` | Động Thiên Cung | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 44 | Hạ Long | `attractions_culture` | Hang Đầu Gỗ | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 45 | Hạ Long | `attractions_culture` | Hang Luồn Cave Entrance | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 46 | Hạ Long | `attractions_culture` | Hòn Đỉnh Hương | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 47 | Hạ Long | `attractions_culture` | Ha Long International Cruise Port | 1 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 48 | Hạ Long | `restaurants_cafes_markets` | Nhà hàng Hồng Hạnh 3 | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 49 | Hạ Long | `restaurants_cafes_markets` | Nhà hàng Ngọc Phương Nam 1 | 3 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 50 | Hạ Long | `restaurants_cafes_markets` | Nhà hàng Buffet Sen Á Đông | 4 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:yes` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_REUSE_EVIDENCE` |
| 51 | Hạ Long | `restaurants_cafes_markets` | Chợ Cái Dăm | 2 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 52 | Hạ Long | `restaurants_cafes_markets` | Chợ Hạ Long II | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 53 | Hạ Long | `restaurants_cafes_markets` | Sữa chua trân châu Hạ Long cơ sở 00 | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 54 | Hạ Long | `restaurants_cafes_markets` | Highlands Coffee | 3 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `true` | **`P2`** | `NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 55 | Hạ Long | `hotels` | Vinpearl Ha Long resort | 0 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 56 | Hạ Long | `hotels` | Novotel Ha Long | 0 | `AUTO_LINK_VERIFIED` | `wd:-; wp:-; web:-` | 2 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY` |
| 57 | Hạ Long | `nature_beach` | Công viên Lán Bè | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 58 | Hạ Long | `nature_beach` | Vườn hoa | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 59 | Hạ Long | `nature_beach` | Vườn hoa Thị trấn Trới | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |
| 60 | Hạ Long | `other_tourism` | Sunworld | 0 | `UNMATCHED` | `wd:-; wp:-; web:-` | 1 | `false` | **`P0`** | `NO_POI_SPECIFIC_KNOWLEDGE,NEEDS_NARRATIVE_SOURCE,STRUCTURED_ONLY,NEEDS_SECOND_INDEPENDENT_SOURCE` |

## 9. No-Collection Counters, Role Preservation & Upstream Immutability

- `NEW_WEB_DOCUMENT_DOWNLOADS`: `0`
- `NEW_SOCIAL_COLLECTION`: `0`
- `NEW_GOOGLE_MAPS_COLLECTION`: `0`
- `NEW_LLM_PROVIDER_CALLS`: `0`
- `NEW_EXTERNAL_API_CALLS_FOR_CORPUS`: `0`
- `SOCIAL_PLATFORM_ROLE`: `DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS` (`SOCIAL-FRESHNESS-01`)
- `GOOGLE_MAPS_ROLE`: `RUNTIME_ENRICHMENT_ONLY`
