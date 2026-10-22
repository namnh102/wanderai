"""Pytest suite for W06-DEV-TUNE-LIVE-LAUNCHER-01-OFFLINE.

Covers LL-01 through LL-35 and adversarial launcher tests under an outbound
network kill switch (0 provider calls).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
    TRANSPORT_STATUS_NOT_INVOKED,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    PromptFreezeFirewallError,
    assert_no_secrets_in_payload,
    build_default_infrastructure_prompt_registry,
    run_cli,
    run_dev_live_runner_dry_run,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    Final100FirewallViolationError,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_tune_stage_a as sa_mod  # noqa: E402
import run_w06_dev_tune_live_v1 as launcher_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _enforce_no_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """LL-35: Block all outbound socket connections across every test in this module."""

    def _blocked_connect(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            f"OUTBOUND_NETWORK_CALL_FORBIDDEN_IN_OFFLINE_TEST: args={args!r}"
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect)
    monkeypatch.setattr(socket, "create_connection", _blocked_connect)


@pytest.fixture(scope="module")
def preflight_result() -> dict[str, Any]:
    """Run `--preflight` once for read-only inspection across LL checks."""
    return launcher_mod.run_launcher_cli(["--preflight"])


@pytest.fixture(scope="module")
def verified_authorities() -> dict[str, Any]:
    """Verify frozen launcher authorities once for read-only inspection."""
    return launcher_mod.verify_frozen_launcher_authorities(REPO_ROOT)


def test_ll01_scientific_bundle_unchanged() -> None:
    """LL-01: scientific bundle SHA256 unchanged."""
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    assert (
        bundle_sha
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )


def test_ll02_launcher_is_outside_scientific_bundle() -> None:
    """LL-02: launcher script is outside SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS."""
    assert (
        "scripts/run_w06_dev_tune_live_v1.py"
        not in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    )
    assert len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14


def test_ll03_frozen_p1_p2_registry_exact() -> None:
    """LL-03: frozen P1/P2 registry contains exact prompt IDs ['P1', 'P2']."""
    reg = launcher_mod.load_and_verify_frozen_p1_p2_registry()
    assert [p.prompt_id for p in reg.prompts] == ["P1", "P2"]


def test_ll04_frozen_prompt_registry_sha256_exact() -> None:
    """LL-04: frozen P1/P2 registry SHA256 = 846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6."""
    reg = launcher_mod.load_and_verify_frozen_p1_p2_registry()
    assert (
        reg.registry_sha256
        == "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
    )


def test_ll05_execution_plan_exact(verified_authorities: dict[str, Any]) -> None:
    """LL-05: DEV-TUNE execution plan path and SHA256 exact."""
    plan_path = verified_authorities["execution_plan_path"]
    assert (
        plan_path.relative_to(REPO_ROOT).as_posix()
        == "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
    )
    assert (
        sha256_bytes(normalize_lf_bytes(plan_path.read_bytes()))
        == "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
    )
    plan_json = json.loads(plan_path.read_text(encoding="utf-8"))
    assert (
        plan_json["plan_sha256"]
        == "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
    )


def test_ll06_prompt_freeze_exact(verified_authorities: dict[str, Any]) -> None:
    """LL-06: prompt freeze artifact path and SHA256 exact."""
    pf_path = verified_authorities["prompt_freeze_path"]
    assert (
        pf_path.relative_to(REPO_ROOT).as_posix()
        == "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
    )
    assert (
        sha256_bytes(normalize_lf_bytes(pf_path.read_bytes()))
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )


def test_ll07_authorization_exact(verified_authorities: dict[str, Any]) -> None:
    """LL-07: authorization artifact path, file SHA256, and internal SHA256 exact."""
    auth_path = verified_authorities["authorization_path"]
    assert (
        auth_path.relative_to(REPO_ROOT).as_posix()
        == "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json"
    )
    assert (
        sha256_bytes(normalize_lf_bytes(auth_path.read_bytes()))
        == "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
    )
    auth_json = json.loads(auth_path.read_text(encoding="utf-8"))
    assert (
        auth_json["authorization_artifact_sha256"]
        == "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
    )


def test_ll08_stage_a_exact(verified_authorities: dict[str, Any]) -> None:
    """LL-08: Stage-A freeze receipt path, file SHA256, and internal SHA256 exact."""
    stage_a_path = verified_authorities["stage_a_receipt_path"]
    assert (
        stage_a_path.relative_to(REPO_ROOT).as_posix()
        == "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
    )
    assert (
        sha256_bytes(normalize_lf_bytes(stage_a_path.read_bytes()))
        == "a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31"
    )
    stage_a_json = json.loads(stage_a_path.read_text(encoding="utf-8"))
    assert (
        stage_a_json["stage_a_receipt_sha256"]
        == "a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f"
    )


def test_ll09_output_root_exact(verified_authorities: dict[str, Any]) -> None:
    """LL-09: output root exact and does not exist before live run."""
    out_root = verified_authorities["output_root"]
    assert (
        out_root.relative_to(REPO_ROOT).as_posix()
        == "data/evaluation/w06/live_dev_tune_primary_v1"
    )
    assert not out_root.exists()


def test_ll10_output_root_existing_fails_closed(tmp_path: Path) -> None:
    """LL-10: existing output root fails closed with LIVE_OUTPUT_ROOT_ALREADY_EXISTS."""
    existing_out = (
        tmp_path / "data" / "evaluation" / "w06" / "live_dev_tune_primary_v1"
    )
    existing_out.mkdir(parents=True)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="LIVE_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        launcher_mod.verify_output_root_not_existing(tmp_path)


def test_ll11_preflight_uses_production_dry_run(
    preflight_result: dict[str, Any],
) -> None:
    """LL-11: --preflight uses production run_dev_live_runner_dry_run and verifies authorization + Stage-A."""
    assert preflight_result["mode"] == "dry_run"
    assert preflight_result["launcher_mode"] == "preflight"
    assert preflight_result["phase"] == "DEV_TUNE"
    assert preflight_result["authorization_verified"] is True
    assert preflight_result["stage_a_verified"] is True


def test_ll12_preflight_planned_cells_120(
    preflight_result: dict[str, Any],
) -> None:
    """LL-12: preflight planned cells = 120, serialized request hashes = 120, planned paths = 120."""
    assert preflight_result["planned_call_count"] == 120
    assert preflight_result["expected_total_cells"] == 120
    assert len(preflight_result["serialized_request_sha256_by_run_id"]) == 120
    assert len(preflight_result["planned_artifact_paths_by_run_id"]) == 120


def test_ll13_preflight_transport_not_invoked(
    preflight_result: dict[str, Any],
) -> None:
    """LL-13: preflight transport_status == TRANSPORT_NOT_INVOKED."""
    assert preflight_result["transport_status"] == TRANSPORT_STATUS_NOT_INVOKED


def test_ll14_preflight_live_calls_zero(
    preflight_result: dict[str, Any],
) -> None:
    """LL-14: preflight live_provider_calls == 0 and provider_cost_usd == 0."""
    assert preflight_result["live_provider_calls"] == 0
    assert preflight_result["provider_cost_usd"] == 0


def test_ll15_preflight_does_not_mint_capability(
    preflight_result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LL-15: preflight does not mint LiveExecutionCapability."""
    assert preflight_result["live_execution_capability_minted"] is False

    def _forbid_capability(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("issue_live_execution_capability forbidden in preflight")

    monkeypatch.setattr(
        launcher_mod, "issue_live_execution_capability", _forbid_capability
    )
    out = launcher_mod.run_launcher_cli(["--preflight"])
    assert out["live_execution_capability_minted"] is False


def test_ll16_preflight_does_not_construct_production_transport(
    preflight_result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LL-16: preflight does not construct ProductionDevProviderTransport or output root."""
    assert preflight_result["production_provider_transport_constructed"] is False
    assert not (REPO_ROOT / launcher_mod.FROZEN_LIVE_OUTPUT_ROOT_REL_PATH).exists()

    def _forbid_transport(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "create_live_provider_transport_factory forbidden in preflight"
        )

    monkeypatch.setattr(
        launcher_mod, "create_live_provider_transport_factory", _forbid_transport
    )
    out = launcher_mod.run_launcher_cli(["--preflight"])
    assert out["production_provider_transport_constructed"] is False


def test_ll17_live_path_requires_execute_live() -> None:
    """LL-17: live path requires --execute-live."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="NO_MODE_SPECIFIED"):
        launcher_mod.run_launcher_cli([])

    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_EXECUTION_FLAG_MISSING"
    ):
        launcher_mod.run_launcher_cli(["--confirm-frozen-120-cells"])


def test_ll18_live_path_requires_confirm_frozen_120_cells() -> None:
    """LL-18: live path also requires --confirm-frozen-120-cells."""
    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_CONFIRMATION_FLAG_MISSING"
    ):
        launcher_mod.run_launcher_cli(["--execute-live"])

    with pytest.raises(PlanBeforeLiveProtocolError, match="MODE_CONFLICT_FORBIDDEN"):
        launcher_mod.run_launcher_cli(
            ["--preflight", "--execute-live", "--confirm-frozen-120-cells"]
        )


