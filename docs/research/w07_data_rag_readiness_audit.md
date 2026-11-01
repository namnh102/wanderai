# W07-0 — Data + RAG Readiness Audit Report

## 0. Gate & Lineage Metadata

- **Task ID:** `W07-0-DATA-RAG-READINESS-AUDIT`
- **Previous Gate:** `W06-SCIENTIFIC-CLOSURE-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Authoritative Base Commit:** `develop@bdd4810de0bc03ef52c67cc112e09d5787a7ffad`
- **W06 Closure Status:** `CLOSED_UNMODIFIED`
- **Next Gate:** `W07-DATA-RAG-READINESS-AUDIT-CHATGPT-AUDIT`
- **JSON Artifact Internal SHA256:** `c5728d6249a1f99c1f1f3309d041023562f7954cb8a739302edab7aa3298a58c`

---

## 1. Exact Data Inventory (Section 3)

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

- **Lexical Baseline:** `BM25 (rank_bm25 / BM25Okapi with Vietnamese-aware tokenization & accent-preserving + accent-folded dual fields)`
- **Dense Multilingual/Vietnamese Shortlist (no large models downloaded in W07-0):**
  - `intfloat/multilingual-e5-small` — Multilingual E5 (118M params, 384d) (Strong multilingual retrieval alignment (query/passage prefix protocol); Fast on local CPU (~15-30 ms/query, <500 MB RAM))
  - `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — Multilingual MiniLM (118M params, 384d) (Solid baseline multilingual semantic similarity; Very fast on local CPU (<500 MB RAM))
  - `bkai-foundation-models/vietnamese-bi-encoder` — PhoBERT-based Vietnamese Bi-Encoder (135M params, 768d) (Native Vietnamese segmentation & semantics; Fast on local CPU (~600 MB RAM); weaker on English/mixed queries)
  - `BAAI/bge-m3` — BGE-M3 multilingual dense+sparse (568M params, 1024d) (High-accuracy Vietnamese + cross-lingual retrieval; Heavier on CPU (~2.2 GB RAM); best run on Colab/local GPU if benchmarked, optional for 1.5k-3k docs)
- **Hybrid Retrieval:** `Evaluate RRF and convex score fusion over BM25 + top dense bi-encoder; particularly effective for Vietnamese queries mixing exact POI/food terms with semantic aspect intent.`
- **Reranker Assessment:** `OPTIONAL_FOR_ABLATION` — For a 1,200-3,000 review corpus with poi_id/city metadata pre-filtering, bi-encoder + BM25 hybrid already retrieves from a small candidate pool (10-50 reviews per POI). A lightweight multilingual cross-encoder top-20 -> top-5 reranker is worth a scientific ablation in W07 only if CPU latency stays reasonable.
- **Index / Vector Store Recommendation:**
  - **Offline Scientific Benchmark:** Local in-memory `FAISS IndexFlatIP` / exact NumPy cosine + `rank_bm25` (100% exact recall, zero server overhead, deterministic artifact hashes).
  - **Application Integration:** Existing `PostgreSQL + pgvector` (`documents` table in `schema.prisma`); `Qdrant` is `NOT_NEEDED`.

---

## 8. Infrastructure Readiness & Decision Categories (Sections 16, 17 & 19)

| Infrastructure Item | Classification | Purpose / Notes |
|---|---|---|
| `cpu_only` | `REQUIRED` | Run offline data pipelines, BM25, compact multilingual bi-encoders (<=135M params), FAISS/NumPy exact search, and deterministic evaluation tests. |
| `local_gpu` | `OPTIONAL` | Accelerate larger embedding/reranker ablations (e.g., BGE-M3) if tested. |
| `google_colab` | `OPTIONAL` | Free T4 GPU fallback if benchmarking heavier 560M+ parameter bi-encoders/rerankers and exporting frozen embeddings. |
| `paid_gpu` | `NOT_NEEDED` | None for W07 corpus scale (1,200-3,000 reviews). |
| `vps` | `NOT_NEEDED` | W07 retrieval evaluation and offline benchmarking run 100% locally. |
| `vector_db_server` | `NOT_NEEDED` | In-memory FAISS/NumPy handles offline W07 scientific benchmarking; existing local PostgreSQL/pgvector handles app integration. |
| `redis` | `NOT_NEEDED` | Not needed for W07 review corpus curation or offline retrieval benchmarking. |
| `paid_embedding_api` | `NOT_NEEDED` | Open-weight multilingual/Vietnamese sentence-transformers run locally for free with higher reproducibility. |
| `llm_api` | `OPTIONAL` | Not needed now (W07-0 and retrieval benchmarking are 100% offline/extractive). Only optional in a later synthesis stage if generative review summarization is evaluated alongside extractive aspect synthesis. |

### Explicit Boolean Decision Flags (Section 19) & API Firewall (Section 17)

- `CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07 = false`
- `ADDITIONAL_REVIEW_DATA_REQUIRED = true`
- `HUMAN_LABELING_REQUIRED = true`
- `GPU_REQUIRED_NOW = false`
- `SERVER_REQUIRED_NOW = false`
- `VECTOR_DB_SERVER_REQUIRED_NOW = false`
- `PAID_EMBEDDING_API_REQUIRED = false`
- `LLM_API_REQUIRED_NOW = false`
- `NEW_LLM_PROVIDER_CALLS = 0`

---

## 9. Concrete Review Data Acquisition Specification & Required User Actions (Section 20)

- **Target Priority Canonical POIs:** `110 priority canonical POIs (range 90-150, deterministically pre-selected from gomate_places_freeze_v2.json by place_id)`
  - **Hà Nội (`ha-noi`):** `35` POIs × `10–15` reviews/POI = `350–525` reviews
  - **Đà Nẵng (`da-nang`):** `45` POIs × `10–15` reviews/POI = `450–675` reviews
  - **Hạ Long (`ha-long`):** `30` POIs × `10–15` reviews/POI = `300–450` reviews
- **POI Category Mix:** `attraction / culture / temple / museum / nature / beach (~40% of selected POIs); restaurant / cafe / market / nightlife (~35% of selected POIs); hotel (~25% of selected POIs)`
- **Expected Total Rows:** `1,100 to 1,650 review rows (acceptable range 1,000-2,500 rows)`
- **Minimum Required Fields:** `review_id (deterministic UUID), poi_id (exact canonical place_id from gomate_places_freeze_v2.json), osm_source_id (exact node/way/relation ID from gomate_places_freeze_v2.json), city (ha-noi | da-nang | ha-long), source (provider/dataset identifier), source_review_id (upstream review identifier or hash), rating (numeric, with explicit rating_scale_max e.g. 5.0 or 10.0), review_text (non-empty UTF-8 review text, >= 15 words preferred), language (vi | en | mixed_vi_en), created_at (ISO-8601 date/timestamp or explicit null if unavailable upstream), collected_at (ISO-8601 UTC collection timestamp), provenance (license/source lineage classification)`
- **Preferred Sources:** Official POI-bound API review retrieval (e.g., Google Places API (New) / TripAdvisor Content API under free credit with explicit canonical `place_id` binding) or provenance-verified datasets deterministically linked to Freeze v2 `place_id`.
- **Acceptable Alternative Sources:** Structured owner-collected/curated verbatim review dataset for the 110 pre-selected Freeze v2 `place_id` targets with full provenance manifest, collection timestamps, and human relevance labels for `40–60` evaluation queries.
