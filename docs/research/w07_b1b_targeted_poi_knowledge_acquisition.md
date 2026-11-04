# W07-B1B — Targeted POI Knowledge Acquisition Report (Corrective 02)

## 1. Authority & Executive Summary

- **Task ID:** `W07-B1B` (`W07-B1B-CORRECTIVE-02`)
- **Accepted Upstream Gate:** `W07-B1-FIX-01B-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Current Gate Status:** `W07-B1B-CORRECTIVE-01-CORPUS-QUALITY-CHATGPT-AUDIT = HOLD-CORRECTIVE-02`
- **Next Gate:** `W07-B1B-CORRECTIVE-02-FACT-CONSISTENCY-CHATGPT-AUDIT`
- **Authoritative Base (`develop`):** `324163636cedc8391c07cf2deca37d907745bd14`
- **Artifact Snapshot Timestamp:** `2026-11-03T18:45:00Z`
- **Upstream Statuses:** `W07_B1_FIX_01B_STATUS = CLOSED`, `PDG_001_STATUS = CLOSED`
- **Primary Strategy:** `EVIDENCE_GROUNDED_POI_KNOWLEDGE` (`PRIMARY_W07_CORPUS = OPEN_AND_OFFICIAL_POI_KNOWLEDGE`)
- **Governance Invariants:**
  - `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION = true`
  - `OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`
  - `GOOGLE_MAPS_ROLE = RUNTIME_ENRICHMENT_ONLY`
  - `SOCIAL_PLATFORM_ROLE = DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS`
- **Readiness Decision:** **`W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2 = true`**

## 2. Corrective 02 Fact-Consistency & Temporal Provenance Repairs

1. **Confirmed Factual Conflicts Resolved (`FC-001` & `FC-002`):**
   - **`FC-001` (`f0d424bd-f722-540f-8964-5e6fd8875b56`, `Bảo tàng Dân tộc học Việt Nam`, Hà Nội — Overture GERS `e55bab3c-c110-4ba6-a005-5c43986a6095`):** Overture's address `"1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN"` conflicts with the canonical POI (`Đường Nguyễn Văn Huyên, Quan Hoa, Cầu Giấy, Hà Nội`), OSM `way/39954624`, Wikipedia (`đường Nguyễn Văn Huyên`), Wikivoyage (`Nguyen Van Huyen St`), and official site (`https://www.vme.org.vn/`). Because the Overture record's coordinates (`21.040176, 105.798732`, `4.1m` from canonical), category (`museum`), phone (`+84437562193`), and website (`http://www.vme.org.vn/`) are corroborated, the conflicting `address` field is suppressed from `raw_text` (`suppressed_conflicted_fields = ["address"]`).
   - **`FC-002` (`75a3fbd1-a24e-43c6-820a-72f95ebc05c0`, `Vinpearl Ha Long resort`, Hạ Long — Overture GERS `9ed3a2e3-60a3-4df0-acd8-83185f57a281`):** Overture's address `"439 P. Lê Lợi, Hạ Long, 180000, VN"` (a Hải Phòng street/postcode) conflicts with canonical coordinates (`20.941167, 107.0253612`), Wikidata `Q111402972` (`20.940934, 107.025632`), and official resort/tourism listings on Đảo Rều, Bãi Cháy. Because the Overture record's coordinates (`20.941068, 107.025318`, `11.7m` from canonical on Đảo Rều), category (`hotel`), and official website (`http://vinpearl.com/...`) are corroborated, the conflicting `address` field is suppressed from `raw_text` (`suppressed_conflicted_fields = ["address"]`).
