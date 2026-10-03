"""LIVE grounding smoke test for /chat (real Gemini API).

Opt-in only: skipped unless CHAT_LIVE_TEST=1 and GEMINI_API_KEY is configured, so normal runs never spend
quota. It is NOT turned green artificially: a Gemini quota/availability fallback ("AI dang ban", HTTP 429)
FAILS the test instead of passing it.

Run:  CHAT_LIVE_TEST=1 pytest tests/test_chat_live.py -v -s
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("CHAT_LIVE_TEST") != "1" or not os.getenv("GEMINI_API_KEY"),
    reason="live test: set CHAT_LIVE_TEST=1 and GEMINI_API_KEY",
)

QUESTION = "Giờ mở cửa và giá vé của Bảo tàng Hồ Chí Minh là gì?"
QUOTA_MARKERS = ("AI dang ban", "qua tai", "Loi ky thuat")


def test_live_chat_returns_real_grounded_reply_with_sources():
    res = TestClient(app).post("/chat", json={"message": QUESTION, "session_id": "live-grounding"})
    assert res.status_code == 200
    body = res.json()
    assert not any(m in body["reply"] for m in QUOTA_MARKERS), f"Gemini unavailable/quota: {body['reply']}"
    assert body["sources"], "no sources returned"
    assert all(s.startswith(("https://www.openstreetmap.org/", "https://en.wikivoyage.org/")) for s in body["sources"])
