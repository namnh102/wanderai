"""W06-DEV-PROMPT-CANDIDATE-FREEZE-01 & AUDIT-CORRECTION-01 — Offline Prompt Candidate Freeze & Verification Script.

Strictly offline scientific prompt-freeze script:
- Reconstructs exact baseline P1 from frozen repository authorities
- Constructs exact pre-results candidate P2 with the provider-neutral constraint-check suffix
- Enforces identical prompt_version ("TRAVEL_PLANNER_BENCHMARK_V2") across P1 and P2 so that
  rendered user prompts are 100% byte-identical for every DEV-TUNE fixture (removing the
  template interpolation confound detected in Audit Correction 01)
- Preserves P2_CANDIDATE_DEFINITION_ID = "W06_DEV_TUNE_CANDIDATE_P2_V1" strictly as experiment
  metadata outside model prompt semantics
- Builds [P1, P2] PromptRegistry (max 2 prompts, P3 forbidden)
- Loads VerifiedDevBundle (80 DEV fixtures: 20 DEV_TUNE, 60 DEV_SELECT)
- Builds deterministic 120-cell DEV_TUNE execution plan (20 fixtures x 2 prompts x 3 candidates x 1 attempt)
- Builds DevPromptFreezeArtifact (W06-DEV-PROMPT-CANDIDATE-FREEZE-01-V1, version 1.0.0)
- Runs all 35 PF checks (PF-01..PF-35) and all 16 Audit Correction checks (PFC-01..PFC-16)
  under an outbound network kill switch
- Emits the freeze artifact, execution plan artifact, and verification receipt
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

import httpx  # noqa: E402

try:
    import httpx2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    httpx2 = None

import app.evaluation.dev_selection_harness as harness  # noqa: E402
from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_MODEL_BY_ID,
    CANDIDATE_PROVIDER_BY_ID,
    verify_runner_prompt_freeze_artifact,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    ALLOWED_PROMPT_IDS,
    DEV_SELECT_COUNT,
    DEV_TOTAL_COUNT,
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    MAX_PROMPT_CANDIDATES,
    ORDERED_CANDIDATE_IDS,
    PRACTICAL_TIE_ABS_DIFF_RATIO,
    PRIMARY_DEV_RATE_CRITERIA,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevCandidateRegistry,
    DevCellExecutionReceipt,
    DevCellFailureClassification,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    PromptCandidateSpec,
    PromptRegistry,
    VerifiedDevBundle,
    assert_not_final100_path,
    build_default_infrastructure_prompt_registry,
    build_destination_catalog_context,
    build_deterministic_dev_scenario_context,
    build_dev_prompt_freeze_artifact,
    build_dev_tune_execution_plan,
    build_prompt_registry,
    canonical_json_bytes,
    compute_candidate_provider_config_sha256,
    compute_common_portable_generation_schema_sha256_v2,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_file_hashes,
    compute_scientific_code_bundle_sha256,
    compute_semantic_prompt_sha256,
    compute_semantic_schema_sha256,
    create_prompt_candidate_spec,
    format_canonical_decimal_str,
    get_cached_provider_config_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    resolve_active_git_commit_sha,
    select_winning_prompt_dev_tune,
    verify_dev_execution_plan_for_execution,
    verify_prompt_candidate_freeze_artifact,
)
from app.evaluation.model_preflight.base import (  # noqa: E402
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
)
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
    TRAVEL_PLANNER_BENCHMARK_V2,
)

TASK_ID = "W06-DEV-PROMPT-CANDIDATE-FREEZE-01"
AUDIT_CORRECTION_TASK_ID = "W06-DEV-PROMPT-CANDIDATE-FREEZE-01-AUDIT-CORRECTION-01"
EXPECTED_BASE_DEVELOP_SHA = "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"
CODE_BASIS_COMMIT_SHA = "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"
PREDECESSOR_DRAFT_HEAD_SHA = "0299fcd5d8d3426867df5298641c894ea8692263"

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES: list[dict[str, str]] = [
    {
        "path": "apps/ai-service/app/evaluation/dev_live_runner.py",
        "sha256": "9f3441c2ca290e9a33b4daa78eaaa58063978364d8375145fc7483b04ed8b817",
    },
    {
        "path": "apps/ai-service/app/evaluation/dev_selection_harness.py",
        "sha256": "85b17c2daa1ea59e26c3118d5cafb38cb3c73a5d57288e2fb4e5fc0e0a732c97",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/__init__.py",
        "sha256": "178aede4930a6b848714fa6d84e14e415df35d1bf7641312ff6f311e3de477dd",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/anthropic_adapter.py",
        "sha256": "ef2570126f6db736a4ef056ac27fcfc77db97fa6ed6526c901e299c71b1b1d42",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/base.py",
        "sha256": "55bd026f224eaf15f5fb68e98d9cd9467bf85f0f90305acac397caef0970454d",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/google_adapter.py",
        "sha256": "184887b19826094326e5fea47efd7aec71308b36af404225f5ef8d0d40882f1c",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/openai_adapter.py",
        "sha256": "62b72237402808ab88d71627ce05d948d4b7d251ba87af51208876c784ee9346",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/schema_adapter.py",
        "sha256": "19513c8735ba4acb2b88587915d6458de2c28d622499c05314d4f9030eb3c589",
    },
    {
        "path": "apps/ai-service/app/evaluation/model_preflight/types.py",
        "sha256": "1fdb31f200a71df4193f1fe4844b49dc1e9750c51c7388e6642dac44ae349371",
    },
    {
        "path": "apps/ai-service/app/evaluation/planner_benchmark_evaluator.py",
        "sha256": "1b299f75a3a51d01b63b1b004df3d8b9d92224591ccde5d537b83735ca268f66",
    },
    {
        "path": "apps/ai-service/app/prompts/planner_benchmark_prompt.py",
        "sha256": "22aa9cd172548fe51a8699704e5832ad44e1d8e946a1ad79437aed99d46c98cb",
    },
    {
        "path": "apps/ai-service/app/schemas/planner_benchmark.py",
        "sha256": "3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712",
    },
    {
        "path": "apps/ai-service/app/services/planner_benchmark_runner.py",
        "sha256": "2831f5aadd80959a86f388508c73679215830ca8854f2a4fbd474328fa7288b7",
    },
    {
        "path": "apps/ai-service/recommendation/reca/contract.py",
        "sha256": "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
    },
]
EXPECTED_DEV_FIXTURES_SHA256 = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
    "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
]

PROMPT_CANDIDATE_DECISION = "P1_PLUS_P2_PRE_RESULTS"
NO_PROMPT_RESULT_SHOPPING = True

FREEZE_ARTIFACT_ID = "W06-DEV-PROMPT-CANDIDATE-FREEZE-01-V1"
FREEZE_ARTIFACT_VERSION = "1.0.0"

P1_PROMPT_ID = "P1"
P1_EXPECTED_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"
P1_EXPECTED_SYSTEM_PROMPT_SHA256 = (
    "4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e"
)
P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)
P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)
P1_NON_AUTHORITATIVE_HISTORICAL_PROSE_SHA256 = (
    "49399ca4ab45e98dd7da05c94609d5bf5c03667ca79a96f52c7f330f357ac5e9"
)

# Audit Correction 01:
# Both P1 and P2 MUST use the exact same template prompt_version ("TRAVEL_PLANNER_BENCHMARK_V2")
# because TRAVEL_PLANNER_BENCHMARK_V2 interpolates `{prompt_version}` into the rendered user prompt.
# P2_CANDIDATE_DEFINITION_ID is preserved strictly as experiment metadata outside model prompt semantics.
P2_PROMPT_ID = "P2"
P2_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"
P2_CANDIDATE_DEFINITION_ID = "W06_DEV_TUNE_CANDIDATE_P2_V1"

P2_EXACT_SYSTEM_PROMPT_SUFFIX = (
    "Before returning the JSON, perform a silent constraint check and correct the draft if needed:\n"
    "(1) every POI_VISIT must copy an exact place_id and matching place_name from the provided REC-A-CORE-V2 catalog;\n"
    "(2) each day must contain at least two POI_VISIT items;\n"
    "(3) do not repeat a place_id unless allow_revisit_place_ids=true;\n"
    "(4) use valid non-overlapping HH:MM intervals with start_time < end_time;\n"
    "(5) when opening_hours is known and parseable, schedule the POI visit within it, while missing or unknown opening_hours must not be invented;\n"
    "and (6) respect the scenario budget when a budget ceiling is provided.\n"
    "Do not reveal this checking process; output only the final JSON object."
)
P2_EXPECTED_SYSTEM_PROMPT_SHA256 = (
    "ab8ec41b7099c1c207217a55e1afd7e075d5de6be9b2fc14863329b5535e6c68"
)
P2_EXPECTED_USER_PROMPT_TEMPLATE_SHA256 = (
    "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
)
P2_EXPECTED_SEMANTIC_PROMPT_SHA256 = (
    "0679dd9463d6cebf04ccb5571a403331eea3ab6819bd6a0e8b2ee1fc08c99fdf"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
EXPECTED_DEV_TUNE_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_DEV_TUNE_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256 = (
    "c632a1f607203a81c9422164a7910c5f82211437d74af9c91bb6b370c1da3c17"
)

FREEZE_ARTIFACT_RELATIVE_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
DEV_TUNE_PLAN_RELATIVE_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
FREEZE_RECEIPT_RELATIVE_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_01_receipt_v1.json"
)
DEV_FIXTURES_FREEZE_RELATIVE_PATH = (
    "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
)
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)

PROVIDER_FORBIDDEN_PROMPT_TOKENS = (
    "gemini",
    "google",
    "openai",
    "gpt-",
    "chatgpt",
    "anthropic",
    "claude",
)


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline prompt freeze."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_create_connection = socket.create_connection
        orig_urlopen = urllib.request.urlopen
        orig_httpx_sync = httpx.HTTPTransport.handle_request
        orig_httpx_async = httpx.AsyncHTTPTransport.handle_async_request
        orig_httpx2_sync = (
            getattr(httpx2.HTTPTransport, "handle_request", None)
            if httpx2 is not None
            else None
        )

        def _block_socket_connect(sock_self: Any, address: Any) -> Any:
            msg = f"OUTBOUND_SOCKET_CONNECT_BLOCKED:{address!r}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        def _block_socket_connect_ex(sock_self: Any, address: Any) -> Any:
            msg = f"OUTBOUND_SOCKET_CONNECT_EX_BLOCKED:{address!r}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        def _block_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
            msg = f"OUTBOUND_CREATE_CONNECTION_BLOCKED:{address!r}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        def _block_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
            msg = f"OUTBOUND_URLOPEN_BLOCKED:{url!r}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        def _block_httpx_sync(transport_self: Any, request: Any) -> Any:
            msg = f"OUTBOUND_HTTPX_SYNC_BLOCKED:{request.url}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        async def _block_httpx_async(transport_self: Any, request: Any) -> Any:
            msg = f"OUTBOUND_HTTPX_ASYNC_BLOCKED:{request.url}"
            self.blocked_attempts.append(msg)
            raise OutboundNetworkBlockedError(msg)

        socket.socket.connect = _block_socket_connect  # type: ignore[assignment]
        socket.socket.connect_ex = _block_socket_connect_ex  # type: ignore[assignment]
        socket.create_connection = _block_create_connection  # type: ignore[assignment]
        urllib.request.urlopen = _block_urlopen  # type: ignore[assignment]
        httpx.HTTPTransport.handle_request = _block_httpx_sync  # type: ignore[assignment]
        httpx.AsyncHTTPTransport.handle_async_request = _block_httpx_async  # type: ignore[assignment]
        if httpx2 is not None and orig_httpx2_sync is not None:
            httpx2.HTTPTransport.handle_request = _block_httpx_sync  # type: ignore[assignment]

        try:
            yield self
        finally:
            socket.socket.connect = orig_connect  # type: ignore[assignment]
            socket.socket.connect_ex = orig_connect_ex  # type: ignore[assignment]
            socket.create_connection = orig_create_connection  # type: ignore[assignment]
            urllib.request.urlopen = orig_urlopen  # type: ignore[assignment]
            httpx.HTTPTransport.handle_request = orig_httpx_sync  # type: ignore[assignment]
            httpx.AsyncHTTPTransport.handle_async_request = orig_httpx_async  # type: ignore[assignment]
            if httpx2 is not None and orig_httpx2_sync is not None:
                httpx2.HTTPTransport.handle_request = orig_httpx2_sync  # type: ignore[assignment]


@contextlib.contextmanager
def scrub_provider_api_keys() -> Iterator[None]:
    """Ensure provider API keys are absent from os.environ during offline prompt freeze."""
    keys = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def sha256_utf8_lf(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_p1_spec() -> PromptCandidateSpec:
    """Reconstruct P1 exclusively from frozen authorities."""
    default_reg = build_default_infrastructure_prompt_registry()
    spec = default_reg.prompts[0]
    if spec.prompt_id != P1_PROMPT_ID:
        raise ValueError(f"Unexpected P1 prompt_id: {spec.prompt_id}")
    if spec.prompt_version != BENCHMARK_PROMPT_VERSION:
        raise ValueError(f"Unexpected P1 prompt_version: {spec.prompt_version}")
    if spec.system_prompt != PREFLIGHT_SHARED_SYSTEM_PROMPT:
        raise ValueError(
            "P1 system_prompt drifted from PREFLIGHT_SHARED_SYSTEM_PROMPT"
        )
    if spec.user_prompt_template != TRAVEL_PLANNER_BENCHMARK_V2:
        raise ValueError(
            "P1 user_prompt_template drifted from TRAVEL_PLANNER_BENCHMARK_V2"
        )
    return spec


def build_p2_system_prompt() -> str:
    """Construct P2 system prompt: PREFLIGHT_SHARED_SYSTEM_PROMPT + '\\n' + exact suffix."""
    return f"{PREFLIGHT_SHARED_SYSTEM_PROMPT}\n{P2_EXACT_SYSTEM_PROMPT_SUFFIX}"


def build_p2_spec() -> PromptCandidateSpec:
    """Construct pre-results candidate P2 with identical template prompt_version as P1."""
    return create_prompt_candidate_spec(
        prompt_id=P2_PROMPT_ID,
        prompt_version=P2_PROMPT_VERSION,
        system_prompt=build_p2_system_prompt(),
        user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
        created_before_live_dev_execution=True,
        provider_specific_semantic_prompt=False,
    )


def compute_expected_p2_semantic_prompt_sha256() -> str:
    """Recompute P2 semantic prompt SHA256 from frozen inputs."""
    return compute_semantic_prompt_sha256(
        prompt_id=P2_PROMPT_ID,
        prompt_version=P2_PROMPT_VERSION,
        system_prompt=build_p2_system_prompt(),
        user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
    )


def build_frozen_p1_p2_registry() -> PromptRegistry:
    """Build exact ordered [P1, P2] PromptRegistry."""
    p1 = build_p1_spec()
    p2 = build_p2_spec()
    return build_prompt_registry([p1, p2])


@contextlib.contextmanager
def _bind_frozen_code_basis_commit(code_basis_commit_sha: str) -> Iterator[None]:
    """Allow deterministic reconstruction anchored to CODE_BASIS_COMMIT_SHA on descendant commits

    after verifying that the 14-file scientific code bundle SHA256 and per-file hashes are completely unchanged.
    """
    current_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    current_bundle_files = compute_scientific_code_bundle_file_hashes(
        repo_root=REPO_ROOT
    )
    if (
        current_bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        or current_bundle_files != EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
    ):
        raise RuntimeError(
            "BLOCKED_BY_SCIENTIFIC_BUNDLE_MUTATION: "
            f"expected {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got {current_bundle_sha}"
        )
    orig_resolve = harness.resolve_active_git_commit_sha
    active_sha = orig_resolve(repo_root=REPO_ROOT)
    if active_sha != code_basis_commit_sha:
        completed = subprocess.run(
            ["git", "cat-file", "-e", f"{code_basis_commit_sha}^{{commit}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            ancestry = subprocess.run(
                ["git", "merge-base", "--is-ancestor", code_basis_commit_sha, "HEAD"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            if ancestry.returncode != 0:
                raise RuntimeError(
                    f"Frozen code_basis_commit_sha {code_basis_commit_sha} is not an ancestor of HEAD."
                )
        else:
            shallow_proc = subprocess.run(
                ["git", "rev-parse", "--is-shallow-repository"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            if shallow_proc.stdout.strip().lower() != "true":
                raise RuntimeError(
                    f"Frozen code_basis_commit_sha {code_basis_commit_sha} not found in non-shallow git object database."
                )
    harness.resolve_active_git_commit_sha = lambda repo_root=REPO_ROOT: code_basis_commit_sha  # type: ignore[assignment]
    try:
        yield
    finally:
        harness.resolve_active_git_commit_sha = orig_resolve  # type: ignore[assignment]


def build_frozen_dev_tune_plan_and_freeze(
    *,
    dev_bundle: VerifiedDevBundle | None = None,
    candidate_registry: DevCandidateRegistry | None = None,
    prompt_registry: PromptRegistry | None = None,
) -> tuple[
    VerifiedDevBundle,
    DevCandidateRegistry,
    PromptRegistry,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
]:
    """Deterministically build the W06 DEV-TUNE execution plan and prompt freeze artifact."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    registry = prompt_registry or build_frozen_p1_p2_registry()
    with _bind_frozen_code_basis_commit(CODE_BASIS_COMMIT_SHA):
        plan = build_dev_tune_execution_plan(
            registry,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            code_basis_commit_sha=CODE_BASIS_COMMIT_SHA,
            repo_root=REPO_ROOT,
        )
        freeze_artifact = build_dev_prompt_freeze_artifact(
            prompt_registry=registry,
            dev_tune_plan=plan,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            code_basis_commit_sha=CODE_BASIS_COMMIT_SHA,
            repo_root=REPO_ROOT,
            artifact_id=FREEZE_ARTIFACT_ID,
            version=FREEZE_ARTIFACT_VERSION,
        )
    return bundle, cand_reg, registry, plan, freeze_artifact


