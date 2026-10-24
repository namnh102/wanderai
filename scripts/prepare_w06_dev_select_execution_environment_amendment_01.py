#!/usr/bin/env python3
"""Strictly offline methodology-amendment preparation and decision-support script.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP

PURPOSE:
Prepare a strictly offline, deterministic, evidence-bound methodology amendment proposal
(`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP-V1`) for ChatGPT review after
the primary preregistered 180-cell W06 DEV-SELECT execution and failure diagnostic.

IMPORTANT FIREWALLS:
- This script PREPARES an amendment proposal only.
- It DOES NOT approve the amendment (`AMENDMENT_APPROVED = false`).
- It DOES NOT authorize or execute amended live calls (`AMENDED_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_EXECUTED = false`).
- It DOES NOT modify the scientific runner/harness (`SCIENTIFIC_CODE_BUNDLE_SHA256` unchanged).
- It DOES NOT execute any provider call (`LIVE_PROVIDER_CALLS_NEW = 0`).
- It DOES NOT select a model (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`).
- ChatGPT retains final amendment/methodology decision authority (`FINAL_METHODOLOGY_DECISION_AUTHORITY = "CHATGPT"`).
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import socket
import statistics
import subprocess
import sys
from typing import Any, Mapping

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
    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE,
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
    compute_scientific_code_bundle_sha256,
    format_canonical_decimal_str,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
from run_w06_dev_select_live_v1 import (  # noqa: E402
    NetworkKillSwitchGuard as _BaseNetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
)


class NetworkKillSwitchGuard(_BaseNetworkKillSwitchGuard):
    """Hard offline network kill switch blocking DNS, socket, urllib, httpx, and httpx2."""

    def __enter__(self) -> "NetworkKillSwitchGuard":
        super().__enter__()
        self._orig_getaddrinfo = socket.getaddrinfo
        self._orig_gethostbyname = socket.gethostbyname
        self._orig_gethostbyname_ex = socket.gethostbyname_ex

        def _deny_dns(label: str) -> Any:
            def _raiser(*_a: Any, **_kw: Any) -> Any:
                self.blocked_attempts.append(label)
                raise OutboundNetworkBlockedError(
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID}."
                )

            return _raiser

        socket.getaddrinfo = _deny_dns("socket.getaddrinfo")  # type: ignore[assignment]
        socket.gethostbyname = _deny_dns("socket.gethostbyname")  # type: ignore[assignment]
        socket.gethostbyname_ex = _deny_dns("socket.gethostbyname_ex")  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.getaddrinfo = self._orig_getaddrinfo  # type: ignore[assignment]
        socket.gethostbyname = self._orig_gethostbyname  # type: ignore[assignment]
        socket.gethostbyname_ex = self._orig_gethostbyname_ex  # type: ignore[assignment]
        super().__exit__(exc_type, exc_val, exc_tb)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS (SECTIONS 1..17)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP"
PREP_ARTIFACT_ID = "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP-V1"
PREP_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_prep_v1.json"
)
PREP_DOC_REL_PATH = (
    "docs/research/w06_dev_select_execution_environment_amendment_01_prep.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "811255a7dd00234d63184ab483e9f88b1f2d8554"
EXPECTED_DIAGNOSTIC_BASE_DEVELOP_SHA = "beb5ec657bb4417bdeaf307356e6895070b64cdc"
EXPECTED_PRE_LIVE_DEVELOP_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"

PRIMARY_EXPERIMENT_CLASSIFICATION = (
    "PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK"
)
AMENDMENT_TRACK_CLASSIFICATION = (
    "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
)
FORBIDDEN_AMENDMENT_DESCRIPTIONS: tuple[str, ...] = (
    "replacement of primary benchmark",
    "retroactive preregistration",
    "correction of primary results",
    "rerun of failed cells",
    "continuation of the same primary batch",
)

FINAL_METHODOLOGY_DECISION_AUTHORITY = "CHATGPT"
NEXT_GATE_ID = "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CHATGPT-DECISION"

RAW_OUTPUT_ROOT_REL_PATH = "data/evaluation/w06/live_dev_select_primary_v1"
EXPECTED_RAW_EVIDENCE_TREE_SHA256 = (
    "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
)
EXPECTED_RESULTS_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json"
)
EXPECTED_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256 = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256 = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

PREFLIGHT_01D_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json"
)
DEV_FIXTURES_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
DEV_FIXTURES_FREEZE_SHA256 = (
    "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
)

FORBIDDEN_AMENDED_OR_DOWNSTREAM_REL_PATHS: tuple[str, ...] = (
    "data/evaluation/w06/w06_dev_select_model_selection_v1.json",
    "data/evaluation/w06/w06_dev_select_model_selection_01_receipt_v1.json",
    "data/evaluation/w06/w06_stochasticity_execution_plan_v1.json",
    "data/evaluation/w06/live_stochasticity_primary_v1",
    "data/evaluation/w06/live_final100_primary_v1",
    "data/evaluation/w06/live_dev_select_amended_v1",
    "data/evaluation/w06/live_dev_select_stabilized_v1",
    "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approved_v1.json",
    "data/evaluation/w06/w06_dev_select_amended_live_authorization_v1.json",
)

EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "21ad72d89a35af7b4607ecd941a5873e7cd60d7e5c54621729d01e6954dfcc11"
)
EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256 = (
    "57794e675d4b279bc875762a000ce74a07173a181afbdb31d0149f01f94b53c9"
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
        raise PlanBeforeLiveProtocolError(f"MISSING_JSON_ARTIFACT: {path}")
    data = json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))
    if not isinstance(data, dict):
        raise PlanBeforeLiveProtocolError(f"INVALID_JSON_OBJECT: {path}")
    return data


def _round_ms(value: float) -> float:
    return round(float(value), 3)


def _format_usd(val: Decimal) -> str:
    return format_canonical_decimal_str(val.quantize(Decimal("0.000001")))


def _assert_not_inside_raw_evidence(target_path: Path, repo_root: Path) -> None:
    raw_root = (repo_root / RAW_OUTPUT_ROOT_REL_PATH).resolve()
    resolved_target = target_path.resolve()
    if resolved_target == raw_root or raw_root in resolved_target.parents:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_WRITE_FORBIDDEN: Refusing to write inside frozen raw evidence root {raw_root}"
        )


def _verify_git_base_lineage(repo_root: Path) -> None:
    """Verify `AUTHORITATIVE_BASE_DEVELOP_SHA` is a valid ancestor of or equal to git HEAD when git is available."""
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return
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
            f"BASE_DEVELOP_SHA_LINEAGE_MISMATCH: {AUTHORITATIVE_BASE_DEVELOP_SHA} is not an ancestor of HEAD"
        )


# ==============================================================================
# 3. SECTION-BY-SECTION DETERMINISTIC BUILDERS
# ==============================================================================


def _collect_observed_token_and_cost_evidence(
    repo_root: Path,
    results_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Collect exact observed token usage and canonical cost from the 9 completed DEV-SELECT cells and Preflight 01D."""
    raw_root = repo_root / RAW_OUTPUT_ROOT_REL_PATH
    c1_completed_cells: list[dict[str, Any]] = []
    c2_completed_cells: list[dict[str, Any]] = []

    for run_id in results_manifest["assigned_run_ids"]:
        cell_dir = raw_root / run_id
        receipt = _load_json_dict(cell_dir / "execution_receipt.json")
        p_cls = str(receipt.get("failure_classification") or "").split(".")[-1].strip()
        if p_cls != "NONE":
            continue
        usage_doc = _load_json_dict(cell_dir / "raw_usage_metadata.json")
        norm_usage = usage_doc.get("normalized_usage_metadata") or {}
        record = {
            "run_id": run_id,
            "candidate_id": receipt["candidate_id"],
            "fixture_id": receipt["fixture_id"],
            "input_tokens": int(norm_usage.get("input_tokens") or 0),
            "output_tokens": int(norm_usage.get("output_tokens") or 0),
            "reasoning_tokens": int(norm_usage.get("reasoning_tokens") or 0),
            "thought_tokens": int(norm_usage.get("thought_tokens") or 0),
            "total_tokens": int(norm_usage.get("total_tokens") or 0),
            "canonical_cost_usd": str(receipt.get("canonical_cost_usd_decimal") or "0"),
            "latency_ms": _round_ms(float(receipt["latency_ms"])),
        }
        if receipt["candidate_id"] == "C1":
            c1_completed_cells.append(record)
        elif receipt["candidate_id"] == "C2":
            c2_completed_cells.append(record)

    if len(c1_completed_cells) != 1 or len(c2_completed_cells) != 8:
        raise PlanBeforeLiveProtocolError(
            f"COMPLETED_CELL_COUNT_MISMATCH: expected C1=1, C2=8, got C1={len(c1_completed_cells)}, C2={len(c2_completed_cells)}"
        )

    c2_input_tokens = [c["input_tokens"] for c in c2_completed_cells]
    c2_output_tokens = [c["output_tokens"] for c in c2_completed_cells]
    c2_reasoning_tokens = [c["reasoning_tokens"] for c in c2_completed_cells]
    c2_costs = [Decimal(c["canonical_cost_usd"]) for c in c2_completed_cells]

    preflight_01d = _load_json_dict(repo_root / PREFLIGHT_01D_RECEIPT_REL_PATH)
    pf_candidates = preflight_01d.get("candidates") or {}

    return {
        "dev_select_completed_cell_count": 9,
        "c1_completed_cell_summary": {
            "completed_count": 1,
            "run_id": c1_completed_cells[0]["run_id"],
            "fixture_id": c1_completed_cells[0]["fixture_id"],
            "input_tokens": c1_completed_cells[0]["input_tokens"],
            "output_tokens": c1_completed_cells[0]["output_tokens"],
            "thought_tokens": c1_completed_cells[0]["thought_tokens"],
            "billable_output_plus_thought_tokens": (
                c1_completed_cells[0]["output_tokens"]
                + c1_completed_cells[0]["thought_tokens"]
            ),
            "total_tokens": c1_completed_cells[0]["total_tokens"],
            "canonical_cost_usd": c1_completed_cells[0]["canonical_cost_usd"],
            "latency_ms": c1_completed_cells[0]["latency_ms"],
        },
        "c2_completed_cells_summary": {
            "completed_count": 8,
            "scenario_days_for_all_completed": 2,
            "input_tokens_min": min(c2_input_tokens),
            "input_tokens_median": float(statistics.median(c2_input_tokens)),
            "input_tokens_max": max(c2_input_tokens),
            "output_tokens_min": min(c2_output_tokens),
            "output_tokens_median": float(statistics.median(c2_output_tokens)),
            "output_tokens_max": max(c2_output_tokens),
            "reasoning_tokens_min": min(c2_reasoning_tokens),
            "reasoning_tokens_median": float(statistics.median(c2_reasoning_tokens)),
            "reasoning_tokens_max": max(c2_reasoning_tokens),
            "canonical_cost_usd_total": format_canonical_decimal_str(sum(c2_costs)),
            "canonical_cost_usd_min": format_canonical_decimal_str(min(c2_costs)),
            "canonical_cost_usd_max": format_canonical_decimal_str(max(c2_costs)),
        },
        "c3_completed_cells_summary": {
            "completed_count": 0,
            "dev_select_generations_observed": 0,
            "preflight_01d_smoke_reference": {
                "fixture_id": preflight_01d["fixture_id"],
                "input_tokens": int(
                    pf_candidates["C3"]["usage_metadata"]["input_tokens"]
                ),
                "output_tokens": int(
                    pf_candidates["C3"]["usage_metadata"]["output_tokens"]
                ),
                "total_tokens": int(
                    pf_candidates["C3"]["usage_metadata"]["total_tokens"]
                ),
                "latency_ms": float(pf_candidates["C3"]["latency_ms"]),
            },
        },
    }


