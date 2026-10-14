"""Deterministic builder and attestation/submission gate for W5 Calibration Round 02.

Implements W5-CAL-R02-PREP-01:
- Round ID: W5-CAL-ROUND-02
- Calibration Version: W5-CALIBRATION-V2
- Track: CALIBRATION_ONLY (excluded_from_final_metrics = True)
- Base Seed: 20261014
- 3 Fresh Scenarios (CAL2-HN-01, CAL2-DN-01, CAL2-HL-01; 15 items each, 45 total)
  covering all 7 canonical REC-A interest dimensions.
- Source Universe: REC-A-CORE-V2 only, strictly excluding all 45 Round 01 calibration
  place_ids and all 255 primary candidate pool place_ids.
- Blinded J1, J2, J3 presentation packages (JSON and CSV) with independent deterministic
  item permutations and all labels/notes null.
- Pre-distribution role assignment contract and mandatory per-judge session attestation
  contract and programmatic gate (missing or failed attestation => NON_QUALIFYING).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from recommendation.reca.contract import (  # noqa: E402
    CANONICAL_INTERESTS,
    poi_to_canonical_vector,
)
from scripts.build_w5_annotation_package import (  # noqa: E402
    evaluate_metadata_sufficiency,
    extract_factual_context,
)
from scripts.validate_w5_calibration_submission import (  # noqa: E402
    ALLOWED_JUDGES,
    CSV_ALL_COLUMNS,
    CSV_READ_ONLY_COLUMNS,
    EDITABLE_ITEM_FIELDS,
    FORBIDDEN_LEAKAGE_KEYS,
    _enforce_exact_dict_shape_and_read_only_values,
    package_to_csv_rows,
    validate_completed_calibration_label,
)

ROUND_ID = "W5-CAL-ROUND-02"
CALIBRATION_VERSION = "W5-CALIBRATION-V2"
RUBRIC_VERSION = "W5-RUBRIC-V1"
POOL_VERSION = "W5-POOL-V1"
PRESENTATION_VERSION = "W5-CAL-R02-OPS-V1"
MANIFEST_VERSION = "W5-CAL-R02-MANIFEST-V1"
ROLE_ASSIGNMENT_CONTRACT_VERSION = "W5-CAL-R02-ROLE-ASSIGNMENT-CONTRACT-V1"
SESSION_ATTESTATION_CONTRACT_VERSION = "W5-CAL-R02-SESSION-ATTESTATION-CONTRACT-V1"
SUBMISSION_CONTRACT_VERSION = "W5-CAL-R02-SUBMISSION-CONTRACT-V1"

ROUND02_SEED = 20261014
SAMPLING_PURPOSE_TAG = "round02-calibration-sampling"
ORDER_PURPOSE_TAG = "round02-calibration-presentation"

EXPECTED_ITEMS_PER_SCENARIO = 15
EXPECTED_TOTAL_ITEMS = 45
TARGET_I0_PER_SCENARIO = 10
TARGET_I1_PER_SCENARIO = 5
NON_SUFFICIENT_CAP_I0 = 2
NON_SUFFICIENT_CAP_I1 = 1

ROUND02_SCENARIO_SPECS: tuple[dict[str, Any], ...] = (
    {
        "scenario_id": "CAL2-HN-01",
        "destination": "ha-noi",
        "destination_slug": "ha-noi",
        "declared_interests": [
            "culture_history",
            "nature_outdoor",
            "nightlife_entertainment",
        ],
    },
    {
        "scenario_id": "CAL2-DN-01",
        "destination": "da-nang",
        "destination_slug": "da-nang",
        "declared_interests": [
            "food_cuisine",
            "beach_island",
        ],
    },
    {
        "scenario_id": "CAL2-HL-01",
        "destination": "ha-long",
        "destination_slug": "ha-long",
        "declared_interests": [
            "coffee_culture",
            "shopping_local",
        ],
    },
)

EXPECTED_SCENARIO_IDS = tuple(spec["scenario_id"] for spec in ROUND02_SCENARIO_SPECS)

REQUIRED_ATTESTATION_BOOLEANS: dict[str, bool] = {
    "actual_human_judge": True,
    "ai_llm_used_for_label_decisions": False,
    "external_search_used": False,
    "inspected_other_judge_labels_before_submission": False,
    "exposed_to_other_judge_label_summary_before_submission": False,
    "direct_label_discussion_before_all_submissions_locked": False,
    "assigned_role_before_distribution": True,
    "completed_all_required_items": True,
    "submitted_privately_to_project_owner": True,
    "published_or_shared_own_labels_or_summary_before_all_submissions_locked": False,
}

FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
ANNOTATION_DIR = EVAL_DIR / "annotation"
ROUND01_CALIBRATION_PATH = ANNOTATION_DIR / "w5_calibration_v1.json"
ROUND02_CALIBRATION_PATH = ANNOTATION_DIR / "w5_calibration_v2.json"
BLINDED_POOL_PATH = EVAL_DIR / "w5_candidate_pool_blinded_v1.json"
INTERNAL_POOL_PATH = EVAL_DIR / "w5_candidate_pool_internal_v1.json"

ROUND02_OPS_DIR = EVAL_DIR / "calibration_round02_ops"
ROUND02_PACKAGES_DIR = ROUND02_OPS_DIR / "judge_packages"
ROUND02_MANIFEST_PATH = ROUND02_OPS_DIR / "w5_calibration_round02_manifest_v1.json"
ROUND02_ROLE_CONTRACT_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_role_assignment_contract_v1.json"
)
ROUND02_ATTESTATION_TEMPLATE_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_session_attestation_template_v1.json"
)
ROUND02_SUBMISSION_CONTRACT_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_submission_contract_v1.json"
)


def canonical_lf_sha256_bytes(raw_bytes: bytes) -> str:
    """Compute platform-independent SHA256 after normalizing CRLF to LF."""
    normalized = raw_bytes.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def canonical_lf_sha256_file(path: Path) -> str:
    """Compute platform-independent LF-normalized SHA256 of a file."""
    return canonical_lf_sha256_bytes(path.read_bytes())


def canonical_json_sha256(obj: Any) -> str:
    """Compute platform-independent SHA256 of canonical compact sorted JSON."""
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def write_json_lf(path: Path, obj: Any) -> None:
    """Write formatted UTF-8 JSON with deterministic LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_csv_lf(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    """Write UTF-8 CSV with deterministic LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def compute_round02_scenario_seed_basis(scenario_id: str, judge_id: str) -> str:
    """Return the canonical permutation seed basis string for Round 02."""
    return f"{ROUND02_SEED}:{scenario_id}:{judge_id}:{ORDER_PURPOSE_TAG}"


def compute_round02_item_order_key(
    scenario_id: str, judge_id: str, judge_item_id: str
) -> tuple[str, str]:
    """Compute SHA256-derived deterministic ordering key for a Round 02 calibration item."""
    basis = f"{compute_round02_scenario_seed_basis(scenario_id, judge_id)}:{judge_item_id}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return (digest, judge_item_id)


def _poi_representation_stratum(place: dict[str, Any]) -> str:
    """Return 'I0' if POI has at least one active canonical interest, else 'I1' (zero-vector)."""
    res = poi_to_canonical_vector(place)
    vec = res[0] if isinstance(res, tuple) else res
    return "I0" if any(v > 0 for v in vec) else "I1"


def load_exclusion_sets() -> dict[str, set[str]]:
    """Load Round 01 calibration place_ids and primary candidate pool place_ids to exclude."""
    round01_doc = json.loads(ROUND01_CALIBRATION_PATH.read_text(encoding="utf-8"))
    round01_ids = {
        it["place_id"] for sc in round01_doc["scenarios"] for it in sc["items"]
    }

    blinded_scenarios = json.loads(BLINDED_POOL_PATH.read_text(encoding="utf-8"))
    internal_scenarios = json.loads(INTERNAL_POOL_PATH.read_text(encoding="utf-8"))
    blinded_ids = {it["place_id"] for sc in blinded_scenarios for it in sc["items"]}
    internal_ids = {it["place_id"] for sc in internal_scenarios for it in sc["items"]}
    primary_pool_ids = blinded_ids | internal_ids

    return {
        "round01_place_ids": round01_ids,
        "primary_pool_place_ids": primary_pool_ids,
        "all_excluded_place_ids": round01_ids | primary_pool_ids,
    }


def select_scenario_items_deterministically(
    scenario_id: str,
    destination_slug: str,
    eligible_places: list[dict[str, Any]],
    *,
    base_seed: int = ROUND02_SEED,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deterministically sample 15 fresh REC-A-CORE-V2 POIs for a Round 02 scenario.

    Algorithm:
    1. Sort eligible places by place_id ascending.
    2. Compute objective structural attributes:
       - representation_stratum in {'I0', 'I1'} from frozen poi_to_canonical_vector
       - metadata_sufficiency in {'SUFFICIENT_FACTUAL_CONTEXT', 'LIMITED_FACTUAL_CONTEXT',
         'INSUFFICIENT_FACTUAL_CONTEXT'} from frozen evaluate_metadata_sufficiency
       - factual category from place['category']
       No expected relevance labels are computed or used.
    3. Derive scenario RNG from SHA256('20261014|<scenario_id>|round02-calibration-sampling').
    4. Within I0 (target quota = 10) and I1 (target quota = 5):
       a. Include up to NON_SUFFICIENT_CAP_I0 (2) in I0 and NON_SUFFICIENT_CAP_I1 (1) in I1
          of non-SUFFICIENT_FACTUAL_CONTEXT items (prioritizing INSUFFICIENT_FACTUAL_CONTEXT
          then LIMITED_FACTUAL_CONTEXT) so judges encounter realistic sparse-metadata cases.
       b. Fill remaining quota via seeded round-robin across factual category buckets so
          multiple categories are represented without cherry-picking.
    5. Shuffle the 15 selected items deterministically using the scenario RNG and assign
       canonical judge_item_id CAL2-<DEST>-01-J01 .. J15.
    """
    if len(eligible_places) < EXPECTED_ITEMS_PER_SCENARIO:
        raise RuntimeError(
            f"ROUND02_INVENTORY_SHORTAGE: {scenario_id} ({destination_slug}) has only "
            f"{len(eligible_places)} eligible fresh core POIs; {EXPECTED_ITEMS_PER_SCENARIO} required."
        )

    seed_str = f"{base_seed}|{scenario_id}|{SAMPLING_PURPOSE_TAG}"
    seed_hex = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    rng = random.Random(int(seed_hex[:16], 16))

    enriched: list[dict[str, Any]] = []
    for place in sorted(eligible_places, key=lambda p: p["place_id"]):
        rep = _poi_representation_stratum(place)
        factual_ctx = extract_factual_context(place)
        item_proxy = {
            "name": place.get("name"),
            "category": place.get("category"),
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "address": place.get("address"),
        }
        suff_status, suff_reason = evaluate_metadata_sufficiency(item_proxy, place, factual_ctx)
        enriched.append(
            {
                "place": place,
                "place_id": place["place_id"],
                "representation_stratum": rep,
                "metadata_sufficiency": suff_status,
                "metadata_sufficiency_reason": suff_reason,
                "factual_context": factual_ctx,
                "category": place.get("category") or "unknown",
            }
        )

    i0_pool = [e for e in enriched if e["representation_stratum"] == "I0"]
    i1_pool = [e for e in enriched if e["representation_stratum"] == "I1"]
    if len(i0_pool) < TARGET_I0_PER_SCENARIO or len(i1_pool) < TARGET_I1_PER_SCENARIO:
        raise RuntimeError(
            f"ROUND02_STRATUM_SHORTAGE for {scenario_id}: "
            f"I0={len(i0_pool)} (need {TARGET_I0_PER_SCENARIO}), "
            f"I1={len(i1_pool)} (need {TARGET_I1_PER_SCENARIO})."
        )

    selected_enriched: list[dict[str, Any]] = []
    for rep_target, quota, non_suff_cap in (
        ("I0", TARGET_I0_PER_SCENARIO, NON_SUFFICIENT_CAP_I0),
        ("I1", TARGET_I1_PER_SCENARIO, NON_SUFFICIENT_CAP_I1),
    ):
        pool = [e for e in enriched if e["representation_stratum"] == rep_target]
        non_suff = [
            e for e in pool if e["metadata_sufficiency"] != "SUFFICIENT_FACTUAL_CONTEXT"
        ]
        rng.shuffle(non_suff)
        non_suff.sort(
            key=lambda e: 0
            if e["metadata_sufficiency"] == "INSUFFICIENT_FACTUAL_CONTEXT"
            else 1
        )
        picked_rep = non_suff[:non_suff_cap]
        picked_ids = {e["place_id"] for e in picked_rep}

        rem_pool = [e for e in pool if e["place_id"] not in picked_ids]
        by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in rem_pool:
            by_cat[e["category"]].append(e)
        for cat in sorted(by_cat):
            rng.shuffle(by_cat[cat])
        cats = sorted(by_cat.keys())
        rng.shuffle(cats)

        idx = 0
        while len(picked_rep) < quota and any(by_cat.values()):
            cat = cats[idx % len(cats)]
            if by_cat[cat]:
                picked_rep.append(by_cat[cat].pop(0))
            idx += 1

        if len(picked_rep) != quota:
            raise RuntimeError(
                f"Failed to select {quota} items for {scenario_id} stratum {rep_target}"
            )
        selected_enriched.extend(picked_rep)

    rng.shuffle(selected_enriched)

    canonical_items: list[dict[str, Any]] = []
    rep_counts: Counter[str] = Counter()
    suff_counts: Counter[str] = Counter()
    cat_counts: Counter[str] = Counter()
    representation_by_place_id: dict[str, str] = {}

    for idx, entry in enumerate(selected_enriched, start=1):
        place = entry["place"]
        pid = entry["place_id"]
        rep = entry["representation_stratum"]
        suff = entry["metadata_sufficiency"]
        cat = place.get("category")

        rep_counts[rep] += 1
        suff_counts[suff] += 1
        cat_counts[str(cat)] += 1
        representation_by_place_id[pid] = rep

        canonical_items.append(
            {
                "scenario_id": scenario_id,
                "judge_item_id": f"{scenario_id}-J{idx:02d}",
                "place_id": pid,
                "name": place.get("name"),
                "category": cat,
                "factual_context": entry["factual_context"],
                "metadata_sufficiency": suff,
                "label": None,
                "judge_note": None,
            }
        )

    audit_stats = {
        "scenario_id": scenario_id,
        "destination": destination_slug,
        "sampling_seed_basis": seed_str,
        "sampling_seed_sha256_prefix16": seed_hex[:16],
        "eligible_fresh_core_count": len(eligible_places),
        "selected_count": len(canonical_items),
        "i0_i1_counts": {
            "I0": rep_counts["I0"],
            "I1": rep_counts["I1"],
        },
        "metadata_sufficiency_counts": {
            "SUFFICIENT_FACTUAL_CONTEXT": suff_counts["SUFFICIENT_FACTUAL_CONTEXT"],
            "LIMITED_FACTUAL_CONTEXT": suff_counts["LIMITED_FACTUAL_CONTEXT"],
            "INSUFFICIENT_FACTUAL_CONTEXT": suff_counts["INSUFFICIENT_FACTUAL_CONTEXT"],
        },
        "category_counts": dict(sorted(cat_counts.items())),
        "representation_by_place_id": representation_by_place_id,
    }
    return canonical_items, audit_stats


def build_canonical_round02_calibration_doc() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the canonical W5-CALIBRATION-V2 document and sampling audit summary."""
    freeze_places: list[dict[str, Any]] = json.loads(
        FREEZE_V2_PATH.read_text(encoding="utf-8")
    )
    core_places = [p for p in freeze_places if p.get("is_rec_a_core_v2") is True]
    exclusions = load_exclusion_sets()
    excluded_ids = exclusions["all_excluded_place_ids"]

    selected_round02_ids: set[str] = set()
    scenarios_out: list[dict[str, Any]] = []
    scenario_audits: dict[str, Any] = {}
    total_items = 0

    for spec in ROUND02_SCENARIO_SPECS:
        sc_id = spec["scenario_id"]
        dst_slug = spec["destination_slug"]
        eligible = [
            p
            for p in core_places
            if p.get("destination_slug") == dst_slug
            and p["place_id"] not in excluded_ids
            and p["place_id"] not in selected_round02_ids
        ]

        items, sc_audit = select_scenario_items_deterministically(
            sc_id, dst_slug, eligible, base_seed=ROUND02_SEED
        )
        for it in items:
            selected_round02_ids.add(it["place_id"])
        total_items += len(items)
        scenario_audits[sc_id] = sc_audit

        scenarios_out.append(
            {
                "scenario_id": sc_id,
                "destination": spec["destination"],
                "declared_interests": list(spec["declared_interests"]),
                "track": "CALIBRATION_ONLY",
                "excluded_from_final_metrics": True,
                "item_count": len(items),
                "items": items,
            }
        )

    canonical_doc = {
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "base_seed": ROUND02_SEED,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "description": (
            "Fresh deterministic Round 02 human calibration package (W5-CALIBRATION-V2) "
            "across CAL2-HN-01, CAL2-DN-01, and CAL2-HL-01. Strictly disjoint from both "
            "W5-CALIBRATION-V1 (Round 01) and the primary 30-scenario evaluation pool. "
            "All labels and notes are null."
        ),
        "scenario_count": len(scenarios_out),
        "total_items": total_items,
        "scenarios": scenarios_out,
    }

    sampling_summary = {
        "round01_excluded_place_count": len(exclusions["round01_place_ids"]),
        "primary_pool_excluded_place_count": len(exclusions["primary_pool_place_ids"]),
        "total_excluded_place_count": len(excluded_ids),
        "round01_place_overlap": len(selected_round02_ids & exclusions["round01_place_ids"]),
        "primary_pool_place_overlap": len(
            selected_round02_ids & exclusions["primary_pool_place_ids"]
        ),
        "secondary_non_core_poi_leakage": 0,
        "unique_round02_place_count": len(selected_round02_ids),
        "scenario_audits": scenario_audits,
    }
    return canonical_doc, sampling_summary


def build_round02_judge_package(
    canonical_doc: dict[str, Any], judge_id: str
) -> dict[str, Any]:
    """Build a blinded, deterministically permuted Round 02 package for a single judge."""
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(f"Unsupported judge_id {judge_id!r}; expected one of {ALLOWED_JUDGES}")

    scenarios_out: list[dict[str, Any]] = []
    global_idx = 0

    for sc in canonical_doc.get("scenarios", []):
        sc_id = sc["scenario_id"]
        destination = sc["destination"]
        declared_interests = list(sc["declared_interests"])

        raw_items = list(sc.get("items", []))
        ordered_items = sorted(
            raw_items,
            key=lambda it: compute_round02_item_order_key(sc_id, judge_id, it["judge_item_id"]),
        )

        presented_items: list[dict[str, Any]] = []
        for p_idx, item in enumerate(ordered_items, start=1):
            global_idx += 1
            factual_ctx = copy.deepcopy(item.get("factual_context", {}))
            for k in list(factual_ctx.keys()):
                if k in FORBIDDEN_LEAKAGE_KEYS:
                    factual_ctx.pop(k, None)

            presented_items.append(
                {
                    "judge_id": judge_id,
                    "round_id": ROUND_ID,
                    "calibration_version": CALIBRATION_VERSION,
                    "rubric_version": RUBRIC_VERSION,
                    "presentation_version": PRESENTATION_VERSION,
                    "scenario_id": sc_id,
                    "presentation_index": p_idx,
                    "global_presentation_index": global_idx,
                    "calibration_item_id": item["judge_item_id"],
                    "judge_item_id": item["judge_item_id"],
                    "place_id": item["place_id"],
                    "destination": destination,
                    "declared_interests": declared_interests,
                    "name": item["name"],
                    "category": item["category"],
                    "factual_context": factual_ctx,
                    "label": None,
                    "judge_note": None,
                }
            )

        scenarios_out.append(
            {
                "scenario_id": sc_id,
                "destination": destination,
                "declared_interests": declared_interests,
                "track": "CALIBRATION_ONLY",
                "excluded_from_final_metrics": True,
                "order_seed_basis": compute_round02_scenario_seed_basis(sc_id, judge_id),
                "item_count": len(presented_items),
                "items": presented_items,
            }
        )

    return {
        "judge_id": judge_id,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "base_seed": ROUND02_SEED,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "scenario_count": len(scenarios_out),
        "total_items": global_idx,
        "scenarios": scenarios_out,
    }


def build_role_assignment_contract_doc() -> dict[str, Any]:
    """Build the Round 02 pre-distribution judge role assignment contract/template."""
    return {
        "contract_version": ROLE_ASSIGNMENT_CONTRACT_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "status": "PRE_DISTRIBUTION_TEMPLATE",
        "assignment_execution_status": "NOT_STARTED",
        "actual_human_roles_assigned": False,
        "distinct_actual_humans_confirmed": False,
        "packages_distributed": False,
        "pre_distribution_assignment_required": True,
        "self_selected_roles_prohibited": True,
        "single_package_per_judge_distribution_required": True,
        "personal_identifiable_information_stored_in_repo": False,
        "private_mapping_owner": "PROJECT_OWNER_OFF_REPO",
        "required_role_assignments": {
            "J1": {
                "judge_id": "J1",
                "must_be_assigned_before_package_distribution": True,
                "other_judge_packages_must_be_withheld": True,
                "actual_human_assigned": False,
                "package_distributed": False,
                "target_package_json": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J1_v2.json"
                ),
                "target_package_csv": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J1_v2.csv"
                ),
            },
            "J2": {
                "judge_id": "J2",
                "must_be_assigned_before_package_distribution": True,
                "other_judge_packages_must_be_withheld": True,
                "actual_human_assigned": False,
                "package_distributed": False,
                "target_package_json": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J2_v2.json"
                ),
                "target_package_csv": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J2_v2.csv"
                ),
            },
            "J3": {
                "judge_id": "J3",
                "must_be_assigned_before_package_distribution": True,
                "other_judge_packages_must_be_withheld": True,
                "actual_human_assigned": False,
                "package_distributed": False,
                "target_package_json": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J3_v2.json"
                ),
                "target_package_csv": (
                    "data/evaluation/reca_w5/calibration_round02_ops/judge_packages/"
                    "w5_calibration_round02_J3_v2.csv"
                ),
            },
        },
        "distribution_rules": [
            "Project owner MUST assign three distinct actual human judges to J1, J2, and J3 BEFORE distributing any package files.",
            "Each human judge MUST receive ONLY their assigned Jk package and the frozen rubric (W5-RUBRIC-V1).",
            "No human judge may choose their own judge_id or inspect another judge's package.",
            "Repository artifacts store only pseudonyms J1, J2, and J3; no personal names or contact details are committed.",
        ],
    }


def build_session_attestation_template_doc() -> dict[str, Any]:
    """Build the machine-readable Round 02 per-judge session attestation template and contract."""
    return {
        "contract_version": SESSION_ATTESTATION_CONTRACT_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "missing_or_failed_attestation_outcome": "NON_QUALIFYING",
        "required_boolean_attestations": copy.deepcopy(REQUIRED_ATTESTATION_BOOLEANS),
        "non_qualifying_triggers": [
            "attestation_missing_or_null",
            "actual_human_judge != true",
            "ai_llm_used_for_label_decisions != false",
            "external_search_used != false",
            "inspected_other_judge_labels_before_submission != false",
            "exposed_to_other_judge_label_summary_before_submission != false",
            "direct_label_discussion_before_all_submissions_locked != false",
            "assigned_role_before_distribution != true",
            "completed_all_required_items != true",
            "submitted_privately_to_project_owner != true",
            "published_or_shared_own_labels_or_summary_before_all_submissions_locked != false",
            "judge_id_mismatch_or_invalid",
            "round_id_or_calibration_version_mismatch",
        ],
        "per_judge_attestation_template": {
            "judge_id": "J1 | J2 | J3",
            "round_id": ROUND_ID,
            "calibration_version": CALIBRATION_VERSION,
            "rubric_version": RUBRIC_VERSION,
            "presentation_version": PRESENTATION_VERSION,
            "actual_human_judge": None,
            "ai_llm_used_for_label_decisions": None,
            "external_search_used": None,
            "inspected_other_judge_labels_before_submission": None,
            "exposed_to_other_judge_label_summary_before_submission": None,
            "direct_label_discussion_before_all_submissions_locked": None,
            "assigned_role_before_distribution": None,
            "completed_all_required_items": None,
            "submitted_privately_to_project_owner": None,
            "published_or_shared_own_labels_or_summary_before_all_submissions_locked": None,
            "completed_at_utc": None,
        },
    }


def build_round02_submission_contract_doc() -> dict[str, Any]:
    """Build the Round 02 calibration submission and attestation contract."""
    return {
        "contract_version": SUBMISSION_CONTRACT_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "allowed_judges": list(ALLOWED_JUDGES),
        "expected_scenarios": list(EXPECTED_SCENARIO_IDS),
        "expected_items_per_scenario": EXPECTED_ITEMS_PER_SCENARIO,
        "expected_total_items": EXPECTED_TOTAL_ITEMS,
        "allowed_completed_labels": [0, 1, 2, "NA"],
        "editable_fields": list(EDITABLE_ITEM_FIELDS),
        "read_only_context_policy": "EXACT_MATCH_TO_FROZEN_ROUND02_PRESENTATION_PACKAGE",
        "attestation_gate_required": True,
        "required_boolean_attestations": copy.deepcopy(REQUIRED_ATTESTATION_BOOLEANS),
        "missing_or_failed_attestation_outcome": "NON_QUALIFYING",
        "privacy_and_locking_rules": [
            "Each judge submits their completed file and attestation privately to the project owner.",
            "No judge may post label counts, examples, or summaries before all 3 submissions are locked.",
            "Both file validation AND session attestation validation must PASS for a submission to be QUALIFYING.",
        ],
    }


def validate_round02_session_attestation(
    attestation_doc: dict[str, Any] | None,
    *,
    expected_judge_id: str | None = None,
) -> dict[str, Any]:
    """Validate a Round 02 per-judge session attestation dictionary.

    Returns a dict with:
    - qualification_status: 'QUALIFYING' or 'NON_QUALIFYING'
    - valid: bool
    - reasons: list[str]
    """
    reasons: list[str] = []
    if attestation_doc is None or not isinstance(attestation_doc, dict):
        return {
            "qualification_status": "NON_QUALIFYING",
            "valid": False,
            "reasons": ["missing_or_invalid_attestation_document"],
        }

    jid = attestation_doc.get("judge_id")
    if jid not in ALLOWED_JUDGES:
        reasons.append(f"invalid_judge_id:{jid!r}")
    if expected_judge_id is not None and jid != expected_judge_id:
        reasons.append(f"judge_id_mismatch:got_{jid!r}_expected_{expected_judge_id!r}")

    if attestation_doc.get("round_id") != ROUND_ID:
        reasons.append(f"round_id_mismatch:{attestation_doc.get('round_id')!r}")
    if attestation_doc.get("calibration_version") != CALIBRATION_VERSION:
        reasons.append(
            f"calibration_version_mismatch:{attestation_doc.get('calibration_version')!r}"
        )

    for key, expected_bool in REQUIRED_ATTESTATION_BOOLEANS.items():
        if key not in attestation_doc:
            reasons.append(f"missing_required_attestation_field:{key}")
            continue
        val = attestation_doc[key]
        if type(val) is not bool:
            reasons.append(f"non_boolean_attestation_field:{key}={val!r}")
            continue
        if val is not expected_bool:
            reasons.append(f"failed_attestation_requirement:{key}={val!r}_expected_{expected_bool!r}")

    is_valid = len(reasons) == 0
    return {
        "qualification_status": "QUALIFYING" if is_valid else "NON_QUALIFYING",
        "valid": is_valid,
        "reasons": reasons,
    }


def validate_round02_package_or_submission(
    submission_doc: dict[str, Any],
    *,
    canonical_doc: dict[str, Any] | None = None,
    validate_empty_package: bool = False,
    attestation_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a Round 02 JSON presentation package or completed submission + attestation."""
    if canonical_doc is None:
        canonical_doc = json.loads(ROUND02_CALIBRATION_PATH.read_text(encoding="utf-8"))

    judge_id = submission_doc.get("judge_id")
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(f"Invalid judge_id {judge_id!r}; expected one of {ALLOWED_JUDGES}.")

    reference_pkg = build_round02_judge_package(canonical_doc, judge_id)
    _enforce_exact_dict_shape_and_read_only_values(
        submission_doc,
        reference_pkg,
        context_label=f"Round 02 package root for {judge_id}",
        mutable_or_child_keys=frozenset({"scenarios"}),
    )

    scenarios = submission_doc.get("scenarios")
    ref_scenarios = reference_pkg["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != len(ref_scenarios):
        raise ValueError("Round 02 scenario list count mismatch.")

    label_counts: dict[str, int] = {"0": 0, "1": 0, "2": 0, "NA": 0, "null": 0}
    total_items = 0

    for sc, ref_sc in zip(scenarios, ref_scenarios, strict=True):
        _enforce_exact_dict_shape_and_read_only_values(
            sc,
            ref_sc,
            context_label=f"Scenario {ref_sc['scenario_id']}",
            mutable_or_child_keys=frozenset({"items"}),
        )
        items = sc.get("items")
        ref_items = ref_sc["items"]
        if not isinstance(items, list) or len(items) != len(ref_items):
            raise ValueError(f"Item count mismatch in {ref_sc['scenario_id']}.")

        for item, ref_item in zip(items, ref_items, strict=True):
            _enforce_exact_dict_shape_and_read_only_values(
                item,
                ref_item,
                context_label=f"Item {ref_item['judge_item_id']}",
                mutable_or_child_keys=frozenset(EDITABLE_ITEM_FIELDS),
            )
            raw_label = item.get("label")
            raw_note = item.get("judge_note")

            if validate_empty_package:
                if raw_label is not None:
                    raise ValueError(f"Generated Round 02 package must have label=None on {ref_item['judge_item_id']}.")
                if raw_note is not None:
                    raise ValueError(f"Generated Round 02 package must have judge_note=None on {ref_item['judge_item_id']}.")
                label_counts["null"] += 1
            else:
                validated = validate_completed_calibration_label(raw_label)
                label_counts[str(validated)] += 1

            total_items += 1

    if validate_empty_package:
        return {
            "status": "PASS",
            "mode": "EMPTY_PACKAGE",
            "judge_id": judge_id,
            "total_items": total_items,
            "label_counts": label_counts,
        }

    att_res = validate_round02_session_attestation(
        attestation_doc, expected_judge_id=judge_id
    )
    return {
        "status": "PASS" if att_res["valid"] else "NON_QUALIFYING",
        "file_integrity_status": "PASS",
        "qualification_status": att_res["qualification_status"],
        "attestation_valid": att_res["valid"],
        "attestation_reasons": att_res["reasons"],
        "mode": "COMPLETED_SUBMISSION",
        "judge_id": judge_id,
        "total_items": total_items,
        "label_counts": label_counts,
    }


def generate_all_round02_artifacts() -> dict[str, Any]:
    """Generate and write all W5-CAL-R02-PREP-01 artifacts deterministically."""
    ROUND02_OPS_DIR.mkdir(parents=True, exist_ok=True)
    ROUND02_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

    canonical_doc, sampling_summary = build_canonical_round02_calibration_doc()
    write_json_lf(ROUND02_CALIBRATION_PATH, canonical_doc)

    role_contract_doc = build_role_assignment_contract_doc()
    write_json_lf(ROUND02_ROLE_CONTRACT_PATH, role_contract_doc)

    attestation_template_doc = build_session_attestation_template_doc()
    write_json_lf(ROUND02_ATTESTATION_TEMPLATE_PATH, attestation_template_doc)

    submission_contract_doc = build_round02_submission_contract_doc()
    write_json_lf(ROUND02_SUBMISSION_CONTRACT_PATH, submission_contract_doc)

    judge_package_records: dict[str, Any] = {}
    presentation_order_hashes: dict[str, str] = {}

    for jid in ALLOWED_JUDGES:
        pkg_doc = build_round02_judge_package(canonical_doc, jid)
        val_res = validate_round02_package_or_submission(
            pkg_doc, canonical_doc=canonical_doc, validate_empty_package=True
        )
        assert val_res["status"] == "PASS"

        json_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.json"
        csv_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.csv"

        write_json_lf(json_path, pkg_doc)
        csv_rows = package_to_csv_rows(pkg_doc)
        write_csv_lf(csv_path, CSV_ALL_COLUMNS, csv_rows)

        ordered_item_ids = [
            it["judge_item_id"]
            for sc in pkg_doc["scenarios"]
            for it in sc["items"]
        ]
        order_sha = hashlib.sha256(
            json.dumps(ordered_item_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        presentation_order_hashes[jid] = order_sha

        judge_package_records[jid] = {
            "judge_id": jid,
            "json_path": f"data/evaluation/reca_w5/calibration_round02_ops/judge_packages/{json_path.name}",
            "json_canonical_lf_sha256": canonical_lf_sha256_file(json_path),
            "json_canonical_object_sha256": canonical_json_sha256(pkg_doc),
            "csv_path": f"data/evaluation/reca_w5/calibration_round02_ops/judge_packages/{csv_path.name}",
            "csv_canonical_lf_sha256": canonical_lf_sha256_file(csv_path),
            "scenario_count": pkg_doc["scenario_count"],
            "total_items": pkg_doc["total_items"],
            "presentation_order_sha256": order_sha,
            "scenario_first3_items": {
                sc["scenario_id"]: [it["judge_item_id"] for it in sc["items"][:3]]
                for sc in pkg_doc["scenarios"]
            },
        }

    covered_interests = sorted(
        {
            interest
            for spec in ROUND02_SCENARIO_SPECS
            for interest in spec["declared_interests"]
        }
    )
    assert set(covered_interests) == set(CANONICAL_INTERESTS)

    total_i0 = sum(
        sc_a["i0_i1_counts"]["I0"]
        for sc_a in sampling_summary["scenario_audits"].values()
    )
    total_i1 = sum(
        sc_a["i0_i1_counts"]["I1"]
        for sc_a in sampling_summary["scenario_audits"].values()
    )
    total_suff = Counter()
    for sc_a in sampling_summary["scenario_audits"].values():
        for k, v in sc_a["metadata_sufficiency_counts"].items():
            total_suff[k] += v

    manifest_doc = {
        "manifest_version": MANIFEST_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "status": "PREPARED_NOT_STARTED",
        "base_seed": ROUND02_SEED,
        "actual_human_judgments_collected": 0,
        "qualifying_independent_human_judgments": 0,
        "calibration_review_eligible": False,
        "human_gt": False,
        "primary_annotation_started": False,
        "recommender_evaluation_performed": False,
        "scientific_winner": "UNKNOWN",
        "round_01_status": "INVALIDATED_FOR_PROTOCOL",
        "round_01_scientific_use": "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY",
        "hash_basis_policy": {
            "primary_hash_basis": "COMMITTED_GIT_BLOB_UTF8_LF_NORMALIZED_SHA256",
            "secondary_json_hash_basis": "CANONICAL_SORTED_COMPACT_JSON_UTF8_SHA256",
            "line_ending_policy": "LF_ONLY_FOR_ALL_NEW_ROUND02_ARTIFACTS",
            "historical_hash_note": (
                "Historical W5 freeze hashes are untouched; any historical LF/CRLF hash "
                "representation concern is tracked separately as W5-HASH-AUDIT-CANDIDATE."
            ),
        },
        "scenario_summary": [
            {
                "scenario_id": spec["scenario_id"],
                "destination": spec["destination"],
                "declared_interests": list(spec["declared_interests"]),
                "item_count": EXPECTED_ITEMS_PER_SCENARIO,
            }
            for spec in ROUND02_SCENARIO_SPECS
        ],
        "canonical_interest_coverage": {
            "required_canonical_interests": list(CANONICAL_INTERESTS),
            "covered_interests": covered_interests,
            "all_7_covered": set(covered_interests) == set(CANONICAL_INTERESTS),
        },
        "sampling_and_exclusion_audit": {
            "sampling_algorithm": (
                "Deterministic stratified sampling per destination from REC-A-CORE-V2 "
                "(seed=20261014) excluding all 45 Round 01 calibration place_ids and all "
                "255 primary candidate pool place_ids; target 10 I0 + 5 I1 per scenario "
                "with non-sufficient metadata inclusion cap (<=2 in I0, <=1 in I1) and "
                "seeded category round-robin; zero expected relevance labels computed or stored."
            ),
            "source_universe": "REC-A-CORE-V2",
            "round01_excluded_place_count": sampling_summary["round01_excluded_place_count"],
            "primary_pool_excluded_place_count": sampling_summary[
                "primary_pool_excluded_place_count"
            ],
            "total_excluded_place_count": sampling_summary["total_excluded_place_count"],
            "round01_place_overlap": sampling_summary["round01_place_overlap"],
            "primary_pool_place_overlap": sampling_summary["primary_pool_place_overlap"],
            "secondary_non_core_poi_leakage": sampling_summary[
                "secondary_non_core_poi_leakage"
            ],
            "unique_round02_place_count": sampling_summary["unique_round02_place_count"],
            "total_i0_count": total_i0,
            "total_i1_count": total_i1,
            "total_metadata_sufficiency_counts": {
                "SUFFICIENT_FACTUAL_CONTEXT": total_suff["SUFFICIENT_FACTUAL_CONTEXT"],
                "LIMITED_FACTUAL_CONTEXT": total_suff["LIMITED_FACTUAL_CONTEXT"],
                "INSUFFICIENT_FACTUAL_CONTEXT": total_suff["INSUFFICIENT_FACTUAL_CONTEXT"],
            },
            "by_scenario": sampling_summary["scenario_audits"],
        },
        "artifacts": {
            "w5_calibration_v2.json": {
                "path": "data/evaluation/reca_w5/annotation/w5_calibration_v2.json",
                "canonical_lf_sha256": canonical_lf_sha256_file(ROUND02_CALIBRATION_PATH),
                "canonical_json_sha256": canonical_json_sha256(canonical_doc),
            },
            "w5_calibration_round02_role_assignment_contract_v1.json": {
                "path": (
                    "data/evaluation/reca_w5/calibration_round02_ops/"
                    "w5_calibration_round02_role_assignment_contract_v1.json"
                ),
                "canonical_lf_sha256": canonical_lf_sha256_file(ROUND02_ROLE_CONTRACT_PATH),
                "canonical_json_sha256": canonical_json_sha256(role_contract_doc),
            },
            "w5_calibration_round02_session_attestation_template_v1.json": {
                "path": (
                    "data/evaluation/reca_w5/calibration_round02_ops/"
                    "w5_calibration_round02_session_attestation_template_v1.json"
                ),
                "canonical_lf_sha256": canonical_lf_sha256_file(
                    ROUND02_ATTESTATION_TEMPLATE_PATH
                ),
                "canonical_json_sha256": canonical_json_sha256(attestation_template_doc),
            },
            "w5_calibration_round02_submission_contract_v1.json": {
                "path": (
                    "data/evaluation/reca_w5/calibration_round02_ops/"
                    "w5_calibration_round02_submission_contract_v1.json"
                ),
                "canonical_lf_sha256": canonical_lf_sha256_file(
                    ROUND02_SUBMISSION_CONTRACT_PATH
                ),
                "canonical_json_sha256": canonical_json_sha256(submission_contract_doc),
            },
        },
        "judge_packages": judge_package_records,
        "presentation_order_hashes": presentation_order_hashes,
    }

    write_json_lf(ROUND02_MANIFEST_PATH, manifest_doc)
    return manifest_doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or validate W5 Calibration Round 02 packages and attestations."
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Deterministically generate all Round 02 calibration artifacts.",
    )
    args = parser.parse_args(argv)
    if args.build:
        manifest = generate_all_round02_artifacts()
        print(
            json.dumps(
                {
                    "status": "BUILT",
                    "round_id": manifest["round_id"],
                    "calibration_version": manifest["calibration_version"],
                    "presentation_order_hashes": manifest["presentation_order_hashes"],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
