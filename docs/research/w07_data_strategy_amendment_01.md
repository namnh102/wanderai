# W07-B0 — Data Strategy Amendment 01: Canonical POI Knowledge RAG (Corrective 01)

## 1. Authority & Context

- **Task ID:** `W07-B0-DATA-STRATEGY-AMENDMENT-01-CORRECTIVE-01`
- **Version:** `1.1.0-corrective-01`
- **Authoritative Base:** `develop@8304a71ee01d3edac224de6dc3d75beb0427fe16`
- **Previous Accepted Gate:** `W07-A4P-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Current Gate Status:** `W07-B0-DATA-STRATEGY-AMENDMENT-01-CHATGPT-AUDIT = HOLD-CORRECTIVE-MINOR`
- **Next Gate:** `W07-B0-CORRECTIVE-01-SOURCE-GOVERNANCE-CHATGPT-AUDIT`
- **Frozen W07-A2 60-POI Manifest SHA256:** `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`
- **Frozen W07-A4P Report SHA256:** `1ee567e59b7d4da8069f32d9734a9de95703d4955dd27cfa1db30f7a06422916`
- **Frozen W07-A4P Evidence Receipt SHA256:** `929f7f55ebdec5387778c11080ae56db8cdf0204ac70bc11109bb59a601011c4`

## 2. Amendment Decision & Strategy Transition

- **Old Strategy:** `POI-grounded review corpus -> retrieval -> RAG review summarization`
- **New Strategy:** `canonical POI knowledge corpus -> retrieval -> grounded POI RAG`
- `W07_PRIMARY_CORPUS_STRATEGY`: `EVIDENCE_GROUNDED_POI_KNOWLEDGE`
- `PRIMARY_W07_CORPUS`: `OPEN_AND_OFFICIAL_POI_KNOWLEDGE`
- `FIRST_PARTY_REVIEW_COLLECTION_STATUS`: `OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT`
- `PUBLIC_REVIEW_ACQUISITION_STATUS`: `CLOSED_NO_SUITABLE_PRIMARY_DATA`
- `GOOGLE_MAPS_ROLE`: `RUNTIME_ENRICHMENT_ONLY`
- `SOCIAL_PLATFORM_ROLE`: `DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS`
- `W07_RETRIEVAL_EXPERIMENT_STATUS`: `NOT_STARTED`
- `W07_RAG_EXPERIMENT_STATUS`: `NOT_STARTED`

### 2.1 Scientific Rationale

W07-A4P investigated 18 public sources comprising 300,536 raw rows and 186,170 unique public reviews, but zero reviews satisfied the combined frozen requirements for clear academic reuse/provenance and high-confidence mapping to the 60 canonical POIs in Hà Nội, Đà Nẵng, and Hạ Long. Continuing broad public-review acquisition has diminishing scientific value. Meanwhile, first-party review collection (W07-A3 Google Forms and W07-A4H Assisted Collection) remains scientifically valid, but human contributor recruitment volume cannot be made a blocking gate for the core W07 retrieval and RAG thesis experiments. Amending the primary W07 corpus to an evidence-grounded canonical POI knowledge corpus preserves strict provenance, avoids fabricated or AI-generated reviews, avoids unauthorized commercial scraping, and enables rigorous offline evaluation of BM25, Dense, and Hybrid RRF retrieval and grounded RAG citation.

## 3. Core Scientific Corpus, Authority Hierarchy & Reuse Governance (Corrective 01)

- **Primary Corpus (`PRIMARY_W07_CORPUS`):** `OPEN_AND_OFFICIAL_POI_KNOWLEDGE`
- **Frozen Target POI Universe:** `data/evaluation/w07/w07_review_target_60_pois_v1.json` (`60` canonical POIs: `20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).
- `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION`: `true`
- **Orthogonal Dimensions Rule:** Source authority tier (TIER_A..TIER_D) and reuse/storage permission (OPEN_REUSABLE, RESEARCH_RESTRICTED, REFERENCE_ONLY, PROHIBITED) are strictly independent dimensions. A Tier A or Tier B official site may still have unclear or restrictive reuse/storage terms, while a Tier C open source may carry explicit open reuse rights.
- **Eligible Evidence Classes:**
  - `OFFICIAL_TOURISM_AUTHORITY_PAGES`
  - `OFFICIAL_ATTRACTION_OR_VENUE_WEBSITES`
  - `GOVERNMENT_OR_LOCAL_TOURISM_PORTALS`
  - `OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA`
  - `OTHER_RESEARCH_USABLE_PUBLIC_DOCUMENTS_WITH_CLEAR_PROVENANCE`

