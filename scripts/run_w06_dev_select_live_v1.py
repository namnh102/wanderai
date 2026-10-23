#!/usr/bin/env python3
"""Operational launcher for the frozen W06 DEV-SELECT (locked prompt P1, 60 fixtures x 3 candidates = 180 cells) experiment.

TASK: W06-DEV-SELECT-LIVE-LAUNCHER-01-OFFLINE

PURPOSE:
Create a minimal, fail-closed frozen launcher for the already-authorized and committed
W06 DEV-SELECT 180-cell experiment without modifying `dev_live_runner.py` or
`dev_selection_harness.py` (preserving `SCIENTIFIC_CODE_BUNDLE_SHA256 =
0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`).

Why a dedicated launcher is required:
- The generic runner CLI (`dev_live_runner.run_cli`) defaults to the one-prompt P1
  infrastructure registry (`build_default_infrastructure_prompt_registry()`), whereas the
  committed production `DevPromptFreezeArtifact` (`w06_dev_prompt_candidate_freeze_v1.json`,
  SHA256 `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956`) binds the
  two-prompt frozen registry (`build_frozen_p1_p2_registry()`, SHA256
  `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6`).
- Simultaneously, the W06 DEV-SELECT experiment is locked to execute ONLY prompt `P1`
  (`096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11`) as selected in
  `w06_dev_tune_prompt_selection_v1.json` (`e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8`).
- Furthermore, generic `run_cli` accepts mutable path/phase CLI flags and `run_dev_live_runner_dry_run`
  calls `verify_stage_a_freeze_receipt(..., require_git_committed=False)` unless committed Stage-A
  verification is explicitly enforced by the launcher before dry-run completion.

Public modes:
1. `--preflight` (strictly offline, 0 provider calls, network kill-switch active)
2. `--execute-live --confirm-frozen-180-cells` (future live command only; NOT invoked in this task)
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Any, Callable, Iterator, Mapping, Sequence
import urllib.request

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation import dev_live_runner as _dlr_mod  # noqa: E402
from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_MODEL_BY_ID,
    RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
    STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
    TRANSPORT_STATUS_NOT_INVOKED,
    DevCallBudgetLedger,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    DevLiveStageAFreezeReceipt,
    ImmutableCellExecutionError,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    PromptFreezeFirewallError,
    StochasticityGateViolationError,
    assert_no_secrets_in_payload,
    compute_assigned_cells_sha256,
    compute_prompt_freeze_sha256,
    create_live_provider_transport_factory,
    execute_live_dev_batch,
    issue_live_execution_capability,
    reattest_stage_a_at_live_action_boundary,
    run_dev_live_runner_dry_run,
    verify_dev_live_authorization_artifact,
    verify_runner_prompt_freeze_artifact,
    verify_stage_a_freeze_receipt,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    CandidateRegistryIntegrityError,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    Final100FirewallViolationError,
    PromptRegistry,
    ScientificCodeBundleIntegrityError,
    assert_not_final100_path,
    assert_not_final100_scenario,
    assert_not_final100_scenario_id,
    build_deterministic_dev_scenario_context,
    canonical_json_bytes,
    compute_candidate_provider_config_sha256,
    compute_common_portable_generation_schema_sha256_v2,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    compute_semantic_schema_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
    verify_cell_manifest_for_execution,
    verify_dev_execution_plan_for_execution,
    verify_prompt_candidate_freeze_artifact,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
    P1_EXPECTED_SYSTEM_PROMPT_SHA256,
    P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
    build_frozen_p1_p2_registry,
    build_p1_spec,
)

try:
    import httpx2
except Exception as _httpx2_exc:  # pragma: no cover
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_MISSING: Frozen package 'httpx2' is required for W06 DEV-SELECT launcher."
    ) from _httpx2_exc

if getattr(httpx2, "__name__", None) != "httpx2" or httpx2 is httpx:
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_ALIAS_ERROR: 'httpx2' must be the actual installed httpx2 package, not an alias of httpx."
    )


# ==============================================================================
# 1. FROZEN EXPERIMENT CONSTANTS & HARD-LOCKED AUTHORITIES (SECTIONS 1..18)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-LIVE-LAUNCHER-01-OFFLINE"
BASE_DEVELOP_SHA = "681510af0e9232bae318562cf115e2ff4ce05968"
BRANCH_NAME = "research/w06-dev-select-live-launcher-01"
LAUNCHER_REL_PATH = "scripts/run_w06_dev_select_live_v1.py"

FROZEN_PHASE = "DEV_SELECT"
FROZEN_CANDIDATE_IDS: tuple[str, ...] = ("C1", "C2", "C3")
FROZEN_SELECTED_PROMPT_ID = "P1"
FROZEN_PLAN_PROMPT_IDS: tuple[str, ...] = ("P1",)
FORBIDDEN_PROMPT_IDS_IN_DEV_SELECT: tuple[str, ...] = ("P0", "P2")
FROZEN_FIXTURE_COUNT = 60
FROZEN_CELL_COUNT = 180
FROZEN_UNIQUE_RUN_IDS = 180
FROZEN_ATTEMPTS_PER_CELL = 1
FROZEN_MAXIMUM_CALLS = 180
FROZEN_RETRY_POLICY = 0

FROZEN_REQUESTED_MODEL_BY_CANDIDATE: dict[str, str] = {
    "C1": "gemini-3.8-flash",
    "C2": "gpt-6.1-sol",
    "C3": "claude-sonnet-5-5",
}

FROZEN_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
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

EXECUTION_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
EXPECTED_EXECUTION_PLAN_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_EXECUTION_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)

PLAN_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json"
)
EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256 = (
    "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
)

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)

DEV_TUNE_EXECUTION_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)

PROMPT_SELECTION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256 = (
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256 = (
    "1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570"
)

AUTHORIZATION_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_authorization_prep_v1.json"
)
EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8"
)

AUTHORIZATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_authorization_v1.json"
)
EXPECTED_AUTHORIZATION_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
)

AUTHORIZATION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_authorization_01_receipt_v1.json"
)
EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256 = (
    "cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39"
)
EXPECTED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256 = (
    "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
)

STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json"
)
EXPECTED_STAGE_A_FILE_SHA256 = (
    "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
)
EXPECTED_STAGE_A_INTERNAL_SHA256 = (
    "1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014"
)

TASK_AUDIT_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_stage_a_freeze_01_receipt_v1.json"
)
EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256 = (
    "73eb38335f6fa0d21f9f38f0e15f9dc2c6497c46519a784b0d4e3df7da6a64c5"
)

EXPECTED_ASSIGNED_CELLS_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_CODE_BASIS_COMMIT_SHA = "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
EXPECTED_STAGE_A_COMMIT_SHA = "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)

EXPECTED_PREFLIGHT_REQUEST_SET_SHA256 = (
    "3ef997b8833399095b9bf5953ae200d45dd85acb7b253c5b6975adf1b01667e2"
)
EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = (
    "2a058ebd180cf3fe557549f5d2d3eff66d72f5320155b0e73bbb6b31f412d544"
)

FROZEN_LIVE_OUTPUT_ROOT_REL_PATH = (
    "data/evaluation/w06/live_dev_select_primary_v1"
)
FUTURE_LIVE_COMMAND = (
    "python scripts/run_w06_dev_select_live_v1.py --execute-live --confirm-frozen-180-cells"
)

REQUIRED_ENV_KEYS: tuple[str, str, str] = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)

EXPECTED_RUNTIME_SDK_VERSIONS: dict[str, str] = {
    "PYTHON_VERSION": "3.11.9",
    "GOOGLE_GENAI_VERSION": "2.25.0",
    "OPENAI_VERSION": "3.17.0",
    "ANTHROPIC_VERSION": "1.15.0",
    "HTTPX_VERSION": "0.28.1",
    "HTTPX2_VERSION": "2.13.0",
}

FORBIDDEN_CLI_OVERRIDE_PREFIXES: tuple[str, ...] = (
    "--execute",
    "--force",
    "--retry",
    "--max-retries",
    "--resume",
    "--rerun",
    "--best-of",
    "--skip-stage-a",
    "--skip-authorization",
    "--ignore-hash",
    "--change-prompt",
    "--prompt",
    "--prompts",
    "--candidate",
    "--candidates",
    "--fixture",
    "--fixtures",
    "--phase",
    "--execution-plan",
    "--prompt-freeze",
    "--authorization",
    "--authorization-artifact",
    "--stage-a",
    "--stage-a-freeze-receipt",
    "--batch-root",
    "--batch-root-dir",
    "--output-root",
    "--output-dir",
    "--cell",
    "--cells",
    "--max-calls",
    "--overwrite",
    "--clean",
    "--confirm-frozen-120-cells",
    "--dev-tune",
    "--stochasticity",
)


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH & SECRET-FREE KEY / SDK CHECKS (SECTIONS 16, 17, 28)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline preflight."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound network calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    def __enter__(self) -> "NetworkKillSwitchGuard":
        self._orig_connect = socket.socket.connect
        self._orig_connect_ex = socket.socket.connect_ex
        self._orig_create_conn = socket.create_connection
        self._orig_urlopen = urllib.request.urlopen
        self._orig_httpx_send = httpx.Client.send
        self._orig_httpx_async_send = httpx.AsyncClient.send
        self._orig_httpx_transport = httpx.HTTPTransport.handle_request
        self._orig_httpx_async_transport = httpx.AsyncHTTPTransport.handle_async_request
        self._orig_httpx2_send = httpx2.Client.send
        self._orig_httpx2_async_send = httpx2.AsyncClient.send
        self._orig_httpx2_transport = (
            httpx2.HTTPTransport.handle_request
            if hasattr(httpx2, "HTTPTransport")
            else None
        )
        self._orig_httpx2_async_transport = (
            httpx2.AsyncHTTPTransport.handle_async_request
            if hasattr(httpx2, "AsyncHTTPTransport")
            else None
        )

        def _deny(label: str) -> Any:
            def _raiser(*_a: Any, **_kw: Any) -> Any:
                self.blocked_attempts.append(label)
                raise OutboundNetworkBlockedError(
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID} preflight."
                )

            return _raiser

        socket.socket.connect = _deny("socket.socket.connect")  # type: ignore[method-assign]
        socket.socket.connect_ex = _deny("socket.socket.connect_ex")  # type: ignore[method-assign]
        socket.create_connection = _deny("socket.create_connection")  # type: ignore[assignment]
        urllib.request.urlopen = _deny("urllib.request.urlopen")  # type: ignore[assignment]
        httpx.Client.send = _deny("httpx.Client.send")  # type: ignore[method-assign]
        httpx.AsyncClient.send = _deny("httpx.AsyncClient.send")  # type: ignore[method-assign]
        httpx.HTTPTransport.handle_request = _deny(  # type: ignore[method-assign]
            "httpx.HTTPTransport.handle_request"
        )
        httpx.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
            "httpx.AsyncHTTPTransport.handle_async_request"
        )
        httpx2.Client.send = _deny("httpx2.Client.send")  # type: ignore[method-assign]
        httpx2.AsyncClient.send = _deny("httpx2.AsyncClient.send")  # type: ignore[method-assign]
        if hasattr(httpx2, "HTTPTransport"):
            httpx2.HTTPTransport.handle_request = _deny(  # type: ignore[method-assign]
                "httpx2.HTTPTransport.handle_request"
            )
        if hasattr(httpx2, "AsyncHTTPTransport"):
            httpx2.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
                "httpx2.AsyncHTTPTransport.handle_async_request"
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.socket.connect = self._orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._orig_create_conn  # type: ignore[assignment]
        urllib.request.urlopen = self._orig_urlopen  # type: ignore[assignment]
        httpx.Client.send = self._orig_httpx_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = self._orig_httpx_async_send  # type: ignore[method-assign]
        httpx.HTTPTransport.handle_request = self._orig_httpx_transport  # type: ignore[method-assign]
        httpx.AsyncHTTPTransport.handle_async_request = (  # type: ignore[method-assign]
            self._orig_httpx_async_transport
        )
        httpx2.Client.send = self._orig_httpx2_send  # type: ignore[method-assign]
        httpx2.AsyncClient.send = self._orig_httpx2_async_send  # type: ignore[method-assign]
        if (
            hasattr(httpx2, "HTTPTransport")
            and self._orig_httpx2_transport is not None
        ):
            httpx2.HTTPTransport.handle_request = self._orig_httpx2_transport  # type: ignore[method-assign]
        if (
            hasattr(httpx2, "AsyncHTTPTransport")
            and self._orig_httpx2_async_transport is not None
        ):
            httpx2.AsyncHTTPTransport.handle_async_request = (  # type: ignore[method-assign]
                self._orig_httpx2_async_transport
            )

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        with self:
            yield self


def check_key_presence_status_only(
    repo_root: Path = REPO_ROOT,
    *,
    env_override: Mapping[str, str] | None = None,
    include_dotenv_files: bool = True,
) -> dict[str, str]:
    """Return ONLY 'PRESENT' or 'MISSING' for GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY (Section 16).

    Never returns, prints, logs, or hashes secret key values, prefixes, suffixes, or lengths.
    """
    present_keys: set[str] = set()
    env_map = env_override if env_override is not None else os.environ
    for k in REQUIRED_ENV_KEYS:
        val = env_map.get(k, "")
        if isinstance(val, str) and len(val.strip()) > 0:
            present_keys.add(k)

    if include_dotenv_files and env_override is None:
        for dotenv_path in (
            repo_root / "apps" / "ai-service" / ".env",
            repo_root / ".env",
        ):
            if dotenv_path.is_file():
                try:
                    for raw_line in dotenv_path.read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines():
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k_part, v_part = line.split("=", 1)
                        k_clean = k_part.strip()
                        v_clean = v_part.strip().strip("'").strip('"').strip()
                        if k_clean in REQUIRED_ENV_KEYS and len(v_clean) > 0:
                            present_keys.add(k_clean)
                except Exception:
                    pass

    return {
        k: ("PRESENT" if k in present_keys else "MISSING") for k in REQUIRED_ENV_KEYS
    }


def check_runtime_sdk_versions(
    *,
    versions_override: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify and report runtime Python and SDK versions against frozen expectations (Section 17)."""
    if versions_override is not None:
        observed = {k: str(v) for k, v in versions_override.items()}
    else:
        pkg_map = {
            "GOOGLE_GENAI_VERSION": "google-genai",
            "OPENAI_VERSION": "openai",
            "ANTHROPIC_VERSION": "anthropic",
            "HTTPX_VERSION": "httpx",
            "HTTPX2_VERSION": "httpx2",
        }
        observed = {"PYTHON_VERSION": platform.python_version()}
        for key, pkg_name in pkg_map.items():
            try:
                observed[key] = importlib.metadata.version(pkg_name)
            except Exception:
                observed[key] = "NOT_INSTALLED"

    drifted_keys = [
        k
        for k, exp_val in EXPECTED_RUNTIME_SDK_VERSIONS.items()
        if observed.get(k) != exp_val
    ]
    drift_detected = len(drifted_keys) > 0
    return {
        "observed_versions": observed,
        "expected_frozen_versions": dict(EXPECTED_RUNTIME_SDK_VERSIONS),
        "environment_version_drift": drift_detected,
        "drifted_components": drifted_keys,
        "runtime_sdk_status": (
            "ENVIRONMENT_VERSION_DRIFT" if drift_detected else "READY"
        ),
        "pre_flight_ready": not drift_detected,
    }


