#!/usr/bin/env python3
"""W07-A4P Permitted Public Review Acquisition, Mapping, Deduplication & Aggregate Progress Verifier (v1).

Responsibilities:
1. Verify upstream scientific immutability (W06, W07-0, W07-A1, W07-A2 60-POI manifest,
   W07-A3 Google Forms launch package, and W07-A4H Assisted First-Party Collection package).
2. Document and evaluate all 18 investigated public/academic candidate sources across
   Hugging Face, Zenodo, Mendeley Data, GitHub, Kaggle, VLSP shared tasks, and commercial APIs.
3. Enforce strict public review intake rules:
   - Allowed source classifications: `APPROVED_PUBLIC_SOURCE`, `CONDITIONAL_SOURCE`,
     `AUXILIARY_ONLY`, `REJECTED_SOURCE`.
   - Ambiguous/unspecified license or reuse rights -> `QUARANTINE_REUSE_UNCLEAR` (never counted as accepted).
   - Allowed POI mapping methods: `EXACT_UPSTREAM_ID`, `GEO_NAME_HIGH_CONFIDENCE`, `MANUAL_VERIFIED`.
   - Rejected POI mapping methods: `NAME_ONLY_AUTOMATIC`, `UNMAPPABLE`.
   - Multi-image row deduplication by `source_review_id` before counting unique reviews, plus
     deduplication on `source_review_id`, normalized `review_text`, and `(poi_id, normalized_review_text)`.
   - Human/public provenance separation: public reviews NEVER use `FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1`
     or `FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1` and NEVER carry a first-party `consent_record_id`.
   - Zero artificial/LLM-generated or rewritten reviews (`LLM_GENERATED_PUBLIC_REVIEWS = 0`,
     `NEW_LLM_PROVIDER_CALLS = 0`) and zero unauthorized bulk scraping (`BULK_SCRAPING_EXECUTED = false`).
4. Maintain separate git-ignored restricted output (`data/restricted/w07_reviews/w07_public_candidate_reviews_v1.jsonl`)
   and generate/verify the committed aggregate artifacts:
   - `data/evaluation/w07/w07_public_review_acquisition_v1.json`
   - `docs/research/w07_public_review_acquisition.md`
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    import_w07_assisted_reviews_v1 as w07_a4h,
    import_w07_contributor_reviews_v1 as w07_a3_import,
    report_w07_review_collection_progress as w07_a3_progress,
    run_w07_data_rag_readiness_audit as w07_0_audit,
    run_w07_review_corpus_feasibility as w07_a1,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w06_scientific_closure as w06_closure,
)

TASK_ID = "W07-A4P-PERMITTED-PUBLIC-REVIEW-ACQUISITION"
PREVIOUS_ACCEPTED_GATE = (
    "W07-A4H-ASSISTED-FIRST-PARTY-COLLECTION-POSTMERGE-CHATGPT-AUDIT = PASS"
)
NEXT_GATE = "W07-A4P-PERMITTED-PUBLIC-REVIEW-ACQUISITION-CHATGPT-AUDIT"
AUTHORITATIVE_BASE_DEVELOP_SHA = "40d9908b52214967bf412f5caf2f06cc866da409"

EXPECTED_A2_MANIFEST_INTERNAL_SHA256 = (
    "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b"
)
EXPECTED_A3_FORM_DEF_INTERNAL_SHA256 = (
    "9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a"
)
EXPECTED_A3_APPS_SCRIPT_LF_SHA256 = (
    "5e87dcf74d2bc4840792701bbd852c75781ef6ba938ac8c1eacad6d2a430be71"
)
EXPECTED_A3_PROGRESS_INTERNAL_SHA256 = (
    "a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70"
)
EXPECTED_A4H_TEMPLATE_LF_SHA256 = (
    "747da9d0b0033ae5ca7649bf456fde59f79f895f1248985ab1f521b43ca42bd9"
)
EXPECTED_A4H_PROGRESS_INTERNAL_SHA256 = (
    "b34e32af7aba9b5ee95d13f30781fbef3e15a4cb9b6a26c7b97fa1489f13ecdb"
)
EXPECTED_A4H_PROGRESS_LF_SHA256 = (
    "79095ce10fbf50a838d9e1a607001d821413ced6e8d6e7ad5ac2fd6e7c6239d1"
)
EXPECTED_A4H_GUIDE_LF_SHA256 = (
    "4e8e133c877ec748fd7bdc66b2f3b50ab72c46686018899b1758779d18409814"
)

PUBLIC_ACQUISITION_JSON_RELPATH = (
    "data/evaluation/w07/w07_public_review_acquisition_v1.json"
)
PUBLIC_SOURCE_RECEIPTS_JSON_RELPATH = (
    "data/evaluation/w07/w07_public_source_evidence_receipts_v1.json"
)
PUBLIC_ACQUISITION_MD_RELPATH = "docs/research/w07_public_review_acquisition.md"
RESTRICTED_PUBLIC_SOURCES_DIR_RELPATH = "data/restricted/w07_reviews/public_sources"
RESTRICTED_PUBLIC_CANDIDATES_JSONL_RELPATH = (
    "data/restricted/w07_reviews/w07_public_candidate_reviews_v1.jsonl"
)

ZENODO_7967494_COORD_PUBLISHED_MD5 = "50fa8970a26ae513b8295bbcdfacd0b0"
ZENODO_7967494_COORD_LOCAL_SHA256 = (
    "4315726de6f5cebe7145e512d29baf0b341a31bf134ecc2abf23c2e22396ff7e"
)
ZENODO_7967494_COORD_BYTES = 263557

ZENODO_7967494_REVIEWS_PUBLISHED_MD5 = "ebae7b018af787978b29cf15591b7e96"
ZENODO_7967494_REVIEWS_LOCAL_SHA256 = (
    "9e79268489e47506051496c4ebd626fab0cb81d3a6d402ab0c5c5283f0d29d90"
)
ZENODO_7967494_REVIEWS_BYTES = 64460152

PUBLIC_ACQUISITION_VERSION = "1.0.0"
ACCESS_DATE_UTC = "2026-11-02"

SOURCE_CLASSIFICATIONS: tuple[str, ...] = (
    "APPROVED_PUBLIC_SOURCE",
    "CONDITIONAL_SOURCE",
    "AUXILIARY_ONLY",
    "REJECTED_SOURCE",
)

ALLOWED_PUBLIC_MAPPING_METHODS: tuple[str, ...] = (
    "EXACT_UPSTREAM_ID",
    "GEO_NAME_HIGH_CONFIDENCE",
    "MANUAL_VERIFIED",
)
REJECTED_PUBLIC_MAPPING_METHODS: tuple[str, ...] = (
    "NAME_ONLY_AUTOMATIC",
    "UNMAPPABLE",
)

FORBIDDEN_FIRST_PARTY_PROVENANCE_CLASSES: frozenset[str] = frozenset(
    {
        "FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1",
        "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1",
    }
)

PUBLIC_PROVENANCE_CLASSES: dict[str, str] = {
    "PUBLIC_OPEN_LICENSED_DATASET_V1": (
        "Publicly published dataset with explicit open license (CC-BY-4.0 / CC0 / MIT / Apache-2.0) "
        "and verifiable canonical POI linkage."
    ),
    "PUBLIC_ACADEMIC_CC_BY_4_0_V1": (
        "Peer-reviewed or institutional academic repository release under CC-BY-4.0 with "
        "verifiable canonical POI linkage."
    ),
}

APPROVED_OPEN_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-4.0",
        "CC0-1.0",
        "MIT",
        "APACHE-2.0",
        "ODC-BY-1.0",
    }
)

GEO_HIGH_CONFIDENCE_MAX_DISTANCE_METERS = 150.0
GEO_HIGH_CONFIDENCE_MIN_NAME_SIMILARITY = 0.60
MAX_PUBLIC_REVIEWS_PER_POI_CAP = 10
MIN_PUBLIC_REVIEW_TEXT_CHARS = 15

PRIMARY_CANDIDATE_SCHEMA_FIELDS: tuple[str, ...] = (
    "review_id",
    "poi_id",
    "upstream_place_id",
    "city",
    "source",
    "source_review_id",
    "rating",
    "rating_scale_max",
    "review_text",
    "language",
    "created_at",
    "collected_at",
    "source_ref",
    "provenance",
    "license_or_usage_class",
    "mapping_method",
    "mapping_confidence",
)


def verify_upstream_immutability(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify W06, W07-0, W07-A1, W07-A2, W07-A3, and W07-A4H committed artifacts remain untouched."""
    w06_res = w06_closure.compute_closure_internal_sha256(
        w06_closure.build_closure_payload()
    )
    if w06_res != w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256:
        raise ValueError(f"FAIL CLOSED: W06 closure internal SHA mismatch: {w06_res}")

    w07_0_res = w07_0_audit.verify_w07_audit_artifacts(repo_root)
    if w07_0_res["status"] != "PASS":
        raise ValueError("FAIL CLOSED: W07-0 readiness audit verification failed.")

    w07_a1_res = w07_a1.verify_w07_a1_artifacts(repo_root)
    if w07_a1_res["status"] != "PASS":
        raise ValueError("FAIL CLOSED: W07-A1 feasibility verification failed.")

    w07_a2_res = w07_a2.verify_w07_a2_artifacts(repo_root)
    if (
        w07_a2_res["status"] != "PASS"
        or w07_a2_res["manifest_internal_sha256"] != EXPECTED_A2_MANIFEST_INTERNAL_SHA256
    ):
        raise ValueError("FAIL CLOSED: W07-A2 manifest verification failed.")

    w07_a3_form_res = w07_a3_import.verify_form_definition_artifacts(repo_root)
    w07_a3_prog_res = w07_a3_progress.verify_collection_progress_artifact(repo_root)
    if (
        w07_a3_form_res["form_definition_internal_sha256"]
        != EXPECTED_A3_FORM_DEF_INTERNAL_SHA256
        or w07_a3_form_res["apps_script_lf_sha256"] != EXPECTED_A3_APPS_SCRIPT_LF_SHA256
        or w07_a3_prog_res["progress_internal_sha256"]
        != EXPECTED_A3_PROGRESS_INTERNAL_SHA256
    ):
        raise ValueError("FAIL CLOSED: W07-A3 artifact hash mismatch.")

    w07_a4h_res = w07_a4h.verify_combined_first_party_progress_artifact(repo_root)
    if (
        w07_a4h_res["status"] != "PASS"
        or w07_a4h_res["assisted_template_lf_sha256"] != EXPECTED_A4H_TEMPLATE_LF_SHA256
        or w07_a4h_res["combined_progress_internal_sha256"]
        != EXPECTED_A4H_PROGRESS_INTERNAL_SHA256
        or w07_a4h_res["combined_progress_file_lf_sha256"]
        != EXPECTED_A4H_PROGRESS_LF_SHA256
        or w07_a4h_res["assisted_guide_lf_sha256"] != EXPECTED_A4H_GUIDE_LF_SHA256
    ):
        raise ValueError("FAIL CLOSED: W07-A4H artifact hash mismatch.")

    return {
        "w06_closure_internal_sha256": w06_res,
        "w07_0_audit_internal_sha256": w07_0_res["json_internal_sha256"],
        "w07_a1_feasibility_internal_sha256": w07_a1_res["internal_sha256"],
        "w07_a2_manifest_internal_sha256": w07_a2_res["manifest_internal_sha256"],
        "w07_a2_intake_status_internal_sha256": w07_a2_res[
            "intake_status_internal_sha256"
        ],
        "w07_a3_form_definition_internal_sha256": w07_a3_form_res[
            "form_definition_internal_sha256"
        ],
        "w07_a3_apps_script_lf_sha256": w07_a3_form_res["apps_script_lf_sha256"],
        "w07_a3_progress_internal_sha256": w07_a3_prog_res["progress_internal_sha256"],
        "w07_a4h_template_lf_sha256": w07_a4h_res["assisted_template_lf_sha256"],
        "w07_a4h_progress_internal_sha256": w07_a4h_res[
            "combined_progress_internal_sha256"
        ],
        "w07_a4h_progress_lf_sha256": w07_a4h_res["combined_progress_file_lf_sha256"],
        "w07_a4h_guide_lf_sha256": w07_a4h_res["assisted_guide_lf_sha256"],
    }


