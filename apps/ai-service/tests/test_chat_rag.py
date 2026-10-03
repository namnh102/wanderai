"""TASK 07.5: the live /chat path is grounded with retrieved verified documents (LLM mocked)."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.routers.chat import build_grounded_message

client = TestClient(app)


def test_build_grounded_message_passthrough_without_context():
    assert build_grounded_message("Xin chào", "") == "Xin chào"


def test_build_grounded_message_embeds_context_and_forbids_invention():
    msg = build_grounded_message("Giờ mở cửa?", "--- [Source: osm (ODbL 1.0)] ---\nGiờ mở cửa: Mo-Su 08:00-17:00.")
    assert "Giờ mở cửa: Mo-Su 08:00-17:00." in msg
    assert "không bịa" in msg and msg.endswith("Câu hỏi của người dùng: Giờ mở cửa?")


def test_chat_passes_retrieved_context_to_llm_and_returns_sources():
    ctx = "--- [Source: osm (ODbL 1.0 - © OpenStreetMap contributors)] ---\nBảo tàng X thuộc nhóm văn hóa."
    url = "https://www.openstreetmap.org/node/42"
    with patch("app.routers.chat.retrieve_grounding", new=AsyncMock(return_value=(ctx, [url]))), patch(
        "app.routers.chat.gemini_provider.chat_with_tools", new_callable=AsyncMock
    ) as llm:
        llm.return_value = {"response": "ok", "tool_calls": []}
        res = client.post("/chat", json={"message": "Địa điểm văn hóa ở Hà Nội?", "session_id": "s1"})
    assert res.status_code == 200
    assert res.json()["sources"] == [url]
    sent = llm.call_args.kwargs["message"]
    assert "Bảo tàng X thuộc nhóm văn hóa." in sent and "Địa điểm văn hóa ở Hà Nội?" in sent


def test_chat_degrades_to_ungrounded_when_retrieval_returns_nothing():
    with patch("app.routers.chat.retrieve_grounding", new=AsyncMock(return_value=("", []))), patch(
        "app.routers.chat.gemini_provider.chat_with_tools", new_callable=AsyncMock
    ) as llm:
        llm.return_value = {"response": "ok", "tool_calls": []}
        res = client.post("/chat", json={"message": "Xin chào", "session_id": "s2"})
    assert res.status_code == 200 and res.json()["sources"] == []
    assert llm.call_args.kwargs["message"] == "Xin chào"
