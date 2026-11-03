# W07-A4P — Permitted Public Review Acquisition Report

## 1. Authority & Scope

- **Task ID:** `W07-A4P-PERMITTED-PUBLIC-REVIEW-ACQUISITION`
- **Authoritative Base:** `develop@40d9908b52214967bf412f5caf2f06cc866da409`
- **Previous Accepted Gate:** `W07-A4H-ASSISTED-FIRST-PARTY-COLLECTION-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Next Gate:** `W07-A4P-PERMITTED-PUBLIC-REVIEW-ACQUISITION-CHATGPT-AUDIT`
- **Frozen W07-A2 60-POI Manifest SHA256:** `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`
- **Outcome Classification:** `OUTCOME_C_ZERO_SUITABLE_PUBLIC_REVIEWS_FOUND`
- **Scientific Outcome Statement:** No suitable public review was found among the investigated sources under the frozen W07 rules.

## 2. Executive Summary (Outcome C)

No suitable public review was found among the investigated sources under the frozen W07 rules. Across 18 investigated public sources (10 newly discovered and audited in W07-A4P across Zenodo, Hugging Face, and GitHub plus 8 sources re-verified from W07-A1), 300,536 raw rows and 186,170 unique review texts were examined. Every source with real review text either: (a) stripped all place names, coordinates, and cities prior to publication (`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, `mendeley:10.17632/dp8s59xnb7.1`, `pqthinh232`, `hienbm`, `Foody_review_nlp`), (b) contained zero geographic overlap with the 60 frozen POIs in Hà Nội, Đà Nẵng, and Hạ Long (`zenodo:10.5281/zenodo.7967494` with 62,887 TripAdvisor hotel reviews across 1,497 hotels in Phú Quốc, Phong Nha, Cam Ranh, etc., and `ThanThoai9x/vietnamese-food-images` with 100% Hồ Chí Minh City rows), or (c) lacked a valid reuse license (`QUARANTINE_REUSE_UNCLEAR`). Scientific provenance and mapping standards were preserved without compromise, yielding `PUBLIC_REVIEWS_ACCEPTED = 0`. First-party collection via W07-A3 Google Forms and W07-A4H Assisted Collection remains the sole primary source for the 60-POI / 300-review corpus.

- `PUBLIC_REVIEWS_DISCOVERED`: `300536`
- `PUBLIC_UNIQUE_REVIEWS`: `186170`
- `PUBLIC_REVIEWS_ACCEPTED`: `0`
- `PUBLIC_REVIEWS_REJECTED`: `124898`
- `PUBLIC_REVIEWS_QUARANTINED`: `61272`
- `SOURCES_WITH_QUARANTINE_STATUS`: `11`
- `REVIEW_BEARING_QUARANTINED_SOURCES`: `3`
- `QUARANTINED_UNIQUE_REVIEW_COUNT`: `61272`
- `PUBLIC_POIS_COVERED`: `0 / 60`
- `NEW_SOURCE_DOWNLOADS`: `0`
- `BULK_SCRAPING_EXECUTED`: `false`
- `LLM_GENERATED_PUBLIC_REVIEWS`: `0`
- `NEW_LLM_PROVIDER_CALLS`: `0`
- `CORPUS_SCIENTIFIC_MINIMUM_READY`: `false`

### 2.1 Global Accounting & Quarantine Semantics

- **Global Unique Review Equation:** `186170 = 0 (accepted) + 124898 (rejected) + 61272 (quarantined)`
- **Sources Carrying a Quarantine Status (`SOURCES_WITH_QUARANTINE_STATUS = 11`):** 11 sources total (`8` zero-review or geography-rejected sources plus `3` review-bearing quarantined sources).
- **Review-Bearing Quarantined Sources (`REVIEW_BEARING_QUARANTINED_SOURCES = 3`, `QUARANTINED_UNIQUE_REVIEW_COUNT = 61272`):**
  1. `huggingface:pqthinh232/vietnamese-restaurant-review-sentiment-dataset`: `32,713` quarantined unique reviews (`QUARANTINE_REUSE_UNCLEAR` + unmappable).
  2. `huggingface:hienbm/tripadvisor_vietnam`: `23,559` quarantined unique reviews (`QUARANTINE_REUSE_UNCLEAR` + unmappable).
  3. `github:NguyenDucHuy14287/Foody_review_nlp`: `5,000` quarantined unique reviews (`QUARANTINE_REUSE_UNCLEAR` + unmappable).