def build_timeout_policy_options(
    diagnostic_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build Section 6B & Section 8 timeout evidence analysis and decision-support table."""
    c1_diag = diagnostic_payload["candidate_diagnostics"]["C1"]
    c2_diag = diagnostic_payload["candidate_diagnostics"]["C2"]

    c2_none_grp = c2_diag["descriptive_comparison_none_vs_timeout"]["NONE"]
    c2_timeout_grp = c2_diag["descriptive_comparison_none_vs_timeout"]["TIMEOUT"]
    c2_none_lat = {
        "min_ms": c2_none_grp["latency_ms_min"],
        "median_ms": c2_none_grp["latency_ms_median"],
        "max_ms": c2_none_grp["latency_ms_max"],
    }
    c2_timeout_lat = {
        "min_ms": c2_timeout_grp["latency_ms_min"],
        "median_ms": c2_timeout_grp["latency_ms_median"],
        "max_ms": c2_timeout_grp["latency_ms_max"],
    }
    c1_timeout_buckets = c1_diag["timeout_audit"]["timeout_boundary_analysis"][
        "bucket_counts"
    ]
    c2_timeout_buckets = c2_diag["timeout_boundary_analysis"]["bucket_counts"]

    if (
        c2_none_lat["min_ms"] != 35812.0
        or c2_none_lat["median_ms"] != 45898.5
        or c2_none_lat["max_ms"] != 53094.0
    ):
        raise PlanBeforeLiveProtocolError(
            f"C2_NONE_LATENCY_EVIDENCE_MISMATCH: {c2_none_lat}"
        )
    if (
        c2_timeout_lat["min_ms"] != 55078.0
        or c2_timeout_lat["median_ms"] != 55132.5
        or c2_timeout_lat["max_ms"] != 55797.0
    ):
        raise PlanBeforeLiveProtocolError(
            f"C2_TIMEOUT_LATENCY_EVIDENCE_MISMATCH: {c2_timeout_lat}"
        )

    def _wall_clock_entry(timeout_s: int) -> dict[str, Any]:
        return {
            "s1_180_cells_unpaced_worst_case_seconds": 180 * timeout_s,
            "s1_180_cells_unpaced_worst_case_hours": round((180 * timeout_s) / 3600.0, 2),
            "s1_180_cells_with_2s_pacing_worst_case_seconds": (180 * timeout_s) + (179 * 2),
            "s1_180_cells_with_2s_pacing_worst_case_hours": round(
                ((180 * timeout_s) + (179 * 2)) / 3600.0, 2
            ),
            "s2_189_cells_with_2s_pacing_worst_case_seconds": (189 * timeout_s) + (188 * 2),
            "s2_189_cells_with_2s_pacing_worst_case_hours": round(
                ((189 * timeout_s) + (188 * 2)) / 3600.0, 2
            ),
            "s3_90_cells_with_2s_pacing_worst_case_seconds": (90 * timeout_s) + (89 * 2),
            "s3_90_cells_with_2s_pacing_worst_case_hours": round(
                ((90 * timeout_s) + (89 * 2)) / 3600.0, 2
            ),
        }

    options = [
        {
            "option_id": "T0_BASELINE_55S",
            "status": "FROZEN_PRIMARY_BASELINE_REFERENCE",
            "timeout_seconds": 55,
            "timeout_ms": 55000,
            "scientific_rationale": (
                "Represents the preregistered primary operational timeout boundary (55,000 ms). "
                "Preserved as the immutable reference for the primary 180-cell benchmark."
            ),
            "engineering_rationale": (
                "Caps per-cell wait time at 55s, bounding worst-case 180-cell sequential wall-clock time to 2.75 hours."
            ),
            "estimated_worst_case_sequential_wall_clock_impact": _wall_clock_entry(55),
            "risk_of_still_censoring_long_responses": (
                "DEMONSTRATED_HIGH: In frozen primary evidence, 52/60 C2 cells timed out at 55,078..55,797 ms, "
                "All 8 completed C2 cells were 2-day scenarios (35,812..53,094 ms; max 53.09s is within 1.91s of the 55s cutoff), "
                "and 0/20 3-day and 0/20 4-day C2 scenarios completed within 55s. C1 also recorded 14/60 TIMEOUT cells "
                "(4 client ReadTimeout at 55,781..56,016 ms and 10 server 504 DEADLINE_EXCEEDED at 53,031..55,891 ms)."
            ),
            "risk_of_excessively_long_stuck_requests": "LOW (55s cap per call).",
            "comparability_implications": (
                "Exact match to primary benchmark, but severely confounds planner itinerary quality with the 55s transport cutoff "
                "for 3-day and 4-day structured JSON generation."
            ),
        },
        {
            "option_id": "T1_CANDIDATE_90S",
            "status": "CANDIDATE_FOR_CHATGPT_DECISION",
            "timeout_seconds": 90,
            "timeout_ms": 90000,
            "scientific_rationale": (
                "Provides a +63.6% (+35,000 ms) headroom expansion above the 55s cutoff where 52/60 C2 cells and 13/14 C1 "
                "timeout cells clustered, allowing observation of responses that require 55..90s to complete."
            ),
            "engineering_rationale": (
                "Moderate increase in per-cell deadline while keeping worst-case 180-cell sequential execution under 4.5 hours."
            ),
            "estimated_worst_case_sequential_wall_clock_impact": _wall_clock_entry(90),
            "risk_of_still_censoring_long_responses": (
                "MODERATE_TO_HIGH: Because C2 2-day completions already reached 53,094 ms (median 45,898.5 ms), "
                "3-day and 4-day itineraries with 3 interests and medium/adaptive reasoning may plausibly exceed 90,000 ms "
                "without completing structured JSON output."
            ),
            "risk_of_excessively_long_stuck_requests": "LOW_TO_MODERATE (90s max stall per stuck socket).",
            "comparability_implications": (
                "Uniformly relaxes the deadline across C1, C2, and C3, but risks leaving residual right-censoring on 4-day scenarios."
            ),
        },
        {
            "option_id": "T2_CANDIDATE_120S",
            "status": "CANDIDATE_FOR_CHATGPT_DECISION",
            "timeout_seconds": 120,
            "timeout_ms": 120000,
            "scientific_rationale": (
                "More than doubles (+118.2%, +65,000 ms) the primary 55s cutoff, providing substantial headroom beyond "
                "the observed 2-day completion range (35.8..53.1s) to observe 3-day and 4-day structured itinerary generation "
                "under medium/high/adaptive reasoning."
            ),
            "engineering_rationale": (
                "Standard 2-minute synchronous API timeout ceiling compatible with Google, OpenAI, and Anthropic SDK defaults, "
                "bounding worst-case 180-cell sequential wall-clock time to 6.0 hours."
            ),
            "estimated_worst_case_sequential_wall_clock_impact": _wall_clock_entry(120),
            "risk_of_still_censoring_long_responses": (
                "MODERATE_LOW: Substantially reduces right-censoring relative to 55s and 90s, though complex 4-day scenarios "
                "under C3 high/adaptive thinking or C2 medium reasoning could still approach 120s under provider load."
            ),
            "risk_of_excessively_long_stuck_requests": (
                "MODERATE (up to 2 minutes per stalled transport call if a provider hangs)."
            ),
            "comparability_implications": (
                "Applied identically to C1, C2, and C3 under the secondary stabilization track while preserving primary 55s results intact."
            ),
        },
        {
            "option_id": "T3_CANDIDATE_180S",
            "status": "CANDIDATE_FOR_CHATGPT_DECISION",
            "timeout_seconds": 180,
            "timeout_ms": 180000,
            "scientific_rationale": (
                "Provides 3.27x (+125,000 ms) the primary 55s boundary, minimizing the risk that client-side timeout censoring "
                "masquerades as model planning failure across 2-day, 3-day, and 4-day itinerary schemas for all three reasoning configurations "
                "(C1 thinking_level=medium, C2 reasoning_effort=medium, C3 effort=high + thinking=adaptive)."
            ),
            "engineering_rationale": (
                "Aligns client-side httpx timeout with longer upstream gateway deadlines for large structured JSON generation "
                "(max_output_tokens=16,384); note that upstream provider server-side 504 deadlines (such as Google 54..55s gateway timeouts) "
                "may still occur independently if enforced by the provider's server infrastructure."
            ),
            "estimated_worst_case_sequential_wall_clock_impact": _wall_clock_entry(180),
            "risk_of_still_censoring_long_responses": (
                "LOW_CLIENT_SIDE (Note: client-side censoring above 180s is unlikely for normal generation, though provider-enforced "
                "server-side HTTP 504 deadlines remain controlled by the provider)."
            ),
            "risk_of_excessively_long_stuck_requests": (
                "MODERATE_HIGH (up to 3 minutes per genuinely hung connection; worst-case 180-cell all-timeout run is 9.0 hours, "
                "though healthy completions terminate upon response receipt)."
            ),
            "comparability_implications": (
                "Maximizes observability of true schema/grounding/core planning quality across C1, C2, and C3 on equal terms "
                "within the secondary stabilization track."
            ),
        },
        {
            "option_id": "T4_OPTIONAL_UPPER_BOUND_240S",
            "status": "OPTIONAL_FOURTH_CANDIDATE_IF_EXTREME_HEADROOM_REQUIRED",
            "timeout_seconds": 240,
            "timeout_ms": 240000,
            "scientific_rationale": (
                "Included as a fourth reference option only if ChatGPT prioritizes near-zero client-side timeout censoring "
                "for C3 high/adaptive thinking + 16,384 max_output_tokens on 4-day catalogs (~93 KB wire payload)."
            ),
            "engineering_rationale": (
                "4-minute client socket ceiling; exceeds typical cloud load-balancer idle timeouts and increases worst-case "
                "sequential batch duration to 12.0 hours if many cells stall."
            ),
            "estimated_worst_case_sequential_wall_clock_impact": _wall_clock_entry(240),
            "risk_of_still_censoring_long_responses": "VERY_LOW_CLIENT_SIDE.",
            "risk_of_excessively_long_stuck_requests": (
                "HIGH (up to 4 minutes per hung request; diminishing return over 180s because upstream provider gateways "
                "frequently enforce their own server-side deadline at or before 60..180s)."
            ),
            "comparability_implications": (
                "Identical across candidates, but operationally heavy with limited incremental benefit over 180s."
            ),
        },
    ]

    return {
        "current_frozen_timeout_ms": 55000,
        "current_frozen_timeout_seconds": 55,
        "selected_timeout_option_id": None,
        "selection_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "frozen_evidence_basis": {
            "c2_completed_none_count": 8,
            "c2_completed_none_latency_ms": {
                "min_ms": c2_none_lat["min_ms"],
                "median_ms": c2_none_lat["median_ms"],
                "max_ms": c2_none_lat["max_ms"],
                "all_completed_days": [2],
            },
            "c2_timeout_count": 52,
            "c2_timeout_latency_ms": {
                "min_ms": c2_timeout_lat["min_ms"],
                "median_ms": c2_timeout_lat["median_ms"],
                "max_ms": c2_timeout_lat["max_ms"],
            },
            "c2_timeout_boundary_buckets": c2_timeout_buckets,
            "c1_completed_none_count": 1,
            "c1_completed_none_latency_ms": 46688.0,
            "c1_timeout_count": 14,
            "c1_timeout_breakdown": {
                "client_read_timeout_count": 4,
                "client_read_timeout_latency_range_ms": [55781.0, 56016.0],
                "server_http_504_deadline_exceeded_count": 10,
                "server_http_504_latency_range_ms": [53031.0, 55891.0],
            },
            "c1_timeout_boundary_buckets": c1_timeout_buckets,
        },
        "counterfactual_firewall": {
            "permitted_evidence_statement": (
                "55 seconds demonstrably censors many C2 requests at the configured boundary "
                "(52/60 C2 cells timed out at 55,078..55,797 ms, and 8/8 C2 completions were 2-day scenarios at 35,812..53,094 ms)."
            ),
            "forbidden_counterfactual_claims": [
                "90 seconds would yield X/60 completions",
                "120 seconds would yield X/60 completions",
                "180 seconds would yield X/60 completions",
                "120 seconds guarantees success",
                "180 seconds guarantees success",
            ],
            "counterfactual_success_rate_estimated": False,
        },
        "candidate_timeout_options": options,
    }


def build_pacing_policy_options() -> dict[str, Any]:
    """Build Section 6C deterministic non-adaptive inter-call pacing policy options."""
    return {
        "current_pacing_policy": "UNPACED_SEQUENTIAL_INTERLEAVED_C1_C2_C3",
        "selected_pacing_option_id": None,
        "pacing_implemented_in_prep": False,
        "selection_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "invariants_for_all_pacing_options": {
            "fixed_before_execution": True,
            "applies_by_explicit_fair_rule": True,
            "reacts_to_success_or_failure": False,
            "performs_retry": False,
            "adapts_to_provider_responses_or_headers": False,
        },
        "options": [
            {
                "option_id": "P0_UNPACED_INTERLEAVED_C1_C2_C3",
                "inter_call_delay_ms": 0,
                "rule": (
                    "Retain current deterministic sequential execution order (C1 -> C2 -> C3 for each fixture 001..060) "
                    "with 0 ms artificial inter-call delay."
                ),
                "added_wall_clock_seconds_180_cells": 0,
                "scientific_and_engineering_assessment": (
                    "When all three providers take 20..50s per call, natural inter-call spacing for any single provider is "
                    "40..100s. However, if two providers fail fast (e.g., <2s HTTP 400/429), consecutive calls to the remaining "
                    "provider occur nearly back-to-back."
                ),
            },
            {
                "option_id": "P1_FIXED_2000MS_INTER_CALL_DELAY",
                "inter_call_delay_ms": 2000,
                "rule": (
                    "Insert a fixed, unconditional 2,000 ms (2.0s) deterministic pause between every consecutive cell execution "
                    "(179 intervals for 180 cells), independent of cell outcome or candidate."
                ),
                "added_wall_clock_seconds_180_cells": 358,
                "scientific_and_engineering_assessment": (
                    "Adds only 5.97 minutes across a 180-cell batch while guaranteeing at least 6.0 seconds between same-provider "
                    "requests even in the worst case where the other two providers fail instantaneously."
                ),
            },
            {
                "option_id": "P2_FIXED_5000MS_INTER_CALL_DELAY",
                "inter_call_delay_ms": 5000,
                "rule": (
                    "Insert a fixed, unconditional 5,000 ms (5.0s) deterministic pause between every consecutive cell execution "
                    "(179 intervals for 180 cells), independent of cell outcome or candidate."
                ),
                "added_wall_clock_seconds_180_cells": 895,
                "scientific_and_engineering_assessment": (
                    "Adds 14.92 minutes across a 180-cell batch and guarantees at least 15.0 seconds (<=4 RPM) between consecutive "
                    "calls to the same provider regardless of how fast other candidates return."
                ),
            },
        ],
    }


def build_retry_policy_options() -> dict[str, Any]:
    """Build Section 6D retry policy options (`retry = 0` default)."""
    return {
        "default_proposal_option_id": "R0_STRICT_ZERO_RETRY",
        "selected_retry_option_id": "R0_STRICT_ZERO_RETRY",
        "options": [
            {
                "option_id": "R0_STRICT_ZERO_RETRY",
                "recommendation_status": "DEFAULT_PROPOSED",
                "retry": 0,
                "automatic_retry": 0,
                "transport_retry": 0,
                "llm_repair": 0,
                "manual_retry": 0,
                "fallback": False,
                "rationale": (
                    "Preserves the core W06 one-shot per-cell scientific measurement contract: every cell makes at most 1 "
                    "outbound HTTP generation request, keeping call count, cost envelope, and failure attribution strictly deterministic."
                ),
            },
            {
                "option_id": "R1_BOUNDED_TRANSPORT_RETRY_ALTERNATIVE",
                "recommendation_status": "NOT_RECOMMENDED_WITHOUT_MAJOR_METHODOLOGY_CHANGE",
                "retry": 1,
                "rationale": (
                    "Marked NOT_RECOMMENDED_WITHOUT_MAJOR_METHODOLOGY_CHANGE. Allowing even 1 transport retry on HTTP 503/504/timeout "
                    "breaks the 1-call-per-cell invariant, doubles worst-case call and cost exposure, and confounds single-shot "
                    "reliability with retry recovery."
                ),
            },
        ],
    }


def build_provider_readiness_attestation_design() -> dict[str, Any]:
    """Build Section 7 pre-live provider-readiness gate design (zero live calls in PREP)."""
    return {
        "gate_id": "W06-DEV-SELECT-AMENDED-PRE-LIVE-PROVIDER-READINESS-GATE-V1",
        "generation_calls_performed_during_prep": 0,
        "secret_safety_invariants": {
            "print_secret_values": False,
            "print_secret_hashes": False,
            "print_secret_prefixes_or_suffixes": False,
            "print_sensitive_account_or_org_ids": False,
        },
        "candidates": {
            "C1": {
                "candidate_id": "C1",
                "provider": CANDIDATE_PROVIDER_BY_ID["C1"],
                "requested_model_id": CANDIDATE_MODEL_BY_ID["C1"],
                "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C1"],
                "owner_action_marker": "OWNER_ACTION_REQUIRED",
                "required_attestations_before_amended_live_authorization": [
                    "API key presence verified as boolean PRESENT without reading or logging secret value/hash/prefix/suffix.",
                    "Account/project identity consistency verified so the configured GEMINI_API_KEY belongs to the intended billing-enabled project without disclosing project/account identifiers.",
                    "Paid tier / quota readiness attested as sufficient for the planned C1 call count (eliminating the 20 requests/day Free Tier ceiling observed in 35/60 primary C1 cells).",
                    "No known daily-call (RPD) or per-minute (RPM/TPM) ceiling below the planned C1 batch call count.",
                    "Model access verified for gemini-3.8-flash under Portable Schema V2.",
                ],
            },
            "C2": {
                "candidate_id": "C2",
                "provider": CANDIDATE_PROVIDER_BY_ID["C2"],
                "requested_model_id": CANDIDATE_MODEL_BY_ID["C2"],
                "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C2"],
                "owner_action_marker": "OWNER_ACTION_REQUIRED",
                "required_attestations_before_amended_live_authorization": [
                    "API key presence verified as boolean PRESENT without reading or logging secret value/hash/prefix/suffix.",
                    "Active billing/credit balance verified as sufficient for the planned C2 call count under higher timeout ceiling (confirming no billing/quota blocker is present, consistent with 0/60 billing/quota errors in primary DEV-SELECT).",
                    "Model access verified for gpt-6.1-sol under Portable Schema V2.",
                ],
            },
            "C3": {
                "candidate_id": "C3",
                "provider": CANDIDATE_PROVIDER_BY_ID["C3"],
                "requested_model_id": CANDIDATE_MODEL_BY_ID["C3"],
                "env_key_name": CANDIDATE_ENV_KEY_BY_ID["C3"],
                "owner_action_marker": "OWNER_ACTION_REQUIRED",
                "required_attestations_before_amended_live_authorization": [
                    "API key presence verified as boolean PRESENT without reading or logging secret value/hash/prefix/suffix.",
                    "Anthropic API billing/credit status verified as active with positive credit balance (resolving the 60/60 HTTP 400 credit-balance rejection observed in primary DEV-SELECT).",
                    "Credit envelope attested as sufficient for the full planned C3 call count with safety margin.",
                    "Model access verified for claude-sonnet-5-5 under Portable Schema V2.",
                ],
            },
        },
    }


def build_fairness_policy_options() -> dict[str, Any]:
    """Build Section 9 fairness policy options (Options A, B, C)."""
    return {
        "selected_fairness_policy_option_id": None,
        "selection_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "options": [
            {
                "option_id": "OPTION_A_MINIMAL_ENVIRONMENT_REPAIR",
                "title": "Option A: Minimal Environment Repair",
                "specification": {
                    "provider_billing_and_quota_readiness_fixed": True,
                    "timeout_policy": "INCREASED_TO_SINGLE_FIXED_CANDIDATE_VALUE_ACROSS_ALL_CANDIDATES",
                    "pacing_policy": "P0_UNPACED_INTERLEAVED_C1_C2_C3",
                    "retry": 0,
                    "prompt_id": "P1",
                    "candidates": list(ORDERED_CANDIDATE_IDS),
                    "primary_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                },
                "advantages": [
                    "Changes only the two directly evidenced environmental blockers (provider billing/quota provisioning and the 55s timeout boundary) while keeping execution pacing identical to the primary run.",
                    "Enables direct observation of C1, C2, and C3 planning quality across 2-day, 3-day, and 4-day scenarios.",
                    "Preserves retry=0, prompt P1, Portable Schema V2, and all primary evaluation metrics.",
                ],
                "scientific_weaknesses": [
                    " constitutes a secondary post-hoc stabilization track after observing primary operational failures, requiring dual reporting alongside the primary benchmark.",
                    "Without inter-call pacing, if one candidate still fails rapidly, consecutive calls to the remaining candidates occur with minimal spacing.",
                ],
                "engineering_weaknesses": [
                    "Does not add deterministic inter-call spacing to smooth transient provider burst load (such as the 10/60 C1 HTTP 503 high-demand errors).",
                ],
                "cost_implications": (
                    "Requires funding/provisioning one amended comparative batch (e.g., 180 calls under S1, estimated $12.357 LOW to $24.03 HIGH under frozen runner registry pricing)."
                ),
                "defense_thesis_implications": (
                    "Clear and parsimonious to defend in thesis: primary benchmark documents strict 55s one-shot operational reality, "
                    "while secondary stabilization track isolates model planning quality once billing/quota and 55s truncation are removed."
                ),
                "risk_to_final100_quality": (
                    "LOW_TO_MODERATE: Substantially lowers the risk of picking a suboptimal model or running Final100 with a censoring timeout, "
                    "provided provider burst capacity remains stable."
                ),
            },
            {
                "option_id": "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT",
                "title": "Option B: Conservative Reliability Environment",
                "specification": {
                    "provider_billing_and_quota_readiness_fixed": True,
                    "pre_live_provider_readiness_attestation_gate": True,
                    "timeout_policy": "STRONGER_FIXED_TIMEOUT_CEILING_ACROSS_ALL_CANDIDATES (e.g. T3_180S or T2_120S)",
                    "pacing_policy": "DETERMINISTIC_FIXED_INTER_CALL_DELAY (e.g. P1_2000MS or P2_5000MS)",
                    "retry": 0,
                    "prompt_id": "P1",
                    "candidates": list(ORDERED_CANDIDATE_IDS),
                    "primary_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                },
                "advantages": [
                    "Addresses all three operational failure modes observed in the diagnostic: account/quota readiness (C1 429, C3 400), 55s timeout censoring (C2 52/60, C1 14/60), and burst spacing via deterministic non-adaptive pacing.",
                    "Includes a formal pre-live provider-readiness attestation gate so a batch is not launched against an unprovisioned account.",
                    "Maintains strict fairness across C1, C2, and C3 (identical timeout, identical deterministic pacing, retry=0, same P1 and V2 schema).",
                ],
                "scientific_weaknesses": [
                    "Introduces two controlled execution-environment changes (timeout ceiling + fixed inter-call pacing) relative to the primary track, so differences from the primary run reflect the combined stabilization environment rather than timeout alone.",
                ],
                "engineering_weaknesses": [
                    "Slightly longer wall-clock batch runtime (+5.97 min for 2s pacing or +14.92 min for 5s pacing, plus higher timeout ceiling on any genuinely hung socket).",
                ],
                "cost_implications": (
                    "Same comparative generation call cost as Option A (plus optional 3..9 smoke/readiness calls if paired with S2/F3, adding ~$0.25..$0.70)."
                ),
                "defense_thesis_implications": (
                    "Strongest methodological defense: demonstrates rigorous root-cause diagnosis followed by a pre-attested, symmetric, "
                    "non-adaptive stabilization protocol before committing the locked Final100 evaluation."
                ),
                "risk_to_final100_quality": (
                    "LOW: Provides the highest probability of obtaining complete, valid comparative measurements across all three candidates "
                    "and carrying a validated execution environment into Stochasticity and Final100."
                ),
            },
            {
                "option_id": "OPTION_C_NO_AMENDED_COMPARATIVE_BENCHMARK",
                "title": "Option C: No Amended Comparative Benchmark",
                "specification": {
                    "provider_billing_and_quota_readiness_fixed": False,
                    "accept_primary_180_cell_results_for_selection": True,
                    "select_under_original_preregistered_criteria": True,
                    "engineering_stabilization_only_after_winner_selection": True,
                    "retry": 0,
                    "prompt_id": "P1",
                    "candidates": list(ORDERED_CANDIDATE_IDS),
                    "primary_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                },
                "advantages": [
                    "Zero additional DEV-SELECT provider calls or cost ($0.00 new DEV-SELECT spend).",
                    "Strict adherence to the initial one-shot preregistered execution without a secondary comparative track.",
                ],
                "scientific_weaknesses": [
                    "SEVERE: Selects a winner when C3 had 0/60 model generations due to account credit balance, C1 had 35/60 Free Tier quota rejections, and C2 had 52/60 55s timeouts with 0/40 completions on 3-day and 4-day scenarios.",
                    "Confounds administrative account provisioning and a 55s client timeout with intrinsic model planning quality.",
                ],
                "engineering_weaknesses": [
                    "Winner selection would be based on only 9/180 completed cells (8 C2 2-day cells and 1 C1 2-day cell), leaving 3-day and 4-day itinerary capability unverified prior to Final100.",
                ],
                "cost_implications": (
                    "Zero immediate DEV-SELECT cost, but high risk of wasted spend or failed execution in Stochasticity and Final100 if environment parameters are adjusted ad hoc later."
                ),
                "defense_thesis_implications": (
                    "Vulnerable to thesis committee critique that C3 was never evaluated and C1/C2 were predominantly censored by quota/timeout settings rather than evaluated on itinerary planning quality."
                ),
                "risk_to_final100_quality": (
                    "HIGH: Proceeding to Final100 without first validating multi-day completion stability and fair 3-candidate comparison risks either massive Final100 timeouts or unvalidated model selection."
                ),
            },
        ],
    }


def build_fixture_policy_options(repo_root: Path) -> dict[str, Any]:
    """Build Section 10 dataset / fixture policy analysis (Policies F1, F2, F3)."""
    if (
        _read_lf_sha256(repo_root / DEV_FIXTURES_FREEZE_REL_PATH)
        != DEV_FIXTURES_FREEZE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("DEV_FIXTURES_FREEZE_SHA256_MISMATCH")
    dev_bundle = load_and_verify_frozen_dev_bundle()
    if (
        len(dev_bundle.dev_select_fixtures) != 60
        or len(dev_bundle.dev_tune_fixtures) != 20
    ):
        raise PlanBeforeLiveProtocolError(
            "DEV_FIXTURE_BUNDLE_COUNT_MISMATCH: expected 60 DEV-SELECT and 20 DEV-TUNE fixtures"
        )

    return {
        "selected_fixture_policy_id": None,
        "selection_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "final100_scenarios_inspected_or_used": False,
        "final100_calibration_forbidden": True,
        "frozen_dev_pool_summary": {
            "source_file": DEV_FIXTURES_FREEZE_REL_PATH,
            "source_file_sha256": DEV_FIXTURES_FREEZE_SHA256,
            "total_dev_fixtures": 80,
            "dev_tune_fixture_count": 20,
            "dev_tune_id_range": "W06-DEV-TUNE-001..W06-DEV-TUNE-020",
            "dev_select_fixture_count": 60,
            "dev_select_id_range": "W06-DEV-SELECT-001..W06-DEV-SELECT-060",
            "preflight_smoke_fixture_id": "W06-PREFLIGHT-SMOKE-001",
        },
        "options": [
            {
                "policy_id": "POLICY_F1_REUSE_EXISTING_DEV_SELECT_60",
                "title": "Policy F1: Reuse Exact Existing DEV-SELECT 60 Fixtures (W06-DEV-SELECT-001..060)",
                "fixture_count_comparative": 60,
                "fixture_source": "W06-DEV-SELECT-001..W06-DEV-SELECT-060 (exact 60 fixtures from w06_dev_fixtures_freeze_v1.json)",
                "post_hoc_bias_risk": (
                    "LOW: Although 9/180 cells completed in the primary run, no prompt, schema, or model parameter is being tuned; "
                    "only uniform execution-environment parameters (billing/quota readiness and timeout/pacing) are stabilized."
                ),
                "comparability_to_primary": (
                    "HIGHEST (1-to-1 cell correspondence across all 60 scenarios, preserving the exact 20x3 destination, "
                    "20x3 day-duration, 20x3 interest-count, and 15x4 budget/style marginal balance)."
                ),
                "risk_of_overfitting_after_observing_results": (
                    "VERY_LOW: Prompt P1, candidate models C1/C2/C3, Portable Schema V2, and evaluator rules remain strictly frozen; "
                    "environment stabilization cannot overfit itinerary content to specific scenarios."
                ),
                "final100_leakage_risk": (
                    "ZERO (strictly disjoint from w06_scenarios_freeze_v1.json as attested by w06_dev_final_overlap_receipt_v1.json)."
                ),
                "implementation_complexity": (
                    "LOW: Reuses the exact 60 frozen DEV-SELECT scenario definitions and prompt hashes."
                ),
            },
            {
                "policy_id": "POLICY_F2_SECONDARY_STABILIZATION_FROM_NON_FINAL_FROZEN_DEV",
                "title": "Policy F2: Construct Secondary Stabilization Set from Non-Final Frozen DEV Material",
                "fixture_count_comparative": 30,
                "fixture_source": (
                    "Stratified subset drawn from w06_dev_fixtures_freeze_v1.json (e.g., 20 DEV-TUNE fixtures W06-DEV-TUNE-001..020 "
                    "or a balanced 30-fixture stratified subset across destination x days x interests without touching Final100)."
                ),
                "post_hoc_bias_risk": (
                    "LOW_TO_MODERATE: Drawing a new subset after observing primary results introduces subset-selection degrees of freedom "
                    "unless the subset rule is fixed deterministically by ChatGPT."
                ),
                "comparability_to_primary": (
                    "LOWER: Loses 1-to-1 scenario correspondence and reduces statistical precision (wider binomial confidence intervals "
                    "under the 10 percentage-point practical-tie rule)."
                ),
                "risk_of_overfitting_after_observing_results": (
                    "LOW (since P1 and models are frozen), though using DEV-TUNE fixtures overlaps with the 5 stochasticity fixtures "
                    "(W06-DEV-TUNE-001..005)."
                ),
                "final100_leakage_risk": (
                    "ZERO (restricted to w06_dev_fixtures_freeze_v1.json; Final100 remains untouched)."
                ),
                "implementation_complexity": (
                    "MODERATE: Requires defining and freezing a new subset manifest and marginal-balance verification receipt."
                ),
            },
            {
                "policy_id": "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET",
                "title": "Policy F3: Small Engineering Readiness Canary Subset Followed by Full 60-Fixture Comparative Set",
                "fixture_count_readiness_canary": 3,
                "fixture_count_comparative": 60,
                "fixture_source": (
                    "Stage 1 Readiness Canary: 3 deterministic non-Final fixtures spanning 2, 3, and 4 days from DEV-TUNE "
                    "(or 1 synthetic smoke fixture W06-PREFLIGHT-SMOKE-001) x 3 candidates (3..9 calls, zero selection weight). "
                    "Stage 2 Comparative Batch: exact 60 DEV-SELECT fixtures W06-DEV-SELECT-001..060 x 3 candidates (180 calls)."
                ),
                "post_hoc_bias_risk": (
                    "LOW: Stage 1 is strictly a binary operational gate (verifying HTTP 200, billing/quota readiness, and non-truncation "
                    "under the chosen timeout) with zero prompt/model tuning, while Stage 2 uses the full balanced 60-fixture DEV-SELECT set."
                ),
                "comparability_to_primary": (
                    "HIGHEST: Stage 2 retains full 1-to-1 comparability with the 60 primary DEV-SELECT fixtures."
                ),
                "risk_of_overfitting_after_observing_results": (
                    "VERY_LOW: Canary outcomes cannot modify prompts, schemas, or candidate models; they only prevent launching "
                    "the 180-cell comparative batch if an account or timeout misconfiguration persists."
                ),
                "final100_leakage_risk": (
                    "ZERO (uses only DEV-TUNE / W06-PREFLIGHT-SMOKE-001 and DEV-SELECT-001..060; Final100 remains untouched)."
                ),
                "implementation_complexity": (
                    "LOW_TO_MODERATE: Clean separation between pre-batch readiness attestation receipt and comparative 180-cell execution."
                ),
            },
        ],
    }


def build_call_budget_options() -> dict[str, Any]:
    """Build Section 11 call-budget options (S1, S2, S3) with zero calls authorized."""
    return {
        "selected_call_budget_option_id": None,
        "authorized_generation_calls_in_prep": 0,
        "selection_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "options": [
            {
                "budget_option_id": "S1_FULL_COMPARATIVE_180",
                "title": "S1: 3 Candidates x 60 Comparative Cells = 180 Calls",
                "readiness_canary_calls": 0,
                "comparative_benchmark_calls": 180,
                "maximum_generation_calls": 180,
                "calls_per_candidate": {"C1": 60, "C2": 60, "C3": 60},
                "estimated_relative_cost_exposure": "1.00x baseline comparative batch ($12.357 LOW to $24.03 HIGH under frozen runner registry pricing; $10.5525 LOW to $20.565 HIGH under Preflight 01D pricing)",
                "scientific_strength": (
                    "HIGH: Preserves the full n=60 per-candidate denominator and exact 20x3 destination / 20x3 day-duration "
                    "stratification required by W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01."
                ),
                "selection_confidence": (
                    "HIGH: Full 60-cell resolution (1 cell = 1.67 percentage points) for applying the 10 percentage-point "
                    "(6-cell) practical-tie survivor threshold."
                ),
                "operational_risk": (
                    "MODERATE: If a provider account or timeout issue was not caught before launch, it is discovered directly "
                    "inside the 180-call comparative batch."
                ),
            },
            {
                "budget_option_id": "S2_READINESS_CANARY_PLUS_COMPARATIVE_180",
                "title": "S2: Small Engineering Readiness Phase (3..9 Calls) + 3 Candidates x 60 Comparative Cells (180 Calls)",
                "readiness_canary_calls_min": 3,
                "readiness_canary_calls_max": 9,
                "comparative_benchmark_calls": 180,
                "maximum_generation_calls": 189,
                "calls_per_candidate": {"C1": 63, "C2": 63, "C3": 63},
                "estimated_relative_cost_exposure": "1.05x baseline comparative batch ($12.97485 LOW to $25.2315 HIGH for 189 calls under frozen runner registry pricing; $11.080125 LOW to $21.59325 HIGH under Preflight 01D pricing)",
                "scientific_strength": (
                    "HIGHEST: Combines pre-batch operational verification on 2/3/4-day canary scenarios with the full "
                    "uncompromised 180-cell comparative benchmark."
                ),
                "selection_confidence": (
                    "HIGHEST: Full n=60 per-candidate comparative denominator protected by pre-verified billing, quota, and timeout readiness."
                ),
                "operational_risk": (
                    "LOW: Any residual billing, quota, or timeout misconfiguration halts at <=9 canary calls before the "
                    "180-cell comparative batch is committed."
                ),
            },
            {
                "budget_option_id": "S3_REDUCED_STRATIFIED_COMPARATIVE_90",
                "title": "S3: Smaller Amended Comparative Benchmark (3 Candidates x 30 Stratified Cells = 90 Calls)",
                "readiness_canary_calls": 0,
                "comparative_benchmark_calls": 90,
                "maximum_generation_calls": 90,
                "calls_per_candidate": {"C1": 30, "C2": 30, "C3": 30},
                "estimated_relative_cost_exposure": "0.50x baseline comparative batch ($6.1785 LOW to $12.015 HIGH under frozen runner registry pricing; $5.27625 LOW to $10.2825 HIGH under Preflight 01D pricing)",
                "scientific_strength": (
                    "MODERATE: Reduces per-candidate sample size from 60 to 30 (10 per destination, 10 per day duration), "
                    "increasing sampling variance by sqrt(2) (+41.4%)."
                ),
                "selection_confidence": (
                    "MODERATE: Each cell represents 3.33 percentage points (3 cells = 10.0 percentage points), making the "
                    "10 percentage-point practical-tie threshold more sensitive to 1..2 boundary cells."
                ),
                "operational_risk": (
                    "LOW_TO_MODERATE: Halves call volume, daily quota consumption (30 calls/provider), and wall-clock runtime, "
                    "useful if provider daily quota or budget constraints are tight."
                ),
            },
        ],
    }


def build_cost_planning_analysis(
    observed_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Build Section 12 cost-planning methodology and LOW / HIGH / CONDITIONAL_MAX_OUTPUT envelopes."""
    # Frozen repository pricing snapshot 1: dev_live_runner.py DEFAULT_COST_COMPARABILITY_BY_CANDIDATE (2026-10-16)
    runner_rates: dict[str, dict[str, Decimal]] = {}
    for cid in ORDERED_CANDIDATE_IDS:
        rec = DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[cid]
        runner_rates[cid] = {
            "input_per_m": Decimal(str(rec.input_price_per_million_usd)),
            "output_per_m": Decimal(str(rec.output_price_per_million_usd)),
        }

    # Frozen repository pricing snapshot 2: w06_model_preflight_01d_v2_live_receipt_v1.json (2026-10-17)
    preflight_01d_rates: dict[str, dict[str, Decimal]] = {
        "C1": {"input_per_m": Decimal("0.75"), "output_per_m": Decimal("3.75")},
        "C2": {"input_per_m": Decimal("2.00"), "output_per_m": Decimal("10.00")},
        "C3": {"input_per_m": Decimal("2.00"), "output_per_m": Decimal("10.00")},
    }

    # Token envelopes per call grounded in observed DEV-SELECTraw_usage_metadata:
    # - Observed C1 completed cell (Da Nang, 92.8 KB wire): input=38,272, output+thought=6,068
    # - Observed C2 completed cells (n=8, 54.7..93.2 KB wire): input=16,086..28,410, output=2,885..4,512
    # - Configured max_output_tokens ceiling across all 180 cells = 16,384
    token_profiles = {
        "LOW_PLANNING_ENVELOPE": {
            "description": (
                "Grounded in lower-to-median observed prompt + catalog token footprint and compact 2..3 day "
                "structured JSON output + moderate reasoning/thinking token overhead."
            ),
            "per_call_tokens_by_candidate": {
                "C1": {"input_tokens": 24000, "billable_output_plus_thought_tokens": 4500},
                "C2": {"input_tokens": 18000, "billable_output_plus_thought_tokens": 3000},
                "C3": {"input_tokens": 20000, "billable_output_plus_thought_tokens": 3500},
            },
        },
        "HIGH_PLANNING_ENVELOPE": {
            "description": (
                "Grounded in upper observed catalog token footprint (~93 KB wire payload) and heavy 3..4 day "
                "structured JSON output + reasoning/adaptive-thinking token consumption."
            ),
            "per_call_tokens_by_candidate": {
                "C1": {"input_tokens": 40000, "billable_output_plus_thought_tokens": 9000},
                "C2": {"input_tokens": 30000, "billable_output_plus_thought_tokens": 7500},
                "C3": {"input_tokens": 32000, "billable_output_plus_thought_tokens": 8000},
            },
        },
        "CONDITIONAL_MAX_OUTPUT_REFERENCE": {
            "description": (
                "Conditional upper reference assuming every single call consumes upper input tokens AND reaches "
                "the configured max_output_tokens = 16,384 ceiling. Not a hard invoice maximum if a provider bills "
                "internal thinking tokens outside max_output_tokens or bills partial generation on timeout."
            ),
            "per_call_tokens_by_candidate": {
                "C1": {"input_tokens": 40000, "billable_output_plus_thought_tokens": 16384},
                "C2": {"input_tokens": 30000, "billable_output_plus_thought_tokens": 16384},
                "C3": {"input_tokens": 32000, "billable_output_plus_thought_tokens": 16384},
            },
        },
    }

    def _compute_envelope(
        rates: Mapping[str, Mapping[str, Decimal]],
        calls_per_candidate: int,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for env_name, env_spec in token_profiles.items():
            by_cand: dict[str, str] = {}
            total = Decimal("0")
            for cid in ORDERED_CANDIDATE_IDS:
                tok = env_spec["per_call_tokens_by_candidate"][cid]
                in_tok = Decimal(str(tok["input_tokens"]))
                out_tok = Decimal(str(tok["billable_output_plus_thought_tokens"]))
                call_cost = (
                    (in_tok * rates[cid]["input_per_m"])
                    + (out_tok * rates[cid]["output_per_m"])
                ) / Decimal("1000000")
                cand_total = call_cost * Decimal(str(calls_per_candidate))
                by_cand[cid] = _format_usd(cand_total)
                total += cand_total
            result[env_name] = {
                "by_candidate_usd": by_cand,
                "total_usd": _format_usd(total),
            }
        return result

    return {
        "current_price_input_status": "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION",
        "hard_maximum_claimed": False,
        "why_hard_maximum_is_not_claimed": (
            "A hard invoice maximum cannot be claimed offline because: (1) repository pricing snapshots from 2026-10-16 "
            "(dev_live_runner.py) and 2026-10-17 (w06_model_preflight_01d_v2_live_receipt_v1.json) differ slightly and must be "
            "refreshed against live provider pricing schedules before authorization; (2) provider billing treatment of internal "
            "reasoning/thinking tokens relative to max_output_tokens=16,384 varies by provider; and (3) providers may bill for "
            "tokens generated prior to a client-side or gateway timeout even when the client receives no usage_metadata."
        ),
        "cost_category_separation": {
            "planning_estimate": (
                "Pre-execution analytical cost envelope (LOW / HIGH / CONDITIONAL_MAX_OUTPUT_REFERENCE) computed from token profiles "
                "and reference price tables to size account credit provisioning before authorization."
            ),
            "authoritative_provider_receipt_cost": (
                "Post-execution deterministic token-usage cost computed in execution_receipt.json from provider-returned "
                "usage_metadata and the frozen CandidateCostComparabilityRecord rate table."
            ),
            "provider_invoice": (
                "Actual financial charge billed on the Project Owner's Google Cloud / OpenAI / Anthropic billing statement, "
                "which is external to the benchmark harness."
            ),
        },
        "frozen_repository_pricing_snapshots": {
            "runner_registry_2026_10_16": {
                cid: {
                    "pricing_source": DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        cid
                    ].pricing_source,
                    "pricing_access_date": DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        cid
                    ].pricing_access_date,
                    "input_price_per_million_usd": format_canonical_decimal_str(
                        runner_rates[cid]["input_per_m"]
                    ),
                    "output_price_per_million_usd": format_canonical_decimal_str(
                        runner_rates[cid]["output_per_m"]
                    ),
                }
                for cid in ORDERED_CANDIDATE_IDS
            },
            "preflight_01d_receipt_2026_10_17": {
                cid: {
                    "pricing_source": "w06_model_preflight_01d_v2_live_receipt_v1.json",
                    "pricing_access_date": "2026-10-17",
                    "input_price_per_million_usd": format_canonical_decimal_str(
                        preflight_01d_rates[cid]["input_per_m"]
                    ),
                    "output_price_per_million_usd": format_canonical_decimal_str(
                        preflight_01d_rates[cid]["output_per_m"]
                    ),
                }
                for cid in ORDERED_CANDIDATE_IDS
            },
        },
        "observed_primary_token_and_cost_evidence": dict(observed_evidence),
        "token_envelope_assumptions": token_profiles,
        "envelopes_by_call_budget_under_runner_registry_2026_10_16_pricing": {
            "S1_180_CALLS_60_PER_CANDIDATE": _compute_envelope(runner_rates, 60),
            "S2_189_CALLS_63_PER_CANDIDATE": _compute_envelope(runner_rates, 63),
            "S3_90_CALLS_30_PER_CANDIDATE": _compute_envelope(runner_rates, 30),
        },
        "envelopes_by_call_budget_under_preflight_01d_2026_10_17_pricing": {
            "S1_180_CALLS_60_PER_CANDIDATE": _compute_envelope(
                preflight_01d_rates, 60
            ),
            "S2_189_CALLS_63_PER_CANDIDATE": _compute_envelope(
                preflight_01d_rates, 63
            ),
            "S3_90_CALLS_30_PER_CANDIDATE": _compute_envelope(
                preflight_01d_rates, 30
            ),
        },
    }