2. **Full 26-Record Overture Fact-Consistency Audit (`130` Field Evaluations across 5 Fields):**
   - Audited `coordinates`, `address`, `category_taxonomy`, `phone`, and `website` across all `26` previously accepted Overture records (`68 CORROBORATED`, `16 CONFLICTED`, `16 UNVERIFIED`, `30 MISSING`).
   - **`23` Overture records retained (`ACCEPT_PRIMARY_CORPUS`)**: `12` clean records with `0` conflicts and `11` valid entities where conflicting fields (`address`, `phone`, or `website`) are suppressed from `raw_text`. Every retained Overture document has `>=1` non-conflicted substantive place attribute (`address`, `phone`, or `website`).
   - **`2` Overture records downgraded to `MAPPING_REVIEW_REQUIRED` (`REJECT`)**:
     - `5fc0994a-e578-4a25-b375-7f079e6dc3ba` (`Chùa Linh Ứng`, Đà Nẵng, GERS `b9ad130e-8f19-4dcb-92a7-638573a3f62d`, `FC-005`): Overture `names.primary = "Chùa Linh Ứng – Sơn Trà"` conflates Chùa Linh Ứng Non Nước (at Ngũ Hành Sơn) with Chùa Linh Ứng Bãi Bụt on Sơn Trà Peninsula 10.6 km away.
     - `c2afbb07-aaf9-47c1-9877-d17e64422066` (`Chợ Bắc Mỹ An`, Đà Nẵng, GERS `4d3dbac0-aae6-4960-8b89-d06c52fe21f5`, `FC-006`): Overture `names.primary = "Chợ Bắc Mỹ An Online"` (`confidence = 0.3150`, TikTok URL `https://www.tiktok.com/@bacmyan`) represents an online social vendor page with uncertain identity to the physical municipal market.
   - **`1` Overture record downgraded to `LOW_INFORMATION` (`REJECT`)**:
     - `96523873-1b85-4d2f-b85c-cb3f5593091b` (`Chợ Cái Dăm`, Hạ Long, GERS `9b6e3c9a-d263-4e5d-8ff7-7d7bddc1ffef`, `FC-007`): After suppressing conflicted `website` (`http://xdha.vn/`) and conflicted `category_taxonomy` (`fishmonger`), only self-referential `address = "Cái Dăm, Hạ Long, VN"` remains (`0` substantive place attributes beyond name/city).
3. **Additional Cross-Source Fact-Consistency & Template Parsing Repairs:**
   - **Wikidata `Q124453533` (`Động Thiên Cung`, `9a979427-a0bb-421d-b75f-2a6ee79b120b`):** Moved from `ACCEPT_PRIMARY_CORPUS` to `REJECT` (`MAPPING_REVIEW_REQUIRED`) because `Q124453533` has `P131 = Hoa Lư (Q131417547)` and `P625 = 20.215960, 105.914210` (a homonymous cave in Ninh Bình, 138.5 km from Hạ Long Bay).
   - **Wikidata `Q117325492` (`Sheraton Hanoi`, `5e92e89d-8524-4792-862a-6dfce0994862`):** Suppressed coarse `P625` (`21.020609, 105.849044`, 4.7 km from canonical/Overture/Wikivoyage Tây Hồ location).
   - **Wikivoyage `[[target|label]]` & `{UNESCO}` Template Normalization:** Normalized inner wiki-link pipes and `{UNESCO}` before splitting template parameters on `|`, restoring full narrative descriptions for `Hồ Chí Minh Mausoleum` and `Hanoi Citadel`.
4. **Four-Field Temporal Provenance Separation:**
   - Every candidate decision (`132`) and every accepted document (`97`) now separates:
     - `retrieved_at`: `2026-11-03T18:45:00Z` for live API-fetched Wikimedia sources; `UNKNOWN_HISTORICAL_RETRIEVAL_TIME` for pre-existing local Overture Parquet records; `NOT_FETCHED_REJECTED_AT_MAPPING_GATE` / `NOT_FETCHED_REFERENCE_ONLY_POINTER` for un-fetched records.
     - `source_published_or_updated_at`: upstream MediaWiki revision timestamp, Wikidata `modified` timestamp, or Overture release date `2026-09-23T00:00:00Z`.
     - `source_terms_checked_at`: `2026-11-03T18:45:00Z`, `NOT_INDEPENDENTLY_CHECKED` (for the 16 OSM website URLs), or `NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE`.
     - `artifact_snapshot_timestamp`: `2026-11-03T18:45:00Z`.

### 26-Record Overture Fact-Consistency Audit Table

