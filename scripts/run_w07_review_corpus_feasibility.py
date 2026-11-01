#!/usr/bin/env python3
"""W07-A1 Public Review Corpus Feasibility + Acquisition Decision & Deterministic Verifier.

Evaluates public/research-accessible Vietnamese travel/hospitality/place review corpora
across Hugging Face, Mendeley Data, Kaggle, GitHub, and academic shared tasks to determine
the safest and highest-value strategy to obtain the real POI-linked review corpus required
by W07 Review Intelligence / RAG.

Enforces:
- W06 remains CLOSED and unmodified (`data/evaluation/w06/w06_scientific_closure_v1.json`).
- W07-0 remains complete and unmodified (`data/evaluation/w07/w07_data_rag_readiness_audit_v1.json`).
- Google Places / Tripadvisor firewall constants preserved:
  - GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5
  - GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
  - TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = "NOT_RECOMMENDED"
- NEW_LLM_PROVIDER_CALLS = 0 (no Gemini, Claude, OpenAI, embedding, or reranker calls).
- Deterministic JSON output ending with the 11 mandatory decision keys from Section 16.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

FEASIBILITY_JSON_RELPATH = "data/evaluation/w07/w07_review_corpus_feasibility_v1.json"
FEASIBILITY_MD_RELPATH = "docs/research/w07_review_corpus_feasibility.md"
W07_0_AUDIT_JSON_RELPATH = "data/evaluation/w07/w07_data_rag_readiness_audit_v1.json"
W06_CLOSURE_JSON_RELPATH = "data/evaluation/w06/w06_scientific_closure_v1.json"

AUTHORITATIVE_DEVELOP_BASE_SHA = "6eb131c5c933aa62026bc2c6a9337d0da3510781"
PREVIOUS_GATE = "W07-DATA-RAG-READINESS-AUDIT-POSTMERGE-CHATGPT-AUDIT = PASS"
PREVIOUS_GATE_DECISION = "PASS"
NEXT_GATE = "W07-A1-REVIEW-CORPUS-FEASIBILITY-CHATGPT-AUDIT"

EXPECTED_W07_0_INTERNAL_SHA256 = (
    "7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9"
)
EXPECTED_W07_0_FILE_LF_SHA256 = (
    "2727cb23ea63af6eada16deba558a82f6329b13ebccb09133c32042466bd2b16"
)
EXPECTED_W06_CLOSURE_INTERNAL_SHA256 = (
    "7dec87d9b318165ba5233d1470df8f12dfbe99449bceabb86dc2322aaab89e12"
)
EXPECTED_W06_CLOSURE_FILE_LF_SHA256 = (
    "7b58fcc8c63a7e1391a4d5212ed08f57317bb4d81d9069a9513cfaf3c03398cc"
)

GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5
GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = "NOT_RECOMMENDED"

MANDATORY_TERMINAL_KEYS = (
    "RECOMMENDED_PRIMARY_SOURCE_STRATEGY",
    "APPROVED_PUBLIC_DATASETS",
    "AUXILIARY_DATASETS",
    "REJECTED_DATASETS",
    "TARGETED_COLLECTION_REQUIRED",
    "TARGETED_COLLECTION_GAPS",
    "USER_ACTION_REQUIRED",
    "EXPECTED_CORPUS_SIZE",
    "EXPECTED_CANONICAL_POI_COVERAGE",
    "EXPECTED_CITY_COVERAGE",
    "EXPECTED_CATEGORY_COVERAGE",
)

TARGET_CITY_SLUGS = ("ha-noi", "da-nang", "ha-long")
TARGET_CITY_LABELS = {
    "ha-noi": "Hà Nội",
    "da-nang": "Đà Nẵng",
    "ha-long": "Hạ Long",
}
TARGET_CITY_ALIASES = {
    "Hà Nội": ["Hà Nội", "Hanoi", "Ha Noi", "TP. Hà Nội", "Thành phố Hà Nội"],
    "Đà Nẵng": ["Đà Nẵng", "Da Nang", "Danang", "TP. Đà Nẵng", "Thành phố Đà Nẵng"],
    "Hạ Long": [
        "Hạ Long",
        "Ha Long",
        "Halong",
        "TP. Hạ Long",
        "Quảng Ninh",
        "Quang Ninh",
    ],
}

CATEGORY_GROUP_MAP = {
    "attraction": "attractions_culture",
    "culture": "attractions_culture",
    "temple": "attractions_culture",
    "museum": "attractions_culture",
    "nature": "nature_beach",
    "beach": "nature_beach",
    "park": "nature_beach",
    "restaurant": "restaurants_cafes_markets",
    "cafe": "restaurants_cafes_markets",
    "market": "restaurants_cafes_markets",
    "hotel": "hotels",
    "nightlife": "other_tourism",
    "entertainment": "other_tourism",
}


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    body = {k: v for k, v in payload.items() if k != "artifact_sha256"}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def compute_internal_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def compute_w06_closure_internal_sha256(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone["closure_internal_sha256"] = ""
    raw = (json.dumps(clone, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_lf_normalized_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _compute_canonical_poi_baseline(places_v2: list[dict[str, Any]]) -> dict[str, Any]:
    total_pois = len(places_v2)
    core_pois = [p for p in places_v2 if p.get("is_rec_a_core_v2")]
    by_slug_total = Counter(p["destination_slug"] for p in places_v2)
    by_slug_core = Counter(p["destination_slug"] for p in core_pois)

    target_city_pois = [p for p in places_v2 if p["destination_slug"] in TARGET_CITY_SLUGS]
    target_city_core_pois = [p for p in core_pois if p["destination_slug"] in TARGET_CITY_SLUGS]

    city_category_matrix: dict[str, dict[str, Any]] = {}
    for slug in TARGET_CITY_SLUGS:
        city_label = TARGET_CITY_LABELS[slug]
        sub = [p for p in places_v2 if p["destination_slug"] == slug]
        sub_core = [p for p in sub if p.get("is_rec_a_core_v2")]
        raw_cat_counts = dict(sorted(Counter(p["category"] for p in sub).items()))
        group_counts = Counter(CATEGORY_GROUP_MAP[p["category"]] for p in sub)
        city_category_matrix[city_label] = {
            "destination_slug": slug,
            "verified_pois_total": len(sub),
            "rec_a_core_pois": len(sub_core),
            "raw_categories": raw_cat_counts,
            "category_groups": {
                "attractions_culture": group_counts["attractions_culture"],
                "nature_beach": group_counts["nature_beach"],
                "restaurants_cafes_markets": group_counts["restaurants_cafes_markets"],
                "hotels": group_counts["hotels"],
                "other_tourism": group_counts["other_tourism"],
            },
        }

    all_raw_cats = dict(sorted(Counter(p["category"] for p in places_v2).items()))
    all_groups = Counter(CATEGORY_GROUP_MAP[p["category"]] for p in places_v2)
    target_raw_cats = dict(sorted(Counter(p["category"] for p in target_city_pois).items()))
    target_groups = Counter(CATEGORY_GROUP_MAP[p["category"]] for p in target_city_pois)

    # Select a deterministic 60-POI Scientific Minimum target intake manifest (20 per target city)
    # and a 90-POI Preferred target intake manifest (30 per target city) from Freeze v2
    # to prove 100% pre-bound canonical POI linkage feasibility.
    per_city_group_quotas_min20 = {
        "attractions_culture": 6,
        "nature_beach": 2,
        "restaurants_cafes_markets": 6,
        "hotels": 5,
        "other_tourism": 1,
    }
    selected_min60_summary: dict[str, dict[str, Any]] = {}
    for slug in TARGET_CITY_SLUGS:
        city_label = TARGET_CITY_LABELS[slug]
        sub_core = sorted(
            [p for p in places_v2 if p["destination_slug"] == slug and p.get("is_rec_a_core_v2")],
            key=lambda x: x["place_id"],
        )
        chosen: list[dict[str, Any]] = []
        chosen_ids: set[str] = set()
        for grp, quota in per_city_group_quotas_min20.items():
            grp_candidates = [
                p for p in sub_core if CATEGORY_GROUP_MAP[p["category"]] == grp
            ]
            for cand in grp_candidates[:quota]:
                chosen.append(cand)
                chosen_ids.add(cand["place_id"])
        # Fill any shortfall deterministically from remaining core POIs in that city
        if len(chosen) < 20:
            for cand in sub_core:
                if cand["place_id"] not in chosen_ids:
                    chosen.append(cand)
                    chosen_ids.add(cand["place_id"])
                    if len(chosen) == 20:
                        break
        chosen_groups = Counter(CATEGORY_GROUP_MAP[p["category"]] for p in chosen)
        selected_min60_summary[city_label] = {
            "selected_canonical_pois": len(chosen),
            "category_groups": {
                "attractions_culture": chosen_groups["attractions_culture"],
                "nature_beach": chosen_groups["nature_beach"],
                "restaurants_cafes_markets": chosen_groups["restaurants_cafes_markets"],
                "hotels": chosen_groups["hotels"],
                "other_tourism": chosen_groups["other_tourism"],
            },
            "sample_place_ids": [p["place_id"] for p in chosen[:5]],
        }

    return {
        "canonical_freeze_file": "data/curated/gomate_places_freeze_v2.json",
        "verified_pois_all_6_destinations": total_pois,
        "rec_a_core_pois_all_destinations": len(core_pois),
        "verified_pois_by_slug": dict(sorted(by_slug_total.items())),
        "rec_a_core_pois_by_slug": dict(sorted(by_slug_core.items())),
        "three_target_cities_total_pois": len(target_city_pois),
        "three_target_cities_rec_a_core_pois": len(target_city_core_pois),
        "all_759_raw_categories": all_raw_cats,
        "all_759_category_groups": {
            "attractions_culture": all_groups["attractions_culture"],
            "nature_beach": all_groups["nature_beach"],
            "restaurants_cafes_markets": all_groups["restaurants_cafes_markets"],
            "hotels": all_groups["hotels"],
            "other_tourism": all_groups["other_tourism"],
        },
        "three_target_cities_raw_categories": target_raw_cats,
        "three_target_cities_category_groups": {
            "attractions_culture": target_groups["attractions_culture"],
            "nature_beach": target_groups["nature_beach"],
            "restaurants_cafes_markets": target_groups["restaurants_cafes_markets"],
            "hotels": target_groups["hotels"],
            "other_tourism": target_groups["other_tourism"],
        },
        "three_target_cities_non_food_poi_share_pct": round(
            (len(target_city_pois) - target_groups["restaurants_cafes_markets"])
            / len(target_city_pois)
            * 100.0,
            2,
        ),
        "three_target_cities_restaurant_only_poi_share_pct": round(
            target_raw_cats.get("restaurant", 0) / len(target_city_pois) * 100.0,
            2,
        ),
        "by_target_city": city_category_matrix,
        "scientific_minimum_60_poi_prebound_template_preview": selected_min60_summary,
    }


def build_w07_a1_feasibility_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    # 1. Verify W06 scientific closure and W07-0 readiness audit immutability
    w06_path = repo_root / W06_CLOSURE_JSON_RELPATH
    w07_0_path = repo_root / W07_0_AUDIT_JSON_RELPATH
    places_v2_path = repo_root / "data/curated/gomate_places_freeze_v2.json"
    review_prov_path = repo_root / "data/manifests/review-provenance.json"
    review_cand_path = repo_root / "data/manifests/review-dataset-candidates.yaml"

    w06_payload = json.loads(w06_path.read_text(encoding="utf-8"))
    w07_0_payload = json.loads(w07_0_path.read_text(encoding="utf-8"))
    places_v2 = json.loads(places_v2_path.read_text(encoding="utf-8"))
    review_prov = json.loads(review_prov_path.read_text(encoding="utf-8"))
    review_cand = yaml.safe_load(review_cand_path.read_text(encoding="utf-8"))

    w06_internal_sha = compute_w06_closure_internal_sha256(w06_payload)
    w07_0_internal_sha = compute_internal_sha256(w07_0_payload)
    w07_0_lf_sha = compute_lf_normalized_sha256(w07_0_path)

    if (
        w06_internal_sha != EXPECTED_W06_CLOSURE_INTERNAL_SHA256
        or w06_payload.get("closure_internal_sha256") != EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    ):
        raise ValueError(
            f"W06 closure internal SHA mismatch: {w06_internal_sha} != "
            f"{EXPECTED_W06_CLOSURE_INTERNAL_SHA256}"
        )
    if w07_0_internal_sha != EXPECTED_W07_0_INTERNAL_SHA256:
        raise ValueError(
            f"W07-0 audit internal SHA mismatch: {w07_0_internal_sha} != "
            f"{EXPECTED_W07_0_INTERNAL_SHA256}"
        )
    if w07_0_lf_sha != EXPECTED_W07_0_FILE_LF_SHA256:
        raise ValueError(
            f"W07-0 audit LF file SHA mismatch: {w07_0_lf_sha} != "
            f"{EXPECTED_W07_0_FILE_LF_SHA256}"
        )
    if review_prov.get("audit_result", {}).get("verified_real_count") != 0:
        raise ValueError("Expected verified_real_count == 0 in review-provenance.json")

    poi_baseline = _compute_canonical_poi_baseline(places_v2)

    # Section 4: Candidate A deep audit (ThanThoai9x/vietnamese-food-images)
    hcmc_area_counts = {
        "quận 1 hồ chí minh": 7596,
        "quận 3 hồ chí minh": 4541,
        "quận bình thạnh hồ chí minh": 3900,
        "quận phú nhuận hồ chí minh": 3350,
        "quận 10 hồ chí minh": 3321,
        "quận 4 hồ chí minh": 3127,
        "quận 5 hồ chí minh": 3096,
        "quận tân bình hồ chí minh": 2818,
        "thủ đức hồ chí minh": 2355,
    }
    hcmc_area_sum = sum(hcmc_area_counts.values())
    if hcmc_area_sum != 34104:
        raise ValueError(f"Expected HCMC area sum == 34104, got {hcmc_area_sum}")

    candidate_a_deep_audit = {
        "dataset_id": "ThanThoai9x/vietnamese-food-images",
        "source_hub": "Hugging Face Datasets",
        "url": "https://huggingface.co/datasets/ThanThoai9x/vietnamese-food-images",
        "accessibility": {
            "public_card_visible": True,
            "gated_access_mode": "manual",
            "gated_access_requirement": (
                "Requires Hugging Face account login and manual author approval "
                "('You need to agree to share your Hugging Face information to access this dataset'). "
                "Unauthenticated /api/datasets, /raw/main/README.md, and datasets-server "
                "requests return HTTP 401 Unauthorized."
            ),
            "parquet_shards": 36,
            "download_size_gb": 18.2,
            "bulk_downloaded_in_w07_a1": False,
        },
        "license_and_origin": {
            "DATASET_LICENSE": "CC-BY-NC-4.0 (declared in Hugging Face dataset card)",
            "UPSTREAM_CONTENT_ORIGIN": (
                "Google Maps user-uploaded restaurant review photos and review text "
                "scraped via custom crawl_image pipeline"
            ),
            "RESEARCH_REUSE_CONFIDENCE": "LOW_TO_MEDIUM_AMBIGUOUS_UPSTREAM_TOS",
            "card_ethics_disclaimer": (
                "Images are user-uploaded review photos on Google Maps and remain the copyright "
                "of their original authors. Released under CC BY-NC 4.0 for academic research and "
                "non-commercial experimentation only. Respect Google Maps' Terms of Service."
            ),
            "project_owner_review_flag": (
                "AMBIGUOUS_UPSTREAM_RIGHTS: Repository author applies CC-BY-NC-4.0, which does not "
                "automatically override Google Maps Platform Terms of Service or third-party reviewer "
                "copyrights; however, dataset is independently disqualified by 0% geographic overlap "
                "with Hà Nội, Đà Nẵng, and Hạ Long."
            ),
        },
        "actual_schema": {
            "field_count": 35,
            "fields": [
                "image",
                "place_name",
                "address",
                "lat",
                "lng",
                "place_rating",
                "reviews_count",
                "categories",
                "query",
                "search_area",
                "distance_km",
                "review_id",
                "author_name",
                "review_rating",
                "text",
                "text_translated",
                "review_url",
                "photo_id",
                "photo_url",
                "width",
                "height",
                "photo_lat",
                "photo_lng",
                "is_food",
                "food_score",
                "dish_label",
                "dish_score",
                "quality_is_good",
                "framing_score",
                "container_score",
                "state_score",
                "clarity_score",
                "sharpness",
                "brightness",
                "crawled_at",
            ],
            "text_is_review_text": True,
            "text_field_semantics": (
                "`text` is the original Google Maps user review text attached to `review_id`, "
                "and `text_translated` is its translated text; however, rows are keyed by `photo_id` "
                "(one row per food image), not by `review_id`."
            ),
            "lat_lng_available": True,
            "address_quality": (
                "Street/ward/district address strings from Google Maps places in Hồ Chí Minh City"
            ),
            "review_id_available": True,
            "rating_available": True,
            "rating_fields": ["place_rating", "review_rating"],
            "date_or_crawled_timestamp_available": True,
            "timestamp_fields": ["crawled_at"],
        },
        "multiplicity_and_unique_review_analysis": {
            "total_image_rows": 34104,
            "unique_places": 1989,
            "mean_image_rows_per_place": round(34104 / 1989, 2),
            "dish_classes": 33,
            "row_granularity": "IMAGE_ROW_KEYED_BY_PHOTO_ID",
            "duplicate_review_text_cause": (
                "A single Google Maps restaurant review (`review_id`) frequently contains 2 to 10+ "
                "food photos (`photo_id`). Because the dataset is flattened to one row per image, "
                "every photo from the same review duplicates `review_id`, `text`, `review_rating`, "
                "and `place_name`."
            ),
            "UNIQUE_REVIEW_ID_COUNT": {
                "exact_count_status": "UNMEASURABLE_WITHOUT_GATED_18_2GB_PARQUET_ACCESS",
                "upper_bound": 34104,
                "lower_bound": 1989,
                "estimated_unique_review_id_range": "8000-17000",
                "target_city_unique_review_id_count_exact": 0,
                "explanation": (
                    "While global UNIQUE_REVIEW_ID_COUNT across Hồ Chí Minh City requires reading the "
                    "manual-gated 18.2 GB parquet shards, the exact UNIQUE_REVIEW_ID_COUNT in GoMate's "
                    "three target cities (Hà Nội, Đà Nẵng, Hạ Long) is deterministically 0 because "
                    "100.0% of all 34,104 rows belong to 9 districts of Hồ Chí Minh City."
                ),
            },
        },
        "geographic_coverage_proof": {
            "search_areas_reported_on_card": hcmc_area_counts,
            "sum_of_9_hcmc_districts": hcmc_area_sum,
            "total_dataset_rows": 34104,
            "hcmc_share_of_dataset_pct": 100.0,
            "non_hcmc_rows": 0,
            "ha_noi_unique_places": 0,
            "ha_noi_unique_reviews": 0,
            "da_nang_unique_places": 0,
            "da_nang_unique_reviews": 0,
            "ha_long_unique_places": 0,
            "ha_long_unique_reviews": 0,
        },
        "canonical_mapping_to_freeze_v2": {
            "EXACT_UPSTREAM_ID": 0,
            "GEO_NAME_HIGH_CONFIDENCE": 0,
            "MANUAL_REVIEW_REQUIRED": 0,
            "UNMAPPABLE": 1989,
            "canonical_freeze_v2_pois_matched": 0,
            "reason": (
                "gomate_places_freeze_v2.json contains 759 POIs across Hà Nội, Đà Nẵng, Hạ Long, "
                "Hội An, Huế, and Nha Trang (0 in Hồ Chí Minh City). ThanThoai9x/vietnamese-food-images "
                "is 100% Hồ Chí Minh City (34,104 / 34,104 rows across 9 HCMC districts), so geographic "
                "and coordinate intersection with Freeze v2 is exactly 0 POIs."
            ),
        },
        "classification": "REJECTED",
        "rejection_reasons": [
            "Zero geographic overlap with Hà Nội (0), Đà Nẵng (0), and Hạ Long (0): 9 HCMC districts sum to 34,104 / 34,104 rows (100.0%).",
            "Zero mappable POIs against gomate_places_freeze_v2.json (0 / 759).",
            "100% food/restaurant category bias (0 attractions, culture, nature, beaches, or hotels).",
            "Manual gated access (HTTP 401 without author approval) and 18.2 GB image-heavy payload.",
            "Ambiguous upstream Google Maps ToS vs repository CC-BY-NC-4.0 license.",
        ],
    }

    # Section 3, 5, 6, 7: Complete Candidate Evaluation Matrix
    candidate_datasets = [
        {
            "candidate_rank": 1,
            "dataset_id": "phamluan/vn_msa_sar_v3 (superseding phamluan/vn_msa_sar) + phamluan/vn_hotel_res_aspect_v3",
            "mandatory_candidate_covered": "phamluan/vn_msa_sar",
            "source_hub": "Hugging Face Datasets",
            "urls": [
                "https://huggingface.co/datasets/phamluan/vn_msa_sar",
                "https://huggingface.co/datasets/phamluan/vn_msa_sar_v3",
                "https://huggingface.co/datasets/phamluan/vn_hotel_res_aspect_v3",
            ],
            "accessibility": "PUBLIC_UNGATED (Parquet via Hugging Face Hub / datasets-server)",
            "DATASET_LICENSE": "CC-BY-4.0 (declared on vn_msa_sar_v3 dataset card)",
            "UPSTREAM_CONTENT_ORIGIN": (
                "Multi-source hotel & restaurant reviews from Google Maps (~12,400 reviews), "
                "Booking.com (~2,400 reviews), Foody (~1,300 reviews), and other platforms (2,375 reviews); "
                "v1 included 7,659 synthetic augmented rows which were removed in v3."
            ),
            "RESEARCH_REUSE_CONFIDENCE": (
                "HIGH_FOR_AUXILIARY_ABSA_BENCHMARK_LOW_FOR_PRIMARY_POI_RAG_DUE_TO_ANONYMIZED_PLACES"
            ),
            "classification": "AUXILIARY_ONLY",
            "schema_fields": [
                "review_id",
                "source",
                "place_type",
                "language",
                "sentence",
                "aspect",
                "sentiment",
                "sarcasm",
            ],
            "schema_suitability_for_primary_poi_rag": "INSUFFICIENT_MISSING_POI_NAME_ADDRESS_COORDS_CITY",
            "row_count": {
                "vn_msa_sar_v1_sentence_aspect_rows": 83009,
                "vn_msa_sar_v3_sentence_aspect_rows": 76785,
                "vn_hotel_res_aspect_v3_rows": 21783,
            },
            "unique_review_count": {
                "measurable": True,
                "vn_msa_sar_v3_unique_review_ids": 18609,
                "train_unique_review_ids": 14536,
                "val_unique_review_ids": 2037,
                "test_unique_review_ids": 2036,
                "note": "76,785 sentence-aspect rows group deterministically into 18,609 unique review_id hashes.",
            },
            "target_city_coverage": {
                "measurable_from_metadata": False,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": None,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": None,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": None,
                "reason": (
                    "Place names, addresses, coordinates, and city fields were stripped during dataset "
                    "publication (`review_id` is an opaque hash such as `gm_da9f8fa1510e`). Counting target "
                    "cities from sentence text mentions alone is forbidden by Section 6."
                ),
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 18609,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "100% UNMAPPABLE to Freeze v2 POIs because no place_name, lat/lng, address, or upstream_place_id exists.",
            },
            "category_coverage": {
                "covered": ["hotel", "restaurant"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "cafe", "market", "nightlife", "entertainment"],
            },
            "decision_rationale": (
                "Best public auxiliary dataset for Vietnamese + multilingual hospitality aspect extraction "
                "(9 aspects: overall, amenities, food, service, location, ambiance, room, price, cleanliness), "
                "sentiment polarity (-3..+3), and sarcasm detection; strictly separated from primary POI-grounded RAG corpus."
            ),
        },
        {
            "candidate_rank": 2,
            "dataset_id": "VLSP2018-ABSA-Restaurant & VLSP2018-ABSA-Hotel (official VLSP + HF mirrors visolex/VLSP2018-ABSA-Restaurant, visolex/VLSP2018-ABSA-Hotel)",
            "mandatory_candidate_covered": "VLSP2018-ABSA-Restaurant",
            "source_hub": "VLSP Shared Task / Hugging Face Mirrors",
            "urls": [
                "https://huggingface.co/datasets/visolex/VLSP2018-ABSA-Restaurant",
                "https://huggingface.co/datasets/visolex/VLSP2018-ABSA-Hotel",
            ],
            "accessibility": "PUBLIC_HF_MIRRORS_UNGATED (Official VLSP requires academic DUA)",
            "DATASET_LICENSE": "VLSP Academic Shared Task Terms (unspecified license tag on visolex HF mirrors)",
            "UPSTREAM_CONTENT_ORIGIN": "Vietnamese restaurant (Foody) and hotel (Tripadvisor/Agoda) reviews annotated for VLSP 2018 ABSA shared task",
            "RESEARCH_REUSE_CONFIDENCE": "HIGH_FOR_AUXILIARY_ABSA_EVALUATION_ONLY",
            "classification": "AUXILIARY_ONLY",
            "schema_fields": [
                "Review",
                "12 restaurant aspect-polarity columns (FOOD#QUALITY, SERVICE#GENERAL, AMBIENCE#GENERAL, LOCATION#GENERAL, RESTAURANT#PRICES, etc.)",
                "34 hotel aspect-polarity columns (HOTEL#CLEANLINESS, ROOMS#COMFORT, LOCATION#GENERAL, SERVICE#GENERAL, etc.)",
                "type",
                "dataset",
            ],
            "schema_suitability_for_primary_poi_rag": "INSUFFICIENT_MISSING_POI_NAME_ADDRESS_COORDS_CITY_RATING_DATE",
            "row_count": {
                "restaurant_total_rows": 4751,
                "restaurant_train_val_test": [2961, 1290, 500],
                "hotel_total_rows": 5600,
                "hotel_train_val_test": [3000, 2000, 600],
            },
            "unique_review_count": {
                "measurable": True,
                "restaurant_unique_reviews": 4751,
                "hotel_unique_reviews": 5600,
                "combined_unique_reviews": 10351,
            },
            "target_city_coverage": {
                "measurable_from_metadata": False,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": None,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": None,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": None,
                "reason": "No place_name, address, city, or coordinate columns exist.",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 10351,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "100% UNMAPPABLE to Freeze v2 POIs due to total absence of place identity and coordinates.",
            },
            "category_coverage": {
                "covered": ["restaurant", "hotel"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "nightlife", "entertainment"],
            },
            "decision_rationale": (
                "Standard academic Vietnamese ABSA benchmark; valuable as an auxiliary taxonomy and "
                "aspect-vocabulary reference for restaurant and hotel queries, unusable for POI-grounded retrieval."
            ),
        },
        {
            "candidate_rank": 3,
            "dataset_id": "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "mandatory_candidate_covered": "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "source_hub": "Hugging Face Datasets",
            "urls": [
                "https://huggingface.co/datasets/pqthinh232/vietnamese-restaurant-review-sentiment-dataset"
            ],
            "accessibility": "PUBLIC_UNGATED (12.0 MB Parquet)",
            "DATASET_LICENSE": "UNSPECIFIED_ON_HF_CARD",
            "UPSTREAM_CONTENT_ORIGIN": "Scraped Vietnamese restaurant reviews (Foody-style) with binary/ternary sentiment labels",
            "RESEARCH_REUSE_CONFIDENCE": "LOW_TO_MEDIUM_UNSPECIFIED_LICENSE_AUXILIARY_ONLY",
            "classification": "AUXILIARY_ONLY",
            "schema_fields": ["review_id", "review", "label"],
            "schema_suitability_for_primary_poi_rag": "INSUFFICIENT_TEXT_AND_SENTIMENT_LABEL_ONLY",
            "row_count": {
                "total_rows": 32713,
                "train": 26170,
                "validation": 3271,
                "test": 3272,
            },
            "unique_review_count": {
                "measurable": True,
                "unique_review_ids": 32713,
            },
            "target_city_coverage": {
                "measurable_from_metadata": False,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": None,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": None,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": None,
                "reason": "Contains only `review_id`, `review` text, and `label`; zero geographic or place fields.",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 32713,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "100% UNMAPPABLE to Freeze v2 POIs because no place identity or location metadata is present.",
            },
            "category_coverage": {
                "covered": ["restaurant", "cafe"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "hotel", "nightlife", "entertainment"],
            },
            "decision_rationale": (
                "Useful only as an auxiliary Vietnamese colloquial food/restaurant sentiment and "
                "linguistic robustness resource; cannot ground POI retrieval."
            ),
        },
        {
            "candidate_rank": 4,
            "dataset_id": "mendeley:10.17632/dp8s59xnb7.1 (CX Vietnamese hotel online reviews / Tripadvisor for VNhotel.csv)",
            "mandatory_candidate_covered": "discovered_academic_repository_candidate",
            "source_hub": "Mendeley Data (Elsevier Academic Repository)",
            "urls": ["https://data.mendeley.com/datasets/dp8s59xnb7/1"],
            "accessibility": "PUBLIC_UNGATED (12.53 MB CSV, SHA256 4d5e5fcbb40699d8d1bc3310cbe6b5828899b057dfa56b41a24f09c7a87f0c27)",
            "DATASET_LICENSE": "CC-BY-4.0 (published by Ha Nguyen, FPT University, July 6, 2023)",
            "UPSTREAM_CONTENT_ORIGIN": "Tripadvisor online hotel reviews in Vietnam collected for customer experience (CX) academic study",
            "RESEARCH_REUSE_CONFIDENCE": "MEDIUM_ACADEMIC_CC_BY_4_0_AUXILIARY_ONLY",
            "classification": "AUXILIARY_ONLY",
            "schema_fields": ["Review", "Rating"],
            "schema_suitability_for_primary_poi_rag": "INSUFFICIENT_TWO_COLUMNS_ONLY_NO_HOTEL_NAME_OR_CITY",
            "row_count": {
                "total_rows": 20551,
            },
            "unique_review_count": {
                "measurable": True,
                "reported_reviews": 20551,
            },
            "target_city_coverage": {
                "measurable_from_metadata": False,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": None,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": None,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": None,
                "reason": (
                    "Direct HTTP Range header inspection (bytes=0-4095) verified the CSV header is "
                    "strictly `Review,Rating` (2 columns only). Hotel name, city, address, and coordinates "
                    "were stripped prior to publication."
                ),
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 20551,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "100% UNMAPPABLE without unsafe text-only guessing because hotel names and coordinates are absent.",
            },
            "category_coverage": {
                "covered": ["hotel"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "restaurant", "cafe", "market", "nightlife", "entertainment"],
            },
            "decision_rationale": (
                "Clean CC-BY-4.0 academic publication for hotel rating/sentiment modeling, but unusable "
                "for primary POI-grounded RAG because hotel identities and cities were removed."
            ),
        },
        {
            "candidate_rank": 5,
            "dataset_id": "hienbm/tripadvisor_vietnam",
            "mandatory_candidate_covered": "discovered_huggingface_candidate",
            "source_hub": "Hugging Face Datasets",
            "urls": ["https://huggingface.co/datasets/hienbm/tripadvisor_vietnam"],
            "accessibility": "PUBLIC_UNGATED (19.8 MB Parquet)",
            "DATASET_LICENSE": "UNSPECIFIED_ON_HF_CARD",
            "UPSTREAM_CONTENT_ORIGIN": "Tripadvisor Vietnam hotel reviews with 6 aspect sub-ratings",
            "RESEARCH_REUSE_CONFIDENCE": "LOW_UNSPECIFIED_LICENSE_AND_TRIPADVISOR_ORIGIN",
            "classification": "AUXILIARY_ONLY",
            "schema_fields": [
                "language",
                "input",
                "output (cleanliness, location, rooms, service, sleep_quality, value)",
            ],
            "schema_suitability_for_primary_poi_rag": "INSUFFICIENT_MISSING_POI_NAME_ADDRESS_COORDS_CITY",
            "row_count": {
                "total_rows": 23559,
                "train": 18847,
                "test": 4712,
            },
            "unique_review_count": {
                "measurable": True,
                "total_review_rows": 23559,
            },
            "target_city_coverage": {
                "measurable_from_metadata": False,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": None,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": None,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": None,
                "reason": "No hotel name, city, address, or coordinate fields in schema.",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 23559,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "100% UNMAPPABLE to Freeze v2 POIs due to missing place identity and coordinates.",
            },
            "category_coverage": {
                "covered": ["hotel"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "restaurant", "cafe", "market", "nightlife", "entertainment"],
            },
            "decision_rationale": "Auxiliary hotel aspect-polarity reference only; unmappable to canonical POIs.",
        },
        {
            "candidate_rank": 6,
            "dataset_id": "ThanThoai9x/vietnamese-food-images",
            "mandatory_candidate_covered": "ThanThoai9x/vietnamese-food-images",
            "source_hub": "Hugging Face Datasets",
            "urls": ["https://huggingface.co/datasets/ThanThoai9x/vietnamese-food-images"],
            "accessibility": "MANUAL_GATED_18_2_GB (36 Parquet shards; HTTP 401 without manual approval)",
            "DATASET_LICENSE": "CC-BY-NC-4.0 (declared on HF card)",
            "UPSTREAM_CONTENT_ORIGIN": "Google Maps scraped restaurant review photos and review text in Hồ Chí Minh City",
            "RESEARCH_REUSE_CONFIDENCE": "LOW_TO_MEDIUM_AMBIGUOUS_UPSTREAM_TOS",
            "classification": "REJECTED",
            "schema_fields": candidate_a_deep_audit["actual_schema"]["fields"],
            "schema_suitability_for_primary_poi_rag": (
                "HAS_PLACE_NAME_AND_COORDS_BUT_100_PCT_HO_CHI_MINH_CITY_AND_IMAGE_ROW_DUPLICATED"
            ),
            "row_count": {
                "image_rows": 34104,
                "unique_places": 1989,
            },
            "unique_review_count": {
                "measurable": False,
                "global_estimated_unique_review_id_range": "8000-17000",
                "target_city_unique_reviews_exact": 0,
            },
            "target_city_coverage": {
                "measurable_from_metadata": True,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": 0,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": 0,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": 0,
                "reason": "All 34,104 rows are in 9 districts of Hồ Chí Minh City (sum = 34,104 = 100.0%).",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 1989,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "0% geographic overlap with Freeze v2 destinations (Hà Nội, Đà Nẵng, Hạ Long, Hội An, Huế, Nha Trang).",
            },
            "category_coverage": {
                "covered": ["restaurant", "cafe"],
                "missing": ["attraction", "culture", "temple", "museum", "nature", "beach", "park", "hotel", "nightlife", "entertainment"],
            },
            "decision_rationale": (
                "Rejected as primary W07 corpus: 0 rows in Hà Nội, Đà Nẵng, or Hạ Long (100% HCMC), "
                "restaurant-only, manual-gated 18.2 GB image dataset, and ambiguous Google Maps upstream ToS."
            ),
        },
        {
            "candidate_rank": 7,
            "dataset_id": "MinhDS/ViHoRec (local data/restricted/vihorec/)",
            "mandatory_candidate_covered": "repository_existing_restricted_dataset",
            "source_hub": "Hugging Face / Local Restricted Snapshot",
            "urls": ["https://huggingface.co/datasets/MinhDS/ViHoRec"],
            "accessibility": "LOCAL_RESTRICTED_SNAPSHOT_PRESENT",
            "DATASET_LICENSE": "CC-BY-NC-4.0",
            "UPSTREAM_CONTENT_ORIGIN": "Vietnamese hotel rating matrix and hotel property metadata",
            "RESEARCH_REUSE_CONFIDENCE": "HIGH_FOR_REC_B_RATINGS_ZERO_FOR_TEXT_RAG",
            "classification": "REJECTED",
            "schema_fields": ["user_id", "item_id", "rating", "hotel_name", "address", "rating_score", "review_Debug"],
            "schema_suitability_for_primary_poi_rag": "REJECTED_ZERO_USER_REVIEW_TEXT",
            "row_count": {
                "rating_interactions": 17911,
                "hotels": 560,
            },
            "unique_review_count": {
                "measurable": True,
                "unique_text_reviews": 0,
            },
            "target_city_coverage": {
                "measurable_from_metadata": True,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": 0,
                "da_nang_unique_places": 120,
                "da_nang_unique_reviews": 0,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": 0,
                "reason": "120 Đà Nẵng hotels have numeric ratings only; 0 user review text across all 560 hotels.",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 120,
                "UNMAPPABLE": 440,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "Contains 0 review text and no coordinates.",
            },
            "category_coverage": {
                "covered": [],
                "missing": ["all_text_review_categories"],
            },
            "decision_rationale": "Retained for W5 REC-B collaborative filtering only; 0 user review text for W07 RAG.",
        },
        {
            "candidate_rank": 8,
            "dataset_id": "trungtrandinh/hotel_danang_vietnam + small HF tourism Q&A repos (Bach293/dulich_hanoi, thanh002/dulich, ducthiem05/dulich, tsang326/chatbot_dulich)",
            "mandatory_candidate_covered": "discovered_huggingface_tourism_candidates",
            "source_hub": "Hugging Face Datasets",
            "urls": [
                "https://huggingface.co/datasets/trungtrandinh/hotel_danang_vietnam",
                "https://huggingface.co/datasets/Bach293/dulich_hanoi",
            ],
            "accessibility": "PUBLIC_UNGATED",
            "DATASET_LICENSE": "UNSPECIFIED_ON_HF_CARD",
            "UPSTREAM_CONTENT_ORIGIN": "Templated SFT instruction/output property descriptions or image captions (<100 rows)",
            "RESEARCH_REUSE_CONFIDENCE": "LOW_NOT_REAL_USER_REVIEWS",
            "classification": "REJECTED",
            "schema_fields": ["instruction", "output"],
            "schema_suitability_for_primary_poi_rag": "REJECTED_SYNTHETIC_TEMPLATED_SUMMARIES_NOT_USER_REVIEWS",
            "row_count": {
                "hotel_danang_vietnam_sft_pairs": 7000,
                "dulich_hanoi_image_captions": 39,
            },
            "unique_review_count": {
                "measurable": True,
                "unique_text_reviews": 0,
            },
            "target_city_coverage": {
                "measurable_from_metadata": True,
                "ha_noi_unique_places": 0,
                "ha_noi_unique_reviews": 0,
                "da_nang_unique_places": 0,
                "da_nang_unique_reviews": 0,
                "ha_long_unique_places": 0,
                "ha_long_unique_reviews": 0,
                "reason": "Zero real user reviews; only templated hotel metadata descriptions or image captions.",
            },
            "canonical_mapping_feasibility": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_REVIEW_REQUIRED": 0,
                "UNMAPPABLE": 7039,
                "canonical_freeze_v2_pois_matched": 0,
                "reason": "Not a user review corpus.",
            },
            "category_coverage": {
                "covered": [],
                "missing": ["all_real_user_review_categories"],
            },
            "decision_rationale": "Rejected because SFT property descriptions and image captions are not real user reviews.",
        },
    ]

    # Section 11: Legitimate Targeted Collection Alternatives Comparison
    targeted_collection_alternatives = [
        {
            "option_id": "OPTION_1_RECOMMENDED_PREBOUND_CURATED_PROVENANCED_INTAKE",
            "title": (
                "Pre-Bound Canonical Freeze v2 POI Intake Template (60 POIs x 5 Reviews = 300 Reviews) "
                "with First-Party / Public-Research-Permitted Provenanced Curation"
            ),
            "recommended": True,
            "data_obtainable": (
                "Full 17-field W07 target schema including exact pre-bound `poi_id` from "
                "gomate_places_freeze_v2.json, `upstream_place_id` (osm/overture), `city`, "
                "`rating`, `rating_scale_max`, `review_text` (Vietnamese/English), `language`, "
                "`created_at`, `collected_at`, `source_ref`, `provenance`, `license_or_usage_class`, "
                "`mapping_method = EXACT_UPSTREAM_ID`, `mapping_confidence = 1.0`."
            ),
            "reviews_per_place": "5 to 10 reviews/POI (Scientific Minimum = 5; Preferred = 8-10)",
            "coverage": (
                "100% balanced across Hà Nội (20 POIs), Đà Nẵng (20 POIs), and Hạ Long (20 POIs) "
                "and across all 5 tourism category groups (attractions/culture, nature/beach, "
                "restaurants/cafes/markets, hotels, other tourism)."
            ),
            "cost_usd": 0.0,
            "account_or_api_requirements": "None (no paid API key, no credit card, no external approval delay).",
            "storage_and_reuse_constraints": (
                "Stored in gitignored `data/restricted/w07_reviews/` with deterministic SHA256 "
                "and provenance manifest committed in `data/manifests/`; first-party contributed "
                "or explicitly research-permitted reviews carry clean academic reuse rights."
            ),
            "automation_feasibility": (
                "HIGH_FOR_SCAFFOLDING_AND_VALIDATION: Agent deterministically exports the 60-POI "
                "canonical template from Freeze v2 (`poi_id`, `name`, `city`, `category`, `lat`, `lng`, "
                "`osm_id`) and validates all 17 schema fields, deduplication, and provenance offline."
            ),
            "scientific_reproducibility": (
                "HIGH: 100% deterministic `poi_id` binding before collection eliminates post-hoc "
                "entity-linking errors and guarantees reproducible SHA256 corpus freeze."
            ),
            "risk": "LOW (zero scraping, zero CAPTCHA/anti-bot bypass, zero platform ToS violation).",
        },
        {
            "option_id": "OPTION_2_CROWD_STUDENT_FIRST_PARTY_SURVEY_COLLECTION",
            "title": (
                "Structured Student/Contributor First-Party Vietnamese Travel Review Collection "
                "Under Explicit CC-BY-4.0 Consent on the 60 Canonical Freeze v2 POIs"
            ),
            "recommended": True,
            "data_obtainable": (
                "First-party Vietnamese & English visitor reviews written directly against the "
                "60 pre-selected Freeze v2 POIs with aspect ratings, star rating (1-5), visit period, "
                "and explicit CC-BY-4.0 academic release consent."
            ),
            "reviews_per_place": "5 to 8 reviews/POI (>= 300 reviews across 60 POIs)",
            "coverage": "Hà Nội (20 POIs), Đà Nẵng (20 POIs), Hạ Long (20 POIs) across all tourism categories.",
            "cost_usd": 0.0,
            "account_or_api_requirements": "None (Google Forms / CSV intake sheet managed by Project Owner).",
            "storage_and_reuse_constraints": (
                "100% clean first-party IP (CC-BY-4.0); can be stored offline and published as a "
                "reproducible thesis benchmark without third-party platform restrictions."
            ),
            "automation_feasibility": "MEDIUM (requires human contributors to submit 300 short reviews; automated CSV validation).",
            "scientific_reproducibility": "VERY_HIGH (permanently archivable and redistributable academic corpus).",
            "risk": "NONE (zero third-party platform ToS risk).",
        },
        {
            "option_id": "OPTION_3_GOOGLE_PLACES_OFFICIAL_API_CONDITIONAL_TIER_C",
            "title": (
                "Google Places API (New) Place Details (`reviews` Field) — Conditional Tier C "
                "(Strictly Capped at <= 5 Reviews/Place & Subject to Storage Terms Review)"
            ),
            "recommended": False,
            "data_obtainable": (
                "Up to 5 reviews per place (`GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5`), rating, "
                "relative/publish timestamp, author attribution, and language."
            ),
            "reviews_per_place": "Hard ceiling of 5 reviews/place (cannot support Preferred 8-12 or Stretch 10-15 tiers).",
            "coverage": (
                "Can cover 60 canonical Freeze v2 POIs x 5 reviews = 300 reviews (Scientific Minimum ceiling only)."
            ),
            "cost_usd": "0.00 under monthly Google Maps Platform free credit (60 Place Details calls), but requires billing-enabled GCP account.",
            "account_or_api_requirements": "Requires Project Owner Google Cloud billing account + Places API key + explicit storage terms sign-off.",
            "storage_and_reuse_constraints": (
                "`GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW`: "
                "Google Maps Platform Terms restrict permanent offline caching/redistribution of "
                "Google Places content outside compliant runtime/evaluation terms."
            ),
            "automation_feasibility": "HIGH (60 official REST calls), but blocked unless Project Owner approves terms.",
            "scientific_reproducibility": "LOW_TO_MEDIUM (API returns top-5 dynamic reviews which drift over time and cannot be redistributed in git).",
            "risk": "MEDIUM_TO_HIGH_TOS_STORAGE_RESTRICTION (preserved as NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW).",
        },
        {
            "option_id": "OPTION_4_TRIPADVISOR_CONTENT_API",
            "title": "Tripadvisor Content API (`location/{id}/reviews`)",
            "recommended": False,
            "data_obtainable": "Up to 3-5 recent reviews per location with commercial display obligations.",
            "reviews_per_place": "3 to 5 reviews/place",
            "coverage": "Commercial partner display only.",
            "cost_usd": "Requires commercial billing/contract tiers beyond basic evaluation.",
            "account_or_api_requirements": "Tripadvisor commercial API account and attribution compliance.",
            "storage_and_reuse_constraints": (
                "`TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = NOT_RECOMMENDED`: "
                "Terms prohibit offline academic dataset creation, permanent caching, and AI/ML dataset redistribution."
            ),
            "automation_feasibility": "NOT_AUTHORIZED",
            "scientific_reproducibility": "LOW (prohibited from permanent academic corpus storage).",
            "risk": "HIGH_EXCLUDED (`NOT_RECOMMENDED`).",
        },
    ]

    # Section 16 mandatory terminal decision values
    recommended_primary_source_strategy = "TARGETED_COLLECTION_REQUIRED"
    approved_public_datasets: list[str] = []
    auxiliary_datasets = [
        "phamluan/vn_msa_sar_v3",
        "phamluan/vn_msa_sar",
        "phamluan/vn_hotel_res_aspect_v3",
        "visolex/VLSP2018-ABSA-Restaurant",
        "visolex/VLSP2018-ABSA-Hotel",
        "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
        "mendeley:10.17632/dp8s59xnb7.1",
        "hienbm/tripadvisor_vietnam",
    ]
    rejected_datasets = [
        "ThanThoai9x/vietnamese-food-images",
        "MinhDS/ViHoRec",
        "trungtrandinh/hotel_danang_vietnam",
        "Bach293/dulich_hanoi",
        "thanh002/dulich",
        "ducthiem05/dulich",
        "tsang326/chatbot_dulich",
    ]
    targeted_collection_required = True
    targeted_collection_gaps = {
        "why_public_dataset_only_is_infeasible": (
            "100% of audited public Vietnamese review datasets either strip POI identity/coordinates/city "
            "(`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, `pqthinh232/*`, `mendeley:10.17632/dp8s59xnb7.1`, "
            "`hienbm/tripadvisor_vietnam`) resulting in 0 deterministically mappable POIs, or cover only "
            "Hồ Chí Minh City restaurants (`ThanThoai9x/vietnamese-food-images`: 34,104 / 34,104 rows in "
            "9 HCMC districts = 0 rows in Hà Nội, Đà Nẵng, or Hạ Long)."
        ),
        "public_dataset_covered_slice_in_target_cities": {
            "ha_noi_pois": 0,
            "da_nang_pois": 0,
            "ha_long_pois": 0,
            "total_canonical_pois_covered_by_public_datasets": 0,
            "total_provenanced_reviews_covered_by_public_datasets": 0,
        },
        "missing_slice_requiring_targeted_collection_scientific_minimum": {
            "target_canonical_pois_total": 60,
            "target_reviews_per_poi_min": 5,
            "target_new_reviews_total_min": 300,
            "by_city": {
                "Hà Nội": {"canonical_pois_needed": 20, "reviews_needed_min": 100},
                "Đà Nẵng": {"canonical_pois_needed": 20, "reviews_needed_min": 100},
                "Hạ Long": {"canonical_pois_needed": 20, "reviews_needed_min": 100},
            },
            "by_category_group": {
                "attractions_culture": {"canonical_pois_needed": 18, "reviews_needed_min": 90},
                "nature_beach": {"canonical_pois_needed": 6, "reviews_needed_min": 30},
                "restaurants_cafes_markets": {"canonical_pois_needed": 18, "reviews_needed_min": 90},
                "hotels": {"canonical_pois_needed": 15, "reviews_needed_min": 75},
                "other_tourism": {"canonical_pois_needed": 3, "reviews_needed_min": 15},
            },
        },
        "missing_slice_preferred_tier_optional": {
            "target_canonical_pois_range": "75-100",
            "target_reviews_per_poi_range": "8-12",
            "target_new_reviews_range": "600-1200",
        },
    }
    user_action_required = {
        "action_required": True,
        "do_not_request_gated_thanthoai9x_download": (
            "Project Owner does NOT need to request gated access or download the 18.2 GB "
            "`ThanThoai9x/vietnamese-food-images` dataset because its public card `Areas` table "
            "proves 100.0% of its 34,104 rows are in 9 districts of Hồ Chí Minh City (0 rows in "
            "Hà Nội, Đà Nẵng, or Hạ Long)."
        ),
        "exact_owner_steps_after_w07_a1_audit_gate": [
            "STEP_1_APPROVE_COLLECTION_PATH: Confirm selection of Option 1/2 (Pre-Bound 60-POI Freeze v2 Canonical Intake Template at data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl with >= 5 real/provenanced reviews per POI = >= 300 reviews across Hà Nội [20 POIs], Đà Nẵng [20 POIs], and Hạ Long [20 POIs]).",
            "STEP_2_POPULATE_OR_PROVIDE_LOCAL_FILE: Using the deterministic 60-POI canonical intake CSV/JSONL template generated from data/curated/gomate_places_freeze_v2.json (where poi_id, city, category, lat, lng, and osm_id are pre-filled), provide or approve >= 300 real/first-party/research-permitted reviews (>= 5 per POI) with source_ref, rating, language, created_at, and license_or_usage_class.",
            "STEP_3_OPTIONAL_AUXILIARY_ABSA_APPROVAL: Confirm whether public ungated `phamluan/vn_msa_sar_v3` (CC-BY-4.0) should be used strictly in a separated auxiliary aspect-extraction test (never mixed into the primary POI-linked retrieval index).",
        ],
    }
    expected_corpus_size = {
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
            "mendeley_dp8s59xnb7_hotel_reviews": 20551,
        },
    }
    expected_canonical_poi_coverage = {
        "canonical_universe_file": "data/curated/gomate_places_freeze_v2.json",
        "total_verified_canonical_pois": poi_baseline["verified_pois_all_6_destinations"],
        "three_target_cities_verified_pois": poi_baseline["three_target_cities_total_pois"],
        "three_target_cities_rec_a_core_pois": poi_baseline["three_target_cities_rec_a_core_pois"],
        "public_dataset_mappable_pois_in_target_cities": 0,
        "scientific_minimum_covered_pois": 60,
        "scientific_minimum_share_of_3_city_core_pct": round(
            60 / poi_baseline["three_target_cities_rec_a_core_pois"] * 100.0, 2
        ),
        "preferred_covered_pois_range": "75-100",
        "stretch_covered_pois": 110,
        "mapping_tier_achieved_by_prebound_collection": "EXACT_UPSTREAM_ID",
        "mapping_confidence": 1.0,
    }
    expected_city_coverage = {
        "target_cities": ["Hà Nội", "Đà Nẵng", "Hạ Long"],
        "aliases_audited": TARGET_CITY_ALIASES,
        "public_dataset_measurable_coverage": {
            "Hà Nội": {"unique_places": 0, "unique_reviews": 0},
            "Đà Nẵng": {"unique_places": 0, "unique_reviews": 0},
            "Hạ Long": {"unique_places": 0, "unique_reviews": 0},
        },
        "scientific_minimum_target_coverage": {
            "Hà Nội": {
                "canonical_pois": 20,
                "min_reviews_per_poi": 5,
                "expected_reviews": 100,
                "freeze_v2_available_pois": poi_baseline["by_target_city"]["Hà Nội"][
                    "verified_pois_total"
                ],
            },
            "Đà Nẵng": {
                "canonical_pois": 20,
                "min_reviews_per_poi": 5,
                "expected_reviews": 100,
                "freeze_v2_available_pois": poi_baseline["by_target_city"]["Đà Nẵng"][
                    "verified_pois_total"
                ],
            },
            "Hạ Long": {
                "canonical_pois": 20,
                "min_reviews_per_poi": 5,
                "expected_reviews": 100,
                "freeze_v2_available_pois": poi_baseline["by_target_city"]["Hạ Long"][
                    "verified_pois_total"
                ],
            },
        },
        "preferred_target_coverage": {
            "Hà Nội": {"canonical_pois": "25-34", "expected_reviews": "200-400"},
            "Đà Nẵng": {"canonical_pois": "25-33", "expected_reviews": "200-400"},
            "Hạ Long": {"canonical_pois": "25-33", "expected_reviews": "200-400"},
        },
    }
    expected_category_coverage = {
        "freeze_v2_three_target_cities_baseline_pois": poi_baseline[
            "three_target_cities_category_groups"
        ],
        "public_datasets_primary_rag_coverage": {
            "attractions_culture": 0,
            "nature_beach": 0,
            "restaurants_cafes_markets": 0,
            "hotels": 0,
            "other_tourism": 0,
        },
        "scientific_minimum_target_60_pois_300_reviews": {
            "attractions_culture": {
                "canonical_pois": 18,
                "expected_reviews": 90,
                "share_of_corpus_pct": 30.0,
            },
            "nature_beach": {
                "canonical_pois": 6,
                "expected_reviews": 30,
                "share_of_corpus_pct": 10.0,
            },
            "restaurants_cafes_markets": {
                "canonical_pois": 18,
                "expected_reviews": 90,
                "share_of_corpus_pct": 30.0,
            },
            "hotels": {
                "canonical_pois": 15,
                "expected_reviews": 75,
                "share_of_corpus_pct": 25.0,
            },
            "other_tourism": {
                "canonical_pois": 3,
                "expected_reviews": 15,
                "share_of_corpus_pct": 5.0,
            },
        },
        "restaurant_bias_mitigation": (
            "Prevents a restaurant-only corpus: 70.0% of the Scientific Minimum corpus (42 / 60 POIs, "
            "210 / 300 reviews) covers non-food tourism categories (attractions/culture 30%, hotels 25%, "
            "nature/beach 10%, other tourism 5%), matching GoMate's multi-category itinerary planner."
        ),
    }

    payload: dict[str, Any] = {
        "artifact_id": "w07_review_corpus_feasibility_v1",
        "artifact_version": "1.0.0",
        "task_id": "W07-A1",
        "task_title": "PUBLIC REVIEW CORPUS FEASIBILITY + ACQUISITION DECISION",
        "authority_and_gates": {
            "previous_gate": PREVIOUS_GATE,
            "previous_gate_decision": PREVIOUS_GATE_DECISION,
            "authoritative_develop_base_sha": AUTHORITATIVE_DEVELOP_BASE_SHA,
            "next_gate": NEXT_GATE,
            "w06_status": "CLOSED_IMMUTABLE",
            "w06_closure_internal_sha256_verified": w06_internal_sha,
            "w07_0_status": "COMPLETE_IMMUTABLE",
            "w07_0_audit_internal_sha256_verified": w07_0_internal_sha,
            "w07_0_audit_file_lf_sha256_verified": w07_0_lf_sha,
        },
        "execution_discipline_and_firewall": {
            "NEW_LLM_PROVIDER_CALLS": 0,
            "NEW_EMBEDDING_API_CALLS": 0,
            "NEW_RERANKER_API_CALLS": 0,
            "NEW_PAID_SERVICE_CALLS": 0,
            "SCRAPING_EXECUTED": False,
            "BULK_GATED_DATA_DOWNLOADED": False,
            "GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE": GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE,
            "GOOGLE_PLACES_OFFLINE_CORPUS_ROLE": GOOGLE_PLACES_OFFLINE_CORPUS_ROLE,
            "TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE": (
                TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE
            ),
        },
        "search_scope_and_methodology": {
            "repositories_searched": [
                "Hugging Face Datasets Hub (/api/datasets, datasets-server parquet metadata, public dataset cards)",
                "Mendeley Data Academic Repository (REST API v1 + HTTP Range header CSV inspection)",
                "Kaggle Datasets & GitHub Public Repositories",
                "VLSP Academic Shared Task Repositories (VLSP 2018 ABSA Restaurant & Hotel)",
                "Existing GoMate Repository Manifests (`data/manifests/review-dataset-candidates.yaml`, `data/manifests/review-provenance.json`)",
            ],
            "existing_repo_candidates_manifest_count": len(review_cand.get("candidates", [])),
            "target_fields_searched": [
                "review_text",
                "place_name",
                "address",
                "latitude",
                "longitude",
                "upstream_place_id",
                "rating",
                "review_date",
                "review_url/source_ref",
                "city",
                "provenance/license",
            ],
            "mandatory_candidates_evaluated": [
                "ThanThoai9x/vietnamese-food-images",
                "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
                "VLSP2018-ABSA-Restaurant",
                "phamluan/vn_msa_sar",
            ],
            "additional_discovered_candidates_evaluated": [
                "phamluan/vn_msa_sar_v3",
                "phamluan/vn_hotel_res_aspect_v3",
                "visolex/VLSP2018-ABSA-Hotel",
                "mendeley:10.17632/dp8s59xnb7.1 (CX Vietnamese hotel online reviews)",
                "hienbm/tripadvisor_vietnam",
                "trungtrandinh/hotel_danang_vietnam",
                "MinhDS/ViHoRec",
                "Bach293/dulich_hanoi, thanh002/dulich, ducthiem05/dulich, tsang326/chatbot_dulich",
            ],
        },
        "candidate_a_deep_audit": candidate_a_deep_audit,
        "candidate_evaluation_matrix": candidate_datasets,
        "canonical_poi_baseline_and_category_balance": poi_baseline,
        "corpus_quality_planning_tiers": {
            "scientific_minimum": {
                "canonical_pois_min": 60,
                "canonical_pois_per_city_approx": 20,
                "real_provenanced_reviews_per_poi_min": 5,
                "total_reviews_min": 300,
                "role": "MANDATORY_MINIMUM_TO_UNBLOCK_W07_RETRIEVAL_EVALUATION",
            },
            "preferred": {
                "canonical_pois_range": "75-100",
                "real_provenanced_reviews_per_poi_range": "8-12",
                "total_reviews_range": "600-1200",
                "role": "DESIRABLE_NOT_MANDATORY",
            },
            "stretch": {
                "canonical_pois_approx": 110,
                "real_provenanced_reviews_per_poi_range": "10-15",
                "total_reviews_range": "1100-1650",
                "role": "ASPIRATIONAL_EXTENSION",
            },
        },
        "targeted_collection_alternatives_comparison": targeted_collection_alternatives,
        "cost_and_infrastructure_requirements": {
            "paid_api_required": False,
            "gpu_required": False,
            "dedicated_server_required": False,
            "proxy_required": False,
            "vps_required": False,
            "browser_automation_required": False,
            "storage_required": (
                "Local gitignored directory `data/restricted/w07_reviews/` (< 5 MB for 300-1,200 "
                "JSONL reviews) plus committed SHA256 manifest in `data/manifests/`."
            ),
            "rationale": (
                "No paid API, GPU, server, proxy, VPS, or browser automation is needed for W07-A1 "
                "or the recommended pre-bound 60-POI / 300-review targeted collection path."
            ),
        },
    }

    # Compute internal SHA256 before attaching artifact_sha256 and the 11 terminal keys,
    # Wait: compute_internal_sha256 hashes all keys except `artifact_sha256` with sort_keys=True,
    # so key position does not change compute_internal_sha256! Placing `artifact_sha256` BEFORE
    # the 11 mandatory terminal keys guarantees that the JSON object literally ends with the
    # exact 11 required keys from Section 16!
    terminal_keys_dict: dict[str, Any] = {
        "RECOMMENDED_PRIMARY_SOURCE_STRATEGY": recommended_primary_source_strategy,
        "APPROVED_PUBLIC_DATASETS": approved_public_datasets,
        "AUXILIARY_DATASETS": auxiliary_datasets,
        "REJECTED_DATASETS": rejected_datasets,
        "TARGETED_COLLECTION_REQUIRED": targeted_collection_required,
        "TARGETED_COLLECTION_GAPS": targeted_collection_gaps,
        "USER_ACTION_REQUIRED": user_action_required,
        "EXPECTED_CORPUS_SIZE": expected_corpus_size,
        "EXPECTED_CANONICAL_POI_COVERAGE": expected_canonical_poi_coverage,
        "EXPECTED_CITY_COVERAGE": expected_city_coverage,
        "EXPECTED_CATEGORY_COVERAGE": expected_category_coverage,
    }

    full_without_sha = {**payload, **terminal_keys_dict}
    internal_sha = compute_internal_sha256(full_without_sha)

    final_payload: dict[str, Any] = {
        **payload,
        "artifact_sha256": internal_sha,
        **terminal_keys_dict,
    }

    # Verify the last 11 keys of final_payload match MANDATORY_TERMINAL_KEYS in exact order
    tail_keys = tuple(list(final_payload.keys())[-len(MANDATORY_TERMINAL_KEYS) :])
    if tail_keys != MANDATORY_TERMINAL_KEYS:
        raise ValueError(
            f"Terminal keys mismatch: {tail_keys} != {MANDATORY_TERMINAL_KEYS}"
        )

    return final_payload


def render_w07_a1_markdown(payload: dict[str, Any]) -> str:
    ca = payload["candidate_a_deep_audit"]
    pb = payload["canonical_poi_baseline_and_category_balance"]
    lines = [
        "# W07-A1 — Public Review Corpus Feasibility + Acquisition Decision",
        "",
        "## 0. Authority & Gate Discipline",
        "",
        f"- **Previous Gate:** `{payload['authority_and_gates']['previous_gate']}`",
        f"- **Authoritative Base:** `develop@{payload['authority_and_gates']['authoritative_develop_base_sha']}`",
        f"- **W06 Closure Status:** `{payload['authority_and_gates']['w06_status']}` "
        f"(verified internal SHA256: `{payload['authority_and_gates']['w06_closure_internal_sha256_verified']}`)",
        f"- **W07-0 Readiness Audit Status:** `{payload['authority_and_gates']['w07_0_status']}` "
        f"(verified internal SHA256: `{payload['authority_and_gates']['w07_0_audit_internal_sha256_verified']}`, "
        f"verified LF file SHA256: `{payload['authority_and_gates']['w07_0_audit_file_lf_sha256_verified']}`)",
        f"- **Artifact Internal SHA256:** `{payload['artifact_sha256']}`",
        f"- **Next Gate:** `{payload['authority_and_gates']['next_gate']}`",
        "",
        "---",
        "",
        "## 1. Broad Public Search & Candidate Evaluation Matrix",
        "",
        "We audited public and research-accessible Vietnamese travel, hospitality, and restaurant review datasets across Hugging Face Datasets (`datasets-server` + dataset cards), Mendeley Data (`DOI: 10.17632/dp8s59xnb7.1`), Kaggle, GitHub, and VLSP shared tasks:",
        "",
        "| Rank | Dataset ID | Hub / Source | License (`DATASET_LICENSE`) | Upstream Origin (`UPSTREAM_CONTENT_ORIGIN`) | Reuse Confidence | Unique Reviews | Target-City Coverage (Hà Nội / Đà Nẵng / Hạ Long) | Canonical Mapping to Freeze v2 | Classification |",
        "|---:|---|---|---|---|---|---:|---|---|---|",
    ]
    for c in payload["candidate_evaluation_matrix"]:
        ur = c["unique_review_count"]
        ur_str = (
            str(
                ur.get(
                    "vn_msa_sar_v3_unique_review_ids",
                    ur.get(
                        "combined_unique_reviews",
                        ur.get(
                            "unique_review_ids",
                            ur.get(
                                "reported_reviews",
                                ur.get("total_review_rows", ur.get("unique_text_reviews", "N/A")),
                            ),
                        ),
                    ),
                )
            )
            if ur.get("measurable")
            else f"~{ur.get('global_estimated_unique_review_id_range')} global (0 in target cities)"
        )
        tc = c["target_city_coverage"]
        tc_str = (
            f"{tc['ha_noi_unique_places']} / {tc['da_nang_unique_places']} / {tc['ha_long_unique_places']} places"
            if tc["measurable_from_metadata"]
            else "Unmeasurable (no place/city/coord metadata)"
        )
        cm = c["canonical_mapping_feasibility"]
        cm_str = f"`{cm['canonical_freeze_v2_pois_matched']}` matched (`100% UNMAPPABLE`)"
        lines.append(
            f"| {c['candidate_rank']} | `{c['dataset_id']}` | {c['source_hub']} | "
            f"{c['DATASET_LICENSE']} | {c['UPSTREAM_CONTENT_ORIGIN']} | "
            f"`{c['RESEARCH_REUSE_CONFIDENCE']}` | {ur_str} | {tc_str} | {cm_str} | "
            f"**`{c['classification']}`** |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Candidate A Deep Audit (`ThanThoai9x/vietnamese-food-images`)",
            "",
            f"- **Accessibility & Gated Access:** Public card visible at `{ca['url']}`, but **`gated = manual`** (`{ca['accessibility']['parquet_shards']}` Parquet shards, **`{ca['accessibility']['download_size_gb']} GB`**). Unauthenticated `/api/datasets` and `datasets-server` requests return `HTTP 401 Unauthorized` without manual author approval.",
            f"- **License & Origin Classification:**",
            f"  - `DATASET_LICENSE`: `{ca['license_and_origin']['DATASET_LICENSE']}`",
            f"  - `UPSTREAM_CONTENT_ORIGIN`: `{ca['license_and_origin']['UPSTREAM_CONTENT_ORIGIN']}`",
            f"  - `RESEARCH_REUSE_CONFIDENCE`: `{ca['license_and_origin']['RESEARCH_REUSE_CONFIDENCE']}`",
            f"- **Actual Schema (`{ca['actual_schema']['field_count']}` fields):** `{', '.join(ca['actual_schema']['fields'])}`.",
            f"- **Review Text vs. Image-Row Multiplicity (`UNIQUE_REVIEW_ID_COUNT`):**",
            f"  - `text` is real Google Maps user review text (`text_translated` is its translation), accompanied by `place_name`, `address`, `lat`, `lng`, `place_rating`, `review_rating`, `review_id`, and `crawled_at`.",
            f"  - However, the dataset's `34,104` rows are keyed by **`photo_id` (food image rows)** across `1,989` unique places (`~17.15` image rows/place). Because a single Google Maps restaurant review (`review_id`) frequently attaches multiple food photos, counting rows as reviews inflates review counts (`UNIQUE_REVIEW_ID_COUNT` globally is bounded below `34,104`, estimated at `{ca['multiplicity_and_unique_review_analysis']['UNIQUE_REVIEW_ID_COUNT']['estimated_unique_review_id_range']}`, and is **`0`** in our target cities).",
            "- **Smoking-Gun Geographic Proof (0% Coverage in Hà Nội, Đà Nẵng, and Hạ Long):**",
            "  - The public dataset card `Areas` breakdown lists 9 `search_area` districts in **Hồ Chí Minh City**:",
        ]
    )
    for area, cnt in ca["geographic_coverage_proof"]["search_areas_reported_on_card"].items():
        lines.append(f"    - `{area}`: `{cnt:,}` rows")
    lines.extend(
        [
            f"  - **Exact Sum of the 9 Hồ Chí Minh City Districts:** **`{ca['geographic_coverage_proof']['sum_of_9_hcmc_districts']:,}` / `34,104` rows (`100.00%`)**.",
            "  - Therefore:",
            "    - **Hà Nội coverage:** `0` unique places / `0` unique reviews (`0.0%`)",
            "    - **Đà Nẵng coverage:** `0` unique places / `0` unique reviews (`0.0%`)",
            "    - **Hạ Long coverage:** `0` unique places / `0` unique reviews (`0.0%`)",
            "    - **Canonical Mapping to `gomate_places_freeze_v2.json` (`759` POIs):** **`0` mappable POIs (`100% UNMAPPABLE`)**.",
            "- **Verdict:** **`REJECTED`** (and Project Owner does **not** need to request gated access or download the `18.2 GB` archive).",
            "",
            "---",
            "",
            "## 3. Canonical POI Category Balance & Why Public Datasets Cannot Ground Primary RAG",
            "",
            f"- Across GoMate's three target cities in `data/curated/gomate_places_freeze_v2.json` (`{pb['three_target_cities_total_pois']}` total verified POIs; `{pb['three_target_cities_rec_a_core_pois']}` REC-A core POIs):",
            f"  - `attractions_culture` (`attraction`, `culture`, `temple`, `museum`): `{pb['three_target_cities_category_groups']['attractions_culture']}` POIs",
            f"  - `nature_beach` (`nature`, `beach`, `park`): `{pb['three_target_cities_category_groups']['nature_beach']}` POIs",
            f"  - `restaurants_cafes_markets` (`restaurant`, `cafe`, `market`): `{pb['three_target_cities_category_groups']['restaurants_cafes_markets']}` POIs (`restaurant` specifically = `{pb['three_target_cities_raw_categories']['restaurant']}` POIs = `{pb['three_target_cities_restaurant_only_poi_share_pct']}%`)",
            f"  - `hotels` (`hotel`): `{pb['three_target_cities_category_groups']['hotels']}` POIs",
            f"  - `other_tourism` (`nightlife`, `entertainment`): `{pb['three_target_cities_category_groups']['other_tourism']}` POIs",
            f"- **Non-food tourism share:** **`{pb['three_target_cities_non_food_poi_share_pct']}%`** of target-city POIs are non-food categories (`402 / 626`).",
            "- Every public Vietnamese review dataset with ungated text (`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, `pqthinh232/*`, `mendeley:10.17632/dp8s59xnb7.1`, `hienbm/tripadvisor_vietnam`) stripped `place_name`, `address`, `latitude`, `longitude`, and `city` prior to release, yielding **`0` mappable canonical POIs**.",
            "",
            "---",
            "",
            "## 4. Targeted Collection Alternatives & Firewall Preservation",
            "",
            "- **Google / Tripadvisor Firewall Constants Preserved:**",
            f"  - `GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = {payload['execution_discipline_and_firewall']['GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE']}`",
            f"  - `GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = {payload['execution_discipline_and_firewall']['GOOGLE_PLACES_OFFLINE_CORPUS_ROLE']}`",
            f"  - `TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = {payload['execution_discipline_and_firewall']['TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE']}`",
            "- **Recommended Primary Acquisition Strategy (`TARGETED_COLLECTION_REQUIRED`):**",
            "  - Bind collection **directly to a pre-selected manifest of `60` canonical POIs from `gomate_places_freeze_v2.json`** (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long) with `>= 5` real/provenanced reviews per POI (`>= 300` reviews total for the Scientific Minimum tier) so `poi_id` and `upstream_place_id` (`EXACT_UPSTREAM_ID`, confidence `1.0`) are locked *before* review intake, with zero scraping and zero post-hoc name-matching ambiguity.",
            "  - Use `phamluan/vn_msa_sar_v3` (`CC-BY-4.0`, `18,609` unique reviews) and `VLSP2018-ABSA` strictly as **separated auxiliary datasets** for aspect vocabulary and ABSA evaluation.",
            "",
            "---",
            "",
            "## 5. Authoritative Terminal Decision Keys",
            "",
            "```json",
            json.dumps(
                {k: payload[k] for k in MANDATORY_TERMINAL_KEYS},
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_w07_a1_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    payload = build_w07_a1_feasibility_payload(repo_root)
    json_path = repo_root / FEASIBILITY_JSON_RELPATH
    md_path = repo_root / FEASIBILITY_MD_RELPATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    md_text = render_w07_a1_markdown(payload)

    json_path.write_bytes(json_text.encode("utf-8"))
    md_path.write_bytes(md_text.encode("utf-8"))
    return payload


def verify_w07_a1_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    expected_payload = build_w07_a1_feasibility_payload(repo_root)
    json_path = repo_root / FEASIBILITY_JSON_RELPATH
    md_path = repo_root / FEASIBILITY_MD_RELPATH

    if not json_path.exists():
        raise FileNotFoundError(f"Missing W07-A1 JSON artifact: {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing W07-A1 Markdown report: {md_path}")

    on_disk = json.loads(json_path.read_text(encoding="utf-8"))
    if on_disk != expected_payload:
        raise ValueError("On-disk W07-A1 JSON does not match expected deterministic payload.")

    recorded_sha = on_disk.get("artifact_sha256")
    computed_sha = compute_internal_sha256(on_disk)
    if recorded_sha != computed_sha:
        raise ValueError(
            f"W07-A1 internal SHA256 mismatch: recorded={recorded_sha} computed={computed_sha}"
        )

    tail_keys = tuple(list(on_disk.keys())[-len(MANDATORY_TERMINAL_KEYS) :])
    if tail_keys != MANDATORY_TERMINAL_KEYS:
        raise ValueError(
            f"On-disk JSON does not end with mandatory keys: {tail_keys} != {MANDATORY_TERMINAL_KEYS}"
        )

    expected_md = render_w07_a1_markdown(expected_payload)
    actual_md = md_path.read_text(encoding="utf-8")
    if actual_md != expected_md:
        raise ValueError("On-disk W07-A1 Markdown report is out of sync with JSON payload.")

    return {
        "status": "PASS",
        "json_path": FEASIBILITY_JSON_RELPATH,
        "md_path": FEASIBILITY_MD_RELPATH,
        "internal_sha256": computed_sha,
        "file_sha256": compute_file_sha256(json_path),
        "file_lf_sha256": compute_lf_normalized_sha256(json_path),
        "md_lf_sha256": compute_lf_normalized_sha256(md_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify W07-A1 Public Review Corpus Feasibility artifacts."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write",
        action="store_true",
        help="Deterministically write W07-A1 JSON and Markdown artifacts.",
    )
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify on-disk W07-A1 artifacts without modifying files.",
    )
    args = parser.parse_args(argv)

    if args.write:
        write_w07_a1_artifacts(REPO_ROOT)
    result = verify_w07_a1_artifacts(REPO_ROOT)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
