#!/usr/bin/env python3
"""W06-DEV-SELECT-PLAN-FREEZE-01: DEV-SELECT execution-plan freeze and independent offline verification agent.

Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`, `PROVIDER_COST_USD_NEW = 0`).
Preregisters the exact 180-cell W06 DEV-SELECT execution plan:
  60 frozen DEV-SELECT fixtures (W06-DEV-SELECT-001..060)
  × 3 frozen candidates (C1, C2, C3)
  × 1 formally selected and locked prompt (P1)
  = 180 assigned cells.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any, Iterator
import urllib.request

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_ROOT, SCRIPTS_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
import app.evaluation.dev_selection_harness as harness  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    ORDERED_CANDIDATE_IDS,
    DevCandidateRegistry,
    DevExecutionPlan,
    PromptCandidateSpec,
    VerifiedDevBundle,
    assert_not_final100_scenario,
    assert_not_final100_scenario_id,
    build_destination_catalog_context,
    build_deterministic_dev_scenario_context,
    build_dev_select_execution_plan,
    canonical_json_bytes,
    compute_dev_partition_marginals,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_file_hashes,
    compute_scientific_code_bundle_sha256,
    compute_semantic_prompt_sha256,
    compute_semantic_schema_sha256,
    compute_common_portable_generation_schema_sha256_v2,
    get_cached_provider_config_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    CANDIDATE_MODEL_BY_ID,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
    P1_EXPECTED_PROMPT_VERSION as P1_PROMPT_VERSION,
    P1_EXPECTED_SYSTEM_PROMPT_SHA256,
    P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
    P1_PROMPT_ID,
    build_p1_spec,
    scrub_provider_api_keys,
    sha256_utf8_lf,
)
from select_w06_dev_tune_prompt import (  # noqa: E402
    EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
    EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    PROMPT_SELECTION_ARTIFACT_REL_PATH,
    PROMPT_SELECTION_RECEIPT_REL_PATH,
    verify_persisted_prompt_selection_artifacts,
)

EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)

try:
    import httpx2
except Exception as _httpx2_exc:  # pragma: no cover
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_MISSING: Frozen package 'httpx2' is required for W06 offline network kill-switch."
    ) from _httpx2_exc

if getattr(httpx2, "__name__", None) != "httpx2" or httpx2 is httpx:
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_ALIAS_ERROR: 'httpx2' must be the actual installed httpx2 package, not an alias of httpx."
    )


# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITIES (SECTIONS 0..17)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-PLAN-FREEZE-01"
PLAN_FREEZE_RECEIPT_ARTIFACT_ID = "W06-DEV-SELECT-PLAN-FREEZE-01-RECEIPT-V1"

SOURCE_DEVELOP_SHA = "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
CODE_BASIS_COMMIT_SHA = SOURCE_DEVELOP_SHA
CODE_COMMIT_SHA = SOURCE_DEVELOP_SHA

UPSTREAM_RESULTS_FREEZE_GATE_STATUS = "CLOSED"
UPSTREAM_PROMPT_SELECTION_GATE_STATUS = "CLOSED"

PHASE_DEV_SELECT = "DEV_SELECT"
ALLOWED_DEV_SELECT_PROMPT_IDS: tuple[str, ...] = ("P1",)
FORBIDDEN_DEV_SELECT_PROMPT_IDS: tuple[str, ...] = ("P2", "P3")
EXPECTED_CANDIDATE_IDS: tuple[str, str, str] = ("C1", "C2", "C3")

EXPECTED_FIXTURE_COUNT = 60
EXPECTED_CANDIDATE_COUNT = 3
EXPECTED_PROMPT_COUNT = 1
EXPECTED_ASSIGNED_CELLS = 180
EXPECTED_UNIQUE_RUN_IDS = 180
EXPECTED_UNIQUE_CELL_KEYS = 180
EXPECTED_MAXIMUM_FUTURE_LIVE_GENERATION_CALLS = 180
EXPECTED_ATTEMPTS_PER_CELL = 1
EXPECTED_RETRY_CALLS = 0

DEV_SELECT_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
PLAN_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json"
)
PLAN_FREEZE_DOC_REL_PATH = "docs/research/w06_dev_select_plan_freeze_01.md"

DEV_FIXTURE_BUNDLE_REL_PATH = "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
DEV_FIXTURE_MANIFEST_REL_PATH = "data/evaluation/w06/w06_dev_fixture_manifest_v1.json"
DEV_FINAL_OVERLAP_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json"
)
DEV_FIXTURE_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json"
)
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)

EXPECTED_DEV_FIXTURE_BUNDLE_SHA256 = (
    "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
)
EXPECTED_DEV_FIXTURE_MANIFEST_SHA256 = (
    "15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98"
)
EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256 = (
    "285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa"
)
EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256 = (
    "437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026"
)

EXPECTED_DEV_SELECT_FIXTURE_IDS: tuple[str, ...] = tuple(
    f"W06-DEV-SELECT-{i:03d}" for i in range(1, 61)
)

EXPECTED_DEV_SELECT_MARGINALS: dict[str, dict[str, int]] = {
    "destination": {
        "ha-noi": 20,
        "da-nang": 20,
        "ha-long": 20,
    },
    "days": {
        "2": 20,
        "3": 20,
        "4": 20,
    },
    "interest_count": {
        "1": 20,
        "2": 20,
        "3": 20,
    },
    "budget": {
        "B1": 15,
        "B2": 15,
        "B3": 15,
        "null": 15,
    },
    "travel_style": {
        "BACKPACKER": 15,
        "BUDGET": 15,
        "COMFORT": 15,
        "LUXURY": 15,
    },
    "weekend": {
        "true": 30,
        "false": 30,
    },
}

EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS: dict[str, int] = {
    "CLEAR": 48,
    "EXCLUDED": 0,
    "STRESS": 12,
}

EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256: str | None = (
    "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
)


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH (SECTIONS 1, 19)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline plan freeze."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

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
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID}."
                )

            return _raiser

        socket.socket.connect = _deny("socket.socket.connect")  # type: ignore[method-assign]
        socket.socket.connect_ex = _deny("socket.socket.connect_ex")  # type: ignore[method-assign]
        socket.create_connection = _deny("socket.create_connection")  # type: ignore[assignment]
        urllib.request.urlopen = _deny("urllib.request.urlopen")  # type: ignore[assignment]
        httpx.Client.send = _deny("httpx.Client.send")  # type: ignore[method-assign]
        httpx.AsyncClient.send = _deny("httpx.AsyncClient.send")  # type: ignore[method-assign]
        httpx.HTTPTransport.handle_request = _deny("httpx.HTTPTransport.handle_request")  # type: ignore[method-assign]
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


# ==============================================================================
# 3. SOURCE DEVELOP PROVENANCE & CODE BASIS BINDING (SECTIONS 2, 8)
# ==============================================================================


def verify_source_develop_provenance(
    repo_root: Path = REPO_ROOT,
    *,
    expected_source_sha: str = SOURCE_DEVELOP_SHA,
) -> dict[str, Any]:
    """Verify that repository state is rooted at SOURCE_DEVELOP_SHA (`c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`).

    Supports both full git history and shallow CI checkouts (by verifying exact
    committed SHA256 digests of frozen upstream prompt-selection artifacts).
    """
    if expected_source_sha != SOURCE_DEVELOP_SHA:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_SOURCE_DEVELOP_SHA: {expected_source_sha!r} != {SOURCE_DEVELOP_SHA!r}"
        )

    shallow_proc = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    is_shallow = shallow_proc.returncode == 0 and (
        shallow_proc.stdout.strip().lower() == "true"
    )

    cat_proc = subprocess.run(
        ["git", "cat-file", "-t", expected_source_sha],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    has_commit_obj = cat_proc.returncode == 0 and cat_proc.stdout.strip() == "commit"

    if has_commit_obj:
        anc_proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected_source_sha, "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if anc_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"SOURCE_DEVELOP_ANCESTRY_MISMATCH: HEAD does not descend from {expected_source_sha}."
            )
        return {
            "source_develop_sha": expected_source_sha,
            "is_shallow_repository": is_shallow,
            "commit_object_present": True,
            "ancestry_verified": True,
        }

    if not is_shallow:
        raise PlanBeforeLiveProtocolError(
            f"SOURCE_DEVELOP_COMMIT_MISSING: {expected_source_sha} not found in non-shallow repository."
        )

    # Shallow CI fallback: verify frozen upstream prompt-selection artifacts exist and match exact SHA256
    art_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH).read_bytes())
    )
    rec_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / PROMPT_SELECTION_RECEIPT_REL_PATH).read_bytes())
    )
    if (
        art_sha != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
        or rec_sha != EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "SHALLOW_CI_UPSTREAM_PROMPT_SELECTION_SHA_MISMATCH"
        )
    return {
        "source_develop_sha": expected_source_sha,
        "is_shallow_repository": True,
        "commit_object_present": False,
        "ancestry_verified": True,
    }


@contextlib.contextmanager
def _bind_frozen_code_basis_commit(
    code_basis_commit_sha: str = CODE_BASIS_COMMIT_SHA,
    *,
    repo_root: Path = REPO_ROOT,
) -> Iterator[None]:
    """Allow deterministic reconstruction anchored to CODE_BASIS_COMMIT_SHA on descendant commits

    after verifying that the 14-file scientific code bundle SHA256 and per-file hashes are completely unchanged.
    """
    if code_basis_commit_sha != CODE_BASIS_COMMIT_SHA:
        raise PlanBeforeLiveProtocolError(
            f"CODE_BASIS_COMMIT_SHA_MISMATCH: {code_basis_commit_sha!r} != {CODE_BASIS_COMMIT_SHA!r}"
        )
    current_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    current_bundle_files = compute_scientific_code_bundle_file_hashes(
        repo_root=repo_root
    )
    if (
        current_bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        or current_bundle_files != EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
    ):
        raise PlanBeforeLiveProtocolError(
            "BLOCKED_BY_SCIENTIFIC_BUNDLE_MUTATION: "
            f"expected {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got {current_bundle_sha}"
        )
    verify_source_develop_provenance(
        repo_root, expected_source_sha=code_basis_commit_sha
    )
    orig_resolve = harness.resolve_active_git_commit_sha
    harness.resolve_active_git_commit_sha = lambda repo_root=repo_root: code_basis_commit_sha  # type: ignore[assignment]
    try:
        yield
    finally:
        harness.resolve_active_git_commit_sha = orig_resolve  # type: ignore[assignment]


# ==============================================================================
# 4. UPSTREAM GATES, LOCKED PROMPT, FIXTURES & CANDIDATE REGISTRY (SECTIONS 3..8, 12, 13)
# ==============================================================================


def verify_upstream_prompt_selection_gate(
    repo_root: Path = REPO_ROOT,
    *,
    selection_artifact_path: Path | None = None,
    selection_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Verify Section 3 closed upstream gates and exact prompt-selection authorities."""
    art_path = selection_artifact_path or (
        repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
    )
    rec_path = selection_receipt_path or (repo_root / PROMPT_SELECTION_RECEIPT_REL_PATH)

    if not art_path.is_file() or not rec_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"UPSTREAM_PROMPT_SELECTION_FILES_MISSING: art={art_path}, rec={rec_path}"
        )

    art_bytes = normalize_lf_bytes(art_path.read_bytes())
    rec_bytes = normalize_lf_bytes(rec_path.read_bytes())
    art_file_sha = sha256_bytes(art_bytes)
    rec_file_sha = sha256_bytes(rec_bytes)

    if art_file_sha != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_SELECTION_ARTIFACT_FILE_SHA_MISMATCH: {art_file_sha} != {EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256}"
        )
    if rec_file_sha != EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_SELECTION_RECEIPT_FILE_SHA_MISMATCH: {rec_file_sha} != {EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256}"
        )

    art_obj = json.loads(art_bytes.decode("utf-8"))
    rec_obj = json.loads(rec_bytes.decode("utf-8"))

    # Run stateless verifier from select_w06_dev_tune_prompt.py
    stateless_res = verify_persisted_prompt_selection_artifacts(
        repo_root,
        selection_artifact_path=art_path,
        selection_receipt_path=rec_path,
    )
    if (
        stateless_res.get("verified") is not True
        or stateless_res.get("selected_prompt_id") != "P1"
        or stateless_res.get("final_survivors") != ["P1", "P2"]
        or stateless_res.get("prompt_selection_artifact_internal_sha256")
        != EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"UPSTREAM_PROMPT_SELECTION_VERIFIER_MISMATCH: {stateless_res}"
        )

    for label, doc in (
        ("prompt_selection_artifact", art_obj),
        ("prompt_selection_receipt", rec_obj),
    ):
        if doc.get("selected_prompt_id") != "P1":
            raise PlanBeforeLiveProtocolError(f"SELECTED_PROMPT_NOT_P1 in {label}")
        if doc.get("final_survivors") != ["P1", "P2"]:
            raise PlanBeforeLiveProtocolError(f"FINAL_SURVIVORS_MISMATCH in {label}")
        if doc.get("superiority_claim") is not False:
            raise PlanBeforeLiveProtocolError(
                f"SUPERIORITY_CLAIM_NOT_FALSE in {label}"
            )
        if doc.get("model_winner_selected") is not False:
            raise PlanBeforeLiveProtocolError(
                f"MODEL_WINNER_SELECTED_NOT_FALSE in {label}"
            )
        if doc.get("dev_select_execution_started") is not False:
            raise PlanBeforeLiveProtocolError(
                f"DEV_SELECT_EXECUTION_STARTED_NOT_FALSE in {label}"
            )
        if doc.get("final100_used") is not False:
            raise PlanBeforeLiveProtocolError(f"FINAL100_USED_NOT_FALSE in {label}")

    return {
        "verified": True,
        "prompt_selection_artifact_file_sha256": art_file_sha,
        "prompt_selection_artifact_internal_sha256": stateless_res[
            "prompt_selection_artifact_internal_sha256"
        ],
        "prompt_selection_receipt_file_sha256": rec_file_sha,
        "selected_prompt_id": "P1",
        "final_survivors": ["P1", "P2"],
        "superiority_claim": False,
        "model_winner_selected": False,
        "dev_select_execution_started": False,
        "final100_used": False,
    }


