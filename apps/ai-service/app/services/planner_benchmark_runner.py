"""Live-only W06 benchmark execution runner and forensic evidence writer (W06-INSTRUMENT-01A).

Grounded in W06-MEASUREMENT-CONTRACT-01 v1.1.0 (7fd5364ed4671c06b0c911b6fd53bd9f54cbc322).
Never uses the production /planner canned mock fallback.
"""
import hashlib
import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - used when running in minimal data-contract env
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from pydantic import ValidationError

from app.config import settings
from app.prompts.planner_benchmark_prompt import (
    BENCHMARK_PROMPT_VERSION,
    DEFAULT_CATALOG_PATH,
    REPO_ROOT,
    build_benchmark_planner_prompt,
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (
    BenchmarkBudgetAnalysis,
    BenchmarkCatalogPOI,
    BenchmarkItineraryDay,
    BenchmarkItineraryItem,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)

MEASUREMENT_CONTRACT_ID = "W06-MEASUREMENT-CONTRACT-01"
MEASUREMENT_CONTRACT_VERSION = "1.1.0"
MEASUREMENT_CONTRACT_SOURCE_COMMIT = "7fd5364ed4671c06b0c911b6fd53bd9f54cbc322"
HASH_BASIS = "EXACT_PERSISTED_UTF8_LF_BYTES_SHA256"
PROVIDER_NAME = "google-genai"
BENCHMARK_TEMPERATURE = 0.7


def sha256_bytes(data: bytes) -> str:
    """Compute lowercase hex SHA256 over exact bytes."""
    return hashlib.sha256(data).hexdigest()


def normalize_lf_bytes(data: bytes) -> bytes:
    """Normalize CRLF to LF so source file hashes are platform-independent across Windows and Linux."""
    return data.replace(b"\r\n", b"\n")


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize structured JSON deterministically to UTF-8 bytes with LF newline."""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return text.encode("utf-8")


def write_canonical_json(path: Path, obj: Any) -> str:
    """Persist canonical UTF-8 LF JSON bytes to disk and return exact SHA256."""
    raw = canonical_json_bytes(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256_bytes(raw)


def write_exact_utf8_text(path: Path, text: str) -> str:
    """Persist exact UTF-8 bytes of a text artifact without OS line-ending conversion and return SHA256."""
    raw = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256_bytes(raw)


def compute_catalog_sha256(catalog_path: Optional[Path] = None) -> str:
    """Compute deterministic SHA256 of the frozen catalog (LF-normalized UTF-8 bytes)."""
    target = catalog_path or DEFAULT_CATALOG_PATH
    return sha256_bytes(normalize_lf_bytes(target.read_bytes()))


def get_current_code_commit_sha() -> str:
    """Return current git HEAD commit SHA (or 'UNKNOWN' if git is unavailable)."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def clean_benchmark_json_response(raw: str) -> str:
    """Extract JSON substring from raw LLM text without mutating the preserved raw response."""
    cleaned = raw.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            part_stripped = part.strip()
            if part_stripped.startswith("json"):
                part_stripped = part_stripped[4:].strip()
            if part_stripped.startswith("{"):
                cleaned = part_stripped
                break
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]

    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)
    return cleaned


