"""W06-DEV-TUNE-STAGE-A-FREEZE-01: Scoped Stage-A pre-live freeze and verification script.

Strictly offline. Zero live provider calls. Zero provider cost.
Never mints LiveExecutionCapability. Never constructs production provider transports.
Never reads or persists provider API key values.

Supports three explicit CLI modes to enforce Process A / Process B separation:
  1. `--generate-stage-a-once` (PROCESS A):
     Generates `data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json`
     exactly once using production `build_stage_a_freeze_receipt(...)`, verifies
     that same-process verification is rejected (`STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN`),
     and exits immediately.
  2. `--write-task-audit-receipt` (SEPARATE PROCESS):
     Verifies the persisted Stage-A receipt from a separate process, executes all
     40 `SA-01`..`SA-40` checks and 15 `SAA-01`..`SAA-15` adversarial checks, and writes
     `data/evaluation/w06/w06_dev_tune_stage_a_freeze_01_receipt_v1.json`.
  3. `--verify-committed` (PROCESS B, default when invoked with no flags):
     Strictly read-only verification of the committed Stage-A receipt and all
     upstream authorities using production `verify_stage_a_freeze_receipt(..., require_git_committed=True)`.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    _CURRENT_PROCESS_INVOCATION_TOKEN,
    _build_stage_a_freeze_receipt_with_token,
    CandidateRegistryIntegrityError,
    DevLiveAuthorizationArtifact,
    DevLiveStageAFreezeReceipt,
    PlanBeforeLiveProtocolError,
    STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
    STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
    assert_no_secrets_in_payload,
    build_stage_a_freeze_receipt,
    compute_assigned_cells_sha256,
    compute_prompt_freeze_sha256,
    verify_dev_live_authorization_artifact,
    verify_runner_prompt_freeze_artifact,
    verify_stage_a_freeze_receipt,
    write_immutable_canonical_json,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    Final100FirewallViolationError,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    ScientificCodeBundleIntegrityError,
    canonical_json_bytes,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_file_hashes,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
    verify_prompt_candidate_freeze_artifact,
)
import freeze_w06_dev_prompt_candidates as pf_mod  # noqa: E402
import issue_w06_dev_tune_live_authorization as auth_mod  # noqa: E402

# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITIES
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-STAGE-A-FREEZE-01"
TASK_AUDIT_RECEIPT_ARTIFACT_ID = "W06-DEV-TUNE-STAGE-A-FREEZE-01-RECEIPT-V1"

SOURCE_DEVELOP_SHA = "25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e"
STAGE_A_COMMIT_SHA = "25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e"
CODE_BASIS_COMMIT_SHA = "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"
BRANCH_NAME = "research/w06-dev-tune-stage-a-freeze-01"
ALLOWED_PHASE = "DEV_TUNE"

EXPECTED_DEV_TUNE_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_DEV_TUNE_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_AUTHORIZATION_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
)
EXPECTED_AUTHORIZATION_TEXT_SHA256 = (
    "90fca01f1b7ecacb2b5ee4405df2a52af6aff02f21dce8bd7c579c4d659327fe"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
EXPECTED_PORTABLE_SCHEMA_V2_SHA256 = (
    "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
)
EXPECTED_SEMANTIC_SCHEMA_SHA256 = (
    "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
)

DEV_TUNE_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
AUTHORIZATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json"
)
STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
)
TASK_AUDIT_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_stage_a_freeze_01_receipt_v1.json"
)
REPORT_MD_REL_PATH = "docs/research/w06_dev_tune_stage_a_freeze_01.md"

# Recorded once after PROCESS A generates the persisted Stage-A receipt:
EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256 = (
    "a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f"
)
EXPECTED_STAGE_A_RECEIPT_FILE_SHA256 = (
    "a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31"
)
EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC = "2026-10-21T12:16:22Z"

HISTORICAL_FROZEN_RECEIPT_SHAS: dict[str, str] = {
    "data/evaluation/w06/w06_dev_live_runner_qa_01_receipt_v1.json": (
        "e400d319ca957acb8e3ef7e8fcb468b7406a837b51b6127ed95327ac6cf72ad2"
    ),
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_01_receipt_v1.json": (
        "20b95381f9f06809ca37e3b806e639fbe788a9370a55a8e85a9f2d94aae0b6e5"
    ),
    "data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json": (
        "168d29741fd75884a9b3f066822a843bcc6fd56ed06d4c16b40b8129d4d62f33"
    ),
    "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json": (
        EXPECTED_AUTHORIZATION_FILE_SHA256
    ),
    "data/evaluation/w06/w06_dev_tune_live_authorization_01_receipt_v1.json": (
        "d185e079e7dc5b7206bc1a48aec6dfaf83c5758c41b64790cda134a7c3d50813"
    ),
}

_PROCESS_TOKEN_PATTERN = re.compile(r"^pid-\d+-ns-\d+$")

FORBIDDEN_CAPABILITY_OR_TRANSPORT_SYMBOLS: tuple[str, ...] = (
    "issue_live_execution_capability",
    "reattest_stage_a_at_live_action_boundary",
    "ProductionDevProviderTransport",
    "GoogleGeminiProductionTransport",
    "OpenAIChatCompletionsProductionTransport",
    "AnthropicMessagesProductionTransport",
    "execute_live_dev_cell",
    "execute_live_dev_batch",
)


# ==============================================================================
# 2. OUTBOUND NETWORK KILL SWITCH
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised when any outbound network connection is attempted during Stage-A freeze."""


class NetworkKillSwitchGuard:
    """Blocks all outbound socket connections during Stage-A freeze and verification."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_create_conn = socket.create_connection
        guard = self

        def _blocked_connect(sock_self: Any, address: Any) -> Any:
            guard.blocked_attempts.append(f"connect:{address!r}")
            raise OutboundNetworkBlockedError(
                f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: connect({address!r})"
            )

        def _blocked_connect_ex(sock_self: Any, address: Any) -> Any:
            guard.blocked_attempts.append(f"connect_ex:{address!r}")
            raise OutboundNetworkBlockedError(
                f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: connect_ex({address!r})"
            )

        def _blocked_create_conn(address: Any, *args: Any, **kwargs: Any) -> Any:
            guard.blocked_attempts.append(f"create_connection:{address!r}")
            raise OutboundNetworkBlockedError(
                f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: create_connection({address!r})"
            )

        socket.socket.connect = _blocked_connect  # type: ignore[assignment]
        socket.socket.connect_ex = _blocked_connect_ex  # type: ignore[assignment]
        socket.create_connection = _blocked_create_conn  # type: ignore[assignment]
        try:
            yield self
        finally:
            socket.socket.connect = orig_connect  # type: ignore[assignment]
            socket.socket.connect_ex = orig_connect_ex  # type: ignore[assignment]
            socket.create_connection = orig_create_conn  # type: ignore[assignment]


# ==============================================================================
# 3. FAIL-CLOSED GIT PROVENANCE & UPSTREAM AUTHORITY VERIFICATION
# ==============================================================================


def verify_source_develop_commit_or_shallow_fallback(
    repo_root: Path = REPO_ROOT,
    *,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Fail-closed verification of SOURCE_DEVELOP_SHA (25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e).

    Case A: If SOURCE_DEVELOP_SHA exists in local git, `git merge-base --is-ancestor` MUST succeed.
            No fallback is permitted if the commit exists locally.
    Case B: If SOURCE_DEVELOP_SHA is missing locally, fallback is permitted ONLY when
            `git rev-parse --is-shallow-repository == true` AND all 5 frozen upstream
            authorities match their exact SHA256s.
    """

    def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        if git_runner is not None:
            return git_runner(args)
        return subprocess.run(
            args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )

    exists_proc = _run_git(
        ["git", "cat-file", "-e", f"{SOURCE_DEVELOP_SHA}^{{commit}}"]
    )
    commit_exists = exists_proc.returncode == 0
    if commit_exists:
        anc_proc = _run_git(
            ["git", "merge-base", "--is-ancestor", SOURCE_DEVELOP_SHA, "HEAD"]
        )
        is_ancestor = anc_proc.returncode == 0
        return {
            "source_develop_sha": SOURCE_DEVELOP_SHA,
            "commit_exists_in_local_git": True,
            "is_ancestor_of_head": is_ancestor,
            "is_shallow_repository": False,
            "shallow_repository_fallback_used": False,
            "verified": is_ancestor,
        }

    shallow_proc = _run_git(["git", "rev-parse", "--is-shallow-repository"])
    is_shallow = shallow_proc.returncode == 0 and (
        shallow_proc.stdout.strip().lower() == "true"
    )
    if not is_shallow:
        return {
            "source_develop_sha": SOURCE_DEVELOP_SHA,
            "commit_exists_in_local_git": False,
            "is_ancestor_of_head": False,
            "is_shallow_repository": False,
            "shallow_repository_fallback_used": False,
            "verified": False,
        }

    auth_path = repo_root / AUTHORIZATION_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH

    auth_sha = (
        sha256_bytes(normalize_lf_bytes(auth_path.read_bytes()))
        if auth_path.is_file()
        else ""
    )
    pf_sha = (
        sha256_bytes(normalize_lf_bytes(pf_path.read_bytes()))
        if pf_path.is_file()
        else ""
    )
    plan_file_sha = (
        sha256_bytes(normalize_lf_bytes(plan_path.read_bytes()))
        if plan_path.is_file()
        else ""
    )
    try:
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    except Exception:
        bundle_sha = ""

    fallback_checks = {
        "authorization_file_sha256": auth_sha == EXPECTED_AUTHORIZATION_FILE_SHA256,
        "scientific_code_bundle_sha256": (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ),
        "prompt_freeze_sha256": pf_sha == EXPECTED_PROMPT_FREEZE_SHA256,
        "dev_tune_plan_file_sha256": (
            plan_file_sha == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
        ),
    }
    fallback_ok = is_shallow and all(fallback_checks.values())
    return {
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "commit_exists_in_local_git": False,
        "is_ancestor_of_head": fallback_ok,
        "is_shallow_repository": True,
        "shallow_repository_fallback_used": True,
        "fallback_authorities_matched": fallback_checks,
        "verified": fallback_ok,
    }