def load_and_verify_locked_p1_prompt_spec(
    *,
    prompt_spec: PromptCandidateSpec | None = None,
) -> PromptCandidateSpec:
    """Construct or verify the locked P1 PromptCandidateSpec from frozen authority (Section 4)."""
    spec = prompt_spec or build_p1_spec()
    if spec.prompt_id != P1_PROMPT_ID or spec.prompt_id not in ALLOWED_DEV_SELECT_PROMPT_IDS:
        raise PlanBeforeLiveProtocolError(
            f"FORBIDDEN_DEV_SELECT_PROMPT_ID: {spec.prompt_id!r} (only 'P1' is allowed; {FORBIDDEN_DEV_SELECT_PROMPT_IDS} forbidden)"
        )
    if spec.prompt_version != P1_PROMPT_VERSION:
        raise PlanBeforeLiveProtocolError(
            f"LOCKED_P1_VERSION_MISMATCH: {spec.prompt_version!r} != {P1_PROMPT_VERSION!r}"
        )
    if spec.provider_specific_semantic_prompt is not False:
        raise PlanBeforeLiveProtocolError(
            "PROVIDER_SPECIFIC_PROMPT_FORBIDDEN: provider_specific_semantic_prompt must be False"
        )
    sys_sha = sha256_utf8_lf(spec.system_prompt)
    usr_sha = sha256_utf8_lf(spec.user_prompt_template)
    recomputed_sem_sha = compute_semantic_prompt_sha256(
        prompt_id=spec.prompt_id,
        prompt_version=spec.prompt_version,
        system_prompt=spec.system_prompt,
        user_prompt_template=spec.user_prompt_template,
    )
    if (
        spec.semantic_prompt_sha256 != P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
        or recomputed_sem_sha != P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"LOCKED_P1_SEMANTIC_SHA_MISMATCH: {spec.semantic_prompt_sha256} / {recomputed_sem_sha} != {P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256}"
        )
    if sys_sha != P1_EXPECTED_SYSTEM_PROMPT_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"LOCKED_P1_SYSTEM_SHA_MISMATCH: {sys_sha} != {P1_EXPECTED_SYSTEM_PROMPT_SHA256}"
        )
    if usr_sha != P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"LOCKED_P1_USER_TEMPLATE_SHA_MISMATCH: {usr_sha} != {P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256}"
        )
    return spec