def build_anty_analytical_recommendation() -> dict[str, Any]:
    """Build Section 13 advisory recommendation (`FINAL_METHODOLOGY_DECISION_AUTHORITY = CHATGPT`)."""
    return {
        "advisory_only": True,
        "recommendation_implemented": False,
        "final_methodology_decision_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
        "recommended_policy_bundle": {
            "amendment_track_classification": AMENDMENT_TRACK_CLASSIFICATION,
            "fairness_policy_option_id": "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT",
            "timeout_policy_option_id": "T3_CANDIDATE_180S",
            "pacing_policy_option_id": "P1_FIXED_2000MS_INTER_CALL_DELAY",
            "retry_policy_option_id": "R0_STRICT_ZERO_RETRY",
            "fixture_policy_option_id": "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET",
            "call_budget_option_id": "S2_READINESS_CANARY_PLUS_COMPARATIVE_180",
        },
        "criteria_evaluation": {
            "scientific_defensibility": (
                "Preserves the primary 180-cell one-shot benchmark immutable and reportable, while executing a clearly labeled "
                "secondary stabilization track on the exact 60 balanced DEV-SELECT fixtures under retry=0, prompt P1, and Schema V2."
            ),
            "fair_provider_conditions": (
                "Verifies paid quota on C1 (Google), active credit balance on C3 (Anthropic), and billing readiness on C2 (OpenAI) "
                "via a pre-live readiness canary before comparative execution, applying the exact same 180s timeout and 2.0s deterministic "
                "inter-call spacing to all three candidates."
            ),
            "planner_quality_observability": (
                "Eliminates the 55s boundary truncation that censored 52/60 C2 cells (including 40/40 3-day and 4-day scenarios) "
                "and 14/60 C1 cells, allowing true observation of schema validity, grounding accuracy, and core constraint satisfaction."
            ),
            "final100_risk": (
                "Protects Final100 completely during amendment prep and execution (zero Final100 access), while ensuring the winning "
                "candidate and operational timeout/pacing parameters are empirically validated on 3-day and 4-day scenarios before Final100."
            ),
            "cost": (
                "Bounded and modest: $12.97485 LOW to $25.2315 HIGH total across 189 calls (9 canary + 180 comparative) under frozen runner "
                "registry rates ($11.080125 LOW to $21.59325 HIGH under Preflight 01D rates), with the 9-call canary preventing wasted spend if any account issue remains."
            ),
            "time": (
                "2.0s deterministic inter-call pacing adds only ~6.3 minutes across 189 calls, and healthy responses return as soon as "
                "generation completes without waiting for the 180s timeout ceiling."
            ),
            "thesis_defense_quality": (
                "Provides a transparent two-track empirical narrative: Track 1 reports strict preregistered 55s operational fragility "
                "(9/180 completions), and Track 2 reports controlled comparative model quality once administrative/timeout confounders are removed."
            ),
        },
    }