## 3. Investigated Public Sources (18 Total: 10 New in W07-A4P + 8 Re-Verified from W07-A1)

| # | Source ID | Stage | License | Classification | Quarantine | Raw Rows | Unique Reviews | Accepted | Rejected | Quarantined | POIs Covered |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | `zenodo:10.5281/zenodo.7967494` | `W07-A4P` | `CC-BY-4.0 (declared on Zenodo metadata; upstream origin TripAdvisor Vietnam)` | `AUXILIARY_ONLY` | `NONE` | 62887 | 62887 | 0 | 62887 | 0 | 0 |
| 2 | `huggingface:trungtrandinh/hotel_danang_vietnam` | `W07-A4P` | `UNSPECIFIED_ON_HF_CARD` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 7000 | 0 | 0 | 0 | 0 | 0 |
| 3 | `huggingface:AnnBae6969/vietnam-tourism-dataset` | `W07-A4P` | `UNSPECIFIED_ON_HF_CARD` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 100 | 0 | 0 | 0 | 0 | 0 |
| 4 | `huggingface:Bach293/dulich_hanoi` | `W07-A4P` | `UNSPECIFIED_ON_HF_CARD` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 200 | 0 | 0 | 0 | 0 | 0 |
| 5 | `huggingface:VLAI-AIVN/vietnamtourism-instruction-dataset` | `W07-A4P` | `license:other (gated access)` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | `github:HongTin2104/VietNam-Travel-Recommendation-System` | `W07-A4P` | `MIT` | `REJECTED_SOURCE` | `NONE` | 315 | 0 | 0 | 0 | 0 | 0 |
| 7 | `github:1109inc/vietnam-travel-dataset` | `W07-A4P` | `UNSPECIFIED_NO_LICENSE_FILE` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 360 | 0 | 0 | 0 | 0 | 0 |
| 8 | `github:koshiroquoc/DaNangtourguide` | `W07-A4P` | `UNSPECIFIED_NO_LICENSE_FILE (Wikivoyage overlay CC-BY-SA-4.0)` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 200 | 0 | 0 | 0 | 0 | 0 |
| 9 | `github:hanhlevna/Manhos` | `W07-A4P` | `UNSPECIFIED_NO_LICENSE_FILE` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 8500 | 0 | 0 | 0 | 0 | 0 |
| 10 | `github:NguyenDucHuy14287/Foody_review_nlp` | `W07-A4P` | `UNSPECIFIED_NO_LICENSE_FILE` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 5000 | 5000 | 0 | 0 | 5000 | 0 |
| 11 | `huggingface:phamluan/vn_msa_sar_v3` | `W07-A1_REVERIFIED_IN_A4P` | `CC-BY-4.0 (declared on HF dataset card)` | `AUXILIARY_ONLY` | `NONE` | 76785 | 18609 | 0 | 18609 | 0 | 0 |
| 12 | `huggingface:visolex/VLSP2018-ABSA` | `W07-A1_REVERIFIED_IN_A4P` | `VLSP Academic Shared Task Terms (unspecified on HF mirrors)` | `AUXILIARY_ONLY` | `NONE` | 10351 | 10351 | 0 | 10351 | 0 | 0 |
| 13 | `huggingface:pqthinh232/vietnamese-restaurant-review-sentiment-dataset` | `W07-A1_REVERIFIED_IN_A4P` | `UNSPECIFIED_ON_HF_CARD` | `AUXILIARY_ONLY` | `QUARANTINE_REUSE_UNCLEAR` | 32713 | 32713 | 0 | 0 | 32713 | 0 |
| 14 | `mendeley:10.17632/dp8s59xnb7.1` | `W07-A1_REVERIFIED_IN_A4P` | `CC-BY-4.0` | `AUXILIARY_ONLY` | `NONE` | 20551 | 20551 | 0 | 20551 | 0 | 0 |
| 15 | `huggingface:hienbm/tripadvisor_vietnam` | `W07-A1_REVERIFIED_IN_A4P` | `UNSPECIFIED_ON_HF_CARD` | `AUXILIARY_ONLY` | `QUARANTINE_REUSE_UNCLEAR` | 23559 | 23559 | 0 | 0 | 23559 | 0 |
| 16 | `huggingface:ThanThoai9x/vietnamese-food-images` | `W07-A1_REVERIFIED_IN_A4P` | `CC-BY-NC-4.0 (declared on HF card; upstream Google Maps ToS ambiguous)` | `REJECTED_SOURCE` | `QUARANTINE_REUSE_UNCLEAR` | 34104 | 12500 | 0 | 12500 | 0 | 0 |
| 17 | `huggingface:MinhDS/ViHoRec` | `W07-A1_REVERIFIED_IN_A4P` | `CC-BY-NC-4.0` | `REJECTED_SOURCE` | `NONE` | 17911 | 0 | 0 | 0 | 0 | 0 |
| 18 | `commercial_platforms:google_maps_tripadvisor_booking_agoda_foody` | `W07-A1_REVERIFIED_IN_A4P` | `Proprietary Commercial Platform Terms of Service (No Offline Corpus Caching / Bulk Scraping Forbidden)` | `REJECTED_SOURCE` | `NONE` | 0 | 0 | 0 | 0 | 0 | 0 |

