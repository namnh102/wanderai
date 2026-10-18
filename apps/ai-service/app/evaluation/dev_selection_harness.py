"""Offline Scientific Execution & Selection Harness for W06 DEV-TUNE / DEV-SELECT (W06-DEV-SELECTION-HARNESS-01-OFFLINE).

Grounded in:
- data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json (W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_dev_fixtures_freeze_v1.json (80 frozen DEV fixtures: 20 DEV-TUNE + 60 DEV-SELECT)
- data/evaluation/w06/w06_dev_fixture_manifest_v1.json
- data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json
- data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json
- data/evaluation/w06/w06_model_preflight_schema_portability_amendment_v1.json

STRICT SCIENTIFIC & OPERATIONAL INVARIANTS:
- 100% OFFLINE: zero live provider calls (Google Gemini, OpenAI, Anthropic Claude, or any fallback).
- Secret-independent: never reads API key values, never requires .env, never enables any live flag.
- Final-100 Firewall: fail-closed runtime guard preventing any read, inspection, serialization,
  or evaluation of w06_scenarios_freeze_v1.json or any final-100 scenario semantics.
- Candidate Registry: strictly C1 (gemini-3.8-flash), C2 (gpt-6.1-sol), C3 (claude-sonnet-5-5),
  all verified PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2 under Portable Schema V2
  (SHA256: 825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490).
- Prompt Registry Infrastructure: supports at most 2 shared semantic prompt candidates (P1, P2);
  rejects P3 or >2 prompts or provider-specific prompt variants.
- Set-based relative-to-best 10pp survivor reduction (NOT pairwise chaining) for both
  DEV-TUNE prompt selection and DEV-SELECT model selection.
- All-survivor cost comparability gate before median-cost tiebreak, followed by median-latency
  tiebreak and final administrative tiebreak (C1 > C2 > C3).
- Stochasticity diagnostic support strictly gated AFTER a DEV-SELECT winner is selected.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime
from decimal import Decimal, localcontext
from enum import Enum
import json
from pathlib import Path
import re
import statistics
import subprocess
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.evaluation.model_preflight.base import (
    FROZEN_ARCHITECTURE_CLASS,
    FROZEN_ARCHITECTURE_ID,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_TIMEOUT_MS,
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
)
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_GENERATION_SCHEMA_SHA256_V1,
    COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
    SEMANTIC_SCHEMA_SHA256,
    build_anthropic_structured_output_wiring_v2,
    build_google_structured_output_wiring_v2,
    build_openai_structured_output_wiring_v2,
    compute_common_generation_schema_sha256_v1,
    compute_common_portable_generation_schema_sha256_v2,
    compute_semantic_schema_sha256,
)
from app.evaluation.model_preflight.types import (
    FROZEN_CLAUDE_EFFORT,
    FROZEN_CLAUDE_THINKING_MODE,
    FROZEN_GOOGLE_THINKING_LEVEL,
    FROZEN_OPENAI_REASONING_EFFORT,
    FROZEN_OPENAI_SERVICE_TIER,
)
from app.evaluation.planner_benchmark_evaluator import (
    ScenarioEvaluationResult,
    evaluate_benchmark_scenario,
    load_core_catalog_by_place_id,
)
from app.prompts.planner_benchmark_prompt import (
    BENCHMARK_PROMPT_VERSION,
    CANONICAL_INTEREST_LABELS_VI,
    DEFAULT_CATALOG_PATH,
    REPO_ROOT,
    TRAVEL_PLANNER_BENCHMARK_V2,
    build_destination_catalog_context,
    validate_canonical_interests_list,
)
from app.schemas.planner_benchmark import (
    HASH_BASIS_VERSION,
    BenchmarkCatalogPOI,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_VERSION,
    canonical_json_bytes,
    compute_catalog_sha256,
    normalize_lf_bytes,
    sha256_bytes,
    write_canonical_json,
    write_exact_utf8_text,
)

TASK_ID_DEV_HARNESS: str = "W06-DEV-SELECTION-HARNESS-01-OFFLINE"
TASK_ID_DEV_HARNESS_FIX_01: str = "W06-DEV-SELECTION-HARNESS-FIX-01"
TASK_ID_DEV_HARNESS_FIX_01_AUDIT_CORRECTION_01: str = (
    "W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-01"
)
TASK_ID_DEV_HARNESS_FIX_01_AUDIT_CORRECTION_02: str = (
    "W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-02"
)
PROVENANCE_LIFECYCLE_MODEL: str = (
    "CODE_BASIS_PLUS_SCIENTIFIC_CODE_BUNDLE_PLUS_RUNTIME_HEAD"
)
HARNESS_ARTIFACT_ID: str = "W06-DEV-SELECTION-HARNESS-01"
HARNESS_RECEIPT_ARTIFACT_ID: str = "W06-DEV-SELECTION-HARNESS-01-RECEIPT"
HARNESS_FIX_01_RECEIPT_ARTIFACT_ID: str = "W06-DEV-SELECTION-HARNESS-FIX-01-RECEIPT"
HARNESS_VERSION: str = "1.0.0"
EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS: str = "50884c610cebf455255b9d05f737d9558cabf2e7"
NEXT_GATE_ID: str = "W06-DEV-SELECTION-HARNESS-QA-01"
NEXT_GATE_ID_FIX_01: str = "W06-DEV-SELECTION-HARNESS-QA-02"
DECIMAL_SCIENTIFIC_PRECISION: int = 100

SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS: Tuple[str, ...] = (
    "apps/ai-service/app/evaluation/dev_selection_harness.py",
    "apps/ai-service/app/evaluation/model_preflight/__init__.py",
    "apps/ai-service/app/evaluation/model_preflight/anthropic_adapter.py",
    "apps/ai-service/app/evaluation/model_preflight/base.py",
    "apps/ai-service/app/evaluation/model_preflight/google_adapter.py",
    "apps/ai-service/app/evaluation/model_preflight/openai_adapter.py",
    "apps/ai-service/app/evaluation/model_preflight/schema_adapter.py",
    "apps/ai-service/app/evaluation/model_preflight/types.py",
    "apps/ai-service/app/evaluation/planner_benchmark_evaluator.py",
    "apps/ai-service/app/prompts/planner_benchmark_prompt.py",
    "apps/ai-service/app/schemas/planner_benchmark.py",
    "apps/ai-service/app/services/planner_benchmark_runner.py",
    "apps/ai-service/recommendation/reca/contract.py",
)

_GIT_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_SEMANTIC_SCHEMA_SHA256: str = (
    "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
)
EXPECTED_GENERATION_SCHEMA_V1_SHA256: str = (
    "5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c"
)
EXPECTED_PORTABLE_SCHEMA_V2_SHA256: str = (
    "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
)

DEFAULT_METHOD_LOCK_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_arch_selection_method_lock_v1.json"
)
DEFAULT_DEV_BUNDLE_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixtures_freeze_v1.json"
)
DEFAULT_DEV_MANIFEST_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_manifest_v1.json"
)
DEFAULT_OVERLAP_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_final_overlap_receipt_v1.json"
)
DEFAULT_01D_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01d_v2_live_receipt_v1.json"
)
DEFAULT_01C_AMENDMENT_PATH: Path = (
    REPO_ROOT
    / "data"
    / "evaluation"
    / "w06"
    / "w06_model_preflight_schema_portability_amendment_v1.json"
)
FORBIDDEN_FINAL100_BUNDLE_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_p11_assignment_manifest_v1.json"
)

DEFAULT_HARNESS_ARTIFACT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_selection_harness_v1.json"
)
DEFAULT_HARNESS_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_selection_harness_01_receipt_v1.json"
)
DEFAULT_HARNESS_FIX_01_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_selection_harness_fix_01_receipt_v1.json"
)

EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS: Dict[str, str] = {
    "data/evaluation/w06/w06_scenarios_freeze_v1.json": (
        "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
    ),
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json": (
        "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"
    ),
    "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json": (
        "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    ),
    "data/evaluation/w06/w06_dev_fixture_manifest_v1.json": (
        "15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98"
    ),
    "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json": (
        "285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa"
    ),
    "data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json": (
        "437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026"
    ),
    "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json": (
        "6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c"
    ),
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": (
        "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
    ),
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": (
        "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
    ),
    "data/evaluation/w06/w06_measurement_contract_v1.json": (
        "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298"
    ),
    "data/evaluation/w06/w06_model_preflight_schema_portability_amendment_v1.json": (
        "7b33fc2568e942db751649a7b2908dba50d2155e311582717e4f753bd608d350"
    ),
    "data/evaluation/w06/w06_model_preflight_portable_schema_v2_manifest.json": (
        "b11974a5119dc49de80d96e2a9ed11ad5c7aca93aff25fec2cb54049a27c6b28"
    ),
    "data/evaluation/w06/w06_model_preflight_01c_portable_schema_receipt_v1.json": (
        "524fcdefdf92de8783a39662c7514eb26612f4228545ad4cd687e700684eceb0"
    ),
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_plan_v1.json": (
        "121b3918fdcae02a93b76a0855f7ce019bb1396f47e85a59978ce9bcde8934c2"
    ),
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json": (
        "2c8c3384e1977816aeff559cddc8010ad9b57fdfa62b618090b7f3911e732e65"
    ),
    "data/curated/gomate_places_freeze_v2.json": (
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
    ),
    "apps/ai-service/recommendation/reca/contract.py": (
        "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
    ),
    "apps/ai-service/app/schemas/planner_benchmark.py": (
        "3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712"
    ),
}

FORBIDDEN_FINAL100_BUNDLE_SHA256: str = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
]
FORBIDDEN_P11_MANIFEST_SHA256: str = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
]

ORDERED_CANDIDATE_IDS: Tuple[str, str, str] = ("C1", "C2", "C3")
ALLOWED_PROMPT_IDS: Tuple[str, str] = ("P1", "P2")
MAX_PROMPT_CANDIDATES: int = 2

DEV_TOTAL_COUNT: int = 80
DEV_TUNE_COUNT: int = 20
DEV_SELECT_COUNT: int = 60

DEV_TUNE_MAX_CALLS_ONE_PROMPT: int = 60
DEV_TUNE_MAX_CALLS_TWO_PROMPTS: int = 120
DEV_SELECT_MAX_CALLS: int = 180

STOCHASTICITY_FIXTURE_COUNT: int = 5
STOCHASTICITY_EXECUTIONS_PER_FIXTURE: int = 3
STOCHASTICITY_MAX_CALLS: int = 15
EXPECTED_STOCHASTICITY_FIXTURE_IDS: Tuple[str, ...] = (
    "W06-DEV-TUNE-001",
    "W06-DEV-TUNE-002",
    "W06-DEV-TUNE-003",
    "W06-DEV-TUNE-004",
    "W06-DEV-TUNE-005",
)

PRACTICAL_TIE_ABS_DIFF_RATIO: Decimal = Decimal("0.10")
COST_CRITERION_SKIPPED_NOT_COMPARABLE: str = "COST_CRITERION_SKIPPED_NOT_COMPARABLE"
COST_CRITERION_APPLIED: str = "COST_CRITERION_APPLIED"
SINGLE_PROMPT_P1_LOCK_STATUS: str = "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"

PRIMARY_DEV_RATE_CRITERIA: Tuple[str, str, str] = (
    "VALID_RUN_AND_SCHEMA_RATE",
    "EXACT_GROUNDING_PASS_RATE",
    "FINAL_CORE_PASS_RATE",
)

EXPECTED_DEV_TUNE_MARGINALS: Dict[str, Dict[str, int]] = {
    "destination": {"ha-noi": 7, "da-nang": 7, "ha-long": 6},
    "days": {"2": 7, "3": 7, "4": 6},
    "interest_count": {"1": 7, "2": 7, "3": 6},
    "budget": {"B1": 5, "B2": 5, "B3": 5, "null": 5},
    "travel_style": {"BACKPACKER": 5, "BUDGET": 5, "COMFORT": 5, "LUXURY": 5},
    "weekend": {"true": 10, "false": 10},
}

EXPECTED_DEV_SELECT_MARGINALS: Dict[str, Dict[str, int]] = {
    "destination": {"ha-noi": 20, "da-nang": 20, "ha-long": 20},
    "days": {"2": 20, "3": 20, "4": 20},
    "interest_count": {"1": 20, "2": 20, "3": 20},
    "budget": {"B1": 15, "B2": 15, "B3": 15, "null": 15},
    "travel_style": {"BACKPACKER": 15, "BUDGET": 15, "COMFORT": 15, "LUXURY": 15},
    "weekend": {"true": 30, "false": 30},
}

# Budget VND ceiling -> budget tier mapping per days (2, 3, 4) from W06-SCENARIO-METHOD-LOCK-01
_BUDGET_VND_TO_TIER_BY_DAYS: Dict[int, Dict[int, str]] = {
    2: {1000000: "B1", 2000000: "B2", 4000000: "B3"},
    3: {1500000: "B1", 3000000: "B2", 6000000: "B3"},
    4: {2000000: "B1", 4000000: "B2", 8000000: "B3"},
}


class DevHarnessOfflineViolationError(RuntimeError):
    """Raised when any live provider execution or live flag is attempted in the offline harness."""


class Final100FirewallViolationError(RuntimeError):
    """Raised when the DEV harness attempts to access, parse, or evaluate final-100 scenarios."""


class ImmutableCellExecutionError(RuntimeError):
    """Raised when attempting to overwrite or re-execute an already attempted DEV cell."""


class DenominatorIntegrityError(RuntimeError):
    """Raised when any assigned cell is missing, dropped, or duplicated during aggregation."""


class StochasticityGateViolationError(RuntimeError):
    """Raised when attempting to plan or run stochasticity diagnostics before DEV-SELECT winner selection."""


class CandidateRegistryIntegrityError(RuntimeError):
    """Raised when candidate registry violates frozen C1/C2/C3 or Schema V2 eligibility rules."""


class PromptRegistryIntegrityError(RuntimeError):
    """Raised when prompt registry violates P1/P2 max-2 shared prompt rules."""


class PromptFreezeFirewallError(RuntimeError):
    """Raised when live DEV execution is attempted without a verified separate frozen prompt artifact."""


class BatchExecutionFatalStopError(RuntimeError):
    """Raised when a batch-fatal integrity or internal error stops the entire scientific batch before aggregation or selection."""


class ModelIntegrityBatchStopError(BatchExecutionFatalStopError):
    """Raised when missing or incompatible returned_model_id violates model integrity and stops the entire scientific batch."""


class HarnessInternalBatchStopError(BatchExecutionFatalStopError):
    """Raised when a HARNESS_INTERNAL_ERROR stops the entire scientific batch."""


class CodeCommitProvenanceError(ValueError, RuntimeError):
    """Raised when git HEAD cannot be resolved or when supplied code_commit_sha does not match active git HEAD."""


class ScientificCodeBundleIntegrityError(BatchExecutionFatalStopError, ValueError):
    """Raised when current scientific_code_bundle_sha256 does not match the frozen execution plan or prompt freeze."""


class LatencyAuthorityUnavailableError(ValueError, RuntimeError):
    """Raised when authoritative integer latency_ns / median_latency_ns_decimal is missing during latency tiebreak."""


class DevCellFailureClassification(str, Enum):
    """Locked failure taxonomy for DEV-TUNE and DEV-SELECT cell executions (Section 11 & Fix Group C)."""

    NONE = "NONE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    MODEL_ACCESS_FAILURE = "MODEL_ACCESS_FAILURE"
    HTTP_ERROR = "HTTP_ERROR"
    HTTP_429 = "HTTP_429"
    HTTP_5XX = "HTTP_5XX"
    TIMEOUT = "TIMEOUT"
    PARTIAL_TIMEOUT = "PARTIAL_TIMEOUT"
    MALFORMED_JSON = "MALFORMED_JSON"
    SCHEMA_INVALID_OUTPUT = "SCHEMA_INVALID_OUTPUT"
    SEMANTIC_VALIDATION_FAILURE = "SEMANTIC_VALIDATION_FAILURE"
    REFUSAL = "REFUSAL"
    MAX_TOKEN_TRUNCATION = "MAX_TOKEN_TRUNCATION"
    MODEL_INTEGRITY_MISMATCH = "MODEL_INTEGRITY_MISMATCH"
    HARNESS_INTERNAL_ERROR = "HARNESS_INTERNAL_ERROR"
    SCIENTIFIC_CODE_BUNDLE_MISMATCH = "SCIENTIFIC_CODE_BUNDLE_MISMATCH"


ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS: frozenset[DevCellFailureClassification] = frozenset(
    {
        DevCellFailureClassification.AUTHENTICATION_FAILURE,
        DevCellFailureClassification.MODEL_ACCESS_FAILURE,
        DevCellFailureClassification.HTTP_ERROR,
        DevCellFailureClassification.HTTP_429,
        DevCellFailureClassification.HTTP_5XX,
        DevCellFailureClassification.TIMEOUT,
        DevCellFailureClassification.PARTIAL_TIMEOUT,
        DevCellFailureClassification.MALFORMED_JSON,
        DevCellFailureClassification.SCHEMA_INVALID_OUTPUT,
        DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
        DevCellFailureClassification.REFUSAL,
        DevCellFailureClassification.MAX_TOKEN_TRUNCATION,
    }
)

BATCH_STOP_FAILURE_CLASSIFICATIONS: frozenset[DevCellFailureClassification] = frozenset(
    {
        DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
        DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
        DevCellFailureClassification.SCIENTIFIC_CODE_BUNDLE_MISMATCH,
    }
)


def validate_git_commit_sha40(sha: str) -> str:
    """Validate that a string is an exact 40-character lowercase hexadecimal git commit SHA."""
    if not isinstance(sha, str) or not _GIT_SHA40_RE.match(sha):
        raise CodeCommitProvenanceError(
            f"INVALID_CODE_COMMIT_SHA: Expected 40-character lowercase hex git SHA, got {sha!r}"
        )
    return sha


def validate_sha256_hex64(sha: str, field_name: str = "sha256") -> str:
    """Validate that a string is an exact 64-character lowercase hexadecimal SHA256 digest."""
    if not isinstance(sha, str) or not _SHA256_HEX64_RE.match(sha):
        raise ValueError(
            f"INVALID_SHA256_DIGEST for {field_name}: Expected 64-character lowercase hex SHA256, got {sha!r}"
        )
    return sha


class ScientificCodeBundleManifest(BaseModel):
    """Deterministic manifest of the frozen scientific source-code bundle (Audit Correction 02 / Section 4)."""

    model_config = ConfigDict(extra="forbid")

    scientific_code_bundle_sha256: str
    scientific_code_bundle_file_hashes: List[Dict[str, str]]

    @model_validator(mode="after")
    def _validate_bundle_manifest(self) -> "ScientificCodeBundleManifest":
        validate_sha256_hex64(
            self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
        )
        paths = [entry.get("path", "") for entry in self.scientific_code_bundle_file_hashes]
        if paths != sorted(paths) or len(set(paths)) != len(paths):
            raise ScientificCodeBundleIntegrityError(
                "scientific_code_bundle_file_hashes must be deterministically ordered with unique paths."
            )
        for entry in self.scientific_code_bundle_file_hashes:
            if set(entry.keys()) != {"path", "sha256"}:
                raise ScientificCodeBundleIntegrityError(
                    f"Invalid entry in scientific_code_bundle_file_hashes: {entry!r}"
                )
            validate_sha256_hex64(entry["sha256"], f"file_hash[{entry['path']}]")
        expected_bundle_sha = sha256_bytes(
            canonical_json_bytes(self.scientific_code_bundle_file_hashes)
        )
        if self.scientific_code_bundle_sha256 != expected_bundle_sha:
            raise ScientificCodeBundleIntegrityError(
                f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: bundle sha256 {self.scientific_code_bundle_sha256} "
                f"!= computed {expected_bundle_sha}"
            )
        return self


_SCIENTIFIC_CODE_BUNDLE_CACHE: Dict[
    Tuple[str, Tuple[Tuple[str, int, int], ...]], ScientificCodeBundleManifest
] = {}


def compute_scientific_code_bundle(
    repo_root: Optional[Path] = None,
) -> ScientificCodeBundleManifest:
    """Compute the deterministic LF-normalized SHA256 bundle over SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS (Section 4).

    Excludes docs, receipts, reports, CI metadata, and frozen result artifacts so that
    metadata/evidence commits do not invalidate frozen plans or prompt-freeze artifacts.
    """
    root = repo_root if repo_root is not None else REPO_ROOT
    if not isinstance(root, Path):
        root = Path(root)
    if not root.exists() or not root.is_dir():
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_ERROR: Repository root does not exist: {root}"
        )

    ordered_paths = list(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS)
    if ordered_paths != sorted(ordered_paths) or len(set(ordered_paths)) != len(ordered_paths):
        raise ScientificCodeBundleIntegrityError(
            "SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS must be strictly sorted with unique paths."
        )

    stat_sig: List[Tuple[str, int, int]] = []
    for rel_path in ordered_paths:
        fpath = root / rel_path
        if not fpath.exists() or not fpath.is_file():
            raise ScientificCodeBundleIntegrityError(
                f"SCIENTIFIC_CODE_BUNDLE_FILE_MISSING: Required scientific source file missing: {rel_path}"
            )
        st = fpath.stat()
        stat_sig.append((rel_path, st.st_mtime_ns, st.st_size))

    cache_key = (str(root.resolve()), tuple(stat_sig))
    if repo_root is None and cache_key in _SCIENTIFIC_CODE_BUNDLE_CACHE:
        return _SCIENTIFIC_CODE_BUNDLE_CACHE[cache_key]

    file_hashes: List[Dict[str, str]] = []
    for rel_path in ordered_paths:
        fpath = root / rel_path
        file_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        file_hashes.append({"path": rel_path, "sha256": file_sha})

    bundle_sha = sha256_bytes(canonical_json_bytes(file_hashes))
    manifest = ScientificCodeBundleManifest(
        scientific_code_bundle_sha256=bundle_sha,
        scientific_code_bundle_file_hashes=file_hashes,
    )
    if repo_root is None:
        _SCIENTIFIC_CODE_BUNDLE_CACHE[cache_key] = manifest
    return manifest


def compute_scientific_code_bundle_file_hashes(
    repo_root: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Return the canonical ordered list of {'path': ..., 'sha256': ...} for the scientific code bundle."""
    return [
        dict(entry)
        for entry in compute_scientific_code_bundle(
            repo_root=repo_root
        ).scientific_code_bundle_file_hashes
    ]


def compute_scientific_code_bundle_sha256(
    repo_root: Optional[Path] = None,
) -> str:
    """Return the deterministic 64-hex SHA256 of the scientific code bundle."""
    return compute_scientific_code_bundle(repo_root=repo_root).scientific_code_bundle_sha256


_ORIG_SUBPROCESS_RUN = subprocess.run
_GIT_HEAD_SHA_CACHE: Dict[Tuple[str, str], str] = {}


def _compute_git_head_state_token(root: Path) -> Optional[str]:
    """Return a state token from .git/HEAD (and its target ref if symbolic) so cache invalidates on any commit."""
    git_dir = root / ".git"
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    try:
        head_text = head_file.read_text(encoding="utf-8", errors="replace").strip()
        if head_text.startswith("ref:"):
            ref_rel = head_text.split(":", 1)[1].strip()
            ref_file = git_dir / ref_rel
            if ref_file.is_file():
                return f"{head_text}:{ref_file.read_text(encoding='utf-8', errors='replace').strip()}"
            packed_refs = git_dir / "packed-refs"
            if packed_refs.is_file():
                return f"{head_text}:packed:{packed_refs.stat().st_mtime_ns}"
        return head_text
    except OSError:
        return None


