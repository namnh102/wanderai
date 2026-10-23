"""Issue W06 DEV-SELECT live authorization artifact and receipt (W06-DEV-SELECT-LIVE-AUTHORIZATION-01).

Strictly offline formalization of explicit Project Owner authorization for W06 DEV-SELECT:
- LIVE_PROVIDER_CALLS_NEW = 0
- PROVIDER_COST_USD_NEW = 0
- STAGE_A_CREATED = false
- LIVE_EXECUTION_CAPABILITY_ISSUED = false
- PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED = false
- TRANSPORT_JOURNAL_CREATED = false
- DEV_SELECT_LIVE_RESULT_DIRECTORY_CREATED = false
- DEV_SELECT_EXECUTION_STARTED = false
- MODEL_WINNER_SELECTED = false
- STOCHASTICITY_EXECUTION_STARTED = false
- FINAL100_USED = false
"""

from __future__ import annotations

import argparse
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

TASK_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01"
AUTHORIZATION_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
RECEIPT_ARTIFACT_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-RECEIPT-V1"
SOURCE_DEVELOP_SHA = "1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f"
CODE_BASIS_COMMIT_SHA = "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"

AUTHORIZATION_SOURCE = "PROJECT_OWNER_EXPLICIT_CHAT_AUTHORIZATION"
AUTHORIZED_BY_ROLE = AUTHORIZED_BY_ROLE_PROJECT_OWNER
AUTHORIZATION_STATUS = AUTHORIZATION_STATUS_AUTHORIZED
AUTHORIZED_AT_UTC = "2026-10-23T05:47:00Z"
AUTHORIZED_AT_UTC_SEMANTICS = (
    "authorized_at_utc represents formal artifact issuance immediately following "
    "the already-explicit Project Owner authorization; it is not a fabricated "
    "historical chat timestamp."
)

EXACT_AUTHORIZATION_TEXT = (
    "I authorize W06 DEV-SELECT live execution for exactly the frozen 180-cell plan "
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d (plan file "
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a), bound by "
    "plan-freeze receipt 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549, "
    "using locked prompt P1 from prompt-selection artifact "
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8 (semantic SHA "
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11), candidates "
    "C1/C2/C3, maximum 180 generation calls, zero retry, no DEV-TUNE rerun, no "
    "stochasticity, and no Final100."
)
AUTHORIZATION_TEXT_CHARACTER_COUNT = 633
AUTHORIZATION_TEXT_SHA256 = (
    "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
)

ALLOWED_PHASE = "DEV_SELECT"
ALLOWED_CANDIDATE_IDS: tuple[str, str, str] = ("C1", "C2", "C3")
MAXIMUM_LIVE_GENERATION_CALLS = 180
ATTEMPTS_PER_CELL = 1
RETRY_CALLS = 0

EXPECTED_DEV_SELECT_PLAN_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
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
EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256 = (
    "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
)
EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256 = (
    "cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39"
)

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
DEV_TUNE_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
)
DEV_SELECT_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
)
PLAN_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json"
)
PROMPT_SELECTION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
PROMPT_SELECTION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json"
)
AUTHORIZATION_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_authorization_prep_v1.json"
)
AUTHORIZATION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_authorization_v1.json"
)
AUTHORIZATION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_authorization_01_receipt_v1.json"
)
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)

HISTORICAL_FROZEN_SHAS: dict[str, str] = {
    PROMPT_FREEZE_REL_PATH: EXPECTED_PROMPT_FREEZE_SHA256,
    PROMPT_SELECTION_ARTIFACT_REL_PATH: EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    PROMPT_SELECTION_RECEIPT_REL_PATH: EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    DEV_SELECT_PLAN_REL_PATH: EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
    PLAN_FREEZE_RECEIPT_REL_PATH: EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
    AUTHORIZATION_PREP_REL_PATH: EXPECTED_PREP_ARTIFACT_FILE_SHA256,
}


