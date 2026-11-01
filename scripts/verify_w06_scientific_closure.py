#!/usr/bin/env python3
"""Freeze and verify the W06 Scientific Closure package (v1).

Task: W06 — SCIENTIFIC CLOSURE
Previous gate:
  W06-AMENDMENT-01-CANARY-LIVE-EXECUTION-01-EVIDENCE-POSTMERGE-CHATGPT-AUDIT (PASS)
Authoritative base develop state:
  develop@f4235a04bad56e60fb9a255a0d670d83c44181b8
Next gate:
  W06-SCIENTIFIC-CLOSURE-CHATGPT-AUDIT

This script is strictly offline:
- LIVE_PROVIDER_CALLS_NEW = 0
- ENV_FILE_READ = false
- API_KEYS_INSPECTED = false
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from scripts import (  # noqa: E402
    freeze_w06_dev_select_amendment_01_canary_live_execution_authorization as exec_auth_freeze,
    run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher,
    verify_w06_dev_select_amendment_01_canary_live_execution_01_evidence as evidence_verifier,
)

TASK_ID = "W06-SCIENTIFIC-CLOSURE"
ARTIFACT_ID = "W06-SCIENTIFIC-CLOSURE-V1"
SCHEMA_VERSION = "1.0.0"

PREVIOUS_GATE = (
    "W06-AMENDMENT-01-CANARY-LIVE-EXECUTION-01-EVIDENCE-POSTMERGE-CHATGPT-AUDIT"
)
PREVIOUS_GATE_DECISION = "PASS"
NEXT_GATE = "W06-SCIENTIFIC-CLOSURE-CHATGPT-AUDIT"

AUTHORITATIVE_BASE_DEVELOP_SHA = "f4235a04bad56e60fb9a255a0d670d83c44181b8"
PR75_MERGE_COMMIT_SHA = "f4235a04bad56e60fb9a255a0d670d83c44181b8"
PR75_MERGE_PARENT_1_SHA = "fb53d1a46775b27b204a7f71a2f8718b2414f28d"
PR75_MERGE_PARENT_2_SHA = "3a8bf83611b04eb6241a6ab044b00a1a2b3b2b38"
ORIGINAL_LIVE_EVIDENCE_COMMIT_SHA = "f7d3225dc02e9cf8cd34e7142f3d6c242d25a993"
PR76_MERGE_COMMIT_SHA = "fb53d1a46775b27b204a7f71a2f8718b2414f28d"
PR74_MERGE_COMMIT_SHA = "4d631da5b5d439d54e511c3561d5e2584765033c"
PR73_MERGE_COMMIT_SHA = "3e103587ab0324717c03af14e236dc37fc579295"
PR72_MERGE_COMMIT_SHA = "1ebe30c251958542088a3056dcfc6b780dac3a88"

CLOSURE_JSON_REL_PATH = "data/evaluation/w06/w06_scientific_closure_v1.json"
CLOSURE_MD_REL_PATH = "docs/research/w06_scientific_closure.md"

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_CANARY_LAUNCHER_LF_SHA256 = (
    "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
)
EXPECTED_PRIMARY_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)

REQUIRED_CLOSURE_STATUS: Mapping[str, Any] = {
    "W06_IMPLEMENTATION_STATUS": "COMPLETED",
    "W06_EVALUATION_PROTOCOL_STATUS": "COMPLETED",
    "PRIMARY_DEV_SELECT_STATUS": (
        "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"
    ),
    "AMENDMENT_01_CANARY_STATUS": "FAILED_OPERATIONAL_GATE",
    "MODEL_SELECTION_STATUS": "INCONCLUSIVE",
    "MODEL_WINNER_SELECTED": False,
    "SELECTED_MODEL_ID": None,
    "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
    "COMPARATIVE_EXECUTED": False,
    "STOCHASTICITY_EXECUTION_STARTED": False,
    "FINAL100_USED": False,
    "FINAL100_STATUS": "NO-GO",
    "W06_OVERALL_STATUS": "CLOSED_WITH_OPERATIONAL_LIMITATION",
}

AUTHORITATIVE_CANDIDATE_MAP: Mapping[str, str] = {
    "C1": "gemini-3.8-flash",
    "C2": "gpt-6.1-sol",
    "C3": "claude-sonnet-5-5",
}

PRIMARY_DEV_SELECT_STRICT_RATES: Mapping[str, str] = {
    "C1": "1/60",
    "C2": "8/60",
    "C3": "0/60",
}

AMENDMENT_01_UNSCHEDULED_CELL_LABELS: tuple[str, ...] = (
    "007/C2",
    "007/C3",
    "011/C1",
    "011/C2",
    "011/C3",
    "015/C1",
    "015/C2",
    "015/C3",
)

AMENDMENT_01_UNSCHEDULED_CELL_IDS: tuple[str, ...] = (
    "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007",
    "W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007",
    "W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015",
    "W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015",
    "W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015",
)

CRITICAL_SCIENTIFIC_STATEMENT = (
    "Under the frozen W6 execution-environment protocol, C1/fixture 007 did not "
    "satisfy the operational readiness criteria within the fixed 180-second timeout."
)

W06_DELIVERABLES: tuple[str, ...] = (
    "deterministic grounded planner context",
    "structured itinerary-generation contract",
    "deterministic read-only validator",
    "exact POI grounding semantics",
    "time-overlap validation",
    "estimated-budget compliance evaluation",
    "opening-hours evaluation",
    "Haversine diagnostic",
    "fixed candidate registry",
    "fixed scenario suites",
    "provider adapters",
    "frozen SDK environment",
    "offline evaluator",
    "immutable evidence pipeline",
    "one-shot/fail-stop live execution controls",
    "reproducible provenance/hashes",
    "operational limitation evidence",
)

BOUND_ARTIFACT_SPECS: Mapping[str, Mapping[str, Any]] = {
    "primary_dev_select_results_manifest": {
        "path": "data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json",
        "expected_file_sha256": (
            "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
        ),
        "internal_sha256_field": "results_manifest_sha256",
        "expected_internal_sha256": (
            "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
        ),
    },
    "primary_dev_select_results_freeze_receipt": {
        "path": "data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json",
        "expected_file_sha256": (
            "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
        ),
        "internal_sha256_field": "results_freeze_receipt_sha256",
        "expected_internal_sha256": (
            "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
        ),
    },
    "primary_dev_select_failure_diagnostic": {
        "path": "data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json",
        "expected_file_sha256": (
            "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
        ),
        "internal_sha256_field": "diagnostic_artifact_sha256",
        "expected_internal_sha256": (
            "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
        ),
    },
    "amendment_01_decision": {
        "path": "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json",
        "expected_file_sha256": (
            "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
        ),
        "internal_sha256_field": "decision_artifact_internal_sha256",
        "expected_internal_sha256": (
            "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
        ),
    },
    "amendment_01_approval_receipt": {
        "path": "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approval_receipt_v1.json",
        "expected_file_sha256": (
            "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
        ),
        "internal_sha256_field": "approval_receipt_internal_sha256",
        "expected_internal_sha256": (
            "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
        ),
    },
    "amendment_01_canary_manifest": {
        "path": "data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json",
        "expected_file_sha256": (
            "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
        ),
        "internal_sha256_field": "canary_manifest_internal_sha256",
        "expected_internal_sha256": (
            "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
        ),
    },
    "amendment_01_owner_readiness_attestation": {
        "path": "data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json",
        "expected_file_sha256": (
            "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
        ),
        "internal_sha256_field": "owner_readiness_attestation_internal_sha256",
        "expected_internal_sha256": (
            "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
        ),
    },
    "amendment_01_canary_authorization_prep": {
        "path": "data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json",
        "expected_file_sha256": (
            "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
        ),
        "internal_sha256_field": "canary_live_authorization_prep_internal_sha256",
        "expected_internal_sha256": (
            "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
        ),
    },
    "amendment_01_canary_live_execution_authorization_receipt": {
        "path": "data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json",
        "expected_file_sha256": (
            "e68c7ad76e9261aaf687660dd20441118ec192a727a6cbf88b15cf4f0268d684"
        ),
        "internal_sha256_field": "canary_live_execution_authorization_internal_sha256",
        "expected_internal_sha256": (
            "d045b1c5e45675dd330515aad5e591e9efb94e219d4418aa739eb8b2270ad8c5"
        ),
    },
}


class W06ScientificClosureVerificationError(RuntimeError):
    """Raised when W06 scientific closure verification fails."""


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize mapping deterministically as canonical UTF-8 JSON with trailing LF."""
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def compute_lf_sha256_bytes(data: bytes) -> str:
    """Compute SHA256 after normalizing CRLF -> LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def compute_file_lf_sha256(path: Path) -> str:
    """Compute canonical LF SHA256 for a file path."""
    return compute_lf_sha256_bytes(path.read_bytes())


def compute_closure_internal_sha256(payload: Mapping[str, Any]) -> str:
    """Compute internal SHA256 of the closure payload with self-hash zeroed out."""
    clone = deepcopy(dict(payload))
    clone["closure_internal_sha256"] = ""
    return compute_lf_sha256_bytes(canonical_json_bytes(clone))


def build_closure_payload() -> dict[str, Any]:
    """Construct the authoritative W06 scientific closure JSON payload."""
    payload: dict[str, Any] = {
        "ALL_9_CANARY_OPERATIONAL_PASS": False,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "AMENDMENT_01_CANARY_STATUS": "FAILED_OPERATIONAL_GATE",
        "API_KEYS_INSPECTED": False,
        "COMPARATIVE_EXECUTED": False,
        "ENV_FILE_READ": False,
        "FINAL100_STATUS": "NO-GO",
        "FINAL100_USED": False,
        "LIVE_PROVIDER_CALLS_NEW": 0,
        "MODEL_SELECTION_STATUS": "INCONCLUSIVE",
        "MODEL_WINNER_SELECTED": False,
        "PRIMARY_DEV_SELECT_STATUS": (
            "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"
        ),
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "W06_EVALUATION_PROTOCOL_STATUS": "COMPLETED",
        "W06_IMPLEMENTATION_STATUS": "COMPLETED",
        "W06_OVERALL_STATUS": "CLOSED_WITH_OPERATIONAL_LIMITATION",
        "amendment_01_canary_authority": {
            "ALL_9_CANARY_OPERATIONAL_PASS": False,
            "actual_http_requests": 1,
            "assigned_cells": 9,
            "attempted_cells": 1,
            "candidate_id": "C1",
            "classification": "TIMEOUT",
            "fail_stop": True,
            "fixture_id": "W06-DEV-TUNE-007",
            "generation_invocations": 1,
            "http_5xx": True,
            "latency_ms": 179986.664,
            "latency_ns": 179986664200,
            "model_identity_evidence": False,
            "operational_pass": "0/9",
            "operational_pass_cells_count": 0,
            "prompt": "P1",
            "provider": "Google",
            "provider_code": "GOOGLE",
            "provider_response_received": False,
            "provider_slug": "google",
            "reported_error": "504 DEADLINE_EXCEEDED",
            "requested_model": "gemini-3.8-flash",
            "rerun": 0,
            "retry": 0,
            "status": "FAILED_OPERATIONAL_GATE",
            "stopped_at": "007 / C1",
            "stopped_at_cell_id": "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007",
            "timeout_ms": 180000,
            "unscheduled_cell_ids": list(AMENDMENT_01_UNSCHEDULED_CELL_IDS),
            "unscheduled_cells": 8,
            "unscheduled_cells_list": list(AMENDMENT_01_UNSCHEDULED_CELL_LABELS),
            "unscheduled_cells_status": "UNSCHEDULED_DUE_TO_FAIL_STOP",
        },
        "artifact_id": ARTIFACT_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "authoritative_candidates": dict(AUTHORITATIVE_CANDIDATE_MAP),
        "bound_provenance": {
            "artifacts": {
                key: {
                    "expected_file_sha256": spec["expected_file_sha256"],
                    "expected_internal_sha256": spec["expected_internal_sha256"],
                    "internal_sha256_field": spec["internal_sha256_field"],
                    "path": spec["path"],
                }
                for key, spec in BOUND_ARTIFACT_SPECS.items()
            },
            "code_and_launchers": {
                "canary_launcher_lf_sha256": EXPECTED_CANARY_LAUNCHER_LF_SHA256,
                "canary_launcher_path": (
                    "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
                ),
                "primary_launcher_lf_sha256": EXPECTED_PRIMARY_LAUNCHER_LF_SHA256,
                "primary_launcher_path": "scripts/run_w06_dev_select_live_v1.py",
                "scientific_code_bundle_sha256": (
                    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
                ),
            },
            "git_lineage": {
                "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
                "original_live_evidence_commit_sha": ORIGINAL_LIVE_EVIDENCE_COMMIT_SHA,
                "pr72_authorization_prep_merge_commit_sha": PR72_MERGE_COMMIT_SHA,
                "pr73_canary_launcher_merge_commit_sha": PR73_MERGE_COMMIT_SHA,
                "pr74_execution_authorization_receipt_merge_commit_sha": (
                    PR74_MERGE_COMMIT_SHA
                ),
                "pr75_live_evidence_merge_commit_sha": PR75_MERGE_COMMIT_SHA,
                "pr75_merge_parent_1_sha": PR75_MERGE_PARENT_1_SHA,
                "pr75_merge_parent_2_sha": PR75_MERGE_PARENT_2_SHA,
                "pr76_lifecycle_corrective_merge_commit_sha": PR76_MERGE_COMMIT_SHA,
            },
            "merged_live_evidence": {
                "batch_summary_sha256": (
                    evidence_verifier.EXPECTED_CANARY_BATCH_SUMMARY_SHA256
                ),
                "cell_01_receipt_sha256": (
                    evidence_verifier.EXPECTED_CANARY_CELL_01_RECEIPT_SHA256
                ),
                "evidence_file_count": 9,
                "evidence_file_lf_sha256": dict(
                    evidence_verifier.EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S
                ),
                "lifecycle_state": "POST_EXECUTION_EVIDENCE_PRESENT",
                "output_root": (
                    evidence_verifier.CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH
                ),
                "second_live_execution_blocked": True,
            },
        },
        "closure_internal_sha256": "",
        "critical_scientific_interpretation": {
            "amendment_01_establishes_gemini_inferior_planner_quality": False,
            "authoritative_statement": CRITICAL_SCIENTIFIC_STATEMENT,
            "comparative180_cannot_be_authorized": True,
            "fair_amendment_01_comparative_quality_dataset_exists": False,
            "final100_cannot_be_opened": True,
            "no_model_winner_can_be_selected": True,
            "why_comparative180_not_authorized": (
                "Frozen Amendment-01 authorization required 9/9 operational PASS "
                "(ALL_9_CANARY_OPERATIONAL_PASS = true) and a subsequent dedicated "
                "ChatGPT audit gate before any 180-cell comparative execution could "
                "be authorized. Cell 1 (007/C1) failed operationally with TIMEOUT "
                "(504 DEADLINE_EXCEEDED) and triggered immediate fail-stop (0/9)."
            ),
            "why_final100_remains_no_go": (
                "Final100 is a locked holdout evaluation reserve that requires a "
                "validly selected model winner from DEV-SELECT and completion of "
                "stochasticity checks. Because MODEL_SELECTION_STATUS is INCONCLUSIVE "
                "and SELECTED_MODEL_ID is null, Final100 remains untouched with "
                "status NO-GO."
            ),
        },
        "downstream_firewalls": {
            "ALL_9_CANARY_OPERATIONAL_PASS": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "COMPARATIVE_EXECUTED": False,
            "FINAL100_STATUS": "NO-GO",
            "FINAL100_USED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "claims_from_final100_forbidden": True,
            "final100_untouched": True,
        },
        "forbidden_actions_enforced": {
            "amendment_02_created": False,
            "c2_c3_side_tests_executed": False,
            "canary_rerun_executed": False,
            "comparative180_executed": False,
            "final100_accessed_or_used": False,
            "live_provider_calls_new": 0,
            "model_order_changed": False,
            "model_replacement_performed": False,
            "retries_enabled": False,
            "stochasticity_started": False,
            "timeout_modified": False,
        },
        "next_gate": NEXT_GATE,
        "previous_gate": PREVIOUS_GATE,
        "previous_gate_decision": PREVIOUS_GATE_DECISION,
        "primary_dev_select_authority": {
            "authoritative_candidates": dict(AUTHORITATIVE_CANDIDATE_MAP),
            "declare_winner_forbidden": True,
            "infer_c2_is_best_forbidden": True,
            "non_comparability_reason": (
                "Severe asymmetric execution-environment failures across providers "
                "during the 180-cell primary run (C1 provider deadline/timeout "
                "dominance, C2 max_output_tokens=4096 JSON truncation, C3 provider "
                "credit-balance exhaustion) confounded planner quality with "
                "execution-environment failure modes."
            ),
            "operationally_valid_benchmark": True,
            "rank_models_from_primary_rates_forbidden": True,
            "status": "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY",
            "strict_valid_core_rates": dict(PRIMARY_DEV_SELECT_STRICT_RATES),
            "total_cells": 180,
            "total_fixtures": 60,
        },
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "thesis_reporting_and_w07_handoff": {
            "limitations_to_report_in_thesis": [
                "Primary 180-cell DEV-SELECT exhibited severe asymmetric provider "
                "execution-environment failures (C1 1/60, C2 8/60, C3 0/60), "
                "rendering cross-model planner-quality ranking scientifically invalid.",
                "Amendment-01 repaired execution-environment confounds (output budget "
                "8192, timeout 180000 ms, pacing 2000 ms, pre-run owner readiness) "
                "under a strict 9-cell fail-stop canary gate.",
                "In Amendment-01 Canary Execution-01, Cell 1 (007/C1, Google "
                "gemini-3.8-flash) timed out after 179986.664 ms with provider error "
                "504 DEADLINE_EXCEEDED, triggering immediate fail-stop with 0/9 "
                "operational passes and leaving Cells 2-9 unscheduled.",
                "The timeout establishes an operational readiness limitation under the "
                "frozen 180-second protocol and does NOT establish that Gemini is "
                "inferior in itinerary-planning quality.",
                "Because strict pre-registered governance forbade ad-hoc retries, "
                "reruns, or skipping C1, no fair comparative dataset was produced, "
                "MODEL_SELECTION_STATUS remains INCONCLUSIVE, SELECTED_MODEL_ID is "
                "null, Comparative180 was not authorized, and Final100 remains NO-GO.",
            ],
            "w07_handoff_conditions": {
                "comparative_winner_claim_permitted": False,
                "final100_benchmark_claim_permitted": False,
                "planner_and_validator_architecture_ready_for_w07": True,
                "runtime_model_configuration_interpretation": (
                    "Any model configured in downstream application or W7 workflows "
                    "must be documented strictly as an engineering/operational default "
                    "and NEVER as an empirically validated W6 comparative winner."
                ),
                "w06_scientific_closure_status": (
                    "CLOSED_WITH_OPERATIONAL_LIMITATION"
                ),
            },
        },
        "w06_successfully_delivered": {
            "classified_as_implementation_failure": False,
            "deliverable_count": len(W06_DELIVERABLES),
            "deliverables": list(W06_DELIVERABLES),
        },
    }
    payload["closure_internal_sha256"] = compute_closure_internal_sha256(payload)
    return payload


def build_closure_markdown(payload: Mapping[str, Any], json_file_sha256: str) -> str:
    """Build the authoritative Markdown report for W06 Scientific Closure."""
    internal_sha = payload["closure_internal_sha256"]
    return f"""# W06 — Scientific Closure Report

