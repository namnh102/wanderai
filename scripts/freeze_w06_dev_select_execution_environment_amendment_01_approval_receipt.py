#!/usr/bin/env python3
"""Strictly offline methodology-approval receipt generator and verifier for W06 DEV-SELECT Amendment 01.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-PREP

PURPOSE:
Create and statelessly verify the strictly offline candidate approval receipt
(`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-V1`) layered on top
of the immutable, already-merged formal decision artifact
(`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-DECISION-V1`) and its bound 9-cell
canary manifest (`W06-DEV-SELECT-AMENDMENT-01-CANARY-ASSIGNMENT-MANIFEST-V1`).

STRICT FIREWALLS:
- Approves METHODOLOGY ONLY (`approval_scope = "METHODOLOGY_ONLY"`, `AMENDMENT_APPROVED = true`).
- Does NOT modify the merged formal decision artifact (`2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf`),
  which intentionally preserves its historical state (`AMENDMENT_METHODOLOGY_SELECTED = true`, `AMENDMENT_APPROVED = false`).
- Does NOT modify the merged canary manifest (`3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96`).
- Does NOT authorize or execute any live provider call (`AMENDED_CANARY_LIVE_AUTHORIZED = false`,
  `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_AUTHORIZED = false`,
  `AMENDED_LIVE_EXECUTED = false`, `LIVE_PROVIDER_CALLS_NEW = 0`).
- Does NOT attest provider readiness (`C1/C2/C3_PROVIDER_READINESS = "NOT_YET_ATTESTED"`).
- Does NOT select a model (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`).
- Does NOT touch Final100 (`FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`).
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
    ORDERED_CANDIDATE_IDS,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    canonical_json_bytes,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as _dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-PREP"
APPROVAL_RECEIPT_ARTIFACT_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-V1"
)
APPROVAL_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approval_receipt_v1.json"
)
APPROVAL_RECEIPT_DOC_REL_PATH = (
    "docs/research/w06_dev_select_execution_environment_amendment_01_approval_receipt.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
FORMAL_DECISION_PR_NUMBER = 68
FORMAL_DECISION_PR_STATE = "MERGED"
FORMAL_DECISION_MERGE_COMMIT_SHA = "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
FORMAL_DECISION_MERGE_PARENT_1 = "bc913ed61097f26db8eae87b9fe47d1869dc3ec5"
FORMAL_DECISION_MERGE_PARENT_2 = "b745067e7e1949a3dfc2ee4974522913ca0c6a39"

POST_MERGE_CI_RUN_ID = 40094419087
POST_MERGE_CI_EVENT = "push"
POST_MERGE_CI_HEAD_SHA = "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
POST_MERGE_CI_CONCLUSION = "success"
POST_MERGE_CI_REQUIRED_JOBS: dict[str, str] = {
    "ai-service": "success",
    "backend": "success",
    "data-contract": "success",
    "mobile": "success",
}

APPROVAL_AUTHORITY = "CHATGPT"
APPROVAL_SCOPE = "METHODOLOGY_ONLY"
TRACK_CLASSIFICATION = (
    "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
)
EXACT_APPROVAL_STATEMENT = (
    "ChatGPT, acting as final methodology decision authority, approved the frozen "
    "secondary post-hoc execution-environment stabilization methodology after "
    "independent audit of the formal decision artifact, normal merge of PR #68, "
    "and successful post-merge CI on the exact merge SHA."
)
APPROVAL_FIREWALL_STATEMENT = (
    "AMENDMENT_APPROVED=true does NOT imply any provider readiness, live-call "
    "authorization, canary authorization, or comparative authorization."
)

RECEIPT_CANDIDATE_STATUS = "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE"
REPOSITORY_AUTHORITATIVE_BEFORE_MERGE = False
BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI = True

PROVIDER_READINESS_NOT_YET_ATTESTED = "NOT_YET_ATTESTED"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-CHATGPT-AUDIT"
)

# Bound upstream artifact hashes
DECISION_ARTIFACT_REL_PATH = _dec_mod.DECISION_ARTIFACT_REL_PATH
EXPECTED_DECISION_ARTIFACT_FILE_SHA256 = (
    "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
)
EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256 = (
    "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
)

CANARY_MANIFEST_REL_PATH = _dec_mod.CANARY_MANIFEST_REL_PATH
EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
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
EXPECTED_DIAGNOSTIC_FILE_SHA256 = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_DIAGNOSTIC_INTERNAL_SHA256 = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)
EXPECTED_DEV_FIXTURES_FREEZE_SHA256 = (
    "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
)

CANARY_CALL_ORDER_MATRIX: tuple[str, ...] = (
    "01 W06-DEV-TUNE-007 × C1",
    "02 W06-DEV-TUNE-007 × C2",
    "03 W06-DEV-TUNE-007 × C3",
    "04 W06-DEV-TUNE-011 × C1",
    "05 W06-DEV-TUNE-011 × C2",
    "06 W06-DEV-TUNE-011 × C3",
    "07 W06-DEV-TUNE-015 × C1",
    "08 W06-DEV-TUNE-015 × C2",
    "09 W06-DEV-TUNE-015 × C3",
)

# Deterministic self-hashes for the approval receipt artifact
EXPECTED_APPROVAL_RECEIPT_FILE_SHA256 = (
    "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
)
EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256 = (
    "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
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


def _assert_not_decision_or_canary_artifact(path: Path, repo_root: Path) -> None:
    resolved = path.resolve()
    decision_path = (repo_root / DECISION_ARTIFACT_REL_PATH).resolve()
    canary_path = (repo_root / CANARY_MANIFEST_REL_PATH).resolve()
    if resolved == decision_path:
        raise PlanBeforeLiveProtocolError(
            f"DECISION_ARTIFACT_MUTATION_FORBIDDEN: {resolved}"
        )
    if resolved == canary_path:
        raise PlanBeforeLiveProtocolError(
            f"CANARY_MANIFEST_MUTATION_FORBIDDEN: {resolved}"
        )


def _verify_git_base_and_merge_lineage(repo_root: Path) -> None:
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
                f"GIT_BASE_LINEAGE_MISMATCH: HEAD does not descend from {AUTHORITATIVE_BASE_DEVELOP_SHA}"
            )

        p1_cat = subprocess.run(
            ["git", "cat-file", "-e", f"{FORMAL_DECISION_MERGE_COMMIT_SHA}^1"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        p2_cat = subprocess.run(
            ["git", "cat-file", "-e", f"{FORMAL_DECISION_MERGE_COMMIT_SHA}^2"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if p1_cat.returncode == 0 and p2_cat.returncode == 0:
            p1 = subprocess.run(
                ["git", "rev-parse", f"{FORMAL_DECISION_MERGE_COMMIT_SHA}^1"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            p2 = subprocess.run(
                ["git", "rev-parse", f"{FORMAL_DECISION_MERGE_COMMIT_SHA}^2"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if p1 != FORMAL_DECISION_MERGE_PARENT_1:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_1_MISMATCH: expected {FORMAL_DECISION_MERGE_PARENT_1}, got {p1}"
                )
            if p2 != FORMAL_DECISION_MERGE_PARENT_2:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_2_MISMATCH: expected {FORMAL_DECISION_MERGE_PARENT_2}, got {p2}"
                )


def derive_effective_amendment_state(
    decision_payload: dict[str, Any],
    approval_receipt_payload: dict[str, Any],
) -> dict[str, Any]:
    """Derive the effective amendment state from the immutable formal decision + layered approval receipt.

    Enforces:
    1. The formal decision artifact records historical state at decision-freeze time:
       `AMENDMENT_METHODOLOGY_SELECTED = true`, `AMENDMENT_APPROVED = false`.
       This is NOT a contradiction; it is the immutable pre-merge state.
    2. The layered approval receipt records:
       `AMENDMENT_METHODOLOGY_SELECTED = true`, `AMENDMENT_APPROVED = true`,
       `approval_scope = "METHODOLOGY_ONLY"`, bound to the exact decision SHA256s,
       PR #68 merge commit/parents, and post-merge CI run.
    3. Together they derive `effective_methodology_approved = true` (`METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED`),
       while NEVER deriving `amended_live_authorized = true`, `amended_canary_live_authorized = true`,
       or `amended_comparative_live_authorized = true`.
    """
    if decision_payload.get("artifact_id") != _dec_mod.DECISION_ARTIFACT_ID:
        raise PlanBeforeLiveProtocolError("INVALID_DECISION_ARTIFACT_ID")
    if decision_payload.get("AMENDMENT_METHODOLOGY_SELECTED") is not True:
        raise PlanBeforeLiveProtocolError(
            "DECISION_METHODOLOGY_SELECTED_MUST_BE_TRUE"
        )
    if decision_payload.get("AMENDMENT_APPROVED") is not False:
        raise PlanBeforeLiveProtocolError(
            "HISTORICAL_DECISION_ARTIFACT_MUST_PRESERVE_AMENDMENT_APPROVED_FALSE"
        )

    if (
        approval_receipt_payload.get("artifact_id")
        != APPROVAL_RECEIPT_ARTIFACT_ID
    ):
        raise PlanBeforeLiveProtocolError("INVALID_APPROVAL_RECEIPT_ARTIFACT_ID")
    if approval_receipt_payload.get("approval_authority") != APPROVAL_AUTHORITY:
        raise PlanBeforeLiveProtocolError("INVALID_APPROVAL_AUTHORITY")
    if approval_receipt_payload.get("approval_scope") != APPROVAL_SCOPE:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_APPROVAL_SCOPE: expected {APPROVAL_SCOPE}, got {approval_receipt_payload.get('approval_scope')}"
        )
    if approval_receipt_payload.get("AMENDMENT_METHODOLOGY_SELECTED") is not True:
        raise PlanBeforeLiveProtocolError(
            "RECEIPT_METHODOLOGY_SELECTED_MUST_BE_TRUE"
        )
    if approval_receipt_payload.get("AMENDMENT_APPROVED") is not True:
        raise PlanBeforeLiveProtocolError("RECEIPT_AMENDMENT_APPROVED_MUST_BE_TRUE")

    bound_decision = approval_receipt_payload.get("bound_authorities", {}).get(
        "formal_decision", {}
    )
    if (
        bound_decision.get("decision_artifact_internal_sha256")
        != decision_payload.get("decision_artifact_internal_sha256")
    ):
        raise PlanBeforeLiveProtocolError(
            "RECEIPT_DECISION_INTERNAL_SHA256_BINDING_MISMATCH"
        )

    for live_flag in (
        "AMENDED_CANARY_LIVE_AUTHORIZED",
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED",
        "AMENDED_LIVE_AUTHORIZED",
        "AMENDED_LIVE_EXECUTED",
        "CANARY_EXECUTED",
        "COMPARATIVE_EXECUTED",
    ):
        if approval_receipt_payload.get(live_flag) is not False:
            raise PlanBeforeLiveProtocolError(
                f"METHODOLOGY_APPROVAL_MUST_NOT_DERIVE_LIVE_EXECUTION_OR_AUTHORIZATION: {live_flag} must be False"
            )

    if approval_receipt_payload.get("LIVE_PROVIDER_CALLS_NEW") != 0:
        raise PlanBeforeLiveProtocolError("LIVE_PROVIDER_CALLS_NEW_MUST_BE_ZERO")

    return {
        "derivation_rule": (
            "decision.AMENDMENT_METHODOLOGY_SELECTED == true "
            "AND decision.AMENDMENT_APPROVED == false (historical immutable decision freeze) "
            "AND approval_receipt.AMENDMENT_METHODOLOGY_SELECTED == true "
            "AND approval_receipt.AMENDMENT_APPROVED == true "
            "AND approval_receipt.approval_scope == 'METHODOLOGY_ONLY' "
            "=> methodology_approved = true, amended_live_authorized = false"
        ),
        "decision_historical_amendment_methodology_selected": True,
        "decision_historical_amendment_approved": False,
        "historical_decision_amendment_approved_false_preserved": True,
        "historical_decision_contradiction": False,
        "approval_receipt_amendment_methodology_selected": True,
        "approval_receipt_amendment_approved": True,
        "approval_scope": APPROVAL_SCOPE,
        "effective_methodology_selected": True,
        "effective_methodology_approved": True,
        "effective_amendment_status": "METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED",
        "methodology_approval_derives_live_authorization": False,
        "effective_amended_canary_live_authorized": False,
        "effective_amended_comparative_live_authorized": False,
        "effective_amended_live_authorized": False,
        "effective_amended_live_executed": False,
        "effective_live_provider_calls_new": 0,
    }


def _verify_all_upstream_authorities(repo_root: Path) -> dict[str, Any]:
    _verify_git_base_and_merge_lineage(repo_root)

    # Verify primary freeze, diagnostic, prep, and formal decision verifiers
    freeze_summary = (
        _freeze_mod.verify_committed_results_freeze_artifacts_from_disk(
            repo_root=repo_root, verify_preflight_dry_run=False
        )
    )
    if not freeze_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("PRIMARY_FREEZE_VERIFICATION_FAILED")

    diag_summary = _diag_mod.verify_w06_dev_select_failure_diagnostic(
        repo_root=repo_root
    )
    if not diag_summary.get("verified"):
        raise PlanBeforeLiveProtocolError(
            "FAILURE_DIAGNOSTIC_VERIFICATION_FAILED"
        )

    prep_summary = (
        _prep_mod.verify_w06_execution_environment_amendment_prep(
            repo_root=repo_root
        )
    )
    if not prep_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("PREP_ARTIFACT_VERIFICATION_FAILED")

    dec_summary = (
        _dec_mod.verify_w06_execution_environment_amendment_decision_freeze(
            repo_root=repo_root
        )
    )
    if not dec_summary.get("verified"):
        raise PlanBeforeLiveProtocolError(
            "DECISION_FREEZE_VERIFICATION_FAILED"
        )

    decision_path = repo_root / DECISION_ARTIFACT_REL_PATH
    decision_file_sha = _read_lf_sha256(decision_path)
    if decision_file_sha != EXPECTED_DECISION_ARTIFACT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DECISION_ARTIFACT_FILE_SHA256_MISMATCH: expected {EXPECTED_DECISION_ARTIFACT_FILE_SHA256}, got {decision_file_sha}"
        )
    decision_payload = _load_json_dict(decision_path)
    if (
        decision_payload.get("decision_artifact_internal_sha256")
        != EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "DECISION_ARTIFACT_INTERNAL_SHA256_MISMATCH"
        )
    if decision_payload.get("AMENDMENT_METHODOLOGY_SELECTED") is not True:
        raise PlanBeforeLiveProtocolError(
            "DECISION_ARTIFACT_METHODOLOGY_SELECTED_MUST_BE_TRUE"
        )
    if decision_payload.get("AMENDMENT_APPROVED") is not False:
        raise PlanBeforeLiveProtocolError(
            "DECISION_ARTIFACT_HISTORICAL_AMENDMENT_APPROVED_MUST_REMAIN_FALSE"
        )

    # Cross-bind primary results-freeze receipt internal SHA across _freeze_mod, decision, and disk receipt
    if (
        EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        != _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MODULE_CONSTANT_MISMATCH"
        )
    if (
        decision_payload.get("bound_authorities", {}).get(
            "primary_results_freeze_receipt_internal_sha256"
        )
        != _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "DECISION_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH"
        )
    freeze_receipt_doc = _load_json_dict(
        repo_root / _freeze_mod.RESULTS_FREEZE_RECEIPT_REL_PATH
    )
    if (
        freeze_receipt_doc.get("results_freeze_receipt_sha256")
        != _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "DISK_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH"
        )

    canary_path = repo_root / CANARY_MANIFEST_REL_PATH
    canary_file_sha = _read_lf_sha256(canary_path)
    if canary_file_sha != EXPECTED_CANARY_MANIFEST_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"CANARY_MANIFEST_FILE_SHA256_MISMATCH: expected {EXPECTED_CANARY_MANIFEST_FILE_SHA256}, got {canary_file_sha}"
        )
    canary_payload = _load_json_dict(canary_path)
    if (
        canary_payload.get("canary_manifest_internal_sha256")
        != EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_MANIFEST_INTERNAL_SHA256_MISMATCH"
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: expected {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got {bundle_sha}"
        )

    dev_bundle = load_and_verify_frozen_dev_bundle()
    if (
        len(dev_bundle.dev_tune_fixtures) != 20
        or len(dev_bundle.dev_select_fixtures) != 60
    ):
        raise PlanBeforeLiveProtocolError("DEV_FIXTURE_BUNDLE_COUNT_MISMATCH")

    cand_reg = load_and_verify_candidate_registry()
    if (
        cand_reg.registry_sha256
        != _dec_mod.EXPECTED_CANDIDATE_REGISTRY_SHA256
    ):
        raise PlanBeforeLiveProtocolError("CANDIDATE_REGISTRY_SHA256_MISMATCH")

    if (
        compute_provider_config_registry_sha256(cand_reg)
        != _dec_mod.EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH"
        )

    final100_sha = _read_lf_sha256(
        repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    )
    if final100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError("FINAL100_SCENARIOS_FREEZE_TOUCHED")
    p11_sha = _read_lf_sha256(
        repo_root / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    )
    if p11_sha != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError("P11_MANIFEST_TOUCHED")

    return {
        "decision_payload": decision_payload,
        "canary_payload": canary_payload,
    }


# ==============================================================================
# 3. BUILD CANDIDATE APPROVAL RECEIPT PAYLOAD
# ==============================================================================


def build_w06_execution_environment_amendment_approval_receipt_payload(
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    with NetworkKillSwitchGuard():
        verified = _verify_all_upstream_authorities(repo_root)
        decision_payload = verified["decision_payload"]
        decision_bundle = decision_payload["frozen_selected_policy_bundle"]

        payload_without_hash: dict[str, Any] = {
            "artifact_id": APPROVAL_RECEIPT_ARTIFACT_ID,
            "task_id": TASK_ID,
            "schema_version": "1.0.0",
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "approval_authority": APPROVAL_AUTHORITY,
            "approval_scope": APPROVAL_SCOPE,
            "track_classification": TRACK_CLASSIFICATION,
            "primary_experiment_classification": _dec_mod.PRIMARY_EXPERIMENT_CLASSIFICATION,
            "AMENDMENT_METHODOLOGY_SELECTED": True,
            "AMENDMENT_APPROVED": True,
            "approval_statement": EXACT_APPROVAL_STATEMENT,
            "approval_firewall_statement": APPROVAL_FIREWALL_STATEMENT,
            "receipt_candidate_status": RECEIPT_CANDIDATE_STATUS,
            "repository_authoritative_before_merge": REPOSITORY_AUTHORITATIVE_BEFORE_MERGE,
            "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci": BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI,
            "receipt_authority_model": {
                "receipt_candidate_status": RECEIPT_CANDIDATE_STATUS,
                "repository_authoritative_before_merge": REPOSITORY_AUTHORITATIVE_BEFORE_MERGE,
                "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci": BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI,
                "required_steps_for_repository_authority": [
                    "1. ChatGPT independent audit = PASS",
                    "2. normal merge into develop",
                    "3. successful post-merge CI on exact develop merge SHA",
                ],
            },
            "bound_authorities": {
                "formal_decision": {
                    "artifact_id": _dec_mod.DECISION_ARTIFACT_ID,
                    "decision_artifact_path": DECISION_ARTIFACT_REL_PATH,
                    "decision_artifact_file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
                    "decision_artifact_internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
                    "historical_decision_amendment_methodology_selected": True,
                    "historical_decision_amendment_approved": False,
                    "historical_decision_state_immutable": True,
                },
                "canary_manifest": {
                    "artifact_id": _dec_mod.CANARY_MANIFEST_ID,
                    "path": CANARY_MANIFEST_REL_PATH,
                    "file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
                    "internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
                },
                "formal_decision_merge": {
                    "pr_number": FORMAL_DECISION_PR_NUMBER,
                    "pr_state": FORMAL_DECISION_PR_STATE,
                    "merge_commit_sha": FORMAL_DECISION_MERGE_COMMIT_SHA,
                    "parent1": FORMAL_DECISION_MERGE_PARENT_1,
                    "parent2": FORMAL_DECISION_MERGE_PARENT_2,
                    "merge_method": "NORMAL_MERGE_COMMIT",
                },
                "post_merge_ci": {
                    "run_id": POST_MERGE_CI_RUN_ID,
                    "exact_head_sha": POST_MERGE_CI_HEAD_SHA,
                    "event": POST_MERGE_CI_EVENT,
                    "conclusion": POST_MERGE_CI_CONCLUSION,
                    "required_jobs": dict(POST_MERGE_CI_REQUIRED_JOBS),
                },
                "prep_authorities": {
                    "prep_artifact_path": PREP_ARTIFACT_REL_PATH,
                    "prep_artifact_file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
                    "prep_artifact_internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
                },
                "primary_authorities": {
                    "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
                    "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
                    "results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
                    "results_manifest_internal_sha256": EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256,
                    "results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                    "results_freeze_receipt_internal_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
                    "diagnostic_file_sha256": EXPECTED_DIAGNOSTIC_FILE_SHA256,
                    "diagnostic_internal_sha256": EXPECTED_DIAGNOSTIC_INTERNAL_SHA256,
                    "dev_fixtures_freeze_sha256": EXPECTED_DEV_FIXTURES_FREEZE_SHA256,
                    "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                    "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
                },
            },
            "approved_frozen_policy": {
                "FAIRNESS_POLICY": _dec_mod.SELECTED_FAIRNESS_POLICY_ID,
                "TIMEOUT_POLICY": {
                    "timeout_policy_id": _dec_mod.SELECTED_TIMEOUT_POLICY_ID,
                    "timeout_ms": _dec_mod.SELECTED_TIMEOUT_MS,
                    "timeout_seconds": _dec_mod.SELECTED_TIMEOUT_SECONDS,
                    "timeout_applies_symmetrically_to": list(ORDERED_CANDIDATE_IDS),
                    "timeout_ms_by_candidate": {
                        cid: _dec_mod.SELECTED_TIMEOUT_MS
                        for cid in ORDERED_CANDIDATE_IDS
                    },
                    "guarantees_completion": False,
                    "scientific_wording": decision_bundle["timeout_policy"][
                        "scientific_wording"
                    ],
                },
                "PACING_POLICY": {
                    "pacing_policy_id": _dec_mod.SELECTED_PACING_POLICY_ID,
                    "inter_call_delay_ms": _dec_mod.SELECTED_INTER_CALL_DELAY_MS,
                    "fixed": True,
                    "deterministic": True,
                    "adaptive": False,
                    "response_dependent": False,
                    "prevents_provider_http_503_or_high_demand_failures_claimed": False,
                    "scientific_wording": decision_bundle["pacing_policy"][
                        "scientific_wording"
                    ],
                },
                "RETRY_POLICY": {
                    "retry_policy_id": _dec_mod.SELECTED_RETRY_POLICY_ID,
                    "retry": 0,
                    "automatic_retry": 0,
                    "transport_retry": 0,
                    "manual_retry": 0,
                    "llm_repair": 0,
                    "semantic_repair": 0,
                    "fallback": False,
                },
                "FIXTURE_POLICY": _dec_mod.SELECTED_FIXTURE_POLICY_ID,
                "CALL_BUDGET_POLICY": {
                    "call_budget_policy_id": _dec_mod.SELECTED_CALL_BUDGET_POLICY_ID,
                    "readiness_canary_assigned_calls": _dec_mod.FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
                    "comparative_assigned_calls": _dec_mod.FROZEN_COMPARATIVE_ASSIGNED_CALLS,
                    "maximum_generation_calls": _dec_mod.FROZEN_MAXIMUM_GENERATION_CALLS,
                    "calls_per_candidate_max": _dec_mod.FROZEN_CALLS_PER_CANDIDATE_MAX,
                },
            },
            "canary_authorities": {
                "exact_fixture_ids": list(_dec_mod.FROZEN_CANARY_FIXTURE_IDS),
                "exact_assigned_canary_cells": _dec_mod.FROZEN_READINESS_CANARY_ASSIGNED_CALLS,
                "exact_call_matrix_order": list(CANARY_CALL_ORDER_MATRIX),
                "pacing_inter_call_delay_ms": _dec_mod.SELECTED_INTER_CALL_DELAY_MS,
                "selection_weight": 0,
                "canary_gate_pass_requirement": "9/9 operational PASS",
                "required_operational_pass_count": 9,
                "required_pass_fraction": "9/9",
                "planner_quality_results_determine_operational_readiness": False,
                "successful_provider_response_failing_schema_or_core_is_operational_pass": True,
                "canary_pass_automatically_authorizes_or_launches_comparative_benchmark": False,
                "separate_chatgpt_authorization_required_for_180_cell_comparative_benchmark": True,
                "if_any_cell_operationally_fails": {
                    "CANARY_GATE_PASS": False,
                    "AMENDED_COMPARATIVE_AUTHORIZED": False,
                    "next_action": "RETURN_TO_CHATGPT_HOLD",
                },
            },
            "provider_readiness_status": {
                "C1_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "C2_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "C3_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION": True,
                "OWNER_PROVIDER_ACTION_REQUIRED_BEFORE_CANARY_AUTHORIZATION": True,
                "owner_and_provider_attestation_distinct_from_live_readiness_canary": True,
                "api_keys_inspected_read_printed_hashed_or_transmitted": False,
                "live_api_calls_made_to_validate_provider_readiness": False,
            },
            "C1_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "C2_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "C3_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION": True,
            "OWNER_PROVIDER_ACTION_REQUIRED_BEFORE_CANARY_AUTHORIZATION": True,
            "AMENDED_CANARY_LIVE_AUTHORIZED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "CANARY_EXECUTED": False,
            "COMPARATIVE_EXECUTED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "NEXT_GATE": NEXT_GATE_ID,
        }

        effective_state = derive_effective_amendment_state(
            decision_payload=decision_payload,
            approval_receipt_payload=payload_without_hash,
        )
        payload_without_hash["effective_amendment_state"] = effective_state

        internal_sha = sha256_bytes(canonical_json_bytes(payload_without_hash))
        full_payload = dict(payload_without_hash)
        full_payload["approval_receipt_internal_sha256"] = internal_sha
        assert_no_secrets_in_payload(
            full_payload, context=APPROVAL_RECEIPT_ARTIFACT_ID
        )
        return full_payload


# ==============================================================================
# 4. WRITE & STATELESS VERIFY FUNCTIONS
# ==============================================================================


def write_w06_execution_environment_amendment_approval_receipt(
    *,
    receipt_path: Path = REPO_ROOT / APPROVAL_RECEIPT_REL_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    _assert_not_inside_raw_evidence(receipt_path, repo_root)
    _assert_not_decision_or_canary_artifact(receipt_path, repo_root)

    payload = build_w06_execution_environment_amendment_approval_receipt_payload(
        repo_root=repo_root
    )
    serialized = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(serialized.encode("utf-8"))
    file_sha = _read_lf_sha256(receipt_path)

    return {
        "approval_receipt_path": receipt_path.relative_to(repo_root).as_posix()
        if receipt_path.is_relative_to(repo_root)
        else str(receipt_path),
        "approval_receipt_file_sha256": file_sha,
        "approval_receipt_internal_sha256": payload[
            "approval_receipt_internal_sha256"
        ],
    }


def verify_w06_execution_environment_amendment_approval_receipt(
    *,
    receipt_path: Path = REPO_ROOT / APPROVAL_RECEIPT_REL_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    with NetworkKillSwitchGuard():
        _assert_not_inside_raw_evidence(receipt_path, repo_root)
        _assert_not_decision_or_canary_artifact(receipt_path, repo_root)

        if not receipt_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_APPROVAL_RECEIPT_ARTIFACT: {receipt_path}"
            )

        raw_bytes = normalize_lf_bytes(receipt_path.read_bytes())
        disk_payload = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(disk_payload, dict):
            raise PlanBeforeLiveProtocolError(
                "APPROVAL_RECEIPT_MUST_BE_JSON_OBJECT"
            )

        assert_no_secrets_in_payload(
            disk_payload, context="DISK_APPROVAL_RECEIPT_ARTIFACT"
        )

        expected_formatted_bytes = (
            json.dumps(
                disk_payload, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n"
        ).encode("utf-8")
        if raw_bytes != expected_formatted_bytes:
            raise PlanBeforeLiveProtocolError(
                "APPROVAL_RECEIPT_NOT_DETERMINISTIC_FORMATTED_JSON"
            )

        recorded_internal = disk_payload.get("approval_receipt_internal_sha256")
        disk_without_internal = {
            k: v
            for k, v in disk_payload.items()
            if k != "approval_receipt_internal_sha256"
        }
        recomputed_internal = sha256_bytes(
            canonical_json_bytes(disk_without_internal)
        )
        if recorded_internal != recomputed_internal:
            raise PlanBeforeLiveProtocolError(
                f"APPROVAL_RECEIPT_INTERNAL_SHA256_TAMPERED: recorded {recorded_internal}, recomputed {recomputed_internal}"
            )

        prim_auth = disk_payload.get("bound_authorities", {}).get(
            "primary_authorities", {}
        )
        if (
            prim_auth.get("results_freeze_receipt_internal_sha256")
            != _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "APPROVAL_RECEIPT_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH"
            )

        expected_payload = (
            build_w06_execution_environment_amendment_approval_receipt_payload(
                repo_root=repo_root
            )
        )
        if disk_payload != expected_payload:
            raise PlanBeforeLiveProtocolError(
                "APPROVAL_RECEIPT_CONTENT_DRIFT_FROM_DETERMINISTIC_REBUILD"
            )

        file_sha = sha256_bytes(raw_bytes)
        if (
            EXPECTED_APPROVAL_RECEIPT_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and file_sha != EXPECTED_APPROVAL_RECEIPT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"APPROVAL_RECEIPT_FILE_SHA256_MISMATCH: expected {EXPECTED_APPROVAL_RECEIPT_FILE_SHA256}, got {file_sha}"
            )
        if (
            EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and recorded_internal != EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"APPROVAL_RECEIPT_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256}, got {recorded_internal}"
            )

        decision_payload = _load_json_dict(repo_root / DECISION_ARTIFACT_REL_PATH)
        effective_state = derive_effective_amendment_state(
            decision_payload=decision_payload,
            approval_receipt_payload=disk_payload,
        )

        return {
            "verified": True,
            "task_id": TASK_ID,
            "artifact_id": APPROVAL_RECEIPT_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "approval_authority": APPROVAL_AUTHORITY,
            "approval_scope": APPROVAL_SCOPE,
            "amendment_methodology_selected": disk_payload[
                "AMENDMENT_METHODOLOGY_SELECTED"
            ],
            "amendment_approved": disk_payload["AMENDMENT_APPROVED"],
            "receipt_candidate_status": disk_payload[
                "receipt_candidate_status"
            ],
            "repository_authoritative_before_merge": disk_payload[
                "repository_authoritative_before_merge"
            ],
            "effective_amendment_status": effective_state[
                "effective_amendment_status"
            ],
            "approval_receipt_file_sha256": file_sha,
            "approval_receipt_internal_sha256": recorded_internal,
            "decision_artifact_file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
            "decision_artifact_internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
            "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
            "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
            "formal_decision_merge_commit_sha": FORMAL_DECISION_MERGE_COMMIT_SHA,
            "post_merge_ci_run_id": POST_MERGE_CI_RUN_ID,
            "c1_provider_readiness": disk_payload["C1_PROVIDER_READINESS"],
            "c2_provider_readiness": disk_payload["C2_PROVIDER_READINESS"],
            "c3_provider_readiness": disk_payload["C3_PROVIDER_READINESS"],
            "external_pricing_refresh_required_before_authorization": disk_payload[
                "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION"
            ],
            "owner_provider_action_required_before_canary_authorization": disk_payload[
                "OWNER_PROVIDER_ACTION_REQUIRED_BEFORE_CANARY_AUTHORIZATION"
            ],
            "amended_canary_live_authorized": disk_payload[
                "AMENDED_CANARY_LIVE_AUTHORIZED"
            ],
            "amended_comparative_live_authorized": disk_payload[
                "AMENDED_COMPARATIVE_LIVE_AUTHORIZED"
            ],
            "amended_live_authorized": disk_payload["AMENDED_LIVE_AUTHORIZED"],
            "amended_live_executed": disk_payload["AMENDED_LIVE_EXECUTED"],
            "live_provider_calls_new": disk_payload["LIVE_PROVIDER_CALLS_NEW"],
            "canary_executed": disk_payload["CANARY_EXECUTED"],
            "comparative_executed": disk_payload["COMPARATIVE_EXECUTED"],
            "model_winner_selected": disk_payload["MODEL_WINNER_SELECTED"],
            "selected_model_id": disk_payload["SELECTED_MODEL_ID"],
            "stochasticity_execution_started": disk_payload[
                "STOCHASTICITY_EXECUTION_STARTED"
            ],
            "final100_used": disk_payload["FINAL100_USED"],
            "final100_status": disk_payload["FINAL100_STATUS"],
            "primary_experiment_mutated": disk_payload[
                "PRIMARY_EXPERIMENT_MUTATED"
            ],
            "primary_results_replaced": disk_payload[
                "PRIMARY_RESULTS_REPLACED"
            ],
            "primary_denominators_changed": disk_payload[
                "PRIMARY_DENOMINATORS_CHANGED"
            ],
            "next_gate": disk_payload["NEXT_GATE"],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Strictly offline W06 DEV-SELECT Execution-Environment Amendment 01 "
            "Approval Receipt Prep generator and verifier."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the existing approval receipt artifact without modifying any files.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Deterministically write the approval receipt artifact.",
    )
    args = parser.parse_args(argv)

    if args.write:
        written = write_w06_execution_environment_amendment_approval_receipt(
            repo_root=REPO_ROOT
        )
        print(json.dumps(written, indent=2, sort_keys=True))
    summary = verify_w06_execution_environment_amendment_approval_receipt(
        repo_root=REPO_ROOT
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
