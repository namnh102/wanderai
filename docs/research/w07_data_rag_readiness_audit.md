# W07-0 — Data + RAG Readiness Audit Report (Corrective 01)

## 0. Gate & Lineage Metadata

- **Task ID:** `W07-0-DATA-RAG-READINESS-AUDIT-CORRECTIVE-01`
- **Previous Gate:** `W07-DATA-RAG-READINESS-AUDIT-CHATGPT-AUDIT = SCIENTIFIC_AUDIT_ACCEPTED / ACQUISITION_PLAN_HOLD_CORRECTIVE`
- **Authoritative Base Commit:** `develop@bdd4810de0bc03ef52c67cc112e09d5787a7ffad`
- **W06 Closure Status:** `CLOSED_UNMODIFIED`
- **Next Gate:** `W07-DATA-RAG-READINESS-AUDIT-CORRECTIVE-01-CHATGPT-AUDIT`
- **JSON Artifact Internal SHA256:** `7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9`

---

## 1. Exact Data Inventory (Section 3 — Preserved Unchanged)

- **Real provenanced review text rows in repository:** `0`
- **Quarantined synthetic review text rows (`vietnam_travel_reviews.json` / `reviews_curated.json`):** `9`
- **Mock tool template strings (`apps/ai-service/app/tools/search_reviews.py`):** `2`
- **Real rating-only hotel interaction rows with ZERO review text (`ViHoRec`):** `17911`
- **Non-review RAG documents in Freeze v2 (`464` Wikivoyage English chunks + `759` OSM place docs):** `1223`

| Source ID | Storage Status | Classification | Provenance Category | Rows | Review Text | Ratings |
|---|---|---|---|---:|---|---|
| `gomate_places_freeze_v2` | `TRACKED_COMMITTED` | `API_DERIVED_PUBLIC_VERIFIED` | official/public + API (OpenStreetMap Overpass ODbL 1.0 + Overture Maps 2026-09-23.1) | `759` | `False` | `False` |
| `places_canonical_v1_legacy` | `TRACKED_COMMITTED` | `MIXED_OSM_AND_LEGACY_SEED` | official/public (97 OSM/Overture rows) + synthetic/legacy seed (11 unsourced rows) | `108` | `False` | `False` |
| `vietnam_travel_reviews_synthetic_pipeline` | `TRACKED_COMMITTED` | `GENERATED_SYNTHETIC_QUARANTINED` | synthetic | `9` | `True` | `True` |
| `vihorec_restricted_hotel_interactions` | `LOCAL_ONLY_GITIGNORED_SHA256_FROZEN` | `RESTRICTED_PUBLIC_ACADEMIC_DATASET` | Kaggle/Hugging Face/GitHub + restricted | `17911` | `False` | `True` |
| `vlsp2018_and_vimacsa_candidates` | `REFERENCED_IN_MANIFEST_NOT_PRESENT_ON_DISK` | `RESTRICTED_EXTERNAL_NOT_ACQUIRED` | restricted | `0` | `False` | `False` |
| `wikivoyage_and_osm_rag_documents` | `TRACKED_MANIFEST_AND_DB_SEED` | `PUBLIC_ENCYCLOPEDIC_AND_OSM_METADATA` | official/public | `1223` | `False` | `False` |
| `synthetic_preferences_and_seed_files` | `TRACKED_COMMITTED` | `GENERATED_SYNTHETIC` | synthetic | `406` | `False` | `True` |
| `ai_service_search_reviews_tool_stub` | `TRACKED_COMMITTED` | `GENERATED_SYNTHETIC_CODE_STUB` | synthetic | `2` | `True` | `False` |

---

## 2. City & Canonical POI Authority Coverage (Section 4)

- **Total Canonical Places in DB State (`dataset-freeze-v2.yaml`):** `882`
- **Verified OSM Places (`gomate_places_freeze_v2.json`):** `759` (`100%` have `rating = null` and `review_count = 0`)
- **REC-A Core 3-City Verified POIs:** `622`
  - **Hà Nội (`ha-noi`):** `145`
  - **Đà Nẵng (`da-nang`):** `293` total verified (`289` REC-A core + `4` outside core)
  - **Hạ Long (`ha-long`):** `188`
