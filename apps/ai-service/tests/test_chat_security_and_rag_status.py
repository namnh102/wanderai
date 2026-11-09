"""Regression suite for PROD-AI-RAG-04:
1. Trusted internal service authentication & user_id / session_id binding (A-01)
2. Tri-state RAG retrieval (OK / EMPTY / ERROR -> 503 fail-closed) & synthetic tool suppression (A-02, A-05)
3. Provider fail-closed error handling (429 / 502 / 503) & history non-pollution (A-03)
4. Session ownership isolation, bounded capacity, TTL expiry & concurrency safety (A-06)
"""
from concurrent.futures import ThreadPoolExecutor
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.llm.gemini import (
    SESSION_STORAGE_LIMITATION,
    GeminiProvider,
    LLMProviderError,
    SessionOwnershipError,
)
from app.main import app
from app.routers.chat import _TOOLS
from app.security.internal_auth import (
    INTERNAL_ASSERTION_HEADER,
    create_internal_assertion,
)
from app.services.rag import RAGService, RetrievalResult
from app.tools.search_hotels import SearchHotelsTool
from app.tools.search_places import SearchPlacesTool

client = TestClient(app)

TEST_INTERNAL_SECRET = "prod-ai-rag-04-test-internal-secret-9876543210"


@pytest.fixture(autouse=True)
def _configure_internal_secret(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_AUTH_SECRET", TEST_INTERNAL_SECRET)
    monkeypatch.setenv("JWT_SECRET", "different-jwt-secret-key-for-testing-12345")
    monkeypatch.setenv(
        "JWT_REFRESH_SECRET", "different-jwt-refresh-secret-for-testing-12345"
    )
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _signed_headers(
    user_id: str = "user-alice",
    action: str = "POST:/chat",
    session_id: str = "",
    secret: str = TEST_INTERNAL_SECRET,
    now_ts: int | None = None,
    ttl_seconds: int = 60,
) -> dict[str, str]:
    token = create_internal_assertion(
        user_id=user_id,
        action=action,
        session_id=session_id,
        secret=secret,
        now=now_ts,
        ttl_seconds=ttl_seconds,
    )
    return {INTERNAL_ASSERTION_HEADER: token}


# ---------------------------------------------------------------------------
# 1. Trusted Principal & Internal Service Assertion (A-01)
# ---------------------------------------------------------------------------


def test_direct_unauthenticated_chat_and_delete_are_rejected_401():
    res_post = client.post("/chat", json={"message": "Xin chào"})
    assert res_post.status_code == 401

    res_del = client.delete("/chat/sess-1")
    assert res_del.status_code == 401


def test_forged_or_expired_or_wrong_action_assertions_are_rejected():
    # Wrong secret -> 401
    bad_sig_headers = _signed_headers(
        user_id="user-alice",
        secret="wrong-internal-secret-key-with-32-chars-minimum!!",
    )
    res_bad_sig = client.post(
        "/chat", json={"message": "Xin chào"}, headers=bad_sig_headers
    )
    assert res_bad_sig.status_code == 401

    # Expired assertion -> 401
    expired_headers = _signed_headers(
        user_id="user-alice",
        now_ts=int(time.time()) - 300,
        ttl_seconds=60,
    )
    res_expired = client.post(
        "/chat", json={"message": "Xin chào"}, headers=expired_headers
    )
    assert res_expired.status_code == 401

    # Action mismatch (signed for DELETE, used on POST) -> 403
    wrong_action_headers = _signed_headers(
        user_id="user-alice",
        action="DELETE:/chat/sess-1",
        session_id="sess-1",
    )
    res_wrong_act = client.post(
        "/chat",
        json={"message": "Xin chào", "session_id": "sess-1"},
        headers=wrong_action_headers,
    )
    assert res_wrong_act.status_code == 403


def test_spoofed_body_or_query_user_id_and_mismatched_session_id_are_rejected_403():
    headers = _signed_headers(
        user_id="user-alice",
        action="POST:/chat",
        session_id="sess-alice",
    )
    # Spoofed body user_id != principal.user_id
    res_spoof_body = client.post(
        "/chat",
        json={
            "message": "Xin chào",
            "session_id": "sess-alice",
            "user_id": "user-bob",
        },
        headers=headers,
    )
    assert res_spoof_body.status_code == 403

    # Mismatched body session_id != assertion sid
    res_spoof_sid = client.post(
        "/chat",
        json={
            "message": "Xin chào",
            "session_id": "sess-other",
        },
        headers=headers,
    )
    assert res_spoof_sid.status_code == 403

    # Spoofed query user_id on DELETE
    del_headers = _signed_headers(
        user_id="user-alice",
        action="DELETE:/chat/sess-alice",
        session_id="sess-alice",
    )
    res_spoof_del = client.delete(
        "/chat/sess-alice?user_id=user-bob",
        headers=del_headers,
    )
    assert res_spoof_del.status_code == 403


def test_internal_secret_fails_closed_when_missing_weak_or_reused(monkeypatch):
    # Reusing JWT_SECRET must fail closed with 503
    reused_secret = "different-jwt-secret-key-for-testing-12345"
    headers = _signed_headers(user_id="user-alice", secret=TEST_INTERNAL_SECRET)
    monkeypatch.setenv("JWT_SECRET", reused_secret)
    monkeypatch.setenv("AI_INTERNAL_AUTH_SECRET", reused_secret)
    res = client.post("/chat", json={"message": "Xin chào"}, headers=headers)
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# 2. RAG Tri-State (OK / EMPTY / ERROR -> 503) & Tool Grounding (A-02, A-05)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rag_service_retrieve_with_status_tri_state():
    # 1. ERROR when retriever raises
    failing_retriever = MagicMock()
    failing_retriever.embedder = MagicMock()
    failing_retriever.search = AsyncMock(side_effect=RuntimeError("pgvector connection refused"))
    svc_err = RAGService(retriever=failing_retriever)
    res_err = await svc_err.retrieve_with_status("Hà Nội")
    assert res_err.status == "error"
    assert res_err.context == ""
    assert res_err.sources == []
    assert res_err.error_type == "RuntimeError"

    # 2. EMPTY when retriever returns []
    empty_retriever = MagicMock()
    empty_retriever.embedder = MagicMock()
    empty_retriever.search = AsyncMock(return_value=[])
    svc_empty = RAGService(retriever=empty_retriever)
    res_empty = await svc_empty.retrieve_with_status("Sao Hỏa")
    assert res_empty.status == "empty"
    assert res_empty.context == ""
    assert res_empty.sources == []
    assert res_empty.error_type is None

    # 3. OK when retriever returns verified chunks
    ok_retriever = MagicMock()
    ok_retriever.embedder = MagicMock()
    ok_retriever.search = AsyncMock(
        return_value=[
            {
                "content": "Văn Miếu tại Hà Nội.",
                "source_name": "osm",
                "license": "ODbL 1.0",
                "attribution": "© OpenStreetMap contributors",
                "source_url": "https://www.openstreetmap.org/way/1",
            },
            {
                "content": "Hoàn Kiếm tại Hà Nội.",
                "source_name": "osm",
                "license": "ODbL 1.0",
                "attribution": "© OpenStreetMap contributors",
                "source_url": "https://www.openstreetmap.org/way/1",
            },
        ]
    )
    svc_ok = RAGService(retriever=ok_retriever)
    res_ok = await svc_ok.retrieve_with_status("Hà Nội")
    assert res_ok.status == "ok"
    assert "Văn Miếu tại Hà Nội." in res_ok.context
    assert res_ok.sources == ["https://www.openstreetmap.org/way/1"]


def test_chat_returns_503_and_does_not_call_gemini_when_rag_errors():
    error_retrieval = RetrievalResult(
        status="error",
        context="",
        chunks=[],
        sources=["https://www.openstreetmap.org/node/should-not-leak"],
        error_type="PostgresConnectionError",
    )
    headers = _signed_headers(user_id="user-alice", action="POST:/chat", session_id="s-err")

    with (
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=error_retrieval),
        ),
        patch(
            "app.routers.chat.gemini_provider.chat_with_tools",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        res = client.post(
            "/chat",
            json={"message": "Địa điểm ở Đà Nẵng?", "session_id": "s-err"},
            headers=headers,
        )

    assert res.status_code == 503
    assert "sources" not in res.json()
    mock_llm.assert_not_called()


@pytest.mark.anyio
async def test_synthetic_hotel_tool_is_removed_from_production_and_marked_unverified():
    tool_names = [t.name for t in _TOOLS]
    assert "search_hotels" not in tool_names

    hotel_tool = SearchHotelsTool()
    out = await hotel_tool.execute({"destination": "Da Nang", "max_budget": 1000000})
    assert out["status"] == "UNVERIFIED_INVENTORY_UNAVAILABLE"
    assert out["verified"] is False
    assert out["synthetic"] is True
    assert out["hotels"] == []
    assert "Budget Inn" not in str(out)
    assert "Grand Da Nang Hotel" not in str(out)


@pytest.mark.anyio
async def test_search_places_tool_reports_db_error_instead_of_empty_places():
    places_tool = SearchPlacesTool()
    with patch("app.tools.search_places.asyncpg.connect", side_effect=OSError("db down")):
        out = await places_tool.execute({"destination": "Ha Giang"})
    assert out["status"] == "DB_ERROR"
    assert out["verified"] is False
    assert "places" not in out


# ---------------------------------------------------------------------------
# 3. Provider Fail-Closed Error Mapping & History Non-Pollution (A-03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_to_raise,expected_status",
    [
        (RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"), 429),
        (RuntimeError("503 UNAVAILABLE: upstream overloaded"), 503),
        (TimeoutError("Request timed out"), 503),
        (RuntimeError("Internal SDK serialization failure"), 502),
    ],
)
def test_provider_exceptions_map_to_non_200_without_sources_or_history_pollution(
    exc_to_raise, expected_status
):
    provider = GeminiProvider()
    ok_retrieval = RetrievalResult(
        status="ok",
        context="--- [Source: osm] ---\nChùa Một Cột.",
        chunks=[{"source_url": "https://www.openstreetmap.org/node/100"}],
        sources=["https://www.openstreetmap.org/node/100"],
    )
    headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id="sess-fail"
    )

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=ok_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=exc_to_raise,
        ),
    ):
        res = client.post(
            "/chat",
            json={"message": "Chùa Một Cột ở đâu?", "session_id": "sess-fail"},
            headers=headers,
        )

    assert res.status_code == expected_status
    body = res.json()
    assert "reply" not in body
    assert "sources" not in body
    assert "sess-fail" not in provider._sessions


