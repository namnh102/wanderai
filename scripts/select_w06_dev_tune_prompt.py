#!/usr/bin/env python3
"""W06-DEV-TUNE-PROMPT-SELECTION-01: Deterministic preregistered prompt-selection and freeze agent.

Strictly offline. Zero provider calls (`LIVE_PROVIDER_CALLS_NEW = 0`).
Verifies the closed W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01 evidence and applies the
frozen 3-tier 10.0-percentage-point survivor-band selection hierarchy across
the pooled 60-cell per-prompt DEV-TUNE design, followed by the preregistered
administrative tie-break (`P1` before `P2`).
"""

from __future__ import annotations

import argparse
import contextlib
from decimal import Decimal, localcontext
from fractions import Fraction
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
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
)
from freeze_w06_dev_tune_live_results import (  # noqa: E402
    EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
    EXPECTED_DEV_TUNE_PLAN_SHA256,
    EXPECTED_LAUNCHER_LF_SHA256,
    EXPECTED_PROMPT_FREEZE_SHA256,
    EXPECTED_PROMPT_REGISTRY_SHA256,
    EXPECTED_RAW_EVIDENCE_FILE_COUNT,
    EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES,
    EXPECTED_RAW_EVIDENCE_TOTAL_BYTES,
    EXPECTED_RAW_EVIDENCE_TREE_SHA256,
    EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
    FORBIDDEN_P11_MANIFEST_REL_PATH,
    PROMPT_FREEZE_REL_PATH,
    RESULTS_FREEZE_RECEIPT_REL_PATH,
    RESULTS_MANIFEST_REL_PATH,
    build_raw_evidence_tree_manifest,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    is_verified_downstream_w06_dev_tune_live_results_tree,
    normalize_lf_bytes,
    sha256_bytes,
    verify_and_summarize_live_results_evidence,
)

try:
    import httpx as httpx2
except Exception:  # pragma: no cover
    httpx2 = httpx  # type: ignore[assignment]


# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITIES (SECTIONS 0, 1, 3, 4, 5, 6, 11, 13, 14)
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-PROMPT-SELECTION-01"
PROMPT_SELECTION_ARTIFACT_ID = "W06-DEV-TUNE-PROMPT-SELECTION-01-V1"
PROMPT_SELECTION_RECEIPT_ARTIFACT_ID = "W06-DEV-TUNE-PROMPT-SELECTION-01-RECEIPT-V1"

SOURCE_DEVELOP_SHA = "7c326b36dcb999b9e16b1ecad7c5596dc2bccce1"
SOURCE_RESULTS_FREEZE_STATUS = "CLOSED"
SELECTION_STATUS = "SELECTED"

PROMPT_SELECTION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
PROMPT_SELECTION_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json"
)
PROMPT_SELECTION_DOC_REL_PATH = "docs/research/w06_dev_tune_prompt_selection_01.md"

EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256 = (
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256 = (
    "1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570"
)
EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256 = (
    "0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114"
)

CANDIDATE_PROMPT_IDS: tuple[str, str] = ("P1", "P2")
DEV_SELECT_CANDIDATE_IDS: tuple[str, str, str] = ("C1", "C2", "C3")
ASSIGNED_CELLS_PER_PROMPT = 60
TOTAL_ASSIGNED_CELLS = 120
FIXTURES_PER_CANDIDATE = 20

EXPECTED_P1_SEMANTIC_PROMPT_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)
EXPECTED_P1_SYSTEM_PROMPT_SHA256 = (
    "4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e"
)
EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)
EXPECTED_P2_SEMANTIC_PROMPT_SHA256 = (
    "0679dd9463d6cebf04ccb5571a403331eea3ab6819bd6a0e8b2ee1fc08c99fdf"
)
EXPECTED_P2_SYSTEM_PROMPT_SHA256 = (
    "ab8ec41b7099c1c207217a55e1afd7e075d5de6be9b2fc14863329b5535e6c68"
)
EXPECTED_P2_USER_PROMPT_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)
EXPECTED_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"

SELECTION_CRITERIA_ORDER: tuple[str, str, str] = (
    "VALID_RUN_AND_SCHEMA_RATE",
    "EXACT_GROUNDING_PASS_RATE",
    "FINAL_CORE_PASS_RATE",
)
SURVIVOR_BAND_PERCENTAGE_POINTS_DECIMAL = Decimal("10.0")
SURVIVOR_BAND_PERCENTAGE_POINTS_FLOAT = 10.0
SURVIVOR_BAND_PERCENTAGE_POINTS_FRACTION = Fraction(10, 1)

TIE_BREAK_POLICY = "PREREGISTERED_ADMINISTRATIVE_ORDER_P1_BEFORE_P2"
EXPECTED_SELECTED_PROMPT_ID = "P1"
EXPECTED_SELECTION_REASON = (
    "ADMINISTRATIVE_TIE_BREAK_AFTER_ALL_PROMPTS_SURVIVED_ALL_THREE_CRITERIA"
)

SCIENTIFIC_INTERPRETATION_STATEMENT = (
    "P1 was selected by the preregistered administrative tie-break because "
    "both P1 and P2 remained within the 10-percentage-point survivor band "
    "through all three frozen criteria."
)

FORBIDDEN_SUPERIORITY_CLAIMS: tuple[str, ...] = (
    "P1 is statistically superior to P2.",
    "P1 is scientifically proven better than P2.",
    "P2 is inferior.",
    "P1 won all metrics.",
)

FORBIDDEN_CAUSAL_429_CLAIMS: tuple[str, ...] = (
    "P2 causes HTTP 429.",
    "P2 prompt text caused provider rate limiting.",
    "P2 is less reliable on C1 due to prompt wording.",
)

