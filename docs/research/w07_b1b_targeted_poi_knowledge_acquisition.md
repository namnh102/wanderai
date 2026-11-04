# W07-B1B — Targeted POI Knowledge Acquisition Report (Corrective 03)

## 1. Authority & Executive Summary

- **Task ID:** `W07-B1B` (`W07-B1B-CORRECTIVE-03`)
- **Accepted Upstream Gate:** `W07-B1-FIX-01B-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Current Gate Status:** `W07-B1B-CORRECTIVE-02-FACT-CONSISTENCY-CHATGPT-AUDIT = HOLD-CORRECTIVE-03`
- **Next Gate:** `W07-B1B-CORRECTIVE-03-SOURCE-BINDING-CHATGPT-AUDIT`
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

## 2. Corrective 03 Source ID Binding & Provenance Reconciliation

1. **43-Reference OSM Source-Binding Reconciliation across 10 Canonical POIs (`OVERTURE_AUDITED_RECORDS = 26`):**
   - Audited all `43` OSM source-reference mismatches across `10` canonical POIs against `data/evaluation/w07/w07_review_target_60_pois_v1.json` and `data/curated/gomate_places_freeze_v2.json`:
     - **Type 1 (`TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` = `40`):** Same canonical OSM entity where the audit cited an outdated/alternate OSM ID -> corrected to exact `osm:<canonical_osm_id>` after verifying the canonical OSM record's tags in `gomate_places_freeze_v2.json` support the field comparison.
     - **Type 2 (`TYPE_2_VERIFIED_ALTERNATE_OSM_ENTITY_CROSSWALK` = `0`):** `0` references required an alternate OSM entity crosswalk.
     - **Type 3 (`TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED` = `3`):** Removed `3` unsupported OSM references and recomputed field status:
       1. `7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Đà Nẵng) `website`: Overture Parquet record `67b0a6b0-f6e8-477d-8517-ef73c56752f7` has `websites=None`; removed `osm:way/537517975` & `osm_website_pointer`, recomputed `CORROBORATED -> MISSING`.
       2. `a32ce1b4-126b-4544-b5ea-4a7edbab6a0a` (`Furama Resort`, Đà Nẵng) `phone`: canonical `osm:way/485212452` has `phone=+84 236 3847888` (which does not match Overture's `+842363847333`); removed `osm:way/977276708`, retained `CORROBORATED` via `wikivoyage:en:Da_Nang#Furama_Resort` (`+84 5 1138 47333`).
       3. `afb3793b-7227-4645-a68a-3647c7468638` (`Sen Tây Hồ`, Hà Nội) `address`: canonical `osm:node/443000681` has no `addr:*` tags; removed `osm:way/613491916`, recomputed `CORROBORATED -> UNVERIFIED`.
2. **Machine-Verifiable Provenance Binding across All 130 Field Evaluations:**
   - Every reference in `corroboration_sources` and `conflicting_sources` (`canonical_poi:<id>`, `osm:<type>/<id>`, `wikidata:<qid>`, `wikipedia:<lang>:<pageid>`, `wikivoyage:en:<page>#<listing>`, `overture:<gers_id>`, `osm_website_pointer:<url>`) is now machine-verified against local frozen/committed artifacts.
   - Removed all unverified arbitrary string tokens (`official_resort_site:...`, `official_tourism_listing:...`, `official_museum_site:...`) and replaced or downgraded fields where committed sources did not corroborate the value (`74 CORROBORATED`, `16 CONFLICTED`, `28 UNVERIFIED`, `12 MISSING`).
3. **Unverified Fact Handling (`[SOURCE_REPORTED_UNVERIFIED ...]` & `answer_ready_confirmed_text`):**
   - `CONFLICTED` fields remain suppressed from `raw_text` and `answer_ready_confirmed_text`.
   - `CORROBORATED` fields carry explicit `[CORROBORATED: <sources>]` provenance in `raw_text`.
   - `UNVERIFIED` contact details (`phone`), addresses (`address`), and website links (`website`) are explicitly qualified in `raw_text` with `[SOURCE_REPORTED_UNVERIFIED — chưa xác minh độc lập, không trình bày như sự kiện đã xác nhận]`, excluded from `answer_ready_confirmed_text`, and listed in `unverified_fields` and `source_reported_unverified_values` (`present_as_confirmed_fact = false`).
4. **Temporal Provenance Reconciliation (`0` New HTTP Requests):**
   - Replaced manufactured timestamp constants so `retrieved_at = "UNKNOWN_HISTORICAL_RETRIEVAL_TIME"` and `source_terms_checked_at = "UNKNOWN_VERIFICATION_TIME"` wherever no separate timestamped retrieval/verification receipt exists, while preserving upstream `source_published_or_updated_at` (MediaWiki `revid` timestamp, Wikidata `modified`, Overture release `2026-09-23T00:00:00Z`) and `artifact_snapshot_timestamp = "2026-11-03T18:45:00Z"`.

### 43-Reference OSM Source-Binding Reconciliation Ledger

| # | Canonical POI | Overture GERS | Field (List) | Previous Reference | Canonical OSM ID | Classification | Reconciled Reference | Field Status Before -> After |
|---|---|---|---|---|---|---|---|---|
| 1 | `75a3fbd1` (Vinpearl Ha Long resort) | `9ed3a2e3` | `coordinates` (`corroboration_sources`) | `osm:node/3929648836` | `osm:node/4330722989` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4330722989` | `CORROBORATED` -> **`CORROBORATED`** |
| 2 | `75a3fbd1` (Vinpearl Ha Long resort) | `9ed3a2e3` | `category_taxonomy` (`corroboration_sources`) | `osm:node/3929648836` | `osm:node/4330722989` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4330722989` | `CORROBORATED` -> **`CORROBORATED`** |
| 3 | `065f8492` (Nhà hàng Buffet Sen Á Đông) | `0772c46b` | `coordinates` (`corroboration_sources`) | `osm:node/12224148306` | `osm:node/12998779901` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998779901` | `CORROBORATED` -> **`CORROBORATED`** |
| 4 | `065f8492` (Nhà hàng Buffet Sen Á Đông) | `0772c46b` | `address` (`corroboration_sources`) | `osm:node/12224148306` | `osm:node/12998779901` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998779901` | `CORROBORATED` -> **`CORROBORATED`** |
| 5 | `065f8492` (Nhà hàng Buffet Sen Á Đông) | `0772c46b` | `category_taxonomy` (`corroboration_sources`) | `osm:node/12224148306` | `osm:node/12998779901` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998779901` | `CORROBORATED` -> **`CORROBORATED`** |
| 6 | `065f8492` (Nhà hàng Buffet Sen Á Đông) | `0772c46b` | `phone` (`conflicting_sources`) | `osm:node/12224148306` | `osm:node/12998779901` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998779901` | `CONFLICTED` -> **`CONFLICTED`** |
| 7 | `065f8492` (Nhà hàng Buffet Sen Á Đông) | `0772c46b` | `website` (`corroboration_sources`) | `osm:node/12224148306` | `osm:node/12998779901` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998779901` | `CORROBORATED` -> **`CORROBORATED`** |
| 8 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1) | `04dda4d2` | `coordinates` (`corroboration_sources`) | `osm:node/12224109901` | `osm:node/12998531301` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998531301` | `CORROBORATED` -> **`CORROBORATED`** |
| 9 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1) | `04dda4d2` | `address` (`corroboration_sources`) | `osm:node/12224109901` | `osm:node/12998531301` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998531301` | `CORROBORATED` -> **`CORROBORATED`** |
| 10 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1) | `04dda4d2` | `category_taxonomy` (`corroboration_sources`) | `osm:node/12224109901` | `osm:node/12998531301` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998531301` | `CORROBORATED` -> **`CORROBORATED`** |
| 11 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1) | `04dda4d2` | `phone` (`conflicting_sources`) | `osm:node/12224109901` | `osm:node/12998531301` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998531301` | `CONFLICTED` -> **`CONFLICTED`** |
| 12 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1) | `04dda4d2` | `website` (`conflicting_sources`) | `osm:node/12224109901` | `osm:node/12998531301` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/12998531301` | `CONFLICTED` -> **`CONFLICTED`** |
| 13 | `61639da8` (My Quang Bà Mua) | `da92232b` | `coordinates` (`corroboration_sources`) | `osm:node/6482150490` | `osm:node/7210857787` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/7210857787` | `CORROBORATED` -> **`CORROBORATED`** |
| 14 | `61639da8` (My Quang Bà Mua) | `da92232b` | `address` (`conflicting_sources`) | `osm:node/6482150490` | `osm:node/7210857787` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/7210857787` | `CONFLICTED` -> **`CONFLICTED`** |
| 15 | `61639da8` (My Quang Bà Mua) | `da92232b` | `category_taxonomy` (`corroboration_sources`) | `osm:node/6482150490` | `osm:node/7210857787` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/7210857787` | `CORROBORATED` -> **`CORROBORATED`** |
| 16 | `61639da8` (My Quang Bà Mua) | `da92232b` | `phone` (`corroboration_sources`) | `osm:node/6482150490` | `osm:node/7210857787` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/7210857787` | `CORROBORATED` -> **`CORROBORATED`** |
| 17 | `61639da8` (My Quang Bà Mua) | `da92232b` | `website` (`conflicting_sources`) | `osm:node/6482150490` | `osm:node/7210857787` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/7210857787` | `CONFLICTED` -> **`CONFLICTED`** |
| 18 | `62a874a9` (Bánh Xèo Bà Dưỡng) | `c732f0d5` | `coordinates` (`corroboration_sources`) | `osm:node/4810542131` | `osm:node/4541527689` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4541527689` | `CORROBORATED` -> **`CORROBORATED`** |
| 19 | `62a874a9` (Bánh Xèo Bà Dưỡng) | `c732f0d5` | `address` (`corroboration_sources`) | `osm:node/4810542131` | `osm:node/4541527689` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4541527689` | `CORROBORATED` -> **`CORROBORATED`** |
| 20 | `62a874a9` (Bánh Xèo Bà Dưỡng) | `c732f0d5` | `category_taxonomy` (`corroboration_sources`) | `osm:node/4810542131` | `osm:node/4541527689` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4541527689` | `CORROBORATED` -> **`CORROBORATED`** |
| 21 | `62a874a9` (Bánh Xèo Bà Dưỡng) | `c732f0d5` | `website` (`conflicting_sources`) | `osm:node/4810542131` | `osm:node/4541527689` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/4541527689` | `CONFLICTED` -> **`CONFLICTED`** |
| 22 | `7ff87c59` (Vincom Plaza) | `67b0a6b0` | `coordinates` (`corroboration_sources`) | `osm:way/537517975` | `osm:way/693393717` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/693393717` | `CORROBORATED` -> **`CORROBORATED`** |
| 23 | `7ff87c59` (Vincom Plaza) | `67b0a6b0` | `address` (`corroboration_sources`) | `osm:way/537517975` | `osm:way/693393717` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/693393717` | `CORROBORATED` -> **`CORROBORATED`** |
| 24 | `7ff87c59` (Vincom Plaza) | `67b0a6b0` | `category_taxonomy` (`corroboration_sources`) | `osm:way/537517975` | `osm:way/693393717` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/693393717` | `CORROBORATED` -> **`CORROBORATED`** |
| 25 | `7ff87c59` (Vincom Plaza) | `67b0a6b0` | `phone` (`conflicting_sources`) | `osm:way/537517975` | `osm:way/693393717` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/693393717` | `CONFLICTED` -> **`CONFLICTED`** |
| 26 | `7ff87c59` (Vincom Plaza) | `67b0a6b0` | `website` (`corroboration_sources`) | `osm:way/537517975` | `osm:way/693393717` | `TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED` | `*(removed)*` | `CORROBORATED` -> **`MISSING`** |
| 27 | `9a2ca486` (Chợ Đêm Sơn Trà) | `a310c792` | `coordinates` (`corroboration_sources`) | `osm:node/6961175185` | `osm:way/1556362196` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/1556362196` | `CORROBORATED` -> **`CORROBORATED`** |
| 28 | `9a2ca486` (Chợ Đêm Sơn Trà) | `a310c792` | `address` (`conflicting_sources`) | `osm:node/6961175185` | `osm:way/1556362196` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/1556362196` | `CONFLICTED` -> **`CONFLICTED`** |
| 29 | `9a2ca486` (Chợ Đêm Sơn Trà) | `a310c792` | `category_taxonomy` (`corroboration_sources`) | `osm:node/6961175185` | `osm:way/1556362196` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/1556362196` | `CORROBORATED` -> **`CORROBORATED`** |
| 30 | `a32ce1b4` (Furama Resort) | `82f95e1f` | `coordinates` (`corroboration_sources`) | `osm:way/977276708` | `osm:way/485212452` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/485212452` | `CORROBORATED` -> **`CORROBORATED`** |
| 31 | `a32ce1b4` (Furama Resort) | `82f95e1f` | `address` (`corroboration_sources`) | `osm:way/977276708` | `osm:way/485212452` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/485212452` | `CORROBORATED` -> **`CORROBORATED`** |
| 32 | `a32ce1b4` (Furama Resort) | `82f95e1f` | `category_taxonomy` (`corroboration_sources`) | `osm:way/977276708` | `osm:way/485212452` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/485212452` | `CORROBORATED` -> **`CORROBORATED`** |
| 33 | `a32ce1b4` (Furama Resort) | `82f95e1f` | `phone` (`corroboration_sources`) | `osm:way/977276708` | `osm:way/485212452` | `TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED` | `*(removed)*` | `CORROBORATED` -> **`CORROBORATED`** |
| 34 | `a32ce1b4` (Furama Resort) | `82f95e1f` | `website` (`conflicting_sources`) | `osm:way/977276708` | `osm:way/485212452` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/485212452` | `CONFLICTED` -> **`CONFLICTED`** |
| 35 | `afb3793b` (Sen Tây Hồ) | `e8077687` | `coordinates` (`corroboration_sources`) | `osm:way/613491916` | `osm:node/443000681` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/443000681` | `CORROBORATED` -> **`CORROBORATED`** |
| 36 | `afb3793b` (Sen Tây Hồ) | `e8077687` | `address` (`corroboration_sources`) | `osm:way/613491916` | `osm:node/443000681` | `TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED` | `*(removed)*` | `CORROBORATED` -> **`UNVERIFIED`** |
| 37 | `afb3793b` (Sen Tây Hồ) | `e8077687` | `category_taxonomy` (`corroboration_sources`) | `osm:way/613491916` | `osm:node/443000681` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/443000681` | `CORROBORATED` -> **`CORROBORATED`** |
| 38 | `afb3793b` (Sen Tây Hồ) | `e8077687` | `website` (`conflicting_sources`) | `osm:way/613491916` | `osm:node/443000681` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:node/443000681` | `CONFLICTED` -> **`CONFLICTED`** |
| 39 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam) | `e55bab3c` | `coordinates` (`corroboration_sources`) | `osm:way/39954624` | `osm:way/339936730` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/339936730` | `CORROBORATED` -> **`CORROBORATED`** |
| 40 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam) | `e55bab3c` | `address` (`conflicting_sources`) | `osm:way/39954624` | `osm:way/339936730` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/339936730` | `CONFLICTED` -> **`CONFLICTED`** |
| 41 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam) | `e55bab3c` | `category_taxonomy` (`corroboration_sources`) | `osm:way/39954624` | `osm:way/339936730` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/339936730` | `CORROBORATED` -> **`CORROBORATED`** |
| 42 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam) | `e55bab3c` | `phone` (`corroboration_sources`) | `osm:way/39954624` | `osm:way/339936730` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/339936730` | `CORROBORATED` -> **`CORROBORATED`** |
| 43 | `f0d424bd` (Bảo tàng Dân tộc học Việt Nam) | `e55bab3c` | `website` (`corroboration_sources`) | `osm:way/39954624` | `osm:way/339936730` | `TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` | `osm:way/339936730` | `CORROBORATED` -> **`CORROBORATED`** |

### 26-Record Overture Fact-Consistency Audit Table (`130` Field Evaluations: `74 CORROBORATED`, `16 CONFLICTED`, `28 UNVERIFIED`, `12 MISSING`)

| # | Canonical POI | Overture GERS | Conflict ID | Coordinates | Address | Category / Taxonomy | Phone | Website | Suppressed Fields | Post-Audit Status & Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `75a3fbd1` (Vinpearl Ha Long resort, Hạ Long) | `9ed3a2e3` | `FC-002` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | `address` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 2 | `8f2b5a69` (Bảo tàng Quảng Ninh, Hạ Long) | `bd078edf` | `FC-008` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 3 | `9740c851` (Novotel Ha Long, Hạ Long) | `893209f5` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 4 | `065f8492` (Nhà hàng Buffet Sen Á Đông, Hạ Long) | `0772c46b` | `FC-009` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `phone` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 5 | `7d01af19` (Nhà hàng Ngọc Phương Nam 1, Hạ Long) | `04dda4d2` | `FC-010` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `CONFLICTED` | `phone`, `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 6 | `85303289` (Highlands Coffee, Hạ Long) | `6039522b` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 7 | `871a6ee7` (Ha Long International Cruise Port, Hạ Long) | `527ebd9f` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 8 | `96523873` (Chợ Cái Dăm, Hạ Long) | `9b6e3c9a` | `FC-007` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `MISSING` | `CONFLICTED` | `category_taxonomy`, `website` | `EXACT_MAPPED` / `LOW_INFORMATION` -> **`REJECT`** |
| 9 | `b37d68ee` (Nhà hàng Hồng Hạnh 3, Hạ Long) | `92ed9717` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 10 | `8ebf0429` (Ca Phe 83, Đà Nẵng) | `1b27afcb` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 11 | `c2afbb07` (Chợ Bắc Mỹ An, Đà Nẵng) | `4d3dbac0` | `FC-006` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `MAPPING_REVIEW_REQUIRED` / `LOW_INFORMATION` -> **`REJECT`** |
| 12 | `4608034c` (InterContinental Danang Sun Peninsula Resort, Đà Nẵng) | `0d91068a` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 13 | `5fc0994a` (Chùa Linh Ứng, Đà Nẵng) | `b9ad130e` | `FC-005` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `MAPPING_REVIEW_REQUIRED` / `LOW_INFORMATION` -> **`REJECT`** |
| 14 | `61639da8` (My Quang Bà Mua, Đà Nẵng) | `da92232b` | `FC-003` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `address`, `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 15 | `62a874a9` (Bánh Xèo Bà Dưỡng, Đà Nẵng) | `c732f0d5` | `FC-011` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 16 | `7ff87c59` (Vincom Plaza, Đà Nẵng) | `67b0a6b0` | `FC-012` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `MISSING` | `phone` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 17 | `9a2ca486` (Chợ Đêm Sơn Trà, Đà Nẵng) | `a310c792` | `FC-004` | `CORROBORATED` | `CONFLICTED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | `address` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 18 | `a32ce1b4` (Furama Resort, Đà Nẵng) | `82f95e1f` | `FC-013` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 19 | `fd118580` (Nhà hàng hải sản Bé Anh, Đà Nẵng) | `df8dc91d` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 20 | `5350dd97` (Pho 10, Hà Nội) | `ff9a223f` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 21 | `5bd45eb7` (Highlands Coffee, Hà Nội) | `e8f37b82` | — | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `MISSING` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 22 | `5e92e89d` (Sheraton Hanoi, Hà Nội) | `80ceecb4` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `UNVERIFIED` | `UNVERIFIED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 23 | `9a96e0a0` (Somerset Grand Hanoi, Hà Nội) | `165cef5b` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 24 | `a2037ceb` (Công viên Lê-nin, Hà Nội) | `3421b671` | — | `CORROBORATED` | `CORROBORATED` | `CORROBORATED` | `MISSING` | `MISSING` | *(none)* | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
| 25 | `afb3793b` (Sen Tây Hồ, Hà Nội) | `e8077687` | `FC-014` | `CORROBORATED` | `UNVERIFIED` | `CORROBORATED` | `UNVERIFIED` | `CONFLICTED` | `website` | `EXACT_MAPPED` / `USEFUL_STRUCTURED_FACTS` -> **`ACCEPT_PRIMARY_CORPUS`** |
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

| Coverage Dimension | Before B1B (`FIX-01B` Baseline) | After B1B (`FIX-01B` + `B1B` Corrective 03) | Delta |
|---|---|---|---|
| POIs with Primary Eligible Evidence | `60 / 60` (`100.0%`) | `60 / 60` (`100.0%`) | `0` |
| POIs with RAG-Candidate Evidence (`RAG_CANDIDATE_ELIGIBLE`) | `40 / 60` (`66.67%`) | **`51 / 60` (`85.00%`)** | **`+11`** |
| POIs with `>=2` Independent Eligible Lineages | `0 / 60` (`0.00%`) | **`42 / 60` (`70.00%`)** | **`+42`** |
| POIs with Narrative Evidence (`USEFUL_NARRATIVE`) | `0 / 60` (`0.00%`) | **`32 / 60` (`53.33%`)** | **`+32`** |
| POIs with Useful Structured Evidence (`USEFUL_STRUCTURED_FACTS`) | `40 / 60` (`66.67%`) | **`48 / 60` (`80.00%`)** | **`+8`** |
| POIs with Both Structured & Narrative Evidence | `0 / 60` (`0.00%`) | **`29 / 60` (`48.33%`)** | **`+29`** |

### Priority Distribution Shift (`P0 -> P1 -> P2 -> P3`)

| Priority Band | Definition | Before B1B | After B1B (Corrective 03) |
|---|---|---|---|
| `P0` | `0` RAG-eligible evidence units (`NO_RAG_ELIGIBLE_EVIDENCE`) | `20` | **`9`** (`11` closed) |
| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`9`** (`2` Hà Nội, `3` Đà Nẵng, `4` Hạ Long) |
| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`13`** (`2` Hà Nội, `4` Đà Nẵng, `7` Hạ Long) |
| `P3` | `>=2` RAG-eligible lineages with BOTH structured & narrative evidence | `0` | **`29`** (`14` Hà Nội, `12` Đà Nẵng, `3` Hạ Long) |

### Coverage by City

| City | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both Structured & Narrative | Post-B1B Priorities (`P0/P1/P2/P3`) |
|---|---|---|---|---|---|---|---|
| **Hà Nội** | `20` | **`18 / 20` (`90.0%`)** | `16 / 20` (`80.0%`) | `14 / 20` (`70.0%`) | `18 / 20` (`90.0%`) | `14 / 20` (`70.0%`) | `2 / 2 / 2 / 14` |
| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 3 / 4 / 12` |
| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `10 / 20` (`50.0%`) | `6 / 20` (`30.0%`) | `11 / 20` (`55.0%`) | `3 / 20` (`15.0%`) | `6 / 4 / 7 / 3` |
| **Total** | **`60`** | **`51 / 60` (`85.0%`)** | **`42 / 60` (`70.0%`)** | **`32 / 60` (`53.3%`)** | **`48 / 60` (`80.0%`)** | **`29 / 60` (`48.3%`)** | **`9 / 9 / 13 / 29`** |

