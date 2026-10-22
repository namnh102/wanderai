"""Operational launcher for the frozen W06 DEV-TUNE (P1 + P2, 120 cells) experiment.

TASK: W06-DEV-TUNE-LIVE-LAUNCHER-01-OFFLINE

PURPOSE:
The generic runner CLI (`dev_live_runner.run_cli`) defaults to the one-prompt P1
infrastructure registry (`build_default_infrastructure_prompt_registry()`).
The frozen W06 DEV-TUNE experiment uses the two-prompt P1 + P2 registry
(`build_frozen_p1_p2_registry()`, SHA256 `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6`).

This script is strictly OPERATIONAL ORCHESTRATION ONLY:
- It is outside `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS`.
- It does NOT implement provider transports, request serialization, evaluation,
  parsing, selection, retry logic, cost logic, call-budget logic, or Stage-A verification.
- It delegates exclusively to existing production functions in
  `apps/ai-service/app/evaluation/dev_live_runner.py` and the frozen P1/P2 registry
  builder in `scripts/freeze_w06_dev_prompt_candidates.py`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
    TRANSPORT_STATUS_NOT_INVOKED,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    DevLiveStageAFreezeReceipt,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    PromptFreezeFirewallError,
    assert_no_secrets_in_payload,
    compute_prompt_freeze_sha256,
    create_live_provider_transport_factory,
    execute_live_dev_batch,
    issue_live_execution_capability,
    run_dev_live_runner_dry_run,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    Final100FirewallViolationError,
    PromptRegistry,
    ScientificCodeBundleIntegrityError,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    build_frozen_p1_p2_registry,
)

# ==============================================================================
# 1. FROZEN EXPERIMENT CONSTANTS & HARD-LOCKED AUTHORITIES (SECTIONS 2, 4, 5, 6, 10)
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-LIVE-LAUNCHER-01-OFFLINE"
BASE_DEVELOP_SHA = "dadff7f64d64444a0c8a72571135777498ecc6bf"
BRANCH_NAME = "research/w06-dev-tune-live-launcher-01"
LAUNCHER_REL_PATH = "scripts/run_w06_dev_tune_live_v1.py"

FROZEN_PHASE = "DEV_TUNE"
FROZEN_CANDIDATE_IDS: tuple[str, ...] = ("C1", "C2", "C3")
FROZEN_PROMPT_IDS: tuple[str, ...] = ("P1", "P2")
FROZEN_CELL_COUNT = 120
FROZEN_MAXIMUM_CALLS = 120
FROZEN_RETRY_POLICY = 0

FROZEN_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)

EXECUTION_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
EXPECTED_EXECUTION_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_EXECUTION_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)

AUTHORIZATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json"
)
EXPECTED_AUTHORIZATION_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
)

STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
)
EXPECTED_STAGE_A_FILE_SHA256 = (
    "a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31"
)
EXPECTED_STAGE_A_INTERNAL_SHA256 = (
    "a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

FROZEN_LIVE_OUTPUT_ROOT_REL_PATH = (
    "data/evaluation/w06/live_dev_tune_primary_v1"
)

FORBIDDEN_CLI_OVERRIDE_PREFIXES: tuple[str, ...] = (
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
    "--candidate",
    "--candidates",
    "--prompt",
    "--prompts",
    "--cell",
    "--cells",
    "--max-calls",
    "--retry",
    "--max-retries",
    "--resume",
    "--overwrite",
    "--clean",
)


# ==============================================================================
# 2. FAIL-CLOSED AUTHORITY, REGISTRY & OUTPUT-ROOT VERIFICATION
# ==============================================================================


def load_and_verify_frozen_p1_p2_registry() -> PromptRegistry:
    """Load the frozen P1+P2 PromptRegistry via `build_frozen_p1_p2_registry()` and verify its SHA256."""
    registry = build_frozen_p1_p2_registry()
    prompt_ids = tuple(p.prompt_id for p in registry.prompts)
    if prompt_ids != FROZEN_PROMPT_IDS:
        raise PromptFreezeFirewallError(
            f"FROZEN_PROMPT_IDS_MISMATCH: expected={list(FROZEN_PROMPT_IDS)}, got={list(prompt_ids)}"
        )
    if registry.registry_sha256 != FROZEN_PROMPT_REGISTRY_SHA256:
        raise PromptFreezeFirewallError(
            f"FROZEN_PROMPT_REGISTRY_SHA256_MISMATCH: expected={FROZEN_PROMPT_REGISTRY_SHA256}, "
            f"got={registry.registry_sha256}"
        )
    return registry


def verify_output_root_not_existing(repo_root: Path = REPO_ROOT) -> Path:
    """Verify that the frozen live output root `data/evaluation/w06/live_dev_tune_primary_v1` does not already exist."""
    output_root = repo_root / FROZEN_LIVE_OUTPUT_ROOT_REL_PATH
    if output_root.exists():
        raise PlanBeforeLiveProtocolError(
            f"LIVE_OUTPUT_ROOT_ALREADY_EXISTS: {output_root} already exists. "
            "Resume, overwrite, and automatic cleanup are strictly forbidden."
        )
    return output_root


def verify_frozen_launcher_authorities(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify scientific code bundle, frozen P1/P2 registry, execution plan, prompt freeze, authorization, Stage-A, and output root."""
    if LAUNCHER_REL_PATH in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        raise ScientificCodeBundleIntegrityError(
            f"LAUNCHER_IN_SCIENTIFIC_BUNDLE_FORBIDDEN: {LAUNCHER_REL_PATH} must remain outside SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS."
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: expected={EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got={bundle_sha}"
        )

    prompt_reg = load_and_verify_frozen_p1_p2_registry()

    plan_path = repo_root / EXECUTION_PLAN_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH
    stage_a_path = repo_root / STAGE_A_RECEIPT_REL_PATH

    if not plan_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_MISSING: {plan_path}"
        )
    if not pf_path.is_file():
        raise PromptFreezeFirewallError(f"PROMPT_FREEZE_MISSING: {pf_path}")
    if not auth_path.is_file():
        raise DevLiveAuthorizationError(f"AUTHORIZATION_MISSING: {auth_path}")
    if not stage_a_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_RECEIPT_MISSING: {stage_a_path}"
        )

    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    stage_a_bytes = normalize_lf_bytes(stage_a_path.read_bytes())

    plan_file_sha = sha256_bytes(plan_bytes)
    pf_file_sha = sha256_bytes(pf_bytes)
    auth_file_sha = sha256_bytes(auth_bytes)
    stage_a_file_sha = sha256_bytes(stage_a_bytes)

    if plan_file_sha != EXPECTED_EXECUTION_PLAN_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_FILE_SHA256_MISMATCH: expected={EXPECTED_EXECUTION_PLAN_FILE_SHA256}, got={plan_file_sha}"
        )
    if pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PromptFreezeFirewallError(
            f"PROMPT_FREEZE_FILE_SHA256_MISMATCH: expected={EXPECTED_PROMPT_FREEZE_SHA256}, got={pf_file_sha}"
        )
    if auth_file_sha != EXPECTED_AUTHORIZATION_FILE_SHA256:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_FILE_SHA256_MISMATCH: expected={EXPECTED_AUTHORIZATION_FILE_SHA256}, got={auth_file_sha}"
        )
    if stage_a_file_sha != EXPECTED_STAGE_A_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_FILE_SHA256_MISMATCH: expected={EXPECTED_STAGE_A_FILE_SHA256}, got={stage_a_file_sha}"
        )

    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)
    pf_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    auth_model = DevLiveAuthorizationArtifact.model_validate_json(auth_bytes)
    stage_a_model = DevLiveStageAFreezeReceipt.model_validate_json(stage_a_bytes)

    if plan_model.plan_sha256 != EXPECTED_EXECUTION_PLAN_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_SHA256_MISMATCH: expected={EXPECTED_EXECUTION_PLAN_SHA256}, got={plan_model.plan_sha256}"
        )
    if (
        plan_model.phase != FROZEN_PHASE
        or tuple(plan_model.candidate_ids) != FROZEN_CANDIDATE_IDS
        or tuple(plan_model.prompt_ids) != FROZEN_PROMPT_IDS
        or plan_model.expected_total_cells != FROZEN_CELL_COUNT
        or len(plan_model.cells) != FROZEN_CELL_COUNT
        or any(c.retry != FROZEN_RETRY_POLICY for c in plan_model.cells)
    ):
        raise PlanBeforeLiveProtocolError(
            "EXECUTION_PLAN_SCOPE_LOCK_MISMATCH: Plan does not match hard-locked DEV_TUNE C1/C2/C3 P1/P2 120-cell retry=0 scope."
        )

    if compute_prompt_freeze_sha256(pf_model) != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PromptFreezeFirewallError(
            "PROMPT_FREEZE_CANONICAL_SHA256_MISMATCH"
        )
    if (
        auth_model.authorization_id != EXPECTED_AUTHORIZATION_ID
        or auth_model.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        or auth_model.allowed_phase != FROZEN_PHASE
        or tuple(auth_model.allowed_candidate_ids) != FROZEN_CANDIDATE_IDS
        or auth_model.maximum_live_generation_calls != FROZEN_MAXIMUM_CALLS
    ):
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_SCOPE_LOCK_MISMATCH: Authorization does not match hard-locked DEV_TUNE scope."
        )
    if (
        stage_a_model.stage_a_receipt_sha256 != EXPECTED_STAGE_A_INTERNAL_SHA256
        or stage_a_model.phase != FROZEN_PHASE
        or len(stage_a_model.assigned_cell_run_ids) != FROZEN_CELL_COUNT
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_SCOPE_LOCK_MISMATCH: Stage-A receipt does not match hard-locked DEV_TUNE scope."
        )

    output_root = verify_output_root_not_existing(repo_root)

    return {
        "prompt_registry": prompt_reg,
        "execution_plan_path": plan_path,
        "prompt_freeze_path": pf_path,
        "authorization_path": auth_path,
        "stage_a_receipt_path": stage_a_path,
        "output_root": output_root,
        "scientific_code_bundle_sha256": bundle_sha,
    }