- **Secondary Verified POIs (`137`):** Hội An (`50`), Huế (`50`), Nha Trang (`33`), Đà Nẵng outside core (`4`)
- **Legacy `places_canonical.json` (`108` rows):** `97` sourced (`97` overlap with Freeze v2) + `11` unsourced legacy rows (`sources = []`)
- **Canonical ID Format:** `UUID (v4/v5 lowercase 36-char hyphenated string, e.g. 7d7e049e-d3f9-436a-aa1a-bf49ca0d1206)`
- **Upstream Source IDs in Freeze v2:** OSM `759/759` (`100.0%`), Overture `247/759` (`32.54%`)

---

## 3. POI Mapping Coverage & Review Corpus Inventory (Sections 4 & 5)

### 3.1 Review-to-POI Mapping Against Authoritative `gomate_places_freeze_v2.json` (`759` Verified POIs)

| Dataset | Total Rows | `EXACT_MAPPING` (by ID) | `HEURISTIC_MAPPING` (normalized city+name) | `UNMAPPED` (by ID / after heuristic) | Audit Finding |
|---|---:|---:|---:|---:|---|
| **Real Review Text Corpus** | `0` | `0` | `0` | `0` | Zero real review text exists in repository. |
| **Synthetic `reviews_curated.json`** | `9` | `0` | `3` | `9` by ID (`6` after heuristic) | All 8 `place_id` values in `reviews_curated.json` point to unsourced (`sources=[]`) rows in legacy `places_canonical.json` excluded from Freeze v2. |
| **`ViHoRec` (`560` hotels / `17,911` ratings)** | `17,911` (`560` hotels) | `0` hotels (`0` rows) | `2` hotels (`36` rows) | `560` hotels by ID (`558` hotels / `17,875` rows after exact name+city heuristic) | Opaque `H0000..H0559` IDs with no coordinates/OSM IDs and `0%` review text. |

### 3.2 City Coverage & Reviews-per-POI Statistics (Section 5)

- **Authoritative Real Review Text Coverage Across `759` Freeze v2 POIs (`622` Core POIs):**
  - Hà Nội: `0` reviews | Đà Nẵng: `0` reviews | Hạ Long: `0` reviews
  - Median / p25 / p50 / p75 / p90 reviews per POI: `0.0 / 0.0 / 0.0 / 0.0 / 0.0`
  - POIs with `0` reviews: `759/759` (`622/622` core); `1–4` reviews: `0`; `5–9` reviews: `0`; `10+` reviews: `0`; `20+` reviews: `0`.
- **Quarantined Synthetic Fixture (`reviews_curated.json`, `9` rows):**
  - Đà Nẵng: `4`, Hà Nội: `2`, Hạ Long: `0`, Hội An: `1`, Huế: `1`, Vùng sâu: `1`.
- **`ViHoRec` Rating-Only Interactions (`17,911` rows across `560` hotels, `0` review text):**
  - Hà Nội: `0` hotels (`0` rows) | Đà Nẵng: `71` hotels (`2260` rows) | Hạ Long: `0` hotels (`0` rows).
  - Interactions per hotel (`560` hotels): min=`1`, p25=`6.0`, median/p50=`17.0`, p75=`41.0`, p90=`83.0`, max=`308` (`0` with 0 ratings, `103` with 1–4, `104` with 5–9, `353` with 10+, `248` with 20+).

---

## 4. Review Field, Text, Language, Rating & Temporal Quality (Sections 6–10)

### 4.1 Field Missingness Percentage (Section 6)

