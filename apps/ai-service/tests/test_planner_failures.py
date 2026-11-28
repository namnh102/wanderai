"""Mocked regression tests for planner failure handling (no API key needed)."""
import json
import pathlib
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

PAYLOAD = {
    "trip_id": "t-1",
    "destination": "Da Nang",
    "days": 2,
    "budget": 2000000,
    "currency": "VND",
    "travel_style": "COMFORT",
    "interests": ["food"],
}


def test_planner_defaults_use_supported_model_and_large_output_limit():
    assert settings.PLANNER_MODEL != "gemini-2.0-flash"
    assert settings.PLANNER_MAX_OUTPUT_TOKENS >= 16384


def test_planner_passes_configured_model_and_limit_to_provider():
    mock_response = MagicMock()
    mock_response.text = json.dumps({"days": [{"day_number": 1, "items": [
        {"activity": "a", "estimated_cost": 1}]}]})
    with patch("app.routers.planner._client") as mc:
        mc.models.generate_content.return_value = mock_response
        res = client.post("/planner", json=PAYLOAD)
        assert res.status_code == 200
        kwargs = mc.models.generate_content.call_args.kwargs
        assert kwargs["model"] == settings.PLANNER_MODEL
        assert kwargs["config"].max_output_tokens >= 16384


def test_planner_provider_failure_is_controlled_and_does_not_leak():
    """Simulates an unsupported/retired model (404 from provider)."""
    with patch("app.routers.planner._client") as mc:
        mc.models.generate_content.side_effect = RuntimeError(
            "404 NOT_FOUND models/gemini-2.0-flash SECRET-INTERNAL-DETAIL"
        )
        res = client.post("/planner", json=PAYLOAD)
    assert res.status_code == 502
    body = res.text
    assert "SECRET-INTERNAL-DETAIL" not in body
    assert "gemini-2.0-flash" not in body
    assert "Traceback" not in body
    assert res.json()["detail"]


def test_planner_malformed_json_returns_502():
    mock_response = MagicMock()
    mock_response.text = "{ this is not json "
    with patch("app.routers.planner._client") as mc:
        mc.models.generate_content.return_value = mock_response
        res = client.post("/planner", json=PAYLOAD)
    assert res.status_code == 502
    assert "Traceback" not in res.text


def test_planner_truncated_output_returns_502():
    mock_response = MagicMock()
    mock_response.text = '{"days": [{"day_number": 1, "items": ['
    mock_response.candidates = [MagicMock(finish_reason="FinishReason.MAX_TOKENS")]
    with patch("app.routers.planner._client") as mc:
        mc.models.generate_content.return_value = mock_response
        res = client.post("/planner", json=PAYLOAD)
    assert res.status_code == 502


def test_planner_router_has_no_database_access():
    """Preview invariant at the AI layer: planner router never touches the DB."""
    src = pathlib.Path("app/routers/planner.py").read_text(encoding="utf-8")
    for token in ("asyncpg", "psycopg", "sqlalchemy", "DATABASE_URL", "INSERT INTO"):
        assert token not in src


def test_planner_503_then_success_records_correlated_request_id_and_retry_timings():
    """Simulates a transient 503 UNAVAILABLE on attempt 1 followed by 200 OK on attempt 2."""
    ok_response = MagicMock()
    ok_response.text = json.dumps(
        {
            "destination": "Hạ Long",
            "total_days": 1,
            "overview": "Lịch trình Hạ Long buổi sáng.",
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-11-28",
                    "title": "Ngày 1: Bảo tàng & Tháp Đồng Hồ",
                    "items": [
                        {
                            "order_index": 1,
                            "start_time": "08:00",
                            "end_time": "10:30",
                            "activity": "Tham quan Bảo tàng Quảng Ninh",
                            "place_name": "Bảo tàng Quảng Ninh",
                            "estimated_cost": 80000,
                        },
                        {
                            "order_index": 2,
                            "start_time": "10:30",
                            "end_time": "12:00",
                            "activity": "Check-in Tháp Đồng Hồ Hạ Long",
                            "place_name": "Tháp Đồng Hồ Hạ Long",
                            "estimated_cost": None,
                        },
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    ok_response.candidates = []

    req_id = "req-c4-503-retry-mock-001"
    with (
        patch("app.routers.planner._client") as mc,
        patch("app.routers.planner._get_max_planner_attempts", return_value=3),
        patch("app.routers.planner._sleep_for_retry", return_value=2000.0) as mock_sleep,
    ):
        mc.models.generate_content.side_effect = [
            RuntimeError("503 UNAVAILABLE: This model is currently experiencing high demand"),
            ok_response,
        ]
        res = client.post(
            "/planner",
            json={
                "trip_id": "88888888-ba26-4c17-8888-000000000c41",
                "destination": "Hạ Long",
                "days": 1,
                "budget": 500000,
                "currency": "VND",
                "interests": ["museum"],
            },
            headers={"X-Request-Id": req_id},
        )

    assert res.status_code == 200
    assert res.headers.get("X-Request-Id") == req_id
    mock_sleep.assert_called_once_with(2.0)

    body = res.json()
    tel = body["timing_telemetry"]
    assert tel["request_id"] == req_id
    assert tel["retry_count"] == 1
    assert tel["retry_wait_ms"] == 2000.0
    assert len(tel["model_attempts"]) == 2
    assert tel["model_attempts"][0]["attempt"] == 1
    assert tel["model_attempts"][0]["status"] == "error_503"
    assert tel["model_attempts"][0]["error_code"] == "PROVIDER_503_UNAVAILABLE"
    assert tel["model_attempts"][0]["duration_ms"] >= 0.0
    assert tel["model_attempts"][1]["attempt"] == 2
    assert tel["model_attempts"][1]["status"] == "ok"
    assert tel["model_attempts"][1]["duration_ms"] >= 0.0
    assert tel["fastapi_total_ms"] >= 0.0
    assert tel["post_ai_schedule_validation_ms"] >= 0.0