def test_empty_model_response_raises_502_and_does_not_save_turn():
    provider = GeminiProvider()
    empty_candidate = SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="   ", function_call=None)]))]
    )
    ok_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )
    headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id="sess-empty-llm"
    )

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=ok_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            return_value=empty_candidate,
        ),
    ):
        res = client.post(
            "/chat",
            json={"message": "Xin chào", "session_id": "sess-empty-llm"},
            headers=headers,
        )

    assert res.status_code == 502
    assert "sess-empty-llm" not in provider._sessions


# ---------------------------------------------------------------------------
# 4. Session Ownership Isolation, Lifespan, Capacity & Concurrency (A-06)
# ---------------------------------------------------------------------------


def _mock_gemini_text_response(text: str):
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(text=text, function_call=None)]
                )
            )
        ]
    )


def test_cross_user_session_reuse_and_delete_are_blocked_with_403():
    provider = GeminiProvider()
    assert provider.storage_limitation == SESSION_STORAGE_LIMITATION
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )

    alice_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id="shared-session-1"
    )
    bob_headers = _signed_headers(
        user_id="user-bob", action="POST:/chat", session_id="shared-session-1"
    )
    bob_delete_headers = _signed_headers(
        user_id="user-bob",
        action="DELETE:/chat/shared-session-1",
        session_id="shared-session-1",
    )
    alice_delete_headers = _signed_headers(
        user_id="user-alice",
        action="DELETE:/chat/shared-session-1",
        session_id="shared-session-1",
    )

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            return_value=_mock_gemini_text_response("Chào Alice!"),
        ),
    ):
        # Alice creates session
        res_alice = client.post(
            "/chat",
            json={"message": "Tôi là Alice", "session_id": "shared-session-1"},
            headers=alice_headers,
        )
        assert res_alice.status_code == 200

        # Bob attempts to read/continue Alice's session -> 403
        res_bob_post = client.post(
            "/chat",
            json={"message": "Tôi là Bob", "session_id": "shared-session-1"},
            headers=bob_headers,
        )
        assert res_bob_post.status_code == 403

        # Bob attempts to delete Alice's session -> 403
        res_bob_del = client.delete(
            "/chat/shared-session-1",
            headers=bob_delete_headers,
        )
        assert res_bob_del.status_code == 403
        assert "shared-session-1" in provider._sessions

        # Alice deletes her own session -> 200
        res_alice_del = client.delete(
            "/chat/shared-session-1",
            headers=alice_delete_headers,
        )
        assert res_alice_del.status_code == 200
        assert "shared-session-1" not in provider._sessions