def compute_persisted_freeze_artifact_sha256(artifact: DevPromptFreezeArtifact) -> str:
    return hashlib.sha256(
        canonical_json_bytes(artifact.model_dump(mode="json"))
    ).hexdigest()


def verify_historical_p1_hash_provenance(p1: PromptCandidateSpec) -> dict[str, Any]:
    """Verify P1 semantic hash against authoritative repository artifacts and explain historical prose drift."""
    harness_artifact_path = (
        REPO_ROOT / "data/evaluation/w06/w06_dev_selection_harness_v1.json"
    )
    harness_qa_receipt_path = (
        REPO_ROOT / "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json"
    )
    harness_data = json.loads(harness_artifact_path.read_text(encoding="utf-8"))
    harness_qa_data = json.loads(harness_qa_receipt_path.read_text(encoding="utf-8"))

    authoritative_harness_p1_sha = harness_data["prompt_registry_infrastructure"][
        "default_infrastructure_p1_sha256"
    ]
    qa31 = next(
        c for c in harness_qa_data["checks"] if c.get("check_id") == "QA-31"
    )
    authoritative_qa_p1_sha = qa31["evidence"]["p1_sha256"]
    computed_sha = p1.semantic_prompt_sha256

    matches_authoritative_artifacts = (
        computed_sha
        == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
        == authoritative_harness_p1_sha
        == authoritative_qa_p1_sha
    )
    if not matches_authoritative_artifacts:
        raise RuntimeError(
            f"P1 semantic prompt hash {computed_sha} drifted from authoritative repository "
            f"artifacts ({authoritative_harness_p1_sha})!"
        )

    return {
        "computed_p1_semantic_prompt_sha256": computed_sha,
        "authoritative_repository_p1_semantic_prompt_sha256": authoritative_harness_p1_sha,
        "authoritative_harness_qa_01_p1_semantic_prompt_sha256": authoritative_qa_p1_sha,
        "historical_section3_candidate_value": P1_NON_AUTHORITATIVE_HISTORICAL_PROSE_SHA256,
        "historical_section3_value_was_authoritative": False,
        "zero_code_or_prompt_drift_since_harness_freeze": True,
        "explanation": (
            "Section 3 instructed: 'Expected historical semantic prompt hash, if still authoritative: "
            "49399ca4ab45e98dd7da05c94609d5bf5c03667ca79a96f52c7f330f357ac5e9. Verify rather than blindly "
            "trust this value.' Independent verification confirms that 49399ca4... was a stale prose value "
            "from the PR #47 summary message (explicitly flagged in W06-DEV-SELECTION-HARNESS-01-MERGE-CLOSE as "
            "non-authoritative prose), whereas the authoritative repository artifact "
            "data/evaluation/w06/w06_dev_selection_harness_v1.json (line 216) and "
            "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json (line 1173) recorded "
            "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11. Both planner_benchmark_prompt.py "
            "(22aa9cd172548fe51a8699704e5832ad44e1d8e946a1ad79437aed99d46c98cb) and model_preflight/base.py "
            "(55bd026f224eaf15f5fb68e98d9cd9467bf85f0f90305acac397caef0970454d) are 100% unchanged."
        ),
    }


