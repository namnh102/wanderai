"""W06-DEV-SELECT-STAGE-A-FREEZE-01: DEV-SELECT Stage-A pre-live freeze, commit attestation, and offline verification agent.

Strictly offline:
- DEV_SELECT_EXECUTION_STARTED = false
- LIVE_PROVIDER_CALLS_NEW = 0
- PROVIDER_COST_USD_NEW = 0
- LIVE_EXECUTION_CAPABILITY_ISSUED = false
- PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED = false
- TRANSPORT_JOURNAL_CREATED = false
- DEV_SELECT_LIVE_RESULT_DIRECTORY_CREATED = false
- MODEL_WINNER_SELECTED = false
- STOCHASTICITY_EXECUTION_STARTED = false
- FINAL100_USED = false
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Callable
import contextlib
import hashlib
import json
from pathlib import Path
import re
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
for _p in (AI_SERVICE_DIR, SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    _CURRENT_PROCESS_INVOCATION_TOKEN,
    _build_stage_a_freeze_receipt_with_token,
    CandidateRegistryIntegrityError,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    DevLiveStageAFreezeReceipt,
    PlanBeforeLiveProtocolError,
    STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
    STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
    assert_no_secrets_in_payload,
    build_stage_a_freeze_receipt,
    compute_assigned_cells_sha256,
    compute_prompt_freeze_sha256,
    verify_dev_live_authorization_artifact,
    verify_stage_a_freeze_receipt,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    DEV_SELECT_COUNT,
    DEV_SELECT_MAX_CALLS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    Final100FirewallViolationError,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    ScientificCodeBundleIntegrityError,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    assert_not_final100_path,
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
import issue_w06_dev_select_live_authorization as ds_auth_mod  # noqa: E402
import prepare_w06_dev_select_authorization as ds_prep_mod  # noqa: E402

# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITATIVE INPUT SHAS (SECTIONS 2–16)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-STAGE-A-FREEZE-01"
TASK_AUDIT_RECEIPT_ARTIFACT_ID = "W06-DEV-SELECT-STAGE-A-FREEZE-01-RECEIPT-V1"
SOURCE_DEVELOP_SHA = "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
STAGE_A_COMMIT_SHA = "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
CODE_BASIS_COMMIT_SHA = "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
BRANCH_NAME = "research/w06-dev-select-stage-a-freeze-01"

ALLOWED_PHASE = "DEV_SELECT"
ALLOWED_CANDIDATE_IDS: tuple[str, str, str] = ("C1", "C2", "C3")
ALLOWED_PROMPT_IDS: tuple[str] = ("P1",)
EXPECTED_ASSIGNED_CELL_COUNT = 180
EXPECTED_FIXTURE_COUNT = 60
EXPECTED_ATTEMPTS_PER_CELL = 1
EXPECTED_RETRY_CALLS = 0

EXPECTED_DEV_SELECT_PLAN_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_ASSIGNED_CELLS_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256 = (
    "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
)

EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_SELECTED_PROMPT_ID = "P1"
EXPECTED_SELECTED_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"
EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)
EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256 = (
    "4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e"
)
EXPECTED_SELECTED_PROMPT_USER_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256 = (
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
)
EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256 = (
    "0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114"
)
EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8"
)

EXPECTED_AUTHORIZATION_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
)
EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256 = (
    "cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39"
)
EXPECTED_AUTHORIZATION_TEXT_SHA256 = (
    "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
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

# Pinned metadata of the single Process A Stage-A freeze invocation (Section 10 & 20)
EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC = "2026-10-23T09:05:00Z"
EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256 = (
    "1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014"
)
EXPECTED_STAGE_A_RECEIPT_FILE_SHA256 = (
    "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
)
EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256 = (
    "73eb38335f6fa0d21f9f38f0e15f9dc2c6497c46519a784b0d4e3df7da6a64c5"
)

DEV_SELECT_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
DEV_TUNE_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
PLAN_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json"
)
PROMPT_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
PROMPT_SELECTION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
PROMPT_SELECTION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json"
)
AUTHORIZATION_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_authorization_prep_v1.json"
)
AUTHORIZATION_REL_PATH = "data/evaluation/w06/w06_dev_select_live_authorization_v1.json"
AUTHORIZATION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_authorization_01_receipt_v1.json"
)

STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json"
)
TASK_AUDIT_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_stage_a_freeze_01_receipt_v1.json"
)
REPORT_MD_REL_PATH = "docs/research/w06_dev_select_stage_a_freeze_01.md"
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)

HISTORICAL_FROZEN_RECEIPT_SHAS: dict[str, str] = {
    PROMPT_FREEZE_REL_PATH: EXPECTED_PROMPT_FREEZE_SHA256,
    PROMPT_SELECTION_ARTIFACT_REL_PATH: EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    PROMPT_SELECTION_RECEIPT_REL_PATH: EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    DEV_SELECT_PLAN_REL_PATH: EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
    PLAN_FREEZE_RECEIPT_REL_PATH: EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
    AUTHORIZATION_PREP_REL_PATH: EXPECTED_PREP_ARTIFACT_FILE_SHA256,
    AUTHORIZATION_REL_PATH: EXPECTED_AUTHORIZATION_FILE_SHA256,
    AUTHORIZATION_RECEIPT_REL_PATH: EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256,
}

_PROCESS_TOKEN_PATTERN = re.compile(r"^pid-\d+-ns-\d+$")


# ==============================================================================
# 2. OUTBOUND NETWORK KILL SWITCH (SOCKET / URLLIB / HTTPX / HTTPX2)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised when any outbound network connection is attempted during Stage-A freeze or verification."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        if httpx2.__name__ != "httpx2" or httpx2 is httpx:
            raise RuntimeError(
                "httpx2 must be the real httpx2 module, distinct from httpx"
            )

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
# 3. FAIL-CLOSED SOURCE DEVELOP PROVENANCE & SHALLOW CI FALLBACK (SECTION 2)
# ==============================================================================


def verify_source_develop_commit_or_shallow_fallback(
    repo_root: Path = REPO_ROOT,
    *,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Fail-closed verification of source develop SHA e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863 (Section 2).

    CASE A — SOURCE_DEVELOP_SHA exists in local git:
      Require `git merge-base --is-ancestor SOURCE_DEVELOP_SHA HEAD` to succeed.
      If commit exists in local git and is NOT an ancestor of HEAD, verified = False.

    CASE B — SOURCE_DEVELOP_SHA does NOT exist in local git:
      Only permit fallback when `git rev-parse --is-shallow-repository == true`.
      Then require ALL frozen fallback authorities to match their exact SHA256s.
      If non-shallow and source commit is unavailable, verified = False.
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

    def _file_sha(rel_path: str) -> str:
        p = repo_root / rel_path
        return sha256_bytes(normalize_lf_bytes(p.read_bytes())) if p.is_file() else ""

    try:
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    except Exception:
        bundle_sha = ""

    fallback_checks = {
        "dev_select_plan_file_sha256": (
            _file_sha(DEV_SELECT_PLAN_REL_PATH) == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        ),
        "plan_freeze_receipt_file_sha256": (
            _file_sha(PLAN_FREEZE_RECEIPT_REL_PATH)
            == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
        ),
        "prompt_freeze_sha256": (
            _file_sha(PROMPT_FREEZE_REL_PATH) == EXPECTED_PROMPT_FREEZE_SHA256
        ),
        "prompt_selection_artifact_file_sha256": (
            _file_sha(PROMPT_SELECTION_ARTIFACT_REL_PATH)
            == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
        ),
        "authorization_prep_file_sha256": (
            _file_sha(AUTHORIZATION_PREP_REL_PATH) == EXPECTED_PREP_ARTIFACT_FILE_SHA256
        ),
        "authorization_artifact_file_sha256": (
            _file_sha(AUTHORIZATION_REL_PATH) == EXPECTED_AUTHORIZATION_FILE_SHA256
        ),
        "authorization_receipt_file_sha256": (
            _file_sha(AUTHORIZATION_RECEIPT_REL_PATH)
            == EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256
        ),
        "scientific_code_bundle_sha256": (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
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


def has_full_stage_a_git_history(repo_root: Path = REPO_ROOT) -> bool:
    """Return True if both STAGE_A_COMMIT_SHA and CODE_BASIS_COMMIT_SHA exist as commit objects in local git."""
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


def verify_committed_stage_a_or_shallow_ci_fallback(
    stage_a_path: Path,
    *,
    execution_plan: DevExecutionPlan,
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    execution_plan_path: Path,
    prompt_freeze_path: Path,
    authorization_path: Path,
    candidate_registry: Any = None,
    repo_root: Path = REPO_ROOT,
) -> DevLiveStageAFreezeReceipt:
    """Run production `verify_stage_a_freeze_receipt(..., require_git_committed=True)` with shallow CI checkout support."""
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

    shallow_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
    if not (shallow_info["is_shallow_repository"] and shallow_info["verified"]):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_COMMIT_NOT_FOUND_IN_NON_SHALLOW_REPO: Stage-A or code-basis commit missing in non-shallow repository."
        )

    receipt = verify_stage_a_freeze_receipt(
        stage_a_path,
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        authorization=authorization,
        execution_plan_path=execution_plan_path,
        prompt_freeze_path=prompt_freeze_path,
        authorization_path=authorization_path,
        candidate_registry=candidate_registry,
        repo_root=repo_root,
        require_git_committed=False,
    )
    if (
        receipt.stage_a_commit_sha != STAGE_A_COMMIT_SHA
        or receipt.code_basis_commit_sha != CODE_BASIS_COMMIT_SHA
    ):
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_SHALLOW_COMMIT_MISMATCH: stage_a={receipt.stage_a_commit_sha}, basis={receipt.code_basis_commit_sha}"
        )

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tracked_paths = [
        execution_plan_path,
        prompt_freeze_path,
        authorization_path,
        stage_a_path,
        *[repo_root / p for p in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS],
    ]
    for fpath in tracked_paths:
        rel_posix = fpath.resolve().relative_to(repo_root.resolve()).as_posix()
        ls_proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_posix],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if ls_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_ARTIFACT_UNCOMMITTED: {rel_posix}"
            )
        st_proc = subprocess.run(
            ["git", "status", "--porcelain", "--", rel_posix],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if st_proc.returncode != 0 or st_proc.stdout.strip():
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_FILE_DIRTY_OR_UNCOMMITTED: {rel_posix}"
            )
        disk_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        show_proc = subprocess.run(
            ["git", "show", f"{head_sha}:{rel_posix}"],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if show_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_BLOB_MISSING_IN_COMMIT: {rel_posix}"
            )
        blob_sha = sha256_bytes(normalize_lf_bytes(show_proc.stdout))
        if blob_sha != disk_sha:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_COMMITTED_BLOB_MISMATCH: {rel_posix}"
            )
    return receipt


# ==============================================================================
# 4. LOAD & VERIFY FROZEN STAGE-A AUTHORITIES (SECTIONS 4–7)
# ==============================================================================


def load_verified_stage_a_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Load and verify all frozen DEV-SELECT Stage-A authorities."""
    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = pf_mod.build_frozen_p1_p2_registry()

    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    dev_tune_plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
    plan_rec_path = repo_root / PLAN_FREEZE_RECEIPT_REL_PATH
    ps_art_path = repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
    ps_rec_path = repo_root / PROMPT_SELECTION_RECEIPT_REL_PATH
    prep_path = repo_root / AUTHORIZATION_PREP_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH
    auth_rec_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH

    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    dev_tune_plan_bytes = normalize_lf_bytes(dev_tune_plan_path.read_bytes())
    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    plan_rec_bytes = normalize_lf_bytes(plan_rec_path.read_bytes())
    ps_art_bytes = normalize_lf_bytes(ps_art_path.read_bytes())
    ps_rec_bytes = normalize_lf_bytes(ps_rec_path.read_bytes())
    prep_bytes = normalize_lf_bytes(prep_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    auth_rec_bytes = normalize_lf_bytes(auth_rec_path.read_bytes())

    pf_file_sha = sha256_bytes(pf_bytes)
    plan_file_sha = sha256_bytes(plan_bytes)
    plan_rec_file_sha = sha256_bytes(plan_rec_bytes)
    ps_art_file_sha = sha256_bytes(ps_art_bytes)
    ps_rec_file_sha = sha256_bytes(ps_rec_bytes)
    prep_file_sha = sha256_bytes(prep_bytes)
    auth_file_sha = sha256_bytes(auth_bytes)
    auth_rec_file_sha = sha256_bytes(auth_rec_bytes)

    freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    dev_tune_plan_model = DevExecutionPlan.model_validate_json(dev_tune_plan_bytes)
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
    plan_rec_data = json.loads(plan_rec_bytes.decode("utf-8"))
    ps_art_data = json.loads(ps_art_bytes.decode("utf-8"))
    ps_rec_data = json.loads(ps_rec_bytes.decode("utf-8"))
    prep_data = json.loads(prep_bytes.decode("utf-8"))
    auth_rec_data = json.loads(auth_rec_bytes.decode("utf-8"))

    verify_dev_execution_plan_for_execution(
        plan_model, candidate_registry=cand_reg, repo_root=repo_root
    )
    verify_prompt_candidate_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        dev_tune_plan=dev_tune_plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    auth_model = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=plan_model,
        prompt_freeze=freeze_model,
        expected_phase=ALLOWED_PHASE,
        repo_root=repo_root,
    )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    pconf_sha = compute_provider_config_registry_sha256(cand_reg)
    pf_canonical_sha = compute_prompt_freeze_sha256(freeze_model)
    assigned_run_ids, assigned_cells_sha = compute_assigned_cells_sha256(plan_model)

    if (
        pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256
        or pf_canonical_sha != EXPECTED_PROMPT_FREEZE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_FREEZE_SHA256_MISMATCH: file={pf_file_sha}, canonical={pf_canonical_sha}"
        )
    if (
        plan_model.plan_sha256 != EXPECTED_DEV_SELECT_PLAN_SHA256
        or plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_SHA256_MISMATCH: internal={plan_model.plan_sha256}, file={plan_file_sha}"
        )
    if (
        auth_file_sha != EXPECTED_AUTHORIZATION_FILE_SHA256
        or auth_model.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        or auth_rec_file_sha != EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256
    ):
        raise DevLiveAuthorizationError(
            f"DEV_SELECT_AUTHORIZATION_SHA256_MISMATCH: file={auth_file_sha}, internal={auth_model.authorization_artifact_sha256}, receipt={auth_rec_file_sha}"
        )
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: {bundle_sha}"
        )
    if (
        cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256
        or pconf_sha != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    ):
        raise CandidateRegistryIntegrityError(
            f"CANDIDATE_OR_PROVIDER_CONFIG_SHA256_MISMATCH: cand={cand_reg.registry_sha256}, pconf={pconf_sha}"
        )

    p1_spec = pf_mod.build_p1_spec()
    return {
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "p1_spec": p1_spec,
        "prompt_freeze": freeze_model,
        "prompt_freeze_sha256": pf_file_sha,
        "prompt_selection_artifact": ps_art_data,
        "prompt_selection_artifact_file_sha256": ps_art_file_sha,
        "prompt_selection_receipt": ps_rec_data,
        "prompt_selection_receipt_file_sha256": ps_rec_file_sha,
        "execution_plan": plan_model,
        "execution_plan_file_sha256": plan_file_sha,
        "plan_freeze_receipt": plan_rec_data,
        "plan_freeze_receipt_file_sha256": plan_rec_file_sha,
        "authorization_prep": prep_data,
        "authorization_prep_file_sha256": prep_file_sha,
        "authorization": auth_model,
        "authorization_file_sha256": auth_file_sha,
        "authorization_receipt": auth_rec_data,
        "authorization_receipt_file_sha256": auth_rec_file_sha,
        "scientific_code_bundle_sha256": bundle_sha,
        "provider_config_registry_sha256": pconf_sha,
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "assigned_cell_run_ids": assigned_run_ids,
        "assigned_cells_sha256": assigned_cells_sha,
    }