def resolve_active_git_commit_sha(repo_root: Optional[Path] = None) -> str:
    """Resolve the active 40-hex git commit SHA of the repository (Correction C).

    Strictly fail-closed: raises CodeCommitProvenanceError if git HEAD cannot be determined.
    Never falls back to any hard-coded SHA.
    """
    root = repo_root if repo_root is not None else REPO_ROOT
    if not isinstance(root, Path):
        root = Path(root)
    if not root.exists() or not root.is_dir():
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_PROVENANCE_ERROR: Repository root does not exist: {root}"
        )

    state_token: Optional[str] = None
    if subprocess.run is _ORIG_SUBPROCESS_RUN:
        state_token = _compute_git_head_state_token(root)
        if state_token is not None:
            cached_sha = _GIT_HEAD_SHA_CACHE.get((str(root.resolve()), state_token))
            if cached_sha is not None:
                return cached_sha

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_PROVENANCE_ERROR: Failed to execute git rev-parse HEAD in {root}: {exc}"
        ) from exc

    if proc.returncode != 0:
        stderr_msg = (proc.stderr or "").strip()
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_PROVENANCE_ERROR: git rev-parse HEAD exited with code {proc.returncode} in {root}: {stderr_msg}"
        )

    candidate = (proc.stdout or "").strip().lower()
    if not _GIT_SHA40_RE.match(candidate):
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_PROVENANCE_ERROR: git rev-parse HEAD returned invalid 40-hex SHA {candidate!r}"
        )
    if subprocess.run is _ORIG_SUBPROCESS_RUN and state_token is not None:
        _GIT_HEAD_SHA_CACHE[(str(root.resolve()), state_token)] = candidate
    return candidate


def resolve_and_verify_code_commit_sha(
    supplied_sha: Optional[str] = None,
    *,
    repo_root: Optional[Path] = None,
) -> str:
    """Resolve current git HEAD and, if supplied_sha is provided, verify exact match with HEAD (Correction C).

    Fails closed with CodeCommitProvenanceError if git HEAD cannot be determined or if
    supplied_sha != current HEAD. Never substitutes a fallback SHA.
    """
    head_sha = resolve_active_git_commit_sha(repo_root=repo_root)
    if supplied_sha is None:
        return head_sha
    validated_supplied = validate_git_commit_sha40(supplied_sha)
    if validated_supplied != head_sha:
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_SHA_MISMATCH: Supplied code_commit_sha {validated_supplied!r} "
            f"does not match active git HEAD {head_sha!r}."
        )
    return head_sha


def format_canonical_decimal_str(value: Decimal | str | int) -> str:
    """Format an exact Decimal, integer, or decimal string as canonical non-exponent decimal text (Correction A & B).

    Strictly rejects float inputs to prevent binary floating-point contamination.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"FLOAT_FORBIDDEN_IN_CANONICAL_DECIMAL: Exact Decimal, int, or str required, got {type(value).__name__}"
        )
    with localcontext() as ctx:
        ctx.prec = DECIMAL_SCIENTIFIC_PRECISION
        dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        if not dec.is_finite():
            raise ValueError(f"Non-finite Decimal is forbidden in scientific artifacts: {dec!r}")
        fixed = f"{dec:f}"
    if "." in fixed:
        fixed = fixed.rstrip("0").rstrip(".")
    if fixed in ("-0", ""):
        fixed = "0"
    return fixed


def parse_canonical_decimal_str(value: str | Decimal | int) -> Decimal:
    """Parse canonical non-exponent decimal text (or Decimal/int) into an exact Decimal (Correction A & B).

    Strictly rejects float inputs to prevent binary floating-point round-trips.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"FLOAT_FORBIDDEN_IN_CANONICAL_DECIMAL: Exact str, Decimal, or int required, got {type(value).__name__}"
        )
    with localcontext() as ctx:
        ctx.prec = DECIMAL_SCIENTIFIC_PRECISION
        dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        if not dec.is_finite():
            raise ValueError(f"Non-finite Decimal is forbidden: {dec!r}")
        return dec


def compute_exact_decimal_median(values: Sequence[Decimal | int | str]) -> Decimal:
    """Compute the exact mathematical median of a non-empty sequence of Decimals/ints without float conversion (Correction A & B)."""
    if not values:
        raise ValueError("Cannot compute exact decimal median of empty sequence.")
    dec_values: List[Decimal] = []
    for v in values:
        if isinstance(v, bool) or isinstance(v, float) or not isinstance(v, (Decimal, int, str)):
            raise TypeError(
                f"compute_exact_decimal_median forbids float/bool and requires Decimal, int, or canonical str elements, got {type(v).__name__}"
            )
        dec_values.append(parse_canonical_decimal_str(v))
    with localcontext() as ctx:
        ctx.prec = DECIMAL_SCIENTIFIC_PRECISION
        sorted_vals = sorted(dec_values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 1:
            return +sorted_vals[mid]
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / Decimal(2)


def is_returned_model_id_compatible(
    requested_model_id: str,
    returned_model_id: Optional[str],
) -> bool:
    """Check whether returned_model_id is present and compatible with requested_model_id.

    Missing/empty returned_model_id or an unrelated model ID is rejected as a model integrity failure.
    Exact matches and snapshot/version suffixes '<requested_model_id>-*' are accepted.
    """
    if returned_model_id is None:
        return False
    ret = str(returned_model_id).strip()
    req = str(requested_model_id).strip()
    if not ret or not req:
        return False
    return ret == req or ret.startswith(f"{req}-")


def assert_not_final100_path(path: Path | str) -> Path:
    """Fail-closed path guard against reading final-100 scenario freeze or P11 manifest semantics.

    Enforces:
    1. Resolve path / symlink.
    2. Reject direct forbidden filenames or resolved canonical paths.
    3. If file exists on disk, compute LF-normalized SHA256 (without parsing JSON semantics)
       and reject if it matches FORBIDDEN_FINAL100_BUNDLE_SHA256 or FORBIDDEN_P11_MANIFEST_SHA256.
    """
    raw_path = Path(path)
    resolved = raw_path.resolve()
    forbidden_names = {
        "w06_scenarios_freeze_v1.json",
        "w06_p11_assignment_manifest_v1.json",
    }
    if (
        raw_path.name in forbidden_names
        or resolved.name in forbidden_names
        or resolved == FORBIDDEN_FINAL100_BUNDLE_PATH.resolve()
        or resolved == FORBIDDEN_P11_MANIFEST_PATH.resolve()
    ):
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Access to final-100 authority path '{resolved.name}' "
            "is strictly forbidden during DEV harness loading, context building, or selection."
        )

    if resolved.exists() and resolved.is_file():
        file_sha = sha256_bytes(normalize_lf_bytes(resolved.read_bytes()))
        if file_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256:
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: File '{resolved}' has SHA256 matching frozen "
                f"final-100 scenario bundle ({FORBIDDEN_FINAL100_BUNDLE_SHA256}). "
                "Copied, renamed, or aliased final-100 bundles are strictly forbidden."
            )
        if file_sha == FORBIDDEN_P11_MANIFEST_SHA256:
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: File '{resolved}' has SHA256 matching frozen "
                f"P11 assignment manifest ({FORBIDDEN_P11_MANIFEST_SHA256}). "
                "Copied, renamed, or aliased P11 manifests are strictly forbidden."
            )
    return resolved


def assert_not_final100_scenario_id(scenario_id: str) -> str:
    """Fail-closed scenario ID guard rejecting any non-DEV or final-100 scenario ID."""
    sid = (scenario_id or "").strip()
    if sid.startswith("W06-S") or not (
        sid.startswith("W06-DEV-TUNE-") or sid.startswith("W06-DEV-SELECT-")
    ):
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Scenario ID '{scenario_id}' is not an allowed "
            "DEV fixture ID (must start with 'W06-DEV-TUNE-' or 'W06-DEV-SELECT-')."
        )
    return sid


def assert_not_final100_scenario(scenario: BenchmarkScenarioInput | Dict[str, Any]) -> None:
    """Fail-closed scenario object guard rejecting any final-100 scenario or cross-partition label mismatch."""
    if isinstance(scenario, dict):
        sid = str(scenario.get("scenario_id") or "")
        label = str(scenario.get("fixture_label") or "")
    else:
        sid = scenario.scenario_id
        label = str(scenario.fixture_label or "")

    sid_clean = assert_not_final100_scenario_id(sid)
    if label not in {"W06_DEV_TUNE", "W06_DEV_SELECT"}:
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Scenario '{sid_clean}' has fixture_label={label!r}; "
            "only 'W06_DEV_TUNE' and 'W06_DEV_SELECT' are permitted in the DEV harness."
        )
    if sid_clean.startswith("W06-DEV-TUNE-") and label != "W06_DEV_TUNE":
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Cross-partition mismatch for '{sid_clean}': "
            f"W06-DEV-TUNE-* scenario must have fixture_label='W06_DEV_TUNE', got {label!r}."
        )
    if sid_clean.startswith("W06-DEV-SELECT-") and label != "W06_DEV_SELECT":
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Cross-partition mismatch for '{sid_clean}': "
            f"W06-DEV-SELECT-* scenario must have fixture_label='W06_DEV_SELECT', got {label!r}."
        )


def verify_frozen_authorities_dev_harness(
    repo_root: Optional[Path] = None,
) -> Dict[str, str]:
    """Verify LF-normalized SHA256 of all frozen W06 authorities without parsing final-100 semantics."""
    root = repo_root or REPO_ROOT
    verified: Dict[str, str] = {}
    for rel_path, expected_sha in sorted(EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS.items()):
        fpath = root / rel_path
        if not fpath.exists():
            raise RuntimeError(f"FROZEN_AUTHORITY_MISSING: {rel_path}")
        actual_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"FROZEN_AUTHORITY_SHA_MISMATCH for {rel_path}: "
                f"expected={expected_sha}, actual={actual_sha}"
            )
        verified[rel_path] = actual_sha

    # Verify live schema hashes match frozen constants
    sem_sha = compute_semantic_schema_sha256()
    v1_sha = compute_common_generation_schema_sha256_v1()
    v2_sha = compute_common_portable_generation_schema_sha256_v2()
    if sem_sha != EXPECTED_SEMANTIC_SCHEMA_SHA256:
        raise RuntimeError(f"SEMANTIC_SCHEMA_SHA256 mismatch: {sem_sha}")
    if v1_sha != EXPECTED_GENERATION_SCHEMA_V1_SHA256:
        raise RuntimeError(f"GENERATION_SCHEMA_V1_SHA256 mismatch: {v1_sha}")
    if v2_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise RuntimeError(f"PORTABLE_SCHEMA_V2_SHA256 mismatch: {v2_sha}")

    return verified


def _is_weekend_exposed(start_date_str: str, end_date_str: str) -> bool:
    """Return True if any date in [start_date, end_date] is Saturday (5) or Sunday (6)."""
    start_dt = datetime.date.fromisoformat(start_date_str)
    end_dt = datetime.date.fromisoformat(end_date_str)
    cur = start_dt
    while cur <= end_dt:
        if cur.weekday() in (5, 6):
            return True
        cur += datetime.timedelta(days=1)
    return False


def _infer_budget_tier(days: int, budget: Optional[int]) -> str:
    """Map scenario (days, budget) to canonical budget tier key ('B1', 'B2', 'B3', or 'null')."""
    if budget is None:
        return "null"
    tier = _BUDGET_VND_TO_TIER_BY_DAYS.get(days, {}).get(budget)
    if tier is None:
        raise ValueError(f"Unexpected budget ceiling {budget} for days={days}")
    return tier


def compute_dev_partition_marginals(
    fixtures: Sequence[BenchmarkScenarioInput],
) -> Dict[str, Dict[str, int]]:
    """Compute exact marginal distributions across destination, days, interest_count, budget, travel_style, weekend."""
    dest_counts: Counter[str] = Counter()
    days_counts: Counter[str] = Counter()
    ic_counts: Counter[str] = Counter()
    budget_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    weekend_counts: Counter[str] = Counter()

    for sc in fixtures:
        assert_not_final100_scenario(sc)
        dest_counts[sc.destination_slug] += 1
        days_counts[str(sc.days)] += 1
        ic_counts[str(len(sc.interests))] += 1
        budget_counts[_infer_budget_tier(sc.days, sc.budget)] += 1
        style_counts[sc.travel_style] += 1
        wk = "true" if _is_weekend_exposed(sc.start_date, sc.end_date) else "false"
        weekend_counts[wk] += 1

    return {
        "destination": {
            "ha-noi": dest_counts["ha-noi"],
            "da-nang": dest_counts["da-nang"],
            "ha-long": dest_counts["ha-long"],
        },
        "days": {
            "2": days_counts["2"],
            "3": days_counts["3"],
            "4": days_counts["4"],
        },
        "interest_count": {
            "1": ic_counts["1"],
            "2": ic_counts["2"],
            "3": ic_counts["3"],
        },
        "budget": {
            "B1": budget_counts["B1"],
            "B2": budget_counts["B2"],
            "B3": budget_counts["B3"],
            "null": budget_counts["null"],
        },
        "travel_style": {
            "BACKPACKER": style_counts["BACKPACKER"],
            "BUDGET": style_counts["BUDGET"],
            "COMFORT": style_counts["COMFORT"],
            "LUXURY": style_counts["LUXURY"],
        },
        "weekend": {
            "true": weekend_counts["true"],
            "false": weekend_counts["false"],
        },
    }


class VerifiedDevBundle(BaseModel):
    """Verified frozen 80-fixture DEV bundle and partition metadata (Section 3)."""

    model_config = ConfigDict(extra="forbid")

    dev_bundle_sha256: str
    dev_manifest_sha256: str
    overlap_receipt_sha256: str
    total_count: int
    dev_tune_count: int
    dev_select_count: int
    dev_tune_fixtures: List[BenchmarkScenarioInput]
    dev_select_fixtures: List[BenchmarkScenarioInput]
    dev_tune_ids: List[str]
    dev_select_ids: List[str]
    dev_tune_ids_sha256: str
    dev_select_ids_sha256: str
    dev_tune_marginals: Dict[str, Dict[str, int]]
    dev_select_marginals: Dict[str, Dict[str, int]]


def load_and_verify_frozen_dev_bundle(
    *,
    dev_bundle_path: Optional[Path] = None,
    dev_manifest_path: Optional[Path] = None,
    overlap_receipt_path: Optional[Path] = None,
) -> VerifiedDevBundle:
    """Load the frozen 80 DEV fixtures and verify exact counts, hashes, firewall, and marginals."""
    b_path = assert_not_final100_path(dev_bundle_path or DEFAULT_DEV_BUNDLE_PATH)
    m_path = assert_not_final100_path(dev_manifest_path or DEFAULT_DEV_MANIFEST_PATH)
    o_path = assert_not_final100_path(overlap_receipt_path or DEFAULT_OVERLAP_RECEIPT_PATH)

    bundle_bytes = normalize_lf_bytes(b_path.read_bytes())
    manifest_bytes = normalize_lf_bytes(m_path.read_bytes())
    overlap_bytes = normalize_lf_bytes(o_path.read_bytes())

    bundle_sha = sha256_bytes(bundle_bytes)
    manifest_sha = sha256_bytes(manifest_bytes)
    overlap_sha = sha256_bytes(overlap_bytes)

    expected_b_sha = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
        "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
    ]
    expected_m_sha = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
        "data/evaluation/w06/w06_dev_fixture_manifest_v1.json"
    ]
    expected_o_sha = EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS[
        "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json"
    ]

    if bundle_sha != expected_b_sha:
        raise ValueError(f"DEV bundle SHA256 mismatch: expected {expected_b_sha}, got {bundle_sha}")
    if manifest_sha != expected_m_sha:
        raise ValueError(
            f"DEV manifest SHA256 mismatch: expected {expected_m_sha}, got {manifest_sha}"
        )
    if overlap_sha != expected_o_sha:
        raise ValueError(
            f"DEV overlap receipt SHA256 mismatch: expected {expected_o_sha}, got {overlap_sha}"
        )

    bundle_data = json.loads(bundle_bytes.decode("utf-8"))
    overlap_data = json.loads(overlap_bytes.decode("utf-8"))

    if overlap_data.get("all_dev_exact_overlap_with_final") != 0:
        raise ValueError("Overlap receipt violates all_dev_exact_overlap_with_final == 0")
    if overlap_data.get("dev_tune_near_overlap_with_final") != 0:
        raise ValueError("Overlap receipt violates dev_tune_near_overlap_with_final == 0")

    raw_fixtures = bundle_data.get("fixtures", [])
    if len(raw_fixtures) != DEV_TOTAL_COUNT:
        raise ValueError(f"Expected {DEV_TOTAL_COUNT} DEV fixtures, found {len(raw_fixtures)}")

    dev_tune_fixtures: List[BenchmarkScenarioInput] = []
    dev_select_fixtures: List[BenchmarkScenarioInput] = []

    for raw_f in raw_fixtures:
        assert_not_final100_scenario(raw_f)
        sc = BenchmarkScenarioInput.model_validate(raw_f)
        assert_not_final100_scenario(sc)
        if sc.fixture_label == "W06_DEV_TUNE":
            dev_tune_fixtures.append(sc)
        elif sc.fixture_label == "W06_DEV_SELECT":
            dev_select_fixtures.append(sc)
        else:
            raise Final100FirewallViolationError(f"Invalid fixture_label: {sc.fixture_label}")

    if len(dev_tune_fixtures) != DEV_TUNE_COUNT:
        raise ValueError(f"Expected {DEV_TUNE_COUNT} DEV-TUNE fixtures, got {len(dev_tune_fixtures)}")
    if len(dev_select_fixtures) != DEV_SELECT_COUNT:
        raise ValueError(
            f"Expected {DEV_SELECT_COUNT} DEV-SELECT fixtures, got {len(dev_select_fixtures)}"
        )

    dev_tune_ids = [sc.scenario_id for sc in dev_tune_fixtures]
    dev_select_ids = [sc.scenario_id for sc in dev_select_fixtures]
    expected_tune_ids = [f"W06-DEV-TUNE-{i:03d}" for i in range(1, DEV_TUNE_COUNT + 1)]
    expected_select_ids = [f"W06-DEV-SELECT-{i:03d}" for i in range(1, DEV_SELECT_COUNT + 1)]
    if dev_tune_ids != expected_tune_ids:
        raise ValueError("DEV-TUNE fixture IDs are not in exact frozen order W06-DEV-TUNE-001..020")
    if dev_select_ids != expected_select_ids:
        raise ValueError(
            "DEV-SELECT fixture IDs are not in exact frozen order W06-DEV-SELECT-001..060"
        )

    tune_marginals = compute_dev_partition_marginals(dev_tune_fixtures)
    select_marginals = compute_dev_partition_marginals(dev_select_fixtures)

    if tune_marginals != EXPECTED_DEV_TUNE_MARGINALS:
        raise ValueError(
            f"DEV-TUNE marginals mismatch: expected={EXPECTED_DEV_TUNE_MARGINALS}, actual={tune_marginals}"
        )
    if select_marginals != EXPECTED_DEV_SELECT_MARGINALS:
        raise ValueError(
            f"DEV-SELECT marginals mismatch: expected={EXPECTED_DEV_SELECT_MARGINALS}, actual={select_marginals}"
        )

    return VerifiedDevBundle(
        dev_bundle_sha256=bundle_sha,
        dev_manifest_sha256=manifest_sha,
        overlap_receipt_sha256=overlap_sha,
        total_count=len(raw_fixtures),
        dev_tune_count=len(dev_tune_fixtures),
        dev_select_count=len(dev_select_fixtures),
        dev_tune_fixtures=dev_tune_fixtures,
        dev_select_fixtures=dev_select_fixtures,
        dev_tune_ids=dev_tune_ids,
        dev_select_ids=dev_select_ids,
        dev_tune_ids_sha256=sha256_bytes(canonical_json_bytes(dev_tune_ids)),
        dev_select_ids_sha256=sha256_bytes(canonical_json_bytes(dev_select_ids)),
        dev_tune_marginals=tune_marginals,
        dev_select_marginals=select_marginals,
    )


class DevCandidateSpec(BaseModel):
    """Frozen candidate model and provider configuration for DEV selection (Sections 5 & 6)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    provider: str
    requested_model_id: str
    technical_preflight_v2_status: str
    portable_generation_schema_v2_sha256: str
    structured_output_wiring: Dict[str, Any]
    sampling_reasoning_config: Dict[str, Any]
    omitted_parameters: List[str]
    max_output_tokens: int = FROZEN_MAX_OUTPUT_TOKENS
    timeout_ms: int = FROZEN_TIMEOUT_MS
    llm_calls_per_execution: int = 1
    automatic_retry: int = 0
    transport_retry: int = 0
    manual_retry: int = 0
    fallback: bool = False
    llm_repair: int = 0
    deterministic_semantic_repair: bool = False
    tools: bool = False

    @model_validator(mode="after")
    def _validate_candidate_invariants(self) -> "DevCandidateSpec":
        expected_map = {
            "C1": ("Google", "gemini-3.8-flash"),
            "C2": ("OpenAI", "gpt-6.1-sol"),
            "C3": ("Anthropic", "claude-sonnet-5-5"),
        }
        if self.candidate_id not in expected_map:
            raise CandidateRegistryIntegrityError(
                f"CANDIDATE_ID_FORBIDDEN: {self.candidate_id!r}. Allowed: {list(expected_map.keys())}"
            )
        exp_provider, exp_model = expected_map[self.candidate_id]
        if self.provider != exp_provider or self.requested_model_id != exp_model:
            raise CandidateRegistryIntegrityError(
                f"CANDIDATE_SUBSTITUTION_FORBIDDEN for {self.candidate_id}: "
                f"expected ({exp_provider}, {exp_model}), got ({self.provider}, {self.requested_model_id})"
            )
        if self.technical_preflight_v2_status != "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2":
            raise CandidateRegistryIntegrityError(
                f"Candidate {self.candidate_id} lacks PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2 status: "
                f"{self.technical_preflight_v2_status!r}"
            )
        if self.portable_generation_schema_v2_sha256 != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
            raise CandidateRegistryIntegrityError(
                f"Candidate {self.candidate_id} schema SHA mismatch: "
                f"{self.portable_generation_schema_v2_sha256}"
            )
        if (
            self.llm_calls_per_execution != 1
            or self.automatic_retry != 0
            or self.transport_retry != 0
            or self.manual_retry != 0
            or self.fallback is not False
            or self.llm_repair != 0
            or self.deterministic_semantic_repair is not False
            or self.tools is not False
        ):
            raise CandidateRegistryIntegrityError(
                f"Candidate {self.candidate_id} violates 1-call / retry=0 / fallback=false / repair=0 / tools=false invariants."
            )
        return self


class DevCandidateRegistry(BaseModel):
    """Frozen 3-candidate registry verified against Phase 01D receipt (Section 5)."""

    model_config = ConfigDict(extra="forbid")

    candidates: Dict[str, DevCandidateSpec]
    ordered_candidate_ids: List[str] = Field(default_factory=lambda: list(ORDERED_CANDIDATE_IDS))
    registry_sha256: str

    @model_validator(mode="after")
    def _validate_registry(self) -> "DevCandidateRegistry":
        if tuple(self.ordered_candidate_ids) != ORDERED_CANDIDATE_IDS:
            raise CandidateRegistryIntegrityError(
                f"Candidate order must be {list(ORDERED_CANDIDATE_IDS)}, got {self.ordered_candidate_ids}"
            )
        if set(self.candidates.keys()) != set(ORDERED_CANDIDATE_IDS) or len(self.candidates) != 3:
            raise CandidateRegistryIntegrityError(
                f"Candidate registry must contain exactly C1, C2, C3; got {sorted(self.candidates.keys())}"
            )
        return self


def load_and_verify_candidate_registry(
    receipt_01d_path: Optional[Path] = None,
) -> DevCandidateRegistry:
    """Build and verify the 3-candidate registry from the frozen 01D live revalidation receipt."""
    r_path = assert_not_final100_path(receipt_01d_path or DEFAULT_01D_RECEIPT_PATH)
    receipt_data = json.loads(normalize_lf_bytes(r_path.read_bytes()).decode("utf-8"))

    if (
        receipt_data.get("portable_generation_schema_v2_sha256")
        != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    ):
        raise CandidateRegistryIntegrityError(
            "01D receipt portable_generation_schema_v2_sha256 does not match frozen V2 hash."
        )

    c_records = receipt_data.get("candidates", {})
    for cid in ORDERED_CANDIDATE_IDS:
        crec = c_records.get(cid, {})
        if crec.get("status") != "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2":
            raise CandidateRegistryIntegrityError(
                f"Candidate {cid} did not pass 01D technical preflight V2."
            )

    c1_spec = DevCandidateSpec(
        candidate_id="C1",
        provider="Google",
        requested_model_id="gemini-3.8-flash",
        technical_preflight_v2_status=c_records["C1"]["status"],
        portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        structured_output_wiring=build_google_structured_output_wiring_v2(),
        sampling_reasoning_config={
            "thinking_level": FROZEN_GOOGLE_THINKING_LEVEL,
            "seed": FROZEN_SAMPLING_SEED,
        },
        omitted_parameters=["temperature", "top_p", "top_k"],
    )
    c2_spec = DevCandidateSpec(
        candidate_id="C2",
        provider="OpenAI",
        requested_model_id="gpt-6.1-sol",
        technical_preflight_v2_status=c_records["C2"]["status"],
        portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        structured_output_wiring=build_openai_structured_output_wiring_v2(),
        sampling_reasoning_config={
            "reasoning_effort": FROZEN_OPENAI_REASONING_EFFORT,
            "seed": FROZEN_SAMPLING_SEED,
            "service_tier": FROZEN_OPENAI_SERVICE_TIER,
        },
        omitted_parameters=["temperature", "top_p", "top_k", "logprobs", "top_logprobs"],
    )
    c3_spec = DevCandidateSpec(
        candidate_id="C3",
        provider="Anthropic",
        requested_model_id="claude-sonnet-5-5",
        technical_preflight_v2_status=c_records["C3"]["status"],
        portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        structured_output_wiring=build_anthropic_structured_output_wiring_v2(),
        sampling_reasoning_config={
            "thinking": {"type": FROZEN_CLAUDE_THINKING_MODE},
            "effort": FROZEN_CLAUDE_EFFORT,
        },
        omitted_parameters=["temperature", "top_p", "top_k", "seed"],
    )

    candidates_map = {"C1": c1_spec, "C2": c2_spec, "C3": c3_spec}
    reg_sha = sha256_bytes(
        canonical_json_bytes({k: v.model_dump() for k, v in sorted(candidates_map.items())})
    )
    return DevCandidateRegistry(
        candidates=candidates_map,
        ordered_candidate_ids=list(ORDERED_CANDIDATE_IDS),
        registry_sha256=reg_sha,
    )


def compute_semantic_prompt_sha256(
    *,
    prompt_id: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt_template: str,
) -> str:
    """Compute canonical SHA256 over a prompt candidate's semantic fields."""
    payload = {
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "system_prompt": system_prompt,
        "user_prompt_template": user_prompt_template,
    }
    return sha256_bytes(canonical_json_bytes(payload))