| # | Canonical POI | Overture GERS | Conflict ID | Coordinates | Address | Category / Taxonomy | Phone | Website | Suppressed Fields | Post-Audit Status & Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `75a3fbd1` (Vinpearl Ha Long resort, Hạ Long) | `9ed3a2e3` | `FC-002` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `address` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 2 | `8f2b5a69` (Bảo tàng Quảng Ninh, Hạ Long) | `bd078edf` | `FC-008` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 3 | `9740c851` (Novotel Ha Long, Hạ Long) | `893209f5` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 4 | `065f8492` (Nhà hàng Buffet Sen Á Đông, Hạ Long) | `0772c46b` | `FC-009` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `phone` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 5 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1, Hạ Long) | `04dda4d2` | `FC-010` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `CONFLICTED` | `phone`, `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 6 | `85303289` (Highlands Coffee, Hạ Long) | `6039522b` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 7 | `871a6ee7` (Ha Long International Cruise Port, Hạ Long) | `527ebd9f` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 8 | `96523873` (Chợ Cái Dăm, Hạ Long) | `9b6e3c9a` | `FC-007` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `MISSING` | `CONFLICTED` | `category_taxonomy`, `website` | `EXACT_MAPPED` / `LOW_INFORMATION` -> **`REJECT`** |
| 9 | `b37d68ee` (Nhà hàng Hồng Hạnh 3, Hạ Long) | `92ed9717` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 10 | `8ebf0429` (Ca Phe 83, Đà Nẵng) | `1b27afcb` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 11 | `c2afbb07` (Chợ Bắc Mỹ An, Đà Nẵng) | `4d3dbac0` | `FC-006` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `MAPPING_REVIEW_REQUIRED` / `LOW_INFORMATION` -> **`REJECT`** |
| 12 | `4608034c` (InterContinental Danang Sun Peninsula Resort, Đà Nẵng) | `0d91068a` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 13 | `5fc0994a` (Chùa Linh Ứng, Đà Nẵng) | `b9ad130e` | `FC-005` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `MISSING` | `MISSING` | *(none)* | `MAPPING_REVIEW_REQUIRED` / `LOW_INFORMATION` -> **`REJECT`** |
| 14 | `61639da8` (My Quang Bà Mua, Đà Nẵng) | `da92232b` | `FC-003` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `address`, `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 15 | `62a874a9` (Bánh Xèo Bà Dưỡng, Đà Nẵng) | `c732f0d5` | `FC-011` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 16 | `7ff87c59` (Vincom Plaza, Đà Nẵng) | `67b0a6b0` | `FC-012` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `phone` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 17 | `9a2ca486` (Chợ Đêm Sơn Trà, Đà Nẵng) | `a310c792` | `FC-004` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | `address` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 18 | `a32ce1b4` (Furama Resort, Đà Nẵng) | `82f95e1f` | `FC-013` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 19 | `fd118580` (Nhà hàng hải sản Bé Anh, Đà Nẵng) | `df8dc91d` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 20 | `5350dd97` (Pho 10, Hà Nội) | `ff9a223f` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 21 | `5bd45eb7` (Highlands Coffee, Hà Nội) | `e8f37b82` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `MISSING` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 22 | `5e92e89d` (Sheraton Hanoi, Hà Nội) | `80ceecb4` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 23 | `9a96e0a0` (Somerset Grand Hanoi, Hà Nội) | `165cef5b` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 24 | `a2037ceb` (Công viên Lê-nin, Hà Nội) | `3421b671` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `MISSING` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 25 | `afb3793b` (Sen Tây Hồ, Hà Nội) | `e8077687` | `FC-014` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 26 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam, Hà Nội) | `e55bab3c` | `FC-001` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `address` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |

## 3. Candidate Discovery vs Primary Ingestion (`w07_b1b_source_decisions_v1.json`)

| Metric | Value |
|---|---|
| Total Candidate Sources Evaluated | `132` |
| `ACCEPT_PRIMARY_CORPUS` (`OPEN_REUSABLE`) | `97` |
| `REFERENCE_ONLY` (`URL_DISCOVERED_FROM_OSM_TAG`, `REUSE_PERMISSION_NOT_ESTABLISHED`) | `16` |
| `ACCEPT_RESTRICTED_RESEARCH_ONLY` | `0` |
| `REJECT` (`MAPPING_REVIEW_REQUIRED` or `LOW_INFORMATION`) | `19` |
| `EXACT_MAPPED` Candidates | `116` |
| `MAPPING_REVIEW_REQUIRED` Candidates | `16` |
| Accepted Primary Corpus Documents (`evidence_unit_count`) | `97` |
| Accepted Independent Source Lineages (`independent_source_lineage_count`) | `78` |

### Accepted Primary Documents by Source Type & License (`poi_knowledge_acquired_v1.jsonl`)

| Source Type | Accepted Documents | Independent Lineages | License / Usage Class | Content Utility |
|---|---|---|---|---|
| `overture_places_parquet` | `23` | `23` | `CDLA-Permissive-2.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikipedia_article` | `26` | `25` | `CC-BY-SA-4.0` | `USEFUL_NARRATIVE` |
| `wikidata_entity` | `28` | `28` | `CC0-1.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikivoyage_poi_listing` | `20` | `2` (`wikivoyage:en:Da_Nang`, `wikivoyage:en:Hanoi`) | `CC-BY-SA-3.0` | `USEFUL_NARRATIVE` |
| **Total Acquired in B1B** | **`97`** | **`78`** | **`100% OPEN_REUSABLE`** | **`46` Narrative + `51` Structured** |

## 4. Recomputed Frozen 60-POI Coverage Before vs After W07-B1B

| Coverage Dimension | Before B1B (`FIX-01B` Baseline) | After B1B (`FIX-01B` + `B1B` Corrective 02) | Delta |
|---|---|---|---|
| POIs with Primary Eligible Evidence | `60 / 60` (`100.0%`) | `60 / 60` (`100.0%`) | `0` |
| POIs with RAG-Candidate Evidence (`RAG_CANDIDATE_ELIGIBLE`) | `40 / 60` (`66.67%`) | **`51 / 60` (`85.00%`)** | **`+11`** |
| POIs with `>=2` Independent Eligible Lineages | `0 / 60` (`0.00%`) | **`42 / 60` (`70.00%`)** | **`+42`** |
| POIs with Narrative Evidence (`USEFUL_NARRATIVE`) | `0 / 60` (`0.00%`) | **`32 / 60` (`53.33%`)** | **`+32`** |
| POIs with Useful Structured Evidence (`USEFUL_STRUCTURED_FACTS`) | `40 / 60` (`66.67%`) | **`48 / 60` (`80.00%`)** | **`+8`** |
| POIs with Both Structured & Narrative Evidence | `0 / 60` (`0.00%`) | **`29 / 60` (`48.33%`)** | **`+29`** |

### Priority Distribution Shift (`P0 -> P1 -> P2 -> P3`)

| Priority Band | Definition | Before B1B | After B1B (Corrective 02) |
|---|---|---|---|
| `P0` | `0` RAG-eligible evidence units (`NO_RAG_ELIGIBLE_EVIDENCE`) | `20` | **`9`** (`11` closed) |
| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`9`** (`2` Hà Nội, `4` Đà Nẵng, `3` Hạ Long) |
| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`13`** (`2` Hà Nội, `4` Đà Nẵng, `7` Hạ Long) |
| `P3` | `>=2` RAG-eligible lineages with BOTH structured & narrative evidence | `0` | **`29`** (`14` Hà Nội, `12` Đà Nẵng, `3` Hạ Long) |

### Coverage by City

| City | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both Structured & Narrative | Post-B1B Priorities (`P0/P1/P2/P3`) |
|---|---|---|---|---|---|---|---|
| **Hà Nội** | `20` | **`18 / 20` (`90.0%`)** | `16 / 20` (`80.0%`) | `14 / 20` (`70.0%`) | `18 / 20` (`90.0%`) | `14 / 20` (`70.0%`) | `2 / 2 / 2 / 14` |
| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 4 / 3 / 12` |
| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `10 / 20` (`50.0%`) | `6 / 20` (`30.0%`) | `11 / 20` (`55.0%`) | `3 / 20` (`15.0%`) | `6 / 3 / 8 / 3` |
| **Total** | **`60`** | **`51 / 60` (`85.0%`)** | **`42 / 60` (`70.0%`)** | **`32 / 60` (`53.3%`)** | **`48 / 60` (`80.0%`)** | **`29 / 60` (`48.3%`)** | **`9 / 9 / 13 / 29`** |

