"""Root test discovery wrapper for W06-SCENARIO-GENERATOR-01."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

TARGET_TEST_PATH = (
    AI_SERVICE_ROOT / "tests" / "test_planner_scenario_generator.py"
)

_spec = importlib.util.spec_from_file_location(
    "_w06_planner_scenario_generator_tests", TARGET_TEST_PATH
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

for _attr_name in dir(_module):
    if _attr_name.startswith("test_w06_gen_"):
        globals()[_attr_name] = getattr(_module, _attr_name)