def test_ll19_no_arbitrary_phase_cli_option() -> None:
    """LL-19: no arbitrary --phase CLI option permitted."""
    for argv in (
        ["--preflight", "--phase=DEV_SELECT"],
        ["--preflight", "--phase", "DEV_SELECT"],
    ):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FROZEN_SCOPE_OVERRIDE_FORBIDDEN"
        ):
            launcher_mod.run_launcher_cli(argv)


def test_ll20_no_arbitrary_plan_prompt_auth_stage_a_or_output_root_override() -> None:
    """LL-20: no arbitrary plan, prompt-freeze, authorization, Stage-A, or output-root override permitted."""
    for override_flag in (
        "--execution-plan=other.json",
        "--prompt-freeze=other.json",
        "--authorization-artifact=other.json",
        "--stage-a-freeze-receipt=other.json",
        "--batch-root-dir=/tmp/out",
        "--output-root=/tmp/out",
    ):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FROZEN_SCOPE_OVERRIDE_FORBIDDEN"
        ):
            launcher_mod.run_launcher_cli(["--preflight", override_flag])


def test_ll21_no_custom_candidate_filter() -> None:
    """LL-21: no custom candidate filter permitted."""
    for cand_flag in ("--candidate=C1", "--candidates=C1,C2"):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FROZEN_SCOPE_OVERRIDE_FORBIDDEN"
        ):
            launcher_mod.run_launcher_cli(["--preflight", cand_flag])


