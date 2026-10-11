from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_endpoint_mocked():
    """Deterministic chat test with mocked LLM provider."""
    mock_result = {
        "response": "Xin chao! Toi la Wandy test mock.",
        "tool_calls": [
            {
                "tool": "get_weather",
                "args": {"lat": 16.0544, "lon": 108.2022},
                "result": {"temp": 28, "condition": "Sunny"}
            }
        ]
    }

    with patch("app.routers.chat.gemini_provider.chat_with_tools", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_result

        response = client.post(
            "/chat",
            json={"message": "Thoi tiet Da Nang the nao?", "session_id": "test-session-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Xin chao! Toi la Wandy test mock."
        assert data["session_id"] == "test-session-123"
        assert "get_weather" in data["tools_used"]
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool"] == "get_weather"

def test_clear_chat_endpoint():
    """Verify delete session history endpoint."""
    with patch("app.routers.chat.gemini_provider.clear_session") as mock_clear:
        response = client.delete("/chat/test-session-123")
        assert response.status_code == 200
        assert response.json()["message"] == "Chat history cleared"
        mock_clear.assert_called_once_with("test-session-123")