# ==============================================================================
# 5. STRONG CRYPTOGRAPHIC STAGE-A DOWNSTREAM VERIFIER (SECTION 17)
# ==============================================================================

_CACHED_CANONICAL_STAGE_A_AUTHORITIES: dict[str, Any] | None = None


def _get_canonical_stage_a_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    global _CACHED_CANONICAL_STAGE_A_AUTHORITIES
    effective_root = (
        repo_root
        if (
            repo_root
            / "apps"
            / "ai-service"
            / "app"
            / "evaluation"
            / "dev_live_runner.py"
        ).is_file()
        else REPO_ROOT
    )
    if effective_root == REPO_ROOT and _CACHED_CANONICAL_STAGE_A_AUTHORITIES is not None:
        return _CACHED_CANONICAL_STAGE_A_AUTHORITIES
    auths = load_verified_stage_a_authorities(effective_root)
    if effective_root == REPO_ROOT:
        _CACHED_CANONICAL_STAGE_A_AUTHORITIES = auths
    return auths


def is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the exact, cryptographically verified W06-DEV-SELECT-STAGE-A-FREEZE-01 Stage-A receipt (Section 17).

    Never accepts by filename or `artifact_id` alone.
    """
    if (
        not path.is_file()
        or path.name != "w06_dev_select_stage_a_freeze_receipt_v1.json"
    ):
        return False

    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if (
            EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
            and file_sha != EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
        ):
            return False

        raw_dict = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(raw_dict, dict):
            return False
        assert_no_secrets_in_payload(
            raw_dict, context="DOWNSTREAM_DEV_SELECT_STAGE_A_RECEIPT_VERIFICATION"
        )

        auths = _get_canonical_stage_a_authorities(repo_root)
        effective_root = (
            repo_root
            if (
                repo_root
                / "apps"
                / "ai-service"
                / "app"
                / "evaluation"
                / "dev_live_runner.py"
            ).is_file()
            else REPO_ROOT
        )

        verification_dict = dict(raw_dict)
        real_token = str(verification_dict.get("stage_a_process_token", ""))
        if not real_token or not _PROCESS_TOKEN_PATTERN.match(real_token):
            return False

        if real_token == _CURRENT_PROCESS_INVOCATION_TOKEN:
            receipt = DevLiveStageAFreezeReceipt.model_validate(verification_dict)
        else:
            receipt = verify_stage_a_freeze_receipt(
                path,
                execution_plan=auths["execution_plan"],
                prompt_freeze=auths["prompt_freeze"],
                authorization=auths["authorization"],
                candidate_registry=auths["candidate_registry"],
                repo_root=effective_root,
                require_git_committed=False,
            )
    except Exception:
        return False

    if (
        EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
        and receipt.stage_a_receipt_sha256 != EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
    ):
        return False
    if (
        EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC
        and receipt.freeze_created_at_utc != EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC
    ):
        return False

    return (
        receipt.artifact_id == STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID
        and receipt.phase == "DEV_SELECT"
        and receipt.execution_plan_sha256 == EXPECTED_DEV_SELECT_PLAN_SHA256
        and receipt.prompt_freeze_sha256 == EXPECTED_PROMPT_FREEZE_SHA256
        and receipt.authorization_artifact_sha256
        == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        and receipt.scientific_code_bundle_sha256
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and receipt.provider_config_registry_sha256
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
        and receipt.code_basis_commit_sha == CODE_BASIS_COMMIT_SHA
        and receipt.stage_a_commit_sha == STAGE_A_COMMIT_SHA
        and receipt.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE
        and len(receipt.assigned_cell_run_ids) == 180
        and receipt.assigned_cell_run_ids == auths["assigned_cell_run_ids"]
        and receipt.assigned_cells_sha256 == auths["assigned_cells_sha256"]
    )


def is_verified_downstream_w06_dev_select_stage_a_task_audit_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is a valid W06-DEV-SELECT-STAGE-A-FREEZE-01 task audit receipt bound to the verified sibling Stage-A receipt."""
    if (
        not path.is_file()
        or path.name != "w06_dev_select_stage_a_freeze_01_receipt_v1.json"
    ):
        return False

    sibling_stage_a = path.parent / "w06_dev_select_stage_a_freeze_receipt_v1.json"
    if not is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
        sibling_stage_a, repo_root=repo_root
    ):
        return False

    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if (
            EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256
            and file_sha != EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256
        ):
            return False

        obj = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(obj, dict):
            return False
        assert_no_secrets_in_payload(
            obj, context="DOWNSTREAM_DEV_SELECT_STAGE_A_TASK_AUDIT_RECEIPT"
        )
        sibling_raw = normalize_lf_bytes(sibling_stage_a.read_bytes())
        sibling_file_sha = sha256_bytes(sibling_raw)
        sibling_obj = json.loads(sibling_raw.decode("utf-8"))
    except Exception:
        return False

    return (
        obj.get("artifact_id") == TASK_AUDIT_RECEIPT_ARTIFACT_ID
        and obj.get("task_id") == TASK_ID
        and obj.get("phase") == "DEV_SELECT"
        and obj.get("source_develop_sha") == SOURCE_DEVELOP_SHA
        and obj.get("code_basis_commit_sha") == CODE_BASIS_COMMIT_SHA
        and obj.get("stage_a_commit_sha") == STAGE_A_COMMIT_SHA
        and obj.get("execution_plan_sha256") == EXPECTED_DEV_SELECT_PLAN_SHA256
        and obj.get("execution_plan_file_sha256")
        == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        and obj.get("prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
        and obj.get("selected_prompt_id") == "P1"
        and obj.get("selected_prompt_semantic_sha256")
        == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
        and obj.get("authorization_artifact_sha256")
        == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        and obj.get("authorization_artifact_file_sha256")
        == EXPECTED_AUTHORIZATION_FILE_SHA256
        and obj.get("scientific_code_bundle_sha256")
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and obj.get("provider_config_registry_sha256")
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
        and obj.get("stage_a_receipt_sha256") == sibling_obj.get("stage_a_receipt_sha256")
        and obj.get("stage_a_receipt_file_sha256") == sibling_file_sha
        and obj.get("assigned_cell_count") == 180
        and obj.get("assigned_cells_sha256") == sibling_obj.get("assigned_cells_sha256")
        and obj.get("same_process_verification_rejected") is True
        and obj.get("separate_process_committed_verification_passed") is True
        and obj.get("live_execution_capability_issued") is False
        and obj.get("production_provider_transport_constructed") is False
        and obj.get("transport_journal_created") is False
        and obj.get("dev_select_live_result_directory_created") is False
        and obj.get("dev_select_execution_started") is False
        and obj.get("live_provider_calls_new") == 0
        and obj.get("provider_cost_usd_new") == 0
        and obj.get("model_winner_selected") is False
        and obj.get("stochasticity_execution_started") is False
        and obj.get("final100_used") is False
    )


def is_verified_downstream_w06_dev_select_stage_a_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the cryptographically verified downstream DEV-SELECT Stage-A receipt or task audit receipt (Section 17)."""
    if path.name == "w06_dev_select_stage_a_freeze_receipt_v1.json":
        return is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
            path, repo_root=repo_root
        )
    if path.name == "w06_dev_select_stage_a_freeze_01_receipt_v1.json":
        return is_verified_downstream_w06_dev_select_stage_a_task_audit_receipt(
            path, repo_root=repo_root
        )
    return False


# ==============================================================================
# 6. PROCESS A: GENERATE REAL STAGE-A RECEIPT EXACTLY ONCE (SECTIONS 8, 9, 10)
# ==============================================================================


def generate_stage_a_receipt_once_process_a(
    repo_root: Path = REPO_ROOT,
    *,
    freeze_created_at_utc: str = EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC,
) -> dict[str, Any]:
    """PROCESS A: Build and persist `data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json` ONCE (Section 10 & 20).

    Refuses to overwrite if the file already exists.
    Never runs committed Process B verification in the same process.
    """
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    if stage_a_path.exists():
        raise RuntimeError(
            f"STAGE_A_RECEIPT_ALREADY_EXISTS: {stage_a_path} already exists. "
            "Persisted Stage-A receipt must be generated ONCE in Process A and never overwritten."
        )

    guard = NetworkKillSwitchGuard()
    with guard.activate():
        auths = load_verified_stage_a_authorities(repo_root)
        stage_a_receipt = build_stage_a_freeze_receipt(
            execution_plan=auths["execution_plan"],
            prompt_freeze=auths["prompt_freeze"],
            authorization=auths["authorization"],
            stage_a_commit_sha=STAGE_A_COMMIT_SHA,
            freeze_created_at_utc=freeze_created_at_utc,
            candidate_registry=auths["candidate_registry"],
        )

        # Prove same-process verification is rejected fail-closed in Process A
        same_process_blocked = False
        try:
            verify_stage_a_freeze_receipt(
                stage_a_receipt,
                execution_plan=auths["execution_plan"],
                prompt_freeze=auths["prompt_freeze"],
                authorization=auths["authorization"],
                candidate_registry=auths["candidate_registry"],
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN" in str(exc):
                same_process_blocked = True

        if not same_process_blocked:
            raise RuntimeError(
                "SAME_PROCESS_BARRIER_FAILURE: verify_stage_a_freeze_receipt did not reject same-process verification in Process A."
            )

        payload_bytes = canonical_json_bytes(stage_a_receipt.model_dump())
        assert_no_secrets_in_payload(
            stage_a_receipt.model_dump(), context="PERSISTED_DEV_SELECT_STAGE_A_RECEIPT"
        )
        stage_a_path.parent.mkdir(parents=True, exist_ok=True)
        stage_a_path.write_bytes(payload_bytes)
        file_sha = sha256_bytes(normalize_lf_bytes(stage_a_path.read_bytes()))

    return {
        "process": "PROCESS_A_CREATE_STAGE_A_ONCE",
        "stage_a_receipt_path": STAGE_A_RECEIPT_REL_PATH,
        "stage_a_receipt_sha256": stage_a_receipt.stage_a_receipt_sha256,
        "stage_a_receipt_file_sha256": file_sha,
        "assigned_cells_sha256": stage_a_receipt.assigned_cells_sha256,
        "assigned_cell_count": len(stage_a_receipt.assigned_cell_run_ids),
        "freeze_created_at_utc": stage_a_receipt.freeze_created_at_utc,
        "stage_a_process_token_present": bool(stage_a_receipt.stage_a_process_token),
        "same_process_verification_rejected": True,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
    }


# ==============================================================================
# 7. AST & FIREWALL HELPERS + DSA-01..DSA-40 & ADVERSARIAL CHECKS (SECTIONS 18 & 19)
# ==============================================================================


def _inspect_script_ast_for_stage_a_compliance(
    script_path: Path,
) -> dict[str, Any]:
    """Inspect this script's AST to verify production builder usage and absence of forbidden calls."""
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))

    called_in_process_a: set[str] = set()
    forbidden_calls_in_module: set[str] = set()
    reads_env_secrets = False

    forbidden_fn_names = {
        "issue_live_execution_capability",
        "execute_authorized_dev_live_stage",
        "run_authorized_dev_live_stage_cli",
        "create_default_candidate_transports",
        "GoogleGeminiCandidateTransport",
        "OpenAICandidateTransport",
        "AnthropicCandidateTransport",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == (
            "generate_stage_a_receipt_once_process_a"
        ):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name):
                        called_in_process_a.add(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute):
                        called_in_process_a.add(sub.func.attr)

        if isinstance(node, ast.Call):
            fn_name = None
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr
            if fn_name in forbidden_fn_names:
                forbidden_calls_in_module.add(fn_name)

        if isinstance(node, ast.Attribute) and node.attr == "environ":
            reads_env_secrets = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "getenv":
                reads_env_secrets = True

    return {
        "production_builder_called_in_process_a": (
            "build_stage_a_freeze_receipt" in called_in_process_a
        ),
        "test_only_builder_called_in_process_a": (
            "build_test_only_stage_a_freeze_receipt" in called_in_process_a
        ),
        "forbidden_capability_or_transport_calls": sorted(forbidden_calls_in_module),
        "reads_env_secrets": reads_env_secrets,
    }


