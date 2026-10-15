"""Root-level verification suite for W06-INSTRUMENT-01D (01D-01..01D-27 + repository invariants).

Re-exports all 27 unit tests from apps/ai-service/tests/test_planner_benchmark_01d.py
and verifies repository-level receipt, artifact hash, and boundary invariants.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_TARGET_TEST_FILE = AI_SERVICE_ROOT / "tests" / "test_planner_benchmark_01d.py"
_SPEC = importlib.util.spec_from_file_location("test_planner_benchmark_01d", _TARGET_TEST_FILE)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if _name.startswith("test_w06_i01d_"):
        globals()[_name] = getattr(_MODULE, _name)

RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_instrument_01d_receipt_v1.json"
RESEARCH_DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_instrument_01d_min_poi_visits_v1.md"
METHOD_LOCK_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_method_lock_v1.json"
SUPPORT_MATRIX_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_support_matrix_v1.json"
MEASUREMENT_CONTRACT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
PROMPT_SOURCE_PATH = AI_SERVICE_ROOT / "app" / "prompts" / "planner_benchmark_prompt.py"
EVALUATOR_SOURCE_PATH = AI_SERVICE_ROOT / "app" / "evaluation" / "planner_benchmark_evaluator.py"

EXPECTED_METHOD_LOCK_SHA256 = "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
EXPECTED_SUPPORT_MATRIX_SHA256 = "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
EXPECTED_BASE_DEVELOP_SHA = "e5e1f450f68772b2fdc09e37eef58fd6bd5509ba"

EXPECTED_PROTECTED_FILE_LF_SHA256 = {
    "data/evaluation/w06/w06_measurement_contract_v1.json": "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": EXPECTED_METHOD_LOCK_SHA256,
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": EXPECTED_SUPPORT_MATRIX_SHA256,
    "data/evaluation/w06/w06_instrument_01a_receipt_v1.json": "30348cdbb98af9b5ac023eb86e55558c1efdb0f80eb61f3982830bfa96050048",
    "data/evaluation/w06/w06_instrument_01b_receipt_v1.json": "f78245dce3f3b1c45023ff22225a63dd710304ffbd8e2a30e66450129dff47d3",
    "data/evaluation/w06/w06_instrument_01c_receipt_v1.json": "2d729e2a294b4c92918de55d2fea56afbaa5d5c64731ff495bc0517e2dd7ce3e",
    "data/evaluation/w06/w06_instrument_validation_01_receipt_v1.json": "f1756338123ad362a647d14a73f289b8af33bc9cbed01b80109e4f8a2cbeac79",
    "apps/ai-service/app/prompts/planner_prompt.py": "31387107994ed10aa0b5d42999dc4c46dcf5f408c6d9ca454db2b0ab8084ef65",
    "apps/ai-service/app/schemas/planner.py": "1792dadcfa681ef75df3d66fb291b4d6702c6cced4fb4aab5d9e571884dc8685",
    "apps/ai-service/app/schemas/planner_benchmark.py": "3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712",
}


def _lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def test_w06_i01d_repo_receipt_identity_and_hashes():
    """Verify W06-INSTRUMENT-01D receipt exists, is canonical JSON, and pins exact hashes."""
    assert RECEIPT_PATH.exists(), f"Missing {RECEIPT_PATH}"
    raw = RECEIPT_PATH.read_bytes()
    receipt = json.loads(raw.decode("utf-8"))
    canonical = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    assert raw == canonical, "w06_instrument_01d_receipt_v1.json must be canonical UTF-8 LF JSON"

    assert receipt["instrument_id"] == "W06-INSTRUMENT-01D"
    assert receipt["instrument_version"] == "1.0.0"
    assert receipt["purpose"] == "ALIGN_EVALUATOR_AND_BENCHMARK_PROMPT_WITH_FROZEN_MINIMUM_POI_VISITS_PER_DAY"
    assert receipt["source_method_lock_id"] == "W06-SCENARIO-METHOD-LOCK-01"
    assert receipt["source_method_lock_version"] == "1.0.0"
    assert receipt["source_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert receipt["min_poi_visits_per_day"] == 2
    assert receipt["required_activity_kind"] == "POI_VISIT"
    assert receipt["transit_only_counts_toward_minimum"] is False
    assert receipt["prompt_version"] == "TRAVEL_PLANNER_BENCHMARK_V2"
    assert receipt["evaluator_version"] == "W06-CORE-EVALUATOR-01D-V1.0.0"

    assert receipt["method_lock_sha256"] == EXPECTED_METHOD_LOCK_SHA256
    assert receipt["support_matrix_sha256"] == EXPECTED_SUPPORT_MATRIX_SHA256
    assert receipt["prompt_source_sha256"] == _lf_sha256(PROMPT_SOURCE_PATH)
    assert receipt["evaluator_source_sha256"] == _lf_sha256(EVALUATOR_SOURCE_PATH)

    hashes = receipt["artifact_hashes"]
    assert hashes["method_lock_artifact_sha256"] == _lf_sha256(METHOD_LOCK_PATH)
    assert hashes["support_matrix_artifact_sha256"] == _lf_sha256(SUPPORT_MATRIX_PATH)
    assert hashes["prompt_source_file_sha256"] == _lf_sha256(PROMPT_SOURCE_PATH)
    assert hashes["evaluator_source_file_sha256"] == _lf_sha256(EVALUATOR_SOURCE_PATH)


def test_w06_i01d_repo_frozen_artifacts_and_boundaries():
    """Verify frozen method lock, support matrix, measurement contract, and scientific boundaries."""
    assert RESEARCH_DOC_PATH.exists(), f"Missing {RESEARCH_DOC_PATH}"
    doc_text = RESEARCH_DOC_PATH.read_text(encoding="utf-8")
    assert "W06-INSTRUMENT-01D" in doc_text
    assert "TRAVEL_PLANNER_BENCHMARK_V2" in doc_text
    assert "W06-CORE-EVALUATOR-01D-V1.0.0" in doc_text
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in doc_text

    # Method lock and support matrix byte/hash unchanged
    assert _lf_sha256(METHOD_LOCK_PATH) == EXPECTED_METHOD_LOCK_SHA256
    assert hashlib.sha256(METHOD_LOCK_PATH.read_bytes()).hexdigest() == EXPECTED_METHOD_LOCK_SHA256
    assert _lf_sha256(SUPPORT_MATRIX_PATH) == EXPECTED_SUPPORT_MATRIX_SHA256
    assert hashlib.sha256(SUPPORT_MATRIX_PATH.read_bytes()).hexdigest() == EXPECTED_SUPPORT_MATRIX_SHA256

    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    for flag in (
        "real_scenarios_generated",
        "p11_created",
        "preregistration_created",
        "gemini_called",
        "scientific_results_generated",
        "production_planner_modified",
        "w5_modified",
        "historical_measurement_contract_modified",
    ):
        assert receipt[flag] is False
        assert receipt["boundary_flags"][flag] is False

    # Confirm no P11 or final scenario manifest files exist
    w06_dir = REPO_ROOT / "data" / "evaluation" / "w06"
    for p in w06_dir.rglob("*"):
        name_lower = p.name.lower()
        assert "p11" not in name_lower, f"Unexpected P11 file: {p}"
        assert "final_100" not in name_lower, f"Unexpected final 100 scenario file: {p}"
        assert "prereg" not in name_lower, f"Unexpected preregistration file: {p}"

    # Verify cryptographic SHA256 digests of all protected historical and production planner files
    for rel_path, expected_sha in EXPECTED_PROTECTED_FILE_LF_SHA256.items():
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), f"Missing protected file: {rel_path}"
        assert _lf_sha256(full_path) == expected_sha, f"Protected file modified: {rel_path}"

    # Also verify git diff against base develop SHA when full git history is present
    has_base_commit = subprocess.run(
        ["git", "cat-file", "-e", f"{EXPECTED_BASE_DEVELOP_SHA}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if has_base_commit.returncode == 0:
        diff_proc = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                EXPECTED_BASE_DEVELOP_SHA,
                "--",
                *EXPECTED_PROTECTED_FILE_LF_SHA256.keys(),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert diff_proc.stdout.strip() == "", f"Protected files modified: {diff_proc.stdout}"
