"""Tests for RAG Module: Chunker, Embedder, and Retrieval."""

import pytest
from app.rag.chunker import SectionAwareChunker, RAGChunk
from app.rag.embedder import MockEmbedder, SentenceTransformerEmbedder
from app.rag.retriever import RAGRetriever


def test_chunker_section_splitting_and_topics():
    chunker = SectionAwareChunker(target_chunk_words=100, max_chunk_words=200)
    sample_text = """
== Understand ==
Da Nang is the commercial and educational center of Central Vietnam.

== Eat ==
Da Nang is famous for Mi Quang noodles and fresh seafood.
You can find Banh Xeo along Hoang Dieu street.

== Stay safe ==
Traffic can be busy when crossing the Dragon Bridge. Always look both ways.
"""
    chunks = chunker.chunk_document(
        document_id="test-doc-01",
        title="Da Nang",
        text=sample_text,
        source_name="wikivoyage",
        source_url="https://en.wikivoyage.org/wiki/Da_Nang",
        license="CC BY-SA 3.0",
        attribution="Wikivoyage contributors",
        language="en",
    )

    assert len(chunks) >= 3
    topics = {c.topic for c in chunks}
    assert "culinary" in topics
    assert "safety" in topics

    # Check hashes and headers
    for c in chunks:
        assert len(c.content_hash) == 64
        assert c.source_name == "wikivoyage"
        assert c.license == "CC BY-SA 3.0"
        assert "Da Nang" in c.content


def test_chunker_deterministic_hash():
    text_a = "Da Nang culinary scene is vibrant."
    text_b = "  Da Nang   culinary scene is vibrant. \n"
    hash_a = SectionAwareChunker.compute_hash(text_a)
    hash_b = SectionAwareChunker.compute_hash(text_b)
    assert hash_a == hash_b


def test_mock_embedder_dimensions_and_determinism():
    embedder = MockEmbedder(dimension=384)
    assert embedder.dimension == 384
    assert embedder.model_name == "mock-embedder-384"

    vec1 = embedder.embed_text("Hanoi old quarter")
    vec2 = embedder.embed_text("Hanoi old quarter")
    vec3 = embedder.embed_text("Hue imperial city")

    assert len(vec1) == 384
    assert vec1 == vec2  # Deterministic
    assert vec1 != vec3  # Distinct texts produce distinct vectors


def test_rag_retrieval_da_nang_culinary():
    import asyncio
    async def _run():
        retriever = RAGRetriever()
        results = await retriever.search(query="Đà Nẵng có món ăn đặc trưng nào?", top_k=5, min_similarity=0.3)
        
        # Should retrieve Da Nang culinary knowledge from pgvector
        assert len(results) > 0
        top_result = results[0]
        assert "content" in top_result
        assert "similarity" in top_result
        assert top_result["similarity"] > 0.4
        assert "source_name" in top_result
        assert "source_url" in top_result
        assert top_result["source_name"] in ["wikivoyage", "osm"]

        # Verify no duplicate chunk IDs in top-k
        chunk_ids = [r["chunk_id"] for r in results]
        assert len(chunk_ids) == len(set(chunk_ids))

        await retriever.close()

    asyncio.run(_run())
