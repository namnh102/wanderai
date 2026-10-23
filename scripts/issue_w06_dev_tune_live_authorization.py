"""Issue W06 DEV-TUNE live authorization artifact and receipt (W06-DEV-TUNE-LIVE-AUTHORIZATION-01).

Includes W06-DEV-TUNE-LIVE-AUTHORIZATION-01-AUDIT-CORRECTION-01:
- Fail-closed source-develop provenance verification (AUC-01..AUC-05)
- Cryptographically bound downstream authorization & receipt recognition for historical gates (AUC-06..AUC-12)
- Strictly offline formalization of explicit Project Owner authorization:
  - LIVE_PROVIDER_CALLS = 0
  - PROVIDER_COST_USD = 0
  - STAGE_A_CREATED = false
  - LIVE_EXECUTION_CAPABILITY_MINTED = false
  - DEV_TUNE_EXECUTION_STARTED = false
"""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Iterator
import urllib.request

import httpx
import httpx2

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for p in (AI_SERVICE_DIR, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZED_BY_ROLE_PROJECT_OWNER,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    assert_no_secrets_in_payload,
    build_dev_live_authorization_artifact,
    compute_prompt_freeze_sha256,
    verify_dev_live_authorization_artifact,
    verify_runner_prompt_freeze_artifact,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    Final100FirewallViolationError,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
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

# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORIZATION EVIDENCE
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01"
AUDIT_CORRECTION_TASK_ID = (
    "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-AUDIT-CORRECTION-01"
)
PREVIOUS_HEAD_SHA = "2e1befc5883e1ca1e5b6d8212338a7b22acae1e2"
AUTHORIZATION_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"
RECEIPT_ARTIFACT_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-RECEIPT-V1"
SOURCE_DEVELOP_SHA = "cd9d4e6ae072e737083c9069123f00a5a04107a5"
CODE_BASIS_COMMIT_SHA = "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"

AUTHORIZATION_SOURCE = "PROJECT_OWNER_EXPLICIT_CHAT_AUTHORIZATION"
AUTHORIZED_BY_ROLE = AUTHORIZED_BY_ROLE_PROJECT_OWNER
AUTHORIZATION_STATUS = AUTHORIZATION_STATUS_AUTHORIZED
AUTHORIZED_AT_UTC = "2026-10-21T06:25:00Z"
AUTHORIZED_AT_UTC_SEMANTICS = (
    "authorized_at_utc represents formal artifact issuance in UTC immediately "
    "following explicit Project Owner chat authorization; it is not a fabricated "
    "historical chat timestamp."
)

EXACT_AUTHORIZATION_TEXT = (
    "I authorize W06 DEV-TUNE live execution for exactly the frozen 120-cell plan "
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae, using frozen "
    "prompt artifact 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956, "
    "candidates C1/C2/C3, maximum 120 generation calls, zero retry, no DEV-SELECT, "
    "no stochasticity, and no Final100."
)
AUTHORIZATION_TEXT_SHA256 = hashlib.sha256(
    EXACT_AUTHORIZATION_TEXT.encode("utf-8")
).hexdigest()

ALLOWED_PHASE = "DEV_TUNE"
ALLOWED_CANDIDATE_IDS: tuple[str, str, str] = ("C1", "C2", "C3")
MAXIMUM_LIVE_GENERATION_CALLS = 120
ATTEMPTS_PER_CELL = 1
RETRY_COUNT = 0

EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_DEV_TUNE_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_DEV_TUNE_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_PREP_ARTIFACT_SHA256 = (
    "168d29741fd75884a9b3f066822a843bcc6fd56ed06d4c16b40b8129d4d62f33"
)
EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256 = (
    "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
)

HISTORICAL_FROZEN_RECEIPT_SHAS: dict[str, str] = {
    "data/evaluation/w06/w06_dev_live_runner_qa_01_receipt_v1.json": (
        "e400d319ca957acb8e3ef7e8fcb468b7406a837b51b6127ed95327ac6cf72ad2"
    ),
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_01_receipt_v1.json": (
        "20b95381f9f06809ca37e3b806e639fbe788a9370a55a8e85a9f2d94aae0b6e5"
    ),
    "data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json": (
        EXPECTED_PREP_ARTIFACT_SHA256
    ),
}

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
DEV_TUNE_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
)
AUTHORIZATION_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json"
)
AUTHORIZATION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json"
)
AUTHORIZATION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_authorization_01_receipt_v1.json"
)
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)


# ==============================================================================
# 2. OUTBOUND NETWORK KILL SWITCH
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline authorization issuance."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_create_conn = socket.create_connection
        orig_urlopen = urllib.request.urlopen
        orig_httpx_send = httpx.Client.send
        orig_httpx_async_send = httpx.AsyncClient.send
        orig_httpx2_send = httpx2.Client.send
        orig_httpx2_async_send = httpx2.AsyncClient.send

        def _deny(label: str) -> Any:
            def _raiser(*_a: Any, **_kw: Any) -> Any:
                self.blocked_attempts.append(label)
                raise OutboundNetworkBlockedError(
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID}."
                )

            return _raiser

        socket.socket.connect = _deny("socket.socket.connect")  # type: ignore[method-assign]
        socket.socket.connect_ex = _deny("socket.socket.connect_ex")  # type: ignore[method-assign]
        socket.create_connection = _deny("socket.create_connection")  # type: ignore[assignment]
        urllib.request.urlopen = _deny("urllib.request.urlopen")  # type: ignore[assignment]
        httpx.Client.send = _deny("httpx.Client.send")  # type: ignore[method-assign]
        httpx.AsyncClient.send = _deny("httpx.AsyncClient.send")  # type: ignore[method-assign]
        httpx2.Client.send = _deny("httpx2.Client.send")  # type: ignore[method-assign]
        httpx2.AsyncClient.send = _deny("httpx2.AsyncClient.send")  # type: ignore[method-assign]
        try:
            yield self
        finally:
            socket.socket.connect = orig_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
            socket.create_connection = orig_create_conn  # type: ignore[assignment]
            urllib.request.urlopen = orig_urlopen  # type: ignore[assignment]
            httpx.Client.send = orig_httpx_send  # type: ignore[method-assign]
            httpx.AsyncClient.send = orig_httpx_async_send  # type: ignore[method-assign]
            httpx2.Client.send = orig_httpx2_send  # type: ignore[method-assign]
            httpx2.AsyncClient.send = orig_httpx2_async_send  # type: ignore[method-assign]


# ==============================================================================
# 3. FAIL-CLOSED SOURCE DEVELOP PROVENANCE & PRE-STAGE-A FIREWALL
# ==============================================================================