class PromptCandidateSpec(BaseModel):
    """Registered shared semantic prompt candidate specification (Section 7)."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    prompt_version: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    user_prompt_template: str = Field(..., min_length=1)
    semantic_prompt_sha256: str
    created_before_live_dev_execution: bool = True
    provider_specific_semantic_prompt: bool = False

    @field_validator("prompt_id")
    @classmethod
    def _validate_prompt_id(cls, v: str) -> str:
        if v not in ALLOWED_PROMPT_IDS:
            raise PromptRegistryIntegrityError(
                f"PROMPT_ID_FORBIDDEN: {v!r}. Only {list(ALLOWED_PROMPT_IDS)} are allowed; P3 or other IDs are forbidden."
            )
        return v

    @model_validator(mode="after")
    def _validate_prompt_spec(self) -> "PromptCandidateSpec":
        if not self.created_before_live_dev_execution:
            raise PromptRegistryIntegrityError(
                f"Prompt {self.prompt_id} must have created_before_live_dev_execution=True."
            )
        if self.provider_specific_semantic_prompt:
            raise PromptRegistryIntegrityError(
                f"Prompt {self.prompt_id} cannot be provider-specific; shared semantic prompts are required across C1/C2/C3."
            )
        expected_sha = compute_semantic_prompt_sha256(
            prompt_id=self.prompt_id,
            prompt_version=self.prompt_version,
            system_prompt=self.system_prompt,
            user_prompt_template=self.user_prompt_template,
        )
        if self.semantic_prompt_sha256 != expected_sha:
            raise PromptRegistryIntegrityError(
                f"Prompt {self.prompt_id} semantic_prompt_sha256 mismatch: "
                f"expected={expected_sha}, got={self.semantic_prompt_sha256}"
            )
        return self


def create_prompt_candidate_spec(
    *,
    prompt_id: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt_template: str,
    created_before_live_dev_execution: bool = True,
    provider_specific_semantic_prompt: bool = False,
) -> PromptCandidateSpec:
    """Create a validated PromptCandidateSpec with automatically computed semantic_prompt_sha256."""
    sha = compute_semantic_prompt_sha256(
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
    )
    return PromptCandidateSpec(
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        semantic_prompt_sha256=sha,
        created_before_live_dev_execution=created_before_live_dev_execution,
        provider_specific_semantic_prompt=provider_specific_semantic_prompt,
    )


class PromptRegistry(BaseModel):
    """Prompt registry infrastructure supporting at most 2 shared prompt candidates (P1, P2)."""

    model_config = ConfigDict(extra="forbid")

    prompts: List[PromptCandidateSpec]
    max_allowed_prompts: int = MAX_PROMPT_CANDIDATES
    registry_sha256: str

    @model_validator(mode="after")
    def _validate_prompt_registry(self) -> "PromptRegistry":
        if len(self.prompts) < 1:
            raise PromptRegistryIntegrityError(
                "PromptRegistry requires at least 1 prompt candidate."
            )
        if len(self.prompts) > MAX_PROMPT_CANDIDATES:
            raise PromptRegistryIntegrityError(
                f"PROMPT_COUNT_EXCEEDS_MAX: registered {len(self.prompts)} prompts, maximum allowed is {MAX_PROMPT_CANDIDATES}."
            )
        ids = [p.prompt_id for p in self.prompts]
        if len(set(ids)) != len(ids):
            raise PromptRegistryIntegrityError(f"Duplicate prompt_id in PromptRegistry: {ids}")
        if len(ids) == 1 and ids[0] != "P1":
            raise PromptRegistryIntegrityError(
                f"When registering a single prompt, prompt_id must be 'P1' (got {ids[0]!r})."
            )
        if len(ids) == 2 and ids != ["P1", "P2"]:
            raise PromptRegistryIntegrityError(
                f"Two-prompt registry must be ordered ['P1', 'P2'] (got {ids})."
            )
        return self


def build_prompt_registry(prompts: Sequence[PromptCandidateSpec]) -> PromptRegistry:
    """Construct a validated PromptRegistry and compute its deterministic SHA256."""
    prompt_list = list(prompts)
    reg_sha = sha256_bytes(canonical_json_bytes([p.model_dump() for p in prompt_list]))
    return PromptRegistry(
        prompts=prompt_list,
        max_allowed_prompts=MAX_PROMPT_CANDIDATES,
        registry_sha256=reg_sha,
    )


def build_default_infrastructure_prompt_registry() -> PromptRegistry:
    """Build the default 1-prompt (P1) infrastructure registry using the existing benchmark template."""
    p1 = create_prompt_candidate_spec(
        prompt_id="P1",
        prompt_version=BENCHMARK_PROMPT_VERSION,
        system_prompt=PREFLIGHT_SHARED_SYSTEM_PROMPT,
        user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
        created_before_live_dev_execution=True,
    )
    return build_prompt_registry([p1])


class DeterministicScenarioContext(BaseModel):
    """Deterministic scenario -> model context artifact for a single DEV fixture and prompt (Section 8)."""

    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    partition: Literal["DEV_TUNE", "DEV_SELECT"]
    prompt_id: str
    prompt_version: str
    destination_slug: str
    catalog_poi_count: int
    system_prompt: str
    user_prompt: str
    scenario_sha256: str
    catalog_context_sha256: str
    source_catalog_sha256: str
    system_prompt_sha256: str
    user_prompt_sha256: str
    semantic_prompt_sha256: str
    semantic_schema_sha256: str
    portable_generation_schema_v2_sha256: str


def render_user_prompt_from_template(
    *,
    scenario: BenchmarkScenarioInput,
    catalog_pois: Sequence[BenchmarkCatalogPOI],
    prompt_spec: PromptCandidateSpec,
) -> str:
    """Deterministically format user_prompt_template for a verified DEV scenario and REC-A catalog context."""
    assert_not_final100_scenario(scenario)
    validate_canonical_interests_list(scenario.interests)
    if not catalog_pois:
        raise ValueError(f"Empty catalog_pois for destination_slug={scenario.destination_slug!r}")

    catalog_serializable = [poi.model_dump() for poi in catalog_pois]
    catalog_json = json.dumps(catalog_serializable, ensure_ascii=False, indent=2)

    interests_vi = ", ".join(CANONICAL_INTEREST_LABELS_VI[i] for i in scenario.interests)
    interests_json = json.dumps(scenario.interests, ensure_ascii=False)
    budget_formatted = (
        f"{scenario.budget:,.0f}" if scenario.budget is not None else "Không giới hạn"
    )
    allow_revisit_policy = (
        "true (cho phép lặp lại place_id nếu cần)"
        if scenario.allow_revisit_place_ids
        else "false (TUYỆT ĐỐI KHÔNG lặp lại cùng một place_id trong lịch trình)"
    )
    additional_notes = (
        f"- Ghi chú kịch bản (notes): {scenario.notes}" if scenario.notes else ""
    )

    return prompt_spec.user_prompt_template.format(
        prompt_version=prompt_spec.prompt_version,
        scenario_id=scenario.scenario_id,
        destination=scenario.destination,
        destination_slug=scenario.destination_slug,
        days=scenario.days,
        start_date=scenario.start_date,
        end_date=scenario.end_date,
        budget_formatted=budget_formatted,
        currency=scenario.currency,
        travel_style=scenario.travel_style,
        canonical_interests_json=interests_json,
        canonical_interests_vi=interests_vi,
        allow_revisit_policy=allow_revisit_policy,
        additional_notes=additional_notes,
        catalog_count=len(catalog_pois),
        catalog_json=catalog_json,
    )


def build_deterministic_dev_scenario_context(
    scenario: BenchmarkScenarioInput,
    prompt_spec: PromptCandidateSpec,
    *,
    catalog_path: Optional[Path] = None,
    preloaded_catalog_by_dest: Optional[Dict[str, List[BenchmarkCatalogPOI]]] = None,
) -> DeterministicScenarioContext:
    """Build deterministic scenario -> model context for a DEV fixture without any LLM or provider-specific logic."""
    assert_not_final100_scenario(scenario)
    partition: Literal["DEV_TUNE", "DEV_SELECT"] = (
        "DEV_TUNE" if scenario.fixture_label == "W06_DEV_TUNE" else "DEV_SELECT"
    )

    if (
        preloaded_catalog_by_dest is not None
        and scenario.destination_slug in preloaded_catalog_by_dest
    ):
        pois = preloaded_catalog_by_dest[scenario.destination_slug]
    else:
        pois = build_destination_catalog_context(
            scenario.destination_slug,
            catalog_path=catalog_path,
        )

    user_prompt = render_user_prompt_from_template(
        scenario=scenario,
        catalog_pois=pois,
        prompt_spec=prompt_spec,
    )
    system_prompt = prompt_spec.system_prompt

    scenario_sha = sha256_bytes(canonical_json_bytes(scenario.model_dump()))
    catalog_context_sha = sha256_bytes(
        canonical_json_bytes([p.model_dump() for p in pois])
    )
    source_catalog_sha = compute_catalog_sha256(catalog_path=catalog_path)
    sys_prompt_sha = sha256_bytes(normalize_lf_bytes(system_prompt.encode("utf-8")))
    usr_prompt_sha = sha256_bytes(normalize_lf_bytes(user_prompt.encode("utf-8")))

    return DeterministicScenarioContext(
        fixture_id=scenario.scenario_id,
        partition=partition,
        prompt_id=prompt_spec.prompt_id,
        prompt_version=prompt_spec.prompt_version,
        destination_slug=scenario.destination_slug,
        catalog_poi_count=len(pois),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        scenario_sha256=scenario_sha,
        catalog_context_sha256=catalog_context_sha,
        source_catalog_sha256=source_catalog_sha,
        system_prompt_sha256=sys_prompt_sha,
        user_prompt_sha256=usr_prompt_sha,
        semantic_prompt_sha256=prompt_spec.semantic_prompt_sha256,
        semantic_schema_sha256=EXPECTED_SEMANTIC_SCHEMA_SHA256,
        portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    )


_CACHED_PROVIDER_CONFIG_SHAS: Dict[str, str] = {}


def compute_candidate_provider_config_sha256(spec: DevCandidateSpec) -> str:
    """Compute deterministic canonical SHA256 for a candidate's provider configuration payload."""
    payload = {
        "candidate_id": spec.candidate_id,
        "provider": spec.provider,
        "requested_model_id": spec.requested_model_id,
        "portable_generation_schema_v2_sha256": spec.portable_generation_schema_v2_sha256,
        "structured_output_wiring": spec.structured_output_wiring,
        "sampling_reasoning_config": spec.sampling_reasoning_config,
        "omitted_parameters": spec.omitted_parameters,
        "max_output_tokens": spec.max_output_tokens,
        "timeout_ms": spec.timeout_ms,
    }
    return sha256_bytes(canonical_json_bytes(payload))


def get_cached_provider_config_sha256(candidate_id: str) -> str:
    """Return deterministic provider_config_sha256 for a frozen candidate_id (C1, C2, C3)."""
    if candidate_id not in _CACHED_PROVIDER_CONFIG_SHAS:
        reg = load_and_verify_candidate_registry()
        for cid, spec in reg.candidates.items():
            _CACHED_PROVIDER_CONFIG_SHAS[cid] = compute_candidate_provider_config_sha256(spec)
    if candidate_id not in _CACHED_PROVIDER_CONFIG_SHAS:
        raise CandidateRegistryIntegrityError(f"Unknown candidate_id: {candidate_id!r}")
    return _CACHED_PROVIDER_CONFIG_SHAS[candidate_id]