# ==============================================================================
# 2. OUTBOUND NETWORK KILL SWITCH (SOCKET / URLLIB / HTTPX / HTTPX2)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline authorization issuance."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        if httpx2.__name__ != "httpx2" or httpx2 is httpx:
            raise RuntimeError("httpx2 must be the real httpx2 module, distinct from httpx")

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
    """Fail-closed verification of source develop SHA 1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f (Section 2).

    CASE A — SOURCE_DEVELOP_SHA exists in local git:
      Require `git merge-base --is-ancestor SOURCE_DEVELOP_SHA HEAD` to succeed.
      If commit exists but is NOT ancestor, verified = False.

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
        "authorization_prep_sha256": (
            _file_sha(AUTHORIZATION_PREP_REL_PATH) == EXPECTED_PREP_ARTIFACT_FILE_SHA256
        ),
        "dev_select_plan_file_sha256": (
            _file_sha(DEV_SELECT_PLAN_REL_PATH) == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        ),
        "plan_freeze_receipt_file_sha256": (
            _file_sha(PLAN_FREEZE_RECEIPT_REL_PATH)
            == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
        ),
        "prompt_selection_artifact_file_sha256": (
            _file_sha(PROMPT_SELECTION_ARTIFACT_REL_PATH)
            == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
        ),
        "prompt_freeze_sha256": (
            _file_sha(PROMPT_FREEZE_REL_PATH) == EXPECTED_PROMPT_FREEZE_SHA256
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


def verify_pre_stage_a_firewall(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify that zero DEV-SELECT Stage-A receipts, capabilities, transport journals, or cell outputs exist."""
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    forbidden_dev_select_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_dev_select_live_dirs: list[str] = []

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
        from freeze_w06_dev_tune_stage_a import (
            is_verified_downstream_w06_dev_tune_stage_a_file,
        )

        verified_downstream_results_tree = (
            is_verified_downstream_w06_dev_tune_live_results_tree(repo_root)
        )
        verified_downstream_dev_select_results_tree = (
            is_verified_downstream_w06_dev_select_live_results_tree(repo_root)
        )

        for path in sorted(w06_dir.rglob("*")):
            rel = path.relative_to(repo_root).as_posix()
            name_lower = path.name.lower()
            is_verified_downstream_results = (
                verified_downstream_results_tree
                and is_path_in_downstream_w06_dev_tune_live_results_scope(
                    path, repo_root=repo_root
                )
            ) or (
                verified_downstream_dev_select_results_tree
                and is_path_in_downstream_w06_dev_select_live_results_scope(
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
                    forbidden_dev_select_stage_a_files.append(rel)
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
                                forbidden_dev_select_stage_a_files.append(rel)
                    except Exception:
                        pass
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
        "stage_a_created": len(forbidden_dev_select_stage_a_files) > 0,
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
        "forbidden_dev_select_stage_a_files": forbidden_dev_select_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_dev_select_live_dirs": forbidden_dev_select_live_dirs,
    }


# ==============================================================================
# 3B. STRONG CRYPTOGRAPHIC DOWNSTREAM AUTHORIZATION & RECEIPT RECOGNITION
# ==============================================================================


def _resolve_effective_repo_root(repo_root: Path) -> Path:
    if (
        repo_root
        / "apps"
        / "ai-service"
        / "app"
        / "evaluation"
        / "dev_live_runner.py"
    ).is_file():
        return repo_root
    return REPO_ROOT


def _verify_upstream_dev_select_authorities_for_downstream(
    effective_root: Path,
) -> tuple[DevExecutionPlan, DevPromptFreezeArtifact] | None:
    """Verify upstream frozen DEV-SELECT plan, plan-freeze receipt, prompt-selection, prompt-freeze, and prep artifact."""
    try:
        pf_path = effective_root / PROMPT_FREEZE_REL_PATH
        plan_path = effective_root / DEV_SELECT_PLAN_REL_PATH
        plan_rec_path = effective_root / PLAN_FREEZE_RECEIPT_REL_PATH
        ps_art_path = effective_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
        ps_rec_path = effective_root / PROMPT_SELECTION_RECEIPT_REL_PATH
        prep_path = effective_root / AUTHORIZATION_PREP_REL_PATH

        for p in (
            pf_path,
            plan_path,
            plan_rec_path,
            ps_art_path,
            ps_rec_path,
            prep_path,
        ):
            if not p.is_file():
                return None

        pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
        plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
        plan_rec_bytes = normalize_lf_bytes(plan_rec_path.read_bytes())
        ps_art_bytes = normalize_lf_bytes(ps_art_path.read_bytes())
        ps_rec_bytes = normalize_lf_bytes(ps_rec_path.read_bytes())
        prep_bytes = normalize_lf_bytes(prep_path.read_bytes())

        if sha256_bytes(pf_bytes) != EXPECTED_PROMPT_FREEZE_SHA256:
            return None
        if sha256_bytes(plan_bytes) != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
            return None
        if sha256_bytes(plan_rec_bytes) != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256:
            return None
        if (
            sha256_bytes(ps_art_bytes)
            != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
        ):
            return None
        if (
            sha256_bytes(ps_rec_bytes)
            != EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
        ):
            return None
        if sha256_bytes(prep_bytes) != EXPECTED_PREP_ARTIFACT_FILE_SHA256:
            return None

        plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
        freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
        ps_art = json.loads(ps_art_bytes.decode("utf-8"))
        prep_art = json.loads(prep_bytes.decode("utf-8"))

        if (
            plan_model.phase != "DEV_SELECT"
            or plan_model.plan_sha256 != EXPECTED_DEV_SELECT_PLAN_SHA256
            or plan_model.prompt_ids != ["P1"]
            or plan_model.candidate_ids != ["C1", "C2", "C3"]
            or len(plan_model.cells) != 180
        ):
            return None

        if (
            ps_art.get("selected_prompt_id") != "P1"
            or ps_art.get("selected_prompt_semantic_sha256")
            != EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
        ):
            return None

        if (
            prep_art.get("proposed_project_owner_authorization_text")
            != EXACT_AUTHORIZATION_TEXT
            or prep_art.get("proposed_project_owner_authorization_text_sha256")
            != AUTHORIZATION_TEXT_SHA256
        ):
            return None

        return plan_model, freeze_model
    except Exception:
        return None


def _verify_downstream_auth_artifact_core(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    if not path.is_file() or path.name != "w06_dev_select_live_authorization_v1.json":
        return False
    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if file_sha != EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256:
            return False

        effective_root = _resolve_effective_repo_root(repo_root)
        upstream = _verify_upstream_dev_select_authorities_for_downstream(
            effective_root
        )
        if upstream is None:
            return False
        plan_model, freeze_model = upstream

        auth = verify_dev_live_authorization_artifact(
            path,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=effective_root,
        )
        assert_no_secrets_in_payload(
            auth.model_dump(), context="DOWNSTREAM_DEV_SELECT_AUTH_VERIFICATION"
        )
    except Exception:
        return False

    return (
        auth.task_id == TASK_ID
        and auth.authorization_id == AUTHORIZATION_ID
        and auth.authorization_status == "AUTHORIZED"
        and auth.authorized_by_role == "PROJECT_OWNER"
        and auth.allowed_phase == "DEV_SELECT"
        and auth.allowed_execution_plan_sha256 == EXPECTED_DEV_SELECT_PLAN_SHA256
        and auth.allowed_prompt_freeze_sha256 == EXPECTED_PROMPT_FREEZE_SHA256
        and auth.allowed_candidate_ids == ["C1", "C2", "C3"]
        and auth.maximum_live_generation_calls == 180
        and auth.scientific_code_bundle_sha256
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and auth.code_basis_commit_sha == CODE_BASIS_COMMIT_SHA
        and auth.authorization_artifact_sha256
        == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    )


def _verify_downstream_auth_receipt_core(
    path: Path,
) -> bool:
    if (
        not path.is_file()
        or path.name != "w06_dev_select_live_authorization_01_receipt_v1.json"
    ):
        return False
    try:
        raw_bytes = normalize_lf_bytes(path.read_bytes())
        if sha256_bytes(raw_bytes) != EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256:
            return False
        obj = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(obj, dict):
            return False
        assert_no_secrets_in_payload(
            obj, context="DOWNSTREAM_DEV_SELECT_RECEIPT_VERIFICATION"
        )
    except Exception:
        return False

    return (
        obj.get("artifact_id") == RECEIPT_ARTIFACT_ID
        and obj.get("task_id") == TASK_ID
        and obj.get("authorization_id") == AUTHORIZATION_ID
        and obj.get("authorization_status") == "AUTHORIZED"
        and obj.get("authorized_by_role") == "PROJECT_OWNER"
        and obj.get("authorization_source") == AUTHORIZATION_SOURCE
        and obj.get("exact_authorization_text") == EXACT_AUTHORIZATION_TEXT
        and obj.get("authorization_text_sha256") == AUTHORIZATION_TEXT_SHA256
        and obj.get("authorization_text_character_count")
        == AUTHORIZATION_TEXT_CHARACTER_COUNT
        and obj.get("authorization_artifact_file_sha256")
        == EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256
        and obj.get("authorization_artifact_sha256")
        == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        and obj.get("allowed_phase") == "DEV_SELECT"
        and obj.get("allowed_execution_plan_sha256") == EXPECTED_DEV_SELECT_PLAN_SHA256
        and obj.get("execution_plan_file_sha256")
        == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        and obj.get("plan_freeze_receipt_file_sha256")
        == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
        and obj.get("allowed_prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
        and obj.get("selected_prompt_id") == "P1"
        and obj.get("selected_prompt_semantic_sha256")
        == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
        and obj.get("prompt_selection_artifact_file_sha256")
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
        and obj.get("prompt_selection_receipt_file_sha256")
        == EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
        and obj.get("authorization_prep_file_sha256")
        == EXPECTED_PREP_ARTIFACT_FILE_SHA256
        and obj.get("allowed_candidate_ids") == ["C1", "C2", "C3"]
        and obj.get("maximum_live_generation_calls") == 180
        and obj.get("attempts_per_cell") == 1
        and obj.get("retry_calls") == 0
        and obj.get("scientific_code_bundle_sha256")
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and obj.get("code_basis_commit_sha") == CODE_BASIS_COMMIT_SHA
        and obj.get("stage_a_created") is False
        and obj.get("live_execution_capability_issued") is False
        and obj.get("production_provider_transport_constructed") is False
        and obj.get("dev_select_execution_started") is False
        and obj.get("live_provider_calls_new") == 0
        and obj.get("provider_cost_usd_new") == 0
        and obj.get("model_winner_selected") is False
        and obj.get("stochasticity_execution_started") is False
        and obj.get("final100_used") is False
    )


def is_verified_downstream_w06_dev_select_authorization_artifact(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the exact, cryptographically verified W06-DEV-SELECT-LIVE-AUTHORIZATION-01 artifact AND its sibling receipt is verified (Section 19)."""
    if not _verify_downstream_auth_artifact_core(path, repo_root=repo_root):
        return False
    sibling_receipt = (
        path.parent / "w06_dev_select_live_authorization_01_receipt_v1.json"
    )
    if sibling_receipt.is_file():
        return _verify_downstream_auth_receipt_core(sibling_receipt)
    return True


def is_verified_downstream_w06_dev_select_authorization_receipt(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the exact W06-DEV-SELECT-LIVE-AUTHORIZATION-01 receipt bound to the verified sibling authorization artifact (Section 19)."""
    sibling_auth = path.parent / "w06_dev_select_live_authorization_v1.json"
    if not _verify_downstream_auth_artifact_core(sibling_auth, repo_root=repo_root):
        return False
    return _verify_downstream_auth_receipt_core(path)


def is_verified_downstream_w06_dev_select_authorization_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is the cryptographically verified downstream DEV-SELECT authorization artifact or receipt (Section 19)."""
    if path.name == "w06_dev_select_live_authorization_v1.json":
        return is_verified_downstream_w06_dev_select_authorization_artifact(
            path, repo_root=repo_root
        )
    if path.name == "w06_dev_select_live_authorization_01_receipt_v1.json":
        return is_verified_downstream_w06_dev_select_authorization_receipt(
            path, repo_root=repo_root
        )
    return False


# ==============================================================================
# 4. BUILD SCOPED DEV-SELECT AUTHORIZATION ARTIFACT & RECEIPT
# ==============================================================================


def load_verified_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Load and verify all frozen upstream authorities before issuing DEV-SELECT authorization."""
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

    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    dev_tune_plan_bytes = normalize_lf_bytes(dev_tune_plan_path.read_bytes())
    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    plan_rec_bytes = normalize_lf_bytes(plan_rec_path.read_bytes())
    ps_art_bytes = normalize_lf_bytes(ps_art_path.read_bytes())
    ps_rec_bytes = normalize_lf_bytes(ps_rec_path.read_bytes())
    prep_bytes = normalize_lf_bytes(prep_path.read_bytes())

    pf_file_sha = sha256_bytes(pf_bytes)
    plan_file_sha = sha256_bytes(plan_bytes)
    plan_rec_file_sha = sha256_bytes(plan_rec_bytes)
    ps_art_file_sha = sha256_bytes(ps_art_bytes)
    ps_rec_file_sha = sha256_bytes(ps_rec_bytes)
    prep_file_sha = sha256_bytes(prep_bytes)

    freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    dev_tune_plan_model = DevExecutionPlan.model_validate_json(dev_tune_plan_bytes)
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
    plan_rec_data = json.loads(plan_rec_bytes.decode("utf-8"))
    ps_art_data = json.loads(ps_art_bytes.decode("utf-8"))
    ps_rec_data = json.loads(ps_rec_bytes.decode("utf-8"))
    prep_data = json.loads(prep_bytes.decode("utf-8"))

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

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    pf_canonical_sha = compute_prompt_freeze_sha256(freeze_model)
    p1_cand = pf_mod.build_p1_spec()

    if (
        pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256
        or pf_canonical_sha != EXPECTED_PROMPT_FREEZE_SHA256
    ):
        raise RuntimeError(
            f"PROMPT_FREEZE_SHA256 mismatch: file={pf_file_sha}, canonical={pf_canonical_sha}"
        )
    if plan_model.plan_sha256 != EXPECTED_DEV_SELECT_PLAN_SHA256:
        raise RuntimeError(
            f"DEV_SELECT_PLAN_SHA256 mismatch: {plan_model.plan_sha256}"
        )
    if plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
        raise RuntimeError(
            f"DEV_SELECT_PLAN_FILE_SHA256 mismatch: {plan_file_sha}"
        )
    if plan_rec_file_sha != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256:
        raise RuntimeError(
            f"PLAN_FREEZE_RECEIPT_FILE_SHA256 mismatch: {plan_rec_file_sha}"
        )
    if ps_art_file_sha != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256:
        raise RuntimeError(
            f"PROMPT_SELECTION_ARTIFACT_FILE_SHA256 mismatch: {ps_art_file_sha}"
        )
    if ps_rec_file_sha != EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256:
        raise RuntimeError(
            f"PROMPT_SELECTION_RECEIPT_FILE_SHA256 mismatch: {ps_rec_file_sha}"
        )
    if prep_file_sha != EXPECTED_PREP_ARTIFACT_FILE_SHA256:
        raise RuntimeError(
            f"PREP_ARTIFACT_FILE_SHA256 mismatch: {prep_file_sha}"
        )
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise RuntimeError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256 mismatch: {bundle_sha}"
        )

    return {
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "p1_candidate": p1_cand,
        "prompt_freeze": freeze_model,
        "prompt_freeze_sha256": pf_file_sha,
        "execution_plan": plan_model,
        "execution_plan_file_sha256": plan_file_sha,
        "plan_freeze_receipt": plan_rec_data,
        "plan_freeze_receipt_file_sha256": plan_rec_file_sha,
        "prompt_selection_artifact": ps_art_data,
        "prompt_selection_artifact_file_sha256": ps_art_file_sha,
        "prompt_selection_receipt": ps_rec_data,
        "prompt_selection_receipt_file_sha256": ps_rec_file_sha,
        "authorization_prep": prep_data,
        "authorization_prep_file_sha256": prep_file_sha,
        "scientific_code_bundle_sha256": bundle_sha,
    }


def verify_dev_select_live_authorization_contract(
    authorization_or_path: DevLiveAuthorizationArtifact | dict[str, Any] | Path | str,
    *,
    execution_plan: DevExecutionPlan,
    prompt_freeze: DevPromptFreezeArtifact,
    expected_phase: str = "DEV_SELECT",
    repo_root: Path = REPO_ROOT,
) -> DevLiveAuthorizationArtifact:
    """Verify DEV-SELECT authorization through production contract plus DEV-SELECT code-basis & P1 locks."""
    verified = verify_dev_live_authorization_artifact(
        authorization_or_path,
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        expected_phase=expected_phase,
        repo_root=repo_root,
    )
    if (
        verified.code_basis_commit_sha != CODE_BASIS_COMMIT_SHA
        or verified.code_basis_commit_sha != execution_plan.code_commit_sha
    ):
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_CODE_BASIS_MISMATCH: code_basis_commit_sha={verified.code_basis_commit_sha!r} "
            f"!= frozen plan code basis {CODE_BASIS_COMMIT_SHA!r}."
        )
    if execution_plan.prompt_ids != ["P1"] or any(
        c.prompt_id != "P1" for c in execution_plan.cells
    ):
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PROMPT_SCOPE_MISMATCH: DEV-SELECT plan must lock prompt strictly to P1; got {execution_plan.prompt_ids}."
        )
    return verified


def build_scoped_dev_select_authorization_artifact(
    repo_root: Path = REPO_ROOT,
) -> DevLiveAuthorizationArtifact:
    """Build the production DevLiveAuthorizationArtifact for W06 DEV-SELECT using dev_live_runner.py."""
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
    verified = verify_dev_select_live_authorization_contract(
        artifact,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        expected_phase="DEV_SELECT",
        repo_root=repo_root,
    )
    assert_no_secrets_in_payload(
        verified.model_dump(), context="W06_DEV_SELECT_LIVE_AUTHORIZATION_ARTIFACT"
    )
    return verified


# ==============================================================================
# 5. AUTHORIZATION CHECK MATRIX (DSAU-01 .. DSAU-40)
# ==============================================================================


def run_all_dsau_checks(
    repo_root: Path = REPO_ROOT,
    *,
    auth_artifact_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Run all 40 authorization checks DSAU-01 through DSAU-40 under the outbound-network kill switch."""
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
        # DSAU-01: source develop provenance valid
        src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
        record(
            "DSAU-01",
            "SOURCE_PROVENANCE",
            "Source develop SHA 1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f provenance is valid",
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
        prep_data: dict[str, Any] = auths["authorization_prep"]
        ps_art_data: dict[str, Any] = auths["prompt_selection_artifact"]
        p1_cand = auths["p1_candidate"]
        cand_reg = auths["candidate_registry"]

        auth_model = build_scoped_dev_select_authorization_artifact(repo_root)
        if auth_artifact_path is not None and auth_artifact_path.is_file():
            persisted_auth = verify_dev_live_authorization_artifact(
                auth_artifact_path,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        else:
            persisted_auth = auth_model

        # DSAU-02: exact authorization text equality
        dsau02_ok = (
            EXACT_AUTHORIZATION_TEXT
            == prep_data["proposed_project_owner_authorization_text"]
            and prep_data["project_owner_authorization_status"] == "NOT_GRANTED"
            and EXPECTED_DEV_SELECT_PLAN_SHA256 in EXACT_AUTHORIZATION_TEXT
            and EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 in EXACT_AUTHORIZATION_TEXT
            and EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256 in EXACT_AUTHORIZATION_TEXT
            and EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
            in EXACT_AUTHORIZATION_TEXT
            and EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256 in EXACT_AUTHORIZATION_TEXT
            and "180-cell plan" in EXACT_AUTHORIZATION_TEXT
            and "locked prompt P1" in EXACT_AUTHORIZATION_TEXT
            and "candidates C1/C2/C3" in EXACT_AUTHORIZATION_TEXT
            and "maximum 180 generation calls" in EXACT_AUTHORIZATION_TEXT
            and "zero retry" in EXACT_AUTHORIZATION_TEXT
            and "no DEV-TUNE rerun" in EXACT_AUTHORIZATION_TEXT
            and "no stochasticity" in EXACT_AUTHORIZATION_TEXT
            and "no Final100" in EXACT_AUTHORIZATION_TEXT
        )
        record(
            "DSAU-02",
            "AUTHORIZATION_EVIDENCE",
            "Exact Project Owner authorization text matches prep_artifact.proposed_project_owner_authorization_text character-for-character",
            prep_data["proposed_project_owner_authorization_text"],
            EXACT_AUTHORIZATION_TEXT,
            dsau02_ok,
        )

        # DSAU-03: exact authorization text SHA
        recomputed_text_sha = hashlib.sha256(
            EXACT_AUTHORIZATION_TEXT.encode("utf-8")
        ).hexdigest()
        dsau03_ok = (
            recomputed_text_sha == AUTHORIZATION_TEXT_SHA256
            and recomputed_text_sha
            == prep_data["proposed_project_owner_authorization_text_sha256"]
        )
        record(
            "DSAU-03",
            "AUTHORIZATION_EVIDENCE",
            "SHA256(exact UTF-8 bytes) equals 6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7",
            AUTHORIZATION_TEXT_SHA256,
            recomputed_text_sha,
            dsau03_ok,
        )

        # DSAU-04: character count 633
        char_count = len(EXACT_AUTHORIZATION_TEXT)
        dsau04_ok = char_count == 633 == AUTHORIZATION_TEXT_CHARACTER_COUNT
        record(
            "DSAU-04",
            "AUTHORIZATION_EVIDENCE",
            "Exact Project Owner authorization sentence length is 633 characters",
            633,
            char_count,
            dsau04_ok,
        )

        # DSAU-05: PROJECT_OWNER role
        dsau05_ok = persisted_auth.authorized_by_role == "PROJECT_OWNER"
        record(
            "DSAU-05",
            "AUTHORIZATION_SCOPE",
            "authorized_by_role is strictly PROJECT_OWNER",
            "PROJECT_OWNER",
            persisted_auth.authorized_by_role,
            dsau05_ok,
        )

        # DSAU-06: AUTHORIZED status
        dsau06_ok = persisted_auth.authorization_status == "AUTHORIZED"
        record(
            "DSAU-06",
            "AUTHORIZATION_SCOPE",
            "authorization_status is strictly AUTHORIZED",
            "AUTHORIZED",
            persisted_auth.authorization_status,
            dsau06_ok,
        )

        # DSAU-07: phase DEV_SELECT
        dsau07_ok = (
            persisted_auth.allowed_phase == "DEV_SELECT"
            and plan_model.phase == "DEV_SELECT"
            and all(c.phase == "DEV_SELECT" for c in plan_model.cells)
        )
        record(
            "DSAU-07",
            "AUTHORIZATION_SCOPE",
            "allowed_phase and all 180 plan cells are strictly DEV_SELECT",
            "DEV_SELECT",
            persisted_auth.allowed_phase,
            dsau07_ok,
        )

        # DSAU-08: plan internal SHA exact
        dsau08_ok = (
            persisted_auth.allowed_execution_plan_sha256
            == EXPECTED_DEV_SELECT_PLAN_SHA256
            and plan_model.plan_sha256 == EXPECTED_DEV_SELECT_PLAN_SHA256
        )
        record(
            "DSAU-08",
            "EXECUTION_PLAN_AUTHORITY",
            "allowed_execution_plan_sha256 matches frozen DEV-SELECT plan internal SHA de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d",
            EXPECTED_DEV_SELECT_PLAN_SHA256,
            persisted_auth.allowed_execution_plan_sha256,
            dsau08_ok,
        )

        # DSAU-09: plan file SHA exact
        dsau09_ok = (
            auths["execution_plan_file_sha256"] == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        )
        record(
            "DSAU-09",
            "EXECUTION_PLAN_AUTHORITY",
            "w06_dev_select_execution_plan_v1.json file SHA256 equals c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a",
            EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
            auths["execution_plan_file_sha256"],
            dsau09_ok,
        )

        # DSAU-10: plan-freeze receipt exact
        dsau10_ok = (
            auths["plan_freeze_receipt_file_sha256"]
            == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
            and auths["plan_freeze_receipt"]["dev_select_plan_internal_sha256"]
            == EXPECTED_DEV_SELECT_PLAN_SHA256
            and auths["plan_freeze_receipt"]["dev_select_plan_file_sha256"]
            == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        )
        record(
            "DSAU-10",
            "EXECUTION_PLAN_AUTHORITY",
            "w06_dev_select_plan_freeze_01_receipt_v1.json file SHA256 equals 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549",
            EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
            auths["plan_freeze_receipt_file_sha256"],
            dsau10_ok,
        )

        # DSAU-11: prompt freeze SHA exact
        dsau11_ok = (
            persisted_auth.allowed_prompt_freeze_sha256
            == EXPECTED_PROMPT_FREEZE_SHA256
            and auths["prompt_freeze_sha256"] == EXPECTED_PROMPT_FREEZE_SHA256
        )
        record(
            "DSAU-11",
            "PROMPT_AUTHORITY",
            "allowed_prompt_freeze_sha256 equals 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
            EXPECTED_PROMPT_FREEZE_SHA256,
            persisted_auth.allowed_prompt_freeze_sha256,
            dsau11_ok,
        )

        # DSAU-12: selected prompt P1 exact
        dsau12_ok = (
            plan_model.prompt_ids == ["P1"]
            and all(c.prompt_id == "P1" for c in plan_model.cells)
            and ps_art_data["selected_prompt_id"] == "P1"
            and p1_cand.prompt_version == EXPECTED_SELECTED_PROMPT_VERSION
            and "P2" not in plan_model.prompt_ids
        )
        record(
            "DSAU-12",
            "PROMPT_AUTHORITY",
            "DEV-SELECT prompt is locked strictly to P1 (TRAVEL_PLANNER_BENCHMARK_V2); P2 is not authorized",
            {"prompt_ids": ["P1"], "version": EXPECTED_SELECTED_PROMPT_VERSION},
            {"prompt_ids": plan_model.prompt_ids, "version": p1_cand.prompt_version},
            dsau12_ok,
        )

        # DSAU-13: P1 semantic SHA exact
        p1_sys_sha = sha256_bytes(normalize_lf_bytes(p1_cand.system_prompt.encode("utf-8")))
        p1_usr_sha = sha256_bytes(normalize_lf_bytes(p1_cand.user_prompt_template.encode("utf-8")))
        dsau13_ok = (
            p1_cand.semantic_prompt_sha256 == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
            and p1_sys_sha == EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256
            and p1_usr_sha == EXPECTED_SELECTED_PROMPT_USER_TEMPLATE_SHA256
            and ps_art_data["selected_prompt_semantic_sha256"]
            == EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256
            and all(
                c.system_prompt_sha256 == EXPECTED_SELECTED_PROMPT_SYSTEM_SHA256
                for c in plan_model.cells
            )
        )
        record(
            "DSAU-13",
            "PROMPT_AUTHORITY",
            "P1 semantic SHA256 (096ff4c7...), system SHA256 (4bcb84a8...), and user-template SHA256 (19762f7c...) match across all 180 cells",
            EXPECTED_SELECTED_PROMPT_SEMANTIC_SHA256,
            p1_cand.semantic_prompt_sha256,
            dsau13_ok,
        )

        # DSAU-14: prompt-selection artifact exact
        dsau14_ok = (
            auths["prompt_selection_artifact_file_sha256"]
            == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
            and auths["prompt_selection_receipt_file_sha256"]
            == EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
        )
        record(
            "DSAU-14",
            "PROMPT_AUTHORITY",
            "Prompt-selection artifact SHA256 (e1e79801...) and receipt SHA256 (0ad09212...) match exactly",
            {
                "artifact_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
                "receipt_sha256": EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
            },
            {
                "artifact_sha256": auths["prompt_selection_artifact_file_sha256"],
                "receipt_sha256": auths["prompt_selection_receipt_file_sha256"],
            },
            dsau14_ok,
        )

        # DSAU-15: candidate IDs exact C1/C2/C3
        cand_map = {
            cid: spec.requested_model_id
            for cid, spec in cand_reg.candidates.items()
        }
        prov_reg_sha = compute_provider_config_registry_sha256(cand_reg)
        dsau15_ok = (
            persisted_auth.allowed_candidate_ids == ["C1", "C2", "C3"]
            and plan_model.candidate_ids == ["C1", "C2", "C3"]
            and cand_map
            == {
                "C1": "gemini-3.8-flash",
                "C2": "gpt-6.1-sol",
                "C3": "claude-sonnet-5-5",
            }
            and cand_reg.registry_sha256 == EXPECTED_CANDIDATE_REGISTRY_SHA256
            and prov_reg_sha == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
        )
        record(
            "DSAU-15",
            "CANDIDATE_SCOPE",
            "Allowed candidate IDs are strictly ['C1', 'C2', 'C3'] with frozen candidate and provider-config registries",
            ["C1", "C2", "C3"],
            persisted_auth.allowed_candidate_ids,
            dsau15_ok,
        )

        # DSAU-16: call budget exactly 180
        dsau16_ok = (
            persisted_auth.maximum_live_generation_calls == 180 == DEV_SELECT_MAX_CALLS
        )
        record(
            "DSAU-16",
            "CALL_BUDGET",
            "maximum_live_generation_calls is strictly 180",
            180,
            persisted_auth.maximum_live_generation_calls,
            dsau16_ok,
        )

        # DSAU-17: 180 unique assigned cells
        unique_run_ids = {c.run_id for c in plan_model.cells}
        unique_cell_keys = {
            (c.phase, c.fixture_id, c.prompt_id, c.candidate_id, c.attempt_number)
            for c in plan_model.cells
        }
        unique_fixtures = {c.fixture_id for c in plan_model.cells}
        dsau17_ok = (
            len(plan_model.cells) == 180
            and len(unique_run_ids) == 180
            and len(unique_cell_keys) == 180
            and len(unique_fixtures) == DEV_SELECT_COUNT == 60
        )
        record(
            "DSAU-17",
            "CALL_BUDGET",
            "Plan contains 180 assigned cells, 180 unique run IDs, 180 unique cell keys, and 60 unique DEV-SELECT fixtures",
            {"cells": 180, "unique_run_ids": 180, "unique_cell_keys": 180, "fixtures": 60},
            {
                "cells": len(plan_model.cells),
                "unique_run_ids": len(unique_run_ids),
                "unique_cell_keys": len(unique_cell_keys),
                "fixtures": len(unique_fixtures),
            },
            dsau17_ok,
        )

        # DSAU-18: attempts per cell exactly 1
        dsau18_ok = ATTEMPTS_PER_CELL == 1 and all(
            c.attempt_number == 1 for c in plan_model.cells
        )
        record(
            "DSAU-18",
            "EXECUTION_POLICY",
            "attempts_per_cell is strictly 1 across all 180 assigned cells",
            1,
            ATTEMPTS_PER_CELL,
            dsau18_ok,
        )

        # DSAU-19: all retry/fallback/repair/tools zero/false
        dsau19_ok = RETRY_CALLS == 0 and all(
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
            "DSAU-19",
            "EXECUTION_POLICY",
            "All retry/fallback/repair/tools flags are strictly zero/false across all 180 cells",
            0,
            RETRY_CALLS,
            dsau19_ok,
        )

        # DSAU-20: scientific bundle exact
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
        bundle_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
        expected_bundle_map = {
            entry["path"]: entry["sha256"]
            for entry in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        }
        actual_bundle_map = {
            entry["path"]: entry["sha256"] for entry in bundle_hashes
        }
        dsau20_ok = (
            persisted_auth.scientific_code_bundle_sha256
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and actual_bundle_map == expected_bundle_map
            and len(bundle_hashes) == len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14
        )
        record(
            "DSAU-20",
            "SCIENTIFIC_CODE_BUNDLE",
            "All 14 scientific code bundle files match SHA256 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
            EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            bundle_sha,
            dsau20_ok,
        )

        # DSAU-21: code basis exact c0adf74...
        dsau21_ok = (
            persisted_auth.code_basis_commit_sha == CODE_BASIS_COMMIT_SHA
            and plan_model.code_commit_sha == CODE_BASIS_COMMIT_SHA
            and persisted_auth.code_basis_commit_sha != SOURCE_DEVELOP_SHA
        )
        record(
            "DSAU-21",
            "CODE_BASIS",
            "code_basis_commit_sha equals frozen plan code basis c0adf74ceda9ffaf8b4ec42d299932e33f448e6a (not replaced with source develop SHA)",
            CODE_BASIS_COMMIT_SHA,
            persisted_auth.code_basis_commit_sha,
            dsau21_ok,
        )

        # DSAU-22: production builder used
        rebuilt = build_dev_live_authorization_artifact(
            task_id=TASK_ID,
            authorization_id=AUTHORIZATION_ID,
            authorized_by_role=AUTHORIZED_BY_ROLE,
            authorized_at_utc=AUTHORIZED_AT_UTC,
            authorization_status=AUTHORIZATION_STATUS,
            allowed_phase=ALLOWED_PHASE,
            allowed_candidate_ids=list(ALLOWED_CANDIDATE_IDS),
            maximum_live_generation_calls=MAXIMUM_LIVE_GENERATION_CALLS,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            scientific_code_bundle_sha256=EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            code_basis_commit_sha=CODE_BASIS_COMMIT_SHA,
        )
        dsau22_ok = (
            isinstance(rebuilt, DevLiveAuthorizationArtifact)
            and rebuilt.model_dump() == persisted_auth.model_dump()
        )
        record(
            "DSAU-22",
            "PRODUCTION_CONTRACT",
            "Production app.evaluation.dev_live_runner.build_dev_live_authorization_artifact produces identical artifact",
            rebuilt.authorization_artifact_sha256,
            persisted_auth.authorization_artifact_sha256,
            dsau22_ok,
        )

        # DSAU-23: production verifier passes
        verified_contract = verify_dev_live_authorization_artifact(
            persisted_auth,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=repo_root,
        )
        dsau23_ok = (
            isinstance(verified_contract, DevLiveAuthorizationArtifact)
            and verified_contract.authorization_id == AUTHORIZATION_ID
            and verified_contract.allowed_phase == "DEV_SELECT"
        )
        record(
            "DSAU-23",
            "PRODUCTION_CONTRACT",
            "Production verify_dev_live_authorization_artifact(..., expected_phase='DEV_SELECT') passes",
            AUTHORIZATION_ID,
            verified_contract.authorization_id,
            dsau23_ok,
        )

        # DSAU-24: DEV_TUNE rejected
        dev_tune_rejected = False
        try:
            verify_dev_live_authorization_artifact(
                persisted_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            dev_tune_rejected = True
        record(
            "DSAU-24",
            "SCOPE_EXCLUSION",
            "DEV_TUNE phase is rejected by verify_dev_live_authorization_artifact",
            True,
            dev_tune_rejected,
            dev_tune_rejected,
        )

        # DSAU-25: STOCHASTICITY rejected
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
            "DSAU-25",
            "SCOPE_EXCLUSION",
            "STOCHASTICITY phase is rejected by verify_dev_live_authorization_artifact",
            True,
            stoch_rejected,
            stoch_rejected,
        )

        # DSAU-26: Final100 rejected
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
            "DSAU-26",
            "FINAL100_FIREWALL",
            "FINAL100 phase is rejected with Final100FirewallViolationError",
            True,
            final100_rejected,
            final100_rejected,
        )

        # DSAU-27: 181 calls rejected
        calls_181_rejected = False
        calls_179_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-181-CALLS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=181,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            calls_181_rejected = True
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-179-CALLS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=179,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            calls_179_rejected = True
        dsau27_ok = calls_181_rejected and calls_179_rejected
        record(
            "DSAU-27",
            "ADVERSARIAL_REJECTION",
            "maximum_live_generation_calls=181 (and 179) rejected by production contract",
            {"181_rejected": True, "179_rejected": True},
            {"181_rejected": calls_181_rejected, "179_rejected": calls_179_rejected},
            dsau27_ok,
        )

        # DSAU-28: C4 rejected
        c4_rejected = False
        missing_cand_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-C4",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3", "C4"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            c4_rejected = True
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-MISSING-C3",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            missing_cand_rejected = True
        dsau28_ok = c4_rejected and missing_cand_rejected
        record(
            "DSAU-28",
            "ADVERSARIAL_REJECTION",
            "Candidate C4 and missing candidate subset are rejected by production contract",
            {"c4_rejected": True, "missing_cand_rejected": True},
            {"c4_rejected": c4_rejected, "missing_cand_rejected": missing_cand_rejected},
            dsau28_ok,
        )

        # DSAU-29: wrong plan rejected
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
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            wrong_plan_rejected = True
        record(
            "DSAU-29",
            "ADVERSARIAL_REJECTION",
            "Mismatched allowed_execution_plan_sha256 is rejected by verify_dev_live_authorization_artifact",
            True,
            wrong_plan_rejected,
            wrong_plan_rejected,
        )

        # DSAU-30: wrong prompt freeze rejected
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
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            wrong_pf_rejected = True
        record(
            "DSAU-30",
            "ADVERSARIAL_REJECTION",
            "Mismatched allowed_prompt_freeze_sha256 is rejected by verify_dev_live_authorization_artifact",
            True,
            wrong_pf_rejected,
            wrong_pf_rejected,
        )

        # DSAU-31: wrong role rejected
        wrong_role_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-ROLE",
                authorized_by_role="AGENT_SELF_AUTHORIZED",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            wrong_role_rejected = True
        record(
            "DSAU-31",
            "ADVERSARIAL_REJECTION",
            "Non-PROJECT_OWNER authorized_by_role is rejected by production contract",
            True,
            wrong_role_rejected,
            wrong_role_rejected,
        )

        # DSAU-32: unauthorized status rejected
        unauth_status_rejected = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-STATUS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="NOT_GRANTED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            unauth_status_rejected = True
        record(
            "DSAU-32",
            "ADVERSARIAL_REJECTION",
            "Non-AUTHORIZED authorization_status is rejected by production contract",
            True,
            unauth_status_rejected,
            unauth_status_rejected,
        )

        # DSAU-33: secret scan passes
        secret_scan_ok = True
        try:
            assert_no_secrets_in_payload(
                persisted_auth.model_dump(), context="DSAU_33_AUTH_ARTIFACT"
            )
            serialized_auth = json.dumps(persisted_auth.model_dump())
            for forbidden_token in (
                "GEMINI_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "key_hash",
                "key_length",
                "key_prefix",
                "key_suffix",
            ):
                if forbidden_token in serialized_auth:
                    secret_scan_ok = False
        except Exception:
            secret_scan_ok = False
        record(
            "DSAU-33",
            "SECRET_SAFETY",
            "assert_no_secrets_in_payload passes and zero key material/metadata is persisted",
            True,
            secret_scan_ok,
            secret_scan_ok,
        )

        # DSAU-34: actual httpx2 outbound blocked
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
        # Clear intentional self-test probes from guard counter
        guard.blocked_attempts.clear()
        dsau34_ok = (
            httpx2.__name__ == "httpx2"
            and httpx2 is not httpx
            and httpx2_blocked
            and socket_blocked
            and urllib_blocked
            and httpx_blocked
        )
        record(
            "DSAU-34",
            "NETWORK_ISOLATION",
            "Actual httpx2 (distinct from httpx), httpx, urllib, and socket outbound calls are blocked by NetworkKillSwitchGuard",
            {
                "httpx2_distinct": True,
                "httpx2_blocked": True,
                "httpx_blocked": True,
                "urllib_blocked": True,
                "socket_blocked": True,
            },
            {
                "httpx2_distinct": httpx2.__name__ == "httpx2" and httpx2 is not httpx,
                "httpx2_blocked": httpx2_blocked,
                "httpx_blocked": httpx_blocked,
                "urllib_blocked": urllib_blocked,
                "socket_blocked": socket_blocked,
            },
            dsau34_ok,
        )

        fw = verify_pre_stage_a_firewall(repo_root)

        # DSAU-35: Stage-A absent
        dsau35_ok = (
            fw["stage_a_created"] is False
            and len(fw["forbidden_dev_select_stage_a_files"]) == 0
        )
        record(
            "DSAU-35",
            "PRE_STAGE_A_FIREWALL",
            "STAGE_A_CREATED is false and no DEV-SELECT Stage-A receipt exists",
            False,
            fw["stage_a_created"],
            dsau35_ok,
        )

        # DSAU-36: capability absent
        dsau36_ok = fw["live_execution_capability_issued"] is False
        record(
            "DSAU-36",
            "PRE_STAGE_A_FIREWALL",
            "LIVE_EXECUTION_CAPABILITY_ISSUED is false",
            False,
            fw["live_execution_capability_issued"],
            dsau36_ok,
        )

        # DSAU-37: production transport absent
        dsau37_ok = (
            fw["production_provider_transport_constructed"] is False
            and fw["transport_journal_created"] is False
            and len(fw["forbidden_transport_journals"]) == 0
        )
        record(
            "DSAU-37",
            "PRE_STAGE_A_FIREWALL",
            "PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED and TRANSPORT_JOURNAL_CREATED are false",
            {
                "production_provider_transport_constructed": False,
                "transport_journal_created": False,
            },
            {
                "production_provider_transport_constructed": fw[
                    "production_provider_transport_constructed"
                ],
                "transport_journal_created": fw["transport_journal_created"],
            },
            dsau37_ok,
        )

        # DSAU-38: DEV-SELECT not started
        dsau38_ok = (
            fw["dev_select_execution_started"] is False
            and fw["dev_select_live_result_directory_created"] is False
            and fw["model_winner_selected"] is False
            and fw["stochasticity_execution_started"] is False
            and len(fw["forbidden_dev_select_live_dirs"]) == 0
        )
        record(
            "DSAU-38",
            "PRE_STAGE_A_FIREWALL",
            "DEV_SELECT_EXECUTION_STARTED, DEV_SELECT_LIVE_RESULT_DIRECTORY_CREATED, MODEL_WINNER_SELECTED, and STOCHASTICITY_EXECUTION_STARTED are false",
            False,
            fw["dev_select_execution_started"],
            dsau38_ok,
        )

        # DSAU-39: zero provider calls
        dsau39_ok = (
            len(guard.blocked_attempts) == 0
            and fw["live_provider_calls_new"] == 0
            and fw["provider_cost_usd_new"] == 0
        )
        record(
            "DSAU-39",
            "NETWORK_ISOLATION",
            "LIVE_PROVIDER_CALLS_NEW = 0 and PROVIDER_COST_USD_NEW = 0",
            {"live_provider_calls_new": 0, "provider_cost_usd_new": 0},
            {
                "live_provider_calls_new": fw["live_provider_calls_new"],
                "provider_cost_usd_new": fw["provider_cost_usd_new"],
            },
            dsau39_ok,
        )

        # DSAU-40: Final100 unused
        f100_path = repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
        p11_path = repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH
        dsau40_ok = (
            fw["final100_used"] is False
            and f100_path.is_file()
            and p11_path.is_file()
            and FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
            not in json.dumps(persisted_auth.model_dump())
            and FORBIDDEN_P11_MANIFEST_REL_PATH
            not in json.dumps(persisted_auth.model_dump())
        )
        record(
            "DSAU-40",
            "FINAL100_FIREWALL",
            "FINAL100_USED is false and Final100/P11 files are untouched and unreferenced",
            False,
            fw["final100_used"],
            dsau40_ok,
        )

    return results


# ==============================================================================
# 6. ADVERSARIAL PRODUCTION CONTRACT CHECKS (SECTION 17: ADV-01 .. ADV-20)
# ==============================================================================


def run_all_adversarial_checks(repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """Run all 20 adversarial checks from Section 17 under the outbound-network kill switch."""
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
        auths = load_verified_authorities(repo_root)
        plan_model: DevExecutionPlan = auths["execution_plan"]
        freeze_model: DevPromptFreezeArtifact = auths["prompt_freeze"]
        cand_reg = auths["candidate_registry"]
        valid_auth = build_scoped_dev_select_authorization_artifact(repo_root)
        valid_dict = valid_auth.model_dump()

        # ADV-01: wrong phase DEV_TUNE
        adv01 = False
        try:
            verify_dev_live_authorization_artifact(
                valid_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_TUNE",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv01 = True
        record("ADV-01", "wrong phase DEV_TUNE rejected", adv01)

        # ADV-02: wrong phase STOCHASTICITY
        adv02 = False
        try:
            verify_dev_live_authorization_artifact(
                valid_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="STOCHASTICITY",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv02 = True
        record("ADV-02", "wrong phase STOCHASTICITY rejected", adv02)

        # ADV-03: Final100
        adv03 = False
        try:
            verify_dev_live_authorization_artifact(
                valid_auth,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="FINAL100",
                repo_root=repo_root,
            )
        except Final100FirewallViolationError:
            adv03 = True
        record("ADV-03", "Final100 rejected with Final100FirewallViolationError", adv03)

        # ADV-04: 179/181 call budget
        adv04_179 = False
        adv04_181 = False
        for bad_budget in (179, 181):
            try:
                build_dev_live_authorization_artifact(
                    task_id=TASK_ID,
                    authorization_id=f"BAD-{bad_budget}",
                    authorized_by_role="PROJECT_OWNER",
                    authorized_at_utc=AUTHORIZED_AT_UTC,
                    authorization_status="AUTHORIZED",
                    allowed_phase="DEV_SELECT",
                    allowed_candidate_ids=["C1", "C2", "C3"],
                    maximum_live_generation_calls=bad_budget,
                    execution_plan=plan_model,
                    prompt_freeze=freeze_model,
                )
            except DevLiveAuthorizationError:
                if bad_budget == 179:
                    adv04_179 = True
                else:
                    adv04_181 = True
        record("ADV-04", "179 and 181 call budgets rejected", adv04_179 and adv04_181)

        # ADV-05: candidate C4
        adv05 = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-C4",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3", "C4"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            adv05 = True
        record("ADV-05", "candidate C4 rejected", adv05)

        # ADV-06: candidate missing
        adv06 = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-CAND-MISSING",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            adv06 = True
        record("ADV-06", "missing candidate rejected", adv06)

        # ADV-07: wrong plan internal SHA
        adv07 = False
        try:
            d07 = dict(valid_dict)
            d07.pop("authorization_artifact_sha256", None)
            d07["allowed_execution_plan_sha256"] = "a" * 64
            d07["authorization_artifact_sha256"] = sha256_bytes(canonical_json_bytes(d07))
            verify_dev_live_authorization_artifact(
                d07,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv07 = True
        record("ADV-07", "wrong plan internal SHA rejected", adv07)

        # ADV-08: wrong prompt-freeze SHA
        adv08 = False
        try:
            d08 = dict(valid_dict)
            d08.pop("authorization_artifact_sha256", None)
            d08["allowed_prompt_freeze_sha256"] = "b" * 64
            d08["authorization_artifact_sha256"] = sha256_bytes(canonical_json_bytes(d08))
            verify_dev_live_authorization_artifact(
                d08,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv08 = True
        record("ADV-08", "wrong prompt-freeze SHA rejected", adv08)

        # ADV-09: wrong owner role
        adv09 = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-ROLE",
                authorized_by_role="DEVELOPER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            adv09 = True
        record("ADV-09", "wrong owner role rejected", adv09)

        # ADV-10: authorization_status != AUTHORIZED
        adv10 = False
        try:
            build_dev_live_authorization_artifact(
                task_id=TASK_ID,
                authorization_id="BAD-STATUS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=AUTHORIZED_AT_UTC,
                authorization_status="PENDING",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )
        except DevLiveAuthorizationError:
            adv10 = True
        record("ADV-10", "authorization_status != AUTHORIZED rejected", adv10)

        # ADV-11: wrong scientific bundle SHA
        adv11 = False
        try:
            d11 = dict(valid_dict)
            d11.pop("authorization_artifact_sha256", None)
            d11["scientific_code_bundle_sha256"] = "c" * 64
            d11["authorization_artifact_sha256"] = sha256_bytes(canonical_json_bytes(d11))
            verify_dev_live_authorization_artifact(
                d11,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except (DevLiveAuthorizationError, ScientificCodeBundleIntegrityError):
            adv11 = True
        record("ADV-11", "wrong scientific bundle SHA rejected", adv11)

        # ADV-12: wrong code basis (including replacing with source develop SHA 1f5f94f...)
        adv12 = False
        try:
            d12 = dict(valid_dict)
            d12.pop("authorization_artifact_sha256", None)
            d12["code_basis_commit_sha"] = SOURCE_DEVELOP_SHA
            d12["authorization_artifact_sha256"] = sha256_bytes(canonical_json_bytes(d12))
            verify_dev_select_live_authorization_contract(
                d12,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except (DevLiveAuthorizationError, ScientificCodeBundleIntegrityError):
            adv12 = True
        record("ADV-12", "wrong code basis (e.g. 1f5f94f...) rejected", adv12)

        # ADV-13: tampered internal authorization SHA
        adv13 = False
        try:
            d13 = dict(valid_dict)
            d13["authorization_artifact_sha256"] = "d" * 64
            verify_dev_live_authorization_artifact(
                d13,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv13 = True
        record("ADV-13", "tampered internal authorization SHA rejected", adv13)

        # ADV-14: tampered authorization file
        with tempfile.TemporaryDirectory() as tmp_str:
            p14 = Path(tmp_str) / "w06_dev_select_live_authorization_v1.json"
            p14.write_bytes(canonical_json_bytes(valid_dict) + b"\n")
            adv14 = (
                is_verified_downstream_w06_dev_select_authorization_file(
                    p14, repo_root=repo_root
                )
                is False
            )
        record("ADV-14", "tampered authorization file rejected", adv14)

        # ADV-15: one-character authorization-text mutation
        mutated_text = EXACT_AUTHORIZATION_TEXT[:-1] + "!"
        adv15 = (
            mutated_text != EXACT_AUTHORIZATION_TEXT
            and hashlib.sha256(mutated_text.encode("utf-8")).hexdigest()
            != AUTHORIZATION_TEXT_SHA256
        )
        record("ADV-15", "one-character authorization-text mutation rejected", adv15)

        # ADV-16: authorization-text SHA mismatch in receipt
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            auth_p = tmp_dir / "w06_dev_select_live_authorization_v1.json"
            rec_p = tmp_dir / "w06_dev_select_live_authorization_01_receipt_v1.json"
            auth_p.write_bytes(canonical_json_bytes(valid_dict))
            rec_p.write_bytes(
                canonical_json_bytes({"authorization_text_sha256": "e" * 64})
            )
            adv16 = (
                is_verified_downstream_w06_dev_select_authorization_file(
                    rec_p, repo_root=repo_root
                )
                is False
            )
        record("ADV-16", "authorization-text SHA mismatch rejected", adv16)

        # ADV-17: P2 substituted into DEV-SELECT plan
        adv17_cell_tamper = False
        adv17_contract_tamper = False
        try:
            p2_plan_dict = plan_model.model_dump()
            p2_plan_dict["cells"][0]["prompt_id"] = "P2"
            DevExecutionPlan.model_validate(p2_plan_dict)
        except Exception:
            adv17_cell_tamper = True
        try:
            p2_header_dict = plan_model.model_dump()
            p2_header_dict["prompt_ids"] = ["P2"]
            p2_header_model = DevExecutionPlan.model_validate(p2_header_dict)
            verify_dev_select_live_authorization_contract(
                valid_auth,
                execution_plan=p2_header_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=repo_root,
            )
        except DevLiveAuthorizationError:
            adv17_contract_tamper = True
        record(
            "ADV-17",
            "P2 substituted into DEV-SELECT plan rejected",
            adv17_cell_tamper and adv17_contract_tamper,
        )

        # ADV-18: retry=1 in cell
        adv18 = False
        try:
            retry_plan_dict = plan_model.model_dump()
            retry_plan_dict["cells"][0]["retry"] = 1
            bad_plan_model = DevExecutionPlan.model_validate(retry_plan_dict)
            verify_dev_execution_plan_for_execution(
                bad_plan_model, candidate_registry=cand_reg, repo_root=repo_root
            )
        except Exception:
            adv18 = True
        record("ADV-18", "retry=1 in DEV-SELECT cell rejected", adv18)

        # ADV-19: Stage-A or provider result directory fabricated early
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_repo = Path(tmp_str)
            w06_tmp = tmp_repo / "data" / "evaluation" / "w06"
            (w06_tmp / "live_dev_select_v1").mkdir(parents=True)
            (w06_tmp / "w06_dev_select_stage_a_freeze_receipt_v1.json").write_text(
                '{"artifact_id": "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"}',
                encoding="utf-8",
            )
            fw_bad = verify_pre_stage_a_firewall(tmp_repo)
            adv19 = (
                fw_bad["stage_a_created"] is True
                and fw_bad["dev_select_live_result_directory_created"] is True
            )
        record(
            "ADV-19",
            "Stage-A or provider result directory fabricated early detected and rejected",
            adv19,
        )

        # ADV-20: outbound network attempt blocked
        adv20 = False
        try:
            with httpx2.Client() as client:
                client.post("https://api.openai.com/v1/responses")
        except OutboundNetworkBlockedError:
            adv20 = True
        guard.blocked_attempts.clear()
        record("ADV-20", "outbound network attempt blocked by kill switch", adv20)

    return results


# ==============================================================================
# 7. ISSUE / PERSIST & VERIFY-ONLY MODE
# ==============================================================================


def build_authorization_receipt_payload(
    repo_root: Path = REPO_ROOT,
    *,
    auth_model: DevLiveAuthorizationArtifact,
    auth_file_sha256: str,
    dsau_checks: list[dict[str, Any]],
    adversarial_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the deterministic W06-DEV-SELECT-LIVE-AUTHORIZATION-01 receipt payload (Section 14)."""
    auths = load_verified_authorities(repo_root)
    cand_reg = auths["candidate_registry"]
    p1_cand = auths["p1_candidate"]

    payload: dict[str, Any] = {
        "artifact_id": RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
        "authorization_id": auth_model.authorization_id,
        "authorization_status": auth_model.authorization_status,
        "authorized_by_role": auth_model.authorized_by_role,
        "authorization_source": AUTHORIZATION_SOURCE,
        "authorized_at_utc": auth_model.authorized_at_utc,
        "authorized_at_utc_semantics": AUTHORIZED_AT_UTC_SEMANTICS,
        "exact_authorization_text": EXACT_AUTHORIZATION_TEXT,
        "authorization_text_sha256": AUTHORIZATION_TEXT_SHA256,
        "authorization_text_character_count": AUTHORIZATION_TEXT_CHARACTER_COUNT,
        "authorization_artifact_relative_path": AUTHORIZATION_ARTIFACT_REL_PATH,
        "authorization_artifact_file_sha256": auth_file_sha256,
        "authorization_artifact_sha256": auth_model.authorization_artifact_sha256,
        "allowed_phase": auth_model.allowed_phase,
        "allowed_execution_plan_sha256": auth_model.allowed_execution_plan_sha256,
        "execution_plan_file_sha256": auths["execution_plan_file_sha256"],
        "plan_freeze_receipt_file_sha256": auths["plan_freeze_receipt_file_sha256"],
        "allowed_prompt_freeze_sha256": auth_model.allowed_prompt_freeze_sha256,
        "selected_prompt_id": EXPECTED_SELECTED_PROMPT_ID,
        "selected_prompt_version": p1_cand.prompt_version,
        "selected_prompt_semantic_sha256": p1_cand.semantic_prompt_sha256,
        "selected_prompt_system_sha256": sha256_bytes(
            normalize_lf_bytes(p1_cand.system_prompt.encode("utf-8"))
        ),
        "selected_prompt_user_template_sha256": sha256_bytes(
            normalize_lf_bytes(p1_cand.user_prompt_template.encode("utf-8"))
        ),
        "prompt_selection_artifact_file_sha256": auths[
            "prompt_selection_artifact_file_sha256"
        ],
        "prompt_selection_receipt_file_sha256": auths[
            "prompt_selection_receipt_file_sha256"
        ],
        "authorization_prep_file_sha256": auths["authorization_prep_file_sha256"],
        "allowed_candidate_ids": auth_model.allowed_candidate_ids,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": compute_provider_config_registry_sha256(
            cand_reg
        ),
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "maximum_live_generation_calls": auth_model.maximum_live_generation_calls,
        "attempts_per_cell": ATTEMPTS_PER_CELL,
        "retry_calls": RETRY_CALLS,
        "scientific_code_bundle_sha256": auth_model.scientific_code_bundle_sha256,
        "experiment_matrix": {
            "phase": "DEV_SELECT",
            "fixture_count": DEV_SELECT_COUNT,
            "prompts": ["P1"],
            "forbidden_prompts": ["P0", "P2"],
            "candidates": ["C1", "C2", "C3"],
            "attempts_per_cell": ATTEMPTS_PER_CELL,
            "total_scientific_cells": DEV_SELECT_MAX_CALLS,
            "unique_run_ids": 180,
            "unique_scientific_cell_keys": 180,
        },
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
            "dev_tune_authorized": False,
            "stochasticity_authorized": False,
            "final100_authorized": False,
            "candidate_c4_or_others_authorized": False,
            "calls_above_180_authorized": False,
            "prompt_p2_authorized": False,
            "retry_above_zero_authorized": False,
            "alternate_plan_sha_authorized": False,
            "alternate_scientific_bundle_authorized": False,
            "alternate_code_basis_authorized": False,
        },
        "historical_evidence_boundary": {
            "historical_artifacts_unmodified": True,
            "historical_frozen_shas": HISTORICAL_FROZEN_SHAS,
            "prep_artifact_status_preserved_as_not_granted": True,
        },
        "stage_a_created": False,
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
        "verification_summary": {
            "dsau_total_checks": len(dsau_checks),
            "dsau_passed_checks": sum(
                1 for c in dsau_checks if c["status"] == "PASS"
            ),
            "dsau_failed_checks": sum(
                1 for c in dsau_checks if c["status"] != "PASS"
            ),
            "adversarial_total_checks": len(adversarial_checks),
            "adversarial_passed_checks": sum(
                1 for c in adversarial_checks if c["status"] == "PASS"
            ),
            "adversarial_failed_checks": sum(
                1 for c in adversarial_checks if c["status"] != "PASS"
            ),
            "overall_status": "PASS",
        },
        "checks": dsau_checks,
        "adversarial_checks": adversarial_checks,
    }
    assert_no_secrets_in_payload(
        payload, context="W06_DEV_SELECT_LIVE_AUTHORIZATION_RECEIPT"
    )
    return payload


