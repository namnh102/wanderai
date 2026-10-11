"""TASK 07.5 tests: OSM place knowledge documents, provenance integrity, idempotency, isolation, grounding.

Unit tests need no services. The DB tests use the same dev PostgreSQL as the other RAG tests and the real
sentence-transformers model; they are skipped when the database is unreachable.
"""

import asyncio
import uuid

import pytest

from app.rag.embedder import SentenceTransformerEmbedder
from app.rag.evaluate import FROZEN_QUERIES, GROUNDING_CULTURE_HANOI, opening_hours_query
from app.rag.ingestion import WikivoyageIngester
from app.rag.osm_documents import (
    CATEGORY_LABEL_VI,
    OSM_ATTRIBUTION,
    OSM_LICENSE,
    build_osm_place_chunk,
    format_osm_address,
)
from app.rag.retriever import RAGRetriever

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _place(tags, **kw):
    base = {
        "id": str(uuid.uuid4()),
        "name": "Bảo tàng Thử",
        "category": "culture",
        "destination_id": str(uuid.uuid4()),
        "destination_name": "Hà Nội",
        "latitude": 21.03,
        "longitude": 105.85,
        "sources": [
            {"source_name": "osm", "source_id": "node/42", "raw_data": tags, "created_at": "2026-10-03T18:49:34+00:00"}
        ],
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- unit tests (no services)

def test_document_contains_only_existing_osm_facts_and_omits_missing_ones():
    c = build_osm_place_chunk(_place({"name": "Bảo tàng Thử", "tourism": "museum"}))
    assert "Bảo tàng Thử thuộc nhóm văn hóa tại Hà Nội." in c.content
    assert "Loại OSM: tourism=museum." in c.content
    assert "Tọa độ: 21.03, 105.85." in c.content
    for absent in ("Giờ mở cửa", "Website", "Điện thoại", "Ẩm thực", "Mô tả", "Địa chỉ", "Đánh giá", "rating", "None", "null"):
        assert absent not in c.content


def test_present_attributes_are_copied_verbatim():
    tags = {
        "name": "Quán X", "name:en": "X Place", "amenity": "restaurant", "opening_hours": "Mo-Su 08:00-22:00",
        "website": "https://x.example", "phone": "+84 24 1234", "cuisine": "vietnamese;seafood",
        "wheelchair": "yes", "wikidata": "Q123", "addr:street": "Hàng Bè", "addr:housenumber": "41",
        "addr:city": "Hà Nội",
    }
    c = build_osm_place_chunk(_place(tags, category="restaurant"))
    for expected in (
        "Giờ mở cửa: Mo-Su 08:00-22:00.", "Website: https://x.example.", "Điện thoại: +84 24 1234.",
        "Ẩm thực: vietnamese;seafood.", "Tiếp cận xe lăn: yes.", "Wikidata: Q123.",
        "Địa chỉ: 41 Hàng Bè, Hà Nội.", "(X Place)",
    ):
        assert expected in c.content, expected
    assert c.metadata["osm_tags_used"] == sorted(["opening_hours", "website", "phone", "cuisine", "wheelchair", "wikidata"])


def test_provenance_fields_complete_and_deterministic():
    place = _place({"name": "A", "tourism": "attraction"})
    c1, c2 = build_osm_place_chunk(place), build_osm_place_chunk(place)
    assert c1.content_hash == c2.content_hash and len(c1.content_hash) == 64
    assert c1.source_name == "osm" and c1.license == OSM_LICENSE == "ODbL 1.0"
    assert c1.attribution == OSM_ATTRIBUTION == "© OpenStreetMap contributors"
    assert c1.source_url == "https://www.openstreetmap.org/node/42"
    assert c1.place_id == place["id"] and c1.metadata["source_id"] == "node/42"
    assert c1.retrieved_at is not None


def test_place_without_osm_source_is_never_ingested():
    assert build_osm_place_chunk(_place({}, sources=[])) is None
    assert build_osm_place_chunk(_place({}, sources=[{"source_name": "wikidata", "source_id": "Q1", "raw_data": {}}])) is None


def test_address_only_from_addr_tags_never_placeholder():
    assert format_osm_address({"name": "X"}) == ""
    assert format_osm_address({"addr:street": "Lê Lợi", "addr:city": "Huế"}) == "Lê Lợi, Huế"


def test_every_place_category_has_a_label():
    assert {"attraction", "culture", "beach", "nature", "entertainment", "cafe", "restaurant", "hotel"} <= set(CATEGORY_LABEL_VI)


def test_frozen_evaluation_queries_unchanged():
    assert [q["query"] for q in FROZEN_QUERIES] == [
        "Đà Nẵng có món ăn đặc trưng nào?",
        "Thời tiết Hà Nội vào mùa thu như thế nào?",
        "How to get to Ha Long Bay from Hanoi?",
        "Lưu ý an toàn khi đi taxi ở Việt Nam",
    ]


# ---------------------------------------------------------------- DB tests

def _db(coro_fn):
    """Run an async test body with a connected retriever; skip if the database is unavailable."""

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


def test_all_osm_documents_have_verified_provenance_zero_violations():
    async def body(_r, pool):
        async with pool.acquire() as c:
            violations = await c.fetch("""
                SELECT d.id::text, d.title FROM documents d
                WHERE d.source_name = 'osm' AND NOT (
                      d.place_id IS NOT NULL
                  AND EXISTS (SELECT 1 FROM places p WHERE p.id = d.place_id AND p.deleted_at IS NULL)
                  AND EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = d.place_id
                              AND ps.source_name = d.source_name AND ps.source_id = d.metadata->>'source_id')
                  AND d.license = 'ODbL 1.0'
                  AND d.attribution = '© OpenStreetMap contributors'
                  AND d.source_url = 'https://www.openstreetmap.org/' || (d.metadata->>'source_id')
                  AND d.embedding_model = $1
                  AND d.retrieved_at IS NOT NULL AND length(d.content_hash) = 64)
            """, MODEL)
            assert violations == []

    _db(body)


def test_every_verified_place_has_exactly_one_osm_document_and_no_unsourced_document():
    async def body(_r, pool):
        async with pool.acquire() as c:
            verified = await c.fetchval(
                "SELECT count(*) FROM places p WHERE p.deleted_at IS NULL AND EXISTS "
                "(SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id AND ps.source_name = 'osm')")
            missing = await c.fetchval(
                "SELECT count(*) FROM places p WHERE p.deleted_at IS NULL AND EXISTS "
                "(SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id AND ps.source_name = 'osm') "
                "AND (SELECT count(*) FROM documents d WHERE d.place_id = p.id AND d.source_name = 'osm') <> 1")
            unsourced_docs = await c.fetchval(
                "SELECT count(*) FROM documents d WHERE d.place_id IS NOT NULL AND NOT EXISTS "
                "(SELECT 1 FROM place_sources ps WHERE ps.place_id = d.place_id)")
            osm_docs = await c.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
            assert verified >= 357
            assert missing == 0
            assert unsourced_docs == 0
            assert osm_docs == verified

    _db(body)


def test_embeddings_valid_and_no_duplicate_chunks():
    async def body(_r, pool):
        async with pool.acquire() as c:
            assert await c.fetchval("SELECT count(*) FROM documents WHERE embedding IS NULL") == 0
            assert await c.fetchval("SELECT count(DISTINCT vector_dims(embedding)) FROM documents") == 1
            assert await c.fetchval("SELECT min(vector_dims(embedding)) FROM documents") == 384
            assert await c.fetchval("SELECT count(*) FROM documents WHERE embedding_model <> $1", MODEL) == 0
            assert await c.fetchval("SELECT count(*) - count(DISTINCT (content_hash, embedding_model)) FROM documents") == 0
            assert await c.fetchval("SELECT count(*) - count(DISTINCT document_id) FROM documents WHERE source_name = 'osm'") == 0
            assert await c.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'") == 464
            assert await c.fetchval("SELECT count(*) FROM pg_indexes WHERE indexname = 'documents_embedding_hnsw_idx'") == 1

    _db(body)


def test_ingestion_is_idempotent():
    async def body(_r, pool):
        embedder = SentenceTransformerEmbedder()
        retriever = RAGRetriever(embedder=embedder)
        try:
            async def snapshot():
                async with pool.acquire() as c:
                    rows = await c.fetch(
                        "SELECT source_name, count(*) n, count(DISTINCT content_hash) h FROM documents GROUP BY 1 ORDER BY 1")
                    return [(r["source_name"], r["n"], r["h"]) for r in rows]

            ingester = WikivoyageIngester(retriever)
            await ingester.ingest_canonical_places()
            a = await snapshot()
            result = await ingester.ingest_canonical_places()
            b = await snapshot()
            assert a == b
            assert result["stale_osm_documents_quarantined_and_removed"] == 0
        finally:
            await retriever.close()

    _db(body)


def test_production_retriever_isolates_unsourced_and_synthetic_documents():
    async def body(retriever, pool):
        marker = "Địa điểm giả lập kiểm thử cô lập " + uuid.uuid4().hex[:8]
        place_id = str(uuid.uuid4())
        doc_ids = []
        async with pool.acquire() as c:
            dest = await c.fetchval("SELECT id::text FROM destinations LIMIT 1")
            await c.execute(
                "INSERT INTO places (id, destination_id, name, review_count, updated_at) VALUES ($1::uuid, $2::uuid, $3, 0, NOW())",
                place_id, dest, marker)
            vec = "[" + ",".join(str(x) for x in retriever.embedder.embed_text(marker)) + "]"
            try:
                for i, (src, pid) in enumerate([("osm", place_id), ("synthetic", None)]):
                    did = str(uuid.uuid4())
                    doc_ids.append(did)
                    await c.execute(
                        """INSERT INTO documents (id, document_id, source_name, source_url, license, attribution, place_id,
                                language, title, content, content_hash, embedding_model, embedding)
                           VALUES ($1::uuid, $2, $3, '', 'test', 'test', $4::uuid, 'vi', $5, $6, $7, $8, $9::vector)""",
                        did, f"isolation-test-{i}", src, pid, marker, marker + f" {src}", uuid.uuid4().hex + uuid.uuid4().hex, MODEL, vec)
                prod = await retriever.search(marker, top_k=10, min_similarity=0.0)
                assert marker not in [r["title"] for r in prod]
                dev = await retriever.search(marker, top_k=10, min_similarity=0.0, include_unverified=True)
                assert marker in [r["title"] for r in dev]
            finally:
                await c.execute("DELETE FROM documents WHERE id = ANY($1::uuid[])", doc_ids)
                await c.execute("DELETE FROM places WHERE id = $1::uuid", place_id)

    _db(body)


def test_frozen_retrieval_regression_expected_topics_still_found():
    expected_rank_limit = {"RAG-EVAL-01": 2, "RAG-EVAL-02": 2, "RAG-EVAL-03": 4}  # ranks measured BEFORE 07.5

    async def body(retriever, _pool):
        for q in FROZEN_QUERIES:
            res = await retriever.search(q["query"], top_k=5, min_similarity=0.35)
            assert res, q["id"]
            ranks = [i + 1 for i, r in enumerate(res) if r["topic"] == q["expected_topic"] and r["title"] == q["expected_title"]]
            if q["id"] in expected_rank_limit:
                assert ranks and ranks[0] <= expected_rank_limit[q["id"]], (q["id"], ranks)
            assert len({r["chunk_id"] for r in res}) == len(res)

    _db(body)


def test_grounding_culture_hanoi_returns_verified_osm_culture_places():
    async def body(retriever, pool):
        res = await retriever.search(GROUNDING_CULTURE_HANOI, top_k=8, min_similarity=0.3)
        assert any(r["source_name"] == "osm" and r["category"] == "culture" for r in res)
        async with pool.acquire() as c:
            hanoi = await c.fetchval("SELECT id::text FROM destinations WHERE name = 'Hà Nội'")
        scoped = await retriever.search(GROUNDING_CULTURE_HANOI, top_k=5, destination_id=hanoi, source_name="osm", min_similarity=0.3)
        assert scoped and any(r["category"] == "culture" for r in scoped)
        for r in scoped:
            assert r["source_name"] == "osm" and r["license"] == "ODbL 1.0" and r["destination_id"] == hanoi

    _db(body)


def test_grounding_opening_hours_only_states_source_metadata():
    async def body(retriever, pool):
        async with pool.acquire() as c:
            row = await c.fetchrow("""
                SELECT p.name, ps.raw_data->>'opening_hours' AS oh
                FROM places p JOIN place_sources ps ON ps.place_id = p.id AND ps.source_name = 'osm'
                WHERE ps.raw_data->>'opening_hours' IS NOT NULL
                  AND (SELECT count(*) FROM places p2 WHERE p2.name = p.name) = 1
                ORDER BY p.name LIMIT 1""")
        assert row is not None
        res = await retriever.search(opening_hours_query(row["name"]), top_k=5, min_similarity=0.3)
        hit = [r for r in res if r["source_name"] == "osm" and r["title"] == row["name"]]
        assert hit, f"{row['name']} not retrieved"
        assert f"Giờ mở cửa: {row['oh']}." in hit[0]["content"]
        async with pool.acquire() as c:
            bad = await c.fetchval("""
                SELECT count(*) FROM documents d JOIN place_sources ps ON ps.place_id = d.place_id AND ps.source_name = 'osm'
                WHERE d.source_name = 'osm' AND d.content LIKE '%Giờ mở cửa:%' AND ps.raw_data->>'opening_hours' IS NULL""")
        assert bad == 0

    _db(body)