def compute_provider_config_registry_sha256(
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> str:
    """Compute canonical SHA256 over the 3-candidate provider configuration registry."""
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    provider_config_payload = {
        cid: {
            "provider": spec.provider,
            "requested_model_id": spec.requested_model_id,
            "sampling_reasoning_config": spec.sampling_reasoning_config,
            "omitted_parameters": spec.omitted_parameters,
            "max_output_tokens": spec.max_output_tokens,
            "timeout_ms": spec.timeout_ms,
            "portable_generation_schema_v2_sha256": spec.portable_generation_schema_v2_sha256,
        }
        for cid, spec in sorted(cand_reg.candidates.items())
    }
    return sha256_bytes(canonical_json_bytes(provider_config_payload))


def _normalize_code_basis_provenance_fields(
    d: Dict[str, Any],
    *,
    error_cls: type[Exception] = CodeCommitProvenanceError,
) -> None:
    """Synchronize code_basis_commit_sha and backward-compatible code_commit_sha on a raw payload dict."""
    has_basis = "code_basis_commit_sha" in d
    has_legacy = "code_commit_sha" in d
    if not has_basis and not has_legacy:
        resolved = resolve_active_git_commit_sha()
        d["code_basis_commit_sha"] = resolved
        d["code_commit_sha"] = resolved
        return
    if has_basis and not has_legacy:
        val = d["code_basis_commit_sha"]
        if val is None or not isinstance(val, str):
            raise error_cls(
                "code_basis_commit_sha is required and must be a 40-character lowercase hex git SHA."
            )
        d["code_commit_sha"] = val
        return
    if has_legacy and not has_basis:
        val = d["code_commit_sha"]
        if val is None or not isinstance(val, str):
            raise error_cls(
                "code_commit_sha is required and must be a 40-character lowercase hex git SHA."
            )
        d["code_basis_commit_sha"] = val
        return
    basis_val = d["code_basis_commit_sha"]
    legacy_val = d["code_commit_sha"]
    if (
        basis_val is None
        or not isinstance(basis_val, str)
        or legacy_val is None
        or not isinstance(legacy_val, str)
    ):
        raise error_cls(
            "code_basis_commit_sha and code_commit_sha must be 40-character lowercase hex git SHAs."
        )
    if basis_val != legacy_val:
        raise error_cls(
            f"CODE_COMMIT_SHA_MISMATCH: Conflicting code_basis_commit_sha {basis_val!r} "
            f"and code_commit_sha {legacy_val!r}."
        )


def _resolve_plan_creation_code_basis_sha(
    *,
    code_basis_commit_sha: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> str:
    """Resolve and verify active git HEAD at plan creation boundary."""
    if (
        code_basis_commit_sha is not None
        and code_commit_sha is not None
        and code_basis_commit_sha != code_commit_sha
    ):
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_SHA_MISMATCH: Conflicting code_basis_commit_sha {code_basis_commit_sha!r} "
            f"and code_commit_sha {code_commit_sha!r}."
        )
    supplied = code_basis_commit_sha if code_basis_commit_sha is not None else code_commit_sha
    return resolve_and_verify_code_commit_sha(supplied, repo_root=repo_root)


class DevCellExecutionManifest(BaseModel):
    """Machine-readable execution manifest for a single cell (Section 9 & Fix Group I / Audit Correction 02)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    phase: Literal["DEV_TUNE", "DEV_SELECT", "STOCHASTICITY_DIAGNOSTIC"]
    fixture_id: str
    candidate_id: str
    prompt_id: str
    requested_model_id: str

    code_basis_commit_sha: str
    code_commit_sha: str
    scientific_code_bundle_sha256: str
    provider_config_sha256: str
    scenario_sha256: str
    catalog_context_sha256: str
    system_prompt_sha256: str
    user_prompt_sha256: str
    semantic_schema_sha256: str
    portable_generation_schema_v2_sha256: str

    sampling_reasoning_configuration: Dict[str, Any]
    max_output_tokens: int = FROZEN_MAX_OUTPUT_TOKENS
    timeout_ms: int = FROZEN_TIMEOUT_MS

    retry: int = 0
    automatic_retry: int = 0
    transport_retry: int = 0
    manual_retry: int = 0
    fallback: bool = False
    repair: int = 0
    llm_repair: int = 0
    deterministic_semantic_repair: bool = False
    tools: bool = False
    attempt_number: int = 1

    @model_validator(mode="before")
    @classmethod
    def _populate_manifest_provenance(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        _normalize_code_basis_provenance_fields(d, error_cls=CodeCommitProvenanceError)
        if "scientific_code_bundle_sha256" not in d:
            d["scientific_code_bundle_sha256"] = compute_scientific_code_bundle_sha256()
        elif d["scientific_code_bundle_sha256"] is None or not isinstance(
            d["scientific_code_bundle_sha256"], str
        ):
            raise ValueError(
                "scientific_code_bundle_sha256 is required and must be a 64-character lowercase hex SHA256."
            )
        if "provider_config_sha256" not in d:
            cid = d.get("candidate_id")
            if cid in ORDERED_CANDIDATE_IDS:
                d["provider_config_sha256"] = get_cached_provider_config_sha256(str(cid))
        elif d["provider_config_sha256"] is None or not isinstance(
            d["provider_config_sha256"], str
        ):
            raise ValueError(
                "provider_config_sha256 is required and must be a 64-character lowercase hex SHA256."
            )
        return d

    @model_validator(mode="after")
    def _validate_manifest_invariants(self) -> "DevCellExecutionManifest":
        assert_not_final100_scenario_id(self.fixture_id)
        if self.candidate_id not in ORDERED_CANDIDATE_IDS:
            raise CandidateRegistryIntegrityError(f"Invalid candidate_id: {self.candidate_id}")
        if self.prompt_id not in ALLOWED_PROMPT_IDS:
            raise PromptRegistryIntegrityError(f"Invalid prompt_id: {self.prompt_id}")
        validate_git_commit_sha40(self.code_basis_commit_sha)
        validate_git_commit_sha40(self.code_commit_sha)
        if self.code_basis_commit_sha != self.code_commit_sha:
            raise CodeCommitProvenanceError(
                f"CODE_COMMIT_SHA_MISMATCH: code_basis_commit_sha {self.code_basis_commit_sha!r} "
                f"!= code_commit_sha {self.code_commit_sha!r}"
            )
        validate_sha256_hex64(
            self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
        )
        validate_sha256_hex64(self.provider_config_sha256, "provider_config_sha256")
        expected_pconf_sha = get_cached_provider_config_sha256(self.candidate_id)
        if self.provider_config_sha256 != expected_pconf_sha:
            raise ValueError(
                f"provider_config_sha256 mismatch for {self.candidate_id}: "
                f"expected={expected_pconf_sha}, got={self.provider_config_sha256}"
            )
        if (
            self.retry != 0
            or self.automatic_retry != 0
            or self.transport_retry != 0
            or self.manual_retry != 0
            or self.fallback is not False
            or self.repair != 0
            or self.llm_repair != 0
            or self.deterministic_semantic_repair is not False
            or self.tools is not False
        ):
            raise ValueError(
                "Manifest violates retry=0 / fallback=false / repair=0 / tools=false invariants."
            )
        if self.phase in ("DEV_TUNE", "DEV_SELECT") and self.attempt_number != 1:
            raise ValueError(
                f"DEV_TUNE and DEV_SELECT require attempt_number == 1 (got {self.attempt_number})."
            )
        if self.phase == "STOCHASTICITY_DIAGNOSTIC" and self.attempt_number not in (1, 2, 3):
            raise ValueError(
                f"STOCHASTICITY_DIAGNOSTIC requires attempt_number in (1, 2, 3) (got {self.attempt_number})."
            )
        if self.portable_generation_schema_v2_sha256 != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
            raise ValueError("Manifest portable_generation_schema_v2_sha256 mismatch.")
        return self


def create_synthetic_test_only_cell_manifest(**kwargs: Any) -> DevCellExecutionManifest:
    """Explicit test-only constructor for synthetic unit tests (Audit Correction 02 / Section 11).

    Does not use any hidden ContextVar bypass; DevCellExecutionManifest is natively historical-safe.
    """
    d = dict(kwargs)
    if "code_commit_sha" in d and "code_basis_commit_sha" in d:
        d["code_basis_commit_sha"] = d["code_commit_sha"]
    return DevCellExecutionManifest(**d)


def calculate_expected_dev_tune_cell_count(
    prompt_count: int,
    *,
    candidate_count: int = 3,
    fixture_count: int = DEV_TUNE_COUNT,
) -> int:
    """Calculate expected DEV-TUNE cell count (60 for 1 prompt, 120 for 2 prompts; Section 16)."""
    if prompt_count < 1 or prompt_count > MAX_PROMPT_CANDIDATES:
        raise PromptRegistryIntegrityError(
            f"DEV-TUNE prompt_count must be 1 or 2 (got {prompt_count})."
        )
    if candidate_count != 3:
        raise CandidateRegistryIntegrityError(
            f"DEV-TUNE candidate_count must be 3 (got {candidate_count})."
        )
    if fixture_count != DEV_TUNE_COUNT:
        raise ValueError(f"DEV-TUNE fixture_count must be {DEV_TUNE_COUNT} (got {fixture_count}).")
    total = fixture_count * candidate_count * prompt_count
    if total not in (DEV_TUNE_MAX_CALLS_ONE_PROMPT, DEV_TUNE_MAX_CALLS_TWO_PROMPTS):
        raise ValueError(f"Unexpected DEV-TUNE cell count: {total}")
    return total


def calculate_expected_dev_select_cell_count(
    *,
    locked_prompt_count: int = 1,
    candidate_count: int = 3,
    fixture_count: int = DEV_SELECT_COUNT,
) -> int:
    """Calculate expected DEV-SELECT cell count (60 fixtures × 3 candidates × 1 locked prompt = 180; Section 17)."""
    if locked_prompt_count != 1:
        raise PromptRegistryIntegrityError(
            f"DEV-SELECT requires exactly 1 locked prompt (got {locked_prompt_count})."
        )
    if candidate_count != 3:
        raise CandidateRegistryIntegrityError(
            f"DEV-SELECT candidate_count must be 3 (got {candidate_count})."
        )
    if fixture_count != DEV_SELECT_COUNT:
        raise ValueError(
            f"DEV-SELECT fixture_count must be {DEV_SELECT_COUNT} (got {fixture_count})."
        )
    return fixture_count * candidate_count


class DevExecutionPlan(BaseModel):
    """Deterministic offline execution plan for DEV-TUNE or DEV-SELECT (Audit Correction 02 / Section 8)."""

    model_config = ConfigDict(extra="forbid")

    phase: Literal["DEV_TUNE", "DEV_SELECT"]
    prompt_ids: List[str]
    candidate_ids: List[str]
    fixture_count: int
    expected_total_cells: int
    code_basis_commit_sha: str
    code_commit_sha: str
    scientific_code_bundle_sha256: str
    scientific_code_bundle_file_hashes: List[Dict[str, str]] = Field(default_factory=list)
    cells: List[DevCellExecutionManifest]
    plan_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _populate_plan_provenance(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        cells_raw = d.get("cells") or []
        first_cell = cells_raw[0] if cells_raw else None
        if "code_basis_commit_sha" not in d and "code_commit_sha" not in d and first_cell is not None:
            if isinstance(first_cell, dict):
                c_sha = first_cell.get("code_basis_commit_sha") or first_cell.get("code_commit_sha")
            else:
                c_sha = getattr(first_cell, "code_basis_commit_sha", None) or getattr(
                    first_cell, "code_commit_sha", None
                )
            if c_sha is not None:
                d["code_basis_commit_sha"] = c_sha
                d["code_commit_sha"] = c_sha
        _normalize_code_basis_provenance_fields(d, error_cls=CodeCommitProvenanceError)
        if "scientific_code_bundle_sha256" not in d:
            if first_cell is not None:
                c_bsha = (
                    first_cell.get("scientific_code_bundle_sha256")
                    if isinstance(first_cell, dict)
                    else getattr(first_cell, "scientific_code_bundle_sha256", None)
                )
                d["scientific_code_bundle_sha256"] = (
                    c_bsha if c_bsha is not None else compute_scientific_code_bundle_sha256()
                )
            else:
                d["scientific_code_bundle_sha256"] = compute_scientific_code_bundle_sha256()
        if "scientific_code_bundle_file_hashes" not in d:
            current_bundle = compute_scientific_code_bundle()
            if (
                d.get("scientific_code_bundle_sha256")
                == current_bundle.scientific_code_bundle_sha256
            ):
                d["scientific_code_bundle_file_hashes"] = [
                    dict(entry) for entry in current_bundle.scientific_code_bundle_file_hashes
                ]
            else:
                d["scientific_code_bundle_file_hashes"] = []
        return d

    @model_validator(mode="after")
    def _validate_plan_size_and_provenance(self) -> "DevExecutionPlan":
        validate_git_commit_sha40(self.code_basis_commit_sha)
        validate_git_commit_sha40(self.code_commit_sha)
        if self.code_basis_commit_sha != self.code_commit_sha:
            raise CodeCommitProvenanceError(
                f"CODE_COMMIT_SHA_MISMATCH: Plan code_basis_commit_sha {self.code_basis_commit_sha!r} "
                f"!= code_commit_sha {self.code_commit_sha!r}"
            )
        validate_sha256_hex64(
            self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
        )
        if self.scientific_code_bundle_file_hashes:
            ScientificCodeBundleManifest(
                scientific_code_bundle_sha256=self.scientific_code_bundle_sha256,
                scientific_code_bundle_file_hashes=self.scientific_code_bundle_file_hashes,
            )
        if len(self.cells) != self.expected_total_cells:
            raise ValueError(
                f"Execution plan cell count {len(self.cells)} != expected {self.expected_total_cells}"
            )
        seen_keys = set()
        for cell in self.cells:
            key = (cell.phase, cell.prompt_id, cell.candidate_id, cell.fixture_id)
            if key in seen_keys:
                raise ValueError(f"Duplicate cell in execution plan: {key}")
            seen_keys.add(key)
            if cell.code_basis_commit_sha != self.code_basis_commit_sha:
                raise CodeCommitProvenanceError(
                    f"CODE_COMMIT_SHA_MISMATCH: Cell {cell.run_id} code_basis_commit_sha "
                    f"{cell.code_basis_commit_sha!r} != plan {self.code_basis_commit_sha!r}"
                )
            if cell.scientific_code_bundle_sha256 != self.scientific_code_bundle_sha256:
                raise ScientificCodeBundleIntegrityError(
                    f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Cell {cell.run_id} bundle sha256 "
                    f"{cell.scientific_code_bundle_sha256!r} != plan {self.scientific_code_bundle_sha256!r}"
                )
        return self


def verify_cell_manifest_for_execution(
    cell_manifest: DevCellExecutionManifest,
    *,
    repo_root: Optional[Path] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> str:
    """Verify a frozen cell manifest at the execution action boundary (Sections 6, 8, 10).

    Allows cell_manifest.code_basis_commit_sha to be a historical commit A while active git HEAD is B,
    ONLY IF the current scientific code bundle SHA256 and provider config SHA256 match the frozen manifest.
    Returns the active runtime_head_sha (B).
    """
    runtime_head_sha = resolve_active_git_commit_sha(repo_root=repo_root)
    validate_git_commit_sha40(cell_manifest.code_basis_commit_sha)
    validate_git_commit_sha40(cell_manifest.code_commit_sha)
    if cell_manifest.code_basis_commit_sha != cell_manifest.code_commit_sha:
        raise CodeCommitProvenanceError(
            f"CODE_COMMIT_SHA_MISMATCH: Manifest {cell_manifest.run_id} has conflicting "
            f"code_basis_commit_sha {cell_manifest.code_basis_commit_sha!r} and code_commit_sha {cell_manifest.code_commit_sha!r}"
        )

    current_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if cell_manifest.scientific_code_bundle_sha256 != current_bundle_sha:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH on cell {cell_manifest.run_id}: "
            f"frozen scientific_code_bundle_sha256={cell_manifest.scientific_code_bundle_sha256} "
            f"(code_basis_commit_sha={cell_manifest.code_basis_commit_sha}) does not match "
            f"current runtime scientific_code_bundle_sha256={current_bundle_sha} "
            f"(runtime_head_sha={runtime_head_sha}). Batch must stop before any provider call."
        )

    if candidate_registry is not None:
        if cell_manifest.candidate_id not in candidate_registry.candidates:
            raise CandidateRegistryIntegrityError(
                f"Unknown candidate_id {cell_manifest.candidate_id!r} in cell {cell_manifest.run_id}"
            )
        expected_pconf_sha = compute_candidate_provider_config_sha256(
            candidate_registry.candidates[cell_manifest.candidate_id]
        )
    else:
        expected_pconf_sha = get_cached_provider_config_sha256(cell_manifest.candidate_id)

    if cell_manifest.provider_config_sha256 != expected_pconf_sha:
        raise CandidateRegistryIntegrityError(
            f"PROVIDER_CONFIG_SHA256_MISMATCH on cell {cell_manifest.run_id} "
            f"(candidate={cell_manifest.candidate_id}): "
            f"expected={expected_pconf_sha}, got={cell_manifest.provider_config_sha256}"
        )
    return runtime_head_sha


def verify_dev_execution_plan_for_execution(
    execution_plan: DevExecutionPlan,
    *,
    repo_root: Optional[Path] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> str:
    """Verify an entire DevExecutionPlan at the execution action boundary (Sections 6, 8, 10).

    Succeeds when plan was created at commit A and is verified/executed at commit B if and only if
    the scientific code bundle and provider configurations are unchanged.
    Returns the active runtime_head_sha (B).
    """
    runtime_head_sha = resolve_active_git_commit_sha(repo_root=repo_root)
    validate_git_commit_sha40(execution_plan.code_basis_commit_sha)
    current_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    if (
        execution_plan.scientific_code_bundle_sha256
        != current_bundle.scientific_code_bundle_sha256
    ):
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Plan frozen scientific_code_bundle_sha256="
            f"{execution_plan.scientific_code_bundle_sha256} (code_basis_commit_sha="
            f"{execution_plan.code_basis_commit_sha}) does not match current runtime bundle "
            f"{current_bundle.scientific_code_bundle_sha256} (runtime_head_sha={runtime_head_sha})."
        )
    if (
        execution_plan.scientific_code_bundle_file_hashes
        and execution_plan.scientific_code_bundle_file_hashes
        != current_bundle.scientific_code_bundle_file_hashes
    ):
        raise ScientificCodeBundleIntegrityError(
            "SCIENTIFIC_CODE_BUNDLE_MISMATCH: Plan scientific_code_bundle_file_hashes "
            "do not match current runtime scientific source files."
        )

    for cell in execution_plan.cells:
        verify_cell_manifest_for_execution(
            cell,
            repo_root=repo_root,
            candidate_registry=candidate_registry,
        )

    computed_plan_sha = sha256_bytes(
        canonical_json_bytes([c.model_dump() for c in execution_plan.cells])
    )
    if execution_plan.plan_sha256 != computed_plan_sha:
        raise CandidateRegistryIntegrityError(
            f"EXECUTION_PLAN_SHA256_MISMATCH: plan_sha256={execution_plan.plan_sha256} "
            f"!= computed={computed_plan_sha}"
        )
    return runtime_head_sha


def build_dev_tune_execution_plan(
    prompt_registry: PromptRegistry,
    *,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
    code_basis_commit_sha: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> DevExecutionPlan:
    """Build deterministic DEV-TUNE execution plan (60 cells for 1 prompt, 120 cells for 2 prompts)."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    active_sha = _resolve_plan_creation_code_basis_sha(
        code_basis_commit_sha=code_basis_commit_sha,
        code_commit_sha=code_commit_sha,
        repo_root=repo_root,
    )
    code_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    expected_cells = calculate_expected_dev_tune_cell_count(
        len(prompt_registry.prompts),
        candidate_count=len(cand_reg.ordered_candidate_ids),
        fixture_count=len(bundle.dev_tune_fixtures),
    )

    preloaded_catalog = {
        slug: build_destination_catalog_context(slug, catalog_path=catalog_path)
        for slug in ("ha-noi", "da-nang", "ha-long")
    }

    cells: List[DevCellExecutionManifest] = []
    for prompt_spec in prompt_registry.prompts:
        for scenario in bundle.dev_tune_fixtures:
            ctx = build_deterministic_dev_scenario_context(
                scenario,
                prompt_spec,
                catalog_path=catalog_path,
                preloaded_catalog_by_dest=preloaded_catalog,
            )
            for cid in cand_reg.ordered_candidate_ids:
                cspec = cand_reg.candidates[cid]
                pconf_sha = compute_candidate_provider_config_sha256(cspec)
                run_id = f"W06-DEV-TUNE-{prompt_spec.prompt_id}-{cid}-{scenario.scenario_id}"
                cells.append(
                    DevCellExecutionManifest(
                        run_id=run_id,
                        phase="DEV_TUNE",
                        fixture_id=scenario.scenario_id,
                        candidate_id=cid,
                        prompt_id=prompt_spec.prompt_id,
                        requested_model_id=cspec.requested_model_id,
                        code_basis_commit_sha=active_sha,
                        code_commit_sha=active_sha,
                        scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
                        provider_config_sha256=pconf_sha,
                        scenario_sha256=ctx.scenario_sha256,
                        catalog_context_sha256=ctx.catalog_context_sha256,
                        system_prompt_sha256=ctx.system_prompt_sha256,
                        user_prompt_sha256=ctx.user_prompt_sha256,
                        semantic_schema_sha256=ctx.semantic_schema_sha256,
                        portable_generation_schema_v2_sha256=ctx.portable_generation_schema_v2_sha256,
                        sampling_reasoning_configuration=cspec.sampling_reasoning_config,
                        max_output_tokens=cspec.max_output_tokens,
                        timeout_ms=cspec.timeout_ms,
                        attempt_number=1,
                    )
                )

    plan_sha = sha256_bytes(canonical_json_bytes([c.model_dump() for c in cells]))
    return DevExecutionPlan(
        phase="DEV_TUNE",
        prompt_ids=[p.prompt_id for p in prompt_registry.prompts],
        candidate_ids=list(cand_reg.ordered_candidate_ids),
        fixture_count=len(bundle.dev_tune_fixtures),
        expected_total_cells=expected_cells,
        code_basis_commit_sha=active_sha,
        code_commit_sha=active_sha,
        scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
        scientific_code_bundle_file_hashes=code_bundle.scientific_code_bundle_file_hashes,
        cells=cells,
        plan_sha256=plan_sha,
    )


