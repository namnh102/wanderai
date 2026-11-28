"""Dual-scope W06 verifier: historical evidence at 33b44cb2 + live HEAD runtime, schema, config & artifact checks.

Preserves 100% of locked W06 hashes, receipts, research docs, and historical test files untouched:
  1. Verifies on live HEAD (and working tree) that all locked W06 research artifacts, receipts,
     cryptographic LF-SHA256 digests, benchmark schemas/prompts/evaluators, legacy evaluate_planner.py,
     W5 artifacts, and curated catalogs remain 100% intact since 33b44cb2.
  2. Executes the untouched W06 historical boundary test functions (9 root tests + PF-A-01 preflight)
     inside a temporary detached git worktree at W06 scientific closure SHA 33b44cb2.
  3. Executes live HEAD configuration, schema/OpenAPI, legacy/C4 evaluator, and POST /planner API
     backward-compatibility assertions carried over from mixed tests (W06-I01A-18 & PF-A-01).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"

W06_CLOSURE_SHA = "33b44cb2b7c694d616f7185c30fbe602711327e6"
PF_A_01_BASE_SHA = "ff40f42db163a21dfc85d467073e99f628e0154a"
AUDIT_01_BASE_SHA = "4de240aeaa5277420695ed5f1de85f7b67cd6c54"
CONTRACT_01_SOURCE_SHA = "7fd5364ed4671c06b0c911b6fd53bd9f54cbc322"
I01D_BASE_SHA = "e5e1f450f68772b2fdc09e37eef58fd6bd5509ba"

REQUIRED_HISTORICAL_COMMITS = (
    W06_CLOSURE_SHA,
    AUDIT_01_BASE_SHA,
    CONTRACT_01_SOURCE_SHA,
    I01D_BASE_SHA,
    PF_A_01_BASE_SHA,
)

FROZEN_W06_AND_RESEARCH_PATHSPECS = (
    "data/evaluation/w06/",
    "data/evaluation/planner/",
    "data/evaluation/w5/",
    "data/curated/",
    ":(exclude)data/curated/w07/",
    "docs/research/w06_measurement_capability_audit_v1.md",
    "docs/research/w06_measurement_contract_v1.md",
    "docs/research/w06_instrument_01d_min_poi_visits_v1.md",
    "docs/research/w06_scenario_generator_qa_01_v1.md",
    "apps/ai-service/app/evaluation/",
    "apps/ai-service/app/prompts/planner_benchmark_prompt.py",
    "apps/ai-service/app/schemas/planner_benchmark.py",
    "scripts/audit_w06_scenario_generator_dryrun.py",
    "apps/ai-service/recommendation/reca/contract.py",
)

EXPECTED_LIVE_PROTECTED_LF_SHA256 = {
    "data/evaluation/w06/w06_measurement_contract_v1.json": "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9",
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4",
    "data/evaluation/w06/w06_instrument_01a_receipt_v1.json": "30348cdbb98af9b5ac023eb86e55558c1efdb0f80eb61f3982830bfa96050048",
    "data/evaluation/w06/w06_instrument_01b_receipt_v1.json": "f78245dce3f3b1c45023ff22225a63dd710304ffbd8e2a30e66450129dff47d3",
    "data/evaluation/w06/w06_instrument_01c_receipt_v1.json": "2d729e2a294b4c92918de55d2fea56afbaa5d5c64731ff495bc0517e2dd7ce3e",
    "data/evaluation/w06/w06_instrument_validation_01_receipt_v1.json": "f1756338123ad362a647d14a73f289b8af33bc9cbed01b80109e4f8a2cbeac79",
    "apps/ai-service/app/schemas/planner_benchmark.py": "3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712",
    "apps/ai-service/app/evaluation/planner_scenario_generator.py": "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1",
    "scripts/audit_w06_scenario_generator_dryrun.py": "2e5a218fc49d4af0052dffa49c14a8a7d5d9818847fd6d37f647422a9cadc6fc",
    "data/curated/gomate_places_freeze_v2.json": "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    "apps/ai-service/recommendation/reca/contract.py": "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
}

HISTORICAL_ROOT_TESTS = (
    "tests/test_w06_instrument_01a.py::test_w06_i01a_18_production_planner_regression_tests_still_pass",
    "tests/test_w06_instrument_01d.py::test_w06_i01d_repo_frozen_artifacts_and_boundaries",
    "tests/test_w06_instrument_validation_01.py::test_w06_val_44_no_leakage_into_production_and_validation_gate_receipt_verified",
    "tests/test_w06_measurement_capability_audit.py::test_w06_audit_03_no_planner_behavior_modified",
    "tests/test_w06_measurement_capability_audit.py::test_w06_audit_04_no_evaluator_or_scenario_behavior_modified",
    "tests/test_w06_measurement_capability_audit.py::test_w06_audit_12_mock_fallback_path_documented",
    "tests/test_w06_measurement_contract.py::test_w06_contract_19_production_behavior_unchanged",
    "tests/test_w06_scenario_generator_01.py::test_w06_gen_38_production_planner_unchanged",
    "tests/test_w06_scenario_generator_qa_01.py::test_qa_non_interference_hashes_and_receipt_complete",
)


def _lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_lf_bytes(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _ensure_commit(sha: str) -> None:
    res = subprocess.run(
        ["git", "--no-optional-locks", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "--no-optional-locks", "fetch", "origin", sha, "--depth=1"],
            cwd=REPO_ROOT,
            check=True,
        )


def verify_frozen_w06_artifacts_on_head() -> None:
    print("[1/3] Checking locked W06 data, evaluators, cryptographic hashes & receipts on HEAD...")
    # 1A. Working-tree + index + HEAD git diff against W06_CLOSURE_SHA (catches committed & uncommitted edits)
    diff_res = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "diff",
            "--name-only",
            W06_CLOSURE_SHA,
            "--",
            *FROZEN_W06_AND_RESEARCH_PATHSPECS,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if diff_res.stdout.strip():
        raise AssertionError(
            f"Protected W06/W5/curated research artifact modified relative to {W06_CLOSURE_SHA}:\n{diff_res.stdout}"
        )

    # Also reject untracked files injected into protected evaluation directories
    untracked_res = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "data/evaluation/w06/",
            "data/evaluation/planner/",
            "data/evaluation/w5/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if untracked_res.stdout.strip():
        raise AssertionError(
            f"Unauthorized untracked file(s) in protected evaluation directories:\n{untracked_res.stdout}"
        )

    # 1B. Direct LF-SHA256 verification on live disk files (carried over from i01d & qa_non_interference)
    for rel_path, expected_sha in EXPECTED_LIVE_PROTECTED_LF_SHA256.items():
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            raise AssertionError(f"Missing protected file on HEAD: {rel_path}")
        actual_sha = _lf_sha256(full_path)
        if actual_sha != expected_sha:
            raise AssertionError(
                f"Protected artifact SHA-256 mismatch on {rel_path}: expected {expected_sha}, got {actual_sha}"
            )

    # 1C. Legacy scenario inventory & W06 receipt/contract invariants on HEAD (from val_44, i01d, audit_03, contract_19, qa_01)
    planner_eval_dir = REPO_ROOT / "data" / "evaluation" / "planner"
    scenario_files = sorted(p.name for p in planner_eval_dir.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"], (
        f"Unexpected scenario files in data/evaluation/planner: {scenario_files}"
    )

    w06_dir = REPO_ROOT / "data" / "evaluation" / "w06"
    audit_doc = json.loads((w06_dir / "w06_measurement_capability_audit_v1.json").read_text(encoding="utf-8"))
    assert audit_doc["planner_behavior_modified"] is False
    assert audit_doc["evaluator_behavior_modified"] is False

    contract_doc = json.loads((w06_dir / "w06_measurement_contract_v1.json").read_text(encoding="utf-8"))
    assert contract_doc["production_behavior_modified"] is False
    assert [p["id"] for p in contract_doc["required_instrumentation_prerequisites"]] == [
        f"P{i}" for i in range(1, 13)
    ]

    val_receipt = json.loads((w06_dir / "w06_instrument_validation_01_receipt_v1.json").read_text(encoding="utf-8"))
    assert val_receipt["gate_id"] == "W06-INSTRUMENT-VALIDATION-01"
    assert val_receipt["overall_gate_status"] == "PASS"
    assert val_receipt["adversarial_test_pass_count"] == 44

    qa_receipt_path = w06_dir / "w06_scenario_generator_qa_01_receipt_v1.json"
    qa_raw = qa_receipt_path.read_bytes().replace(b"\r\n", b"\n")
    qa_receipt = json.loads(qa_raw.decode("utf-8"))
    assert qa_raw == _canonical_json_lf_bytes(qa_receipt)
    assert qa_receipt["task_id"] == "W06-SCENARIO-GENERATOR-QA-01"
    assert qa_receipt["production_planner_modified"] is False

    print("  [PASS] All locked W06/W5/curated artifacts, SHA-256 digests, and receipts verified on HEAD.")


def verify_historical_w06_suite_at_closure(include_ai_service_preflight: bool) -> None:
    print(f"[2/3] Running untouched historical W06 test suite at {W06_CLOSURE_SHA[:8]}...")
    tmp_wt = Path(tempfile.mkdtemp(prefix="w06_closure_verify_"))
    env = {**os.environ, "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY") or "dummy-key-not-used-in-ci"}
    try:
        subprocess.run(
            ["git", "--no-optional-locks", "worktree", "add", "--detach", str(tmp_wt), W06_CLOSURE_SHA],
            cwd=REPO_ROOT,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", *HISTORICAL_ROOT_TESTS, "-q"],
            cwd=tmp_wt,
            env=env,
            check=True,
        )
        if include_ai_service_preflight:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_w06_model_preflight_01a_offline.py::test_pf_a_01_production_config_and_historical_tests_byte_identical_to_develop",
                    "-q",
                ],
                cwd=tmp_wt / "apps" / "ai-service",
                env=env,
                check=True,
            )
    finally:
        subprocess.run(
            ["git", "--no-optional-locks", "worktree", "remove", "--force", str(tmp_wt)],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        shutil.rmtree(tmp_wt, ignore_errors=True)
    print(f"  [PASS] Historical W06 suite passed 100% verbatim at {W06_CLOSURE_SHA[:8]}.")


def verify_live_config_schema_and_api_on_head(require_fastapi: bool) -> None:
    print("[3/3] Verifying live HEAD configuration, schema/OpenAPI, evaluators & POST /planner API...")
    # 3A. Configuration, requirements, LLM adapter & historical test file guards (carried over from PF-A-01)
    pf_diff = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "diff",
            "--name-only",
            PF_A_01_BASE_SHA,
            "--",
            "apps/ai-service/app/config.py",
            "apps/ai-service/requirements.txt",
            "requirements-data-contract.txt",
            "tests/test_w06_measurement_capability_audit.py",
            "apps/ai-service/app/llm/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if pf_diff.stdout.strip():
        raise AssertionError(
            f"Protected config/requirements/llm/audit-test files modified since {PF_A_01_BASE_SHA}:\n{pf_diff.stdout}"
        )

    contract_test_diff = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "diff",
            "-U0",
            PF_A_01_BASE_SHA,
            "--",
            "tests/test_w06_measurement_contract.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    changed_lines = [
        line
        for line in contract_test_diff.stdout.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
    ]
    assert changed_lines in ([], ['+            ":(exclude)data/curated/w07/",']), (
        f"Unexpected diff in tests/test_w06_measurement_contract.py: {changed_lines}"
    )

    # 3B. Runtime settings, Pydantic schemas & evaluators (runs in BOTH data-contract & ai-service)
    os.environ.setdefault("GEMINI_API_KEY", "dummy-key-not-used-in-ci")
    if str(AI_SERVICE_ROOT) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE_ROOT))

    from app.config import settings
    from app.evaluation.planner_benchmark_evaluator import EVALUATOR_VERSION, EVALUATOR_VERSION_01D
    from app.prompts.planner_prompt import build_planner_prompt
    from app.schemas.planner import ItineraryItem, PlanRequest, PlanResponse, TripContextRequest
    from app.services.c4_itinerary_evaluator import evaluate_c4_itinerary

    assert settings.PLANNER_MODEL == "gemini-3.5-flash", (
        f"Unexpected PLANNER_MODEL={settings.PLANNER_MODEL}"
    )
    assert EVALUATOR_VERSION == EVALUATOR_VERSION_01D == "W06-CORE-EVALUATOR-01D-V1.0.0"

    # Schema checks: legacy PlanRequest + TripContextRequest + nullable vs zero ItineraryItem
    prod_req = PlanRequest(destination="Đà Nẵng", days=2, style="family", interests=["beach", "food"])
    ctx_req = TripContextRequest(destination="Đà Nẵng", days=2, budget=3000000, interests=["beach", "food"])
    item_null = ItineraryItem(activity="Cafe", estimated_cost=None)
    item_zero = ItineraryItem(activity="Biển Mỹ Khê", estimated_cost=0, cost_status="KNOWN")
    assert item_null.estimated_cost is None and item_null.cost_status == "UNKNOWN"
    assert item_zero.estimated_cost == 0 and item_zero.cost_status == "KNOWN"

    prod_prompt = build_planner_prompt(destination=prod_req.destination, days=ctx_req.days)
    assert "Đà Nẵng" in prod_prompt

    # 3C. FastAPI OpenAPI snapshot parity & live POST /planner check (mandatory in ai-service job)
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        if require_fastapi:
            raise
        print("  [PASS] Live HEAD configuration, Pydantic schemas & evaluators verified (FastAPI HTTP check runs in ai-service job).")
        return

    from app.main import app

    openapi_path = REPO_ROOT / "docs" / "contracts" / "ai-service.openapi.json"
    expected_openapi = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    actual_openapi = openapi_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual_openapi == expected_openapi, "OpenAPI snapshot docs/contracts/ai-service.openapi.json is stale"

    client = TestClient(app)
    with patch("app.routers.planner._client", None):
        resp = client.post(
            "/planner",
            json={
                "destination": "Đà Nẵng",
                "days": 2,
                "budget": 3000000,
                "travel_style": "family",
                "interests": ["beach", "food"],
            },
        )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    validated = PlanResponse.model_validate(body)
    assert validated.destination == "Đà Nẵng"
    assert validated.total_days == 2
    assert len(validated.days) == 2

    c4_eval = evaluate_c4_itinerary(body, {"scenario_id": "head_smoke", "expected_constraints": {"min_days": 2, "max_days": 2}})
    assert c4_eval["success"] is True, f"C4 evaluator failed on live /planner output: {c4_eval['failed_checks']}"
    print("  [PASS] Live HEAD configuration, schemas, OpenAPI, evaluators & POST /planner API verified.")


def main() -> int:
    include_preflight = "--include-ai-service-preflight" in sys.argv
    for sha in REQUIRED_HISTORICAL_COMMITS:
        _ensure_commit(sha)

    verify_frozen_w06_artifacts_on_head()
    verify_historical_w06_suite_at_closure(include_ai_service_preflight=include_preflight)
    verify_live_config_schema_and_api_on_head(require_fastapi=include_preflight)
    print("W06 DUAL-SCOPE VERIFICATION (33b44cb2 + LIVE HEAD): PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
