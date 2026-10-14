#!/usr/bin/env python3
"""Controlled CLI entrypoint for W06 Planner Benchmark Instrumentation (W06-INSTRUMENT-01A).

Modes:
  - validate-environment: Offline check of catalog, contract, model config, and benchmark prompt.
  - prepare: Validate a single scenario, build catalog context + prompt, and write prep artifacts (no provider call).
  - execute: Execute a single scenario via live-only provider harness and persist forensic run evidence.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.config import settings  # noqa: E402
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
    DEFAULT_CATALOG_PATH,
    TRAVEL_PLANNER_BENCHMARK_V1,
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    EXPECTED_PRIMARY_CATALOG_COUNTS,
    PRIMARY_BENCHMARK_DESTINATIONS,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
)
from app.services.planner_benchmark_runner import (  # noqa: E402
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_SOURCE_COMMIT,
    MEASUREMENT_CONTRACT_VERSION,
    execute_benchmark_scenario,
    prepare_benchmark_scenario,
)

CONTRACT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"


def run_validate_environment(
    catalog_path: Optional[Path] = None,
    contract_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate offline benchmark prerequisites and report live provider availability."""
    target_catalog = catalog_path or DEFAULT_CATALOG_PATH
    target_contract = contract_path or CONTRACT_JSON_PATH

    catalog_exists = target_catalog.exists()
    contract_exists = target_contract.exists()

    destination_counts: Dict[str, int] = {}
    counts_match = False
    if catalog_exists:
        for slug in PRIMARY_BENCHMARK_DESTINATIONS:
            pois = build_destination_catalog_context(slug, catalog_path=target_catalog)
            destination_counts[slug] = len(pois)
        counts_match = destination_counts == EXPECTED_PRIMARY_CATALOG_COUNTS

    contract_valid = False
    if contract_exists:
        contract_doc = json.loads(target_contract.read_text(encoding="utf-8"))
        contract_valid = (
            contract_doc.get("contract_id") == MEASUREMENT_CONTRACT_ID
            and contract_doc.get("contract_version") == MEASUREMENT_CONTRACT_VERSION
        )

    model_config_present = bool(settings.PLANNER_MODEL and str(settings.PLANNER_MODEL).strip())
    benchmark_prompt_available = bool(
        BENCHMARK_PROMPT_VERSION == "TRAVEL_PLANNER_BENCHMARK_V1"
        and TRAVEL_PLANNER_BENCHMARK_V1.strip()
    )
    live_execution_available = bool(settings.GEMINI_API_KEY and str(settings.GEMINI_API_KEY).strip())

    environment_valid = all(
        [
            catalog_exists,
            counts_match,
            contract_exists,
            contract_valid,
            model_config_present,
            benchmark_prompt_available,
        ]
    )

    return {
        "environment_valid": environment_valid,
        "catalog_exists": catalog_exists,
        "primary_destination_counts": destination_counts,
        "primary_destination_counts_valid": counts_match,
        "total_primary_catalog_pois": sum(destination_counts.values()),
        "contract_exists": contract_exists,
        "contract_valid": contract_valid,
        "measurement_contract_id": MEASUREMENT_CONTRACT_ID,
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
        "measurement_contract_source_commit": MEASUREMENT_CONTRACT_SOURCE_COMMIT,
        "model_config_present": model_config_present,
        "configured_model_id": settings.PLANNER_MODEL,
        "benchmark_prompt_available": benchmark_prompt_available,
        "benchmark_prompt_version": BENCHMARK_PROMPT_VERSION,
        "live_execution_available": live_execution_available,
    }


def _load_scenario_input(scenario_path: Path) -> BenchmarkScenarioInput:
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    return BenchmarkScenarioInput.model_validate(raw)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="W06 Planner Benchmark Instrumentation CLI (W06-INSTRUMENT-01A)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "validate-environment",
        help="Validate catalog, contract, model config, and benchmark prompt (no API key required).",
    )

    prep_parser = subparsers.add_parser(
        "prepare",
        help="Validate a scenario, build destination catalog context and prompt, and write prep metadata without calling provider.",
    )
    prep_parser.add_argument("--scenario", required=True, type=Path, help="Path to scenario JSON")
    prep_parser.add_argument("--output", required=True, type=Path, help="Output directory")

    exec_parser = subparsers.add_parser(
        "execute",
        help="Execute a single scenario using the live-only benchmark provider and persist forensic evidence.",
    )
    exec_parser.add_argument("--scenario", required=True, type=Path, help="Path to scenario JSON")
    exec_parser.add_argument("--output", required=True, type=Path, help="Private run output directory")
    exec_parser.add_argument(
        "--expected-model-id",
        required=False,
        default=None,
        help="Optional expected model identifier guard (fails closed on mismatch).",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-environment":
        report = run_validate_environment()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["environment_valid"] else 1

    if args.command == "prepare":
        scenario = _load_scenario_input(args.scenario)
        prep_manifest = prepare_benchmark_scenario(scenario=scenario, output_dir=args.output)
        print(json.dumps(prep_manifest, ensure_ascii=False, indent=2))
        return 0

    if args.command == "execute":
        scenario = _load_scenario_input(args.scenario)
        result = execute_benchmark_scenario(
            scenario=scenario,
            output_dir=args.output,
            expected_model_id=args.expected_model_id,
        )
        print(json.dumps(result.manifest.model_dump(), ensure_ascii=False, indent=2))
        return 0 if result.run_status == BenchmarkRunStatus.VALID else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