def build_project_owner_action_matrix() -> list[dict[str, Any]]:
    """Build Section 14 machine-readable Project Owner Action Matrix."""
    return [
        {
            "action_id": "POA-01",
            "action": (
                "Verify Anthropic console Plans & Billing status and ensure positive credit balance sufficient for planned C3 calls "
                "(>=63 calls under S2 or >=60 calls under S1, recommended >=$15..$20 credit headroom)."
            ),
            "provider": "anthropic (C3 / claude-sonnet-5-5)",
            "required_before_which_gate": "W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE",
            "mandatory_or_optional": "MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED",
            "reason": (
                "60/60 primary C3 cells failed with HTTP 400 invalid_request_error: "
                "'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'"
            ),
            "how_to_verify_without_secret_disclosure": (
                "Project Owner confirms active positive credit tier in Anthropic Console and runs the future ChatGPT-approved "
                "pre-live readiness attestation check, which records only boolean readiness status and HTTP 200 model-access verification "
                "without logging API keys, hashes, prefixes, or organization IDs."
            ),
            "owner_action_marker": "OWNER_ACTION_REQUIRED",
            "status": "PENDING_CHATGPT_AMENDMENT_DECISION",
        },
        {
            "action_id": "POA-02",
            "action": (
                "Verify Google AI Studio / Google Cloud project bound to GEMINI_API_KEY is on Paid Tier (Pay-as-you-go) "
                "with daily request quota >=200 RPD and rate limits sufficient for >=63 C1 calls."
            ),
            "provider": "google (C1 / gemini-3.8-flash)",
            "required_before_which_gate": "W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE",
            "mandatory_or_optional": "MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED",
            "reason": (
                "35/60 primary C1 cells failed with HTTP 429 RESOURCE_EXHAUSTED explicitly citing quotaId "
                "'GenerateRequestsPerDayPerProjectPerModel-FreeTier' and quotaValue '20'."
            ),
            "how_to_verify_without_secret_disclosure": (
                "Project Owner confirms Paid Tier billing linkage in Google AI Studio / Cloud Console and records boolean "
                "tier attestation in the pre-live readiness receipt without disclosing project IDs, billing account IDs, or API key material."
            ),
            "owner_action_marker": "OWNER_ACTION_REQUIRED",
            "status": "PENDING_CHATGPT_AMENDMENT_DECISION",
        },
        {
            "action_id": "POA-03",
            "action": (
                "Verify OpenAI platform billing credit balance and usage tier limits for OPENAI_API_KEY are sufficient "
                "for >=63 C2 calls with up to 16,384 max_output_tokens."
            ),
            "provider": "openai (C2 / gpt-6.1-sol)",
            "required_before_which_gate": "W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE",
            "mandatory_or_optional": "MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED",
            "reason": (
                "Although C2 recorded 0/60 billing/quota errors in primary DEV-SELECT (8/60 NONE, 52/60 client timeout at 55s), "
                "longer timeouts allow all 60 cells to complete token generation and incur full output token billing (~$3.51..$7.50+)."
            ),
            "how_to_verify_without_secret_disclosure": (
                "Project Owner confirms positive OpenAI credit balance in OpenAI Platform Billing and records boolean readiness "
                "status without exposing API keys, organization IDs, or secret hashes."
            ),
            "owner_action_marker": "OWNER_ACTION_REQUIRED",
            "status": "PENDING_CHATGPT_AMENDMENT_DECISION",
        },
        {
            "action_id": "POA-04",
            "action": (
                "Confirm current official per-million input/output/thinking token price schedules for C1 (gemini-3.8-flash), "
                "C2 (gpt-6.1-sol), and C3 (claude-sonnet-5-5) before amended live authorization."
            ),
            "provider": "all_providers (C1, C2, C3)",
            "required_before_which_gate": "W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE",
            "mandatory_or_optional": "OPTIONAL_FOR_OPERATIONAL_READINESS_MANDATORY_FOR_COST_TIEBREAK_AUTHORITY",
            "reason": (
                "Repository contains two historical pricing snapshots (2026-10-16 in dev_live_runner.py and 2026-10-17 in "
                "w06_model_preflight_01d_v2_live_receipt_v1.json); current_price_input_status is marked "
                "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION."
            ),
            "how_to_verify_without_secret_disclosure": (
                "Record public provider documentation URLs, access date, and per-million USD rates in the amended authorization plan "
                "(public pricing metadata contains no secrets)."
            ),
            "owner_action_marker": "OWNER_ACTION_REQUIRED",
            "status": "PENDING_CHATGPT_AMENDMENT_DECISION",
        },
    ]