# ==============================================================================
# 3. SOURCE DEVELOP PROVENANCE & COMMITTED STAGE-A VERIFICATION (SECTIONS 1, 6, 7)
# ==============================================================================


def verify_source_develop_provenance(
    repo_root: Path = REPO_ROOT,
    *,
    expected_source_sha: str = BASE_DEVELOP_SHA,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Fail-closed verification that BASE_DEVELOP_SHA (`681510af0e9232bae318562cf115e2ff4ce05968`) is an ancestor of HEAD (with shallow CI fallback)."""
    if expected_source_sha != BASE_DEVELOP_SHA:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_BASE_DEVELOP_SHA: expected={BASE_DEVELOP_SHA!r}, got={expected_source_sha!r}"
        )

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
        ["git", "cat-file", "-e", f"{BASE_DEVELOP_SHA}^{{commit}}"]
    )
    if exists_proc.returncode == 0:
        anc_proc = _run_git(
            ["git", "merge-base", "--is-ancestor", BASE_DEVELOP_SHA, "HEAD"]
        )
        is_ancestor = anc_proc.returncode == 0
        if not is_ancestor:
            raise PlanBeforeLiveProtocolError(
                f"SOURCE_DEVELOP_NOT_ANCESTOR_OF_HEAD: {BASE_DEVELOP_SHA} is not an ancestor of HEAD."
            )
        return {
            "base_develop_sha": BASE_DEVELOP_SHA,
            "commit_exists_in_local_git": True,
            "is_ancestor_of_head": True,
            "is_shallow_repository": False,
            "shallow_repository_fallback_used": False,
            "verified": True,
        }

    shallow_proc = _run_git(["git", "rev-parse", "--is-shallow-repository"])
    is_shallow = (
        shallow_proc.returncode == 0
        and shallow_proc.stdout.strip().lower() == "true"
    )
    if not is_shallow:
        raise PlanBeforeLiveProtocolError(
            f"SOURCE_DEVELOP_MISSING_IN_NON_SHALLOW_REPO: {BASE_DEVELOP_SHA} not found in non-shallow repository."
        )

    def _file_sha(rel_path: str) -> str:
        p = repo_root / rel_path
        return sha256_bytes(normalize_lf_bytes(p.read_bytes())) if p.is_file() else ""

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    fallback_checks = {
        "execution_plan_file_sha256": (
            _file_sha(EXECUTION_PLAN_REL_PATH) == EXPECTED_EXECUTION_PLAN_FILE_SHA256
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
        "authorization_file_sha256": (
            _file_sha(AUTHORIZATION_REL_PATH) == EXPECTED_AUTHORIZATION_FILE_SHA256
        ),
        "stage_a_file_sha256": (
            _file_sha(STAGE_A_RECEIPT_REL_PATH) == EXPECTED_STAGE_A_FILE_SHA256
        ),
        "task_audit_receipt_file_sha256": (
            _file_sha(TASK_AUDIT_RECEIPT_REL_PATH)
            == EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256
        ),
        "scientific_code_bundle_sha256": (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ),
    }
    if not all(fallback_checks.values()):
        raise PlanBeforeLiveProtocolError(
            f"SHALLOW_REPO_AUTHORITY_MISMATCH: {fallback_checks}"
        )
    return {
        "base_develop_sha": BASE_DEVELOP_SHA,
        "commit_exists_in_local_git": False,
        "is_ancestor_of_head": True,
        "is_shallow_repository": True,
        "shallow_repository_fallback_used": True,
        "fallback_authorities_matched": fallback_checks,
        "verified": True,
    }


_ORIG_VERIFY_STAGE_A_FREEZE_RECEIPT = _dlr_mod.verify_stage_a_freeze_receipt


def verify_committed_stage_a_for_launcher(
    stage_a_path: Any,
    *,
    execution_plan: Any,
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    execution_plan_path: Path | None = None,
    prompt_freeze_path: Path | None = None,
    authorization_path: Path | None = None,
    candidate_registry: Any = None,
    repo_root: Path | None = REPO_ROOT,
    require_git_committed: bool = True,
) -> DevLiveStageAFreezeReceipt:
    """Invoke production `verify_stage_a_freeze_receipt(..., require_git_committed=True)` with explicit paths (Section 7).

    Always invokes `verify_stage_a_freeze_receipt(..., require_git_committed=True)` first.
    If and only if running in a shallow CI checkout (`git rev-parse --is-shallow-repository == true`)
    where historical ancestor commit objects (`STAGE_A_COMMIT_SHA` / `CODE_BASIS_COMMIT_SHA`) are not
    in the shallow object database, enforces git tracking (`git ls-files --error-unmatch`),
    clean working tree (`git status --porcelain`), and `git show HEAD:<path>` blob attestation
    across all Stage-A and scientific bundle files so uncommitted or dirty Stage-A files NEVER pass.
    """
    eff_root = repo_root if repo_root is not None else REPO_ROOT
    if not require_git_committed:
        return _ORIG_VERIFY_STAGE_A_FREEZE_RECEIPT(
            stage_a_path,
            execution_plan=execution_plan,
            prompt_freeze=prompt_freeze,
            authorization=authorization,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            candidate_registry=candidate_registry,
            repo_root=eff_root,
            require_git_committed=False,
        )

    try:
        return _ORIG_VERIFY_STAGE_A_FREEZE_RECEIPT(
            stage_a_path,
            execution_plan=execution_plan,
            prompt_freeze=prompt_freeze,
            authorization=authorization,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            candidate_registry=candidate_registry,
            repo_root=eff_root,
            require_git_committed=True,
        )
    except PlanBeforeLiveProtocolError as exc:
        if "STAGE_A_COMMIT_NOT_FOUND_IN_REPO" not in str(exc):
            raise
        shallow_proc = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=str(eff_root),
            capture_output=True,
            text=True,
            check=False,
        )
        is_shallow = (
            shallow_proc.returncode == 0
            and shallow_proc.stdout.strip().lower() == "true"
        )
        if not is_shallow:
            raise

    if (
        execution_plan_path is None
        or prompt_freeze_path is None
        or authorization_path is None
        or not isinstance(stage_a_path, (Path, str))
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_PATHS_REQUIRED_FOR_GIT_ATTESTATION: Live Stage-A verification requires on-disk paths."
        )
    stage_a_p = Path(stage_a_path)

    verify_source_develop_provenance(repo_root=eff_root)
    receipt = _ORIG_VERIFY_STAGE_A_FREEZE_RECEIPT(
        stage_a_p,
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        authorization=authorization,
        execution_plan_path=execution_plan_path,
        prompt_freeze_path=prompt_freeze_path,
        authorization_path=authorization_path,
        candidate_registry=candidate_registry,
        repo_root=eff_root,
        require_git_committed=False,
    )
    if (
        receipt.stage_a_commit_sha != EXPECTED_STAGE_A_COMMIT_SHA
        or receipt.code_basis_commit_sha != EXPECTED_CODE_BASIS_COMMIT_SHA
    ):
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_COMMIT_MISMATCH: stage_a={receipt.stage_a_commit_sha}, basis={receipt.code_basis_commit_sha}"
        )

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(eff_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tracked_paths = [
        execution_plan_path,
        prompt_freeze_path,
        authorization_path,
        stage_a_p,
        *[eff_root / p for p in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS],
    ]
    for fpath in tracked_paths:
        try:
            rel_posix = fpath.resolve().relative_to(eff_root.resolve()).as_posix()
        except ValueError as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_ARTIFACT_OUTSIDE_REPO: {fpath} is outside repository root {eff_root}."
            ) from exc
        ls_proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_posix],
            cwd=str(eff_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if ls_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_ARTIFACT_UNCOMMITTED: Stage-A file {rel_posix} is untracked in git."
            )
        st_proc = subprocess.run(
            ["git", "status", "--porcelain", "--", rel_posix],
            cwd=str(eff_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if st_proc.returncode != 0 or st_proc.stdout.strip():
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_FILE_DIRTY_OR_UNCOMMITTED: Stage-A file {rel_posix} has uncommitted changes."
            )
        disk_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        show_proc = subprocess.run(
            ["git", "show", f"{head_sha}:{rel_posix}"],
            cwd=str(eff_root),
            capture_output=True,
            check=False,
        )
        if show_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_BLOB_MISSING_IN_COMMIT: {rel_posix} not found in commit {head_sha}."
            )
        blob_sha = sha256_bytes(normalize_lf_bytes(show_proc.stdout))
        if blob_sha != disk_sha:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_COMMITTED_BLOB_MISMATCH: {rel_posix} at {head_sha}."
            )
    return receipt


verify_stage_a_freeze_receipt = verify_committed_stage_a_for_launcher


# ==============================================================================
# 4. FAIL-CLOSED AUTHORITY, REGISTRY, P1-LOCK & OUTPUT-ROOT VERIFICATION
# ==============================================================================

_ORIG_VERIFY_RUNNER_PROMPT_FREEZE_ARTIFACT = _dlr_mod.verify_runner_prompt_freeze_artifact


def verify_dev_select_runner_prompt_freeze_artifact(
    prompt_freeze: Any,
    *,
    prompt_registry: PromptRegistry,
    execution_plan: Any,
    dev_bundle: Any = None,
    candidate_registry: Any = None,
    repo_root: Path | None = None,
) -> DevPromptFreezeArtifact:
    """Verify `DevPromptFreezeArtifact` for `DEV_SELECT` against the committed frozen `w06_dev_tune_execution_plan_v1.json`."""
    if (
        isinstance(execution_plan, DevExecutionPlan)
        and execution_plan.phase == FROZEN_PHASE
        and execution_plan.plan_sha256 == EXPECTED_EXECUTION_PLAN_SHA256
    ):
        if prompt_freeze is None:
            raise PromptFreezeFirewallError(
                "PROMPT_FREEZE_MISSING: Live/runner execution requires a verified DevPromptFreezeArtifact."
            )
        pf_arg: Any = Path(prompt_freeze) if isinstance(prompt_freeze, str) else prompt_freeze
        if isinstance(pf_arg, Path):
            assert_not_final100_path(pf_arg)

        bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
        cand_reg = candidate_registry or load_and_verify_candidate_registry()
        eff_root = repo_root if repo_root is not None else REPO_ROOT
        dev_tune_plan_path = eff_root / DEV_TUNE_EXECUTION_PLAN_REL_PATH
        if not dev_tune_plan_path.is_file():
            dev_tune_plan_path = REPO_ROOT / DEV_TUNE_EXECUTION_PLAN_REL_PATH
        if not dev_tune_plan_path.is_file():
            raise PromptFreezeFirewallError(
                f"DEV_TUNE_EXECUTION_PLAN_MISSING_FOR_PROMPT_FREEZE_VERIFICATION: {dev_tune_plan_path}"
            )
        dt_bytes = normalize_lf_bytes(dev_tune_plan_path.read_bytes())
        dt_file_sha = sha256_bytes(dt_bytes)
        if dt_file_sha != EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256:
            raise PromptFreezeFirewallError(
                f"DEV_TUNE_EXECUTION_PLAN_FILE_SHA256_MISMATCH: expected={EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256}, got={dt_file_sha}"
            )
        dev_tune_plan_model = DevExecutionPlan.model_validate_json(dt_bytes)
        if dev_tune_plan_model.plan_sha256 != EXPECTED_DEV_TUNE_EXECUTION_PLAN_SHA256:
            raise PromptFreezeFirewallError(
                f"DEV_TUNE_EXECUTION_PLAN_SHA256_MISMATCH: expected={EXPECTED_DEV_TUNE_EXECUTION_PLAN_SHA256}, got={dev_tune_plan_model.plan_sha256}"
            )
        verify_dev_execution_plan_for_execution(
            dev_tune_plan_model, candidate_registry=cand_reg, repo_root=repo_root
        )
        return verify_prompt_candidate_freeze_artifact(
            pf_arg,
            prompt_registry=prompt_registry,
            dev_tune_plan=dev_tune_plan_model,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            repo_root=repo_root,
        )

    return _ORIG_VERIFY_RUNNER_PROMPT_FREEZE_ARTIFACT(
        prompt_freeze,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=dev_bundle,
        candidate_registry=candidate_registry,
        repo_root=repo_root,
    )


verify_runner_prompt_freeze_artifact = verify_dev_select_runner_prompt_freeze_artifact


@contextlib.contextmanager
def _launcher_runner_bridge() -> Iterator[None]:
    """Scope Stage-A commit enforcement and DEV_SELECT prompt-freeze bridge strictly to launcher execution."""
    prev_stage_a = _dlr_mod.verify_stage_a_freeze_receipt
    prev_pf = _dlr_mod.verify_runner_prompt_freeze_artifact
    _dlr_mod.verify_stage_a_freeze_receipt = verify_committed_stage_a_for_launcher
    _dlr_mod.verify_runner_prompt_freeze_artifact = (
        verify_dev_select_runner_prompt_freeze_artifact
    )
    try:
        yield
    finally:
        _dlr_mod.verify_stage_a_freeze_receipt = prev_stage_a
        _dlr_mod.verify_runner_prompt_freeze_artifact = prev_pf


def load_and_verify_frozen_prompt_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Load the frozen P1+P2 PromptRegistry (for prompt-freeze verification) and verify that DEV-SELECT locks P1 ONLY (Section 4)."""
    registry: PromptRegistry = build_frozen_p1_p2_registry()
    if registry.registry_sha256 != FROZEN_PROMPT_REGISTRY_SHA256:
        raise PromptFreezeFirewallError(
            f"FROZEN_PROMPT_REGISTRY_SHA256_MISMATCH: expected={FROZEN_PROMPT_REGISTRY_SHA256}, "
            f"got={registry.registry_sha256}"
        )

    p1_spec = build_p1_spec()
    p1_system_sha256 = sha256_bytes(
        normalize_lf_bytes(p1_spec.system_prompt.encode("utf-8"))
    )
    p1_user_template_sha256 = sha256_bytes(
        normalize_lf_bytes(p1_spec.user_prompt_template.encode("utf-8"))
    )
    if (
        p1_spec.prompt_id != FROZEN_SELECTED_PROMPT_ID
        or p1_spec.semantic_prompt_sha256 != EXPECTED_P1_SEMANTIC_SHA256
        or p1_system_sha256 != EXPECTED_P1_SYSTEM_PROMPT_SHA256
        or p1_user_template_sha256 != EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
        or P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256 != EXPECTED_P1_SEMANTIC_SHA256
        or P1_EXPECTED_SYSTEM_PROMPT_SHA256 != EXPECTED_P1_SYSTEM_PROMPT_SHA256
        or P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256
        != EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
    ):
        raise PromptFreezeFirewallError(
            "LOCKED_P1_PROMPT_AUTHORITY_MISMATCH: P1 specification hashes do not match frozen DEV-SELECT P1 authorities."
        )

    ps_path = repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
    if not ps_path.is_file():
        raise PromptFreezeFirewallError(
            f"PROMPT_SELECTION_ARTIFACT_MISSING: {ps_path}"
        )
    ps_bytes = normalize_lf_bytes(ps_path.read_bytes())
    ps_file_sha = sha256_bytes(ps_bytes)
    if ps_file_sha != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256:
        raise PromptFreezeFirewallError(
            f"PROMPT_SELECTION_ARTIFACT_FILE_SHA256_MISMATCH: expected={EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256}, got={ps_file_sha}"
        )
    ps_obj = json.loads(ps_bytes.decode("utf-8"))
    if (
        ps_obj.get("selected_prompt_id") != FROZEN_SELECTED_PROMPT_ID
        or ps_obj.get("selected_prompt_semantic_sha256") != EXPECTED_P1_SEMANTIC_SHA256
        or ps_obj.get("selected_prompt_system_sha256")
        != EXPECTED_P1_SYSTEM_PROMPT_SHA256
        or ps_obj.get("selected_prompt_user_template_sha256")
        != EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
        or ps_obj.get("prompt_selection_artifact_sha256")
        != EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
    ):
        raise PromptFreezeFirewallError(
            "PROMPT_SELECTION_CONTENT_MISMATCH: Prompt selection artifact does not lock P1 with exact expected hashes."
        )

    return {
        "prompt_registry": registry,
        "p1_spec": p1_spec,
        "prompt_selection_path": ps_path,
        "prompt_selection_file_sha256": ps_file_sha,
        "prompt_selection_obj": ps_obj,
    }


def verify_output_root_not_existing(repo_root: Path = REPO_ROOT) -> Path:
    """Verify that the frozen live output root `data/evaluation/w06/live_dev_select_primary_v1` does not already exist (Section 14)."""
    output_root = repo_root / FROZEN_LIVE_OUTPUT_ROOT_REL_PATH
    assert_not_final100_path(output_root)
    if output_root.exists():
        raise PlanBeforeLiveProtocolError(
            f"LIVE_OUTPUT_ROOT_ALREADY_EXISTS: {output_root} already exists. "
            "Resume, overwrite, and automatic cleanup are strictly forbidden."
        )
    return output_root


def verify_frozen_launcher_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify source develop provenance, scientific bundle, schemas, registries, plan, P1 prompt, authorization, committed Stage-A, and output root."""
    if LAUNCHER_REL_PATH in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        raise ScientificCodeBundleIntegrityError(
            f"LAUNCHER_IN_SCIENTIFIC_BUNDLE_FORBIDDEN: {LAUNCHER_REL_PATH} must remain outside SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS."
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: expected={EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got={bundle_sha}"
        )

    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    pconf_reg_sha = compute_provider_config_registry_sha256(cand_reg)
    portable_schema_sha = compute_common_portable_generation_schema_sha256_v2()
    semantic_schema_sha = compute_semantic_schema_sha256()

    if cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256:
        raise CandidateRegistryIntegrityError(
            f"CANDIDATE_REGISTRY_SHA256_MISMATCH: expected={EXPECTED_CANDIDATE_REGISTRY_SHA256}, got={cand_reg.registry_sha256}"
        )
    if pconf_reg_sha != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256:
        raise CandidateRegistryIntegrityError(
            f"PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH: expected={EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256}, got={pconf_reg_sha}"
        )
    if (
        portable_schema_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        or semantic_schema_sha != EXPECTED_SEMANTIC_SCHEMA_SHA256
    ):
        raise CandidateRegistryIntegrityError(
            f"SCHEMA_AUTHORITY_MISMATCH: portable={portable_schema_sha}, semantic={semantic_schema_sha}"
        )

    for cid, exp_model in FROZEN_REQUESTED_MODEL_BY_CANDIDATE.items():
        if CANDIDATE_MODEL_BY_ID.get(cid) != exp_model:
            raise CandidateRegistryIntegrityError(
                f"CANDIDATE_MODEL_ID_MISMATCH for {cid}: expected={exp_model}, got={CANDIDATE_MODEL_BY_ID.get(cid)}"
            )

    prompt_auth = load_and_verify_frozen_prompt_authorities(repo_root=repo_root)
    prompt_reg: PromptRegistry = prompt_auth["prompt_registry"]

    plan_path = repo_root / EXECUTION_PLAN_REL_PATH
    plan_rec_path = repo_root / PLAN_FREEZE_RECEIPT_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    prep_path = repo_root / AUTHORIZATION_PREP_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH
    auth_rec_path = repo_root / AUTHORIZATION_RECEIPT_REL_PATH
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    task_audit_path = repo_root / TASK_AUDIT_RECEIPT_REL_PATH

    for req_path, label in (
        (plan_path, "EXECUTION_PLAN_MISSING"),
        (plan_rec_path, "PLAN_FREEZE_RECEIPT_MISSING"),
        (pf_path, "PROMPT_FREEZE_MISSING"),
        (prep_path, "AUTHORIZATION_PREP_MISSING"),
        (auth_path, "AUTHORIZATION_MISSING"),
        (auth_rec_path, "AUTHORIZATION_RECEIPT_MISSING"),
        (stage_a_path, "STAGE_A_RECEIPT_MISSING"),
        (task_audit_path, "STAGE_A_TASK_AUDIT_RECEIPT_MISSING"),
    ):
        if not req_path.is_file():
            if "AUTHORIZATION" in label and "PREP" not in label:
                raise DevLiveAuthorizationError(f"{label}: {req_path}")
            if "PROMPT" in label:
                raise PromptFreezeFirewallError(f"{label}: {req_path}")
            raise PlanBeforeLiveProtocolError(f"{label}: {req_path}")

    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    plan_rec_bytes = normalize_lf_bytes(plan_rec_path.read_bytes())
    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    prep_bytes = normalize_lf_bytes(prep_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    auth_rec_bytes = normalize_lf_bytes(auth_rec_path.read_bytes())
    stage_a_bytes = normalize_lf_bytes(stage_a_path.read_bytes())
    task_audit_bytes = normalize_lf_bytes(task_audit_path.read_bytes())

    plan_file_sha = sha256_bytes(plan_bytes)
    plan_rec_file_sha = sha256_bytes(plan_rec_bytes)
    pf_file_sha = sha256_bytes(pf_bytes)
    prep_file_sha = sha256_bytes(prep_bytes)
    auth_file_sha = sha256_bytes(auth_bytes)
    auth_rec_file_sha = sha256_bytes(auth_rec_bytes)
    stage_a_file_sha = sha256_bytes(stage_a_bytes)
    task_audit_file_sha = sha256_bytes(task_audit_bytes)

    if plan_file_sha != EXPECTED_EXECUTION_PLAN_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_FILE_SHA256_MISMATCH: expected={EXPECTED_EXECUTION_PLAN_FILE_SHA256}, got={plan_file_sha}"
        )
    if plan_rec_file_sha != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PLAN_FREEZE_RECEIPT_FILE_SHA256_MISMATCH: expected={EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256}, got={plan_rec_file_sha}"
        )
    if pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PromptFreezeFirewallError(
            f"PROMPT_FREEZE_FILE_SHA256_MISMATCH: expected={EXPECTED_PROMPT_FREEZE_SHA256}, got={pf_file_sha}"
        )
    if prep_file_sha != EXPECTED_PREP_ARTIFACT_FILE_SHA256:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PREP_FILE_SHA256_MISMATCH: expected={EXPECTED_PREP_ARTIFACT_FILE_SHA256}, got={prep_file_sha}"
        )
    if auth_file_sha != EXPECTED_AUTHORIZATION_FILE_SHA256:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_FILE_SHA256_MISMATCH: expected={EXPECTED_AUTHORIZATION_FILE_SHA256}, got={auth_file_sha}"
        )
    if auth_rec_file_sha != EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_RECEIPT_FILE_SHA256_MISMATCH: expected={EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256}, got={auth_rec_file_sha}"
        )
    if stage_a_file_sha != EXPECTED_STAGE_A_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_FILE_SHA256_MISMATCH: expected={EXPECTED_STAGE_A_FILE_SHA256}, got={stage_a_file_sha}"
        )
    if task_audit_file_sha != EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_TASK_AUDIT_RECEIPT_SHA256_MISMATCH: expected={EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256}, got={task_audit_file_sha}"
        )

    auth_rec_obj = json.loads(auth_rec_bytes.decode("utf-8"))
    if (
        auth_rec_obj.get("authorization_text_sha256")
        != EXPECTED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
    ):
        raise DevLiveAuthorizationError(
            "PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256_MISMATCH"
        )

    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
    pf_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    auth_model = DevLiveAuthorizationArtifact.model_validate_json(auth_bytes)
    stage_a_model = DevLiveStageAFreezeReceipt.model_validate_json(stage_a_bytes)

    if plan_model.plan_sha256 != EXPECTED_EXECUTION_PLAN_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_SHA256_MISMATCH: expected={EXPECTED_EXECUTION_PLAN_SHA256}, got={plan_model.plan_sha256}"
        )

    expected_fixture_ids = tuple(
        f"W06-DEV-SELECT-{i:03d}" for i in range(1, FROZEN_FIXTURE_COUNT + 1)
    )
    observed_fixture_ids = tuple(sorted({c.fixture_id for c in plan_model.cells}))
    run_ids = [c.run_id for c in plan_model.cells]
    if (
        plan_model.phase != FROZEN_PHASE
        or tuple(plan_model.candidate_ids) != FROZEN_CANDIDATE_IDS
        or tuple(plan_model.prompt_ids) != FROZEN_PLAN_PROMPT_IDS
        or plan_model.fixture_count != FROZEN_FIXTURE_COUNT
        or observed_fixture_ids != expected_fixture_ids
        or plan_model.expected_total_cells != FROZEN_CELL_COUNT
        or len(plan_model.cells) != FROZEN_CELL_COUNT
        or len(set(run_ids)) != FROZEN_UNIQUE_RUN_IDS
        or plan_model.code_basis_commit_sha != EXPECTED_CODE_BASIS_COMMIT_SHA
        or plan_model.scientific_code_bundle_sha256
        != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "EXECUTION_PLAN_SCOPE_LOCK_MISMATCH: Plan does not match hard-locked DEV_SELECT 60-fixture P1 C1/C2/C3 180-cell scope."
        )

    for cell in plan_model.cells:
        if cell.prompt_id in FORBIDDEN_PROMPT_IDS_IN_DEV_SELECT or (
            cell.prompt_id != FROZEN_SELECTED_PROMPT_ID
        ):
            raise PromptFreezeFirewallError(
                f"FORBIDDEN_PROMPT_IN_DEV_SELECT_CELL: cell {cell.run_id} uses prompt_id={cell.prompt_id!r}; only P1 is permitted."
            )
        if cell.system_prompt_sha256 != EXPECTED_P1_SYSTEM_PROMPT_SHA256:
            raise PromptFreezeFirewallError(
                f"CELL_P1_PROMPT_HASH_MISMATCH: cell {cell.run_id} does not match locked P1 prompt hashes."
            )
        if cell.candidate_id not in FROZEN_CANDIDATE_IDS:
            raise CandidateRegistryIntegrityError(
                f"FORBIDDEN_CANDIDATE_IN_DEV_SELECT_CELL: {cell.candidate_id!r}"
            )
        if (
            cell.requested_model_id
            != FROZEN_REQUESTED_MODEL_BY_CANDIDATE[cell.candidate_id]
        ):
            raise CandidateRegistryIntegrityError(
                f"CELL_MODEL_ID_MISMATCH: cell {cell.run_id} requested_model_id={cell.requested_model_id!r}"
            )
        if cell.attempt_number != FROZEN_ATTEMPTS_PER_CELL:
            raise ImmutableCellExecutionError(
                f"CELL_ATTEMPT_NUMBER_INVALID: cell {cell.run_id} has attempt_number={cell.attempt_number}; must be 1."
            )
        if cell.retry != FROZEN_RETRY_POLICY:
            raise ImmutableCellExecutionError(
                f"CELL_RETRY_POLICY_INVALID: cell {cell.run_id} has retry={cell.retry}; must be 0."
            )

    if compute_prompt_freeze_sha256(pf_model) != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PromptFreezeFirewallError("PROMPT_FREEZE_CANONICAL_SHA256_MISMATCH")

    verified_pf = verify_runner_prompt_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        execution_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )

    verified_auth = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=plan_model,
        prompt_freeze=verified_pf,
        expected_phase=FROZEN_PHASE,
        repo_root=repo_root,
    )
    if (
        auth_model.authorization_id != EXPECTED_AUTHORIZATION_ID
        or verified_auth.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        or verified_auth.authorization_status != "AUTHORIZED"
        or verified_auth.allowed_phase != FROZEN_PHASE
        or tuple(verified_auth.allowed_candidate_ids) != FROZEN_CANDIDATE_IDS
        or verified_auth.maximum_live_generation_calls != FROZEN_MAXIMUM_CALLS
    ):
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_SCOPE_LOCK_MISMATCH: Authorization does not match hard-locked DEV_SELECT 180-cell scope."
        )

    source_prov = verify_source_develop_provenance(repo_root=repo_root)

    verified_stage_a = verify_committed_stage_a_for_launcher(
        stage_a_path,
        execution_plan=plan_model,
        prompt_freeze=verified_pf,
        authorization=verified_auth,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    assigned_run_ids, assigned_cells_sha = compute_assigned_cells_sha256(plan_model)
    if (
        stage_a_model.stage_a_receipt_sha256 != EXPECTED_STAGE_A_INTERNAL_SHA256
        or verified_stage_a.stage_a_receipt_sha256 != EXPECTED_STAGE_A_INTERNAL_SHA256
        or verified_stage_a.phase != FROZEN_PHASE
        or verified_stage_a.stage_a_status != STAGE_A_STATUS_FROZEN_BEFORE_LIVE
        or len(verified_stage_a.assigned_cell_run_ids) != FROZEN_CELL_COUNT
        or verified_stage_a.assigned_cell_run_ids != assigned_run_ids
        or verified_stage_a.assigned_cells_sha256 != EXPECTED_ASSIGNED_CELLS_SHA256
        or assigned_cells_sha != EXPECTED_ASSIGNED_CELLS_SHA256
        or verified_stage_a.code_basis_commit_sha != EXPECTED_CODE_BASIS_COMMIT_SHA
        or verified_stage_a.stage_a_commit_sha != EXPECTED_STAGE_A_COMMIT_SHA
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_SCOPE_LOCK_MISMATCH: Stage-A receipt does not match hard-locked DEV_SELECT 180-cell scope."
        )

    output_root = verify_output_root_not_existing(repo_root)

    return {
        "source_develop_provenance": source_prov,
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "p1_spec": prompt_auth["p1_spec"],
        "prompt_selection_file_sha256": prompt_auth["prompt_selection_file_sha256"],
        "execution_plan": plan_model,
        "execution_plan_path": plan_path,
        "execution_plan_file_sha256": plan_file_sha,
        "plan_freeze_receipt_file_sha256": plan_rec_file_sha,
        "prompt_freeze": verified_pf,
        "prompt_freeze_path": pf_path,
        "prompt_freeze_file_sha256": pf_file_sha,
        "authorization": verified_auth,
        "authorization_path": auth_path,
        "authorization_file_sha256": auth_file_sha,
        "authorization_receipt_file_sha256": auth_rec_file_sha,
        "stage_a_receipt": verified_stage_a,
        "stage_a_receipt_path": stage_a_path,
        "stage_a_file_sha256": stage_a_file_sha,
        "task_audit_receipt_file_sha256": task_audit_file_sha,
        "output_root": output_root,
        "scientific_code_bundle_sha256": bundle_sha,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": pconf_reg_sha,
        "portable_schema_v2_sha256": portable_schema_sha,
        "semantic_schema_sha256": semantic_schema_sha,
        "assigned_cell_run_ids": assigned_run_ids,
        "assigned_cells_sha256": assigned_cells_sha,
    }


def _validate_and_hash_preflight_requests_and_paths(
    *,
    plan_model: DevExecutionPlan,
    dry_run_out: Mapping[str, Any],
    dev_bundle: Any,
    cand_reg: Any,
    p1_spec: Any,
    repo_root: Path,
) -> dict[str, Any]:
    """Validate every cell's request metadata and artifact paths (Sections 12 & 13) and compute deterministic set hashes."""
    req_hashes_by_run_id = dry_run_out.get("serialized_request_sha256_by_run_id", {})
    planned_paths_by_run_id = dry_run_out.get("planned_artifact_paths_by_run_id", {})

    if len(req_hashes_by_run_id) != FROZEN_CELL_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_REQUEST_HASH_COUNT_MISMATCH: expected={FROZEN_CELL_COUNT}, got={len(req_hashes_by_run_id)}"
        )
    if len(planned_paths_by_run_id) != FROZEN_CELL_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_ARTIFACT_PATH_COUNT_MISMATCH: expected={FROZEN_CELL_COUNT}, got={len(planned_paths_by_run_id)}"
        )

    scenarios_by_id = {
        s.scenario_id: s for s in dev_bundle.dev_select_fixtures
    }
    if len(scenarios_by_id) != FROZEN_FIXTURE_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_FIXTURE_COUNT_MISMATCH: {len(scenarios_by_id)}"
        )

    ordered_request_records: list[dict[str, str]] = []
    ordered_path_records: list[dict[str, Any]] = []
    seen_cell_dirs: set[str] = set()
    seen_artifact_files: set[str] = set()
    root_resolved = repo_root.resolve()

    scenario_ctx_by_id = {
        fid: build_deterministic_dev_scenario_context(scen, p1_spec)
        for fid, scen in scenarios_by_id.items()
    }
    pconf_sha_by_cid = {
        cid: compute_candidate_provider_config_sha256(cand_reg.candidates[cid])
        for cid in FROZEN_CANDIDATE_IDS
    }

    for cell in plan_model.cells:
        assert_not_final100_scenario_id(cell.fixture_id)
        if cell.fixture_id not in scenarios_by_id:
            raise PlanBeforeLiveProtocolError(
                f"UNKNOWN_DEV_SELECT_FIXTURE_ID: {cell.fixture_id!r}"
            )
        scenario = scenarios_by_id[cell.fixture_id]
        assert_not_final100_scenario(scenario)

        verify_cell_manifest_for_execution(
            cell, candidate_registry=cand_reg, repo_root=repo_root
        )

        scen_ctx = scenario_ctx_by_id[cell.fixture_id]
        expected_pconf_sha = pconf_sha_by_cid[cell.candidate_id]

        if (
            cell.prompt_id != FROZEN_SELECTED_PROMPT_ID
            or cell.requested_model_id
            != FROZEN_REQUESTED_MODEL_BY_CANDIDATE[cell.candidate_id]
            or cell.system_prompt_sha256 != EXPECTED_P1_SYSTEM_PROMPT_SHA256
            or cell.system_prompt_sha256 != scen_ctx.system_prompt_sha256
            or cell.user_prompt_sha256 != scen_ctx.user_prompt_sha256
            or cell.scenario_sha256 != scen_ctx.scenario_sha256
            or cell.catalog_context_sha256 != scen_ctx.catalog_context_sha256
            or cell.provider_config_sha256 != expected_pconf_sha
            or cell.semantic_schema_sha256 != EXPECTED_SEMANTIC_SCHEMA_SHA256
            or cell.portable_generation_schema_v2_sha256
            != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            or cell.code_basis_commit_sha != EXPECTED_CODE_BASIS_COMMIT_SHA
            or cell.scientific_code_bundle_sha256
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            or cell.attempt_number != FROZEN_ATTEMPTS_PER_CELL
            or cell.retry != FROZEN_RETRY_POLICY
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_CELL_METADATA_MISMATCH: Cell {cell.run_id} failed Section 12 validation."
            )

        req_sha = req_hashes_by_run_id.get(cell.run_id)
        if not isinstance(req_sha, str) or len(req_sha) != 64:
            raise PlanBeforeLiveProtocolError(
                f"INVALID_SERIALIZED_REQUEST_SHA256 for {cell.run_id}: {req_sha!r}"
            )
        ordered_request_records.append(
            {
                "run_id": cell.run_id,
                "serialized_request_sha256": req_sha,
            }
        )

        cell_paths_map = planned_paths_by_run_id.get(cell.run_id)
        if not isinstance(cell_paths_map, Mapping) or len(cell_paths_map) != 10:
            raise PlanBeforeLiveProtocolError(
                f"INVALID_PLANNED_ARTIFACT_PATHS for {cell.run_id}"
            )

        expected_cell_dir_rel = f"{FROZEN_LIVE_OUTPUT_ROOT_REL_PATH}/{cell.run_id}"
        if expected_cell_dir_rel in seen_cell_dirs:
            raise PlanBeforeLiveProtocolError(
                f"DUPLICATE_PREFLIGHT_CELL_OUTPUT_DIR: {expected_cell_dir_rel}"
            )
        seen_cell_dirs.add(expected_cell_dir_rel)

        rel_files_map: dict[str, str] = {}
        for fname in sorted(cell_paths_map.keys()):
            raw_fpath = Path(cell_paths_map[fname])
            assert_not_final100_path(raw_fpath)
            rel_posix = raw_fpath.resolve().relative_to(root_resolved).as_posix()
            expected_file_rel = f"{expected_cell_dir_rel}/{fname}"
            if rel_posix != expected_file_rel:
                raise PlanBeforeLiveProtocolError(
                    f"PREFLIGHT_ARTIFACT_PATH_MISMATCH: got={rel_posix}, expected={expected_file_rel}"
                )
            if "final100" in rel_posix.lower() or "w06-scenario-" in rel_posix.lower():
                raise Final100FirewallViolationError(
                    f"FINAL100_PATH_IN_PREFLIGHT_ARTIFACTS: {rel_posix}"
                )
            if rel_posix in seen_artifact_files:
                raise PlanBeforeLiveProtocolError(
                    f"DUPLICATE_PREFLIGHT_ARTIFACT_FILE_PATH: {rel_posix}"
                )
            seen_artifact_files.add(rel_posix)
            rel_files_map[fname] = rel_posix

        ordered_path_records.append(
            {
                "run_id": cell.run_id,
                "cell_dir": expected_cell_dir_rel,
                "artifact_paths": rel_files_map,
            }
        )

    if len(seen_cell_dirs) != FROZEN_CELL_COUNT or len(seen_artifact_files) != (
        FROZEN_CELL_COUNT * 10
    ):
        raise PlanBeforeLiveProtocolError(
            "PREFLIGHT_ARTIFACT_PATH_UNIQUENESS_FAILURE"
        )

    request_set_sha256 = sha256_bytes(canonical_json_bytes(ordered_request_records))
    artifact_path_set_sha256 = sha256_bytes(canonical_json_bytes(ordered_path_records))

    if request_set_sha256 != EXPECTED_PREFLIGHT_REQUEST_SET_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_REQUEST_SET_SHA256_MISMATCH: expected={EXPECTED_PREFLIGHT_REQUEST_SET_SHA256}, got={request_set_sha256}"
        )
    if artifact_path_set_sha256 != EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_ARTIFACT_PATH_SET_SHA256_MISMATCH: expected={EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256}, got={artifact_path_set_sha256}"
        )

    return {
        "preflight_request_hash_count": len(ordered_request_records),
        "preflight_request_set_sha256": request_set_sha256,
        "preflight_artifact_path_count": len(ordered_path_records),
        "preflight_artifact_path_set_sha256": artifact_path_set_sha256,
        "normalized_artifact_paths_by_run_id": {
            rec["run_id"]: rec["artifact_paths"] for rec in ordered_path_records
        },
    }


