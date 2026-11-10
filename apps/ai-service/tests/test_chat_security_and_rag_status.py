"""Regression suite for PROD-AI-RAG-04:
1. Trusted internal service authentication & user_id / session_id binding (A-01)
2. Tri-state RAG retrieval (OK / EMPTY / ERROR -> 503 fail-closed) & synthetic tool suppression (A-02, A-05)
3. Provider fail-closed error handling (429 / 502 / 503) & history non-pollution (A-03)
4. Session ownership isolation, bounded capacity, TTL expiry & concurrency safety (A-06)
"""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.main import app
from app.routers.chat import _TOOLS
from app.security.internal_auth import (
    INTERNAL_ASSERTION_HEADER,
    create_internal_assertion,
)
from app.services.chat_llm import (
    SESSION_STORAGE_LIMITATION,
    GeminiProvider,
    LLMProviderError,
    SessionOwnershipError,
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


def test_f02_exact_signed_sid_and_body_sid_binding_all_four_conditions():
    """F-02 regression test:
    1. (signed empty sid="", body nonempty session_id="sess-1") => 403
    2. (signed nonempty sid="sess-1", body empty/omitted session_id) => 403
    3. (signed nonempty sid="sess-1", body matching session_id="sess-1") => 200
    4. (signed empty sid="", body empty/omitted session_id) => 200 with generated UUID
    Plus DELETE with empty signed sid => 403.
    """
    provider = GeminiProvider()
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            return_value=SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[SimpleNamespace(text="Xin chào!", function_call=None)]
                        )
                    )
                ]
            ),
        ),
    ):
        # Condition 1: signed sid="", body session_id="sess-1" => 403
        headers_empty_sid = _signed_headers(
            user_id="user-alice",
            action="POST:/chat",
            session_id="",
        )
        res_cond1 = client.post(
            "/chat",
            json={"message": "Xin chào", "session_id": "sess-1"},
            headers=headers_empty_sid,
        )
        assert res_cond1.status_code == 403
        assert "session_id" in res_cond1.json()["detail"]

        # Condition 2a: signed sid="sess-1", body session_id omitted (None) => 403
        headers_bound_sid = _signed_headers(
            user_id="user-alice",
            action="POST:/chat",
            session_id="sess-1",
        )
        res_cond2_none = client.post(
            "/chat",
            json={"message": "Xin chào"},
            headers=headers_bound_sid,
        )
        assert res_cond2_none.status_code == 403

        # Condition 2b: signed sid="sess-1", body session_id="" => 403
        res_cond2_empty = client.post(
            "/chat",
            json={"message": "Xin chào", "session_id": ""},
            headers=headers_bound_sid,
        )
        assert res_cond2_empty.status_code == 403

        # Condition 3: signed sid="sess-1", body session_id="sess-1" (exact match) => 200
        res_cond3 = client.post(
            "/chat",
            json={"message": "Xin chào", "session_id": "sess-1"},
            headers=headers_bound_sid,
        )
        assert res_cond3.status_code == 200
        assert res_cond3.json()["session_id"] == "sess-1"

        # Condition 4: signed sid="", body session_id omitted/empty (both empty) => 200 with generated UUID
        res_cond4 = client.post(
            "/chat",
            json={"message": "Xin chào"},
            headers=headers_empty_sid,
        )
        assert res_cond4.status_code == 200
        generated_sid = res_cond4.json()["session_id"]
        assert generated_sid and generated_sid != "sess-1"
        uuid.UUID(generated_sid)

        # Companion check: DELETE with empty signed sid => 403
        del_headers_empty_sid = _signed_headers(
            user_id="user-alice",
            action="DELETE:/chat/sess-1",
            session_id="",
        )
        res_del_empty_sid = client.delete(
            "/chat/sess-1",
            headers=del_headers_empty_sid,
        )
        assert res_del_empty_sid.status_code == 403


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


