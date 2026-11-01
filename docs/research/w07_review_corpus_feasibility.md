# W07-A1 — Public Review Corpus Feasibility + Acquisition Decision

## 0. Authority & Gate Discipline

- **Previous Gate:** `W07-DATA-RAG-READINESS-AUDIT-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Authoritative Base:** `develop@6eb131c5c933aa62026bc2c6a9337d0da3510781`
- **W06 Closure Status:** `CLOSED_IMMUTABLE` (verified internal SHA256: `7dec87d9b318165ba5233d1470df8f12dfbe99449bceabb86dc2322aaab89e12`)
- **W07-0 Readiness Audit Status:** `COMPLETE_IMMUTABLE` (verified internal SHA256: `7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9`, verified LF file SHA256: `2727cb23ea63af6eada16deba558a82f6329b13ebccb09133c32042466bd2b16`)
- **Artifact Internal SHA256:** `6658b23c4f58f9dd05b7739e20eb7bd0543ed93f8dea76010e4ec3639eae6442`
- **Next Gate:** `W07-A1-REVIEW-CORPUS-FEASIBILITY-CHATGPT-AUDIT`

---

## 1. Broad Public Search & Candidate Evaluation Matrix

We audited public and research-accessible Vietnamese travel, hospitality, and restaurant review datasets across Hugging Face Datasets (`datasets-server` + dataset cards), Mendeley Data (`DOI: 10.17632/dp8s59xnb7.1`), Kaggle, GitHub, and VLSP shared tasks:

| Rank | Dataset ID | Hub / Source | License (`DATASET_LICENSE`) | Upstream Origin (`UPSTREAM_CONTENT_ORIGIN`) | Reuse Confidence | Unique Reviews | Target-City Coverage (Hà Nội / Đà Nẵng / Hạ Long) | Canonical Mapping to Freeze v2 | Classification |
|---:|---|---|---|---|---|---:|---|---|---|
| 1 | `phamluan/vn_msa_sar_v3 (superseding phamluan/vn_msa_sar) + phamluan/vn_hotel_res_aspect_v3` | Hugging Face Datasets | CC-BY-4.0 (declared on vn_msa_sar_v3 dataset card) | Multi-source hotel & restaurant reviews from Google Maps (~12,400 reviews), Booking.com (~2,400 reviews), Foody (~1,300 reviews), and other platforms (2,375 reviews); v1 included 7,659 synthetic augmented rows which were removed in v3. | `HIGH_FOR_AUXILIARY_ABSA_BENCHMARK_LOW_FOR_PRIMARY_POI_RAG_DUE_TO_ANONYMIZED_PLACES` | 18609 | Unmeasurable (no place/city/coord metadata) | `0` matched (`100% UNMAPPABLE`) | **`AUXILIARY_ONLY`** |
| 2 | `VLSP2018-ABSA-Restaurant & VLSP2018-ABSA-Hotel (official VLSP + HF mirrors visolex/VLSP2018-ABSA-Restaurant, visolex/VLSP2018-ABSA-Hotel)` | VLSP Shared Task / Hugging Face Mirrors | VLSP Academic Shared Task Terms (unspecified license tag on visolex HF mirrors) | Vietnamese restaurant (Foody) and hotel (Tripadvisor/Agoda) reviews annotated for VLSP 2018 ABSA shared task | `HIGH_FOR_AUXILIARY_ABSA_EVALUATION_ONLY` | 10351 | Unmeasurable (no place/city/coord metadata) | `0` matched (`100% UNMAPPABLE`) | **`AUXILIARY_ONLY`** |
| 3 | `pqthinh232/vietnamese-restaurant-review-sentiment-dataset` | Hugging Face Datasets | UNSPECIFIED_ON_HF_CARD | Scraped Vietnamese restaurant reviews (Foody-style) with binary/ternary sentiment labels | `LOW_TO_MEDIUM_UNSPECIFIED_LICENSE_AUXILIARY_ONLY` | 32713 | Unmeasurable (no place/city/coord metadata) | `0` matched (`100% UNMAPPABLE`) | **`AUXILIARY_ONLY`** |
| 4 | `mendeley:10.17632/dp8s59xnb7.1 (CX Vietnamese hotel online reviews / Tripadvisor for VNhotel.csv)` | Mendeley Data (Elsevier Academic Repository) | CC-BY-4.0 (published by Ha Nguyen, FPT University, July 6, 2023) | Tripadvisor online hotel reviews in Vietnam collected for customer experience (CX) academic study | `MEDIUM_ACADEMIC_CC_BY_4_0_AUXILIARY_ONLY` | 20551 | Unmeasurable (no place/city/coord metadata) | `0` matched (`100% UNMAPPABLE`) | **`AUXILIARY_ONLY`** |
| 5 | `hienbm/tripadvisor_vietnam` | Hugging Face Datasets | UNSPECIFIED_ON_HF_CARD | Tripadvisor Vietnam hotel reviews with 6 aspect sub-ratings | `LOW_UNSPECIFIED_LICENSE_AND_TRIPADVISOR_ORIGIN` | 23559 | Unmeasurable (no place/city/coord metadata) | `0` matched (`100% UNMAPPABLE`) | **`AUXILIARY_ONLY`** |
| 6 | `ThanThoai9x/vietnamese-food-images` | Hugging Face Datasets | CC-BY-NC-4.0 (declared on HF card) | Google Maps scraped restaurant review photos and review text in Hồ Chí Minh City | `LOW_TO_MEDIUM_AMBIGUOUS_UPSTREAM_TOS` | ~8000-17000 global (0 in target cities) | 0 / 0 / 0 places | `0` matched (`100% UNMAPPABLE`) | **`REJECTED`** |
| 7 | `MinhDS/ViHoRec (local data/restricted/vihorec/)` | Hugging Face / Local Restricted Snapshot | CC-BY-NC-4.0 | Vietnamese hotel rating matrix and hotel property metadata | `HIGH_FOR_REC_B_RATINGS_ZERO_FOR_TEXT_RAG` | 0 | 0 / 120 / 0 places | `0` matched (`100% UNMAPPABLE`) | **`REJECTED`** |
| 8 | `trungtrandinh/hotel_danang_vietnam + small HF tourism Q&A repos (Bach293/dulich_hanoi, thanh002/dulich, ducthiem05/dulich, tsang326/chatbot_dulich)` | Hugging Face Datasets | UNSPECIFIED_ON_HF_CARD | Templated SFT instruction/output property descriptions or image captions (<100 rows) | `LOW_NOT_REAL_USER_REVIEWS` | 0 | 0 / 0 / 0 places | `0` matched (`100% UNMAPPABLE`) | **`REJECTED`** |

---

## 2. Candidate A Deep Audit (`ThanThoai9x/vietnamese-food-images`)

- **Accessibility & Gated Access:** Public card visible at `https://huggingface.co/datasets/ThanThoai9x/vietnamese-food-images`, but **`gated = manual`** (`36` Parquet shards, **`18.2 GB`**). Unauthenticated `/api/datasets` and `datasets-server` requests return `HTTP 401 Unauthorized` without manual author approval.
- **License & Origin Classification:**
  - `DATASET_LICENSE`: `CC-BY-NC-4.0 (declared in Hugging Face dataset card)`
  - `UPSTREAM_CONTENT_ORIGIN`: `Google Maps user-uploaded restaurant review photos and review text scraped via custom crawl_image pipeline`
  - `RESEARCH_REUSE_CONFIDENCE`: `LOW_TO_MEDIUM_AMBIGUOUS_UPSTREAM_TOS`