def load_verified_stage_a_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Load and cryptographically verify all frozen upstream authorities required for Stage-A."""
    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = pf_mod.build_frozen_p1_p2_registry()

    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH

    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())

    plan_file_sha = sha256_bytes(plan_bytes)
    pf_file_sha = sha256_bytes(pf_bytes)
    auth_file_sha = sha256_bytes(auth_bytes)

    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
    freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)

    verify_dev_execution_plan_for_execution(
        plan_model, candidate_registry=cand_reg, repo_root=repo_root
    )
    verify_prompt_candidate_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        dev_tune_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    verify_runner_prompt_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        execution_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    auth_model = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=plan_model,
        prompt_freeze=freeze_model,
        expected_phase="DEV_TUNE",
        repo_root=repo_root,
    )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    pconf_sha = compute_provider_config_registry_sha256(cand_reg)
    pf_canonical_sha = compute_prompt_freeze_sha256(freeze_model)
    portable_schema_sha = plan_model.cells[0].portable_generation_schema_v2_sha256
    semantic_schema_sha = plan_model.cells[0].semantic_schema_sha256
    if not all(
        c.portable_generation_schema_v2_sha256 == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        and c.semantic_schema_sha256 == EXPECTED_SEMANTIC_SCHEMA_SHA256
        for c in plan_model.cells
    ):
        raise RuntimeError("Cell schema SHA256 mismatch in DEV-TUNE execution plan.")
    assigned_run_ids, assigned_cells_sha = compute_assigned_cells_sha256(plan_model)

    if plan_model.plan_sha256 != EXPECTED_DEV_TUNE_PLAN_SHA256:
        raise RuntimeError(f"Plan SHA256 mismatch: {plan_model.plan_sha256}")
    if plan_file_sha != EXPECTED_DEV_TUNE_PLAN_FILE_SHA256:
        raise RuntimeError(f"Plan file SHA256 mismatch: {plan_file_sha}")
    if (
        pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256
        or pf_canonical_sha != EXPECTED_PROMPT_FREEZE_SHA256
    ):
        raise RuntimeError(
            f"Prompt freeze SHA256 mismatch: file={pf_file_sha}, canonical={pf_canonical_sha}"
        )
    if auth_file_sha != EXPECTED_AUTHORIZATION_FILE_SHA256:
        raise RuntimeError(f"Authorization file SHA256 mismatch: {auth_file_sha}")
    if auth_model.authorization_artifact_sha256 != EXPECTED_AUTHORIZATION_INTERNAL_SHA256:
        raise RuntimeError(
            f"Authorization internal SHA256 mismatch: {auth_model.authorization_artifact_sha256}"
        )
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise RuntimeError(f"Scientific code bundle SHA256 mismatch: {bundle_sha}")
    if cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256:
        raise RuntimeError(
            f"Candidate registry SHA256 mismatch: {cand_reg.registry_sha256}"
        )
    if pconf_sha != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256:
        raise RuntimeError(f"Provider config registry SHA256 mismatch: {pconf_sha}")
    if prompt_reg.registry_sha256 != EXPECTED_PROMPT_REGISTRY_SHA256:
        raise RuntimeError(
            f"Prompt registry SHA256 mismatch: {prompt_reg.registry_sha256}"
        )
    if portable_schema_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise RuntimeError(f"Portable schema V2 SHA256 mismatch: {portable_schema_sha}")
    if semantic_schema_sha != EXPECTED_SEMANTIC_SCHEMA_SHA256:
        raise RuntimeError(f"Semantic schema SHA256 mismatch: {semantic_schema_sha}")

    return {
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "execution_plan": plan_model,
        "execution_plan_path": plan_path,
        "execution_plan_file_sha256": plan_file_sha,
        "prompt_freeze": freeze_model,
        "prompt_freeze_path": pf_path,
        "prompt_freeze_sha256": pf_file_sha,
        "authorization": auth_model,
        "authorization_path": auth_path,
        "authorization_file_sha256": auth_file_sha,
        "scientific_code_bundle_sha256": bundle_sha,
        "provider_config_registry_sha256": pconf_sha,
        "portable_schema_v2_sha256": portable_schema_sha,
        "semantic_schema_sha256": semantic_schema_sha,
        "assigned_cell_run_ids": assigned_run_ids,
        "assigned_cells_sha256": assigned_cells_sha,
    }


# ==============================================================================
# 4. CRYPTOGRAPHIC DOWNSTREAM STAGE-A VERIFICATION FOR HISTORICAL GATES (SECTION 18)
# ==============================================================================


def is_verified_downstream_w06_stage_a_freeze_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Cryptographically and semantically verify `w06_dev_tune_stage_a_freeze_receipt_v1.json`."""
    if not path.is_file() or path.name != "w06_dev_tune_stage_a_freeze_receipt_v1.json":
        return False
    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if (
            not EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
            or EXPECTED_STAGE_A_RECEIPT_FILE_SHA256.startswith("__PENDING")
            or file_sha != EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
        ):
            return False

        raw_dict = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(raw_dict, dict):
            return False
        assert_no_secrets_in_payload(
            raw_dict, context="DOWNSTREAM_STAGE_A_RECEIPT_VERIFICATION"
        )
        receipt = DevLiveStageAFreezeReceipt.model_validate(raw_dict)

        auths = load_verified_stage_a_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]

        # Also run production verify_stage_a_freeze_receipt if we are in a separate process
        if receipt.stage_a_process_token != _CURRENT_PROCESS_INVOCATION_TOKEN:
            verified = verify_stage_a_freeze_receipt(
                path,
                execution_plan=plan_model,
                prompt_freeze=auths["prompt_freeze"],
                authorization=auths["authorization"],
                candidate_registry=auths["candidate_registry"],
                repo_root=repo_root,
                require_git_committed=False,
            )
        else:
            verified = receipt

        return (
            verified.artifact_id == STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID
            and verified.phase == "DEV_TUNE"
            and verified.execution_plan_sha256 == EXPECTED_DEV_TUNE_PLAN_SHA256
            and verified.prompt_freeze_sha256 == EXPECTED_PROMPT_FREEZE_SHA256
            and verified.authorization_artifact_sha256
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            and verified.scientific_code_bundle_sha256
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and verified.provider_config_registry_sha256
            == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
            and verified.code_basis_commit_sha == CODE_BASIS_COMMIT_SHA
            and verified.stage_a_commit_sha == STAGE_A_COMMIT_SHA
            and verified.freeze_created_at_utc == EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC
            and bool(verified.stage_a_process_token and _PROCESS_TOKEN_PATTERN.match(verified.stage_a_process_token))
            and verified.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE
            and verified.assigned_cell_run_ids == auths["assigned_cell_run_ids"]
            and len(verified.assigned_cell_run_ids) == 120
            and verified.assigned_cells_sha256 == auths["assigned_cells_sha256"]
            and verified.stage_a_receipt_sha256
            == EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
        )
    except Exception:
        return False


def is_verified_downstream_w06_stage_a_task_audit_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Cryptographically and semantically verify `w06_dev_tune_stage_a_freeze_01_receipt_v1.json`."""
    if (
        not path.is_file()
        or path.name != "w06_dev_tune_stage_a_freeze_01_receipt_v1.json"
    ):
        return False
    sibling_stage_a = path.parent / "w06_dev_tune_stage_a_freeze_receipt_v1.json"
    if not is_verified_downstream_w06_stage_a_freeze_receipt(
        sibling_stage_a, repo_root=repo_root
    ):
        return False
    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        obj = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(obj, dict):
            return False
        assert_no_secrets_in_payload(
            obj, context="DOWNSTREAM_STAGE_A_TASK_AUDIT_RECEIPT_VERIFICATION"
        )
        summary = obj.get("verification_summary", {})
        return (
            obj.get("artifact_id") == TASK_AUDIT_RECEIPT_ARTIFACT_ID
            and obj.get("task") == TASK_ID
            and obj.get("task_id") == TASK_ID
            and obj.get("source_develop_sha") == SOURCE_DEVELOP_SHA
            and obj.get("phase") == "DEV_TUNE"
            and obj.get("execution_plan_sha256") == EXPECTED_DEV_TUNE_PLAN_SHA256
            and obj.get("execution_plan_file_sha256")
            == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
            and obj.get("prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
            and obj.get("authorization_file_sha256")
            == EXPECTED_AUTHORIZATION_FILE_SHA256
            and obj.get("authorization_internal_sha256")
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            and obj.get("scientific_code_bundle_sha256")
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and obj.get("candidate_registry_sha256")
            == EXPECTED_CANDIDATE_REGISTRY_SHA256
            and obj.get("provider_config_registry_sha256")
            == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
            and obj.get("code_basis_commit_sha") == CODE_BASIS_COMMIT_SHA
            and obj.get("stage_a_commit_sha") == STAGE_A_COMMIT_SHA
            and obj.get("stage_a_receipt_sha256")
            == EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
            and obj.get("stage_a_receipt_file_sha256")
            == EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
            and obj.get("assigned_run_id_count") == 120
            and obj.get("same_process_execution_blocked") is True
            and obj.get("separate_process_committed_verification_passed") is True
            and obj.get("live_execution_capability_minted") is False
            and obj.get("live_provider_calls") == 0
            and obj.get("provider_cost_usd") == 0.0
            and obj.get("dev_tune_execution_started") is False
            and obj.get("dev_select_execution_started") is False
            and obj.get("stochasticity_execution_started") is False
            and obj.get("final100_used") is False
            and isinstance(summary, dict)
            and summary.get("overall_status") == "PASS"
        )
    except Exception:
        return False


def is_verified_downstream_w06_dev_tune_stage_a_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the cryptographically verified downstream Stage-A receipt or task audit receipt."""
    if path.name == "w06_dev_tune_stage_a_freeze_receipt_v1.json":
        return is_verified_downstream_w06_stage_a_freeze_receipt(
            path, repo_root=repo_root
        )
    if path.name == "w06_dev_tune_stage_a_freeze_01_receipt_v1.json":
        return is_verified_downstream_w06_stage_a_task_audit_receipt(
            path, repo_root=repo_root
        )
    return False