def test_f01_delete_during_in_flight_post_does_not_recreate_cleared_session():
    """F-01 deterministic barrier concurrency test:
    1. User A establishes session S (Turn 1).
    2. User A starts in-flight POST /chat (Turn 2) on S and enters mocked Gemini call.
    3. While Turn 2 is inside Gemini, User A executes DELETE /chat/S (200 OK).
    4. Release mocked Gemini call so Turn 2 finishes.
    5. Assert Turn 2 completes without resurrecting S in provider._sessions (no restored history).
    6. Subsequent Turn 3 by User A on S starts from clean empty history (only Turn 3 is stored).
    """
    provider = GeminiProvider()
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )
    session_id = "sess-delete-race"
    post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=session_id
    )
    delete_headers = _signed_headers(
        user_id="user-alice",
        action=f"DELETE:/chat/{session_id}",
        session_id=session_id,
    )

    entered_model_event = threading.Event()
    release_model_event = threading.Event()
    call_counter = {"count": 0}

    def controlled_generate_content(*, model, contents, config):
        call_counter["count"] += 1
        idx = call_counter["count"]
        if idx == 2:
            entered_model_event.set()
            assert release_model_event.wait(timeout=5.0), "Timed out waiting for release_model_event"
        return _mock_gemini_text_response(f"Phản hồi lượt {idx}")

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=controlled_generate_content,
        ),
    ):
        # Step 1: Turn 1 establishes session S
        res_turn1 = client.post(
            "/chat",
            json={"message": "Lượt 1 trước khi xóa", "session_id": session_id},
            headers=post_headers,
        )
        assert res_turn1.status_code == 200
        assert session_id in provider._sessions
        assert len(provider._sessions[session_id].history) == 2

        # Step 2: Start Turn 2 in background thread; it pauses inside generate_content
        with ThreadPoolExecutor(max_workers=1) as executor:
            inflight_future = executor.submit(
                client.post,
                "/chat",
                json={"message": "Lượt 2 đang chạy thì bị xóa", "session_id": session_id},
                headers=post_headers,
            )

            assert entered_model_event.wait(timeout=5.0), "In-flight POST never entered model call"

            # Step 3: While Turn 2 is in-flight, User A clears session S
            res_del = client.delete(
                f"/chat/{session_id}",
                headers=delete_headers,
            )
            assert res_del.status_code == 200
            assert session_id not in provider._sessions

            # Step 4: Release model call so Turn 2 finishes
            release_model_event.set()
            res_turn2 = inflight_future.result(timeout=5.0)

        # Step 5: Turn 2 returns 200 (success without persistence) and MUST NOT recreate S
        assert res_turn2.status_code == 200
        assert session_id not in provider._sessions
        assert provider._authorize_and_snapshot_history(session_id, "user-alice") == []

        # Step 6: A subsequent Turn 3 after DELETE starts fresh with only Turn 3 (2 items: user + model)
        res_turn3 = client.post(
            "/chat",
            json={"message": "Lượt 3 mới sau khi xóa", "session_id": session_id},
            headers=post_headers,
        )
        assert res_turn3.status_code == 200
        assert session_id in provider._sessions
        assert len(provider._sessions[session_id].history) == 2
        persisted_texts = [
            part.text
            for item in provider._sessions[session_id].history
            for part in (item.parts or [])
            if getattr(part, "text", None)
        ]
        assert any("Lượt 3 mới sau khi xóa" in t for t in persisted_texts)
        assert not any("Lượt 1 trước khi xóa" in t for t in persisted_texts)
        assert not any("Lượt 2 đang chạy thì bị xóa" in t for t in persisted_texts)


