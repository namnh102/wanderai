"""Offline tests for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP.

Covers:
- All 24 positive verification requirements from Section 13;
- All 15+ negative/tamper scenarios from Section 14;
- Offline safety firewalls from Section 15 (`LIVE_PROVIDER_CALLS_NEW = 0`,
  `ENV_FILE_READ = false`, `API_KEYS_INSPECTED = false`, live output root absent).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_DIR, SCRIPTS_DIR, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CandidateRegistryIntegrityError,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    Final100FirewallViolationError,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_amendment_01_canary_live_execution_authorization as exec_auth_freeze  # noqa: E402
import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher  # noqa: E402

EXPECTED_RECEIPT_FILE_SHA256 = (
    "e68c7ad76e9261aaf687660dd20441118ec192a727a6cbf88b15cf4f0268d684"
)
EXPECTED_RECEIPT_INTERNAL_SHA256 = (
    "d045b1c5e45675dd330515aad5e591e9efb94e219d4418aa739eb8b2270ad8c5"
)
EXPECTED_MARKDOWN_SHA256 = (
    "1aeedeab3ede22b7f84ddf2fa2214a690ed79b0f358aa3239f389eb717c77b5b"
)


@pytest.fixture(autouse=True)
def _enforce_offline_guards():
    """Run every test in this module under the offline network and secret/env kill-switches."""
    with (
        canary_launcher.NetworkKillSwitchGuard(),
        canary_launcher.PreflightSecretAndEnvFileAccessGuard(),
    ):
        yield


@pytest.fixture(scope="module")
def verified_out() -> dict[str, Any]:
    """Run the 24-point verifier once at module scope."""
    return exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
        repo_root=REPO_ROOT
    )


@pytest.fixture(scope="module")
def receipt_data() -> dict[str, Any]:
    """Load the committed JSON receipt from disk."""
    path = REPO_ROOT / exec_auth_freeze.RECEIPT_REL_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _resign_and_write(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    cloned = copy.deepcopy(payload)
    key = exec_auth_freeze.RECEIPT_INTERNAL_SHA_KEY
    without_sig = {k: v for k, v in cloned.items() if k != key}
    cloned[key] = sha256_bytes(canonical_json_bytes(without_sig))
    out_path = tmp_path / name
    out_path.write_text(
        json.dumps(cloned, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


# ==============================================================================
# SECTION 13: 24-POINT POSITIVE VERIFICATION
# ==============================================================================


def test_01_receipt_internal_and_file_sha256_and_markdown_reproducibility(
    verified_out: dict[str, Any],
    receipt_data: dict[str, Any],
) -> None:
    """Section 13 (1, 2): Receipt internal SHA is valid; receipt FILE SHA and Markdown SHA are reproducible."""
    receipt_path = REPO_ROOT / exec_auth_freeze.RECEIPT_REL_PATH
    doc_path = REPO_ROOT / exec_auth_freeze.RECEIPT_DOC_REL_PATH
    assert receipt_path.is_file()
    assert doc_path.is_file()

    actual_file_sha = sha256_bytes(normalize_lf_bytes(receipt_path.read_bytes()))
    actual_doc_sha = sha256_bytes(normalize_lf_bytes(doc_path.read_bytes()))
    assert actual_file_sha == EXPECTED_RECEIPT_FILE_SHA256
    assert actual_doc_sha == EXPECTED_MARKDOWN_SHA256
    assert (
        receipt_data[exec_auth_freeze.RECEIPT_INTERNAL_SHA_KEY]
        == EXPECTED_RECEIPT_INTERNAL_SHA256
    )

    assert verified_out["status"] == "PASS"
    assert verified_out["verified"] is True
    assert verified_out["receipt_file_sha256"] == EXPECTED_RECEIPT_FILE_SHA256
    assert verified_out["receipt_internal_sha256"] == EXPECTED_RECEIPT_INTERNAL_SHA256
    assert verified_out["markdown_sha256"] == EXPECTED_MARKDOWN_SHA256
    assert (
        exec_auth_freeze.is_verified_downstream_w06_canary_live_execution_authorization_receipt(
            REPO_ROOT
        )
        is True
    )


def test_02_pr_73_git_and_launcher_hash_provenance(
    verified_out: dict[str, Any],
    receipt_data: dict[str, Any],
) -> None:
    """Section 13 (3..10): PR number=73, PR HEAD, merge commit, code basis, parents 1 & 2, runtime ancestor, and launcher LF SHA256."""
    assert receipt_data["launcher_pr_number"] == 73
    assert (
        receipt_data["launcher_pr_head_sha"]
        == "c6c984aef8712538c8c29587caff1e0bbb36afaa"
    )
    assert (
        receipt_data["launcher_merge_commit_sha"]
        == "3e103587ab0324717c03af14e236dc37fc579295"
    )
    assert (
        receipt_data["authorized_code_basis_commit_sha"]
        == "3e103587ab0324717c03af14e236dc37fc579295"
    )
    assert (
        receipt_data["authoritative_base_develop_sha"]
        == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    )
    assert (
        receipt_data["launcher_path"]
        == "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
    )
    assert (
        receipt_data["launcher_file_lf_sha256"]
        == "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
    )

    prov = verified_out["code_provenance"]
    assert prov["verified"] is True
    assert prov["launcher_pr_number"] == 73
    assert prov["merge_parent_1"] == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    assert prov["merge_parent_2"] == "c6c984aef8712538c8c29587caff1e0bbb36afaa"
    assert (
        prov["launcher_merge_commit_sha"]
        == "3e103587ab0324717c03af14e236dc37fc579295"
    )
    assert (
        prov["authorized_code_basis_commit_sha"]
        == "3e103587ab0324717c03af14e236dc37fc579295"
    )
    assert (
        prov["launcher_file_lf_sha256"]
        == "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
    )

    launcher_on_disk_sha = sha256_bytes(
        normalize_lf_bytes(
            (
                REPO_ROOT
                / "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
            ).read_bytes()
        )
    )
    assert (
        launcher_on_disk_sha
        == "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
    )


def test_03_candidates_prompt_fixtures_and_9_cell_order(
    receipt_data: dict[str, Any],
) -> None:
    """Section 13 (11..14): Exact 3 candidates, P1 prompt, 3 fixtures, and exact 9-cell order."""
    assert receipt_data["candidates"] == {
        "C1": {
            "candidate_id": "C1",
            "provider": "GOOGLE",
            "provider_slug": "google",
            "exact_model_id": "gemini-3.8-flash",
        },
        "C2": {
            "candidate_id": "C2",
            "provider": "OPENAI",
            "provider_slug": "openai",
            "exact_model_id": "gpt-6.1-sol",
        },
        "C3": {
            "candidate_id": "C3",
            "provider": "ANTHROPIC",
            "provider_slug": "anthropic",
            "exact_model_id": "claude-sonnet-5-5",
        },
    }
    assert receipt_data["prompt_id"] == "P1"
    assert (
        receipt_data["selected_prompt_semantic_sha256"]
        == "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
    )
    assert receipt_data["exact_canary_fixtures"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    order = receipt_data["exact_9_cell_execution_order"]
    assert len(order) == 9
    assert [c["short_label"] for c in order] == [
        "007 / C1",
        "007 / C2",
        "007 / C3",
        "011 / C1",
        "011 / C2",
        "011 / C3",
        "015 / C1",
        "015 / C2",
        "015 / C3",
    ]


def test_04_runtime_contract_and_downstream_firewalls_and_upstream_hashes(
    verified_out: dict[str, Any],
    receipt_data: dict[str, Any],
) -> None:
    """Section 13 (15..24) & Section 15: Runtime contract, downstream firewalls, upstream hashes, and offline safety."""
    assert receipt_data["max_provider_generation_calls"] == 9
    assert receipt_data["generation_calls_per_assigned_cell"] == 1
    assert receipt_data["concurrency"] == 1
    assert receipt_data["timeout_policy_id"] == "T3_CANDIDATE_180S"
    assert receipt_data["timeout_ms"] == 180000
    assert receipt_data["pacing_policy_id"] == "P1_FIXED_2000MS_INTER_CALL_DELAY"
    assert receipt_data["inter_call_delay_ms"] == 2000
    assert receipt_data["delay_before_first_call_ms"] == 0
    assert receipt_data["delay_after_last_call_ms"] == 0
    assert receipt_data["maximum_scheduled_delays"] == 8
    assert receipt_data["retry_policy_id"] == "R0_STRICT_ZERO_RETRY"
    assert receipt_data["retry"] == 0
    assert receipt_data["automatic_retry"] == 0
    assert receipt_data["transport_retry"] == 0
    assert receipt_data["manual_retry"] == 0
    assert receipt_data["llm_repair"] == 0
    assert receipt_data["semantic_repair"] == 0
    assert receipt_data["fallback"] is False

    # Effective receipt flag & PREP governance
    assert receipt_data["CANARY_LIVE_EXECUTION_AUTHORIZED"] is True
    assert receipt_data["receipt_prep_only_not_executable_during_prep_task"] is True
    assert receipt_data["CANARY_EXECUTED"] is False

    # Downstream firewall
    assert receipt_data["comparative_live_authorized"] is False
    assert receipt_data["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert receipt_data["COMPARATIVE_EXECUTED"] is False
    assert receipt_data["MODEL_WINNER_SELECTED"] is False
    assert receipt_data["SELECTED_MODEL_ID"] is None
    assert receipt_data["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert receipt_data["final100_permitted"] is False
    assert receipt_data["FINAL100_USED"] is False
    assert receipt_data["FINAL100_STATUS"] == "NO-GO"

    # Primary experiment unchanged
    assert receipt_data["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert receipt_data["PRIMARY_RESULTS_REPLACED"] is False
    assert receipt_data["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert receipt_data["authoritative_primary_strict_rates"] == {
        "C1": "1/60",
        "C2": "8/60",
        "C3": "0/60",
    }

    # Upstream hashes
    assert (
        receipt_data["canary_authorization_prep_file_sha256"]
        == "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
    )
    assert (
        receipt_data["canary_authorization_prep_internal_sha256"]
        == "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
    )
    assert (
        receipt_data["canary_authorization_prep_doc_sha256"]
        == "d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da"
    )
    assert (
        receipt_data["canary_manifest_file_sha256"]
        == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
    )
    assert (
        receipt_data["canary_manifest_internal_sha256"]
        == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
    )
    assert (
        receipt_data["owner_readiness_attestation_file_sha256"]
        == "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
    )
    assert (
        receipt_data["owner_readiness_attestation_internal_sha256"]
        == "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
    )
    assert (
        receipt_data["scientific_code_bundle_sha256"]
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )

    # Offline safety & live output root absence
    assert verified_out["output_root_exists"] is False
    assert not (REPO_ROOT / "data/evaluation/w06/live_amendment_01_canary_v1").exists()
    assert verified_out["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert verified_out["ENV_FILE_READ"] is False
    assert verified_out["API_KEYS_INSPECTED"] is False

    # Inspect state via merged launcher
    state = canary_launcher.inspect_canary_live_execution_authorization_state(
        repo_root=REPO_ROOT,
        git_runner=exec_auth_freeze.build_shallow_aware_git_runner(REPO_ROOT),
    )
    assert state["execution_authorization_receipt_present"] is True
    assert state["effective_live_execution_authorized"] is True
    assert state["live_execution_available"] is True
    assert (
        state["execution_authorization_receipt_file_sha256"]
        == EXPECTED_RECEIPT_FILE_SHA256
    )
    assert (
        state["execution_authorization_receipt_internal_sha256"]
        == EXPECTED_RECEIPT_INTERNAL_SHA256
    )


# ==============================================================================
# SECTION 14: NEGATIVE / TAMPER TESTS (15+ SCENARIOS)
# ==============================================================================


def test_05_neg_01_receipt_internal_sha_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (1): Receipt internal SHA mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad[exec_auth_freeze.RECEIPT_INTERNAL_SHA_KEY] = "0" * 64
    p = tmp_path / "bad_internal_sha.json"
    p.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_INTERNAL_SHA256_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_06_neg_02_launcher_hash_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (2): Launcher hash mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["launcher_file_lf_sha256"] = "a" * 64
    bad["launcher_repository_merge_provenance"]["launcher_file_lf_sha256"] = "a" * 64
    p = _resign_and_write(tmp_path, "bad_launcher_hash.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_FILE_LF_SHA256_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_07_neg_03_launcher_pr_head_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (3): Launcher PR HEAD mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["launcher_pr_head_sha"] = "1111111111111111111111111111111111111111"
    bad["launcher_repository_merge_provenance"]["pr_head_sha"] = (
        "1111111111111111111111111111111111111111"
    )
    p = _resign_and_write(tmp_path, "bad_pr_head.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_PR_HEAD_COMMIT_NOT_FOUND",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_08_neg_04_launcher_merge_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (4): Launcher merge commit mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["launcher_merge_commit_sha"] = "2222222222222222222222222222222222222222"
    bad["authorized_code_basis_commit_sha"] = (
        "2222222222222222222222222222222222222222"
    )
    bad["launcher_repository_merge_provenance"]["merge_commit_sha"] = (
        "2222222222222222222222222222222222222222"
    )
    bad["launcher_repository_merge_provenance"]["authorized_code_basis_commit_sha"] = (
        "2222222222222222222222222222222222222222"
    )
    p = _resign_and_write(tmp_path, "bad_merge_sha.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_MERGE_COMMIT_NOT_FOUND",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_09_neg_05_code_basis_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (5): Code basis mutation (differing from merge commit or nonexistent) -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["authorized_code_basis_commit_sha"] = (
        exec_auth_freeze.FROZEN_LAUNCHER_PR_HEAD_SHA
    )
    bad["launcher_repository_merge_provenance"]["authorized_code_basis_commit_sha"] = (
        exec_auth_freeze.FROZEN_LAUNCHER_PR_HEAD_SHA
    )
    p = _resign_and_write(tmp_path, "bad_code_basis.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_CODE_BASIS_NOT_EQUAL_TO_LAUNCHER_MERGE_COMMIT",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_10_neg_06_model_substitution_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (6): Model substitution -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["candidates"]["C3"]["exact_model_id"] = "claude-3-7-sonnet"
    p = _resign_and_write(tmp_path, "bad_model.json", bad)
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="CANARY_EXECUTION_AUTH_CANDIDATE_SET_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_11_neg_07_fixture_substitution_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (7): Fixture substitution -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["exact_canary_fixtures"] = [
        "W06-DEV-TUNE-001",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    p = _resign_and_write(tmp_path, "bad_fixtures.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_FIXTURE_SET_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_12_neg_08_order_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (8): Order mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    order = bad["exact_9_cell_execution_order"]
    order[2], order[3] = order[3], order[2]
    p = _resign_and_write(tmp_path, "bad_order.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_9_CELL_ORDER_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_13_neg_09_max_calls_greater_than_9_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (9): max_provider_generation_calls > 9 -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["max_provider_generation_calls"] = 10
    p = _resign_and_write(tmp_path, "bad_max_calls.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_14_neg_10_retry_greater_than_0_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (10): Any retry dimension > 0 -> fail."""
    for field in (
        "retry",
        "automatic_retry",
        "transport_retry",
        "manual_retry",
        "llm_repair",
        "semantic_repair",
    ):
        bad = copy.deepcopy(receipt_data)
        bad[field] = 1
        p = _resign_and_write(tmp_path, f"bad_{field}.json", bad)
        with pytest.raises(
            PlanBeforeLiveProtocolError,
            match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
        ):
            exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
                repo_root=REPO_ROOT, receipt_path_override=p
            )