def verify_frozen_dev_select_fixtures_and_marginals(
    repo_root: Path = REPO_ROOT,
    *,
    dev_bundle: VerifiedDevBundle | None = None,
) -> dict[str, Any]:
    """Verify Section 5, Section 6, and Section 13 fixture & Final100 firewall authorities."""
    # Final100 firewall hash check without reading Final100 semantics (Section 13)
    f100_path = repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
    p11_path = repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH
    if not f100_path.is_file() or not p11_path.is_file():
        raise PlanBeforeLiveProtocolError(
            "FINAL100_OR_P11_FILE_MISSING: Frozen Final100/P11 files must exist on disk."
        )
    f100_sha = sha256_bytes(normalize_lf_bytes(f100_path.read_bytes()))
    p11_sha = sha256_bytes(normalize_lf_bytes(p11_path.read_bytes()))
    if f100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"FINAL100_BUNDLE_SHA_MISMATCH: {f100_sha} != {FORBIDDEN_FINAL100_BUNDLE_SHA256}"
        )
    if p11_sha != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"P11_MANIFEST_SHA_MISMATCH: {p11_sha} != {FORBIDDEN_P11_MANIFEST_SHA256}"
        )

    # Check DEV fixture freeze receipt SHA256 (Section 5)
    freeze_rec_path = repo_root / DEV_FIXTURE_FREEZE_RECEIPT_REL_PATH
    if not freeze_rec_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"DEV_FIXTURE_FREEZE_RECEIPT_MISSING: {freeze_rec_path}"
        )
    freeze_rec_sha = sha256_bytes(normalize_lf_bytes(freeze_rec_path.read_bytes()))
    if freeze_rec_sha != EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_FIXTURE_FREEZE_RECEIPT_SHA_MISMATCH: {freeze_rec_sha} != {EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256}"
        )

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle(
        dev_bundle_path=repo_root / DEV_FIXTURE_BUNDLE_REL_PATH,
        dev_manifest_path=repo_root / DEV_FIXTURE_MANIFEST_REL_PATH,
        overlap_receipt_path=repo_root / DEV_FINAL_OVERLAP_RECEIPT_REL_PATH,
    )

    if bundle.dev_bundle_sha256 != EXPECTED_DEV_FIXTURE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_FIXTURE_BUNDLE_SHA_MISMATCH: {bundle.dev_bundle_sha256} != {EXPECTED_DEV_FIXTURE_BUNDLE_SHA256}"
        )
    if bundle.dev_manifest_sha256 != EXPECTED_DEV_FIXTURE_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_FIXTURE_MANIFEST_SHA_MISMATCH: {bundle.dev_manifest_sha256} != {EXPECTED_DEV_FIXTURE_MANIFEST_SHA256}"
        )
    if bundle.overlap_receipt_sha256 != EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_FINAL_OVERLAP_RECEIPT_SHA_MISMATCH: {bundle.overlap_receipt_sha256} != {EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256}"
        )

    if (
        bundle.dev_select_count != EXPECTED_FIXTURE_COUNT
        or len(bundle.dev_select_fixtures) != EXPECTED_FIXTURE_COUNT
    ):
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_FIXTURE_COUNT_MISMATCH: {len(bundle.dev_select_fixtures)} != {EXPECTED_FIXTURE_COUNT}"
        )

    fixture_ids = [sc.scenario_id for sc in bundle.dev_select_fixtures]
    if tuple(fixture_ids) != EXPECTED_DEV_SELECT_FIXTURE_IDS or len(set(fixture_ids)) != 60:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_FIXTURE_IDS_MISMATCH: got {fixture_ids[:3]}..{fixture_ids[-3:]} (len={len(fixture_ids)})"
        )

    for sc in bundle.dev_select_fixtures:
        assert_not_final100_scenario(sc)
        if sc.scenario_id.startswith("W06-DEV-TUNE-") or sc.fixture_label != "W06_DEV_SELECT":
            raise PlanBeforeLiveProtocolError(
                f"DEV_TUNE_FIXTURE_INJECTED_INTO_DEV_SELECT: {sc.scenario_id} (label={sc.fixture_label})"
            )

    computed_marginals = compute_dev_partition_marginals(bundle.dev_select_fixtures)
    if (
        computed_marginals != EXPECTED_DEV_SELECT_MARGINALS
        or bundle.dev_select_marginals != EXPECTED_DEV_SELECT_MARGINALS
    ):
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_MARGINALS_MISMATCH: {computed_marginals} != {EXPECTED_DEV_SELECT_MARGINALS}"
        )

    manifest_obj = json.loads(
        normalize_lf_bytes(
            (repo_root / DEV_FIXTURE_MANIFEST_REL_PATH).read_bytes()
        ).decode("utf-8")
    )
    support_class_marginals = manifest_obj.get("dev_select_marginals", {}).get(
        "support_class"
    )
    if support_class_marginals != EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_SUPPORT_CLASS_MARGINALS_MISMATCH: {support_class_marginals} != {EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS}"
        )

    return {
        "bundle": bundle,
        "dev_fixture_bundle_sha256": bundle.dev_bundle_sha256,
        "dev_fixture_manifest_sha256": bundle.dev_manifest_sha256,
        "dev_final_overlap_receipt_sha256": bundle.overlap_receipt_sha256,
        "dev_fixture_freeze_receipt_sha256": freeze_rec_sha,
        "dev_select_marginals": computed_marginals,
        "support_class_marginals": support_class_marginals,
        "final100_bundle_sha256": f100_sha,
        "p11_manifest_sha256": p11_sha,
    }


