"""Offline tests for W06 Scientific Closure (v1).

Task: W06 — SCIENTIFIC CLOSURE
Next Gate: W06-SCIENTIFIC-CLOSURE-CHATGPT-AUDIT
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from scripts import (  # noqa: E402
    verify_w06_dev_select_amendment_01_canary_live_execution_01_evidence as evidence_verifier,
    verify_w06_scientific_closure as closure_verifier,
)


def test_01_closure_artifacts_exist_and_match_canonical_hashes() -> None:
    """Verify closure JSON and Markdown exist and match canonical LF SHA256 and internal SHA256."""
    json_path = REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH
    md_path = REPO_ROOT / closure_verifier.CLOSURE_MD_REL_PATH
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    expected_payload = closure_verifier.build_closure_payload()
    assert payload == expected_payload

    internal_sha = closure_verifier.compute_closure_internal_sha256(payload)
    assert payload["closure_internal_sha256"] == internal_sha

    file_sha = closure_verifier.compute_file_lf_sha256(json_path)
    expected_md = closure_verifier.build_closure_markdown(payload, file_sha)
    assert md_path.read_bytes().replace(b"\r\n", b"\n") == expected_md.replace(
        "\r\n", "\n"
    ).encode("utf-8")


def test_02_required_closure_statuses_and_firewalls() -> None:
    """Verify all required Section 3 closure status keys and Section 8 Final100 firewall values."""
    payload = json.loads(
        (REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH).read_text(encoding="utf-8")
    )
    assert payload["W06_IMPLEMENTATION_STATUS"] == "COMPLETED"
    assert payload["W06_EVALUATION_PROTOCOL_STATUS"] == "COMPLETED"
    assert (
        payload["PRIMARY_DEV_SELECT_STATUS"]
        == "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"
    )
    assert payload["AMENDMENT_01_CANARY_STATUS"] == "FAILED_OPERATIONAL_GATE"
    assert payload["MODEL_SELECTION_STATUS"] == "INCONCLUSIVE"
    assert payload["MODEL_WINNER_SELECTED"] is False
    assert payload["SELECTED_MODEL_ID"] is None
    assert payload["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert payload["COMPARATIVE_EXECUTED"] is False
    assert payload["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert payload["FINAL100_USED"] is False
    assert payload["FINAL100_STATUS"] == "NO-GO"
    assert payload["W06_OVERALL_STATUS"] == "CLOSED_WITH_OPERATIONAL_LIMITATION"
    assert payload["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert payload["ENV_FILE_READ"] is False
    assert payload["API_KEYS_INSPECTED"] is False


def test_03_primary_dev_select_authority_and_non_comparability() -> None:
    """Verify Section 4 primary DEV-SELECT strict rates and non-comparability constraints."""
    payload = json.loads(
        (REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH).read_text(encoding="utf-8")
    )
    primary = payload["primary_dev_select_authority"]
    assert primary["strict_valid_core_rates"] == {
        "C1": "1/60",
        "C2": "8/60",
        "C3": "0/60",
    }
    assert primary["authoritative_candidates"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    assert (
        primary["status"]
        == "OPERATIONALLY_VALID_BUT_NON_COMPARABLE_FOR_PLANNER_QUALITY"
    )
    assert primary["operationally_valid_benchmark"] is True
    assert primary["infer_c2_is_best_forbidden"] is True
    assert primary["rank_models_from_primary_rates_forbidden"] is True
    assert primary["declare_winner_forbidden"] is True


def test_04_amendment_01_canary_authority_and_fail_stop() -> None:
    """Verify Section 5 Amendment-01 canary metrics and unscheduled cell list."""
    payload = json.loads(
        (REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH).read_text(encoding="utf-8")
    )
    canary = payload["amendment_01_canary_authority"]
    assert canary["assigned_cells"] == 9
    assert canary["attempted_cells"] == 1
    assert canary["unscheduled_cells"] == 8
    assert canary["operational_pass"] == "0/9"
    assert canary["operational_pass_cells_count"] == 0
    assert canary["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert canary["fail_stop"] is True
    assert canary["stopped_at"] == "007 / C1"
    assert canary["provider"] == "Google"
    assert canary["requested_model"] == "gemini-3.8-flash"
    assert canary["prompt"] == "P1"
    assert canary["generation_invocations"] == 1
    assert canary["actual_http_requests"] == 1
    assert canary["retry"] == 0
    assert canary["rerun"] == 0
    assert canary["latency_ms"] == pytest.approx(179986.664)
    assert canary["classification"] == "TIMEOUT"
    assert canary["http_5xx"] is True
    assert canary["reported_error"] == "504 DEADLINE_EXCEEDED"
    assert canary["provider_response_received"] is False
    assert canary["model_identity_evidence"] is False
    assert canary["unscheduled_cells_list"] == [
        "007/C2",
        "007/C3",
        "011/C1",
        "011/C2",
        "011/C3",
        "015/C1",
        "015/C2",
        "015/C3",
    ]
    assert canary["unscheduled_cells_status"] == "UNSCHEDULED_DUE_TO_FAIL_STOP"


def test_05_critical_scientific_interpretation_and_deliverables() -> None:
    """Verify Section 6 critical interpretation and Section 7 17 deliverables."""
    payload = json.loads(
        (REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH).read_text(encoding="utf-8")
    )
    interp = payload["critical_scientific_interpretation"]
    assert interp["amendment_01_establishes_gemini_inferior_planner_quality"] is False
    assert (
        interp["authoritative_statement"]
        == "Under the frozen W6 execution-environment protocol, C1/fixture 007 did not "
        "satisfy the operational readiness criteria within the fixed 180-second timeout."
    )
    assert interp["fair_amendment_01_comparative_quality_dataset_exists"] is False
    assert interp["no_model_winner_can_be_selected"] is True
    assert interp["comparative180_cannot_be_authorized"] is True
    assert interp["final100_cannot_be_opened"] is True

    delivered = payload["w06_successfully_delivered"]
    assert delivered["classified_as_implementation_failure"] is False
    assert delivered["deliverable_count"] == 17
    assert len(delivered["deliverables"]) == 17

    md_text = (REPO_ROOT / closure_verifier.CLOSURE_MD_REL_PATH).read_text(
        encoding="utf-8"
    )
    assert (
        "does NOT establish that Gemini is inferior in itinerary-planning quality"
        in md_text
    )
    assert interp["authoritative_statement"] in md_text


def test_06_bound_provenance_and_full_verifier_pass() -> None:
    """Verify all bound provenance hashes and run verify_scientific_closure end-to-end."""
    result = closure_verifier.verify_scientific_closure(repo_root=REPO_ROOT)
    assert result["status"] == "PASS"
    assert result["verified"] is True
    assert result["W06_OVERALL_STATUS"] == "CLOSED_WITH_OPERATIONAL_LIMITATION"
    assert result["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert result["ENV_FILE_READ"] is False
    assert result["API_KEYS_INSPECTED"] is False
    assert (
        result["scientific_code_bundle_sha256"]
        == closure_verifier.EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    )
    assert (
        result["canary_launcher_lf_sha256"]
        == closure_verifier.EXPECTED_CANARY_LAUNCHER_LF_SHA256
    )
    assert (
        result["primary_launcher_lf_sha256"]
        == closure_verifier.EXPECTED_PRIMARY_LAUNCHER_LF_SHA256
    )
    assert result["evidence_verified"] is True
    assert result["evidence_file_count"] == 9
    assert result["second_live_execution_blocked"] is True
    assert result["next_gate"] == "W06-SCIENTIFIC-CLOSURE-CHATGPT-AUDIT"


def test_07_tamper_detection_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that tampering with closure status or markdown causes verification to fail closed."""
    payload = closure_verifier.build_closure_payload()
    tampered = deepcopy(payload)
    tampered["MODEL_WINNER_SELECTED"] = True
    tampered["closure_internal_sha256"] = (
        closure_verifier.compute_closure_internal_sha256(tampered)
    )

    json_dir = tmp_path / "data" / "evaluation" / "w06"
    md_dir = tmp_path / "docs" / "research"
    json_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    (json_dir / "w06_scientific_closure_v1.json").write_bytes(
        closure_verifier.canonical_json_bytes(tampered)
    )
    (md_dir / "w06_scientific_closure.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(
        closure_verifier.W06ScientificClosureVerificationError,
        match="CLOSURE_PAYLOAD_DRIFT",
    ):
        closure_verifier.verify_scientific_closure(repo_root=tmp_path)

    # Confirm authoritative evidence hashes in repository remain untouched
    ev = evidence_verifier.verify_w06_amendment_01_canary_repository_lifecycle(
        repo_root=REPO_ROOT,
        require_evidence_present=True,
    )
    assert ev["status"] == "PASS"
    assert ev["evidence_verified"] is True