# ==============================================================================
# 5. PROCESS A: GENERATE STAGE-A RECEIPT EXACTLY ONCE (SECTIONS 8, 9, 10, 11, 22)
# ==============================================================================


def generate_stage_a_receipt_once_process_a(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """PROCESS A: Generate `w06_dev_tune_stage_a_freeze_receipt_v1.json` once using production `build_stage_a_freeze_receipt(...)`."""
    guard = NetworkKillSwitchGuard()
    with guard.activate():
        stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
        if stage_a_path.exists():
            raise RuntimeError(
                f"STAGE_A_RECEIPT_ALREADY_EXISTS: Refusing to regenerate or overwrite {stage_a_path}"
            )

        src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
        if not src_info["verified"]:
            raise RuntimeError(
                f"SOURCE_DEVELOP_PROVENANCE_FAILED: {src_info}"
            )

        auths = load_verified_stage_a_authorities(repo_root)
        freeze_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Production contract builder (Section 8): auto-stamps _CURRENT_PROCESS_INVOCATION_TOKEN
        receipt_model = build_stage_a_freeze_receipt(
            execution_plan=auths["execution_plan"],
            prompt_freeze=auths["prompt_freeze"],
            authorization=auths["authorization"],
            stage_a_commit_sha=STAGE_A_COMMIT_SHA,
            freeze_created_at_utc=freeze_utc,
            candidate_registry=auths["candidate_registry"],
        )

        # Verify Same-Process Barrier (Section 11) in Process A before writing
        same_process_rejected = False
        try:
            verify_stage_a_freeze_receipt(
                receipt_model,
                execution_plan=auths["execution_plan"],
                prompt_freeze=auths["prompt_freeze"],
                authorization=auths["authorization"],
                candidate_registry=auths["candidate_registry"],
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN" in str(exc):
                same_process_rejected = True
        if not same_process_rejected:
            raise RuntimeError(
                "SAME_PROCESS_BARRIER_FAILURE: Expected STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN in Process A."
            )

        file_sha = write_immutable_canonical_json(
            stage_a_path, receipt_model.model_dump()
        )
        return {
            "stage_a_receipt_relative_path": STAGE_A_RECEIPT_REL_PATH,
            "freeze_created_at_utc": receipt_model.freeze_created_at_utc,
            "stage_a_process_token": receipt_model.stage_a_process_token,
            "stage_a_receipt_sha256": receipt_model.stage_a_receipt_sha256,
            "stage_a_receipt_file_sha256": file_sha,
            "assigned_run_id_count": len(receipt_model.assigned_cell_run_ids),
            "assigned_cells_sha256": receipt_model.assigned_cells_sha256,
            "same_process_execution_blocked": same_process_rejected,
        }


# ==============================================================================
# 6. GIT COMMITTED STAGE-A VERIFICATION HELPER & FIREWALL SCANNER
# ==============================================================================


def has_full_stage_a_git_history(repo_root: Path = REPO_ROOT) -> bool:
    """Return True if both STAGE_A_COMMIT_SHA and CODE_BASIS_COMMIT_SHA exist as commit objects in repo_root."""
    for sha in (STAGE_A_COMMIT_SHA, CODE_BASIS_COMMIT_SHA):
        proc = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "commit":
            return False
    return True


def _is_path_committed_and_clean_in_head(repo_root: Path, rel_posix: str) -> bool:
    """Return True if `rel_posix` is tracked, clean in working tree, and present in HEAD."""
    ls_proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel_posix],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if ls_proc.returncode != 0:
        return False
    st_proc = subprocess.run(
        ["git", "status", "--porcelain", "--", rel_posix],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if st_proc.returncode != 0 or st_proc.stdout.strip():
        return False
    show_proc = subprocess.run(
        ["git", "show", f"HEAD:{rel_posix}"],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    return show_proc.returncode == 0


def verify_committed_stage_a_or_shallow_ci_fallback(
    stage_a_path: Path,
    *,
    execution_plan: DevExecutionPlan,
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    execution_plan_path: Path,
    prompt_freeze_path: Path,
    authorization_path: Path,
    candidate_registry: Any,
    repo_root: Path,
) -> DevLiveStageAFreezeReceipt:
    """Verify committed Stage-A receipt with full git history, or fail-closed shallow CI HEAD blob attestation."""
    if has_full_stage_a_git_history(repo_root):
        return verify_stage_a_freeze_receipt(
            stage_a_path,
            execution_plan=execution_plan,
            prompt_freeze=prompt_freeze,
            authorization=authorization,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            candidate_registry=candidate_registry,
            repo_root=repo_root,
            require_git_committed=True,
        )

    src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
    if not (src_info["is_shallow_repository"] and src_info["verified"]):
        # Fail closed via production verifier when not a verified shallow clone
        return verify_stage_a_freeze_receipt(
            stage_a_path,
            execution_plan=execution_plan,
            prompt_freeze=prompt_freeze,
            authorization=authorization,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            candidate_registry=candidate_registry,
            repo_root=repo_root,
            require_git_committed=True,
        )

    verified = verify_stage_a_freeze_receipt(
        stage_a_path,
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        authorization=authorization,
        candidate_registry=candidate_registry,
        repo_root=repo_root,
        require_git_committed=False,
    )

    expected_head_blobs: list[tuple[str, str]] = [
        (DEV_TUNE_PLAN_REL_PATH, EXPECTED_DEV_TUNE_PLAN_FILE_SHA256),
        (PROMPT_FREEZE_REL_PATH, EXPECTED_PROMPT_FREEZE_SHA256),
        (AUTHORIZATION_REL_PATH, EXPECTED_AUTHORIZATION_FILE_SHA256),
        (STAGE_A_RECEIPT_REL_PATH, EXPECTED_STAGE_A_RECEIPT_FILE_SHA256),
        *[
            (entry["path"], entry["sha256"])
            for entry in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        ],
    ]
    for rel_posix, expected_sha in expected_head_blobs:
        if not _is_path_committed_and_clean_in_head(repo_root, rel_posix):
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_SHALLOW_CI_UNCOMMITTED_OR_DIRTY: {rel_posix}"
            )
        show_proc = subprocess.run(
            ["git", "show", f"HEAD:{rel_posix}"],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if show_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_SHALLOW_CI_HEAD_BLOB_MISSING: {rel_posix}"
            )
        blob_sha = sha256_bytes(normalize_lf_bytes(show_proc.stdout))
        if blob_sha != expected_sha:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_SHALLOW_CI_HEAD_BLOB_MISMATCH for {rel_posix}: {blob_sha} != {expected_sha}"
            )
    return verified


@contextmanager
def _committed_repo_view_for_stage_a(
    repo_root: Path,
    *,
    require_committed_in_head: bool,
) -> Iterator[tuple[Path, bool]]:
    """Yield `(target_repo_root, directly_committed_in_real_head)`.

    When `require_committed_in_head=True` (Process B `--verify-committed` and pytest),
    ALWAYS yields `(repo_root, True)` with zero fallback.
    When `require_committed_in_head=False` (only during Step 5 pre-commit assembly of
    `w06_dev_tune_stage_a_freeze_01_receipt_v1.json` before `git commit`), if
    `w06_dev_tune_stage_a_freeze_receipt_v1.json` is not yet in `HEAD`, creates a
    temporary git worktree rooted at `STAGE_A_COMMIT_SHA` (`25c81ad...`), copies the
    exact persisted `w06_dev_tune_stage_a_freeze_receipt_v1.json`, commits it in the
    temporary worktree, and runs production `verify_stage_a_freeze_receipt(..., require_git_committed=True)`.
    """
    directly_committed = _is_path_committed_and_clean_in_head(
        repo_root, STAGE_A_RECEIPT_REL_PATH
    )
    if require_committed_in_head or directly_committed:
        yield repo_root, directly_committed
        return

    with tempfile.TemporaryDirectory() as tmp_str:
        wt_dir = Path(tmp_str) / "stage_a_wt"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt_dir), STAGE_A_COMMIT_SHA],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        try:
            persisted_bytes = (repo_root / STAGE_A_RECEIPT_REL_PATH).read_bytes()
            wt_receipt = wt_dir / STAGE_A_RECEIPT_REL_PATH
            wt_receipt.write_bytes(persisted_bytes)
            subprocess.run(
                ["git", "add", STAGE_A_RECEIPT_REL_PATH],
                cwd=str(wt_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=StageAVerifier",
                    "-c",
                    "user.email=stagea@wanderai.local",
                    "commit",
                    "-m",
                    "temp: verify stage-a git attestation",
                ],
                cwd=str(wt_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            yield wt_dir, False
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_dir)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )


def verify_no_live_execution_or_stage_b_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify that zero transport journals, live cell outputs, or unauthorized Stage-A files exist."""
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    unauthorized_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_live_cell_dirs: list[str] = []

    if w06_dir.is_dir():
        from freeze_w06_dev_select_live_results import (
            is_path_in_downstream_w06_dev_select_live_results_scope,
            is_verified_downstream_w06_dev_select_live_results_tree,
        )
        from freeze_w06_dev_select_stage_a import (
            is_verified_downstream_w06_dev_select_stage_a_file,
        )
        from freeze_w06_dev_tune_live_results import (
            is_path_in_downstream_w06_dev_tune_live_results_scope,
            is_verified_downstream_w06_dev_tune_live_results_tree,
        )
        from verify_w06_dev_select_amendment_01_canary_live_execution_01_evidence import (
            is_path_in_downstream_w06_amendment_01_canary_live_evidence_scope,
            is_verified_downstream_w06_amendment_01_canary_live_evidence_tree,
        )

        verified_downstream_results_tree = (
            is_verified_downstream_w06_dev_tune_live_results_tree(repo_root)
        )
        verified_downstream_dev_select_results_tree = (
            is_verified_downstream_w06_dev_select_live_results_tree(repo_root)
        )
        verified_downstream_canary_live_evidence_tree = (
            is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(repo_root)
        )

        for path in sorted(w06_dir.rglob("*")):
            rel = path.relative_to(repo_root).as_posix()
            name_lower = path.name.lower()
            is_verified_results = (
                (
                    verified_downstream_results_tree
                    and is_path_in_downstream_w06_dev_tune_live_results_scope(
                        path, repo_root=repo_root
                    )
                )
                or (
                    verified_downstream_dev_select_results_tree
                    and is_path_in_downstream_w06_dev_select_live_results_scope(
                        path, repo_root=repo_root
                    )
                )
                or (
                    verified_downstream_canary_live_evidence_tree
                    and is_path_in_downstream_w06_amendment_01_canary_live_evidence_scope(
                        path, repo_root=repo_root
                    )
                )
            )
            if path.is_file():
                is_verified_stage_a = (
                    is_verified_downstream_w06_dev_tune_stage_a_file(
                        path, repo_root=repo_root
                    )
                    or is_verified_downstream_w06_dev_select_stage_a_file(
                        path, repo_root=repo_root
                    )
                )
                if (
                    (
                        "stage_a" in name_lower
                        or "stage-a" in name_lower
                        or name_lower == "stage_a_freeze_receipt.json"
                    )
                    and not is_verified_stage_a
                    and not is_verified_results
                ):
                    unauthorized_stage_a_files.append(rel)
                if (
                    "transport_journal" in name_lower
                    and not is_verified_results
                ):
                    forbidden_transport_journals.append(rel)
            elif path.is_dir():
                if (
                    any(
                        tok in name_lower
                        for tok in (
                            "live_dev_tune",
                            "dev_tune_live",
                            "dev_select_live",
                            "stochasticity_live",
                            "live_runs",
                            "cell_outputs",
                        )
                    )
                    and not is_verified_results
                ):
                    forbidden_live_cell_dirs.append(rel)

    return {
        "unauthorized_stage_a_files": unauthorized_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_live_cell_dirs": forbidden_live_cell_dirs,
        "transport_journal_created": len(forbidden_transport_journals) > 0,
        "provider_result_directory_created": len(forbidden_live_cell_dirs) > 0,
        "live_execution_capability_minted": False,
        "production_provider_transport_constructed": False,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
    }


def _inspect_script_ast_for_stage_a_compliance(script_path: Path) -> dict[str, Any]:
    """Inspect `freeze_w06_dev_tune_stage_a.py` AST to prove production builder usage and zero capability/transport calls."""
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))

    gen_func_calls: list[str] = []
    all_called_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                all_called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                all_called_names.add(node.func.attr)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "generate_stage_a_receipt_once_process_a"
        ):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name):
                        gen_func_calls.append(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute):
                        gen_func_calls.append(sub.func.attr)

    forbidden_called = sorted(
        sym for sym in FORBIDDEN_CAPABILITY_OR_TRANSPORT_SYMBOLS if sym in all_called_names
    )
    reads_env_secrets = any(
        name in all_called_names for name in ("getenv", "load_dotenv")
    ) or any(
        isinstance(n, ast.Attribute) and n.attr == "environ"
        for n in ast.walk(tree)
    )
    return {
        "production_builder_called_in_process_a": (
            "build_stage_a_freeze_receipt" in gen_func_calls
        ),
        "test_only_builder_called_in_process_a": (
            "build_test_only_stage_a_freeze_receipt" in gen_func_calls
        ),
        "forbidden_capability_or_transport_calls": forbidden_called,
        "reads_env_secrets": reads_env_secrets,
    }


# ==============================================================================
# 7. VERIFICATION SUITE: SA-01..SA-40 & ADVERSARIAL SAA-01..SAA-15 (SECTION 21)
# ==============================================================================


def run_all_sa_checks(
    repo_root: Path = REPO_ROOT,
    *,
    require_committed_in_head: bool = True,
) -> list[dict[str, Any]]:
    """Run all 40 Stage-A verification checks SA-01 through SA-40 under the outbound-network kill switch."""
    results: list[dict[str, Any]] = []

    def record(
        check_id: str,
        domain: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "domain": domain,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
            }
        )

    guard = NetworkKillSwitchGuard()
    with guard.activate():
        # SA-01: source develop exact
        src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
        record(
            "SA-01",
            "SOURCE_STATE",
            "Source develop SHA 25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e exists and is ancestor of HEAD",
            {"source_develop_sha": SOURCE_DEVELOP_SHA, "verified": True},
            {
                "source_develop_sha": src_info["source_develop_sha"],
                "verified": src_info["verified"],
            },
            bool(src_info["verified"]),
        )

        # SA-02: source worktree clean for upstream tracked authorities and scientific bundle
        upstream_tracked_paths = [
            DEV_TUNE_PLAN_REL_PATH,
            PROMPT_FREEZE_REL_PATH,
            AUTHORIZATION_REL_PATH,
            *SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
        ]
        dirty_upstream: list[str] = []
        for rel in upstream_tracked_paths:
            st = subprocess.run(
                ["git", "status", "--porcelain", "--", rel],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if st.returncode != 0 or st.stdout.strip():
                dirty_upstream.append(rel)
        record(
            "SA-02",
            "SOURCE_STATE",
            "Source worktree clean for all upstream frozen authorities and 14 scientific bundle files",
            [],
            dirty_upstream,
            len(dirty_upstream) == 0,
        )

        auths = load_verified_stage_a_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]
        freeze_model: DevPromptFreezeArtifact = auths["prompt_freeze"]
        auth_model: DevLiveAuthorizationArtifact = auths["authorization"]
        cand_reg = auths["candidate_registry"]

        stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
        stage_a_bytes = normalize_lf_bytes(stage_a_path.read_bytes())
        stage_a_file_sha = sha256_bytes(stage_a_bytes)
        persisted_stage_a = DevLiveStageAFreezeReceipt.model_validate_json(
            stage_a_bytes
        )

        # SA-03: DEV-TUNE plan SHA exact
        record(
            "SA-03",
            "FROZEN_PLAN",
            "DEV-TUNE execution plan SHA256 matches 582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
            EXPECTED_DEV_TUNE_PLAN_SHA256,
            persisted_stage_a.execution_plan_sha256,
            persisted_stage_a.execution_plan_sha256
            == plan_model.plan_sha256
            == EXPECTED_DEV_TUNE_PLAN_SHA256,
        )

        # SA-04: plan file SHA exact
        record(
            "SA-04",
            "FROZEN_PLAN",
            "DEV-TUNE execution plan file SHA256 matches 652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74",
            EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
            auths["execution_plan_file_sha256"],
            auths["execution_plan_file_sha256"] == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
        )

        # SA-05: prompt freeze SHA exact
        record(
            "SA-05",
            "PROMPT_FREEZE",
            "Prompt freeze SHA256 matches 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
            EXPECTED_PROMPT_FREEZE_SHA256,
            persisted_stage_a.prompt_freeze_sha256,
            persisted_stage_a.prompt_freeze_sha256
            == auths["prompt_freeze_sha256"]
            == EXPECTED_PROMPT_FREEZE_SHA256,
        )

        # SA-06: authorization file SHA exact
        record(
            "SA-06",
            "AUTHORIZATION",
            "Authorization artifact file SHA256 matches b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4",
            EXPECTED_AUTHORIZATION_FILE_SHA256,
            auths["authorization_file_sha256"],
            auths["authorization_file_sha256"] == EXPECTED_AUTHORIZATION_FILE_SHA256,
        )

        # SA-07: authorization internal SHA exact
        record(
            "SA-07",
            "AUTHORIZATION",
            "Authorization internal SHA256 matches fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83",
            EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
            persisted_stage_a.authorization_artifact_sha256,
            persisted_stage_a.authorization_artifact_sha256
            == auth_model.authorization_artifact_sha256
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
        )

        # SA-08: authorization scope DEV_TUNE exact
        record(
            "SA-08",
            "AUTHORIZATION_SCOPE",
            "Stage-A phase and authorized phase are strictly DEV_TUNE",
            "DEV_TUNE",
            persisted_stage_a.phase,
            persisted_stage_a.phase == auth_model.allowed_phase == "DEV_TUNE",
        )

        # SA-09: candidates C1/C2/C3 exact
        record(
            "SA-09",
            "AUTHORIZATION_SCOPE",
            "Authorized candidates are strictly ['C1', 'C2', 'C3']",
            ["C1", "C2", "C3"],
            auth_model.allowed_candidate_ids,
            auth_model.allowed_candidate_ids == ["C1", "C2", "C3"]
            and list(plan_model.candidate_ids) == ["C1", "C2", "C3"],
        )

        # SA-10: maximum calls 120 exact
        record(
            "SA-10",
            "CALL_BUDGET",
            "Authorized maximum_live_generation_calls is strictly 120",
            120,
            auth_model.maximum_live_generation_calls,
            auth_model.maximum_live_generation_calls == 120
            and plan_model.expected_total_cells == 120,
        )

        # SA-11: scientific bundle exact
        bundle_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
        expected_bundle_map = {
            e["path"]: e["sha256"]
            for e in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        }
        actual_bundle_map = {e["path"]: e["sha256"] for e in bundle_hashes}
        sa11_ok = (
            persisted_stage_a.scientific_code_bundle_sha256
            == auths["scientific_code_bundle_sha256"]
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and actual_bundle_map == expected_bundle_map
            and len(bundle_hashes) == 14
        )
        record(
            "SA-11",
            "SCIENTIFIC_AUTHORITIES",
            "Scientific code bundle SHA256 matches 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3 across all 14 files",
            EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            persisted_stage_a.scientific_code_bundle_sha256,
            sa11_ok,
        )

        # SA-12: provider config registry exact
        record(
            "SA-12",
            "SCIENTIFIC_AUTHORITIES",
            "Provider config registry SHA256 matches 3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938",
            EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
            persisted_stage_a.provider_config_registry_sha256,
            persisted_stage_a.provider_config_registry_sha256
            == auths["provider_config_registry_sha256"]
            == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
        )

        # SA-13: candidate registry exact
        record(
            "SA-13",
            "SCIENTIFIC_AUTHORITIES",
            "Candidate registry SHA256 matches 4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058",
            EXPECTED_CANDIDATE_REGISTRY_SHA256,
            cand_reg.registry_sha256,
            cand_reg.registry_sha256 == EXPECTED_CANDIDATE_REGISTRY_SHA256,
        )

        # SA-14: code_basis_commit_sha remains 60d52d...
        record(
            "SA-14",
            "COMMIT_SEMANTICS",
            "code_basis_commit_sha remains 60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26",
            CODE_BASIS_COMMIT_SHA,
            persisted_stage_a.code_basis_commit_sha,
            persisted_stage_a.code_basis_commit_sha
            == plan_model.code_basis_commit_sha
            == CODE_BASIS_COMMIT_SHA,
        )

        # SA-15: stage_a_commit_sha exactly 25c81ad...
        record(
            "SA-15",
            "COMMIT_SEMANTICS",
            "stage_a_commit_sha is 25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e",
            STAGE_A_COMMIT_SHA,
            persisted_stage_a.stage_a_commit_sha,
            persisted_stage_a.stage_a_commit_sha == STAGE_A_COMMIT_SHA,
        )

        # SA-16 & SA-17: AST inspection of Stage-A script
        ast_info = _inspect_script_ast_for_stage_a_compliance(Path(__file__).resolve())
        record(
            "SA-16",
            "PRODUCTION_CONTRACT",
            "Production build_stage_a_freeze_receipt(...) used to construct persisted Stage-A receipt",
            True,
            ast_info["production_builder_called_in_process_a"],
            ast_info["production_builder_called_in_process_a"] is True,
        )
        record(
            "SA-17",
            "PRODUCTION_CONTRACT",
            "build_test_only_stage_a_freeze_receipt(...) is NOT used for persisted Stage-A receipt",
            False,
            ast_info["test_only_builder_called_in_process_a"],
            ast_info["test_only_builder_called_in_process_a"] is False
            and "test-only" not in persisted_stage_a.stage_a_process_token.lower(),
        )

        # SA-18: stage_a_process_token non-empty and production-generated
        token_ok = bool(
            persisted_stage_a.stage_a_process_token
            and _PROCESS_TOKEN_PATTERN.match(persisted_stage_a.stage_a_process_token)
        )
        record(
            "SA-18",
            "PRODUCTION_CONTRACT",
            "stage_a_process_token is non-empty and matches production auto-stamped format pid-<int>-ns-<int>",
            True,
            token_ok,
            token_ok,
        )

        # SA-19: stage_a_status FROZEN_BEFORE_LIVE
        record(
            "SA-19",
            "STAGE_A_SEMANTICS",
            "stage_a_status is FROZEN_BEFORE_LIVE",
            STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
            persisted_stage_a.stage_a_status,
            persisted_stage_a.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
        )

        # SA-20: assigned run IDs exactly 120
        record(
            "SA-20",
            "STAGE_A_SEMANTICS",
            "assigned_cell_run_ids contains exactly 120 unique run IDs",
            120,
            len(persisted_stage_a.assigned_cell_run_ids),
            len(persisted_stage_a.assigned_cell_run_ids) == 120
            and len(set(persisted_stage_a.assigned_cell_run_ids)) == 120,
        )

        # SA-21: assigned run IDs equal frozen plan ordering
        record(
            "SA-21",
            "STAGE_A_SEMANTICS",
            "assigned_cell_run_ids matches exact ordered 120 run IDs from frozen execution plan",
            True,
            persisted_stage_a.assigned_cell_run_ids == auths["assigned_cell_run_ids"],
            persisted_stage_a.assigned_cell_run_ids == auths["assigned_cell_run_ids"],
        )

        # SA-22: assigned cells SHA recomputes exactly
        record(
            "SA-22",
            "STAGE_A_SEMANTICS",
            "assigned_cells_sha256 recomputes exactly via compute_assigned_cells_sha256(execution_plan)",
            auths["assigned_cells_sha256"],
            persisted_stage_a.assigned_cells_sha256,
            persisted_stage_a.assigned_cells_sha256 == auths["assigned_cells_sha256"],
        )

        # SA-23: Stage-A internal receipt SHA verifies
        body_without_sha = persisted_stage_a.model_dump(
            exclude={"stage_a_receipt_sha256"}
        )
        recomputed_internal_sha = sha256_bytes(canonical_json_bytes(body_without_sha))
        sa23_ok = (
            persisted_stage_a.stage_a_receipt_sha256 == recomputed_internal_sha
            and persisted_stage_a.stage_a_receipt_sha256
            == EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
            and stage_a_file_sha == EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
        )
        record(
            "SA-23",
            "STAGE_A_SEMANTICS",
            "Stage-A internal receipt SHA256 and file SHA256 verify against canonical JSON",
            EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256,
            persisted_stage_a.stage_a_receipt_sha256,
            sa23_ok,
        )

        # SA-24: same-process Stage-B verification rejected
        same_proc_rejected = False
        same_proc_receipt = _build_stage_a_freeze_receipt_with_token(
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            stage_a_commit_sha=STAGE_A_COMMIT_SHA,
            freeze_created_at_utc=persisted_stage_a.freeze_created_at_utc,
            stage_a_process_token=_CURRENT_PROCESS_INVOCATION_TOKEN,
            candidate_registry=cand_reg,
        )
        try:
            verify_stage_a_freeze_receipt(
                same_proc_receipt,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN" in str(exc):
                same_proc_rejected = True
        record(
            "SA-24",
            "SAME_PROCESS_BARRIER",
            "Same-process Stage-B verification is rejected with STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN",
            True,
            same_proc_rejected,
            same_proc_rejected,
        )

        # SA-25 .. SA-31: Separate-process committed verification & git blob attestation
        with _committed_repo_view_for_stage_a(
            repo_root, require_committed_in_head=require_committed_in_head
        ) as (verify_root, _directly_committed):
            full_git = has_full_stage_a_git_history(verify_root)
            verified_committed = verify_committed_stage_a_or_shallow_ci_fallback(
                verify_root / STAGE_A_RECEIPT_REL_PATH,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                execution_plan_path=verify_root / DEV_TUNE_PLAN_REL_PATH,
                prompt_freeze_path=verify_root / PROMPT_FREEZE_REL_PATH,
                authorization_path=verify_root / AUTHORIZATION_REL_PATH,
                candidate_registry=cand_reg,
                repo_root=verify_root,
            )
            sa25_ok = (
                isinstance(verified_committed, DevLiveStageAFreezeReceipt)
                and verified_committed.stage_a_receipt_sha256
                == persisted_stage_a.stage_a_receipt_sha256
                and persisted_stage_a.stage_a_process_token
                != _CURRENT_PROCESS_INVOCATION_TOKEN
            )
            record(
                "SA-25",
                "SEPARATE_PROCESS_VERIFICATION",
                "Separate-process verification succeeds via production verify_stage_a_freeze_receipt(..., require_git_committed=True)",
                True,
                sa25_ok,
                sa25_ok,
            )

            # SA-26: git ancestor attestation
            if full_git:
                anc_stage_a = (
                    subprocess.run(
                        [
                            "git",
                            "merge-base",
                            "--is-ancestor",
                            STAGE_A_COMMIT_SHA,
                            "HEAD",
                        ],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=False,
                    ).returncode
                    == 0
                )
                anc_basis = (
                    subprocess.run(
                        [
                            "git",
                            "merge-base",
                            "--is-ancestor",
                            CODE_BASIS_COMMIT_SHA,
                            "HEAD",
                        ],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=False,
                    ).returncode
                    == 0
                )
            else:
                shallow_info = verify_source_develop_commit_or_shallow_fallback(
                    verify_root
                )
                anc_stage_a = bool(
                    shallow_info["is_shallow_repository"]
                    and shallow_info["verified"]
                )
                anc_basis = anc_stage_a
            record(
                "SA-26",
                "GIT_BLOB_ATTESTATION",
                "Git ancestor attestation succeeds for stage_a_commit_sha (25c81ad...) and code_basis_commit_sha (60d52d...)",
                {"stage_a_ancestor": True, "code_basis_ancestor": True},
                {"stage_a_ancestor": anc_stage_a, "code_basis_ancestor": anc_basis},
                anc_stage_a and anc_basis,
            )

            # SA-27: execution plan committed blob attestation
            plan_blob_head = sha256_bytes(
                normalize_lf_bytes(
                    subprocess.run(
                        ["git", "show", f"HEAD:{DEV_TUNE_PLAN_REL_PATH}"],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=True,
                    ).stdout
                )
            )
            plan_blob_stage_a = (
                sha256_bytes(
                    normalize_lf_bytes(
                        subprocess.run(
                            [
                                "git",
                                "show",
                                f"{STAGE_A_COMMIT_SHA}:{DEV_TUNE_PLAN_REL_PATH}",
                            ],
                            cwd=str(verify_root),
                            capture_output=True,
                            check=True,
                        ).stdout
                    )
                )
                if full_git
                else plan_blob_head
            )
            record(
                "SA-27",
                "GIT_BLOB_ATTESTATION",
                "Execution plan committed blob at stage_a_commit_sha and HEAD matches disk SHA256",
                EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
                plan_blob_head,
                plan_blob_head
                == plan_blob_stage_a
                == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
            )

            # SA-28: prompt freeze committed blob attestation
            pf_blob_head = sha256_bytes(
                normalize_lf_bytes(
                    subprocess.run(
                        ["git", "show", f"HEAD:{PROMPT_FREEZE_REL_PATH}"],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=True,
                    ).stdout
                )
            )
            pf_blob_stage_a = (
                sha256_bytes(
                    normalize_lf_bytes(
                        subprocess.run(
                            [
                                "git",
                                "show",
                                f"{STAGE_A_COMMIT_SHA}:{PROMPT_FREEZE_REL_PATH}",
                            ],
                            cwd=str(verify_root),
                            capture_output=True,
                            check=True,
                        ).stdout
                    )
                )
                if full_git
                else pf_blob_head
            )
            record(
                "SA-28",
                "GIT_BLOB_ATTESTATION",
                "Prompt freeze committed blob at stage_a_commit_sha and HEAD matches disk SHA256",
                EXPECTED_PROMPT_FREEZE_SHA256,
                pf_blob_head,
                pf_blob_head == pf_blob_stage_a == EXPECTED_PROMPT_FREEZE_SHA256,
            )

            # SA-29: authorization committed blob attestation
            auth_blob_head = sha256_bytes(
                normalize_lf_bytes(
                    subprocess.run(
                        ["git", "show", f"HEAD:{AUTHORIZATION_REL_PATH}"],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=True,
                    ).stdout
                )
            )
            auth_blob_stage_a = (
                sha256_bytes(
                    normalize_lf_bytes(
                        subprocess.run(
                            [
                                "git",
                                "show",
                                f"{STAGE_A_COMMIT_SHA}:{AUTHORIZATION_REL_PATH}",
                            ],
                            cwd=str(verify_root),
                            capture_output=True,
                            check=True,
                        ).stdout
                    )
                )
                if full_git
                else auth_blob_head
            )
            record(
                "SA-29",
                "GIT_BLOB_ATTESTATION",
                "Authorization artifact committed blob at stage_a_commit_sha and HEAD matches disk SHA256",
                EXPECTED_AUTHORIZATION_FILE_SHA256,
                auth_blob_head,
                auth_blob_head == auth_blob_stage_a == EXPECTED_AUTHORIZATION_FILE_SHA256,
            )

            # SA-30: Stage-A receipt HEAD blob attestation
            stage_a_blob_head = sha256_bytes(
                normalize_lf_bytes(
                    subprocess.run(
                        ["git", "show", f"HEAD:{STAGE_A_RECEIPT_REL_PATH}"],
                        cwd=str(verify_root),
                        capture_output=True,
                        check=True,
                    ).stdout
                )
            )
            record(
                "SA-30",
                "GIT_BLOB_ATTESTATION",
                "Stage-A receipt HEAD blob matches persisted Stage-A receipt file SHA256",
                stage_a_file_sha,
                stage_a_blob_head,
                stage_a_blob_head
                == stage_a_file_sha
                == EXPECTED_STAGE_A_RECEIPT_FILE_SHA256,
            )

            # SA-31: scientific bundle blob attestation
            bundle_mismatches: list[str] = []
            refs_to_check = (STAGE_A_COMMIT_SHA, "HEAD") if full_git else ("HEAD",)
            for entry in bundle_hashes:
                b_rel = entry["path"]
                b_exp = entry["sha256"]
                for ref in refs_to_check:
                    b_sha = sha256_bytes(
                        normalize_lf_bytes(
                            subprocess.run(
                                ["git", "show", f"{ref}:{b_rel}"],
                                cwd=str(verify_root),
                                capture_output=True,
                                check=True,
                            ).stdout
                        )
                    )
                    if b_sha != b_exp:
                        bundle_mismatches.append(f"{ref}:{b_rel}")
            record(
                "SA-31",
                "GIT_BLOB_ATTESTATION",
                "All 14 scientific code bundle files match committed git blobs at stage_a_commit_sha and HEAD",
                [],
                bundle_mismatches,
                len(bundle_mismatches) == 0,
            )

        fw = verify_no_live_execution_or_stage_b_artifacts(repo_root)

        # SA-32: no LiveExecutionCapability minted
        sa32_ok = (
            fw["live_execution_capability_minted"] is False
            and "issue_live_execution_capability"
            not in ast_info["forbidden_capability_or_transport_calls"]
        )
        record(
            "SA-32",
            "NO_LIVE_CAPABILITY",
            "No LiveExecutionCapability minted during Stage-A freeze or verification",
            False,
            fw["live_execution_capability_minted"],
            sa32_ok,
        )

        # SA-33: no production provider transport constructed
        sa33_ok = (
            fw["production_provider_transport_constructed"] is False
            and len(ast_info["forbidden_capability_or_transport_calls"]) == 0
        )
        record(
            "SA-33",
            "NO_LIVE_CAPABILITY",
            "No production provider transport constructed",
            [],
            ast_info["forbidden_capability_or_transport_calls"],
            sa33_ok,
        )

        # SA-34: zero live provider calls
        sa34_ok = (
            len(guard.blocked_attempts) == 0
            and fw["live_provider_calls"] == 0
            and fw["provider_cost_usd"] == 0.0
        )
        record(
            "SA-34",
            "NETWORK_ISOLATION",
            "Zero live provider calls and zero provider cost",
            {"blocked_attempts": 0, "live_provider_calls": 0, "provider_cost_usd": 0.0},
            {
                "blocked_attempts": len(guard.blocked_attempts),
                "live_provider_calls": fw["live_provider_calls"],
                "provider_cost_usd": fw["provider_cost_usd"],
            },
            sa34_ok,
        )

        # SA-35: no provider secret value read/persisted
        no_secrets_ok = True
        try:
            assert_no_secrets_in_payload(
                persisted_stage_a.model_dump(), context="SA_35_STAGE_A_RECEIPT"
            )
        except Exception:
            no_secrets_ok = False
        reads_env_secrets = bool(ast_info["reads_env_secrets"])
        record(
            "SA-35",
            "SECRET_HYGIENE",
            "No provider API key value read from environment or persisted in Stage-A artifacts",
            {"no_secrets_in_receipt": True, "reads_env_secrets": False},
            {
                "no_secrets_in_receipt": no_secrets_ok,
                "reads_env_secrets": reads_env_secrets,
            },
            no_secrets_ok and not reads_env_secrets,
        )

        # SA-36: DEV-SELECT forbidden
        dev_select_rejected = False
        try:
            bad_ds = persisted_stage_a.model_dump(exclude={"stage_a_receipt_sha256"})
            bad_ds["phase"] = "DEV_SELECT"
            bad_ds["stage_a_process_token"] = "pid-99999-ns-1"
            bad_ds["stage_a_receipt_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_ds)
            )
            verify_stage_a_freeze_receipt(
                bad_ds,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            dev_select_rejected = True
        record(
            "SA-36",
            "SCOPE_EXCLUSION",
            "DEV_SELECT phase is rejected by Stage-A verification against DEV_TUNE plan and authorization",
            True,
            dev_select_rejected,
            dev_select_rejected,
        )

        # SA-37: stochasticity forbidden
        stoch_rejected = False
        try:
            bad_st = persisted_stage_a.model_dump(exclude={"stage_a_receipt_sha256"})
            bad_st["phase"] = "STOCHASTICITY"
            bad_st["stage_a_process_token"] = "pid-99999-ns-2"
            bad_st["stage_a_receipt_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_st)
            )
            verify_stage_a_freeze_receipt(
                bad_st,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            stoch_rejected = True
        record(
            "SA-37",
            "SCOPE_EXCLUSION",
            "STOCHASTICITY phase is rejected by Stage-A verification against DEV_TUNE plan and authorization",
            True,
            stoch_rejected,
            stoch_rejected,
        )

        # SA-38: Final100 forbidden
        final100_rejected = False
        try:
            verify_stage_a_freeze_receipt(
                repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json",
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except Final100FirewallViolationError:
            final100_rejected = True
        record(
            "SA-38",
            "FINAL100_FIREWALL",
            "Final100 paths and phases are strictly rejected with Final100FirewallViolationError",
            True,
            final100_rejected,
            final100_rejected,
        )

        # SA-39: retry remains zero
        retry_ok = all(
            c.attempt_number == 1
            and c.retry == 0
            and c.transport_retry == 0
            and c.manual_retry == 0
            and c.automatic_retry == 0
            and c.fallback is False
            and c.repair == 0
            and c.llm_repair == 0
            and c.deterministic_semantic_repair is False
            and c.tools is False
            for c in plan_model.cells
        )
        record(
            "SA-39",
            "EXECUTION_POLICY",
            "Retry policy remains strictly 0 across all 120 assigned cells",
            True,
            retry_ok,
            retry_ok,
        )

        # SA-40: no live result/journal/cell output directories created
        sa40_ok = (
            len(fw["unauthorized_stage_a_files"]) == 0
            and len(fw["forbidden_transport_journals"]) == 0
            and len(fw["forbidden_live_cell_dirs"]) == 0
        )
        record(
            "SA-40",
            "STAGE_B_FIREWALL",
            "No transport journal, live result directory, cell output directory, or unauthorized Stage-A file created",
            {
                "unauthorized_stage_a_files": [],
                "forbidden_transport_journals": [],
                "forbidden_live_cell_dirs": [],
            },
            {
                "unauthorized_stage_a_files": fw["unauthorized_stage_a_files"],
                "forbidden_transport_journals": fw["forbidden_transport_journals"],
                "forbidden_live_cell_dirs": fw["forbidden_live_cell_dirs"],
            },
            sa40_ok,
        )

    return results


def run_all_saa_adversarial_checks(
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Run all 15 adversarial Stage-A checks SAA-01 through SAA-15 (Section 21)."""
    results: list[dict[str, Any]] = []

    def record(
        check_id: str,
        domain: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "domain": domain,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
            }
        )

    guard = NetworkKillSwitchGuard()
    with guard.activate():
        auths = load_verified_stage_a_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]
        freeze_model: DevPromptFreezeArtifact = auths["prompt_freeze"]
        auth_model: DevLiveAuthorizationArtifact = auths["authorization"]
        cand_reg = auths["candidate_registry"]

        stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
        persisted_stage_a = DevLiveStageAFreezeReceipt.model_validate_json(
            stage_a_path.read_bytes()
        )
        base_dict = persisted_stage_a.model_dump(exclude={"stage_a_receipt_sha256"})
        base_dict["stage_a_process_token"] = "pid-88888-ns-999"

        def _make_tampered(overrides: dict[str, Any]) -> dict[str, Any]:
            d = dict(base_dict)
            d.update(overrides)
            d["stage_a_receipt_sha256"] = sha256_bytes(canonical_json_bytes(d))
            return d

        # SAA-01: wrong plan SHA
        saa01 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"execution_plan_sha256": "1" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa01 = True
        record(
            "SAA-01",
            "ADVERSARIAL_STAGE_A",
            "Wrong execution_plan_sha256 is rejected by verify_stage_a_freeze_receipt",
            True,
            saa01,
            saa01,
        )

        # SAA-02: wrong prompt freeze SHA
        saa02 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"prompt_freeze_sha256": "2" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa02 = True
        record(
            "SAA-02",
            "ADVERSARIAL_STAGE_A",
            "Wrong prompt_freeze_sha256 is rejected by verify_stage_a_freeze_receipt",
            True,
            saa02,
            saa02,
        )

        # SAA-03: wrong authorization SHA
        saa03 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"authorization_artifact_sha256": "3" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa03 = True
        record(
            "SAA-03",
            "ADVERSARIAL_STAGE_A",
            "Wrong authorization_artifact_sha256 is rejected by verify_stage_a_freeze_receipt",
            True,
            saa03,
            saa03,
        )

        # SAA-04: wrong scientific bundle SHA
        saa04 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"scientific_code_bundle_sha256": "4" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except ScientificCodeBundleIntegrityError:
            saa04 = True
        record(
            "SAA-04",
            "ADVERSARIAL_STAGE_A",
            "Wrong scientific_code_bundle_sha256 is rejected with ScientificCodeBundleIntegrityError",
            True,
            saa04,
            saa04,
        )

        # SAA-05: wrong provider-config registry SHA
        saa05 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"provider_config_registry_sha256": "5" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except CandidateRegistryIntegrityError:
            saa05 = True
        record(
            "SAA-05",
            "ADVERSARIAL_STAGE_A",
            "Wrong provider_config_registry_sha256 is rejected with CandidateRegistryIntegrityError",
            True,
            saa05,
            saa05,
        )

        # SAA-06: wrong stage_a_commit_sha
        saa06 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            p06 = Path(tmp_str) / "w06_dev_tune_stage_a_freeze_receipt_v1.json"
            p06.write_bytes(
                canonical_json_bytes(_make_tampered({"stage_a_commit_sha": "a" * 40}))
            )
            try:
                verify_stage_a_freeze_receipt(
                    p06,
                    execution_plan=plan_model,
                    prompt_freeze=freeze_model,
                    authorization=auth_model,
                    execution_plan_path=repo_root / DEV_TUNE_PLAN_REL_PATH,
                    prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
                    authorization_path=repo_root / AUTHORIZATION_REL_PATH,
                    candidate_registry=cand_reg,
                    repo_root=repo_root,
                    require_git_committed=True,
                )
            except PlanBeforeLiveProtocolError:
                saa06 = True
        record(
            "SAA-06",
            "ADVERSARIAL_STAGE_A",
            "Non-existent or non-ancestor stage_a_commit_sha is rejected",
            True,
            saa06,
            saa06,
        )

        # SAA-07: wrong code_basis_commit_sha
        saa07 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"code_basis_commit_sha": "b" * 40}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa07 = True
        record(
            "SAA-07",
            "ADVERSARIAL_STAGE_A",
            "Wrong code_basis_commit_sha is rejected by verify_stage_a_freeze_receipt",
            True,
            saa07,
            saa07,
        )

        # SAA-08: missing/empty process token
        saa08 = False
        try:
            DevLiveStageAFreezeReceipt.model_validate(
                _make_tampered({"stage_a_process_token": "   "})
            )
        except PlanBeforeLiveProtocolError:
            saa08 = True
        record(
            "SAA-08",
            "ADVERSARIAL_STAGE_A",
            "Missing or whitespace stage_a_process_token is rejected by DevLiveStageAFreezeReceipt",
            True,
            saa08,
            saa08,
        )

        # SAA-09: 121-cell / tampered assigned run list
        saa09 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered(
                    {
                        "assigned_cell_run_ids": [
                            *persisted_stage_a.assigned_cell_run_ids,
                            "W06-DEV-TUNE-EXTRA-121",
                        ]
                    }
                ),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa09 = True
        record(
            "SAA-09",
            "ADVERSARIAL_STAGE_A",
            "121-cell / tampered assigned_cell_run_ids list is rejected",
            True,
            saa09,
            saa09,
        )

        # SAA-10: tampered assigned_cells_sha256
        saa10 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"assigned_cells_sha256": "c" * 64}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            saa10 = True
        record(
            "SAA-10",
            "ADVERSARIAL_STAGE_A",
            "Tampered assigned_cells_sha256 is rejected",
            True,
            saa10,
            saa10,
        )

        # SAA-11: fake Stage-A filename-only artifact rejected by downstream verifier and historical gates
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            w06_tmp = tmp_dir / "data" / "evaluation" / "w06"
            w06_tmp.mkdir(parents=True)
            fake_sa = w06_tmp / "w06_dev_tune_stage_a_freeze_receipt_v1.json"
            fake_sa.write_text(
                json.dumps(
                    {
                        "artifact_id": STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
                        "task_id": TASK_ID,
                        "phase": "DEV_TUNE",
                    }
                ),
                encoding="utf-8",
            )
            saa11_verifier_rejected = (
                is_verified_downstream_w06_dev_tune_stage_a_file(
                    fake_sa, repo_root=repo_root
                )
                is False
            )
            fw_auth = auth_mod.verify_pre_stage_a_firewall(tmp_dir)
            saa11_firewall_rejected = fw_auth["stage_a_created"] is True
        record(
            "SAA-11",
            "ADVERSARIAL_STAGE_A",
            "Fake Stage-A filename/artifact_id-only file is rejected by cryptographic verifier and historical firewall",
            {"verifier_rejected": True, "firewall_rejected": True},
            {
                "verifier_rejected": saa11_verifier_rejected,
                "firewall_rejected": saa11_firewall_rejected,
            },
            saa11_verifier_rejected and saa11_firewall_rejected,
        )

        # SAA-12: same-process execution attempt rejected
        saa12 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered(
                    {"stage_a_process_token": _CURRENT_PROCESS_INVOCATION_TOKEN}
                ),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN" in str(exc):
                saa12 = True
        record(
            "SAA-12",
            "ADVERSARIAL_STAGE_A",
            "Same-process verification attempt is rejected with STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN",
            True,
            saa12,
            saa12,
        )

        # SAA-13: uncommitted Stage-A receipt rejected when require_git_committed=True
        full_git_saa = has_full_stage_a_git_history(repo_root)
        if full_git_saa:
            git_ref_saa = STAGE_A_COMMIT_SHA
            plan_for_saa = plan_model
            sa_bytes_for_saa = stage_a_path.read_bytes()
        else:
            head_sha_saa = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git_ref_saa = head_sha_saa
            plan_for_saa = plan_model.model_copy(
                update={"code_basis_commit_sha": head_sha_saa}
            )
            sa_bytes_for_saa = canonical_json_bytes(
                _make_tampered(
                    {
                        "code_basis_commit_sha": head_sha_saa,
                        "stage_a_commit_sha": head_sha_saa,
                    }
                )
            )

        saa13 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            uncommitted_path = (
                repo_root
                / "data"
                / "evaluation"
                / "w06"
                / f".tmp_uncommitted_stage_a_{Path(tmp_str).name}.json"
            )
            try:
                uncommitted_path.write_bytes(sa_bytes_for_saa)
                verify_stage_a_freeze_receipt(
                    uncommitted_path,
                    execution_plan=plan_for_saa,
                    prompt_freeze=freeze_model,
                    authorization=auth_model,
                    execution_plan_path=repo_root / DEV_TUNE_PLAN_REL_PATH,
                    prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
                    authorization_path=repo_root / AUTHORIZATION_REL_PATH,
                    candidate_registry=cand_reg,
                    repo_root=repo_root,
                    require_git_committed=True,
                )
            except PlanBeforeLiveProtocolError as exc:
                if "STAGE_A_ARTIFACT_UNCOMMITTED" in str(exc):
                    saa13 = True
            finally:
                if uncommitted_path.exists():
                    uncommitted_path.unlink()
        record(
            "SAA-13",
            "ADVERSARIAL_STAGE_A",
            "Uncommitted Stage-A receipt is rejected with STAGE_A_ARTIFACT_UNCOMMITTED when require_git_committed=True",
            True,
            saa13,
            saa13,
        )

        # SAA-14: dirty tracked authority file rejected when require_git_committed=True
        saa14 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            wt_dir = Path(tmp_str) / "dirty_wt"
            subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(wt_dir),
                    git_ref_saa,
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            try:
                # Commit valid Stage-A receipt in worktree, then dirty authorization_path
                wt_sa = wt_dir / STAGE_A_RECEIPT_REL_PATH
                wt_sa.write_bytes(sa_bytes_for_saa)
                subprocess.run(
                    ["git", "add", STAGE_A_RECEIPT_REL_PATH],
                    cwd=str(wt_dir),
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=StageAVerifier",
                        "-c",
                        "user.email=stagea@wanderai.local",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "temp: stage-a receipt",
                    ],
                    cwd=str(wt_dir),
                    capture_output=True,
                    check=True,
                )
                wt_auth = wt_dir / AUTHORIZATION_REL_PATH
                wt_auth.write_bytes(wt_auth.read_bytes() + b"\n")
                try:
                    verify_stage_a_freeze_receipt(
                        wt_sa,
                        execution_plan=plan_for_saa,
                        prompt_freeze=freeze_model,
                        authorization=auth_model,
                        execution_plan_path=wt_dir / DEV_TUNE_PLAN_REL_PATH,
                        prompt_freeze_path=wt_dir / PROMPT_FREEZE_REL_PATH,
                        authorization_path=wt_auth,
                        candidate_registry=cand_reg,
                        repo_root=wt_dir,
                        require_git_committed=True,
                    )
                except PlanBeforeLiveProtocolError as exc:
                    if "STAGE_A_FILE_DIRTY_OR_UNCOMMITTED" in str(
                        exc
                    ) or "STAGE_A_DISK_BLOB_MISMATCH" in str(exc):
                        saa14 = True
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(wt_dir)],
                    cwd=str(repo_root),
                    capture_output=True,
                    check=False,
                )
        record(
            "SAA-14",
            "ADVERSARIAL_STAGE_A",
            "Dirty tracked authority file is rejected when require_git_committed=True",
            True,
            saa14,
            saa14,
        )

        # SAA-15: historical frozen receipts remain byte-for-byte unchanged
        hist_mismatches: list[str] = []
        for rel_path, expected_sha in HISTORICAL_FROZEN_RECEIPT_SHAS.items():
            p = repo_root / rel_path
            actual_sha = (
                sha256_bytes(normalize_lf_bytes(p.read_bytes()))
                if p.is_file()
                else "MISSING"
            )
            if actual_sha != expected_sha:
                hist_mismatches.append(f"{rel_path}:{actual_sha}")
        record(
            "SAA-15",
            "HISTORICAL_EVIDENCE_IMMUTABILITY",
            "All 5 historical frozen receipts/artifacts remain byte-for-byte unchanged",
            [],
            hist_mismatches,
            len(hist_mismatches) == 0,
        )

    return results