- **Actual Schema (`35` fields):** `image, place_name, address, lat, lng, place_rating, reviews_count, categories, query, search_area, distance_km, review_id, author_name, review_rating, text, text_translated, review_url, photo_id, photo_url, width, height, photo_lat, photo_lng, is_food, food_score, dish_label, dish_score, quality_is_good, framing_score, container_score, state_score, clarity_score, sharpness, brightness, crawled_at`.
- **Review Text vs. Image-Row Multiplicity (`UNIQUE_REVIEW_ID_COUNT`):**
  - `text` is real Google Maps user review text (`text_translated` is its translation), accompanied by `place_name`, `address`, `lat`, `lng`, `place_rating`, `review_rating`, `review_id`, and `crawled_at`.
  - However, the dataset's `34,104` rows are keyed by **`photo_id` (food image rows)** across `1,989` unique places (`~17.15` image rows/place). Because a single Google Maps restaurant review (`review_id`) frequently attaches multiple food photos, counting rows as reviews inflates review counts (`UNIQUE_REVIEW_ID_COUNT` globally is bounded below `34,104`, estimated at `8000-17000`, and is **`0`** in our target cities).
- **Smoking-Gun Geographic Proof (0% Coverage in Hà Nội, Đà Nẵng, and Hạ Long):**
  - The public dataset card `Areas` breakdown lists 9 `search_area` districts in **Hồ Chí Minh City**:
    - `quận 1 hồ chí minh`: `7,596` rows
    - `quận 3 hồ chí minh`: `4,541` rows
    - `quận bình thạnh hồ chí minh`: `3,900` rows
    - `quận phú nhuận hồ chí minh`: `3,350` rows
    - `quận 10 hồ chí minh`: `3,321` rows
    - `quận 4 hồ chí minh`: `3,127` rows
    - `quận 5 hồ chí minh`: `3,096` rows
    - `quận tân bình hồ chí minh`: `2,818` rows
    - `thủ đức hồ chí minh`: `2,355` rows
  - **Exact Sum of the 9 Hồ Chí Minh City Districts:** **`34,104` / `34,104` rows (`100.00%`)**.
  - Therefore:
    - **Hà Nội coverage:** `0` unique places / `0` unique reviews (`0.0%`)
    - **Đà Nẵng coverage:** `0` unique places / `0` unique reviews (`0.0%`)
    - **Hạ Long coverage:** `0` unique places / `0` unique reviews (`0.0%`)
    - **Canonical Mapping to `gomate_places_freeze_v2.json` (`759` POIs):** **`0` mappable POIs (`100% UNMAPPABLE`)**.