## 0. Authority & Repository Provenance

- **Task ID:** `{TASK_ID}`
- **Artifact ID:** `{ARTIFACT_ID}`
- **Previous Gate:** `{PREVIOUS_GATE}` (`{PREVIOUS_GATE_DECISION}`)
- **Authoritative Base Commit (`develop`):** `{AUTHORITATIVE_BASE_DEVELOP_SHA}`
- **PR #75 Merge Commit (`develop`):** `{PR75_MERGE_COMMIT_SHA}`
  - **Parent 1 (`develop` after PR #76):** `{PR75_MERGE_PARENT_1_SHA}`
  - **Parent 2 (PR #75 synced head):** `{PR75_MERGE_PARENT_2_SHA}`
  - **Original Immutable Live Evidence Commit (retained in ancestry):** `{ORIGINAL_LIVE_EVIDENCE_COMMIT_SHA}`
- **Closure JSON Artifact:** `{CLOSURE_JSON_REL_PATH}`
  - **Canonical LF FILE SHA256:** `{json_file_sha256}`
  - **Canonical INTERNAL SHA256:** `{internal_sha}`
- **Scientific Code Bundle SHA256:** `{EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}`
- **Canary Launcher LF SHA256:** `{EXPECTED_CANARY_LAUNCHER_LF_SHA256}`
- **Primary Launcher LF SHA256:** `{EXPECTED_PRIMARY_LAUNCHER_LF_SHA256}`
- **Next Gate:** `{NEXT_GATE}`

---

## 1. Frozen W06 Closure Status

| Status Key | Authoritative Value |
| :--- | :--- |
| `W06_IMPLEMENTATION_STATUS` | `"COMPLETED"` |
| `W06_EVALUATION_PROTOCOL_STATUS` | `"COMPLETED"` |
| `PRIMARY_DEV_SELECT_STATUS` | `"OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"` |
| `AMENDMENT_01_CANARY_STATUS` | `"FAILED_OPERATIONAL_GATE"` |
| `MODEL_SELECTION_STATUS` | `"INCONCLUSIVE"` |
| `MODEL_WINNER_SELECTED` | `false` |
| `SELECTED_MODEL_ID` | `null` |
| `AMENDED_COMPARATIVE_LIVE_AUTHORIZED` | `false` |
| `COMPARATIVE_EXECUTED` | `false` |
| `STOCHASTICITY_EXECUTION_STARTED` | `false` |
| `FINAL100_USED` | `false` |
| `FINAL100_STATUS` | `"NO-GO"` |
| `W06_OVERALL_STATUS` | `"CLOSED_WITH_OPERATIONAL_LIMITATION"` |

---

## 2. Primary DEV-SELECT Authority (180 Cells)

The primary 180-cell DEV-SELECT experiment (`60` DEV-SELECT fixtures × `3` frozen candidates under prompt `P1`) is preserved in full as an operationally valid benchmark record:

- **`C1` (`gemini-3.8-flash`):** strict valid/core rate = `1/60`
- **`C2` (`gpt-6.1-sol`):** strict valid/core rate = `8/60`
- **`C3` (`claude-sonnet-5-5`):** strict valid/core rate = `0/60`

**Scientific status:** `OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY`.

Because the primary run suffered severe asymmetric execution-environment failures across providers (`C1` provider deadline/timeout dominance, `C2` `max_output_tokens = 4096` JSON truncation, and `C3` provider credit-balance exhaustion), it is scientifically invalid to infer that `C2` is the best planner model, to rank models from `1/60`, `8/60`, `0/60`, or to declare a model winner from the primary run.

---

## 3. Amendment-01 Canary Authority (9-Cell Fail-Stop Gate)

To address the execution-environment confounds without mutating the primary record, `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01` froze an environment-only protocol correction (`max_output_tokens = 8192`, client timeout = `180000 ms`, inter-call pacing = `2000 ms`, concurrency = `1`, retries = `0`, fallback = `false`) and required a 9-cell operational canary (`007`, `011`, `015` × `C1`, `C2`, `C3` under `P1`) to pass `9/9` before any amended 180-cell comparative run could be considered.

Under one-time execution authorization (`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`), the frozen canary produced the following immutable result:

- **Assigned cells:** `9`
- **Attempted cells:** `1`
- **Unscheduled cells:** `8`
- **Operational PASS:** `0/9` (`ALL_9_CANARY_OPERATIONAL_PASS = false`)
- **Fail-stop triggered:** `true`
- **Stopped at cell:** `007 / C1` (`W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007`)
- **Provider / Requested Model / Prompt:** `Google` / `gemini-3.8-flash` / `P1`
- **Logical generation invocations:** `1`
- **Actual provider HTTP requests:** `1`
- **Retries / Reruns:** `0` / `0`
- **Latency:** `179986.664 ms` (`179986664200 ns`)
- **Classification:** `TIMEOUT`
- **HTTP 5xx failure:** `true`
- **Reported provider error:** `504 DEADLINE_EXCEEDED`
- **Provider response received:** `false`
- **Provider model identity evidence captured:** `false`
- **Unscheduled cells (`UNSCHEDULED_DUE_TO_FAIL_STOP`):**
  - `007/C2`, `007/C3`, `011/C1`, `011/C2`, `011/C3`, `015/C1`, `015/C2`, `015/C3`

---

## 4. Critical Scientific Interpretation

The Amendment-01 result **does NOT establish that Gemini is inferior in itinerary-planning quality**.

It establishes only that:

> {CRITICAL_SCIENTIFIC_STATEMENT}

Because the pre-registered fail-stop rule halted execution immediately after `007/C1` and prevented `C2` (`gpt-6.1-sol`) and `C3` (`claude-sonnet-5-5`) from running:

1. **There is no fair Amendment-01 comparative quality dataset;**
2. **No model winner can be selected (`MODEL_SELECTION_STATUS = "INCONCLUSIVE"`, `SELECTED_MODEL_ID = null`);**
3. **Comparative180 cannot be authorized (`AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `COMPARATIVE_EXECUTED = false`);**
4. **Final100 cannot be opened (`FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`).**

---

## 5. What W06 Successfully Delivered

Despite the external provider execution-environment limitation, W06 completed all software engineering, grounding, validation, and evaluation-governance objectives:

1. Deterministic grounded planner context;
2. Structured itinerary-generation contract;
3. Deterministic read-only validator;
4. Exact POI grounding semantics;
5. Time-overlap validation;
6. Estimated-budget compliance evaluation;
7. Opening-hours evaluation;
8. Haversine diagnostic;
9. Fixed candidate registry (`C1 = gemini-3.8-flash`, `C2 = gpt-6.1-sol`, `C3 = claude-sonnet-5-5`);
10. Fixed scenario suites (`DEV-TUNE`, `DEV-SELECT`, and locked `FINAL100`);
11. Provider adapters (Google, OpenAI, Anthropic);
12. Frozen SDK environment;
13. Offline evaluator;
14. Immutable evidence pipeline;
15. One-shot/fail-stop live execution controls;
16. Reproducible cryptographic provenance and canonical LF SHA256 hashes;
17. Auditable operational limitation evidence.

Accordingly, **W06 is NOT classified as an implementation failure** (`W06_IMPLEMENTATION_STATUS = "COMPLETED"`, `W06_EVALUATION_PROTOCOL_STATUS = "COMPLETED"`, `W06_OVERALL_STATUS = "CLOSED_WITH_OPERATIONAL_LIMITATION"`).

---

## 6. Final100 Firewall Status

- `FINAL100_USED = false`
- `FINAL100_STATUS = "NO-GO"`

The `Final100` holdout set remains completely untouched. No experimental claim, benchmark score, or model comparison may be made from `Final100`.

---

## 7. Thesis / Academic Report Section (Report-Ready Wording)

### 7.1 Grounded Planner Architecture and Deterministic Validation

In Work Package 6 (W06), WanderAI implemented a deterministic, grounded itinerary-planning pipeline paired with a read-only post-generation validator. Candidate POIs are retrieved from the verified catalog and assembled into a deterministic grounded planner context with stable POI identifiers, coordinates, categories, estimated costs, and opening-hours specifications. The language model is constrained to emit a structured itinerary conforming to a portable JSON schema (`v2`), which is subsequently evaluated by a deterministic offline validator covering exact POI grounding, intra-day time-overlap absence, cumulative budget compliance, opening-hours compatibility, and Haversine spatial-coherence diagnostics.

### 7.2 Pre-Registered Multi-Stage Evaluation Governance

To prevent selective reporting, post-hoc prompt tuning on test scenarios, or unlogged retry inflation, W06 enforced a multi-stage evaluation protocol separating prompt selection (`DEV-TUNE`), candidate model comparison (`DEV-SELECT`, 60 fixtures × 3 candidates = 180 cells), and a locked holdout reserve (`FINAL100`). Every execution plan, prompt manifest, pricing snapshot, authorization receipt, and per-cell transport journal was cryptographically frozen in Git prior to live provider invocation, with single-flight execution (`concurrency = 1`), zero automatic retries (`retry = 0`), and immutable per-cell evidence capture.

### 7.3 Provider Execution Instability and Amendment-01 Fail-Stop Outcome

During the primary 180-cell `DEV-SELECT` benchmark under prompt `P1`, strict valid core pass rates were `1/60` for `C1` (`gemini-3.8-flash`), `8/60` for `C2` (`gpt-6.1-sol`), and `0/60` for `C3` (`claude-sonnet-5-5`). Diagnostic auditing established that these outcomes were dominated by asymmetric execution-environment failures rather than intrinsic planning quality: `C1` experienced frequent client/provider deadline timeouts under the initial timeout budget, `C2` suffered systematic JSON truncation at the initial `4096`-token output cap on 5-day itineraries, and `C3` failed all 60 requests due to provider credit-balance exhaustion (`HTTP 400`).

To isolate model planning quality from environment confounds, `Amendment-01` froze an environment-only remediation (`max_output_tokens = 8192`, `timeout = 180000 ms`, `2000 ms` pacing, and verified provider readiness) gated by a 9-cell operational canary (`007`, `011`, `015` × `C1`, `C2`, `C3`) requiring `9/9` operational passes with immediate fail-stop on any operational failure. In the authorized one-shot canary run (`Execution-01`), the first cell (`007 / C1`, Google `gemini-3.8-flash`) remained open for `179986.664 ms` and terminated with provider error `504 DEADLINE_EXCEEDED` (`TIMEOUT`, `HTTP 5xx`). Per the frozen fail-stop rule, execution halted immediately (`1` attempted cell, `0/9` operational passes, `8` cells unscheduled).

### 7.4 Methodological Limitation and Future Work

This negative operational result is reported transparently as an external execution-environment limitation. Specifically, under the frozen W06 execution-environment protocol, `C1` on fixture `007` did not satisfy operational readiness criteria within the fixed 180-second deadline. Because strict experimental governance prohibited ad-hoc reruns, silent retries, or bypassing `C1`, cells for `C2` and `C3` were not scheduled in the canary, and no fair Amendment-01 comparative dataset was generated. Consequently, `C1`'s timeout must not be interpreted as evidence of inferior itinerary-planning quality, no model winner is selected (`MODEL_SELECTION_STATUS = "INCONCLUSIVE"`), the 180-cell amended comparative run was not authorized, and the `FINAL100` holdout set remains unopened (`NO-GO`). Future work with dedicated enterprise quota/latency guarantees or asynchronous batch endpoints can re-execute the frozen comparative harness without modifying the underlying W06 planner or validator implementation.

---

## 8. W07 Handoff Conditions

1. **Architecture & Validator Readiness:** The W06 deterministic grounded planner context builder, portable structured schema (`v2`), provider adapters, and deterministic read-only validator (`0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`) are complete, verified, and ready for downstream integration in W07.
2. **No Comparative Winner Claim:** Downstream documentation, thesis chapters, and W07 components must respect `MODEL_SELECTION_STATUS = "INCONCLUSIVE"`, `MODEL_WINNER_SELECTED = false`, and `SELECTED_MODEL_ID = null`. Any runtime model selection used for application operation must be described strictly as an engineering/operational configuration rather than an empirically validated W06 comparative winner.
3. **Final100 Holdout Preservation:** `FINAL100_USED = false` and `FINAL100_STATUS = "NO-GO"` remain permanently enforced for W06.

---

## 9. Bound Artifact & Evidence Provenance

| Artifact / Evidence | Path | Canonical LF File SHA256 | Internal SHA256 |
| :--- | :--- | :--- | :--- |
| Primary DEV-SELECT Results Manifest | `data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json` | `1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0` | `4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011` |
| Primary DEV-SELECT Freeze Receipt | `data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json` | `c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4` | `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a` |
| Primary DEV-SELECT Failure Diagnostic | `data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json` | `b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692` | `509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8` |
| Amendment-01 Decision | `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json` | `2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf` | `38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a` |
| Amendment-01 Approval Receipt | `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approval_receipt_v1.json` | `171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5` | `d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991` |
| Amendment-01 Canary Manifest | `data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json` | `3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96` | `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518` |
| Owner Provider Readiness Attestation | `data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json` | `91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06` | `137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75` |
| Canary Authorization PREP | `data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json` | `21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61` | `0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61` |
| Canary Live Execution Authorization Receipt | `data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json` | `e68c7ad76e9261aaf687660dd20441118ec192a727a6cbf88b15cf4f0268d684` | `d045b1c5e45675dd330515aad5e591e9efb94e219d4418aa739eb8b2270ad8c5` |
| Canary Batch Execution Summary | `data/evaluation/w06/live_amendment_01_canary_v1/canary_batch_execution_summary_v1.json` | `d16a3f5f49101914a584045bee2e7470e4dee7eb7aa106c7e9409b1d3d77a8ec` | `n/a` |
| Canary Cell 01 Evidence Receipt | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/canary_cell_evidence_receipt.json` | `1456833419e4ba76bd52be9f3e4444724febc52e24e08ff30c808379596442c6` | `n/a` |
| Canary Cell 01 Diagnostic Evaluation | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/diagnostic_evaluation.json` | `fd66de87664c5dbc24adab8c58c7457408e62ca72280f091f52d9d157aef57ff` | `n/a` |
| Canary Cell 01 Provider Response Metadata | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/provider_response_metadata.json` | `5a3a345baa1bbb116f10a1759801b9d45a22d8d632cdf2b38572aadad438a885` | `n/a` |
| Canary Cell 01 Raw Provider Response | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/raw_provider_response.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `n/a` |
| Canary Cell 01 Raw Usage Metadata | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/raw_usage_metadata.json` | `6a40b68c53cc49e8f49c22ef79f97dafe36a57f3ed4615eb32e15d0e56d2f9de` | `n/a` |
| Canary Cell 01 Request Manifest | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/request_manifest.json` | `360db1d7f655705379e3879bcdb0868d772688c5a3e1089a0d3a020e48e61db6` | `n/a` |
| Canary Cell 01 Transport Journal Completed | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/transport_journal_completed.json` | `f0946e08a666bee2f67776e59696ed3e4e4e433bdc76913ee29fc948f442a78a` | `n/a` |
| Canary Cell 01 Transport Journal Starting | `data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/transport_journal_starting.json` | `f8d4fd09fb20f001314ca16bc8133aef0a359a09a6cf1e15e4cecd79d5ac4a7d` | `n/a` |
"""


def write_closure_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write the W06 scientific closure JSON and Markdown artifacts."""
    payload = build_closure_payload()
    json_bytes = canonical_json_bytes(payload)
    json_file_sha256 = compute_lf_sha256_bytes(json_bytes)

    json_path = repo_root / CLOSURE_JSON_REL_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(json_bytes)

    md_text = build_closure_markdown(payload, json_file_sha256)
    md_bytes = md_text.replace("\r\n", "\n").encode("utf-8")
    md_path = repo_root / CLOSURE_MD_REL_PATH
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_bytes(md_bytes)

    return verify_scientific_closure(repo_root=repo_root)


def verify_scientific_closure(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify the W06 scientific closure artifacts, bound hashes, and post-live evidence."""
    json_path = repo_root / CLOSURE_JSON_REL_PATH
    md_path = repo_root / CLOSURE_MD_REL_PATH

    if not json_path.is_file():
        raise W06ScientificClosureVerificationError(
            f"MISSING_CLOSURE_JSON: {CLOSURE_JSON_REL_PATH}"
        )
    if not md_path.is_file():
        raise W06ScientificClosureVerificationError(
            f"MISSING_CLOSURE_MARKDOWN: {CLOSURE_MD_REL_PATH}"
        )

    try:
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise W06ScientificClosureVerificationError(
            f"INVALID_CLOSURE_JSON: {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        raise W06ScientificClosureVerificationError("CLOSURE_JSON_NOT_OBJECT")

    expected_payload = build_closure_payload()
    computed_internal = compute_closure_internal_sha256(loaded)
    if loaded.get("closure_internal_sha256") != computed_internal:
        raise W06ScientificClosureVerificationError(
            "CLOSURE_INTERNAL_SHA256_MISMATCH: "
            f"recorded={loaded.get('closure_internal_sha256')} "
            f"computed={computed_internal}"
        )
    if loaded != expected_payload:
        raise W06ScientificClosureVerificationError(
            "CLOSURE_PAYLOAD_DRIFT: closure JSON does not match canonical expected payload"
        )

    for key, expected_val in REQUIRED_CLOSURE_STATUS.items():
        if loaded.get(key) != expected_val:
            raise W06ScientificClosureVerificationError(
                f"CLOSURE_STATUS_MISMATCH[{key}]: "
                f"actual={loaded.get(key)!r} expected={expected_val!r}"
            )

    actual_json_bytes = json_path.read_bytes().replace(b"\r\n", b"\n")
    expected_json_bytes = canonical_json_bytes(expected_payload)
    if actual_json_bytes != expected_json_bytes:
        raise W06ScientificClosureVerificationError(
            "CLOSURE_JSON_NON_CANONICAL_BYTES"
        )
    json_file_sha256 = compute_lf_sha256_bytes(actual_json_bytes)

    expected_md_bytes = (
        build_closure_markdown(expected_payload, json_file_sha256)
        .replace("\r\n", "\n")
        .encode("utf-8")
    )
    actual_md_bytes = md_path.read_bytes().replace(b"\r\n", b"\n")
    if actual_md_bytes != expected_md_bytes:
        raise W06ScientificClosureVerificationError(
            "CLOSURE_MARKDOWN_DRIFT: markdown does not match canonical expected report"
        )
    md_file_sha256 = compute_lf_sha256_bytes(actual_md_bytes)

    # Verify all bound artifacts exist and match their frozen file and internal hashes.
    verified_bound_artifacts: dict[str, dict[str, str]] = {}
    for key, spec in BOUND_ARTIFACT_SPECS.items():
        rel_path = str(spec["path"])
        target_path = repo_root / rel_path
        if not target_path.is_file():
            raise W06ScientificClosureVerificationError(
                f"MISSING_BOUND_ARTIFACT[{key}]: {rel_path}"
            )
        actual_file_sha = compute_file_lf_sha256(target_path)
        if actual_file_sha != spec["expected_file_sha256"]:
            raise W06ScientificClosureVerificationError(
                f"BOUND_ARTIFACT_FILE_SHA256_MISMATCH[{key}]: "
                f"actual={actual_file_sha} expected={spec['expected_file_sha256']}"
            )
        artifact_obj = json.loads(target_path.read_text(encoding="utf-8"))
        internal_field = str(spec["internal_sha256_field"])
        actual_internal_sha = artifact_obj.get(internal_field)
        if actual_internal_sha != spec["expected_internal_sha256"]:
            raise W06ScientificClosureVerificationError(
                f"BOUND_ARTIFACT_INTERNAL_SHA256_MISMATCH[{key}]: "
                f"actual={actual_internal_sha} expected={spec['expected_internal_sha256']}"
            )
        verified_bound_artifacts[key] = {
            "file_sha256": actual_file_sha,
            "internal_sha256": str(actual_internal_sha),
            "path": rel_path,
        }

    # Verify scientific code bundle and launcher hashes.
    bundle_sha = canary_launcher.compute_scientific_code_bundle_sha256(repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise W06ScientificClosureVerificationError(
            f"SCIENTIFIC_BUNDLE_SHA256_MISMATCH: {bundle_sha}"
        )
    canary_launcher_sha = compute_file_lf_sha256(
        repo_root / "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
    )
    if canary_launcher_sha != EXPECTED_CANARY_LAUNCHER_LF_SHA256:
        raise W06ScientificClosureVerificationError(
            f"CANARY_LAUNCHER_SHA256_MISMATCH: {canary_launcher_sha}"
        )
    primary_launcher_sha = compute_file_lf_sha256(
        repo_root / "scripts/run_w06_dev_select_live_v1.py"
    )
    if primary_launcher_sha != EXPECTED_PRIMARY_LAUNCHER_LF_SHA256:
        raise W06ScientificClosureVerificationError(
            f"PRIMARY_LAUNCHER_SHA256_MISMATCH: {primary_launcher_sha}"
        )

    # Verify post-live evidence and second-execution protection via authoritative verifier.
    evidence_summary = (
        evidence_verifier.verify_w06_amendment_01_canary_repository_lifecycle(
            repo_root=repo_root,
            require_evidence_present=True,
        )
    )
    if (
        evidence_summary.get("status") != "PASS"
        or not evidence_summary.get("evidence_verified")
        or not evidence_summary.get("second_live_execution_blocked")
        or evidence_summary.get("lifecycle_state") != "POST_EXECUTION_EVIDENCE_PRESENT"
    ):
        raise W06ScientificClosureVerificationError(
            f"POST_LIVE_EVIDENCE_VERIFICATION_FAILED: {evidence_summary}"
        )

    # Verify execution authorization receipt in post-execution state (shallow-clone aware).
    git_runner = exec_auth_freeze.build_shallow_aware_git_runner(repo_root)
    auth_summary = (
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=repo_root,
            git_runner=git_runner,
        )
    )
    if (
        auth_summary.get("status") != "PASS"
        or not auth_summary.get("verified")
        or auth_summary.get("lifecycle_state") != "POST_EXECUTION_EVIDENCE_PRESENT"
    ):
        raise W06ScientificClosureVerificationError(
            f"EXECUTION_AUTHORIZATION_VERIFICATION_FAILED: {auth_summary}"
        )

    return {
        "ALL_9_CANARY_OPERATIONAL_PASS": False,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "AMENDMENT_01_CANARY_STATUS": "FAILED_OPERATIONAL_GATE",
        "API_KEYS_INSPECTED": False,
        "COMPARATIVE_EXECUTED": False,
        "ENV_FILE_READ": False,
        "FINAL100_STATUS": "NO-GO",
        "FINAL100_USED": False,
        "LIVE_PROVIDER_CALLS_NEW": 0,
        "MODEL_SELECTION_STATUS": "INCONCLUSIVE",
        "MODEL_WINNER_SELECTED": False,
        "PRIMARY_DEV_SELECT_STATUS": (
            "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"
        ),
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "W06_EVALUATION_PROTOCOL_STATUS": "COMPLETED",
        "W06_IMPLEMENTATION_STATUS": "COMPLETED",
        "W06_OVERALL_STATUS": "CLOSED_WITH_OPERATIONAL_LIMITATION",
        "artifact_id": ARTIFACT_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "bound_artifacts_verified_count": len(verified_bound_artifacts),
        "canary_launcher_lf_sha256": canary_launcher_sha,
        "closure_internal_sha256": computed_internal,
        "closure_json_file_sha256": json_file_sha256,
        "closure_json_path": CLOSURE_JSON_REL_PATH,
        "closure_markdown_file_sha256": md_file_sha256,
        "closure_markdown_path": CLOSURE_MD_REL_PATH,
        "evidence_file_count": 9,
        "evidence_verified": True,
        "lifecycle_state": "POST_EXECUTION_EVIDENCE_PRESENT",
        "next_gate": NEXT_GATE,
        "previous_gate": PREVIOUS_GATE,
        "primary_launcher_lf_sha256": primary_launcher_sha,
        "scientific_code_bundle_sha256": bundle_sha,
        "second_live_execution_blocked": True,
        "status": "PASS",
        "task_id": TASK_ID,
        "verified": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the W06 Scientific Closure package (v1)."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing W06 scientific closure artifacts offline (default).",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Write/freeze W06 scientific closure JSON and Markdown artifacts, then verify.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.write:
        result = write_closure_artifacts(repo_root=REPO_ROOT)
    else:
        result = verify_scientific_closure(repo_root=REPO_ROOT)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