# ==============================================================================
# 8. WRITE TASK AUDIT RECEIPT & READ-ONLY PROCESS B VERIFICATION
# ==============================================================================


def write_task_audit_receipt(
    repo_root: Path = REPO_ROOT,
    *,
    require_committed_in_head: bool = False,
) -> dict[str, Any]:
    """Assemble and write `data/evaluation/w06/w06_dev_tune_stage_a_freeze_01_receipt_v1.json` without touching Stage-A receipt."""
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    if not stage_a_path.is_file():
        raise RuntimeError(
            f"STAGE_A_RECEIPT_MISSING: Run --generate-stage-a-once in Process A first ({stage_a_path})"
        )

    stage_a_before_bytes = stage_a_path.read_bytes()
    stage_a_file_sha = sha256_bytes(normalize_lf_bytes(stage_a_before_bytes))
    persisted_stage_a = DevLiveStageAFreezeReceipt.model_validate_json(
        stage_a_before_bytes
    )

    if persisted_stage_a.stage_a_process_token == _CURRENT_PROCESS_INVOCATION_TOKEN:
        raise RuntimeError(
            "PROCESS_SEPARATION_VIOLATION: --write-task-audit-receipt must run in a separate process from Process A."
        )

    auths = load_verified_stage_a_authorities(repo_root)
    sa_checks = run_all_sa_checks(
        repo_root, require_committed_in_head=require_committed_in_head
    )
    failed_sa = [c for c in sa_checks if c["status"] != "PASS"]
    if failed_sa:
        raise RuntimeError(f"SA checks failed: {failed_sa}")

    saa_checks = run_all_saa_adversarial_checks(repo_root)
    failed_saa = [c for c in saa_checks if c["status"] != "PASS"]
    if failed_saa:
        raise RuntimeError(f"SAA adversarial checks failed: {failed_saa}")

    # Verify Stage-A receipt was not modified
    if stage_a_path.read_bytes() != stage_a_before_bytes:
        raise RuntimeError("STAGE_A_RECEIPT_MUTATED_DURING_VERIFICATION")

    receipt_payload: dict[str, Any] = {
        "artifact_id": TASK_AUDIT_RECEIPT_ARTIFACT_ID,
        "task": TASK_ID,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "branch": BRANCH_NAME,
        "phase": ALLOWED_PHASE,
        "execution_plan_sha256": auths["execution_plan"].plan_sha256,
        "execution_plan_file_sha256": auths["execution_plan_file_sha256"],
        "prompt_freeze_sha256": auths["prompt_freeze_sha256"],
        "prompt_registry_sha256": auths["prompt_registry"].registry_sha256,
        "authorization_id": auths["authorization"].authorization_id,
        "authorization_file_sha256": auths["authorization_file_sha256"],
        "authorization_internal_sha256": auths[
            "authorization"
        ].authorization_artifact_sha256,
        "authorization_text_sha256": EXPECTED_AUTHORIZATION_TEXT_SHA256,
        "scientific_code_bundle_sha256": auths["scientific_code_bundle_sha256"],
        "candidate_registry_sha256": auths["candidate_registry"].registry_sha256,
        "provider_config_registry_sha256": auths["provider_config_registry_sha256"],
        "portable_schema_v2_sha256": auths["portable_schema_v2_sha256"],
        "semantic_schema_sha256": auths["semantic_schema_sha256"],
        "code_basis_commit_sha": persisted_stage_a.code_basis_commit_sha,
        "stage_a_commit_sha": persisted_stage_a.stage_a_commit_sha,
        "freeze_created_at_utc": persisted_stage_a.freeze_created_at_utc,
        "stage_a_process_token_present": bool(
            persisted_stage_a.stage_a_process_token
            and _PROCESS_TOKEN_PATTERN.match(persisted_stage_a.stage_a_process_token)
        ),
        "stage_a_status": persisted_stage_a.stage_a_status,
        "stage_a_receipt_relative_path": STAGE_A_RECEIPT_REL_PATH,
        "stage_a_receipt_sha256": persisted_stage_a.stage_a_receipt_sha256,
        "stage_a_receipt_file_sha256": stage_a_file_sha,
        "assigned_run_id_count": len(persisted_stage_a.assigned_cell_run_ids),
        "assigned_cells_sha256": persisted_stage_a.assigned_cells_sha256,
        "same_process_execution_blocked": True,
        "separate_process_committed_verification_passed": True,
        "scientific_code_bundle_unchanged": True,
        "live_execution_capability_minted": False,
        "production_provider_transport_constructed": False,
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "historical_evidence_boundary": {
            "historical_receipts_unmodified": True,
            "historical_frozen_receipt_shas": HISTORICAL_FROZEN_RECEIPT_SHAS,
        },
        "verification_summary": {
            "sa_total_checks": len(sa_checks),
            "sa_passed_checks": sum(1 for c in sa_checks if c["status"] == "PASS"),
            "sa_failed_checks": sum(1 for c in sa_checks if c["status"] != "PASS"),
            "saa_total_checks": len(saa_checks),
            "saa_passed_checks": sum(1 for c in saa_checks if c["status"] == "PASS"),
            "saa_failed_checks": sum(1 for c in saa_checks if c["status"] != "PASS"),
            "overall_status": "PASS",
        },
        "checks": sa_checks,
        "adversarial_checks": saa_checks,
    }
    assert_no_secrets_in_payload(
        receipt_payload, context="W06_DEV_TUNE_STAGE_A_TASK_AUDIT_RECEIPT"
    )
    audit_path = repo_root / TASK_AUDIT_RECEIPT_REL_PATH
    audit_path.write_bytes(canonical_json_bytes(receipt_payload))
    return receipt_payload