def test_f01_companion_concurrent_same_owner_turns_succeed_and_cross_owner_rejected():
    """F-01 companion concurrency test:
    Normal concurrent non-deleted POST requests by the same owner on session S both succeed
    and persist both turns without invalidating each other, while concurrent cross-owner
    requests on S are rejected with 403.
    """
    provider = GeminiProvider()
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )
    session_id = "sess-concurrent-same-owner"
    alice_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=session_id
    )
    bob_headers = _signed_headers(
        user_id="user-bob", action="POST:/chat", session_id=session_id
    )

    both_entered = threading.Barrier(2, timeout=5.0)

    def concurrent_generate_content(*, model, contents, config):
        try:
            both_entered.wait()
        except threading.BrokenBarrierError:
            pass
        return _mock_gemini_text_response("Phản hồi đồng thời")

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=concurrent_generate_content,
        ),
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(
                client.post,
                "/chat",
                json={"message": "Alice câu 1", "session_id": session_id},
                headers=alice_headers,
            )
            f2 = executor.submit(
                client.post,
                "/chat",
                json={"message": "Alice câu 2", "session_id": session_id},
                headers=alice_headers,
            )
            r1 = f1.result(timeout=5.0)
            r2 = f2.result(timeout=5.0)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert session_id in provider._sessions
        # Both turns (2 user + 2 model = 4 items) are persisted
        assert len(provider._sessions[session_id].history) == 4

        # Cross-owner request on established session is still rejected with 403
        res_bob = client.post(
            "/chat",
            json={"message": "Bob xâm nhập", "session_id": session_id},
            headers=bob_headers,
        )
        assert res_bob.status_code == 403


def test_f01_edge_max_sessions_1_tombstone_eviction_rejects_stale_commit():
    """F-01-EDGE (1): With max_sessions=1:
    start S (in-flight) -> DELETE S -> create T (forcing eviction of S tombstone) ->
    release stale S -> stale S commit is rejected fail-closed and T remains intact.
    """
    provider = GeminiProvider(max_sessions=1, session_ttl_seconds=3600)
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )
    sid_s = "sess-edge-s"
    sid_t = "sess-edge-t"

    s_post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_s
    )
    s_del_headers = _signed_headers(
        user_id="user-alice", action=f"DELETE:/chat/{sid_s}", session_id=sid_s
    )
    t_post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_t
    )

    s_entered = threading.Event()
    s_release = threading.Event()

    def controlled_generate(*, model, contents, config):
        prompt_text = str(contents[-1].parts[0].text)
        if "Tin nhắn của S" in prompt_text:
            s_entered.set()
            assert s_release.wait(timeout=5.0), "Timed out waiting to release S"
            return _mock_gemini_text_response("Phản hồi S trễ")
        return _mock_gemini_text_response("Phản hồi T hợp lệ")

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=controlled_generate,
        ),
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            s_future = executor.submit(
                client.post,
                "/chat",
                json={"message": "Tin nhắn của S", "session_id": sid_s},
                headers=s_post_headers,
            )
            assert s_entered.wait(timeout=5.0), "S never entered model call"

            # DELETE S while S is in-flight
            res_del_s = client.delete(f"/chat/{sid_s}", headers=s_del_headers)
            assert res_del_s.status_code == 200
            assert sid_s not in provider._sessions
            assert sid_s in provider._session_revisions
            assert provider._session_revisions[sid_s].cleared is True

            # Create T with max_sessions=1 -> forces eviction of S tombstone from _session_revisions
            res_post_t = client.post(
                "/chat",
                json={"message": "Tin nhắn của T", "session_id": sid_t},
                headers=t_post_headers,
            )
            assert res_post_t.status_code == 200
            assert sid_s not in provider._session_revisions
            assert sid_t in provider._sessions

            # Release stale S; its generation entry is now missing (None) -> must fail closed
            s_release.set()
            res_post_s = s_future.result(timeout=5.0)

        assert res_post_s.status_code == 200
        assert sid_s not in provider._sessions
        assert sid_s not in provider._session_revisions
        assert sid_t in provider._sessions
        assert len(provider._sessions[sid_t].history) == 2


