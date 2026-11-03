# W07-B1B — Targeted POI Knowledge Acquisition Report

## 1. Authority & Executive Summary

- **Task ID:** `W07-B1B`
- **Accepted Upstream Gate:** `W07-B1-FIX-01B-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Authoritative Base (`develop`):** `324163636cedc8391c07cf2deca37d907745bd14`
- **Upstream Statuses:** `W07_B1_FIX_01B_STATUS = CLOSED`, `PDG_001_STATUS = CLOSED`
- **Primary Strategy:** `EVIDENCE_GROUNDED_POI_KNOWLEDGE` (`PRIMARY_W07_CORPUS = OPEN_AND_OFFICIAL_POI_KNOWLEDGE`)
- **Governance Invariants:**
  - `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION = true`
  - `OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`
  - `GOOGLE_MAPS_ROLE = RUNTIME_ENRICHMENT_ONLY`
  - `SOCIAL_PLATFORM_ROLE = DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS`
- **Readiness Decision:** **`W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2 = true`**

## 2. Candidate Discovery vs Primary Ingestion (`w07_b1b_source_decisions_v1.json`)

Every candidate source was evaluated through the two-gate rule (`CANONICAL_MAPPING_OK` and `REUSE_STATUS_ALLOWED`) plus content utility (`CONTENT_UTILITY_OK`):

| Metric | Value |
|---|---|
| Total Candidate Sources Evaluated | `132` |
| `ACCEPT_PRIMARY_CORPUS` (`OPEN_REUSABLE`) | `101` |
| `REFERENCE_ONLY` (`Tier A`/`Tier B` official websites without open redistribution license) | `16` |
| `ACCEPT_RESTRICTED_RESEARCH_ONLY` | `0` |
| `REJECT` (`MAPPING_REVIEW_REQUIRED` or `LOW_INFORMATION`) | `15` |
| `EXACT_MAPPED` Candidates | `119` |
| `MAPPING_REVIEW_REQUIRED` Candidates | `13` |
| Accepted Primary Corpus Documents (`evidence_unit_count`) | `101` |
| Accepted Independent Source Lineages (`independent_source_lineage_count`) | `82` |

### Accepted Primary Documents by Source Type & License (`poi_knowledge_acquired_v1.jsonl`)

| Source Type | Accepted Documents | Independent Lineages | License / Usage Class | Content Utility |
|---|---|---|---|---|
| `overture_places_parquet` | `26` | `26` | `CDLA-Permissive-2.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikipedia_article` | `26` | `25` | `CC-BY-SA-4.0` | `USEFUL_NARRATIVE` |
| `wikidata_entity` | `29` | `29` | `CC0-1.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikivoyage_poi_listing` | `20` | `2` (`wikivoyage:en:Da_Nang`, `wikivoyage:en:Hanoi`) | `CC-BY-SA-3.0` | `USEFUL_NARRATIVE` |
| **Total Acquired in B1B** | **`101`** | **`82`** | **`100% OPEN_REUSABLE`** | **`46` Narrative + `55` Structured** |

## 3. Frozen 60-POI Coverage Before vs After W07-B1B

| Coverage Dimension | Before B1B (`FIX-01B` Baseline) | After B1B (`FIX-01B` + `B1B`) | Delta |
|---|---|---|---|
| POIs with Primary Eligible Evidence | `60 / 60` (`100.0%`) | `60 / 60` (`100.0%`) | `0` |
| POIs with RAG-Candidate Evidence (`RAG_CANDIDATE_ELIGIBLE`) | `40 / 60` (`66.67%`) | **`52 / 60` (`86.67%`)** | **`+12`** |
| POIs with `>=2` Independent Eligible Lineages | `0 / 60` (`0.00%`) | **`45 / 60` (`75.00%`)** | **`+45`** |
| POIs with Narrative Evidence (`USEFUL_NARRATIVE`) | `0 / 60` (`0.00%`) | **`32 / 60` (`53.33%`)** | **`+32`** |
| POIs with Useful Structured Evidence (`USEFUL_STRUCTURED_FACTS`) | `40 / 60` (`66.67%`) | **`50 / 60` (`83.33%`)** | **`+10`** |
| POIs with Both Structured & Narrative Evidence | `0 / 60` (`0.00%`) | **`30 / 60` (`50.00%`)** | **`+30`** |

### Priority Distribution Shift (`P0 -> P1 -> P2 -> P3`)

| Priority Band | Definition | Before B1B | After B1B |
|---|---|---|---|
| `P0` | `0` RAG-eligible evidence units (`NO_RAG_ELIGIBLE_EVIDENCE`) | `20` | **`8`** (`12` closed: `7` Hạ Long, `5` Đà Nẵng) |
| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`7`** (`2` Hà Nội, `3` Đà Nẵng, `2` Hạ Long) |
| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`15`** (`2` Hà Nội, `5` Đà Nẵng, `8` Hạ Long) |
| `P3` | `>=2` RAG-eligible lineages with BOTH structured & narrative evidence | `0` | **`30`** (`14` Hà Nội, `12` Đà Nẵng, `4` Hạ Long) |

### Coverage by City

| City | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both Structured & Narrative | Post-B1B Priorities (`P0/P1/P2/P3`) |
|---|---|---|---|---|---|---|---|
| **Hà Nội** | `20` | **`18 / 20` (`90.0%`)** | `16 / 20` (`80.0%`) | `14 / 20` (`70.0%`) | `18 / 20` (`90.0%`) | `14 / 20` (`70.0%`) | `2 / 2 / 2 / 14` |
| **Đà Nẵng** | `20` | **`20 / 20` (`100.0%`)** | `17 / 20` (`85.0%`) | `12 / 20` (`60.0%`) | `20 / 20` (`100.0%`) | `12 / 20` (`60.0%`) | `0 / 3 / 5 / 12` |
| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `12 / 20` (`60.0%`) | `6 / 20` (`30.0%`) | `12 / 20` (`60.0%`) | `4 / 20` (`20.0%`) | `6 / 2 / 8 / 4` |
| **Total** | **`60`** | **`52 / 60` (`86.7%`)** | **`45 / 60` (`75.0%`)** | **`32 / 60` (`53.3%`)** | **`50 / 60` (`83.3%`)** | **`30 / 60` (`50.0%`)** | **`8 / 7 / 15 / 30`** |

### Coverage by Category Group

| Category Group | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both |
|---|---|---|---|---|---|---|
| `attractions_culture` | `20` | `19 / 20` | `17 / 20` | `17 / 20` | `17 / 20` | `15 / 20` |
| `restaurants_cafes_markets` | `22` | `19 / 22` | `16 / 22` | `5 / 22` | `19 / 22` | `5 / 22` |
| `nature_beach` | `9` | `6 / 9` | `6 / 9` | `6 / 9` | `6 / 9` | `6 / 9` |
| `hotels` | `6` | `6 / 6` | `6 / 6` | `3 / 6` | `6 / 6` | `3 / 6` |
| `other_tourism` | `3` | `2 / 3` | `2 / 3` | `2 / 3` | `2 / 3` | `2 / 3` |

## 4. Remaining Gap Reasons & Honest Governance Boundaries

- **Remaining `P0` (`8` POIs: `6` Hạ Long, `0` Đà Nẵng, `2` Hà Nội):**
  - `0931b06b-4563-4af0-a3a4-75f1ad8392ee` (`Vườn hoa`, Hạ Long), `6215446b-2fdd-4014-aacf-23de6e45e264` (`Chợ Hạ Long II`, Hạ Long), `708ee182-c879-477c-b920-516e2c99b0a6` (`Công viên Lán Bè`, Hạ Long), `77af14b6-85ac-4c91-873a-e7da27d555f4` (`Hang Luồn Cave Entrance`, Hạ Long), `8fe33554-7a07-4eb2-870f-8af643d8c728` (`Vườn hoa Thị trấn Trới`, Hạ Long), `b57b3f7d-9704-44b0-8139-19bea1998391` (`Sữa chua trân châu Hạ Long cơ sở 00`, Hạ Long), `4146f2b7-8289-4309-b7e6-60ba7de3470e` (`Cà Phê Nola`, Hà Nội), `b0641225-0f38-4bcc-9f4c-34f65fa50d45` (`Cửa Hàng Bánh Tôm Hồ Tây`, Hà Nội).
  - These 8 hyper-local parks, municipal markets, and cafes have no open-licensed (`OPEN_REUSABLE`) entity-specific article on Wikipedia/Wikivoyage/Wikidata and no `AUTO_LINK_VERIFIED` Overture record (`Cà Phê Nola`'s Overture candidate `Cà Phê Lâm` and `Cửa Hàng Bánh Tôm Hồ Tây`'s dish-level Wikipedia article `Q10742230` were both rejected under Section 10).
- **External Activity & Zero-Violation Counters:**
  - `WEB_SOURCE_PAGES_CHECKED = 79`
  - `WEB_DOCUMENTS_DOWNLOADED = 56`
  - `OPEN_REUSABLE_DOCUMENTS_ACCEPTED = 101`
  - `REFERENCE_ONLY_SOURCES = 16`
  - `RESEARCH_RESTRICTED_SOURCES = 0`
  - `REJECTED_SOURCES = 15`
  - `PAID_DATA_API_USED = false`
  - `NEW_SOCIAL_COLLECTION = 0`
  - `NEW_GOOGLE_MAPS_REVIEW_COLLECTION = 0`
  - `NEW_LLM_PROVIDER_CALLS = 0`

## 5. Artifact Hashes

- `data/evaluation/w07/w07_b1b_source_decisions_v1.json`:
  - Internal `artifact_sha256`: `0eafb594afcffe92c09d244e49153a268749f9a174981403d1c4d541d26e16a5`
  - File LF SHA256: `a43ee28bfa2064aadabe69a6dc84cbad4a61cd955eea2e065fa2c34b2d137b17`
- `data/curated/w07/poi_knowledge_acquired_v1.jsonl`:
  - File LF SHA256: `d8e925f94208fc0a2cb3edc01baa658bb10ce967c26745aeab6dab8d2f39875f`
- `data/evaluation/w07/w07_b1b_acquisition_summary_v1.json`:
  - Internal `artifact_sha256`: `9442b0868a58d277bf5b968755ea4e5923e5b5eac345efcf2019e1e2e0ec86d6`
  - File LF SHA256: `8b973a04ca63855c92e5d1ec792407abbeac2f4c72267809e649a3481d3fe823`