def build_dev_select_execution_plan(
    locked_prompt_spec: PromptCandidateSpec,
    *,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
    code_basis_commit_sha: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> DevExecutionPlan:
    """Build deterministic DEV-SELECT execution plan (60 fixtures × 3 candidates = 180 cells)."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    active_sha = _resolve_plan_creation_code_basis_sha(
        code_basis_commit_sha=code_basis_commit_sha,
        code_commit_sha=code_commit_sha,
        repo_root=repo_root,
    )
    code_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    expected_cells = calculate_expected_dev_select_cell_count(
        locked_prompt_count=1,
        candidate_count=len(cand_reg.ordered_candidate_ids),
        fixture_count=len(bundle.dev_select_fixtures),
    )

    preloaded_catalog = {
        slug: build_destination_catalog_context(slug, catalog_path=catalog_path)
        for slug in ("ha-noi", "da-nang", "ha-long")
    }

    cells: List[DevCellExecutionManifest] = []
    for scenario in bundle.dev_select_fixtures:
        ctx = build_deterministic_dev_scenario_context(
            scenario,
            locked_prompt_spec,
            catalog_path=catalog_path,
            preloaded_catalog_by_dest=preloaded_catalog,
        )
        for cid in cand_reg.ordered_candidate_ids:
            cspec = cand_reg.candidates[cid]
            pconf_sha = compute_candidate_provider_config_sha256(cspec)
            run_id = f"W06-DEV-SELECT-{locked_prompt_spec.prompt_id}-{cid}-{scenario.scenario_id}"
            cells.append(
                DevCellExecutionManifest(
                    run_id=run_id,
                    phase="DEV_SELECT",
                    fixture_id=scenario.scenario_id,
                    candidate_id=cid,
                    prompt_id=locked_prompt_spec.prompt_id,
                    requested_model_id=cspec.requested_model_id,
                    code_basis_commit_sha=active_sha,
                    code_commit_sha=active_sha,
                    scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
                    provider_config_sha256=pconf_sha,
                    scenario_sha256=ctx.scenario_sha256,
                    catalog_context_sha256=ctx.catalog_context_sha256,
                    system_prompt_sha256=ctx.system_prompt_sha256,
                    user_prompt_sha256=ctx.user_prompt_sha256,
                    semantic_schema_sha256=ctx.semantic_schema_sha256,
                    portable_generation_schema_v2_sha256=ctx.portable_generation_schema_v2_sha256,
                    sampling_reasoning_configuration=cspec.sampling_reasoning_config,
                    max_output_tokens=cspec.max_output_tokens,
                    timeout_ms=cspec.timeout_ms,
                    attempt_number=1,
                )
            )

    plan_sha = sha256_bytes(canonical_json_bytes([c.model_dump() for c in cells]))
    return DevExecutionPlan(
        phase="DEV_SELECT",
        prompt_ids=[locked_prompt_spec.prompt_id],
        candidate_ids=list(cand_reg.ordered_candidate_ids),
        fixture_count=len(bundle.dev_select_fixtures),
        expected_total_cells=expected_cells,
        code_basis_commit_sha=active_sha,
        code_commit_sha=active_sha,
        scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
        scientific_code_bundle_file_hashes=code_bundle.scientific_code_bundle_file_hashes,
        cells=cells,
        plan_sha256=plan_sha,
    )


class DevPromptFreezeArtifact(BaseModel):
    """Contract for the separate future frozen prompt artifact required before any live DEV-TUNE execution (Section 11 / Fix Group H / Audit Correction 02)."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    prompt_candidate_ids: List[str]
    prompt_versions: Dict[str, str]
    system_prompt_by_id: Dict[str, str]
    system_prompt_sha256_by_id: Dict[str, str]
    user_prompt_template_by_id: Dict[str, str]
    user_prompt_template_sha256_by_id: Dict[str, str]
    semantic_prompt_sha256_by_id: Dict[str, str]
    created_before_live_dev_execution: bool
    candidate_registry_sha256: str
    ordered_candidate_ids: List[str] = Field(default_factory=lambda: list(ORDERED_CANDIDATE_IDS))
    portable_generation_schema_v2_sha256: str
    dev_tune_bundle_sha256: str
    dev_tune_execution_plan_sha256: str
    max_call_budget: int
    code_basis_commit_sha: str
    code_commit_sha: str
    scientific_code_bundle_sha256: str
    scientific_code_bundle_file_hashes: List[Dict[str, str]] = Field(default_factory=list)
    provider_config_registry_sha256: str
    freeze_status: str

    @model_validator(mode="before")
    @classmethod
    def _populate_freeze_provenance(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        _normalize_code_basis_provenance_fields(d, error_cls=PromptFreezeFirewallError)
        if "scientific_code_bundle_sha256" not in d:
            d["scientific_code_bundle_sha256"] = compute_scientific_code_bundle_sha256()
        if "scientific_code_bundle_file_hashes" not in d:
            current_bundle = compute_scientific_code_bundle()
            if (
                d.get("scientific_code_bundle_sha256")
                == current_bundle.scientific_code_bundle_sha256
            ):
                d["scientific_code_bundle_file_hashes"] = [
                    dict(entry) for entry in current_bundle.scientific_code_bundle_file_hashes
                ]
            else:
                d["scientific_code_bundle_file_hashes"] = []
        return d

    @model_validator(mode="after")
    def _validate_freeze_contract(self) -> "DevPromptFreezeArtifact":
        if not self.created_before_live_dev_execution:
            raise PromptFreezeFirewallError(
                "Prompt freeze artifact must have created_before_live_dev_execution=True."
            )
        if self.freeze_status != "FROZEN_FOR_LIVE_DEV_TUNE":
            raise PromptFreezeFirewallError(
                f"Prompt freeze artifact freeze_status must be 'FROZEN_FOR_LIVE_DEV_TUNE', got {self.freeze_status!r}."
            )
        if not (1 <= len(self.prompt_candidate_ids) <= MAX_PROMPT_CANDIDATES):
            raise PromptFreezeFirewallError(
                f"prompt_candidate_ids must have length 1 or 2, got {self.prompt_candidate_ids!r}."
            )
        try:
            validate_git_commit_sha40(self.code_basis_commit_sha)
            validate_git_commit_sha40(self.code_commit_sha)
            if self.code_basis_commit_sha != self.code_commit_sha:
                raise PromptFreezeFirewallError(
                    f"CODE_COMMIT_SHA_MISMATCH: code_basis_commit_sha {self.code_basis_commit_sha!r} "
                    f"!= code_commit_sha {self.code_commit_sha!r}"
                )
            validate_sha256_hex64(
                self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
            )
            validate_sha256_hex64(
                self.provider_config_registry_sha256, "provider_config_registry_sha256"
            )
            if self.scientific_code_bundle_file_hashes:
                ScientificCodeBundleManifest(
                    scientific_code_bundle_sha256=self.scientific_code_bundle_sha256,
                    scientific_code_bundle_file_hashes=self.scientific_code_bundle_file_hashes,
                )
        except PromptFreezeFirewallError:
            raise
        except Exception as exc:
            raise PromptFreezeFirewallError(str(exc)) from exc
        if self.portable_generation_schema_v2_sha256 != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
            raise PromptFreezeFirewallError(
                "Prompt freeze artifact portable_generation_schema_v2_sha256 mismatch."
            )
        return self


def build_dev_prompt_freeze_artifact(
    *,
    prompt_registry: PromptRegistry,
    dev_tune_plan: DevExecutionPlan,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    code_basis_commit_sha: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
    artifact_id: str = "W06-DEV-PROMPT-FREEZE-V1",
    version: str = "1.0.0",
) -> DevPromptFreezeArtifact:
    """Build a valid DevPromptFreezeArtifact for offline verification or a future prompt-freeze gate."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    if code_basis_commit_sha is not None or code_commit_sha is not None:
        basis_sha = _resolve_plan_creation_code_basis_sha(
            code_basis_commit_sha=code_basis_commit_sha,
            code_commit_sha=code_commit_sha,
            repo_root=repo_root,
        )
    else:
        verify_dev_execution_plan_for_execution(
            dev_tune_plan, repo_root=repo_root, candidate_registry=cand_reg
        )
        basis_sha = dev_tune_plan.code_basis_commit_sha

    code_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    if (
        dev_tune_plan.scientific_code_bundle_sha256
        != code_bundle.scientific_code_bundle_sha256
    ):
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: dev_tune_plan bundle "
            f"{dev_tune_plan.scientific_code_bundle_sha256} != current bundle "
            f"{code_bundle.scientific_code_bundle_sha256}"
        )

    pids = [p.prompt_id for p in prompt_registry.prompts]
    return DevPromptFreezeArtifact(
        artifact_id=artifact_id,
        version=version,
        prompt_candidate_ids=pids,
        prompt_versions={p.prompt_id: p.prompt_version for p in prompt_registry.prompts},
        system_prompt_by_id={p.prompt_id: p.system_prompt for p in prompt_registry.prompts},
        system_prompt_sha256_by_id={
            p.prompt_id: sha256_bytes(normalize_lf_bytes(p.system_prompt.encode("utf-8")))
            for p in prompt_registry.prompts
        },
        user_prompt_template_by_id={
            p.prompt_id: p.user_prompt_template for p in prompt_registry.prompts
        },
        user_prompt_template_sha256_by_id={
            p.prompt_id: sha256_bytes(normalize_lf_bytes(p.user_prompt_template.encode("utf-8")))
            for p in prompt_registry.prompts
        },
        semantic_prompt_sha256_by_id={
            p.prompt_id: p.semantic_prompt_sha256 for p in prompt_registry.prompts
        },
        created_before_live_dev_execution=True,
        candidate_registry_sha256=cand_reg.registry_sha256,
        ordered_candidate_ids=list(cand_reg.ordered_candidate_ids),
        portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        dev_tune_bundle_sha256=bundle.dev_bundle_sha256,
        dev_tune_execution_plan_sha256=dev_tune_plan.plan_sha256,
        max_call_budget=dev_tune_plan.expected_total_cells,
        code_basis_commit_sha=basis_sha,
        code_commit_sha=basis_sha,
        scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
        scientific_code_bundle_file_hashes=code_bundle.scientific_code_bundle_file_hashes,
        provider_config_registry_sha256=compute_provider_config_registry_sha256(cand_reg),
        freeze_status="FROZEN_FOR_LIVE_DEV_TUNE",
    )


def verify_prompt_candidate_freeze_artifact(
    freeze_artifact: Optional[DevPromptFreezeArtifact | Path | Dict[str, Any]],
    *,
    prompt_registry: PromptRegistry,
    dev_tune_plan: DevExecutionPlan,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    active_code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> DevPromptFreezeArtifact:
    """Fail-closed verifier requiring a separate frozen prompt artifact before any live DEV-TUNE execution (Fix Group H / QA-32 / Audit Correction 02).

    Survives metadata/artifact commits (where HEAD advances from A to B) if and only if
    scientific_code_bundle_sha256(B) == artifact.scientific_code_bundle_sha256 and all
    frozen prompt, candidate, provider config, DEV bundle, and execution plan hashes match.
    """
    if freeze_artifact is None:
        raise PromptFreezeFirewallError(
            "PROMPT_FREEZE_ARTIFACT_MISSING: Live DEV execution is forbidden without a frozen prompt artifact."
        )
    if isinstance(freeze_artifact, Path):
        if not freeze_artifact.exists() or not freeze_artifact.is_file():
            raise PromptFreezeFirewallError(
                f"PROMPT_FREEZE_ARTIFACT_MISSING_ON_DISK: {freeze_artifact}"
            )
        try:
            raw_dict = json.loads(
                normalize_lf_bytes(freeze_artifact.read_bytes()).decode("utf-8")
            )
            artifact = DevPromptFreezeArtifact.model_validate(raw_dict)
        except PromptFreezeFirewallError:
            raise
        except Exception as exc:
            raise PromptFreezeFirewallError(
                f"PROMPT_FREEZE_ARTIFACT_INVALID: {exc}"
            ) from exc
    elif isinstance(freeze_artifact, dict):
        try:
            artifact = DevPromptFreezeArtifact.model_validate(freeze_artifact)
        except PromptFreezeFirewallError:
            raise
        except Exception as exc:
            raise PromptFreezeFirewallError(
                f"PROMPT_FREEZE_ARTIFACT_INVALID: {exc}"
            ) from exc
    elif isinstance(freeze_artifact, DevPromptFreezeArtifact):
        artifact = freeze_artifact
    else:
        raise PromptFreezeFirewallError(
            f"Unsupported freeze_artifact type: {type(freeze_artifact)!r}"
        )

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    expected_pconf_reg_sha = compute_provider_config_registry_sha256(cand_reg)

    expected_pids = [p.prompt_id for p in prompt_registry.prompts]
    if artifact.prompt_candidate_ids != expected_pids:
        raise PromptFreezeFirewallError(
            f"PROMPT_CANDIDATE_ID_MISMATCH: freeze_artifact={artifact.prompt_candidate_ids}, "
            f"registry={expected_pids}"
        )

    for p in prompt_registry.prompts:
        pid = p.prompt_id
        exp_sys_sha = sha256_bytes(normalize_lf_bytes(p.system_prompt.encode("utf-8")))
        exp_usr_sha = sha256_bytes(normalize_lf_bytes(p.user_prompt_template.encode("utf-8")))
        if artifact.prompt_versions.get(pid) != p.prompt_version:
            raise PromptFreezeFirewallError(f"Prompt version mismatch for {pid}")
        if artifact.system_prompt_by_id.get(pid) != p.system_prompt:
            raise PromptFreezeFirewallError(f"System prompt text mismatch for {pid}")
        if artifact.system_prompt_sha256_by_id.get(pid) != exp_sys_sha:
            raise PromptFreezeFirewallError(f"System prompt SHA256 mismatch for {pid}")
        if artifact.user_prompt_template_by_id.get(pid) != p.user_prompt_template:
            raise PromptFreezeFirewallError(f"User prompt template text mismatch for {pid}")
        if artifact.user_prompt_template_sha256_by_id.get(pid) != exp_usr_sha:
            raise PromptFreezeFirewallError(f"User prompt template SHA256 mismatch for {pid}")
        if artifact.semantic_prompt_sha256_by_id.get(pid) != p.semantic_prompt_sha256:
            raise PromptFreezeFirewallError(f"Semantic prompt SHA256 mismatch for {pid}")

    if (
        artifact.candidate_registry_sha256 != cand_reg.registry_sha256
        or tuple(artifact.ordered_candidate_ids) != ORDERED_CANDIDATE_IDS
    ):
        raise PromptFreezeFirewallError("Candidate registry mismatch in prompt freeze artifact.")
    if artifact.portable_generation_schema_v2_sha256 != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise PromptFreezeFirewallError("Portable Schema V2 SHA256 mismatch in prompt freeze artifact.")
    if artifact.dev_tune_bundle_sha256 != bundle.dev_bundle_sha256:
        raise PromptFreezeFirewallError("DEV-TUNE bundle SHA256 mismatch in prompt freeze artifact.")
    if artifact.dev_tune_execution_plan_sha256 != dev_tune_plan.plan_sha256:
        raise PromptFreezeFirewallError(
            "DEV-TUNE execution plan SHA256 mismatch in prompt freeze artifact."
        )
    if artifact.max_call_budget != dev_tune_plan.expected_total_cells:
        raise PromptFreezeFirewallError(
            f"Call budget mismatch in prompt freeze artifact: {artifact.max_call_budget} != {dev_tune_plan.expected_total_cells}"
        )
    if artifact.provider_config_registry_sha256 != expected_pconf_reg_sha:
        raise PromptFreezeFirewallError(
            "provider_config_registry_sha256 mismatch in prompt freeze artifact."
        )

    try:
        runtime_head_sha = resolve_and_verify_code_commit_sha(
            active_code_commit_sha, repo_root=repo_root
        )
    except CodeCommitProvenanceError as exc:
        raise PromptFreezeFirewallError(str(exc)) from exc

    if artifact.code_basis_commit_sha != dev_tune_plan.code_basis_commit_sha:
        raise PromptFreezeFirewallError(
            f"CODE_BASIS_COMMIT_SHA_MISMATCH: freeze artifact code_basis_commit_sha "
            f"{artifact.code_basis_commit_sha!r} != dev_tune_plan {dev_tune_plan.code_basis_commit_sha!r}"
        )

    try:
        current_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    except ScientificCodeBundleIntegrityError as exc:
        raise PromptFreezeFirewallError(str(exc)) from exc

    if artifact.scientific_code_bundle_sha256 != current_bundle.scientific_code_bundle_sha256:
        raise PromptFreezeFirewallError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH in prompt freeze artifact: "
            f"frozen={artifact.scientific_code_bundle_sha256} (code_basis_commit_sha={artifact.code_basis_commit_sha}) "
            f"!= current={current_bundle.scientific_code_bundle_sha256} (runtime_head_sha={runtime_head_sha})."
        )
    if (
        artifact.scientific_code_bundle_file_hashes
        and artifact.scientific_code_bundle_file_hashes
        != current_bundle.scientific_code_bundle_file_hashes
    ):
        raise PromptFreezeFirewallError(
            "SCIENTIFIC_CODE_BUNDLE_MISMATCH: Prompt freeze scientific_code_bundle_file_hashes "
            "do not match current runtime scientific source files."
        )
    try:
        verify_dev_execution_plan_for_execution(
            dev_tune_plan, repo_root=repo_root, candidate_registry=cand_reg
        )
    except (ScientificCodeBundleIntegrityError, CandidateRegistryIntegrityError) as exc:
        raise PromptFreezeFirewallError(str(exc)) from exc
    return artifact


assert_prompt_freeze_before_live = verify_prompt_candidate_freeze_artifact


class CandidateCostComparabilityRecord(BaseModel):
    """Explicit cost comparability record per candidate (Section 20)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    authoritative_usage_available: bool
    pricing_source: Optional[str] = None
    pricing_access_date: Optional[str] = None
    input_price_per_million_usd: Optional[float] = None
    output_price_per_million_usd: Optional[float] = None
    canonical_cost_computable: bool

    @model_validator(mode="after")
    def _validate_comparability_consistency(self) -> "CandidateCostComparabilityRecord":
        if self.canonical_cost_computable:
            if (
                not self.authoritative_usage_available
                or not self.pricing_source
                or not self.pricing_access_date
                or self.input_price_per_million_usd is None
                or self.output_price_per_million_usd is None
            ):
                raise ValueError(
                    f"Candidate {self.candidate_id} marked canonical_cost_computable=True "
                    "without authoritative usage and complete pricing metadata."
                )
        return self


def compute_canonical_cell_cost_decimal(
    *,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    thought_or_reasoning_tokens: Optional[int] = None,
    thought_tokens: Optional[int] = None,
    reasoning_tokens: Optional[int] = None,
    thinking_tokens: Optional[int] = None,
    cached_input_tokens: Optional[int] = None,
    cache_read_input_tokens: Optional[int] = None,
    cache_creation_input_tokens: Optional[int] = None,
    cost_record: CandidateCostComparabilityRecord,
) -> Optional[Decimal]:
    """Compute exact unrounded canonical USD cost as Decimal using provider-specific token billing semantics (Fix Group E / QA-27 & QA-28 / Correction A).

    Provider billing rules:
    - C1 (Google gemini-3.8-flash): candidates_token_count (output_tokens) is disjoint from
      thoughts_token_count (thought_tokens). billable_output_tokens = output_tokens + thought_tokens.
    - C2 (OpenAI gpt-6.1-sol): completion_tokens (output_tokens) is ALREADY inclusive of
      reasoning_tokens. DO NOT add reasoning_tokens again. billable_output_tokens = output_tokens.
    - C3 (Anthropic claude-sonnet-5-5): output_tokens is ALREADY inclusive of thinking_tokens.
      DO NOT add thinking_tokens again. billable_output_tokens = output_tokens.
    - Any nonzero unsupported cache token usage (cached_input_tokens, cache_read_input_tokens,
      cache_creation_input_tokens > 0) returns None (fail-safe non-comparable cost).
    """
    if not cost_record.canonical_cost_computable:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    if (
        (cached_input_tokens is not None and cached_input_tokens > 0)
        or (cache_read_input_tokens is not None and cache_read_input_tokens > 0)
        or (cache_creation_input_tokens is not None and cache_creation_input_tokens > 0)
    ):
        return None

    assert cost_record.input_price_per_million_usd is not None
    assert cost_record.output_price_per_million_usd is not None

    cid = cost_record.candidate_id
    if cid == "C1":
        disjoint_thoughts = (
            thought_tokens
            if thought_tokens is not None
            else (thought_or_reasoning_tokens or 0)
        )
        billed_out = output_tokens + disjoint_thoughts
    elif cid in ("C2", "C3"):
        # OpenAI completion_tokens and Anthropic output_tokens already include reasoning/thinking tokens
        _ = (reasoning_tokens, thinking_tokens, thought_or_reasoning_tokens)
        billed_out = output_tokens
    else:
        raise CandidateRegistryIntegrityError(
            f"Unknown candidate_id in compute_canonical_cell_cost_decimal: {cid!r}"
        )

    with localcontext() as ctx:
        ctx.prec = DECIMAL_SCIENTIFIC_PRECISION
        in_price = Decimal(str(cost_record.input_price_per_million_usd))
        out_price = Decimal(str(cost_record.output_price_per_million_usd))
        return (
            (Decimal(input_tokens) * in_price) + (Decimal(billed_out) * out_price)
        ) / Decimal(1_000_000)


def compute_canonical_cell_cost_decimal_str(
    *,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    thought_or_reasoning_tokens: Optional[int] = None,
    thought_tokens: Optional[int] = None,
    reasoning_tokens: Optional[int] = None,
    thinking_tokens: Optional[int] = None,
    cached_input_tokens: Optional[int] = None,
    cache_read_input_tokens: Optional[int] = None,
    cache_creation_input_tokens: Optional[int] = None,
    cost_record: CandidateCostComparabilityRecord,
) -> Optional[str]:
    """Compute exact canonical USD cost formatted as a non-exponent decimal string (Correction A)."""
    cost_dec = compute_canonical_cell_cost_decimal(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thought_or_reasoning_tokens=thought_or_reasoning_tokens,
        thought_tokens=thought_tokens,
        reasoning_tokens=reasoning_tokens,
        thinking_tokens=thinking_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cost_record=cost_record,
    )
    return format_canonical_decimal_str(cost_dec) if cost_dec is not None else None


def compute_canonical_cell_cost_usd(
    *,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    thought_or_reasoning_tokens: Optional[int] = None,
    thought_tokens: Optional[int] = None,
    reasoning_tokens: Optional[int] = None,
    thinking_tokens: Optional[int] = None,
    cached_input_tokens: Optional[int] = None,
    cache_read_input_tokens: Optional[int] = None,
    cache_creation_input_tokens: Optional[int] = None,
    cost_record: CandidateCostComparabilityRecord,
) -> Optional[float]:
    """Display-only float conversion of compute_canonical_cell_cost_decimal.

    NEVER used for scientific cell receipts, median aggregation, or Criterion 4 model selection.
    """
    cost_dec = compute_canonical_cell_cost_decimal(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thought_or_reasoning_tokens=thought_or_reasoning_tokens,
        thought_tokens=thought_tokens,
        reasoning_tokens=reasoning_tokens,
        thinking_tokens=thinking_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cost_record=cost_record,
    )
    return float(cost_dec) if cost_dec is not None else None


class DevCellExecutionReceipt(BaseModel):
    """Immutable per-cell execution receipt preserving primary scientific indicators, provenance, and usage/cost (Sections 8, 10-12; Corrections A, B, C; Audit Correction 02)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    phase: Literal["DEV_TUNE", "DEV_SELECT", "STOCHASTICITY_DIAGNOSTIC"]
    fixture_id: str
    candidate_id: str
    prompt_id: str
    requested_model_id: str
    returned_model_id: Optional[str] = None
    code_basis_commit_sha: str
    code_commit_sha: str
    runtime_head_sha: str
    scientific_code_bundle_sha256: str
    provider_config_sha256: str
    attempt_number: int = 1
    attempted: bool = True

    failure_classification: DevCellFailureClassification
    counts_in_denominator: bool = True
    batch_stop_required: bool = False
    valid_run_and_schema: bool
    exact_grounding_pass: bool
    final_core_pass: bool

    latency_ns: Optional[int] = None
    latency_ms_display: Optional[float] = None
    latency_ms: Optional[float] = None
    authoritative_usage_available: bool = False
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    thought_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    thinking_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    raw_usage_metadata: Optional[Dict[str, Any]] = None
    canonical_cost_usd_decimal: Optional[str] = None
    canonical_cost_usd_display: Optional[float] = None
    canonical_cost_usd: Optional[float] = None

    request_manifest_sha256: str
    raw_response_sha256: str
    provider_metadata_sha256: str
    parsed_response_sha256: Optional[str] = None
    evaluation_result_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _populate_receipt_provenance(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        _normalize_code_basis_provenance_fields(d, error_cls=CodeCommitProvenanceError)
        if "runtime_head_sha" not in d:
            # Never synthesize runtime_head_sha from code_basis_commit_sha; resolve active git HEAD
            d["runtime_head_sha"] = resolve_active_git_commit_sha()
        elif d["runtime_head_sha"] is None or not isinstance(d["runtime_head_sha"], str):
            raise CodeCommitProvenanceError(
                "runtime_head_sha is required and must be a 40-character lowercase hex git SHA."
            )
        if "scientific_code_bundle_sha256" not in d:
            d["scientific_code_bundle_sha256"] = compute_scientific_code_bundle_sha256()
        elif d["scientific_code_bundle_sha256"] is None or not isinstance(
            d["scientific_code_bundle_sha256"], str
        ):
            raise ValueError(
                "scientific_code_bundle_sha256 is required and must be a 64-character lowercase hex SHA256."
            )
        if "provider_config_sha256" not in d:
            cid = d.get("candidate_id")
            if cid in ORDERED_CANDIDATE_IDS:
                d["provider_config_sha256"] = get_cached_provider_config_sha256(str(cid))
        elif d["provider_config_sha256"] is None or not isinstance(
            d["provider_config_sha256"], str
        ):
            raise ValueError(
                "provider_config_sha256 is required and must be a 64-character lowercase hex SHA256."
            )
        fclass = d.get("failure_classification")
        if fclass in (
            DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
            DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
            DevCellFailureClassification.SCIENTIFIC_CODE_BUNDLE_MISMATCH,
            "MODEL_INTEGRITY_MISMATCH",
            "HARNESS_INTERNAL_ERROR",
            "SCIENTIFIC_CODE_BUNDLE_MISMATCH",
        ):
            d.setdefault("counts_in_denominator", False)
            d.setdefault("batch_stop_required", True)

        # Correction B: Validate integer latency_ns; never synthesize latency_ns from float latency_ms
        raw_lat_ns = d.get("latency_ns")
        if raw_lat_ns is not None:
            if isinstance(raw_lat_ns, bool) or not isinstance(raw_lat_ns, int) or raw_lat_ns < 0:
                raise ValueError(
                    f"latency_ns must be a non-negative integer, got {raw_lat_ns!r}"
                )
            if d.get("latency_ms_display") is None:
                d["latency_ms_display"] = (
                    float(d["latency_ms"])
                    if d.get("latency_ms") is not None
                    else float(Decimal(raw_lat_ns) / Decimal(1_000_000))
                )
            if d.get("latency_ms") is None:
                d["latency_ms"] = d["latency_ms_display"]
        else:
            if d.get("latency_ms_display") is None and d.get("latency_ms") is not None:
                d["latency_ms_display"] = float(d["latency_ms"])
            elif d.get("latency_ms") is None and d.get("latency_ms_display") is not None:
                d["latency_ms"] = float(d["latency_ms_display"])

        # Correction A: Validate exact canonical_cost_usd_decimal; NEVER derive it from float canonical_cost_usd
        raw_cost_dec = d.get("canonical_cost_usd_decimal")
        if raw_cost_dec is not None:
            norm_cost_str = format_canonical_decimal_str(raw_cost_dec)
            d["canonical_cost_usd_decimal"] = norm_cost_str
            cost_disp = float(parse_canonical_decimal_str(norm_cost_str))
            if d.get("canonical_cost_usd_display") is None:
                d["canonical_cost_usd_display"] = cost_disp
            if d.get("canonical_cost_usd") is None:
                d["canonical_cost_usd"] = d["canonical_cost_usd_display"]
        else:
            if (
                d.get("canonical_cost_usd_display") is None
                and d.get("canonical_cost_usd") is not None
            ):
                d["canonical_cost_usd_display"] = float(d["canonical_cost_usd"])
            elif (
                d.get("canonical_cost_usd") is None
                and d.get("canonical_cost_usd_display") is not None
            ):
                d["canonical_cost_usd"] = float(d["canonical_cost_usd_display"])
        return d

    @model_validator(mode="after")
    def _validate_receipt_consistency(self) -> "DevCellExecutionReceipt":
        assert_not_final100_scenario_id(self.fixture_id)
        validate_git_commit_sha40(self.code_basis_commit_sha)
        validate_git_commit_sha40(self.code_commit_sha)
        if self.code_basis_commit_sha != self.code_commit_sha:
            raise CodeCommitProvenanceError(
                f"CODE_COMMIT_SHA_MISMATCH: code_basis_commit_sha {self.code_basis_commit_sha!r} "
                f"!= code_commit_sha {self.code_commit_sha!r}"
            )
        validate_git_commit_sha40(self.runtime_head_sha)
        validate_sha256_hex64(
            self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
        )
        validate_sha256_hex64(self.provider_config_sha256, "provider_config_sha256")
        expected_pconf_sha = get_cached_provider_config_sha256(self.candidate_id)
        if self.provider_config_sha256 != expected_pconf_sha:
            raise ValueError(
                f"Receipt provider_config_sha256 mismatch for {self.candidate_id}: "
                f"expected={expected_pconf_sha}, got={self.provider_config_sha256}"
            )
        if self.latency_ns is not None:
            if isinstance(self.latency_ns, bool) or not isinstance(self.latency_ns, int) or self.latency_ns < 0:
                raise ValueError(
                    f"Receipt latency_ns must be a non-negative integer, got {self.latency_ns!r}"
                )
        if self.canonical_cost_usd_decimal is not None:
            if "e" in self.canonical_cost_usd_decimal.lower():
                raise ValueError(
                    f"canonical_cost_usd_decimal must be non-exponent decimal text, got {self.canonical_cost_usd_decimal!r}"
                )
            normalized = format_canonical_decimal_str(
                parse_canonical_decimal_str(self.canonical_cost_usd_decimal)
            )
            if normalized != self.canonical_cost_usd_decimal:
                raise ValueError(
                    f"canonical_cost_usd_decimal is not in canonical non-exponent form: {self.canonical_cost_usd_decimal!r} != {normalized!r}"
                )
        if self.failure_classification in BATCH_STOP_FAILURE_CLASSIFICATIONS:
            if self.counts_in_denominator or not self.batch_stop_required:
                raise ValueError(
                    f"Batch-stop failure classification {self.failure_classification.value} "
                    "requires counts_in_denominator=False and batch_stop_required=True."
                )
        if not self.valid_run_and_schema:
            if self.exact_grounding_pass or self.final_core_pass:
                raise ValueError(
                    "Invalid run/schema cell cannot have exact_grounding_pass=True or final_core_pass=True."
                )
        if not self.exact_grounding_pass and self.final_core_pass:
            raise ValueError(
                "Cell failing exact_grounding_pass cannot have final_core_pass=True."
            )
        return self


def create_synthetic_test_only_cell_receipt(**kwargs: Any) -> DevCellExecutionReceipt:
    """Explicit test-only constructor for purely synthetic unit tests (Correction C / Audit Correction 02).

    Does not use any hidden ContextVar bypass. Historical receipts and synthetic test receipts
    validate 40-hex commit syntax and 64-hex bundle/provider hash syntax without binding model_validate
    to the current git HEAD.
    """
    return DevCellExecutionReceipt(**kwargs)


def assert_batch_receipts_integrity(
    cell_receipts: Sequence[DevCellExecutionReceipt],
) -> None:
    """Unified batch integrity gate (Section 13 / Fix Group B & C / Audit Correction 02).

    Scans all receipts BEFORE any scientific aggregation, metric calculation, or selection.
    Fails closed and raises ModelIntegrityBatchStopError, HarnessInternalBatchStopError, or
    ScientificCodeBundleIntegrityError if any cell:
    - has failure_classification == MODEL_INTEGRITY_MISMATCH
    - has failure_classification == HARNESS_INTERNAL_ERROR
    - has failure_classification == SCIENTIFIC_CODE_BUNDLE_MISMATCH
    - has batch_stop_required == True or counts_in_denominator == False
    - has missing/empty or incompatible returned_model_id when not an ordinary transport failure
    """
    for r in cell_receipts:
        if r.failure_classification == DevCellFailureClassification.HARNESS_INTERNAL_ERROR:
            raise HarnessInternalBatchStopError(
                f"BATCH_STOP_HARNESS_INTERNAL_ERROR on cell {r.run_id} "
                f"(candidate={r.candidate_id}, fixture={r.fixture_id}): "
                "Entire scientific batch must stop immediately with no winner or aggregate."
            )
        if r.failure_classification == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH:
            raise ModelIntegrityBatchStopError(
                f"BATCH_STOP_MODEL_INTEGRITY_MISMATCH on cell {r.run_id} "
                f"(candidate={r.candidate_id}, requested={r.requested_model_id!r}, "
                f"returned={r.returned_model_id!r}): "
                "Entire scientific batch must stop immediately with no winner or aggregate."
            )
        if r.failure_classification == DevCellFailureClassification.SCIENTIFIC_CODE_BUNDLE_MISMATCH:
            raise ScientificCodeBundleIntegrityError(
                f"BATCH_STOP_SCIENTIFIC_CODE_BUNDLE_MISMATCH on cell {r.run_id} "
                f"(candidate={r.candidate_id}, fixture={r.fixture_id}): "
                "Entire scientific batch must stop immediately with no winner or aggregate."
            )
        if r.batch_stop_required or not r.counts_in_denominator:
            raise BatchExecutionFatalStopError(
                f"BATCH_STOP_FATAL_STATE on cell {r.run_id} "
                f"(classification={r.failure_classification.value}): "
                "Entire scientific batch must stop immediately."
            )
        if r.failure_classification == DevCellFailureClassification.NONE and not is_returned_model_id_compatible(
            r.requested_model_id, r.returned_model_id
        ):
            raise ModelIntegrityBatchStopError(
                f"BATCH_STOP_MODEL_INTEGRITY_MISMATCH on cell {r.run_id}: "
                f"requested_model_id={r.requested_model_id!r}, returned_model_id={r.returned_model_id!r}"
            )


def evaluate_dev_cell_scenario(
    scenario: BenchmarkScenarioInput,
    plan_response: Optional[BenchmarkPlanResponse],
    run_manifest: BenchmarkRunManifest,
    *,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
) -> ScenarioEvaluationResult:
    """Evaluate a DEV scenario cell with a fail-closed Final-100 firewall guard (DH-31)."""
    assert_not_final100_scenario(scenario)
    return evaluate_benchmark_scenario(
        scenario=scenario,
        plan_response=plan_response,
        run_manifest=run_manifest,
        catalog_path=catalog_path,
        core_catalog_by_id=core_catalog_by_id,
        verify_hashes=False,
    )


class MockProviderTransportResponse(BaseModel):
    """Simulated provider response used ONLY for offline mock testing (Section 8 & 23)."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = ""
    returned_model_id: Optional[str] = None
    finish_reason: str = "stop"
    latency_ms: float = 1200.0
    latency_ns: Optional[int] = 1_200_000_000
    simulated_failure: DevCellFailureClassification = DevCellFailureClassification.NONE
    authoritative_usage_available: bool = True
    input_tokens: Optional[int] = 1000
    output_tokens: Optional[int] = 800
    total_tokens: Optional[int] = 1800
    thought_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    thinking_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    raw_usage_metadata: Optional[Dict[str, Any]] = None


def parse_primary_dev_plan_response(
    raw_text: str,
) -> Tuple[Optional[BenchmarkPlanResponse], DevCellFailureClassification, BenchmarkRunStatus]:
    """Strict primary DEV response parser (Fix Group A / QA-14).

    Primary DEV scientific response acceptance is strictly:
        raw provider response text -> json.loads(raw_text) -> BenchmarkPlanResponse.model_validate(decoded_json)

    Strictly forbids:
    - parse_strict_benchmark_plan_response or any legacy fallback parser
    - plan_id, scenario_id, destination_slug, day_cost, or budget_analysis synthesis
    - markdown fence stripping or substring/regex JSON extraction
    - extra unsupported fields (rejected by BenchmarkPlanResponse extra='forbid')
    """
    if not isinstance(raw_text, str) or not raw_text:
        return (
            None,
            DevCellFailureClassification.MALFORMED_JSON,
            BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
        )
    # Reject markdown code fences or leading/trailing non-whitespace prose
    stripped = raw_text.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        return (
            None,
            DevCellFailureClassification.MALFORMED_JSON,
            BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
        )
    try:
        decoded_json = json.loads(raw_text)
    except Exception:
        return (
            None,
            DevCellFailureClassification.MALFORMED_JSON,
            BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
        )

    if not isinstance(decoded_json, dict):
        return (
            None,
            DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        )

    required_top_keys = {
        "plan_id",
        "scenario_id",
        "destination_slug",
        "destination",
        "total_days",
        "overview",
        "best_time_to_visit",
        "general_tips",
        "budget_analysis",
        "days",
    }
    if not required_top_keys.issubset(decoded_json.keys()):
        return (
            None,
            DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        )

    budget_obj = decoded_json.get("budget_analysis")
    required_budget_keys = {
        "total_budget",
        "estimated_cost",
        "currency",
        "is_over_budget",
        "variance",
    }
    if not isinstance(budget_obj, dict) or not required_budget_keys.issubset(budget_obj.keys()):
        return (
            None,
            DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        )

    days_obj = decoded_json.get("days")
    required_day_keys = {"day_number", "title", "day_cost", "items"}
    if not isinstance(days_obj, list) or not days_obj:
        return (
            None,
            DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        )
    for day_entry in days_obj:
        if (
            not isinstance(day_entry, dict)
            or not required_day_keys.issubset(day_entry.keys())
            or day_entry.get("day_cost") is None
        ):
            return (
                None,
                DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
                BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
            )

    try:
        parsed_plan = BenchmarkPlanResponse.model_validate(decoded_json)
        return (
            parsed_plan,
            DevCellFailureClassification.NONE,
            BenchmarkRunStatus.VALID,
        )
    except Exception:
        return (
            None,
            DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE,
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        )


def execute_dev_cell_with_mock_transport(
    *,
    cell_manifest: DevCellExecutionManifest,
    scenario: BenchmarkScenarioInput,
    cell_dir: Path,
    mock_response: MockProviderTransportResponse
    | Callable[[DevCellExecutionManifest], MockProviderTransportResponse]
    | Callable[[], MockProviderTransportResponse],
    cost_comparability: Optional[CandidateCostComparabilityRecord] = None,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
    enforce_batch_stop: bool = False,
    allow_synthetic_test_only_code_sha: bool = False,
    repo_root: Optional[Path] = None,
) -> Tuple[DevCellExecutionReceipt, ScenarioEvaluationResult]:
    """Execute a single DEV cell against a strictly offline mock transport and persist the 6 raw evidence contract files.

    Enforces:
    - Final-100 firewall
    - Action-boundary scientific code bundle verification BEFORE any cell directory or mock transport execution (Audit Correction 02)
    - Cell immutability (raises ImmutableCellExecutionError if cell_dir already has persisted artifacts)
    - Exact returned_model_id preservation (NEVER substitutes requested_model_id when returned_model_id is None/empty)
    - Strict JSON + BenchmarkPlanResponse.model_validate without rescue/repair (Fix Group A)
    - Provider-aware token usage & exact Decimal canonical cost calculation (Correction A / Fix Group E)
    - Authoritative integer nanoseconds latency_ns propagation (Correction B)
    - Fail-closed code_basis_commit_sha, runtime_head_sha, scientific_code_bundle_sha256, and provider_config_sha256 provenance propagation (Audit Correction 02)
    """
    assert_not_final100_scenario(scenario)
    if cell_manifest.fixture_id != scenario.scenario_id:
        raise ValueError("cell_manifest.fixture_id does not match scenario.scenario_id")
    if not allow_synthetic_test_only_code_sha:
        runtime_head_sha = verify_cell_manifest_for_execution(
            cell_manifest, repo_root=repo_root
        )
    else:
        validate_git_commit_sha40(cell_manifest.code_basis_commit_sha)
        validate_git_commit_sha40(cell_manifest.code_commit_sha)
        if cell_manifest.code_basis_commit_sha != cell_manifest.code_commit_sha:
            raise CodeCommitProvenanceError(
                f"CODE_COMMIT_SHA_MISMATCH: code_basis_commit_sha {cell_manifest.code_basis_commit_sha!r} "
                f"!= code_commit_sha {cell_manifest.code_commit_sha!r}"
            )
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=repo_root)

    required_files = (
        "request_manifest.json",
        "raw_provider_response.txt",
        "provider_response_metadata.json",
        "parsed_plan_response.json",
        "evaluation_result.json",
        "execution_receipt.json",
    )
    if cell_dir.exists() and any((cell_dir / fname).exists() for fname in required_files):
        raise ImmutableCellExecutionError(
            f"CELL_ALREADY_ATTEMPTED_OVERWRITE_FORBIDDEN: {cell_dir}"
        )

    if callable(mock_response):
        try:
            resolved_mock_response = mock_response(cell_manifest)  # type: ignore[arg-type]
        except TypeError:
            resolved_mock_response = mock_response()  # type: ignore[call-arg]
    else:
        resolved_mock_response = mock_response

    cell_dir.mkdir(parents=True, exist_ok=True)

    req_sha = write_canonical_json(
        cell_dir / "request_manifest.json", cell_manifest.model_dump()
    )
    raw_sha = write_exact_utf8_text(
        cell_dir / "raw_provider_response.txt", resolved_mock_response.raw_text
    )

    # Fix Group B (QA-15): NEVER substitute requested_model_id when returned_model_id is None or empty
    returned_model = resolved_mock_response.returned_model_id
    usage_avail = resolved_mock_response.authoritative_usage_available
    provider_meta = {
        "candidate_id": cell_manifest.candidate_id,
        "requested_model_id": cell_manifest.requested_model_id,
        "returned_model_id": returned_model,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "code_commit_sha": cell_manifest.code_basis_commit_sha,
        "runtime_head_sha": runtime_head_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "provider_config_sha256": cell_manifest.provider_config_sha256,
        "finish_reason": resolved_mock_response.finish_reason,
        "latency_ns": resolved_mock_response.latency_ns,
        "latency_ms_display": resolved_mock_response.latency_ms,
        "latency_ms": resolved_mock_response.latency_ms,
        "simulated_failure": resolved_mock_response.simulated_failure.value,
        "usage_metadata": {
            "authoritative_usage_available": usage_avail,
            "input_tokens": resolved_mock_response.input_tokens if usage_avail else None,
            "output_tokens": resolved_mock_response.output_tokens if usage_avail else None,
            "total_tokens": resolved_mock_response.total_tokens if usage_avail else None,
            "thought_tokens": resolved_mock_response.thought_tokens if usage_avail else None,
            "reasoning_tokens": resolved_mock_response.reasoning_tokens if usage_avail else None,
            "thinking_tokens": resolved_mock_response.thinking_tokens if usage_avail else None,
            "cached_input_tokens": resolved_mock_response.cached_input_tokens if usage_avail else None,
            "cache_read_input_tokens": (
                resolved_mock_response.cache_read_input_tokens if usage_avail else None
            ),
            "cache_creation_input_tokens": (
                resolved_mock_response.cache_creation_input_tokens if usage_avail else None
            ),
            "raw_usage_metadata": resolved_mock_response.raw_usage_metadata if usage_avail else None,
        },
    }
    meta_sha = write_canonical_json(
        cell_dir / "provider_response_metadata.json", provider_meta
    )

    failure_class = resolved_mock_response.simulated_failure
    parsed_plan: Optional[BenchmarkPlanResponse] = None
    parsed_sha: Optional[str] = None
    run_status = BenchmarkRunStatus.VALID

    if failure_class != DevCellFailureClassification.NONE:
        if failure_class == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH:
            run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
        else:
            run_status = BenchmarkRunStatus.API_ERROR
    elif not is_returned_model_id_compatible(cell_manifest.requested_model_id, returned_model):
        failure_class = DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
        run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
    else:
        parsed_plan, failure_class, run_status = parse_primary_dev_plan_response(
            resolved_mock_response.raw_text
        )
        if parsed_plan is not None:
            parsed_sha = write_canonical_json(
                cell_dir / "parsed_plan_response.json",
                parsed_plan.model_dump(),
            )

    manifest_model_id = (
        returned_model
        if (returned_model is not None and str(returned_model).strip())
        else "MISSING_RETURNED_MODEL_ID"
    )
    run_manifest = BenchmarkRunManifest(
        run_id=cell_manifest.run_id,
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-17T00:00:00Z",
        provider=cell_manifest.candidate_id,
        model_id=manifest_model_id,
        expected_model_id=cell_manifest.requested_model_id,
        generation_parameters={
            "temperature": 0.0,
            "seed": FROZEN_SAMPLING_SEED,
        },
        execution_mode="OFFLINE_MOCK_HARNESS_VERIFICATION",
        latency_ms=resolved_mock_response.latency_ms,
        usage_metadata=BenchmarkUsageMetadata(
            input_tokens=resolved_mock_response.input_tokens if usage_avail else None,
            output_tokens=resolved_mock_response.output_tokens if usage_avail else None,
            total_tokens=resolved_mock_response.total_tokens if usage_avail else None,
        ),
        code_commit_sha=cell_manifest.code_basis_commit_sha,
        scenario_sha256=cell_manifest.scenario_sha256,
        catalog_sha256=compute_catalog_sha256(catalog_path=catalog_path),
        benchmark_prompt_version=cell_manifest.prompt_id,
        raw_response_sha256=raw_sha,
        parsed_response_sha256=parsed_sha,
        measurement_contract_id=MEASUREMENT_CONTRACT_ID,
        measurement_contract_version=MEASUREMENT_CONTRACT_VERSION,
        hash_basis_version=HASH_BASIS_VERSION,
        run_status=run_status,
        error_detail=None if run_status == BenchmarkRunStatus.VALID else failure_class.value,
    )

    eval_result = evaluate_dev_cell_scenario(
        scenario=scenario,
        plan_response=parsed_plan,
        run_manifest=run_manifest,
        catalog_path=catalog_path,
        core_catalog_by_id=core_catalog_by_id,
    )
    eval_sha = write_canonical_json(
        cell_dir / "evaluation_result.json", eval_result.model_dump()
    )

    canonical_cost_dec: Optional[Decimal] = None
    canonical_cost_dec_str: Optional[str] = None
    canonical_cost_disp: Optional[float] = None
    if cost_comparability is not None and usage_avail:
        canonical_cost_dec = compute_canonical_cell_cost_decimal(
            input_tokens=resolved_mock_response.input_tokens,
            output_tokens=resolved_mock_response.output_tokens,
            thought_tokens=resolved_mock_response.thought_tokens,
            reasoning_tokens=resolved_mock_response.reasoning_tokens,
            thinking_tokens=resolved_mock_response.thinking_tokens,
            cached_input_tokens=resolved_mock_response.cached_input_tokens,
            cache_read_input_tokens=resolved_mock_response.cache_read_input_tokens,
            cache_creation_input_tokens=resolved_mock_response.cache_creation_input_tokens,
            cost_record=cost_comparability,
        )
        if canonical_cost_dec is not None:
            canonical_cost_dec_str = format_canonical_decimal_str(canonical_cost_dec)
            canonical_cost_disp = float(canonical_cost_dec)

    is_batch_stop = failure_class in BATCH_STOP_FAILURE_CLASSIFICATIONS
    valid_run_and_schema = bool(eval_result.run_valid) and not is_batch_stop
    exact_grounding_pass = bool(
        valid_run_and_schema
        and eval_result.all_pois_grounded
        and eval_result.scenario_destination_valid
    )
    final_core_pass = bool(valid_run_and_schema and eval_result.core_scenario_pass)

    receipt = DevCellExecutionReceipt(
        run_id=cell_manifest.run_id,
        phase=cell_manifest.phase,
        fixture_id=cell_manifest.fixture_id,
        candidate_id=cell_manifest.candidate_id,
        prompt_id=cell_manifest.prompt_id,
        requested_model_id=cell_manifest.requested_model_id,
        returned_model_id=returned_model,
        code_basis_commit_sha=cell_manifest.code_basis_commit_sha,
        code_commit_sha=cell_manifest.code_basis_commit_sha,
        runtime_head_sha=runtime_head_sha,
        scientific_code_bundle_sha256=cell_manifest.scientific_code_bundle_sha256,
        provider_config_sha256=cell_manifest.provider_config_sha256,
        attempt_number=cell_manifest.attempt_number,
        attempted=True,
        failure_classification=failure_class,
        counts_in_denominator=not is_batch_stop,
        batch_stop_required=is_batch_stop,
        valid_run_and_schema=valid_run_and_schema,
        exact_grounding_pass=exact_grounding_pass,
        final_core_pass=final_core_pass,
        latency_ns=resolved_mock_response.latency_ns,
        latency_ms_display=resolved_mock_response.latency_ms,
        latency_ms=resolved_mock_response.latency_ms,
        authoritative_usage_available=usage_avail,
        input_tokens=resolved_mock_response.input_tokens if usage_avail else None,
        output_tokens=resolved_mock_response.output_tokens if usage_avail else None,
        total_tokens=resolved_mock_response.total_tokens if usage_avail else None,
        thought_tokens=resolved_mock_response.thought_tokens if usage_avail else None,
        reasoning_tokens=resolved_mock_response.reasoning_tokens if usage_avail else None,
        thinking_tokens=resolved_mock_response.thinking_tokens if usage_avail else None,
        cached_input_tokens=resolved_mock_response.cached_input_tokens if usage_avail else None,
        cache_read_input_tokens=(
            resolved_mock_response.cache_read_input_tokens if usage_avail else None
        ),
        cache_creation_input_tokens=(
            resolved_mock_response.cache_creation_input_tokens if usage_avail else None
        ),
        raw_usage_metadata=resolved_mock_response.raw_usage_metadata if usage_avail else None,
        canonical_cost_usd_decimal=canonical_cost_dec_str,
        canonical_cost_usd_display=canonical_cost_disp,
        canonical_cost_usd=canonical_cost_disp,
        request_manifest_sha256=req_sha,
        raw_response_sha256=raw_sha,
        provider_metadata_sha256=meta_sha,
        parsed_response_sha256=parsed_sha,
        evaluation_result_sha256=eval_sha,
    )
    write_canonical_json(cell_dir / "execution_receipt.json", receipt.model_dump())
    if enforce_batch_stop:
        assert_batch_receipts_integrity([receipt])
    return receipt, eval_result


def execute_dev_batch_with_mock_transport(
    *,
    execution_plan: DevExecutionPlan,
    scenarios_by_id: Dict[str, BenchmarkScenarioInput],
    batch_root_dir: Path,
    mock_response_by_run_id: Dict[str, MockProviderTransportResponse]
    | Callable[[DevCellExecutionManifest], MockProviderTransportResponse],
    cost_comparability_by_candidate: Optional[Dict[str, CandidateCostComparabilityRecord]] = None,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
    repo_root: Optional[Path] = None,
) -> List[DevCellExecutionReceipt]:
    """Execute a planned batch of DEV cells with immediate fail-closed batch stop on MODEL_INTEGRITY_MISMATCH, HARNESS_INTERNAL_ERROR, or SCIENTIFIC_CODE_BUNDLE_MISMATCH."""
    verify_dev_execution_plan_for_execution(execution_plan, repo_root=repo_root)
    receipts: List[DevCellExecutionReceipt] = []
    for cell_manifest in execution_plan.cells:
        scenario = scenarios_by_id[cell_manifest.fixture_id]
        if callable(mock_response_by_run_id):
            mock_resp = mock_response_by_run_id(cell_manifest)
        else:
            mock_resp = mock_response_by_run_id[cell_manifest.run_id]
        cost_rec = (
            cost_comparability_by_candidate.get(cell_manifest.candidate_id)
            if cost_comparability_by_candidate is not None
            else None
        )
        rec, _ = execute_dev_cell_with_mock_transport(
            cell_manifest=cell_manifest,
            scenario=scenario,
            cell_dir=batch_root_dir / cell_manifest.run_id,
            mock_response=mock_resp,
            cost_comparability=cost_rec,
            catalog_path=catalog_path,
            core_catalog_by_id=core_catalog_by_id,
            enforce_batch_stop=True,
            repo_root=repo_root,
        )
        receipts.append(rec)
    assert_batch_receipts_integrity(receipts)
    return receipts


class DevGroupAggregateMetrics(BaseModel):
    """Deterministic aggregate metrics for a prompt or candidate across its assigned denominator (Sections 12 & 19).

    Strictly reports the three locked scientific rates separately without any weighted composite score.
    Authoritative cost and latency comparisons use exact non-exponent decimal strings:
    - median_canonical_cost_usd_decimal (derived strictly from DevCellExecutionReceipt.canonical_cost_usd_decimal)
    - median_latency_ns_decimal (derived strictly from integer DevCellExecutionReceipt.latency_ns)
    Float fields (median_canonical_cost_usd, median_canonical_cost_usd_display, median_latency_ms,
    median_latency_ms_display) are display-only and MUST NEVER be used for scientific selection.
    """

    model_config = ConfigDict(extra="forbid")

    group_id: str
    n_assigned: int
    n_attempted: int
    n_valid_schema: int
    n_exact_grounding_pass: int
    n_core_pass: int

    valid_run_and_schema_rate: float
    exact_grounding_pass_rate: float
    final_core_pass_rate: float

    median_latency_ns_decimal: Optional[str] = None
    median_latency_ms_display: Optional[float] = None
    median_latency_ms: Optional[float] = None

    canonical_cost_comparable: bool = False
    median_canonical_cost_usd_decimal: Optional[str] = None
    median_canonical_cost_usd_display: Optional[float] = None
    median_canonical_cost_usd: Optional[float] = None
    failure_classification_counts: Dict[str, int]


def aggregate_dev_cell_receipts(
    *,
    group_id: str,
    assigned_cell_keys: Sequence[Tuple[str, str, str]],
    cell_receipts: Sequence[DevCellExecutionReceipt],
    cost_comparability_all_computable: bool = True,
) -> DevGroupAggregateMetrics:
    """Deterministically aggregate a set of cell receipts against an authoritative list of assigned (prompt_id, candidate_id, fixture_id) keys."""
    # Section 13: Unified batch integrity gate BEFORE any denominator or metric computation
    assert_batch_receipts_integrity(cell_receipts)

    if not assigned_cell_keys:
        raise DenominatorIntegrityError(f"Empty assigned_cell_keys for group {group_id}")

    expected_set = set(assigned_cell_keys)
    if len(expected_set) != len(assigned_cell_keys):
        raise DenominatorIntegrityError(f"Duplicate keys in assigned_cell_keys for {group_id}")

    if len(cell_receipts) != len(expected_set):
        raise DenominatorIntegrityError(
            f"DENOMINATOR_MISMATCH for {group_id}: assigned {len(expected_set)} cells, "
            f"received {len(cell_receipts)} cell receipts. Failed cells must never be dropped."
        )

    observed_keys = set()
    for r in cell_receipts:
        assert_not_final100_scenario_id(r.fixture_id)
        key = (r.prompt_id, r.candidate_id, r.fixture_id)
        if key not in expected_set:
            raise DenominatorIntegrityError(f"Unexpected cell key {key} in group {group_id}")
        if key in observed_keys:
            raise DenominatorIntegrityError(f"Duplicate cell receipt for {key} in group {group_id}")
        observed_keys.add(key)

    n_assigned = len(expected_set)
    n_attempted = sum(1 for r in cell_receipts if r.attempted)
    if n_attempted != n_assigned:
        raise DenominatorIntegrityError(
            f"All assigned cells must be attempted (n_attempted={n_attempted} != n_assigned={n_assigned})."
        )

    n_valid_schema = sum(1 for r in cell_receipts if r.valid_run_and_schema)
    n_exact_grounding = sum(1 for r in cell_receipts if r.exact_grounding_pass)
    n_core_pass = sum(1 for r in cell_receipts if r.final_core_pass)

    valid_rate = n_valid_schema / n_assigned
    grounding_rate = n_exact_grounding / n_assigned
    core_rate = n_core_pass / n_assigned

    # Correction B: Authoritative latency median is computed strictly from integer latency_ns
    latencies_ns: List[int] = []
    for r in cell_receipts:
        if r.latency_ns is not None:
            if isinstance(r.latency_ns, bool) or not isinstance(r.latency_ns, int) or r.latency_ns < 0:
                raise ValueError(f"Invalid latency_ns {r.latency_ns!r} in receipt {r.run_id}")
            latencies_ns.append(r.latency_ns)

    median_latency_ns_dec: Optional[Decimal] = (
        compute_exact_decimal_median(latencies_ns)
        if len(latencies_ns) == n_assigned
        else None
    )
    median_latency_ns_str: Optional[str] = (
        format_canonical_decimal_str(median_latency_ns_dec)
        if median_latency_ns_dec is not None
        else None
    )
    if median_latency_ns_dec is not None:
        with localcontext() as ctx:
            ctx.prec = DECIMAL_SCIENTIFIC_PRECISION
            median_latency_ms_disp: Optional[float] = float(
                median_latency_ns_dec / Decimal(1_000_000)
            )
    else:
        latencies_ms_disp = [
            r.latency_ms for r in cell_receipts if r.latency_ms is not None
        ]
        median_latency_ms_disp = (
            float(statistics.median(latencies_ms_disp))
            if len(latencies_ms_disp) == n_assigned
            else None
        )

    has_unsupported_cache_usage = any(
        (r.cached_input_tokens is not None and r.cached_input_tokens > 0)
        or (r.cache_read_input_tokens is not None and r.cache_read_input_tokens > 0)
        or (r.cache_creation_input_tokens is not None and r.cache_creation_input_tokens > 0)
        for r in cell_receipts
    )
    # Correction A: Authoritative cost median is computed strictly from canonical_cost_usd_decimal
    costs_dec: List[Decimal] = [
        parse_canonical_decimal_str(r.canonical_cost_usd_decimal)
        for r in cell_receipts
        if r.canonical_cost_usd_decimal is not None
    ]
    cost_comparable = bool(
        cost_comparability_all_computable
        and not has_unsupported_cache_usage
        and len(costs_dec) == n_assigned
        and all(r.authoritative_usage_available for r in cell_receipts)
    )
    median_cost_dec: Optional[Decimal] = (
        compute_exact_decimal_median(costs_dec) if cost_comparable else None
    )
    median_cost_dec_str: Optional[str] = (
        format_canonical_decimal_str(median_cost_dec)
        if median_cost_dec is not None
        else None
    )
    median_cost_disp: Optional[float] = (
        float(median_cost_dec) if median_cost_dec is not None else None
    )

    failure_counts: Counter[str] = Counter(r.failure_classification.value for r in cell_receipts)

    return DevGroupAggregateMetrics(
        group_id=group_id,
        n_assigned=n_assigned,
        n_attempted=n_attempted,
        n_valid_schema=n_valid_schema,
        n_exact_grounding_pass=n_exact_grounding,
        n_core_pass=n_core_pass,
        valid_run_and_schema_rate=valid_rate,
        exact_grounding_pass_rate=grounding_rate,
        final_core_pass_rate=core_rate,
        median_latency_ns_decimal=median_latency_ns_str,
        median_latency_ms_display=median_latency_ms_disp,
        median_latency_ms=median_latency_ms_disp,
        canonical_cost_comparable=cost_comparable,
        median_canonical_cost_usd_decimal=median_cost_dec_str,
        median_canonical_cost_usd_display=median_cost_disp,
        median_canonical_cost_usd=median_cost_disp,
        failure_classification_counts=dict(sorted(failure_counts.items())),
    )


def _to_exact_decimal(value: float | str | Decimal | int) -> Decimal:
    """Convert numeric or canonical string value to exact unrounded Decimal without fixed-digit rounding (Fix Groups F & G)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    return Decimal(str(value))


def reduce_survivors_by_10pp_rule(
    survivor_ids: Sequence[str],
    scores_by_id: Dict[str, float],
) -> Tuple[List[str], float]:
    """Apply set-based relative-to-best 10pp survivor reduction (Sections 13, 14, 24).

    best = max(score[s] for s in survivor_ids)
    retain s iff (best - score[s]) <= 0.10

    Strictly forbids pairwise chaining (e.g., if A=0.90, B=0.82, C=0.73, best=0.90,
    only A and B survive; C is eliminated because 0.90 - 0.73 = 0.17 > 0.10).
    """
    if not survivor_ids:
        raise ValueError("survivor_ids cannot be empty")
    best_float = max(scores_by_id[s] for s in survivor_ids)
    best_dec = _to_exact_decimal(best_float)
    next_survivors = [
        s
        for s in survivor_ids
        if (best_dec - _to_exact_decimal(scores_by_id[s])) <= PRACTICAL_TIE_ABS_DIFF_RATIO
    ]
    return next_survivors, best_float


class CriterionReductionStepTrace(BaseModel):
    """Audit trace for a single criterion reduction step in DEV-TUNE or DEV-SELECT."""

    model_config = ConfigDict(extra="forbid")

    criterion_name: str
    survivors_entering: List[str]
    scores_of_entering_survivors: Dict[str, float]
    scores_of_entering_survivors_decimal: Dict[str, str] = Field(default_factory=dict)
    best_or_reference_value: Optional[float] = None
    best_or_reference_value_decimal: Optional[str] = None
    survivors_remaining: List[str]
    eliminated: List[str]
    step_status: str


class DevTunePromptSelectionResult(BaseModel):
    """Machine-reproducible result of DEV-TUNE prompt selection (Section 13)."""

    model_config = ConfigDict(extra="forbid")

    selected_prompt_id: str
    selected_prompt_sha256: str
    all_attempted_prompt_ids: List[str]
    all_attempted_prompt_hashes: Dict[str, str]
    selected_at_stage: str
    is_administrative_tiebreak: bool
    administrative_tiebreak_claims_superiority: bool = False
    used_cost_or_latency: bool = False
    used_final100: bool = False
    prompt_aggregates: Dict[str, DevGroupAggregateMetrics]
    reduction_trace: List[CriterionReductionStepTrace]


def select_winning_prompt_dev_tune(
    *,
    prompt_registry: PromptRegistry,
    cell_receipts: Sequence[DevCellExecutionReceipt],
    dev_tune_fixture_ids: Sequence[str],
    candidate_ids: Sequence[str] = ORDERED_CANDIDATE_IDS,
) -> DevTunePromptSelectionResult:
    """Execute the locked DEV-TUNE prompt selection algorithm (Section 13).

    - Preflights all receipts through the unified batch integrity gate (Section 13).
    - Evaluates across the same 20 DEV-TUNE fixtures × 3 eligible candidates.
    - If only P1 is registered, locks P1 with exact status LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON.
    - Applies set-based relative-to-best 10pp reduction on:
      1. VALID_RUN_AND_SCHEMA_RATE
      2. EXACT_GROUNDING_PASS_RATE
      3. FINAL_CORE_PASS_RATE
    - If multiple remain after criterion 3, selects P1 administratively.
    - Never uses cost, latency, human preference, or final100.
    """
    assert_batch_receipts_integrity(cell_receipts)

    for fid in dev_tune_fixture_ids:
        assert_not_final100_scenario_id(fid)
        if not fid.startswith("W06-DEV-TUNE-"):
            raise ValueError(f"Non-DEV-TUNE fixture ID in DEV-TUNE selection: {fid}")

    if len(dev_tune_fixture_ids) != DEV_TUNE_COUNT:
        raise ValueError(
            f"DEV-TUNE requires {DEV_TUNE_COUNT} fixtures, got {len(dev_tune_fixture_ids)}"
        )
    if tuple(candidate_ids) != ORDERED_CANDIDATE_IDS:
        raise CandidateRegistryIntegrityError(
            f"DEV-TUNE requires candidates {list(ORDERED_CANDIDATE_IDS)}, got {list(candidate_ids)}"
        )

    expected_total = calculate_expected_dev_tune_cell_count(
        len(prompt_registry.prompts),
        candidate_count=len(candidate_ids),
        fixture_count=len(dev_tune_fixture_ids),
    )
    if len(cell_receipts) != expected_total:
        raise DenominatorIntegrityError(
            f"DEV-TUNE expected {expected_total} total cell receipts, got {len(cell_receipts)}"
        )

    prompt_map = {p.prompt_id: p for p in prompt_registry.prompts}
    prompt_ids = [p.prompt_id for p in prompt_registry.prompts]
    prompt_hashes = {p.prompt_id: p.semantic_prompt_sha256 for p in prompt_registry.prompts}

    prompt_aggregates: Dict[str, DevGroupAggregateMetrics] = {}
    for pid in prompt_ids:
        assigned_keys = [
            (pid, cid, fid) for cid in candidate_ids for fid in dev_tune_fixture_ids
        ]
        p_receipts = [r for r in cell_receipts if r.prompt_id == pid]
        prompt_aggregates[pid] = aggregate_dev_cell_receipts(
            group_id=pid,
            assigned_cell_keys=assigned_keys,
            cell_receipts=p_receipts,
            cost_comparability_all_computable=False,
        )

    if len(prompt_ids) == 1:
        only_pid = prompt_ids[0]
        return DevTunePromptSelectionResult(
            selected_prompt_id=only_pid,
            selected_prompt_sha256=prompt_map[only_pid].semantic_prompt_sha256,
            all_attempted_prompt_ids=prompt_ids,
            all_attempted_prompt_hashes=prompt_hashes,
            selected_at_stage=SINGLE_PROMPT_P1_LOCK_STATUS,
            is_administrative_tiebreak=False,
            prompt_aggregates=prompt_aggregates,
            reduction_trace=[],
        )

    survivors = list(prompt_ids)
    trace: List[CriterionReductionStepTrace] = []

    criterion_attr_map = {
        "VALID_RUN_AND_SCHEMA_RATE": "valid_run_and_schema_rate",
        "EXACT_GROUNDING_PASS_RATE": "exact_grounding_pass_rate",
        "FINAL_CORE_PASS_RATE": "final_core_pass_rate",
    }

    for crit_name in PRIMARY_DEV_RATE_CRITERIA:
        attr_name = criterion_attr_map[crit_name]
        entering = list(survivors)
        scores = {pid: getattr(prompt_aggregates[pid], attr_name) for pid in entering}
        next_surv, best_val = reduce_survivors_by_10pp_rule(entering, scores)
        eliminated = [pid for pid in entering if pid not in next_surv]
        trace.append(
            CriterionReductionStepTrace(
                criterion_name=crit_name,
                survivors_entering=entering,
                scores_of_entering_survivors=scores,
                best_or_reference_value=best_val,
                survivors_remaining=next_surv,
                eliminated=eliminated,
                step_status="SINGLE_SURVIVOR_SELECTED"
                if len(next_surv) == 1
                else "MULTIPLE_SURVIVORS_ADVANCE",
            )
        )
        survivors = next_surv
        if len(survivors) == 1:
            winner = survivors[0]
            return DevTunePromptSelectionResult(
                selected_prompt_id=winner,
                selected_prompt_sha256=prompt_map[winner].semantic_prompt_sha256,
                all_attempted_prompt_ids=prompt_ids,
                all_attempted_prompt_hashes=prompt_hashes,
                selected_at_stage=crit_name,
                is_administrative_tiebreak=False,
                prompt_aggregates=prompt_aggregates,
                reduction_trace=trace,
            )

    # Multiple remain after criterion 3 -> administrative tie preference P1
    winner = "P1" if "P1" in survivors else survivors[0]
    trace.append(
        CriterionReductionStepTrace(
            criterion_name="ADMINISTRATIVE_TIEBREAK_P1",
            survivors_entering=list(survivors),
            scores_of_entering_survivors={},
            best_or_reference_value=None,
            survivors_remaining=[winner],
            eliminated=[pid for pid in survivors if pid != winner],
            step_status="ADMINISTRATIVE_TIEBREAK_P1_APPLIED",
        )
    )
    return DevTunePromptSelectionResult(
        selected_prompt_id=winner,
        selected_prompt_sha256=prompt_map[winner].semantic_prompt_sha256,
        all_attempted_prompt_ids=prompt_ids,
        all_attempted_prompt_hashes=prompt_hashes,
        selected_at_stage="ADMINISTRATIVE_TIEBREAK_P1",
        is_administrative_tiebreak=True,
        prompt_aggregates=prompt_aggregates,
        reduction_trace=trace,
    )


class DevSelectModelSelectionResult(BaseModel):
    """Machine-reproducible result of DEV-SELECT model selection (Section 14)."""

    model_config = ConfigDict(extra="forbid")

    winner_selected: bool = True
    selected_candidate_id: str
    locked_prompt_id: str
    selected_at_stage: str
    cost_criterion_status: str
    is_administrative_tiebreak: bool
    administrative_tiebreak_claims_scientific_superiority: bool = False
    used_final100: bool = False
    candidate_aggregates: Dict[str, DevGroupAggregateMetrics]
    cost_comparability_by_candidate: Dict[str, CandidateCostComparabilityRecord]
    reduction_trace: List[CriterionReductionStepTrace]


def select_winning_candidate_dev_select(
    *,
    cell_receipts: Sequence[DevCellExecutionReceipt],
    cost_comparability_by_candidate: Dict[str, CandidateCostComparabilityRecord],
    dev_select_fixture_ids: Sequence[str],
    locked_prompt_id: str = "P1",
    eligible_candidate_ids: Sequence[str] = ORDERED_CANDIDATE_IDS,
) -> DevSelectModelSelectionResult:
    """Execute the locked DEV-SELECT model selection algorithm (Section 14).

    0. Unified batch integrity gate (Section 13): fails closed on MODEL_INTEGRITY_MISMATCH or HARNESS_INTERNAL_ERROR.
    1. VALID_RUN_AND_SCHEMA_RATE (10pp relative-to-best survivor reduction)
    2. EXACT_GROUNDING_PASS_RATE (10pp relative-to-best survivor reduction)
    3. FINAL_CORE_PASS_RATE (10pp relative-to-best survivor reduction)
    4. MEDIAN_COST_PER_SCENARIO (minimum unrounded canonical Decimal median cost from
       median_canonical_cost_usd_decimal if comparable for ALL current survivors;
       otherwise skip cost for ALL survivors with COST_CRITERION_SKIPPED_NOT_COMPARABLE;
       NEVER uses float cost fields)
    5. MEDIAN_LATENCY (minimum unrounded canonical Decimal median latency from
       median_latency_ns_decimal without epsilon or rounding; fails closed if
       median_latency_ns_decimal is unavailable for any survivor; NEVER falls back to float latency_ms)
    6. Final administrative order: C1 > C2 > C3
    """
    assert_batch_receipts_integrity(cell_receipts)

    if locked_prompt_id not in ALLOWED_PROMPT_IDS:
        raise PromptRegistryIntegrityError(f"Invalid locked_prompt_id: {locked_prompt_id!r}")
    for fid in dev_select_fixture_ids:
        assert_not_final100_scenario_id(fid)
        if not fid.startswith("W06-DEV-SELECT-"):
            raise ValueError(f"Non-DEV-SELECT fixture ID in DEV-SELECT selection: {fid}")

    if len(dev_select_fixture_ids) != DEV_SELECT_COUNT:
        raise ValueError(
            f"DEV-SELECT requires {DEV_SELECT_COUNT} fixtures, got {len(dev_select_fixture_ids)}"
        )
    if tuple(eligible_candidate_ids) != ORDERED_CANDIDATE_IDS:
        raise CandidateRegistryIntegrityError(
            f"DEV-SELECT requires eligible candidates {list(ORDERED_CANDIDATE_IDS)}, got {list(eligible_candidate_ids)}"
        )

    expected_total = calculate_expected_dev_select_cell_count(
        locked_prompt_count=1,
        candidate_count=len(eligible_candidate_ids),
        fixture_count=len(dev_select_fixture_ids),
    )
    if len(cell_receipts) != expected_total:
        raise DenominatorIntegrityError(
            f"DEV-SELECT expected {expected_total} total cell receipts, got {len(cell_receipts)}"
        )

    candidate_aggregates: Dict[str, DevGroupAggregateMetrics] = {}
    for cid in eligible_candidate_ids:
        if cid not in cost_comparability_by_candidate:
            raise ValueError(f"Missing cost comparability record for candidate {cid}")
        assigned_keys = [(locked_prompt_id, cid, fid) for fid in dev_select_fixture_ids]
        c_receipts = [r for r in cell_receipts if r.candidate_id == cid]
        comp_rec = cost_comparability_by_candidate[cid]
        candidate_aggregates[cid] = aggregate_dev_cell_receipts(
            group_id=cid,
            assigned_cell_keys=assigned_keys,
            cell_receipts=c_receipts,
            cost_comparability_all_computable=comp_rec.canonical_cost_computable,
        )

    survivors = list(eligible_candidate_ids)
    trace: List[CriterionReductionStepTrace] = []
    cost_status = "NOT_REACHED"

    criterion_attr_map = {
        "VALID_RUN_AND_SCHEMA_RATE": "valid_run_and_schema_rate",
        "EXACT_GROUNDING_PASS_RATE": "exact_grounding_pass_rate",
        "FINAL_CORE_PASS_RATE": "final_core_pass_rate",
    }

    for crit_name in PRIMARY_DEV_RATE_CRITERIA:
        attr_name = criterion_attr_map[crit_name]
        entering = list(survivors)
        scores = {cid: getattr(candidate_aggregates[cid], attr_name) for cid in entering}
        next_surv, best_val = reduce_survivors_by_10pp_rule(entering, scores)
        eliminated = [cid for cid in entering if cid not in next_surv]
        trace.append(
            CriterionReductionStepTrace(
                criterion_name=crit_name,
                survivors_entering=entering,
                scores_of_entering_survivors=scores,
                best_or_reference_value=best_val,
                survivors_remaining=next_surv,
                eliminated=eliminated,
                step_status="SINGLE_SURVIVOR_SELECTED"
                if len(next_surv) == 1
                else "MULTIPLE_SURVIVORS_ADVANCE",
            )
        )
        survivors = next_surv
        if len(survivors) == 1:
            return DevSelectModelSelectionResult(
                selected_candidate_id=survivors[0],
                locked_prompt_id=locked_prompt_id,
                selected_at_stage=crit_name,
                cost_criterion_status=cost_status,
                is_administrative_tiebreak=False,
                candidate_aggregates=candidate_aggregates,
                cost_comparability_by_candidate=cost_comparability_by_candidate,
                reduction_trace=trace,
            )

    # Criterion 4: Cost tiebreak (Correction A: strictly compares exact Decimal median_canonical_cost_usd_decimal)
    entering_cost = list(survivors)
    all_survivors_cost_comparable = all(
        cost_comparability_by_candidate[cid].canonical_cost_computable
        and candidate_aggregates[cid].canonical_cost_comparable
        and candidate_aggregates[cid].median_canonical_cost_usd_decimal is not None
        for cid in entering_cost
    )

    if not all_survivors_cost_comparable:
        cost_status = COST_CRITERION_SKIPPED_NOT_COMPARABLE
        trace.append(
            CriterionReductionStepTrace(
                criterion_name="MEDIAN_COST_PER_SCENARIO",
                survivors_entering=entering_cost,
                scores_of_entering_survivors={},
                scores_of_entering_survivors_decimal={},
                best_or_reference_value=None,
                best_or_reference_value_decimal=None,
                survivors_remaining=entering_cost,
                eliminated=[],
                step_status=COST_CRITERION_SKIPPED_NOT_COMPARABLE,
            )
        )
    else:
        cost_status = COST_CRITERION_APPLIED
        cost_decimals: Dict[str, Decimal] = {
            cid: parse_canonical_decimal_str(
                candidate_aggregates[cid].median_canonical_cost_usd_decimal  # type: ignore[arg-type]
            )
            for cid in entering_cost
        }
        cost_decimal_strs: Dict[str, str] = {
            cid: format_canonical_decimal_str(cost_decimals[cid]) for cid in entering_cost
        }
        min_cost_dec = min(cost_decimals.values())
        min_cost_dec_str = format_canonical_decimal_str(min_cost_dec)
        next_surv_cost = [
            cid for cid in entering_cost if cost_decimals[cid] == min_cost_dec
        ]
        eliminated_cost = [cid for cid in entering_cost if cid not in next_surv_cost]
        cost_display_scores: Dict[str, float] = {
            cid: float(cost_decimals[cid]) for cid in entering_cost
        }
        trace.append(
            CriterionReductionStepTrace(
                criterion_name="MEDIAN_COST_PER_SCENARIO",
                survivors_entering=entering_cost,
                scores_of_entering_survivors=cost_display_scores,
                scores_of_entering_survivors_decimal=cost_decimal_strs,
                best_or_reference_value=float(min_cost_dec),
                best_or_reference_value_decimal=min_cost_dec_str,
                survivors_remaining=next_surv_cost,
                eliminated=eliminated_cost,
                step_status="SINGLE_SURVIVOR_SELECTED"
                if len(next_surv_cost) == 1
                else "MULTIPLE_SURVIVORS_ADVANCE",
            )
        )
        survivors = next_surv_cost
        if len(survivors) == 1:
            return DevSelectModelSelectionResult(
                selected_candidate_id=survivors[0],
                locked_prompt_id=locked_prompt_id,
                selected_at_stage="MEDIAN_COST_PER_SCENARIO",
                cost_criterion_status=cost_status,
                is_administrative_tiebreak=False,
                candidate_aggregates=candidate_aggregates,
                cost_comparability_by_candidate=cost_comparability_by_candidate,
                reduction_trace=trace,
            )

    # Criterion 5: Latency tiebreak (Correction B: strictly compares exact Decimal median_latency_ns_decimal)
    entering_lat = list(survivors)
    if any(
        candidate_aggregates[cid].median_latency_ns_decimal is None
        for cid in entering_lat
    ):
        raise LatencyAuthorityUnavailableError(
            "LATENCY_AUTHORITY_UNAVAILABLE: Missing authoritative median_latency_ns_decimal "
            "(derived from integer latency_ns) for one or more survivors during DEV-SELECT "
            "Criterion 5 tiebreak. Fallback to float latency_ms is strictly forbidden."
        )
    lat_ns_decimals: Dict[str, Decimal] = {
        cid: parse_canonical_decimal_str(
            candidate_aggregates[cid].median_latency_ns_decimal  # type: ignore[arg-type]
        )
        for cid in entering_lat
    }
    lat_ns_decimal_strs: Dict[str, str] = {
        cid: format_canonical_decimal_str(lat_ns_decimals[cid]) for cid in entering_lat
    }
    min_lat_ns_dec = min(lat_ns_decimals.values())
    min_lat_ns_dec_str = format_canonical_decimal_str(min_lat_ns_dec)
    next_surv_lat = [
        cid for cid in entering_lat if lat_ns_decimals[cid] == min_lat_ns_dec
    ]
    eliminated_lat = [cid for cid in entering_lat if cid not in next_surv_lat]
    lat_display_scores: Dict[str, float] = {
        cid: float(lat_ns_decimals[cid]) for cid in entering_lat
    }
    trace.append(
        CriterionReductionStepTrace(
            criterion_name="MEDIAN_LATENCY",
            survivors_entering=entering_lat,
            scores_of_entering_survivors=lat_display_scores,
            scores_of_entering_survivors_decimal=lat_ns_decimal_strs,
            best_or_reference_value=float(min_lat_ns_dec),
            best_or_reference_value_decimal=min_lat_ns_dec_str,
            survivors_remaining=next_surv_lat,
            eliminated=eliminated_lat,
            step_status="SINGLE_SURVIVOR_SELECTED"
            if len(next_surv_lat) == 1
            else "MULTIPLE_SURVIVORS_ADVANCE",
        )
    )
    survivors = next_surv_lat
    if len(survivors) == 1:
        return DevSelectModelSelectionResult(
            selected_candidate_id=survivors[0],
            locked_prompt_id=locked_prompt_id,
            selected_at_stage="MEDIAN_LATENCY",
            cost_criterion_status=cost_status,
            is_administrative_tiebreak=False,
            candidate_aggregates=candidate_aggregates,
            cost_comparability_by_candidate=cost_comparability_by_candidate,
            reduction_trace=trace,
        )

    # Final administrative tiebreak: C1 > C2 > C3
    winner = next(cid for cid in ORDERED_CANDIDATE_IDS if cid in survivors)
    trace.append(
        CriterionReductionStepTrace(
            criterion_name="FINAL_ADMINISTRATIVE_TIEBREAK_C1_GT_C2_GT_C3",
            survivors_entering=list(survivors),
            scores_of_entering_survivors={},
            scores_of_entering_survivors_decimal={},
            best_or_reference_value=None,
            best_or_reference_value_decimal=None,
            survivors_remaining=[winner],
            eliminated=[cid for cid in survivors if cid != winner],
            step_status="FINAL_ADMINISTRATIVE_TIEBREAK_APPLIED",
        )
    )
    return DevSelectModelSelectionResult(
        selected_candidate_id=winner,
        locked_prompt_id=locked_prompt_id,
        selected_at_stage="FINAL_ADMINISTRATIVE_TIEBREAK_C1_GT_C2_GT_C3",
        cost_criterion_status=cost_status,
        is_administrative_tiebreak=True,
        administrative_tiebreak_claims_scientific_superiority=False,
        candidate_aggregates=candidate_aggregates,
        cost_comparability_by_candidate=cost_comparability_by_candidate,
        reduction_trace=trace,
    )


class StochasticityDiagnosticPlan(BaseModel):
    """Post-winner stochasticity diagnostic plan (5 lexicographically smallest DEV-TUNE IDs × 3 runs = 15 calls; Section 18; Audit Correction 02)."""

    model_config = ConfigDict(extra="forbid")

    phase: Literal["STOCHASTICITY_DIAGNOSTIC"] = "STOCHASTICITY_DIAGNOSTIC"
    selected_candidate_id: str
    locked_prompt_id: str
    fixture_ids: List[str]
    executions_per_fixture: int = STOCHASTICITY_EXECUTIONS_PER_FIXTURE
    max_calls: int = STOCHASTICITY_MAX_CALLS
    retry: int = 0
    best_of_n: bool = False
    diagnostic_only: bool = True
    may_alter_selected_model: bool = False
    may_alter_selected_prompt: bool = False
    may_alter_sampling_config: bool = False
    may_alter_dev_select_results: bool = False
    code_basis_commit_sha: str
    code_commit_sha: str
    scientific_code_bundle_sha256: str
    scientific_code_bundle_file_hashes: List[Dict[str, str]] = Field(default_factory=list)
    cells: List[DevCellExecutionManifest]
    plan_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _populate_stochasticity_plan_provenance(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        _normalize_code_basis_provenance_fields(d, error_cls=CodeCommitProvenanceError)
        if "scientific_code_bundle_sha256" not in d:
            d["scientific_code_bundle_sha256"] = compute_scientific_code_bundle_sha256()
        if "scientific_code_bundle_file_hashes" not in d:
            current_bundle = compute_scientific_code_bundle()
            if (
                d.get("scientific_code_bundle_sha256")
                == current_bundle.scientific_code_bundle_sha256
            ):
                d["scientific_code_bundle_file_hashes"] = [
                    dict(entry) for entry in current_bundle.scientific_code_bundle_file_hashes
                ]
            else:
                d["scientific_code_bundle_file_hashes"] = []
        return d

    @model_validator(mode="after")
    def _validate_stochasticity_plan_provenance(self) -> "StochasticityDiagnosticPlan":
        validate_git_commit_sha40(self.code_basis_commit_sha)
        validate_git_commit_sha40(self.code_commit_sha)
        if self.code_basis_commit_sha != self.code_commit_sha:
            raise CodeCommitProvenanceError(
                f"CODE_COMMIT_SHA_MISMATCH: code_basis_commit_sha {self.code_basis_commit_sha!r} "
                f"!= code_commit_sha {self.code_commit_sha!r}"
            )
        validate_sha256_hex64(
            self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
        )
        if self.scientific_code_bundle_file_hashes:
            ScientificCodeBundleManifest(
                scientific_code_bundle_sha256=self.scientific_code_bundle_sha256,
                scientific_code_bundle_file_hashes=self.scientific_code_bundle_file_hashes,
            )
        for cell in self.cells:
            if cell.code_basis_commit_sha != self.code_basis_commit_sha:
                raise CodeCommitProvenanceError(
                    f"CODE_COMMIT_SHA_MISMATCH: Cell {cell.run_id} code_basis_commit_sha "
                    f"{cell.code_basis_commit_sha!r} != plan {self.code_basis_commit_sha!r}"
                )
            if cell.scientific_code_bundle_sha256 != self.scientific_code_bundle_sha256:
                raise ScientificCodeBundleIntegrityError(
                    f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Cell {cell.run_id} bundle "
                    f"{cell.scientific_code_bundle_sha256!r} != plan {self.scientific_code_bundle_sha256!r}"
                )
        return self


def build_stochasticity_diagnostic_plan(
    *,
    dev_select_result: Optional[DevSelectModelSelectionResult],
    locked_prompt_spec: PromptCandidateSpec,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
    code_basis_commit_sha: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> StochasticityDiagnosticPlan:
    """Build the post-DEV-SELECT stochasticity diagnostic plan (strictly gated AFTER winner selection; Section 18)."""
    if (
        dev_select_result is None
        or not dev_select_result.winner_selected
        or dev_select_result.selected_candidate_id not in ORDERED_CANDIDATE_IDS
    ):
        raise StochasticityGateViolationError(
            "STOCHASTICITY_DIAGNOSTIC_FORBIDDEN_BEFORE_DEV_SELECT_WINNER: "
            "Stochasticity diagnostic cannot be planned or executed before a DEV-SELECT winning candidate is selected."
        )
    if dev_select_result.locked_prompt_id != locked_prompt_spec.prompt_id:
        raise StochasticityGateViolationError(
            "locked_prompt_spec.prompt_id does not match dev_select_result.locked_prompt_id"
        )

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    active_sha = _resolve_plan_creation_code_basis_sha(
        code_basis_commit_sha=code_basis_commit_sha,
        code_commit_sha=code_commit_sha,
        repo_root=repo_root,
    )
    code_bundle = compute_scientific_code_bundle(repo_root=repo_root)
    winner_cid = dev_select_result.selected_candidate_id
    cspec = cand_reg.candidates[winner_cid]
    pconf_sha = compute_candidate_provider_config_sha256(cspec)

    sorted_tune_fixtures = sorted(bundle.dev_tune_fixtures, key=lambda sc: sc.scenario_id)[:5]
    fixture_ids = [sc.scenario_id for sc in sorted_tune_fixtures]
    if tuple(fixture_ids) != EXPECTED_STOCHASTICITY_FIXTURE_IDS:
        raise ValueError(
            f"Stochasticity fixture IDs must be {list(EXPECTED_STOCHASTICITY_FIXTURE_IDS)}, got {fixture_ids}"
        )

    preloaded_catalog = {
        slug: build_destination_catalog_context(slug, catalog_path=catalog_path)
        for slug in ("ha-noi", "da-nang", "ha-long")
    }

    cells: List[DevCellExecutionManifest] = []
    for scenario in sorted_tune_fixtures:
        ctx = build_deterministic_dev_scenario_context(
            scenario,
            locked_prompt_spec,
            catalog_path=catalog_path,
            preloaded_catalog_by_dest=preloaded_catalog,
        )
        for attempt_idx in (1, 2, 3):
            run_id = (
                f"W06-STOCHASTICITY-{locked_prompt_spec.prompt_id}-"
                f"{winner_cid}-{scenario.scenario_id}-R{attempt_idx}"
            )
            cells.append(
                DevCellExecutionManifest(
                    run_id=run_id,
                    phase="STOCHASTICITY_DIAGNOSTIC",
                    fixture_id=scenario.scenario_id,
                    candidate_id=winner_cid,
                    prompt_id=locked_prompt_spec.prompt_id,
                    requested_model_id=cspec.requested_model_id,
                    code_basis_commit_sha=active_sha,
                    code_commit_sha=active_sha,
                    scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
                    provider_config_sha256=pconf_sha,
                    scenario_sha256=ctx.scenario_sha256,
                    catalog_context_sha256=ctx.catalog_context_sha256,
                    system_prompt_sha256=ctx.system_prompt_sha256,
                    user_prompt_sha256=ctx.user_prompt_sha256,
                    semantic_schema_sha256=ctx.semantic_schema_sha256,
                    portable_generation_schema_v2_sha256=ctx.portable_generation_schema_v2_sha256,
                    sampling_reasoning_configuration=cspec.sampling_reasoning_config,
                    max_output_tokens=cspec.max_output_tokens,
                    timeout_ms=cspec.timeout_ms,
                    attempt_number=attempt_idx,
                )
            )

    if len(cells) != STOCHASTICITY_MAX_CALLS:
        raise ValueError(f"Expected {STOCHASTICITY_MAX_CALLS} stochasticity cells, got {len(cells)}")

    plan_sha = sha256_bytes(canonical_json_bytes([c.model_dump() for c in cells]))
    return StochasticityDiagnosticPlan(
        selected_candidate_id=winner_cid,
        locked_prompt_id=locked_prompt_spec.prompt_id,
        fixture_ids=fixture_ids,
        code_basis_commit_sha=active_sha,
        code_commit_sha=active_sha,
        scientific_code_bundle_sha256=code_bundle.scientific_code_bundle_sha256,
        scientific_code_bundle_file_hashes=code_bundle.scientific_code_bundle_file_hashes,
        cells=cells,
        plan_sha256=plan_sha,
    )



def compute_harness_determinism_hashes(
    *,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    prompt_registry: Optional[PromptRegistry] = None,
) -> Dict[str, str]:
    """Compute deterministic hashes for all harness components without any timestamps (Section 21)."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    prompt_reg = prompt_registry or build_default_infrastructure_prompt_registry()

    provider_config_payload = {
        cid: {
            "provider": spec.provider,
            "requested_model_id": spec.requested_model_id,
            "sampling_reasoning_config": spec.sampling_reasoning_config,
            "omitted_parameters": spec.omitted_parameters,
            "max_output_tokens": spec.max_output_tokens,
            "timeout_ms": spec.timeout_ms,
            "portable_generation_schema_v2_sha256": spec.portable_generation_schema_v2_sha256,
        }
        for cid, spec in sorted(cand_reg.candidates.items())
    }

    selection_algorithm_payload = {
        "algorithm_id": "LEXICOGRAPHIC_BEST_RELATIVE_SURVIVOR_SET_REDUCTION",
        "pairwise_chaining_allowed": False,
        "practical_tie_abs_diff_ratio": str(PRACTICAL_TIE_ABS_DIFF_RATIO),
        "ordered_rate_criteria": list(PRIMARY_DEV_RATE_CRITERIA),
        "dev_tune_tie_after_criterion_3_winner": "P1",
        "dev_tune_uses_cost_or_latency": False,
        "dev_select_criterion_4": "LOWER_UNROUNDED_CANONICAL_MEDIAN_COST_IF_COMPARABLE_FOR_ALL_SURVIVORS_ELSE_SKIP_FOR_ALL",
        "dev_select_cost_skipped_status": COST_CRITERION_SKIPPED_NOT_COMPARABLE,
        "dev_select_criterion_5": "LOWER_UNROUNDED_CANONICAL_MEDIAN_LATENCY_WINS",
        "dev_select_final_administrative_order": list(ORDERED_CANDIDATE_IDS),
        "weighted_composite_allowed": False,
    }

    artifact_schema_payload = {
        "required_cell_files": [
            "request_manifest.json",
            "raw_provider_response.txt",
            "provider_response_metadata.json",
            "parsed_plan_response.json (only when parse/semantic validation succeeds)",
            "evaluation_result.json",
            "execution_receipt.json",
        ],
        "overwrite_allowed": False,
        "retry_until_success_allowed": False,
        "manifest_schema": DevCellExecutionManifest.model_json_schema(),
        "receipt_schema": DevCellExecutionReceipt.model_json_schema(),
    }

    aggregator_config_payload = {
        "all_assigned_remain_in_denominator": True,
        "dropped_failures_allowed": False,
        "primary_rates": list(PRIMARY_DEV_RATE_CRITERIA),
        "weighted_composite_allowed": False,
        "aggregate_schema": DevGroupAggregateMetrics.model_json_schema(),
    }

    return {
        "dev_bundle_sha256": bundle.dev_bundle_sha256,
        "dev_tune_id_list_sha256": bundle.dev_tune_ids_sha256,
        "dev_select_id_list_sha256": bundle.dev_select_ids_sha256,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": sha256_bytes(
            canonical_json_bytes(provider_config_payload)
        ),
        "prompt_registry_sha256": prompt_reg.registry_sha256,
        "selection_algorithm_sha256": sha256_bytes(
            canonical_json_bytes(selection_algorithm_payload)
        ),
        "artifact_schema_sha256": sha256_bytes(canonical_json_bytes(artifact_schema_payload)),
        "aggregator_configuration_sha256": sha256_bytes(
            canonical_json_bytes(aggregator_config_payload)
        ),
    }


