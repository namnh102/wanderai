"""Root-level test runner entrypoint for W06-INSTRUMENT-01B (re-exports all W06-I01B-01..30 tests)."""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "ai_service_test_planner_benchmark_evaluator",
    AI_SERVICE_ROOT / "tests" / "test_planner_benchmark_evaluator.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

for _attr in dir(_MOD):
    if _attr.startswith("test_w06_i01b_"):
        globals()[_attr] = getattr(_MOD, _attr)