def test_ll22_no_custom_prompt_filter() -> None:
    """LL-22: no custom prompt filter permitted."""
    for prompt_flag in ("--prompt=P1", "--prompts=P1"):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FROZEN_SCOPE_OVERRIDE_FORBIDDEN"
        ):
            launcher_mod.run_launcher_cli(["--preflight", prompt_flag])


def test_ll23_no_retry_or_resume_controls() -> None:
    """LL-23: no retry, resume, or overwrite CLI controls permitted."""
    for retry_flag in ("--retry=1", "--max-retries=2", "--resume", "--overwrite"):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FROZEN_SCOPE_OVERRIDE_FORBIDDEN"
        ):
            launcher_mod.run_launcher_cli(["--preflight", retry_flag])


def _run_monkeypatched_live_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]], Any, Any, Any]:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _DummyPlan:
        phase = "DEV_TUNE"

    class _DummyAuth:
        authorization_id = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"

    class _DummyCapability:
        phase = "DEV_TUNE"

    class _DummyLedger:
        def summary(self) -> dict[str, Any]:
            return {
                "phase": "DEV_TUNE",
                "maximum_live_generation_calls": 120,
                "reserved_calls": 0,
                "consumed_calls": 0,
            }

    dummy_cap = _DummyCapability()
    dummy_auth = _DummyAuth()
    dummy_transport = object()

    def _fake_issue_capability(**kwargs: Any) -> Any:
        calls.append(("issue_live_execution_capability", kwargs))
        return dummy_cap, _DummyPlan(), object(), dummy_auth, object()

    def _fake_create_transport(**kwargs: Any) -> Any:
        calls.append(("create_live_provider_transport_factory", kwargs))
        return dummy_transport

    def _fake_execute_batch(**kwargs: Any) -> Any:
        calls.append(("execute_live_dev_batch", kwargs))
        return [], _DummyLedger()

    monkeypatch.setattr(
        launcher_mod, "issue_live_execution_capability", _fake_issue_capability
    )
    monkeypatch.setattr(
        launcher_mod,
        "create_live_provider_transport_factory",
        _fake_create_transport,
    )
    monkeypatch.setattr(
        launcher_mod, "execute_live_dev_batch", _fake_execute_batch
    )

    out = launcher_mod.run_launcher_cli(
        ["--execute-live", "--confirm-frozen-120-cells"]
    )
    return out, calls, dummy_cap, dummy_auth, dummy_transport


