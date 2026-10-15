"""CLI wrapper for W06 deterministic scenario generator DRY-RUN mode (W06-SCENARIO-GENERATOR-01).

IMPORTANT SAFETY BOUNDARIES:
- Runs ONLY in DRY_RUN / SYNTHETIC_GENERATOR_QA mode.
- Defaults to stdout summary output.
- If --output-json is provided, refuses to write to any path inside data/evaluation/w06/
  or data/curated/ or any path containing 'p11', 'final_100', or 'prereg' so it can NEVER
  be mistaken for or overwrite final frozen W06 scenario artifacts.
"""
import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    DEFAULT_SCENARIO_GENERATION_SEED,
    canonical_json_bytes,
    generate_dry_run_scenarios,
    sha256_hex,
)

FORBIDDEN_OUTPUT_SUBSTRINGS = (
    "p11",
    "final_100",
    "prereg",
    "w06_scenario_method_lock",
    "w06_scenario_support_matrix",
    "w06_measurement_contract",
)


def _validate_safe_dry_run_output_path(output_path: Path) -> Path:
    resolved = output_path.resolve()
    w06_dir = (REPO_ROOT / "data" / "evaluation" / "w06").resolve()
    curated_dir = (REPO_ROOT / "data" / "curated").resolve()

    if resolved == w06_dir or w06_dir in resolved.parents:
        raise ValueError(
            f"Refusing to write DRY_RUN output inside protected directory {w06_dir}: {resolved}"
        )
    if resolved == curated_dir or curated_dir in resolved.parents:
        raise ValueError(
            f"Refusing to write DRY_RUN output inside protected directory {curated_dir}: {resolved}"
        )
    lower_name = resolved.name.lower()
    for token in FORBIDDEN_OUTPUT_SUBSTRINGS:
        if token in lower_name:
            raise ValueError(
                f"Refusing to write DRY_RUN output to path matching final/protected token '{token}': {resolved}"
            )
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run W06 deterministic scenario generator in DRY_RUN / SYNTHETIC_GENERATOR_QA mode."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SCENARIO_GENERATION_SEED,
        help="Deterministic generation seed (must equal frozen seed 2026101506).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional temporary/test path to write full dry-run JSON bundle (protected repo paths forbidden).",
    )
    args = parser.parse_args(argv)

    bundle = generate_dry_run_scenarios(seed=args.seed)
    raw_bytes = canonical_json_bytes(bundle.model_dump(mode="json"))
    bundle_sha256 = sha256_hex(raw_bytes)

    if args.output_json is not None:
        safe_target = _validate_safe_dry_run_output_path(args.output_json)
        safe_target.parent.mkdir(parents=True, exist_ok=True)
        safe_target.write_bytes(raw_bytes)

    summary = {
        "generator_version": bundle.generator_version,
        "run_mode": bundle.run_mode,
        "fixture_label": bundle.fixture_label,
        "is_final_100_scenarios": bundle.is_final_100_scenarios,
        "real_scenarios_generated": bundle.real_scenarios_generated,
        "p11_created": bundle.p11_created,
        "seed": bundle.seed,
        "slot_count": bundle.slot_count,
        "bundle_sha256": bundle_sha256,
        "locked_marginal_counts": bundle.cross_balance_report.locked_marginal_counts,
        "support_class_counts": bundle.cross_balance_report.support_class_counts,
        "rejection_log_count": bundle.rejection_log_count,
        "rejection_reason_counts": bundle.rejection_reason_counts,
    }
    sys.stdout.write(canonical_json_bytes(summary).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
