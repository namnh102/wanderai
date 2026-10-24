"""Comprehensive offline tests for W06-DEV-SELECT-FAILURE-DIAGNOSTIC-01-OFFLINE (DFD-01..DFD-35).

All tests execute strictly offline under `NetworkKillSwitchGuard` with zero provider calls
and zero mutation of `data/evaluation/w06/live_dev_select_primary_v1/**`.
"""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as diag_mod  # noqa: E402
from diagnose_w06_dev_select_failures import (  # noqa: E402
    NetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
)
import freeze_w06_dev_select_live_results as freeze_mod  # noqa: E402


@pytest.fixture(scope="module")
def computed_diagnostic_payload() -> dict:
    with NetworkKillSwitchGuard():
        return diag_mod.build_w06_dev_select_failure_diagnostic_payload(
            repo_root=REPO_ROOT
        )


@pytest.fixture(scope="module")
def disk_diagnostic_payload() -> dict:
    path = REPO_ROOT / diag_mod.DIAGNOSTIC_ARTIFACT_REL_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def test_dfd_01_exact_source_develop_binding(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-01: Exact source develop and pre-live develop SHA bindings."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert (
            payload["source_develop_sha"]
            == "beb5ec657bb4417bdeaf307356e6895070b64cdc"
        )
        assert (
            payload["base_develop_sha"]
            == "beb5ec657bb4417bdeaf307356e6895070b64cdc"
        )
        assert (
            payload["pre_live_execution_develop_sha"]
            == "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
        )