# ==============================================================================
# 3. PREFLIGHT MODE & LIVE DELEGATION MODE (SECTIONS 7, 8, 9)
# ==============================================================================


def run_preflight(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Run `--preflight` mode: delegate to production `run_dev_live_runner_dry_run(...)` with frozen P1+P2 registry."""
    verified = verify_frozen_launcher_authorities(repo_root)
    prompt_reg: PromptRegistry = verified["prompt_registry"]
    output_root: Path = verified["output_root"]

    dry_run_out = run_dev_live_runner_dry_run(
        execution_plan=verified["execution_plan_path"],
        prompt_freeze=verified["prompt_freeze_path"],
        prompt_registry=prompt_reg,
        authorization=verified["authorization_path"],
        stage_a_freeze_receipt=verified["stage_a_receipt_path"],
        batch_root_dir=output_root,
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
        or len(dry_run_out.get("serialized_request_sha256_by_run_id", {}))
        != FROZEN_CELL_COUNT
        or len(dry_run_out.get("planned_artifact_paths_by_run_id", {}))
        != FROZEN_CELL_COUNT
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_INVARIANT_MISMATCH: Unexpected dry-run output summary: {dry_run_out.get('mode')}, "
            f"phase={dry_run_out.get('phase')}, calls={dry_run_out.get('planned_call_count')}"
        )

    result = {
        **dry_run_out,
        "launcher_task_id": TASK_ID,
        "launcher_mode": "preflight",
        "frozen_prompt_ids": list(FROZEN_PROMPT_IDS),
        "frozen_prompt_registry_sha256": prompt_reg.registry_sha256,
        "live_output_root": FROZEN_LIVE_OUTPUT_ROOT_REL_PATH,
        "live_output_root_exists": output_root.exists(),
        "live_execution_capability_minted": False,
        "production_provider_transport_constructed": False,
    }
    assert_no_secrets_in_payload(result, context="W06_DEV_TUNE_LIVE_LAUNCHER_PREFLIGHT")
    return result


def run_live_execution(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Run `--execute-live --confirm-frozen-120-cells`: delegate exclusively to production runner functions."""
    verified = verify_frozen_launcher_authorities(repo_root)
    frozen_p1_p2_registry: PromptRegistry = verified["prompt_registry"]
    plan_path: Path = verified["execution_plan_path"]
    pf_path: Path = verified["prompt_freeze_path"]
    auth_path: Path = verified["authorization_path"]
    stage_a_path: Path = verified["stage_a_receipt_path"]
    output_root: Path = verified["output_root"]

    capability, plan_obj, _, verified_auth, _ = issue_live_execution_capability(
        execute_live=True,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        stage_a_freeze_receipt_path=stage_a_path,
        prompt_registry=frozen_p1_p2_registry,
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
        "frozen_prompt_ids": list(FROZEN_PROMPT_IDS),
        "frozen_prompt_registry_sha256": frozen_p1_p2_registry.registry_sha256,
        "live_output_root": FROZEN_LIVE_OUTPUT_ROOT_REL_PATH,
        "executed_cells": len(receipts),
        "ledger": ledger.summary(),
    }


# ==============================================================================
# 4. CLI ENTRYPOINT WITH HARD SCOPE LOCK & SAFETY FLAGS (SECTIONS 7, 8, 9, 10, 14)
# ==============================================================================


def run_launcher_cli(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """CLI entrypoint for `scripts/run_w06_dev_tune_live_v1.py`."""
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
                f"FINAL100_FIREWALL_VIOLATION: Forbidden Final100 argument {arg!r} in W06 DEV-TUNE launcher."
            )
        for forbidden_prefix in FORBIDDEN_CLI_OVERRIDE_PREFIXES:
            if arg_lower == forbidden_prefix or arg_lower.startswith(
                f"{forbidden_prefix}="
            ):
                raise PlanBeforeLiveProtocolError(
                    f"FROZEN_SCOPE_OVERRIDE_FORBIDDEN: CLI override {arg!r} is forbidden; "
                    "W06 DEV-TUNE launcher authorities, phase, candidates, prompts, cells, and output root are hard-locked."
                )

    parser = argparse.ArgumentParser(
        description="Frozen W06 DEV-TUNE (P1+P2, 120 cells) Operational Launcher.",
        add_help=True,
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run offline preflight dry-run using build_frozen_p1_p2_registry() and run_dev_live_runner_dry_run() (0 provider calls).",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Explicit live execution flag (MUST be combined with --confirm-frozen-120-cells).",
    )
    parser.add_argument(
        "--confirm-frozen-120-cells",
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
        parsed.execute_live or parsed.confirm_frozen_120_cells
    ):
        raise PlanBeforeLiveProtocolError(
            "MODE_CONFLICT_FORBIDDEN: Cannot combine --preflight with --execute-live or --confirm-frozen-120-cells."
        )

    if parsed.confirm_frozen_120_cells and not parsed.execute_live:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_FLAG_MISSING: --confirm-frozen-120-cells cannot be used without --execute-live."
        )

    if parsed.execute_live and not parsed.confirm_frozen_120_cells:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CONFIRMATION_FLAG_MISSING: --execute-live requires --confirm-frozen-120-cells."
        )

    if parsed.preflight:
        return run_preflight(repo_root=repo_root)

    if parsed.execute_live and parsed.confirm_frozen_120_cells:
        return run_live_execution(repo_root=repo_root)

    raise LiveExecutionNotAuthorizedError(
        "NO_MODE_SPECIFIED: Specify --preflight (offline) or both --execute-live and --confirm-frozen-120-cells."
    )


def main(argv: Sequence[str] | None = None) -> int:
    out = run_launcher_cli(argv if argv is not None else sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