## 4. Key Empirical Findings from W07-A4P Broad Discovery

1. **Zenodo Record `7967494` (`10.5281/zenodo.7967494` — *TripAdvisor Vietnam Hotel Reviews*, CC-BY-4.0):**
   - Both published CSV files (`hotel_coordinate.csv`: `263,557` bytes, MD5 `50fa8970a26ae513b8295bbcdfacd0b0`, `3,910` hotels; `Reviews.csv`: `64,460,152` bytes, MD5 `ebae7b018af787978b29cf15591b7e96`, `62,887` rows / `62,887` unique review IDs across `1,497` hotels) were inspected in full.
   - Despite the record abstract mentioning Hanoi and Da Nang, `Reviews.csv` contains `0` reviews for hotels in `Hà Nội`, `Đà Nẵng`, or `Hạ Long` (its `62,887` reviews are concentrated in Phú Quốc `17,781`, Cù Dù/Lăng Cô `3,407`, Phong Nha-Kẻ Bàng `3,354`, Cam Hải Đông/Cam Ranh `4,450`, Ninh Vân `2,788`, Điện Bàn `2,340`, etc.), and `0` hotels in `Reviews.csv` match any of the 60 frozen canonical POIs by ID, coordinate (`<=500m`), or name.
2. **Newly Discovered Hugging Face Datasets (`trungtrandinh/hotel_danang_vietnam`, `AnnBae6969/vietnam-tourism-dataset`, `Bach293/dulich_hanoi`, `VLAI-AIVN/vietnamtourism-instruction-dataset`):**
   - Consist of synthetic instruction-tuning hotel price/amenity templates (`7,000` rows), chatbot Q&A pairs (`100` rows), English image captions (`200` rows), or gated LLaVA VQA samples (`HTTP 401`), with `0` real first-hand visitor reviews and unspecified/restricted licenses.