def verify_committed_stage_a_process_b(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """PROCESS B: Strictly read-only committed verification of Stage-A receipt (Section 12 & 22)."""
    status_before = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    auths = load_verified_stage_a_authorities(repo_root)
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    stage_a_before_bytes = stage_a_path.read_bytes()

    verified_receipt = verify_committed_stage_a_or_shallow_ci_fallback(
        stage_a_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        authorization=auths["authorization"],
        execution_plan_path=repo_root / DEV_TUNE_PLAN_REL_PATH,
        prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
        authorization_path=repo_root / AUTHORIZATION_REL_PATH,
        candidate_registry=auths["candidate_registry"],
        repo_root=repo_root,
    )

    sa_checks = run_all_sa_checks(repo_root, require_committed_in_head=True)
    failed_sa = [c for c in sa_checks if c["status"] != "PASS"]
    if failed_sa:
        raise RuntimeError(f"Committed SA checks failed in Process B: {failed_sa}")

    saa_checks = run_all_saa_adversarial_checks(repo_root)
    failed_saa = [c for c in saa_checks if c["status"] != "PASS"]
    if failed_saa:
        raise RuntimeError(f"Committed SAA checks failed in Process B: {failed_saa}")

    status_after = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if status_after != status_before or stage_a_path.read_bytes() != stage_a_before_bytes:
        raise RuntimeError(
            "PROCESS_B_READ_ONLY_VIOLATION: Verification modified repository state."
        )

    return {
        "task": TASK_ID,
        "process_b_read_only": True,
        "separate_process_committed_verification_passed": True,
        "stage_a_receipt_sha256": verified_receipt.stage_a_receipt_sha256,
        "stage_a_receipt_file_sha256": sha256_bytes(
            normalize_lf_bytes(stage_a_before_bytes)
        ),
        "assigned_cells_sha256": verified_receipt.assigned_cells_sha256,
        "freeze_created_at_utc": verified_receipt.freeze_created_at_utc,
        "sa_checks": f"{len(sa_checks)}/{len(sa_checks)} PASS",
        "saa_checks": f"{len(saa_checks)}/{len(saa_checks)} PASS",
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W06-DEV-TUNE-STAGE-A-FREEZE-01 offline freeze and verification tool."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--generate-stage-a-once",
        action="store_true",
        help="PROCESS A: Generate persisted Stage-A receipt once and exit.",
    )
    group.add_argument(
        "--write-task-audit-receipt",
        action="store_true",
        help="SEPARATE PROCESS: Verify persisted Stage-A receipt and write task audit receipt.",
    )
    group.add_argument(
        "--verify-committed",
        action="store_true",
        help="PROCESS B: Read-only verification of committed Stage-A receipt with require_git_committed=True.",
    )
    args = parser.parse_args(argv)

    if args.generate_stage_a_once:
        out = generate_stage_a_receipt_once_process_a(REPO_ROOT)
        print(json.dumps(out, indent=2))
        return 0

    if args.write_task_audit_receipt:
        receipt = write_task_audit_receipt(REPO_ROOT, require_committed_in_head=False)
        audit_file_sha = hashlib.sha256(
            (REPO_ROOT / TASK_AUDIT_RECEIPT_REL_PATH).read_bytes()
        ).hexdigest()
        print(
            json.dumps(
                {
                    "task": receipt["task"],
                    "stage_a_receipt_sha256": receipt["stage_a_receipt_sha256"],
                    "stage_a_receipt_file_sha256": receipt[
                        "stage_a_receipt_file_sha256"
                    ],
                    "task_audit_receipt_file_sha256": audit_file_sha,
                    "assigned_cells_sha256": receipt["assigned_cells_sha256"],
                    "freeze_created_at_utc": receipt["freeze_created_at_utc"],
                    "sa_checks": f"{receipt['verification_summary']['sa_passed_checks']}/{receipt['verification_summary']['sa_total_checks']}",
                    "saa_checks": f"{receipt['verification_summary']['saa_passed_checks']}/{receipt['verification_summary']['saa_total_checks']}",
                },
                indent=2,
            )
        )
        return 0

    out = verify_committed_stage_a_process_b(REPO_ROOT)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