EXPECTED_PRIMARY_COUNTS: dict[str, dict[str, dict[str, int]]] = {
    "VALID_RUN_AND_SCHEMA_RATE": {
        "P1": {"true": 23, "false": 37, "denominator": 60},
        "P2": {"true": 21, "false": 39, "denominator": 60},
    },
    "EXACT_GROUNDING_PASS_RATE": {
        "P1": {"true": 23, "false": 37, "denominator": 60},
        "P2": {"true": 21, "false": 39, "denominator": 60},
    },
    "FINAL_CORE_PASS_RATE": {
        "P1": {"true": 20, "false": 40, "denominator": 60},
        "P2": {"true": 21, "false": 39, "denominator": 60},
    },
}


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH (SECTION 16)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline prompt selection."""


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

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        with self:
            yield self


# ==============================================================================
# 3. SOURCE DEVELOP PROVENANCE & FROZEN INPUT VERIFICATION (SECTIONS 0, 1, 2)
# ==============================================================================


def format_decimal_28(val: Decimal) -> str:
    """Format Decimal to deterministic string with up to 12 decimal places (or exact integer/decimal)."""
    with localcontext() as ctx:
        ctx.prec = 28
        quantized = val.quantize(Decimal("0.000000000001"))
        return format(quantized, "f")


def verify_source_develop_provenance(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify that repository state is rooted at SOURCE_DEVELOP_SHA (`7c326b36dcb999b9e16b1ecad7c5596dc2bccce1`).

    Supports both full git history and shallow CI checkouts (by verifying exact
    committed SHA256 digests of frozen upstream artifacts).
    """
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
        ["git", "cat-file", "-t", SOURCE_DEVELOP_SHA],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    has_commit_obj = cat_proc.returncode == 0 and cat_proc.stdout.strip() == "commit"

    if has_commit_obj:
        anc_proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", SOURCE_DEVELOP_SHA, "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if anc_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"SOURCE_DEVELOP_ANCESTRY_MISMATCH: HEAD does not descend from {SOURCE_DEVELOP_SHA}."
            )
        return {
            "source_develop_sha": SOURCE_DEVELOP_SHA,
            "is_shallow_repository": is_shallow,
            "commit_object_present": True,
            "ancestry_verified": True,
        }

    if not is_shallow:
        raise PlanBeforeLiveProtocolError(
            f"SOURCE_DEVELOP_COMMIT_MISSING: {SOURCE_DEVELOP_SHA} not found in non-shallow repository."
        )

    # Shallow CI fallback: verify frozen upstream artifacts exist and match exact SHA256
    manifest_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / RESULTS_MANIFEST_REL_PATH).read_bytes())
    )
    receipt_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH).read_bytes())
    )
    if (
        manifest_sha != EXPECTED_RESULTS_MANIFEST_FILE_SHA256
        or receipt_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "SHALLOW_CI_UPSTREAM_RESULTS_FREEZE_SHA_MISMATCH"
        )
    return {
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "is_shallow_repository": True,
        "commit_object_present": False,
        "ancestry_verified": True,
    }