3. **Newly Discovered GitHub Repositories (`HongTin2104/VietNam-Travel-Recommendation-System`, `1109inc/vietnam-travel-dataset`, `koshiroquoc/DaNangtourguide`, `hanhlevna/Manhos`, `NguyenDucHuy14287/Foody_review_nlp`, `anh147/Foody-Review-Sentiment-With-LSTM`):**
   - Either contain only editorial destination catalogs / numeric aspect counts (`0` review text) or unlicensed Foody.vn comment scrapes (`QUARANTINE_REUSE_UNCLEAR`) with `100%` missing restaurant names, addresses, cities, and coordinates.
   - For `github:koshiroquoc/DaNangtourguide`, row counts are explicitly reconciled across all three repository artifacts: `review_relevant_row_count = 200` (curated 200-place Đà Nẵng evaluation subset inspected for review text), `primary_csv_row_count = 299` (`Data/data_danang_ok.csv`), and `broader_source_row_count = 2557` (`Data/processed/places_enriched_v2.jsonl`), with `unique_reviews = 0` across all three.
4. **`CC-BY-NC-4.0` License Compatibility vs. Scientific Usability (`LICENSE_CONDITIONALLY_COMPATIBLE != SOURCE_SCIENTIFICALLY_USABLE`):**
   - `CC-BY-NC-4.0` is classified as `LICENSE_CONDITIONALLY_COMPATIBLE_FOR_NONCOMMERCIAL_ACADEMIC_USE` for non-commercial academic thesis research rather than universally forbidden.
   - `huggingface:MinhDS/ViHoRec` (`CC-BY-NC-4.0`) is conditionally license-compatible, but `source_scientifically_usable = false` for the W07 review corpus because it contains `17,911` numeric user-hotel ratings and `0` user review texts.
   - `huggingface:ThanThoai9x/vietnamese-food-images` (`CC-BY-NC-4.0` declared on HF card) is marked `source_scientifically_usable = false` because `100.0%` of its rows are in Hồ Chí Minh City (`0` in Hà Nội, Đà Nẵng, or Hạ Long), parquet access is manually gated (`HTTP 401`), and upstream Google Maps ToS provenance is ambiguous.

## 5. Mapping Hierarchy, Deduplication, Candidate Integrity & Provenance Firewall

- **Allowed Mapping Methods:** `EXACT_UPSTREAM_ID`, `GEO_NAME_HIGH_CONFIDENCE` (`<= 150m` Haversine distance + normalized name similarity `>= 0.60`), `MANUAL_VERIFIED`.
- **Rejected Mapping Methods:** `NAME_ONLY_AUTOMATIC`, `UNMAPPABLE`.
- **Rating Scale Integrity (Corrective B1):** Upstream `rating` and `rating_scale_max` are preserved without rescaling in A4P. Missing `rating_scale_max` is never defaulted to `5`; if `rating` exists without a valid `rating_scale_max`, `rating_scale_max` remains `None` and the row is quarantined as `QUARANTINE_RATING_SCALE_UNKNOWN` before primary acceptance.
- **Source Locator Provenance (Corrective B2):** Every accepted public candidate requires either an explicit upstream locator (`https://...`, `http://...`, `doi:...`, or `dataset:<source_id>#review_id:<source_review_id>`) or a deterministic internal locator `dataset:<source_id>#review_id:<source_review_id>` derived from a real `source_id` and stable upstream `source_review_id`. Index-only fallbacks (`source#0`) are rejected and quarantined as `QUARANTINE_PROVENANCE_LOCATOR_INSUFFICIENT`.
- **Deduplication:** Collapses multi-photo rows sharing `(source, source_review_id)` before counting unique reviews, then deduplicates on `source_review_id`, normalized `review_text`, and `(poi_id, normalized_review_text)`.
- **Human/Public Provenance Firewall:** Public reviews never receive `FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1` or `FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1` and never carry a first-party `consent_record_id`.
- **Restricted Storage Separation:** Public candidate output (`data/restricted/w07_reviews/w07_public_candidate_reviews_v1.jsonl`) is strictly isolated from Google Form (`w07_google_form_candidate_reviews_v1.jsonl`) and Assisted (`w07_assisted_candidate_reviews_v1.jsonl`) candidate corpora.