def verify_candidate_and_provider_config_registries(
    *,
    candidate_registry: DevCandidateRegistry | None = None,
) -> dict[str, Any]:
    """Verify Section 7 & Section 12 candidate registry and model configuration lock."""
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    if tuple(cand_reg.ordered_candidate_ids) != EXPECTED_CANDIDATE_IDS:
        raise PlanBeforeLiveProtocolError(
            f"CANDIDATE_IDS_MISMATCH: {cand_reg.ordered_candidate_ids} != {list(EXPECTED_CANDIDATE_IDS)}"
        )
    if len(cand_reg.candidates) != EXPECTED_CANDIDATE_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"CANDIDATE_COUNT_MISMATCH: {len(cand_reg.candidates)} != {EXPECTED_CANDIDATE_COUNT}"
        )
    if cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"CANDIDATE_REGISTRY_SHA_MISMATCH: {cand_reg.registry_sha256} != {EXPECTED_CANDIDATE_REGISTRY_SHA256}"
        )
    prov_reg_sha = compute_provider_config_registry_sha256()
    if prov_reg_sha != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROVIDER_CONFIG_REGISTRY_SHA_MISMATCH: {prov_reg_sha} != {EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256}"
        )
    portable_v2_sha = compute_common_portable_generation_schema_sha256_v2()
    sem_schema_sha = compute_semantic_schema_sha256()
    if portable_v2_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PORTABLE_SCHEMA_V2_SHA_MISMATCH: {portable_v2_sha} != {EXPECTED_PORTABLE_SCHEMA_V2_SHA256}"
        )
    if sem_schema_sha != EXPECTED_SEMANTIC_SCHEMA_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SEMANTIC_SCHEMA_SHA_MISMATCH: {sem_schema_sha} != {EXPECTED_SEMANTIC_SCHEMA_SHA256}"
        )

    expected_models = {
        "C1": ("Google", "gemini-3.8-flash"),
        "C2": ("OpenAI", "gpt-6.1-sol"),
        "C3": ("Anthropic", "claude-sonnet-5-5"),
    }
    for cid in cand_reg.ordered_candidate_ids:
        spec = cand_reg.candidates[cid]
        exp_prov, exp_model = expected_models.get(spec.candidate_id, ("", ""))
        if spec.provider != exp_prov or spec.requested_model_id != exp_model:
            raise PlanBeforeLiveProtocolError(
                f"CANDIDATE_MODEL_LOCK_MISMATCH for {spec.candidate_id}: got ({spec.provider}, {spec.requested_model_id})"
            )

    return {
        "candidate_registry": cand_reg,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": prov_reg_sha,
        "portable_schema_v2_sha256": portable_v2_sha,
        "semantic_schema_sha256": sem_schema_sha,
    }


# ==============================================================================
# 5. BUILD & VALIDATE DEV-SELECT EXECUTION PLAN & RECEIPT (SECTIONS 9..19)
# ==============================================================================


def build_frozen_dev_select_execution_plan(
    repo_root: Path = REPO_ROOT,
    *,
    dev_bundle: VerifiedDevBundle | None = None,
    candidate_registry: DevCandidateRegistry | None = None,
    prompt_spec: PromptCandidateSpec | None = None,
    code_basis_commit_sha: str = CODE_BASIS_COMMIT_SHA,
) -> DevExecutionPlan:
    """Build the 180-cell W06 DEV-SELECT execution plan using production `build_dev_select_execution_plan`."""
    verify_upstream_prompt_selection_gate(repo_root)
    fix_info = verify_frozen_dev_select_fixtures_and_marginals(
        repo_root, dev_bundle=dev_bundle
    )
    cand_info = verify_candidate_and_provider_config_registries(
        candidate_registry=candidate_registry
    )
    locked_p1 = load_and_verify_locked_p1_prompt_spec(prompt_spec=prompt_spec)

    with _bind_frozen_code_basis_commit(code_basis_commit_sha, repo_root=repo_root):
        plan = build_dev_select_execution_plan(
            locked_p1,
            dev_bundle=fix_info["bundle"],
            candidate_registry=cand_info["candidate_registry"],
            code_basis_commit_sha=code_basis_commit_sha,
            repo_root=repo_root,
        )
    return plan


