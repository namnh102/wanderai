from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.security.internal_auth import InternalPrincipal, require_internal_principal
from app.services.rag import RetrievalResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_internal_principal():
    app.dependency_overrides[require_internal_principal] = lambda: InternalPrincipal(
        user_id="test-user-1",
        bound_session_id="test-session-123",
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_internal_principal, None)


def test_chat_endpoint_mocked():
    """Deterministic chat test with mocked RAG retrieval and mocked LLM provider."""
    mock_result = {
        "response": "Xin chao! Toi la Wandy test mock.",
        "tool_calls": [
            {
                "tool": "get_weather",
                "args": {"lat": 16.0544, "lon": 108.2022},
                "result": {"temp": 28, "condition": "Sunny"},
            }
        ],
    }
    empty_retrieval = RetrievalResult(
        status="empty",
        context="",
        chunks=[],
        sources=[],
    )

    with (
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.routers.chat.gemini_provider.chat_with_tools",
            new_callable=AsyncMock,
        ) as mock_chat,
    ):
        mock_chat.return_value = mock_result

        response = client.post(
            "/chat",
            json={
                "message": "Thoi tiet Da Nang the nao?",
                "session_id": "test-session-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Xin chao! Toi la Wandy test mock."
        assert data["session_id"] == "test-session-123"
        assert data["retrieval_status"] == "empty"
        assert data["sources"] == []
        assert "get_weather" in data["tools_used"]
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool"] == "get_weather"


def test_clear_chat_endpoint():
    """Verify delete session history endpoint passes authenticated owner user_id."""
    with patch("app.routers.chat.gemini_provider.clear_session") as mock_clear:
        response = client.delete("/chat/test-session-123")
        assert response.status_code == 200
        assert response.json()["message"] == "Chat history cleared"
        mock_clear.assert_called_once_with("test-session-123", user_id="test-user-1")


def test_chat_planning_intent_and_c4_budget_presentation_suppresses_false_surplus():
    """Verify Hạ Long planning prompt extracts party/time/budget/interests and rewrites false 420k surplus to C4 summary."""
    halong_msg = (
        "Hai người lớn đi Hạ Long từ 8h đến 12h, tổng ngân sách 500.000 đồng, "
        "ưu tiên bảo tàng. Lập giúp tôi một lịch và ghi rõ khoản nào chưa biết giá."
    )
    raw_llm_reply = (
        "### Lịch trình 8:00 - 12:00\n"
        "1. 08:00 - 10:30: Bảo tàng Quảng Ninh — Chi phí cho 2 người lớn: 80.000 đồng\n"
        "2. 10:30 - 12:00: Tháp Đồng Hồ Hạ Long — Chưa biết giá\n"
        "* Số tiền còn lại (cho di chuyển, ăn uống): 420.000 đồng"
    )
    ok_retrieval = RetrievalResult(
        status="ok",
        context="Bảo tàng Quảng Ninh 40.000đ/người; Tháp Đồng Hồ chưa biết giá.",
        chunks=[],
        sources=["https://www.openstreetmap.org/node/5395107122"],
    )
    with (
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=ok_retrieval),
        ),
        patch(
            "app.routers.chat.gemini_provider.chat_with_tools",
            new=AsyncMock(return_value={"response": raw_llm_reply, "tool_calls": []}),
        ),
    ):
        res = client.post(
            "/chat",
            json={"message": halong_msg, "session_id": "test-session-123"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["can_plan_trip"] is True
        assert body["planning_context"] == {
            "raw_prompt": halong_msg,
            "party_size": 2,
            "party_description": "2 người lớn",
            "time_window_start": "08:00",
            "time_window_end": "12:00",
            "total_budget": 500000,
            "interests": ["museum"],
        }
        assert "Đã biết 80.000đ; còn khoản chưa xác minh" in body["reply"]
        assert "420.000" not in body["reply"]