| Field | `vietnam_travel_reviews.json` (`n=9`) | `reviews_curated.json` (`n=9`) | `vihorec/interactions.csv` (`n=17,911`) | `search_reviews.py` stub (`n=2`) |
|---|---:|---:|---:|---:|
| `review_id` | `100.00%` | `0.00%` | `100.00%` | `100.00%` |
| `poi_id` | `100.00%` | `11.11%` | `0.00%` | `100.00%` |
| `source` | `0.00%` | `0.00%` | `0.00%` | `100.00%` |
| `source_review_id` | `0.00%` | `0.00%` | `100.00%` | `100.00%` |
| `city` | `0.00%` | `0.00%` | `0.00%` | `100.00%` |
| `rating` | `0.00%` | `0.00%` | `0.00%` | `100.00%` |
| `review_text` | `0.00%` | `0.00%` | `100.00%` | `0.00%` |
| `language` | `100.00%` | `100.00%` | `100.00%` | `100.00%` |
| `created_at` | `100.00%` | `100.00%` | `0.00%` | `100.00%` |
| `author/anonymized_author` | `100.00%` | `100.00%` | `0.00%` | `100.00%` |
| `source_url/source_ref` | `100.00%` | `100.00%` | `100.00%` | `100.00%` |
| `collected_at` | `100.00%` | `100.00%` | `100.00%` | `100.00%` |
| `provenance` | `0.00%` | `0.00%` | `0.00%` | `0.00%` |

### 4.2 Text, Language, Rating & Temporal Quality Summary (Sections 7–10)

- **Text Quality (`reviews_curated.json`, `9` synthetic rows):** empty=`0`, whitespace-only=`0`, `<20` chars=`0`, `>2000` chars=`0`, exact duplicates=`0`, normalized duplicates=`0`, near-duplicates=`0`, HTML/Unicode issues=`0`. Char length: min=`85`, p25=`168.0`, p50=`176.0`, p75=`180.0`, p90=`185.8`, max=`189` (word length p50=`40.0`).
- **Language Distribution (deterministic offline):** `reviews_curated.json`: Vietnamese=`9`, English=`0`, mixed=`0`, unknown=`0`; `search_reviews.py` stub: English=`2`; Wikivoyage non-review guide chunks: English=`464`.
- **Rating Quality & Scale Incompatibility:** `gomate_places_freeze_v2.json` has `100%` null ratings (`759/759`); synthetic `reviews_curated.json` uses a `1.0–5.0` scale (mean=`4.5`, median=`4.5`); `ViHoRec` uses a `1.0–10.0` OTA hotel scale (mean=`7.5765`, median=`8.0`, missing=`0`, invalid=`0`). Rating scales differ (`scales_differ_between_sources = true`); no normalization performed in W07-0.
- **Temporal Audit:** `reviews_curated.json` is `100.0%` missing dates; `ViHoRec` spans `2011-10-15` to `2023-12-09` (`0%` missing, `0` invalid/future dates) but has `0%` review text. Recency-aware review-text retrieval is **not possible** on current data.

---

## 5. Provenance & Synthetic Data Firewall (Sections 11 & 12)

- **`REAL_REVIEW_DATA` (text reviews):** `0` rows (`ViHoRec` has `17911` real rating-only rows with `0` text).
- **`SYNTHETIC_REVIEW_DATA`:** `9` rows in `vietnam_travel_reviews.json` / `reviews_normalized.json` / `reviews_curated.json` + `2` stub strings in `search_reviews.py` + `300` synthetic user preference profiles (`seed=42`). Quarantined by `data/manifests/review-provenance.json` (`UNVERIFIED_SYNTHETIC`).
- **`UNKNOWN_PROVENANCE`:** `0` review rows (`123` legacy seed places in DB / `11` unsourced rows in `places_canonical.json` excluded from Freeze v2).

---

## 6. Gaps & W07 RAG Readiness Status (Sections 13 & 14)

- **`RAG_READINESS_STATUS`:** `NOT_READY`
- **Primary Gaps:**
  1. `0` real provenanced review text records exist across all `759` verified OSM POIs (`622` core POIs in Hà Nội, Đà Nẵng, Hạ Long).
  2. Hạ Long has `0` reviews even in the synthetic test fixture and `0` hotels in `ViHoRec`.
  3. `40–60` multi-aspect evaluation queries and human relevance judgments cannot be constructed from `0` real reviews.
