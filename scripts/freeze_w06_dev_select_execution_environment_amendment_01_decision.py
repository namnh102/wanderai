#!/usr/bin/env python3
"""Strictly offline formal methodology-decision freeze script for W06 DEV-SELECT Amendment 01.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-FREEZE

PURPOSE:
Create and statelessly verify the immutable formal methodology-decision freeze artifact
(`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-DECISION-V1`) and its bound
9-cell canary assignment manifest (`W06-DEV-SELECT-AMENDMENT-01-CANARY-ASSIGNMENT-MANIFEST-V1`)
following ChatGPT's `APPROVED_FOR_FORMAL_FREEZE` decision on PREP PR #67.

STRICT FIREWALLS:
- This script freezes the ChatGPT-selected methodology decision ONLY.
- It DOES NOT implement or execute the live amendment (`AMENDED_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_EXECUTED = false`).
- It DOES NOT execute any provider call (`LIVE_PROVIDER_CALLS_NEW = 0`).
- It DOES NOT modify the scientific runner/harness (`SCIENTIFIC_CODE_BUNDLE_SHA256` unchanged).
- It DOES NOT mutate primary DEV-SELECT evidence or results (`PRIMARY_EXPERIMENT_MUTATED = false`).
- It DOES NOT select a model (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`).
- It DOES NOT touch Final100 (`FINAL100_USED = false`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_ENV_KEY_BY_ID,
    CANDIDATE_MODEL_BY_ID,
    CANDIDATE_PROVIDER_BY_ID,
    ORDERED_CANDIDATE_IDS,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    PRACTICAL_TIE_ABS_DIFF_RATIO,
    PRIMARY_DEV_RATE_CRITERIA,
    canonical_json_bytes,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    format_canonical_decimal_str,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS (SECTIONS 1..25)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-FREEZE"
DECISION_ARTIFACT_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-DECISION-V1"
)
CANARY_MANIFEST_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-CANARY-ASSIGNMENT-MANIFEST-V1"
)

DECISION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json"
)
CANARY_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_canary_assignment_manifest_v1.json"
)
DECISION_DOC_REL_PATH = (
    "docs/research/w06_dev_select_execution_environment_amendment_01_decision.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "bc913ed61097f26db8eae87b9fe47d1869dc3ec5"
PREP_BASE_DEVELOP_SHA = "811255a7dd00234d63184ab483e9f88b1f2d8554"
PREP_GATE_STATUS = "CLOSED"
CHATGPT_FINAL_METHODOLOGY_DECISION_FOR_FREEZE = "APPROVED_FOR_FORMAL_FREEZE"
FINAL_METHODOLOGY_DECISION_AUTHORITY = "CHATGPT"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-CHATGPT-AUDIT"
)

PREP_ARTIFACT_REL_PATH = _prep_mod.PREP_ARTIFACT_REL_PATH
EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
)
EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256 = (
    "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_RAW_EVIDENCE_TREE_SHA256 = (
    "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
)
EXPECTED_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256 = (
    "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256 = (
    "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256 = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256 = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)

DEV_FIXTURES_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
EXPECTED_DEV_FIXTURES_FREEZE_SHA256 = (
    "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
)
DEV_FIXTURE_MANIFEST_REL_PATH = "data/evaluation/w06/w06_dev_fixture_manifest_v1.json"
EXPECTED_DEV_FIXTURE_MANIFEST_SHA256 = (
    "15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98"
)
DEV_FINAL_OVERLAP_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json"
)
EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256 = (
    "285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa"
)

DEV_TUNE_EXECUTION_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)

DEV_SELECT_EXECUTION_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
)
EXPECTED_DEV_SELECT_EXECUTION_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_DEV_SELECT_EXECUTION_PLAN_INTERNAL_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
EXPECTED_PROMPT_FREEZE_FILE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
PROMPT_SELECTION_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
EXPECTED_PROMPT_SELECTION_FILE_SHA256 = (
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
)
EXPECTED_PROMPT_SELECTION_INTERNAL_SHA256 = (
    "1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570"
)
EXPECTED_P1_SEMANTIC_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)
EXPECTED_P1_SYSTEM_PROMPT_SHA256 = (
    "4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e"
)
EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)

EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)
EXPECTED_PRIMARY_PROVIDER_CONFIG_SHA256_BY_CANDIDATE: dict[str, str] = {
    "C1": "d4d417bdeff3f4156ac9605f976b46780c1cb0866d87674f1cee51d8bf3f3217",
    "C2": "6201244268383e85106b4d6e6ad0f503e066de9def361cbafa685227e8ba332e",
    "C3": "5ecff5a4e2899245d1cd113285d1193dad17b6ed4e7521bd10be3937650d2a29",
}

# Frozen selected policy IDs & parameters (Sections 1..13)
SELECTED_TRACK_CLASSIFICATION = (
    "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
)
PRIMARY_EXPERIMENT_CLASSIFICATION = (
    "PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK"
)
SELECTED_FAIRNESS_POLICY_ID = "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
SELECTED_TIMEOUT_POLICY_ID = "T3_CANDIDATE_180S"
SELECTED_TIMEOUT_MS = 180000
SELECTED_TIMEOUT_SECONDS = 180
SELECTED_PACING_POLICY_ID = "P1_FIXED_2000MS_INTER_CALL_DELAY"
SELECTED_INTER_CALL_DELAY_MS = 2000
SELECTED_RETRY_POLICY_ID = "R0_STRICT_ZERO_RETRY"
SELECTED_RETRY_COUNT = 0
SELECTED_FIXTURE_POLICY_ID = (
    "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET"
)
SELECTED_CALL_BUDGET_POLICY_ID = "S2_READINESS_CANARY_PLUS_COMPARATIVE_180"

FROZEN_READINESS_CANARY_ASSIGNED_CALLS = 9
FROZEN_COMPARATIVE_ASSIGNED_CALLS = 180
FROZEN_MAXIMUM_GENERATION_CALLS = 189
FROZEN_CALLS_PER_CANDIDATE_MAX = 63

FROZEN_CANARY_FIXTURE_IDS: tuple[str, str, str] = (
    "W06-DEV-TUNE-007",
    "W06-DEV-TUNE-011",
    "W06-DEV-TUNE-015",
)
FROZEN_CANARY_FIXTURE_LABELS: dict[str, str] = {
    "W06-DEV-TUNE-007": "A",
    "W06-DEV-TUNE-011": "B",
    "W06-DEV-TUNE-015": "C",
}

EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
)
EXPECTED_DECISION_ARTIFACT_FILE_SHA256 = (
    "02e154b465c8aab91682568f131727c8612d27fdad18eb3b1ccf6978bf4c4897"
)
EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256 = (
    "566d0869a5b9ae3f648d50cf8bc5cc460eddcb7cc35def9d6df28c4bfb1f7f6d"
)


# ==============================================================================
# 2. DETERMINISTIC HELPERS & GUARDS
# ==============================================================================


def _read_lf_sha256(path: Path) -> str:
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(f"MISSING_REQUIRED_FILE: {path}")
    return sha256_bytes(normalize_lf_bytes(path.read_bytes()))


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(f"MISSING_REQUIRED_JSON_FILE: {path}")
    data = json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))
    if not isinstance(data, dict):
        raise PlanBeforeLiveProtocolError(f"JSON_OBJECT_REQUIRED: {path}")
    return data


def _assert_not_inside_raw_evidence(path: Path, repo_root: Path) -> None:
    resolved = path.resolve()
    raw_root = (repo_root / _prep_mod.RAW_OUTPUT_ROOT_REL_PATH).resolve()
    if resolved == raw_root or raw_root in resolved.parents:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_WRITE_FORBIDDEN: {resolved} is inside {raw_root}"
        )


def _verify_git_base_lineage(repo_root: Path) -> None:
    cat_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{AUTHORITATIVE_BASE_DEVELOP_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if cat_proc.returncode == 0:
        proc = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                AUTHORITATIVE_BASE_DEVELOP_SHA,
                "HEAD",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"GIT_LINEAGE_MISMATCH: HEAD does not descend from authoritative base {AUTHORITATIVE_BASE_DEVELOP_SHA}."
            )


# ==============================================================================
# 3. CANARY ASSIGNMENT MANIFEST & DECISION BUILDERS
# ==============================================================================


def compute_w06_amendment_01_canary_assignment_manifest(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Deterministically compute the 9-cell canary assignment manifest (Sections 8..12)."""
    with NetworkKillSwitchGuard():
        dev_fixtures_path = repo_root / DEV_FIXTURES_FREEZE_REL_PATH
        if _read_lf_sha256(dev_fixtures_path) != EXPECTED_DEV_FIXTURES_FREEZE_SHA256:
            raise PlanBeforeLiveProtocolError("DEV_FIXTURES_FREEZE_SHA256_MISMATCH")

        dev_tune_plan_path = repo_root / DEV_TUNE_EXECUTION_PLAN_REL_PATH
        if (
            _read_lf_sha256(dev_tune_plan_path)
            != EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "DEV_TUNE_EXECUTION_PLAN_FILE_SHA256_MISMATCH"
            )

        dev_bundle = load_and_verify_frozen_dev_bundle()
        if (
            len(dev_bundle.dev_tune_fixtures) != 20
            or len(dev_bundle.dev_select_fixtures) != 60
        ):
            raise PlanBeforeLiveProtocolError("DEV_FIXTURE_BUNDLE_COUNT_MISMATCH")

        raw_dev_doc = _load_json_dict(dev_fixtures_path)
        raw_fixtures_by_id = {
            entry["scenario_id"]: entry for entry in raw_dev_doc["fixtures"]
        }

        dev_tune_plan_doc = _load_json_dict(dev_tune_plan_path)
        if (
            dev_tune_plan_doc.get("plan_sha256")
            != EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256_MISMATCH"
            )

        p1_cells_by_fixture_and_cand: dict[tuple[str, str], dict[str, Any]] = {}
        for cell in dev_tune_plan_doc["cells"]:
            if cell["prompt_id"] == "P1":
                p1_cells_by_fixture_and_cand[
                    (cell["fixture_id"], cell["candidate_id"])
                ] = cell

        selected_fixtures: list[dict[str, Any]] = []
        destinations_seen: list[str] = []
        days_seen: list[int] = []
        interest_counts_seen: list[int] = []

        for fid in FROZEN_CANARY_FIXTURE_IDS:
            if fid not in raw_fixtures_by_id:
                raise PlanBeforeLiveProtocolError(f"MISSING_CANARY_FIXTURE_ID: {fid}")
            raw_fix = raw_fixtures_by_id[fid]
            if raw_fix.get("fixture_label") != "W06_DEV_TUNE":
                raise PlanBeforeLiveProtocolError(
                    f"CANARY_FIXTURE_NOT_DEV_TUNE: {fid}"
                )
            c1_cell = p1_cells_by_fixture_and_cand[(fid, "C1")]
            interest_list = list(raw_fix["interests"])
            interest_count = len(interest_list)
            destinations_seen.append(raw_fix["destination"])
            days_seen.append(int(raw_fix["days"]))
            interest_counts_seen.append(interest_count)

            selected_fixtures.append(
                {
                    "canary_fixture_slot": FROZEN_CANARY_FIXTURE_LABELS[fid],
                    "fixture_id": fid,
                    "source_pool": "W06_DEV_TUNE",
                    "source_file": DEV_FIXTURES_FREEZE_REL_PATH,
                    "source_file_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
                    "destination": raw_fix["destination"],
                    "destination_slug": raw_fix["destination_slug"],
                    "days": int(raw_fix["days"]),
                    "interest_count": interest_count,
                    "interests": interest_list,
                    "budget": raw_fix["budget"],
                    "currency": raw_fix["currency"],
                    "travel_style": raw_fix["travel_style"],
                    "start_date": raw_fix["start_date"],
                    "end_date": raw_fix["end_date"],
                    "allow_revisit_place_ids": bool(raw_fix["allow_revisit_place_ids"]),
                    "scenario_sha256": c1_cell["scenario_sha256"],
                    "catalog_context_sha256": c1_cell["catalog_context_sha256"],
                    "p1_system_prompt_sha256": c1_cell["system_prompt_sha256"],
                    "p1_user_prompt_sha256": c1_cell["user_prompt_sha256"],
                }
            )

        # Verify exact structural coverage (Section 8)
        if set(destinations_seen) != {"Hà Nội", "Đà Nẵng", "Hạ Long"} or len(
            destinations_seen
        ) != 3:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_DESTINATION_BALANCE_INVALID: {destinations_seen}"
            )
        if set(days_seen) != {2, 3, 4} or len(days_seen) != 3:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_DAYS_BALANCE_INVALID: {days_seen}"
            )
        if set(interest_counts_seen) != {1, 2, 3} or len(interest_counts_seen) != 3:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_INTEREST_COUNT_BALANCE_INVALID: {interest_counts_seen}"
            )

        # Build exact 9-cell matrix in frozen order 01..09 (Section 9)
        canary_cells: list[dict[str, Any]] = []
        order_idx = 0
        for fid in FROZEN_CANARY_FIXTURE_IDS:
            raw_fix = raw_fixtures_by_id[fid]
            for cid in ORDERED_CANDIDATE_IDS:
                order_idx += 1
                ref_cell = p1_cells_by_fixture_and_cand[(fid, cid)]
                order_code = f"{order_idx:02d}"
                canary_cells.append(
                    {
                        "order_index": order_idx,
                        "order_code": order_code,
                        "matrix_label": f"{order_code} {fid} × {cid}",
                        "cell_id": f"W06-AMENDMENT-01-CANARY-{order_code}-P1-{cid}-{fid}",
                        "canary_fixture_slot": FROZEN_CANARY_FIXTURE_LABELS[fid],
                        "fixture_id": fid,
                        "destination": raw_fix["destination"],
                        "destination_slug": raw_fix["destination_slug"],
                        "days": int(raw_fix["days"]),
                        "interest_count": len(raw_fix["interests"]),
                        "candidate_id": cid,
                        "provider": CANDIDATE_PROVIDER_BY_ID[cid],
                        "requested_model_id": CANDIDATE_MODEL_BY_ID[cid],
                        "prompt_id": "P1",
                        "attempt_number": 1,
                        "selection_weight": 0,
                        "timeout_ms": SELECTED_TIMEOUT_MS,
                        "inter_call_delay_ms_before_next_cell": (
                            SELECTED_INTER_CALL_DELAY_MS if order_idx < 9 else 0
                        ),
                        "retry": 0,
                        "automatic_retry": 0,
                        "transport_retry": 0,
                        "manual_retry": 0,
                        "llm_repair": 0,
                        "semantic_repair": 0,
                        "fallback": False,
                        "tools": False,
                        "max_output_tokens": int(ref_cell["max_output_tokens"]),
                        "sampling_reasoning_configuration": dict(
                            ref_cell["sampling_reasoning_configuration"]
                        ),
                        "scenario_sha256": ref_cell["scenario_sha256"],
                        "catalog_context_sha256": ref_cell["catalog_context_sha256"],
                        "system_prompt_sha256": ref_cell["system_prompt_sha256"],
                        "user_prompt_sha256": ref_cell["user_prompt_sha256"],
                        "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
                        "primary_baseline_provider_config_sha256": EXPECTED_PRIMARY_PROVIDER_CONFIG_SHA256_BY_CANDIDATE[
                            cid
                        ],
                        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
                    }
                )

        if len(canary_cells) != FROZEN_READINESS_CANARY_ASSIGNED_CALLS:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_CELL_COUNT_MISMATCH: expected 9, got {len(canary_cells)}"
            )

        manifest_without_self_hash: dict[str, Any] = {
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "alternate_fixtures_permitted": False,
            "assigned_canary_cells": FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "calls_per_candidate": {"C1": 3, "C2": 3, "C3": 3},
            "candidate_ids": list(ORDERED_CANDIDATE_IDS),
            "cells": canary_cells,
            "dev_fixtures_freeze_file": DEV_FIXTURES_FREEZE_REL_PATH,
            "dev_fixtures_freeze_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
            "dev_tune_execution_plan_file": DEV_TUNE_EXECUTION_PLAN_REL_PATH,
            "dev_tune_execution_plan_file_sha256": EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256,
            "dev_tune_execution_plan_internal_sha256": EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256,
            "fixture_count": 3,
            "fixture_ids": list(FROZEN_CANARY_FIXTURE_IDS),
            "fixture_selection_rationale": {
                "method": "DETERMINISTIC_STRUCTURAL_COVERAGE_ONLY",
                "prior_canary_success_or_failure_used": False,
                "prior_model_quality_output_used": False,
                "rationale_statement": (
                    "Chosen by deterministic structural coverage only: all 3 destinations ({Hà Nội, Đà Nẵng, Hạ Long}) "
                    "covered exactly once, day counts ({2, 3, 4}) covered exactly once, and interest counts ({1, 2, 3}) "
                    "covered exactly once. No prior model-quality output or prior canary success/failure was used to justify these fixture IDs."
                ),
                "structural_coverage_verification": {
                    "all_3_destinations_exactly_once": True,
                    "day_counts_2_3_4_exactly_once": True,
                    "destinations": ["Hà Nội", "Đà Nẵng", "Hạ Long"],
                    "days": [4, 3, 2],
                    "interest_counts": [3, 2, 1],
                    "interest_counts_1_2_3_exactly_once": True,
                },
            },
            "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
            "manifest_id": CANARY_MANIFEST_ID,
            "pacing_policy_id": SELECTED_PACING_POLICY_ID,
            "prompt_id": "P1",
            "reruns_permitted": False,
            "retries_permitted": False,
            "retry_policy_id": SELECTED_RETRY_POLICY_ID,
            "selected_fixtures": selected_fixtures,
            "selection_weight": 0,
            "task_id": TASK_ID,
            "timeout_ms": SELECTED_TIMEOUT_MS,
            "timeout_policy_id": SELECTED_TIMEOUT_POLICY_ID,
            "total_inter_cell_pacing_intervals": 8,
            "total_inter_cell_pacing_ms": 8 * SELECTED_INTER_CALL_DELAY_MS,
        }

        manifest_internal_sha = sha256_bytes(
            canonical_json_bytes(manifest_without_self_hash)
        )
        full_manifest = dict(manifest_without_self_hash)
        full_manifest["canary_manifest_internal_sha256"] = manifest_internal_sha
        assert_no_secrets_in_payload(
            full_manifest, context="W06_AMENDMENT_01_CANARY_MANIFEST"
        )
        return full_manifest