def test_ll24_live_path_delegates_to_issue_live_execution_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LL-24: live path delegates to issue_live_execution_capability with frozen P1/P2 registry."""
    out, calls, _, _, _ = _run_monkeypatched_live_delegation(monkeypatch)
    assert out["mode"] == "execute_live"
    assert calls[0][0] == "issue_live_execution_capability"
    cap_kwargs = calls[0][1]
    assert cap_kwargs["execute_live"] is True
    assert (
        cap_kwargs["prompt_registry"].registry_sha256
        == launcher_mod.FROZEN_PROMPT_REGISTRY_SHA256
    )


def test_ll25_live_path_delegates_to_create_live_provider_transport_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LL-25: live path delegates to create_live_provider_transport_factory."""
    _, calls, dummy_cap, dummy_auth, _ = _run_monkeypatched_live_delegation(
        monkeypatch
    )
    assert calls[1][0] == "create_live_provider_transport_factory"
    tr_kwargs = calls[1][1]
    assert tr_kwargs["execute_live"] is True
    assert tr_kwargs["authorization"] is dummy_auth
    assert tr_kwargs["live_capability"] is dummy_cap


def test_ll26_live_path_delegates_to_execute_live_dev_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LL-26: live path delegates to execute_live_dev_batch with exact frozen paths and output root."""
    _, calls, dummy_cap, _, dummy_transport = _run_monkeypatched_live_delegation(
        monkeypatch
    )
    assert calls[2][0] == "execute_live_dev_batch"
    batch_kwargs = calls[2][1]
    assert batch_kwargs["transport"] is dummy_transport
    assert batch_kwargs["execution_mode"] == RUNNER_EXECUTION_MODE_LIVE_EXECUTION
    assert batch_kwargs["live_capability"] is dummy_cap
    assert (
        batch_kwargs["batch_root_dir"]
        == REPO_ROOT / "data/evaluation/w06/live_dev_tune_primary_v1"
    )


def test_ll27_launcher_contains_no_provider_specific_http_code() -> None:
    """LL-27: launcher AST contains no provider-specific HTTP imports or clients."""
    launcher_path = REPO_ROOT / "scripts" / "run_w06_dev_tune_live_v1.py"
    source = launcher_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(launcher_path))

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_http_modules = {
        "httpx",
        "requests",
        "urllib",
        "urllib.request",
        "aiohttp",
        "openai",
        "anthropic",
        "google.genai",
    }
    assert imported_modules.isdisjoint(forbidden_http_modules)


def test_ll28_launcher_contains_no_evaluator_or_parser_logic() -> None:
    """LL-28: launcher AST contains no evaluator, parser, cell-loop, or secret-loader calls."""
    launcher_path = REPO_ROOT / "scripts" / "run_w06_dev_tune_live_v1.py"
    source = launcher_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(launcher_path))

    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert "execute_live_dev_cell" not in called_names
    assert "evaluate_itinerary" not in called_names
    assert "parse_primary_json_response" not in called_names
    assert "build_test_only_stage_a_freeze_receipt" not in called_names
    assert "getenv" not in called_names
    assert "load_dotenv" not in called_names


def test_ll29_generic_p1_only_registry_fails_frozen_p1_p2_validation_offline() -> None:
    """LL-29: generic P1-only registry fails frozen P1+P2 validation offline with PROMPT_CANDIDATE_ID_MISMATCH."""
    p1_only_reg = build_default_infrastructure_prompt_registry()
    assert [p.prompt_id for p in p1_only_reg.prompts] == ["P1"]

    with pytest.raises(
        PromptFreezeFirewallError, match="PROMPT_CANDIDATE_ID_MISMATCH"
    ):
        run_cli(
            [
                "--dry-run",
                "--execution-plan",
                str(REPO_ROOT / launcher_mod.EXECUTION_PLAN_REL_PATH),
                "--prompt-freeze",
                str(REPO_ROOT / launcher_mod.PROMPT_FREEZE_REL_PATH),
            ]
        )

    with pytest.raises(
        PromptFreezeFirewallError, match="PROMPT_CANDIDATE_ID_MISMATCH"
    ):
        run_dev_live_runner_dry_run(
            execution_plan=REPO_ROOT / launcher_mod.EXECUTION_PLAN_REL_PATH,
            prompt_freeze=REPO_ROOT / launcher_mod.PROMPT_FREEZE_REL_PATH,
            prompt_registry=p1_only_reg,
            repo_root=REPO_ROOT,
        )


def test_ll30_explicit_p1_p2_registry_passes_dry_run_validation_offline() -> None:
    """LL-30: explicit P1+P2 registry passes dry-run validation offline."""
    p1_p2_reg = launcher_mod.load_and_verify_frozen_p1_p2_registry()
    dry_out = run_dev_live_runner_dry_run(
        execution_plan=REPO_ROOT / launcher_mod.EXECUTION_PLAN_REL_PATH,
        prompt_freeze=REPO_ROOT / launcher_mod.PROMPT_FREEZE_REL_PATH,
        prompt_registry=p1_p2_reg,
        authorization=REPO_ROOT / launcher_mod.AUTHORIZATION_REL_PATH,
        stage_a_freeze_receipt=REPO_ROOT / launcher_mod.STAGE_A_RECEIPT_REL_PATH,
        repo_root=REPO_ROOT,
    )
    assert dry_out["mode"] == "dry_run"
    assert dry_out["planned_call_count"] == 120
    assert dry_out["authorization_verified"] is True
    assert dry_out["stage_a_verified"] is True


def test_ll31_final100_forbidden() -> None:
    """LL-31: Final100 paths, flags, and scenario IDs are forbidden."""
    for forbidden_arg in (
        "--final100",
        "data/evaluation/w06/w06_scenarios_freeze_v1.json",
        "data/evaluation/w06/w06_p11_assignment_manifest_v1.json",
        "W06-SCENARIO-001",
    ):
        with pytest.raises(
            Final100FirewallViolationError, match="FINAL100_FIREWALL_VIOLATION"
        ):
            launcher_mod.run_launcher_cli(["--preflight", forbidden_arg])


def test_ll32_no_api_key_value_printed_or_persisted(
    preflight_result: dict[str, Any],
) -> None:
    """LL-32: no API key value printed or persisted in preflight output."""
    assert_no_secrets_in_payload(preflight_result, context="LL_32_PREFLIGHT_OUTPUT")


def test_ll33_stage_a_unchanged_and_valid_in_separate_process() -> None:
    """LL-33: Stage-A receipt remains unchanged and separate-process verification passes."""
    stage_a_path = REPO_ROOT / launcher_mod.STAGE_A_RECEIPT_REL_PATH
    assert (
        sha256_bytes(normalize_lf_bytes(stage_a_path.read_bytes()))
        == "a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31"
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "freeze_w06_dev_tune_stage_a.py"),
            "--verify-committed",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Stage-A verify-committed failed: {proc.stderr}\n{proc.stdout}"
    stage_a_verify_payload = json.loads(proc.stdout)
    assert stage_a_verify_payload["separate_process_committed_verification_passed"] is True
    assert stage_a_verify_payload["sa_checks"] == "40/40 PASS"
    assert stage_a_verify_payload["saa_checks"] == "15/15 PASS"


def test_ll34_authorization_unchanged() -> None:
    """LL-34: authorization artifact remains unchanged."""
    auth_path = REPO_ROOT / launcher_mod.AUTHORIZATION_REL_PATH
    assert (
        sha256_bytes(normalize_lf_bytes(auth_path.read_bytes()))
        == "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
    )


def test_ll35_zero_provider_calls_during_tests() -> None:
    """LL-35: zero provider calls, zero cost, and zero live output directories created."""
    fw = sa_mod.verify_no_live_execution_or_stage_b_artifacts(REPO_ROOT)
    assert fw["live_provider_calls"] == 0
    assert fw["provider_cost_usd"] == 0.0
    assert fw["transport_journal_created"] is False
    assert fw["provider_result_directory_created"] is False
    assert not (REPO_ROOT / launcher_mod.FROZEN_LIVE_OUTPUT_ROOT_REL_PATH).exists()
