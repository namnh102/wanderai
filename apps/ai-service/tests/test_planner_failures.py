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