## 5. Remaining Gap Reasons & Measured Activity Counters

- **Remaining `P0` (`9` POIs: `6` Hạ Long, `1` Đà Nẵng, `2` Hà Nội):**
  - `0931b06b-4563-4af0-a3a4-75f1ad8392ee` (`Vườn hoa`, Hạ Long), `6215446b-2fdd-4014-aacf-23de6e45e264` (`Chợ Hạ Long II`, Hạ Long), `708ee182-c879-477c-b920-516e2c99b0a6` (`Công viên Lán Bè`, Hạ Long), `77af14b6-85ac-4c91-873a-e7da27d555f4` (`Hang Luồn Cave Entrance`, Hạ Long), `8fe33554-7a07-4eb2-870f-8af643d8c728` (`Vườn hoa Thị trấn Trới`, Hạ Long), `b57b3f7d-9704-44b0-8139-19bea1998391` (`Sữa chua trân châu Hạ Long cơ sở 00`, Hạ Long), `c2afbb07-aaf9-47c1-9877-d17e64422066` (`Chợ Bắc Mỹ An`, Đà Nẵng — Overture `Chợ Bắc Mỹ An Online` rejected under `FC-006`), `4146f2b7-8289-4309-b7e6-60ba7de3470e` (`Cà Phê Nola`, Hà Nội), `b0641225-0f38-4bcc-9f4c-34f65fa50d45` (`Cửa Hàng Bánh Tôm Hồ Tây`, Hà Nội).