def build_dev_selection_harness_v1_payload() -> Dict[str, Any]:
    """Build the canonical JSON payload for data/evaluation/w06/w06_dev_selection_harness_v1.json (Section 26)."""
    bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = build_default_infrastructure_prompt_registry()
    det_hashes = compute_harness_determinism_hashes(
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        prompt_registry=prompt_reg,
    )
    dev_tune_plan_1p = build_dev_tune_execution_plan(
        prompt_reg, dev_bundle=bundle, candidate_registry=cand_reg
    )
    dev_select_plan_p1 = build_dev_select_execution_plan(
        prompt_reg.prompts[0], dev_bundle=bundle, candidate_registry=cand_reg
    )

    return {
        "artifact_id": HARNESS_ARTIFACT_ID,
        "task_id": TASK_ID_DEV_HARNESS,
        "version": HARNESS_VERSION,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS,
        "architecture_id": FROZEN_ARCHITECTURE_ID,
        "architecture_class": FROZEN_ARCHITECTURE_CLASS,
        "offline_only": True,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "final100_firewall": {
            "enabled": True,
            "forbidden_paths": [
                "data/evaluation/w06/w06_scenarios_freeze_v1.json",
                "data/evaluation/w06/w06_p11_assignment_manifest_v1.json",
            ],
            "allowed_dev_fixture_labels": ["W06_DEV_TUNE", "W06_DEV_SELECT"],
            "final100_semantics_loaded": False,
        },
        "dev_dataset_summary": {
            "total_dev": bundle.total_count,
            "dev_tune_total": bundle.dev_tune_count,
            "dev_select_total": bundle.dev_select_count,
            "dev_bundle_sha256": bundle.dev_bundle_sha256,
            "dev_manifest_sha256": bundle.dev_manifest_sha256,
            "overlap_receipt_sha256": bundle.overlap_receipt_sha256,
            "dev_tune_marginals": bundle.dev_tune_marginals,
            "dev_select_marginals": bundle.dev_select_marginals,
        },
        "candidate_registry": {
            "ordered_candidate_ids": cand_reg.ordered_candidate_ids,
            "registry_sha256": cand_reg.registry_sha256,
            "candidates": {
                cid: {
                    "candidate_id": spec.candidate_id,
                    "provider": spec.provider,
                    "requested_model_id": spec.requested_model_id,
                    "technical_preflight_v2_status": spec.technical_preflight_v2_status,
                    "portable_generation_schema_v2_sha256": spec.portable_generation_schema_v2_sha256,
                    "sampling_reasoning_config": spec.sampling_reasoning_config,
                    "omitted_parameters": spec.omitted_parameters,
                    "max_output_tokens": spec.max_output_tokens,
                    "timeout_ms": spec.timeout_ms,
                    "llm_calls_per_execution": spec.llm_calls_per_execution,
                    "automatic_retry": spec.automatic_retry,
                    "transport_retry": spec.transport_retry,
                    "manual_retry": spec.manual_retry,
                    "fallback": spec.fallback,
                    "llm_repair": spec.llm_repair,
                    "deterministic_semantic_repair": spec.deterministic_semantic_repair,
                    "tools": spec.tools,
                }
                for cid, spec in sorted(cand_reg.candidates.items())
            },
        },
        "prompt_registry_infrastructure": {
            "allowed_prompt_ids": list(ALLOWED_PROMPT_IDS),
            "max_registered_prompts": MAX_PROMPT_CANDIDATES,
            "p3_allowed": False,
            "provider_specific_semantic_prompts_allowed": False,
            "prompt_semantic_freeze_status": "INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE",
            "default_infrastructure_p1_sha256": prompt_reg.prompts[0].semantic_prompt_sha256,
        },
        "call_budget_limits": {
            "dev_tune_max_calls_one_prompt": DEV_TUNE_MAX_CALLS_ONE_PROMPT,
            "dev_tune_max_calls_two_prompts": DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
            "dev_select_max_calls": DEV_SELECT_MAX_CALLS,
            "stochasticity_diagnostic_max_calls": STOCHASTICITY_MAX_CALLS,
            "executions_per_cell": 1,
            "retry": 0,
            "fallback": False,
            "repair": 0,
        },
        "selection_algorithms": {
            "rule_type": "LEXICOGRAPHIC_BEST_RELATIVE_SURVIVOR_SET_REDUCTION",
            "pairwise_chaining_allowed": False,
            "practical_tie_abs_diff_ratio": 0.10,
            "primary_rate_criteria_order": list(PRIMARY_DEV_RATE_CRITERIA),
            "weighted_composite_allowed": False,
            "dev_tune_prompt_selection": {
                "pool": "20_DEV_TUNE_FIXTURES_BY_3_ELIGIBLE_CANDIDATES",
                "tie_after_criterion_3_winner": "P1",
                "uses_cost_or_latency": False,
            },
            "dev_select_model_selection": {
                "pool": "60_DEV_SELECT_FIXTURES_ON_LOCKED_PROMPT",
                "criterion_4_cost": {
                    "rule": "KEEP_MINIMUM_UNROUNDED_CANONICAL_MEDIAN_COST_IF_COMPARABLE_FOR_ALL_CURRENT_SURVIVORS",
                    "skip_status": COST_CRITERION_SKIPPED_NOT_COMPARABLE,
                },
                "criterion_5_latency": {
                    "rule": "KEEP_MINIMUM_UNROUNDED_CANONICAL_MEDIAN_LATENCY",
                },
                "final_administrative_tie_order": list(ORDERED_CANDIDATE_IDS),
                "human_choice_allowed": False,
            },
        },
        "stochasticity_diagnostic_contract": {
            "gated_after_dev_select_winner": True,
            "fixture_selection_rule": "FIVE_LEXICOGRAPHICALLY_SMALLEST_FROZEN_DEV_TUNE_SCENARIO_IDS",
            "fixture_ids": list(EXPECTED_STOCHASTICITY_FIXTURE_IDS),
            "executions_per_fixture": STOCHASTICITY_EXECUTIONS_PER_FIXTURE,
            "max_calls": STOCHASTICITY_MAX_CALLS,
            "retry": 0,
            "best_of_n": False,
            "diagnostic_only": True,
            "may_alter_selected_model_or_prompt_or_sampling": False,
        },
        "determinism_hashes": {
            **det_hashes,
            "dev_tune_1_prompt_plan_sha256": dev_tune_plan_1p.plan_sha256,
            "dev_select_p1_plan_sha256": dev_select_plan_p1.plan_sha256,
        },
    }


