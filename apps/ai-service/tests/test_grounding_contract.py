"""TASK 07.5 — grounding contract, deterministic retrieval and mock-provider chat grounding.

None of these tests call Gemini. They prove the prompt contract and the exact message handed to the
provider; they are NOT evidence that a live Gemini reply is grounded.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.prompts.system_prompt import (
    GROUNDING_RULES,
    NO_OPENING_HOURS_INFO,
    NO_PRICE_INFO,
    NO_RATING_INFO,
    SYSTEM_PROMPT,
)
from app.rag.retriever import RAGRetriever
from app.routers.chat import NO_CONTEXT_INSTRUCTION, build_grounded_message, retrieve_grounding

client = TestClient(app)

HANOI_CULTURE = "Địa điểm văn hóa ở Hà Nội"
HCM_MUSEUM_HOURS = "Giờ mở cửa Bảo tàng Hồ Chí Minh"
OSM_URL_PREFIX = "https://www.openstreetmap.org/"


# ------------------------------------------------------------ prompt contract (unit)

def test_prompt_contains_exact_fallback_sentences():
    assert NO_PRICE_INFO == "Chưa có thông tin giá trong dữ liệu hiện có."
    assert NO_OPENING_HOURS_INFO == "Chưa có thông tin giờ mở cửa trong dữ liệu hiện có."
    assert NO_RATING_INFO == "Chưa có đánh giá."
    for sentence in (NO_PRICE_INFO, NO_OPENING_HOURS_INFO, NO_RATING_INFO):
        assert sentence in SYSTEM_PROMPT


def test_prompt_only_allows_facts_from_context_or_tools():
    assert GROUNDING_RULES in SYSTEM_PROMPT
    assert "dữ liệu truy xuất" in GROUNDING_RULES and "kết quả của tool" in GROUNDING_RULES
    assert "Tuyệt đối không bịa" in GROUNDING_RULES


def test_prompt_no_longer_forces_prices_or_opening_hours():
    # The pre-07.5 rules forced "Kem gia VND cu the" and "gio mo cua" in every answer.
    assert "Kem gia VND cu the" not in SYSTEM_PROMPT
    assert "(~50.000d/suat" not in SYSTEM_PROMPT
    assert "Kem tips thuc te (gio mo cua" not in SYSTEM_PROMPT
    assert "Chi dua gia, gio mo cua, danh gia khi co trong du lieu" in SYSTEM_PROMPT


def test_budget_numbers_only_from_tool():
    assert "calculate_budget" in GROUNDING_RULES and "không tự ước lượng" in GROUNDING_RULES


def test_prompt_keeps_vietnamese_persona_and_tools():
    assert "Wandy" in SYSTEM_PROMPT and "tieng Viet" in SYSTEM_PROMPT
    for tool in ("get_weather", "search_places", "calculate_budget", "search_hotels"):
        assert tool in SYSTEM_PROMPT


# ------------------------------------------------------------ deterministic retrieval (no Gemini)

def _db(coro_fn):
    async def _run():
        retriever = RAGRetriever()
        try:
            pool = await retriever.get_pool()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"database unavailable: {e}")
        try:
            return await coro_fn(retriever, pool)
        finally:
            await retriever.close()

    return asyncio.run(_run())


async def _assert_verified(pool, results):
    """Every returned document is wikivoyage or an OSM document backed by a real osm place_sources row."""
    assert results
    for r in results:
        assert r["source_name"] in ("osm", "wikivoyage"), r["source_name"]
        assert r["source_name"] not in ("synthetic", "mock")
        assert r["source_url"], r["title"]
        if r["source_name"] == "osm":
            assert r["source_url"].startswith(OSM_URL_PREFIX)
            assert r["license"] == "ODbL 1.0"
            async with pool.acquire() as c:
                n = await c.fetchval(
                    "SELECT count(*) FROM place_sources ps JOIN documents d ON d.place_id = ps.place_id "
                    "WHERE ps.source_name = 'osm' AND d.source_url = $1 AND d.source_name = 'osm' "
                    "AND $2 || ps.source_id = d.source_url",
                    r["source_url"], OSM_URL_PREFIX,
                )
            assert n >= 1, f"unsourced/unverified OSM document returned: {r['title']}"
        else:
            assert r["source_url"].startswith("https://en.wikivoyage.org/")


def test_retrieval_hanoi_culture_returns_verified_documents_only():
    async def body(retriever, pool):
        res = await retriever.search(HANOI_CULTURE, top_k=8, min_similarity=0.3)
        await _assert_verified(pool, res)
        assert any(r["source_name"] == "osm" and r["category"] == "culture" for r in res)

    _db(body)


def test_retrieval_ho_chi_minh_museum_hours_returns_matching_osm_document():
    async def body(retriever, pool):
        res = await retriever.search(HCM_MUSEUM_HOURS, top_k=5, min_similarity=0.3)
        await _assert_verified(pool, res)
        hits = [r for r in res if r["source_name"] == "osm" and "Hồ Chí Minh" in r["title"]]
        assert hits, [r["title"] for r in res]
        assert "Giờ mở cửa:" in hits[0]["content"]  # only present when the OSM tag exists (verified in 07.5 ingestion tests)

    _db(body)


def test_production_search_excludes_synthetic_and_unsourced_documents():
    async def body(retriever, pool):
        for q in (HANOI_CULTURE, HCM_MUSEUM_HOURS, "bãi biển đẹp ở Đà Nẵng"):
            res = await retriever.search(q, top_k=10, min_similarity=0.0)
            assert all(r["source_name"] not in ("synthetic", "mock") for r in res)
            async with pool.acquire() as c:
                for r in res:
                    if r["source_name"] == "osm":
                        assert await c.fetchval(
                            "SELECT count(*) FROM documents d JOIN place_sources ps ON ps.place_id = d.place_id "
                            "WHERE d.source_url = $1", r["source_url"]) >= 1

    _db(body)


# ------------------------------------------------------------ chat grounding with a MOCK provider

def _chat(message, retrieval):
    with patch("app.routers.chat.retrieve_grounding", new=AsyncMock(return_value=retrieval)), patch(
        "app.routers.chat.gemini_provider.chat_with_tools", new_callable=AsyncMock
    ) as llm:
        llm.return_value = {"response": "mock reply", "tool_calls": []}
        res = client.post("/chat", json={"message": message, "session_id": "grounding-test"})
    assert res.status_code == 200
    return res.json(), llm


def test_mock_provider_receives_context_question_and_instruction():
    ctx = ("--- [Source: osm (ODbL 1.0 - © OpenStreetMap contributors)] ---\n"
           "Bảo tàng Hồ Chí Minh thuộc nhóm văn hóa tại Hà Nội. Giờ mở cửa: Tu-Su 08:00-11:30.")
    url = "https://www.openstreetmap.org/way/123"
    body, llm = _chat(HCM_MUSEUM_HOURS, (ctx, [url]))
    sent = llm.call_args.kwargs["message"]
    assert ctx in sent
    assert HCM_MUSEUM_HOURS in sent
    assert "không bịa" in sent  # grounding instruction
    assert sent.index(ctx) < sent.index(HCM_MUSEUM_HOURS)
    assert body["sources"] == [url] and body["reply"] == "mock reply"


def test_mock_provider_no_context_gets_no_invention_instruction():
    body, llm = _chat("Xin chào", ("", []))
    sent = llm.call_args.kwargs["message"]
    assert NO_CONTEXT_INSTRUCTION in sent and "Xin chào" in sent
    assert "không bịa" in sent and "chưa có thông tin" in sent
    assert body["sources"] == []


def test_mock_provider_missing_fact_context_is_not_padded():
    ctx = "--- [Source: osm (ODbL 1.0)] ---\nChùa Thử thuộc nhóm văn hóa. Tọa độ: 21.0, 105.8."  # no hours, no price
    _, llm = _chat("Giờ mở cửa và giá vé chùa Thử?", (ctx, ["https://www.openstreetmap.org/node/9"]))
    sent = llm.call_args.kwargs["message"]
    assert "Giờ mở cửa:" not in sent and "Giá vé" not in sent  # nothing invented by the pipeline
    assert "không bịa thêm giờ mở cửa, giá vé" in sent  # model is told not to add them


def test_synthetic_documents_never_reach_the_provider():
    from app.services.rag import RAGService

    async def go():
        svc = RAGService()
        try:
            context, chunks = await svc.search_with_sources(HANOI_CULTURE, top_k=4)
        finally:
            await svc.retriever.close()
        return context, [c["source_url"] for c in chunks if c.get("source_url")]

    ctx, sources = asyncio.run(go())
    assert ctx, "retrieval returned nothing for a query that must have verified documents"
    assert "[Source: synthetic" not in ctx and "[Source: mock" not in ctx
    assert sources and all(s.startswith((OSM_URL_PREFIX, "https://en.wikivoyage.org/")) for s in sources)
    with patch("app.routers.chat.retrieve_grounding", new=AsyncMock(return_value=(ctx, sources))), patch(
        "app.routers.chat.gemini_provider.chat_with_tools", new_callable=AsyncMock
    ) as llm:
        llm.return_value = {"response": "ok", "tool_calls": []}
        res = client.post("/chat", json={"message": HANOI_CULTURE, "session_id": "g2"})
    assert res.status_code == 200
    sent = llm.call_args.kwargs["message"]
    assert ctx in sent and "[Source: synthetic" not in sent and "[Source: mock" not in sent
