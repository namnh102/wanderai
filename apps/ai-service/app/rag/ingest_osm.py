"""Reproducible CLI: regenerate OSM place knowledge documents for all verified places.

    cd apps/ai-service
    python -m app.rag.ingest_osm --out ../../docs/audit/evidence/rag-ingest-run1.json

Input : PostgreSQL tables places / place_sources(osm) / destinations / place_categories (DATABASE_URL)
Output: rows in `documents` (source_name='osm', ODbL 1.0) + a JSON run report (counts, model, timestamp, checksums)
Model : sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384-dim); the run ABORTS if the real
        model cannot be loaded (no silent fallback to the mock embedder).
"""

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone

from app.config import settings
from app.rag.embedder import SentenceTransformerEmbedder
from app.rag.ingestion import WikivoyageIngester
from app.rag.retriever import RAGRetriever

EXPECTED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


async def _counts(retriever: RAGRetriever) -> dict:
    pool = await retriever.get_pool()
    async with pool.acquire() as conn:
        by_source = {r["source_name"]: r["n"] for r in await conn.fetch(
            "SELECT source_name, count(*) AS n FROM documents GROUP BY 1 ORDER BY 1")}
        wiki = await conn.fetch(
            "SELECT id::text, content_hash FROM documents WHERE source_name = 'wikivoyage' ORDER BY id")
        return {
            "documents_total": sum(by_source.values()),
            "documents_by_source": by_source,
            "wikivoyage_fingerprint": hashlib.sha256(
                "\n".join(f"{r['id']}:{r['content_hash']}" for r in wiki).encode()).hexdigest(),
            "embeddings_null": await conn.fetchval("SELECT count(*) FROM documents WHERE embedding IS NULL"),
            "duplicate_content_hashes": await conn.fetchval(
                "SELECT count(*) - count(DISTINCT (content_hash, embedding_model)) FROM documents"),
            "document_quarantine": await conn.fetchval("SELECT count(*) FROM document_quarantine"),
            "verified_places": await conn.fetchval(
                "SELECT count(*) FROM places p WHERE p.deleted_at IS NULL AND EXISTS "
                "(SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id AND ps.source_name = 'osm')"),
        }


async def main_async(out: str | None) -> dict:
    embedder = SentenceTransformerEmbedder()  # raises if the model is unavailable
    assert embedder.model_name == EXPECTED_MODEL and embedder.dimension == 384
    retriever = RAGRetriever(embedder=embedder)
    before = await _counts(retriever)
    result = await WikivoyageIngester(retriever).ingest_canonical_places()
    after = await _counts(retriever)
    report = {
        "command": "python -m app.rag.ingest_osm",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": settings.DATABASE_URL.rsplit("@", 1)[-1],
        "embedding_model": embedder.model_name,
        "embedding_dimension": embedder.dimension,
        "before": before,
        "result": result,
        "after": after,
        "wikivoyage_unchanged": before["wikivoyage_fingerprint"] == after["wikivoyage_fingerprint"],
    }
    await retriever.close()
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    r = asyncio.run(main_async(args.out))
    print(json.dumps({k: r[k] for k in ("timestamp", "result", "after", "wikivoyage_unchanged")}, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()