def extract_authoritative_usage_metadata(response: Any) -> BenchmarkUsageMetadata:
    """Extract authoritative provider token usage metadata if present; never estimate from string length."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return BenchmarkUsageMetadata(input_tokens=None, output_tokens=None, total_tokens=None)

    def _int_or_none(obj: Any, *attr_names: str) -> Optional[int]:
        for name in attr_names:
            val = getattr(obj, name, None) if not isinstance(obj, dict) else obj.get(name)
            if isinstance(val, int) and not isinstance(val, bool):
                return val
        return None

    return BenchmarkUsageMetadata(
        input_tokens=_int_or_none(usage, "prompt_token_count", "input_tokens"),
        output_tokens=_int_or_none(usage, "candidates_token_count", "output_tokens"),
        total_tokens=_int_or_none(usage, "total_token_count", "total_tokens"),
    )


def parse_strict_benchmark_plan_response(
    raw_data: Dict[str, Any],
    scenario: BenchmarkScenarioInput,
    plan_id: Optional[str] = None,
) -> BenchmarkPlanResponse:
    """Parse raw decoded JSON dict into strict BenchmarkPlanResponse.

    Rejects missing/unknown activity_kind, missing place_id on POI_VISIT,
    or non-null place_id on TRANSIT_ONLY.
    """
    if not isinstance(raw_data, dict):
        raise ValueError("Top-level model output must be a JSON object.")

    raw_days = raw_data.get("days")
    if not isinstance(raw_days, list) or not raw_days:
        raise ValueError("Model output must contain a non-empty 'days' list.")

    parsed_days: List[BenchmarkItineraryDay] = []
    deterministic_total_cost = 0

    for day_idx, day_obj in enumerate(raw_days):
        if not isinstance(day_obj, dict):
            raise ValueError(f"Day entry at index {day_idx} must be a JSON object.")
        if "day_number" not in day_obj:
            raise ValueError(f"Day entry at index {day_idx} missing required 'day_number'.")
        if "title" not in day_obj:
            raise ValueError(f"Day entry at index {day_idx} missing required 'title'.")
        raw_items = day_obj.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError(f"Day {day_obj.get('day_number')} must contain a non-empty 'items' list.")

        parsed_items: List[BenchmarkItineraryItem] = []
        day_cost = 0
        for item_idx, item_obj in enumerate(raw_items):
            if not isinstance(item_obj, dict):
                raise ValueError(f"Item at index {item_idx} in day {day_idx + 1} must be a JSON object.")
            # Strict BenchmarkItineraryItem validation (extra="forbid", no default activity_kind)
            parsed_item = BenchmarkItineraryItem.model_validate(item_obj)
            day_cost += parsed_item.estimated_cost
            parsed_items.append(parsed_item)

        deterministic_total_cost += day_cost
        parsed_days.append(
            BenchmarkItineraryDay(
                day_number=int(day_obj["day_number"]),
                date=day_obj.get("date"),
                title=str(day_obj["title"]),
                items=parsed_items,
                day_cost=day_cost,
            )
        )

    budget = scenario.budget
    is_over = False
    variance = 0
    if budget is not None and budget > 0:
        is_over = deterministic_total_cost > budget
        variance = budget - deterministic_total_cost

    budget_analysis = BenchmarkBudgetAnalysis(
        total_budget=budget,
        estimated_cost=deterministic_total_cost,
        currency=scenario.currency,
        is_over_budget=is_over,
        variance=variance,
    )

    return BenchmarkPlanResponse(
        plan_id=plan_id or str(uuid.uuid4()),
        scenario_id=scenario.scenario_id,
        destination_slug=scenario.destination_slug,
        destination=str(raw_data.get("destination") or scenario.destination),
        total_days=len(parsed_days),
        overview=str(raw_data.get("overview") or "").strip(),
        best_time_to_visit=str(raw_data.get("best_time_to_visit") or "").strip(),
        general_tips=[str(tip) for tip in (raw_data.get("general_tips") or [])],
        budget_analysis=budget_analysis,
        days=parsed_days,
    )


@dataclass
class BenchmarkExecutionResult:
    """Result container returned by execute_benchmark_scenario."""

    run_status: BenchmarkRunStatus
    manifest: BenchmarkRunManifest
    scenario_input: BenchmarkScenarioInput
    benchmark_prompt: str
    raw_provider_response: Optional[str]
    cleaned_provider_json: Optional[str]
    parsed_plan_response: Optional[BenchmarkPlanResponse]
    output_dir: Path

    @property
    def is_valid(self) -> bool:
        return self.run_status == BenchmarkRunStatus.VALID


def prepare_benchmark_scenario(
    scenario: BenchmarkScenarioInput,
    output_dir: Path,
    catalog_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Prepare and validate scenario input, catalog context, and benchmark prompt without calling provider."""
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_pois: List[BenchmarkCatalogPOI] = build_destination_catalog_context(
        scenario.destination_slug,
        catalog_path=catalog_path,
    )
    prompt = build_benchmark_planner_prompt(
        scenario=scenario,
        catalog_pois=catalog_pois,
        catalog_path=catalog_path,
    )

    scenario_sha256 = write_canonical_json(
        output_dir / "scenario_input.json",
        scenario.model_dump(),
    )
    catalog_context_sha256 = write_canonical_json(
        output_dir / "catalog_context.json",
        [p.model_dump() for p in catalog_pois],
    )
    prompt_sha256 = write_exact_utf8_text(
        output_dir / "benchmark_prompt.txt",
        prompt,
    )
    source_catalog_sha256 = compute_catalog_sha256(catalog_path=catalog_path)

    prep_manifest = {
        "scenario_id": scenario.scenario_id,
        "destination_slug": scenario.destination_slug,
        "catalog_poi_count": len(catalog_pois),
        "benchmark_prompt_version": BENCHMARK_PROMPT_VERSION,
        "scenario_sha256": scenario_sha256,
        "catalog_sha256": source_catalog_sha256,
        "catalog_context_sha256": catalog_context_sha256,
        "prompt_sha256": prompt_sha256,
        "measurement_contract_id": MEASUREMENT_CONTRACT_ID,
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
        "measurement_contract_source_commit": MEASUREMENT_CONTRACT_SOURCE_COMMIT,
        "provider_called": False,
    }
    write_canonical_json(output_dir / "preparation_manifest.json", prep_manifest)
    return prep_manifest