- **Measured External Activity & Zero-Violation Counters:**
  - `MEASURED_HTTP_API_REQUESTS = 30` (`25` Wikipedia + `2` Wikidata + `3` Wikivoyage)
  - `WEB_SOURCE_PAGES_CHECKED = 59` (`25` Wikipedia + `31` Wikidata + `3` Wikivoyage)
  - `WEB_DOCUMENTS_DOWNLOADED = 59`
  - `LOCAL_OVERTURE_PARQUET_RECORDS_INSPECTED = 34`
  - `OSM_TAG_WEBSITE_URLS_DISCOVERED_NOT_FETCHED = 16`
  - `OPEN_REUSABLE_DOCUMENTS_ACCEPTED = 97`
  - `REFERENCE_ONLY_SOURCES = 16`
  - `RESEARCH_RESTRICTED_SOURCES = 0`
  - `REJECTED_SOURCES = 19`
  - `PAID_DATA_API_USED = false`
  - `NEW_SOCIAL_COLLECTION = 0`
  - `NEW_GOOGLE_MAPS_REVIEW_COLLECTION = 0`
  - `NEW_LLM_PROVIDER_CALLS = 0`
- **Future Useful Chunk Range (`ESTIMATE`):**
  - `value_kind = ESTIMATE`, `observed_chunk_count_in_b1b = null`, `estimated_target_60_useful_chunks_min = 330`, `estimated_target_60_useful_chunks_max = 505` (actual chunking is deferred to `W07-B2`).

## 6. Artifact Hashes

- `data/evaluation/w07/w07_b1b_source_decisions_v1.json`:
  - Internal `artifact_sha256`: `679cc9c64e12466e2ae59d88d63490e7f137d9357941d89780f81a96bb0efb53`
  - File LF SHA256: `2e551752e45cc0bdca0d725750d349777d3e3f4be74aaa50886335090baa524f`
- `data/curated/w07/poi_knowledge_acquired_v1.jsonl`:
  - File LF SHA256: `21f42ddcdfced86a5b55d19762c93c492a6ceb35902244fb54caab5bc39bcb01`
- `data/evaluation/w07/w07_b1b_acquisition_summary_v1.json`:
  - Internal `artifact_sha256`: `ec05c536e28738a304deaa7c136b94c376a7b45f1b248e4159d961ae9b9362b7`
  - File LF SHA256: `c8c31799c6c6a06e8d0ff4656cce8d4ee0ac21a0467f4f91f55e7cf523a8eecc`