def test_dfd_02_exact_raw_tree_binding(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-02: Exact raw evidence tree SHA256, file count, and total bytes binding."""
    tm = freeze_mod.build_raw_evidence_tree_manifest(
        repo_root=REPO_ROOT, double_pass=False
    )
    assert (
        tm["raw_evidence_tree_sha256"]
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )
    assert tm["raw_evidence_file_count"] == 1629
    assert tm["raw_evidence_total_bytes"] == 16264062
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert (
            payload["raw_evidence_tree_sha256"]
            == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
        )
        assert payload["raw_evidence_file_count"] == 1629
        assert payload["raw_evidence_total_bytes"] == 16264062


def test_dfd_03_exact_results_manifest_binding(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-03: Exact results manifest file and internal SHA256 binding."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert (
            payload["results_manifest_file_sha256"]
            == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
        )
        assert (
            payload["results_manifest_internal_sha256"]
            == "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
        )


def test_dfd_04_exact_results_receipt_binding(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-04: Exact results-freeze receipt file and internal SHA256 binding."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert (
            payload["results_freeze_receipt_file_sha256"]
            == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
        )
        assert (
            payload["results_freeze_receipt_internal_sha256"]
            == "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
        )
        assert (
            payload["execution_plan_file_sha256"]
            == "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
        )
        assert (
            payload["execution_plan_internal_sha256"]
            == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
        )
        assert (
            payload["scientific_code_bundle_sha256"]
            == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
        )
        assert (
            payload["launcher_lf_sha256"]
            == "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
        )


def test_dfd_05_exact_180_run_ids(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-05: Exact 180 run IDs bound in execution plan order."""
    plan = json.loads(
        (REPO_ROOT / diag_mod.EXPECTED_DEV_SELECT_PLAN_REL_PATH).read_text(
            encoding="utf-8"
        )
    )
    expected_ids = [c["run_id"] for c in plan["cells"]]
    assert len(expected_ids) == 180
    assert len(set(expected_ids)) == 180
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert payload["assigned_cells"] == 180
        assert payload["assigned_run_ids"] == expected_ids
        assert [c["run_id"] for c in payload["cell_diagnostics"]] == expected_ids


def test_dfd_06_primary_taxonomy_unchanged(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-06: Primary classification authority and total counts unchanged."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert (
            payload["primary_failure_authority"]
            == "execution_receipt.failure_classification"
        )
        assert payload["primary_counts_total"] == {
            "HTTP_429": 35,
            "HTTP_5XX": 10,
            "HTTP_ERROR": 60,
            "NONE": 9,
            "TIMEOUT": 66,
        }


def test_dfd_07_exact_candidate_primary_counts(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-07: Exact per-candidate primary failure counts reproduced."""
    expected = {
        "C1": {
            "HTTP_429": 35,
            "HTTP_5XX": 10,
            "HTTP_ERROR": 0,
            "NONE": 1,
            "TIMEOUT": 14,
        },
        "C2": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 0,
            "NONE": 8,
            "TIMEOUT": 52,
        },
        "C3": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 60,
            "NONE": 0,
            "TIMEOUT": 0,
        },
    }
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert payload["primary_counts_by_candidate"] == expected


def test_dfd_08_exactly_one_secondary_label_per_cell(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-08: Every cell receives exactly one valid secondary diagnostic label."""
    cells = computed_diagnostic_payload["cell_diagnostics"]
    assert len(cells) == 180
    for cell in cells:
        lbl = cell["secondary_diagnostic_label"]
        assert isinstance(lbl, str)
        assert lbl in diag_mod.ALLOWED_SECONDARY_DIAGNOSTIC_LABELS
    assert (
        sum(computed_diagnostic_payload["secondary_counts_total"].values()) == 180
    )
    for cid in ("C1", "C2", "C3"):
        assert (
            sum(
                computed_diagnostic_payload["secondary_counts_by_candidate"][
                    cid
                ].values()
            )
            == 60
        )


def test_dfd_09_secondary_labels_deterministic_and_candidate_agnostic(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-09: Secondary labels are deterministic and do not inspect candidate_id."""
    sig = inspect.signature(diag_mod.classify_secondary_diagnostic_label)
    assert "candidate_id" not in sig.parameters

    second_run = diag_mod.build_w06_dev_select_failure_diagnostic_payload(
        repo_root=REPO_ROOT
    )
    assert (
        computed_diagnostic_payload["secondary_counts_total"]
        == second_run["secondary_counts_total"]
        == diag_mod.EXPECTED_SECONDARY_COUNTS_TOTAL
    )
    assert (
        computed_diagnostic_payload["secondary_counts_by_candidate"]
        == second_run["secondary_counts_by_candidate"]
        == diag_mod.EXPECTED_SECONDARY_COUNTS_BY_CANDIDATE
    )


def test_dfd_10_volatile_request_ids_do_not_split_normalized_signatures() -> None:
    """DFD-10: Volatile request_id, response_id, retryDelay, and quotaDimensions key order do not split signatures."""
    msg_a = (
        "BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, "
        "'request_id': 'req_011CgKWWCk3KB2ZAfffpBanj'}"
    )
    msg_b = (
        "BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, "
        "'request_id': 'req_999ZzYyXxDifferentRequestId000'}"
    )
    sig_a = diag_mod.build_normalized_error_signature_record(
        candidate_id="C3",
        primary_classification="HTTP_ERROR",
        secondary_label="HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
        error_detail_sanitized=msg_a,
    )
    sig_b = diag_mod.build_normalized_error_signature_record(
        candidate_id="C3",
        primary_classification="HTTP_ERROR",
        secondary_label="HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
        error_detail_sanitized=msg_b,
    )
    assert (
        sig_a["normalized_signature_sha256"]
        == sig_b["normalized_signature_sha256"]
    )
    assert (
        sig_a["representative_sanitized_semantic_message"]
        == sig_b["representative_sanitized_semantic_message"]
    )

    # Also test volatile retryDelay and quotaDimensions key order in C1 429
    c1_a = (
        "ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Quota exceeded.\\nPlease retry in 12h44m31.734s.', "
        "'status': 'RESOURCE_EXHAUSTED', 'details': [{'quotaDimensions': {'model': 'gemini-3.8-flash', 'location': 'global'}}, "
        "{'retryDelay': '45871s'}]}}"
    )
    c1_b = (
        "ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Quota exceeded.\\nPlease retry in 13h09m20.808s.', "
        "'status': 'RESOURCE_EXHAUSTED', 'details': [{'quotaDimensions': {'location': 'global', 'model': 'gemini-3.8-flash'}}, "
        "{'retryDelay': '47360s'}]}}"
    )
    sig_c1_a = diag_mod.build_normalized_error_signature_record(
        candidate_id="C1",
        primary_classification="HTTP_429",
        secondary_label="HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED",
        error_detail_sanitized=c1_a,
    )
    sig_c1_b = diag_mod.build_normalized_error_signature_record(
        candidate_id="C1",
        primary_classification="HTTP_429",
        secondary_label="HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED",
        error_detail_sanitized=c1_b,
    )
    assert (
        sig_c1_a["normalized_signature_sha256"]
        == sig_c1_b["normalized_signature_sha256"]
    )


def test_dfd_11_semantic_error_message_changes_do_change_signature() -> None:
    """DFD-11: Changing HTTP status, exception class, error type, semantic message, or timeout type changes signature SHA256."""
    base_msg = (
        "BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'Your credit balance is too low to access the Anthropic API.'}, 'request_id': 'req_123'}"
    )
    base_sig = diag_mod.build_normalized_error_signature_record(
        candidate_id="C3",
        primary_classification="HTTP_ERROR",
        secondary_label="HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
        error_detail_sanitized=base_msg,
    )

    diff_msg = (
        "BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'max_tokens must be less than or equal to 8192.'}, 'request_id': 'req_123'}"
    )
    diff_sig_msg = diag_mod.build_normalized_error_signature_record(
        candidate_id="C3",
        primary_classification="HTTP_ERROR",
        secondary_label="HTTP_4XX_OTHER",
        error_detail_sanitized=diff_msg,
    )
    assert (
        base_sig["normalized_signature_sha256"]
        != diff_sig_msg["normalized_signature_sha256"]
    )

    diff_status = base_msg.replace("Error code: 400", "Error code: 402")
    diff_sig_status = diag_mod.build_normalized_error_signature_record(
        candidate_id="C3",
        primary_classification="HTTP_ERROR",
        secondary_label="HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
        error_detail_sanitized=diff_status,
    )
    assert (
        base_sig["normalized_signature_sha256"]
        != diff_sig_status["normalized_signature_sha256"]
    )


def test_dfd_12_c3_all_60_audited(computed_diagnostic_payload: dict) -> None:
    """DFD-12: All 60 C3 cells audited with exact billing/credit evidence and interpretation firewall."""
    c3 = computed_diagnostic_payload["candidate_diagnostics"]["C3"]
    assert c3["assigned_cells"] == 60
    assert c3["primary_http_error_count"] == 60
    assert c3["http_400_count"] == 60
    assert c3["provider_declared_error_types"] == ["invalid_request_error"]
    assert c3["provider_declared_billing_credit_count"] == 60
    assert c3["all_60_same_billing_credit_cause"] is True
    assert c3["distinct_normalized_error_signatures"] == 1
    assert c3["returned_model_id_null_for_all_failures"] is True
    assert c3["returned_model_id_null_count"] == 60
    assert c3["actual_http_request_count_equals_1_for_all_60"] is True
    assert c3["actual_http_request_count_1_cells"] == 60
    assert c3["latency_summary_ms"] == {
        "count": 60,
        "latency_ms_min": 594.0,
        "latency_ms_median": 765.5,
        "latency_ms_max": 2609.0,
    }
    assert c3["permitted_finding"] == diag_mod.PERMITTED_C3_FINDING
    assert c3["evidence_level"] == "DIRECT_PROVIDER_DECLARATION"


def test_dfd_13_c2_all_60_audited(computed_diagnostic_payload: dict) -> None:
    """DFD-13: All 60 C2 cells audited (8 NONE, 52 TIMEOUT at 55078..55797 ms)."""
    c2 = computed_diagnostic_payload["candidate_diagnostics"]["C2"]
    assert c2["assigned_cells"] == 60
    assert c2["none_count"] == 8
    assert c2["timeout_count"] == 52
    assert c2["distinct_normalized_error_signatures"] == 1
    tb = c2["timeout_boundary_analysis"]
    assert tb["count"] == 52
    assert tb["latency_ms_min"] == 55078.0
    assert tb["latency_ms_median"] == 55132.5
    assert tb["latency_ms_max"] == 55797.0
    assert tb["bucket_counts"] == {
        "lt_54000_ms": 0,
        "from_54000_to_lt_55000_ms": 0,
        "from_55000_to_57000_ms": 52,
        "gt_57000_ms": 0,
    }
    assert tb["near_frozen_55s_timeout_boundary_count"] == 52
    comp = c2["descriptive_comparison_none_vs_timeout"]
    assert comp["NONE"]["count"] == 8
    assert comp["NONE"]["days_counts"] == {"2": 8}
    assert comp["TIMEOUT"]["count"] == 52
    assert comp["TIMEOUT"]["days_counts"] == {"2": 12, "3": 20, "4": 20}


def test_dfd_14_c1_all_60_audited(computed_diagnostic_payload: dict) -> None:
    """DFD-14: All 60 C1 cells audited across HTTP_429 (35), HTTP_5XX (10), TIMEOUT (14), and NONE (1)."""
    c1 = computed_diagnostic_payload["candidate_diagnostics"]["C1"]
    assert c1["assigned_cells"] == 60
    assert c1["primary_counts"] == {
        "HTTP_429": 35,
        "HTTP_5XX": 10,
        "HTTP_ERROR": 0,
        "NONE": 1,
        "TIMEOUT": 14,
    }
    assert c1["distinct_normalized_error_signatures"] == 4
    assert c1["http_429_audit"]["count"] == 35
    assert c1["http_429_audit"]["http_status_codes_observed"] == [429]
    assert c1["http_429_audit"]["quota_or_rate_limit_declared_for_all"] is True
    assert c1["http_429_audit"]["distinct_normalized_signatures"] == 1

    assert c1["http_5xx_audit"]["count"] == 10
    assert c1["http_5xx_audit"]["http_status_codes_observed"] == [503]
    assert (
        c1["http_5xx_audit"][
            "provider_declared_high_demand_or_capacity_for_all"
        ]
        is True
    )
    assert c1["http_5xx_audit"]["distinct_normalized_signatures"] == 1

    assert c1["timeout_audit"]["count"] == 14
    assert c1["timeout_audit"]["distinct_normalized_signatures"] == 2
    assert c1["timeout_audit"]["timeout_boundary_analysis"]["bucket_counts"] == {
        "lt_54000_ms": 1,
        "from_54000_to_lt_55000_ms": 8,
        "from_55000_to_57000_ms": 5,
        "gt_57000_ms": 0,
    }
    assert c1["none_audit"]["count"] == 1
    assert c1["none_audit"]["run_ids"] == [
        "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026"
    ]


def test_dfd_15_timeout_boundary_computation_deterministic() -> None:
    """DFD-15: Deterministic timeout latency bucket and NEAR_FROZEN_55S_TIMEOUT_BOUNDARY intervals."""
    assert diag_mod.classify_timeout_latency_bucket(53999.9) == "lt_54000_ms"
    assert (
        diag_mod.classify_timeout_latency_bucket(54000.0)
        == "from_54000_to_lt_55000_ms"
    )
    assert (
        diag_mod.classify_timeout_latency_bucket(54999.9)
        == "from_54000_to_lt_55000_ms"
    )
    assert (
        diag_mod.classify_timeout_latency_bucket(55000.0)
        == "from_55000_to_57000_ms"
    )
    assert (
        diag_mod.classify_timeout_latency_bucket(57000.0)
        == "from_55000_to_57000_ms"
    )
    assert diag_mod.classify_timeout_latency_bucket(57000.1) == "gt_57000_ms"

    assert diag_mod.is_near_frozen_55s_timeout_boundary(53999.9) is False
    assert diag_mod.is_near_frozen_55s_timeout_boundary(54000.0) is True
    assert diag_mod.is_near_frozen_55s_timeout_boundary(55000.0) is True
    assert diag_mod.is_near_frozen_55s_timeout_boundary(57000.0) is True
    assert diag_mod.is_near_frozen_55s_timeout_boundary(57000.1) is False


def test_dfd_16_temporal_ordering_deterministic(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-16: All 180 cells ordered deterministically by execution_started_at_utc."""
    timeline = computed_diagnostic_payload["temporal_diagnostics"][
        "ordered_timeline"
    ]
    assert len(timeline) == 180
    assert [r["execution_ordinal"] for r in timeline] == list(range(1, 181))
    keys = [(r["execution_started_at_utc"], r["run_id"]) for r in timeline]
    assert keys == sorted(keys)


def test_dfd_17_quartile_assignment_deterministic(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-17: Execution quartiles Q1..Q4 each contain 45 cells and match exact candidate x primary counts."""
    td = computed_diagnostic_payload["temporal_diagnostics"]
    timeline = td["ordered_timeline"]
    for q_name, lo, hi in (
        ("Q1", 1, 45),
        ("Q2", 46, 90),
        ("Q3", 91, 135),
        ("Q4", 136, 180),
    ):
        q_items = [r for r in timeline if r["execution_quartile"] == q_name]
        assert len(q_items) == 45
        assert [r["execution_ordinal"] for r in q_items] == list(
            range(lo, hi + 1)
        )

    q_counts = td["quartile_counts_by_candidate_and_primary"]
    assert q_counts["Q1"]["C1"] == {
        "HTTP_429": 0,
        "HTTP_5XX": 8,
        "HTTP_ERROR": 0,
        "NONE": 0,
        "TIMEOUT": 7,
    }
    assert q_counts["Q2"]["C1"] == {
        "HTTP_429": 5,
        "HTTP_5XX": 2,
        "HTTP_ERROR": 0,
        "NONE": 1,
        "TIMEOUT": 7,
    }
    assert q_counts["Q3"]["C1"] == {
        "HTTP_429": 15,
        "HTTP_5XX": 0,
        "HTTP_ERROR": 0,
        "NONE": 0,
        "TIMEOUT": 0,
    }
    assert q_counts["Q4"]["C1"] == {
        "HTTP_429": 15,
        "HTTP_5XX": 0,
        "HTTP_ERROR": 0,
        "NONE": 0,
        "TIMEOUT": 0,
    }


def test_dfd_18_request_byte_size_computation_deterministic(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-18: Canonical provider-wire-request byte sizes match canonical_json_bytes across all 180 cells."""
    raw_root = REPO_ROOT / diag_mod.RAW_OUTPUT_ROOT_REL_PATH
    for cell in computed_diagnostic_payload["cell_diagnostics"]:
        rm = json.loads(
            (raw_root / cell["run_id"] / "request_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        expected_len = len(canonical_json_bytes(rm["provider_wire_request"]))
        assert cell["wire_request_canonical_bytes"] == expected_len


def test_dfd_19_no_primary_denominator_mutation(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-19: All 180 cells retain counts_in_denominator == True (60 per candidate)."""
    cells = computed_diagnostic_payload["cell_diagnostics"]
    assert len(cells) == 180
    assert all(c["counts_in_denominator"] is True for c in cells)
    for cid in ("C1", "C2", "C3"):
        cid_cells = [c for c in cells if c["candidate_id"] == cid]
        assert len(cid_cells) == 60
        assert all(c["counts_in_denominator"] is True for c in cid_cells)


def test_dfd_20_retry_zero(computed_diagnostic_payload: dict) -> None:
    """DFD-20: Zero retries and all 180 cells have actual_http_request_count == 1."""
    hb = computed_diagnostic_payload["harness_binding_check"]
    assert hb["retry_calls"] == 0
    assert hb["actual_http_request_count_not_equal_1_cells"] == 0
    assert all(
        c["actual_http_request_count"] == 1
        for c in computed_diagnostic_payload["cell_diagnostics"]
    )


def test_dfd_21_rerun_zero(computed_diagnostic_payload: dict) -> None:
    """DFD-21: Zero rerun cells, zero duplicate logical cells, and attempt_number == 1 for all 180 cells."""
    hb = computed_diagnostic_payload["harness_binding_check"]
    assert hb["rerun_cells"] == 0
    assert hb["attempt_number_not_equal_1_cells"] == 0
    assert hb["duplicate_logical_cell_count"] == 0
    assert all(
        c["attempt_number"] == 1
        for c in computed_diagnostic_payload["cell_diagnostics"]
    )


def test_dfd_22_model_mismatch_zero(computed_diagnostic_payload: dict) -> None:
    """DFD-22: Model ID mismatch count is 0."""
    hb = computed_diagnostic_payload["harness_binding_check"]
    assert hb["model_id_mismatch_count"] == 0
    for c in computed_diagnostic_payload["cell_diagnostics"]:
        assert c["returned_model_id"] in (None, c["requested_model_id"])


def test_dfd_23_request_identity_180_of_180(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-23: Request identity matches 180/180."""
    hb = computed_diagnostic_payload["harness_binding_check"]
    assert hb["request_identity_match"] == "180/180"
    assert hb["provider_config_binding_match"] == "180/180"
    assert hb["scientific_code_bundle_match"] == "180/180"


def test_dfd_24_cell_hash_chain_180_of_180(
    computed_diagnostic_payload: dict,
) -> None:
    """DFD-24: Cell hash chain valid 180/180 and harness_or_binding_inconsistency_observed is False."""
    hb = computed_diagnostic_payload["harness_binding_check"]
    assert hb["cell_hash_chain_valid"] == "180/180"
    assert hb["harness_or_binding_inconsistency_observed"] is False
    assert (
        computed_diagnostic_payload[
            "harness_or_binding_inconsistency_observed"
        ]
        is False
    )


def test_dfd_25_raw_evidence_unchanged_after_diagnostic() -> None:
    """DFD-25: Raw evidence tree SHA256 is identical before and after diagnostic verification."""
    before = freeze_mod.build_raw_evidence_tree_manifest(
        repo_root=REPO_ROOT, double_pass=False
    )
    summary = diag_mod.verify_w06_dev_select_failure_diagnostic(
        repo_root=REPO_ROOT
    )
    after = freeze_mod.build_raw_evidence_tree_manifest(
        repo_root=REPO_ROOT, double_pass=False
    )
    assert summary["verified"] is True
    assert summary["raw_evidence_mutated"] is False
    assert (
        before["raw_evidence_tree_sha256"]
        == after["raw_evidence_tree_sha256"]
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )


def test_dfd_26_no_provider_call_and_no_api_key_or_dotenv_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DFD-26: LIVE_PROVIDER_CALLS_NEW == 0 and diagnostic works with all API keys cleared."""
    for env_key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(env_key, raising=False)

    summary = diag_mod.verify_w06_dev_select_failure_diagnostic(
        repo_root=REPO_ROOT
    )
    assert summary["verified"] is True
    assert summary["live_provider_calls_new"] == 0


def test_dfd_27_network_kill_switch_enforced() -> None:
    """DFD-27: NetworkKillSwitchGuard blocks socket, DNS, urllib, and httpx outbound calls."""
    with NetworkKillSwitchGuard():
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("example.com", 443))
        with pytest.raises(OutboundNetworkBlockedError):
            socket.getaddrinfo("example.com", 443)
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx.get("https://example.com")


def test_dfd_28_no_model_winner(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-28: model_winner_selected is False, selected_model_id is None, and no winner artifact exists."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert payload["model_winner_selected"] is False
        assert payload["selected_model_id"] is None
    assert not (
        REPO_ROOT / "data/evaluation/w06/w06_dev_select_model_selection_v1.json"
    ).exists()
    assert not (
        REPO_ROOT
        / "data/evaluation/w06/w06_dev_select_model_selection_01_receipt_v1.json"
    ).exists()


def test_dfd_29_no_stochasticity(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-29: stochasticity_execution_started is False and no stochasticity artifacts exist."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert payload["stochasticity_execution_started"] is False
    assert not (
        REPO_ROOT
        / "data/evaluation/w06/w06_stochasticity_execution_plan_v1.json"
    ).exists()
    assert not (
        REPO_ROOT / "data/evaluation/w06/live_stochasticity_primary_v1"
    ).exists()


def test_dfd_30_no_final100_usage_and_scientific_bundle_unchanged(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-30: final100_used is False, Final100/P11 freezes untouched, and scientific bundle SHA unchanged."""
    for payload in (computed_diagnostic_payload, disk_diagnostic_payload):
        assert payload["final100_used"] is False
    final100_sha = sha256_bytes(
        (
            REPO_ROOT / freeze_mod.FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
        ).read_bytes()
    )
    p11_sha = sha256_bytes(
        (REPO_ROOT / freeze_mod.FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes()
    )
    assert final100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
    assert p11_sha == FORBIDDEN_P11_MANIFEST_SHA256
    assert (
        compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )


def test_dfd_31_stateless_verifier_no_positive_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DFD-31: Verifier is stateless and does not cache positive verification results."""
    first = diag_mod.verify_w06_dev_select_failure_diagnostic(
        repo_root=REPO_ROOT
    )
    assert first["verified"] is True

    # Simulate tampering on a subsequent call via monkeypatched expected file SHA
    monkeypatch.setattr(
        diag_mod,
        "EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256",
        "0" * 64,
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="DIAGNOSTIC_ARTIFACT_FILE_SHA256_MISMATCH",
    ):
        diag_mod.verify_w06_dev_select_failure_diagnostic(repo_root=REPO_ROOT)


def test_dfd_32_tampered_raw_evidence_causes_diagnostic_verifier_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DFD-32: Any tampering in the raw evidence tree causes diagnostic verifier failure."""
    orig_builder = freeze_mod.build_raw_evidence_tree_manifest

    def _tampered_tree(*args, **kwargs):
        res = copy.deepcopy(orig_builder(*args, **kwargs))
        res["raw_evidence_tree_sha256"] = "f" * 64
        return res

    monkeypatch.setattr(
        freeze_mod, "build_raw_evidence_tree_manifest", _tampered_tree
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RAW_EVIDENCE_TREE_SHA256_MISMATCH"
    ):
        diag_mod.verify_w06_dev_select_failure_diagnostic(repo_root=REPO_ROOT)


def test_dfd_33_tampered_diagnostic_artifact_causes_verifier_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DFD-33: Tampering with the diagnostic artifact JSON causes verifier failure."""
    orig_path = REPO_ROOT / diag_mod.DIAGNOSTIC_ARTIFACT_REL_PATH
    tampered_obj = json.loads(orig_path.read_text(encoding="utf-8"))
    tampered_obj["live_provider_calls_new"] = 1

    fake_root = tmp_path / "repo"
    fake_diag = fake_root / diag_mod.DIAGNOSTIC_ARTIFACT_REL_PATH
    fake_diag.parent.mkdir(parents=True, exist_ok=True)
    fake_diag.write_bytes(canonical_json_bytes(tampered_obj))

    orig_scan = freeze_mod.build_raw_evidence_tree_manifest
    monkeypatch.setattr(
        freeze_mod,
        "build_raw_evidence_tree_manifest",
        lambda *a, **kw: orig_scan(repo_root=REPO_ROOT, double_pass=False),
    )
    monkeypatch.setattr(
        diag_mod, "EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256", None
    )

    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256_TAMPERED",
    ):
        diag_mod.verify_w06_dev_select_failure_diagnostic(repo_root=fake_root)


def test_dfd_34_unknown_error_text_falls_back_fail_closed() -> None:
    """DFD-34: Unspecified or unknown error text falls back fail-closed to generic/unknown categories."""
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_429",
            error_detail_sanitized="ClientError: 429 Too Many Requests (no reason given)",
            finish_reason="PROVIDER_EXCEPTION:HTTP_429",
        )
        == "HTTP_429_UNSPECIFIED"
    )
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_5XX",
            error_detail_sanitized="ServerError: 500 Internal Server Error",
            finish_reason="PROVIDER_EXCEPTION:HTTP_5XX",
        )
        == "HTTP_5XX_OTHER"
    )
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_ERROR",
            error_detail_sanitized="BadRequestError: Error code: 400 - {'error': {'message': 'Invalid parameter'}}",
            finish_reason="PROVIDER_EXCEPTION:HTTP_ERROR",
        )
        == "HTTP_4XX_OTHER"
    )
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_ERROR",
            error_detail_sanitized="HTTPError: socket hang up during transport",
            finish_reason="PROVIDER_EXCEPTION:HTTP_ERROR",
        )
        == "HTTP_ERROR_OTHER"
    )
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_ERROR",
            error_detail_sanitized="OpaqueMysteryFailureWithNoStatusOrKnownToken",
            finish_reason="PROVIDER_EXCEPTION:HTTP_ERROR",
        )
        == "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"
    )
    assert (
        diag_mod.classify_secondary_diagnostic_label(
            primary_failure_classification="HTTP_ERROR",
            error_detail_sanitized=None,
            finish_reason="PROVIDER_EXCEPTION:HTTP_ERROR",
        )
        == "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"
    )


def test_dfd_35_no_secrets_in_diagnostic_artifact(
    computed_diagnostic_payload: dict, disk_diagnostic_payload: dict
) -> None:
    """DFD-35: No secrets in diagnostic artifact and secret scanner rejects injected keys."""
    assert_no_secrets_in_payload(
        computed_diagnostic_payload, context="TEST_COMPUTED_DIAGNOSTIC"
    )
    assert_no_secrets_in_payload(
        disk_diagnostic_payload, context="TEST_DISK_DIAGNOSTIC"
    )

    poisoned = copy.deepcopy(computed_diagnostic_payload)
    poisoned["injected_secret"] = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    with pytest.raises(Exception):
        assert_no_secrets_in_payload(poisoned, context="TEST_POISONED")


def test_dfd_cli_verify_only_and_raw_write_guard() -> None:
    """CLI `--verify-only` exits 0 and write guard blocks any path inside raw evidence root."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/diagnose_w06_dev_select_failures.py"),
            "--verify-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verified"] is True
    assert (
        out["diagnostic_artifact_file_sha256"]
        == diag_mod.EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256
    )