def execute_benchmark_scenario(
    scenario: BenchmarkScenarioInput,
    output_dir: Path,
    *,
    expected_model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    configured_model_id: Optional[str] = None,
    client: Optional[Any] = None,
    catalog_path: Optional[Path] = None,
    run_id: Optional[str] = None,
    execution_timestamp_utc: Optional[str] = None,
    code_commit_sha: Optional[str] = None,
    clock_fn: Callable[[], float] = time.perf_counter,
    force_mock_mode: bool = False,
) -> BenchmarkExecutionResult:
    """Execute a single W06 benchmark scenario with strict live-only fail-closed guards.

    - Never falls back to canned mock output.
    - Performs zero silent retries.
    - Preserves raw_provider_response.txt even when JSON parsing or schema validation fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_run_id = run_id or str(uuid.uuid4())
    effective_timestamp = execution_timestamp_utc or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    effective_commit_sha = (
        code_commit_sha if code_commit_sha is not None else get_current_code_commit_sha()
    )

    catalog_pois = build_destination_catalog_context(
        scenario.destination_slug,
        catalog_path=catalog_path,
    )
    prompt = build_benchmark_planner_prompt(
        scenario=scenario,
        catalog_pois=catalog_pois,
        catalog_path=catalog_path,
    )

    scenario_sha256 = write_canonical_json(
        output_dir / "scenario_input.json",
        scenario.model_dump(),
    )
    catalog_sha256 = compute_catalog_sha256(catalog_path=catalog_path)

    actual_model_id = (
        configured_model_id if configured_model_id is not None else settings.PLANNER_MODEL
    )
    gen_params: Dict[str, Any] = {
        "temperature": BENCHMARK_TEMPERATURE,
        "max_output_tokens": settings.PLANNER_MAX_OUTPUT_TOKENS,
        "response_mime_type": "application/json",
        "timeout_ms": settings.PLANNER_TIMEOUT_MS,
        "top_p": None,
        "top_k": None,
        "seed": None,
    }

    def _finalize(
        status: BenchmarkRunStatus,
        exec_mode: str,
        *,
        latency_ms: Optional[float] = None,
        usage: Optional[BenchmarkUsageMetadata] = None,
        raw_text: Optional[str] = None,
        cleaned_json: Optional[str] = None,
        parsed_resp: Optional[BenchmarkPlanResponse] = None,
        raw_sha: Optional[str] = None,
        parsed_sha: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> BenchmarkExecutionResult:
        manifest = BenchmarkRunManifest(
            run_id=effective_run_id,
            scenario_id=scenario.scenario_id,
            execution_timestamp_utc=effective_timestamp,
            provider=PROVIDER_NAME,
            model_id=str(actual_model_id or ""),
            expected_model_id=expected_model_id,
            generation_parameters=gen_params,
            execution_mode=exec_mode,
            latency_ms=latency_ms,
            usage_metadata=usage or BenchmarkUsageMetadata(),
            code_commit_sha=effective_commit_sha,
            scenario_sha256=scenario_sha256,
            catalog_sha256=catalog_sha256,
            benchmark_prompt_version=BENCHMARK_PROMPT_VERSION,
            raw_response_sha256=raw_sha,
            parsed_response_sha256=parsed_sha,
            measurement_contract_id=MEASUREMENT_CONTRACT_ID,
            measurement_contract_version=MEASUREMENT_CONTRACT_VERSION,
            measurement_contract_source_commit=MEASUREMENT_CONTRACT_SOURCE_COMMIT,
            hash_basis=HASH_BASIS,
            claims_bitwise_model_determinism=False,
            run_status=status,
            error_detail=error_detail,
        )
        write_canonical_json(output_dir / "run_manifest.json", manifest.model_dump())
        return BenchmarkExecutionResult(
            run_status=status,
            manifest=manifest,
            scenario_input=scenario,
            benchmark_prompt=prompt,
            raw_provider_response=raw_text,
            cleaned_provider_json=cleaned_json,
            parsed_plan_response=parsed_resp,
            output_dir=output_dir,
        )

    # Guard 1: Required run metadata check
    if (
        not actual_model_id
        or not str(actual_model_id).strip()
        or not effective_commit_sha
        or effective_commit_sha == "UNKNOWN"
    ):
        return _finalize(
            BenchmarkRunStatus.MISSING_REQUIRED_RUN_METADATA,
            "NOT_EXECUTED_FAIL_CLOSED",
            error_detail="Missing required model_id or code_commit_sha metadata.",
        )

    # Guard 2: Expected model ID mismatch check (FAIL CLOSED before calling provider)
    if expected_model_id is not None and str(actual_model_id).strip() != expected_model_id.strip():
        return _finalize(
            BenchmarkRunStatus.MODEL_ID_MISMATCH,
            "NOT_EXECUTED_FAIL_CLOSED",
            error_detail=(
                f"Configured model_id '{actual_model_id}' does not match "
                f"expected_model_id '{expected_model_id}'."
            ),
        )

    # Guard 3: Explicit rejection of mock or fallback execution
    if force_mock_mode:
        return _finalize(
            BenchmarkRunStatus.MOCK_OR_FALLBACK_RUN,
            "MOCK_REJECTED_FAIL_CLOSED",
            error_detail="Mock or fallback execution is forbidden in W06 scientific benchmark mode.",
        )

    effective_api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
    if client is None and (not effective_api_key or not str(effective_api_key).strip()):
        return _finalize(
            BenchmarkRunStatus.LIVE_PROVIDER_REQUIRED,
            "NOT_EXECUTED_FAIL_CLOSED",
            error_detail="GEMINI_API_KEY is absent; live provider execution is required and canned mock fallback is forbidden.",
        )

    if client is not None:
        active_client = client
    else:
        if genai is None:
            return _finalize(
                BenchmarkRunStatus.LIVE_PROVIDER_REQUIRED,
                "NOT_EXECUTED_FAIL_CLOSED",
                error_detail="google-genai SDK is not installed in the current environment.",
            )
        active_client = genai.Client(api_key=effective_api_key)

    if types is not None:
        call_config = types.GenerateContentConfig(
            temperature=BENCHMARK_TEMPERATURE,
            max_output_tokens=settings.PLANNER_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            http_options=types.HttpOptions(timeout=settings.PLANNER_TIMEOUT_MS),
        )
    else:
        call_config = SimpleNamespace(
            temperature=BENCHMARK_TEMPERATURE,
            max_output_tokens=settings.PLANNER_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            http_options=SimpleNamespace(timeout=settings.PLANNER_TIMEOUT_MS),
        )

    # Live provider call with tight latency measurement boundary (no retries)
    t_start = clock_fn()
    try:
        provider_response = active_client.models.generate_content(
            model=actual_model_id,
            contents=prompt,
            config=call_config,
        )
    except Exception as exc:
        t_end = clock_fn()
        latency_ms = round((t_end - t_start) * 1000.0, 3)
        return _finalize(
            BenchmarkRunStatus.API_ERROR,
            "LIVE_PROVIDER",
            latency_ms=latency_ms,
            error_detail=f"Provider API error ({type(exc).__name__}): {exc}",
        )
    t_end = clock_fn()
    latency_ms = round((t_end - t_start) * 1000.0, 3)

    usage_metadata = extract_authoritative_usage_metadata(provider_response)
    raw_text = getattr(provider_response, "text", None)
    if not isinstance(raw_text, str):
        raw_text = ""

    # Always preserve raw provider output before cleaning or parsing
    raw_response_sha256 = write_exact_utf8_text(
        output_dir / "raw_provider_response.txt",
        raw_text,
    )

    if not raw_text.strip():
        return _finalize(
            BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
            "LIVE_PROVIDER",
            latency_ms=latency_ms,
            usage=usage_metadata,
            raw_text=raw_text,
            cleaned_json="",
            raw_sha=raw_response_sha256,
            error_detail="Provider returned empty response text.",
        )

    cleaned_json = clean_benchmark_json_response(raw_text)
    try:
        decoded_json = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        return _finalize(
            BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
            "LIVE_PROVIDER",
            latency_ms=latency_ms,
            usage=usage_metadata,
            raw_text=raw_text,
            cleaned_json=cleaned_json,
            raw_sha=raw_response_sha256,
            error_detail=f"Invalid JSON from provider: {exc}",
        )

    try:
        parsed_plan = parse_strict_benchmark_plan_response(
            raw_data=decoded_json,
            scenario=scenario,
            plan_id=effective_run_id,
        )
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        return _finalize(
            BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
            "LIVE_PROVIDER",
            latency_ms=latency_ms,
            usage=usage_metadata,
            raw_text=raw_text,
            cleaned_json=cleaned_json,
            raw_sha=raw_response_sha256,
            error_detail=f"Output failed strict benchmark schema validation: {exc}",
        )

    parsed_response_sha256 = write_canonical_json(
        output_dir / "parsed_plan_response.json",
        parsed_plan.model_dump(),
    )

    return _finalize(
        BenchmarkRunStatus.VALID,
        "LIVE_PROVIDER",
        latency_ms=latency_ms,
        usage=usage_metadata,
        raw_text=raw_text,
        cleaned_json=cleaned_json,
        parsed_resp=parsed_plan,
        raw_sha=raw_response_sha256,
        parsed_sha=parsed_response_sha256,
    )