def build_dev_selection_harness_01_receipt_payload() -> Dict[str, Any]:
    """Build the canonical JSON payload for data/evaluation/w06/w06_dev_selection_harness_01_receipt_v1.json (Section 27)."""
    verified_authorities = verify_frozen_authorities_dev_harness()
    harness_payload = build_dev_selection_harness_v1_payload()
    harness_sha = sha256_bytes(canonical_json_bytes(harness_payload))

    return {
        "artifact_id": HARNESS_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID_DEV_HARNESS,
        "version": HARNESS_VERSION,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "dev_tune_model_execution_started": False,
        "dev_select_model_execution_started": False,
        "stochasticity_diagnostic_started": False,
        "winner_selected": False,
        "final100_used": False,
        "all_three_candidates_technically_eligible": True,
        "technically_eligible_candidates": list(ORDERED_CANDIDATE_IDS),
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": EXPECTED_GENERATION_SCHEMA_V1_SHA256,
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "dev_total": DEV_TOTAL_COUNT,
        "dev_tune_total": DEV_TUNE_COUNT,
        "dev_select_total": DEV_SELECT_COUNT,
        "prompt_registry_max": MAX_PROMPT_CANDIDATES,
        "dev_tune_max_calls_one_prompt": DEV_TUNE_MAX_CALLS_ONE_PROMPT,
        "dev_tune_max_calls_two_prompts": DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
        "dev_select_max_calls": DEV_SELECT_MAX_CALLS,
        "final100_firewall_status": "PASS",
        "prompt_selection_algorithm_status": "PASS",
        "model_selection_algorithm_status": "PASS",
        "pairwise_chaining_forbidden_status": "PASS",
        "cost_comparability_rule_status": "PASS",
        "stochasticity_gate_status": "PASS",
        "harness_artifact_sha256": harness_sha,
        "frozen_authority_preservation": verified_authorities,
        "next_gate": NEXT_GATE_ID,
        "status": "READY_FOR_CHATGPT_AUDIT",
    }