### 3.1 Source Authority Hierarchy (`source_tier`)

| Tier | Rank | Authority Class | Scope |
|---|---:|---|---|
| `TIER_A` | 1 | Official POI / venue website | Official website or digital publication operated by the attraction, museum, hotel, or venue. High factual authority, but requires explicit reuse/storage verification before primary corpus ingestion. |
| `TIER_B` | 2 | Government / tourism-authority site | National, provincial, or municipal tourism authority portals and heritage administration pages. Requires explicit reuse/storage verification before primary corpus ingestion. |
| `TIER_C` | 3 | Open-data / open-license geographic or tourism source | OpenStreetMap (ODbL-1.0), Overture Maps (theme- and source-specific: CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0 for Places; other themes may carry ODbL-1.0), Wikidata structured data (CC0-1.0), and Wikimedia/Wikipedia/Wikivoyage text (CC-BY-SA-4.0 / CC-BY-SA-3.0 with attribution/share-alike). |
| `TIER_D` | 4 | Other research-usable public source | Publicly accessible travel/cultural reference documents with verified reuse rights, clear provenance, and non-conflicting factual claims. |

- **Conflict Resolution Rule:** Prefer higher authority tiers (TIER_A > TIER_B > TIER_C > TIER_D) when factual claims conflict; never treat low-authority social posts as canonical factual evidence, and never treat authority tier alone as permission to store or redistribute raw text.

### 3.2 Reuse & Storage Classification (`reuse_storage_class`)

| Reuse/Storage Class | Primary Corpus Eligible (if Mapped) | Raw Text Storage | Redistributable in Git | Governance Semantics |
|---|---|---|---|---|
| `OPEN_REUSABLE` | `true` | `true` | `true` | Explicit compatible license or reuse basis allows intended primary corpus text storage and redistribution in Git, subject to recorded attribution/share-alike obligations. |
| `RESEARCH_RESTRICTED` | `true` | `true` | `false` | Permitted/justified only for internal academic research handling under documented constraints; raw content is stored only in git-ignored restricted storage (`data/restricted/`) and never redistributed in Git unless explicit permission allows it. |
| `REFERENCE_ONLY` | `false` | `false` | `false` | Useful authoritative source for factual verification/reference, but reuse/storage rights are insufficient for persistent primary corpus text. Only metadata (`source_url`, `publisher`, `source_title`, `retrieved_at`, `provenance_status`, and factual verification notes where allowed) may be retained; copied full raw text must never be committed. |
| `PROHIBITED` | `false` | `false` | `false` | Terms or license explicitly conflict with intended collection, storage, or research reuse; must not be ingested. |

### 3.3 Two-Gate Primary Corpus Eligibility & Raw-Text Git Policy

- **Two-Gate Formula:** `PRIMARY_CORPUS_ELIGIBLE = CANONICAL_MAPPING_OK AND REUSE_STATUS_ALLOWED`
  1. **Gate 1 (`CANONICAL_MAPPING_OK`):** Document must deterministically map to one of the 60 frozen canonical POIs in `data/evaluation/w07/w07_review_target_60_pois_v1.json` (`CANONICAL_MAPPING_OK = true`).
  2. **Gate 2 (`REUSE_STATUS_ALLOWED`):** Document must have verified reuse/storage permission (`reuse_storage_class` in `{OPEN_REUSABLE, RESEARCH_RESTRICTED}` with explicit `reuse_evidence`, `attribution_requirement`, and `source_terms_checked_at`; `REUSE_STATUS_ALLOWED = true`).
