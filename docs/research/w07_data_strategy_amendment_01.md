# W07-B0 — Data Strategy Amendment 01: Canonical POI Knowledge RAG

## 1. Authority & Context

- **Task ID:** `W07-B0-DATA-STRATEGY-AMENDMENT-01`
- **Authoritative Base:** `develop@8304a71ee01d3edac224de6dc3d75beb0427fe16`
- **Previous Accepted Gate:** `W07-A4P-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Next Gate:** `W07-B0-DATA-STRATEGY-AMENDMENT-01-CHATGPT-AUDIT`
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

## 3. Core Scientific Corpus & Source Hierarchy

- **Primary Corpus (`PRIMARY_W07_CORPUS`):** `OPEN_AND_OFFICIAL_POI_KNOWLEDGE`
- **Frozen Target POI Universe:** `data/evaluation/w07/w07_review_target_60_pois_v1.json` (`60` canonical POIs: `20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).
- **Eligible Evidence Classes:**
  - `OFFICIAL_TOURISM_AUTHORITY_PAGES`
  - `OFFICIAL_ATTRACTION_OR_VENUE_WEBSITES`
  - `GOVERNMENT_OR_LOCAL_TOURISM_PORTALS`
  - `OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA`
  - `OTHER_RESEARCH_USABLE_PUBLIC_DOCUMENTS_WITH_CLEAR_PROVENANCE`

### 3.1 Source Authority Hierarchy

| Tier | Rank | Authority Class | Scope |
|---|---:|---|---|
| `TIER_A` | 1 | Official POI / venue website | Official website or digital publication operated by the attraction, museum, hotel, or venue. |
| `TIER_B` | 2 | Government / tourism-authority site | National, provincial, or municipal tourism authority portals and heritage administration pages. |
| `TIER_C` | 3 | Open-data / open-license geographic or tourism source | OpenStreetMap (ODbL 1.0), Overture Maps (CDLA Permissive 2.0 / CC0 1.0), Wikidata (CC0), Wikimedia/Wikipedia/Wikivoyage (CC BY-SA). |
| `TIER_D` | 4 | Other research-usable public source | Publicly accessible travel/cultural reference documents with clear provenance and non-conflicting factual claims. |

- **Conflict Resolution Rule:** Prefer higher authority tiers (TIER_A > TIER_B > TIER_C > TIER_D) when factual claims conflict; never treat low-authority social posts as canonical factual evidence.

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

## 6. Baseline Repository Inspection & Proposed Corpus Thresholds

- **Frozen 60 POIs in Freeze v2 (`data/curated/gomate_places_freeze_v2.json`):** `60 / 60` (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).
- **Existing Local POI Signals on the 60 POIs:** `60` verified OSM IDs, `26` Overture GERS IDs, `41` street addresses, `15` OSM website tags, `14` Wikidata IDs, `13` Wikipedia tags, `18` opening hours.
- **Minimum Corpus Threshold:** `>= 30` canonical POIs (`>= 10` per city across all 3 target cities), `>= 2` independently provenance-bound documents per covered POI where available, and `>= 150` useful chunks after cleaning/chunking.
- **Preferred Corpus Threshold:** `45–60` canonical POIs, `>= 3` documents per POI where feasible, and `300–600` high-quality chunks.

## 7. Canonical Document & Chunk Schemas

- **Document Schema (`14` fields):** `document_id`, `poi_id`, `city`, `source_type`, `source_tier`, `source_title`, `source_url`, `publisher`, `language`, `retrieved_at`, `license_or_usage_class`, `raw_text`, `content_sha256`, `provenance_status`
- **Chunk Schema (`8` fields):** `chunk_id`, `document_id`, `poi_id`, `chunk_index`, `chunk_text`, `token_count`, `section_title`, `content_sha256`
- **Deferred Method Decisions (Not Frozen in B0):** `embedding_model`, `reranker`, `vector_db`, `chunk_size`, `bm25_implementation`, `llm_provider`

## 8. Scientific Claims Firewall & Infrastructure at B0

- **Allowed Scientific Claims:**
  - "Review-based W07 corpus construction was not feasible under the frozen constraints and available investigated sources."
  - "The project therefore adopts an evidence-grounded POI knowledge corpus as the primary W07 retrieval corpus."
  - "No suitable public review was found among the investigated sources under the frozen W07 rules."
- **Forbidden Overclaims:**
  - ~~"No usable tourism reviews exist anywhere."~~ *(Forbidden)*
  - ~~"Google Maps cannot be used."~~ *(Forbidden)*
  - ~~"First-party review collection failed scientifically."~~ *(Forbidden)*
- `GPU_REQUIRED_NOW`: `false`
- `SERVER_REQUIRED_NOW`: `false`
- `VECTOR_DB_SERVER_REQUIRED_NOW`: `false`
- `PAID_EMBEDDING_API_REQUIRED_NOW`: `false`
- `NEW_LLM_PROVIDER_CALLS`: `0`