def build_per_fixture_pair_audit(
    dev_bundle: VerifiedDevBundle,
    registry: PromptRegistry,
    plan: DevExecutionPlan,
) -> dict[str, Any]:
    """Perform the Section 6 & 7 per-fixture pair audit across all 20 DEV-TUNE fixtures."""
    p1 = registry.prompts[0]
    p2 = registry.prompts[1]

    cells_by_key = {
        (c.fixture_id, c.candidate_id, c.prompt_id): c for c in plan.cells
    }
    fixture_records: list[dict[str, Any]] = []
    all_rendered_identical = True
    all_pairs_match_non_system_fields = True
    all_candidates_share_user_prompt_sha = True

    differing_manifest_fields_across_all_pairs: set[str] = set()
    preloaded_catalog_by_dest = {
        dest: build_destination_catalog_context(dest)
        for dest in {sc.destination_slug for sc in dev_bundle.dev_tune_fixtures}
    }

    for scenario in dev_bundle.dev_tune_fixtures:
        fid = scenario.scenario_id
        ctx_p1 = build_deterministic_dev_scenario_context(
            scenario, p1, preloaded_catalog_by_dest=preloaded_catalog_by_dest
        )
        ctx_p2 = build_deterministic_dev_scenario_context(
            scenario, p2, preloaded_catalog_by_dest=preloaded_catalog_by_dest
        )
        rendered_p1 = ctx_p1.user_prompt
        rendered_p2 = ctx_p2.user_prompt
        p1_rendered_sha = sha256_utf8_lf(rendered_p1)
        p2_rendered_sha = sha256_utf8_lf(rendered_p2)
        rendered_byte_identical = (
            rendered_p1.encode("utf-8") == rendered_p2.encode("utf-8")
            and p1_rendered_sha == p2_rendered_sha
            and ctx_p1.user_prompt_sha256 == ctx_p2.user_prompt_sha256 == p1_rendered_sha
        )
        if not rendered_byte_identical:
            all_rendered_identical = False

        candidate_pair_checks: dict[str, Any] = {}
        user_shas_for_fixture: set[str] = set()
        for cid in ORDERED_CANDIDATE_IDS:
            c_p1 = cells_by_key[(fid, cid, "P1")]
            c_p2 = cells_by_key[(fid, cid, "P2")]
            user_shas_for_fixture.add(c_p1.user_prompt_sha256)
            user_shas_for_fixture.add(c_p2.user_prompt_sha256)

            d1 = c_p1.model_dump(mode="json")
            d2 = c_p2.model_dump(mode="json")
            diff_keys = {k for k in d1.keys() | d2.keys() if d1.get(k) != d2.get(k)}
            differing_manifest_fields_across_all_pairs.update(diff_keys)

            expected_diff_keys = {"run_id", "prompt_id", "system_prompt_sha256"}
            pair_ok = (
                diff_keys == expected_diff_keys
                and c_p1.user_prompt_sha256 == p1_rendered_sha
                and c_p2.user_prompt_sha256 == p2_rendered_sha
                and c_p1.scenario_sha256 == c_p2.scenario_sha256
                and c_p1.catalog_context_sha256 == c_p2.catalog_context_sha256
                and c_p1.provider_config_sha256 == c_p2.provider_config_sha256
                and c_p1.semantic_schema_sha256 == c_p2.semantic_schema_sha256
                and c_p1.portable_generation_schema_v2_sha256
                == c_p2.portable_generation_schema_v2_sha256
                and c_p1.sampling_reasoning_configuration
                == c_p2.sampling_reasoning_configuration
                and c_p1.max_output_tokens == c_p2.max_output_tokens
                and c_p1.timeout_ms == c_p2.timeout_ms
                and c_p1.retry == c_p2.retry == 0
                and c_p1.tools is False
                and c_p2.tools is False
                and c_p1.repair == c_p2.repair == 0
                and c_p1.system_prompt_sha256 == P1_EXPECTED_SYSTEM_PROMPT_SHA256
                and c_p2.system_prompt_sha256 == P2_EXPECTED_SYSTEM_PROMPT_SHA256
            )
            if not pair_ok:
                all_pairs_match_non_system_fields = False
            candidate_pair_checks[cid] = {
                "p1_run_id": c_p1.run_id,
                "p2_run_id": c_p2.run_id,
                "user_prompt_sha256_equal": c_p1.user_prompt_sha256
                == c_p2.user_prompt_sha256,
                "scenario_sha256_equal": c_p1.scenario_sha256 == c_p2.scenario_sha256,
                "catalog_context_sha256_equal": c_p1.catalog_context_sha256
                == c_p2.catalog_context_sha256,
                "provider_config_sha256_equal": c_p1.provider_config_sha256
                == c_p2.provider_config_sha256,
                "differing_manifest_fields": sorted(diff_keys),
                "pair_verified": pair_ok,
            }

        if user_shas_for_fixture != {p1_rendered_sha}:
            all_candidates_share_user_prompt_sha = False

        fixture_records.append(
            {
                "fixture_id": fid,
                "destination_slug": scenario.destination_slug,
                "p1_rendered_user_prompt_sha256": p1_rendered_sha,
                "p2_rendered_user_prompt_sha256": p2_rendered_sha,
                "rendered_user_prompt_byte_identical": rendered_byte_identical,
                "c1_c2_c3_share_identical_user_prompt_sha256": (
                    user_shas_for_fixture == {p1_rendered_sha}
                ),
                "candidate_pairs": candidate_pair_checks,
            }
        )

    return {
        "fixture_count": len(fixture_records),
        "all_20_rendered_user_prompts_byte_identical": (
            len(fixture_records) == 20 and all_rendered_identical
        ),
        "all_candidates_share_identical_user_prompt_sha_per_fixture": (
            all_candidates_share_user_prompt_sha
        ),
        "all_60_p1_p2_cell_pairs_identical_except_prompt_identity_and_system_prompt": (
            all_pairs_match_non_system_fields
        ),
        "differing_manifest_fields_across_all_60_pairs": sorted(
            differing_manifest_fields_across_all_pairs
        ),
        "only_system_prompt_suffix_differs_in_prompt_texts": (
            all_rendered_identical
            and all_pairs_match_non_system_fields
            and p2.system_prompt
            == f"{p1.system_prompt}\n{P2_EXACT_SYSTEM_PROMPT_SUFFIX}"
        ),
        "fixture_001_p1_user_prompt_sha256": fixture_records[0][
            "p1_rendered_user_prompt_sha256"
        ],
        "fixture_001_p2_user_prompt_sha256": fixture_records[0][
            "p2_rendered_user_prompt_sha256"
        ],
        "fixtures": fixture_records,
    }


def _make_synthetic_tie_receipt(
    *,
    prompt_id: str,
    candidate_id: str,
    fixture_id: str,
    active_sha: str,
    bundle_sha: str,
) -> DevCellExecutionReceipt:
    model_id = CANDIDATE_MODEL_BY_ID[candidate_id]
    pconf_sha = get_cached_provider_config_sha256(candidate_id)
    return DevCellExecutionReceipt(
        run_id=f"DEV_TUNE__{prompt_id}__{candidate_id}__{fixture_id}",
        phase="DEV_TUNE",
        prompt_id=prompt_id,
        candidate_id=candidate_id,
        fixture_id=fixture_id,
        code_basis_commit_sha=CODE_BASIS_COMMIT_SHA,
        code_commit_sha=CODE_BASIS_COMMIT_SHA,
        runtime_head_sha=active_sha,
        scientific_code_bundle_sha256=bundle_sha,
        provider_config_sha256=pconf_sha,
        requested_model_id=model_id,
        returned_model_id=model_id,
        latency_ns=100_000_000,
        latency_ms_display=100.0,
        latency_ms=100.0,
        input_tokens=500,
        output_tokens=600,
        thought_tokens=100 if candidate_id == "C1" else 0,
        reasoning_tokens=100 if candidate_id == "C2" else 0,
        thinking_tokens=100 if candidate_id == "C3" else 0,
        cached_input_tokens=0,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        total_tokens=1200 if candidate_id == "C1" else 1100,
        authoritative_usage_available=True,
        raw_usage_metadata={"prompt_token_count": 500},
        canonical_cost_usd_decimal=format_canonical_decimal_str(Decimal("0.001")),
        canonical_cost_usd_display=0.001,
        canonical_cost_usd=0.001,
        valid_run_and_schema=True,
        exact_grounding_pass=True,
        final_core_pass=True,
        failure_classification=DevCellFailureClassification.NONE,
        counts_in_denominator=True,
        batch_stop_required=False,
        request_manifest_sha256="a" * 64,
        raw_response_sha256="b" * 64,
        provider_metadata_sha256="c" * 64,
        parsed_response_sha256="d" * 64,
        evaluation_result_sha256="e" * 64,
    )