def test_15_neg_11_timeout_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (11): Timeout mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["timeout_ms"] = 60000
    p = _resign_and_write(tmp_path, "bad_timeout.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_16_neg_12_pacing_mutation_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (12): Pacing mutation -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["inter_call_delay_ms"] = 500
    p = _resign_and_write(tmp_path, "bad_pacing.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_17_neg_13_comparative_authorized_true_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (13): comparative=true -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] = True
    p = _resign_and_write(tmp_path, "bad_comparative.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_AUTH_COMPARATIVE_OR_DOWNSTREAM_FORBIDDEN",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_18_neg_14_holdout_firewall_true_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (14): Final100=true -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["FINAL100_USED"] = True
    p = _resign_and_write(tmp_path, "bad_holdout.json", bad)
    with pytest.raises(
        Final100FirewallViolationError,
        match="CANARY_EXECUTION_AUTH_FINAL100_FORBIDDEN",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )


def test_19_neg_15_execution_authorized_false_fails(
    receipt_data: dict[str, Any], tmp_path: Path
) -> None:
    """Section 14 (15): CANARY_LIVE_EXECUTION_AUTHORIZED=false -> fail."""
    bad = copy.deepcopy(receipt_data)
    bad["CANARY_LIVE_EXECUTION_AUTHORIZED"] = False
    p = _resign_and_write(tmp_path, "bad_exec_auth_false.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_NOT_AUTHORIZED",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT, receipt_path_override=p
        )