def test_f01_edge_aba_delete_evict_recreate_rejects_old_generation_while_new_generation_commits():
    """F-01-EDGE (2) ABA scenario:
    start old S -> DELETE S -> create T to evict S tombstone -> start new S on same session_id ->
    old S finishes and is rejected across the ABA boundary -> new S finishes and commits cleanly.
    """
    provider = GeminiProvider(max_sessions=1, session_ttl_seconds=3600)
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )
    sid_s = "sess-aba"
    sid_t = "sess-evictor"

    s_post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_s
    )
    s_del_headers = _signed_headers(
        user_id="user-alice", action=f"DELETE:/chat/{sid_s}", session_id=sid_s
    )
    t_post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_t
    )

    s_old_entered = threading.Event()
    s_old_release = threading.Event()
    s_new_entered = threading.Event()
    s_new_release = threading.Event()

    def controlled_aba_generate(*, model, contents, config):
        prompt_text = str(contents[-1].parts[0].text)
        if "Tin nhắn S_old đã bị xóa" in prompt_text:
            s_old_entered.set()
            assert s_old_release.wait(timeout=5.0), "Timed out waiting for S_old release"
            return _mock_gemini_text_response("Phản hồi của S_old")
        if "Tin nhắn S_new thế hệ mới" in prompt_text:
            s_new_entered.set()
            assert s_new_release.wait(timeout=5.0), "Timed out waiting for S_new release"
            return _mock_gemini_text_response("Phản hồi của S_new")
        return _mock_gemini_text_response("Phản hồi của T")

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=controlled_aba_generate,
        ),
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 1. Start old S (generation 1)
            f_old = executor.submit(
                client.post,
                "/chat",
                json={"message": "Tin nhắn S_old đã bị xóa", "session_id": sid_s},
                headers=s_post_headers,
            )
            assert s_old_entered.wait(timeout=5.0), "S_old did not enter model call"

            # 2. DELETE S (allocates tombstone generation 2)
            res_del = client.delete(f"/chat/{sid_s}", headers=s_del_headers)
            assert res_del.status_code == 200

            # 3. Create T with max_sessions=1 to evict S tombstone from _session_revisions
            res_t = client.post(
                "/chat",
                json={"message": "Tin nhắn T gây eviction", "session_id": sid_t},
                headers=t_post_headers,
            )
            assert res_t.status_code == 200
            assert sid_s not in provider._session_revisions

            # 4. Start new S on the same session_id (allocates fresh generation > 1)
            f_new = executor.submit(
                client.post,
                "/chat",
                json={"message": "Tin nhắn S_new thế hệ mới", "session_id": sid_s},
                headers=s_post_headers,
            )
            assert s_new_entered.wait(timeout=5.0), "S_new did not enter model call"
            assert sid_s in provider._session_revisions
            assert provider._session_revisions[sid_s].cleared is False

            # 5. Release old S first -> must be rejected because its generation != new S generation
            s_old_release.set()
            res_old = f_old.result(timeout=5.0)
            assert res_old.status_code == 200
            assert sid_s not in provider._sessions

            # 6. Release new S -> must commit cleanly
            s_new_release.set()
            res_new = f_new.result(timeout=5.0)
            assert res_new.status_code == 200

        assert sid_s in provider._sessions
        assert len(provider._sessions[sid_s].history) == 2
        stored_texts = [
            part.text
            for item in provider._sessions[sid_s].history
            for part in (item.parts or [])
            if getattr(part, "text", None)
        ]
        assert any("Tin nhắn S_new thế hệ mới" in t for t in stored_texts)
        assert any("Phản hồi của S_new" in t for t in stored_texts)
        assert not any("S_old" in t for t in stored_texts)


