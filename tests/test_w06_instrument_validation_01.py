"""Root pytest discovery wrapper for W06-INSTRUMENT-VALIDATION-01 adversarial validation gate tests (W06-VAL-01..44).

Re-exports the 44 adversarial assertions from apps/ai-service/tests/test_planner_benchmark_validation_gate.py
so both root pytest (data-contract CI job) and apps/ai-service pytest (ai-service CI job)
execute the complete W06-VAL-01..44 suite.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
AI_SERVICE_TESTS = AI_SERVICE_ROOT / "tests"

for p in (str(AI_SERVICE_ROOT), str(AI_SERVICE_TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_planner_benchmark_validation_gate import *  # noqa: F401, F403, E402