- **Raw-Text Git Policy (`RAW_TEXT_COMMIT_ALLOWED = true`):** `RAW_TEXT_COMMIT_ALLOWED = true` ONLY when `reuse_storage_class == 'OPEN_REUSABLE'` and `redistributable_in_git == true` with verified `reuse_evidence`. Otherwise, keep raw text in git-ignored `data/restricted/` (if `RESEARCH_RESTRICTED`) or retain metadata only (`REFERENCE_ONLY`). No copyrighted or public webpage may be committed to Git merely because it is publicly accessible.

### 3.4 Source-Specific License Precision (Overture, OSM, Wikidata, Wikimedia Text)

- **Overture Maps (`OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`):** At B1, inspect record-level Overture attribution/license metadata for the exact theme (`overture_theme`) and contributing source (`overture_contributing_source`) used; never assign one blanket Overture license to every record. For `Places`, licenses may include `CDLA-Permissive-2.0`, `Apache-2.0`, or `CC0-1.0` depending on contributing source; other themes may carry `ODbL-1.0`.
- **OpenStreetMap (`ODbL-1.0`):** OpenStreetMap data is governed by ODbL-1.0; record attribution (`© OpenStreetMap contributors, ODbL-1.0`) and share-alike obligations where applicable.
- **Wikidata (`CC0-1.0`):** Wikidata structured data statements are licensed under CC0-1.0 (Public Domain Dedication).
- **Wikipedia / Wikivoyage / Wikimedia Text (`CC-BY-SA-4.0` / `CC-BY-SA-3.0`):** Wikipedia, Wikivoyage, and Wikimedia prose/text must NOT be collapsed into Wikidata CC0 semantics; text reuse must preserve the applicable Creative Commons Attribution-ShareAlike license, author/revision history link, and source-specific share-alike requirements.

### 3.5 B1 Source Decision Matrix Specification

- **Required Evaluation Fields (`11`):** `canonical_poi_mapping`, `authority_tier`, `publisher`, `source_url`, `source_type`, `license_or_reuse_evidence`, `reuse_storage_class`, `attribution_requirement`, `redistributable_in_git`, `raw_text_permitted`, `final_b1_decision`
- **Allowed Terminal Decisions (`4`):** `ACCEPT_PRIMARY_CORPUS`, `ACCEPT_RESTRICTED_RESEARCH_ONLY`, `REFERENCE_ONLY`, `REJECT`

## 4. Role Governance Across Data Channels

1. **First-Party Reviews (`OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT`):**
   - W07-A3 Google Forms and W07-A4H Assisted Collection remain scientifically valid and preserved.
   - First-party reviews are **not** marked as scientifically failed and may be added later when recruited, without blocking core W07 retrieval/RAG experiments.
2. **Public Reviews (`CLOSED_NO_SUITABLE_PRIMARY_DATA`):**
   - W07-A4P is closed (`300,536` discovered rows, `186,170` unique reviews, `0` accepted, `124,898` rejected, `61,272` quarantined). Broad public-review acquisition is not reopened.
3. **Google Maps (`RUNTIME_ENRICHMENT_ONLY` / `RUNTIME_POI_ENRICHMENT_ONLY`):**
   - Reserved for authorized runtime POI enrichment (`rating`, `user_rating_count`, limited provider-authorized review display, place metadata, attribution/source link); excluded from the primary frozen scientific corpus.
4. **Social Platforms (`DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS` / `DYNAMIC_SOCIAL_FRESHNESS_LAYER`):**
   - TikTok, Facebook, Instagram, YouTube, and social posts/comments are reserved for future task `SOCIAL-FRESHNESS-01` (trending POIs, recent events, dynamic homepage Hot Trending, supplementary recommender reranking signal) and must never become primary factual corpus or relevance ground truth.
5. **OpenClaw & JEV Roadmap:**
   - Neither is implemented in B0 or required for B0/B1 (`openclaw_implemented_in_b0 = false`, `jev_implemented_in_b0 = false`).

## 5. Primary W07 Research Questions & Ground Truth Policy