- **Verdict:** **`REJECTED`** (and Project Owner does **not** need to request gated access or download the `18.2 GB` archive).

---

## 3. Canonical POI Category Balance & Why Public Datasets Cannot Ground Primary RAG

- Across GoMate's three target cities in `data/curated/gomate_places_freeze_v2.json` (`626` total verified POIs; `622` REC-A core POIs):
  - `attractions_culture` (`attraction`, `culture`, `temple`, `museum`): `185` POIs
  - `nature_beach` (`nature`, `beach`, `park`): `34` POIs
  - `restaurants_cafes_markets` (`restaurant`, `cafe`, `market`): `224` POIs (`restaurant` specifically = `110` POIs = `17.57%`)
  - `hotels` (`hotel`): `150` POIs
  - `other_tourism` (`nightlife`, `entertainment`): `33` POIs
- **Non-food tourism share:** **`64.22%`** of target-city POIs are non-food categories (`402 / 626`).
- Every public Vietnamese review dataset with ungated text (`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, `pqthinh232/*`, `mendeley:10.17632/dp8s59xnb7.1`, `hienbm/tripadvisor_vietnam`) stripped `place_name`, `address`, `latitude`, `longitude`, and `city` prior to release, yielding **`0` mappable canonical POIs**.

---

## 4. Targeted Collection Alternatives & Firewall Preservation

- **Google / Tripadvisor Firewall Constants Preserved:**
  - `GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5`
  - `GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW`
  - `TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = NOT_RECOMMENDED`
- **Recommended Primary Acquisition Strategy (`TARGETED_COLLECTION_REQUIRED`):**
  - Bind collection **directly to a pre-selected manifest of `60` canonical POIs from `gomate_places_freeze_v2.json`** (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long) with `>= 5` real/provenanced reviews per POI (`>= 300` reviews total for the Scientific Minimum tier) so `poi_id` and `upstream_place_id` (`EXACT_UPSTREAM_ID`, confidence `1.0`) are locked *before* review intake, with zero scraping and zero post-hoc name-matching ambiguity.
  - Use `phamluan/vn_msa_sar_v3` (`CC-BY-4.0`, `18,609` unique reviews) and `VLSP2018-ABSA` strictly as **separated auxiliary datasets** for aspect vocabulary and ABSA evaluation.

---

## 5. Authoritative Terminal Decision Keys

```json
{
  "RECOMMENDED_PRIMARY_SOURCE_STRATEGY": "TARGETED_COLLECTION_REQUIRED",
  "APPROVED_PUBLIC_DATASETS": [],
  "AUXILIARY_DATASETS": [
    "phamluan/vn_msa_sar_v3",
    "phamluan/vn_msa_sar",
    "phamluan/vn_hotel_res_aspect_v3",
    "visolex/VLSP2018-ABSA-Restaurant",
    "visolex/VLSP2018-ABSA-Hotel",
    "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
    "mendeley:10.17632/dp8s59xnb7.1",
    "hienbm/tripadvisor_vietnam"
  ],
  "REJECTED_DATASETS": [
    "ThanThoai9x/vietnamese-food-images",
    "MinhDS/ViHoRec",
    "trungtrandinh/hotel_danang_vietnam",
    "Bach293/dulich_hanoi",
    "thanh002/dulich",
    "ducthiem05/dulich",
    "tsang326/chatbot_dulich"
  ],
  "TARGETED_COLLECTION_REQUIRED": true,
  "TARGETED_COLLECTION_GAPS": {
    "why_public_dataset_only_is_infeasible": "100% of audited public Vietnamese review datasets either strip POI identity/coordinates/city (`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, `pqthinh232/*`, `mendeley:10.17632/dp8s59xnb7.1`, `hienbm/tripadvisor_vietnam`) resulting in 0 deterministically mappable POIs, or cover only Hồ Chí Minh City restaurants (`ThanThoai9x/vietnamese-food-images`: 34,104 / 34,104 rows in 9 HCMC districts = 0 rows in Hà Nội, Đà Nẵng, or Hạ Long).",
    "public_dataset_covered_slice_in_target_cities": {
      "ha_noi_pois": 0,
      "da_nang_pois": 0,
      "ha_long_pois": 0,
      "total_canonical_pois_covered_by_public_datasets": 0,
      "total_provenanced_reviews_covered_by_public_datasets": 0
    },
    "missing_slice_requiring_targeted_collection_scientific_minimum": {
      "target_canonical_pois_total": 60,
      "target_reviews_per_poi_min": 5,
      "target_new_reviews_total_min": 300,
      "by_city": {
        "Hà Nội": {
          "canonical_pois_needed": 20,
          "reviews_needed_min": 100
        },
        "Đà Nẵng": {
          "canonical_pois_needed": 20,
          "reviews_needed_min": 100
        },
        "Hạ Long": {
          "canonical_pois_needed": 20,
          "reviews_needed_min": 100
        }
      },
      "by_category_group": {
        "attractions_culture": {
          "canonical_pois_needed": 18,
          "reviews_needed_min": 90
        },
        "nature_beach": {
          "canonical_pois_needed": 6,
          "reviews_needed_min": 30
        },
        "restaurants_cafes_markets": {
          "canonical_pois_needed": 18,
          "reviews_needed_min": 90
        },
        "hotels": {
          "canonical_pois_needed": 15,
          "reviews_needed_min": 75
        },
        "other_tourism": {
          "canonical_pois_needed": 3,
          "reviews_needed_min": 15
        }
      }
    },
    "missing_slice_preferred_tier_optional": {
      "target_canonical_pois_range": "75-100",
      "target_reviews_per_poi_range": "8-12",
      "target_new_reviews_range": "600-1200"
    }
  },
  "USER_ACTION_REQUIRED": {
    "action_required": true,
    "do_not_request_gated_thanthoai9x_download": "Project Owner does NOT need to request gated access or download the 18.2 GB `ThanThoai9x/vietnamese-food-images` dataset because its public card `Areas` table proves 100.0% of its 34,104 rows are in 9 districts of Hồ Chí Minh City (0 rows in Hà Nội, Đà Nẵng, or Hạ Long).",
    "exact_owner_steps_after_w07_a1_audit_gate": [
      "STEP_1_APPROVE_COLLECTION_PATH: Confirm selection of Option 1/2 (Pre-Bound 60-POI Freeze v2 Canonical Intake Template at data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl with >= 5 real/provenanced reviews per POI = >= 300 reviews across Hà Nội [20 POIs], Đà Nẵng [20 POIs], and Hạ Long [20 POIs]).",
      "STEP_2_POPULATE_OR_PROVIDE_LOCAL_FILE: Using the deterministic 60-POI canonical intake CSV/JSONL template generated from data/curated/gomate_places_freeze_v2.json (where poi_id, city, category, lat, lng, and osm_id are pre-filled), provide or approve >= 300 real/first-party/research-permitted reviews (>= 5 per POI) with source_ref, rating, language, created_at, and license_or_usage_class.",
      "STEP_3_OPTIONAL_AUXILIARY_ABSA_APPROVAL: Confirm whether public ungated `phamluan/vn_msa_sar_v3` (CC-BY-4.0) should be used strictly in a separated auxiliary aspect-extraction test (never mixed into the primary POI-linked retrieval index)."
    ]
  },
  "EXPECTED_CORPUS_SIZE": {
    "current_verified_real_reviews_in_repo": 0,
    "from_approved_public_datasets_for_primary_rag": 0,
    "scientific_minimum_target_reviews": 300,
    "scientific_minimum_reviews_per_poi": 5,
    "preferred_target_reviews_range": "600-1200",
    "preferred_reviews_per_poi_range": "8-12",
    "stretch_target_reviews_range": "1100-1650",
    "stretch_reviews_per_poi_range": "10-15",
    "auxiliary_separated_benchmark_reviews_available": {
      "phamluan/vn_msa_sar_v3_unique_reviews": 18609,
      "VLSP2018_ABSA_restaurant_plus_hotel_reviews": 10351,
      "pqthinh232_restaurant_sentiment_reviews": 32713,
      "mendeley_dp8s59xnb7_hotel_reviews": 20551
    }
  },
  "EXPECTED_CANONICAL_POI_COVERAGE": {
    "canonical_universe_file": "data/curated/gomate_places_freeze_v2.json",
    "total_verified_canonical_pois": 759,
    "three_target_cities_verified_pois": 626,
    "three_target_cities_rec_a_core_pois": 622,
    "public_dataset_mappable_pois_in_target_cities": 0,
    "scientific_minimum_covered_pois": 60,
    "scientific_minimum_share_of_3_city_core_pct": 9.65,
    "preferred_covered_pois_range": "75-100",
    "stretch_covered_pois": 110,
    "mapping_tier_achieved_by_prebound_collection": "EXACT_UPSTREAM_ID",
    "mapping_confidence": 1.0
  },
  "EXPECTED_CITY_COVERAGE": {
    "target_cities": [
      "Hà Nội",
      "Đà Nẵng",
      "Hạ Long"
    ],
    "aliases_audited": {
      "Hà Nội": [
        "Hà Nội",
        "Hanoi",
        "Ha Noi",
        "TP. Hà Nội",
        "Thành phố Hà Nội"
      ],
      "Đà Nẵng": [
        "Đà Nẵng",
        "Da Nang",
        "Danang",
        "TP. Đà Nẵng",
        "Thành phố Đà Nẵng"
      ],
      "Hạ Long": [
        "Hạ Long",
        "Ha Long",
        "Halong",
        "TP. Hạ Long",
        "Quảng Ninh",
        "Quang Ninh"
      ]
    },
    "public_dataset_measurable_coverage": {
      "Hà Nội": {
        "unique_places": 0,
        "unique_reviews": 0
      },
      "Đà Nẵng": {
        "unique_places": 0,
        "unique_reviews": 0
      },
      "Hạ Long": {
        "unique_places": 0,
        "unique_reviews": 0
      }
    },
    "scientific_minimum_target_coverage": {
      "Hà Nội": {
        "canonical_pois": 20,
        "min_reviews_per_poi": 5,
        "expected_reviews": 100,
        "freeze_v2_available_pois": 145
      },
      "Đà Nẵng": {
        "canonical_pois": 20,
        "min_reviews_per_poi": 5,
        "expected_reviews": 100,
        "freeze_v2_available_pois": 293
      },
      "Hạ Long": {
        "canonical_pois": 20,
        "min_reviews_per_poi": 5,
        "expected_reviews": 100,
        "freeze_v2_available_pois": 188
      }
    },
    "preferred_target_coverage": {
      "Hà Nội": {
        "canonical_pois": "25-34",
        "expected_reviews": "200-400"
      },
      "Đà Nẵng": {
        "canonical_pois": "25-33",
        "expected_reviews": "200-400"
      },
      "Hạ Long": {
        "canonical_pois": "25-33",
        "expected_reviews": "200-400"
      }
    }
  },
  "EXPECTED_CATEGORY_COVERAGE": {
    "freeze_v2_three_target_cities_baseline_pois": {
      "attractions_culture": 185,
      "nature_beach": 34,
      "restaurants_cafes_markets": 224,
      "hotels": 150,
      "other_tourism": 33
    },
    "public_datasets_primary_rag_coverage": {
      "attractions_culture": 0,
      "nature_beach": 0,
      "restaurants_cafes_markets": 0,
      "hotels": 0,
      "other_tourism": 0
    },
    "scientific_minimum_target_60_pois_300_reviews": {
      "attractions_culture": {
        "canonical_pois": 18,
        "expected_reviews": 90,
        "share_of_corpus_pct": 30.0
      },
      "nature_beach": {
        "canonical_pois": 6,
        "expected_reviews": 30,
        "share_of_corpus_pct": 10.0
      },
      "restaurants_cafes_markets": {
        "canonical_pois": 18,
        "expected_reviews": 90,
        "share_of_corpus_pct": 30.0
      },
      "hotels": {
        "canonical_pois": 15,
        "expected_reviews": 75,
        "share_of_corpus_pct": 25.0
      },
      "other_tourism": {
        "canonical_pois": 3,
        "expected_reviews": 15,
        "share_of_corpus_pct": 5.0
      }
    },
    "restaurant_bias_mitigation": "Prevents a restaurant-only corpus: 70.0% of the Scientific Minimum corpus (42 / 60 POIs, 210 / 300 reviews) covers non-food tourism categories (attractions/culture 30%, hotels 25%, nature/beach 10%, other tourism 5%), matching GoMate's multi-category itinerary planner."
  }
}
```