def test_f01_edge_ttl_eviction_during_inflight_and_post_delete_tombstone_expiry_rejects_stale_commit():
    """F-01-EDGE (3): Deterministic TTL eviction during in-flight requests (no sleeps):
    Part A: Active session expires via TTL while an in-flight POST is running -> stale commit rejected.
    Part B: Session is deleted via DELETE while POST is in-flight, and the DELETE tombstone
            expires via TTL before the stale POST finishes -> stale commit rejected.
    """
    fake_now = [1000.0]
    provider = GeminiProvider(
        max_sessions=10,
        session_ttl_seconds=60,
        clock=lambda: fake_now[0],
    )
    empty_retrieval = RetrievalResult(
        status="empty", context="", chunks=[], sources=[]
    )

    sid_active = "sess-ttl-active"
    sid_deleted = "sess-ttl-deleted"
    active_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_active
    )
    deleted_post_headers = _signed_headers(
        user_id="user-alice", action="POST:/chat", session_id=sid_deleted
    )
    deleted_del_headers = _signed_headers(
        user_id="user-alice",
        action=f"DELETE:/chat/{sid_deleted}",
        session_id=sid_deleted,
    )

    inflight_entered = threading.Event()
    inflight_release = threading.Event()

    def ttl_controlled_generate(*, model, contents, config):
        prompt_text = str(contents[-1].parts[0].text)
        if "Đang bay khi hết hạn TTL" in prompt_text:
            inflight_entered.set()
            assert inflight_release.wait(timeout=5.0), "Timed out waiting for TTL release"
        return _mock_gemini_text_response("Phản hồi sau khi TTL hết hạn")

    with (
        patch("app.routers.chat.gemini_provider", provider),
        patch(
            "app.routers.chat.retrieve_grounding",
            new=AsyncMock(return_value=empty_retrieval),
        ),
        patch(
            "app.llm.gemini._client.models.generate_content",
            side_effect=ttl_controlled_generate,
        ),
    ):
        # Part A: Establish sid_active at t=1000.0
        res1 = client.post(
            "/chat",
            json={"message": "Khởi tạo phiên", "session_id": sid_active},
            headers=active_headers,
        )
        assert res1.status_code == 200
        assert sid_active in provider._sessions

        # Start Turn 2 at t=1010.0, then advance clock past TTL (t=1080.0) while in-flight
        fake_now[0] = 1010.0
        with ThreadPoolExecutor(max_workers=1) as executor:
            f_active = executor.submit(
                client.post,
                "/chat",
                json={"message": "Đang bay khi hết hạn TTL (Part A)", "session_id": sid_active},
                headers=active_headers,
            )
            assert inflight_entered.wait(timeout=5.0)
            fake_now[0] = 1080.0
            inflight_release.set()
            res_active_expired = f_active.result(timeout=5.0)

        assert res_active_expired.status_code == 200
        assert sid_active not in provider._sessions
        assert sid_active not in provider._session_revisions

        # Part B: Start in-flight POST on sid_deleted at t=2000.0, DELETE at t=2005.0,
        # advance clock past TTL to t=2100.0 so tombstone expires, then release in-flight POST
        inflight_entered.clear()
        inflight_release.clear()
        fake_now[0] = 2000.0

        with ThreadPoolExecutor(max_workers=1) as executor:
            f_deleted = executor.submit(
                client.post,
                "/chat",
                json={"message": "Đang bay khi hết hạn TTL (Part B)", "session_id": sid_deleted},
                headers=deleted_post_headers,
            )
            assert inflight_entered.wait(timeout=5.0)

            fake_now[0] = 2005.0
            res_del = client.delete(
                f"/chat/{sid_deleted}",
                headers=deleted_del_headers,
            )
            assert res_del.status_code == 200
            assert sid_deleted in provider._session_revisions

            # Advance fake clock past tombstone TTL (2005 + 60 < 2100)
            fake_now[0] = 2100.0
            inflight_release.set()
            res_deleted_expired = f_deleted.result(timeout=5.0)

        assert res_deleted_expired.status_code == 200
        assert sid_deleted not in provider._sessions
        assert sid_deleted not in provider._session_revisions