def compute_w06_execution_environment_amendment_decision_payload(
    repo_root: Path = REPO_ROOT,
    canary_manifest_file_sha256: str | None = None,
) -> dict[str, Any]:
    """Deterministically compute `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-DECISION-V1`."""
    with NetworkKillSwitchGuard():
        _verify_git_base_lineage(repo_root)

        # 1. Verify upstream PREP, Results Freeze, and Diagnostic verifiers
        prep_summary = _prep_mod.verify_w06_execution_environment_amendment_prep(
            repo_root=repo_root
        )
        if not prep_summary.get("verified"):
            raise PlanBeforeLiveProtocolError("UPSTREAM_PREP_VERIFICATION_FAILED")
        if (
            prep_summary["prep_artifact_file_sha256"]
            != EXPECTED_PREP_ARTIFACT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError("PREP_ARTIFACT_FILE_SHA256_MISMATCH")
        if (
            prep_summary["prep_artifact_internal_sha256"]
            != EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError("PREP_ARTIFACT_INTERNAL_SHA256_MISMATCH")

        freeze_summary = (
            _freeze_mod.verify_committed_results_freeze_artifacts_from_disk(
                repo_root=repo_root, verify_preflight_dry_run=False
            )
        )
        if not freeze_summary.get("verified"):
            raise PlanBeforeLiveProtocolError("UPSTREAM_FREEZE_VERIFICATION_FAILED")

        diag_summary = _diag_mod.verify_w06_dev_select_failure_diagnostic(
            repo_root=repo_root
        )
        if not diag_summary.get("verified"):
            raise PlanBeforeLiveProtocolError(
                "UPSTREAM_DIAGNOSTIC_VERIFICATION_FAILED"
            )

        # 2. Verify scientific code bundle, candidate registry, and Final100 firewall
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root)
        if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: {bundle_sha}"
            )

        cand_reg = load_and_verify_candidate_registry()
        if cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256:
            raise PlanBeforeLiveProtocolError("CANDIDATE_REGISTRY_SHA256_MISMATCH")
        if (
            compute_provider_config_registry_sha256(cand_reg)
            != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH"
            )

        final100_path = repo_root / _freeze_mod.FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
        p11_path = repo_root / _freeze_mod.FORBIDDEN_P11_MANIFEST_REL_PATH
        if _read_lf_sha256(final100_path) != FORBIDDEN_FINAL100_BUNDLE_SHA256:
            raise PlanBeforeLiveProtocolError("FINAL100_SCENARIOS_SHA256_MISMATCH")
        if _read_lf_sha256(p11_path) != FORBIDDEN_P11_MANIFEST_SHA256:
            raise PlanBeforeLiveProtocolError("P11_MANIFEST_SHA256_MISMATCH")

        if (
            _read_lf_sha256(repo_root / PROMPT_FREEZE_REL_PATH)
            != EXPECTED_PROMPT_FREEZE_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError("PROMPT_FREEZE_FILE_SHA256_MISMATCH")
        if (
            _read_lf_sha256(repo_root / PROMPT_SELECTION_REL_PATH)
            != EXPECTED_PROMPT_SELECTION_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError("PROMPT_SELECTION_FILE_SHA256_MISMATCH")
        if (
            _read_lf_sha256(repo_root / DEV_SELECT_EXECUTION_PLAN_REL_PATH)
            != EXPECTED_DEV_SELECT_EXECUTION_PLAN_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "DEV_SELECT_EXECUTION_PLAN_FILE_SHA256_MISMATCH"
            )

        # 3. Compute canary manifest and verify file SHA256
        canary_manifest = compute_w06_amendment_01_canary_assignment_manifest(
            repo_root=repo_root
        )
        if canary_manifest_file_sha256 is None:
            canary_serialized = (
                json.dumps(
                    canary_manifest, indent=2, sort_keys=True, ensure_ascii=False
                )
                + "\n"
            )
            canary_manifest_file_sha256 = sha256_bytes(
                normalize_lf_bytes(canary_serialized.encode("utf-8"))
            )

        prep_payload = _load_json_dict(repo_root / PREP_ARTIFACT_REL_PATH)
        diag_payload = _load_json_dict(
            repo_root / _prep_mod.EXPECTED_DIAGNOSTIC_ARTIFACT_REL_PATH
        )

        operational_pass_conditions = [
            "correct_frozen_candidate_and_config_requested",
            "exactly_1_outbound_generation_request_attempted",
            "retry_count_equals_0",
            "no_api_auth_rejection",
            "no_billing_or_credit_rejection",
            "no_quota_or_rate_limit_rejection",
            "no_model_access_rejection",
            "no_client_timeout",
            "no_provider_transport_failure",
            "no_http_or_provider_4xx_5xx_failure",
            "successful_provider_response_received",
            "request_and_cell_identity_evidence_valid",
            "returned_model_identity_when_supplied_by_provider_does_not_mismatch_frozen_candidate",
        ]

        payload_without_self_hash: dict[str, Any] = {
            "AMENDED_CANARY_LIVE_AUTHORIZED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "AMENDMENT_APPROVED": False,
            "AMENDMENT_METHODOLOGY_SELECTED": True,
            "CHATGPT_FINAL_METHODOLOGY_DECISION_FOR_FREEZE": CHATGPT_FINAL_METHODOLOGY_DECISION_FOR_FREEZE,
            "FINAL100_USED": False,
            "FINAL_METHODOLOGY_DECISION_AUTHORITY": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "MODEL_WINNER_SELECTED": False,
            "PREP_GATE": PREP_GATE_STATUS,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "amended_canary_live_authorized": False,
            "amended_comparative_live_authorized": False,
            "amended_live_authorized": False,
            "amended_live_executed": False,
            "amendment_approved": False,
            "amendment_methodology_selected": True,
            "amendment_status_lifecycle": {
                "amended_canary_live_authorized": False,
                "amended_comparative_live_authorized": False,
                "amended_live_authorized": False,
                "amended_live_executed": False,
                "amendment_approved": False,
                "amendment_approved_transition_rule": (
                    "AMENDMENT_APPROVED remains false in this formal decision freeze PR and may become true only "
                    "in the authoritative decision receipt after ChatGPT audits and merges this formal-decision PR."
                ),
                "amendment_methodology_selected": True,
                "live_provider_calls_new": 0,
            },
            "artifact_id": DECISION_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "bound_authorities": {
                "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
                "canary_manifest_file_sha256": canary_manifest_file_sha256,
                "canary_manifest_internal_sha256": canary_manifest[
                    "canary_manifest_internal_sha256"
                ],
                "canary_manifest_path": CANARY_MANIFEST_REL_PATH,
                "candidate_registry_sha256": EXPECTED_CANDIDATE_REGISTRY_SHA256,
                "dev_final_overlap_receipt_sha256": EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256,
                "dev_fixture_manifest_sha256": EXPECTED_DEV_FIXTURE_MANIFEST_SHA256,
                "dev_fixtures_freeze_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
                "dev_select_execution_plan_file_sha256": EXPECTED_DEV_SELECT_EXECUTION_PLAN_FILE_SHA256,
                "dev_select_execution_plan_internal_sha256": EXPECTED_DEV_SELECT_EXECUTION_PLAN_INTERNAL_SHA256,
                "dev_tune_execution_plan_file_sha256": EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256,
                "dev_tune_execution_plan_internal_sha256": EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256,
                "diagnostic_artifact_file_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256,
                "diagnostic_artifact_internal_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256,
                "p1_semantic_prompt_sha256": EXPECTED_P1_SEMANTIC_SHA256,
                "p1_system_prompt_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
                "p1_user_prompt_template_sha256": EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
                "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                "prep_artifact_file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
                "prep_artifact_internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
                "prep_base_develop_sha": PREP_BASE_DEVELOP_SHA,
                "primary_provider_config_sha256_by_candidate": dict(
                    EXPECTED_PRIMARY_PROVIDER_CONFIG_SHA256_BY_CANDIDATE
                ),
                "primary_raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
                "primary_results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                "primary_results_freeze_receipt_internal_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
                "primary_results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
                "primary_results_manifest_internal_sha256": EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256,
                "prompt_freeze_file_sha256": EXPECTED_PROMPT_FREEZE_FILE_SHA256,
                "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
                "prompt_selection_file_sha256": EXPECTED_PROMPT_SELECTION_FILE_SHA256,
                "prompt_selection_internal_sha256": EXPECTED_PROMPT_SELECTION_INTERNAL_SHA256,
                "provider_config_registry_sha256": EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
                "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
                "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
            },
            "canary_call_matrix_and_order": {
                "all_9_cells_assigned_once": True,
                "alternate_fixtures_permitted": False,
                "assigned_cell_count": FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
                "canary_manifest_file_sha256": canary_manifest_file_sha256,
                "canary_manifest_internal_sha256": canary_manifest[
                    "canary_manifest_internal_sha256"
                ],
                "canary_manifest_path": CANARY_MANIFEST_REL_PATH,
                "cells": canary_manifest["cells"],
                "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
                "matrix_summary": [
                    cell["matrix_label"] for cell in canary_manifest["cells"]
                ],
                "reruns_permitted": False,
                "retries_permitted": False,
            },
            "canary_fixtures": {
                "bound_fixture_source_file": DEV_FIXTURES_FREEZE_REL_PATH,
                "bound_fixture_source_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
                "fixture_count": 3,
                "fixture_ids": list(FROZEN_CANARY_FIXTURE_IDS),
                "fixture_selection_rationale": canary_manifest[
                    "fixture_selection_rationale"
                ],
                "fixtures": canary_manifest["selected_fixtures"],
            },
            "canary_gate_and_operational_pass_rules": {
                "canary_gate_rule": {
                    "action_on_any_failure": "RETURN_TO_CHATGPT_HOLD",
                    "automatic_adjustments_on_failure_permitted": {
                        "automatic_pacing_change": False,
                        "automatic_prompt_or_model_or_schema_modification": False,
                        "automatic_provider_specific_parameter_change": False,
                        "automatic_replacement_fixture": False,
                        "automatic_rerun": False,
                        "automatic_retry": False,
                        "automatic_timeout_increase": False,
                    },
                    "if_any_single_cell_operationally_fails": {
                        "AMENDED_COMPARATIVE_AUTHORIZED": False,
                        "CANARY_GATE_PASS": False,
                        "next_status": "CHATGPT_HOLD",
                    },
                    "required_operational_pass_cell_count": 9,
                    "total_assigned_canary_cells": 9,
                },
                "canary_selection_weight_policy": {
                    "can_alter_prompt_model_schema_or_evaluator_parameters": False,
                    "can_contribute_to_dev_select_comparative_denominator": False,
                    "can_contribute_to_final100": False,
                    "can_contribute_to_stochasticity": False,
                    "can_select_model_winner": False,
                    "selection_weight": 0,
                },
                "operational_canary_cell_pass_rule": {
                    "all_conditions_required_for_operational_pass": operational_pass_conditions,
                    "planner_quality_firewall": {
                        "excluded_planner_quality_metrics": [
                            "VALID_RUN_AND_SCHEMA_RATE",
                            "EXACT_GROUNDING_PASS_RATE",
                            "OPENING_HOUR_COMPLIANCE",
                            "BUDGET_METRIC",
                            "FINAL_CORE_PASS",
                        ],
                        "planner_quality_determines_operational_pass_or_fail": False,
                        "rule_statement": (
                            "Schema validity, exact grounding, opening-hour compliance, budget metric, or FINAL_CORE_PASS "
                            "MUST NOT determine operational canary PASS/FAIL. A successful provider response that fails "
                            "schema/core evaluation remains OPERATIONAL PASS."
                        ),
                        "successful_provider_response_failing_schema_or_core_is_operational_pass": True,
                    },
                },
            },
            "comparative_batch_policy": {
                "assigned_comparative_cells": FROZEN_COMPARATIVE_ASSIGNED_CALLS,
                "calls_per_candidate": {"C1": 60, "C2": 60, "C3": 60},
                "canary_pass_automatically_launches_comparative_execution": False,
                "candidate_ids": list(ORDERED_CANDIDATE_IDS),
                "comparative_fixture_count": 60,
                "comparative_fixture_id_range": "W06-DEV-SELECT-001..W06-DEV-SELECT-060",
                "comparative_fixture_source_file": DEV_FIXTURES_FREEZE_REL_PATH,
                "comparative_fixture_source_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
                "evaluator_semantics_unchanged": True,
                "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
                "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                "portable_generation_schema_v2_unchanged": True,
                "practical_tie_survivor_threshold_cells": 6,
                "practical_tie_survivor_threshold_denominator": 60,
                "practical_tie_survivor_threshold_percentage_points": 10,
                "practical_tie_survivor_threshold_ratio": format_canonical_decimal_str(
                    PRACTICAL_TIE_ABS_DIFF_RATIO
                ),
                "practical_tie_survivor_threshold_unchanged": True,
                "prerequisite_1_future_canary_audited_pass_by_chatgpt": True,
                "prerequisite_2_separate_chatgpt_comparative_authorization_gate": True,
                "primary_model_selection_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                "prompt_id": "P1",
                "prompt_unchanged": True,
                "retry": 0,
                "separate_chatgpt_authorization_gate_required_before_180_comparative_calls": True,
                "timeout_ms": SELECTED_TIMEOUT_MS,
            },
            "final100_firewall": {
                "final100_calibration_forbidden": True,
                "final100_execution_forbidden": True,
                "final100_scenarios_file_sha256": FORBIDDEN_FINAL100_BUNDLE_SHA256,
                "final100_status": "NO-GO",
                "final100_used": False,
                "p11_manifest_file_sha256": FORBIDDEN_P11_MANIFEST_SHA256,
            },
            "final100_used": False,
            "final_methodology_decision_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "frozen_scientific_invariants": {
                "candidate_models": dict(CANDIDATE_MODEL_BY_ID),
                "candidate_reasoning_and_thinking_settings": {
                    "C1": {"seed": 2026101508, "thinking_level": "medium"},
                    "C2": {
                        "reasoning_effort": "medium",
                        "seed": 2026101508,
                        "service_tier": "default",
                    },
                    "C3": {"effort": "high", "thinking": {"type": "adaptive"}},
                },
                "candidate_reasoning_settings_unchanged": True,
                "candidates_unchanged": True,
                "evaluator_semantics_unchanged": True,
                "final100_unchanged": True,
                "fourth_model_addition_forbidden": True,
                "fourth_model_added": False,
                "max_output_tokens": 16384,
                "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                "portable_schema_v2_unchanged": True,
                "practical_tie_rule_unchanged": True,
                "primary_180_evidence_and_results_unchanged": True,
                "primary_selection_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                "primary_selection_metrics_unchanged": True,
                "prompt_id": "P1",
                "prompt_p1_unchanged": True,
                "retry0_unchanged": True,
                "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
                "semantic_schema_unchanged": True,
            },
            " frozen_selected_policy_bundle".strip(): {
                "call_budget_policy": {
                    "call_budget_policy_id": SELECTED_CALL_BUDGET_POLICY_ID,
                    "calls_per_candidate_max": FROZEN_CALLS_PER_CANDIDATE_MAX,
                    "canary_assigned_calls_by_candidate": {
                        "C1": 3,
                        "C2": 3,
                        "C3": 3,
                    },
                    "comparative_assigned_calls": FROZEN_COMPARATIVE_ASSIGNED_CALLS,
                    "comparative_assigned_calls_by_candidate": {
                        "C1": 60,
                        "C2": 60,
                        "C3": 60,
                    },
                    "exact_canary_assigned_matrix_cells": FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
                    "maximum_generation_calls": FROZEN_MAXIMUM_GENERATION_CALLS,
                    "readiness_canary_assigned_calls": FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
                    "total_calls_per_candidate_max": {
                        "C1": 63,
                        "C2": 63,
                        "C3": 63,
                    },
                    "variable_canary_range_removed": True,
                },
                "fairness_policy_id": SELECTED_FAIRNESS_POLICY_ID,
                "fixture_policy_id": SELECTED_FIXTURE_POLICY_ID,
                "pacing_policy": {
                    "adaptive": False,
                    "deterministic": True,
                    "fixed": True,
                    "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
                    "pacing_policy_id": SELECTED_PACING_POLICY_ID,
                    "prevents_provider_http_503_or_high_demand_failures_claimed": False,
                    "response_dependent": False,
                    "scientific_wording": (
                        "Pacing bounds client-issued request cadence only. "
                        "It MUST NOT be claimed to prevent provider HTTP 503/high-demand failures."
                    ),
                },
                "retry_policy": {
                    "automatic_retry": 0,
                    "fallback": False,
                    "llm_repair": 0,
                    "manual_retry": 0,
                    "retry": 0,
                    "retry_policy_id": SELECTED_RETRY_POLICY_ID,
                    "semantic_repair": 0,
                    "transport_retry": 0,
                },
                "timeout_policy": {
                    "applied_symmetrically_to_candidates": list(ORDERED_CANDIDATE_IDS),
                    "guarantees_completion": False,
                    "scientific_wording": (
                        "This removes the frozen 55s client-side cutoff from the secondary configuration and materially "
                        "reduces client-side right-censoring risk. It does NOT guarantee completion. Provider-side deadlines, "
                        "capacity failures, quota errors, or other transport failures may still prevent observation."
                    ),
                    "timeout_ms": SELECTED_TIMEOUT_MS,
                    "timeout_ms_by_candidate": {
                        "C1": SELECTED_TIMEOUT_MS,
                        "C2": SELECTED_TIMEOUT_MS,
                        "C3": SELECTED_TIMEOUT_MS,
                    },
                    "timeout_policy_id": SELECTED_TIMEOUT_POLICY_ID,
                    "timeout_seconds": SELECTED_TIMEOUT_SECONDS,
                },
                "track_classification": SELECTED_TRACK_CLASSIFICATION,
            },
            "live_provider_calls_new": 0,
            "model_winner_selected": False,
            "next_gate": NEXT_GATE_ID,
            "prep_gate": PREP_GATE_STATUS,
            "pricing_and_cost_boundary": {
                "current_price_input_status": "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION",
                "envelope_nature": (
                    "Historical LOW/HIGH envelopes from frozen repository price snapshots remain planning references only; "
                    "they are not hard cost caps."
                ),
                "hard_maximum_claimed": False,
                "historical_s2_189_call_envelopes_reference": {
                    "preflight_01d_2026_10_17_snapshot": prep_payload["cost_planning"][
                        "envelopes_by_call_budget_under_preflight_01d_2026_10_17_pricing"
                    ]["S2_189_CALLS_63_PER_CANDIDATE"],
                    "runner_registry_2026_10_16_snapshot": prep_payload[
                        "cost_planning"
                    ][
                        "envelopes_by_call_budget_under_runner_registry_2026_10_16_pricing"
                    ]["S2_189_CALLS_63_PER_CANDIDATE"],
                },
                "live_pricing_calls_performed_in_decision_freeze": 0,
            },
            "primary_denominators_changed": False,
            "primary_experiment_immutability": {
                "classification": PRIMARY_EXPERIMENT_CLASSIFICATION,
                "primary_counts_by_candidate": diag_payload[
                    "primary_counts_by_candidate"
                ],
                "primary_counts_total": diag_payload["primary_counts_total"],
                "primary_denominators_by_candidate": {"C1": 60, "C2": 60, "C3": 60},
                "primary_denominators_changed": False,
                "primary_experiment_mutated": False,
                "primary_results_replaced": False,
                "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
                "reclassification_or_rerun_or_replacement_permitted": False,
                "results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                "results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
            },
            "primary_experiment_mutated": False,
            "primary_results_replaced": False,
            "provider_readiness_boundary": {
                "candidates": {
                    "C1": {
                        "candidate_id": "C1",
                        "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C1"],
                        "max_authorized_calls_under_s2": 63,
                        "no_free_tier_20_rpd_ceiling_required": True,
                        "paid_or_billing_enabled_tier_required": True,
                        "provider": CANDIDATE_PROVIDER_BY_ID["C1"],
                        "quota_and_rate_limit_requirement": (
                            "Paid/billing-enabled tier with daily/request quota and RPM/TPM limits sufficient for the exact "
                            "total authorized C1 call count (under selected S2 = max 63 C1 calls), with no Free Tier 20-RPD ceiling."
                        ),
                        "requested_model_id": CANDIDATE_MODEL_BY_ID["C1"],
                    },
                    "C2": {
                        "active_billing_or_credit_required": True,
                        "candidate_id": "C2",
                        "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C2"],
                        "max_authorized_calls_under_s2": 63,
                        "model_access_required": True,
                        "provider": CANDIDATE_PROVIDER_BY_ID["C2"],
                        "quota_and_rate_limit_requirement": (
                            "Active billing/credit, verified model access, and sufficient account limits for the exact "
                            "authorized C2 volume (under selected S2 = max 63 C2 calls) under the 180,000 ms client timeout."
                        ),
                        "requested_model_id": CANDIDATE_MODEL_BY_ID["C2"],
                    },
                    "C3": {
                        "active_billing_required": True,
                        "candidate_id": "C3",
                        "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C3"],
                        "max_authorized_calls_under_s2": 63,
                        "model_access_required": True,
                        "positive_credits_sufficient_for_exact_authorized_volume_required": True,
                        "provider": CANDIDATE_PROVIDER_BY_ID["C3"],
                        "quota_and_rate_limit_requirement": (
                            "Active billing, positive credits sufficient for the exact authorized C3 volume "
                            "(under selected S2 = max 63 C3 calls), and verified model access."
                        ),
                        "requested_model_id": CANDIDATE_MODEL_BY_ID["C3"],
                    },
                },
                "owner_and_provider_attestation_separate_from_live_readiness_canary": True,
                "separation_contract": {
                    "LIVE_READINESS_CANARY": (
                        "9-cell operational readiness probe (3 fixtures x 3 candidates) under the frozen amended configuration; "
                        "3 canary calls per candidate do not prove quota sufficiency for 63 calls and do not prove absence of "
                        "later capacity or deadline failures."
                    ),
                    "OWNER_AND_PROVIDER_ATTESTATION": (
                        "Pre-authorization administrative/account attestation that billing is active, daily/request quota and "
                        "RPM/TPM limits are sufficient for the exact authorized call count (max 63 per candidate under S2, with "
                        "no Free Tier 20-RPD ceiling on C1), positive credits cover the authorized volume, and model access is enabled."
                    ),
                },
                "secret_safety_invariants": {
                    "print_billing_or_project_or_org_ids": False,
                    "print_secret_hashes": False,
                    "print_secret_prefixes_or_suffixes": False,
                    "print_secret_values": False,
                },
            },
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "selected_model_id": None,
            "stochasticity_execution_started": False,
            "task_id": TASK_ID,
        }

        decision_internal_sha = sha256_bytes(
            canonical_json_bytes(payload_without_self_hash)
        )
        full_payload = dict(payload_without_self_hash)
        full_payload["decision_artifact_internal_sha256"] = decision_internal_sha
        assert_no_secrets_in_payload(
            full_payload, context="W06_AMENDMENT_01_DECISION_PAYLOAD"
        )
        return full_payload


