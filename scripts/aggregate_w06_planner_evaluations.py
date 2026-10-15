#!/usr/bin/env python3
"""Controlled CLI entrypoint for W06 Batch Statistical Aggregator (W06-INSTRUMENT-01C).

Aggregates persisted single-scenario evaluation results against an authoritative
assignment manifest without auto-discovering or omitting missing assigned scenarios.
"""
import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.evaluation.planner_benchmark_aggregator import (  # noqa: E402
    aggregate_evaluations_from_disk,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="W06 Deterministic Batch Statistical Aggregation CLI (W06-INSTRUMENT-01C)"
    )
    parser.add_argument(
        "--assignment-manifest",
        required=True,
        type=Path,
        help="Path to the authoritative assignment manifest JSON file.",
    )
    parser.add_argument(
        "--evaluations-dir",
        required=True,
        type=Path,
        help="Directory containing persisted scenario_evaluation.json files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for the canonical batch aggregation JSON.",
    )
    parser.add_argument(
        "--final-100",
        action="store_true",
        default=False,
        help="Enable strict FINAL_100 mode (requires exactly 100 assigned scenarios: 34 ha-noi, 33 da-nang, 33 ha-long).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        result = aggregate_evaluations_from_disk(
            assignment_manifest_path=args.assignment_manifest,
            evaluations_dir=args.evaluations_dir,
            output_path=args.output,
            final_100_mode=args.final_100,
        )
    except Exception as exc:
        error_payload = {
            "aggregation_status": "REJECTED_INVALID_BATCH_EVIDENCE",
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(error_payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