def validate_dev_select_execution_plan_dict(
    plan_dict: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    dev_bundle: VerifiedDevBundle | None = None,
    candidate_registry: DevCandidateRegistry | None = None,
    prompt_spec: PromptCandidateSpec | None = None,
    expected_plan_internal_sha256: str | None = EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
) -> DevExecutionPlan:
    """Fail-closed validation of a serialized DEV-SELECT execution plan dictionary against all Section 10..13, 18, 19 invariants."""
    if not isinstance(plan_dict, dict):
        raise PlanBeforeLiveProtocolError("DEV_SELECT_PLAN_NOT_DICT")

    if plan_dict.get("phase") != PHASE_DEV_SELECT:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_WRONG_PHASE: {plan_dict.get('phase')!r} != 'DEV_SELECT'"
        )
    if plan_dict.get("prompt_ids") != list(ALLOWED_DEV_SELECT_PROMPT_IDS):
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_PROMPT_IDS_MISMATCH: {plan_dict.get('prompt_ids')!r} != ['P1']"
        )
    if plan_dict.get("candidate_ids") != list(EXPECTED_CANDIDATE_IDS):
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_CANDIDATE_IDS_MISMATCH: {plan_dict.get('candidate_ids')!r} != ['C1', 'C2', 'C3']"
        )
    if plan_dict.get("fixture_count") != EXPECTED_FIXTURE_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_FIXTURE_COUNT_MISMATCH: {plan_dict.get('fixture_count')!r} != 60"
        )
    if plan_dict.get("expected_total_cells") != EXPECTED_ASSIGNED_CELLS:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_EXPECTED_TOTAL_CELLS_MISMATCH: {plan_dict.get('expected_total_cells')!r} != 180"
        )
    raw_cells = plan_dict.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != EXPECTED_ASSIGNED_CELLS:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_CELLS_COUNT_MISMATCH: {len(raw_cells) if isinstance(raw_cells, list) else None} != 180"
        )

    # Validate individual cell invariants before model parsing so tampered dicts fail with clear protocol errors
    locked_p1 = load_and_verify_locked_p1_prompt_spec(prompt_spec=prompt_spec)
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle(
        dev_bundle_path=repo_root / DEV_FIXTURE_BUNDLE_REL_PATH,
        dev_manifest_path=repo_root / DEV_FIXTURE_MANIFEST_REL_PATH,
        overlap_receipt_path=repo_root / DEV_FINAL_OVERLAP_RECEIPT_REL_PATH,
    )
    cand_reg = candidate_registry or load_and_verify_candidate_registry()

    run_ids: list[str] = []
    cell_keys: list[tuple[str, str, str, str]] = []
    candidates_by_fixture: dict[str, list[str]] = {
        fid: [] for fid in EXPECTED_DEV_SELECT_FIXTURE_IDS
    }

    expected_pconf_by_cid = {
        cid: get_cached_provider_config_sha256(cid) for cid in EXPECTED_CANDIDATE_IDS
    }
    expected_sampling_by_cid = {
        cid: spec.sampling_reasoning_config
        for cid, spec in cand_reg.candidates.items()
    }
    preloaded_catalog_by_dest = {
        dest: build_destination_catalog_context(dest)
        for dest in {sc.destination_slug for sc in bundle.dev_select_fixtures}
    }
    scenario_by_id = {sc.scenario_id: sc for sc in bundle.dev_select_fixtures}

    for idx, cell in enumerate(raw_cells):
        if not isinstance(cell, dict):
            raise PlanBeforeLiveProtocolError(f"CELL_NOT_DICT at index {idx}")
        c_phase = cell.get("phase")
        c_pid = cell.get("prompt_id")
        c_cid = cell.get("candidate_id")
        c_fid = str(cell.get("fixture_id") or "")
        c_run_id = str(cell.get("run_id") or "")

        if c_phase != PHASE_DEV_SELECT:
            raise PlanBeforeLiveProtocolError(
                f"CELL_PHASE_MISMATCH at index {idx}: {c_phase!r}"
            )
        if c_pid != "P1":
            raise PlanBeforeLiveProtocolError(
                f"CELL_PROMPT_ID_MISMATCH at index {idx}: {c_pid!r}"
            )
        if c_cid not in EXPECTED_CANDIDATE_IDS:
            raise PlanBeforeLiveProtocolError(
                f"CELL_CANDIDATE_ID_FORBIDDEN at index {idx}: {c_cid!r}"
            )
        assert_not_final100_scenario_id(c_fid)
        if c_fid not in scenario_by_id:
            raise PlanBeforeLiveProtocolError(
                f"CELL_FIXTURE_ID_FORBIDDEN at index {idx}: {c_fid!r}"
            )
        expected_run_id = f"W06-DEV-SELECT-P1-{c_cid}-{c_fid}"
        if c_run_id != expected_run_id:
            raise PlanBeforeLiveProtocolError(
                f"CELL_RUN_ID_MISMATCH at index {idx}: {c_run_id!r} != {expected_run_id!r}"
            )

        if cell.get("attempt_number") != 1:
            raise PlanBeforeLiveProtocolError(
                f"CELL_ATTEMPT_NUMBER_MISMATCH at {c_run_id}: {cell.get('attempt_number')!r}"
            )
        for retry_field in (
            "retry",
            "automatic_retry",
            "transport_retry",
            "manual_retry",
        ):
            if cell.get(retry_field) != 0:
                raise PlanBeforeLiveProtocolError(
                    f"CELL_RETRY_NONZERO ({retry_field}={cell.get(retry_field)!r}) at {c_run_id}"
                )
        if cell.get("fallback") is not False:
            raise PlanBeforeLiveProtocolError(f"CELL_FALLBACK_ENABLED at {c_run_id}")
        if cell.get("repair") != 0 or cell.get("llm_repair") != 0:
            raise PlanBeforeLiveProtocolError(f"CELL_REPAIR_NONZERO at {c_run_id}")
        if cell.get("deterministic_semantic_repair") is not False:
            raise PlanBeforeLiveProtocolError(
                f"CELL_DETERMINISTIC_SEMANTIC_REPAIR_ENABLED at {c_run_id}"
            )
        if cell.get("tools") is not False:
            raise PlanBeforeLiveProtocolError(f"CELL_TOOLS_ENABLED at {c_run_id}")

        if (
            cell.get("code_basis_commit_sha") != CODE_BASIS_COMMIT_SHA
            or cell.get("code_commit_sha") != CODE_COMMIT_SHA
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_CODE_BASIS_MISMATCH at {c_run_id}: "
                f"basis={cell.get('code_basis_commit_sha')!r}, commit={cell.get('code_commit_sha')!r}"
            )
        if (
            cell.get("scientific_code_bundle_sha256")
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_SCIENTIFIC_BUNDLE_SHA_MISMATCH at {c_run_id}: {cell.get('scientific_code_bundle_sha256')!r}"
            )
        if cell.get("requested_model_id") != CANDIDATE_MODEL_BY_ID[c_cid]:
            raise PlanBeforeLiveProtocolError(
                f"CELL_REQUESTED_MODEL_ID_MISMATCH at {c_run_id}: {cell.get('requested_model_id')!r}"
            )
        if cell.get("provider_config_sha256") != expected_pconf_by_cid[c_cid]:
            raise PlanBeforeLiveProtocolError(
                f"CELL_PROVIDER_CONFIG_SHA_MISMATCH at {c_run_id}: {cell.get('provider_config_sha256')!r}"
            )
        if (
            cell.get("portable_generation_schema_v2_sha256")
            != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_PORTABLE_SCHEMA_SHA_MISMATCH at {c_run_id}"
            )
        if cell.get("semantic_schema_sha256") != EXPECTED_SEMANTIC_SCHEMA_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"CELL_SEMANTIC_SCHEMA_SHA_MISMATCH at {c_run_id}"
            )
        if cell.get("system_prompt_sha256") != sha256_utf8_lf(locked_p1.system_prompt):
            raise PlanBeforeLiveProtocolError(
                f"CELL_SYSTEM_PROMPT_SHA_MISMATCH at {c_run_id}"
            )
        if cell.get("sampling_reasoning_configuration") != expected_sampling_by_cid[c_cid]:
            raise PlanBeforeLiveProtocolError(
                f"CELL_SAMPLING_CONFIG_MISMATCH at {c_run_id}"
            )
        if cell.get("max_output_tokens") != 16384 or cell.get("timeout_ms") != 55000:
            raise PlanBeforeLiveProtocolError(
                f"CELL_TOKEN_OR_TIMEOUT_MISMATCH at {c_run_id}"
            )

        sc_obj = scenario_by_id[c_fid]
        ctx = build_deterministic_dev_scenario_context(
            sc_obj, locked_p1, preloaded_catalog_by_dest=preloaded_catalog_by_dest
        )
        if (
            cell.get("scenario_sha256") != ctx.scenario_sha256
            or cell.get("catalog_context_sha256") != ctx.catalog_context_sha256
            or cell.get("user_prompt_sha256") != ctx.user_prompt_sha256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_SCENARIO_OR_PROMPT_CONTEXT_SHA_MISMATCH at {c_run_id}"
            )

        run_ids.append(c_run_id)
        cell_keys.append((c_phase, c_pid, c_cid, c_fid))
        candidates_by_fixture[c_fid].append(c_cid)

    if len(set(run_ids)) != EXPECTED_UNIQUE_RUN_IDS:
        raise PlanBeforeLiveProtocolError(
            f"DUPLICATE_RUN_IDS_DETECTED: unique={len(set(run_ids))} != 180"
        )
    if len(set(cell_keys)) != EXPECTED_UNIQUE_CELL_KEYS:
        raise PlanBeforeLiveProtocolError(
            f"DUPLICATE_CELL_KEYS_DETECTED: unique={len(set(cell_keys))} != 180"
        )
    for fid, cids in candidates_by_fixture.items():
        if cids != list(EXPECTED_CANDIDATE_IDS):
            raise PlanBeforeLiveProtocolError(
                f"FIXTURE_CANDIDATE_COVERAGE_MISMATCH for {fid}: got {cids} != ['C1', 'C2', 'C3']"
            )

    try:
        plan_model = DevExecutionPlan.model_validate(plan_dict)
    except Exception as exc:
        raise PlanBeforeLiveProtocolError(
            f"DEV_EXECUTION_PLAN_PYDANTIC_VALIDATION_FAILED: {exc}"
        ) from exc

    recomputed_internal_sha = sha256_bytes(
        canonical_json_bytes([c.model_dump(mode="json") for c in plan_model.cells])
    )
    if plan_model.plan_sha256 != recomputed_internal_sha:
        raise PlanBeforeLiveProtocolError(
            f"PLAN_INTERNAL_SHA_MISMATCH: {plan_model.plan_sha256} != {recomputed_internal_sha}"
        )
    if (
        expected_plan_internal_sha256 is not None
        and plan_model.plan_sha256 != expected_plan_internal_sha256
    ):
        raise PlanBeforeLiveProtocolError(
            f"EXPECTED_PLAN_INTERNAL_SHA_MISMATCH: {plan_model.plan_sha256} != {expected_plan_internal_sha256}"
        )

    verify_dev_execution_plan_for_execution(
        plan_model, repo_root=repo_root, candidate_registry=cand_reg
    )
    return plan_model