def verify_frozen_inputs_and_results_freeze(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify all Section 1 & Section 2 requirements before performing prompt selection."""
    # 1. Verify Final100 and P11 manifest are untouched
    f100_path = repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
    p11_path = repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH
    if not f100_path.is_file() or not p11_path.is_file():
        raise PlanBeforeLiveProtocolError(
            "FINAL100_OR_P11_FILE_MISSING: Frozen benchmark files must remain intact on disk."
        )
    f100_sha = sha256_bytes(normalize_lf_bytes(f100_path.read_bytes()))
    p11_sha = sha256_bytes(normalize_lf_bytes(p11_path.read_bytes()))
    if f100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"FINAL100_TAMPERED: {f100_sha} != {FORBIDDEN_FINAL100_BUNDLE_SHA256}"
        )
    if p11_sha != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"P11_MANIFEST_TAMPERED: {p11_sha} != {FORBIDDEN_P11_MANIFEST_SHA256}"
        )

    # 2. Run stateless production/offline results-freeze verifier first (Section 2)
    if not is_verified_downstream_w06_dev_tune_live_results_tree(repo_root):
        raise PlanBeforeLiveProtocolError(
            "RESULTS_FREEZE_VERIFICATION_FAILED: is_verified_downstream_w06_dev_tune_live_results_tree returned False."
        )

    # 3. Verify prompt candidate freeze artifact (Section 1)
    prompt_freeze_path = repo_root / PROMPT_FREEZE_REL_PATH
    if not prompt_freeze_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_FREEZE_MISSING: {prompt_freeze_path}"
        )
    prompt_freeze_bytes = normalize_lf_bytes(prompt_freeze_path.read_bytes())
    prompt_freeze_sha = sha256_bytes(prompt_freeze_bytes)
    if prompt_freeze_sha != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_FREEZE_SHA_MISMATCH: {prompt_freeze_sha} != {EXPECTED_PROMPT_FREEZE_SHA256}"
        )
    prompt_freeze_obj = json.loads(prompt_freeze_bytes.decode("utf-8"))

    if prompt_freeze_obj.get("prompt_candidate_ids") != list(CANDIDATE_PROMPT_IDS):
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_CANDIDATE_IDS_MISMATCH: {prompt_freeze_obj.get('prompt_candidate_ids')}"
        )
    if (
        prompt_freeze_obj.get("dev_tune_execution_plan_sha256")
        != EXPECTED_DEV_TUNE_PLAN_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PROMPT_FREEZE_PLAN_SHA_MISMATCH")

    sem_by_id = prompt_freeze_obj.get("semantic_prompt_sha256_by_id", {})
    sys_by_id = prompt_freeze_obj.get("system_prompt_sha256_by_id", {})
    usr_by_id = prompt_freeze_obj.get("user_prompt_template_sha256_by_id", {})
    ver_by_id = prompt_freeze_obj.get("prompt_versions", {})

    if (
        sem_by_id.get("P1") != EXPECTED_P1_SEMANTIC_PROMPT_SHA256
        or sem_by_id.get("P2") != EXPECTED_P2_SEMANTIC_PROMPT_SHA256
        or sys_by_id.get("P1") != EXPECTED_P1_SYSTEM_PROMPT_SHA256
        or sys_by_id.get("P2") != EXPECTED_P2_SYSTEM_PROMPT_SHA256
        or usr_by_id.get("P1") != EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
        or usr_by_id.get("P2") != EXPECTED_P2_USER_PROMPT_TEMPLATE_SHA256
        or ver_by_id.get("P1") != EXPECTED_PROMPT_VERSION
        or ver_by_id.get("P2") != EXPECTED_PROMPT_VERSION
    ):
        raise PlanBeforeLiveProtocolError(
            "PROMPT_FREEZE_HASH_OR_VERSION_MISMATCH: P1/P2 prompt hashes do not match frozen authority."
        )

    # 4. Verify results manifest & results-freeze receipt files (Sections 1 & 2)
    manifest_path = repo_root / RESULTS_MANIFEST_REL_PATH
    receipt_path = repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
    manifest_bytes = normalize_lf_bytes(manifest_path.read_bytes())
    receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
    manifest_sha = sha256_bytes(manifest_bytes)
    receipt_sha = sha256_bytes(receipt_bytes)
    if manifest_sha != EXPECTED_RESULTS_MANIFEST_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_MANIFEST_SHA_MISMATCH: {manifest_sha} != {EXPECTED_RESULTS_MANIFEST_FILE_SHA256}"
        )
    if receipt_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_SHA_MISMATCH: {receipt_sha} != {EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256}"
        )

    manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
    receipt_obj = json.loads(receipt_bytes.decode("utf-8"))

    # Require input flags in manifest and receipt (Section 2)
    for label, doc in (
        ("results_manifest", manifest_obj),
        ("results_freeze_receipt", receipt_obj),
    ):
        if doc.get("winning_prompt_selected") is not False:
            raise PlanBeforeLiveProtocolError(
                f"INPUT_WINNING_PROMPT_ALREADY_SELECTED in {label}"
            )
        if doc.get("model_winner_selected") is not False:
            raise PlanBeforeLiveProtocolError(
                f"INPUT_MODEL_WINNER_ALREADY_SELECTED in {label}"
            )
        if doc.get("dev_select_execution_started") is not False:
            raise PlanBeforeLiveProtocolError(
                f"INPUT_DEV_SELECT_ALREADY_STARTED in {label}"
            )
        if doc.get("stochasticity_execution_started") is not False:
            raise PlanBeforeLiveProtocolError(
                f"INPUT_STOCHASTICITY_ALREADY_STARTED in {label}"
            )
        if doc.get("final100_used") is not False:
            raise PlanBeforeLiveProtocolError(f"INPUT_FINAL100_USED in {label}")
        if doc.get("live_provider_calls_new") != 0:
            raise PlanBeforeLiveProtocolError(
                f"INPUT_LIVE_PROVIDER_CALLS_NEW_NONZERO in {label}"
            )

    # 5. Recompute full raw evidence summary directly from disk (Sections 2, 3, 4)
    raw_summary = verify_and_summarize_live_results_evidence(repo_root)
    tm = raw_summary["tree_manifest"]
    if (
        tm["raw_evidence_file_count"] != EXPECTED_RAW_EVIDENCE_FILE_COUNT
        or tm["raw_evidence_total_bytes"] != EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
        or tm["raw_evidence_max_file_bytes"] != EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES
        or tm["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("RAW_EVIDENCE_TREE_MISMATCH")

    if (
        len(raw_summary["assigned_run_ids"]) != TOTAL_ASSIGNED_CELLS
        or raw_summary["retry_calls"] != 0
        or raw_summary["rerun_cells"] != 0
        or raw_summary["model_id_mismatch_count"] != 0
        or raw_summary["result_counts_by_prompt"] != {"P1": 60, "P2": 60}
        or raw_summary["result_counts_by_candidate"] != {"C1": 40, "C2": 40, "C3": 40}
    ):
        raise PlanBeforeLiveProtocolError(
            "RAW_EVIDENCE_CELL_COUNT_OR_INTEGRITY_MISMATCH"
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA_MISMATCH: {bundle_sha} != {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}"
        )

    launcher_sha = sha256_bytes(
        normalize_lf_bytes(
            (repo_root / "scripts" / "run_w06_dev_tune_live_v1.py").read_bytes()
        )
    )
    if launcher_sha != EXPECTED_LAUNCHER_LF_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"LAUNCHER_LF_SHA_MISMATCH: {launcher_sha} != {EXPECTED_LAUNCHER_LF_SHA256}"
        )

    return {
        "prompt_freeze_sha256": prompt_freeze_sha,
        "prompt_freeze_obj": prompt_freeze_obj,
        "results_manifest_sha256": manifest_sha,
        "results_manifest_obj": manifest_obj,
        "results_freeze_receipt_sha256": receipt_sha,
        "results_freeze_receipt_obj": receipt_obj,
        "raw_summary": raw_summary,
        "scientific_code_bundle_sha256": bundle_sha,
        "launcher_lf_sha256": launcher_sha,
    }


# ==============================================================================
# 4. PREREGISTERED SELECTION ENGINE (SECTIONS 3, 4, 5, 6, 7, 8, 9, 12, 13)
# ==============================================================================


def extract_and_verify_pooled_prompt_counts(
    raw_summary: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> dict[str, dict[str, dict[str, int]]]:
    """Extract pooled 60-cell counts per prompt from raw summary and cross-verify against manifest & receipt (Section 4)."""
    exec_summary = receipt_obj.get("execution_summary", {})
    mapping = (
        (
            "VALID_RUN_AND_SCHEMA_RATE",
            raw_summary["valid_run_and_schema_counts"]["by_prompt"],
            manifest_obj["valid_run_and_schema_counts"]["by_prompt"],
            exec_summary["valid_run_and_schema"]["by_prompt"],
        ),
        (
            "EXACT_GROUNDING_PASS_RATE",
            raw_summary["exact_grounding_pass_counts"]["by_prompt"],
            manifest_obj["exact_grounding_pass_counts"]["by_prompt"],
            exec_summary["exact_grounding_pass"]["by_prompt"],
        ),
        (
            "FINAL_CORE_PASS_RATE",
            raw_summary["final_core_pass_counts"]["by_prompt"],
            manifest_obj["final_core_pass_counts"]["by_prompt"],
            exec_summary["final_core_pass"]["by_prompt"],
        ),
    )

    extracted: dict[str, dict[str, dict[str, int]]] = {}
    for crit_name, raw_by_p, man_by_p, rec_by_p in mapping:
        if raw_by_p != man_by_p or raw_by_p != rec_by_p:
            raise PlanBeforeLiveProtocolError(
                f"PROMPT_COUNTS_CROSS_ARTIFACT_MISMATCH for {crit_name}: "
                f"raw={raw_by_p}, manifest={man_by_p}, receipt={rec_by_p}"
            )
        extracted[crit_name] = {}
        for pid in CANDIDATE_PROMPT_IDS:
            p_counts = raw_by_p.get(pid, {})
            t_cnt = int(p_counts.get("true", -1))
            f_cnt = int(p_counts.get("false", -1))
            denom = t_cnt + f_cnt
            if denom != ASSIGNED_CELLS_PER_PROMPT:
                raise PlanBeforeLiveProtocolError(
                    f"PROMPT_DENOMINATOR_MISMATCH for {crit_name}/{pid}: "
                    f"true={t_cnt}, false={f_cnt}, denominator={denom} != {ASSIGNED_CELLS_PER_PROMPT}"
                )
            expected_pf = EXPECTED_PRIMARY_COUNTS[crit_name][pid]
            if (
                t_cnt != expected_pf["true"]
                or f_cnt != expected_pf["false"]
                or denom != expected_pf["denominator"]
            ):
                raise PlanBeforeLiveProtocolError(
                    f"PRIMARY_COUNT_MISMATCH for {crit_name}/{pid}: "
                    f"got (true={t_cnt}, false={f_cnt}, denom={denom}) != expected {expected_pf}"
                )
            extracted[crit_name][pid] = {
                "true": t_cnt,
                "false": f_cnt,
                "denominator": denom,
            }
    return extracted


def evaluate_preregistered_prompt_selection(
    counts_by_criterion: dict[str, dict[str, dict[str, int]]],
    *,
    candidate_prompt_ids: tuple[str, ...] = CANDIDATE_PROMPT_IDS,
    criteria_order: tuple[str, ...] = SELECTION_CRITERIA_ORDER,
    survivor_band_pp: Decimal = SURVIVOR_BAND_PERCENTAGE_POINTS_DECIMAL,
    tie_break_policy: str = TIE_BREAK_POLICY,
    use_cost_criterion: bool = False,
    use_latency_criterion: bool = False,
    per_candidate_selection: bool = False,
    use_significance_test: bool = False,
    use_manual_preference: bool = False,
    use_qualitative_inspection: bool = False,
    override_selected_prompt_id: str | None = None,
    enforce_frozen_primary_counts: bool = True,
) -> dict[str, Any]:
    """Deterministically apply the frozen W06 DEV-TUNE prompt-selection hierarchy (Sections 3, 4, 5, 6, 12).

    Raises PlanBeforeLiveProtocolError on any protocol violation or count/rule tampering.
    """
    if use_cost_criterion:
        raise PlanBeforeLiveProtocolError(
            "COST_CRITERION_FORBIDDEN: Cost must never be used for DEV-TUNE prompt selection."
        )
    if use_latency_criterion:
        raise PlanBeforeLiveProtocolError(
            "LATENCY_CRITERION_FORBIDDEN: Latency must never be used for DEV-TUNE prompt selection."
        )
    if per_candidate_selection:
        raise PlanBeforeLiveProtocolError(
            "PER_CANDIDATE_PROMPT_SELECTION_FORBIDDEN: Prompt selection must be pooled across all candidates; only one shared prompt may be selected."
        )
    if use_significance_test:
        raise PlanBeforeLiveProtocolError(
            "SIGNIFICANCE_TEST_CRITERION_FORBIDDEN: Statistical significance testing is not part of the preregistered rule."
        )
    if use_manual_preference or use_qualitative_inspection:
        raise PlanBeforeLiveProtocolError(
            "MANUAL_OR_QUALITATIVE_SELECTION_FORBIDDEN: Prompt selection must be 100% deterministic."
        )
    if tuple(candidate_prompt_ids) != CANDIDATE_PROMPT_IDS:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_CANDIDATE_PROMPT_IDS: {candidate_prompt_ids!r} != {CANDIDATE_PROMPT_IDS!r}"
        )
    if tuple(criteria_order) != SELECTION_CRITERIA_ORDER:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_CRITERIA_ORDER: {criteria_order!r} != {SELECTION_CRITERIA_ORDER!r}"
        )

    with localcontext() as ctx:
        ctx.prec = 28
        band_dec = Decimal(str(survivor_band_pp))
        if band_dec != SURVIVOR_BAND_PERCENTAGE_POINTS_DECIMAL:
            raise PlanBeforeLiveProtocolError(
                f"INVALID_SURVIVOR_BAND_PP: {band_dec} != {SURVIVOR_BAND_PERCENTAGE_POINTS_DECIMAL}"
            )
        band_frac = Fraction(10, 1)

        surviving: list[str] = list(candidate_prompt_ids)
        criterion_evaluations: dict[str, dict[str, Any]] = {}

        for step_idx, crit_name in enumerate(criteria_order, start=1):
            if crit_name not in counts_by_criterion:
                raise PlanBeforeLiveProtocolError(
                    f"MISSING_CRITERION_COUNTS: {crit_name}"
                )
            crit_counts = counts_by_criterion[crit_name]
            rates_frac_by_p: dict[str, Fraction] = {}
            rates_dec_by_p: dict[str, Decimal] = {}
            prompt_details: dict[str, dict[str, Any]] = {}

            for pid in candidate_prompt_ids:
                if pid not in crit_counts:
                    raise PlanBeforeLiveProtocolError(
                        f"MISSING_PROMPT_IN_CRITERION: {crit_name}/{pid}"
                    )
                entry = crit_counts[pid]
                t_cnt = int(entry.get("true", -1))
                f_cnt = int(entry.get("false", -1))
                denom = int(entry.get("denominator", -1))
                if (
                    denom != ASSIGNED_CELLS_PER_PROMPT
                    or t_cnt < 0
                    or f_cnt < 0
                    or (t_cnt + f_cnt) != denom
                ):
                    raise PlanBeforeLiveProtocolError(
                        f"INVALID_PROMPT_CELL_DENOMINATOR for {crit_name}/{pid}: "
                        f"true={t_cnt}, false={f_cnt}, denominator={denom} (expected 60)"
                    )
                if enforce_frozen_primary_counts:
                    exp = EXPECTED_PRIMARY_COUNTS[crit_name][pid]
                    if (
                        t_cnt != exp["true"]
                        or f_cnt != exp["false"]
                        or denom != exp["denominator"]
                    ):
                        raise PlanBeforeLiveProtocolError(
                            f"FROZEN_PRIMARY_COUNT_TAMPERED for {crit_name}/{pid}: "
                            f"got (true={t_cnt}, false={f_cnt}, denom={denom}) != expected {exp}"
                        )

                rate_frac = Fraction(t_cnt, denom)
                pct_frac = rate_frac * 100
                rate_dec = Decimal(t_cnt) / Decimal(denom)
                pct_dec = (Decimal(t_cnt) * Decimal(100)) / Decimal(denom)

                rates_frac_by_p[pid] = pct_frac
                rates_dec_by_p[pid] = pct_dec
                prompt_details[pid] = {
                    "prompt_id": pid,
                    "true_count": t_cnt,
                    "false_count": f_cnt,
                    "denominator": denom,
                    "rational_rate": f"{t_cnt}/{denom}",
                    "reduced_rational_rate": f"{rate_frac.numerator}/{rate_frac.denominator}",
                    "percentage_rational": f"{pct_frac.numerator}/{pct_frac.denominator}",
                    "rate_decimal_str": format_decimal_28(rate_dec),
                    "percentage_decimal_str": format_decimal_28(pct_dec),
                }

            # Best rate among currently surviving prompts
            best_pct_frac = max(rates_frac_by_p[p] for p in surviving)
            best_prompts = [
                p for p in surviving if rates_frac_by_p[p] == best_pct_frac
            ]
            best_prompt_id = best_prompts[0]
            threshold_pct_frac = best_pct_frac - band_frac

            best_pct_dec = rates_dec_by_p[best_prompt_id]
            threshold_pct_dec = best_pct_dec - band_dec

            next_survivors: list[str] = []
            for p in surviving:
                # Verify exact agreement between Fraction and Decimal comparisons
                survives_frac = rates_frac_by_p[p] >= threshold_pct_frac
                survives_dec = rates_dec_by_p[p] >= threshold_pct_dec
                if survives_frac != survives_dec:
                    raise PlanBeforeLiveProtocolError(
                        f"THRESHOLD_PRECISION_DISAGREEMENT for {crit_name}/{p}"
                    )
                margin_frac = best_pct_frac - rates_frac_by_p[p]
                margin_dec = best_pct_dec - rates_dec_by_p[p]
                prompt_details[p]["distance_from_best_percentage_points_rational"] = (
                    f"{margin_frac.numerator}/{margin_frac.denominator}"
                )
                prompt_details[
                    p
                ]["distance_from_best_percentage_points_decimal_str"] = (
                    format_decimal_28(margin_dec)
                )
                prompt_details[p]["within_10pp_survivor_band"] = survives_frac
                if survives_frac:
                    next_survivors.append(p)

            if not next_survivors:
                raise PlanBeforeLiveProtocolError(
                    f"EMPTY_SURVIVOR_SET at criterion {step_idx} ({crit_name})"
                )

            criterion_evaluations[crit_name] = {
                "criterion_index": step_idx,
                "criterion_id": crit_name,
                "input_survivors": list(surviving),
                "prompts": prompt_details,
                "best_surviving_prompt_id": best_prompt_id,
                "best_percentage_rational": f"{best_pct_frac.numerator}/{best_pct_frac.denominator}",
                "best_percentage_decimal_str": format_decimal_28(best_pct_dec),
                "survivor_band_percentage_points_decimal_str": "10.0",
                "survivor_threshold_percentage_rational": (
                    f"{threshold_pct_frac.numerator}/{threshold_pct_frac.denominator}"
                ),
                "survivor_threshold_percentage_decimal_str": format_decimal_28(
                    threshold_pct_dec
                ),
                "output_survivors": list(next_survivors),
            }
            surviving = next_survivors

        if tie_break_policy != TIE_BREAK_POLICY:
            raise PlanBeforeLiveProtocolError(
                f"INVALID_TIE_BREAK_POLICY: {tie_break_policy!r} != {TIE_BREAK_POLICY!r}"
            )

        if len(surviving) == 1:
            selected_prompt_id = surviving[0]
            tie_break_applied = False
            selection_reason = "UNIQUE_SURVIVOR"
        else:
            # Administrative tie-break: P1 before P2
            selected_prompt_id = surviving[0]
            tie_break_applied = True
            selection_reason = EXPECTED_SELECTION_REASON

        if (
            override_selected_prompt_id is not None
            and override_selected_prompt_id != selected_prompt_id
        ):
            raise PlanBeforeLiveProtocolError(
                f"SELECTED_PROMPT_OVERRIDE_FORBIDDEN: Attempted to select {override_selected_prompt_id!r} "
                f"instead of deterministic outcome {selected_prompt_id!r} (final_survivors={surviving})."
            )

        return {
            "criterion_evaluations": criterion_evaluations,
            "criterion_1_survivors": criterion_evaluations[
                "VALID_RUN_AND_SCHEMA_RATE"
            ]["output_survivors"],
            "criterion_2_survivors": criterion_evaluations[
                "EXACT_GROUNDING_PASS_RATE"
            ]["output_survivors"],
            "criterion_3_survivors": criterion_evaluations["FINAL_CORE_PASS_RATE"][
                "output_survivors"
            ],
            "final_survivors": list(surviving),
            "tie_break_policy": tie_break_policy,
            "tie_break_applied": tie_break_applied,
            "selected_prompt_id": selected_prompt_id,
            "selection_reason": selection_reason,
            "superiority_claim": False,
        }


# ==============================================================================
# 5. BUILD PROMPT SELECTION ARTIFACT & RECEIPT (SECTIONS 10, 11, 12, 13, 14)
# ==============================================================================


def build_prompt_selection_artifact_payload(
    repo_root: Path = REPO_ROOT,
    *,
    verified_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build `data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json` (Sections 10-13)."""
    verify_source_develop_provenance(repo_root)
    ctx = verified_context or verify_frozen_inputs_and_results_freeze(repo_root)
    raw_summary = ctx["raw_summary"]
    manifest_obj = ctx["results_manifest_obj"]
    receipt_obj = ctx["results_freeze_receipt_obj"]

    pooled_counts = extract_and_verify_pooled_prompt_counts(
        raw_summary, manifest_obj, receipt_obj
    )
    selection_result = evaluate_preregistered_prompt_selection(pooled_counts)

    if (
        selection_result["criterion_1_survivors"] != ["P1", "P2"]
        or selection_result["criterion_2_survivors"] != ["P1", "P2"]
        or selection_result["criterion_3_survivors"] != ["P1", "P2"]
        or selection_result["final_survivors"] != ["P1", "P2"]
        or selection_result["selected_prompt_id"] != EXPECTED_SELECTED_PROMPT_ID
        or selection_result["selection_reason"] != EXPECTED_SELECTION_REASON
        or selection_result["superiority_claim"] is not False
    ):
        raise PlanBeforeLiveProtocolError(
            f"UNEXPECTED_SELECTION_OUTCOME: {selection_result}"
        )

    temporal_limitation = {
        "p1_executed_before_p2": True,
        "p1_assigned_cell_count": 60,
        "p2_assigned_cell_count": 60,
        "p1_cell_indices": [0, 59],
        "p2_cell_indices": [60, 119],
        "prompt_treatment_temporally_interleaved_or_randomized": False,
        "primary_failure_classification_authority": "execution_receipt.failure_classification",
        "observed_http_429_total": 15,
        "observed_http_429_in_p1": 0,
        "observed_http_429_in_p2_c1": 15,
        "causal_inference_p2_causes_http_429_forbidden": True,
        "retroactive_interleaved_rerun_forbidden": True,
        "primary_results_modification_forbidden": True,
        "forbidden_causal_claims": list(FORBIDDEN_CAUSAL_429_CLAIMS),
        "scientific_limitation_statement": (
            "All 60 P1 cells executed before all 60 P2 cells without temporal "
            "interleaving or randomization. All 15 primary HTTP_429 classifications "
            "occurred in P2/C1, which may reflect cumulative provider quota/rate-limit "
            "state rather than prompt properties. It is strictly forbidden to infer "
            "that P2 causes HTTP 429 or to rerun/interleave after observing results. "
            "Because both P1 and P2 survived all three 10-percentage-point criteria, "
            "selecting P1 is a preregistered administrative tie-break outcome rather "
            "than a superiority claim."
        ),
    }

    payload_without_self_sha: dict[str, Any] = {
        "artifact_id": PROMPT_SELECTION_ARTIFACT_ID,
        "task_id": TASK_ID,
        "selection_status": SELECTION_STATUS,
        "source_results_freeze_status": SOURCE_RESULTS_FREEZE_STATUS,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "dev_tune_execution_plan_sha256": EXPECTED_DEV_TUNE_PLAN_SHA256,
        "dev_tune_execution_plan_file_sha256": EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
        "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
        "results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
        "results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "launcher_lf_sha256": EXPECTED_LAUNCHER_LF_SHA256,
        "candidate_prompt_ids": list(CANDIDATE_PROMPT_IDS),
        "candidate_prompt_metadata": {
            "P1": {
                "prompt_id": "P1",
                "prompt_version": EXPECTED_PROMPT_VERSION,
                "semantic_prompt_sha256": EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
                "system_prompt_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
                "user_prompt_template_sha256": EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
            },
            "P2": {
                "prompt_id": "P2",
                "prompt_version": EXPECTED_PROMPT_VERSION,
                "semantic_prompt_sha256": EXPECTED_P2_SEMANTIC_PROMPT_SHA256,
                "system_prompt_sha256": EXPECTED_P2_SYSTEM_PROMPT_SHA256,
                "user_prompt_template_sha256": EXPECTED_P2_USER_PROMPT_TEMPLATE_SHA256,
            },
        },
        "selection_unit": {
            "pooling_design": "POOLED_EQUAL_CANDIDATE_BY_FIXTURE_DEV_TUNE_DESIGN",
            "assigned_cells_per_prompt": ASSIGNED_CELLS_PER_PROMPT,
            "fixtures_per_candidate": FIXTURES_PER_CANDIDATE,
            "candidate_ids_pooled": list(DEV_SELECT_CANDIDATE_IDS),
            "total_assigned_cells": TOTAL_ASSIGNED_CELLS,
            "all_assigned_cells_included_in_denominator": True,
            "condition_only_on_successful_responses": False,
            "timeouts_discarded": False,
            "http_errors_discarded": False,
            "http_429_discarded": False,
            "http_5xx_discarded": False,
            "invalid_schema_outputs_discarded": False,
            "candidate_reweighting_allowed": False,
            "per_provider_prompt_selection_allowed": False,
        },
        "selection_criteria_order": list(SELECTION_CRITERIA_ORDER),
        "survivor_band_percentage_points": SURVIVOR_BAND_PERCENTAGE_POINTS_FLOAT,
        "survivor_band_percentage_points_decimal": "10.0",
        "survivor_band_percentage_points_rational": "10/1",
        "criterion_metrics": selection_result["criterion_evaluations"],
        "criterion_1_rates": {
            "P1": selection_result["criterion_evaluations"][
                "VALID_RUN_AND_SCHEMA_RATE"
            ]["prompts"]["P1"],
            "P2": selection_result["criterion_evaluations"][
                "VALID_RUN_AND_SCHEMA_RATE"
            ]["prompts"]["P2"],
        },
        "criterion_1_survivors": selection_result["criterion_1_survivors"],
        "criterion_2_rates": {
            "P1": selection_result["criterion_evaluations"][
                "EXACT_GROUNDING_PASS_RATE"
            ]["prompts"]["P1"],
            "P2": selection_result["criterion_evaluations"][
                "EXACT_GROUNDING_PASS_RATE"
            ]["prompts"]["P2"],
        },
        "criterion_2_survivors": selection_result["criterion_2_survivors"],
        "criterion_3_rates": {
            "P1": selection_result["criterion_evaluations"]["FINAL_CORE_PASS_RATE"][
                "prompts"
            ]["P1"],
            "P2": selection_result["criterion_evaluations"]["FINAL_CORE_PASS_RATE"][
                "prompts"
            ]["P2"],
        },
        "criterion_3_survivors": selection_result["criterion_3_survivors"],
        "final_survivors": selection_result["final_survivors"],
        "tie_break_policy": TIE_BREAK_POLICY,
        "tie_break_applied": True,
        "selected_prompt_id": EXPECTED_SELECTED_PROMPT_ID,
        "selected_prompt_version": EXPECTED_PROMPT_VERSION,
        "selected_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
        "selected_prompt_system_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
        "selected_prompt_user_template_sha256": EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
        "selection_reason": EXPECTED_SELECTION_REASON,
        "scientific_interpretation_statement": SCIENTIFIC_INTERPRETATION_STATEMENT,
        "observed_metric_direction_summary": {
            "valid_run_and_schema_rate_higher_prompt": "P1 (23/60 vs 21/60)",
            "exact_grounding_pass_rate_higher_prompt": "P1 (23/60 vs 21/60)",
            "final_core_pass_rate_higher_prompt": "P2 (21/60 vs 20/60)",
            "both_prompts_within_10pp_band_across_all_three_criteria": True,
        },
        "superiority_claim": False,
        "forbidden_superiority_claims": list(FORBIDDEN_SUPERIORITY_CLAIMS),
        "temporal_ordering_limitation": temporal_limitation,
        "future_dev_select_prompt_lock": {
            "allowed_dev_select_prompt_ids": ["P1"],
            "forbidden_dev_select_prompt_ids": ["P2", "P3"],
            "prompt_editing_allowed": False,
            "prompt_suffix_modification_allowed": False,
            "user_template_modification_allowed": False,
            "provider_specific_prompt_allowed": False,
            "locked_prompt_id": "P1",
            "locked_prompt_version": EXPECTED_PROMPT_VERSION,
            "locked_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
            "locked_prompt_system_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
            "locked_prompt_user_template_sha256": EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
        },
        "model_selection_firewall": {
            "model_winner_selected": False,
            "selected_model_id": None,
            "dev_tune_candidate_rates_used_for_model_selection": False,
            "model_selection_authority": "DEV_SELECT_ONLY",
            "dev_select_candidate_ids": list(DEV_SELECT_CANDIDATE_IDS),
            "candidates_removed_in_dev_tune": [],
        },
        "cost_used_for_prompt_selection": False,
        "latency_used_for_prompt_selection": False,
        "provider_specific_prompt_selection": False,
        "significance_test_used_for_prompt_selection": False,
        "manual_preference_used_for_prompt_selection": False,
        "qualitative_inspection_used_for_prompt_selection": False,
        "model_winner_selected": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
    }

    internal_sha = sha256_bytes(canonical_json_bytes(payload_without_self_sha))
    payload = dict(payload_without_self_sha)
    payload["prompt_selection_artifact_sha256"] = internal_sha
    assert_no_secrets_in_payload(payload, context="W06_DEV_TUNE_PROMPT_SELECTION_V1")
    return payload


def build_prompt_selection_receipt_payload(
    repo_root: Path = REPO_ROOT,
    *,
    selection_artifact_payload: dict[str, Any],
    selection_artifact_file_sha256: str,
) -> dict[str, Any]:
    """Build `data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json` (Section 14)."""
    ps_checks = {
        "PS-01_source_develop_sha_exact": "PASS",
        "PS-02_results_freeze_verifies": "PASS",
        "PS-03_raw_tree_sha_exact": "PASS",
        "PS-04_results_manifest_sha_exact": "PASS",
        "PS-05_results_freeze_receipt_sha_exact": "PASS",
        "PS-06_prompt_freeze_sha_exact": "PASS",
        "PS-07_prompt_candidates_exact_p1_p2": "PASS",
        "PS-08_p1_valid_schema_23_of_60": "PASS",
        "PS-09_p2_valid_schema_21_of_60": "PASS",
        "PS-10_criterion1_survivors_p1_p2": "PASS",
        "PS-11_p1_grounding_23_of_60": "PASS",
        "PS-12_p2_grounding_21_of_60": "PASS",
        "PS-13_criterion2_survivors_p1_p2": "PASS",
        "PS-14_p1_core_20_of_60": "PASS",
        "PS-15_p2_core_21_of_60": "PASS",
        "PS-16_criterion3_survivors_p1_p2": "PASS",
        "PS-17_final_survivors_p1_p2": "PASS",
        "PS-18_admin_tie_break_selects_p1": "PASS",
        "PS-19_selected_p1_semantic_sha_exact": "PASS",
        "PS-20_no_cost_criterion": "PASS",
        "PS-21_no_latency_criterion": "PASS",
        "PS-22_no_provider_specific_selection": "PASS",
        "PS-23_superiority_claim_false": "PASS",
        "PS-24_temporal_ordering_limitation_recorded": "PASS",
        "PS-25_429_causal_claim_forbidden": "PASS",
        "PS-26_model_winner_false": "PASS",
        "PS-27_dev_select_not_started": "PASS",
        "PS-28_stochasticity_not_started": "PASS",
        "PS-29_final100_untouched": "PASS",
        "PS-30_zero_new_provider_calls": "PASS",
        "PS-31_raw_evidence_unchanged": "PASS",
        "PS-32_results_manifest_unchanged": "PASS",
        "PS-33_results_freeze_receipt_unchanged": "PASS",
        "PS-34_prompt_freeze_unchanged": "PASS",
        "PS-35_scientific_bundle_unchanged": "PASS",
    }

    receipt_payload: dict[str, Any] = {
        "artifact_id": PROMPT_SELECTION_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "selection_status": SELECTION_STATUS,
        "source_results_freeze_status": SOURCE_RESULTS_FREEZE_STATUS,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "prompt_selection_artifact_relative_path": PROMPT_SELECTION_ARTIFACT_REL_PATH,
        "prompt_selection_artifact_file_sha256": selection_artifact_file_sha256,
        "prompt_selection_artifact_internal_sha256": selection_artifact_payload[
            "prompt_selection_artifact_sha256"
        ],
        "dev_tune_execution_plan_sha256": EXPECTED_DEV_TUNE_PLAN_SHA256,
        "dev_tune_execution_plan_file_sha256": EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
        "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
        "results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
        "results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "launcher_lf_sha256": EXPECTED_LAUNCHER_LF_SHA256,
        "candidate_prompt_ids": list(CANDIDATE_PROMPT_IDS),
        "selection_criteria_order": list(SELECTION_CRITERIA_ORDER),
        "survivor_band_percentage_points": SURVIVOR_BAND_PERCENTAGE_POINTS_FLOAT,
        "survivor_band_percentage_points_decimal": "10.0",
        "criterion_metrics": selection_artifact_payload["criterion_metrics"],
        "criterion_1_survivors": selection_artifact_payload["criterion_1_survivors"],
        "criterion_2_survivors": selection_artifact_payload["criterion_2_survivors"],
        "criterion_3_survivors": selection_artifact_payload["criterion_3_survivors"],
        "final_survivors": selection_artifact_payload["final_survivors"],
        "tie_break_policy": TIE_BREAK_POLICY,
        "selected_prompt_id": EXPECTED_SELECTED_PROMPT_ID,
        "selected_prompt_version": EXPECTED_PROMPT_VERSION,
        "selected_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
        "selected_prompt_system_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
        "selected_prompt_user_template_sha256": EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
        "selection_reason": EXPECTED_SELECTION_REASON,
        "scientific_interpretation_statement": SCIENTIFIC_INTERPRETATION_STATEMENT,
        "superiority_claim": False,
        "temporal_ordering_limitation": selection_artifact_payload[
            "temporal_ordering_limitation"
        ],
        "future_dev_select_prompt_lock": selection_artifact_payload[
            "future_dev_select_prompt_lock"
        ],
        "model_selection_firewall": selection_artifact_payload[
            "model_selection_firewall"
        ],
        "cost_used_for_prompt_selection": False,
        "latency_used_for_prompt_selection": False,
        "provider_specific_prompt_selection": False,
        "model_winner_selected": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "ps_checks": ps_checks,
    }
    assert_no_secrets_in_payload(
        receipt_payload, context="W06_DEV_TUNE_PROMPT_SELECTION_RECEIPT_V1"
    )
    return receipt_payload


# ==============================================================================
# 6. STATELESS CRYPTOGRAPHIC VERIFIER FOR PERSISTED SELECTION ARTIFACTS
# ==============================================================================


def verify_persisted_prompt_selection_artifacts(
    repo_root: Path = REPO_ROOT,
    *,
    selection_artifact_path: Path | None = None,
    selection_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Statelessly verify persisted `w06_dev_tune_prompt_selection_v1.json` and `w06_dev_tune_prompt_selection_01_receipt_v1.json`."""
    with NetworkKillSwitchGuard():
        art_path = selection_artifact_path or (
            repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
        )
        rec_path = selection_receipt_path or (
            repo_root / PROMPT_SELECTION_RECEIPT_REL_PATH
        )
        if not art_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"PROMPT_SELECTION_ARTIFACT_MISSING: {art_path}"
            )
        if not rec_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"PROMPT_SELECTION_RECEIPT_MISSING: {rec_path}"
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
        if not isinstance(art_obj, dict) or not isinstance(rec_obj, dict):
            raise PlanBeforeLiveProtocolError("PROMPT_SELECTION_JSON_NOT_OBJECT")

        # Recompute expected payloads from disk authorities
        expected_art = build_prompt_selection_artifact_payload(repo_root)
        if art_obj != expected_art:
            raise PlanBeforeLiveProtocolError(
                "PROMPT_SELECTION_ARTIFACT_CONTENT_MISMATCH: Persisted selection artifact does not match deterministic recomputation."
            )

        expected_rec = build_prompt_selection_receipt_payload(
            repo_root,
            selection_artifact_payload=expected_art,
            selection_artifact_file_sha256=art_file_sha,
        )
        if rec_obj != expected_rec:
            raise PlanBeforeLiveProtocolError(
                "PROMPT_SELECTION_RECEIPT_CONTENT_MISMATCH: Persisted selection receipt does not match deterministic recomputation."
            )

        return {
            "verified": True,
            "prompt_selection_artifact_file_sha256": art_file_sha,
            "prompt_selection_artifact_internal_sha256": expected_art[
                "prompt_selection_artifact_sha256"
            ],
            "prompt_selection_receipt_file_sha256": rec_file_sha,
            "selected_prompt_id": expected_art["selected_prompt_id"],
            "selected_prompt_semantic_sha256": expected_art[
                "selected_prompt_semantic_sha256"
            ],
            "final_survivors": expected_art["final_survivors"],
            "live_provider_calls_new": 0,
        }


def write_prompt_selection_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Generate and persist the formal prompt selection artifact and receipt, then verify."""
    with NetworkKillSwitchGuard():
        pre_tree = build_raw_evidence_tree_manifest(repo_root)
        if pre_tree["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256:
            raise PlanBeforeLiveProtocolError("PRE_SELECTION_RAW_TREE_SHA_MISMATCH")

        art_payload = build_prompt_selection_artifact_payload(repo_root)
        art_bytes = canonical_json_bytes(art_payload)
        art_file_sha = sha256_bytes(art_bytes)

        rec_payload = build_prompt_selection_receipt_payload(
            repo_root,
            selection_artifact_payload=art_payload,
            selection_artifact_file_sha256=art_file_sha,
        )
        rec_bytes = canonical_json_bytes(rec_payload)
        rec_file_sha = sha256_bytes(rec_bytes)

        art_path = repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
        rec_path = repo_root / PROMPT_SELECTION_RECEIPT_REL_PATH
        art_path.write_bytes(art_bytes)
        rec_path.write_bytes(rec_bytes)

        post_tree = build_raw_evidence_tree_manifest(repo_root)
        if post_tree["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256:
            raise PlanBeforeLiveProtocolError("POST_SELECTION_RAW_TREE_SHA_MISMATCH")

        verification = verify_persisted_prompt_selection_artifacts(repo_root)
        if (
            verification["prompt_selection_artifact_file_sha256"] != art_file_sha
            or verification["prompt_selection_receipt_file_sha256"] != rec_file_sha
        ):
            raise PlanBeforeLiveProtocolError("POST_WRITE_VERIFICATION_SHA_MISMATCH")
        return verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W06-DEV-TUNE-PROMPT-SELECTION-01 offline deterministic prompt selection."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing persisted prompt selection artifact and receipt without writing.",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        res = verify_persisted_prompt_selection_artifacts(REPO_ROOT)
    else:
        res = write_prompt_selection_artifacts(REPO_ROOT)

    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