# ==============================================================================
# 4. MASTER PAYLOAD COMPUTATION & VERIFICATION
# ==============================================================================


def compute_w06_execution_environment_amendment_prep_payload(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Deterministically compute the `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP-V1` artifact."""
    with NetworkKillSwitchGuard():
        _verify_git_base_lineage(repo_root)

        # 1. Run upstream offline verifiers (Section 1)
        freeze_summary = (
            _freeze_mod.verify_committed_results_freeze_artifacts_from_disk(
                repo_root=repo_root, verify_preflight_dry_run=False
            )
        )
        if not freeze_summary.get("verified"):
            raise PlanBeforeLiveProtocolError(
                "UPSTREAM_FREEZE_VERIFICATION_FAILED"
            )

        diag_summary = _diag_mod.verify_w06_dev_select_failure_diagnostic(
            repo_root=repo_root
        )
        if not diag_summary.get("verified"):
            raise PlanBeforeLiveProtocolError(
                "UPSTREAM_DIAGNOSTIC_VERIFICATION_FAILED"
            )

        # 2. Verify exact bound SHA256s (Section 2)
        if (
            freeze_summary["raw_evidence_tree_sha256"]
            != EXPECTED_RAW_EVIDENCE_TREE_SHA256
        ):
            raise PlanBeforeLiveProtocolError("RAW_EVIDENCE_TREE_SHA256_MISMATCH")

        manifest_path = repo_root / EXPECTED_RESULTS_MANIFEST_REL_PATH
        receipt_path = repo_root / EXPECTED_RESULTS_FREEZE_RECEIPT_REL_PATH
        diag_path = repo_root / EXPECTED_DIAGNOSTIC_ARTIFACT_REL_PATH

        if _read_lf_sha256(manifest_path) != EXPECTED_RESULTS_MANIFEST_FILE_SHA256:
            raise PlanBeforeLiveProtocolError("RESULTS_MANIFEST_FILE_SHA256_MISMATCH")
        if (
            _read_lf_sha256(receipt_path)
            != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "RESULTS_FREEZE_RECEIPT_FILE_SHA256_MISMATCH"
            )
        if _read_lf_sha256(diag_path) != EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256:
            raise PlanBeforeLiveProtocolError(
                "DIAGNOSTIC_ARTIFACT_FILE_SHA256_MISMATCH"
            )

        results_manifest = _load_json_dict(manifest_path)
        diagnostic_payload = _load_json_dict(diag_path)

        if (
            diagnostic_payload.get("diagnostic_artifact_sha256")
            != EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256_MISMATCH"
            )

        # 3. Verify scientific code bundle & Final100 firewall
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root)
        if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: {bundle_sha}"
            )

        final100_path = repo_root / _freeze_mod.FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
        p11_path = repo_root / _freeze_mod.FORBIDDEN_P11_MANIFEST_REL_PATH
        if _read_lf_sha256(final100_path) != FORBIDDEN_FINAL100_BUNDLE_SHA256:
            raise PlanBeforeLiveProtocolError("FINAL100_SCENARIOS_SHA256_MISMATCH")
        if _read_lf_sha256(p11_path) != FORBIDDEN_P11_MANIFEST_SHA256:
            raise PlanBeforeLiveProtocolError("P11_MANIFEST_SHA256_MISMATCH")

        for rel_forbidden in FORBIDDEN_AMENDED_OR_DOWNSTREAM_REL_PATHS:
            if (repo_root / rel_forbidden).exists():
                raise PlanBeforeLiveProtocolError(
                    f"FORBIDDEN_DOWNSTREAM_OR_AMENDED_ARTIFACT_PRESENT: {rel_forbidden}"
                )

        # 4. Build sections
        observed_token_cost = _collect_observed_token_and_cost_evidence(
            repo_root, results_manifest
        )
        timeout_policy_options = build_timeout_policy_options(diagnostic_payload)
        pacing_policy_options = build_pacing_policy_options()
        retry_policy_options = build_retry_policy_options()
        provider_readiness_design = build_provider_readiness_attestation_design()
        fairness_policy_options = build_fairness_policy_options()
        fixture_policy_options = build_fixture_policy_options(repo_root)
        call_budget_options = build_call_budget_options()
        cost_planning = build_cost_planning_analysis(observed_token_cost)
        recommendation = build_anty_analytical_recommendation()
        owner_action_matrix = build_project_owner_action_matrix()

        payload_without_self_hash: dict[str, Any] = {
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "AMENDMENT_APPROVED": False,
            "FINAL100_USED": False,
            "FINAL_METHODOLOGY_DECISION_AUTHORITY": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "MODEL_WINNER_SELECTED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "amended_live_authorized": False,
            "amended_live_executed": False,
            "amendment_approved": False,
            "amendment_classification": {
                "classification": AMENDMENT_TRACK_CLASSIFICATION,
                "forbidden_descriptions": list(FORBIDDEN_AMENDMENT_DESCRIPTIONS),
                "primary_experiment_remains_reportable": True,
                "primary_experiment_valid": True,
            },
            "amendment_scope_boundary": {
                "candidate_model_change_proposed": False,
                "candidates": dict(CANDIDATE_MODEL_BY_ID),
                "evaluator_semantics_unchanged": True,
                "final100_used_for_amendment_calibration": False,
                "fourth_model_addition_proposed": False,
                "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                "portable_schema_v2_unchanged": True,
                "primary_model_selection_metrics": list(PRIMARY_DEV_RATE_CRITERIA),
                "prompt_id": "P1",
                "prompt_retuning_proposed": False,
                "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
                "semantic_schema_unchanged": True,
                "ten_percentage_point_survivor_rule_threshold": format_canonical_decimal_str(
                    PRACTICAL_TIE_ABS_DIFF_RATIO
                ),
                "ten_percentage_point_survivor_rule_unchanged": True,
            },
            "anty_analytical_recommendation": recommendation,
            "artifact_id": PREP_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "call_budget_options": call_budget_options,
            "cost_planning": cost_planning,
            "evidence_supported_reasons_for_amendment_consideration": {
                "C1": {
                    "candidate_id": "C1",
                    "http_429_free_tier_quota_exhaustion_ratio": "35/60",
                    "http_503_high_demand_capacity_failure_ratio": "10/60",
                    "none_completed_ratio": "1/60",
                    "primary_counts": diagnostic_payload["primary_counts_by_candidate"][
                        "C1"
                    ],
                    "primary_timeout_breakdown": {
                        "client_read_timeout_count": 4,
                        "server_http_504_deadline_exceeded_count": 10,
                        "total_timeout_ratio": "14/60",
                    },
                    "secondary_counts": diagnostic_payload[
                        "secondary_counts_by_candidate"
                    ]["C1"],
                },
                "C2": {
                    "all_completed_cells_scenario_days": 2,
                    "candidate_id": "C2",
                    "client_api_timeout_error_ratio": "52/60",
                    "completed_3_day_or_4_day_cells": 0,
                    "frozen_timeout_ms": 55000,
                    "none_completed_latency_range_ms": [35812.0, 53094.0],
                    "none_completed_ratio": "8/60",
                    "primary_counts": diagnostic_payload["primary_counts_by_candidate"][
                        "C2"
                    ],
                    "secondary_counts": diagnostic_payload[
                        "secondary_counts_by_candidate"
                    ]["C2"],
                    "timeout_latency_range_ms": [55078.0, 55797.0],
                },
                "C3": {
                    "candidate_id": "C3",
                    "http_400_invalid_request_error_ratio": "60/60",
                    "model_generations_observed": 0,
                    "primary_counts": diagnostic_payload["primary_counts_by_candidate"][
                        "C3"
                    ],
                    "provider_declared_billing_credit_rejection_ratio": "60/60",
                    "secondary_counts": diagnostic_payload[
                        "secondary_counts_by_candidate"
                    ]["C3"],
                },
                "harness_and_binding_integrity": {
                    "cell_hash_chain_valid": "180/180",
                    "harness_or_binding_inconsistency_observed": False,
                    "model_id_mismatch_count": 0,
                    "request_identity_match": "180/180",
                    "rerun_cells": 0,
                    "retry_calls": 0,
                },
            },
            "execution_environment_factors_under_review": {
                "A_provider_readiness_account_provisioning": {
                    "C1": "Quota and Paid Tier rate-limit readiness sufficient for planned C1 call batch (removing 20 RPD Free Tier cap).",
                    "C2": "Confirm active API key, billing credit sufficiency, and model access; no billing/quota blocker was evidenced in primary DEV-SELECT (0/60 HTTP 429/400).",
                    "C3": "Anthropic API billing and positive credit balance sufficient for planned C3 call batch (resolving 60/60 HTTP 400 credit rejection).",
                },
                "B_request_timeout_policy": timeout_policy_options,
                "C_pacing_policy": pacing_policy_options,
                "D_retry_policy": retry_policy_options,
            },
            "fairness_policy_options": fairness_policy_options,
            "final100_used": False,
            "final_methodology_decision_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "fixture_policy_options": fixture_policy_options,
            "live_provider_calls_new": 0,
            "model_winner_selected": False,
            "next_gate": NEXT_GATE_ID,
            "pacing_policy_options": pacing_policy_options,
            "primary_denominators_changed": False,
            "primary_experiment_immutability": {
                "classification": PRIMARY_EXPERIMENT_CLASSIFICATION,
                "diagnostic_artifact_file_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256,
                "diagnostic_artifact_internal_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256,
                "primary_counts_by_candidate": diagnostic_payload[
                    "primary_counts_by_candidate"
                ],
                "primary_counts_total": diagnostic_payload["primary_counts_total"],
                "primary_denominators_by_candidate": {"C1": 60, "C2": 60, "C3": 60},
                "primary_failure_classification_authority": "execution_receipt.failure_classification",
                "prohibitions_enforced": {
                    "claim_primary_invalidated_by_amendment_proposal": False,
                    "change_primary_denominator": False,
                    "delete_primary_failures": False,
                    "overwrite_primary_manifests": False,
                    "reclassify_primary_failures": False,
                    "replace_primary_outputs": False,
                    "rerun_primary_cells": False,
                },
                "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
                "results_freeze_receipt_file_sha256": EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                "results_manifest_file_sha256": EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
            },
            "primary_experiment_mutated": False,
            "primary_results_replaced": False,
            "project_owner_action_matrix": owner_action_matrix,
            "proposed_status": "READY_FOR_CHATGPT_DECISION",
            "provider_readiness_attestation_design": provider_readiness_design,
            "retry_policy_options": retry_policy_options,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "selected_model_id": None,
            "stochasticity_execution_started": False,
            "task_id": TASK_ID,
            "timeout_policy_options": timeout_policy_options,
        }

        internal_sha = sha256_bytes(canonical_json_bytes(payload_without_self_hash))
        full_payload = dict(payload_without_self_hash)
        full_payload["prep_artifact_internal_sha256"] = internal_sha

        assert_no_secrets_in_payload(
            full_payload, context="W06_AMENDMENT_01_PREP_PAYLOAD"
        )
        return full_payload


def write_w06_execution_environment_amendment_prep_artifact(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Write `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_prep_v1.json`."""
    target_path = repo_root / PREP_ARTIFACT_REL_PATH
    _assert_not_inside_raw_evidence(target_path, repo_root)
    payload = compute_w06_execution_environment_amendment_prep_payload(
        repo_root=repo_root
    )
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(serialized.encode("utf-8"))
    file_sha = _read_lf_sha256(target_path)
    return {
        "prep_artifact_path": PREP_ARTIFACT_REL_PATH,
        "prep_artifact_file_sha256": file_sha,
        "prep_artifact_internal_sha256": payload["prep_artifact_internal_sha256"],
    }


def verify_w06_execution_environment_amendment_prep(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Statelessly verify the amendment-prep artifact and all upstream authorities."""
    with NetworkKillSwitchGuard():
        target_path = repo_root / PREP_ARTIFACT_REL_PATH
        if not target_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_PREP_ARTIFACT: {target_path}"
            )

        computed = compute_w06_execution_environment_amendment_prep_payload(
            repo_root=repo_root
        )
        disk_payload = _load_json_dict(target_path)
        assert_no_secrets_in_payload(
            disk_payload, context="W06_AMENDMENT_01_PREP_DISK"
        )

        disk_without_hash = dict(disk_payload)
        disk_internal_sha = disk_without_hash.pop(
            "prep_artifact_internal_sha256", None
        )
        recomputed_disk_internal_sha = sha256_bytes(
            canonical_json_bytes(disk_without_hash)
        )
        if disk_internal_sha != recomputed_disk_internal_sha:
            raise PlanBeforeLiveProtocolError(
                "PREP_ARTIFACT_INTERNAL_SHA256_TAMPERED"
            )

        if disk_payload != computed:
            raise PlanBeforeLiveProtocolError(
                "PREP_ARTIFACT_CONTENT_DRIFT_FROM_DETERMINISTIC_COMPUTATION"
            )

        file_sha = _read_lf_sha256(target_path)
        if (
            EXPECTED_PREP_ARTIFACT_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and file_sha != EXPECTED_PREP_ARTIFACT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREP_ARTIFACT_FILE_SHA256_MISMATCH: expected {EXPECTED_PREP_ARTIFACT_FILE_SHA256}, got {file_sha}"
            )
        if (
            EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and disk_internal_sha != EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREP_ARTIFACT_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256}, got {disk_internal_sha}"
            )

        return {
            "amended_live_authorized": False,
            "amended_live_executed": False,
            "amendment_approved": False,
            "artifact_id": PREP_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "diagnostic_artifact_file_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256,
            "diagnostic_artifact_internal_sha256": EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256,
            "final100_used": False,
            "final_methodology_decision_authority": FINAL_METHODOLOGY_DECISION_AUTHORITY,
            "live_provider_calls_new": 0,
            "model_winner_selected": False,
            "next_gate": NEXT_GATE_ID,
            "prep_artifact_file_sha256": file_sha,
            "prep_artifact_internal_sha256": disk_internal_sha,
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
        description="Prepare or verify W06 DEV-SELECT execution-environment amendment prep artifact."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the committed amendment-prep artifact without writing.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Deterministically generate and write the amendment-prep JSON artifact.",
    )
    args = parser.parse_args(argv)

    if args.write:
        write_info = write_w06_execution_environment_amendment_prep_artifact(
            repo_root=REPO_ROOT
        )
        print(json.dumps(write_info, indent=2, sort_keys=True))
        return 0

    summary = verify_w06_execution_environment_amendment_prep(repo_root=REPO_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