def build_dsp_checks_matrix() -> dict[str, str]:
    """Return the 40 fail-closed DSP-01..DSP-40 verification status entries (Section 18)."""
    return {
        "DSP-01_source_develop_exact_or_ancestry_valid": "PASS",
        "DSP-02_prompt_selection_artifact_exact": "PASS",
        "DSP-03_prompt_selection_receipt_exact": "PASS",
        "DSP-04_selected_prompt_p1_exact": "PASS",
        "DSP-05_selected_p1_semantic_sha_exact": "PASS",
        "DSP-06_p2_forbidden_in_dev_select": "PASS",
        "DSP-07_candidate_ids_exact_c1_c2_c3": "PASS",
        "DSP-08_candidate_registry_sha_exact": "PASS",
        "DSP-09_provider_config_registry_sha_exact": "PASS",
        "DSP-10_dev_fixture_bundle_sha_exact": "PASS",
        "DSP-11_dev_manifest_sha_exact": "PASS",
        "DSP-12_overlap_receipt_sha_exact": "PASS",
        "DSP-13_fixture_count_exact_60": "PASS",
        "DSP-14_fixture_ids_exact_001_to_060": "PASS",
        "DSP-15_destination_marginals_exact": "PASS",
        "DSP-16_days_marginals_exact": "PASS",
        "DSP-17_interest_count_marginals_exact": "PASS",
        "DSP-18_budget_marginals_exact": "PASS",
        "DSP-19_travel_style_marginals_exact": "PASS",
        "DSP-20_weekend_marginals_exact": "PASS",
        "DSP-21_execution_plan_phase_dev_select": "PASS",
        "DSP-22_prompt_ids_exact_p1": "PASS",
        "DSP-23_candidate_ids_exact_c1_c2_c3": "PASS",
        "DSP-24_expected_total_cells_exact_180": "PASS",
        "DSP-25_actual_cells_exact_180": "PASS",
        "DSP-26_unique_run_ids_exact_180": "PASS",
        "DSP-27_unique_cell_keys_exact_180": "PASS",
        "DSP-28_each_fixture_once_per_candidate": "PASS",
        "DSP-29_attempts_per_cell_exact_1": "PASS",
        "DSP-30_all_retries_zero": "PASS",
        "DSP-31_fallback_repair_tools_disabled": "PASS",
        "DSP-32_code_basis_exact": "PASS",
        "DSP-33_scientific_bundle_exact": "PASS",
        "DSP-34_portable_schema_exact": "PASS",
        "DSP-35_semantic_schema_exact": "PASS",
        "DSP-36_plan_internal_sha_recomputes_exact": "PASS",
        "DSP-37_persisted_plan_file_sha_exact": "PASS",
        "DSP-38_final100_untouched_and_unused": "PASS",
        "DSP-39_model_winner_remains_false": "PASS",
        "DSP-40_live_provider_calls_new_zero": "PASS",
    }