def write_dev_selection_harness_artifacts(
    *,
    harness_path: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Write w06_dev_selection_harness_v1.json and w06_dev_selection_harness_01_receipt_v1.json."""
    h_target = harness_path or DEFAULT_HARNESS_ARTIFACT_PATH
    r_target = receipt_path or DEFAULT_HARNESS_RECEIPT_PATH
    h_payload = build_dev_selection_harness_v1_payload()
    r_payload = build_dev_selection_harness_01_receipt_payload()
    h_sha = write_canonical_json(h_target, h_payload)
    r_sha = write_canonical_json(r_target, r_payload)
    return h_sha, r_sha


def run_cli(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Run offline safety modes (--offline-validate, --plan-dev-tune, --plan-dev-select; Section 22).

    Fails closed if no mode is given or if any live execution argument is passed.
    """
    raw_args = list(argv) if argv is not None else []
    forbidden_live_flags = {"--execute-live", "--confirm-live", "--live", "--run-live"}
    for arg in raw_args:
        if arg in forbidden_live_flags or arg.startswith("--live"):
            raise DevHarnessOfflineViolationError(
                f"LIVE_PROVIDER_CALL_FORBIDDEN: Flag {arg!r} is forbidden in W06-DEV-SELECTION-HARNESS-01-OFFLINE."
            )

    parser = argparse.ArgumentParser(
        description="W06 DEV Selection Offline Scientific Harness (100% offline)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--offline-validate",
        action="store_true",
        help="Validate frozen DEV bundle, marginals, candidate registry, firewall, and determinism hashes.",
    )
    group.add_argument(
        "--plan-dev-tune",
        action="store_true",
        help="Build offline DEV-TUNE execution plan (no live calls).",
    )
    group.add_argument(
        "--plan-dev-select",
        action="store_true",
        help="Build offline DEV-SELECT execution plan (no live calls).",
    )
    group.add_argument(
        "--write-artifacts",
        action="store_true",
        help="Materialize offline harness method and receipt artifacts.",
    )

    parsed = parser.parse_args(raw_args)

    if parsed.offline_validate:
        verify_frozen_authorities_dev_harness()
        payload = build_dev_selection_harness_01_receipt_payload()
        return {"mode": "offline_validate", "status": "PASS", "receipt": payload}

    if parsed.plan_dev_tune:
        prompt_reg = build_default_infrastructure_prompt_registry()
        plan = build_dev_tune_execution_plan(prompt_reg)
        return {
            "mode": "plan_dev_tune",
            "expected_total_cells": plan.expected_total_cells,
            "plan_sha256": plan.plan_sha256,
        }

    if parsed.plan_dev_select:
        prompt_reg = build_default_infrastructure_prompt_registry()
        plan = build_dev_select_execution_plan(prompt_reg.prompts[0])
        return {
            "mode": "plan_dev_select",
            "expected_total_cells": plan.expected_total_cells,
            "plan_sha256": plan.plan_sha256,
        }

    if parsed.write_artifacts:
        h_sha, r_sha = write_dev_selection_harness_artifacts()
        return {
            "mode": "write_artifacts",
            "harness_sha256": h_sha,
            "receipt_sha256": r_sha,
        }

    raise DevHarnessOfflineViolationError("No valid offline mode specified.")


if __name__ == "__main__":
    import sys

    result = run_cli(sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
