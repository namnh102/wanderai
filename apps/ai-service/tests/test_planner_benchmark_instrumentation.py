"""Focused tests for W06-INSTRUMENT-01A (Groundable Benchmark Planner Path & Live-Run Evidence Harness).

Covers W06-I01A-01 through W06-I01A-20.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AI_SERVICE_ROOT.parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
    DEFAULT_CATALOG_PATH,
    build_benchmark_planner_prompt,
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    ActivityKind,
    BenchmarkItineraryItem,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
)
from app.services.planner_benchmark_runner import (  # noqa: E402
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_SOURCE_COMMIT,
    MEASUREMENT_CONTRACT_VERSION,
    execute_benchmark_scenario,
    normalize_lf_bytes,
    prepare_benchmark_scenario,
    sha256_bytes,
)
from scripts.run_w06_planner_benchmark import main as benchmark_cli_main  # noqa: E402
from scripts.run_w06_planner_benchmark import run_validate_environment  # noqa: E402

RECEIPT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_instrument_01a_receipt_v1.json"
RECEIPT_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_instrument_01a_implementation_v1.md"
CONTRACT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
PLANNER_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "planner"


def _make_synthetic_test_scenario(destination_slug: str = "da-nang") -> BenchmarkScenarioInput:
    dest_names = {"ha-noi": "Hà Nội", "da-nang": "Đà Nẵng", "ha-long": "Hạ Long"}
    return BenchmarkScenarioInput(
        scenario_id="SYNTHETIC_TEST_ONLY_DN_2D",
        destination_slug=destination_slug,
        destination=dest_names[destination_slug],
        days=2,
        start_date="2026-07-01",
        end_date="2026-07-02",
        budget=4000000,
        currency="VND",
        travel_style="comfort",
        interests=["beach_island", "food_cuisine", "culture_history"],
        notes="SYNTHETIC_TEST_ONLY fixture for W06-INSTRUMENT-01A unit tests",
        allow_revisit_place_ids=False,
        fixture_label="SYNTHETIC_TEST_ONLY",
    )


def _make_valid_provider_json(first_place_id: str, first_place_name: str, second_place_id: str, second_place_name: str) -> str:
    payload = {
        "destination": "Đà Nẵng",
        "total_days": 2,
        "overview": "SYNTHETIC_TEST_ONLY 2-day benchmark itinerary.",
        "best_time_to_visit": "Tháng 3 - Tháng 8",
        "general_tips": ["Mang kem chống nắng"],
        "days": [
            {
                "day_number": 1,
                "date": "2026-07-01",
                "title": "Ngày 1: Khám phá Đà Nẵng",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:00",
                        "end_time": "09:30",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Tham quan {first_place_name}",
                        "place_name": first_place_name,
                        "place_id": first_place_id,
                        "notes": "Buổi sáng",
                        "estimated_cost": 50000,
                        "transport_mode": "taxi",
                    },
                    {
                        "order_index": 2,
                        "start_time": "09:30",
                        "end_time": "10:00",
                        "activity_kind": "TRANSIT_ONLY",
                        "activity": "Di chuyển nội đô",
                        "place_name": None,
                        "place_id": None,
                        "notes": "Di chuyển bằng taxi",
                        "estimated_cost": 30000,
                        "transport_mode": "taxi",
                    },
                ],
            },
            {
                "day_number": 2,
                "date": "2026-07-02",
                "title": "Ngày 2: Trải nghiệm Đà Nẵng",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:30",
                        "end_time": "10:30",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Trải nghiệm {second_place_name}",
                        "place_name": second_place_name,
                        "place_id": second_place_id,
                        "notes": "Buổi sáng ngày 2",
                        "estimated_cost": 40000,
                        "transport_mode": "motorbike",
                    }
                ],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def test_w06_i01a_01_primary_destination_catalog_counts_exact():
    """W06-I01A-01: primary destination catalog counts exactly 145 / 289 / 188 and deterministically ordered."""
    hn = build_destination_catalog_context("ha-noi")
    dn = build_destination_catalog_context("da-nang")
    hl = build_destination_catalog_context("ha-long")

    assert len(hn) == 145
    assert len(dn) == 289
    assert len(hl) == 188
    assert len(hn) + len(dn) + len(hl) == 622

    # Deterministic ordering by place_id ascending
    assert [p.place_id for p in hn] == sorted(p.place_id for p in hn)
    assert [p.place_id for p in dn] == sorted(p.place_id for p in dn)
    assert [p.place_id for p in hl] == sorted(p.place_id for p in hl)


def test_w06_i01a_02_non_core_pois_excluded_from_benchmark_catalog():
    """W06-I01A-02: non-core POIs excluded from benchmark catalog and non-primary destinations rejected."""
    raw_places = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    non_core_ids = {p["place_id"] for p in raw_places if not p.get("is_rec_a_core_v2")}
    assert len(non_core_ids) == 137

    for slug in ("ha-noi", "da-nang", "ha-long"):
        ctx = build_destination_catalog_context(slug)
        ctx_ids = {p.place_id for p in ctx}
        assert ctx_ids.isdisjoint(non_core_ids)
        assert all(p.destination_slug == slug for p in ctx)

    for forbidden_slug in ("hoi-an", "hue", "nha-trang", "ha-giang", "moc-chau", "unknown"):
        with pytest.raises(ValueError, match="not an allowed primary benchmark destination"):
            build_destination_catalog_context(forbidden_slug)


def test_w06_i01a_03_poi_visit_requires_non_empty_place_id():
    """W06-I01A-03: POI_VISIT requires non-empty place_id."""
    valid_item = BenchmarkItineraryItem(
        order_index=1,
        start_time="08:00",
        end_time="09:30",
        activity_kind=ActivityKind.POI_VISIT,
        activity="Tham quan Cầu Rồng",
        place_name="Cầu Rồng",
        place_id="7d7e049e-d3f9-436a-aa1a-bf49ca0d1206",
        notes=None,
        estimated_cost=0,
        transport_mode="motorbike",
    )
    assert valid_item.place_id == "7d7e049e-d3f9-436a-aa1a-bf49ca0d1206"

    for invalid_place_id in (None, "", "   "):
        with pytest.raises(ValidationError, match="non-empty canonical place_id"):
            BenchmarkItineraryItem(
                order_index=1,
                start_time="08:00",
                end_time="09:30",
                activity_kind=ActivityKind.POI_VISIT,
                activity="Tham quan Cầu Rồng",
                place_name="Cầu Rồng",
                place_id=invalid_place_id,
                notes=None,
                estimated_cost=0,
                transport_mode="motorbike",
            )


def test_w06_i01a_04_transit_only_requires_null_place_id():
    """W06-I01A-04: TRANSIT_ONLY requires null place_id."""
    transit_item = BenchmarkItineraryItem(
        order_index=2,
        start_time="09:30",
        end_time="10:00",
        activity_kind=ActivityKind.TRANSIT_ONLY,
        activity="Di chuyển sang điểm tiếp theo",
        place_name=None,
        place_id=None,
        notes="Di chuyển bằng taxi",
        estimated_cost=30000,
        transport_mode="taxi",
    )
    assert transit_item.place_id is None

    with pytest.raises(ValidationError, match="TRANSIT_ONLY item must have place_id=null"):
        BenchmarkItineraryItem(
            order_index=2,
            start_time="09:30",
            end_time="10:00",
            activity_kind=ActivityKind.TRANSIT_ONLY,
            activity="Di chuyển",
            place_name=None,
            place_id="7d7e049e-d3f9-436a-aa1a-bf49ca0d1206",
            notes=None,
            estimated_cost=30000,
            transport_mode="taxi",
        )


def test_w06_i01a_05_unknown_activity_kind_rejected():
    """W06-I01A-05: unknown activity_kind rejected."""
    with pytest.raises(ValidationError):
        BenchmarkItineraryItem.model_validate(
            {
                "order_index": 1,
                "start_time": "08:00",
                "end_time": "09:00",
                "activity_kind": "MEAL_BREAK",
                "activity": "Ăn sáng",
                "place_name": "Quán phở",
                "place_id": "7d7e049e-d3f9-436a-aa1a-bf49ca0d1206",
                "notes": None,
                "estimated_cost": 40000,
                "transport_mode": "walk",
            }
        )


def test_w06_i01a_06_missing_activity_kind_rejected():
    """W06-I01A-06: missing activity_kind rejected (no silent default)."""
    with pytest.raises(ValidationError):
        BenchmarkItineraryItem.model_validate(
            {
                "order_index": 1,
                "start_time": "08:00",
                "end_time": "09:00",
                "activity": "Tham quan",
                "place_name": "Cầu Rồng",
                "place_id": "7d7e049e-d3f9-436a-aa1a-bf49ca0d1206",
                "notes": None,
                "estimated_cost": 0,
                "transport_mode": "walk",
            }
        )


def test_w06_i01a_07_non_canonical_interest_rejected():
    """W06-I01A-07: non-canonical interest rejected."""
    with pytest.raises(ValidationError, match="Non-canonical interest keys rejected"):
        BenchmarkScenarioInput(
            scenario_id="SYNTHETIC_TEST_BAD_INTEREST",
            destination_slug="da-nang",
            destination="Đà Nẵng",
            days=2,
            start_date="2026-07-01",
            end_date="2026-07-02",
            budget=3000000,
            travel_style="budget",
            interests=["beach", "food"],
        )


def test_w06_i01a_08_benchmark_prompt_contains_supplied_canonical_place_ids():
    """W06-I01A-08: benchmark prompt contains supplied canonical place_ids."""
    scenario = _make_synthetic_test_scenario("da-nang")
    catalog = build_destination_catalog_context("da-nang")
    prompt = build_benchmark_planner_prompt(scenario, catalog_pois=catalog)

    assert BENCHMARK_PROMPT_VERSION in prompt
    assert catalog[0].place_id in prompt
    assert catalog[-1].place_id in prompt
    assert f"ALLOWED REC-A-CORE-V2 POI CATALOG — {len(catalog)} POIs" in prompt


def test_w06_i01a_09_benchmark_prompt_instructs_exact_id_copying_and_no_invented_pois():
    """W06-I01A-09: benchmark prompt instructs exact-ID copying and no invented POIs."""
    scenario = _make_synthetic_test_scenario("ha-noi")
    prompt = build_benchmark_planner_prompt(scenario)

    assert '"activity_kind": "POI_VISIT"' in prompt
    assert '"activity_kind": "TRANSIT_ONLY"' in prompt
    assert "sao chép CHÍNH XÁC từng ký tự place_id" in prompt
    assert "TUYỆT ĐỐI KHÔNG tự bịa ra place_id hoặc địa điểm nằm ngoài danh mục" in prompt
    assert '"place_id": null' in prompt


def test_w06_i01a_10_missing_api_key_cannot_produce_canned_scientific_output(tmp_path: Path):
    """W06-I01A-10: missing API key cannot produce canned scientific output."""
    scenario = _make_synthetic_test_scenario("da-nang")
    out_dir = tmp_path / "no_api_key_run"

    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=out_dir,
        api_key="",
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert result.run_status == BenchmarkRunStatus.LIVE_PROVIDER_REQUIRED
    assert result.is_valid is False
    assert result.parsed_plan_response is None
    assert not (out_dir / "parsed_plan_response.json").exists()
    assert (out_dir / "run_manifest.json").exists()

    # Also verify explicit force_mock_mode is rejected with MOCK_OR_FALLBACK_RUN
    mock_dir = tmp_path / "mock_rejected_run"
    mock_result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=mock_dir,
        api_key="dummy-key",
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
        force_mock_mode=True,
    )
    assert mock_result.run_status == BenchmarkRunStatus.MOCK_OR_FALLBACK_RUN
    assert mock_result.parsed_plan_response is None


def test_w06_i01a_11_model_mismatch_fails_closed(tmp_path: Path):
    """W06-I01A-11: model mismatch fails closed without calling provider."""
    scenario = _make_synthetic_test_scenario("da-nang")
    called = False

    class NeverCallModels:
        def generate_content(self, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("Provider should not be called on MODEL_ID_MISMATCH")

    fake_client = SimpleNamespace(models=NeverCallModels())
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=tmp_path / "mismatch_run",
        expected_model_id="gemini-3.5-flash",
        configured_model_id="gemini-2.5-pro",
        client=fake_client,
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert called is False
    assert result.run_status == BenchmarkRunStatus.MODEL_ID_MISMATCH
    assert result.parsed_plan_response is None


def test_w06_i01a_12_raw_provider_output_preserved_on_parse_failure(tmp_path: Path):
    """W06-I01A-12: raw provider output preserved on parse failure (and schema failure)."""
    scenario = _make_synthetic_test_scenario("da-nang")
    corrupted_raw_text = "```json\n{\"destination\": \"Đà Nẵng\", \"days\": [BROKEN_JSON\n```"

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                text=corrupted_raw_text,
                usage_metadata=None,
            )
        )
    )
    out_dir = tmp_path / "unparsable_run"
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=out_dir,
        client=fake_client,
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert result.run_status == BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT
    assert result.raw_provider_response == corrupted_raw_text
    assert result.parsed_plan_response is None

    raw_file = out_dir / "raw_provider_response.txt"
    assert raw_file.exists()
    assert raw_file.read_bytes().decode("utf-8") == corrupted_raw_text
    assert result.manifest.raw_response_sha256 == sha256_bytes(raw_file.read_bytes())
    assert result.manifest.parsed_response_sha256 is None


def test_w06_i01a_13_token_fields_remain_null_when_authoritative_metadata_unavailable(tmp_path: Path):
    """W06-I01A-13: token fields remain null when authoritative metadata unavailable."""
    scenario = _make_synthetic_test_scenario("da-nang")
    catalog = build_destination_catalog_context("da-nang")
    valid_json_text = _make_valid_provider_json(
        catalog[0].place_id,
        catalog[0].name,
        catalog[1].place_id,
        catalog[1].name,
    )

    fake_client_no_usage = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                text=valid_json_text,
                usage_metadata=None,
            )
        )
    )
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=tmp_path / "no_usage_run",
        client=fake_client_no_usage,
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert result.run_status == BenchmarkRunStatus.VALID
    assert result.manifest.usage_metadata.input_tokens is None
    assert result.manifest.usage_metadata.output_tokens is None
    assert result.manifest.usage_metadata.total_tokens is None


def test_w06_i01a_14_latency_measurement_boundary_surrounds_provider_call(tmp_path: Path):
    """W06-I01A-14: latency measurement boundary surrounds provider call."""
    scenario = _make_synthetic_test_scenario("da-nang")
    catalog = build_destination_catalog_context("da-nang")
    valid_json_text = _make_valid_provider_json(
        catalog[0].place_id,
        catalog[0].name,
        catalog[1].place_id,
        catalog[1].name,
    )

    events: list[str] = []
    clock_values = iter([10.000, 10.425])

    def fake_clock() -> float:
        events.append("clock")
        return next(clock_values)

    def fake_generate_content(**_kwargs):
        events.append("provider_call")
        return SimpleNamespace(
            text=valid_json_text,
            usage_metadata=SimpleNamespace(
                prompt_token_count=1200,
                candidates_token_count=350,
                total_token_count=1550,
            ),
        )

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=tmp_path / "latency_run",
        client=fake_client,
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
        clock_fn=fake_clock,
    )
    assert events == ["clock", "provider_call", "clock"]
    assert result.manifest.latency_ms == 425.0
    assert result.manifest.usage_metadata.input_tokens == 1200
    assert result.manifest.usage_metadata.output_tokens == 350
    assert result.manifest.usage_metadata.total_tokens == 1550


def test_w06_i01a_15_manifest_contains_contract_id_version_and_source_commit(tmp_path: Path):
    """W06-I01A-15: manifest contains contract id/version/source commit."""
    scenario = _make_synthetic_test_scenario("da-nang")
    catalog = build_destination_catalog_context("da-nang")
    valid_json_text = _make_valid_provider_json(
        catalog[0].place_id,
        catalog[0].name,
        catalog[1].place_id,
        catalog[1].name,
    )
    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                text=valid_json_text,
                usage_metadata=None,
            )
        )
    )
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=tmp_path / "contract_meta_run",
        client=fake_client,
        configured_model_id="gemini-3.5-flash",
        expected_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    manifest_data = json.loads((tmp_path / "contract_meta_run" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["measurement_contract_id"] == MEASUREMENT_CONTRACT_ID == "W06-MEASUREMENT-CONTRACT-01"
    assert manifest_data["measurement_contract_version"] == MEASUREMENT_CONTRACT_VERSION == "1.1.0"
    assert (
        manifest_data["measurement_contract_source_commit"]
        == MEASUREMENT_CONTRACT_SOURCE_COMMIT
        == "7fd5364ed4671c06b0c911b6fd53bd9f54cbc322"
    )
    assert manifest_data["claims_bitwise_model_determinism"] is False
    assert manifest_data["execution_mode"] == "LIVE_PROVIDER"


def test_w06_i01a_16_manifest_hashes_reproduce_from_persisted_fixture_evidence(tmp_path: Path):
    """W06-I01A-16: manifest hashes reproduce from persisted fixture evidence."""
    scenario = _make_synthetic_test_scenario("da-nang")
    catalog = build_destination_catalog_context("da-nang")
    raw_text_with_fences = "```json\n" + _make_valid_provider_json(
        catalog[0].place_id,
        catalog[0].name,
        catalog[1].place_id,
        catalog[1].name,
    ) + "\n```"

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                text=raw_text_with_fences,
                usage_metadata=None,
            )
        )
    )
    out_dir = tmp_path / "hash_repro_run"
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=out_dir,
        client=fake_client,
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert result.run_status == BenchmarkRunStatus.VALID

    scenario_bytes = (out_dir / "scenario_input.json").read_bytes()
    raw_bytes = (out_dir / "raw_provider_response.txt").read_bytes()
    parsed_bytes = (out_dir / "parsed_plan_response.json").read_bytes()
    catalog_lf_bytes = normalize_lf_bytes(DEFAULT_CATALOG_PATH.read_bytes())

    assert result.manifest.scenario_sha256 == hashlib.sha256(scenario_bytes).hexdigest()
    assert result.manifest.raw_response_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert result.manifest.parsed_response_sha256 == hashlib.sha256(parsed_bytes).hexdigest()
    assert result.manifest.catalog_sha256 == hashlib.sha256(catalog_lf_bytes).hexdigest()


def test_w06_i01a_17_no_silent_retry_exists_in_benchmark_execution_path(tmp_path: Path):
    """W06-I01A-17: no silent retry exists in benchmark execution path."""
    scenario = _make_synthetic_test_scenario("da-nang")
    call_count = 0

    def failing_generate_content(**_kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Simulated provider transient failure")

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=failing_generate_content))
    result = execute_benchmark_scenario(
        scenario=scenario,
        output_dir=tmp_path / "api_error_run",
        client=fake_client,
        configured_model_id="gemini-3.5-flash",
        code_commit_sha="7fd5364ed4671c06b0c911b6fd53bd9f54cbc322",
    )
    assert call_count == 1
    assert result.run_status == BenchmarkRunStatus.API_ERROR
    assert result.parsed_plan_response is None


def _ensure_commit_present(commit_sha: str) -> None:
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", commit_sha, "--depth=1"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )


def test_w06_i01a_18_production_planner_regression_tests_still_pass():
    """W06-I01A-18: production /planner endpoint, schema, and prompt remain backward compatible."""
    from app.prompts.planner_prompt import build_planner_prompt
    from app.schemas.planner import PlanRequest

    prod_req = PlanRequest(destination="Đà Nẵng", days=2, travel_style="family", interests=["beach", "food"])
    prod_prompt = build_planner_prompt(destination=prod_req.destination, days=prod_req.days)
    assert "Đà Nẵng" in prod_prompt

    _ensure_commit_present(MEASUREMENT_CONTRACT_SOURCE_COMMIT)
    res = subprocess.run(
        [
            "git",
            "diff",
            MEASUREMENT_CONTRACT_SOURCE_COMMIT,
            "--",
            "apps/ai-service/app/routers/planner.py",
            "apps/ai-service/app/schemas/planner.py",
            "apps/ai-service/app/prompts/planner_prompt.py",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        return

    from app.config import settings

    if not settings.GEMINI_API_KEY:
        with patch.object(settings, "GEMINI_API_KEY", "dummy-key-for-test-import"):
            from app.main import app
    else:
        from app.main import app

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
    assert resp.status_code == 200
    body = resp.json()
    assert body["destination"] == "Đà Nẵng"
    assert body["total_days"] == 2
    assert len(body["days"]) == 2


def test_w06_i01a_19_no_final_100_scenarios_generated():
    """W06-I01A-19: no final 100 scenarios generated."""
    assert RECEIPT_JSON_PATH.exists()
    receipt = json.loads(RECEIPT_JSON_PATH.read_text(encoding="utf-8"))
    assert receipt["scientific_boundaries"]["final_100_scenarios_generated"] is False

    scenario_files = sorted(p.name for p in PLANNER_EVAL_DIR.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"]


def test_w06_i01a_20_no_scientific_w06_performance_result_generated_and_cli_works(tmp_path: Path):
    """W06-I01A-20: no scientific W06 performance result generated; receipt and CLI modes verified."""
    assert RECEIPT_JSON_PATH.exists()
    assert RECEIPT_MD_PATH.exists()
    receipt = json.loads(RECEIPT_JSON_PATH.read_text(encoding="utf-8"))
    bounds = receipt["scientific_boundaries"]
    assert bounds["scientific_results_generated"] is False
    assert bounds["final_benchmark_executed"] is False
    assert bounds["preregistration_created"] is False
    assert bounds["human_gt_created"] is False
    assert bounds["W5_modified"] is False
    assert bounds["measurement_contract_semantics_modified"] is False

    matrix = receipt["prerequisite_implementation_matrix"]
    assert list(matrix.keys()) == [f"P{i}" for i in range(1, 13)]
    for pid in ("P3", "P4", "P5", "P6", "P7", "P11"):
        assert matrix[pid]["status"] == "NOT_IMPLEMENTED"

    # Verify CLI validate-environment and prepare modes offline
    env_report = run_validate_environment()
    assert env_report["environment_valid"] is True
    assert env_report["primary_destination_counts"] == {"ha-noi": 145, "da-nang": 289, "ha-long": 188}

    scenario = _make_synthetic_test_scenario("da-nang")
    scenario_file = tmp_path / "synthetic_scenario.json"
    scenario_file.write_text(json.dumps(scenario.model_dump(), ensure_ascii=False), encoding="utf-8")

    prep_dir = tmp_path / "prep_out"
    rc = benchmark_cli_main(["prepare", "--scenario", str(scenario_file), "--output", str(prep_dir)])
    assert rc == 0
    assert (prep_dir / "scenario_input.json").exists()
    assert (prep_dir / "catalog_context.json").exists()
    assert (prep_dir / "benchmark_prompt.txt").exists()
    prep_manifest = json.loads((prep_dir / "preparation_manifest.json").read_text(encoding="utf-8"))
    assert prep_manifest["provider_called"] is False
    assert prep_manifest["catalog_poi_count"] == 289
