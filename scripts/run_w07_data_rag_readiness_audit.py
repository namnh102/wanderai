#!/usr/bin/env python3
"""W07-0 Data + RAG Readiness Audit & Deterministic Offline Verifier.

Read-only evidence-based audit of all repository data sources relevant to W07
Review Intelligence / RAG prior to corpus, retrieval, embedding, index,
reranker, summarizer, or infrastructure selection.

Includes Corrective 01 (Acquisition Plan Feasibility Corrective 01):
- Google Places max-review constraint (GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5)
  and offline storage restriction (GOOGLE_PLACES_OFFLINE_CORPUS_ROLE =
  NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW).
- Tripadvisor Content API academic exclusion (TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE =
  NOT_RECOMMENDED).
- Three-tier corpus acquisition target (Scientific Minimum >= 60 POIs / >= 300 reviews,
  Preferred 75-100 POIs / 600-1,200 reviews, Stretch ~110 POIs / 1,100-1,650 reviews).
- Ranked candidate source classes (Tier A, Tier B, Tier C, Excluded) and Candidate
  Dataset Feasibility Queue (Candidate A/B/C).
- Canonical POI mapping rules (name-only automatic linking forbidden) and 17-field schema.
- Explicit PLANNING_ESTIMATE_NOT_MEASURED hygiene on all unmeasured latency/RAM estimates.
- W06 remains CLOSED and unmodified; NEW_LLM_PROVIDER_CALLS = 0; NEW_REVIEW_DATA_ACQUIRED = 0.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

AUDIT_JSON_RELPATH = "data/evaluation/w07/w07_data_rag_readiness_audit_v1.json"
AUDIT_MD_RELPATH = "docs/research/w07_data_rag_readiness_audit.md"

AUTHORITATIVE_DEVELOP_BASE_SHA = "bdd4810de0bc03ef52c67cc112e09d5787a7ffad"
PREVIOUS_GATE = (
    "W07-DATA-RAG-READINESS-AUDIT-CHATGPT-AUDIT = "
    "SCIENTIFIC_AUDIT_ACCEPTED / ACQUISITION_PLAN_HOLD_CORRECTIVE"
)
PREVIOUS_GATE_DECISION = "SCIENTIFIC_AUDIT_ACCEPTED / ACQUISITION_PLAN_HOLD_CORRECTIVE"
NEXT_GATE = "W07-DATA-RAG-READINESS-AUDIT-CORRECTIVE-01-CHATGPT-AUDIT"

GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5
GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = "NOT_RECOMMENDED"
PLANNING_ESTIMATE_LABEL = "PLANNING_ESTIMATE_NOT_MEASURED"

SECTION_6_REQUIRED_FIELDS = [
    "review_id",
    "poi_id",
    "source",
    "source_review_id",
    "city",
    "rating",
    "review_text",
    "language",
    "created_at",
    "author/anonymized_author",
    "source_url/source_ref",
    "collected_at",
    "provenance",
]

SECTION_8_TARGET_CORPUS_SCHEMA_FIELDS = [
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
    "source_ref / review_url",
    "provenance",
    "license_or_usage_class",
    "mapping_method",
    "mapping_confidence",
]

VIETNAMESE_DIACRITIC_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
ENGLISH_STOPWORD_RE = re.compile(
    r"\b(the|and|was|were|very|with|visited|visiting|loved|crowded|bit|okay|good|great|place|hotel)\b",
    re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]",
    re.UNICODE,
)


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    body = {k: v for k, v in payload.items() if k != "artifact_sha256"}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_internal_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_lf_normalized_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _percentile(sorted_values: list[float | int], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(float(sorted_values[0]), 4)
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    val = float(sorted_values[f]) + (k - f) * float(sorted_values[c] - sorted_values[f])
    return round(val, 4)


def _normalize_text(text: str) -> str:
    s = unicodedata.normalize("NFC", text.lower().strip())
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def classify_language_deterministic(text: str | None) -> str:
    if not text or not text.strip():
        return "unknown_or_empty"
    has_vi = bool(VIETNAMESE_DIACRITIC_RE.search(text))
    has_en = bool(ENGLISH_STOPWORD_RE.search(text))
    if has_vi and has_en:
        return "mixed_vi_en"
    if has_vi:
        return "vi"
    if has_en:
        return "en"
    return "unknown_or_other"


def _audit_text_corpus(texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    if total == 0:
        return {
            "total_rows": 0,
            "non_empty_text_rows": 0,
            "empty_review_count": 0,
            "whitespace_only_count": 0,
            "very_short_reviews_lt_20_chars": 0,
            "very_short_reviews_lt_5_words": 0,
            "excessively_long_reviews_gt_2000_chars": 0,
            "url_only_or_noise_reviews": 0,
            "emoji_only_reviews": 0,
            "exact_duplicate_text_rows": 0,
            "normalized_duplicate_text_rows": 0,
            "near_duplicate_pairs_jaccard_ge_0_80": 0,
            "encoding_or_unicode_problem_rows": 0,
            "html_remnant_rows": 0,
            "malformed_rows": 0,
            "char_length_distribution": {
                "min": 0,
                "p25": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "max": 0,
                "mean": 0.0,
            },
            "word_length_distribution": {
                "min": 0,
                "p25": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "max": 0,
                "mean": 0.0,
            },
        }

    empty_cnt = sum(1 for t in texts if t == "")
    ws_only_cnt = sum(1 for t in texts if t != "" and t.strip() == "")
    non_empty = [t for t in texts if t.strip() != ""]
    char_lens = sorted(len(t) for t in non_empty)
    word_lens = sorted(len(t.split()) for t in non_empty)

    short_chars = sum(1 for c in char_lens if c < 20)
    short_words = sum(1 for w in word_lens if w < 5)
    long_chars = sum(1 for c in char_lens if c > 2000)

    url_only = 0
    emoji_only = 0
    unicode_issues = 0
    html_rows = 0

    for t in non_empty:
        stripped_urls = URL_RE.sub("", t).strip()
        if stripped_urls == "":
            url_only += 1
        stripped_emoji = EMOJI_RE.sub("", t).strip()
        if stripped_emoji == "" and EMOJI_RE.search(t):
            emoji_only += 1
        if "\ufffd" in t or "\x00" in t or unicodedata.normalize("NFC", t) != t:
            unicode_issues += 1
        if HTML_TAG_RE.search(t) or "&nbsp;" in t or "&amp;" in t:
            html_rows += 1

    exact_counts = Counter(non_empty)
    exact_dups = sum(c - 1 for c in exact_counts.values() if c > 1)

    norm_texts = [_normalize_text(t) for t in non_empty]
    norm_counts = Counter(norm_texts)
    norm_dups = sum(c - 1 for c in norm_counts.values() if c > 1)

    near_dup_pairs = 0
    token_sets = [set(nt.split()) for nt in norm_texts]
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            u = token_sets[i] | token_sets[j]
            if u and (len(token_sets[i] & token_sets[j]) / len(u)) >= 0.80:
                near_dup_pairs += 1

    return {
        "total_rows": total,
        "non_empty_text_rows": len(non_empty),
        "empty_review_count": empty_cnt,
        "whitespace_only_count": ws_only_cnt,
        "very_short_reviews_lt_20_chars": short_chars,
        "very_short_reviews_lt_5_words": short_words,
        "excessively_long_reviews_gt_2000_chars": long_chars,
        "url_only_or_noise_reviews": url_only,
        "emoji_only_reviews": emoji_only,
        "exact_duplicate_text_rows": exact_dups,
        "normalized_duplicate_text_rows": norm_dups,
        "near_duplicate_pairs_jaccard_ge_0_80": near_dup_pairs,
        "encoding_or_unicode_problem_rows": unicode_issues,
        "html_remnant_rows": html_rows,
        "malformed_rows": 0,
        "char_length_distribution": {
            "min": min(char_lens) if char_lens else 0,
            "p25": _percentile(char_lens, 25),
            "p50": _percentile(char_lens, 50),
            "p75": _percentile(char_lens, 75),
            "p90": _percentile(char_lens, 90),
            "max": max(char_lens) if char_lens else 0,
            "mean": round(sum(char_lens) / len(char_lens), 4) if char_lens else 0.0,
        },
        "word_length_distribution": {
            "min": min(word_lens) if word_lens else 0,
            "p25": _percentile(word_lens, 25),
            "p50": _percentile(word_lens, 50),
            "p75": _percentile(word_lens, 75),
            "p90": _percentile(word_lens, 90),
            "max": max(word_lens) if word_lens else 0,
            "mean": round(sum(word_lens) / len(word_lens), 4) if word_lens else 0.0,
        },
    }


def _compute_reviews_per_poi_stats(counts_per_poi: list[int]) -> dict[str, Any]:
    s = sorted(counts_per_poi)
    return {
        "poi_universe_size": len(s),
        "total_reviews_mapped": sum(s),
        "min_reviews_per_poi": min(s) if s else 0,
        "median_reviews_per_poi": _percentile(s, 50),
        "mean_reviews_per_poi": round(sum(s) / len(s), 4) if s else 0.0,
        "max_reviews_per_poi": max(s) if s else 0,
        "p25_reviews_per_poi": _percentile(s, 25),
        "p50_reviews_per_poi": _percentile(s, 50),
        "p75_reviews_per_poi": _percentile(s, 75),
        "p90_reviews_per_poi": _percentile(s, 90),
        "pois_with_0_reviews": sum(1 for c in s if c == 0),
        "pois_with_1_to_4_reviews": sum(1 for c in s if 1 <= c <= 4),
        "pois_with_5_to_9_reviews": sum(1 for c in s if 5 <= c <= 9),
        "pois_with_10_plus_reviews": sum(1 for c in s if c >= 10),
        "pois_with_20_plus_reviews": sum(1 for c in s if c >= 20),
    }


def build_w07_audit_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    # Load authoritative manifests and POI files
    freeze_v2_manifest = yaml.safe_load(
        (repo_root / "data/manifests/dataset-freeze-v2.yaml").read_text(encoding="utf-8")
    )
    places_v2 = json.loads(
        (repo_root / "data/curated/gomate_places_freeze_v2.json").read_text(encoding="utf-8")
    )
    places_v1 = json.loads(
        (repo_root / "data/curated/places_canonical.json").read_text(encoding="utf-8")
    )
    raw_reviews_bundle = json.loads(
        (repo_root / "data/raw/vietnam_travel_reviews.json").read_text(encoding="utf-8")
    )
    norm_reviews = json.loads(
        (repo_root / "data/processed/reviews_normalized.json").read_text(encoding="utf-8")
    )
    curated_reviews = json.loads(
        (repo_root / "data/curated/reviews_curated.json").read_text(encoding="utf-8")
    )
    review_provenance = json.loads(
        (repo_root / "data/manifests/review-provenance.json").read_text(encoding="utf-8")
    )
    review_candidates = yaml.safe_load(
        (repo_root / "data/manifests/review-dataset-candidates.yaml").read_text(encoding="utf-8")
    )
    synth_prefs_lines = [
        line
        for line in (
            repo_root / "data/research/preferences/synthetic_preferences_v1.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    synth_places = json.loads(
        (repo_root / "data/seed/synthetic_places.json").read_text(encoding="utf-8")
    )
    synth_dests = json.loads(
        (repo_root / "data/seed/synthetic_destinations.json").read_text(encoding="utf-8")
    )

    if (
        len(norm_reviews) != len(curated_reviews)
        or review_provenance.get("audit_result", {}).get("verified_real_count") != 0
    ):
        raise ValueError("Unexpected review pipeline state.")

    # Canonical POI calculations
    v2_by_slug = Counter(p["destination_slug"] for p in places_v2)
    v2_core = [p for p in places_v2 if p.get("is_rec_a_core_v2")]
    v2_core_by_slug = Counter(p["destination_slug"] for p in v2_core)
    v2_categories = dict(sorted(Counter(p["category"] for p in places_v2).items()))
    v2_core_categories = dict(sorted(Counter(p["category"] for p in v2_core).items()))

    v2_osm_count = sum(
        1
        for p in places_v2
        if any(s.get("source_name") == "osm" for s in p.get("sources", []))
    )
    v2_overture_count = sum(
        1
        for p in places_v2
        if any(s.get("source_name") == "overture" for s in p.get("sources", []))
    )

    v2_ids = {p["place_id"]: p for p in places_v2}
    v1_ids = {p["id"]: p for p in places_v1}
    v1_sourced_count = sum(1 for p in places_v1 if len(p.get("sources", [])) > 0)
    v1_unsourced_count = sum(1 for p in places_v1 if len(p.get("sources", [])) == 0)
    v1_v2_id_overlap = len(set(v1_ids) & set(v2_ids))

    # Synthetic review pipeline analysis (vietnam_travel_reviews.json -> reviews_curated.json)
    raw_reviews = raw_reviews_bundle.get("reviews", [])
    curated_texts = [r.get("content", "") for r in curated_reviews]
    curated_lang_counts = Counter(
        classify_language_deterministic(r.get("content", "")) for r in curated_reviews
    )
    curated_city_counts = dict(
        sorted(Counter(r.get("city", "") for r in curated_reviews).items())
    )
    curated_ratings = [float(r["rating"]) for r in curated_reviews if r.get("rating") is not None]
    curated_rating_dist = dict(
        sorted(Counter(str(float(r["rating"])) for r in curated_reviews).items())
    )
    curated_per_city_ratings: dict[str, dict[str, Any]] = {}
    for city_name in sorted({r["city"] for r in curated_reviews}):
        vals = sorted(
            float(r["rating"]) for r in curated_reviews if r["city"] == city_name
        )
        curated_per_city_ratings[city_name] = {
            "count": len(vals),
            "min": min(vals),
            "max": max(vals),
            "mean": round(sum(vals) / len(vals), 4),
            "median": statistics.median(vals),
        }

    # Check how curated_reviews link to v1 vs v2
    curated_linked_v1 = [
        r for r in curated_reviews if r.get("place_id") and r["place_id"] in v1_ids
    ]
    curated_linked_v2 = [
        r for r in curated_reviews if r.get("place_id") and r["place_id"] in v2_ids
    ]

    # Heuristic name+city overlap between curated_reviews and Freeze v2
    v2_norm_city_name = {
        (_normalize_text(p["destination"]), _normalize_text(p["name"])): p["place_id"]
        for p in places_v2
    }
    curated_exact_name_in_v2 = sum(
        1
        for r in curated_reviews
        if (_normalize_text(r.get("city", "")), _normalize_text(r.get("target_name_raw", "")))
        in v2_norm_city_name
    )

    # ViHoRec audit (computed from local files when present, or verified from manifest + frozen snapshot)
    vihorec_dir = repo_root / "data/restricted/vihorec"
    vihorec_manifest_hashes = {
        Path(item["path"]).name: {
            "path": item["path"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for item in freeze_v2_manifest.get("committed_immutable_artifacts", [])
        if str(item.get("path", "")).startswith("data/restricted/vihorec/")
    }

    if vihorec_dir.exists() and (vihorec_dir / "interactions.csv").exists():
        with (vihorec_dir / "hotels.csv").open(encoding="utf-8") as f:
            vh_hotels = list(csv.DictReader(f))
        with (vihorec_dir / "interactions.csv").open(encoding="utf-8") as f:
            vh_inter = list(csv.DictReader(f))
        with (vihorec_dir / "users.csv").open(encoding="utf-8") as f:
            vh_users = list(csv.DictReader(f))
        with (vihorec_dir / "train.csv").open(encoding="utf-8") as f:
            vh_train = list(csv.DictReader(f))
        with (vihorec_dir / "val.csv").open(encoding="utf-8") as f:
            vh_val = list(csv.DictReader(f))
        with (vihorec_dir / "test.csv").open(encoding="utf-8") as f:
            vh_test = list(csv.DictReader(f))

        for fname, meta in vihorec_manifest_hashes.items():
            actual_sha = compute_file_sha256(vihorec_dir / fname)
            if actual_sha != meta["sha256"]:
                raise ValueError(
                    f"ViHoRec SHA256 mismatch for {fname}: expected {meta['sha256']}, got {actual_sha}"
                )

        hotel_city_map = {h["hotel_id"]: h["location"] for h in vh_hotels}
        vh_hotels_by_city = dict(
            sorted(Counter(h["location"] for h in vh_hotels).items())
        )
        vh_inter_by_city = dict(
            sorted(Counter(hotel_city_map[r["hotel_id"]] for r in vh_inter).items())
        )
        vh_inter_by_source = dict(
            sorted(Counter(r["source"] for r in vh_inter).items())
        )
        vh_inter_by_hotel = Counter(r["hotel_id"] for r in vh_inter)
        vh_counts_per_hotel = [vh_inter_by_hotel.get(h["hotel_id"], 0) for h in vh_hotels]

        vh_ratings = sorted(float(r["rating"]) for r in vh_inter)
        vh_rating_buckets = {
            "1.0_to_2.9": sum(1 for x in vh_ratings if 1.0 <= x < 3.0),
            "3.0_to_4.9": sum(1 for x in vh_ratings if 3.0 <= x < 5.0),
            "5.0_to_6.9": sum(1 for x in vh_ratings if 5.0 <= x < 7.0),
            "7.0_to_8.9": sum(1 for x in vh_ratings if 7.0 <= x < 9.0),
            "9.0_to_10.0": sum(1 for x in vh_ratings if 9.0 <= x <= 10.0),
        }
        vh_per_city_ratings: dict[str, dict[str, Any]] = {}
        for city_name in sorted(vh_hotels_by_city.keys()):
            c_vals = sorted(
                float(r["rating"])
                for r in vh_inter
                if hotel_city_map[r["hotel_id"]] == city_name
            )
            vh_per_city_ratings[city_name] = {
                "interactions": len(c_vals),
                "min": min(c_vals),
                "max": max(c_vals),
                "mean": round(sum(c_vals) / len(c_vals), 4),
                "median": statistics.median(c_vals),
            }
        vh_per_source_ratings: dict[str, dict[str, Any]] = {}
        for src_name in sorted(vh_inter_by_source.keys()):
            s_vals = sorted(
                float(r["rating"]) for r in vh_inter if r["source"] == src_name
            )
            vh_per_source_ratings[src_name] = {
                "interactions": len(s_vals),
                "min": min(s_vals),
                "max": max(s_vals),
                "mean": round(sum(s_vals) / len(s_vals), 4),
                "median": statistics.median(s_vals),
            }

        vh_dates = sorted(r["date"] for r in vh_inter if r.get("date"))
        vh_years = dict(sorted(Counter(d[:4] for d in vh_dates).items()))
        vh_invalid_dates = sum(
            1
            for d in vh_dates
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d) or d > "2026-12-31" or d < "2000-01-01"
        )

        # Heuristic normalized (city, hotel_name) match against Freeze v2
        vh_exact_name_city_matches = []
        for h in vh_hotels:
            key = (_normalize_text(h["location"]), _normalize_text(h["name"]))
            if key in v2_norm_city_name:
                vh_exact_name_city_matches.append(
                    {
                        "hotel_id": h["hotel_id"],
                        "location": h["location"],
                        "hotel_name": h["name"],
                        "matched_v2_place_id": v2_norm_city_name[key],
                        "interaction_count": vh_inter_by_hotel[h["hotel_id"]],
                    }
                )

        vihorec_summary = {
            "presence_status": "LOCAL_GITIGNORED_PRESENT_AND_SHA256_VERIFIED",
            "total_hotels": len(vh_hotels),
            "total_users": len(vh_users),
            "total_interactions": len(vh_inter),
            "train_rows": len(vh_train),
            "val_rows": len(vh_val),
            "test_rows": len(vh_test),
            "review_text_rows": 0,
            "hotels_by_city": vh_hotels_by_city,
            "interactions_by_city": vh_inter_by_city,
            "interactions_by_source": vh_inter_by_source,
            "core_three_city_coverage": {
                "hanoi_hotels": vh_hotels_by_city.get("Hà Nội", 0),
                "hanoi_interactions": vh_inter_by_city.get("Hà Nội", 0),
                "danang_hotels": vh_hotels_by_city.get("Đà Nẵng", 0),
                "danang_interactions": vh_inter_by_city.get("Đà Nẵng", 0),
                "halong_hotels": vh_hotels_by_city.get("Hạ Long", 0),
                "halong_interactions": vh_inter_by_city.get("Hạ Long", 0),
            },
            "interactions_per_hotel_stats": _compute_reviews_per_poi_stats(
                vh_counts_per_hotel
            ),
            "rating_audit": {
                "scale": "1.0_to_10.0",
                "missing_rating_count": 0,
                "invalid_range_count": sum(
                    1 for x in vh_ratings if x < 1.0 or x > 10.0
                ),
                "min": min(vh_ratings),
                "max": max(vh_ratings),
                "mean": round(sum(vh_ratings) / len(vh_ratings), 4),
                "median": statistics.median(vh_ratings),
                "bucket_distribution": vh_rating_buckets,
                "per_city_distribution": vh_per_city_ratings,
                "per_source_distribution": vh_per_source_ratings,
            },
            "temporal_audit": {
                "timestamp_format_interactions_csv": "YYYY-MM-DD",
                "timestamp_format_splits_csv": "unix_epoch_seconds",
                "oldest_date": vh_dates[0],
                "newest_date": vh_dates[-1],
                "missing_date_count": len(vh_inter) - len(vh_dates),
                "missing_date_pct": 0.0,
                "invalid_or_future_date_count": vh_invalid_dates,
                "counts_by_year": vh_years,
                "recency_aware_retrieval_possible": False,
                "recency_reason": "Timestamps exist (2011-10-15 to 2023-12-09), but review_text is 100% missing (ratings only).",
            },
            "canonical_poi_mapping": {
                "EXACT_MAPPING_HOTELS": 0,
                "EXACT_MAPPING_INTERACTIONS": 0,
                "HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_HOTELS": len(
                    vh_exact_name_city_matches
                ),
                "HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_INTERACTIONS": sum(
                    m["interaction_count"] for m in vh_exact_name_city_matches
                ),
                "UNMAPPED_BY_DETERMINISTIC_ID_HOTELS": len(vh_hotels),
                "UNMAPPED_BY_DETERMINISTIC_ID_INTERACTIONS": len(vh_inter),
                "exact_normalized_name_city_matches": vh_exact_name_city_matches,
            },
            "cryptographic_manifest_entries": vihorec_manifest_hashes,
        }
    else:
        existing_audit_path = repo_root / AUDIT_JSON_RELPATH
        if not existing_audit_path.exists():
            raise FileNotFoundError(
                "ViHoRec local directory is missing and no frozen audit artifact exists."
            )
        existing_payload = json.loads(existing_audit_path.read_text(encoding="utf-8"))
        vihorec_summary = existing_payload["section_5_review_corpus_inventory"][
            "vihorec_rating_interactions"
        ]
        if (
            vihorec_summary["cryptographic_manifest_entries"]
            != vihorec_manifest_hashes
        ):
            raise ValueError(
                "ViHoRec manifest hashes in dataset-freeze-v2.yaml do not match frozen audit."
            )

    # Coverage across the 759 verified OSM POIs and 622 REC-A Core v2 POIs
    real_reviews_per_v2_poi = [0 for _ in places_v2]
    real_reviews_per_core_poi = [0 for _ in v2_core]
    heur_synth_reviews_per_v2_poi = [
        1
        if (
            _normalize_text(p["destination"]),
            _normalize_text(p["name"]),
        )
        in {
            (_normalize_text(r.get("city", "")), _normalize_text(r.get("target_name_raw", "")))
            for r in curated_reviews
        }
        else 0
        for p in places_v2
    ]

    # Section 6: Missingness across all 13 required fields
    section_6_field_quality = {
        "required_fields": SECTION_6_REQUIRED_FIELDS,
        "sources": {
            "vietnam_travel_reviews_raw_json": {
                "path": "data/raw/vietnam_travel_reviews.json",
                "total_rows": len(raw_reviews),
                "missingness_pct_by_field": {
                    "review_id": 100.0,
                    "poi_id": 100.0,
                    "source": 0.0,
                    "source_review_id": 0.0,
                    "city": 0.0,
                    "rating": 0.0,
                    "review_text": 0.0,
                    "language": 100.0,
                    "created_at": 100.0,
                    "author/anonymized_author": 100.0,
                    "source_url/source_ref": 100.0,
                    "collected_at": 100.0,
                    "provenance": 0.0,
                },
                "field_notes": {
                    "review_id": "Missing in raw; only source_review_id (rev_dn_001..rev_unmatched_001) exists.",
                    "poi_id": "100% missing in raw; only target_place_name string exists.",
                    "provenance": "Top-level metadata falsely claims academic_benchmark; audited as UNVERIFIED_SYNTHETIC in data/manifests/review-provenance.json.",
                },
            },
            "reviews_curated_json": {
                "path": "data/curated/reviews_curated.json",
                "total_rows": len(curated_reviews),
                "missingness_pct_by_field": {
                    "review_id": 0.0,
                    "poi_id": round((1 / len(curated_reviews)) * 100.0, 2),
                    "source": 0.0,
                    "source_review_id": 0.0,
                    "city": 0.0,
                    "rating": 0.0,
                    "review_text": 0.0,
                    "language": 100.0,
                    "created_at": 100.0,
                    "author/anonymized_author": 100.0,
                    "source_url/source_ref": 100.0,
                    "collected_at": 100.0,
                    "provenance": 0.0,
                },
                "field_notes": {
                    "poi_id": "1/9 missing (11.11%, rev_unmatched_001); 8/9 heuristically linked ONLY to unsourced legacy v1 rows in places_canonical.json (0/9 in gomate_places_freeze_v2.json).",
                    "review_text": "Stored under key 'content'; all 9 rows are handcrafted synthetic Vietnamese fixtures.",
                },
            },
            "vihorec_interactions_csv": {
                "path": "data/restricted/vihorec/interactions.csv",
                "total_rows": vihorec_summary["total_interactions"],
                "missingness_pct_by_field": {
                    "review_id": 100.0,
                    "poi_id": 0.0,
                    "source": 0.0,
                    "source_review_id": 100.0,
                    "city": 0.0,
                    "rating": 0.0,
                    "review_text": 100.0,
                    "language": 100.0,
                    "created_at": 0.0,
                    "author/anonymized_author": 0.0,
                    "source_url/source_ref": 100.0,
                    "collected_at": 100.0,
                    "provenance": 0.0,
                },
                "field_notes": {
                    "poi_id": "Has ViHoRec internal hotel_id (H0000..H0559) via hotels.csv, but 100% missing canonical GoMate place_id or OSM source_id.",
                    "review_text": "100% missing (0 review text rows across all 17,911 interactions).",
                    "author/anonymized_author": "Has anonymized user_id (U00000..U06821).",
                },
            },
            "ai_service_search_reviews_stub": {
                "path": "apps/ai-service/app/tools/search_reviews.py",
                "total_rows": 2,
                "missingness_pct_by_field": {
                    "review_id": 100.0,
                    "poi_id": 100.0,
                    "source": 100.0,
                    "source_review_id": 100.0,
                    "city": 100.0,
                    "rating": 100.0,
                    "review_text": 0.0,
                    "language": 100.0,
                    "created_at": 100.0,
                    "author/anonymized_author": 100.0,
                    "source_url/source_ref": 100.0,
                    "collected_at": 100.0,
                    "provenance": 0.0,
                },
                "field_notes": {
                    "review_text": "Hardcoded mock tool returning 2 template strings ('Loved visiting {place_name}!', 'It was okay, a bit crowded.').",
                },
            },
        },
    }

    payload: dict[str, Any] = {
        "schema_version": "w07_data_rag_readiness_audit.v1",
        "task_id": "W07-0-DATA-RAG-READINESS-AUDIT-CORRECTIVE-01",
        "previous_gate": PREVIOUS_GATE,
        "previous_gate_decision": PREVIOUS_GATE_DECISION,
        "authoritative_base_commit": AUTHORITATIVE_DEVELOP_BASE_SHA,
        "w06_status": "CLOSED_UNMODIFIED",
        "next_gate": NEXT_GATE,
        "section_3_repository_data_sources": {
            "summary": {
                "total_sources_inspected": 12,
                "real_provenanced_review_text_sources_present": 0,
                "real_provenanced_review_text_rows": 0,
                "synthetic_review_text_rows": 9,
                "stub_template_review_strings": 2,
                "rating_only_interaction_rows_no_text": vihorec_summary["total_interactions"],
                "non_review_rag_documents_in_freeze_v2": 1223,
            },
            "sources": [
                {
                    "source_id": "gomate_places_freeze_v2",
                    "paths": ["data/curated/gomate_places_freeze_v2.json"],
                    "storage_status": "TRACKED_COMMITTED",
                    "classification": "API_DERIVED_PUBLIC_VERIFIED",
                    "provenance_category": "official/public + API (OpenStreetMap Overpass ODbL 1.0 + Overture Maps 2026-09-23.1)",
                    "entity_type": "POI_AUTHORITY",
                    "row_count": len(places_v2),
                    "has_review_text": False,
                    "has_ratings": False,
                    "notes": "Authoritative canonical POI freeze v2: 759 verified OSM POIs (622 REC-A core 3-city POIs + 137 secondary POIs). All rating=null and review_count=0.",
                },
                {
                    "source_id": "places_canonical_v1_legacy",
                    "paths": ["data/curated/places_canonical.json"],
                    "storage_status": "TRACKED_COMMITTED",
                    "classification": "MIXED_OSM_AND_LEGACY_SEED",
                    "provenance_category": "official/public (97 OSM/Overture rows) + synthetic/legacy seed (11 unsourced rows)",
                    "entity_type": "LEGACY_POI_TABLE",
                    "row_count": len(places_v1),
                    "has_review_text": False,
                    "has_ratings": False,
                    "notes": "Legacy 108-POI table used by data/pipelines/reviews/link_reviews.py; 97 overlap with Freeze v2, while 11 have sources=[] (and all 8 linked synthetic reviews map to those 11 unsourced rows).",
                },
                {
                    "source_id": "vietnam_travel_reviews_synthetic_pipeline",
                    "paths": [
                        "data/raw/vietnam_travel_reviews.json",
                        "data/processed/reviews_normalized.json",
                        "data/curated/reviews_curated.json",
                        "data/manifests/review-provenance.json",
                    ],
                    "storage_status": "TRACKED_COMMITTED",
                    "classification": "GENERATED_SYNTHETIC_QUARANTINED",
                    "provenance_category": "synthetic",
                    "entity_type": "SYNTHETIC_REVIEW_FIXTURE",
                    "row_count": len(curated_reviews),
                    "has_review_text": True,
                    "has_ratings": True,
                    "notes": "9 handcrafted Vietnamese review rows created as pipeline unit-test fixtures; quarantined by review-provenance.json (overall_status=UNVERIFIED_SYNTHETIC, verified_real_count=0).",
                },
                {
                    "source_id": "vihorec_restricted_hotel_interactions",
                    "paths": [
                        "data/restricted/vihorec/hotels.csv",
                        "data/restricted/vihorec/interactions.csv",
                        "data/restricted/vihorec/users.csv",
                        "data/restricted/vihorec/train.csv",
                        "data/restricted/vihorec/val.csv",
                        "data/restricted/vihorec/test.csv",
                    ],
                    "storage_status": "LOCAL_ONLY_GITIGNORED_SHA256_FROZEN",
                    "classification": "RESTRICTED_PUBLIC_ACADEMIC_DATASET",
                    "provenance_category": "Kaggle/Hugging Face/GitHub + restricted",
                    "entity_type": "HOTEL_RATING_INTERACTIONS_NO_TEXT",
                    "row_count": vihorec_summary["total_interactions"],
                    "has_review_text": False,
                    "has_ratings": True,
                    "notes": "17,911 real hotel rating interactions (1.0-10.0 scale) across 560 hotels and 6,822 users from Booking/Traveloka/iVIVU. Contains 0 review text and 0 Hà Nội / Hạ Long hotels.",
                },
                {
                    "source_id": "vlsp2018_and_vimacsa_candidates",
                    "paths": [
                        "data/manifests/review-dataset-candidates.yaml",
                        "data/restricted/README.md",
                    ],
                    "storage_status": "REFERENCED_IN_MANIFEST_NOT_PRESENT_ON_DISK",
                    "classification": "RESTRICTED_EXTERNAL_NOT_ACQUIRED",
                    "provenance_category": "restricted",
                    "entity_type": "EXTERNAL_CANDIDATE_MANIFEST_ONLY",
                    "row_count": 0,
                    "has_review_text": False,
                    "has_ratings": False,
                    "notes": f"Documented in review-dataset-candidates.yaml ({len(review_candidates.get('candidates', {}))} candidates: vlsp_2018_absa_hotel, vimacsa, vihorec, google_maps_reviews, tripadvisor_reviews). Neither data/restricted/vlsp2018/ nor data/restricted/vimacsa/ exists on disk (status=REQUEST_NOT_SENT).",
                },
                {
                    "source_id": "wikivoyage_and_osm_rag_documents",
                    "paths": [
                        "data/manifests/dataset-freeze-v2.yaml",
                        "apps/ai-service/app/rag/retriever.py",
                    ],
                    "storage_status": "TRACKED_MANIFEST_AND_DB_SEED",
                    "classification": "PUBLIC_ENCYCLOPEDIC_AND_OSM_METADATA",
                    "provenance_category": "official/public",
                    "entity_type": "NON_REVIEW_RAG_DOCUMENTS",
                    "row_count": 1223,
                    "has_review_text": False,
                    "has_ratings": False,
                    "notes": "464 English Wikivoyage destination guide chunks (CC BY-SA 3.0) + 759 OSM place metadata documents (ODbL 1.0) in Freeze v2 database state. Contains 0 user reviews.",
                },
                {
                    "source_id": "synthetic_preferences_and_seed_files",
                    "paths": [
                        "data/research/preferences/synthetic_preferences_v1.jsonl",
                        "data/evaluation/synthetic/preferences_n300_seed42.json",
                        "data/seed/synthetic_places.json",
                        "data/seed/synthetic_destinations.json",
                        "database/seed/places.json",
                    ],
                    "storage_status": "TRACKED_COMMITTED",
                    "classification": "GENERATED_SYNTHETIC",
                    "provenance_category": "synthetic",
                    "entity_type": "SYNTHETIC_PERSONAS_AND_SEED_PLACES",
                    "row_count": len(synth_prefs_lines) + len(synth_places) + len(synth_dests),
                    "has_review_text": False,
                    "has_ratings": True,
                    "notes": "300 synthetic user preference profiles (seed=42) for REC-A + 56 legacy synthetic seed places + 50 synthetic destinations. Quarantined from W07 review RAG.",
                },
                {
                    "source_id": "ai_service_search_reviews_tool_stub",
                    "paths": ["apps/ai-service/app/tools/search_reviews.py"],
                    "storage_status": "TRACKED_COMMITTED",
                    "classification": "GENERATED_SYNTHETIC_CODE_STUB",
                    "provenance_category": "synthetic",
                    "entity_type": "MOCK_TOOL_STUB",
                    "row_count": 2,
                    "has_review_text": True,
                    "has_ratings": False,
                    "notes": "Hardcoded Python stub returning 2 generic English strings for any place_name.",
                },
            ],
        },
        "section_4_poi_authority": {
            "total_canonical_pois_db": freeze_v2_manifest["item_universe"]["total_canonical_places"],
            "verified_pois_freeze_v2": len(places_v2),
            "core_pois_rec_a_v2": len(v2_core),
            "secondary_verified_pois_v2": len(places_v2) - len(v2_core),
            "unverified_legacy_seed_pois_in_db": (
                freeze_v2_manifest["item_universe"]["total_canonical_places"] - len(places_v2)
            ),
            "legacy_places_canonical_v1_count": len(places_v1),
            "legacy_places_canonical_v1_sourced": v1_sourced_count,
            "legacy_places_canonical_v1_unsourced": v1_unsourced_count,
            "legacy_places_v1_overlap_with_freeze_v2": v1_v2_id_overlap,
            "counts_by_core_city_verified_v2": {
                "ha_noi": v2_by_slug["ha-noi"],
                "da_nang_total_verified": v2_by_slug["da-nang"],
                "da_nang_rec_a_core": v2_core_by_slug["da-nang"],
                "da_nang_outside_core": v2_by_slug["da-nang"] - v2_core_by_slug["da-nang"],
                "ha_long": v2_by_slug["ha-long"],
            },
            "counts_by_secondary_city_verified_v2": {
                "hoi_an": v2_by_slug["hoi-an"],
                "hue": v2_by_slug["hue"],
                "nha_trang": v2_by_slug["nha-trang"],
            },
            "category_distribution_verified_v2": v2_categories,
            "category_distribution_core_v2": v2_core_categories,
            "canonical_id_format": "UUID (v4/v5 lowercase 36-char hyphenated string, e.g. 7d7e049e-d3f9-436a-aa1a-bf49ca0d1206)",
            "available_source_ids": {
                "osm": {
                    "places_count": v2_osm_count,
                    "coverage_pct_of_verified_v2": 100.0,
                    "id_format": "{node|way|relation}/{osm_numeric_id}",
                },
                "overture": {
                    "places_count": v2_overture_count,
                    "coverage_pct_of_verified_v2": round(
                        (v2_overture_count / len(places_v2)) * 100.0, 2
                    ),
                    "id_format": "32-hex-char Overture GERS ID",
                },
            },
            "usable_mapping_keys_for_reviews": [
                "place_id (canonical GoMate UUID from gomate_places_freeze_v2.json - required on every final review row)",
                "sources[].source_id where source_name=='osm' (deterministic upstream OSM element key)",
                "sources[].source_id where source_name=='overture' (deterministic Overture GERS key for 247 POIs)",
                "(latitude, longitude, normalized_name, city/address) - audited multi-signal geo/entity resolution with manual verification for ambiguous cases; name-only automatic linking is forbidden as scientific authority",
            ],
            "review_to_poi_mapping_audit": {
                "synthetic_reviews_curated_9_rows_against_freeze_v2_759": {
                    "EXACT_MAPPING": 0,
                    "HEURISTIC_MAPPING": curated_exact_name_in_v2,
                    "UNMAPPED": len(curated_reviews) - curated_exact_name_in_v2,
                    "explanation": (
                        f"0/9 rows carry a Freeze v2 place_id or OSM source_id (EXACT_MAPPING=0). "
                        f"All 8 linked place_ids in reviews_curated.json ({len(curated_linked_v1)}/9 in places_canonical.json, "
                        f"{len(curated_linked_v2)}/9 in gomate_places_freeze_v2.json) point to unsourced legacy v1 rows. "
                        f"By normalized (city, name) string heuristic against Freeze v2, only {curated_exact_name_in_v2}/9 match."
                    ),
                },
                "synthetic_reviews_curated_9_rows_against_legacy_places_canonical_108": {
                    "EXACT_MAPPING": 0,
                    "HEURISTIC_MAPPING": len(curated_linked_v1),
                    "UNMAPPED": len(curated_reviews) - len(curated_linked_v1),
                    "explanation": "Linked by data/pipelines/reviews/link_reviews.py using target_place_name + city string similarity (no upstream POI ID).",
                },
                "vihorec_560_hotels_17911_interactions_against_freeze_v2_759": {
                    "EXACT_MAPPING_HOTELS": 0,
                    "EXACT_MAPPING_INTERACTIONS": 0,
                    "HEURISTIC_MAPPING_HOTELS": vihorec_summary["canonical_poi_mapping"][
                        "HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_HOTELS"
                    ],
                    "HEURISTIC_MAPPING_INTERACTIONS": vihorec_summary[
                        "canonical_poi_mapping"
                    ]["HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_INTERACTIONS"],
                    "UNMAPPED_HOTELS": (
                        vihorec_summary["total_hotels"]
                        - vihorec_summary["canonical_poi_mapping"][
                            "HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_HOTELS"
                        ]
                    ),
                    "UNMAPPED_INTERACTIONS": (
                        vihorec_summary["total_interactions"]
                        - vihorec_summary["canonical_poi_mapping"][
                            "HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_INTERACTIONS"
                        ]
                    ),
                    "explanation": "ViHoRec uses internal hotel_id H0000..H0559 with no coordinates or OSM IDs (EXACT_MAPPING=0). Only 2 Đà Nẵng hotels (36 rating-only interactions) match Freeze v2 by exact normalized (city, hotel_name).",
                },
                "real_text_reviews_against_freeze_v2_759": {
                    "EXACT_MAPPING": 0,
                    "HEURISTIC_MAPPING": 0,
                    "UNMAPPED": 0,
                    "explanation": "0 real provenanced review text records exist in the repository.",
                },
            },
        },
        "section_5_review_corpus_inventory": {
            "authoritative_real_review_text_corpus_against_freeze_v2_759": {
                "total_rows": 0,
                "unique_reviews": 0,
                "unique_pois_with_reviews": 0,
                "reviews_by_city": {
                    "Hà Nội": 0,
                    "Đà Nẵng": 0,
                    "Hạ Long": 0,
                },
                "reviews_per_poi_across_759_verified_pois": _compute_reviews_per_poi_stats(
                    real_reviews_per_v2_poi
                ),
                "reviews_per_poi_across_622_core_pois": _compute_reviews_per_poi_stats(
                    real_reviews_per_core_poi
                ),
            },
            "quarantined_synthetic_reviews_curated": {
                "total_rows": len(curated_reviews),
                "unique_reviews": len({r["content"] for r in curated_reviews}),
                "unique_pois_linked_in_legacy_v1": len(
                    {r["place_id"] for r in curated_reviews if r.get("place_id")}
                ),
                "unique_pois_linked_by_id_in_freeze_v2": 0,
                "unique_pois_heuristic_name_match_in_freeze_v2": curated_exact_name_in_v2,
                "reviews_by_city": curated_city_counts,
                "core_three_city_coverage": {
                    "Hà Nội": curated_city_counts.get("Hà Nội", 0),
                    "Đà Nẵng": curated_city_counts.get("Đà Nẵng", 0),
                    "Hạ Long": curated_city_counts.get("Hạ Long", 0),
                },
                "reviews_per_poi_across_759_verified_pois_by_id": _compute_reviews_per_poi_stats(
                    real_reviews_per_v2_poi
                ),
                "reviews_per_poi_across_759_verified_pois_if_heuristic_name_matched": _compute_reviews_per_poi_stats(
                    heur_synth_reviews_per_v2_poi
                ),
                "reviews_per_poi_across_108_legacy_v1_pois": _compute_reviews_per_poi_stats(
                    [
                        1
                        if p["id"]
                        in {r["place_id"] for r in curated_reviews if r.get("place_id")}
                        else 0
                        for p in places_v1
                    ]
                ),
            },
            "vihorec_rating_interactions": vihorec_summary,
        },
        "section_6_review_field_quality": section_6_field_quality,
        "section_7_text_quality_audit": {
            "real_review_text_corpus": _audit_text_corpus([]),
            "quarantined_synthetic_reviews_curated_9_rows": _audit_text_corpus(
                curated_texts
            ),
            "vihorec_interactions_17911_rows": {
                "total_rows": vihorec_summary["total_interactions"],
                "non_empty_text_rows": 0,
                "empty_review_count": vihorec_summary["total_interactions"],
                "note": "ViHoRec contains numerical ratings only; 100% of rows have no review_text column.",
            },
        },
        "section_8_language_audit": {
            "method": "Deterministic offline regex/Unicode diacritic + lexical marker classification (zero LLM calls)",
            "real_review_text_corpus": {
                "vi": 0,
                "en": 0,
                "mixed_vi_en": 0,
                "unknown_or_other": 0,
            },
            "quarantined_synthetic_reviews_curated_9_rows": {
                "vi": curated_lang_counts.get("vi", 0),
                "en": curated_lang_counts.get("en", 0),
                "mixed_vi_en": curated_lang_counts.get("mixed_vi_en", 0),
                "unknown_or_other": curated_lang_counts.get("unknown_or_other", 0),
            },
            "ai_service_search_reviews_stub_2_rows": {
                "vi": 0,
                "en": 2,
                "mixed_vi_en": 0,
                "unknown_or_other": 0,
            },
            "existing_non_review_rag_wikivoyage_464_chunks": {
                "language": "en",
                "note": "Wikivoyage travel-guide chunks are 100% English encyclopedic text, not Vietnamese user reviews.",
            },
        },
        "section_9_rating_audit": {
            "scale_comparison_and_incompatibility": {
                "places_freeze_v2": "All 759 verified POIs have rating=null (100% missing by governance rule).",
                "vietnam_travel_reviews_synthetic_9_rows": "1.0 to 5.0 scale (0.5 increments; range observed 3.0 to 5.0).",
                "vihorec_17911_interactions": "1.0 to 10.0 scale (OTA hotel rating scale from Booking/Traveloka/iVIVU).",
                "scales_differ_between_sources": True,
                "normalization_performed_in_w07_0": False,
            },
            "quarantined_synthetic_reviews_curated_9_rows": {
                "scale": "1.0_to_5.0",
                "missing_rating_count": 0,
                "invalid_range_count": 0,
                "min": min(curated_ratings),
                "max": max(curated_ratings),
                "mean": round(sum(curated_ratings) / len(curated_ratings), 4),
                "median": statistics.median(curated_ratings),
                "value_distribution": curated_rating_dist,
                "per_city_distribution": curated_per_city_ratings,
                "per_source_distribution": {
                    "academic_benchmark_unverified_synthetic": {
                        "count": len(curated_ratings),
                        "mean": round(sum(curated_ratings) / len(curated_ratings), 4),
                        "median": statistics.median(curated_ratings),
                    }
                },
            },
            "vihorec_interactions_17911_rows": vihorec_summary["rating_audit"],
        },
        "section_10_temporal_audit": {
            "quarantined_synthetic_reviews_curated_9_rows": {
                "oldest_review": None,
                "newest_review": None,
                "missing_date_count": len(curated_reviews),
                "missing_date_pct": 100.0,
                "counts_by_year": {},
                "invalid_or_future_dates": 0,
                "timestamp_format": None,
                "recency_aware_retrieval_possible": False,
            },
            "vihorec_interactions_17911_rows": vihorec_summary["temporal_audit"],
            "recency_aware_retrieval_overall_feasibility": {
                "possible_now": False,
                "reason": "Synthetic text reviews have 100% missing dates; ViHoRec has valid dates (2011-2023) but 0% review text.",
            },
        },
        "section_11_provenance_and_licensing_audit": {
            "sources": [
                {
                    "source_id": "vietnam_travel_reviews_synthetic_pipeline",
                    "provenance_class": "synthetic",
                    "license": "Internal test fixture (falsely labeled CC BY-NC-SA 4.0 / academic_benchmark in raw header; corrected to UNVERIFIED_SYNTHETIC in data/manifests/review-provenance.json)",
                    "explains_where_from": True,
                    "explains_when_collected": True,
                    "explains_which_poi": False,
                    "thesis_authority_risk": "HIGH_RISK_IF_CLAIMED_AS_REAL",
                    "audit_verdict": "MUST NOT be claimed as real user reviews or academic benchmark data in the thesis; strictly quarantined as a 9-row pipeline unit test fixture.",
                },
                {
                    "source_id": "vihorec_restricted_hotel_interactions",
                    "provenance_class": "Kaggle/Hugging Face/GitHub + restricted",
                    "license": "Academic research benchmark (upstream ViHoRec 1.0.0; git-ignored under data/restricted/vihorec/, SHA256-locked in dataset-freeze-v2.yaml)",
                    "explains_where_from": True,
                    "explains_when_collected": True,
                    "explains_which_poi": False,
                    "thesis_authority_risk": "LOW_FOR_RECB_COLLABORATIVE_FILTERING_HIGH_IF_CLAIMED_FOR_RAG",
                    "audit_verdict": "Valid for REC-B hotel collaborative filtering only; cannot support W07 review-text RAG because review_text is 100% absent and hotels lack deterministic links to canonical OSM POIs.",
                },
                {
                    "source_id": "vlsp2018_and_vimacsa_external_candidates",
                    "provenance_class": "restricted",
                    "license": "Pending academic DUA / request not sent",
                    "explains_where_from": True,
                    "explains_when_collected": False,
                    "explains_which_poi": False,
                    "thesis_authority_risk": "NOT_USABLE_NOT_ACQUIRED_AND_UNLINKED_TO_POIS",
                    "audit_verdict": "0 files present on disk; furthermore VLSP 2018 ABSA consists of anonymized sentence-level fragments without POI identifiers.",
                },
                {
                    "source_id": "gomate_places_freeze_v2_and_wikivoyage",
                    "provenance_class": "official/public + API",
                    "license": "ODbL 1.0 (OpenStreetMap) + CDLA Permissive 2.0 / Apache 2.0 / CC0 (Overture) + CC BY-SA 3.0 (Wikivoyage)",
                    "explains_where_from": True,
                    "explains_when_collected": True,
                    "explains_which_poi": True,
                    "thesis_authority_risk": "LOW_AUTHORITATIVE_FOR_POI_METADATA_AND_GUIDES",
                    "audit_verdict": "Authoritative for canonical POI entity layer (759 POIs) and general destination guide chunks (464 chunks), but contains 0 user reviews.",
                },
            ],
        },
        "section_12_synthetic_data_firewall": {
            "REAL_REVIEW_DATA": {
                "text_review_rows": 0,
                "rating_only_interaction_rows_no_text": vihorec_summary[
                    "total_interactions"
                ],
                "sources": [
                    "None for review text (0 rows). ViHoRec (17,911 rows) is real rating-only interaction data with 0 text."
                ],
            },
            "SYNTHETIC_REVIEW_DATA": {
                "text_review_rows": len(curated_reviews),
                "tool_stub_template_rows": 2,
                "synthetic_preference_personas": len(synth_prefs_lines),
                "synthetic_seed_places": len(synth_places),
                "synthetic_seed_destinations": len(synth_dests),
                "sources": [
                    "data/raw/vietnam_travel_reviews.json (9 rows)",
                    "data/processed/reviews_normalized.json (9 rows)",
                    "data/curated/reviews_curated.json (9 rows)",
                    "apps/ai-service/app/tools/search_reviews.py (2 stub strings)",
                    "data/research/preferences/synthetic_preferences_v1.jsonl (300 personas)",
                    "data/seed/synthetic_places.json (56 rows)",
                    "data/seed/synthetic_destinations.json (50 rows)",
                ],
                "firewall_rule": "Strictly quarantined from W07 scientific retrieval and factuality evaluation (`review-provenance.json`: overall_status=UNVERIFIED_SYNTHETIC).",
            },
            "UNKNOWN_PROVENANCE": {
                "text_review_rows": 0,
                "unverified_legacy_seed_places_in_db": 123,
                "sources": [
                    "123 legacy seed places in DB / 11 unsourced rows in data/curated/places_canonical.json with sources=[] (excluded from gomate_places_freeze_v2.json)."
                ],
            },
        },
        "section_13_retrieval_unit_recommendation": {
            "recommended_primary_unit": "one_review_equals_one_retrieval_unit",
            "rationale": (
                "Typical travel/hospitality reviews (and the 9 repository fixture reviews at 85-189 chars / 19-42 words, "
                "median 176 chars / 40 words) are short, self-contained opinion units tied to a single (poi_id, rating, author, created_at) tuple. "
                "Splitting short reviews into sentence or sliding-window fragments severs aspect opinions from their POI/rating/date metadata "
                "and inflates index noise, while aggregating all reviews of a POI into one giant block dilutes aspect-specific retrieval precision."
            ),
            "comparison_matrix": [
                {
                    "unit_type": "one_review_equals_one_retrieval_unit",
                    "pros": "Preserves exact review_id, poi_id, rating, timestamp, and aspect context; ideal for 20-250 word travel reviews; straightforward citation & factuality grounding.",
                    "cons": "Very long multi-topic blog-style reviews (>1,500 chars / >300 words) may benefit from secondary sub-chunking with parent review_id metadata.",
                    "verdict": "RECOMMENDED_DEFAULT (with optional sub-chunking only if acquired reviews exceed 300 words).",
                },
                {
                    "unit_type": "sentence_chunks",
                    "pros": "Fine-grained aspect isolation.",
                    "cons": "Loses coreference ('Quán rất sạch', 'Giá hợp lý') and detaches sentences from surrounding sentiment caveats.",
                    "verdict": "NOT_RECOMMENDED_AS_PRIMARY",
                },
                {
                    "unit_type": "sliding_window_chunks",
                    "pros": "Useful for long encyclopedic guides (e.g., 464 Wikivoyage chunks).",
                    "cons": "Unnecessary overhead and boundary duplication for short user reviews (<200 words).",
                    "verdict": "NOT_RECOMMENDED_FOR_SHORT_REVIEWS",
                },
                {
                    "unit_type": "aggregated_poi_review_blocks",
                    "pros": "One document per POI.",
                    "cons": "Mixes contradictory user opinions and ratings into a single vector, degrading aspect-specific top-k retrieval and per-review citation.",
                    "verdict": "NOT_RECOMMENDED_AS_PRIMARY",
                },
            ],
        },
        "section_14_w07_evaluation_feasibility": {
            "RAG_READINESS_STATUS": "NOT_READY",
            "target_query_set_size": "40-60 queries",
            "required_query_dimensions": [
                "POI specific",
                "food",
                "service",
                "culture",
                "nature",
                "family",
                "budget",
                "positive aspect",
                "negative aspect",
                "location",
                "experience",
            ],
            "dimension_coverage_in_current_real_review_data": {
                dim: {"real_reviews_available": 0, "status": "UNSUPPORTED_ZERO_REAL_DATA"}
                for dim in [
                    "POI specific",
                    "food",
                    "service",
                    "culture",
                    "nature",
                    "family",
                    "budget",
                    "positive aspect",
                    "negative aspect",
                    "location",
                    "experience",
                ]
            },
            "can_create_human_relevance_labels_from_current_corpus": False,
            "evidence_summary": (
                "The repository currently contains 0 real provenanced review text records across all 759 verified OSM POIs "
                "(and 0 across the 622 REC-A core POIs in Hà Nội, Đà Nẵng, and Hạ Long). The only review text in the repository "
                "is a 9-row synthetic fixture (vietnam_travel_reviews.json / reviews_curated.json) quarantined by review-provenance.json, "
                "which covers 0 POIs in Hạ Long, 0 verified Freeze v2 POIs by ID, and has only 1 negative-aspect sentence across the entire file. "
                "Therefore, a scientifically valid 40-60 query review-RAG evaluation benchmark cannot be constructed or human-labeled until "
                "an authoritative POI-linked review corpus is acquired."
            ),
        },
        "section_15_technology_decision_matrix": {
            "winner_frozen_in_w07_0": False,
            "candidate_status": "PROVISIONAL_SHORTLIST_NO_WINNER_FROZEN",
            "measurement_hygiene_label": PLANNING_ESTIMATE_LABEL,
            "measurement_hygiene_note": (
                "All latency, RAM, and workload figures in Section 15 and Section 16 are strictly "
                "labelled PLANNING_ESTIMATE_NOT_MEASURED and must NOT be cited as experimental W07 evidence."
            ),
            "expected_target_corpus_scale_after_acquisition": (
                "Scientific Minimum >= 300 reviews across >= 60 POIs; Preferred 600-1,200 reviews across 75-100 POIs; "
                "Stretch 1,100-1,650 reviews across ~110 POIs in Hà Nội, Đà Nẵng, and Hạ Long (comfortably fits in local RAM/CPU)."
            ),
            "lexical_baseline": {
                "method": "BM25 (rank_bm25 / BM25Okapi with Vietnamese-aware tokenization & accent-preserving + accent-folded dual fields)",
                "role": "Mandatory deterministic lexical baseline for exact POI names, dish names, and Vietnamese aspect keywords.",
                "local_cpu_feasible": True,
                "measurement_status": PLANNING_ESTIMATE_LABEL,
            },
            "dense_retrieval_candidate_families": [
                {
                    "candidate_id": "intfloat/multilingual-e5-small",
                    "family": "Multilingual E5 (118M params, 384d)",
                    "vietnamese_support": "Strong multilingual retrieval alignment (query/passage prefix protocol)",
                    "cpu_latency_and_memory": f"{PLANNING_ESTIMATE_LABEL}: compact local CPU bi-encoder (approx. <500 MB RAM class)",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "free_local_operation": True,
                },
                {
                    "candidate_id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    "family": "Multilingual MiniLM (118M params, 384d)",
                    "vietnamese_support": "Solid baseline multilingual semantic similarity",
                    "cpu_latency_and_memory": f"{PLANNING_ESTIMATE_LABEL}: compact local CPU bi-encoder (approx. <500 MB RAM class)",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "free_local_operation": True,
                },
                {
                    "candidate_id": "bkai-foundation-models/vietnamese-bi-encoder",
                    "family": "PhoBERT-based Vietnamese Bi-Encoder (135M params, 768d)",
                    "vietnamese_support": "Native Vietnamese segmentation & semantics",
                    "cpu_latency_and_memory": f"{PLANNING_ESTIMATE_LABEL}: local CPU bi-encoder (approx. ~600 MB RAM class); weaker on English/mixed queries",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "free_local_operation": True,
                },
                {
                    "candidate_id": "BAAI/bge-m3",
                    "family": "BGE-M3 multilingual dense+sparse (568M params, 1024d)",
                    "vietnamese_support": "High-accuracy Vietnamese + cross-lingual retrieval",
                    "cpu_latency_and_memory": f"{PLANNING_ESTIMATE_LABEL}: heavier model class (approx. ~2.2 GB RAM class); optional for 300-1,650 docs",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "free_local_operation": True,
                },
            ],
            "hybrid_retrieval": {
                "methods": [
                    "Reciprocal Rank Fusion (RRF, k=60) combining BM25 + Dense top-k",
                    "Min-max / z-score normalized linear score fusion (alpha * dense + (1 - alpha) * bm25)",
                ],
                "recommendation": "Evaluate RRF and convex score fusion over BM25 + top dense bi-encoder; particularly effective for Vietnamese queries mixing exact POI/food terms with semantic aspect intent.",
                "measurement_status": PLANNING_ESTIMATE_LABEL,
            },
            "reranker_evaluation": {
                "justified_at_target_scale": "OPTIONAL_FOR_ABLATION",
                "candidates": [
                    "BAAI/bge-reranker-v2-m3 (or lightweight multilingual MiniLM cross-encoder such as cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)"
                ],
                "analysis": (
                    "For a 300-1,650 review corpus with poi_id/city metadata pre-filtering, bi-encoder + BM25 hybrid "
                    "already retrieves from a small candidate pool (5-15 reviews per POI). A lightweight multilingual "
                    "cross-encoder top-20 -> top-5 reranker is optional for scientific ablation in W07."
                ),
                "measurement_status": PLANNING_ESTIMATE_LABEL,
            },
            "index_and_vector_store_comparison": [
                {
                    "option": "Local in-memory / flat index (FAISS IndexFlatIP / NumPy exact cosine + rank_bm25)",
                    "retrieval_quality": "100% exact nearest-neighbor recall (no ANN quantization loss)",
                    "vietnamese_support": "Model-determined; full Unicode metadata filtering in Python",
                    "latency": f"{PLANNING_ESTIMATE_LABEL}: sub-10ms class for <=2,000 vectors on local CPU",
                    "memory": f"{PLANNING_ESTIMATE_LABEL}: <50 MB class for <=2,000 x 768d float32 vectors",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "installation_complexity": "Minimal (Pure Python / faiss-cpu)",
                    "deployment_complexity": "Zero daemon / zero server required",
                    "free_local_operation": True,
                    "reproducibility": "100% deterministic offline artifact snapshots",
                    "verdict": "RECOMMENDED_FOR_W07_SCIENTIFIC_BENCHMARK",
                },
                {
                    "option": "PostgreSQL + pgvector (already integrated in apps/backend/prisma/schema.prisma & apps/ai-service/app/rag/retriever.py)",
                    "retrieval_quality": "Exact or HNSW vector search + SQL relational filtering by place_id/city",
                    "vietnamese_support": "Full UTF-8 + SQL metadata joins with canonical places",
                    "latency": f"{PLANNING_ESTIMATE_LABEL}: local DB query class",
                    "memory": f"{PLANNING_ESTIMATE_LABEL}: managed by existing local PostgreSQL container",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "installation_complexity": "Already present in repository stack",
                    "deployment_complexity": "Requires running PostgreSQL service (blocked in mandatory stateless CI)",
                    "free_local_operation": True,
                    "reproducibility": "High when seeded from frozen JSON/embeddings",
                    "verdict": "RECOMMENDED_FOR_APPLICATION_INTEGRATION_AFTER_OFFLINE_BENCHMARK",
                },
                {
                    "option": "Qdrant (local or server)",
                    "retrieval_quality": "Equivalent to exact/HNSW vector search",
                    "vietnamese_support": "UTF-8 payload filtering",
                    "latency": f"{PLANNING_ESTIMATE_LABEL}: local vector DB query class",
                    "memory": f"{PLANNING_ESTIMATE_LABEL}: additional container/process overhead",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "installation_complexity": "Requires adding new client & server dependency not currently in stack",
                    "deployment_complexity": "Unnecessary extra infrastructure for <10,000 reviews when FAISS/NumPy (offline benchmark) and pgvector (app stack) already cover all needs",
                    "free_local_operation": True,
                    "reproducibility": "No advantage over local FAISS/NumPy at this corpus scale",
                    "verdict": "NOT_NEEDED",
                },
            ],
        },
        "section_16_infrastructure_readiness": {
            "measurement_hygiene_label": PLANNING_ESTIMATE_LABEL,
            "items": {
                "cpu_only": {
                    "classification": "REQUIRED",
                    "purpose": "Run offline data pipelines, BM25, compact multilingual bi-encoders (<=135M params), FAISS/NumPy exact search, and deterministic evaluation tests.",
                    "minimum_requirement": "Standard developer laptop CPU (4+ cores, 8-16 GB RAM)",
                    "free_alternative": "Already available locally and in GitHub Actions CI",
                    "approximate_workload": f"{PLANNING_ESTIMATE_LABEL}: batch encoding 300-1,650 short reviews with compact bi-encoder on CPU",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": False,
                },
                "local_gpu": {
                    "classification": "OPTIONAL",
                    "purpose": "Accelerate larger embedding/reranker ablations (e.g., BGE-M3) if tested.",
                    "minimum_requirement": "None required now; CPU or free Colab T4 is sufficient",
                    "free_alternative": "CPU (for small/base models) or free Google Colab T4",
                    "approximate_workload": f"{PLANNING_ESTIMATE_LABEL}: optional batch embedding export",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "google_colab": {
                    "classification": "OPTIONAL",
                    "purpose": "Free T4 GPU fallback if benchmarking heavier 560M+ parameter bi-encoders/rerankers and exporting frozen embeddings.",
                    "minimum_requirement": "Standard free Google account",
                    "free_alternative": "Free Google Colab tier or local CPU with compact models",
                    "approximate_workload": f"{PLANNING_ESTIMATE_LABEL}: one-time batch embedding export if needed",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "paid_gpu": {
                    "classification": "NOT_NEEDED",
                    "purpose": "None for W07 corpus scale (300-1,650 reviews).",
                    "minimum_requirement": "N/A",
                    "free_alternative": "Local CPU / free Google Colab",
                    "approximate_workload": "0",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "vps": {
                    "classification": "NOT_NEEDED",
                    "purpose": "W07 retrieval evaluation and offline benchmarking run 100% locally.",
                    "minimum_requirement": "N/A",
                    "free_alternative": "Local workstation",
                    "approximate_workload": "0",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "vector_db_server": {
                    "classification": "NOT_NEEDED",
                    "purpose": "In-memory FAISS/NumPy handles offline W07 scientific benchmarking; existing local PostgreSQL/pgvector handles app integration.",
                    "minimum_requirement": "N/A",
                    "free_alternative": "Local FAISS / NumPy + existing pgvector schema",
                    "approximate_workload": "0",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "redis": {
                    "classification": "NOT_NEEDED",
                    "purpose": "Not needed for W07 review corpus curation or offline retrieval benchmarking.",
                    "minimum_requirement": "N/A",
                    "free_alternative": "Local disk JSON/NPZ cache",
                    "approximate_workload": "0",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "paid_embedding_api": {
                    "classification": "NOT_NEEDED",
                    "purpose": "Open-weight multilingual/Vietnamese sentence-transformers run locally for free with higher reproducibility.",
                    "minimum_requirement": "N/A",
                    "free_alternative": "Open-weight HuggingFace models (multilingual-e5-small, paraphrase-multilingual-MiniLM-L12-v2, vietnamese-bi-encoder)",
                    "approximate_workload": "0",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
                "llm_api": {
                    "classification": "OPTIONAL",
                    "purpose": "Not needed now (W07-0 and retrieval benchmarking are 100% offline/extractive). Only optional in a later synthesis stage if generative review summarization is evaluated alongside extractive aspect synthesis.",
                    "minimum_requirement": "None now (NEW_LLM_PROVIDER_CALLS = 0)",
                    "free_alternative": "Deterministic extractive aspect & snippet synthesis from retrieved top-k reviews",
                    "approximate_workload": "0 calls now",
                    "measurement_status": PLANNING_ESTIMATE_LABEL,
                    "can_wait": True,
                },
            },
        },
        "section_17_api_external_ai_firewall": {
            "NEW_LLM_PROVIDER_CALLS": 0,
            "NEW_REVIEW_DATA_ACQUIRED": 0,
            "gemini_calls": 0,
            "openai_calls": 0,
            "claude_calls": 0,
            "google_places_calls": 0,
            "tripadvisor_calls": 0,
            "external_embedding_api_calls": 0,
            "paid_reranker_api_calls": 0,
            "crawler_execution_count": 0,
            "dataset_download_count": 0,
            "secrets_inspected_or_printed": False,
        },
        "section_19_decision_categories": {
            "CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07": False,
            "ADDITIONAL_REVIEW_DATA_REQUIRED": True,
            "HUMAN_LABELING_REQUIRED": True,
            "GPU_REQUIRED_NOW": False,
            "SERVER_REQUIRED_NOW": False,
            "VECTOR_DB_SERVER_REQUIRED_NOW": False,
            "PAID_EMBEDDING_API_REQUIRED": False,
            "LLM_API_REQUIRED_NOW": False,
        },
        "section_20_review_data_acquisition_specification": {
            "crawling_performed_in_w07_0": False,
            "NEW_REVIEW_DATA_ACQUIRED": 0,
            "api_feasibility_corrections": {
                "google_places": {
                    "GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE": GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE,
                    "GOOGLE_PLACES_OFFLINE_CORPUS_ROLE": GOOGLE_PLACES_OFFLINE_CORPUS_ROLE,
                    "can_satisfy_10_to_15_reviews_per_poi_by_itself": False,
                    "approved_as_primary_frozen_w07_corpus": False,
                    "policy_and_technical_reasons": [
                        "Google Places API returns at most 5 reviews per place (GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5) and therefore cannot satisfy a 10-15 reviews/POI target by itself.",
                        "Google Maps Platform Places policies restrict pre-fetching, caching, and persistent offline storage of Places content except documented exceptions such as place IDs.",
                    ],
                    "permitted_later_consideration": [
                        "live/runtime enrichment",
                        "UI display",
                        "place mapping",
                    ],
                },
                "tripadvisor": {
                    "TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE": TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE,
                    "approved_as_primary_frozen_w07_corpus": False,
                    "policy_and_technical_reasons": [
                        "Current consumer Content API exposes only a small number of reviews per location.",
                        "Tripadvisor states its Content API is intended for consumer-facing B2C applications.",
                        "Academic research access is not supported under normal Content API eligibility.",
                    ],
                },
            },
            "acquisition_target_tiers": {
                "scientific_minimum": {
                    "tier_name": "Scientific Minimum",
                    "role": "Minimum dataset allowed to begin W07 retrieval science",
                    "min_canonical_pois": 60,
                    "city_balance": "Balanced across all 3 thesis cities (~20 POIs/city: Hà Nội ~20, Đà Nẵng ~20, Hạ Long ~20)",
                    "min_reviews_per_poi": 5,
                    "min_total_usable_reviews": 300,
                },
                "preferred": {
                    "tier_name": "Preferred",
                    "role": "Recommended balanced benchmark target",
                    "target_canonical_pois_range": "75-100",
                    "city_and_category_balance": "Approximately balanced across Hà Nội, Đà Nẵng, Hạ Long and core POI categories",
                    "target_reviews_per_poi_range": "8-12",
                    "target_total_usable_reviews_range": "600-1,200",
                },
                "stretch": {
                    "tier_name": "Stretch",
                    "role": "Stretch target only — explicitly NOT a prerequisite for starting W07",
                    "is_prerequisite_for_starting_w07": False,
                    "target_canonical_pois_approx": 110,
                    "target_reviews_per_poi_range": "10-15",
                    "target_total_usable_reviews_range": "1,100-1,650",
                },
            },
            "candidate_source_classes_ranked": [
                {
                    "tier": "Tier A",
                    "classification": "PREFERRED_PRIMARY_SCIENTIFIC_CORPUS",
                    "description": (
                        "Public/research-permitted datasets containing review text, place/business identity, "
                        "city/address and preferably coordinates, provenance, usage/license permitting research, "
                        "and enough metadata for deterministic or audited mapping to GoMate canonical POIs."
                    ),
                },
                {
                    "tier": "Tier B",
                    "classification": "ACCEPTABLE_PRIMARY_SCIENTIFIC_CORPUS",
                    "description": (
                        "Owner-curated or research-collected reviews where reuse rights are clear, provenance "
                        "is recorded, source reference is retained, and exact canonical POI mapping is possible."
                    ),
                },
                {
                    "tier": "Tier C",
                    "classification": "RUNTIME_ENRICHMENT_ONLY_NOT_PERSISTENT_FROZEN_CORPUS",
                    "description": (
                        "Official APIs usable for runtime enrichment but unsuitable as a persistent frozen "
                        "research corpus under standard terms. Google Places belongs here unless storage/research "
                        "rights are independently established."
                    ),
                },
                {
                    "tier": "Excluded",
                    "classification": "FORBIDDEN_FOR_PRIMARY_POI_RAG_AUTHORITY",
                    "excluded_categories": [
                        "synthetic review generation for scientific evaluation",
                        "unprovenanced scraped text",
                        "datasets with no review text (e.g., ViHoRec ratings-only)",
                        "anonymous text-only sentiment corpora as the primary POI-grounded RAG corpus",
                    ],
                },
            ],
            "candidate_dataset_feasibility_queue": [
                {
                    "candidate_slot": "Candidate A",
                    "dataset_id": "ThanThoai9x/vietnamese-food-images",
                    "status": "PROMISING_BUT_NOT_YET_APPROVED",
                    "reported_unique_places_approx": 1989,
                    "indicated_public_metadata_fields": [
                        "place_name",
                        "address",
                        "lat",
                        "lng",
                        "review_id",
                        "review_rating",
                        "text",
                        "review_url",
                        "crawled_at",
                    ],
                    "required_next_checks": [
                        "gated access",
                        "exact license/reuse terms",
                        "Google-origin implications",
                        "Hà Nội coverage",
                        "Đà Nẵng coverage",
                        "Hạ Long coverage",
                        "number of text reviews",
                        "number of unique POIs",
                        "coordinate mapping rate to Freeze v2",
                    ],
                    "acquired_or_downloaded_in_w07_0": False,
                },
                {
                    "candidate_slot": "Candidate B",
                    "dataset_id": "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
                    "status": "AUXILIARY_TEXT_DATA_ONLY",
                    "reason": (
                        "Large Vietnamese restaurant-review corpus, but currently exposed fields do not provide "
                        "sufficient POI identity/location metadata for canonical POI RAG."
                    ),
                    "potential_use": [
                        "linguistic robustness",
                        "sentiment auxiliary experiment",
                    ],
                    "usable_for_authoritative_poi_grounded_retrieval": False,
                    "acquired_or_downloaded_in_w07_0": False,
                },
                {
                    "candidate_slot": "Candidate C",
                    "dataset_id": "VLSP2018-ABSA-Restaurant",
                    "status": "AUXILIARY_ABSA_DATASET",
                    "potential_use": [
                        "aspect extraction",
                        "sentiment evaluation",
                        "query/aspect vocabulary development",
                    ],
                    "usable_for_authoritative_poi_grounded_retrieval": False,
                    "restriction_note": (
                        "Do not use as canonical POI review corpus unless deterministic POI identity unexpectedly exists."
                    ),
                    "acquired_or_downloaded_in_w07_0": False,
                },
            ],
            "canonical_mapping_requirements": {
                "required_mapping_support": [
                    "EXACT_MAPPING",
                    "AUDITED_HIGH_CONFIDENCE_GEO_ENTITY_RESOLUTION",
                ],
                "preferred_mapping_evidence_hierarchy": [
                    "1. exact upstream POI ID (e.g., OSM node/way/relation ID or Overture GERS ID)",
                    "2. coordinates + normalized name + city/address",
                    "3. manual verification for ambiguous cases",
                ],
                "name_only_automatic_linking_forbidden": True,
                "required_canonical_foreign_key": "poi_id from data/curated/gomate_places_freeze_v2.json on every final review row",
            },
            "required_primary_corpus_schema_fields": SECTION_8_TARGET_CORPUS_SCHEMA_FIELDS,
            "do_not_fabricate_missing_upstream_fields": True,
            "human_labeling_specification_after_corpus_freeze": {
                "query_count": "40-60 frozen evaluation queries stratified across Hà Nội, Đà Nẵng, Hạ Long and all 11 query dimensions",
                "labeling_protocol": "Graded relevance (0=irrelevant, 1=partially relevant, 2=highly relevant) over pooled top-k candidates from BM25 + Dense retrievers",
            },
        },
    }

    payload["artifact_sha256"] = compute_internal_sha256(payload)
    return payload


def render_w07_audit_markdown(payload: dict[str, Any]) -> str:
    s3 = payload["section_3_repository_data_sources"]
    s4 = payload["section_4_poi_authority"]
    s5 = payload["section_5_review_corpus_inventory"]
    s6 = payload["section_6_review_field_quality"]
    s7 = payload["section_7_text_quality_audit"]
    s8 = payload["section_8_language_audit"]
    s9 = payload["section_9_rating_audit"]
    s12 = payload["section_12_synthetic_data_firewall"]
    s14 = payload["section_14_w07_evaluation_feasibility"]
    s15 = payload["section_15_technology_decision_matrix"]
    s16 = payload["section_16_infrastructure_readiness"]["items"]
    s17 = payload["section_17_api_external_ai_firewall"]
    s19 = payload["section_19_decision_categories"]
    s20 = payload["section_20_review_data_acquisition_specification"]

    vh = s5["vihorec_rating_interactions"]
    cur = s5["quarantined_synthetic_reviews_curated"]
    cur_text = s7["quarantined_synthetic_reviews_curated_9_rows"]
    api_corr = s20["api_feasibility_corrections"]
    tiers = s20["acquisition_target_tiers"]

    lines = [
        "# W07-0 — Data + RAG Readiness Audit Report (Corrective 01)",
        "",
        "## 0. Gate & Lineage Metadata",
        "",
        f"- **Task ID:** `{payload['task_id']}`",
        f"- **Previous Gate:** `{payload['previous_gate']}`",
        f"- **Authoritative Base Commit:** `develop@{payload['authoritative_base_commit']}`",
        f"- **W06 Closure Status:** `{payload['w06_status']}`",
        f"- **Next Gate:** `{payload['next_gate']}`",
        f"- **JSON Artifact Internal SHA256:** `{payload['artifact_sha256']}`",
        "",
        "---",
        "",
        "## 1. Exact Data Inventory (Section 3 — Preserved Unchanged)",
        "",
        f"- **Real provenanced review text rows in repository:** `{s3['summary']['real_provenanced_review_text_rows']}`",
        f"- **Quarantined synthetic review text rows (`vietnam_travel_reviews.json` / `reviews_curated.json`):** `{s3['summary']['synthetic_review_text_rows']}`",
        f"- **Mock tool template strings (`apps/ai-service/app/tools/search_reviews.py`):** `{s3['summary']['stub_template_review_strings']}`",
        f"- **Real rating-only hotel interaction rows with ZERO review text (`ViHoRec`):** `{s3['summary']['rating_only_interaction_rows_no_text']}`",
        f"- **Non-review RAG documents in Freeze v2 (`464` Wikivoyage English chunks + `759` OSM place docs):** `{s3['summary']['non_review_rag_documents_in_freeze_v2']}`",
        "",
        "| Source ID | Storage Status | Classification | Provenance Category | Rows | Review Text | Ratings |",
        "|---|---|---|---|---:|---|---|",
    ]
    for src in s3["sources"]:
        lines.append(
            f"| `{src['source_id']}` | `{src['storage_status']}` | `{src['classification']}` | {src['provenance_category']} | `{src['row_count']}` | `{src['has_review_text']}` | `{src['has_ratings']}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. City & Canonical POI Authority Coverage (Section 4)",
            "",
            f"- **Total Canonical Places in DB State (`dataset-freeze-v2.yaml`):** `{s4['total_canonical_pois_db']}`",
            f"- **Verified OSM Places (`gomate_places_freeze_v2.json`):** `{s4['verified_pois_freeze_v2']}` (`100%` have `rating = null` and `review_count = 0`)",
            f"- **REC-A Core 3-City Verified POIs:** `{s4['core_pois_rec_a_v2']}`",
            f"  - **Hà Nội (`ha-noi`):** `{s4['counts_by_core_city_verified_v2']['ha_noi']}`",
            f"  - **Đà Nẵng (`da-nang`):** `{s4['counts_by_core_city_verified_v2']['da_nang_total_verified']}` total verified (`{s4['counts_by_core_city_verified_v2']['da_nang_rec_a_core']}` REC-A core + `{s4['counts_by_core_city_verified_v2']['da_nang_outside_core']}` outside core)",
            f"  - **Hạ Long (`ha-long`):** `{s4['counts_by_core_city_verified_v2']['ha_long']}`",
            f"- **Secondary Verified POIs (`137`):** Hội An (`{s4['counts_by_secondary_city_verified_v2']['hoi_an']}`), Huế (`{s4['counts_by_secondary_city_verified_v2']['hue']}`), Nha Trang (`{s4['counts_by_secondary_city_verified_v2']['nha_trang']}`), Đà Nẵng outside core (`4`)",
            f"- **Legacy `places_canonical.json` (`108` rows):** `{s4['legacy_places_canonical_v1_sourced']}` sourced (`{s4['legacy_places_v1_overlap_with_freeze_v2']}` overlap with Freeze v2) + `{s4['legacy_places_canonical_v1_unsourced']}` unsourced legacy rows (`sources = []`)",
            f"- **Canonical ID Format:** `{s4['canonical_id_format']}`",
            f"- **Upstream Source IDs in Freeze v2:** OSM `{s4['available_source_ids']['osm']['places_count']}/759` (`100.0%`), Overture `{s4['available_source_ids']['overture']['places_count']}/759` (`{s4['available_source_ids']['overture']['coverage_pct_of_verified_v2']}%`)",
            "",
            "---",
            "",
            "## 3. POI Mapping Coverage & Review Corpus Inventory (Sections 4 & 5)",
            "",
            "### 3.1 Review-to-POI Mapping Against Authoritative `gomate_places_freeze_v2.json` (`759` Verified POIs)",
            "",
            "| Dataset | Total Rows | `EXACT_MAPPING` (by ID) | `HEURISTIC_MAPPING` (normalized city+name) | `UNMAPPED` (by ID / after heuristic) | Audit Finding |",
            "|---|---:|---:|---:|---:|---|",
            "| **Real Review Text Corpus** | `0` | `0` | `0` | `0` | Zero real review text exists in repository. |",
            f"| **Synthetic `reviews_curated.json`** | `9` | `0` | `{cur['unique_pois_heuristic_name_match_in_freeze_v2']}` | `9` by ID (`{9 - cur['unique_pois_heuristic_name_match_in_freeze_v2']}` after heuristic) | All 8 `place_id` values in `reviews_curated.json` point to unsourced (`sources=[]`) rows in legacy `places_canonical.json` excluded from Freeze v2. |",
            f"| **`ViHoRec` (`560` hotels / `17,911` ratings)** | `17,911` (`560` hotels) | `0` hotels (`0` rows) | `{vh['canonical_poi_mapping']['HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_HOTELS']}` hotels (`{vh['canonical_poi_mapping']['HEURISTIC_MAPPING_EXACT_NORMALIZED_NAME_CITY_INTERACTIONS']}` rows) | `560` hotels by ID (`558` hotels / `17,875` rows after exact name+city heuristic) | Opaque `H0000..H0559` IDs with no coordinates/OSM IDs and `0%` review text. |",
            "",
            "### 3.2 City Coverage & Reviews-per-POI Statistics (Section 5)",
            "",
            "- **Authoritative Real Review Text Coverage Across `759` Freeze v2 POIs (`622` Core POIs):**",
            "  - Hà Nội: `0` reviews | Đà Nẵng: `0` reviews | Hạ Long: `0` reviews",
            "  - Median / p25 / p50 / p75 / p90 reviews per POI: `0.0 / 0.0 / 0.0 / 0.0 / 0.0`",
            "  - POIs with `0` reviews: `759/759` (`622/622` core); `1–4` reviews: `0`; `5–9` reviews: `0`; `10+` reviews: `0`; `20+` reviews: `0`.",
            "- **Quarantined Synthetic Fixture (`reviews_curated.json`, `9` rows):**",
            f"  - Đà Nẵng: `{cur['reviews_by_city'].get('Đà Nẵng', 0)}`, Hà Nội: `{cur['reviews_by_city'].get('Hà Nội', 0)}`, Hạ Long: `{cur['core_three_city_coverage']['Hạ Long']}`, Hội An: `{cur['reviews_by_city'].get('Hội An', 0)}`, Huế: `{cur['reviews_by_city'].get('Huế', 0)}`, Vùng sâu: `{cur['reviews_by_city'].get('Vùng sâu', 0)}`.",
            "- **`ViHoRec` Rating-Only Interactions (`17,911` rows across `560` hotels, `0` review text):**",
            f"  - Hà Nội: `0` hotels (`0` rows) | Đà Nẵng: `{vh['core_three_city_coverage']['danang_hotels']}` hotels (`{vh['core_three_city_coverage']['danang_interactions']}` rows) | Hạ Long: `0` hotels (`0` rows).",
            f"  - Interactions per hotel (`560` hotels): min=`{vh['interactions_per_hotel_stats']['min_reviews_per_poi']}`, p25=`{vh['interactions_per_hotel_stats']['p25_reviews_per_poi']}`, median/p50=`{vh['interactions_per_hotel_stats']['p50_reviews_per_poi']}`, p75=`{vh['interactions_per_hotel_stats']['p75_reviews_per_poi']}`, p90=`{vh['interactions_per_hotel_stats']['p90_reviews_per_poi']}`, max=`{vh['interactions_per_hotel_stats']['max_reviews_per_poi']}` (`0` with 0 ratings, `103` with 1–4, `104` with 5–9, `353` with 10+, `248` with 20+).",
            "",
            "---",
            "",
            "## 4. Review Field, Text, Language, Rating & Temporal Quality (Sections 6–10)",
            "",
            "### 4.1 Field Missingness Percentage (Section 6)",
            "",
            "| Field | `vietnam_travel_reviews.json` (`n=9`) | `reviews_curated.json` (`n=9`) | `vihorec/interactions.csv` (`n=17,911`) | `search_reviews.py` stub (`n=2`) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for field in SECTION_6_REQUIRED_FIELDS:
        m_raw = s6["sources"]["vietnam_travel_reviews_raw_json"]["missingness_pct_by_field"][field]
        m_cur = s6["sources"]["reviews_curated_json"]["missingness_pct_by_field"][field]
        m_vh = s6["sources"]["vihorec_interactions_csv"]["missingness_pct_by_field"][field]
        m_stub = s6["sources"]["ai_service_search_reviews_stub"]["missingness_pct_by_field"][field]
        lines.append(f"| `{field}` | `{m_raw:.2f}%` | `{m_cur:.2f}%` | `{m_vh:.2f}%` | `{m_stub:.2f}%` |")

    lines.extend(
        [
            "",
            "### 4.2 Text, Language, Rating & Temporal Quality Summary (Sections 7–10)",
            "",
            f"- **Text Quality (`reviews_curated.json`, `9` synthetic rows):** empty=`{cur_text['empty_review_count']}`, whitespace-only=`{cur_text['whitespace_only_count']}`, `<20` chars=`{cur_text['very_short_reviews_lt_20_chars']}`, `>2000` chars=`{cur_text['excessively_long_reviews_gt_2000_chars']}`, exact duplicates=`{cur_text['exact_duplicate_text_rows']}`, normalized duplicates=`{cur_text['normalized_duplicate_text_rows']}`, near-duplicates=`{cur_text['near_duplicate_pairs_jaccard_ge_0_80']}`, HTML/Unicode issues=`0`. Char length: min=`{cur_text['char_length_distribution']['min']}`, p25=`{cur_text['char_length_distribution']['p25']}`, p50=`{cur_text['char_length_distribution']['p50']}`, p75=`{cur_text['char_length_distribution']['p75']}`, p90=`{cur_text['char_length_distribution']['p90']}`, max=`{cur_text['char_length_distribution']['max']}` (word length p50=`{cur_text['word_length_distribution']['p50']}`).",
            f"- **Language Distribution (deterministic offline):** `reviews_curated.json`: Vietnamese=`{s8['quarantined_synthetic_reviews_curated_9_rows']['vi']}`, English=`0`, mixed=`0`, unknown=`0`; `search_reviews.py` stub: English=`2`; Wikivoyage non-review guide chunks: English=`464`.",
            f"- **Rating Quality & Scale Incompatibility:** `gomate_places_freeze_v2.json` has `100%` null ratings (`759/759`); synthetic `reviews_curated.json` uses a `1.0–5.0` scale (mean=`{s9['quarantined_synthetic_reviews_curated_9_rows']['mean']}`, median=`{s9['quarantined_synthetic_reviews_curated_9_rows']['median']}`); `ViHoRec` uses a `1.0–10.0` OTA hotel scale (mean=`{vh['rating_audit']['mean']}`, median=`{vh['rating_audit']['median']}`, missing=`0`, invalid=`0`). Rating scales differ (`scales_differ_between_sources = true`); no normalization performed in W07-0.",
            f"- **Temporal Audit:** `reviews_curated.json` is `100.0%` missing dates; `ViHoRec` spans `{vh['temporal_audit']['oldest_date']}` to `{vh['temporal_audit']['newest_date']}` (`0%` missing, `0` invalid/future dates) but has `0%` review text. Recency-aware review-text retrieval is **not possible** on current data.",
            "",
            "---",
            "",
            "## 5. Provenance & Synthetic Data Firewall (Sections 11 & 12)",
            "",
            f"- **`REAL_REVIEW_DATA` (text reviews):** `{s12['REAL_REVIEW_DATA']['text_review_rows']}` rows (`ViHoRec` has `{s12['REAL_REVIEW_DATA']['rating_only_interaction_rows_no_text']}` real rating-only rows with `0` text).",
            f"- **`SYNTHETIC_REVIEW_DATA`:** `{s12['SYNTHETIC_REVIEW_DATA']['text_review_rows']}` rows in `vietnam_travel_reviews.json` / `reviews_normalized.json` / `reviews_curated.json` + `{s12['SYNTHETIC_REVIEW_DATA']['tool_stub_template_rows']}` stub strings in `search_reviews.py` + `{s12['SYNTHETIC_REVIEW_DATA']['synthetic_preference_personas']}` synthetic user preference profiles (`seed=42`). Quarantined by `data/manifests/review-provenance.json` (`UNVERIFIED_SYNTHETIC`).",
            f"- **`UNKNOWN_PROVENANCE`:** `{s12['UNKNOWN_PROVENANCE']['text_review_rows']}` review rows (`123` legacy seed places in DB / `11` unsourced rows in `places_canonical.json` excluded from Freeze v2).",
            "",
            "---",
            "",
            "## 6. Gaps & W07 RAG Readiness Status (Sections 13 & 14)",
            "",
            f"- **`RAG_READINESS_STATUS`:** `{s14['RAG_READINESS_STATUS']}`",
            "- **Primary Gaps:**",
            "  1. `0` real provenanced review text records exist across all `759` verified OSM POIs (`622` core POIs in Hà Nội, Đà Nẵng, Hạ Long).",
            "  2. Hạ Long has `0` reviews even in the synthetic test fixture and `0` hotels in `ViHoRec`.",
            "  3. `40–60` multi-aspect evaluation queries and human relevance judgments cannot be constructed from `0` real reviews.",
            "- **Recommended Retrieval Unit (Section 13):** **`one review = one retrieval unit`** (`one_review_equals_one_retrieval_unit`), preserving `review_id`, `poi_id`, `rating`, `created_at`, and aspect sentiment without fragmenting short reviews.",
            "",
            "---",
            "",
            "## 7. Proposed Retrieval Architecture & Technology Decision Matrix (Section 15)",
            "",
            f"- **Measurement Hygiene (`{s15['measurement_hygiene_label']}`):** {s15['measurement_hygiene_note']}",
            f"- **Winner Frozen in W07-0:** `{s15['winner_frozen_in_w07_0']}` (`{s15['candidate_status']}`)",
            f"- **Lexical Baseline:** `{s15['lexical_baseline']['method']}` (`{s15['lexical_baseline']['measurement_status']}`)",
            "- **Dense Multilingual/Vietnamese Provisional Shortlist (no large models downloaded in W07-0):**",
        ]
    )
    for cand in s15["dense_retrieval_candidate_families"]:
        lines.append(
            f"  - `{cand['candidate_id']}` — {cand['family']} ({cand['vietnamese_support']}; `{cand['cpu_latency_and_memory']}`)"
        )
    lines.extend(
        [
            f"- **Hybrid Retrieval:** `{s15['hybrid_retrieval']['recommendation']}` (`{s15['hybrid_retrieval']['measurement_status']}`)",
            f"- **Reranker Assessment:** `{s15['reranker_evaluation']['justified_at_target_scale']}` (`{s15['reranker_evaluation']['measurement_status']}`) — {s15['reranker_evaluation']['analysis']}",
            "- **Index / Vector Store Recommendation:**",
            f"  - **Offline Scientific Benchmark:** Local in-memory `FAISS IndexFlatIP` / exact NumPy cosine + `rank_bm25` (`{PLANNING_ESTIMATE_LABEL}`, 100% exact recall, zero server overhead, deterministic artifact hashes).",
            f"  - **Application Integration:** Existing `PostgreSQL + pgvector` (`documents` table in `schema.prisma`; `{PLANNING_ESTIMATE_LABEL}`); `Qdrant` is `NOT_NEEDED`.",
            "",
            "---",
            "",
            "## 8. Infrastructure Readiness & Decision Categories (Sections 16, 17 & 19)",
            "",
            "| Infrastructure Item | Classification | Measurement Hygiene | Purpose / Notes |",
            "|---|---|---|---|",
        ]
    )
    for k, item in s16.items():
        lines.append(
            f"| `{k}` | `{item['classification']}` | `{item['measurement_status']}` | {item['purpose']} |"
        )

    lines.extend(
        [
            "",
            "### Explicit Boolean Decision Flags (Section 19) & API / Acquisition Firewall (Section 17)",
            "",
            f"- `CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07 = {str(s19['CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07']).lower()}`",
            f"- `ADDITIONAL_REVIEW_DATA_REQUIRED = {str(s19['ADDITIONAL_REVIEW_DATA_REQUIRED']).lower()}`",
            f"- `HUMAN_LABELING_REQUIRED = {str(s19['HUMAN_LABELING_REQUIRED']).lower()}`",
            f"- `GPU_REQUIRED_NOW = {str(s19['GPU_REQUIRED_NOW']).lower()}`",
            f"- `SERVER_REQUIRED_NOW = {str(s19['SERVER_REQUIRED_NOW']).lower()}`",
            f"- `VECTOR_DB_SERVER_REQUIRED_NOW = {str(s19['VECTOR_DB_SERVER_REQUIRED_NOW']).lower()}`",
            f"- `PAID_EMBEDDING_API_REQUIRED = {str(s19['PAID_EMBEDDING_API_REQUIRED']).lower()}`",
            f"- `LLM_API_REQUIRED_NOW = {str(s19['LLM_API_REQUIRED_NOW']).lower()}`",
            f"- `NEW_LLM_PROVIDER_CALLS = {s17['NEW_LLM_PROVIDER_CALLS']}`",
            f"- `NEW_REVIEW_DATA_ACQUIRED = {s17['NEW_REVIEW_DATA_ACQUIRED']}`",
            "",
            "---",
            "",
            "## 9. Corrected Review Data Acquisition Specification & Feasibility Queue (Section 20 — Corrective 01)",
            "",
            "### 9.1 Official API Feasibility Corrections (Sections 2 & 3 of Corrective 01)",
            "",
            f"- **Google Places API:**",
            f"  - `GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = {api_corr['google_places']['GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE']}` (cannot satisfy a `10–15` reviews/POI target by itself).",
            f"  - `GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = {api_corr['google_places']['GOOGLE_PLACES_OFFLINE_CORPUS_ROLE']}` (Google Maps Platform Places policies restrict pre-fetching/caching/storage of Places content except documented exceptions such as place IDs; may be considered later for live/runtime enrichment, UI display, and place mapping, but must NOT automatically become the frozen scientific W07 corpus).",
            f"- **Tripadvisor Content API:**",
            f"  - `TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = {api_corr['tripadvisor']['TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE']}` (exposes only a small number of reviews/location, intended for consumer-facing B2C apps, and academic research access is not supported under normal Content API eligibility; excluded as primary W07 scientific review-corpus acquisition plan).",
            "",
            "### 9.2 Three-Tier Corpus Acquisition Targets (Section 4 of Corrective 01)",
            "",
            "| Tier | Canonical POIs | City Balance | Reviews / POI | Total Usable Reviews | Role |",
            "|---|---|---|---|---|---|",
            f"| **Scientific Minimum** | `>= {tiers['scientific_minimum']['min_canonical_pois']}` | {tiers['scientific_minimum']['city_balance']} | `>= {tiers['scientific_minimum']['min_reviews_per_poi']}` | `>= {tiers['scientific_minimum']['min_total_usable_reviews']}` | {tiers['scientific_minimum']['role']} |",
            f"| **Preferred** | `{tiers['preferred']['target_canonical_pois_range']}` | {tiers['preferred']['city_and_category_balance']} | `{tiers['preferred']['target_reviews_per_poi_range']}` | `{tiers['preferred']['target_total_usable_reviews_range']}` | {tiers['preferred']['role']} |",
            f"| **Stretch** | `~{tiers['stretch']['target_canonical_pois_approx']}` | Balanced across 3 core cities | `{tiers['stretch']['target_reviews_per_poi_range']}` | `{tiers['stretch']['target_total_usable_reviews_range']}` | {tiers['stretch']['role']} |",
            "",
            "### 9.3 Ranked Candidate Source Classes (Section 5 of Corrective 01)",
            "",
        ]
    )
    for sc in s20["candidate_source_classes_ranked"]:
        if "description" in sc:
            lines.append(f"- **{sc['tier']} (`{sc['classification']}`):** {sc['description']}")
        else:
            lines.append(
                f"- **{sc['tier']} (`{sc['classification']}`):** {'; '.join(sc['excluded_categories'])}."
            )

    lines.extend(
        [
            "",
            "### 9.4 Candidate Dataset Feasibility Queue (Section 6 of Corrective 01 — Research Candidates Only)",
            "",
            "| Slot | Dataset | Status | Notes / Required Next Checks |",
            "|---|---|---|---|",
        ]
    )
    for cand in s20["candidate_dataset_feasibility_queue"]:
        if "required_next_checks" in cand:
            checks = ", ".join(cand["required_next_checks"])
            fields = ", ".join(cand["indicated_public_metadata_fields"])
            lines.append(
                f"| **{cand['candidate_slot']}** | `{cand['dataset_id']}` | `{cand['status']}` | ~`{cand['reported_unique_places_approx']}` unique places; fields: `{fields}`. Next checks: {checks}. |"
            )
        else:
            reason = cand.get("reason") or cand.get("restriction_note") or ""
            uses = ", ".join(cand.get("potential_use", []))
            lines.append(
                f"| **{cand['candidate_slot']}** | `{cand['dataset_id']}` | `{cand['status']}` | {reason} Potential use: {uses}. |"
            )

    lines.extend(
        [
            "",
            "### 9.5 Canonical POI Mapping Requirements & Target 17-Field Schema (Sections 7 & 8 of Corrective 01)",
            "",
            "- **Mapping Support Required:** `EXACT_MAPPING` or `AUDITED_HIGH_CONFIDENCE_GEO_ENTITY_RESOLUTION`.",
            "- **Preferred Mapping Evidence Hierarchy:** (1) exact upstream POI ID; (2) coordinates + normalized name + city/address; (3) manual verification for ambiguous cases.",
            "- **Strict Rule:** Name-only automatic linking is **forbidden** as scientific authority (`name_only_automatic_linking_forbidden = true`). Every final review row must carry canonical `poi_id` from `data/curated/gomate_places_freeze_v2.json`.",
            f"- **Target 17 Schema Fields:** `{', '.join(s20['required_primary_corpus_schema_fields'])}` (do not fabricate missing upstream fields).",
            "",
        ]
    )
    return "\n".join(lines)


def verify_w07_audit_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    json_path = repo_root / AUDIT_JSON_RELPATH
    md_path = repo_root / AUDIT_MD_RELPATH

    if not json_path.exists():
        raise FileNotFoundError(f"Missing W07 audit JSON artifact: {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing W07 audit Markdown report: {md_path}")

    frozen_payload = json.loads(json_path.read_text(encoding="utf-8"))
    expected_internal_sha = compute_internal_sha256(frozen_payload)
    if frozen_payload.get("artifact_sha256") != expected_internal_sha:
        raise ValueError(
            f"Internal artifact_sha256 mismatch: stored={frozen_payload.get('artifact_sha256')} != computed={expected_internal_sha}"
        )

    recomputed_payload = build_w07_audit_payload(repo_root)
    if frozen_payload != recomputed_payload:
        raise ValueError("Frozen W07 audit JSON differs from recomputed repository state.")

    expected_md = render_w07_audit_markdown(recomputed_payload)
    actual_md = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual_md != expected_md.replace("\r\n", "\n"):
        raise ValueError("Frozen W07 audit Markdown differs from rendered payload.")

    return {
        "status": "PASS",
        "json_path": AUDIT_JSON_RELPATH,
        "json_file_sha256": compute_file_sha256(json_path),
        "json_internal_sha256": frozen_payload["artifact_sha256"],
        "md_path": AUDIT_MD_RELPATH,
        "md_file_sha256": compute_file_sha256(md_path),
        "md_lf_sha256": compute_lf_normalized_sha256(md_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run or verify W07-0 Data + RAG Readiness Audit artifacts."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write/update the JSON and Markdown audit artifacts before verifying.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing JSON and Markdown audit artifacts without modifying files.",
    )
    args = parser.parse_args(argv)

    if args.write and args.verify_only:
        parser.error("Cannot specify both --write and --verify-only.")

    if args.write:
        payload = build_w07_audit_payload(REPO_ROOT)
        json_path = REPO_ROOT / AUDIT_JSON_RELPATH
        md_path = REPO_ROOT / AUDIT_MD_RELPATH
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        md_path.write_text(
            render_w07_audit_markdown(payload),
            encoding="utf-8",
            newline="\n",
        )

    result = verify_w07_audit_artifacts(REPO_ROOT)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