# ==============================================================================
# 5. PREFLIGHT MODE & LIVE DELEGATION MODE (SECTIONS 11..20)
# ==============================================================================


def run_preflight(
    repo_root: Path = REPO_ROOT,
    *,
    env_override: Mapping[str, str] | None = None,
    include_dotenv_files: bool = True,
    versions_override: Mapping[str, str] | None = None,
    require_live_ready: bool = True,
) -> dict[str, Any]:
    """Run `--preflight` mode strictly offline under `NetworkKillSwitchGuard` (0 provider calls)."""
    with NetworkKillSwitchGuard(), _launcher_runner_bridge():
        verified = verify_frozen_launcher_authorities(repo_root)
        prompt_reg: PromptRegistry = verified["prompt_registry"]
        plan_model: DevExecutionPlan = verified["execution_plan"]
        auth_model: DevLiveAuthorizationArtifact = verified["authorization"]
        output_root: Path = verified["output_root"]

        key_presence = check_key_presence_status_only(
            repo_root,
            env_override=env_override,
            include_dotenv_files=include_dotenv_files,
        )
        sdk_info = check_runtime_sdk_versions(versions_override=versions_override)

        missing_keys = [
            k for k in REQUIRED_ENV_KEYS if key_presence.get(k) != "PRESENT"
        ]
        all_keys_present = len(missing_keys) == 0
        no_sdk_drift = not sdk_info["environment_version_drift"]

        if require_live_ready and not all_keys_present:
            raise DevLiveAuthorizationError(
                f"PREFLIGHT_API_KEY_MISSING: Missing required API keys {missing_keys}; "
                "LIVE_READINESS=NOT_READY, PRE_FLIGHT_READY=false."
            )
        if require_live_ready and not no_sdk_drift:
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_RUNTIME_SDK_DRIFT: Runtime/SDK version drift in {sdk_info['drifted_components']}; "
                "PRE_FLIGHT_READY=false."
            )

        ledger = DevCallBudgetLedger.from_execution_plan(
            plan_model,
            maximum_live_generation_calls=auth_model.maximum_live_generation_calls,
        )
        ledger_summary = ledger.summary()
        if (
            ledger_summary["maximum_live_generation_calls"] != FROZEN_MAXIMUM_CALLS
            or ledger_summary["reserved_calls"] != 0
            or ledger_summary["consumed_calls"] != 0
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_CALL_BUDGET_INVALID: {ledger_summary}"
            )

        dry_run_out = run_dev_live_runner_dry_run(
            execution_plan=verified["execution_plan_path"],
            prompt_freeze=verified["prompt_freeze_path"],
            prompt_registry=prompt_reg,
            authorization=verified["authorization_path"],
            stage_a_freeze_receipt=verified["stage_a_receipt_path"],
            batch_root_dir=output_root,
            dev_bundle=verified["dev_bundle"],
            candidate_registry=verified["candidate_registry"],
            repo_root=repo_root,
        )

        if output_root.exists():
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_CREATED_OUTPUT_ROOT_FORBIDDEN: {output_root} must not be created during --preflight."
            )

        if (
            dry_run_out.get("mode") != "dry_run"
            or dry_run_out.get("phase") != FROZEN_PHASE
            or dry_run_out.get("planned_call_count") != FROZEN_CELL_COUNT
            or dry_run_out.get("expected_total_cells") != FROZEN_CELL_COUNT
            or dry_run_out.get("authorization_verified") is not True
            or dry_run_out.get("stage_a_verified") is not True
            or dry_run_out.get("transport_status") != TRANSPORT_STATUS_NOT_INVOKED
            or dry_run_out.get("live_provider_calls") != 0
            or dry_run_out.get("provider_cost_usd") != 0
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_INVARIANT_MISMATCH: Unexpected dry-run output summary: mode={dry_run_out.get('mode')}, "
                f"phase={dry_run_out.get('phase')}, calls={dry_run_out.get('planned_call_count')}"
            )

        req_and_path_hashes = _validate_and_hash_preflight_requests_and_paths(
            plan_model=plan_model,
            dry_run_out=dry_run_out,
            dev_bundle=verified["dev_bundle"],
            cand_reg=verified["candidate_registry"],
            p1_spec=verified["p1_spec"],
            repo_root=repo_root,
        )

        live_readiness = (
            "READY" if (all_keys_present and no_sdk_drift) else "NOT_READY"
        )
        pre_flight_ready = all_keys_present and no_sdk_drift

        result: dict[str, Any] = {
            **dry_run_out,
            "planned_artifact_paths_by_run_id": req_and_path_hashes[
                "normalized_artifact_paths_by_run_id"
            ],
            "launcher_task_id": TASK_ID,
            "base_develop_sha": BASE_DEVELOP_SHA,
            "launcher_mode": "preflight",
            "selected_prompt_id": FROZEN_SELECTED_PROMPT_ID,
            "selected_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_SHA256,
            "selected_prompt_system_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
            "selected_prompt_user_template_sha256": (
                EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
            ),
            "prompt_selection_artifact_file_sha256": verified[
                "prompt_selection_file_sha256"
            ],
            "frozen_plan_prompt_ids": list(FROZEN_PLAN_PROMPT_IDS),
            "forbidden_prompt_ids": list(FORBIDDEN_PROMPT_IDS_IN_DEV_SELECT),
            "frozen_candidate_ids": list(FROZEN_CANDIDATE_IDS),
            "requested_model_by_candidate": dict(FROZEN_REQUESTED_MODEL_BY_CANDIDATE),
            "frozen_prompt_registry_sha256": prompt_reg.registry_sha256,
            "execution_plan_file_sha256": verified["execution_plan_file_sha256"],
            "plan_freeze_receipt_file_sha256": verified[
                "plan_freeze_receipt_file_sha256"
            ],
            "authorization_file_sha256": verified["authorization_file_sha256"],
            "authorization_internal_sha256": (
                auth_model.authorization_artifact_sha256
            ),
            "authorization_receipt_file_sha256": verified[
                "authorization_receipt_file_sha256"
            ],
            "project_owner_authorization_text_sha256": (
                EXPECTED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
            ),
            "stage_a_file_sha256": verified["stage_a_file_sha256"],
            "stage_a_internal_sha256": (
                verified["stage_a_receipt"].stage_a_receipt_sha256
            ),
            "stage_a_committed_verified": True,
            "stage_a_commit_sha": verified["stage_a_receipt"].stage_a_commit_sha,
            "task_audit_receipt_file_sha256": verified[
                "task_audit_receipt_file_sha256"
            ],
            "assigned_cells_sha256": verified["assigned_cells_sha256"],
            "candidate_registry_sha256": verified["candidate_registry_sha256"],
            "provider_config_registry_sha256": verified[
                "provider_config_registry_sha256"
            ],
            "portable_schema_v2_sha256": verified["portable_schema_v2_sha256"],
            "semantic_schema_sha256": verified["semantic_schema_sha256"],
            "preflight_request_hash_count": req_and_path_hashes[
                "preflight_request_hash_count"
            ],
            "preflight_request_set_sha256": req_and_path_hashes[
                "preflight_request_set_sha256"
            ],
            "preflight_artifact_path_count": req_and_path_hashes[
                "preflight_artifact_path_count"
            ],
            "preflight_artifact_path_set_sha256": req_and_path_hashes[
                "preflight_artifact_path_set_sha256"
            ],
            "call_budget_max": ledger_summary["maximum_live_generation_calls"],
            "call_budget_reserved": ledger_summary["reserved_calls"],
            "call_budget_consumed": ledger_summary["consumed_calls"],
            "retry_calls": FROZEN_RETRY_POLICY,
            "attempts_per_cell": FROZEN_ATTEMPTS_PER_CELL,
            "gemini_key_presence": key_presence["GEMINI_API_KEY"],
            "openai_key_presence": key_presence["OPENAI_API_KEY"],
            "anthropic_key_presence": key_presence["ANTHROPIC_API_KEY"],
            "api_key_presence_records": [
                {"env_var_name": k, "presence_status": key_presence[k]}
                for k in REQUIRED_ENV_KEYS
            ],
            "runtime_environment": sdk_info["observed_versions"],
            "runtime_sdk_version_evidence": sdk_info,
            "live_readiness": live_readiness,
            "pre_flight_ready": pre_flight_ready,
            "live_output_root": FROZEN_LIVE_OUTPUT_ROOT_REL_PATH,
            "live_output_root_exists": output_root.exists(),
            "live_command": FUTURE_LIVE_COMMAND,
            "live_command_executed": False,
            "live_execution_capability_minted": False,
            "production_provider_transport_constructed": False,
            "transport_starting_count": 0,
            "dev_select_execution_started": False,
            "model_winner_selected": False,
            "stochasticity_execution_started": False,
            "final100_used": False,
            "final100_firewall": {
                "final100_bundle_sha256": FORBIDDEN_FINAL100_BUNDLE_SHA256,
                "p11_assignment_manifest_sha256": FORBIDDEN_P11_MANIFEST_SHA256,
                "final100_used": False,
            },
        }
        assert_no_secrets_in_payload(
            result, context="W06_DEV_SELECT_LIVE_LAUNCHER_PREFLIGHT"
        )
        return result