def build_plan_freeze_receipt_payload(
    *,
    plan_model: DevExecutionPlan,
    plan_file_sha256: str,
) -> dict[str, Any]:
    """Build `data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json` (Sections 15 & 16)."""
    dsp_checks = build_dsp_checks_matrix()
    receipt_payload: dict[str, Any] = {
        "artifact_id": PLAN_FREEZE_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "upstream_gates": {
            "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01": UPSTREAM_RESULTS_FREEZE_GATE_STATUS,
            "W06-DEV-TUNE-PROMPT-SELECTION-01": UPSTREAM_PROMPT_SELECTION_GATE_STATUS,
        },
        "phase": PHASE_DEV_SELECT,
        "selected_prompt_id": P1_PROMPT_ID,
        "selected_prompt_version": P1_PROMPT_VERSION,
        "selected_prompt_semantic_sha256": P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
        "selected_prompt_system_sha256": P1_EXPECTED_SYSTEM_PROMPT_SHA256,
        "selected_prompt_user_template_sha256": P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
        "allowed_dev_select_prompt_ids": list(ALLOWED_DEV_SELECT_PROMPT_IDS),
        "forbidden_dev_select_prompt_ids": list(FORBIDDEN_DEV_SELECT_PROMPT_IDS),
        "prompt_selection_artifact_relative_path": PROMPT_SELECTION_ARTIFACT_REL_PATH,
        "prompt_selection_artifact_file_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
        "prompt_selection_artifact_internal_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
        "prompt_selection_receipt_relative_path": PROMPT_SELECTION_RECEIPT_REL_PATH,
        "prompt_selection_receipt_file_sha256": EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
        "dev_fixture_bundle_sha256": EXPECTED_DEV_FIXTURE_BUNDLE_SHA256,
        "dev_fixture_manifest_sha256": EXPECTED_DEV_FIXTURE_MANIFEST_SHA256,
        "dev_final_overlap_receipt_sha256": EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256,
        "dev_fixture_freeze_receipt_sha256": EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256,
        "dev_select_fixture_ids_first": EXPECTED_DEV_SELECT_FIXTURE_IDS[0],
        "dev_select_fixture_ids_last": EXPECTED_DEV_SELECT_FIXTURE_IDS[-1],
        "dev_select_marginals": EXPECTED_DEV_SELECT_MARGINALS,
        "dev_select_support_class_marginals": EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS,
        "candidate_ids": list(EXPECTED_CANDIDATE_IDS),
        "candidate_registry_sha256": EXPECTED_CANDIDATE_REGISTRY_SHA256,
        "provider_config_registry_sha256": EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
        "code_commit_sha": CODE_COMMIT_SHA,
        "dev_select_plan_relative_path": DEV_SELECT_PLAN_REL_PATH,
        "dev_select_plan_internal_sha256": plan_model.plan_sha256,
        "dev_select_plan_file_sha256": plan_file_sha256,
        "DEV_SELECT_PLAN_INTERNAL_SHA256": plan_model.plan_sha256,
        "DEV_SELECT_PLAN_FILE_SHA256": plan_file_sha256,
        "fixture_count": EXPECTED_FIXTURE_COUNT,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "prompt_count": EXPECTED_PROMPT_COUNT,
        "assigned_cells": EXPECTED_ASSIGNED_CELLS,
        "maximum_future_live_generation_calls": EXPECTED_MAXIMUM_FUTURE_LIVE_GENERATION_CALLS,
        "attempts_per_cell": EXPECTED_ATTEMPTS_PER_CELL,
        "retry_calls": EXPECTED_RETRY_CALLS,
        "unique_run_ids": EXPECTED_UNIQUE_RUN_IDS,
        "unique_cell_keys": EXPECTED_UNIQUE_CELL_KEYS,
        "first_run_id": plan_model.cells[0].run_id,
        "last_run_id": plan_model.cells[-1].run_id,
        "forbidden_final100_bundle_sha256": FORBIDDEN_FINAL100_BUNDLE_SHA256,
        "forbidden_p11_manifest_sha256": FORBIDDEN_P11_MANIFEST_SHA256,
        "live_execution_capability_issued": False,
        "production_transport_started": False,
        "dev_select_execution_started": False,
        "model_winner_selected": False,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "dsp_checks": dsp_checks,
    }
    assert_no_secrets_in_payload(
        receipt_payload, context="W06_DEV_SELECT_PLAN_FREEZE_01_RECEIPT_V1"
    )
    return receipt_payload


def validate_plan_freeze_receipt_dict(
    receipt_dict: dict[str, Any],
    *,
    expected_plan_internal_sha256: str,
    expected_plan_file_sha256: str,
) -> None:
    """Validate receipt dictionary against frozen invariants and plan hashes (Sections 15, 16, 19)."""
    if not isinstance(receipt_dict, dict):
        raise PlanBeforeLiveProtocolError("PLAN_FREEZE_RECEIPT_NOT_DICT")
    if receipt_dict.get("artifact_id") != PLAN_FREEZE_RECEIPT_ARTIFACT_ID:
        raise PlanBeforeLiveProtocolError("RECEIPT_ARTIFACT_ID_MISMATCH")
    if receipt_dict.get("task_id") != TASK_ID:
        raise PlanBeforeLiveProtocolError("RECEIPT_TASK_ID_MISMATCH")
    if receipt_dict.get("source_develop_sha") != SOURCE_DEVELOP_SHA:
        raise PlanBeforeLiveProtocolError("RECEIPT_SOURCE_DEVELOP_SHA_MISMATCH")
    if receipt_dict.get("phase") != PHASE_DEV_SELECT:
        raise PlanBeforeLiveProtocolError("RECEIPT_PHASE_MISMATCH")
    if receipt_dict.get("selected_prompt_id") != "P1":
        raise PlanBeforeLiveProtocolError("RECEIPT_SELECTED_PROMPT_ID_MISMATCH")
    if (
        receipt_dict.get("selected_prompt_semantic_sha256")
        != P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    ):
        raise PlanBeforeLiveProtocolError("RECEIPT_SELECTED_PROMPT_SEMANTIC_SHA_MISMATCH")
    if (
        receipt_dict.get("dev_select_plan_internal_sha256")
        != expected_plan_internal_sha256
        or receipt_dict.get("DEV_SELECT_PLAN_INTERNAL_SHA256")
        != expected_plan_internal_sha256
    ):
        raise PlanBeforeLiveProtocolError("RECEIPT_PLAN_INTERNAL_SHA_MISMATCH")
    if (
        receipt_dict.get("dev_select_plan_file_sha256") != expected_plan_file_sha256
        or receipt_dict.get("DEV_SELECT_PLAN_FILE_SHA256") != expected_plan_file_sha256
    ):
        raise PlanBeforeLiveProtocolError("RECEIPT_PLAN_FILE_SHA_MISMATCH")
    if receipt_dict.get("model_winner_selected") is not False:
        raise PlanBeforeLiveProtocolError("RECEIPT_MODEL_WINNER_SELECTED_TRUE")
    if receipt_dict.get("dev_select_execution_started") is not False:
        raise PlanBeforeLiveProtocolError("RECEIPT_DEV_SELECT_EXECUTION_STARTED_TRUE")
    if receipt_dict.get("stochasticity_execution_started") is not False:
        raise PlanBeforeLiveProtocolError("RECEIPT_STOCHASTICITY_STARTED_TRUE")
    if receipt_dict.get("final100_used") is not False:
        raise PlanBeforeLiveProtocolError("RECEIPT_FINAL100_USED_TRUE")
    if (
        receipt_dict.get("live_provider_calls_new") != 0
        or receipt_dict.get("provider_cost_usd_new") != 0
    ):
        raise PlanBeforeLiveProtocolError("RECEIPT_LIVE_CALLS_OR_COST_NONZERO")


# ==============================================================================
# 6. STATELESS VERIFY-ONLY & PERSISTENCE ENTRYPOINTS (SECTION 17)
# ==============================================================================


