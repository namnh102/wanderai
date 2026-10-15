"""Deterministic Scenario Materialization & P11 Freeze Script for W06 (W06-SCENARIO-FREEZE-01).

Materializes the audited 100-slot deterministic W06 scenario dry-run bundle
(seed=2026101506, dry_run_sha256=3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769)
1:1 into:
1. data/evaluation/w06/w06_scenarios_freeze_v1.json
2. data/evaluation/w06/w06_p11_assignment_manifest_v1.json

Scientific Boundaries:
- Does NOT alter generator logic, Method Lock, Support Matrix, Catalog, or REC-A contract.
- Performs strict 1:1 slot mapping (dry-run slot N -> W06-SCENARIO-NNN) with
  fixture_label normalized from "SYNTHETIC_GENERATOR_QA" to None (null).
- Strips all generator/QA audit metadata from BenchmarkScenarioInput objects and
  places audit metadata into P11 only.
- Uses canonical UTF-8 LF JSON serialization (`indent=2, sort_keys=True, ensure_ascii=False`)
  with zero wall-clock timestamps so repeated runs are byte-for-byte deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    DEFAULT_SCENARIO_GENERATION_SEED,
    SCENARIO_GENERATOR_VERSION,
    canonical_json_bytes,
    generate_dry_run_scenarios,
)
from app.schemas.planner_benchmark import BenchmarkScenarioInput  # noqa: E402
from scripts.audit_w06_scenario_generator_dryrun import (  # noqa: E402
    EXPECTED_DRY_RUN_SHA256,
    audit_dry_run_bundle_independently,
)

DEFAULT_SCENARIO_BUNDLE_REL_PATH = "data/evaluation/w06/w06_scenarios_freeze_v1.json"
DEFAULT_P11_REL_PATH = "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"

BENCHMARK_SCENARIO_INPUT_FIELDS: Tuple[str, ...] = (
    "scenario_id",
    "destination_slug",
    "destination",
    "days",
    "start_date",
    "end_date",
    "budget",
    "currency",
    "travel_style",
    "interests",
    "notes",
    "allow_revisit_place_ids",
    "fixture_label",
)

SEMANTIC_1_TO_1_INVARIANT_FIELDS: Tuple[str, ...] = (
    "destination_slug",
    "destination",
    "days",
    "start_date",
    "end_date",
    "budget",
    "currency",
    "travel_style",
    "interests",
    "notes",
    "allow_revisit_place_ids",
)


class ScenarioFreezeError(ValueError):
    """Raised when any W06 scenario freeze precondition or 1:1 invariant fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def serialize_canonical_json_lf(obj: Any) -> bytes:
    """Serialize JSON object to deterministic UTF-8 LF bytes (sort_keys=True, indent=2)."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_canonical_json_lf(obj: Any) -> str:
    """Compute SHA256 hex digest over canonical UTF-8 LF JSON bytes."""
    return hashlib.sha256(serialize_canonical_json_lf(obj)).hexdigest()


def build_frozen_scenario_artifacts(
    *,
    scenario_bundle_rel_path: str = DEFAULT_SCENARIO_BUNDLE_REL_PATH,
) -> Dict[str, Any]:
    """Materialize the final 100-scenario bundle and P11 manifest in memory from the audited generator."""
    dry_run_bundle = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    dry_run_dict = dry_run_bundle.model_dump(mode="json")
    dry_run_sha256 = hashlib.sha256(canonical_json_bytes(dry_run_dict)).hexdigest()

    if dry_run_sha256 != EXPECTED_DRY_RUN_SHA256:
        raise ScenarioFreezeError(
            "DRY_RUN_SHA_MISMATCH",
            f"Dry-run SHA {dry_run_sha256} != expected audited SHA {EXPECTED_DRY_RUN_SHA256}",
        )

    qa_report = audit_dry_run_bundle_independently(dry_run_dict)
    if (
        qa_report["audit_status"] != "PASS"
        or qa_report["slot_count"] != 100
        or qa_report["rule_a_failures"] != 0
        or qa_report["rule_b_failures"] != 0
        or qa_report["excluded_combinations_used"] != 0
        or qa_report["repeat_cap_violations"] != 0
        or qa_report["duplicate_canonical_signatures"] != 0
    ):
        raise ScenarioFreezeError(
            "QA_BASELINE_FAILED",
            f"Independent QA baseline audit did not pass cleanly: {qa_report}",
        )

    slots = dry_run_dict["slots"]
    if len(slots) != 100:
        raise ScenarioFreezeError("SLOT_COUNT_INVALID", f"Expected 100 dry-run slots, got {len(slots)}")

    final_scenarios: List[Dict[str, Any]] = []
    p11_assignments: List[Dict[str, Any]] = []
    seen_scenario_hashes: set[str] = set()

    for expected_idx, slot in enumerate(slots, start=1):
        slot_idx = slot["slot_index"]
        if slot_idx != expected_idx:
            raise ScenarioFreezeError(
                "SLOT_ORDER_VIOLATION",
                f"Expected slot_index={expected_idx}, got {slot_idx}",
            )

        dry_run_scen_id = slot["scenario_id"]
        expected_dry_run_id = f"W06-DRYRUN-{expected_idx:03d}"
        if dry_run_scen_id != expected_dry_run_id:
            raise ScenarioFreezeError(
                "DRY_RUN_ID_VIOLATION",
                f"Expected dry-run ID {expected_dry_run_id}, got {dry_run_scen_id}",
            )

        src_input = slot["scenario_input"]
        if src_input.get("fixture_label") != "SYNTHETIC_GENERATOR_QA":
            raise ScenarioFreezeError(
                "DRY_RUN_FIXTURE_LABEL_VIOLATION",
                f"Expected dry-run fixture_label='SYNTHETIC_GENERATOR_QA', got {src_input.get('fixture_label')!r}",
            )

        final_scen_id = f"W06-SCENARIO-{expected_idx:03d}"
        raw_final_input: Dict[str, Any] = {
            "scenario_id": final_scen_id,
            "destination_slug": src_input["destination_slug"],
            "destination": src_input["destination"],
            "days": src_input["days"],
            "start_date": src_input["start_date"],
            "end_date": src_input["end_date"],
            "budget": src_input["budget"],
            "currency": src_input["currency"],
            "travel_style": src_input["travel_style"],
            "interests": list(src_input["interests"]),
            "notes": src_input["notes"],
            "allow_revisit_place_ids": src_input["allow_revisit_place_ids"],
            "fixture_label": None,
        }

        validated_model = BenchmarkScenarioInput.model_validate(raw_final_input)
        final_scen_dict = validated_model.model_dump(mode="json")

        if tuple(sorted(final_scen_dict.keys())) != tuple(sorted(BENCHMARK_SCENARIO_INPUT_FIELDS)):
            raise ScenarioFreezeError(
                "SCHEMA_FIELD_SET_MISMATCH",
                f"Unexpected fields on {final_scen_id}: {sorted(final_scen_dict.keys())}",
            )

        # Verify strict 1:1 semantic equality across all non-ID/non-fixture fields
        for field_name in SEMANTIC_1_TO_1_INVARIANT_FIELDS:
            if final_scen_dict[field_name] != src_input[field_name]:
                raise ScenarioFreezeError(
                    "SEMANTIC_1_TO_1_MISMATCH",
                    f"Field {field_name!r} differed on slot {expected_idx}: "
                    f"{final_scen_dict[field_name]!r} != {src_input[field_name]!r}",
                )

        if final_scen_dict["currency"] != "VND":
            raise ScenarioFreezeError("CURRENCY_INVALID", f"currency={final_scen_dict['currency']!r}")
        if final_scen_dict["allow_revisit_place_ids"] is not False:
            raise ScenarioFreezeError(
                "ALLOW_REVISIT_INVALID",
                f"allow_revisit_place_ids={final_scen_dict['allow_revisit_place_ids']!r}",
            )
        if final_scen_dict["fixture_label"] is not None:
            raise ScenarioFreezeError(
                "FIXTURE_LABEL_NOT_NULL",
                f"fixture_label={final_scen_dict['fixture_label']!r}",
            )

        scen_sha256 = sha256_canonical_json_lf(final_scen_dict)
        if scen_sha256 in seen_scenario_hashes:
            raise ScenarioFreezeError(
                "DUPLICATE_SCENARIO_SHA256",
                f"Duplicate per-scenario SHA256 {scen_sha256} at {final_scen_id}",
            )
        seen_scenario_hashes.add(scen_sha256)

        final_scenarios.append(final_scen_dict)
        p11_assignments.append(
            {
                "assignment_index": expected_idx,
                "source_slot_index": slot_idx,
                "source_dry_run_scenario_id": dry_run_scen_id,
                "scenario_id": final_scen_id,
                "scenario_sha256": scen_sha256,
                "destination_slug": slot["destination_slug"],
                "days": slot["days"],
                "interest_count": slot["interest_count"],
                "interests": list(slot["interests"]),
                "budget_tier_or_null": slot["budget_tier_or_null"],
                "travel_style": slot["travel_style"],
                "weekend_exposure": slot["weekend_exposure"],
                "support_class": slot["support_class"],
                "canonical_signature": list(slot["canonical_signature"]),
            }
        )

    scenario_bundle: Dict[str, Any] = {
        "artifact_id": "W06-SCENARIOS-FREEZE-01",
        "version": "1.0.0",
        "scenario_count": 100,
        "source_generator_version": SCENARIO_GENERATOR_VERSION,
        "source_seed": DEFAULT_SCENARIO_GENERATION_SEED,
        "source_dry_run_sha256": dry_run_sha256,
        "hash_basis": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
        "scenarios": final_scenarios,
    }
    scenario_bundle_bytes = serialize_canonical_json_lf(scenario_bundle)
    scenario_bundle_sha256 = hashlib.sha256(scenario_bundle_bytes).hexdigest()

    p11_manifest: Dict[str, Any] = {
        "artifact_id": "W06-P11-FROZEN-ASSIGNMENT-MANIFEST",
        "version": "1.0.0",
        "scenario_freeze_id": "W06-SCENARIOS-FREEZE-01",
        "scenario_count": 100,
        "generator_seed": DEFAULT_SCENARIO_GENERATION_SEED,
        "source_dry_run_sha256": dry_run_sha256,
        "scenario_bundle_path": scenario_bundle_rel_path,
        "scenario_bundle_sha256": scenario_bundle_sha256,
        "hash_basis_version": "W06-ARTIFACT-HASH-BASIS-V1",
        "created_before_model_selection": True,
        "created_before_preregistration": True,
        "created_before_final_execution": True,
        "model_output_used": False,
        "assignments": p11_assignments,
    }
    p11_bytes = serialize_canonical_json_lf(p11_manifest)
    p11_sha256 = hashlib.sha256(p11_bytes).hexdigest()

    return {
        "scenario_bundle": scenario_bundle,
        "scenario_bundle_bytes": scenario_bundle_bytes,
        "scenario_bundle_sha256": scenario_bundle_sha256,
        "p11_manifest": p11_manifest,
        "p11_bytes": p11_bytes,
        "p11_sha256": p11_sha256,
        "source_dry_run_sha256": dry_run_sha256,
        "per_scenario_hash_count": len(seen_scenario_hashes),
    }


def write_frozen_scenario_artifacts(
    *,
    scenario_bundle_path: Path = REPO_ROOT / DEFAULT_SCENARIO_BUNDLE_REL_PATH,
    p11_path: Path = REPO_ROOT / DEFAULT_P11_REL_PATH,
    scenario_bundle_rel_path: str = DEFAULT_SCENARIO_BUNDLE_REL_PATH,
) -> Dict[str, Any]:
    """Materialize and write canonical frozen scenario bundle and P11 manifest to disk."""
    built = build_frozen_scenario_artifacts(scenario_bundle_rel_path=scenario_bundle_rel_path)
    scenario_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    p11_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_bundle_path.write_bytes(built["scenario_bundle_bytes"])
    p11_path.write_bytes(built["p11_bytes"])
    return built


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize and freeze the W06 primary 100-scenario bundle and P11 assignment manifest."
    )
    parser.add_argument(
        "--bundle-out",
        type=Path,
        default=REPO_ROOT / DEFAULT_SCENARIO_BUNDLE_REL_PATH,
        help="Output path for w06_scenarios_freeze_v1.json.",
    )
    parser.add_argument(
        "--p11-out",
        type=Path,
        default=REPO_ROOT / DEFAULT_P11_REL_PATH,
        help="Output path for w06_p11_assignment_manifest_v1.json.",
    )
    args = parser.parse_args(argv)

    built = write_frozen_scenario_artifacts(
        scenario_bundle_path=args.bundle_out,
        p11_path=args.p11_out,
    )
    summary = {
        "status": "FROZEN",
        "scenario_count": built["scenario_bundle"]["scenario_count"],
        "per_scenario_hash_count": built["per_scenario_hash_count"],
        "source_dry_run_sha256": built["source_dry_run_sha256"],
        "scenario_bundle_path": str(args.bundle_out.relative_to(REPO_ROOT).as_posix())
        if args.bundle_out.is_relative_to(REPO_ROOT)
        else str(args.bundle_out),
        "scenario_bundle_sha256": built["scenario_bundle_sha256"],
        "p11_path": str(args.p11_out.relative_to(REPO_ROOT).as_posix())
        if args.p11_out.is_relative_to(REPO_ROOT)
        else str(args.p11_out),
        "p11_sha256": built["p11_sha256"],
    }
    sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