def run_live_execution(
    repo_root: Path = REPO_ROOT,
    *,
    env_override: Mapping[str, str] | None = None,
    include_dotenv_files: bool = True,
    versions_override: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run `--execute-live --confirm-frozen-180-cells` following exact Section 19 production order.

    1. load exact frozen plan
    2. load exact prompt authority
    3. load exact authorization
    4. load exact Stage-A
    5. verify committed Stage-A
    6. re-attest runtime authorities (bundle, registries, key presence, SDK versions, output root non-existence)
    7. verify exact 180-cell scope
    8. issue LiveExecutionCapability using production function
    9. re-attest Stage-A at action boundary
    10. construct production transports
    11. execute frozen plan
    """
    with _launcher_runner_bridge():
        verified = verify_frozen_launcher_authorities(repo_root)

        key_presence = check_key_presence_status_only(
            repo_root,
            env_override=env_override,
            include_dotenv_files=include_dotenv_files,
        )
        missing_keys = [
            k for k in REQUIRED_ENV_KEYS if key_presence.get(k) != "PRESENT"
        ]
        if missing_keys:
            raise DevLiveAuthorizationError(
                f"LIVE_API_KEY_MISSING: Missing required provider API keys {missing_keys}."
            )

        sdk_info = check_runtime_sdk_versions(versions_override=versions_override)
        if sdk_info["environment_version_drift"]:
            raise PlanBeforeLiveProtocolError(
                f"LIVE_RUNTIME_SDK_DRIFT: Runtime/SDK version drift in {sdk_info['drifted_components']}."
            )

        frozen_p1_p2_registry: PromptRegistry = verified["prompt_registry"]
        plan_path: Path = verified["execution_plan_path"]
        pf_path: Path = verified["prompt_freeze_path"]
        auth_path: Path = verified["authorization_path"]
        stage_a_path: Path = verified["stage_a_receipt_path"]
        output_root: Path = verified["output_root"]

        capability, plan_obj, verified_pf, verified_auth, _ = (
            issue_live_execution_capability(
                execute_live=True,
                execution_plan_path=plan_path,
                prompt_freeze_path=pf_path,
                authorization_path=auth_path,
                stage_a_freeze_receipt_path=stage_a_path,
                prompt_registry=frozen_p1_p2_registry,
                repo_root=repo_root,
            )
        )
        reattest_stage_a_at_live_action_boundary(
            live_capability=capability,
            execution_plan=plan_obj,
            prompt_freeze=verified_pf,
            authorization=verified_auth,
            prompt_registry=frozen_p1_p2_registry,
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            stage_a_freeze_receipt_path=stage_a_path,
            repo_root=repo_root,
        )
        prod_transport = create_live_provider_transport_factory(
            execute_live=True,
            authorization=verified_auth,
            live_capability=capability,
        )
        receipts, ledger = execute_live_dev_batch(
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            stage_a_freeze_receipt_path=stage_a_path,
            batch_root_dir=output_root,
            prompt_registry=frozen_p1_p2_registry,
            transport=prod_transport,
            execution_mode=RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
            live_capability=capability,
            repo_root=repo_root,
        )
        return {
            "mode": "execute_live",
            "phase": plan_obj.phase,
            "selected_prompt_id": FROZEN_SELECTED_PROMPT_ID,
            "frozen_plan_prompt_ids": list(FROZEN_PLAN_PROMPT_IDS),
            "frozen_prompt_registry_sha256": frozen_p1_p2_registry.registry_sha256,
            "live_output_root": FROZEN_LIVE_OUTPUT_ROOT_REL_PATH,
            "executed_cells": len(receipts),
            "ledger": ledger.summary(),
        }


# ==============================================================================
# 6. CLI ENTRYPOINT WITH HARD SCOPE LOCK & SAFETY FLAGS (SECTIONS 10, 18, 23, 24)
# ==============================================================================


def run_launcher_cli(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    env_override: Mapping[str, str] | None = None,
    include_dotenv_files: bool = True,
    versions_override: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """CLI entrypoint for `scripts/run_w06_dev_select_live_v1.py`."""
    raw_args = list(argv) if argv is not None else []

    for arg in raw_args:
        arg_lower = arg.lower()
        if (
            "final100" in arg_lower
            or "w06-scenario-" in arg_lower
            or "w06_scenarios_freeze" in arg_lower
            or "w06_p11_assignment" in arg_lower
        ):
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: Forbidden Final100 argument {arg!r} in W06 DEV-SELECT launcher."
            )
        if "stochasticity" in arg_lower:
            raise StochasticityGateViolationError(
                f"STOCHASTICITY_FORBIDDEN_IN_DEV_SELECT_LAUNCHER: Forbidden stochasticity argument {arg!r}."
            )
        if "dev_tune" in arg_lower or "dev-tune" in arg_lower:
            raise PlanBeforeLiveProtocolError(
                f"DEV_TUNE_FORBIDDEN_IN_DEV_SELECT_LAUNCHER: Forbidden DEV-TUNE argument {arg!r}."
            )
        for forbidden_prefix in FORBIDDEN_CLI_OVERRIDE_PREFIXES:
            if arg_lower == forbidden_prefix or arg_lower.startswith(
                f"{forbidden_prefix}="
            ):
                raise PlanBeforeLiveProtocolError(
                    f"FROZEN_SCOPE_OVERRIDE_FORBIDDEN: CLI override {arg!r} is forbidden; "
                    "W06 DEV-SELECT launcher authorities, phase, candidates, P1 prompt, 180 cells, and output root are hard-locked."
                )

    parser = argparse.ArgumentParser(
        description="Frozen W06 DEV-SELECT (P1 only, 60 fixtures x 3 candidates = 180 cells) Operational Launcher.",
        add_help=True,
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run strictly offline preflight dry-run (0 provider calls, network kill-switch active).",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Explicit live execution flag (MUST be combined with --confirm-frozen-180-cells).",
    )
    parser.add_argument(
        "--confirm-frozen-180-cells",
        action="store_true",
        help="Mandatory confirmation flag required alongside --execute-live.",
    )

    try:
        parsed, unknown = parser.parse_known_args(raw_args)
    except SystemExit as exc:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_CLI_ARGUMENTS: {raw_args!r}"
        ) from exc

    if unknown:
        raise PlanBeforeLiveProtocolError(
            f"UNSUPPORTED_CLI_ARGUMENTS_FORBIDDEN: {unknown!r}; launcher scope is hard-locked."
        )

    if parsed.preflight and (
        parsed.execute_live or parsed.confirm_frozen_180_cells
    ):
        raise PlanBeforeLiveProtocolError(
            "MODE_CONFLICT_FORBIDDEN: Cannot combine --preflight with --execute-live or --confirm-frozen-180-cells."
        )

    if parsed.confirm_frozen_180_cells and not parsed.execute_live:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_FLAG_MISSING: --confirm-frozen-180-cells cannot be used without --execute-live."
        )

    if parsed.execute_live and not parsed.confirm_frozen_180_cells:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CONFIRMATION_FLAG_MISSING: --execute-live requires --confirm-frozen-180-cells."
        )

    if parsed.preflight:
        return run_preflight(
            repo_root=repo_root,
            env_override=env_override,
            include_dotenv_files=include_dotenv_files,
            versions_override=versions_override,
        )

    if parsed.execute_live and parsed.confirm_frozen_180_cells:
        return run_live_execution(
            repo_root=repo_root,
            env_override=env_override,
            include_dotenv_files=include_dotenv_files,
            versions_override=versions_override,
        )

    raise LiveExecutionNotAuthorizedError(
        "NO_MODE_SPECIFIED: Specify --preflight (offline) or both --execute-live and --confirm-frozen-180-cells."
    )


def main(argv: Sequence[str] | None = None) -> int:
    out = run_launcher_cli(argv if argv is not None else sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