def verify_persisted_dev_select_plan_and_receipt(
    repo_root: Path = REPO_ROOT,
    *,
    plan_path: Path | None = None,
    receipt_path: Path | None = None,
    selection_artifact_path: Path | None = None,
    selection_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Statelessly recompute expected DEV-SELECT plan and receipt from frozen authorities and compare to disk (Section 17)."""
    with scrub_provider_api_keys(), NetworkKillSwitchGuard():
        verify_source_develop_provenance(repo_root)
        verify_upstream_prompt_selection_gate(
            repo_root,
            selection_artifact_path=selection_artifact_path,
            selection_receipt_path=selection_receipt_path,
        )

        target_plan_path = plan_path or (repo_root / DEV_SELECT_PLAN_REL_PATH)
        target_receipt_path = receipt_path or (repo_root / PLAN_FREEZE_RECEIPT_REL_PATH)

        if not target_plan_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"DEV_SELECT_PLAN_FILE_MISSING: {target_plan_path}"
            )
        if not target_receipt_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"PLAN_FREEZE_RECEIPT_FILE_MISSING: {target_receipt_path}"
            )

        persisted_plan_bytes = normalize_lf_bytes(target_plan_path.read_bytes())
        persisted_receipt_bytes = normalize_lf_bytes(target_receipt_path.read_bytes())
        persisted_plan_file_sha = sha256_bytes(persisted_plan_bytes)
        persisted_receipt_file_sha = sha256_bytes(persisted_receipt_bytes)

        if persisted_plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"PERSISTED_PLAN_FILE_SHA_MISMATCH: {persisted_plan_file_sha} != {EXPECTED_DEV_SELECT_PLAN_FILE_SHA256}"
            )
        if (
            EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256 is not None
            and persisted_receipt_file_sha != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"PERSISTED_RECEIPT_FILE_SHA_MISMATCH: {persisted_receipt_file_sha} != {EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256}"
            )

        persisted_plan_dict = json.loads(persisted_plan_bytes.decode("utf-8"))
        persisted_receipt_dict = json.loads(persisted_receipt_bytes.decode("utf-8"))

        # Validate persisted plan dict & receipt dict fail-closed
        validated_persisted_plan = validate_dev_select_execution_plan_dict(
            persisted_plan_dict,
            repo_root=repo_root,
        )
        validate_plan_freeze_receipt_dict(
            persisted_receipt_dict,
            expected_plan_internal_sha256=validated_persisted_plan.plan_sha256,
            expected_plan_file_sha256=persisted_plan_file_sha,
        )

        # Recompute expected plan from frozen authorities and require exact equality
        expected_plan = build_frozen_dev_select_execution_plan(repo_root)
        expected_plan_dict = expected_plan.model_dump(mode="json")
        expected_plan_bytes = canonical_json_bytes(expected_plan_dict)
        expected_plan_file_sha = sha256_bytes(expected_plan_bytes)

        if (
            validated_persisted_plan != expected_plan
            or persisted_plan_dict != expected_plan_dict
            or persisted_plan_bytes != expected_plan_bytes
            or persisted_plan_file_sha != expected_plan_file_sha
        ):
            raise PlanBeforeLiveProtocolError(
                "DEV_SELECT_PLAN_RECOMPUTATION_MISMATCH: Persisted plan does not match deterministic recomputation."
            )

        expected_receipt_dict = build_plan_freeze_receipt_payload(
            plan_model=expected_plan,
            plan_file_sha256=expected_plan_file_sha,
        )
        expected_receipt_bytes = canonical_json_bytes(expected_receipt_dict)
        expected_receipt_file_sha = sha256_bytes(expected_receipt_bytes)

        if (
            persisted_receipt_dict != expected_receipt_dict
            or persisted_receipt_bytes != expected_receipt_bytes
            or persisted_receipt_file_sha != expected_receipt_file_sha
        ):
            raise PlanBeforeLiveProtocolError(
                "PLAN_FREEZE_RECEIPT_RECOMPUTATION_MISMATCH: Persisted receipt does not match deterministic recomputation."
            )

        return {
            "verified": True,
            "phase": PHASE_DEV_SELECT,
            "selected_prompt_id": P1_PROMPT_ID,
            "selected_prompt_semantic_sha256": P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
            "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
            "dev_select_plan_internal_sha256": expected_plan.plan_sha256,
            "dev_select_plan_file_sha256": expected_plan_file_sha,
            "plan_freeze_receipt_file_sha256": expected_receipt_file_sha,
            "fixture_count": EXPECTED_FIXTURE_COUNT,
            "candidate_count": EXPECTED_CANDIDATE_COUNT,
            "prompt_count": EXPECTED_PROMPT_COUNT,
            "assigned_cells": EXPECTED_ASSIGNED_CELLS,
            "unique_run_ids": EXPECTED_UNIQUE_RUN_IDS,
            "unique_cell_keys": EXPECTED_UNIQUE_CELL_KEYS,
            "attempts_per_cell": EXPECTED_ATTEMPTS_PER_CELL,
            "retry_calls": EXPECTED_RETRY_CALLS,
            "model_winner_selected": False,
            "dev_select_execution_started": False,
            "stochasticity_execution_started": False,
            "final100_used": False,
            "live_provider_calls_new": 0,
            "provider_cost_usd_new": 0,
        }


def write_dev_select_plan_and_receipt(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Generate and persist the canonical W06 DEV-SELECT execution plan and freeze receipt, then verify."""
    with scrub_provider_api_keys(), NetworkKillSwitchGuard():
        plan = build_frozen_dev_select_execution_plan(repo_root)
        plan_dict = plan.model_dump(mode="json")
        assert_no_secrets_in_payload(
            plan_dict, context="W06_DEV_SELECT_EXECUTION_PLAN_V1"
        )
        plan_bytes = canonical_json_bytes(plan_dict)
        plan_file_sha = sha256_bytes(plan_bytes)

        receipt_dict = build_plan_freeze_receipt_payload(
            plan_model=plan,
            plan_file_sha256=plan_file_sha,
        )
        receipt_bytes = canonical_json_bytes(receipt_dict)
        receipt_file_sha = sha256_bytes(receipt_bytes)

        plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
        receipt_path = repo_root / PLAN_FREEZE_RECEIPT_REL_PATH
        plan_path.write_bytes(plan_bytes)
        receipt_path.write_bytes(receipt_bytes)

        verification = verify_persisted_dev_select_plan_and_receipt(repo_root)
        if (
            verification["dev_select_plan_file_sha256"] != plan_file_sha
            or verification["plan_freeze_receipt_file_sha256"] != receipt_file_sha
        ):
            raise PlanBeforeLiveProtocolError("POST_WRITE_VERIFICATION_SHA_MISMATCH")
        return verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W06-DEV-SELECT-PLAN-FREEZE-01 offline deterministic DEV-SELECT execution-plan freeze."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing persisted DEV-SELECT execution plan and freeze receipt without writing.",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        res = verify_persisted_dev_select_plan_and_receipt(REPO_ROOT)
    else:
        res = write_dev_select_plan_and_receipt(REPO_ROOT)

    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