def test_session_ttl_expiry_and_max_capacity_eviction():
    provider = GeminiProvider(max_sessions=3, session_ttl_seconds=10)

    provider._commit_turn("s1", "user-1", "u1", "m1")
    provider._commit_turn("s2", "user-1", "u2", "m2")
    provider._commit_turn("s3", "user-1", "u3", "m3")
    provider._commit_turn("s4", "user-1", "u4", "m4")

    # Max sessions is 3 -> oldest ("s1") evicted
    assert len(provider._sessions) == 3
    assert "s1" not in provider._sessions
    assert set(provider._sessions.keys()) == {"s2", "s3", "s4"}

    # Expire s2 by backdating updated_at
    provider._sessions["s2"].updated_at -= 25
    history = provider._authorize_and_snapshot_history("s2", "user-1")
    assert history == []
    assert "s2" not in provider._sessions


def test_concurrent_cross_user_access_never_interleaves_or_overwrites_owner():
    provider = GeminiProvider()
    provider._commit_turn("race-sess", "user-alice", "u-init", "m-init")

    def worker(idx: int) -> str:
        if idx % 2 == 0:
            provider._commit_turn("race-sess", "user-alice", f"u-{idx}", f"m-{idx}")
            return "alice_ok"
        try:
            provider._commit_turn("race-sess", "user-bob", f"u-{idx}", f"m-{idx}")
            return "bob_unexpected_success"
        except SessionOwnershipError:
            return "bob_blocked"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(worker, range(24)))

    assert "bob_unexpected_success" not in outcomes
    assert outcomes.count("bob_blocked") == 12
    assert provider._sessions["race-sess"].owner_user_id == "user-alice"
