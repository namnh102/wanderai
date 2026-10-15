"""Root-level test discovery bridge for W06-INSTRUMENT-01C (W06-I01C-01..40).

Loads apps/ai-service/tests/test_planner_benchmark_01c.py via importlib so both root pytest
(including the CI data-contract job) and apps/ai-service pytest execute all 40 W06-I01C tests.
"""
import importlib.util
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_TARGET_TEST_FILE = AI_SERVICE_ROOT / "tests" / "test_planner_benchmark_01c.py"
_SPEC = importlib.util.spec_from_file_location("test_planner_benchmark_01c", _TARGET_TEST_FILE)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if _name.startswith("test_w06_i01c_"):
        globals()[_name] = getattr(_MODULE, _name)