- **Recommended Retrieval Unit (Section 13):** **`one review = one retrieval unit`** (`one_review_equals_one_retrieval_unit`), preserving `review_id`, `poi_id`, `rating`, `created_at`, and aspect sentiment without fragmenting short reviews.

---

## 7. Proposed Retrieval Architecture & Technology Decision Matrix (Section 15)

- **Measurement Hygiene (`PLANNING_ESTIMATE_NOT_MEASURED`):** All latency, RAM, and workload figures in Section 15 and Section 16 are strictly labelled PLANNING_ESTIMATE_NOT_MEASURED and must NOT be cited as experimental W07 evidence.
- **Winner Frozen in W07-0:** `False` (`PROVISIONAL_SHORTLIST_NO_WINNER_FROZEN`)
- **Lexical Baseline:** `BM25 (rank_bm25 / BM25Okapi with Vietnamese-aware tokenization & accent-preserving + accent-folded dual fields)` (`PLANNING_ESTIMATE_NOT_MEASURED`)
- **Dense Multilingual/Vietnamese Provisional Shortlist (no large models downloaded in W07-0):**
  - `intfloat/multilingual-e5-small` — Multilingual E5 (118M params, 384d) (Strong multilingual retrieval alignment (query/passage prefix protocol); `PLANNING_ESTIMATE_NOT_MEASURED: compact local CPU bi-encoder (approx. <500 MB RAM class)`)
  - `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — Multilingual MiniLM (118M params, 384d) (Solid baseline multilingual semantic similarity; `PLANNING_ESTIMATE_NOT_MEASURED: compact local CPU bi-encoder (approx. <500 MB RAM class)`)
  - `bkai-foundation-models/vietnamese-bi-encoder` — PhoBERT-based Vietnamese Bi-Encoder (135M params, 768d) (Native Vietnamese segmentation & semantics; `PLANNING_ESTIMATE_NOT_MEASURED: local CPU bi-encoder (approx. ~600 MB RAM class); weaker on English/mixed queries`)
  - `BAAI/bge-m3` — BGE-M3 multilingual dense+sparse (568M params, 1024d) (High-accuracy Vietnamese + cross-lingual retrieval; `PLANNING_ESTIMATE_NOT_MEASURED: heavier model class (approx. ~2.2 GB RAM class); optional for 300-1,650 docs`)
- **Hybrid Retrieval:** `Evaluate RRF and convex score fusion over BM25 + top dense bi-encoder; particularly effective for Vietnamese queries mixing exact POI/food terms with semantic aspect intent.` (`PLANNING_ESTIMATE_NOT_MEASURED`)
- **Reranker Assessment:** `OPTIONAL_FOR_ABLATION` (`PLANNING_ESTIMATE_NOT_MEASURED`) — For a 300-1,650 review corpus with poi_id/city metadata pre-filtering, bi-encoder + BM25 hybrid already retrieves from a small candidate pool (5-15 reviews per POI). A lightweight multilingual cross-encoder top-20 -> top-5 reranker is optional for scientific ablation in W07.
- **Index / Vector Store Recommendation:**
  - **Offline Scientific Benchmark:** Local in-memory `FAISS IndexFlatIP` / exact NumPy cosine + `rank_bm25` (`PLANNING_ESTIMATE_NOT_MEASURED`, 100% exact recall, zero server overhead, deterministic artifact hashes).
  - **Application Integration:** Existing `PostgreSQL + pgvector` (`documents` table in `schema.prisma`; `PLANNING_ESTIMATE_NOT_MEASURED`); `Qdrant` is `NOT_NEEDED`.

---

## 8. Infrastructure Readiness & Decision Categories (Sections 16, 17 & 19)

| Infrastructure Item | Classification | Measurement Hygiene | Purpose / Notes |
|---|---|---|---|
| `cpu_only` | `REQUIRED` | `PLANNING_ESTIMATE_NOT_MEASURED` | Run offline data pipelines, BM25, compact multilingual bi-encoders (<=135M params), FAISS/NumPy exact search, and deterministic evaluation tests. |
| `local_gpu` | `OPTIONAL` | `PLANNING_ESTIMATE_NOT_MEASURED` | Accelerate larger embedding/reranker ablations (e.g., BGE-M3) if tested. |
| `google_colab` | `OPTIONAL` | `PLANNING_ESTIMATE_NOT_MEASURED` | Free T4 GPU fallback if benchmarking heavier 560M+ parameter bi-encoders/rerankers and exporting frozen embeddings. |
| `paid_gpu` | `NOT_NEEDED` | `PLANNING_ESTIMATE_NOT_MEASURED` | None for W07 corpus scale (300-1,650 reviews). |
| `vps` | `NOT_NEEDED` | `PLANNING_ESTIMATE_NOT_MEASURED` | W07 retrieval evaluation and offline benchmarking run 100% locally. |
| `vector_db_server` | `NOT_NEEDED` | `PLANNING_ESTIMATE_NOT_MEASURED` | In-memory FAISS/NumPy handles offline W07 scientific benchmarking; existing local PostgreSQL/pgvector handles app integration. |
| `redis` | `NOT_NEEDED` | `PLANNING_ESTIMATE_NOT_MEASURED` | Not needed for W07 review corpus curation or offline retrieval benchmarking. |
| `paid_embedding_api` | `NOT_NEEDED` | `PLANNING_ESTIMATE_NOT_MEASURED` | Open-weight multilingual/Vietnamese sentence-transformers run locally for free with higher reproducibility. |
| `llm_api` | `OPTIONAL` | `PLANNING_ESTIMATE_NOT_MEASURED` | Not needed now (W07-0 and retrieval benchmarking are 100% offline/extractive). Only optional in a later synthesis stage if generative review summarization is evaluated alongside extractive aspect synthesis. |

### Explicit Boolean Decision Flags (Section 19) & API / Acquisition Firewall (Section 17)

- `CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07 = false`
- `ADDITIONAL_REVIEW_DATA_REQUIRED = true`
- `HUMAN_LABELING_REQUIRED = true`
- `GPU_REQUIRED_NOW = false`
- `SERVER_REQUIRED_NOW = false`
- `VECTOR_DB_SERVER_REQUIRED_NOW = false`
- `PAID_EMBEDDING_API_REQUIRED = false`
- `LLM_API_REQUIRED_NOW = false`
- `NEW_LLM_PROVIDER_CALLS = 0`
- `NEW_REVIEW_DATA_ACQUIRED = 0`

---

## 9. Corrected Review Data Acquisition Specification & Feasibility Queue (Section 20 — Corrective 01)

### 9.1 Official API Feasibility Corrections (Sections 2 & 3 of Corrective 01)

- **Google Places API:**
  - `GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5` (cannot satisfy a `10–15` reviews/POI target by itself).
  - `GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW` (Google Maps Platform Places policies restrict pre-fetching/caching/storage of Places content except documented exceptions such as place IDs; may be considered later for live/runtime enrichment, UI display, and place mapping, but must NOT automatically become the frozen scientific W07 corpus).
- **Tripadvisor Content API:**
  - `TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = NOT_RECOMMENDED` (exposes only a small number of reviews/location, intended for consumer-facing B2C apps, and academic research access is not supported under normal Content API eligibility; excluded as primary W07 scientific review-corpus acquisition plan).

### 9.2 Three-Tier Corpus Acquisition Targets (Section 4 of Corrective 01)

| Tier | Canonical POIs | City Balance | Reviews / POI | Total Usable Reviews | Role |
|---|---|---|---|---|---|
| **Scientific Minimum** | `>= 60` | Balanced across all 3 thesis cities (~20 POIs/city: Hà Nội ~20, Đà Nẵng ~20, Hạ Long ~20) | `>= 5` | `>= 300` | Minimum dataset allowed to begin W07 retrieval science |
| **Preferred** | `75-100` | Approximately balanced across Hà Nội, Đà Nẵng, Hạ Long and core POI categories | `8-12` | `600-1,200` | Recommended balanced benchmark target |
| **Stretch** | `~110` | Balanced across 3 core cities | `10-15` | `1,100-1,650` | Stretch target only — explicitly NOT a prerequisite for starting W07 |

### 9.3 Ranked Candidate Source Classes (Section 5 of Corrective 01)

- **Tier A (`PREFERRED_PRIMARY_SCIENTIFIC_CORPUS`):** Public/research-permitted datasets containing review text, place/business identity, city/address and preferably coordinates, provenance, usage/license permitting research, and enough metadata for deterministic or audited mapping to GoMate canonical POIs.
- **Tier B (`ACCEPTABLE_PRIMARY_SCIENTIFIC_CORPUS`):** Owner-curated or research-collected reviews where reuse rights are clear, provenance is recorded, source reference is retained, and exact canonical POI mapping is possible.
- **Tier C (`RUNTIME_ENRICHMENT_ONLY_NOT_PERSISTENT_FROZEN_CORPUS`):** Official APIs usable for runtime enrichment but unsuitable as a persistent frozen research corpus under standard terms. Google Places belongs here unless storage/research rights are independently established.
- **Excluded (`FORBIDDEN_FOR_PRIMARY_POI_RAG_AUTHORITY`):** synthetic review generation for scientific evaluation; unprovenanced scraped text; datasets with no review text (e.g., ViHoRec ratings-only); anonymous text-only sentiment corpora as the primary POI-grounded RAG corpus.

### 9.4 Candidate Dataset Feasibility Queue (Section 6 of Corrective 01 — Research Candidates Only)

| Slot | Dataset | Status | Notes / Required Next Checks |
|---|---|---|---|
| **Candidate A** | `ThanThoai9x/vietnamese-food-images` | `PROMISING_BUT_NOT_YET_APPROVED` | ~`1989` unique places; fields: `place_name, address, lat, lng, review_id, review_rating, text, review_url, crawled_at`. Next checks: gated access, exact license/reuse terms, Google-origin implications, Hà Nội coverage, Đà Nẵng coverage, Hạ Long coverage, number of text reviews, number of unique POIs, coordinate mapping rate to Freeze v2. |
| **Candidate B** | `pqthinh232/vietnamese-restaurant-review-sentiment-dataset` | `AUXILIARY_TEXT_DATA_ONLY` | Large Vietnamese restaurant-review corpus, but currently exposed fields do not provide sufficient POI identity/location metadata for canonical POI RAG. Potential use: linguistic robustness, sentiment auxiliary experiment. |
| **Candidate C** | `VLSP2018-ABSA-Restaurant` | `AUXILIARY_ABSA_DATASET` | Do not use as canonical POI review corpus unless deterministic POI identity unexpectedly exists. Potential use: aspect extraction, sentiment evaluation, query/aspect vocabulary development. |

### 9.5 Canonical POI Mapping Requirements & Target 17-Field Schema (Sections 7 & 8 of Corrective 01)

- **Mapping Support Required:** `EXACT_MAPPING` or `AUDITED_HIGH_CONFIDENCE_GEO_ENTITY_RESOLUTION`.
- **Preferred Mapping Evidence Hierarchy:** (1) exact upstream POI ID; (2) coordinates + normalized name + city/address; (3) manual verification for ambiguous cases.
- **Strict Rule:** Name-only automatic linking is **forbidden** as scientific authority (`name_only_automatic_linking_forbidden = true`). Every final review row must carry canonical `poi_id` from `data/curated/gomate_places_freeze_v2.json`.
- **Target 17 Schema Fields:** `review_id, poi_id, upstream_place_id, city, source, source_review_id, rating, rating_scale_max, review_text, language, created_at, collected_at, source_ref / review_url, provenance, license_or_usage_class, mapping_method, mapping_confidence` (do not fabricate missing upstream fields).