def _strip_accents_lower(text: str) -> str:
    replaced = (text or "").replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", replaced)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def _normalize_text_for_dedup(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def compute_haversine_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Deterministic Haversine distance in meters between two WGS84 coordinates."""
    earth_radius_m = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    )
    return 2.0 * earth_radius_m * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Deterministic token + substring similarity in [0.0, 1.0] on normalized place names."""
    norm_a = _strip_accents_lower(name_a)
    norm_b = _strip_accents_lower(name_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / float(len(tokens_a | tokens_b))
    if norm_a in norm_b or norm_b in norm_a:
        overlap = min(len(tokens_a), len(tokens_b)) / float(
            max(len(tokens_a), len(tokens_b))
        )
        return max(jaccard, round(0.65 + 0.35 * overlap, 4))
    return round(jaccard, 4)


def map_public_record_to_frozen_poi(
    record: dict[str, Any],
    *,
    manifest_payload: dict[str, Any],
    manual_verified_lookup: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    """Map a candidate public review record to the frozen 60-POI manifest (Section 6).

    Allowed mapping classes:
      - `EXACT_UPSTREAM_ID`
      - `GEO_NAME_HIGH_CONFIDENCE`
      - `MANUAL_VERIFIED`
    Rejected mapping classes:
      - `NAME_ONLY_AUTOMATIC`
      - `UNMAPPABLE`
    """
    pois = manifest_payload["pois"]
    pois_by_id = {p["poi_id"]: p for p in pois}

    # Map upstream source_ids (e.g. "osm:way/37625751", "overture:...") and raw osm_id/overture_id
    upstream_index: dict[str, dict[str, Any]] = {}
    for p in pois:
        for sid in p.get("source_ids", []):
            upstream_index[sid.strip().lower()] = p
        if p.get("osm_id"):
            upstream_index[str(p["osm_id"]).strip().lower()] = p
            upstream_index[f"osm:{str(p['osm_id']).strip().lower()}"] = p
        if p.get("overture_id"):
            upstream_index[str(p["overture_id"]).strip().lower()] = p
            upstream_index[f"overture:{str(p['overture_id']).strip().lower()}"] = p

    # 1. Check EXACT_UPSTREAM_ID
    raw_up_id = str(record.get("upstream_place_id") or "").strip().lower()
    if raw_up_id and raw_up_id in upstream_index:
        matched_poi = upstream_index[raw_up_id]
        return {
            "accepted_mapping": True,
            "mapping_method": "EXACT_UPSTREAM_ID",
            "mapping_confidence": 1.0,
            "poi_id": matched_poi["poi_id"],
            "canonical_city": matched_poi["city"],
            "upstream_place_id": record.get("upstream_place_id"),
            "evidence": {
                "matched_upstream_place_id": record.get("upstream_place_id"),
                "canonical_poi_name": matched_poi["name"],
            },
        }

    # 2. Check MANUAL_VERIFIED lookup table `(source_id, source_place_id)` -> `poi_id`
    source_key = (
        str(record.get("source") or "").strip(),
        str(record.get("source_place_id") or record.get("upstream_place_id") or "").strip(),
    )
    if (
        manual_verified_lookup
        and source_key in manual_verified_lookup
        and manual_verified_lookup[source_key] in pois_by_id
    ):
        matched_poi = pois_by_id[manual_verified_lookup[source_key]]
        return {
            "accepted_mapping": True,
            "mapping_method": "MANUAL_VERIFIED",
            "mapping_confidence": 0.95,
            "poi_id": matched_poi["poi_id"],
            "canonical_city": matched_poi["city"],
            "upstream_place_id": record.get("upstream_place_id")
            or (
                f"source_place:{source_key[1]}" if source_key[1] else None
            ),
            "evidence": {
                "manual_verified_source_key": list(source_key),
                "canonical_poi_name": matched_poi["name"],
            },
        }

    # 3. Check GEO_NAME_HIGH_CONFIDENCE (requires valid coordinates + high name similarity + city/category compatibility)
    raw_place_name = str(record.get("place_name") or "").strip()
    raw_lat = record.get("latitude")
    raw_lon = record.get("longitude")
    has_coords = False
    lat_f = 0.0
    lon_f = 0.0
    if raw_lat is not None and raw_lon is not None and str(raw_lat).strip() != "" and str(raw_lon).strip() != "":
        try:
            lat_f = float(raw_lat)
            lon_f = float(raw_lon)
            if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0:
                has_coords = True
        except (TypeError, ValueError):
            has_coords = False

    if has_coords and raw_place_name:
        best_candidate: dict[str, Any] | None = None
        best_score = -1.0
        best_dist = float("inf")
        best_sim = 0.0
        for p in pois:
            dist_m = compute_haversine_meters(
                lat_f, lon_f, float(p["latitude"]), float(p["longitude"])
            )
            if dist_m > GEO_HIGH_CONFIDENCE_MAX_DISTANCE_METERS:
                continue
            sim = compute_name_similarity(raw_place_name, p["name"])
            if sim < GEO_HIGH_CONFIDENCE_MIN_NAME_SIMILARITY:
                continue
            # Require city consistency if record provides city
            raw_city = str(record.get("city") or "").strip().lower()
            if raw_city:
                valid_aliases = w07_a2.CITY_VALID_ALIASES[p["city"]]
                if raw_city not in valid_aliases:
                    continue
            combined_conf = round(
                0.65 * sim
                + 0.35 * (1.0 - (dist_m / GEO_HIGH_CONFIDENCE_MAX_DISTANCE_METERS)),
                4,
            )
            if combined_conf > best_score:
                best_score = combined_conf
                best_candidate = p
                best_dist = round(dist_m, 2)
                best_sim = sim

        if best_candidate is not None and best_score >= 0.75:
            return {
                "accepted_mapping": True,
                "mapping_method": "GEO_NAME_HIGH_CONFIDENCE",
                "mapping_confidence": max(0.80, min(0.99, best_score)),
                "poi_id": best_candidate["poi_id"],
                "canonical_city": best_candidate["city"],
                "upstream_place_id": record.get("upstream_place_id"),
                "evidence": {
                    "distance_meters": best_dist,
                    "name_similarity": best_sim,
                    "input_place_name": raw_place_name,
                    "canonical_poi_name": best_candidate["name"],
                },
            }

    # 4. If no coordinates and no upstream ID, check if name-only match would have occurred -> reject as NAME_ONLY_AUTOMATIC!
    if not has_coords and raw_place_name:
        for p in pois:
            if compute_name_similarity(raw_place_name, p["name"]) >= 0.60:
                return {
                    "accepted_mapping": False,
                    "mapping_method": "NAME_ONLY_AUTOMATIC",
                    "mapping_confidence": 0.0,
                    "poi_id": None,
                    "canonical_city": None,
                    "upstream_place_id": record.get("upstream_place_id"),
                    "rejection_reason": "REJECT_NAME_ONLY_AUTOMATIC_MAPPING",
                    "evidence": {
                        "input_place_name": raw_place_name,
                        "candidate_poi_name_without_geo_or_id": p["name"],
                    },
                }

    # 5. Otherwise UNMAPPABLE
    return {
        "accepted_mapping": False,
        "mapping_method": "UNMAPPABLE",
        "mapping_confidence": 0.0,
        "poi_id": None,
        "canonical_city": None,
        "upstream_place_id": record.get("upstream_place_id"),
        "rejection_reason": "REJECT_UNMAPPABLE_PUBLIC_REVIEW",
        "evidence": {
            "input_place_name": raw_place_name or None,
            "has_coordinates": has_coords,
        },
    }


def deduplicate_public_raw_rows(
    raw_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate multi-image or repeated raw rows by `(source, source_review_id)` before counting unique reviews (Section 9)."""
    unique_rows: list[dict[str, Any]] = []
    seen_source_review_ids: set[tuple[str, str]] = set()
    collapsed_image_or_dup_rows = 0

    for row in raw_rows:
        src = str(row.get("source") or "").strip().lower()
        srid = str(row.get("source_review_id") or "").strip()
        if srid:
            key = (src, srid)
            if key in seen_source_review_ids:
                collapsed_image_or_dup_rows += 1
                continue
            seen_source_review_ids.add(key)
        unique_rows.append(row)

    return unique_rows, collapsed_image_or_dup_rows


def generate_public_review_id(
    *,
    source: str,
    source_review_id: str | None,
    poi_id: str,
    review_text: str,
) -> str:
    """Deterministic `review_id` for accepted public candidate reviews."""
    payload = {
        "poi_id": poi_id.strip().lower(),
        "review_text_sha256": hashlib.sha256(review_text.encode("utf-8")).hexdigest(),
        "source": source.strip().lower(),
        "source_review_id": (source_review_id or "").strip(),
        "version": PUBLIC_ACQUISITION_VERSION,
    }
    canon = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(canon).hexdigest()
    return f"w07_prev_{digest[:16]}"


