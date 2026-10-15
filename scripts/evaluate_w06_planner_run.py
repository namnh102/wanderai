#!/usr/bin/env python3
"""Controlled CLI entrypoint for W06 Deterministic Core Constraint Evaluator (W06-INSTRUMENT-01B).

Evaluates a single persisted benchmark scenario run directory and writes scenario_evaluation.json.
Does NOT aggregate multiple scenarios or compute final CORE_SCENARIO_PASS (opening-hours evaluation belongs to 01C).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    evaluate_run_directory,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="W06 Deterministic Core Constraint Evaluator CLI (W06-INSTRUMENT-01B)"
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to a single persisted benchmark scenario run directory.",
    )
    parser.add_argument(
        "--output",
        required=False,
        default=None,
        type=Path,
        help="Optional output path for scenario_evaluation.json (defaults to <run-dir>/scenario_evaluation.json).",
    )
    parser.add_argument(
        "--catalog",
        required=False,
        default=None,
        type=Path,
        help="Optional override path for frozen catalog JSON.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        result = evaluate_run_directory(
            run_dir=args.run_dir,
            output_path=args.output,
            catalog_path=args.catalog,
        )
    except Exception as exc:
        error_payload = {
            "evaluation_status": "REJECTED_INVALID_INPUT",
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(error_payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    if (
        result.evaluation_status != "EVALUATED"
        or not result.evidence_integrity_valid
        or not result.run_valid
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