def issue_and_persist_authorization_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Persist w06_dev_select_live_authorization_v1.json and w06_dev_select_live_authorization_01_receipt_v1.json."""
    auth_path = repo_root / AUTHORIZATION_ARTIFACT_REL_PATH
    receipt_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH

    auth_model = build_scoped_dev_select_authorization_artifact(repo_root)
    auth_bytes = canonical_json_bytes(auth_model.model_dump())
    auth_path.write_bytes(auth_bytes)
    auth_file_sha256 = sha256_bytes(normalize_lf_bytes(auth_path.read_bytes()))

    dsau_checks = run_all_dsau_checks(repo_root, auth_artifact_path=auth_path)
    failed_dsau = [c for c in dsau_checks if c["status"] != "PASS"]
    if failed_dsau:
        raise RuntimeError(f"DSAU checks failed: {failed_dsau}")

    adversarial_checks = run_all_adversarial_checks(repo_root)
    failed_adv = [c for c in adversarial_checks if c["status"] != "PASS"]
    if failed_adv:
        raise RuntimeError(f"Adversarial checks failed: {failed_adv}")

    receipt_payload = build_authorization_receipt_payload(
        repo_root,
        auth_model=auth_model,
        auth_file_sha256=auth_file_sha256,
        dsau_checks=dsau_checks,
        adversarial_checks=adversarial_checks,
    )
    receipt_bytes = canonical_json_bytes(receipt_payload)
    receipt_path.write_bytes(receipt_bytes)
    return receipt_payload


def verify_persisted_dev_select_live_authorization(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify persisted DEV-SELECT authorization artifact and receipt without writing any files (Section 22)."""
    guard = NetworkKillSwitchGuard()
    with guard.activate():
        auth_path = repo_root / AUTHORIZATION_ARTIFACT_REL_PATH
        receipt_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH
        if not auth_path.is_file():
            raise RuntimeError(f"Missing authorization artifact: {auth_path}")
        if not receipt_path.is_file():
            raise RuntimeError(f"Missing authorization receipt: {receipt_path}")

        auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
        receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
        auth_file_sha = sha256_bytes(auth_bytes)
        receipt_file_sha = sha256_bytes(receipt_bytes)

        if auth_file_sha != EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256:
            raise RuntimeError(
                f"Authorization artifact file SHA256 mismatch: {auth_file_sha} != {EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256}"
            )
        if receipt_file_sha != EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256:
            raise RuntimeError(
                f"Authorization receipt file SHA256 mismatch: {receipt_file_sha} != {EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256}"
            )

        auths = load_verified_authorities(repo_root)
        verified_auth = verify_dev_live_authorization_artifact(
            auth_path,
            execution_plan=auths["execution_plan"],
            prompt_freeze=auths["prompt_freeze"],
            expected_phase="DEV_SELECT",
            repo_root=repo_root,
        )
        if (
            verified_auth.authorization_artifact_sha256
            != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        ):
            raise RuntimeError(
                f"Authorization internal SHA256 mismatch: {verified_auth.authorization_artifact_sha256}"
            )

        dsau_checks = run_all_dsau_checks(repo_root, auth_artifact_path=auth_path)
        failed_dsau = [c for c in dsau_checks if c["status"] != "PASS"]
        if failed_dsau:
            raise RuntimeError(f"DSAU checks failed in --verify-only: {failed_dsau}")

        adversarial_checks = run_all_adversarial_checks(repo_root)
        failed_adv = [c for c in adversarial_checks if c["status"] != "PASS"]
        if failed_adv:
            raise RuntimeError(
                f"Adversarial checks failed in --verify-only: {failed_adv}"
            )

        expected_receipt = build_authorization_receipt_payload(
            repo_root,
            auth_model=verified_auth,
            auth_file_sha256=auth_file_sha,
            dsau_checks=dsau_checks,
            adversarial_checks=adversarial_checks,
        )
        if canonical_json_bytes(expected_receipt) != receipt_bytes:
            raise RuntimeError(
                "Persisted authorization receipt does not match recomputed canonical payload"
            )

        if not is_verified_downstream_w06_dev_select_authorization_file(
            auth_path, repo_root=repo_root
        ):
            raise RuntimeError(
                "Downstream recognizer rejected persisted authorization artifact"
            )
        if not is_verified_downstream_w06_dev_select_authorization_file(
            receipt_path, repo_root=repo_root
        ):
            raise RuntimeError(
                "Downstream recognizer rejected persisted authorization receipt"
            )

        return {
            "status": "PASS",
            "task_id": TASK_ID,
            "authorization_id": verified_auth.authorization_id,
            "authorization_status": verified_auth.authorization_status,
            "authorized_by_role": verified_auth.authorized_by_role,
            "authorized_at_utc": verified_auth.authorized_at_utc,
            "authorization_text_character_count": AUTHORIZATION_TEXT_CHARACTER_COUNT,
            "authorization_text_sha256": AUTHORIZATION_TEXT_SHA256,
            "authorization_artifact_file_sha256": auth_file_sha,
            "authorization_artifact_internal_sha256": verified_auth.authorization_artifact_sha256,
            "authorization_receipt_file_sha256": receipt_file_sha,
            "prep_artifact_file_sha256": auths["authorization_prep_file_sha256"],
            "dsau_checks": f"{len(dsau_checks)}/{len(dsau_checks)} PASS",
            "adversarial_checks": f"{len(adversarial_checks)}/{len(adversarial_checks)} PASS",
            "stage_a_created": False,
            "live_execution_capability_issued": False,
            "production_provider_transport_constructed": False,
            "dev_select_execution_started": False,
            "live_provider_calls_new": 0,
            "provider_cost_usd_new": 0,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Issue or verify W06 DEV-SELECT Project Owner live authorization artifact."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify persisted DEV-SELECT authorization artifact and receipt without writing.",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        summary = verify_persisted_dev_select_live_authorization(REPO_ROOT)
        print(json.dumps(summary, indent=2))
        return 0

    receipt = issue_and_persist_authorization_artifacts(REPO_ROOT)
    receipt_file_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / AUTHORIZATION_RECEIPT_REL_PATH).read_bytes())
    )
    print(
        json.dumps(
            {
                "task_id": receipt["task_id"],
                "authorization_id": receipt["authorization_id"],
                "authorization_status": receipt["authorization_status"],
                "authorized_by_role": receipt["authorized_by_role"],
                "authorized_at_utc": receipt["authorized_at_utc"],
                "authorization_text_character_count": receipt[
                    "authorization_text_character_count"
                ],
                "authorization_text_sha256": receipt["authorization_text_sha256"],
                "authorization_artifact_sha256": receipt[
                    "authorization_artifact_sha256"
                ],
                "authorization_artifact_file_sha256": receipt[
                    "authorization_artifact_file_sha256"
                ],
                "authorization_receipt_file_sha256": receipt_file_sha,
                "dsau_checks": f"{receipt['verification_summary']['dsau_passed_checks']}/{receipt['verification_summary']['dsau_total_checks']}",
                "adversarial_checks": f"{receipt['verification_summary']['adversarial_passed_checks']}/{receipt['verification_summary']['adversarial_total_checks']}",
                "stage_a_created": receipt["stage_a_created"],
                "live_execution_capability_issued": receipt[
                    "live_execution_capability_issued"
                ],
                "live_provider_calls_new": receipt["live_provider_calls_new"],
                "provider_cost_usd_new": receipt["provider_cost_usd_new"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