def write_w06_execution_environment_amendment_decision_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Write the canary assignment manifest and formal methodology-decision freeze JSON artifacts."""
    canary_path = repo_root / CANARY_MANIFEST_REL_PATH
    decision_path = repo_root / DECISION_ARTIFACT_REL_PATH
    _assert_not_inside_raw_evidence(canary_path, repo_root)
    _assert_not_inside_raw_evidence(decision_path, repo_root)

    canary_manifest = compute_w06_amendment_01_canary_assignment_manifest(
        repo_root=repo_root
    )
    canary_serialized = (
        json.dumps(canary_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    canary_path.parent.mkdir(parents=True, exist_ok=True)
    canary_path.write_bytes(canary_serialized.encode("utf-8"))
    canary_file_sha = _read_lf_sha256(canary_path)

    decision_payload = compute_w06_execution_environment_amendment_decision_payload(
        repo_root=repo_root,
        canary_manifest_file_sha256=canary_file_sha,
    )
    decision_serialized = (
        json.dumps(decision_payload, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_bytes(decision_serialized.encode("utf-8"))
    decision_file_sha = _read_lf_sha256(decision_path)

    return {
        "canary_manifest_file_sha256": canary_file_sha,
        "canary_manifest_internal_sha256": canary_manifest[
            "canary_manifest_internal_sha256"
        ],
        "canary_manifest_path": CANARY_MANIFEST_REL_PATH,
        "decision_artifact_file_sha256": decision_file_sha,
        "decision_artifact_internal_sha256": decision_payload[
            "decision_artifact_internal_sha256"
        ],
        "decision_artifact_path": DECISION_ARTIFACT_REL_PATH,
    }


def verify_w06_execution_environment_amendment_decision_freeze(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Statelessly verify the formal decision freeze artifact, canary manifest, and all upstream bindings."""
    with NetworkKillSwitchGuard():
        canary_path = repo_root / CANARY_MANIFEST_REL_PATH
        decision_path = repo_root / DECISION_ARTIFACT_REL_PATH
        if not canary_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_CANARY_MANIFEST_ARTIFACT: {canary_path}"
            )
        if not decision_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_DECISION_ARTIFACT: {decision_path}"
            )

        # 1. Verify canary manifest
        computed_canary = compute_w06_amendment_01_canary_assignment_manifest(
            repo_root=repo_root
        )
        disk_canary = _load_json_dict(canary_path)
        assert_no_secrets_in_payload(
            disk_canary, context="W06_AMENDMENT_01_CANARY_MANIFEST_DISK"
        )
        disk_canary_without_hash = dict(disk_canary)
        disk_canary_internal_sha = disk_canary_without_hash.pop(
            "canary_manifest_internal_sha256", None
        )
        recomputed_canary_internal_sha = sha256_bytes(
            canonical_json_bytes(disk_canary_without_hash)
        )
        if disk_canary_internal_sha != recomputed_canary_internal_sha:
            raise PlanBeforeLiveProtocolError(
                "CANARY_MANIFEST_INTERNAL_SHA256_TAMPERED"
            )
        if disk_canary != computed_canary:
            raise PlanBeforeLiveProtocolError(
                "CANARY_MANIFEST_CONTENT_DRIFT_FROM_DETERMINISTIC_COMPUTATION"
            )
        canary_file_sha = _read_lf_sha256(canary_path)
        if (
            EXPECTED_CANARY_MANIFEST_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and canary_file_sha != EXPECTED_CANARY_MANIFEST_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_MANIFEST_FILE_SHA256_MISMATCH: expected {EXPECTED_CANARY_MANIFEST_FILE_SHA256}, got {canary_file_sha}"
            )
        if (
            EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and disk_canary_internal_sha != EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_MANIFEST_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256}, got {disk_canary_internal_sha}"
            )

        # 2. Verify decision artifact
        computed_decision = (
            compute_w06_execution_environment_amendment_decision_payload(
                repo_root=repo_root,
                canary_manifest_file_sha256=canary_file_sha,
            )
        )
        disk_decision = _load_json_dict(decision_path)
        assert_no_secrets_in_payload(
            disk_decision, context="W06_AMENDMENT_01_DECISION_DISK"
        )
        disk_decision_without_hash = dict(disk_decision)
        disk_decision_internal_sha = disk_decision_without_hash.pop(
            "decision_artifact_internal_sha256", None
        )
        recomputed_decision_internal_sha = sha256_bytes(
            canonical_json_bytes(disk_decision_without_hash)
        )
        if disk_decision_internal_sha != recomputed_decision_internal_sha:
            raise PlanBeforeLiveProtocolError(
                "DECISION_ARTIFACT_INTERNAL_SHA256_TAMPERED"
            )
        if disk_decision != computed_decision:
            raise PlanBeforeLiveProtocolError(
                "DECISION_ARTIFACT_CONTENT_DRIFT_FROM_DETERMINISTIC_COMPUTATION"
            )
        decision_file_sha = _read_lf_sha256(decision_path)
        if (
            EXPECTED_DECISION_ARTIFACT_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and decision_file_sha != EXPECTED_DECISION_ARTIFACT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"DECISION_ARTIFACT_FILE_SHA256_MISMATCH: expected {EXPECTED_DECISION_ARTIFACT_FILE_SHA256}, got {decision_file_sha}"
            )
        if (
            EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and disk_decision_internal_sha != EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"DECISION_ARTIFACT_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256}, got {disk_decision_internal_sha}"
            )

        return {
            "amended_canary_live_authorized": False,
            "amended_comparative_live_authorized": False,
            "amended_live_authorized": False,
            "amended_live_executed": False,
            "amendment_approved": False,
            "amendment_methodology_selected": True,
            "artifact_id": DECISION_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "canary_manifest_file_sha256": canary_file_sha,
            "canary_manifest_internal_sha256": disk_canary_internal_sha,
            "chatgpt_final_methodology_decision_for_freeze": CHATGPT_FINAL_METHODOLOGY_DECISION_FOR_FREEZE,
            "decision_artifact_file_sha256": decision_file_sha,
            "decision_artifact_internal_sha256": disk_decision_internal_sha,
            "final100_used": False,
            "final_methodology_decision_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "live_provider_calls_new": 0,
            "model_winner_selected": False,
            "next_gate": NEXT_GATE_ID,
            "prep_artifact_file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
            "prep_artifact_internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
            "primary_denominators_changed": False,
            "primary_experiment_mutated": False,
            "primary_results_replaced": False,
            "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "selected_model_id": None,
            "stochasticity_execution_started": False,
            "task_id": TASK_ID,
            "verified": True,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write or verify W06 DEV-SELECT execution-environment amendment formal decision freeze artifacts."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the committed decision freeze and canary manifest artifacts without writing.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Deterministically generate and write the canary manifest and decision freeze JSON artifacts.",
    )
    args = parser.parse_args(argv)

    if args.write:
        write_info = write_w06_execution_environment_amendment_decision_artifacts(
            repo_root=REPO_ROOT
        )
        print(json.dumps(write_info, indent=2, sort_keys=True))
        return 0

    summary = verify_w06_execution_environment_amendment_decision_freeze(
        repo_root=REPO_ROOT
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