def evaluate_and_filter_public_candidates(
    raw_rows: list[dict[str, Any]],
    *,
    manifest_payload: dict[str, Any],
    source_registry: dict[str, dict[str, Any]] | None = None,
    manual_verified_lookup: dict[tuple[str, str], str] | None = None,
    max_per_poi: int = MAX_PUBLIC_REVIEWS_PER_POI_CAP,
) -> dict[str, Any]:
    """Evaluate raw public rows through license/reuse quarantine, POI mapping, deduplication, and schema normalization.

    Enforces Sections 4, 5, 6, 7, 8, 9, 12, 13, 14:
    - Ambiguous license/reuse -> `QUARANTINE_REUSE_UNCLEAR` (never accepted).
    - Disallowed/rejected source -> `REJECTED_SOURCE` (never accepted).
    - Synthetic/LLM/rewritten/translated row -> `REJECT_SYNTHETIC_OR_AI_PUBLIC_REVIEW`.
    - `NAME_ONLY_AUTOMATIC` or `UNMAPPABLE` -> rejected.
    - Deduplicates by `source_review_id`, normalized `review_text`, and `(poi_id, normalized_review_text)`.
    - Never uses first-party provenance (`FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1` / `FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1`)
      and never sets `consent_record_id`.
    - Never fabricates missing upstream fields (`None` / `null` preserved).
    """
    unique_raw_rows, collapsed_multi_image_rows = deduplicate_public_raw_rows(raw_rows)

    accepted_candidates: list[dict[str, Any]] = []
    quarantined_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    seen_source_review_ids: set[str] = set()
    seen_norm_texts: set[str] = set()
    seen_poi_norm_texts: set[tuple[str, str]] = set()
    accepted_per_poi: Counter[str] = Counter()

    for idx, row in enumerate(unique_raw_rows):
        src_id = str(row.get("source") or "").strip()
        src_info = (source_registry or {}).get(src_id, {})
        src_class = str(
            row.get("source_classification")
            or src_info.get("classification")
            or ""
        ).strip()
        raw_license = str(
            row.get("license_or_usage_class")
            or src_info.get("license")
            or ""
        ).strip()
        reuse_ambiguous = bool(
            row.get("reuse_ambiguous")
            or src_info.get("quarantine_status") == "QUARANTINE_REUSE_UNCLEAR"
        )

        # 1. Check synthetic / LLM / rewritten / automatic translation flags (Section 14)
        if (
            bool(row.get("is_synthetic"))
            or bool(row.get("is_llm_rewritten"))
            or bool(row.get("is_auto_translated_duplicate"))
            or any(
                tok in src_id.lower()
                for tok in ("synthetic", "gpt", "gemini", "claude", "llm")
            )
        ):
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "reasons": ["REJECT_SYNTHETIC_OR_AI_PUBLIC_REVIEW"],
                }
            )
            continue

        # 2. Check rejected source or bulk-scraped commercial platform (Sections 5 & 8)
        if src_class == "REJECTED_SOURCE":
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "reasons": ["REJECT_DISALLOWED_PUBLIC_SOURCE"],
                }
            )
            continue

        # 3. Check ambiguous license / reuse rights -> QUARANTINE_REUSE_UNCLEAR (Section 8)
        if (
            reuse_ambiguous
            or not raw_license
            or raw_license.upper() in {"UNSPECIFIED", "UNKNOWN", "UNSPECIFIED_ON_HF_CARD", "UNSPECIFIED_NO_LICENSE_FILE"}
            or raw_license.upper().split()[0] not in APPROVED_OPEN_LICENSES
        ):
            quarantined_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "license": raw_license or "UNSPECIFIED",
                    "quarantine_reason": "QUARANTINE_REUSE_UNCLEAR",
                }
            )
            continue

        # 4. Check review_text presence and PII firewall
        raw_text = str(row.get("review_text") or "").strip()
        if len(raw_text) < MIN_PUBLIC_REVIEW_TEXT_CHARS:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "reasons": ["SHORT_OR_EMPTY_REVIEW_TEXT"],
                }
            )
            continue
        if w07_a2.EMAIL_RE.search(raw_text) or w07_a2.PHONE_RE.search(raw_text):
            quarantined_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "license": raw_license,
                    "quarantine_reason": "QUARANTINE_PII_REVIEW_TEXT",
                }
            )
            continue

        # 5. Map to frozen 60 POIs (Section 6)
        map_res = map_public_record_to_frozen_poi(
            row,
            manifest_payload=manifest_payload,
            manual_verified_lookup=manual_verified_lookup,
        )
        if not map_res["accepted_mapping"]:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "mapping_method": map_res["mapping_method"],
                    "reasons": [
                        map_res.get("rejection_reason")
                        or f"REJECT_MAPPING_{map_res['mapping_method']}"
                    ],
                }
            )
            continue

        poi_id = str(map_res["poi_id"])
        canonical_city = str(map_res["canonical_city"])

        # 6. Deduplication (Section 9): source_review_id, normalized text, poi_id + normalized text
        srid = (
            str(row["source_review_id"]).strip()
            if row.get("source_review_id") is not None
            and str(row.get("source_review_id")).strip() != ""
            else None
        )
        norm_text = _normalize_text_for_dedup(raw_text)
        dup_reasons: list[str] = []
        if srid and f"{src_id}:{srid}" in seen_source_review_ids:
            dup_reasons.append("DUPLICATE_SOURCE_REVIEW_ID")
        if norm_text in seen_norm_texts:
            dup_reasons.append("DUPLICATE_NORMALIZED_TEXT")
        if (poi_id, norm_text) in seen_poi_norm_texts:
            dup_reasons.append("DUPLICATE_POI_NORMALIZED_TEXT")
        if dup_reasons:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "poi_id": poi_id,
                    "reasons": dup_reasons,
                }
            )
            continue

        # 7. Coverage priority cap per POI (Section 12)
        if accepted_per_poi[poi_id] >= max_per_poi:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "source": src_id,
                    "poi_id": poi_id,
                    "reasons": ["REJECT_POI_COVERAGE_CAP_EXCEEDED"],
                }
            )
            continue

        # 8. Provenance separation (Section 13): never allow first-party provenance or consent_record_id
        requested_prov = str(
            row.get("provenance") or "PUBLIC_OPEN_LICENSED_DATASET_V1"
        ).strip()
        if requested_prov in FORBIDDEN_FIRST_PARTY_PROVENANCE_CLASSES:
            raise ValueError(
                f"FAIL CLOSED: Public review cannot use first-party provenance class: {requested_prov}"
            )
        if requested_prov not in PUBLIC_PROVENANCE_CLASSES:
            requested_prov = "PUBLIC_OPEN_LICENSED_DATASET_V1"

        # 9. Normalize schema without fabricating missing upstream values (Section 7)
        raw_rating = row.get("rating")
        parsed_rating: float | None = None
        if raw_rating is not None and str(raw_rating).strip() != "":
            try:
                parsed_rating = float(raw_rating)
            except (TypeError, ValueError):
                parsed_rating = None

        raw_scale = row.get("rating_scale_max")
        parsed_scale: int | None = None
        if raw_scale is not None and str(raw_scale).strip() != "":
            try:
                parsed_scale = int(raw_scale)
            except (TypeError, ValueError):
                parsed_scale = None
        elif parsed_rating is not None:
            parsed_scale = 5

        raw_lang = (
            str(row["language"]).strip().lower()
            if row.get("language") is not None and str(row.get("language")).strip() != ""
            else None
        )
        raw_created_at = (
            str(row["created_at"]).strip()
            if row.get("created_at") is not None and str(row.get("created_at")).strip() != ""
            else None
        )
        raw_collected_at = (
            str(row["collected_at"]).strip()
            if row.get("collected_at") is not None
            and str(row.get("collected_at")).strip() != ""
            else None
        )
        raw_source_ref = (
            str(row["source_ref"]).strip()
            if row.get("source_ref") is not None and str(row.get("source_ref")).strip() != ""
            else f"{src_id}#{srid or idx}"
        )

        rev_id = generate_public_review_id(
            source=src_id,
            source_review_id=srid,
            poi_id=poi_id,
            review_text=raw_text,
        )

        candidate_record: dict[str, Any] = {
            "review_id": rev_id,
            "poi_id": poi_id,
            "upstream_place_id": map_res["upstream_place_id"],
            "city": canonical_city,
            "source": src_id,
            "source_review_id": srid,
            "rating": parsed_rating,
            "rating_scale_max": parsed_scale,
            "review_text": raw_text,
            "language": raw_lang,
            "created_at": raw_created_at,
            "collected_at": raw_collected_at,
            "source_ref": raw_source_ref,
            "provenance": requested_prov,
            "license_or_usage_class": raw_license.upper().split()[0],
            "mapping_method": map_res["mapping_method"],
            "mapping_confidence": map_res["mapping_confidence"],
        }

        if srid:
            seen_source_review_ids.add(f"{src_id}:{srid}")
        seen_norm_texts.add(norm_text)
        seen_poi_norm_texts.add((poi_id, norm_text))
        accepted_per_poi[poi_id] += 1
        accepted_candidates.append(candidate_record)

    return {
        "raw_rows_input": len(raw_rows),
        "collapsed_multi_image_or_same_id_rows": collapsed_multi_image_rows,
        "unique_reviews_evaluated": len(unique_raw_rows),
        "accepted_candidates": accepted_candidates,
        "quarantined_rows": quarantined_rows,
        "rejected_rows": rejected_rows,
    }


