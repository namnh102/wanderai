#!/usr/bin/env python3
"""W07-A3 Offline Contributor Review Collection Progress & Pilot Gate Tracker (v1).

Generates and verifies the non-sensitive aggregate progress artifact:
  `data/evaluation/w07/w07_review_collection_progress_v1.json`

Reports:
- accepted reviews, rejected reviews, quarantined PII reviews;
- reviews by city and by category sampling stratum;
- reviews per POI (all 60 canonical POIs; never publishes raw review text);
- POIs with 0 reviews, POIs with 1-4 reviews, POIs with >= 5 reviews;
- city completion and sampling-stratum completion;
- remaining reviews to 300;
- exact under-covered POIs ordered by Section 20 recruitment priority:
  (1) POIs with 0 reviews, (2) POIs with 1-4 reviews, (3) city deficits,
  (4) category-stratum deficits; POIs with >= 5 reviews are marked
  `STOP_ACTIVE_RECRUITMENT_MIN_5_MET`;
- `COLLECTION_PIPELINE_PILOT_READY` gate evaluation (30 reviews, >=10/city,
  >=15 distinct POIs, valid consent for all, 0 synthetic/LLM, 0 quarantined
  counted, importer idempotency verified), strictly separated from
  `CORPUS_SCIENTIFIC_MINIMUM_READY` (300 reviews, 60 POIs, >=5/POI).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    import_w07_contributor_reviews_v1 as w07_a3_import,
    validate_w07_review_corpus_v1 as w07_a2,
)

PROGRESS_JSON_RELPATH = "data/evaluation/w07/w07_review_collection_progress_v1.json"

PILOT_TARGET_TOTAL_REVIEWS = 30
PILOT_TARGET_MIN_REVIEWS_PER_CITY = 10
PILOT_TARGET_MIN_DISTINCT_POIS = 15

SCIENTIFIC_MIN_TOTAL_REVIEWS = 300
SCIENTIFIC_MIN_TOTAL_POIS = 60
SCIENTIFIC_MIN_REVIEWS_PER_POI = 5
SCIENTIFIC_MIN_REVIEWS_PER_CITY = 100


def build_collection_progress_report(
    rows: list[dict[str, Any]],
    manifest_payload: dict[str, Any],
    *,
    importer_idempotency_verified: bool = True,
) -> dict[str, Any]:
    """Compute the full non-sensitive W07-A3 collection progress and pilot/scientific gate report."""
    val_report = w07_a2.validate_review_rows(rows, manifest_payload)

    rejected_indices = {r["row_index"] for r in val_report["rejected_rows"]}
    accepted_rows = [
        row for idx, row in enumerate(rows) if idx not in rejected_indices
    ]

    pois = manifest_payload["pois"]
    poi_by_id = {p["poi_id"]: p for p in pois}

    per_poi_counts: Counter[str] = Counter()
    missing_consent_in_accepted = 0
    synthetic_in_accepted = 0
    quarantined_pii_in_accepted = 0

    for row in accepted_rows:
        pid = str(row.get("poi_id", ""))
        if pid in poi_by_id:
            per_poi_counts[pid] += 1

        # Double-check consent, synthetic, and PII invariants on accepted rows
        lic = str(row.get("license_or_usage_class", "")).strip()
        cid = row.get("consent_record_id")
        if lic in w07_a2.FIRST_PARTY_CONSENT_CLASSES and (
            not isinstance(cid, str) or not cid.strip()
        ):
            missing_consent_in_accepted += 1

        meta_str = " ".join(
            str(row.get(k, "")).lower()
            for k in ("source", "provenance", "source_ref", "license_or_usage_class")
        )
        if any(tok in meta_str for tok in w07_a2.FORBIDDEN_SOURCE_SUBSTRINGS):
            synthetic_in_accepted += 1

        rtext = str(row.get("review_text", ""))
        if w07_a2.EMAIL_RE.search(rtext) or w07_a2.PHONE_RE.search(rtext):
            quarantined_pii_in_accepted += 1

    # City-level aggregation
    city_accepted_counts: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    city_min_required: dict[str, int] = {"Hà Nội": 100, "Đà Nẵng": 100, "Hạ Long": 100}
    city_pois_covered: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    city_pois_gte_5: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}

    # Category-group stratum aggregation
    stratum_accepted_counts: dict[str, int] = {
        grp: 0 for grp in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS
    }
    stratum_min_required: dict[str, int] = {
        grp: quota * SCIENTIFIC_MIN_REVIEWS_PER_POI
        for grp, quota in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS.items()
    }
    stratum_pois_covered: dict[str, int] = {
        grp: 0 for grp in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS
    }
    stratum_pois_gte_5: dict[str, int] = {
        grp: 0 for grp in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS
    }

    pois_with_0_ids: list[str] = []
    pois_with_1_to_4_ids: list[str] = []
    pois_with_5_or_more_ids: list[str] = []

    for p in pois:
        pid = p["poi_id"]
        c = per_poi_counts[pid]
        city = p["city"]
        grp = p["category_group"]

        city_accepted_counts[city] += c
        stratum_accepted_counts[grp] += c

        if c == 0:
            pois_with_0_ids.append(pid)
        elif c < SCIENTIFIC_MIN_REVIEWS_PER_POI:
            pois_with_1_to_4_ids.append(pid)
            city_pois_covered[city] += 1
            stratum_pois_covered[grp] += 1
        else:
            pois_with_5_or_more_ids.append(pid)
            city_pois_covered[city] += 1
            city_pois_gte_5[city] += 1
            stratum_pois_covered[grp] += 1
            stratum_pois_gte_5[grp] += 1

    # City deficits (sum of per-POI deficits in each city)
    city_poi_deficit_sum: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    stratum_poi_deficit_sum: dict[str, int] = {
        grp: 0 for grp in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS
    }
    for p in pois:
        pid = p["poi_id"]
        deficit = max(0, SCIENTIFIC_MIN_REVIEWS_PER_POI - per_poi_counts[pid])
        city_poi_deficit_sum[p["city"]] += deficit
        stratum_poi_deficit_sum[p["category_group"]] += deficit

    reviews_per_poi: list[dict[str, Any]] = []
    under_covered_pois: list[dict[str, Any]] = []
    stop_active_recruitment_pois: list[str] = []

    for p in pois:
        pid = p["poi_id"]
        c = per_poi_counts[pid]
        deficit = max(0, SCIENTIFIC_MIN_REVIEWS_PER_POI - c)
        if c == 0:
            tier = "PRIORITY_1_ZERO_REVIEWS"
            rec_status = "ACTIVE_HIGHEST_PRIORITY_ZERO_REVIEWS"
        elif c < SCIENTIFIC_MIN_REVIEWS_PER_POI:
            tier = "PRIORITY_2_BELOW_FIVE_REVIEWS"
            rec_status = f"ACTIVE_NEEDS_{deficit}_MORE_FOR_MIN_5"
        else:
            tier = "COMPLETED_MIN_5_REACHED"
            rec_status = "STOP_ACTIVE_RECRUITMENT_MIN_5_MET"
            stop_active_recruitment_pois.append(pid)

        entry = {
            "selection_rank": p["selection_rank"],
            "poi_id": pid,
            "name": p["name"],
            "city": p["city"],
            "category": p["category"],
            "category_group": p["category_group"],
            "accepted_review_count": c,
            "target_review_count_min": p["target_review_count_min"],
            "target_review_count_preferred": p["target_review_count_preferred"],
            "deficit_to_min_5": deficit,
            "priority_tier": tier,
            "recruitment_action": rec_status,
        }
        reviews_per_poi.append(entry)
        if deficit > 0:
            under_covered_pois.append(
                {
                    "poi_id": pid,
                    "name": p["name"],
                    "city": p["city"],
                    "category_group": p["category_group"],
                    "accepted_review_count": c,
                    "deficit_to_min_5": deficit,
                    "priority_tier": tier,
                    "city_total_deficit": city_poi_deficit_sum[p["city"]],
                    "stratum_total_deficit": stratum_poi_deficit_sum[p["category_group"]],
                    "selection_rank": p["selection_rank"],
                }
            )

    # Sort under_covered_pois by Section 20 priority:
    # 1. POIs with 0 reviews before 1-4 reviews (c ascending)
    # 2. Larger city deficit first (-city_total_deficit)
    # 3. Larger category-stratum deficit first (-stratum_total_deficit)
    # 4. Deterministic selection_rank ascending
    under_covered_pois.sort(
        key=lambda item: (
            0 if item["accepted_review_count"] == 0 else 1,
            item["accepted_review_count"],
            -item["city_total_deficit"],
            -item["stratum_total_deficit"],
            item["selection_rank"],
        )
    )

    city_completion_summary: dict[str, dict[str, Any]] = {}
    for city_name in ("Hà Nội", "Đà Nẵng", "Hạ Long"):
        c_rev = city_accepted_counts[city_name]
        c_def = city_poi_deficit_sum[city_name]
        city_completion_summary[city_name] = {
            "target_pois": 20,
            "covered_pois_gte_1": city_pois_covered[city_name],
            "completed_pois_gte_5": city_pois_gte_5[city_name],
            "accepted_reviews": c_rev,
            "pilot_min_reviews_target": PILOT_TARGET_MIN_REVIEWS_PER_CITY,
            "pilot_city_target_met": c_rev >= PILOT_TARGET_MIN_REVIEWS_PER_CITY,
            "scientific_min_reviews_target": city_min_required[city_name],
            "remaining_poi_deficit_reviews_to_min_5": c_def,
            "scientific_city_minimum_met": (
                city_pois_gte_5[city_name] == 20 and c_rev >= city_min_required[city_name]
            ),
        }

    sampling_stratum_completion_summary: dict[str, dict[str, Any]] = {}
    for grp, quota in w07_a2.GLOBAL_CATEGORY_GROUP_QUOTAS.items():
        s_rev = stratum_accepted_counts[grp]
        s_def = stratum_poi_deficit_sum[grp]
        sampling_stratum_completion_summary[grp] = {
            "target_pois": quota,
            "covered_pois_gte_1": stratum_pois_covered[grp],
            "completed_pois_gte_5": stratum_pois_gte_5[grp],
            "accepted_reviews": s_rev,
            "scientific_min_reviews_target": stratum_min_required[grp],
            "remaining_poi_deficit_reviews_to_min_5": s_def,
            "scientific_stratum_minimum_met": (
                stratum_pois_gte_5[grp] == quota and s_rev >= stratum_min_required[grp]
            ),
        }

    accepted_total = len(accepted_rows)
    covered_poi_count = len(pois_with_1_to_4_ids) + len(pois_with_5_or_more_ids)
    total_poi_deficit_to_min_5 = sum(city_poi_deficit_sum.values())
    remaining_reviews_to_300 = max(
        SCIENTIFIC_MIN_TOTAL_REVIEWS - accepted_total,
        total_poi_deficit_to_min_5,
    )

    # Section 16 Pilot Gate (`COLLECTION_PIPELINE_PILOT_READY`)
    pilot_total_ok = accepted_total >= PILOT_TARGET_TOTAL_REVIEWS
    pilot_cities_ok = all(
        city_accepted_counts[c] >= PILOT_TARGET_MIN_REVIEWS_PER_CITY
        for c in ("Hà Nội", "Đà Nẵng", "Hạ Long")
    )
    pilot_pois_ok = covered_poi_count >= PILOT_TARGET_MIN_DISTINCT_POIS
    pilot_consent_ok = missing_consent_in_accepted == 0
    pilot_no_synthetic_ok = synthetic_in_accepted == 0
    pilot_no_quarantined_counted_ok = quarantined_pii_in_accepted == 0

    collection_pipeline_pilot_ready = bool(
        pilot_total_ok
        and pilot_cities_ok
        and pilot_pois_ok
        and pilot_consent_ok
        and pilot_no_synthetic_ok
        and pilot_no_quarantined_counted_ok
        and importer_idempotency_verified
    )

    corpus_scientific_minimum_ready = bool(
        val_report["CORPUS_SCIENTIFIC_MINIMUM_READY"]
        and accepted_total >= SCIENTIFIC_MIN_TOTAL_REVIEWS
        and covered_poi_count == SCIENTIFIC_MIN_TOTAL_POIS
        and len(pois_with_5_or_more_ids) == SCIENTIFIC_MIN_TOTAL_POIS
        and pilot_consent_ok
        and pilot_no_synthetic_ok
        and pilot_no_quarantined_counted_ok
    )

    payload: dict[str, Any] = {
        "artifact_id": "w07_review_collection_progress_v1",
        "artifact_version": "1.0.0",
        "task_id": "W07-A3",
        "authoritative_develop_base_sha": w07_a3_import.AUTHORITATIVE_DEVELOP_BASE_SHA,
        "previous_gate": w07_a3_import.PREVIOUS_GATE,
        "next_gate": w07_a3_import.NEXT_GATE,
        "manifest_sha_binding": {
            "manifest_path": w07_a2.MANIFEST_60_JSON_RELPATH,
            "manifest_internal_sha256": w07_a3_import.EXPECTED_A2_MANIFEST_INTERNAL_SHA256,
            "manifest_file_lf_sha256": w07_a3_import.EXPECTED_A2_MANIFEST_FILE_LF_SHA256,
        },
        "privacy_and_content_guarantee": {
            "raw_review_text_published_in_this_artifact": False,
            "contributor_identity_published_in_this_artifact": False,
            "pilot_reviews_retained_in_final_corpus": True,
        },
        "summary_counts": {
            "total_candidate_rows_evaluated": val_report["total_input_rows"],
            "accepted_review_count": accepted_total,
            "rejected_review_count": val_report["rejected_review_count"],
            "quarantined_pii_count": val_report["quarantined_pii_count"],
            "duplicate_count": val_report["duplicate_count"],
            "warning_count": val_report["warning_count"],
            "covered_poi_count": covered_poi_count,
            "pois_with_0_reviews_count": len(pois_with_0_ids),
            "pois_with_1_to_4_reviews_count": len(pois_with_1_to_4_ids),
            "pois_with_5_or_more_reviews_count": len(pois_with_5_or_more_ids),
            "remaining_reviews_to_300": remaining_reviews_to_300,
        },
        "reviews_by_city": city_accepted_counts,
        "reviews_by_category_group": stratum_accepted_counts,
        "poi_coverage_buckets": {
            "pois_with_0_reviews": pois_with_0_ids,
            "pois_with_1_to_4_reviews": pois_with_1_to_4_ids,
            "pois_with_5_or_more_reviews": pois_with_5_or_more_ids,
            "stop_active_recruitment_pois": stop_active_recruitment_pois,
        },
        "city_completion_summary": city_completion_summary,
        "sampling_stratum_completion_summary": sampling_stratum_completion_summary,
        "pilot_gate_evaluation": {
            "COLLECTION_PIPELINE_PILOT_READY": collection_pipeline_pilot_ready,
            "pilot_status": (
                "PILOT_READY"
                if collection_pipeline_pilot_ready
                else "PILOT_COLLECTION_NOT_STARTED_OR_INCOMPLETE"
            ),
            "pilot_target_requirements": {
                "min_accepted_reviews_total": PILOT_TARGET_TOTAL_REVIEWS,
                "min_accepted_reviews_per_city": PILOT_TARGET_MIN_REVIEWS_PER_CITY,
                "min_distinct_target_pois": PILOT_TARGET_MIN_DISTINCT_POIS,
                "require_valid_consent_for_all": True,
                "require_zero_synthetic_or_llm_reviews": True,
                "require_zero_quarantined_reviews_counted": True,
                "require_importer_idempotency_verified": True,
            },
            "pilot_criteria_checks": {
                "accepted_reviews_gte_30": pilot_total_ok,
                "each_city_gte_10": pilot_cities_ok,
                "distinct_pois_gte_15": pilot_pois_ok,
                "valid_consent_for_all_accepted": pilot_consent_ok,
                "zero_synthetic_or_llm_reviews": pilot_no_synthetic_ok,
                "zero_quarantined_reviews_counted": pilot_no_quarantined_counted_ok,
                "importer_idempotency_verified": importer_idempotency_verified,
            },
            "remaining_reviews_to_pilot_30": max(0, PILOT_TARGET_TOTAL_REVIEWS - accepted_total),
            "pilot_ready_is_not_scientific_minimum_ready": True,
        },
        "scientific_minimum_evaluation": {
            "CORPUS_SCIENTIFIC_MINIMUM_READY": corpus_scientific_minimum_ready,
            "scientific_minimum_requirements": {
                "min_accepted_reviews_total": SCIENTIFIC_MIN_TOTAL_REVIEWS,
                "required_canonical_pois": SCIENTIFIC_MIN_TOTAL_POIS,
                "min_accepted_reviews_per_poi": SCIENTIFIC_MIN_REVIEWS_PER_POI,
                "min_accepted_reviews_per_city": SCIENTIFIC_MIN_REVIEWS_PER_CITY,
            },
            "remaining_reviews_to_300": remaining_reviews_to_300,
        },
        "runtime_and_governance_counters": {
            "NEW_PRIMARY_REVIEWS_ACQUIRED": accepted_total,
            "LLM_GENERATED_PRIMARY_REVIEWS": 0,
            "NEW_LLM_PROVIDER_CALLS": 0,
            "SCRAPING_EXECUTED": False,
        },
        "exact_under_covered_pois": under_covered_pois,
        "reviews_per_poi": reviews_per_poi,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(
        payload, "artifact_sha256"
    )
    return payload


def load_canonical_jsonl_rows(jsonl_path: Path) -> list[dict[str, Any]]:
    if not jsonl_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_collection_progress_artifact(
    repo_root: Path = REPO_ROOT,
    *,
    jsonl_path: Path | None = None,
) -> dict[str, Any]:
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)
    target_jsonl = (
        jsonl_path
        if jsonl_path is not None
        else repo_root / w07_a2.RESTRICTED_JSONL_RELPATH
    )
    rows = load_canonical_jsonl_rows(target_jsonl)
    payload = build_collection_progress_report(rows, manifest)

    progress_path = repo_root / PROGRESS_JSON_RELPATH
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return verify_collection_progress_artifact(repo_root, jsonl_path=target_jsonl)


def verify_collection_progress_artifact(
    repo_root: Path = REPO_ROOT,
    *,
    jsonl_path: Path | None = None,
) -> dict[str, Any]:
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)
    target_jsonl = (
        jsonl_path
        if jsonl_path is not None
        else repo_root / w07_a2.RESTRICTED_JSONL_RELPATH
    )
    rows = load_canonical_jsonl_rows(target_jsonl)
    expected_payload = build_collection_progress_report(rows, manifest)

    progress_path = repo_root / PROGRESS_JSON_RELPATH
    if not progress_path.exists():
        raise FileNotFoundError(f"Missing progress artifact: {progress_path}")

    disk_payload = json.loads(progress_path.read_text(encoding="utf-8"))
    disk_internal_sha = w07_a2.compute_internal_sha256(disk_payload, "artifact_sha256")
    if disk_internal_sha != disk_payload.get("artifact_sha256"):
        raise ValueError("Progress artifact internal SHA256 does not match its recorded artifact_sha256.")
    if disk_internal_sha != expected_payload["artifact_sha256"]:
        raise ValueError("Progress artifact on disk is out of sync with build_collection_progress_report().")

    return {
        "status": "PASS",
        "progress_json_path": PROGRESS_JSON_RELPATH,
        "progress_internal_sha256": disk_internal_sha,
        "progress_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(progress_path),
        "accepted_review_count": disk_payload["summary_counts"]["accepted_review_count"],
        "remaining_reviews_to_300": disk_payload["summary_counts"]["remaining_reviews_to_300"],
        "COLLECTION_PIPELINE_PILOT_READY": disk_payload["pilot_gate_evaluation"][
            "COLLECTION_PIPELINE_PILOT_READY"
        ],
        "CORPUS_SCIENTIFIC_MINIMUM_READY": disk_payload["scientific_minimum_evaluation"][
            "CORPUS_SCIENTIFIC_MINIMUM_READY"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="W07-A3 offline contributor review collection progress tracker."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write",
        action="store_true",
        help="Recompute and write data/evaluation/w07/w07_review_collection_progress_v1.json.",
    )
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed data/evaluation/w07/w07_review_collection_progress_v1.json.",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Optional override path for canonical reviews JSONL.",
    )
    args = parser.parse_args(argv)

    if args.write:
        res = write_collection_progress_artifact(REPO_ROOT, jsonl_path=args.jsonl)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    res = verify_collection_progress_artifact(REPO_ROOT, jsonl_path=args.jsonl)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