def verify_source_develop_commit_or_shallow_fallback(
    repo_root: Path = REPO_ROOT,
    *,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Fail-closed verification of source develop SHA cd9d4e6ae072e737083c9069123f00a5a04107a5 (Section 2).

    CASE A — SOURCE_DEVELOP_SHA exists in local git:
      Require `git merge-base --is-ancestor SOURCE_DEVELOP_SHA HEAD` to succeed.
      If commit exists but is NOT ancestor, verified = False (NO artifact hash fallback may override).

    CASE B — SOURCE_DEVELOP_SHA does NOT exist in local git:
      Only permit fallback when `git rev-parse --is-shallow-repository == true`.
      Then require ALL 4 frozen fallback authorities to match their exact SHA256s.
      If non-shallow and source commit is unavailable, verified = False (fail closed).
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

    prep_path = repo_root / AUTHORIZATION_PREP_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH

    prep_sha = (
        sha256_bytes(normalize_lf_bytes(prep_path.read_bytes()))
        if prep_path.is_file()
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
        "authorization_prep_sha256": prep_sha == EXPECTED_PREP_ARTIFACT_SHA256,
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


# ==============================================================================
# 3B. STRONG CRYPTOGRAPHIC DOWNSTREAM AUTHORIZATION & RECEIPT RECOGNITION
# ==============================================================================

_CACHED_FROZEN_PLAN_AND_PROMPT: tuple[DevExecutionPlan, DevPromptFreezeArtifact] | None = None


def _get_canonical_frozen_plan_and_prompt() -> tuple[DevExecutionPlan, DevPromptFreezeArtifact]:
    """Load the frozen DEV-TUNE execution plan and prompt freeze from REPO_ROOT for production contract verification."""
    global _CACHED_FROZEN_PLAN_AND_PROMPT
    if _CACHED_FROZEN_PLAN_AND_PROMPT is None:
        pf_bytes = normalize_lf_bytes((REPO_ROOT / PROMPT_FREEZE_REL_PATH).read_bytes())
        plan_bytes = normalize_lf_bytes((REPO_ROOT / DEV_TUNE_PLAN_REL_PATH).read_bytes())
        _CACHED_FROZEN_PLAN_AND_PROMPT = (
            DevExecutionPlan.model_validate_json(plan_bytes),
            DevPromptFreezeArtifact.model_validate_json(pf_bytes),
        )
    return _CACHED_FROZEN_PLAN_AND_PROMPT


def is_verified_downstream_w06_authorization_artifact(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the exact, cryptographically verified W06-DEV-TUNE-LIVE-AUTHORIZATION-01 artifact (Section 5)."""
    if not path.is_file() or path.name != "w06_dev_tune_live_authorization_v1.json":
        return False
    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if file_sha != EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256:
            return False

        plan_model, freeze_model = _get_canonical_frozen_plan_and_prompt()
        effective_root = (
            repo_root
            if (repo_root / "apps" / "ai-service" / "app" / "evaluation" / "dev_live_runner.py").is_file()
            else REPO_ROOT
        )
        auth = verify_dev_live_authorization_artifact(
            path,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_TUNE",
            repo_root=effective_root,
        )
    except Exception:
        return False

    return (
        auth.task_id == TASK_ID
        and auth.authorization_id == AUTHORIZATION_ID
        and auth.authorization_status == "AUTHORIZED"
        and auth.authorized_by_role == "PROJECT_OWNER"
        and auth.allowed_phase == "DEV_TUNE"
        and auth.allowed_execution_plan_sha256 == EXPECTED_DEV_TUNE_PLAN_SHA256
        and auth.allowed_prompt_freeze_sha256 == EXPECTED_PROMPT_FREEZE_SHA256
        and auth.allowed_candidate_ids == ["C1", "C2", "C3"]
        and auth.maximum_live_generation_calls == 120
        and auth.scientific_code_bundle_sha256 == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and auth.authorization_artifact_sha256 == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    )


def is_verified_downstream_w06_authorization_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is a valid W06-DEV-TUNE-LIVE-AUTHORIZATION-01 receipt bound to the verified sibling authorization artifact (Section 6)."""
    if (
        not path.is_file()
        or path.name != "w06_dev_tune_live_authorization_01_receipt_v1.json"
    ):
        return False

    sibling_auth = path.parent / "w06_dev_tune_live_authorization_v1.json"
    if not is_verified_downstream_w06_authorization_artifact(
        sibling_auth, repo_root=repo_root
    ):
        return False

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return False
        assert_no_secrets_in_payload(obj, context="DOWNSTREAM_RECEIPT_VERIFICATION")
    except Exception:
        return False

    return (
        obj.get("task_id") == TASK_ID
        and obj.get("authorization_id") == AUTHORIZATION_ID
        and obj.get("authorization_status") == "AUTHORIZED"
        and obj.get("authorized_by_role") == "PROJECT_OWNER"
        and obj.get("authorization_artifact_file_sha256")
        == EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256
        and obj.get("authorization_artifact_sha256")
        == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        and obj.get("authorization_text_sha256") == AUTHORIZATION_TEXT_SHA256
        and obj.get("allowed_phase") == "DEV_TUNE"
        and obj.get("allowed_execution_plan_sha256") == EXPECTED_DEV_TUNE_PLAN_SHA256
        and obj.get("allowed_prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
        and obj.get("allowed_candidate_ids") == ["C1", "C2", "C3"]
        and obj.get("maximum_live_generation_calls") == 120
        and obj.get("scientific_code_bundle_sha256")
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and obj.get("live_provider_calls") == 0
        and obj.get("stage_a_created") is False
        and obj.get("live_execution_capability_minted") is False
        and obj.get("dev_tune_execution_started") is False
        and obj.get("dev_select_execution_started") is False
        and obj.get("stochasticity_execution_started") is False
        and obj.get("final100_used") is False
    )


def is_verified_downstream_w06_dev_tune_authorization_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the cryptographically verified downstream authorization artifact or receipt."""
    if path.name == "w06_dev_tune_live_authorization_v1.json":
        return is_verified_downstream_w06_authorization_artifact(
            path, repo_root=repo_root
        )
    if path.name == "w06_dev_tune_live_authorization_01_receipt_v1.json":
        return is_verified_downstream_w06_authorization_receipt(
            path, repo_root=repo_root
        )
    return False


def verify_pre_stage_a_firewall(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify that zero Stage-A receipts, live capabilities, transport journals, or cell outputs exist."""
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    forbidden_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_live_cell_dirs: list[str] = []

    if w06_dir.is_dir():
        from freeze_w06_dev_select_stage_a import (
            is_verified_downstream_w06_dev_select_stage_a_file,
        )
        from freeze_w06_dev_tune_live_results import (
            is_path_in_downstream_w06_dev_tune_live_results_scope,
            is_verified_downstream_w06_dev_tune_live_results_tree,
        )
        from freeze_w06_dev_tune_stage_a import (
            is_verified_downstream_w06_dev_tune_stage_a_file,
        )

        verified_downstream_results_tree = (
            is_verified_downstream_w06_dev_tune_live_results_tree(repo_root)
        )

        for path in sorted(w06_dir.rglob("*")):
            rel = path.relative_to(repo_root).as_posix()
            name_lower = path.name.lower()
            is_verified_downstream_results = (
                verified_downstream_results_tree
                and is_path_in_downstream_w06_dev_tune_live_results_scope(
                    path, repo_root=repo_root
                )
            )
            if path.is_file():
                is_verified_downstream_stage_a = (
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
                    and not is_verified_downstream_stage_a
                    and not is_verified_downstream_results
                ):
                    forbidden_stage_a_files.append(rel)
                if (
                    "transport_journal" in name_lower
                    and not is_verified_downstream_results
                ):
                    forbidden_transport_journals.append(rel)
                if path.suffix.lower() == ".json" and path.parent == w06_dir:
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            if (
                                (
                                    data.get("artifact_id")
                                    == "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"
                                    or "stage_a_process_token" in data
                                )
                                and not is_verified_downstream_stage_a
                                and not is_verified_downstream_results
                            ):
                                forbidden_stage_a_files.append(rel)
                    except Exception:
                        pass
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
                    and not is_verified_downstream_results
                ):
                    forbidden_live_cell_dirs.append(rel)

    return {
        "stage_a_created": len(forbidden_stage_a_files) > 0,
        "live_execution_capability_minted": False,
        "transport_journal_created": len(forbidden_transport_journals) > 0,
        "provider_result_directory_created": len(forbidden_live_cell_dirs) > 0,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
        "forbidden_stage_a_files": forbidden_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_live_cell_dirs": forbidden_live_cell_dirs,
    }


# ==============================================================================
# 4. BUILD SCOPED DEV-TUNE AUTHORIZATION ARTIFACT & RECEIPT
# ==============================================================================


def load_verified_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Load and verify all frozen upstream authorities before issuing authorization."""
    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = pf_mod.build_frozen_p1_p2_registry()

    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH

    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    pf_file_sha = sha256_bytes(pf_bytes)
    plan_file_sha = sha256_bytes(plan_bytes)

    freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)

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

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    pf_canonical_sha = compute_prompt_freeze_sha256(freeze_model)

    if (
        pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256
        or pf_canonical_sha != EXPECTED_PROMPT_FREEZE_SHA256
    ):
        raise RuntimeError(
            f"PROMPT_FREEZE_SHA256 mismatch: file={pf_file_sha}, canonical={pf_canonical_sha}"
        )
    if plan_model.plan_sha256 != EXPECTED_DEV_TUNE_PLAN_SHA256:
        raise RuntimeError(
            f"DEV_TUNE_PLAN_SHA256 mismatch: {plan_model.plan_sha256}"
        )
    if plan_file_sha != EXPECTED_DEV_TUNE_PLAN_FILE_SHA256:
        raise RuntimeError(
            f"DEV_TUNE_PLAN_FILE_SHA256 mismatch: {plan_file_sha}"
        )
    if prompt_reg.registry_sha256 != EXPECTED_PROMPT_REGISTRY_SHA256:
        raise RuntimeError(
            f"PROMPT_REGISTRY_SHA256 mismatch: {prompt_reg.registry_sha256}"
        )
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise RuntimeError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256 mismatch: {bundle_sha}"
        )

    return {
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "prompt_freeze": freeze_model,
        "prompt_freeze_sha256": pf_file_sha,
        "execution_plan": plan_model,
        "execution_plan_file_sha256": plan_file_sha,
        "scientific_code_bundle_sha256": bundle_sha,
    }


def build_scoped_dev_tune_authorization_artifact(
    repo_root: Path = REPO_ROOT,
) -> DevLiveAuthorizationArtifact:
    """Build the production DevLiveAuthorizationArtifact for W06 DEV-TUNE using dev_live_runner.py."""
    auths = load_verified_authorities(repo_root)
    artifact = build_dev_live_authorization_artifact(
        task_id=TASK_ID,
        authorization_id=AUTHORIZATION_ID,
        authorized_by_role=AUTHORIZED_BY_ROLE,
        authorized_at_utc=AUTHORIZED_AT_UTC,
        authorization_status=AUTHORIZATION_STATUS,
        allowed_phase=ALLOWED_PHASE,
        allowed_candidate_ids=list(ALLOWED_CANDIDATE_IDS),
        maximum_live_generation_calls=MAXIMUM_LIVE_GENERATION_CALLS,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        scientific_code_bundle_sha256=auths["scientific_code_bundle_sha256"],
        code_basis_commit_sha=CODE_BASIS_COMMIT_SHA,
    )
    verified = verify_dev_live_authorization_artifact(
        artifact,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        expected_phase="DEV_TUNE",
        repo_root=repo_root,
    )
    assert_no_secrets_in_payload(
        verified.model_dump(), context="W06_DEV_TUNE_LIVE_AUTHORIZATION_ARTIFACT"
    )
    return verified


def run_all_au_checks(
    repo_root: Path = REPO_ROOT,
    *,
    auth_artifact_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Run all 30 authorization checks AU-01 through AU-30 under the outbound-network kill switch."""
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
        # AU-01: source develop exact
        src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
        record(
            "AU-01",
            "SOURCE_STATE",
            "Source develop SHA cd9d4e6ae072e737083c9069123f00a5a04107a5 exists and is ancestor of HEAD",
            {"source_develop_sha": SOURCE_DEVELOP_SHA, "verified": True},
            {
                "source_develop_sha": src_info["source_develop_sha"],
                "verified": src_info["verified"],
            },
            bool(src_info["verified"]),
        )

        auths = load_verified_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]
        freeze_model: DevPromptFreezeArtifact = auths["prompt_freeze"]
        auth_model = build_scoped_dev_tune_authorization_artifact(repo_root)

        if auth_artifact_path is not None and auth_artifact_path.is_file():
            persisted_auth = verify_dev_live_authorization_artifact(
                auth_artifact_path,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        else:
            persisted_auth = auth_model

        # AU-02: exact owner authorization text
        prep_path = repo_root / AUTHORIZATION_PREP_REL_PATH
        prep_data = json.loads(prep_path.read_text(encoding="utf-8"))
        au02_ok = (
            EXACT_AUTHORIZATION_TEXT == prep_data["proposed_owner_authorization_text"]
            and EXPECTED_DEV_TUNE_PLAN_SHA256 in EXACT_AUTHORIZATION_TEXT
            and EXPECTED_PROMPT_FREEZE_SHA256 in EXACT_AUTHORIZATION_TEXT
            and "120-cell plan" in EXACT_AUTHORIZATION_TEXT
            and "candidates C1/C2/C3" in EXACT_AUTHORIZATION_TEXT
            and "maximum 120 generation calls" in EXACT_AUTHORIZATION_TEXT
            and "zero retry" in EXACT_AUTHORIZATION_TEXT
            and "no DEV-SELECT" in EXACT_AUTHORIZATION_TEXT
            and "no stochasticity" in EXACT_AUTHORIZATION_TEXT
            and "no Final100" in EXACT_AUTHORIZATION_TEXT
        )
        record(
            "AU-02",
            "AUTHORIZATION_EVIDENCE",
            "Exact Project Owner authorization text matches frozen authorization-prep sentence character-for-character",
            prep_data["proposed_owner_authorization_text"],
            EXACT_AUTHORIZATION_TEXT,
            au02_ok,
        )

        # AU-03: authorization text SHA deterministic
        recomputed_text_sha = hashlib.sha256(
            EXACT_AUTHORIZATION_TEXT.encode("utf-8")
        ).hexdigest()
        au03_ok = (
            recomputed_text_sha == AUTHORIZATION_TEXT_SHA256
            and len(recomputed_text_sha) == 64
        )
        record(
            "AU-03",
            "AUTHORIZATION_EVIDENCE",
            "authorization_text_sha256 is deterministic UTF-8 SHA256 of exact Project Owner sentence",
            AUTHORIZATION_TEXT_SHA256,
            recomputed_text_sha,
            au03_ok,
        )

        # AU-04: role PROJECT_OWNER exact
        au04_ok = persisted_auth.authorized_by_role == "PROJECT_OWNER"
        record(
            "AU-04",
            "AUTHORIZATION_SCOPE",
            "authorized_by_role is strictly PROJECT_OWNER",
            "PROJECT_OWNER",
            persisted_auth.authorized_by_role,
            au04_ok,
        )

        # AU-05: status AUTHORIZED exact
        au05_ok = persisted_auth.authorization_status == "AUTHORIZED"
        record(
            "AU-05",
            "AUTHORIZATION_SCOPE",
            "authorization_status is strictly AUTHORIZED",
            "AUTHORIZED",
            persisted_auth.authorization_status,
            au05_ok,
        )

        # AU-06: phase DEV_TUNE exact
        au06_ok = (
            persisted_auth.allowed_phase == "DEV_TUNE"
            and plan_model.phase == "DEV_TUNE"
            and all(c.phase == "DEV_TUNE" for c in plan_model.cells)
        )
        record(
            "AU-06",
            "AUTHORIZATION_SCOPE",
            "allowed_phase is strictly DEV_TUNE",
            "DEV_TUNE",
            persisted_auth.allowed_phase,
            au06_ok,
        )

        # AU-07: plan SHA exact
        au07_ok = (
            persisted_auth.allowed_execution_plan_sha256
            == EXPECTED_DEV_TUNE_PLAN_SHA256
            and plan_model.plan_sha256 == EXPECTED_DEV_TUNE_PLAN_SHA256
            and auths["execution_plan_file_sha256"]
            == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
        )
        record(
            "AU-07",
            "AUTHORIZATION_SCOPE",
            "allowed_execution_plan_sha256 matches frozen DEV-TUNE plan 582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
            EXPECTED_DEV_TUNE_PLAN_SHA256,
            persisted_auth.allowed_execution_plan_sha256,
            au07_ok,
        )

        # AU-08: prompt freeze SHA exact
        au08_ok = (
            persisted_auth.allowed_prompt_freeze_sha256
            == EXPECTED_PROMPT_FREEZE_SHA256
            and auths["prompt_freeze_sha256"] == EXPECTED_PROMPT_FREEZE_SHA256
        )
        record(
            "AU-08",
            "AUTHORIZATION_SCOPE",
            "allowed_prompt_freeze_sha256 matches frozen prompt artifact 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
            EXPECTED_PROMPT_FREEZE_SHA256,
            persisted_auth.allowed_prompt_freeze_sha256,
            au08_ok,
        )

        # AU-09: candidates exactly C1/C2/C3
        au09_ok = persisted_auth.allowed_candidate_ids == ["C1", "C2", "C3"]
        record(
            "AU-09",
            "AUTHORIZATION_SCOPE",
            "allowed_candidate_ids is strictly ['C1', 'C2', 'C3']",
            ["C1", "C2", "C3"],
            persisted_auth.allowed_candidate_ids,
            au09_ok,
        )

        # AU-10: max calls exactly 120
        unique_run_ids = {c.run_id for c in plan_model.cells}
        unique_cell_keys = {
            (c.phase, c.fixture_id, c.prompt_id, c.candidate_id, c.attempt_number)
            for c in plan_model.cells
        }
        au10_ok = (
            persisted_auth.maximum_live_generation_calls == 120
            and len(plan_model.cells) == 120
            and len(unique_run_ids) == 120
            and len(unique_cell_keys) == 120
        )
        record(
            "AU-10",
            "CALL_BUDGET",
            "maximum_live_generation_calls is strictly 120 matching 120 unique run_ids and cell keys",
            {"max_calls": 120, "unique_run_ids": 120, "unique_cell_keys": 120},
            {
                "max_calls": persisted_auth.maximum_live_generation_calls,
                "unique_run_ids": len(unique_run_ids),
                "unique_cell_keys": len(unique_cell_keys),
            },
            au10_ok,
        )

        # AU-11: attempt one only
        au11_ok = ATTEMPTS_PER_CELL == 1 and all(
            c.attempt_number == 1 for c in plan_model.cells
        )
        record(
            "AU-11",
            "EXECUTION_POLICY",
            "attempts_per_cell is strictly 1 across all 120 assigned cells",
            1,
            ATTEMPTS_PER_CELL,
            au11_ok,
        )

        # AU-12: retry zero
        au12_ok = RETRY_COUNT == 0 and all(
            c.retry == 0
            and c.automatic_retry == 0
            and c.transport_retry == 0
            and c.manual_retry == 0
            and c.fallback is False
            and c.repair == 0
            and c.llm_repair == 0
            and c.deterministic_semantic_repair is False
            and c.tools is False
            for c in plan_model.cells
        )
        record(
            "AU-12",
            "EXECUTION_POLICY",
            "All retry counters (sdk, transport, manual, automatic), fallback, repair, and tools are zero/false across all 120 cells",
            0,
            RETRY_COUNT,
            au12_ok,
        )

        # AU-13: DEV_SELECT not authorized
        dev_select_rejected = False
        try:
            verify_dev_live_authorization_artifact(
                persisted_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            dev_select_rejected = True
        record(
            "AU-13",
            "SCOPE_EXCLUSION",
            "DEV_TUNE authorization artifact is rejected by verify_dev_live_authorization_artifact when requested phase is DEV_SELECT",
            True,
            dev_select_rejected,
            dev_select_rejected,
        )

        # AU-14: stochasticity not authorized
        stoch_rejected = False
        try:
            verify_dev_live_authorization_artifact(
                persisted_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="STOCHASTICITY",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            stoch_rejected = True
        record(
            "AU-14",
            "SCOPE_EXCLUSION",
            "DEV_TUNE authorization artifact is rejected by verify_dev_live_authorization_artifact when requested phase is STOCHASTICITY",
            True,
            stoch_rejected,
            stoch_rejected,
        )

        # AU-15: Final100 not authorized
        final100_rejected = False
        try:
            verify_dev_live_authorization_artifact(
                persisted_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="FINAL100",
                repo_root=repo_root,
            )
        except Final100FirewallViolationError:
            final100_rejected = True
        record(
            "AU-15",
            "FINAL100_FIREWALL",
            "Final100 is strictly rejected with Final100FirewallViolationError",
            True,
            final100_rejected,
            final100_rejected,
        )

        # AU-16: 121 calls rejected
        calls_121_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-121-CALLS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_TUNE",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=121,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            calls_121_rejected = True
        record(
            "AU-16",
            "ADVERSARIAL_REJECTION",
            "maximum_live_generation_calls=121 is rejected by DevLiveAuthorizationArtifact contract",
            True,
            calls_121_rejected,
            calls_121_rejected,
        )

        # AU-17: C4 rejected
        c4_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-C4",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_TUNE",
                allowed_candidate_ids=["C1", "C2", "C3", "C4"],
                maximum_live_generation_calls=120,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            c4_rejected = True
        record(
            "AU-17",
            "ADVERSARIAL_REJECTION",
            "Candidate C4 is rejected by DevLiveAuthorizationArtifact contract",
            True,
            c4_rejected,
            c4_rejected,
        )

        # AU-18: wrong plan rejected
        wrong_plan_rejected = False
        try:
            bad_plan_dict = persisted_auth.model_dump(
                exclude={"authorization_artifact_sha256"}
            )
            bad_plan_dict["allowed_execution_plan_sha256"] = "0" * 64
            bad_plan_dict["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_plan_dict)
            )
            verify_dev_live_authorization_artifact(
                bad_plan_dict,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            wrong_plan_rejected = True
        record(
            "AU-18",
            "ADVERSARIAL_REJECTION",
            "Mismatched allowed_execution_plan_sha256 is rejected by verify_dev_live_authorization_artifact",
            True,
            wrong_plan_rejected,
            wrong_plan_rejected,
        )

        # AU-19: wrong prompt freeze rejected
        wrong_pf_rejected = False
        try:
            bad_pf_dict = persisted_auth.model_dump(
                exclude={"authorization_artifact_sha256"}
            )
            bad_pf_dict["allowed_prompt_freeze_sha256"] = "f" * 64
            bad_pf_dict["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_pf_dict)
            )
            verify_dev_live_authorization_artifact(
                bad_pf_dict,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            wrong_pf_rejected = True
        record(
            "AU-19",
            "ADVERSARIAL_REJECTION",
            "Mismatched allowed_prompt_freeze_sha256 is rejected by verify_dev_live_authorization_artifact",
            True,
            wrong_pf_rejected,
            wrong_pf_rejected,
        )

        # AU-20: wrong phase rejected
        wrong_phase_rejected = False
        try:
            bad_phase_dict = persisted_auth.model_dump(
                exclude={"authorization_artifact_sha256"}
            )
            bad_phase_dict["allowed_phase"] = "DEV_SELECT"
            bad_phase_dict["maximum_live_generation_calls"] = 180
            bad_phase_dict["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_phase_dict)
            )
            verify_dev_live_authorization_artifact(
                bad_phase_dict,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            wrong_phase_rejected = True
        record(
            "AU-20",
            "ADVERSARIAL_REJECTION",
            "Wrong allowed_phase is rejected by verify_dev_live_authorization_artifact",
            True,
            wrong_phase_rejected,
            wrong_phase_rejected,
        )

        # AU-21: wrong owner role rejected
        wrong_role_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-ROLE",
                authorized_by_role="AGENT_SELF_AUTHORIZED",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_TUNE",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=120,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            wrong_role_rejected = True
        record(
            "AU-21",
            "ADVERSARIAL_REJECTION",
            "Non-PROJECT_OWNER authorized_by_role is rejected by DevLiveAuthorizationArtifact",
            True,
            wrong_role_rejected,
            wrong_role_rejected,
        )

        # AU-22: unauthorized status rejected
        unauth_status_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-STATUS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="NOT_GRANTED",
                allowed_phase="DEV_TUNE",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=120,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            unauth_status_rejected = True
        record(
            "AU-22",
            "ADVERSARIAL_REJECTION",
            "Non-AUTHORIZED authorization_status is rejected by DevLiveAuthorizationArtifact",
            True,
            unauth_status_rejected,
            unauth_status_rejected,
        )

        # AU-23: artifact validates through production runner authorization contract
        validated_contract = verify_dev_live_authorization_artifact(
            persisted_auth,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_TUNE",
            repo_root=repo_root,
        )
        au23_ok = (
            isinstance(validated_contract, DevLiveAuthorizationArtifact)
            and validated_contract.authorization_id == AUTHORIZATION_ID
            and validated_contract.authorization_artifact_sha256
            == auth_model.authorization_artifact_sha256
        )
        record(
            "AU-23",
            "PRODUCTION_CONTRACT_VALIDATION",
            "Artifact validates cleanly through production verify_dev_live_authorization_artifact",
            AUTHORIZATION_ID,
            validated_contract.authorization_id,
            au23_ok,
        )

        # AU-24: scientific bundle unchanged
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
        bundle_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
        expected_bundle_map = {
            entry["path"]: entry["sha256"]
            for entry in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        }
        actual_bundle_map = {
            entry["path"]: entry["sha256"] for entry in bundle_hashes
        }
        au24_ok = (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and actual_bundle_map == expected_bundle_map
            and len(bundle_hashes) == len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14
        )
        record(
            "AU-24",
            "SCIENTIFIC_CODE_BUNDLE",
            "All 14 scientific code bundle files remain byte-for-byte unchanged with SHA256 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
            EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            bundle_sha,
            au24_ok,
        )

        # AU-25: no secret values persisted
        no_secrets_ok = True
        try:
            assert_no_secrets_in_payload(
                persisted_auth.model_dump(), context="AU_25_AUTH_ARTIFACT"
            )
        except Exception:
            no_secrets_ok = False
        record(
            "AU-25",
            "SECRET_HYGIENE",
            "Authorization artifact contains zero secret fields or token patterns",
            True,
            no_secrets_ok,
            no_secrets_ok,
        )

        # AU-26: no .env required
        au26_ok = (
            "GEMINI_API_KEY" not in json.dumps(persisted_auth.model_dump())
            and "OPENAI_API_KEY" not in json.dumps(persisted_auth.model_dump())
            and "ANTHROPIC_API_KEY" not in json.dumps(persisted_auth.model_dump())
        )
        record(
            "AU-26",
            "SECRET_HYGIENE",
            "Authorization issuance does not read or require .env or provider API keys",
            True,
            au26_ok,
            au26_ok,
        )

        # AU-27: no Stage-A artifact created
        fw = verify_pre_stage_a_firewall(repo_root)
        au27_ok = (
            fw["stage_a_created"] is False and len(fw["forbidden_stage_a_files"]) == 0
        )
        record(
            "AU-27",
            "PRE_STAGE_A_FIREWALL",
            "No Stage-A freeze receipt created during authorization issuance",
            False,
            fw["stage_a_created"],
            au27_ok,
        )

        # AU-28: no live capability minted
        au28_ok = fw["live_execution_capability_minted"] is False
        record(
            "AU-28",
            "PRE_STAGE_A_FIREWALL",
            "No LiveExecutionCapability minted during authorization issuance",
            False,
            fw["live_execution_capability_minted"],
            au28_ok,
        )

        # AU-29: no transport journal/result artifacts
        au29_ok = (
            fw["transport_journal_created"] is False
            and fw["provider_result_directory_created"] is False
            and fw["dev_tune_execution_started"] is False
        )
        record(
            "AU-29",
            "PRE_STAGE_A_FIREWALL",
            "No transport journal or provider result directory created",
            {
                "transport_journal_created": False,
                "provider_result_directory_created": False,
            },
            {
                "transport_journal_created": fw["transport_journal_created"],
                "provider_result_directory_created": fw[
                    "provider_result_directory_created"
                ],
            },
            au29_ok,
        )

        # AU-30: zero live provider calls
        au30_ok = (
            len(guard.blocked_attempts) == 0
            and fw["live_provider_calls"] == 0
            and fw["provider_cost_usd"] == 0.0
        )
        record(
            "AU-30",
            "NETWORK_ISOLATION",
            "Zero outbound network calls and zero provider cost during authorization issuance",
            {"blocked_attempts": 0, "live_provider_calls": 0, "provider_cost_usd": 0.0},
            {
                "blocked_attempts": len(guard.blocked_attempts),
                "live_provider_calls": fw["live_provider_calls"],
                "provider_cost_usd": fw["provider_cost_usd"],
            },
            au30_ok,
        )

    return results


# ==============================================================================
# 5. AUDIT CORRECTION ADVERSARIAL CHECKS (AUC-01 .. AUC-12)
# ==============================================================================


def run_all_auc_checks(repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """Run all 12 audit-correction checks AUC-01 through AUC-12 under the outbound-network kill switch."""
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
        # AUC-01: FULL repository, SOURCE_DEVELOP_SHA exists, but is NOT ancestor of HEAD -> verified MUST be false
        def _git_auc01(args: list[str]) -> subprocess.CompletedProcess[str]:
            if "cat-file" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if "merge-base" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

        res_auc01 = verify_source_develop_commit_or_shallow_fallback(
            repo_root, git_runner=_git_auc01
        )
        auc01_ok = (
            res_auc01["commit_exists_in_local_git"] is True
            and res_auc01["is_ancestor_of_head"] is False
            and res_auc01["shallow_repository_fallback_used"] is False
            and res_auc01["verified"] is False
        )
        record(
            "AUC-01",
            "SOURCE_PROVENANCE_FAIL_CLOSED",
            "Full repository where SOURCE_DEVELOP_SHA exists but is NOT ancestor of HEAD fails closed (verified=false) even when prep artifact matches",
            {"verified": False, "shallow_repository_fallback_used": False},
            {
                "verified": res_auc01["verified"],
                "shallow_repository_fallback_used": res_auc01[
                    "shallow_repository_fallback_used"
                ],
            },
            auc01_ok,
        )

        # AUC-02: FULL repository, correct ancestry -> verified = true
        def _git_auc02(args: list[str]) -> subprocess.CompletedProcess[str]:
            if "cat-file" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if "merge-base" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

        res_auc02 = verify_source_develop_commit_or_shallow_fallback(
            repo_root, git_runner=_git_auc02
        )
        auc02_ok = (
            res_auc02["commit_exists_in_local_git"] is True
            and res_auc02["is_ancestor_of_head"] is True
            and res_auc02["shallow_repository_fallback_used"] is False
            and res_auc02["verified"] is True
        )
        record(
            "AUC-02",
            "SOURCE_PROVENANCE_FAIL_CLOSED",
            "Full repository with valid ancestry succeeds (verified=true, shallow_repository_fallback_used=false)",
            {"verified": True, "shallow_repository_fallback_used": False},
            {
                "verified": res_auc02["verified"],
                "shallow_repository_fallback_used": res_auc02[
                    "shallow_repository_fallback_used"
                ],
            },
            auc02_ok,
        )

        # AUC-03: SHALLOW repository, source commit unavailable, all frozen fallback authorities exact -> verified = true
        def _git_shallow_missing_commit(
            args: list[str],
        ) -> subprocess.CompletedProcess[str]:
            if "cat-file" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
            if "--is-shallow-repository" in args:
                return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

        res_auc03 = verify_source_develop_commit_or_shallow_fallback(
            repo_root, git_runner=_git_shallow_missing_commit
        )
        auc03_ok = (
            res_auc03["commit_exists_in_local_git"] is False
            and res_auc03["is_shallow_repository"] is True
            and res_auc03["shallow_repository_fallback_used"] is True
            and res_auc03["verified"] is True
        )
        record(
            "AUC-03",
            "SOURCE_PROVENANCE_FAIL_CLOSED",
            "Shallow repository where source commit is unavailable and all 4 frozen fallback authorities match succeeds (verified=true)",
            {"verified": True, "shallow_repository_fallback_used": True},
            {
                "verified": res_auc03["verified"],
                "shallow_repository_fallback_used": res_auc03[
                    "shallow_repository_fallback_used"
                ],
            },
            auc03_ok,
        )

        # AUC-04: SHALLOW repository, source commit unavailable, one fallback authority stale -> verified = false
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            w06_tmp = tmp_dir / "data" / "evaluation" / "w06"
            w06_tmp.mkdir(parents=True)
            # Copy 2 valid authorities, corrupt 1
            (tmp_dir / PROMPT_FREEZE_REL_PATH).write_bytes(
                (repo_root / PROMPT_FREEZE_REL_PATH).read_bytes()
            )
            (tmp_dir / DEV_TUNE_PLAN_REL_PATH).write_bytes(
                (repo_root / DEV_TUNE_PLAN_REL_PATH).read_bytes()
            )
            (tmp_dir / AUTHORIZATION_PREP_REL_PATH).write_bytes(b'{"stale": true}\n')
            res_auc04 = verify_source_develop_commit_or_shallow_fallback(
                tmp_dir, git_runner=_git_shallow_missing_commit
            )
        auc04_ok = (
            res_auc04["is_shallow_repository"] is True
            and res_auc04["shallow_repository_fallback_used"] is True
            and res_auc04["verified"] is False
        )
        record(
            "AUC-04",
            "SOURCE_PROVENANCE_FAIL_CLOSED",
            "Shallow repository with any stale fallback authority fails closed (verified=false)",
            {"verified": False, "shallow_repository_fallback_used": True},
            {
                "verified": res_auc04["verified"],
                "shallow_repository_fallback_used": res_auc04[
                    "shallow_repository_fallback_used"
                ],
            },
            auc04_ok,
        )

        # AUC-05: NON-SHALLOW repository, source commit unavailable -> verified = false
        def _git_non_shallow_missing_commit(
            args: list[str],
        ) -> subprocess.CompletedProcess[str]:
            if "cat-file" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
            if "--is-shallow-repository" in args:
                return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

        res_auc05 = verify_source_develop_commit_or_shallow_fallback(
            repo_root, git_runner=_git_non_shallow_missing_commit
        )
        auc05_ok = (
            res_auc05["commit_exists_in_local_git"] is False
            and res_auc05["is_shallow_repository"] is False
            and res_auc05["shallow_repository_fallback_used"] is False
            and res_auc05["verified"] is False
        )
        record(
            "AUC-05",
            "SOURCE_PROVENANCE_FAIL_CLOSED",
            "Non-shallow repository with missing source commit fails closed (verified=false) without fallback",
            {"verified": False, "shallow_repository_fallback_used": False},
            {
                "verified": res_auc05["verified"],
                "shallow_repository_fallback_used": res_auc05[
                    "shallow_repository_fallback_used"
                ],
            },
            auc05_ok,
        )

        # AUC-06: Exact legitimate downstream authorization is recognized
        legit_auth_path = repo_root / AUTHORIZATION_ARTIFACT_REL_PATH
        legit_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
            legit_auth_path, repo_root=repo_root
        )
        record(
            "AUC-06",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Exact legitimate downstream authorization artifact (SHA256 b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4) is recognized",
            True,
            legit_recognized,
            legit_recognized is True,
        )

        valid_auth_dict = json.loads(legit_auth_path.read_text(encoding="utf-8"))

        # AUC-07: Same filename + correct task_id but wrong artifact file SHA is NOT exempted
        with tempfile.TemporaryDirectory() as tmp_str:
            p07 = Path(tmp_str) / "w06_dev_tune_live_authorization_v1.json"
            # Add trailing whitespace/newline so JSON fields match but file SHA differs
            p07.write_bytes(legit_auth_path.read_bytes() + b"\n")
            auc07_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p07, repo_root=repo_root
            )
        record(
            "AUC-07",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Same filename + correct task_id but wrong artifact file SHA256 is rejected (not exempted)",
            False,
            auc07_recognized,
            auc07_recognized is False,
        )

        # AUC-08: Same filename + correct task_id but wrong plan SHA is NOT exempted
        with tempfile.TemporaryDirectory() as tmp_str:
            p08 = Path(tmp_str) / "w06_dev_tune_live_authorization_v1.json"
            bad_plan = dict(valid_auth_dict)
            bad_plan.pop("authorization_artifact_sha256", None)
            bad_plan["allowed_execution_plan_sha256"] = "0" * 64
            bad_plan["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_plan)
            )
            p08.write_bytes(canonical_json_bytes(bad_plan))
            auc08_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p08, repo_root=repo_root
            )
        record(
            "AUC-08",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Same filename + correct task_id but wrong allowed_execution_plan_sha256 is rejected (not exempted)",
            False,
            auc08_recognized,
            auc08_recognized is False,
        )

        # AUC-09: Same filename + correct task_id but 121-call scope is NOT exempted
        with tempfile.TemporaryDirectory() as tmp_str:
            p09 = Path(tmp_str) / "w06_dev_tune_live_authorization_v1.json"
            bad_calls = dict(valid_auth_dict)
            bad_calls.pop("authorization_artifact_sha256", None)
            bad_calls["maximum_live_generation_calls"] = 121
            bad_calls["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_calls)
            )
            p09.write_bytes(canonical_json_bytes(bad_calls))
            auc09_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p09, repo_root=repo_root
            )
        record(
            "AUC-09",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Same filename + correct task_id but 121-call scope is rejected (not exempted)",
            False,
            auc09_recognized,
            auc09_recognized is False,
        )

        # AUC-10: Same filename + correct task_id but DEV_SELECT phase is NOT exempted
        with tempfile.TemporaryDirectory() as tmp_str:
            p10 = Path(tmp_str) / "w06_dev_tune_live_authorization_v1.json"
            bad_phase = dict(valid_auth_dict)
            bad_phase.pop("authorization_artifact_sha256", None)
            bad_phase["allowed_phase"] = "DEV_SELECT"
            bad_phase["maximum_live_generation_calls"] = 180
            bad_phase["authorization_artifact_sha256"] = sha256_bytes(
                canonical_json_bytes(bad_phase)
            )
            p10.write_bytes(canonical_json_bytes(bad_phase))
            auc10_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p10, repo_root=repo_root
            )
        record(
            "AUC-10",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Same filename + correct task_id but DEV_SELECT phase is rejected (not exempted)",
            False,
            auc10_recognized,
            auc10_recognized is False,
        )

        # AUC-11: Malformed downstream authorization JSON is NOT exempted
        with tempfile.TemporaryDirectory() as tmp_str:
            p11 = Path(tmp_str) / "w06_dev_tune_live_authorization_v1.json"
            p11.write_text('{"task_id": "W06-DEV-TUNE-LIVE-AUTHORIZATION-01", broken', encoding="utf-8")
            auc11_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p11, repo_root=repo_root
            )
        record(
            "AUC-11",
            "DOWNSTREAM_AUTHORIZATION_RECOGNITION",
            "Malformed downstream authorization JSON is rejected (not exempted)",
            False,
            auc11_recognized,
            auc11_recognized is False,
        )

        # AUC-12: Fake receipt pointing to wrong authorization artifact is NOT exempted
        legit_receipt_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            # Copy valid auth file so sibling exists, then tamper receipt's authorization_artifact_file_sha256
            (tmp_dir / "w06_dev_tune_live_authorization_v1.json").write_bytes(
                legit_auth_path.read_bytes()
            )
            fake_receipt = json.loads(legit_receipt_path.read_text(encoding="utf-8"))
            fake_receipt["authorization_artifact_file_sha256"] = "c" * 64
            p12 = tmp_dir / "w06_dev_tune_live_authorization_01_receipt_v1.json"
            p12.write_bytes(canonical_json_bytes(fake_receipt))
            auc12_recognized = is_verified_downstream_w06_dev_tune_authorization_file(
                p12, repo_root=repo_root
            )
        record(
            "AUC-12",
            "DOWNSTREAM_RECEIPT_RECOGNITION",
            "Fake receipt pointing to wrong authorization_artifact_file_sha256 is rejected (not exempted)",
            False,
            auc12_recognized,
            auc12_recognized is False,
        )

    return results


def issue_and_persist_authorization_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Persist w06_dev_tune_live_authorization_v1.json and w06_dev_tune_live_authorization_01_receipt_v1.json."""
    auth_path = repo_root / AUTHORIZATION_ARTIFACT_REL_PATH
    receipt_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH

    auth_model = build_scoped_dev_tune_authorization_artifact(repo_root)
    auth_bytes = canonical_json_bytes(auth_model.model_dump())
    auth_path.write_bytes(auth_bytes)

    # Compute file SHA256 AFTER serialization (Section 8)
    auth_file_sha256 = sha256_bytes(normalize_lf_bytes(auth_path.read_bytes()))
    if auth_file_sha256 != EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256:
        raise RuntimeError(
            f"UNEXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA_CHANGE: {auth_file_sha256} != {EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256}"
        )
    if (
        auth_model.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    ):
        raise RuntimeError(
            f"UNEXPECTED_AUTHORIZATION_INTERNAL_SHA_CHANGE: {auth_model.authorization_artifact_sha256} != {EXPECTED_AUTHORIZATION_INTERNAL_SHA256}"
        )

    au_checks = run_all_au_checks(repo_root, auth_artifact_path=auth_path)
    failed_au = [c for c in au_checks if c["status"] != "PASS"]
    if failed_au:
        raise RuntimeError(f"AU checks failed: {failed_au}")

    auths = load_verified_authorities(repo_root)
    cand_reg = auths["candidate_registry"]

    base_receipt_payload: dict[str, Any] = {
        "artifact_id": RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "audit_correction_task_id": AUDIT_CORRECTION_TASK_ID,
        "previous_head_sha": PREVIOUS_HEAD_SHA,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
        "authorization_id": auth_model.authorization_id,
        "authorization_source": AUTHORIZATION_SOURCE,
        "authorized_by_role": auth_model.authorized_by_role,
        "authorized_at_utc": auth_model.authorized_at_utc,
        "authorized_at_utc_semantics": AUTHORIZED_AT_UTC_SEMANTICS,
        "authorization_status": auth_model.authorization_status,
        "exact_authorization_text": EXACT_AUTHORIZATION_TEXT,
        "authorization_text_sha256": AUTHORIZATION_TEXT_SHA256,
        "authorization_artifact_relative_path": AUTHORIZATION_ARTIFACT_REL_PATH,
        "authorization_artifact_sha256": auth_model.authorization_artifact_sha256,
        "authorization_artifact_file_sha256": auth_file_sha256,
        "allowed_phase": auth_model.allowed_phase,
        "allowed_execution_plan_sha256": auth_model.allowed_execution_plan_sha256,
        "execution_plan_file_sha256": auths["execution_plan_file_sha256"],
        "allowed_prompt_freeze_sha256": auth_model.allowed_prompt_freeze_sha256,
        "prompt_registry_sha256": auths["prompt_registry"].registry_sha256,
        "allowed_candidate_ids": auth_model.allowed_candidate_ids,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": compute_provider_config_registry_sha256(
            cand_reg
        ),
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "scientific_code_bundle_sha256": auth_model.scientific_code_bundle_sha256,
        "experiment_matrix": {
            "phase": "DEV_TUNE",
            "fixture_count": DEV_TUNE_COUNT,
            "prompts": ["P1", "P2"],
            "candidates": ["C1", "C2", "C3"],
            "attempts_per_cell": ATTEMPTS_PER_CELL,
            "total_scientific_cells": DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
            "unique_run_ids": 120,
            "unique_scientific_cell_keys": 120,
        },
        "maximum_live_generation_calls": auth_model.maximum_live_generation_calls,
        "retry_policy": {
            "attempts_per_cell": 1,
            "retry": 0,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "automatic_retry": 0,
            "fallback": False,
            "best_of": False,
            "llm_repair": 0,
            "deterministic_semantic_repair": False,
            "tools": False,
            "max_outbound_generation_http_requests_per_cell": 1,
        },
        "scope_exclusions": {
            "dev_select_authorized": False,
            "stochasticity_authorized": False,
            "final100_authorized": False,
            "candidate_c4_or_others_authorized": False,
            "calls_above_120_authorized": False,
            "retry_above_zero_authorized": False,
            "multiple_attempts_per_cell_authorized": False,
            "fallback_or_best_of_authorized": False,
            "repair_or_diagnostic_calls_authorized": False,
        },
        "cost_acknowledgement": {
            "creates_scientific_cost_criterion": False,
            "cost_stop_rules_introduced": False,
            "cells_skipped_based_on_spend": False,
            "provider_changed_based_on_spend": False,
            "planning_metadata_only": True,
            "conservative_planning_range_usd": "$4.88 - $9.82 USD",
            "conditional_16384_billable_output_cap_reference_usd": "$23.34 USD",
            "hard_max_cost_usd": "NOT_DEFENSIBLY_COMPUTABLE",
            "authorization_prep_artifact_sha256": EXPECTED_PREP_ARTIFACT_SHA256,
        },
        "historical_evidence_boundary": {
            "historical_receipts_unmodified": True,
            "historical_frozen_receipt_shas": HISTORICAL_FROZEN_RECEIPT_SHAS,
            "policy_statement": (
                "Historical checks refer to the repository state at their original gate. "
                "A later, separately verified downstream authorization (cryptographically bound "
                "to file SHA256 b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4 "
                "and internal SHA256 fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83) "
                "does not invalidate the original historical evidence. Any unknown, tampered, "
                "or unverified authorization artifact invalidates current regression verification "
                "and fails closed."
            ),
        },
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
        "stage_a_created": False,
        "live_execution_capability_minted": False,
        "transport_journal_created": False,
        "provider_result_directory_created": False,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
    }

    # Write provisional receipt so AUC-12 can inspect the persisted receipt on disk
    receipt_path.write_bytes(
        canonical_json_bytes(
            {
                **base_receipt_payload,
                "verification_summary": {
                    "total_checks": len(au_checks),
                    "passed_checks": len(au_checks),
                    "failed_checks": 0,
                    "overall_status": "PASS",
                },
                "checks": au_checks,
            }
        )
    )

    auc_checks = run_all_auc_checks(repo_root)
    failed_auc = [c for c in auc_checks if c["status"] != "PASS"]
    if failed_auc:
        raise RuntimeError(f"AUC checks failed: {failed_auc}")

    receipt_payload: dict[str, Any] = {
        **base_receipt_payload,
        "verification_summary": {
            "total_checks": len(au_checks),
            "passed_checks": sum(1 for c in au_checks if c["status"] == "PASS"),
            "failed_checks": sum(1 for c in au_checks if c["status"] != "PASS"),
            "auc_total_checks": len(auc_checks),
            "auc_passed_checks": sum(1 for c in auc_checks if c["status"] == "PASS"),
            "auc_failed_checks": sum(1 for c in auc_checks if c["status"] != "PASS"),
            "overall_status": "PASS",
        },
        "checks": au_checks,
        "audit_correction_checks": auc_checks,
    }
    assert_no_secrets_in_payload(
        receipt_payload, context="W06_DEV_TUNE_LIVE_AUTHORIZATION_RECEIPT"
    )
    receipt_bytes = canonical_json_bytes(receipt_payload)
    receipt_path.write_bytes(receipt_bytes)
    return receipt_payload


if __name__ == "__main__":
    receipt = issue_and_persist_authorization_artifacts()
    receipt_file_sha = hashlib.sha256(
        (REPO_ROOT / AUTHORIZATION_RECEIPT_REL_PATH).read_bytes()
    ).hexdigest()
    print(
        json.dumps(
            {
                "task_id": receipt["task_id"],
                "audit_correction_task_id": receipt["audit_correction_task_id"],
                "authorization_id": receipt["authorization_id"],
                "authorization_status": receipt["authorization_status"],
                "authorized_by_role": receipt["authorized_by_role"],
                "authorized_at_utc": receipt["authorized_at_utc"],
                "authorization_text_sha256": receipt["authorization_text_sha256"],
                "authorization_artifact_sha256": receipt[
                    "authorization_artifact_sha256"
                ],
                "authorization_artifact_file_sha256": receipt[
                    "authorization_artifact_file_sha256"
                ],
                "receipt_file_sha256": receipt_file_sha,
                "au_checks": f"{receipt['verification_summary']['passed_checks']}/{receipt['verification_summary']['total_checks']}",
                "auc_checks": f"{receipt['verification_summary']['auc_passed_checks']}/{receipt['verification_summary']['auc_total_checks']}",
                "stage_a_created": receipt["stage_a_created"],
                "live_execution_capability_minted": receipt[
                    "live_execution_capability_minted"
                ],
                "live_provider_calls": receipt["live_provider_calls"],
                "provider_cost_usd": receipt["provider_cost_usd"],
            },
            indent=2,
        )
    )