def build_investigated_source_manifests() -> list[dict[str, Any]]:
    """Return the complete deterministic manifest of all 18 investigated public sources (Section 8)."""
    return [
        {
            "source_id": "zenodo:10.5281/zenodo.7967494",
            "source_name": "TripAdvisor Vietnam Hotel Reviews (An Dinh Van et al., Zenodo Record 7967494)",
            "source_url": "https://zenodo.org/records/7967494",
            "doi": "10.5281/zenodo.7967494",
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "CC-BY-4.0 (declared on Zenodo metadata; upstream origin TripAdvisor Vietnam)",
            "upstream_origin": "User-generated TripAdvisor hotel reviews across Vietnam (Reviews.csv + hotel_coordinate.csv)",
            "research_reuse_assessment": (
                "Published on Zenodo under CC-BY-4.0 with open file access; however, upstream content originates "
                "from TripAdvisor hotel pages and 0 of the 1,497 hotels in Reviews.csv match any of the 60 frozen "
                "canonical POIs in Hà Nội, Đà Nẵng, or Hạ Long."
            ),
            "download_or_crawl_mechanism": (
                "Direct HTTP download via Zenodo REST API of both published CSV files (`hotel_coordinate.csv`: "
                "263,557 bytes, MD5 50fa8970a26ae513b8295bbcdfacd0b0, 3,910 hotel rows; `Reviews.csv`: "
                "64,460,152 bytes, MD5 ebae7b018af787978b29cf15591b7e96, 62,887 review rows)."
            ),
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": None,
            "original_rows": 62887,
            "unique_reviews": 62887,
            "accepted": 0,
            "rejected": 62887,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 62887,
            },
            "audit_notes": (
                "Full parsing of all 62,887 rows in Reviews.csv joined with 3,910 hotels in hotel_coordinate.csv "
                "verified that Reviews.csv covers 1,497 hotels concentrated in Phú Quốc (17,781), Cù Dù/Lăng Cô (3,407), "
                "Phong Nha-Kẻ Bàng (3,354), Cam Hải Đông/Cam Ranh (4,450), Ninh Vân (2,788), Điện Bàn (2,340), etc. "
                "Exactly 0 hotels in Reviews.csv are within 500m of or match any of the 60 frozen canonical POIs "
                "(including 0 matches for Sheraton Hanoi, Somerset Grand Hanoi, InterContinental Danang Sun Peninsula "
                "Resort, Furama Resort, Vinpearl Ha Long resort, and Novotel Ha Long)."
            ),
        },
        {
            "source_id": "huggingface:trungtrandinh/hotel_danang_vietnam",
            "source_name": "trungtrandinh/hotel_danang_vietnam (hotel_dataset_7k.jsonl)",
            "source_url": "https://huggingface.co/datasets/trungtrandinh/hotel_danang_vietnam",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_ON_HF_CARD",
            "upstream_origin": "Templated instruction-output pairs generated from Đà Nẵng hotel listing attributes and prices",
            "research_reuse_assessment": "Disqualified: synthetic templated hotel descriptions ('Thông tin về Khách sạn ...'), zero first-hand user reviews, and unspecified license.",
            "download_or_crawl_mechanism": "Hugging Face Datasets Server API (`/first-rows` and `/api/datasets`) inspection.",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 7000,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Contains 7,000 instruction/output pairs describing star ratings, room prices, and amenities; 0 user review texts.",
        },
        {
            "source_id": "huggingface:AnnBae6969/vietnam-tourism-dataset",
            "source_name": "AnnBae6969/vietnam-tourism-dataset (vietnam_tourism_dataset.xlsx)",
            "source_url": "https://huggingface.co/datasets/AnnBae6969/vietnam-tourism-dataset",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_ON_HF_CARD",
            "upstream_origin": "Synthetic Vietnamese travel chatbot Q&A pairs (Train_80, Test_20, Full_100_Samples)",
            "research_reuse_assessment": "Disqualified: chatbot Q&A pairs (`input`, `output`, `instruction`), zero real visitor reviews, and unspecified license.",
            "download_or_crawl_mechanism": "Direct HTTP inspection of `vietnam_tourism_dataset.xlsx` (38,221 bytes).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 100,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "All 100 rows are general travel itinerary/weather Q&A prompts, not POI visitor reviews.",
        },
        {
            "source_id": "huggingface:Bach293/dulich_hanoi",
            "source_name": "Bach293/dulich_hanoi (train.csv)",
            "source_url": "https://huggingface.co/datasets/Bach293/dulich_hanoi",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_ON_HF_CARD",
            "upstream_origin": "Image captioning dataset for Hanoi landmarks (`image`, `text`, `text2`, `text3`, `text4`)",
            "research_reuse_assessment": "Disqualified: visual image captions ('a stone path through a park...'), zero visitor reviews, and unspecified license.",
            "download_or_crawl_mechanism": "Hugging Face Datasets Server API (`/first-rows`) inspection.",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 200,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Image-captioning pairs only; 0 user review texts.",
        },
        {
            "source_id": "huggingface:VLAI-AIVN/vietnamtourism-instruction-dataset",
            "source_name": "VLAI-AIVN/vietnamtourism-instruction-dataset (VietnamTourism LLaVA Instruction)",
            "source_url": "https://huggingface.co/datasets/VLAI-AIVN/vietnamtourism-instruction-dataset",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "license:other (gated access)",
            "upstream_origin": "Multimodal visual-question-answering (LLaVA) instruction-tuning dataset",
            "research_reuse_assessment": "Disqualified: gated VQA instruction dataset (`license:other`, HTTP 401), not POI visitor reviews.",
            "download_or_crawl_mechanism": "Hugging Face Hub API metadata inspection (gated dataset).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 0,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Gated multimodal VQA dataset; 0 accessible public visitor reviews.",
        },
        {
            "source_id": "github:HongTin2104/VietNam-Travel-Recommendation-System",
            "source_name": "HongTin2104/VietNam-Travel-Recommendation-System (data/processed/places.csv)",
            "source_url": "https://github.com/HongTin2104/VietNam-Travel-Recommendation-System",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "MIT",
            "upstream_origin": "Hand-compiled destination catalog (315 places: 5 per pre-2025 province)",
            "research_reuse_assessment": "MIT-licensed repository, but contains only 1-sentence author-written place descriptions and aggregate ratings (`0` user reviews).",
            "download_or_crawl_mechanism": "GitHub REST API + raw inspection of `data/DATASET.md` and `data/processed/places.csv`.",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": None,
            "original_rows": 315,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Destination catalog only (`id,name,province,old_province,description,rating,keywords,image_url`); 0 user reviews.",
        },
        {
            "source_id": "github:1109inc/vietnam-travel-dataset",
            "source_name": "1109inc/vietnam-travel-dataset (vietnam_travel_dataset.json)",
            "source_url": "https://github.com/1109inc/vietnam-travel-dataset",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_NO_LICENSE_FILE",
            "upstream_origin": "Synthetic knowledge-graph nodes for Vietnamese cities and travel themes",
            "research_reuse_assessment": "Disqualified: synthetic templated city descriptions, zero user reviews, and no repository license.",
            "download_or_crawl_mechanism": "GitHub REST API + raw JSON inspection (360 nodes, 193,000 bytes).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 360,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Contains 360 templated destination nodes (`semantic_text` / `connections`); 0 user reviews.",
        },
        {
            "source_id": "github:koshiroquoc/DaNangtourguide",
            "source_name": "koshiroquoc/DaNangtourguide (Data/data_danang_ok.csv & places_enriched_v2.jsonl)",
            "source_url": "https://github.com/koshiroquoc/DaNangtourguide",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_NO_LICENSE_FILE (Wikivoyage overlay CC-BY-SA-4.0)",
            "upstream_origin": "OSM + English Wikivoyage Đà Nẵng place listings (`eat`, `see`, `stay`)",
            "research_reuse_assessment": "Disqualified for review corpus: contains editorial Wikivoyage/guidebook blurbs, zero first-hand visitor reviews, and no repository license.",
            "download_or_crawl_mechanism": "GitHub REST API + raw inspection of `Data/data_danang_ok.csv` and `Data/processed/places_enriched_v2.meta.json`.",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 200,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Place guide listings (`type,name,description,time,price,location,area,note,id,full_text,vector_search`); 0 user reviews.",
        },
        {
            "source_id": "github:hanhlevna/Manhos",
            "source_name": "hanhlevna/Manhos (data_Booking.com.csv)",
            "source_url": "https://github.com/hanhlevna/Manhos",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_NO_LICENSE_FILE",
            "upstream_origin": "Booking.com numeric aspect count matrix across Vietnamese provinces",
            "research_reuse_assessment": "Disqualified: numeric aspect counts only (`ServicePositive`, `AmenityPositive`, etc.), zero review text, zero hotel names, and no license.",
            "download_or_crawl_mechanism": "GitHub REST API + HTTP Range header inspection of `data_Booking.com.csv` (620,499 bytes).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 8500,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "20 numeric columns with province-level `location` only; 0 review texts and 0 hotel identifiers.",
        },
        {
            "source_id": "github:NguyenDucHuy14287/Foody_review_nlp",
            "source_name": "NguyenDucHuy14287/Foody_review_nlp & anh147/Foody-Review-Sentiment-With-LSTM",
            "source_url": "https://github.com/NguyenDucHuy14287/Foody_review_nlp",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A4P",
            "license": "UNSPECIFIED_NO_LICENSE_FILE",
            "upstream_origin": "Scraped Foody.vn restaurant comments with aspect/sentiment labels (`id,comment,food,drink,price,staff,service,space,hygiene`)",
            "research_reuse_assessment": (
                "Quarantined & unmappable: unlicensed GitHub scrapes of Foody.vn (`QUARANTINE_REUSE_UNCLEAR`) "
                "and 100% missing restaurant name, address, city, and coordinates."
            ),
            "download_or_crawl_mechanism": "GitHub REST API + HTTP Range header inspection (`data/data.csv`, 649,222 bytes, 5,000 comments).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 5000,
            "unique_reviews": 5000,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 5000,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 5000,
            },
            "audit_notes": "Quarantined due to absent license/Foody ToS ambiguity and 100% unmappable (no restaurant name, city, or coordinates).",
        },
        {
            "source_id": "huggingface:phamluan/vn_msa_sar_v3",
            "source_name": "phamluan/vn_msa_sar_v3 (+ phamluan/vn_hotel_res_aspect_v3)",
            "source_url": "https://huggingface.co/datasets/phamluan/vn_msa_sar_v3",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "CC-BY-4.0 (declared on HF dataset card)",
            "upstream_origin": "Multi-source hotel & restaurant reviews (Google Maps, Booking.com, Foody) with anonymized `review_id` hashes",
            "research_reuse_assessment": "Approved for auxiliary ABSA benchmark only; unusable for primary POI corpus because all place names, addresses, coordinates, and cities were stripped.",
            "download_or_crawl_mechanism": "Hugging Face Hub Parquet / datasets-server inspection.",
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": None,
            "original_rows": 76785,
            "unique_reviews": 18609,
            "accepted": 0,
            "rejected": 18609,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 18609,
            },
            "audit_notes": "76,785 sentence-aspect rows collapse to 18,609 unique review_ids; 100% UNMAPPABLE to the 60 frozen POIs due to stripped place identity.",
        },
        {
            "source_id": "huggingface:visolex/VLSP2018-ABSA",
            "source_name": "VLSP2018-ABSA-Restaurant & VLSP2018-ABSA-Hotel (visolex HF mirrors)",
            "source_url": "https://huggingface.co/datasets/visolex/VLSP2018-ABSA-Restaurant",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "VLSP Academic Shared Task Terms (unspecified on HF mirrors)",
            "upstream_origin": "Vietnamese restaurant and hotel reviews annotated for VLSP 2018 ABSA shared task",
            "research_reuse_assessment": "Auxiliary ABSA reference only; zero place names, addresses, cities, or coordinates.",
            "download_or_crawl_mechanism": "Hugging Face Hub Parquet / datasets-server inspection.",
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": None,
            "original_rows": 10351,
            "unique_reviews": 10351,
            "accepted": 0,
            "rejected": 10351,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 10351,
            },
            "audit_notes": "4,751 restaurant + 5,600 hotel reviews; 100% UNMAPPABLE to the 60 frozen POIs.",
        },
        {
            "source_id": "huggingface:pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "source_name": "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "source_url": "https://huggingface.co/datasets/pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "UNSPECIFIED_ON_HF_CARD",
            "upstream_origin": "Scraped Vietnamese restaurant reviews with sentiment labels (`review_id, review, label`)",
            "research_reuse_assessment": "Quarantined for unspecified license (`QUARANTINE_REUSE_UNCLEAR`) and 100% unmappable (no restaurant name, city, or coordinates).",
            "download_or_crawl_mechanism": "Hugging Face Hub Parquet / datasets-server inspection.",
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 32713,
            "unique_reviews": 32713,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 32713,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 32713,
            },
            "audit_notes": "Quarantined due to unspecified license on HF card and complete absence of POI metadata.",
        },
        {
            "source_id": "mendeley:10.17632/dp8s59xnb7.1",
            "source_name": "CX Vietnamese hotel online reviews (Ha Nguyen, FPT University, Mendeley Data)",
            "source_url": "https://data.mendeley.com/datasets/dp8s59xnb7/1",
            "doi": "10.17632/dp8s59xnb7.1",
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "CC-BY-4.0",
            "upstream_origin": "TripAdvisor Vietnam hotel reviews (`Tripadvisor for VNhotel.csv`)",
            "research_reuse_assessment": "CC-BY-4.0 academic dataset, but CSV contains strictly two columns (`Review,Rating`) with all hotel names, cities, and coordinates removed.",
            "download_or_crawl_mechanism": "Mendeley Data REST API + HTTP Range header inspection.",
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": None,
            "original_rows": 20551,
            "unique_reviews": 20551,
            "accepted": 0,
            "rejected": 20551,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 20551,
            },
            "audit_notes": "100% UNMAPPABLE because hotel names, cities, addresses, and coordinates were stripped prior to publication.",
        },
        {
            "source_id": "huggingface:hienbm/tripadvisor_vietnam",
            "source_name": "hienbm/tripadvisor_vietnam",
            "source_url": "https://huggingface.co/datasets/hienbm/tripadvisor_vietnam",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "UNSPECIFIED_ON_HF_CARD",
            "upstream_origin": "TripAdvisor Vietnam hotel reviews with 6 aspect sub-ratings (`language, input, output`)",
            "research_reuse_assessment": "Quarantined due to unspecified license (`QUARANTINE_REUSE_UNCLEAR`) and 100% unmappable (no hotel name, city, or coordinates).",
            "download_or_crawl_mechanism": "Hugging Face Hub Parquet / datasets-server inspection.",
            "classification": "AUXILIARY_ONLY",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 23559,
            "unique_reviews": 23559,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 23559,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 23559,
            },
            "audit_notes": "Quarantined due to unspecified license and missing hotel identity/location fields.",
        },
        {
            "source_id": "huggingface:ThanThoai9x/vietnamese-food-images",
            "source_name": "ThanThoai9x/vietnamese-food-images",
            "source_url": "https://huggingface.co/datasets/ThanThoai9x/vietnamese-food-images",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "CC-BY-NC-4.0 (declared on HF card; upstream Google Maps ToS ambiguous)",
            "upstream_origin": "Google Maps restaurant review photos and text in 9 districts of Hồ Chí Minh City",
            "research_reuse_assessment": "Rejected: 100.0% Hồ Chí Minh City (34,104 / 34,104 image rows across 1,989 HCMC places; 0 in Hà Nội, Đà Nẵng, or Hạ Long), manual gated access (HTTP 401), and ambiguous upstream Google Maps ToS.",
            "download_or_crawl_mechanism": "Hugging Face dataset card & metadata inspection (manual gated parquet shards not bulk-downloaded).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": "QUARANTINE_REUSE_UNCLEAR",
            "original_rows": 34104,
            "unique_reviews": 12500,
            "accepted": 0,
            "rejected": 12500,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 12500,
            },
            "audit_notes": "One row per photo (`photo_id`); 100% Hồ Chí Minh City (0 rows in Hà Nội, Đà Nẵng, or Hạ Long).",
        },
        {
            "source_id": "huggingface:MinhDS/ViHoRec",
            "source_name": "MinhDS/ViHoRec (local restricted snapshot `data/restricted/vihorec/`)",
            "source_url": "https://huggingface.co/datasets/MinhDS/ViHoRec",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "CC-BY-NC-4.0",
            "upstream_origin": "Vietnamese hotel collaborative-filtering rating matrix and hotel metadata",
            "research_reuse_assessment": "Valid for REC-B collaborative filtering ratings, but contains 0 user review text.",
            "download_or_crawl_mechanism": "Local restricted snapshot inspection (`data/restricted/vihorec/`).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": None,
            "original_rows": 17911,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Numeric user-hotel ratings only (`0` review text rows).",
        },
        {
            "source_id": "commercial_platforms:google_maps_tripadvisor_booking_agoda_foody",
            "source_name": "Commercial Platforms & APIs (Google Maps/Places, TripAdvisor, Booking.com, Agoda, Foody)",
            "source_url": "https://developers.google.com/maps/documentation/places/web-service/policies",
            "doi": None,
            "access_date": ACCESS_DATE_UTC,
            "discovered_in_stage": "W07-A1_REVERIFIED_IN_A4P",
            "license": "Proprietary Commercial Platform Terms of Service (No Offline Corpus Caching / Bulk Scraping Forbidden)",
            "upstream_origin": "Commercial travel/hospitality platforms",
            "research_reuse_assessment": (
                "Forbidden by Section 5: bulk scraping of Google Maps, TripAdvisor, Booking.com, Agoda, and Foody "
                "is prohibited without explicit storage/academic-reuse permission, and Google Places API limits "
                "responses to at most 5 reviews per place without offline benchmark caching rights."
            ),
            "download_or_crawl_mechanism": "Policy & ToS audit only (`BULK_SCRAPING_EXECUTED = false`).",
            "classification": "REJECTED_SOURCE",
            "quarantine_status": None,
            "original_rows": 0,
            "unique_reviews": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "target_pois_covered": 0,
            "mapping_breakdown": {
                "EXACT_UPSTREAM_ID": 0,
                "GEO_NAME_HIGH_CONFIDENCE": 0,
                "MANUAL_VERIFIED": 0,
                "NAME_ONLY_AUTOMATIC": 0,
                "UNMAPPABLE": 0,
            },
            "audit_notes": "Zero scraping or API harvesting executed.",
        },
    ]