## 5. Remaining Gap Reasons & Measured Activity Counters

- **Remaining `P0` (`9` POIs: `6` Hạ Long, `1` Đà Nẵng, `2` Hà Nội):**
  - `0931b06b-4563-4af0-a3a4-75f1ad8392ee` (`Vườn hoa`, Hạ Long), `6215446b-2fdd-4014-aacf-23de6e45e264` (`Chợ Hạ Long II`, Hạ Long), `708ee182-c879-477c-b920-516e2c99b0a6` (`Công viên Lán Bè`, Hạ Long), `77af14b6-85ac-4c91-873a-e7da27d555f4` (`Hang Luồn Cave Entrance`, Hạ Long), `8fe33554-7a07-4eb2-870f-8af643d8c728` (`Vườn hoa Thị trấn Trới`, Hạ Long), `b57b3f7d-9704-44b0-8139-19bea1998391` (`Sữa chua trân châu Hạ Long cơ sở 00`, Hạ Long), `c2afbb07-aaf9-47c1-9877-d17e64422066` (`Chợ Bắc Mỹ An`, Đà Nẵng — Overture `Chợ Bắc Mỹ An Online` rejected under `FC-006`), `4146f2b7-8289-4309-b7e6-60ba7de3470e` (`Cà Phê Nola`, Hà Nội), `b0641225-0f38-4bcc-9f4c-34f65fa50d45` (`Cửa Hàng Bánh Tôm Hồ Tây`, Hà Nội).
- **Measured External Activity & Zero-Violation Counters:**
  - `MEASURED_HTTP_API_REQUESTS = 30` (`25` Wikipedia + `2` Wikidata + `3` Wikivoyage; `CORRECTIVE_03_NEW_HTTP_REQUESTS = 0`)
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
  - Internal `artifact_sha256`: `15264c290c9b6a964a331cd88d57a32b968362dcd457591408fe5f3c7e694046`
  - File LF SHA256: `edbec84b6161862d439ce2b5d9687b15bd181656b7fa8ff145a713f74afe1249`
- `data/curated/w07/poi_knowledge_acquired_v1.jsonl`:
  - File LF SHA256: `9b0ed36e060924057872a2e8fe9941940f7bc3455f2c9cad21cdc9a9c1141fda`
- `data/evaluation/w07/w07_b1b_acquisition_summary_v1.json`:
  - Internal `artifact_sha256`: `ce64cd5c03b5ca5575fd4073531503c1e3651d34cf36a02e53ec34efc422cb43`
  - File LF SHA256: `1cf83d3b143f9ceba85ea0c592bf2d339b28d1f0734507aea4c46648dc05e1a0`
