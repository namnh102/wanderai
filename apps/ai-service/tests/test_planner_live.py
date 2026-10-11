"""LIVE smoke test for the AI planner (real Gemini API).

Skipped unless PLANNER_LIVE_TEST=1 and GEMINI_API_KEY is configured, so normal
`pytest tests/` runs never need or use an API key.

Run:  PLANNER_LIVE_TEST=1 pytest tests/test_planner_live.py -v -s
"""
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("PLANNER_LIVE_TEST") != "1" or not settings.GEMINI_API_KEY,
    reason="live test: set PLANNER_LIVE_TEST=1 and GEMINI_API_KEY",
)

TIMEOUT_S = 60


def test_live_planner_da_nang_3_days():
    client = TestClient(app)
    payload = {
        "trip_id": "live-smoke",
        "destination": "Đà Nẵng",
        "days": 3,
        "budget": 5000000,
        "currency": "VND",
        "travel_style": "COMFORT",
        "interests": ["food", "beach"],
    }
    t0 = time.time()
    res = client.post("/planner", json=payload)
    elapsed = time.time() - t0

    # 1, 10: success within timeout
    assert res.status_code == 200, res.text[:300]
    assert elapsed < TIMEOUT_S
    print(f"\nLIVE model={settings.PLANNER_MODEL} elapsed={elapsed:.1f}s")

    # 2, 8: valid JSON, no markdown wrapper leaking into fields
    data = res.json()
    assert "```" not in res.text

    # 3: schema
    for key in ("plan_id", "destination", "total_days", "overview", "budget_analysis", "days"):
        assert key in data

    # 4, 5, 9: day count, non-empty
    assert data["total_days"] == 3
    assert len(data["days"]) == 3
    assert [d["day_number"] for d in data["days"]] == [1, 2, 3]
    total_items = 0
    grand = 0
    for d in data["days"]:
        assert len(d["items"]) > 0, f"day {d['day_number']} empty"
        day_sum = 0
        for it in d["items"]:
            # 6: valid estimated cost
            assert isinstance(it["estimated_cost"], int) and it["estimated_cost"] >= 0
            assert it["activity"].strip()
            day_sum += it["estimated_cost"]
        # 7: arithmetic integrity
        assert d["day_cost"] == day_sum
        grand += day_sum
        total_items += len(d["items"])
    ba = data["budget_analysis"]
    assert ba["estimated_cost"] == grand
    assert ba["total_budget"] == 5000000
    assert ba["variance"] == 5000000 - grand
    assert ba["is_over_budget"] == (grand > 5000000)
    assert total_items >= 3
    print(f"LIVE items={total_items} estimated={grand}")