- **`RQ-W07-RETRIEVAL`:** *Which retrieval strategy most effectively retrieves relevant, provenance-grounded POI information for Vietnamese travel queries over the GoMate canonical POI knowledge corpus?*
  - Candidate strategies (for later gates): `BM25`, `Dense Retrieval`, `Hybrid RRF`, `Optional Reranking`.
  - Primary metric: `NDCG@10`; secondary metrics: `Recall@K`, `MRR`, `HitRate@K`, `coverage`.
- **`RQ-W07-RAG`:** *Can grounded generation using retrieved authoritative POI evidence answer travel questions with higher factual support and citation correctness than generation without retrieval?*
  - Evaluation dimensions (for later gates): `answer_correctness`, `groundedness`, `citation_correctness`, `unsupported_claim_rate`, `answer_completeness`.
- **Human Relevance Ground Truth Policy:**
  - Project researchers/team members judge `query <-> source chunk relevance` under frozen annotation guidelines, strictly separated from user review collection (`review_contributors_required_for_retrieval_gt = false`, `labels_created_in_b0 = 0`).

## 6. Baseline Repository Inspection & Provisional Corpus Thresholds

- **Frozen 60 POIs in Freeze v2 (`data/curated/gomate_places_freeze_v2.json`):** `60 / 60` (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).
- **Existing Local POI Signals on the 60 POIs:** `60` verified OSM IDs, `26` Overture GERS IDs, `41` street addresses, `15` OSM website tags, `14` Wikidata IDs, `13` Wikipedia tags, `18` opening hours.
- **Provisional Minimum Corpus Threshold:** `>= 30` canonical POIs (`>= 10` per city across all 3 target cities), `>= 2` independently provenance-bound documents per covered POI where available, and `>= 150` useful chunks after cleaning/chunking.
- **Provisional Preferred Corpus Threshold:** `45–60` canonical POIs, `>= 3` documents per POI where feasible, and `300–600` high-quality chunks.

## 7. Canonical Document & Chunk Schemas

- **Document Schema (`19` fields):** `document_id`, `poi_id`, `city`, `source_type`, `source_tier`, `source_title`, `source_url`, `publisher`, `language`, `retrieved_at`, `license_or_usage_class`, `reuse_storage_class`, `reuse_evidence`, `attribution_requirement`, `redistributable_in_git`, `source_terms_checked_at`, `raw_text`, `content_sha256`, `provenance_status`
- **Chunk Schema (`8` fields):** `chunk_id`, `document_id`, `poi_id`, `chunk_index`, `chunk_text`, `token_count`, `section_title`, `content_sha256`
- **Deferred Method Decisions (Not Frozen in B0):** `embedding_model`, `reranker`, `vector_db`, `chunk_size`, `bm25_implementation`, `llm_provider`

## 8. Scientific Claims Firewall, No-Acquisition Counters & Infrastructure at B0

- **Allowed Scientific Claims:**
  - "Review-based W07 corpus construction was not feasible under the frozen constraints and available investigated sources."
  - "The project therefore adopts an evidence-grounded POI knowledge corpus as the primary W07 retrieval corpus."
  - "No suitable public review was found among the investigated sources under the frozen W07 rules."
- **Forbidden Overclaims:**
  - ~~"No usable tourism reviews exist anywhere."~~ *(Forbidden)*
  - ~~"Google Maps cannot be used."~~ *(Forbidden)*
  - ~~"First-party review collection failed scientifically."~~ *(Forbidden)*
- `NEW_WEB_DOCUMENT_DOWNLOADS`: `0`
- `NEW_SOCIAL_COLLECTION`: `0`
- `NEW_GOOGLE_MAPS_COLLECTION`: `0`
- `GPU_REQUIRED_NOW`: `false`
- `SERVER_REQUIRED_NOW`: `false`
- `VECTOR_DB_SERVER_REQUIRED_NOW`: `false`
- `PAID_EMBEDDING_API_REQUIRED_NOW`: `false`
- `NEW_LLM_PROVIDER_CALLS`: `0`