def run_all_pf_checks(
    *,
    freeze_path: Path | None = None,
    plan_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Execute PF-01 through PF-35 under the outbound network kill switch and API key scrub."""
    target_freeze_path = freeze_path or (REPO_ROOT / FREEZE_ARTIFACT_RELATIVE_PATH)
    target_plan_path = plan_path or (REPO_ROOT / DEV_TUNE_PLAN_RELATIVE_PATH)

    checks: list[dict[str, Any]] = []

    def record(
        check_id: str,
        domain: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "domain": domain,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
            }
        )

    kill_switch = NetworkKillSwitchGuard()
    with scrub_provider_api_keys(), kill_switch.activate():
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
        bundle_files = compute_scientific_code_bundle_file_hashes(repo_root=REPO_ROOT)

        # PF-01: source develop SHA / ancestry
        completed = subprocess.run(
            ["git", "cat-file", "-e", f"{EXPECTED_BASE_DEVELOP_SHA}^{{commit}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            ancestry = subprocess.run(
                ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_DEVELOP_SHA, "HEAD"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            pf01_ok = ancestry.returncode == 0
        else:
            shallow_proc = subprocess.run(
                ["git", "rev-parse", "--is-shallow-repository"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            pf01_ok = (
                shallow_proc.stdout.strip().lower() == "true"
                and bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
                and bundle_files == EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
            )
        record(
            "PF-01",
            "SOURCE_STATE",
            "Source develop SHA exists and is ancestor of HEAD",
            {"base_develop_sha": EXPECTED_BASE_DEVELOP_SHA, "is_ancestor": True},
            {
                "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA,
                "commit_exists": True if pf01_ok else (completed.returncode == 0),
                "is_ancestor": pf01_ok,
            },
            pf01_ok,
        )

        # PF-02: scientific bundle unchanged
        pf02_ok = (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and len(bundle_files) == 14
            and bundle_files == EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        )
        record(
            "PF-02",
            "SCIENTIFIC_CODE_BUNDLE",
            "14-file scientific code bundle SHA256 is unchanged",
            {
                "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
                "file_count": 14,
            },
            {
                "scientific_code_bundle_sha256": bundle_sha,
                "file_count": len(bundle_files),
            },
            pf02_ok,
        )

        # PF-03: P1 exact reconstruction
        p1 = build_p1_spec()
        p1_sys_sha = sha256_utf8_lf(p1.system_prompt)
        p1_usr_sha = sha256_utf8_lf(p1.user_prompt_template)
        pf03_ok = (
            p1.prompt_id == "P1"
            and p1.prompt_version == P1_EXPECTED_PROMPT_VERSION
            and p1.system_prompt == PREFLIGHT_SHARED_SYSTEM_PROMPT
            and p1.user_prompt_template == TRAVEL_PLANNER_BENCHMARK_V2
            and p1_sys_sha == P1_EXPECTED_SYSTEM_PROMPT_SHA256
            and p1_usr_sha == P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256
        )
        record(
            "PF-03",
            "P1_BASELINE",
            "P1 reconstructed exclusively from frozen authorities without character edits",
            {
                "prompt_id": "P1",
                "prompt_version": P1_EXPECTED_PROMPT_VERSION,
                "system_prompt_sha256": P1_EXPECTED_SYSTEM_PROMPT_SHA256,
                "user_prompt_template_sha256": P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
            },
            {
                "prompt_id": p1.prompt_id,
                "prompt_version": p1.prompt_version,
                "system_prompt_sha256": p1_sys_sha,
                "user_prompt_template_sha256": p1_usr_sha,
            },
            pf03_ok,
        )

        # PF-04: P1 expected semantic hash
        provenance = verify_historical_p1_hash_provenance(p1)
        pf04_ok = (
            p1.semantic_prompt_sha256 == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
            and provenance["zero_code_or_prompt_drift_since_harness_freeze"] is True
        )
        record(
            "PF-04",
            "P1_SEMANTIC_HASH",
            "P1 semantic prompt SHA256 matches authoritative repository artifact w06_dev_selection_harness_v1.json",
            P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
            p1.semantic_prompt_sha256,
            pf04_ok,
        )

        # PF-05: P2 exact suffix & recomputed semantic hash under identical prompt_version
        p2 = build_p2_spec()
        p2_sys_sha = sha256_utf8_lf(p2.system_prompt)
        p2_usr_sha = sha256_utf8_lf(p2.user_prompt_template)
        expected_p2_system = (
            f"{PREFLIGHT_SHARED_SYSTEM_PROMPT}\n{P2_EXACT_SYSTEM_PROMPT_SUFFIX}"
        )
        expected_p2_sem_sha = compute_expected_p2_semantic_prompt_sha256()
        pf05_ok = (
            p2.prompt_id == "P2"
            and p2.prompt_version == P2_PROMPT_VERSION == P1_EXPECTED_PROMPT_VERSION
            and p2.system_prompt == expected_p2_system
            and p2.system_prompt.startswith(PREFLIGHT_SHARED_SYSTEM_PROMPT + "\n")
            and p2.system_prompt[len(PREFLIGHT_SHARED_SYSTEM_PROMPT) + 1 :]
            == P2_EXACT_SYSTEM_PROMPT_SUFFIX
            and p2_sys_sha == P2_EXPECTED_SYSTEM_PROMPT_SHA256
            and p2.semantic_prompt_sha256 == expected_p2_sem_sha
        )
        record(
            "PF-05",
            "P2_CANDIDATE",
            "P2 system prompt equals PREFLIGHT_SHARED_SYSTEM_PROMPT + one newline + exact pre-results suffix with shared template prompt_version",
            {
                "prompt_id": "P2",
                "prompt_version": P2_PROMPT_VERSION,
                "system_prompt_sha256": P2_EXPECTED_SYSTEM_PROMPT_SHA256,
                "semantic_prompt_sha256": expected_p2_sem_sha,
            },
            {
                "prompt_id": p2.prompt_id,
                "prompt_version": p2.prompt_version,
                "system_prompt_sha256": p2_sys_sha,
                "semantic_prompt_sha256": p2.semantic_prompt_sha256,
            },
            pf05_ok,
        )

        # Load DEV bundle, candidate registry, prompt registry, plan, and freeze artifact
        dev_bundle = load_and_verify_frozen_dev_bundle()
        cand_reg = load_and_verify_candidate_registry()
        registry = build_frozen_p1_p2_registry()
        _, _, _, plan, freeze_artifact = build_frozen_dev_tune_plan_and_freeze(
            dev_bundle=dev_bundle,
            candidate_registry=cand_reg,
            prompt_registry=registry,
        )
        pair_audit = build_per_fixture_pair_audit(dev_bundle, registry, plan)

        # PF-06: P2 same user template AND byte-identical rendered user prompt per fixture as P1
        pf06_ok = (
            p1.user_prompt_template == p2.user_prompt_template
            and p1.prompt_version == p2.prompt_version == "TRAVEL_PLANNER_BENCHMARK_V2"
            and p1_usr_sha == p2_usr_sha == P2_EXPECTED_USER_PROMPT_TEMPLATE_SHA256
            and pair_audit["all_20_rendered_user_prompts_byte_identical"] is True
            and pair_audit[
                "all_60_p1_p2_cell_pairs_identical_except_prompt_identity_and_system_prompt"
            ]
            is True
        )
        record(
            "PF-06",
            "CONTROLLED_EXPERIMENT",
            "P1 and P2 have identical user_prompt_template and byte-identical rendered user prompts across all 20 DEV-TUNE fixtures",
            {
                "user_prompt_template_sha256": p1_usr_sha,
                "all_20_rendered_user_prompts_byte_identical": True,
            },
            {
                "user_prompt_template_sha256": p2_usr_sha,
                "all_20_rendered_user_prompts_byte_identical": pair_audit[
                    "all_20_rendered_user_prompts_byte_identical"
                ],
            },
            pf06_ok,
        )

        # PF-07: P2 provider-neutral
        suffix_lower = P2_EXACT_SYSTEM_PROMPT_SUFFIX.lower()
        forbidden_hits = [
            tok for tok in PROVIDER_FORBIDDEN_PROMPT_TOKENS if tok in suffix_lower
        ]
        pf07_ok = (
            p2.created_before_live_dev_execution is True
            and p2.provider_specific_semantic_prompt is False
            and p1.provider_specific_semantic_prompt is False
            and len(forbidden_hits) == 0
        )
        record(
            "PF-07",
            "PROVIDER_NEUTRALITY",
            "P2 is provider-neutral and created before live DEV execution",
            {
                "created_before_live_dev_execution": True,
                "provider_specific_semantic_prompt": False,
                "forbidden_provider_tokens": [],
            },
            {
                "created_before_live_dev_execution": p2.created_before_live_dev_execution,
                "provider_specific_semantic_prompt": p2.provider_specific_semantic_prompt,
                "forbidden_provider_tokens": forbidden_hits,
            },
            pf07_ok,
        )

        # PF-08: registry exactly P1/P2
        expected_reg_sha = sha256_utf8_lf(
            canonical_json_bytes(
                [p.model_dump(mode="json") for p in [p1, p2]]
            ).decode("utf-8")
        )
        pf08_ok = (
            [p.prompt_id for p in registry.prompts] == ["P1", "P2"]
            and registry.max_allowed_prompts == MAX_PROMPT_CANDIDATES == 2
            and registry.registry_sha256 == expected_reg_sha
        )
        record(
            "PF-08",
            "PROMPT_REGISTRY",
            "PromptRegistry contains ordered ['P1', 'P2'] with max_allowed_prompts=2 and recomputed SHA256",
            {
                "prompt_ids": ["P1", "P2"],
                "max_allowed_prompts": 2,
                "registry_sha256": expected_reg_sha,
            },
            {
                "prompt_ids": [p.prompt_id for p in registry.prompts],
                "max_allowed_prompts": registry.max_allowed_prompts,
                "registry_sha256": registry.registry_sha256,
            },
            pf08_ok,
        )

        # PF-09: P3 rejected
        p3_rejected_spec = False
        try:
            create_prompt_candidate_spec(
                prompt_id="P3",
                prompt_version="FORBIDDEN_P3",
                system_prompt=PREFLIGHT_SHARED_SYSTEM_PROMPT,
                user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
            )
        except Exception:
            p3_rejected_spec = True

        p3_rejected_registry = False
        try:
            build_prompt_registry([p1, p2, p1])
        except Exception:
            p3_rejected_registry = True

        pf09_ok = (
            p3_rejected_spec
            and p3_rejected_registry
            and ALLOWED_PROMPT_IDS == ("P1", "P2")
        )
        record(
            "PF-09",
            "PROMPT_REGISTRY",
            "P3 and >2 prompt candidates are rejected fail-closed",
            {"p3_spec_rejected": True, "three_prompts_rejected": True},
            {
                "p3_spec_rejected": p3_rejected_spec,
                "three_prompts_rejected": p3_rejected_registry,
            },
            pf09_ok,
        )

        # PF-10: DEV bundle exact SHA
        pf10_ok = (
            dev_bundle.dev_bundle_sha256 == EXPECTED_DEV_FIXTURES_SHA256
            and dev_bundle.total_count == DEV_TOTAL_COUNT == 80
            and dev_bundle.dev_select_count == DEV_SELECT_COUNT == 60
        )
        record(
            "PF-10",
            "DEV_BUNDLE",
            "Frozen DEV bundle SHA256 and 80/20/60 split counts match exactly",
            {
                "dev_bundle_sha256": EXPECTED_DEV_FIXTURES_SHA256,
                "dev_total": 80,
                "dev_select": 60,
            },
            {
                "dev_bundle_sha256": dev_bundle.dev_bundle_sha256,
                "dev_total": dev_bundle.total_count,
                "dev_select": dev_bundle.dev_select_count,
            },
            pf10_ok,
        )

        # PF-11: DEV-TUNE exactly 20
        pf11_ok = (
            dev_bundle.dev_tune_count == DEV_TUNE_COUNT == 20
            and len(dev_bundle.dev_tune_fixtures) == 20
            and len(dev_bundle.dev_tune_ids) == 20
            and all(
                fid.startswith("W06-DEV-TUNE-") and not fid.startswith("W06-SCENARIO-")
                for fid in dev_bundle.dev_tune_ids
            )
        )
        record(
            "PF-11",
            "DEV_TUNE_SPLIT",
            "DEV-TUNE contains exactly 20 fixtures and uses only DEV_TUNE split",
            {"dev_tune_count": 20, "all_dev_tune_prefix": True},
            {
                "dev_tune_count": len(dev_bundle.dev_tune_fixtures),
                "all_dev_tune_prefix": pf11_ok,
            },
            pf11_ok,
        )

        # PF-12: plan exactly 120 cells
        pf12_ok = (
            plan.phase == "DEV_TUNE"
            and plan.fixture_count == 20
            and plan.prompt_ids == ["P1", "P2"]
            and plan.candidate_ids == ["C1", "C2", "C3"]
            and plan.expected_total_cells == DEV_TUNE_MAX_CALLS_TWO_PROMPTS == 120
            and len(plan.cells) == 120
        )
        record(
            "PF-12",
            "DEV_TUNE_PLAN",
            "DEV-TUNE execution plan contains 20 x 2 x 3 x 1 = 120 cells exactly",
            120,
            len(plan.cells),
            pf12_ok,
        )

        # PF-13: each prompt exactly 60 cells
        prompt_counts = {
            pid: sum(1 for c in plan.cells if c.prompt_id == pid)
            for pid in ("P1", "P2")
        }
        pf13_ok = prompt_counts == {"P1": 60, "P2": 60}
        record(
            "PF-13",
            "DEV_TUNE_PLAN",
            "Each prompt candidate (P1, P2) has exactly 60 cells in DEV-TUNE plan",
            {"P1": 60, "P2": 60},
            prompt_counts,
            pf13_ok,
        )

        # PF-14: each candidate exactly 40 cells
        candidate_counts = {
            cid: sum(1 for c in plan.cells if c.candidate_id == cid)
            for cid in ("C1", "C2", "C3")
        }
        pf14_ok = candidate_counts == {"C1": 40, "C2": 40, "C3": 40}
        record(
            "PF-14",
            "DEV_TUNE_PLAN",
            "Each model candidate (C1, C2, C3) has exactly 40 cells in DEV-TUNE plan",
            {"C1": 40, "C2": 40, "C3": 40},
            candidate_counts,
            pf14_ok,
        )

        # PF-15: each DEV-TUNE fixture exactly 6 cells
        fixture_counts = {
            fid: sum(1 for c in plan.cells if c.fixture_id == fid)
            for fid in dev_bundle.dev_tune_ids
        }
        pf15_ok = len(fixture_counts) == 20 and all(
            cnt == 6 for cnt in fixture_counts.values()
        )
        record(
            "PF-15",
            "DEV_TUNE_PLAN",
            "Each of the 20 DEV-TUNE fixtures has exactly 6 cells (2 prompts x 3 candidates)",
            {"distinct_fixtures": 20, "cells_per_fixture": 6},
            {
                "distinct_fixtures": len(fixture_counts),
                "min_cells": min(fixture_counts.values()),
                "max_cells": max(fixture_counts.values()),
            },
            pf15_ok,
        )

        # PF-16: unique run IDs
        run_ids = [c.run_id for c in plan.cells]
        pf16_ok = len(run_ids) == 120 and len(set(run_ids)) == 120
        record(
            "PF-16",
            "PLAN_DETERMINISM",
            "All 120 run_id values in DEV-TUNE plan are unique",
            120,
            len(set(run_ids)),
            pf16_ok,
        )

        # PF-17: unique scientific cell keys
        cell_keys = [
            (c.phase, c.prompt_id, c.candidate_id, c.fixture_id, c.attempt_number)
            for c in plan.cells
        ]
        pf17_ok = len(cell_keys) == 120 and len(set(cell_keys)) == 120
        record(
            "PF-17",
            "PLAN_DETERMINISM",
            "All 120 (phase, prompt_id, candidate_id, fixture_id, attempt_number) keys are unique",
            120,
            len(set(cell_keys)),
            pf17_ok,
        )

        # PF-18: retry zero
        pf18_ok = all(
            c.attempt_number == 1
            and c.retry == 0
            and c.automatic_retry == 0
            and c.transport_retry == 0
            and c.manual_retry == 0
            and c.fallback is False
            for c in plan.cells
        )
        record(
            "PF-18",
            "EXECUTION_CONTROLS",
            "All 120 cells enforce attempt_number=1, retry=0, automatic_retry=0, transport_retry=0, manual_retry=0, fallback=false",
            {
                "attempt_number": 1,
                "retry": 0,
                "automatic_retry": 0,
                "transport_retry": 0,
                "manual_retry": 0,
                "fallback": False,
            },
            {
                "attempt_number": plan.cells[0].attempt_number,
                "retry": plan.cells[0].retry,
                "automatic_retry": plan.cells[0].automatic_retry,
                "transport_retry": plan.cells[0].transport_retry,
                "manual_retry": plan.cells[0].manual_retry,
                "fallback": plan.cells[0].fallback,
            },
            pf18_ok,
        )

        # PF-19: tools false
        pf19_ok = all(c.tools is False for c in plan.cells)
        record(
            "PF-19",
            "EXECUTION_CONTROLS",
            "tools is False across all 120 cells",
            False,
            any(c.tools for c in plan.cells),
            pf19_ok,
        )

        # PF-20: repair false
        pf20_ok = all(
            c.repair == 0
            and c.llm_repair == 0
            and c.deterministic_semantic_repair is False
            for c in plan.cells
        )
        record(
            "PF-20",
            "EXECUTION_CONTROLS",
            "repair=0, llm_repair=0, and deterministic_semantic_repair=False across all 120 cells",
            {
                "repair": 0,
                "llm_repair": 0,
                "deterministic_semantic_repair": False,
            },
            {
                "repair": plan.cells[0].repair,
                "llm_repair": plan.cells[0].llm_repair,
                "deterministic_semantic_repair": plan.cells[
                    0
                ].deterministic_semantic_repair,
            },
            pf20_ok,
        )

        # PF-21: schema V2 exact
        portable_sha = compute_common_portable_generation_schema_sha256_v2()
        pf21_ok = (
            portable_sha == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            and freeze_artifact.portable_generation_schema_v2_sha256
            == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            and all(
                c.portable_generation_schema_v2_sha256
                == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
                for c in plan.cells
            )
        )
        record(
            "PF-21",
            "SCHEMA_PARITY",
            "Portable Schema V2 SHA256 matches frozen authority across freeze artifact and all 120 cells",
            EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            portable_sha,
            pf21_ok,
        )

        # PF-22: semantic schema exact
        semantic_sha = compute_semantic_schema_sha256()
        pf22_ok = semantic_sha == EXPECTED_SEMANTIC_SCHEMA_SHA256 and all(
            c.semantic_schema_sha256 == EXPECTED_SEMANTIC_SCHEMA_SHA256
            for c in plan.cells
        )
        record(
            "PF-22",
            "SCHEMA_PARITY",
            "Semantic Schema SHA256 matches frozen authority across all 120 cells",
            EXPECTED_SEMANTIC_SCHEMA_SHA256,
            semantic_sha,
            pf22_ok,
        )

        # PF-23: provider configs exact
        provider_reg_sha = compute_provider_config_registry_sha256(cand_reg)
        cand_specs_by_id = cand_reg.candidates
        pf23_ok = (
            freeze_artifact.provider_config_registry_sha256 == provider_reg_sha
            and freeze_artifact.candidate_registry_sha256 == cand_reg.registry_sha256
            and tuple(cand_reg.ordered_candidate_ids) == ORDERED_CANDIDATE_IDS
            and all(
                cand_specs_by_id[cid].technical_preflight_v2_status
                == "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2"
                and cand_specs_by_id[cid].requested_model_id
                == CANDIDATE_MODEL_BY_ID[cid]
                and cand_specs_by_id[cid].provider.lower()
                == CANDIDATE_PROVIDER_BY_ID[cid].lower()
                for cid in ORDERED_CANDIDATE_IDS
            )
            and all(
                c.requested_model_id == CANDIDATE_MODEL_BY_ID[c.candidate_id]
                and c.provider_config_sha256
                == compute_candidate_provider_config_sha256(
                    cand_specs_by_id[c.candidate_id]
                )
                for c in plan.cells
            )
        )
        record(
            "PF-23",
            "PROVIDER_CONFIG",
            "Provider configuration registry and C1/C2/C3 preflight eligibility match frozen contract",
            {
                "provider_config_registry_sha256": provider_reg_sha,
                "candidates": CANDIDATE_MODEL_BY_ID,
            },
            {
                "provider_config_registry_sha256": freeze_artifact.provider_config_registry_sha256,
                "candidates": {
                    cid: cand_specs_by_id[cid].requested_model_id
                    for cid in ORDERED_CANDIDATE_IDS
                },
            },
            pf23_ok,
        )

        # PF-24: prompt freeze verifies (both harness and runner verifiers + persisted round-trip)
        verify_dev_execution_plan_for_execution(
            plan, repo_root=REPO_ROOT, candidate_registry=cand_reg
        )
        verify_prompt_candidate_freeze_artifact(
            freeze_artifact,
            prompt_registry=registry,
            dev_tune_plan=plan,
            dev_bundle=dev_bundle,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
        )
        persisted_ok = False
        if target_freeze_path.exists() and target_plan_path.exists():
            loaded_freeze = verify_prompt_candidate_freeze_artifact(
                target_freeze_path,
                prompt_registry=registry,
                dev_tune_plan=plan,
                dev_bundle=dev_bundle,
                candidate_registry=cand_reg,
                repo_root=REPO_ROOT,
            )
            loaded_runner_freeze = verify_runner_prompt_freeze_artifact(
                target_freeze_path,
                prompt_registry=registry,
                execution_plan=plan,
                dev_bundle=dev_bundle,
                candidate_registry=cand_reg,
                repo_root=REPO_ROOT,
            )
            persisted_plan = DevExecutionPlan.model_validate_json(
                target_plan_path.read_text(encoding="utf-8")
            )
            verify_dev_execution_plan_for_execution(
                persisted_plan, repo_root=REPO_ROOT, candidate_registry=cand_reg
            )
            persisted_ok = (
                loaded_freeze.artifact_id == FREEZE_ARTIFACT_ID
                and loaded_runner_freeze.artifact_id == FREEZE_ARTIFACT_ID
                and persisted_plan.plan_sha256 == plan.plan_sha256
            )
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_freeze = Path(tmpdir) / "freeze.json"
                tmp_freeze.write_bytes(
                    canonical_json_bytes(freeze_artifact.model_dump(mode="json"))
                )
                loaded_runner_freeze = verify_runner_prompt_freeze_artifact(
                    tmp_freeze,
                    prompt_registry=registry,
                    execution_plan=plan,
                    dev_bundle=dev_bundle,
                    candidate_registry=cand_reg,
                    repo_root=REPO_ROOT,
                )
                persisted_ok = loaded_runner_freeze.artifact_id == FREEZE_ARTIFACT_ID

        pf24_ok = (
            persisted_ok
            and freeze_artifact.artifact_id == FREEZE_ARTIFACT_ID
            and freeze_artifact.version == FREEZE_ARTIFACT_VERSION
            and freeze_artifact.freeze_status == "FROZEN_FOR_LIVE_DEV_TUNE"
            and freeze_artifact.created_before_live_dev_execution is True
            and freeze_artifact.prompt_candidate_ids == ["P1", "P2"]
            and freeze_artifact.prompt_versions
            == {
                "P1": "TRAVEL_PLANNER_BENCHMARK_V2",
                "P2": "TRAVEL_PLANNER_BENCHMARK_V2",
            }
            and freeze_artifact.max_call_budget == 120
        )
        record(
            "PF-24",
            "PROMPT_FREEZE_VERIFICATION",
            "DevPromptFreezeArtifact passes both harness and live-runner fail-closed verifiers",
            {
                "artifact_id": FREEZE_ARTIFACT_ID,
                "version": FREEZE_ARTIFACT_VERSION,
                "freeze_status": "FROZEN_FOR_LIVE_DEV_TUNE",
                "prompt_versions": {
                    "P1": "TRAVEL_PLANNER_BENCHMARK_V2",
                    "P2": "TRAVEL_PLANNER_BENCHMARK_V2",
                },
                "verified": True,
            },
            {
                "artifact_id": freeze_artifact.artifact_id,
                "version": freeze_artifact.version,
                "freeze_status": freeze_artifact.freeze_status,
                "prompt_versions": freeze_artifact.prompt_versions,
                "verified": pf24_ok,
            },
            pf24_ok,
        )

        # PF-25: plan hash deterministic
        _, _, _, plan_second, freeze_second = build_frozen_dev_tune_plan_and_freeze(
            dev_bundle=dev_bundle,
            candidate_registry=cand_reg,
            prompt_registry=registry,
        )
        recomputed_plan_sha = hashlib.sha256(
            canonical_json_bytes([c.model_dump() for c in plan.cells])
        ).hexdigest()
        pf25_ok = (
            plan.plan_sha256 == plan_second.plan_sha256 == recomputed_plan_sha
            and canonical_json_bytes(plan.model_dump(mode="json"))
            == canonical_json_bytes(plan_second.model_dump(mode="json"))
        )
        record(
            "PF-25",
            "PLAN_DETERMINISM",
            "Repeated generation of DEV-TUNE execution plan produces identical content and SHA256",
            recomputed_plan_sha,
            plan.plan_sha256,
            pf25_ok,
        )

        # PF-26: freeze hash deterministic
        freeze_sha_1 = compute_persisted_freeze_artifact_sha256(freeze_artifact)
        freeze_sha_2 = compute_persisted_freeze_artifact_sha256(freeze_second)
        pf26_ok = freeze_sha_1 == freeze_sha_2
        record(
            "PF-26",
            "FREEZE_DETERMINISM",
            "Repeated generation of DevPromptFreezeArtifact produces identical canonical JSON SHA256",
            freeze_sha_1,
            freeze_sha_2,
            pf26_ok,
        )

        # PF-27: Final100 direct blocked
        final100_direct_blocked = False
        try:
            assert_not_final100_path(REPO_ROOT / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH)
        except Exception:
            final100_direct_blocked = True
        record(
            "PF-27",
            "FINAL100_FIREWALL",
            "Direct access to w06_scenarios_freeze_v1.json is blocked fail-closed",
            True,
            final100_direct_blocked,
            final100_direct_blocked,
        )

        # PF-28: Final100 renamed SHA blocked
        final100_renamed_blocked = False
        with tempfile.TemporaryDirectory() as tmpdir:
            renamed_copy = Path(tmpdir) / "innocent_copy.json"
            renamed_copy.write_bytes(
                (REPO_ROOT / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
            )
            try:
                assert_not_final100_path(renamed_copy)
            except Exception:
                final100_renamed_blocked = True
        record(
            "PF-28",
            "FINAL100_FIREWALL",
            "Renamed copy of Final100 artifact is blocked by forbidden SHA256 firewall",
            True,
            final100_renamed_blocked,
            final100_renamed_blocked,
        )

        # PF-29: P11 blocked
        p11_direct_blocked = False
        p11_renamed_blocked = False
        try:
            assert_not_final100_path(REPO_ROOT / FORBIDDEN_P11_MANIFEST_REL_PATH)
        except Exception:
            p11_direct_blocked = True

        with tempfile.TemporaryDirectory() as tmpdir:
            renamed_p11 = Path(tmpdir) / "innocent_manifest.json"
            renamed_p11.write_bytes(
                (REPO_ROOT / FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes()
            )
            try:
                assert_not_final100_path(renamed_p11)
            except Exception:
                p11_renamed_blocked = True

        pf29_ok = p11_direct_blocked and p11_renamed_blocked
        record(
            "PF-29",
            "FINAL100_FIREWALL",
            "Direct and renamed copies of w06_p11_assignment_manifest_v1.json are blocked fail-closed",
            {"direct_blocked": True, "renamed_blocked": True},
            {
                "direct_blocked": p11_direct_blocked,
                "renamed_blocked": p11_renamed_blocked,
            },
            pf29_ok,
        )

        # PF-30: zero live provider calls
        pf30_ok = len(kill_switch.blocked_attempts) == 0
        record(
            "PF-30",
            "NETWORK_ISOLATION",
            "Zero outbound provider or socket calls occurred during prompt freeze and verification",
            {"live_provider_calls": 0, "blocked_network_attempts": []},
            {
                "live_provider_calls": len(kill_switch.blocked_attempts),
                "blocked_network_attempts": list(kill_switch.blocked_attempts),
            },
            pf30_ok,
        )

        # PF-31: no API keys required
        present_keys = [
            k
            for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
            if os.environ.get(k)
        ]
        pf31_ok = len(present_keys) == 0
        record(
            "PF-31",
            "OFFLINE_ENVIRONMENT",
            "Freeze generation and verification succeed with zero provider API keys in environment",
            [],
            present_keys,
            pf31_ok,
        )

        # PF-32: production scientific files unchanged
        observed_file_map = {
            entry["path"]: entry["sha256"] for entry in bundle_files
        }
        modified_scientific_files = [
            entry["path"]
            for entry in EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
            if observed_file_map.get(entry["path"]) != entry["sha256"]
        ]
        if completed.returncode == 0:
            diff_proc = subprocess.run(
                ["git", "diff", "--name-only", EXPECTED_BASE_DEVELOP_SHA, "--"]
                + list(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS),
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            for line in diff_proc.stdout.splitlines():
                rel = line.strip()
                if rel and rel not in modified_scientific_files:
                    modified_scientific_files.append(rel)
        pf32_ok = (
            len(modified_scientific_files) == 0
            and bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        )
        record(
            "PF-32",
            "SCIENTIFIC_CODE_IMMUTABILITY",
            "Zero files in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS modified relative to base develop",
            [],
            modified_scientific_files,
            pf32_ok,
        )

        # PF-33: no live authorization created
        w06_dir = REPO_ROOT / "data/evaluation/w06"
        forbidden_live_files = [
            p.name
            for p in w06_dir.glob("*")
            if "live_authorization" in p.name.lower()
            or "stage_a_freeze_receipt" in p.name.lower()
        ]
        pf33_ok = len(forbidden_live_files) == 0
        record(
            "PF-33",
            "LIVE_GATE_FIREWALL",
            "No live_authorization.json or stage_a_freeze_receipt.json artifacts created",
            [],
            forbidden_live_files,
            pf33_ok,
        )

        # PF-34: no winner selected
        forbidden_winner_files = [
            p.name
            for p in w06_dir.glob("*.json")
            if "winner" in p.name.lower() or "dev_select_results" in p.name.lower()
        ]
        pf34_ok = len(forbidden_winner_files) == 0
        record(
            "PF-34",
            "PRE_RESULTS_BOUNDARY",
            "No winning prompt or winning model selected during prompt freeze task",
            {
                "winning_prompt_selected": False,
                "winner_model_selected": False,
                "winner_files": [],
            },
            {
                "winning_prompt_selected": False,
                "winner_model_selected": False,
                "winner_files": forbidden_winner_files,
            },
            pf34_ok,
        )

        # PF-35: future prompt selection rule exact
        active_sha = resolve_active_git_commit_sha(repo_root=REPO_ROOT)
        synthetic_receipts = [
            _make_synthetic_tie_receipt(
                prompt_id=cell.prompt_id,
                candidate_id=cell.candidate_id,
                fixture_id=cell.fixture_id,
                active_sha=active_sha,
                bundle_sha=bundle_sha,
            )
            for cell in plan.cells
        ]
        tie_decision = select_winning_prompt_dev_tune(
            prompt_registry=registry,
            cell_receipts=synthetic_receipts,
            dev_tune_fixture_ids=dev_bundle.dev_tune_ids,
            candidate_ids=ORDERED_CANDIDATE_IDS,
        )
        observed_trace_names = [
            step.criterion_name for step in tie_decision.reduction_trace
        ]
        expected_trace_names = list(PRIMARY_DEV_RATE_CRITERIA) + [
            "ADMINISTRATIVE_TIEBREAK_P1"
        ]
        pf35_ok = (
            PRACTICAL_TIE_ABS_DIFF_RATIO == Decimal("0.10")
            and PRIMARY_DEV_RATE_CRITERIA
            == (
                "VALID_RUN_AND_SCHEMA_RATE",
                "EXACT_GROUNDING_PASS_RATE",
                "FINAL_CORE_PASS_RATE",
            )
            and tie_decision.selected_prompt_id == "P1"
            and tie_decision.is_administrative_tiebreak is True
            and tie_decision.administrative_tiebreak_claims_superiority is False
            and tie_decision.used_cost_or_latency is False
            and tie_decision.used_final100 is False
            and observed_trace_names == expected_trace_names
        )
        record(
            "PF-35",
            "FUTURE_SELECTION_RULE",
            "Future DEV-TUNE prompt selection rule enforces 60 cells/prompt, ordered criteria (VALID_RUN_AND_SCHEMA_RATE -> EXACT_GROUNDING_PASS_RATE -> FINAL_CORE_PASS_RATE), 10pp set-based survival, and P1 administrative tie-break",
            {
                "relative_threshold": "0.10",
                "ordered_criteria": expected_trace_names,
                "administrative_tie_winner": "P1",
                "used_cost_or_latency": False,
                "used_final100": False,
            },
            {
                "relative_threshold": str(PRACTICAL_TIE_ABS_DIFF_RATIO),
                "ordered_criteria": observed_trace_names,
                "administrative_tie_winner": tie_decision.selected_prompt_id,
                "used_cost_or_latency": tie_decision.used_cost_or_latency,
                "used_final100": tie_decision.used_final100,
            },
            pf35_ok,
        )

    return checks


def run_all_pfc_checks() -> list[dict[str, Any]]:
    """Execute Audit Correction 01 checks PFC-01 through PFC-16 under outbound network kill switch."""
    checks: list[dict[str, Any]] = []

    def record(
        check_id: str,
        domain: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "domain": domain,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
            }
        )

    kill_switch = NetworkKillSwitchGuard()
    with scrub_provider_api_keys(), kill_switch.activate():
        dev_bundle, cand_reg, registry, plan, freeze_artifact = (
            build_frozen_dev_tune_plan_and_freeze()
        )
        p1 = registry.prompts[0]
        p2 = registry.prompts[1]
        pair_audit = build_per_fixture_pair_audit(dev_bundle, registry, plan)
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)

        # PFC-01: P1 prompt_version remains TRAVEL_PLANNER_BENCHMARK_V2
        pfc01_ok = (
            p1.prompt_version == "TRAVEL_PLANNER_BENCHMARK_V2"
            and freeze_artifact.prompt_versions["P1"] == "TRAVEL_PLANNER_BENCHMARK_V2"
        )
        record(
            "PFC-01",
            "PROMPT_VERSION_SEMANTICS",
            "P1 prompt_version remains TRAVEL_PLANNER_BENCHMARK_V2",
            "TRAVEL_PLANNER_BENCHMARK_V2",
            p1.prompt_version,
            pfc01_ok,
        )

        # PFC-02: P2 prompt_version equals TRAVEL_PLANNER_BENCHMARK_V2
        pfc02_ok = (
            p2.prompt_version == "TRAVEL_PLANNER_BENCHMARK_V2"
            and freeze_artifact.prompt_versions["P2"] == "TRAVEL_PLANNER_BENCHMARK_V2"
        )
        record(
            "PFC-02",
            "PROMPT_VERSION_SEMANTICS",
            "P2 prompt_version equals TRAVEL_PLANNER_BENCHMARK_V2 (matching P1 template interpolation)",
            "TRAVEL_PLANNER_BENCHMARK_V2",
            p2.prompt_version,
            pfc02_ok,
        )

        # PFC-03: P2 candidate definition ID remains W06_DEV_TUNE_CANDIDATE_P2_V1 outside model prompt semantics
        rendered_prompts_contain_def_id = False
        preloaded_catalog_by_dest = {
            dest: build_destination_catalog_context(dest)
            for dest in {sc.destination_slug for sc in dev_bundle.dev_tune_fixtures}
        }
        for scenario in dev_bundle.dev_tune_fixtures:
            ctx_p1 = build_deterministic_dev_scenario_context(
                scenario, p1, preloaded_catalog_by_dest=preloaded_catalog_by_dest
            )
            ctx_p2 = build_deterministic_dev_scenario_context(
                scenario, p2, preloaded_catalog_by_dest=preloaded_catalog_by_dest
            )
            if (
                P2_CANDIDATE_DEFINITION_ID in ctx_p1.user_prompt
                or P2_CANDIDATE_DEFINITION_ID in ctx_p2.user_prompt
            ):
                rendered_prompts_contain_def_id = True
        pfc03_ok = (
            P2_CANDIDATE_DEFINITION_ID == "W06_DEV_TUNE_CANDIDATE_P2_V1"
            and P2_CANDIDATE_DEFINITION_ID not in p1.system_prompt
            and P2_CANDIDATE_DEFINITION_ID not in p2.system_prompt
            and P2_CANDIDATE_DEFINITION_ID not in p1.user_prompt_template
            and P2_CANDIDATE_DEFINITION_ID not in p2.user_prompt_template
            and not rendered_prompts_contain_def_id
            and "p2_candidate_definition_id"
            not in freeze_artifact.model_dump(mode="json")
        )
        record(
            "PFC-03",
            "CANDIDATE_DEFINITION_METADATA",
            "P2_CANDIDATE_DEFINITION_ID remains W06_DEV_TUNE_CANDIDATE_P2_V1 strictly outside model prompt semantics",
            {
                "p2_candidate_definition_id": "W06_DEV_TUNE_CANDIDATE_P2_V1",
                "interpolated_into_prompts": False,
            },
            {
                "p2_candidate_definition_id": P2_CANDIDATE_DEFINITION_ID,
                "interpolated_into_prompts": rendered_prompts_contain_def_id,
            },
            pfc03_ok,
        )

        # PFC-04: P2 system suffix byte-identical to previously frozen intended suffix
        observed_suffix = p2.system_prompt[len(PREFLIGHT_SHARED_SYSTEM_PROMPT) + 1 :]
        pfc04_ok = (
            observed_suffix.encode("utf-8")
            == P2_EXACT_SYSTEM_PROMPT_SUFFIX.encode("utf-8")
            and sha256_utf8_lf(p2.system_prompt) == P2_EXPECTED_SYSTEM_PROMPT_SHA256
        )
        record(
            "PFC-04",
            "P2_SYSTEM_SUFFIX",
            "P2 system prompt suffix is byte-identical to the frozen constraint-check suffix",
            P2_EXPECTED_SYSTEM_PROMPT_SHA256,
            sha256_utf8_lf(p2.system_prompt),
            pfc04_ok,
        )

        # PFC-05: P1 semantic hash remains authoritative 096ff4...
        pfc05_ok = (
            p1.semantic_prompt_sha256 == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
            and p1.semantic_prompt_sha256
            != P1_NON_AUTHORITATIVE_HISTORICAL_PROSE_SHA256
        )
        record(
            "PFC-05",
            "P1_AUTHORITATIVE_HASH",
            "P1 semantic prompt SHA256 remains authoritative 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11",
            P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
            p1.semantic_prompt_sha256,
            pfc05_ok,
        )

        # PFC-06: all 20 P1/P2 fixture pairs have identical rendered user_prompt_sha256
        pfc06_ok = (
            pair_audit["fixture_count"] == 20
            and pair_audit["all_20_rendered_user_prompts_byte_identical"] is True
            and pair_audit["all_candidates_share_identical_user_prompt_sha_per_fixture"]
            is True
        )
        record(
            "PFC-06",
            "CONTROLLED_EXPERIMENT_PARITY",
            "All 20 DEV-TUNE fixture pairs have byte-identical P1/P2 rendered user prompts and user_prompt_sha256",
            {"fixture_count": 20, "all_20_identical": True},
            {
                "fixture_count": pair_audit["fixture_count"],
                "all_20_identical": pair_audit[
                    "all_20_rendered_user_prompts_byte_identical"
                ],
            },
            pfc06_ok,
        )

        # PFC-07: fixture 001 P1/P2 rendered user hash identical
        f001_p1 = pair_audit["fixture_001_p1_user_prompt_sha256"]
        f001_p2 = pair_audit["fixture_001_p2_user_prompt_sha256"]
        pfc07_ok = (
            f001_p1 == f001_p2 == EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256
        )
        record(
            "PFC-07",
            "FIXTURE_001_PARITY",
            "W06-DEV-TUNE-001 P1 and P2 rendered user_prompt_sha256 both equal c632a1f607203a81c9422164a7910c5f82211437d74af9c91bb6b370c1da3c17",
            EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256,
            {"P1": f001_p1, "P2": f001_p2},
            pfc07_ok,
        )

        # PFC-08: same candidate/provider config identical between P1/P2
        pfc08_ok = all(
            f_rec["candidate_pairs"][cid]["provider_config_sha256_equal"]
            for f_rec in pair_audit["fixtures"]
            for cid in ORDERED_CANDIDATE_IDS
        )
        record(
            "PFC-08",
            "PROVIDER_CONFIG_PARITY",
            "Provider configuration SHA256 and sampling/reasoning config are identical between paired P1/P2 cells for every candidate",
            True,
            pfc08_ok,
            pfc08_ok,
        )

        # PFC-09: scenario/catalog hashes identical between paired cells
        pfc09_ok = all(
            f_rec["candidate_pairs"][cid]["scenario_sha256_equal"]
            and f_rec["candidate_pairs"][cid]["catalog_context_sha256_equal"]
            for f_rec in pair_audit["fixtures"]
            for cid in ORDERED_CANDIDATE_IDS
        )
        record(
            "PFC-09",
            "SCENARIO_CATALOG_PARITY",
            "scenario_sha256 and catalog_context_sha256 are identical between paired P1/P2 cells across all 60 pairs",
            True,
            pfc09_ok,
            pfc09_ok,
        )

        # PFC-10: system prompt is the only semantic prompt-text difference
        pfc10_ok = (
            pair_audit["only_system_prompt_suffix_differs_in_prompt_texts"] is True
            and pair_audit["differing_manifest_fields_across_all_60_pairs"]
            == ["prompt_id", "run_id", "system_prompt_sha256"]
        )
        record(
            "PFC-10",
            "SOLE_SEMANTIC_DIFFERENCE",
            "System prompt suffix is the sole semantic prompt-text difference between P1 and P2 across all 60 cell pairs",
            {
                "only_system_prompt_suffix_differs": True,
                "differing_manifest_fields": [
                    "prompt_id",
                    "run_id",
                    "system_prompt_sha256",
                ],
            },
            {
                "only_system_prompt_suffix_differs": pair_audit[
                    "only_system_prompt_suffix_differs_in_prompt_texts"
                ],
                "differing_manifest_fields": pair_audit[
                    "differing_manifest_fields_across_all_60_pairs"
                ],
            },
            pfc10_ok,
        )

        # PFC-11: 120-cell plan unchanged in cardinality
        pfc11_ok = len(plan.cells) == 120 and plan.expected_total_cells == 120
        record(
            "PFC-11",
            "PLAN_CARDINALITY",
            "DEV-TUNE execution plan contains 120 cells",
            120,
            len(plan.cells),
            pfc11_ok,
        )

        # PFC-12: 60 cells per prompt
        prompt_counts = {
            pid: sum(1 for c in plan.cells if c.prompt_id == pid)
            for pid in ("P1", "P2")
        }
        pfc12_ok = prompt_counts == {"P1": 60, "P2": 60}
        record(
            "PFC-12",
            "PLAN_CARDINALITY",
            "Each prompt candidate (P1, P2) has 60 cells",
            {"P1": 60, "P2": 60},
            prompt_counts,
            pfc12_ok,
        )

        # PFC-13: 40 cells per candidate
        cand_counts = {
            cid: sum(1 for c in plan.cells if c.candidate_id == cid)
            for cid in ("C1", "C2", "C3")
        }
        pfc13_ok = cand_counts == {"C1": 40, "C2": 40, "C3": 40}
        record(
            "PFC-13",
            "PLAN_CARDINALITY",
            "Each model candidate (C1, C2, C3) has 40 cells",
            {"C1": 40, "C2": 40, "C3": 40},
            cand_counts,
            pfc13_ok,
        )

        # PFC-14: 6 cells per fixture
        fix_counts = {
            fid: sum(1 for c in plan.cells if c.fixture_id == fid)
            for fid in dev_bundle.dev_tune_ids
        }
        pfc14_ok = len(fix_counts) == 20 and all(
            v == 6 for v in fix_counts.values()
        )
        record(
            "PFC-14",
            "PLAN_CARDINALITY",
            "Each of the 20 DEV-TUNE fixtures has 6 cells",
            {"fixtures": 20, "cells_per_fixture": 6},
            {
                "fixtures": len(fix_counts),
                "min_cells": min(fix_counts.values()),
                "max_cells": max(fix_counts.values()),
            },
            pfc14_ok,
        )

        # PFC-15: scientific bundle SHA unchanged
        pfc15_ok = bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        record(
            "PFC-15",
            "SCIENTIFIC_CODE_BUNDLE",
            "Scientific code bundle SHA256 remains 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
            EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            bundle_sha,
            pfc15_ok,
        )

        # PFC-16: zero live provider calls
        pfc16_ok = len(kill_switch.blocked_attempts) == 0
        record(
            "PFC-16",
            "NETWORK_ISOLATION",
            "Zero live provider calls occurred during Audit Correction 01 verification",
            0,
            len(kill_switch.blocked_attempts),
            pfc16_ok,
        )

    return checks


def generate_and_persist_all_artifacts() -> dict[str, Any]:
    """Generate and write the freeze artifact, execution plan, and verification receipt."""
    freeze_path = REPO_ROOT / FREEZE_ARTIFACT_RELATIVE_PATH
    plan_path = REPO_ROOT / DEV_TUNE_PLAN_RELATIVE_PATH
    receipt_path = REPO_ROOT / FREEZE_RECEIPT_RELATIVE_PATH

    dev_bundle, cand_reg, registry, plan, freeze_artifact = (
        build_frozen_dev_tune_plan_and_freeze()
    )
    p1 = registry.prompts[0]
    p2 = registry.prompts[1]

    freeze_bytes = canonical_json_bytes(freeze_artifact.model_dump(mode="json"))
    plan_bytes = canonical_json_bytes(plan.model_dump(mode="json"))

    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    freeze_path.write_bytes(freeze_bytes)
    plan_path.write_bytes(plan_bytes)

    pf_checks = run_all_pf_checks(freeze_path=freeze_path, plan_path=plan_path)
    pfc_checks = run_all_pfc_checks()
    failed_pf = [c for c in pf_checks if c["status"] != "PASS"]
    failed_pfc = [c for c in pfc_checks if c["status"] != "PASS"]
    if failed_pf or failed_pfc:
        raise RuntimeError(
            f"Verification failed: PF={[c['check_id'] for c in failed_pf]}, "
            f"PFC={[c['check_id'] for c in failed_pfc]}"
        )

    pair_audit = build_per_fixture_pair_audit(dev_bundle, registry, plan)
    freeze_file_sha256 = hashlib.sha256(freeze_bytes).hexdigest()
    plan_file_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    provider_config_registry_sha256 = compute_provider_config_registry_sha256(cand_reg)
    bundle_file_hashes = compute_scientific_code_bundle_file_hashes(repo_root=REPO_ROOT)

    receipt_payload: dict[str, Any] = {
        "task_id": TASK_ID,
        "audit_correction_task_id": AUDIT_CORRECTION_TASK_ID,
        "schema_version": "1.1.0",
        "status": "PASS",
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA,
        "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
        "predecessor_draft_head_sha": PREDECESSOR_DRAFT_HEAD_SHA,
        "scientific_decision": {
            "prompt_candidate_decision": PROMPT_CANDIDATE_DECISION,
            "prompt_candidate_count": 2,
            "prompt_candidate_ids": ["P1", "P2"],
            "no_prompt_result_shopping": NO_PROMPT_RESULT_SHOPPING,
            "frozen_before": [
                "DEV_TUNE_EXECUTION",
                "DEV_SELECT_EXECUTION",
                "MODEL_WINNER_SELECTION",
                "FINAL100_EXECUTION",
            ],
            "pre_results_declaration": {
                "prompt_choice_frozen_before_any_dev_tune_result": True,
                "no_provider_output_inspected": True,
                "no_live_provider_call_occurred": True,
                "no_prompt_candidate_added_removed_rewritten_or_selected_based_on_performance": True,
                "p2_is_provider_neutral_constraint_reinforcement_variant": True,
                "experimental_question": (
                    "Tests whether explicit pre-output constraint checking improves primary "
                    "scientific rates without changing catalog, schema, model configuration, or evaluator."
                ),
            },
            "audit_correction_01_declaration": {
                "pre_merge_draft_defect": (
                    "The first pre-merge freeze draft used a P2 prompt_version label "
                    "(W06_DEV_TUNE_CANDIDATE_P2_V1) that was interpolated into the rendered user prompt "
                    "via 'BENCHMARK MODE — {prompt_version}'."
                ),
                "detected_by": "ChatGPT independent audit before any DEV-TUNE execution or live provider call.",
                "correction_applied": (
                    "The corrected freeze uses the exact same template prompt_version "
                    "(TRAVEL_PLANNER_BENCHMARK_V2) for both P1 and P2, preserving "
                    "P2_CANDIDATE_DEFINITION_ID = W06_DEV_TUNE_CANDIDATE_P2_V1 strictly as experiment "
                    "metadata outside model prompt semantics and leaving the system-prompt constraint "
                    "suffix as the sole intended semantic difference."
                ),
                "result_contamination_occurred": False,
            },
            "claim_boundary": {
                "p2_claimed_superior": False,
                "p1_claimed_inferior": False,
                "scope": [
                    "candidate_definitions",
                    "experimental_comparison",
                    "execution_plan",
                    "selection_rule",
                ],
            },
        },
        "prompts": {
            "P1": {
                "prompt_id": p1.prompt_id,
                "prompt_version": p1.prompt_version,
                "system_prompt_sha256": freeze_artifact.system_prompt_sha256_by_id[
                    "P1"
                ],
                "user_prompt_template_sha256": freeze_artifact.user_prompt_template_sha256_by_id[
                    "P1"
                ],
                "semantic_prompt_sha256": p1.semantic_prompt_sha256,
                "created_before_live_dev_execution": p1.created_before_live_dev_execution,
                "provider_specific_semantic_prompt": p1.provider_specific_semantic_prompt,
            },
            "P2": {
                "prompt_id": p2.prompt_id,
                "prompt_version": p2.prompt_version,
                "p2_candidate_definition_id": P2_CANDIDATE_DEFINITION_ID,
                "system_prompt_sha256": freeze_artifact.system_prompt_sha256_by_id[
                    "P2"
                ],
                "user_prompt_template_sha256": freeze_artifact.user_prompt_template_sha256_by_id[
                    "P2"
                ],
                "semantic_prompt_sha256": p2.semantic_prompt_sha256,
                "system_prompt_suffix": P2_EXACT_SYSTEM_PROMPT_SUFFIX,
                "created_before_live_dev_execution": p2.created_before_live_dev_execution,
                "provider_specific_semantic_prompt": p2.provider_specific_semantic_prompt,
            },
            "p1_p2_user_template_identical": (
                freeze_artifact.user_prompt_template_sha256_by_id["P1"]
                == freeze_artifact.user_prompt_template_sha256_by_id["P2"]
            ),
            "p1_p2_rendered_user_prompts_identical_all_20": pair_audit[
                "all_20_rendered_user_prompts_byte_identical"
            ],
            "only_system_prompt_suffix_differs": pair_audit[
                "only_system_prompt_suffix_differs_in_prompt_texts"
            ],
            "provider_specific_prompts": False,
            "p1_historical_hash_verification": verify_historical_p1_hash_provenance(p1),
        },
        "per_fixture_pair_audit": pair_audit,
        "prompt_registry": {
            "max_allowed_prompts": registry.max_allowed_prompts,
            "prompt_candidate_ids": [p.prompt_id for p in registry.prompts],
            "prompt_registry_sha256": registry.registry_sha256,
        },
        "dev_tune_execution_plan": {
            "phase": plan.phase,
            "dev_bundle_relative_path": DEV_FIXTURES_FREEZE_RELATIVE_PATH,
            "dev_bundle_sha256": dev_bundle.dev_bundle_sha256,
            "dev_total_fixtures": dev_bundle.total_count,
            "dev_tune_fixtures": plan.fixture_count,
            "dev_select_fixtures": dev_bundle.dev_select_count,
            "candidates": len(plan.candidate_ids),
            "prompts": len(plan.prompt_ids),
            "executions_per_cell": 1,
            "expected_dev_tune_cells": plan.expected_total_cells,
            "actual_dev_tune_cells": len(plan.cells),
            "cells_per_prompt": {"P1": 60, "P2": 60},
            "cells_per_candidate": {"C1": 40, "C2": 40, "C3": 40},
            "cells_per_fixture": 6,
            "dev_tune_plan_sha256": plan.plan_sha256,
            "dev_tune_plan_file_sha256": plan_file_sha256,
        },
        "future_prompt_selection_rule": {
            "winning_prompt_selected_now": False,
            "aggregation_scope": "20 DEV-TUNE fixtures x 3 candidates = 60 cells per prompt (120 cells total, 0 retries)",
            "ordered_criteria": list(PRIMARY_DEV_RATE_CRITERIA),
            "survival_band_relative_to_best": float(PRACTICAL_TIE_ABS_DIFF_RATIO),
            "survival_mode": "SET_BASED_RELATIVE_TO_BEST_NO_PAIRWISE_CHAINING",
            "administrative_tie_breaker": "P1",
            "cost_criterion_used": False,
            "latency_criterion_used": False,
            "weighted_composite_used": False,
            "final100_used": False,
        },
        "code_and_schema_provenance": {
            "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "scientific_code_bundle_unchanged": True,
            "scientific_code_bundle_file_count": len(bundle_file_hashes),
            "scientific_code_bundle_file_hashes": bundle_file_hashes,
            "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
            "candidate_registry_sha256": cand_reg.registry_sha256,
            "provider_config_registry_sha256": provider_config_registry_sha256,
            "provider_config_sha256_by_candidate": {
                cid: get_cached_provider_config_sha256(cid)
                for cid in ORDERED_CANDIDATE_IDS
            },
            "forbidden_final100_sha256s": sorted(
                [FORBIDDEN_FINAL100_BUNDLE_SHA256, FORBIDDEN_P11_MANIFEST_SHA256]
            ),
        },
        "artifacts": {
            "prompt_freeze_artifact_id": freeze_artifact.artifact_id,
            "prompt_freeze_artifact_version": freeze_artifact.version,
            "prompt_freeze_relative_path": FREEZE_ARTIFACT_RELATIVE_PATH,
            "prompt_freeze_sha256": freeze_file_sha256,
            "dev_tune_plan_relative_path": DEV_TUNE_PLAN_RELATIVE_PATH,
            "dev_tune_plan_sha256": plan.plan_sha256,
            "dev_tune_plan_file_sha256": plan_file_sha256,
            "receipt_relative_path": FREEZE_RECEIPT_RELATIVE_PATH,
        },
        "zero_live_execution_boundary": {
            "live_provider_calls": 0,
            "provider_cost_usd": 0.0,
            "dev_tune_execution_started": False,
            "dev_select_execution_started": False,
            "winning_prompt_selected": False,
            "winner_model_selected": False,
            "final100_used": False,
            "live_authorization_created": False,
        },
        "verification_summary": {
            "pf_total_checks": len(pf_checks),
            "pf_passed_checks": sum(1 for c in pf_checks if c["status"] == "PASS"),
            "pf_failed_checks": sum(1 for c in pf_checks if c["status"] != "PASS"),
            "pfc_total_checks": len(pfc_checks),
            "pfc_passed_checks": sum(1 for c in pfc_checks if c["status"] == "PASS"),
            "pfc_failed_checks": sum(1 for c in pfc_checks if c["status"] != "PASS"),
            "total_checks": len(pf_checks) + len(pfc_checks),
            "passed_checks": sum(
                1 for c in (pf_checks + pfc_checks) if c["status"] == "PASS"
            ),
            "failed_checks": sum(
                1 for c in (pf_checks + pfc_checks) if c["status"] != "PASS"
            ),
            "overall_status": "PASS",
        },
        "checks": pf_checks,
        "audit_correction_01_checks": pfc_checks,
    }

    receipt_path.write_bytes(canonical_json_bytes(receipt_payload))
    return receipt_payload


if __name__ == "__main__":
    receipt = generate_and_persist_all_artifacts()
    print(
        json.dumps(
            {
                "task_id": receipt["task_id"],
                "audit_correction_task_id": receipt["audit_correction_task_id"],
                "status": receipt["status"],
                "pf_checks": f"{receipt['verification_summary']['pf_passed_checks']}/{receipt['verification_summary']['pf_total_checks']}",
                "pfc_checks": f"{receipt['verification_summary']['pfc_passed_checks']}/{receipt['verification_summary']['pfc_total_checks']}",
                "p1_semantic_prompt_sha256": receipt["prompts"]["P1"][
                    "semantic_prompt_sha256"
                ],
                "p2_semantic_prompt_sha256": receipt["prompts"]["P2"][
                    "semantic_prompt_sha256"
                ],
                "p2_candidate_definition_id": receipt["prompts"]["P2"][
                    "p2_candidate_definition_id"
                ],
                "p1_p2_rendered_user_prompts_identical_all_20": receipt["prompts"][
                    "p1_p2_rendered_user_prompts_identical_all_20"
                ],
                "only_system_prompt_suffix_differs": receipt["prompts"][
                    "only_system_prompt_suffix_differs"
                ],
                "prompt_registry_sha256": receipt["prompt_registry"][
                    "prompt_registry_sha256"
                ],
                "dev_tune_plan_sha256": receipt["dev_tune_execution_plan"][
                    "dev_tune_plan_sha256"
                ],
                "dev_tune_plan_file_sha256": receipt["dev_tune_execution_plan"][
                    "dev_tune_plan_file_sha256"
                ],
                "prompt_freeze_sha256": receipt["artifacts"]["prompt_freeze_sha256"],
            },
            indent=2,
        )
    )
