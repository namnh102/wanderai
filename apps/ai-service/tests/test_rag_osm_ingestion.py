"""TASK 07.5 & W07-B1-FIX-01A tests: OSM place knowledge documents, nested/flat tag rendering, provenance integrity, idempotency, isolation, grounding.

Unit tests need no services. The DB tests use the same dev PostgreSQL as the other RAG tests and the real
sentence-transformers model; they are skipped when the database is unreachable.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
import uuid

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.rag.embedder import SentenceTransformerEmbedder
from app.rag.evaluate import FROZEN_QUERIES, GROUNDING_CULTURE_HANOI, opening_hours_query
from app.rag.ingestion import WikivoyageIngester
from app.rag.osm_documents import (
    CATEGORY_LABEL_VI,
    OSM_ATTRIBUTION,
    OSM_LICENSE,
    _tags,
    build_osm_place_chunk,
    format_osm_address,
)
from app.rag.retriever import RAGRetriever
from scripts import audit_w07_b1a_existing_poi_knowledge as w07_b1a

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


def test_nested_raw_data_tags_renders_all_required_factual_fields():
    """W07-B1-FIX-01A Sections 3, 6, 7: Nested `raw_data.tags` exposes all required factual fields verbatim."""
    nested_raw_data = {
        "id": 37625751,
        "type": "way",
        "_osm_base_timestamp": "2026-10-07T09:52:02Z",
        "tags": {
            "name": "Bảo tàng Dân tộc học Việt Nam",
            "name:en": "Vietnam Museum of Ethnology",
            "tourism": "museum",
            "addr:housenumber": "1",
            "addr:street": "Đường Nguyễn Văn Huyên",
            "addr:district": "Quận Cầu Giấy",
            "addr:city": "Hà Nội",
            "opening_hours": "Tu-Su 08:30-17:30",
            "contact:website": "https://www.vme.org.vn/",
            "contact:phone": "+84 24 3756 2193",
            "cuisine": "vietnamese;coffee_shop",
            "wheelchair": "yes",
            "operator": "Viện Hàn lâm Khoa học xã hội Việt Nam",
            "wikidata": "Q1048345",
            "wikipedia": "vi:Bảo tàng Dân tộc học Việt Nam",
            "description:vi": "Bảo tàng trưng bày văn hóa 54 dân tộc Việt Nam",
        },
    }
    chunk = build_osm_place_chunk(
        _place(nested_raw_data, name="Bảo tàng Dân tộc học Việt Nam", category="culture")
    )
    assert chunk is not None
    for expected in (
        "Bảo tàng Dân tộc học Việt Nam (Vietnam Museum of Ethnology) thuộc nhóm văn hóa tại Hà Nội.",
        "Loại OSM: tourism=museum.",
        "Địa chỉ: 1 Đường Nguyễn Văn Huyên, Quận Cầu Giấy, Hà Nội.",
        "Giờ mở cửa: Tu-Su 08:30-17:30.",
        "Website: https://www.vme.org.vn/.",
        "Điện thoại: +84 24 3756 2193.",
        "Ẩm thực: vietnamese;coffee_shop.",
        "Tiếp cận xe lăn: yes.",
        "Đơn vị vận hành: Viện Hàn lâm Khoa học xã hội Việt Nam.",
        "Wikipedia: vi:Bảo tàng Dân tộc học Việt Nam.",
        "Wikidata: Q1048345.",
        "Mô tả (OSM): Bảo tàng trưng bày văn hóa 54 dân tộc Việt Nam.",
    ):
        assert expected in chunk.content, expected
    assert "tags" not in _tags(nested_raw_data)
    assert chunk.metadata["osm_base_timestamp"] == "2026-10-07T09:52:02Z"
    assert chunk.metadata["osm_tags_used"] == sorted(
        [
            "opening_hours",
            "contact:website",
            "contact:phone",
            "cuisine",
            "wheelchair",
            "operator",
            "wikipedia",
            "wikidata",
            "description:vi",
        ]
    )


def test_flat_vs_nested_raw_data_equivalence():
    """W07-B1-FIX-01A Section 8: Legacy flat `raw_data` and nested `raw_data.tags` render identical output."""
    shared_tags = {
        "name": "Quán Ăn Ngon",
        "name:en": "Ngon Restaurant",
        "amenity": "restaurant",
        "addr:housenumber": "18",
        "addr:street": "Phan Bội Châu",
        "addr:district": "Quận Hoàn Kiếm",
        "addr:city": "Hà Nội",
        "opening_hours": "Mo-Su 06:30-22:00",
        "website": "https://ngonhanoi.com.vn/",
        "phone": "+84 24 3942 8162",
        "cuisine": "vietnamese",
        "wheelchair": "limited",
        "operator": "Ngon Group",
        "wikidata": "Q999999",
        "wikipedia": "vi:Quán Ăn Ngon",
        "description": "Nhà hàng ẩm thực truyền thống ba miền",
    }
    fixed_place_id = "28df83b5-b37f-55c9-bb07-cd366d14843d"
    fixed_dest_id = "071e1382-7972-4dde-af61-dac9ef2c3c69"

    flat_place = _place(
        {**shared_tags, "_osm_base_timestamp": "2026-10-07T09:52:02Z"},
        id=fixed_place_id,
        destination_id=fixed_dest_id,
        name="Quán Ăn Ngon",
        category="restaurant",
    )
    nested_place = _place(
        {
            "id": 987654321,
            "type": "node",
            "_osm_base_timestamp": "2026-10-07T09:52:02Z",
            "tags": dict(shared_tags),
        },
        id=fixed_place_id,
        destination_id=fixed_dest_id,
        name="Quán Ăn Ngon",
        category="restaurant",
    )

    c_flat = build_osm_place_chunk(flat_place)
    c_nested = build_osm_place_chunk(nested_place)

    assert c_flat is not None and c_nested is not None
    assert _tags(flat_place["sources"][0]["raw_data"]) == _tags(
        nested_place["sources"][0]["raw_data"]
    )
    assert c_flat.content == c_nested.content
    assert c_flat.content_hash == c_nested.content_hash
    assert c_flat.chunk_id == c_nested.chunk_id == f"osm-place-{fixed_place_id}"
    assert c_flat.document_id == c_nested.document_id == f"osm-place-{fixed_place_id}"
    assert c_flat.metadata == c_nested.metadata
    assert c_flat.retrieved_at == c_nested.retrieved_at


def test_internal_metadata_filtering_and_malformed_raw_data_safety():
    """W07-B1-FIX-01A Sections 3C & 4: Internal `_...` keys, envelope keys, and malformed inputs fail safely."""
    # Nested tags with internal keys, None, whitespace, and nested objects
    raw_with_internals = {
        "id": 1001,
        "type": "way",
        "_internal_ provenance": "do_not_expose",
        "tags": {
            "_osm_internal_note": "secret",
            "_ingest_helper": "skip",
            "opening_hours": "Mo-Su 08:00-22:00",
            "website": "   ",
            "phone": None,
            "nested_object": {"unexpected": 1},
            "nested_list": ["a", "b"],
        },
    }
    extracted = _tags(raw_with_internals)
    assert extracted == {"opening_hours": "Mo-Su 08:00-22:00"}

    # JSON string containing nested tags
    assert _tags(json.dumps(raw_with_internals)) == {
        "opening_hours": "Mo-Su 08:00-22:00"
    }

    # Malformed / non-dict inputs must never crash and must return empty or valid flat fallback
    for malformed in (
        None,
        {},
        "",
        "{malformed json",
        "[1, 2, 3]",
        '"scalar string"',
        12345,
        ["not", "a", "dict"],
        {"tags": None},
        {"tags": "not-a-dict"},
        {"tags": [1, 2, 3]},
    ):
        assert _tags(malformed) == {}
        chunk = build_osm_place_chunk(_place(malformed))
        assert chunk is not None
        assert "None" not in chunk.content
        assert "tags" not in chunk.content

    # Flat raw_data where `tags` key is None or non-dict still preserves valid flat sibling tags
    flat_with_null_tags = {
        "tags": None,
        "opening_hours": "07:00-21:00",
        "website": "https://flat-fallback.example",
    }
    assert _tags(flat_with_null_tags) == {
        "opening_hours": "07:00-21:00",
        "website": "https://flat-fallback.example",
    }


def test_frozen_60_target_pois_and_759_repository_diagnostics():
    """W07-B1-FIX-01A Sections 9, 10, 11, 15, 18: Verify 59/60 nested, 40/60 useful post-render, and 621/759 repo nested."""
    places_v2 = json.loads(
        (REPO_ROOT / "data/curated/gomate_places_freeze_v2.json").read_text(
            encoding="utf-8"
        )
    )
    target_manifest = json.loads(
        (
            REPO_ROOT / "data/evaluation/w07/w07_review_target_60_pois_v1.json"
        ).read_text(encoding="utf-8")
    )
    pois_60 = target_manifest["pois"]

    assert len(places_v2) == 759
    assert len(pois_60) == 60

    # Repository-wide diagnostic: 621 / 759 Freeze v2 POIs have nested `raw_data.tags`
    repo_nested_count = 0
    for p in places_v2:
        osm_src = next(s for s in p["sources"] if s["source_name"] == "osm")
        rd = osm_src.get("raw_data") or {}
        if isinstance(rd, dict) and isinstance(rd.get("tags"), dict):
            repo_nested_count += 1
    assert repo_nested_count == 621

    # Frozen 60 target POIs diagnostic: 59 / 60 nested, 40 / 60 useful structured facts via repaired renderer
    v2_by_id = {p["place_id"]: p for p in places_v2}
    target_nested_count = 0
    target_useful_post_render_count = 0
    changed_hash_count = 0

    for tp in pois_60:
        pid = tp["poi_id"]
        p = v2_by_id[pid]
        osm_src = next(s for s in p["sources"] if s["source_name"] == "osm")
        rd = osm_src.get("raw_data") or {}
        if isinstance(rd, dict) and isinstance(rd.get("tags"), dict):
            target_nested_count += 1

        # Render directly through repaired build_osm_place_chunk using unmodified Freeze v2 place record
        repaired_chunk = build_osm_place_chunk(
            {
                "id": pid,
                "name": p["name"],
                "category": p.get("category"),
                "destination_id": None,
                "destination_name": p.get("destination"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "sources": p["sources"],
            }
        )
        assert repaired_chunk is not None
        assert repaired_chunk.chunk_id == f"osm-place-{pid}"
        assert repaired_chunk.document_id == f"osm-place-{pid}"
        assert repaired_chunk.place_id == pid
        assert repaired_chunk.metadata["source_id"] == osm_src["source_id"]

        # Compare against pre-fix flat-only rendering
        flat_only_raw = (
            {k: v for k, v in rd.items() if k != "tags"}
            if isinstance(rd, dict)
            else {}
        )
        legacy_chunk = build_osm_place_chunk(
            {
                "id": pid,
                "name": p["name"],
                "category": p.get("category"),
                "destination_id": None,
                "destination_name": p.get("destination"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "sources": [
                    {
                        "source_name": "osm",
                        "source_id": osm_src["source_id"],
                        "raw_data": flat_only_raw,
                    }
                ],
            }
        )
        assert legacy_chunk is not None
        assert repaired_chunk.chunk_id == legacy_chunk.chunk_id
        if repaired_chunk.content_hash != legacy_chunk.content_hash:
            changed_hash_count += 1

        has_rendered_address = "Địa chỉ:" in repaired_chunk.content
        has_rendered_facts = len(repaired_chunk.metadata["osm_tags_used"]) > 0
        if has_rendered_address or has_rendered_facts:
            target_useful_post_render_count += 1

    assert target_nested_count == 59
    assert target_useful_post_render_count == 40
    assert changed_hash_count > 0

    # Verify frozen B1A and all upstream W06..W07-B0 artifacts remain untouched
    b1a_res = w07_b1a.verify_b1a_audit_artifacts(REPO_ROOT)
    assert b1a_res["status"] == "PASS"
    assert (
        b1a_res["audit_internal_sha256"]
        == "27d6dae8fd3ec284ea92806080a044b6745fb30abdddc265297e0f9da1d1c5b2"
    )
    assert (
        b1a_res["audit_file_lf_sha256"]
        == "433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563"
    )
    assert (
        b1a_res["audit_md_lf_sha256"]
        == "130aca652c9b808a8b7e5fac50d070dd0c3f36a8e94f7693cfac8793643d0ac5"
    )


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
            if os.environ.get("REQUIRE_DB_TESTS") == "1":
                raise
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
            assert await c.fetchval("SELECT count(*) FROM pg_indexes WHERE indexname = 'documents_embedding_hnsw_idx'") == 1

    _db(body)


def test_historical_464_wikivoyage_corpus_presence_regression():
    """Historical corpus regression check separated from CI engineering fixture tests (C01-F04)."""

    async def body(_r, pool):
        async with pool.acquire() as c:
            wiki_count = await c.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
        if os.environ.get("REQUIRE_HISTORICAL_464_WIKIVOYAGE") == "1":
            assert wiki_count == 464
            return
        if wiki_count != 464:
            pytest.skip(
                "Requires 464 historical live-crawled Wikivoyage chunks "
                "(git_tracked_chunk_text_export_present=false in w07_b1a_existing_poi_knowledge_audit_v1.json; "
                "CI never fabricates Wikivoyage documents)"
            )
        assert wiki_count == 464

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

    async def body(retriever, pool):
        async with pool.acquire() as c:
            wiki_count = await c.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
        if wiki_count != 464:
            pytest.skip(
                "Requires 464 historical live-crawled Wikivoyage chunks "
                "(git_tracked_chunk_text_export_present=false in w07_b1a_existing_poi_knowledge_audit_v1.json)"
            )
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
                SELECT p.name, COALESCE(ps.raw_data->'tags'->>'opening_hours', ps.raw_data->>'opening_hours') AS oh
                FROM places p JOIN place_sources ps ON ps.place_id = p.id AND ps.source_name = 'osm'
                WHERE COALESCE(ps.raw_data->'tags'->>'opening_hours', ps.raw_data->>'opening_hours') IS NOT NULL
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
                WHERE d.source_name = 'osm'
                  AND d.content LIKE '%Giờ mở cửa:%'
                  AND COALESCE(ps.raw_data->'tags'->>'opening_hours', ps.raw_data->>'opening_hours') IS NULL""")
        assert bad == 0

    _db(body)
