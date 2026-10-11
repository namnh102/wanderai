"""pgvector-backed RAG Retrieval Service for WanderAI."""

import json
import logging
from typing import List, Dict, Any, Optional
import asyncpg
from app.config import settings
from app.rag.embedder import BaseEmbedder, get_embedder

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Retrieves relevant knowledge chunks using PostgreSQL pgvector cosine similarity."""

    def __init__(self, embedder: Optional[BaseEmbedder] = None, database_url: Optional[str] = None):
        self.embedder = embedder or get_embedder()
        self.database_url = database_url or settings.DATABASE_URL
        self._pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=10)
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def search(
        self,
        query: str,
        top_k: int = 5,
        destination_id: Optional[str] = None,
        topic: Optional[str] = None,
        source_name: Optional[str] = None,
        language: Optional[str] = None,
        min_similarity: float = 0.3,
        include_unverified: bool = False,
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using pgvector cosine similarity.

        Production isolation (TASK 07.5): unless include_unverified=True (development/test only),
        a document linked to a place is returned only when that place has a place_sources row,
        and synthetic documents are never returned.
        """
        query_vec = self.embedder.embed_text(query)
        vec_str = "[" + ",".join(str(x) for x in query_vec) + "]"

        pool = await self.get_pool()
        conditions = ["embedding IS NOT NULL"]
        if not include_unverified:
            conditions.append("source_name NOT IN ('synthetic', 'mock')")
            conditions.append(
                "(place_id IS NULL OR EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = documents.place_id))"
            )
        params = [vec_str]
        param_idx = 2

        if destination_id:
            conditions.append(f"destination_id = ${param_idx}::uuid")
            params.append(destination_id)
            param_idx += 1

        if topic:
            conditions.append(f"topic = ${param_idx}")
            params.append(topic)
            param_idx += 1

        if source_name:
            conditions.append(f"source_name = ${param_idx}")
            params.append(source_name)
            param_idx += 1

        if language:
            conditions.append(f"language = ${param_idx}")
            params.append(language)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT 
                id::text as chunk_id,
                document_id,
                title,
                section_heading,
                topic,
                content,
                source_name,
                source_url,
                license,
                attribution,
                language,
                destination_id::text,
                category,
                metadata,
                1 - (embedding <=> $1::vector) as similarity
            FROM documents
            WHERE {where_clause}
            ORDER BY embedding <=> $1::vector ASC
            LIMIT {top_k}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for r in rows:
            sim = float(r["similarity"])
            if sim >= min_similarity:
                results.append({
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "title": r["title"],
                    "section_heading": r["section_heading"],
                    "topic": r["topic"],
                    "content": r["content"],
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "license": r["license"],
                    "attribution": r["attribution"],
                    "language": r["language"],
                    "destination_id": r["destination_id"],
                    "category": r["category"],
                    "similarity": round(sim, 4),
                })

        return results

    async def insert_chunks(self, chunks: List[Any], batch_size: int = 50) -> int:
        """Insert or update chunks with embeddings into pgvector."""
        if not chunks:
            return 0

        pool = await self.get_pool()
        total_inserted = 0

        # Embed texts in batches
        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed_batch(texts)

        async with pool.acquire() as conn:
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i : i + batch_size]
                batch_embeddings = embeddings[i : i + batch_size]

                for chunk, emb in zip(batch_chunks, batch_embeddings):
                    vec_str = "[" + ",".join(str(x) for x in emb) + "]"
                    meta_json = json.dumps(chunk.metadata if hasattr(chunk, "metadata") else {})

                    sql = """
                        INSERT INTO documents (
                            id, document_id, source_name, source_url, license, attribution,
                            destination_id, place_id, language, topic, section_heading,
                            title, content, content_hash, embedding_model, category, metadata,
                            retrieved_at, created_at, updated_at, embedding
                        ) VALUES (
                            gen_random_uuid(), $1, $2, $3, $4, $5,
                            $6::uuid, $7::uuid, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16::jsonb,
                            COALESCE($18::timestamptz, NOW()), NOW(), NOW(), $17::vector
                        )
                        ON CONFLICT (content_hash, embedding_model) DO UPDATE SET
                            title = EXCLUDED.title,
                            section_heading = EXCLUDED.section_heading,
                            topic = EXCLUDED.topic,
                            content = EXCLUDED.content,
                            source_url = EXCLUDED.source_url,
                            attribution = EXCLUDED.attribution,
                            destination_id = EXCLUDED.destination_id,
                            place_id = EXCLUDED.place_id,
                            license = EXCLUDED.license,
                            category = EXCLUDED.category,
                            metadata = EXCLUDED.metadata,
                            retrieved_at = CASE WHEN $18::timestamptz IS NULL THEN documents.retrieved_at ELSE $18::timestamptz END,
                            updated_at = NOW(),
                            embedding = EXCLUDED.embedding
                    """
                    dest_id = chunk.destination_id if chunk.destination_id else None
                    pl_id = chunk.place_id if chunk.place_id else None

                    await conn.execute(
                        sql,
                        chunk.document_id,
                        chunk.source_name,
                        chunk.source_url,
                        chunk.license,
                        chunk.attribution,
                        dest_id,
                        pl_id,
                        chunk.language,
                        chunk.topic,
                        chunk.section_heading,
                        chunk.title,
                        chunk.content,
                        chunk.content_hash,
                        self.embedder.model_name,
                        chunk.category,
                        meta_json,
                        vec_str,
                        getattr(chunk, "retrieved_at", None),
                    )
                    total_inserted += 1

        return total_inserted