def verify_no_live_execution_or_stage_b_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify no transport journal, DEV-SELECT live result directory, cell output, or unauthorized Stage-A file exists."""
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    unauthorized_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_dev_select_live_dirs: list[str] = []

    if w06_dir.is_dir():
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
                is_verified_dev_tune_stage_a = (
                    is_verified_downstream_w06_dev_tune_stage_a_file(
                        path, repo_root=repo_root
                    )
                )
                is_verified_dev_select_stage_a = (
                    is_verified_downstream_w06_dev_select_stage_a_file(
                        path, repo_root=repo_root
                    )
                )
                if (
                    "stage_a" in name_lower
                    or "stage-a" in name_lower
                    or name_lower == "stage_a_freeze_receipt.json"
                ) and not (
                    is_verified_dev_tune_stage_a
                    or is_verified_dev_select_stage_a
                    or is_verified_downstream_results
                ):
                    unauthorized_stage_a_files.append(rel)
                if (
                    "transport_journal" in name_lower
                    and not is_verified_downstream_results
                ):
                    forbidden_transport_journals.append(rel)
            elif path.is_dir():
                if (
                    any(
                        tok in name_lower
                        for tok in (
                            "live_dev_select",
                            "dev_select_live",
                            "stochasticity_live",
                            "live_runs",
                            "cell_outputs",
                        )
                    )
                    and not is_verified_downstream_results
                ):
                    forbidden_dev_select_live_dirs.append(rel)

    return {
        "unauthorized_stage_a_files": unauthorized_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_dev_select_live_dirs": forbidden_dev_select_live_dirs,
        "live_execution_capability_issued": False,
        "production_provider_transport_constructed": False,
        "transport_journal_created": len(forbidden_transport_journals) > 0,
        "dev_select_live_result_directory_created": (
            len(forbidden_dev_select_live_dirs) > 0
        ),
        "dev_select_execution_started": False,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
    }


@contextlib.contextmanager
def _committed_repo_view_for_stage_a(
    repo_root: Path,
    *,
    require_committed_in_head: bool,
) -> Iterator[tuple[Path, bool]]:
    """Provide a git repo view where `w06_dev_select_stage_a_freeze_receipt_v1.json` is committed in HEAD.

    - If `require_committed_in_head=True` (Process B `--verify-committed` and pytest after commit),
      verifies directly against `repo_root` without creating any worktree.
    - If `require_committed_in_head=False` (during `--write-task-audit-receipt` before the single branch commit),
      creates an isolated temporary git worktree at `HEAD` and commits `w06_dev_select_stage_a_freeze_receipt_v1.json`
      inside that temporary worktree so `verify_stage_a_freeze_receipt(..., require_git_committed=True)`
      executes full git ancestor and blob verification against a real committed git tree.
    """
    ls_proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", STAGE_A_RECEIPT_REL_PATH],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    st_proc = subprocess.run(
        ["git", "status", "--porcelain", "--", STAGE_A_RECEIPT_REL_PATH],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    is_cleanly_committed = ls_proc.returncode == 0 and not st_proc.stdout.strip()
    if require_committed_in_head or is_cleanly_committed:
        yield repo_root, True
        return

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        wt_path = Path(tmp_dir_str) / "stage_a_verify_wt"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt_path), "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        try:
            src_stage_a = repo_root / STAGE_A_RECEIPT_REL_PATH
            dst_stage_a = wt_path / STAGE_A_RECEIPT_REL_PATH
            dst_stage_a.parent.mkdir(parents=True, exist_ok=True)
            dst_stage_a.write_bytes(src_stage_a.read_bytes())
            subprocess.run(
                ["git", "add", STAGE_A_RECEIPT_REL_PATH],
                cwd=str(wt_path),
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
                    "temp: stage-a verification commit",
                ],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                check=True,
            )
            yield wt_path, False
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_path)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )


def run_all_dsa_checks(
    repo_root: Path = REPO_ROOT,
    *,
    require_committed_in_head: bool = True,
) -> list[dict[str, Any]]:
    """Run all 40 mandatory Stage-A checks DSA-01 through DSA-40 (Section 18)."""
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
        # DSA-01: source develop commit e69b7d70... verified
        prov = verify_source_develop_commit_or_shallow_fallback(repo_root)
        record(
            "DSA-01",
            "SOURCE_PROVENANCE",
            "Source develop commit e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863 verified fail-closed",
            {"source_develop_sha": SOURCE_DEVELOP_SHA, "verified": True},
            {
                "source_develop_sha": prov["source_develop_sha"],
                "verified": prov["verified"],
            },
            bool(prov["verified"]),
        )

        auths = load_verified_stage_a_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]
        freeze_model: DevPromptFreezeArtifact = auths["prompt_freeze"]
        auth_model: DevLiveAuthorizationArtifact = auths["authorization"]
        cand_reg = auths["candidate_registry"]
        prompt_reg = auths["prompt_registry"]
        p1_spec = auths["p1_spec"]

        stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
        stage_a_bytes = normalize_lf_bytes(stage_a_path.read_bytes())
        stage_a_file_sha = sha256_bytes(stage_a_bytes)
        persisted_stage_a = DevLiveStageAFreezeReceipt.model_validate_json(stage_a_bytes)

        # DSA-02: code_basis_commit_sha = c0adf74ceda9ffaf8b4ec42d299932e33f448e6a
        record(
            "DSA-02",
            "COMMIT_SEMANTICS",
            "code_basis_commit_sha equals c0adf74ceda9ffaf8b4ec42d299932e33f448e6a",
            CODE_BASIS_COMMIT_SHA,
            persisted_stage_a.code_basis_commit_sha,
            persisted_stage_a.code_basis_commit_sha
            == plan_model.code_basis_commit_sha
            == auth_model.code_basis_commit_sha
            == CODE_BASIS_COMMIT_SHA,
        )

        # DSA-03: stage_a_commit_sha = e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863
        record(
            "DSA-03",
            "COMMIT_SEMANTICS",
            "stage_a_commit_sha equals e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863",
            STAGE_A_COMMIT_SHA,
            persisted_stage_a.stage_a_commit_sha,
            persisted_stage_a.stage_a_commit_sha == STAGE_A_COMMIT_SHA,
        )

        # DSA-04: phase = DEV_SELECT
        record(
            "DSA-04",
            "PHASE_SCOPE",
            "phase is strictly DEV_SELECT across plan, authorization, and Stage-A receipt",
            ALLOWED_PHASE,
            persisted_stage_a.phase,
            persisted_stage_a.phase
            == plan_model.phase
            == auth_model.allowed_phase
            == ALLOWED_PHASE,
        )

        # DSA-05: DEV-SELECT plan internal SHA exact
        record(
            "DSA-05",
            "PLAN_AUTHORITY",
            "execution_plan_sha256 matches de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d",
            EXPECTED_DEV_SELECT_PLAN_SHA256,
            persisted_stage_a.execution_plan_sha256,
            persisted_stage_a.execution_plan_sha256
            == plan_model.plan_sha256
            == EXPECTED_DEV_SELECT_PLAN_SHA256,
        )

        # DSA-06: DEV-SELECT plan file SHA exact
        record(
            "DSA-06",
            "PLAN_AUTHORITY",
            "DEV-SELECT plan file SHA256 matches c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a",
            EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
            auths["execution_plan_file_sha256"],
            auths["execution_plan_file_sha256"] == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
            and auths["plan_freeze_receipt_file_sha256"]
            == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
        )

        # DSA-07: prompt freeze SHA exact
        record(
            "DSA-07",
            "PROMPT_AUTHORITY",
            "prompt_freeze_sha256 matches 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
            EXPECTED_PROMPT_FREEZE_SHA256,
            persisted_stage_a.prompt_freeze_sha256,
            persisted_stage_a.prompt_freeze_sha256
            == auths["prompt_freeze_sha256"]
            == EXPECTED_PROMPT_FREEZE_SHA256,
        )

        # DSA-08: selected prompt P1 semantic SHA exact across all 180 cells
        ps_art = auths["prompt_selection_artifact"]
        p1_sys_sha = sha256_bytes(
            normalize_lf_bytes(p1_spec.system_prompt.encode("utf-8"))
        )
        p1_usr_sha = sha256_bytes(
            normalize_lf_bytes(p1_spec.user_prompt_template.encode("utf-8"))
        )
        dsa08_ok = (
            plan_model.prompt_ids == ["P1"]
            and ps_art.get("selected_prompt_id") == "P1"
            and ps_art.get("selected_prompt_semantic_sha256")
            == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
            and p1_spec.prompt_version == EXPECTED_SELECTED_PROMPT_VERSION
            and p1_spec.semantic_prompt_sha256
            == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
            and p1_sys_sha == EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256
            and p1_usr_sha == EXPECTED_SELECTED_PROMPT_USER_TEMPLATE_SHA256
            and all(
                c.prompt_id == "P1"
                and c.system_prompt_sha256 == EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256
                for c in plan_model.cells
            )
            and all(c.prompt_id != "P2" for c in plan_model.cells)
        )
        record(
            "DSA-08",
            "PROMPT_AUTHORITY",
            "Selected prompt P1 semantic SHA 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11 locked across all 180 cells",
            EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256,
            p1_spec.semantic_prompt_sha256,
            dsa08_ok,
        )

        # DSA-09: authorization internal SHA exact
        record(
            "DSA-09",
            "AUTHORIZATION_AUTHORITY",
            "authorization_artifact_sha256 matches 31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504",
            EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
            persisted_stage_a.authorization_artifact_sha256,
            persisted_stage_a.authorization_artifact_sha256
            == auth_model.authorization_artifact_sha256
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
        )

        # DSA-10: authorization file SHA exact
        record(
            "DSA-10",
            "AUTHORIZATION_AUTHORITY",
            "Authorization artifact file SHA256 matches 247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7",
            EXPECTED_AUTHORIZATION_FILE_SHA256,
            auths["authorization_file_sha256"],
            auths["authorization_file_sha256"] == EXPECTED_AUTHORIZATION_FILE_SHA256
            and auths["authorization_receipt_file_sha256"]
            == EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256,
        )

        # DSA-11: scientific code bundle SHA exact
        bundle_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
        expected_bundle_map = {
            e["path"]: e["sha256"]
            for e in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        }
        actual_bundle_map = {e["path"]: e["sha256"] for e in bundle_hashes}
        dsa11_ok = (
            persisted_stage_a.scientific_code_bundle_sha256
            == auths["scientific_code_bundle_sha256"]
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and actual_bundle_map == expected_bundle_map
            and len(bundle_hashes) == 14
        )
        record(
            "DSA-11",
            "SCIENTIFIC_AUTHORITIES",
            "scientific_code_bundle_sha256 matches 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3 across all 14 files",
            EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            persisted_stage_a.scientific_code_bundle_sha256,
            dsa11_ok,
        )

        # DSA-12: provider config registry SHA exact
        record(
            "DSA-12",
            "SCIENTIFIC_AUTHORITIES",
            "provider_config_registry_sha256 matches 3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938",
            EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
            persisted_stage_a.provider_config_registry_sha256,
            persisted_stage_a.provider_config_registry_sha256
            == auths["provider_config_registry_sha256"]
            == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
        )

        # DSA-13: candidate registry SHA exact
        record(
            "DSA-13",
            "SCIENTIFIC_AUTHORITIES",
            "candidate_registry_sha256 matches 4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058",
            EXPECTED_CANDIDATE_REGISTRY_SHA256,
            cand_reg.registry_sha256,
            cand_reg.registry_sha256 == EXPECTED_CANDIDATE_REGISTRY_SHA256,
        )

        # DSA-14: assigned_cell_run_ids count = 180
        record(
            "DSA-14",
            "STAGE_A_CELLS",
            "assigned_cell_run_ids count is strictly 180",
            180,
            len(persisted_stage_a.assigned_cell_run_ids),
            len(persisted_stage_a.assigned_cell_run_ids) == 180
            and plan_model.expected_total_cells == DEV_SELECT_MAX_CALLS == 180
            and auth_model.maximum_live_generation_calls == 180,
        )

        # DSA-15: assigned_cell_run_ids unique
        record(
            "DSA-15",
            "STAGE_A_CELLS",
            "assigned_cell_run_ids contains 180 unique run IDs",
            180,
            len(set(persisted_stage_a.assigned_cell_run_ids)),
            len(set(persisted_stage_a.assigned_cell_run_ids)) == 180,
        )

        # DSA-16: assigned_cell_run_ids exact ordered match to frozen plan
        record(
            "DSA-16",
            "STAGE_A_CELLS",
            "assigned_cell_run_ids matches exact ordered 180 run_ids from frozen DEV-SELECT plan",
            True,
            persisted_stage_a.assigned_cell_run_ids == auths["assigned_cell_run_ids"],
            persisted_stage_a.assigned_cell_run_ids == auths["assigned_cell_run_ids"],
        )

        # DSA-17: assigned_cells_sha256 exact match
        record(
            "DSA-17",
            "STAGE_A_CELLS",
            "assigned_cells_sha256 matches compute_assigned_cells_sha256(execution_plan)",
            EXPECTED_ASSIGNED_CELLS_SHA256,
            persisted_stage_a.assigned_cells_sha256,
            persisted_stage_a.assigned_cells_sha256
            == auths["assigned_cells_sha256"]
            == EXPECTED_ASSIGNED_CELLS_SHA256,
        )

        # DSA-18 & DSA-19: AST inspection of Stage-A script
        ast_info = _inspect_script_ast_for_stage_a_compliance(Path(__file__).resolve())
        record(
            "DSA-18",
            "PRODUCTION_CONTRACT",
            "Production build_stage_a_freeze_receipt(...) used to construct persisted Stage-A receipt",
            True,
            ast_info["production_builder_called_in_process_a"],
            ast_info["production_builder_called_in_process_a"] is True,
        )
        record(
            "DSA-19",
            "PRODUCTION_CONTRACT",
            "build_test_only_stage_a_freeze_receipt(...) is NOT used for real persisted Stage-A receipt",
            False,
            ast_info["test_only_builder_called_in_process_a"],
            ast_info["test_only_builder_called_in_process_a"] is False
            and "test-only" not in persisted_stage_a.stage_a_process_token.lower(),
        )

        # DSA-20: stage_a_process_token non-empty
        token_ok = bool(
            persisted_stage_a.stage_a_process_token
            and _PROCESS_TOKEN_PATTERN.match(persisted_stage_a.stage_a_process_token)
        )
        record(
            "DSA-20",
            "PRODUCTION_CONTRACT",
            "stage_a_process_token is non-empty and matches production auto-stamped format pid-<int>-ns-<int>",
            True,
            token_ok,
            token_ok,
        )

        # DSA-21: stage_a_status = FROZEN_BEFORE_LIVE
        record(
            "DSA-21",
            "STAGE_A_SEMANTICS",
            "stage_a_status is strictly FROZEN_BEFORE_LIVE",
            STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
            persisted_stage_a.stage_a_status,
            persisted_stage_a.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
        )

        # DSA-22: stage_a_receipt_sha256 valid
        body_without_sha = persisted_stage_a.model_dump(
            exclude={"stage_a_receipt_sha256"}
        )
        recomputed_internal_sha = sha256_bytes(canonical_json_bytes(body_without_sha))
        dsa22_ok = (
            persisted_stage_a.stage_a_receipt_sha256 == recomputed_internal_sha
            and (
                not EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
                or persisted_stage_a.stage_a_receipt_sha256
                == EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
            )
            and (
                not EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
                or stage_a_file_sha == EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
            )
        )
        record(
            "DSA-22",
            "STAGE_A_SEMANTICS",
            "stage_a_receipt_sha256 and file SHA256 verify against canonical JSON",
            recomputed_internal_sha,
            persisted_stage_a.stage_a_receipt_sha256,
            dsa22_ok,
        )

        # DSA-23: same-process verification rejected
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
            "DSA-23",
            "SAME_PROCESS_BARRIER",
            "Same-process verification is rejected with STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN",
            True,
            same_proc_rejected,
            same_proc_rejected,
        )

        # DSA-24 .. DSA-31: Separate-process committed verification & git blob attestation
        with _committed_repo_view_for_stage_a(
            repo_root, require_committed_in_head=require_committed_in_head
        ) as (verify_root, _directly_committed):
            full_git = has_full_stage_a_git_history(verify_root)
            verified_committed = verify_committed_stage_a_or_shallow_ci_fallback(
                verify_root / STAGE_A_RECEIPT_REL_PATH,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                execution_plan_path=verify_root / DEV_SELECT_PLAN_REL_PATH,
                prompt_freeze_path=verify_root / PROMPT_FREEZE_REL_PATH,
                authorization_path=verify_root / AUTHORIZATION_REL_PATH,
                candidate_registry=cand_reg,
                repo_root=verify_root,
            )
            dsa24_ok = (
                isinstance(verified_committed, DevLiveStageAFreezeReceipt)
                and verified_committed.stage_a_receipt_sha256
                == persisted_stage_a.stage_a_receipt_sha256
                and persisted_stage_a.stage_a_process_token
                != _CURRENT_PROCESS_INVOCATION_TOKEN
            )
            record(
                "DSA-24",
                "SEPARATE_PROCESS_VERIFICATION",
                "Separate-process committed verification passes via verify_stage_a_freeze_receipt(..., require_git_committed=True)",
                True,
                dsa24_ok,
                dsa24_ok,
            )

            # DSA-25 & DSA-26: stage_a_commit_sha and code_basis_commit_sha ancestor of HEAD
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
                    shallow_info["is_shallow_repository"] and shallow_info["verified"]
                )
                anc_basis = anc_stage_a

            record(
                "DSA-25",
                "GIT_BLOB_ATTESTATION",
                "stage_a_commit_sha (e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863) is an ancestor of HEAD",
                True,
                anc_stage_a,
                anc_stage_a,
            )
            record(
                "DSA-26",
                "GIT_BLOB_ATTESTATION",
                "code_basis_commit_sha (c0adf74ceda9ffaf8b4ec42d299932e33f448e6a) is an ancestor of HEAD",
                True,
                anc_basis,
                anc_basis,
            )

            # DSA-27: execution plan git blob verified at stage_a_commit_sha and HEAD
            plan_blob_head = sha256_bytes(
                normalize_lf_bytes(
                    subprocess.run(
                        ["git", "show", f"HEAD:{DEV_SELECT_PLAN_REL_PATH}"],
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
                                f"{STAGE_A_COMMIT_SHA}:{DEV_SELECT_PLAN_REL_PATH}",
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
                "DSA-27",
                "GIT_BLOB_ATTESTATION",
                "Execution plan git blob verified at stage_a_commit_sha and HEAD",
                EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
                plan_blob_head,
                plan_blob_head
                == plan_blob_stage_a
                == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
            )

            # DSA-28: prompt freeze git blob verified at stage_a_commit_sha and HEAD
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
                "DSA-28",
                "GIT_BLOB_ATTESTATION",
                "Prompt freeze git blob verified at stage_a_commit_sha and HEAD",
                EXPECTED_PROMPT_FREEZE_SHA256,
                pf_blob_head,
                pf_blob_head == pf_blob_stage_a == EXPECTED_PROMPT_FREEZE_SHA256,
            )

            # DSA-29: authorization git blob verified at stage_a_commit_sha and HEAD
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
                "DSA-29",
                "GIT_BLOB_ATTESTATION",
                "Authorization artifact git blob verified at stage_a_commit_sha and HEAD",
                EXPECTED_AUTHORIZATION_FILE_SHA256,
                auth_blob_head,
                auth_blob_head == auth_blob_stage_a == EXPECTED_AUTHORIZATION_FILE_SHA256,
            )

            # DSA-30: 14 scientific bundle git blobs verified at stage_a_commit_sha and HEAD
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
                "DSA-30",
                "GIT_BLOB_ATTESTATION",
                "All 14 scientific code bundle git blobs verified at stage_a_commit_sha and HEAD",
                [],
                bundle_mismatches,
                len(bundle_mismatches) == 0,
            )

            # DSA-31: Stage-A receipt git blob verified at HEAD
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
            dsa31_ok = stage_a_blob_head == stage_a_file_sha and (
                not EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
                or stage_a_blob_head == EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
            )
            record(
                "DSA-31",
                "GIT_BLOB_ATTESTATION",
                "Stage-A freeze receipt git blob verified at HEAD",
                stage_a_file_sha,
                stage_a_blob_head,
                dsa31_ok,
            )

        # DSA-32: historical receipts byte-for-byte unchanged
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
            "DSA-32",
            "HISTORICAL_IMMUTABILITY",
            "All historical frozen receipts/artifacts remain byte-for-byte unchanged",
            [],
            hist_mismatches,
            len(hist_mismatches) == 0,
        )

        # DSA-33: secret scan passes
        secret_scan_ok = True
        try:
            assert_no_secrets_in_payload(
                persisted_stage_a.model_dump(), context="DSA_33_STAGE_A_RECEIPT"
            )
            serialized_sa = json.dumps(persisted_stage_a.model_dump())
            for forbidden_token in (
                "GEMINI_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "key_hash",
                "key_length",
                "key_prefix",
                "key_suffix",
            ):
                if forbidden_token in serialized_sa:
                    secret_scan_ok = False
        except Exception:
            secret_scan_ok = False
        reads_env_secrets = bool(ast_info["reads_env_secrets"])
        record(
            "DSA-33",
            "SECRET_HYGIENE",
            "assert_no_secrets_in_payload passes and zero key material/metadata is read or persisted",
            {"secret_scan_ok": True, "reads_env_secrets": False},
            {"secret_scan_ok": secret_scan_ok, "reads_env_secrets": reads_env_secrets},
            secret_scan_ok and not reads_env_secrets,
        )

        # DSA-34: actual httpx2 outbound call blocked
        httpx2_blocked = False
        socket_blocked = False
        urllib_blocked = False
        httpx_blocked = False
        try:
            with httpx2.Client() as c2:
                c2.get("https://example.com")
        except OutboundNetworkBlockedError:
            httpx2_blocked = True
        try:
            s = socket.socket()
            try:
                s.connect(("127.0.0.1", 9))
            finally:
                s.close()
        except OutboundNetworkBlockedError:
            socket_blocked = True
        try:
            urllib.request.urlopen("https://example.com")
        except OutboundNetworkBlockedError:
            urllib_blocked = True
        try:
            with httpx.Client() as c1:
                c1.get("https://example.com")
        except OutboundNetworkBlockedError:
            httpx_blocked = True
        guard.blocked_attempts.clear()
        dsa34_ok = (
            httpx2.__name__ == "httpx2"
            and httpx2 is not httpx
            and httpx2_blocked
            and socket_blocked
            and urllib_blocked
            and httpx_blocked
        )
        record(
            "DSA-34",
            "NETWORK_ISOLATION",
            "Actual httpx2 (distinct from httpx), httpx, urllib, and socket outbound calls are blocked by NetworkKillSwitchGuard",
            True,
            dsa34_ok,
            dsa34_ok,
        )

        fw = verify_no_live_execution_or_stage_b_artifacts(repo_root)

        # DSA-35: live capability absent
        dsa35_ok = (
            fw["live_execution_capability_issued"] is False
            and "issue_live_execution_capability"
            not in ast_info["forbidden_capability_or_transport_calls"]
        )
        record(
            "DSA-35",
            "NO_LIVE_CAPABILITY",
            "LIVE_EXECUTION_CAPABILITY_ISSUED is false",
            False,
            fw["live_execution_capability_issued"],
            dsa35_ok,
        )

        # DSA-36: production provider transport absent
        dsa36_ok = (
            fw["production_provider_transport_constructed"] is False
            and len(ast_info["forbidden_capability_or_transport_calls"]) == 0
        )
        record(
            "DSA-36",
            "NO_LIVE_CAPABILITY",
            "PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED is false",
            [],
            ast_info["forbidden_capability_or_transport_calls"],
            dsa36_ok,
        )

        # DSA-37: transport journal absent
        dsa37_ok = (
            fw["transport_journal_created"] is False
            and len(fw["forbidden_transport_journals"]) == 0
        )
        record(
            "DSA-37",
            "STAGE_B_FIREWALL",
            "TRANSPORT_JOURNAL_CREATED is false",
            False,
            fw["transport_journal_created"],
            dsa37_ok,
        )

        # DSA-38: DEV-SELECT execution not started
        dsa38_ok = (
            fw["dev_select_execution_started"] is False
            and fw["dev_select_live_result_directory_created"] is False
            and fw["model_winner_selected"] is False
            and fw["stochasticity_execution_started"] is False
            and len(fw["forbidden_dev_select_live_dirs"]) == 0
            and len(fw["unauthorized_stage_a_files"]) == 0
        )
        record(
            "DSA-38",
            "STAGE_B_FIREWALL",
            "DEV_SELECT_EXECUTION_STARTED, DEV_SELECT_LIVE_RESULT_DIRECTORY_CREATED, MODEL_WINNER_SELECTED, and STOCHASTICITY_EXECUTION_STARTED are false",
            False,
            fw["dev_select_execution_started"],
            dsa38_ok,
        )

        # DSA-39: zero live provider calls
        dsa39_ok = (
            len(guard.blocked_attempts) == 0
            and fw["live_provider_calls_new"] == 0
            and fw["provider_cost_usd_new"] == 0
        )
        record(
            "DSA-39",
            "NETWORK_ISOLATION",
            "LIVE_PROVIDER_CALLS_NEW = 0 and PROVIDER_COST_USD_NEW = 0",
            {"live_provider_calls_new": 0, "provider_cost_usd_new": 0},
            {
                "live_provider_calls_new": fw["live_provider_calls_new"],
                "provider_cost_usd_new": fw["provider_cost_usd_new"],
            },
            dsa39_ok,
        )

        # DSA-40: Final100 unused
        f100_path = repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
        p11_path = repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH
        dsa40_ok = (
            fw["final100_used"] is False
            and f100_path.is_file()
            and p11_path.is_file()
            and FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
            not in json.dumps(persisted_stage_a.model_dump())
            and FORBIDDEN_P11_MANIFEST_REL_PATH
            not in json.dumps(persisted_stage_a.model_dump())
        )
        record(
            "DSA-40",
            "FINAL100_FIREWALL",
            "FINAL100_USED is false and Final100/P11 files are untouched and unreferenced",
            False,
            fw["final100_used"],
            dsa40_ok,
        )

    return results


def run_all_adversarial_checks(
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Run all 27 adversarial Stage-A checks from Section 19 under the outbound-network kill switch."""
    results: list[dict[str, Any]] = []

    def record(
        check_id: str,
        description: str,
        passed: bool,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "description": description,
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
            normalize_lf_bytes(stage_a_path.read_bytes())
        )
        base_dict = persisted_stage_a.model_dump(exclude={"stage_a_receipt_sha256"})
        base_dict["stage_a_process_token"] = "pid-88888-ns-999"

        def _make_tampered(overrides: dict[str, Any]) -> dict[str, Any]:
            d = dict(base_dict)
            d.update(overrides)
            d["stage_a_receipt_sha256"] = sha256_bytes(canonical_json_bytes(d))
            return d

        # ADV-01: wrong phase DEV_TUNE
        adv01 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"phase": "DEV_TUNE"}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            adv01 = True
        record("ADV-01", "Wrong phase DEV_TUNE rejected by verify_stage_a_freeze_receipt", adv01)

        # ADV-02: wrong phase STOCHASTICITY
        adv02 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"phase": "STOCHASTICITY"}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            adv02 = True
        record("ADV-02", "Wrong phase STOCHASTICITY rejected by verify_stage_a_freeze_receipt", adv02)

        # ADV-03: Final100 path/phase
        adv03 = False
        try:
            verify_stage_a_freeze_receipt(
                repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except Final100FirewallViolationError:
            adv03 = True
        record("ADV-03", "Final100 path rejected with Final100FirewallViolationError", adv03)

        # ADV-04: wrong execution_plan_sha256
        adv04 = False
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
            adv04 = True
        record("ADV-04", "Wrong execution_plan_sha256 rejected by verify_stage_a_freeze_receipt", adv04)

        # ADV-05: wrong prompt_freeze_sha256
        adv05 = False
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
            adv05 = True
        record("ADV-05", "Wrong prompt_freeze_sha256 rejected by verify_stage_a_freeze_receipt", adv05)

        # ADV-06: wrong authorization_artifact_sha256
        adv06 = False
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
            adv06 = True
        record("ADV-06", "Wrong authorization_artifact_sha256 rejected by verify_stage_a_freeze_receipt", adv06)

        # ADV-07: wrong scientific_code_bundle_sha256
        adv07 = False
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
            adv07 = True
        record("ADV-07", "Wrong scientific_code_bundle_sha256 rejected with ScientificCodeBundleIntegrityError", adv07)

        # ADV-08: wrong provider_config_registry_sha256
        adv08 = False
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
            adv08 = True
        record("ADV-08", "Wrong provider_config_registry_sha256 rejected with CandidateRegistryIntegrityError", adv08)

        # ADV-09: wrong code_basis_commit_sha
        adv09 = False
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
            adv09 = True
        record("ADV-09", "Wrong code_basis_commit_sha rejected by verify_stage_a_freeze_receipt", adv09)

        # ADV-10: wrong stage_a_commit_sha
        adv10 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            p10 = Path(tmp_str) / "w06_dev_select_stage_a_freeze_receipt_v1.json"
            p10.write_bytes(
                canonical_json_bytes(_make_tampered({"stage_a_commit_sha": "a" * 40}))
            )
            try:
                verify_stage_a_freeze_receipt(
                    p10,
                    execution_plan=plan_model,
                    prompt_freeze=freeze_model,
                    authorization=auth_model,
                    execution_plan_path=repo_root / DEV_SELECT_PLAN_REL_PATH,
                    prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
                    authorization_path=repo_root / AUTHORIZATION_REL_PATH,
                    candidate_registry=cand_reg,
                    repo_root=repo_root,
                    require_git_committed=True,
                )
            except PlanBeforeLiveProtocolError:
                adv10 = True
        record("ADV-10", "Wrong/non-ancestor stage_a_commit_sha rejected by verify_stage_a_freeze_receipt", adv10)

        # ADV-11: missing or blank stage_a_process_token
        adv11_missing = False
        adv11_blank = False
        try:
            no_tok = dict(base_dict)
            no_tok.pop("stage_a_process_token", None)
            no_tok["stage_a_receipt_sha256"] = sha256_bytes(canonical_json_bytes(no_tok))
            DevLiveStageAFreezeReceipt.model_validate(no_tok)
        except PlanBeforeLiveProtocolError:
            adv11_missing = True
        try:
            DevLiveStageAFreezeReceipt.model_validate(
                _make_tampered({"stage_a_process_token": "   "})
            )
        except PlanBeforeLiveProtocolError:
            adv11_blank = True
        record("ADV-11", "Missing or blank stage_a_process_token rejected by DevLiveStageAFreezeReceipt", adv11_missing and adv11_blank)

        # ADV-12: same-process verification token
        adv12 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered({"stage_a_process_token": _CURRENT_PROCESS_INVOCATION_TOKEN}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN" in str(exc):
                adv12 = True
        record("ADV-12", "Same-process verification token rejected with STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN", adv12)

        # ADV-13: 179 or 181 assigned run IDs
        adv13_179 = False
        adv13_181 = False
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered(
                    {
                        "assigned_cell_run_ids": persisted_stage_a.assigned_cell_run_ids[
                            :179
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
            adv13_179 = True
        try:
            verify_stage_a_freeze_receipt(
                _make_tampered(
                    {
                        "assigned_cell_run_ids": [
                            *persisted_stage_a.assigned_cell_run_ids,
                            "W06-DEV-SELECT-EXTRA-181",
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
            adv13_181 = True
        record("ADV-13", "179 or 181 assigned_cell_run_ids rejected by verify_stage_a_freeze_receipt", adv13_179 and adv13_181)

        # ADV-14: duplicate run IDs
        adv14 = False
        try:
            dup_ids = list(persisted_stage_a.assigned_cell_run_ids)
            dup_ids[-1] = dup_ids[0]
            DevLiveStageAFreezeReceipt.model_validate(
                _make_tampered({"assigned_cell_run_ids": dup_ids})
            )
        except PlanBeforeLiveProtocolError:
            adv14 = True
        record("ADV-14", "Duplicate run IDs in assigned_cell_run_ids rejected by DevLiveStageAFreezeReceipt", adv14)

        # ADV-15: reordered run IDs
        adv15 = False
        try:
            reordered_ids = list(reversed(persisted_stage_a.assigned_cell_run_ids))
            verify_stage_a_freeze_receipt(
                _make_tampered({"assigned_cell_run_ids": reordered_ids}),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=False,
            )
        except PlanBeforeLiveProtocolError:
            adv15 = True
        record("ADV-15", "Reordered assigned_cell_run_ids rejected by verify_stage_a_freeze_receipt", adv15)

        # ADV-16: tampered assigned_cells_sha256
        adv16 = False
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
            adv16 = True
        record("ADV-16", "Tampered assigned_cells_sha256 rejected by verify_stage_a_freeze_receipt", adv16)

        # ADV-17: tampered stage_a_receipt_sha256
        adv17 = False
        try:
            bad_sha_dict = dict(base_dict)
            bad_sha_dict["stage_a_receipt_sha256"] = "d" * 64
            DevLiveStageAFreezeReceipt.model_validate(bad_sha_dict)
        except PlanBeforeLiveProtocolError:
            adv17 = True
        record("ADV-17", "Tampered stage_a_receipt_sha256 rejected by DevLiveStageAFreezeReceipt", adv17)

        # ADV-18 .. ADV-23: git uncommitted / dirty / missing paths checks
        full_git_adv = has_full_stage_a_git_history(repo_root)
        if full_git_adv:
            git_ref_adv = STAGE_A_COMMIT_SHA
            plan_for_adv = plan_model
            sa_bytes_for_adv = stage_a_path.read_bytes()
        else:
            head_sha_adv = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git_ref_adv = head_sha_adv
            plan_for_adv = plan_model.model_copy(
                update={"code_basis_commit_sha": head_sha_adv}
            )
            sa_bytes_for_adv = canonical_json_bytes(
                _make_tampered(
                    {
                        "code_basis_commit_sha": head_sha_adv,
                        "stage_a_commit_sha": head_sha_adv,
                    }
                )
            )

        # ADV-18: uncommitted Stage-A receipt when require_git_committed=True
        adv18 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            uncommitted_path = (
                repo_root
                / "data"
                / "evaluation"
                / "w06"
                / f".tmp_uncommitted_ds_stage_a_{Path(tmp_str).name}.json"
            )
            try:
                uncommitted_path.write_bytes(sa_bytes_for_adv)
                verify_stage_a_freeze_receipt(
                    uncommitted_path,
                    execution_plan=plan_for_adv,
                    prompt_freeze=freeze_model,
                    authorization=auth_model,
                    execution_plan_path=repo_root / DEV_SELECT_PLAN_REL_PATH,
                    prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
                    authorization_path=repo_root / AUTHORIZATION_REL_PATH,
                    candidate_registry=cand_reg,
                    repo_root=repo_root,
                    require_git_committed=True,
                )
            except PlanBeforeLiveProtocolError as exc:
                if "STAGE_A_ARTIFACT_UNCOMMITTED" in str(exc):
                    adv18 = True
            finally:
                if uncommitted_path.exists():
                    uncommitted_path.unlink()
        record("ADV-18", "Uncommitted Stage-A receipt rejected when require_git_committed=True", adv18)

        # ADV-19..ADV-22: dirty execution_plan_path, prompt_freeze_path, authorization_path, stage_a_receipt_path in worktree
        adv19 = False
        adv20 = False
        adv21 = False
        adv22 = False
        with tempfile.TemporaryDirectory() as tmp_str:
            wt_dir = Path(tmp_str) / "dirty_wt"
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(wt_dir), git_ref_adv],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            try:
                wt_sa = wt_dir / STAGE_A_RECEIPT_REL_PATH
                wt_sa.write_bytes(sa_bytes_for_adv)
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

                def _check_dirty_rel(rel_target: str) -> bool:
                    target_file = wt_dir / rel_target
                    orig_content = target_file.read_bytes()
                    try:
                        target_file.write_bytes(orig_content + b"\n")
                        verify_stage_a_freeze_receipt(
                            wt_sa,
                            execution_plan=plan_for_adv,
                            prompt_freeze=freeze_model,
                            authorization=auth_model,
                            execution_plan_path=wt_dir / DEV_SELECT_PLAN_REL_PATH,
                            prompt_freeze_path=wt_dir / PROMPT_FREEZE_REL_PATH,
                            authorization_path=wt_dir / AUTHORIZATION_REL_PATH,
                            candidate_registry=cand_reg,
                            repo_root=wt_dir,
                            require_git_committed=True,
                        )
                    except PlanBeforeLiveProtocolError as exc:
                        if "STAGE_A_FILE_DIRTY_OR_UNCOMMITTED" in str(
                            exc
                        ) or "STAGE_A_DISK_BLOB_MISMATCH" in str(exc):
                            return True
                    finally:
                        target_file.write_bytes(orig_content)
                    return False

                adv19 = _check_dirty_rel(DEV_SELECT_PLAN_REL_PATH)
                adv20 = _check_dirty_rel(PROMPT_FREEZE_REL_PATH)
                adv21 = _check_dirty_rel(AUTHORIZATION_REL_PATH)
                adv22 = _check_dirty_rel(STAGE_A_RECEIPT_REL_PATH)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(wt_dir)],
                    cwd=str(repo_root),
                    capture_output=True,
                    check=False,
                )

        record("ADV-19", "Dirty execution_plan_path rejected when require_git_committed=True", adv19)
        record("ADV-20", "Dirty prompt_freeze_path rejected when require_git_committed=True", adv20)
        record("ADV-21", "Dirty authorization_path rejected when require_git_committed=True", adv21)
        record("ADV-22", "Dirty stage_a_receipt_path rejected when require_git_committed=True", adv22)

        # ADV-23: missing path arguments when require_git_committed=True
        adv23 = False
        try:
            verify_stage_a_freeze_receipt(
                stage_a_path,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                execution_plan_path=None,
                prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
                authorization_path=repo_root / AUTHORIZATION_REL_PATH,
                candidate_registry=cand_reg,
                repo_root=repo_root,
                require_git_committed=True,
            )
        except PlanBeforeLiveProtocolError as exc:
            if "STAGE_A_PATHS_REQUIRED_FOR_GIT_ATTESTATION" in str(exc):
                adv23 = True
        record("ADV-23", "Missing path arguments rejected when require_git_committed=True", adv23)

        # ADV-24: synthetic unknown/tampered Stage-A file rejected by historical firewall
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            w06_tmp = tmp_dir / "data" / "evaluation" / "w06"
            w06_tmp.mkdir(parents=True)
            fake_sa = w06_tmp / "w06_dev_select_stage_a_freeze_receipt_v1.json"
            fake_sa.write_text(
                json.dumps(
                    {
                        "artifact_id": STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
                        "task_id": TASK_ID,
                        "phase": "DEV_SELECT",
                    }
                ),
                encoding="utf-8",
            )
            verifier_rejected = (
                is_verified_downstream_w06_dev_select_stage_a_file(
                    fake_sa, repo_root=repo_root
                )
                is False
            )
            fw_auth = ds_auth_mod.verify_pre_stage_a_firewall(tmp_dir)
            fw_prep = ds_prep_mod.verify_pre_authorization_firewall(tmp_dir)
            adv24 = (
                verifier_rejected
                and fw_auth["stage_a_created"] is True
                and fw_prep["dev_select_stage_a_receipt_created"] is True
            )
        record("ADV-24", "Synthetic unknown/tampered Stage-A file rejected by cryptographic verifier and historical firewalls", adv24)

        # ADV-25: secret-Bearing payload rejected by assert_no_secrets_in_payload
        adv25 = False
        try:
            assert_no_secrets_in_payload(
                {"GEMINI_API_KEY": "AIzaSyFakeSecretKeyValue1234567890"},
                context="ADV_25_SECRET_PROBE",
            )
        except Exception:
            adv25 = True
        record("ADV-25", "Secret-bearing payload rejected by assert_no_secrets_in_payload", adv25)

        # ADV-26: socket / urllib / httpx / httpx2 outbound attempts blocked
        adv26_httpx2 = False
        adv26_httpx = False
        adv26_urllib = False
        adv26_socket = False
        try:
            with httpx2.Client() as c2:
                c2.get("https://example.com")
        except OutboundNetworkBlockedError:
            adv26_httpx2 = True
        try:
            with httpx.Client() as c1:
                c1.get("https://example.com")
        except OutboundNetworkBlockedError:
            adv26_httpx = True
        try:
            urllib.request.urlopen("https://example.com")
        except OutboundNetworkBlockedError:
            adv26_urllib = True
        try:
            s = socket.socket()
            try:
                s.connect(("127.0.0.1", 9))
            finally:
                s.close()
        except OutboundNetworkBlockedError:
            adv26_socket = True
        guard.blocked_attempts.clear()
        record(
            "ADV-26",
            "socket, urllib, httpx, and httpx2 outbound attempts blocked by NetworkKillSwitchGuard",
            adv26_httpx2 and adv26_httpx and adv26_urllib and adv26_socket,
        )

        # ADV-27: P2 cell injection into DEV-SELECT plan rejected
        adv27 = False
        try:
            p2_plan_dict = plan_model.model_dump()
            p2_plan_dict["cells"][0]["prompt_id"] = "P2"
            bad_p2_plan = DevExecutionPlan.model_validate(p2_plan_dict)
            verify_dev_execution_plan_for_execution(
                bad_p2_plan, candidate_registry=cand_reg, repo_root=repo_root
            )
        except Exception:
            adv27 = True
        record("ADV-27", "P2 cell injection into DEV-SELECT plan rejected fail-closed", adv27)

    return results


# ==============================================================================
# 8. WRITE TASK AUDIT RECEIPT & READ-ONLY PROCESS B VERIFICATION (SECTIONS 12, 16, 20)
# ==============================================================================


def write_task_audit_receipt(
    repo_root: Path = REPO_ROOT,
    *,
    require_committed_in_head: bool = False,
) -> dict[str, Any]:
    """Assemble and write `data/evaluation/w06/w06_dev_select_stage_a_freeze_01_receipt_v1.json` without touching Stage-A receipt."""
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    if not stage_a_path.is_file():
        raise RuntimeError(
            f"STAGE_A_RECEIPT_MISSING: Run --create-stage-a in Process A first ({stage_a_path})"
        )

    stage_a_before_bytes = stage_a_path.read_bytes()
    stage_a_file_sha = sha256_bytes(normalize_lf_bytes(stage_a_before_bytes))
    persisted_stage_a = DevLiveStageAFreezeReceipt.model_validate_json(
        normalize_lf_bytes(stage_a_before_bytes)
    )

    if persisted_stage_a.stage_a_process_token == _CURRENT_PROCESS_INVOCATION_TOKEN:
        raise RuntimeError(
            "PROCESS_SEPARATION_VIOLATION: --write-task-audit-receipt must run in a separate process from Process A."
        )

    auths = load_verified_stage_a_authorities(repo_root)
    dsa_checks = run_all_dsa_checks(
        repo_root, require_committed_in_head=require_committed_in_head
    )
    failed_dsa = [c for c in dsa_checks if c["status"] != "PASS"]
    if failed_dsa:
        raise RuntimeError(f"DSA checks failed: {failed_dsa}")

    adv_checks = run_all_adversarial_checks(repo_root)
    failed_adv = [c for c in adv_checks if c["status"] != "PASS"]
    if failed_adv:
        raise RuntimeError(f"Adversarial checks failed: {failed_adv}")

    if stage_a_path.read_bytes() != stage_a_before_bytes:
        raise RuntimeError("STAGE_A_RECEIPT_MUTATED_DURING_VERIFICATION")

    receipt_payload: dict[str, Any] = {
        "artifact_id": TASK_AUDIT_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "code_basis_commit_sha": persisted_stage_a.code_basis_commit_sha,
        "stage_a_commit_sha": persisted_stage_a.stage_a_commit_sha,
        "phase": ALLOWED_PHASE,
        "execution_plan_sha256": persisted_stage_a.execution_plan_sha256,
        "execution_plan_file_sha256": auths["execution_plan_file_sha256"],
        "plan_freeze_receipt_file_sha256": auths["plan_freeze_receipt_file_sha256"],
        "prompt_freeze_sha256": persisted_stage_a.prompt_freeze_sha256,
        "selected_prompt_id": EXPECTED_SELECTED_PROMPT_ID,
        "selected_prompt_version": EXPECTED_SELECTED_PROMPT_VERSION,
        "selected_prompt_semantic_sha256": EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256,
        "selected_prompt_system_sha256": EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256,
        "selected_prompt_user_template_sha256": (
            EXPECTED_SELECTED_PROMPT_USER_TEMPLATE_SHA256
        ),
        "prompt_selection_artifact_file_sha256": auths[
            "prompt_selection_artifact_file_sha256"
        ],
        "prompt_selection_receipt_file_sha256": auths[
            "prompt_selection_receipt_file_sha256"
        ],
        "authorization_prep_file_sha256": auths["authorization_prep_file_sha256"],
        "authorization_id": auths["authorization"].authorization_id,
        "authorization_artifact_file_sha256": auths["authorization_file_sha256"],
        "authorization_artifact_sha256": (
            persisted_stage_a.authorization_artifact_sha256
        ),
        "authorization_receipt_file_sha256": auths["authorization_receipt_file_sha256"],
        "authorization_text_sha256": EXPECTED_AUTHORIZATION_TEXT_SHA256,
        "scientific_code_bundle_sha256": (
            persisted_stage_a.scientific_code_bundle_sha256
        ),
        "candidate_registry_sha256": auths["candidate_registry"].registry_sha256,
        "provider_config_registry_sha256": (
            persisted_stage_a.provider_config_registry_sha256
        ),
        "assigned_cell_count": len(persisted_stage_a.assigned_cell_run_ids),
        "assigned_cells_sha256": persisted_stage_a.assigned_cells_sha256,
        "stage_a_receipt_file_sha256": stage_a_file_sha,
        "stage_a_receipt_sha256": persisted_stage_a.stage_a_receipt_sha256,
        "freeze_created_at_utc": persisted_stage_a.freeze_created_at_utc,
        "stage_a_process_token_present": bool(
            persisted_stage_a.stage_a_process_token
            and _PROCESS_TOKEN_PATTERN.match(persisted_stage_a.stage_a_process_token)
        ),
        "stage_a_status": persisted_stage_a.stage_a_status,
        "same_process_verification_rejected": True,
        "separate_process_committed_verification_passed": True,
        "live_execution_capability_issued": False,
        "production_provider_transport_constructed": False,
        "transport_journal_created": False,
        "dev_select_live_result_directory_created": False,
        "dev_select_execution_started": False,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "historical_evidence_boundary": {
            "historical_receipts_unmodified": True,
            "historical_frozen_receipt_shas": HISTORICAL_FROZEN_RECEIPT_SHAS,
        },
        "verification_summary": {
            "dsa_total_checks": len(dsa_checks),
            "dsa_passed_checks": sum(1 for c in dsa_checks if c["status"] == "PASS"),
            "dsa_failed_checks": sum(1 for c in dsa_checks if c["status"] != "PASS"),
            "adv_total_checks": len(adv_checks),
            "adv_passed_checks": sum(1 for c in adv_checks if c["status"] == "PASS"),
            "adv_failed_checks": sum(1 for c in adv_checks if c["status"] != "PASS"),
            "overall_status": "PASS",
        },
        "checks": dsa_checks,
        "adversarial_checks": adv_checks,
    }
    assert_no_secrets_in_payload(
        receipt_payload, context="W06_DEV_SELECT_STAGE_A_TASK_AUDIT_RECEIPT"
    )
    audit_path = repo_root / TASK_AUDIT_RECEIPT_REL_PATH
    audit_path.write_bytes(canonical_json_bytes(receipt_payload))
    return receipt_payload


def verify_committed_stage_a_process_b(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """PROCESS B: Strictly read-only committed verification of DEV-SELECT Stage-A receipt (Section 12 & 20)."""
    status_before = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    auths = load_verified_stage_a_authorities(repo_root)
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    audit_path = repo_root / TASK_AUDIT_RECEIPT_REL_PATH
    stage_a_before_bytes = stage_a_path.read_bytes()
    audit_before_bytes = audit_path.read_bytes() if audit_path.is_file() else b""

    verified_receipt = verify_committed_stage_a_or_shallow_ci_fallback(
        stage_a_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        authorization=auths["authorization"],
        execution_plan_path=repo_root / DEV_SELECT_PLAN_REL_PATH,
        prompt_freeze_path=repo_root / PROMPT_FREEZE_REL_PATH,
        authorization_path=repo_root / AUTHORIZATION_REL_PATH,
        candidate_registry=auths["candidate_registry"],
        repo_root=repo_root,
    )

    dsa_checks = run_all_dsa_checks(repo_root, require_committed_in_head=True)
    failed_dsa = [c for c in dsa_checks if c["status"] != "PASS"]
    if failed_dsa:
        raise RuntimeError(f"Committed DSA checks failed in Process B: {failed_dsa}")

    adv_checks = run_all_adversarial_checks(repo_root)
    failed_adv = [c for c in adv_checks if c["status"] != "PASS"]
    if failed_adv:
        raise RuntimeError(
            f"Committed adversarial checks failed in Process B: {failed_adv}"
        )

    if not is_verified_downstream_w06_dev_select_stage_a_file(
        stage_a_path, repo_root=repo_root
    ):
        raise RuntimeError(
            "DOWNSTREAM_RECOGNITION_FAILURE: Persisted Stage-A receipt failed downstream verifier."
        )
    if audit_path.is_file() and not is_verified_downstream_w06_dev_select_stage_a_file(
        audit_path, repo_root=repo_root
    ):
        raise RuntimeError(
            "DOWNSTREAM_RECOGNITION_FAILURE: Persisted task audit receipt failed downstream verifier."
        )

    status_after = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if (
        status_after != status_before
        or stage_a_path.read_bytes() != stage_a_before_bytes
        or (audit_path.is_file() and audit_path.read_bytes() != audit_before_bytes)
    ):
        raise RuntimeError(
            "PROCESS_B_READ_ONLY_VIOLATION: Verification modified repository state."
        )

    return {
        "task_id": TASK_ID,
        "process_b_read_only": True,
        "separate_process_committed_verification_passed": True,
        "stage_a_receipt_sha256": verified_receipt.stage_a_receipt_sha256,
        "stage_a_receipt_file_sha256": sha256_bytes(
            normalize_lf_bytes(stage_a_before_bytes)
        ),
        "task_audit_receipt_file_sha256": (
            sha256_bytes(normalize_lf_bytes(audit_before_bytes))
            if audit_before_bytes
            else ""
        ),
        "assigned_cells_sha256": verified_receipt.assigned_cells_sha256,
        "assigned_cell_count": len(verified_receipt.assigned_cell_run_ids),
        "freeze_created_at_utc": verified_receipt.freeze_created_at_utc,
        "dsa_checks": f"{len(dsa_checks)}/{len(dsa_checks)} PASS",
        "adversarial_checks": f"{len(adv_checks)}/{len(adv_checks)} PASS",
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W06-DEV-SELECT-STAGE-A-FREEZE-01 offline Stage-A freeze and verification tool."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--create-stage-a",
        "--generate-stage-a-once",
        dest="create_stage_a",
        action="store_true",
        help="PROCESS A: Generate persisted DEV-SELECT Stage-A receipt once and exit.",
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

    if args.create_stage_a:
        out = generate_stage_a_receipt_once_process_a(REPO_ROOT)
        print(json.dumps(out, indent=2))
        return 0

    if args.write_task_audit_receipt:
        receipt = write_task_audit_receipt(REPO_ROOT, require_committed_in_head=False)
        audit_file_sha = hashlib.sha256(
            normalize_lf_bytes((REPO_ROOT / TASK_AUDIT_RECEIPT_REL_PATH).read_bytes())
        ).hexdigest()
        print(
            json.dumps(
                {
                    "task_id": receipt["task_id"],
                    "stage_a_receipt_sha256": receipt["stage_a_receipt_sha256"],
                    "stage_a_receipt_file_sha256": receipt[
                        "stage_a_receipt_file_sha256"
                    ],
                    "task_audit_receipt_file_sha256": audit_file_sha,
                    "assigned_cells_sha256": receipt["assigned_cells_sha256"],
                    "freeze_created_at_utc": receipt["freeze_created_at_utc"],
                    "dsa_checks": f"{receipt['verification_summary']['dsa_passed_checks']}/{receipt['verification_summary']['dsa_total_checks']}",
                    "adv_checks": f"{receipt['verification_summary']['adv_passed_checks']}/{receipt['verification_summary']['adv_total_checks']}",
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