def build_public_acquisition_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build the deterministic W07-A4P aggregate report (`data/evaluation/w07/w07_public_review_acquisition_v1.json`)."""
    upstream_hashes = verify_upstream_immutability(repo_root)
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)
    pois = manifest["pois"]

    source_manifests = build_investigated_source_manifests()

    raw_discovered = sum(s["original_rows"] for s in source_manifests)
    unique_reviews = sum(s["unique_reviews"] for s in source_manifests)
    accepted_reviews = sum(s["accepted"] for s in source_manifests)
    rejected_reviews = sum(s["rejected"] for s in source_manifests)
    quarantined_reviews = sum(s["quarantined"] for s in source_manifests)

    reviews_by_city = {
        "Hà Nội": 0,
        "Đà Nẵng": 0,
        "Hạ Long": 0,
    }
    reviews_by_category_group = {
        "attractions_culture": 0,
        "restaurants_cafes_markets": 0,
        "hotels": 0,
        "nature_beach": 0,
        "other_tourism": 0,
    }
    reviews_per_poi = [
        {
            "selection_rank": p["selection_rank"],
            "poi_id": p["poi_id"],
            "name": p["name"],
            "city": p["city"],
            "category": p["category"],
            "category_group": p["category_group"],
            "accepted_public_review_count": 0,
            "target_review_count_min": p["target_review_count_min"],
            "remaining_reviews_to_min_5": p["target_review_count_min"],
        }
        for p in pois
    ]

    class_counts = Counter(s["classification"] for s in source_manifests)
    source_distribution = {
        "APPROVED_PUBLIC_SOURCE": class_counts.get("APPROVED_PUBLIC_SOURCE", 0),
        "CONDITIONAL_SOURCE": class_counts.get("CONDITIONAL_SOURCE", 0),
        "AUXILIARY_ONLY": class_counts.get("AUXILIARY_ONLY", 0),
        "REJECTED_SOURCE": class_counts.get("REJECTED_SOURCE", 0),
    }

    license_distribution = {
        "CC-BY-4.0": sum(
            1 for s in source_manifests if s["license"].startswith("CC-BY-4.0")
        ),
        "CC-BY-NC-4.0": sum(
            1 for s in source_manifests if s["license"].startswith("CC-BY-NC-4.0")
        ),
        "MIT": sum(1 for s in source_manifests if s["license"] == "MIT"),
        "VLSP_ACADEMIC_SHARED_TASK": sum(
            1 for s in source_manifests if s["license"].startswith("VLSP")
        ),
        "UNSPECIFIED_OR_GATED_OTHER": sum(
            1
            for s in source_manifests
            if "UNSPECIFIED" in s["license"] or "license:other" in s["license"]
        ),
        "PROPRIETARY_COMMERCIAL_TOS": sum(
            1 for s in source_manifests if s["license"].startswith("Proprietary")
        ),
    }

    mapping_method_distribution = {
        "EXACT_UPSTREAM_ID": sum(
            s["mapping_breakdown"]["EXACT_UPSTREAM_ID"] for s in source_manifests
        ),
        "GEO_NAME_HIGH_CONFIDENCE": sum(
            s["mapping_breakdown"]["GEO_NAME_HIGH_CONFIDENCE"] for s in source_manifests
        ),
        "MANUAL_VERIFIED": sum(
            s["mapping_breakdown"]["MANUAL_VERIFIED"] for s in source_manifests
        ),
        "NAME_ONLY_AUTOMATIC": sum(
            s["mapping_breakdown"]["NAME_ONLY_AUTOMATIC"] for s in source_manifests
        ),
        "UNMAPPABLE": sum(
            s["mapping_breakdown"]["UNMAPPABLE"] for s in source_manifests
        ),
    }

    payload: dict[str, Any] = {
        "artifact_id": "w07_public_review_acquisition_v1",
        "version": PUBLIC_ACQUISITION_VERSION,
        "task_id": TASK_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "next_gate": NEXT_GATE,
        "outcome_classification": "OUTCOME_C_ZERO_SUITABLE_PUBLIC_REVIEWS_FOUND",
        "outcome_rationale": (
            "Across 18 investigated public sources (10 newly discovered and audited in W07-A4P across Zenodo, "
            "Hugging Face, and GitHub plus 8 sources re-verified from W07-A1), 300,536 raw rows and 186,170 "
            "unique review texts were examined. Every source with real review text either: (a) stripped all "
            "place names, coordinates, and cities prior to publication (`phamluan/vn_msa_sar_v3`, `VLSP2018-ABSA`, "
            "`mendeley:10.17632/dp8s59xnb7.1`, `pqthinh232`, `hienbm`, `Foody_review_nlp`), (b) contained zero "
            "geographic overlap with the 60 frozen POIs in Hà Nội, Đà Nẵng, and Hạ Long (`zenodo:10.5281/zenodo.7967494` "
            "with 62,887 TripAdvisor hotel reviews across 1,497 hotels in Phú Quốc, Phong Nha, Cam Ranh, etc., "
            "and `ThanThoai9x/vietnamese-food-images` with 100% Hồ Chí Minh City rows), or (c) lacked a valid "
            "reuse license (`QUARANTINE_REUSE_UNCLEAR`). Scientific provenance and mapping standards were preserved "
            "without compromise, yielding `PUBLIC_REVIEWS_ACCEPTED = 0`. First-party collection via W07-A3 Google Forms "
            "and W07-A4H Assisted Collection remains the sole primary source for the 60-POI / 300-review corpus."
        ),
        "upstream_immutability": upstream_hashes,
        "restricted_storage_contract": {
            "public_sources_dir": RESTRICTED_PUBLIC_SOURCES_DIR_RELPATH,
            "public_candidate_jsonl": RESTRICTED_PUBLIC_CANDIDATES_JSONL_RELPATH,
            "separated_from_google_form_corpus": True,
            "separated_from_assisted_first_party_corpus": True,
            "raw_review_text_in_committed_repo": False,
        },
        "human_public_provenance_separation": {
            "forbidden_first_party_provenance_classes": sorted(
                FORBIDDEN_FIRST_PARTY_PROVENANCE_CLASSES
            ),
            "public_provenance_classes": PUBLIC_PROVENANCE_CLASSES,
            "public_rows_have_first_party_consent_record_id": False,
        },
        "PUBLIC_REVIEWS_DISCOVERED": raw_discovered,
        "PUBLIC_UNIQUE_REVIEWS": unique_reviews,
        "PUBLIC_REVIEWS_ACCEPTED": accepted_reviews,
        "PUBLIC_REVIEWS_REJECTED": rejected_reviews,
        "PUBLIC_REVIEWS_QUARANTINED": quarantined_reviews,
        "PUBLIC_POIS_COVERED": 0,
        "REVIEWS_BY_CITY": reviews_by_city,
        "REVIEWS_BY_CATEGORY_GROUP": reviews_by_category_group,
        "REVIEWS_PER_POI": reviews_per_poi,
        "SOURCE_DISTRIBUTION": source_distribution,
        "LICENSE_DISTRIBUTION": license_distribution,
        "MAPPING_METHOD_DISTRIBUTION": mapping_method_distribution,
        "remaining_coverage_gap": {
            "target_canonical_pois": 60,
            "public_pois_covered": 0,
            "remaining_pois_needing_first_party_reviews": 60,
            "scientific_minimum_total_reviews": 300,
            "accepted_public_reviews": 0,
            "remaining_reviews_to_300": 300,
            "remaining_reviews_by_city": {
                "Hà Nội": 100,
                "Đà Nẵng": 100,
                "Hạ Long": 100,
            },
        },
        "investigated_sources_count": len(source_manifests),
        "investigated_sources": source_manifests,
        "BULK_SCRAPING_EXECUTED": False,
        "LLM_GENERATED_PUBLIC_REVIEWS": 0,
        "NEW_LLM_PROVIDER_CALLS": 0,
        "CORPUS_SCIENTIFIC_MINIMUM_READY": False,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(payload)
    return payload


def render_public_acquisition_markdown(report: dict[str, Any]) -> str:
    """Render deterministic Markdown documentation for W07-A4P (`docs/research/w07_public_review_acquisition.md`)."""
    lines: list[str] = [
        "# W07-A4P — Permitted Public Review Acquisition Report",
        "",
        "## 1. Authority & Scope",
        "",
        f"- **Task ID:** `{report['task_id']}`",
        f"- **Authoritative Base:** `develop@{report['authoritative_base_develop_sha']}`",
        f"- **Previous Accepted Gate:** `{report['previous_accepted_gate']}`",
        f"- **Next Gate:** `{report['next_gate']}`",
        f"- **Frozen W07-A2 60-POI Manifest SHA256:** `{report['upstream_immutability']['w07_a2_manifest_internal_sha256']}`",
        f"- **Outcome Classification:** `{report['outcome_classification']}`",
        "",
        "## 2. Executive Summary (Outcome C)",
        "",
        report["outcome_rationale"],
        "",
        "- `PUBLIC_REVIEWS_DISCOVERED`: "
        f"`{report['PUBLIC_REVIEWS_DISCOVERED']}`",
        f"- `PUBLIC_UNIQUE_REVIEWS`: `{report['PUBLIC_UNIQUE_REVIEWS']}`",
        f"- `PUBLIC_REVIEWS_ACCEPTED`: `{report['PUBLIC_REVIEWS_ACCEPTED']}`",
        f"- `PUBLIC_REVIEWS_REJECTED`: `{report['PUBLIC_REVIEWS_REJECTED']}`",
        f"- `PUBLIC_REVIEWS_QUARANTINED`: `{report['PUBLIC_REVIEWS_QUARANTINED']}`",
        f"- `PUBLIC_POIS_COVERED`: `{report['PUBLIC_POIS_COVERED']} / 60`",
        f"- `BULK_SCRAPING_EXECUTED`: `{str(report['BULK_SCRAPING_EXECUTED']).lower()}`",
        f"- `LLM_GENERATED_PUBLIC_REVIEWS`: `{report['LLM_GENERATED_PUBLIC_REVIEWS']}`",
        f"- `NEW_LLM_PROVIDER_CALLS`: `{report['NEW_LLM_PROVIDER_CALLS']}`",
        f"- `CORPUS_SCIENTIFIC_MINIMUM_READY`: `{str(report['CORPUS_SCIENTIFIC_MINIMUM_READY']).lower()}`",
        "",
        "## 3. Investigated Public Sources (18 Total: 10 New in W07-A4P + 8 Re-Verified from W07-A1)",
        "",
        "| # | Source ID | Stage | License | Classification | Quarantine | Raw Rows | Unique Reviews | Accepted | Rejected | Quarantined | POIs Covered |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for idx, src in enumerate(report["investigated_sources"], start=1):
        q_status = src["quarantine_status"] or "NONE"
        lines.append(
            f"| {idx} | `{src['source_id']}` | `{src['discovered_in_stage']}` | "
            f"`{src['license']}` | `{src['classification']}` | `{q_status}` | "
            f"{src['original_rows']} | {src['unique_reviews']} | {src['accepted']} | "
            f"{src['rejected']} | {src['quarantined']} | {src['target_pois_covered']} |"
        )

    lines.extend(
        [
            "",
            "## 4. Key Empirical Findings from W07-A4P Broad Discovery",
            "",
            "1. **Zenodo Record `7967494` (`10.5281/zenodo.7967494` — *TripAdvisor Vietnam Hotel Reviews*, CC-BY-4.0):**",
            "   - Both published CSV files (`hotel_coordinate.csv`: `263,557` bytes, MD5 `50fa8970a26ae513b8295bbcdfacd0b0`, `3,910` hotels; `Reviews.csv`: `64,460,152` bytes, MD5 `ebae7b018af787978b29cf15591b7e96`, `62,887` rows / `62,887` unique review IDs across `1,497` hotels) were inspected in full.",
            "   - Despite the record abstract mentioning Hanoi and Da Nang, `Reviews.csv` contains `0` reviews for hotels in `Hà Nội`, `Đà Nẵng`, or `Hạ Long` (its `62,887` reviews are concentrated in Phú Quốc `17,781`, Cù Dù/Lăng Cô `3,407`, Phong Nha-Kẻ Bàng `3,354`, Cam Hải Đông/Cam Ranh `4,450`, Ninh Vân `2,788`, Điện Bàn `2,340`, etc.), and `0` hotels in `Reviews.csv` match any of the 60 frozen canonical POIs by ID, coordinate (`<=500m`), or name.",
            "2. **Newly Discovered Hugging Face Datasets (`trungtrandinh/hotel_danang_vietnam`, `AnnBae6969/vietnam-tourism-dataset`, `Bach293/dulich_hanoi`, `VLAI-AIVN/vietnamtourism-instruction-dataset`):**",
            "   - Consist of synthetic instruction-tuning hotel price/amenity templates (`7,000` rows), chatbot Q&A pairs (`100` rows), English image captions (`200` rows), or gated LLaVA VQA samples (`HTTP 401`), with `0` real first-hand visitor reviews and unspecified/restricted licenses.",
            "3. **Newly Discovered GitHub Repositories (`HongTin2104/VietNam-Travel-Recommendation-System`, `1109inc/vietnam-travel-dataset`, `koshiroquoc/DaNangtourguide`, `hanhlevna/Manhos`, `NguyenDucHuy14287/Foody_review_nlp`, `anh147/Foody-Review-Sentiment-With-LSTM`):**",
            "   - Either contain only editorial destination catalogs / numeric aspect counts (`0` review text) or unlicensed Foody.vn comment scrapes (`QUARANTINE_REUSE_UNCLEAR`) with `100%` missing restaurant names, addresses, cities, and coordinates.",
            "",
            "## 5. Mapping Hierarchy, Deduplication & Provenance Firewall",
            "",
            "- **Allowed Mapping Methods:** `EXACT_UPSTREAM_ID`, `GEO_NAME_HIGH_CONFIDENCE` (`<= 150m` Haversine distance + normalized name similarity `>= 0.60`), `MANUAL_VERIFIED`.",
            "- **Rejected Mapping Methods:** `NAME_ONLY_AUTOMATIC`, `UNMAPPABLE`.",
            "- **Deduplication:** Collapses multi-photo rows sharing `(source, source_review_id)` before counting unique reviews, then deduplicates on `source_review_id`, normalized `review_text`, and `(poi_id, normalized_review_text)`.",
            "- **Human/Public Provenance Firewall:** Public reviews never receive `FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1` or `FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1` and never carry a first-party `consent_record_id`.",
            "- **Restricted Storage Separation:** Public candidate output (`data/restricted/w07_reviews/w07_public_candidate_reviews_v1.jsonl`) is strictly isolated from Google Form (`w07_google_form_candidate_reviews_v1.jsonl`) and Assisted (`w07_assisted_candidate_reviews_v1.jsonl`) candidate corpora.",
            "",
        ]
    )
    return "\n".join(lines)


def write_public_acquisition_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write committed W07-A4P aggregate JSON and Markdown artifacts and initialize git-ignored restricted files."""
    report = build_public_acquisition_report(repo_root)
    json_path = repo_root / PUBLIC_ACQUISITION_JSON_RELPATH
    md_path = repo_root / PUBLIC_ACQUISITION_MD_RELPATH

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    json_path.write_text(json_text, encoding="utf-8", newline="\n")

    md_text = render_public_acquisition_markdown(report)
    md_path.write_text(md_text, encoding="utf-8", newline="\n")

    # Ensure git-ignored restricted directory and empty candidate JSONL exist without modifying first-party files
    restricted_sources_dir = repo_root / RESTRICTED_PUBLIC_SOURCES_DIR_RELPATH
    restricted_sources_dir.mkdir(parents=True, exist_ok=True)
    restricted_jsonl = repo_root / RESTRICTED_PUBLIC_CANDIDATES_JSONL_RELPATH
    restricted_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if not restricted_jsonl.exists():
        restricted_jsonl.write_text("", encoding="utf-8", newline="\n")

    return verify_public_acquisition_artifacts(repo_root)


def verify_public_acquisition_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify committed W07-A4P JSON and Markdown artifacts and upstream immutability."""
    upstream_hashes = verify_upstream_immutability(repo_root)
    expected_report = build_public_acquisition_report(repo_root)

    json_path = repo_root / PUBLIC_ACQUISITION_JSON_RELPATH
    md_path = repo_root / PUBLIC_ACQUISITION_MD_RELPATH

    if not json_path.exists():
        raise FileNotFoundError(f"Missing W07-A4P JSON artifact: {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing W07-A4P Markdown artifact: {md_path}")

    on_disk = json.loads(json_path.read_text(encoding="utf-8"))
    computed_internal = w07_a2.compute_internal_sha256(on_disk)
    if computed_internal != on_disk.get("artifact_sha256"):
        raise ValueError(
            f"W07-A4P JSON internal SHA mismatch: {computed_internal} != {on_disk.get('artifact_sha256')}"
        )
    if computed_internal != expected_report["artifact_sha256"]:
        raise ValueError(
            "W07-A4P JSON on-disk payload differs from deterministic builder output."
        )

    expected_md = render_public_acquisition_markdown(expected_report)
    actual_md = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual_md != expected_md:
        raise ValueError(
            "W07-A4P Markdown on-disk content differs from deterministic builder output."
        )

    if on_disk.get("CORPUS_SCIENTIFIC_MINIMUM_READY") is not False:
        raise ValueError("FAIL CLOSED: CORPUS_SCIENTIFIC_MINIMUM_READY must be false in W07-A4P.")
    if on_disk.get("NEW_LLM_PROVIDER_CALLS") != 0:
        raise ValueError("FAIL CLOSED: NEW_LLM_PROVIDER_CALLS must be 0.")
    if on_disk.get("LLM_GENERATED_PUBLIC_REVIEWS") != 0:
        raise ValueError("FAIL CLOSED: LLM_GENERATED_PUBLIC_REVIEWS must be 0.")
    if on_disk.get("BULK_SCRAPING_EXECUTED") is not False:
        raise ValueError("FAIL CLOSED: BULK_SCRAPING_EXECUTED must be false.")

    return {
        "status": "PASS",
        "public_acquisition_json_path": PUBLIC_ACQUISITION_JSON_RELPATH,
        "public_acquisition_internal_sha256": computed_internal,
        "public_acquisition_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(
            json_path
        ),
        "public_acquisition_md_path": PUBLIC_ACQUISITION_MD_RELPATH,
        "public_acquisition_md_lf_sha256": w07_a2.compute_lf_normalized_sha256(md_path),
        "outcome_classification": on_disk["outcome_classification"],
        "PUBLIC_REVIEWS_DISCOVERED": on_disk["PUBLIC_REVIEWS_DISCOVERED"],
        "PUBLIC_UNIQUE_REVIEWS": on_disk["PUBLIC_UNIQUE_REVIEWS"],
        "PUBLIC_REVIEWS_ACCEPTED": on_disk["PUBLIC_REVIEWS_ACCEPTED"],
        "PUBLIC_REVIEWS_REJECTED": on_disk["PUBLIC_REVIEWS_REJECTED"],
        "PUBLIC_REVIEWS_QUARANTINED": on_disk["PUBLIC_REVIEWS_QUARANTINED"],
        "PUBLIC_POIS_COVERED": on_disk["PUBLIC_POIS_COVERED"],
        "CORPUS_SCIENTIFIC_MINIMUM_READY": on_disk["CORPUS_SCIENTIFIC_MINIMUM_READY"],
        "upstream_immutability": upstream_hashes,
    }


def build_zenodo_7967494_frozen_evidence() -> dict[str, Any]:
    """Return frozen deterministic Zenodo 7967494 two-file evidence and derived statistics."""
    return {
        "source_id": "zenodo:10.5281/zenodo.7967494",
        "doi": "10.5281/zenodo.7967494",
        "source_url": "https://zenodo.org/records/7967494",
        "files": {
            "hotel_coordinate.csv": {
                "upstream_filename": "hotel_coordinate.csv",
                "local_restricted_filename": "data/restricted/w07_reviews/public_sources/zenodo_7967494/hotel_coordinate.csv",
                "byte_size": ZENODO_7967494_COORD_BYTES,
                "published_md5": ZENODO_7967494_COORD_PUBLISHED_MD5,
                "local_md5": ZENODO_7967494_COORD_PUBLISHED_MD5,
                "local_sha256": ZENODO_7967494_COORD_LOCAL_SHA256,
                "schema_columns": [
                    "locationId",
                    "name",
                    "latitude",
                    "longitude",
                    "parentGeo",
                    "parentGeoId",
                ],
                "parsed_row_count": 3910,
                "unique_location_ids": 3910,
                "target_city_coordinate_rows": {
                    "Hà Nội": 29,
                    "Đà Nẵng": 17,
                    "Hạ Long": 0,
                },
            },
            "Reviews.csv": {
                "upstream_filename": "Reviews.csv",
                "local_restricted_filename": "data/restricted/w07_reviews/public_sources/zenodo_7967494/Reviews.csv",
                "byte_size": ZENODO_7967494_REVIEWS_BYTES,
                "published_md5": ZENODO_7967494_REVIEWS_PUBLISHED_MD5,
                "local_md5": ZENODO_7967494_REVIEWS_PUBLISHED_MD5,
                "local_sha256": ZENODO_7967494_REVIEWS_LOCAL_SHA256,
                "schema_columns": [
                    "id",
                    "language",
                    "rating",
                    "additionalRatings",
                    "createdDate",
                    "helpfulVotes",
                    "username",
                    "userId",
                    "title",
                    "text",
                    "locationId",
                    "parentGeoId",
                    "hotelName",
                    "stayDate",
                    "tripType",
                ],
                "parsed_row_count": 62887,
                "unique_review_ids": 62887,
                "unique_hotel_location_ids": 1497,
                "unique_hotel_names": 1470,
            },
        },
        "derived_statistics": {
            "reviews_row_count": 62887,
            "unique_review_ids": 62887,
            "unique_hotel_location_ids_in_reviews": 1497,
            "unique_hotel_names_in_reviews": 1470,
            "hotel_coordinate_row_count": 3910,
            "hotel_coordinate_joined_review_rows": 60570,
            "hotel_coordinate_joined_unique_hotels": 1475,
            "unjoined_review_rows": 2317,
            "unjoined_unique_hotels": 22,
            "distinct_locales_in_reviews": 183,
            "top_15_locales_in_reviews": {
                "Đảo Phú Quốc": 17781,
                "Cu Du": 3407,
                "Vườn quốc gia Phong Nha-Kẻ Bàng": 3354,
                "Cam Hải Đông": 3345,
                "Ninh Vân": 2788,
                "Điện Bàn": 2340,
                "UNJOINED": 2317,
                "Thuan An": 1548,
                "Bến Tre": 1466,
                "Cái Bè": 1281,
                "Hồ Tràm": 1218,
                "Cam Ranh": 1105,
                "Nam Cát Tiên": 1064,
                "Phú Lộc": 905,
                "Mỹ Tho": 867,
            },
            "unjoined_2317_rows_resolved_by_parent_geo_id": {
                "Vườn quốc gia Phong Nha-Kẻ Bàng": 1030,
                "Lâm Đồng": 804,
                "Bến Tre": 375,
                "Phong Nha": 59,
                "Đồng Văn": 26,
                "Bắc Hà": 15,
                "Dao Co To": 3,
                "Phúc Yên": 3,
                "Pho Chau": 1,
                "Binh Dong": 1,
            },
            "normalized_review_counts_target_cities": {
                "Hà Nội": 0,
                "Đà Nẵng": 0,
                "Hạ Long": 0,
            },
            "frozen_6_hotel_poi_matches": 0,
            "frozen_60_poi_matches": 0,
            "closest_hotel_in_reviews_to_any_frozen_poi": {
                "zenodo_location_id": "19378023",
                "zenodo_hotel_name": "Nhà Nghỉ Yến Nhi",
                "zenodo_parent_geo": "Quan Lạn",
                "canonical_poi_id": "b37d68ee-0cb3-49f0-a399-cac4c8e2732c",
                "canonical_poi_name": "Nhà hàng Hồng Hạnh 3",
                "canonical_city": "Hạ Long",
                "distance_meters": 528.44,
            },
        },
    }


def build_public_source_evidence_receipts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build deterministic source evidence receipts for all 18 investigated sources (Corrective 01A)."""
    zenodo_ev = build_zenodo_7967494_frozen_evidence()
    receipts: list[dict[str, Any]] = [
        {
            "source_id": "zenodo:10.5281/zenodo.7967494",
            "source_name": "TripAdvisor Vietnam Hotel Reviews (An Dinh Van et al., Zenodo Record 7967494)",
            "source_url": "https://zenodo.org/records/7967494",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "hotel_coordinate.csv + Reviews.csv",
            "local_restricted_filename": (
                "data/restricted/w07_reviews/public_sources/zenodo_7967494/hotel_coordinate.csv;"
                "data/restricted/w07_reviews/public_sources/zenodo_7967494/Reviews.csv"
            ),
            "file_size": ZENODO_7967494_COORD_BYTES + ZENODO_7967494_REVIEWS_BYTES,
            "published_md5_or_sha": {
                "hotel_coordinate.csv": f"md5:{ZENODO_7967494_COORD_PUBLISHED_MD5}",
                "Reviews.csv": f"md5:{ZENODO_7967494_REVIEWS_PUBLISHED_MD5}",
            },
            "local_sha256": {
                "hotel_coordinate.csv": ZENODO_7967494_COORD_LOCAL_SHA256,
                "Reviews.csv": ZENODO_7967494_REVIEWS_LOCAL_SHA256,
            },
            "schema_columns": {
                "hotel_coordinate.csv": zenodo_ev["files"]["hotel_coordinate.csv"]["schema_columns"],
                "Reviews.csv": zenodo_ev["files"]["Reviews.csv"]["schema_columns"],
            },
            "parsed_row_count": 62887,
            "unique_review_count": 62887,
            "unique_location_or_place_count": 1497,
            "target_city_statistics": {
                "Hà Nội": 0,
                "Đà Nẵng": 0,
                "Hạ Long": 0,
                "hotel_coordinate_only_without_reviews": {
                    "Hà Nội": 29,
                    "Đà Nẵng": 17,
                    "Hạ Long": 0,
                },
            },
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILES_DOWNLOADED_AND_PARSED",
            "zenodo_7967494_detail": zenodo_ev,
        },
        {
            "source_id": "huggingface:trungtrandinh/hotel_danang_vietnam",
            "source_name": "trungtrandinh/hotel_danang_vietnam (hotel_dataset_7k.jsonl)",
            "source_url": "https://huggingface.co/datasets/trungtrandinh/hotel_danang_vietnam",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "hotel_dataset_7k.jsonl",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/hf_trungtrandinh/hotel_dataset_7k.jsonl",
            "file_size": 2167241,
            "published_md5_or_sha": None,
            "local_sha256": "60e1216d186042f2a1bd3bc8ebb187531bb9686d757f8b6a8e98516b8c1afce0",
            "schema_columns": ["instruction", "output"],
            "parsed_row_count": 7372,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "huggingface:AnnBae6969/vietnam-tourism-dataset",
            "source_name": "AnnBae6969/vietnam-tourism-dataset (vietnam_tourism_dataset.xlsx)",
            "source_url": "https://huggingface.co/datasets/AnnBae6969/vietnam-tourism-dataset",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "vietnam_tourism_dataset.xlsx",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/hf_annbae6969/vietnam_tourism_dataset.xlsx",
            "file_size": 38221,
            "published_md5_or_sha": None,
            "local_sha256": "25bce9b5ae37ad2b375418958c21a07cf5ed6b43b3900c800d98d1e570581fd3",
            "schema_columns": ["input", "output", "instruction"],
            "parsed_row_count": 100,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "huggingface:Bach293/dulich_hanoi",
            "source_name": "Bach293/dulich_hanoi",
            "source_url": "https://huggingface.co/datasets/Bach293/dulich_hanoi",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data/train-00000-of-00001.parquet",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["image", "text"],
            "parsed_row_count": 200,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "HF_DATASETS_SERVER_API_INSPECTED",
        },
        {
            "source_id": "huggingface:VLAI-AIVN/vietnamtourism-instruction-dataset",
            "source_name": "VLAI-AIVN/vietnamtourism-instruction-dataset",
            "source_url": "https://huggingface.co/datasets/VLAI-AIVN/vietnamtourism-instruction-dataset",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": None,
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["id", "image", "conversations"],
            "parsed_row_count": 0,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "HF_API_METADATA_AUDITED_GATED_HTTP_401",
        },
        {
            "source_id": "github:HongTin2104/VietNam-Travel-Recommendation-System",
            "source_name": "HongTin2104/VietNam-Travel-Recommendation-System (data/processed/places.csv)",
            "source_url": "https://github.com/HongTin2104/VietNam-Travel-Recommendation-System",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data/processed/places.csv",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/github_hongtin2104/data__processed__places.csv",
            "file_size": 125367,
            "published_md5_or_sha": None,
            "local_sha256": "95a10d615a2c76156f7931332853a8c9f82a95a5a1cf4e8165e2247c41fc6474",
            "schema_columns": [
                "id",
                "name",
                "province",
                "old_province",
                "description",
                "rating",
                "keywords",
                "image_url",
            ],
            "parsed_row_count": 315,
            "unique_review_count": 0,
            "unique_location_or_place_count": 315,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "github:1109inc/vietnam-travel-dataset",
            "source_name": "1109inc/vietnam-travel-dataset (vietnam_travel_dataset.json)",
            "source_url": "https://github.com/1109inc/vietnam-travel-dataset",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "vietnam_travel_dataset.json",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/github_1109inc/vietnam_travel_dataset.json",
            "file_size": 193000,
            "published_md5_or_sha": None,
            "local_sha256": "cf966810481b42d2f27b29aafff41df5f3829999db4c7af339bf98048f9a94f1",
            "schema_columns": [
                "best_time_to_visit",
                "connections",
                "description",
                "id",
                "name",
                "region",
                "semantic_text",
                "tags",
                "type",
            ],
            "parsed_row_count": 360,
            "unique_review_count": 0,
            "unique_location_or_place_count": 360,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "github:koshiroquoc/DaNangtourguide",
            "source_name": "koshiroquoc/DaNangtourguide (Đà Nẵng place listings)",
            "source_url": "https://github.com/koshiroquoc/DaNangtourguide",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "Data/data_danang_ok.csv + Data/processed/places_enriched_v2.jsonl",
            "local_restricted_filename": (
                "data/restricted/w07_reviews/public_sources/github_koshiroquoc_danangtourguide/Data__data_danang_ok.csv;"
                "data/restricted/w07_reviews/public_sources/github_koshiroquoc_danangtourguide/Data__processed__places_enriched_v2.jsonl"
            ),
            "file_size": 2503435,
            "published_md5_or_sha": None,
            "local_sha256": {
                "Data/data_danang_ok.csv": "89d42fb7e2337480ecb8d26035cf83741ddbca42b30508a5454c1b4299d4a811",
                "Data/processed/places_enriched_v2.jsonl": "3a0b2feaaac5fc426e41969ca1c8f997717287f929c9a33d09400722fe582518",
            },
            "schema_columns": {
                "Data/data_danang_ok.csv": [
                    "type",
                    "name",
                    "description",
                    "time",
                    "price",
                    "location",
                    "area",
                    "note",
                    "id",
                    "full_text",
                    "vector_search",
                ],
                "Data/processed/places_enriched_v2.jsonl": [
                    "address",
                    "area",
                    "categories",
                    "cuisine",
                    "description",
                    "description_origin",
                    "enrichment_sources",
                    "field_provenance",
                    "full_text",
                    "id",
                    "is_synthetic",
                    "last_verified_at",
                    "latitude",
                    "longitude",
                    "name",
                    "name_en",
                    "name_vi",
                    "opening_hours",
                    "phone",
                    "price_currency",
                    "price_max_vnd",
                    "price_min_vnd",
                    "price_text",
                    "retrieved_at",
                    "schema_version",
                    "source",
                    "source_id",
                    "source_license",
                    "source_updated_at",
                    "source_url",
                    "type",
                    "website",
                ],
            },
            "parsed_row_count": 2557,
            "unique_review_count": 0,
            "unique_location_or_place_count": 2557,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILES_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "github:hanhlevna/Manhos",
            "source_name": "hanhlevna/Manhos (data_Booking.com.csv)",
            "source_url": "https://github.com/hanhlevna/Manhos",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data_Booking.com.csv",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/github_hanhlevna_manhos/data_Booking.com.csv",
            "file_size": 620499,
            "published_md5_or_sha": None,
            "local_sha256": "b77179746dd9b34df4f71d42b1e215fcc11283f01f039859a9656c3784caf6df",
            "schema_columns": [
                "",
                "ServicePositive",
                "AmenityPositive",
                "FacilityPositive",
                "FacilityNegative",
                "LoyaltyPositive",
                "ServiceNegative",
                "AmenityNegative",
                "LoyaltyNegative",
                "ServiceNeutral",
                "AmenityNeutral",
                "FacilityNeutral",
                "LoyaltyNeutral",
                "fill_star",
                "old_score",
                "location",
                "star",
                "Experience_BrandingPositive",
                "Experience_BrandingNeutral",
                "Experience_BrandingNegative",
            ],
            "parsed_row_count": 6955,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "github:NguyenDucHuy14287/Foody_review_nlp",
            "source_name": "NguyenDucHuy14287/Foody_review_nlp & anh147/Foody-Review-Sentiment-With-LSTM",
            "source_url": "https://github.com/NguyenDucHuy14287/Foody_review_nlp",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data/data.csv",
            "local_restricted_filename": "data/restricted/w07_reviews/public_sources/github_foody_review_nlp/data__data.csv",
            "file_size": 649222,
            "published_md5_or_sha": None,
            "local_sha256": "25fb6580e523b0ead23dfaa38966d605d06c0033054bd4b8f914bc5e3e69ee09",
            "schema_columns": [
                "id",
                "comment",
                "food",
                "drink",
                "price",
                "staff",
                "service",
                "space",
                "hygiene",
            ],
            "parsed_row_count": 5000,
            "unique_review_count": 5000,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "FULL_LOCAL_RAW_FILE_DOWNLOADED_AND_PARSED",
        },
        {
            "source_id": "huggingface:phamluan/vn_msa_sar_v3",
            "source_name": "phamluan/vn_msa_sar_v3 (Vietnamese Restaurant ABSA)",
            "source_url": "https://huggingface.co/datasets/phamluan/vn_msa_sar_v3",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "train/validation/test parquet splits",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["text", "aspect", "sentiment"],
            "parsed_row_count": 76785,
            "unique_review_count": 18609,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "W07_A1_PARQUET_AUDITED_AND_REVERIFIED",
        },
        {
            "source_id": "huggingface:visolex/VLSP2018-ABSA",
            "source_name": "visolex/VLSP2018-ABSA (Hotel + Restaurant splits)",
            "source_url": "https://huggingface.co/datasets/visolex/VLSP2018-ABSA",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "hotel + restaurant splits",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["Review", "aspect_polarities"],
            "parsed_row_count": 10351,
            "unique_review_count": 10351,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "W07_A1_PARQUET_AUDITED_AND_REVERIFIED",
        },
        {
            "source_id": "huggingface:pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "source_name": "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "source_url": "https://huggingface.co/datasets/pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data/train-00000-of-00001.parquet",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["user", "text", "rating"],
            "parsed_row_count": 32713,
            "unique_review_count": 32713,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "W07_A1_PARQUET_AUDITED_AND_REVERIFIED",
        },
        {
            "source_id": "mendeley:10.17632/dp8s59xnb7.1",
            "source_name": "CX Vietnamese hotel online reviews (Ha Nguyen, FPT University, Mendeley Data)",
            "source_url": "https://data.mendeley.com/datasets/dp8s59xnb7/1",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "Tripadvisor for VNhotel.csv",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": "sha256:9f2c8d1a (Mendeley Data v1)",
            "local_sha256": None,
            "schema_columns": ["Review", "Rating"],
            "parsed_row_count": 20551,
            "unique_review_count": 20551,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "MENDELEY_REST_API_AND_HTTP_RANGE_AUDITED",
        },
        {
            "source_id": "huggingface:hienbm/tripadvisor_vietnam",
            "source_name": "hienbm/tripadvisor_vietnam",
            "source_url": "https://huggingface.co/datasets/hienbm/tripadvisor_vietnam",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "train parquet",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": ["language", "input", "output"],
            "parsed_row_count": 23559,
            "unique_review_count": 23559,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "W07_A1_PARQUET_AUDITED_AND_REVERIFIED",
        },
        {
            "source_id": "huggingface:ThanThoai9x/vietnamese-food-images",
            "source_name": "ThanThoai9x/vietnamese-food-images",
            "source_url": "https://huggingface.co/datasets/ThanThoai9x/vietnamese-food-images",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "data/train-*.parquet (gated)",
            "local_restricted_filename": None,
            "file_size": None,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": [
                "photo_id",
                "review_id",
                "place_name",
                "district",
                "city",
                "review_text",
                "rating",
            ],
            "parsed_row_count": 34104,
            "unique_review_count": 12500,
            "unique_location_or_place_count": 1989,
            "target_city_statistics": {
                "Hà Nội": 0,
                "Đà Nẵng": 0,
                "Hạ Long": 0,
                "Hồ Chí Minh City": 34104,
            },
            "target_poi_mapping_count": 0,
            "evidence_status": "HF_DATASET_CARD_AND_CITY_DISTRIBUTION_AUDITED_GATED_401",
        },
        {
            "source_id": "huggingface:MinhDS/ViHoRec",
            "source_name": "MinhDS/ViHoRec (local restricted snapshot `data/restricted/vihorec/`)",
            "source_url": "https://huggingface.co/datasets/MinhDS/ViHoRec",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": "interactions.csv + hotels.csv",
            "local_restricted_filename": "data/restricted/vihorec/interactions.csv",
            "file_size": 776686,
            "published_md5_or_sha": None,
            "local_sha256": "6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb",
            "schema_columns": ["user_id", "hotel_id", "rating"],
            "parsed_row_count": 17911,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "LOCAL_RESTRICTED_SNAPSHOT_AUDITED",
        },
        {
            "source_id": "commercial_platforms:google_maps_tripadvisor_booking_agoda_foody",
            "source_name": "Commercial Platforms & APIs (Google Maps/Places, TripAdvisor, Booking.com, Agoda, Foody)",
            "source_url": "https://developers.google.com/maps/documentation/places/web-service/policies",
            "access_date": ACCESS_DATE_UTC,
            "upstream_filename": None,
            "local_restricted_filename": None,
            "file_size": 0,
            "published_md5_or_sha": None,
            "local_sha256": None,
            "schema_columns": [],
            "parsed_row_count": 0,
            "unique_review_count": 0,
            "unique_location_or_place_count": 0,
            "target_city_statistics": {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0},
            "target_poi_mapping_count": 0,
            "evidence_status": "POLICY_AND_TOS_AUDITED_NO_SCRAPING",
        },
    ]

    payload: dict[str, Any] = {
        "artifact_id": "w07_public_source_evidence_receipts_v1",
        "version": "1.0.0-corrective-01a",
        "task_id": "W07-A4P-CORRECTIVE-01A",
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "receipts_count": len(receipts),
        "raw_review_text_included": False,
        "zenodo_7967494_reproducibility": zenodo_ev,
        "source_receipts": receipts,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(payload)
    return payload


def write_public_source_evidence_receipts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write committed W07-A4P Corrective 01A source evidence receipts JSON artifact."""
    receipt_payload = build_public_source_evidence_receipts(repo_root)
    receipt_path = repo_root / PUBLIC_SOURCE_RECEIPTS_JSON_RELPATH
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_text = json.dumps(receipt_payload, indent=2, ensure_ascii=False) + "\n"
    receipt_path.write_text(receipt_text, encoding="utf-8", newline="\n")
    return verify_public_source_evidence_receipts(repo_root)


def verify_public_source_evidence_receipts(
    repo_root: Path = REPO_ROOT,
    *,
    restricted_sources_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify committed W07-A4P source evidence receipts and distinguish receipt verification from raw-file replay."""
    receipt_path = repo_root / PUBLIC_SOURCE_RECEIPTS_JSON_RELPATH
    if not receipt_path.exists():
        raise FileNotFoundError(
            f"Missing W07-A4P source evidence receipt artifact: {receipt_path}"
        )

    expected_payload = build_public_source_evidence_receipts(repo_root)
    on_disk = json.loads(receipt_path.read_text(encoding="utf-8"))
    computed_internal = w07_a2.compute_internal_sha256(on_disk)

    if computed_internal != on_disk.get("artifact_sha256"):
        raise ValueError(
            f"W07-A4P source evidence receipt internal SHA mismatch: {computed_internal} != {on_disk.get('artifact_sha256')}"
        )
    if computed_internal != expected_payload["artifact_sha256"]:
        raise ValueError(
            "W07-A4P source evidence receipt on-disk payload differs from deterministic builder output."
        )
    if on_disk.get("receipts_count") != 18 or len(on_disk.get("source_receipts", [])) != 18:
        raise ValueError("FAIL CLOSED: W07-A4P source evidence receipts must cover all 18 sources.")

    zenodo_files = on_disk["zenodo_7967494_reproducibility"]["files"]
    if (
        zenodo_files["hotel_coordinate.csv"]["published_md5"]
        != ZENODO_7967494_COORD_PUBLISHED_MD5
        or zenodo_files["Reviews.csv"]["published_md5"]
        != ZENODO_7967494_REVIEWS_PUBLISHED_MD5
    ):
        raise ValueError("FAIL CLOSED: Zenodo 7967494 published MD5 binding mismatch.")

    eff_restricted_dir = (
        restricted_sources_dir
        if restricted_sources_dir is not None
        else (repo_root / RESTRICTED_PUBLIC_SOURCES_DIR_RELPATH)
    )
    coord_path = eff_restricted_dir / "zenodo_7967494" / "hotel_coordinate.csv"
    reviews_path = eff_restricted_dir / "zenodo_7967494" / "Reviews.csv"

    raw_replay_verified = False
    raw_replay_status = (
        "RAW_SOURCE_FILES_ABSENT_IN_CLEAN_CHECKOUT_FROZEN_RECEIPT_VERIFIED_ONLY"
    )

    if coord_path.exists() and reviews_path.exists():
        coord_bytes = coord_path.read_bytes()
        rev_bytes = reviews_path.read_bytes()
        if len(coord_bytes) != ZENODO_7967494_COORD_BYTES:
            raise ValueError("FAIL CLOSED: Local hotel_coordinate.csv byte size mismatch.")
        if hashlib.md5(coord_bytes).hexdigest() != ZENODO_7967494_COORD_PUBLISHED_MD5:
            raise ValueError("FAIL CLOSED: Local hotel_coordinate.csv MD5 mismatch.")
        if hashlib.sha256(coord_bytes).hexdigest() != ZENODO_7967494_COORD_LOCAL_SHA256:
            raise ValueError("FAIL CLOSED: Local hotel_coordinate.csv SHA256 mismatch.")

        if len(rev_bytes) != ZENODO_7967494_REVIEWS_BYTES:
            raise ValueError("FAIL CLOSED: Local Reviews.csv byte size mismatch.")
        if hashlib.md5(rev_bytes).hexdigest() != ZENODO_7967494_REVIEWS_PUBLISHED_MD5:
            raise ValueError("FAIL CLOSED: Local Reviews.csv MD5 mismatch.")
        if hashlib.sha256(rev_bytes).hexdigest() != ZENODO_7967494_REVIEWS_LOCAL_SHA256:
            raise ValueError("FAIL CLOSED: Local Reviews.csv SHA256 mismatch.")

        coord_rows = list(
            csv.DictReader(coord_bytes.decode("utf-8-sig").splitlines())
        )
        rev_rows = list(csv.DictReader(rev_bytes.decode("utf-8-sig").splitlines()))
        if len(coord_rows) != 3910 or len(rev_rows) != 62887:
            raise ValueError("FAIL CLOSED: Local Zenodo 7967494 parsed row count mismatch.")

        raw_replay_verified = True
        raw_replay_status = "RAW_SOURCE_REPLAY_VERIFIED_FROM_LOCAL_RESTRICTED_FILES"

    return {
        "status": "PASS",
        "receipt_json_path": PUBLIC_SOURCE_RECEIPTS_JSON_RELPATH,
        "receipt_internal_sha256": computed_internal,
        "receipt_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(receipt_path),
        "receipts_count": on_disk["receipts_count"],
        "SOURCE_EVIDENCE_RECEIPT_VERIFIED": True,
        "RAW_SOURCE_REPLAY_VERIFIED": raw_replay_verified,
        "raw_source_replay_status": raw_replay_status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W07-A4P Permitted Public Review Acquisition & Verifier (v1)."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write committed W07-A4P aggregate JSON and Markdown artifacts.",
    )
    parser.add_argument(
        "--write-receipts",
        action="store_true",
        help="Write committed W07-A4P source evidence receipts artifact.",
    )
    parser.add_argument(
        "--verify-receipts",
        action="store_true",
        help="Verify committed W07-A4P source evidence receipts artifact.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed W07-A4P artifacts and upstream immutability without writing.",
    )
    args = parser.parse_args(argv)

    if args.write_receipts:
        res = write_public_source_evidence_receipts(REPO_ROOT)
    elif args.verify_receipts:
        res = verify_public_source_evidence_receipts(REPO_ROOT)
    elif args.write:
        res = write_public_acquisition_artifacts(REPO_ROOT)
    else:
        res = verify_public_acquisition_artifacts(REPO_ROOT)

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
