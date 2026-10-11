"""Pilot Ingestion Pipeline for Wikivoyage & OSM Canonical Places."""

import asyncio
import json
import logging
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional
import asyncpg

from app.config import settings
from app.rag.chunker import SectionAwareChunker, RAGChunk
from app.rag.embedder import BaseEmbedder, get_embedder
from app.rag.osm_documents import build_osm_place_chunk
from app.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)

# Selected official pilot destinations for Wikivoyage
PILOT_WIKIVOYAGE_PAGES = [
    {"page": "Vietnam", "destination_name": None},
    {"page": "Hanoi", "destination_name": "Hà Nội"},
    {"page": "Da Nang", "destination_name": "Đà Nẵng"},
    {"page": "Hoi An", "destination_name": "Hội An"},
    {"page": "Hue", "destination_name": "Huế"},
    {"page": "Nha Trang", "destination_name": "Nha Trang"},
    {"page": "Da Lat", "destination_name": "Đà Lạt"},
    {"page": "Ha Long Bay", "destination_name": "Hạ Long"},
    {"page": "Ninh Binh", "destination_name": "Ninh Bình"},
    {"page": "Phu Quoc", "destination_name": "Phú Quốc"},
]

USER_AGENT = "WanderAI-ResearchBot/1.0 (academic travel research; contact: wanderai@example.com)"


class WikivoyageIngester:
    """Fetches official Wikivoyage articles, chunks them with section awareness, and stores in pgvector."""

    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self.chunker = SectionAwareChunker(target_chunk_words=250, max_chunk_words=450)
        self.retriever = retriever or RAGRetriever()

    def fetch_page_text(self, page_title: str) -> Optional[Dict[str, str]]:
        """Fetch article extract via official MediaWiki Action API."""
        encoded_title = urllib.parse.quote(page_title)
        url = (
            f"https://en.wikivoyage.org/w/api.php?"
            f"action=query&prop=extracts&explaintext=1&titles={encoded_title}&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pages = data.get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    if pid == "-1":
                        logger.warning(f"Page '{page_title}' not found on Wikivoyage.")
                        return None
                    return {
                        "title": pdata.get("title", page_title),
                        "extract": pdata.get("extract", ""),
                        "url": f"https://en.wikivoyage.org/wiki/{encoded_title}",
                    }
        except Exception as e:
            logger.error(f"Error fetching Wikivoyage page '{page_title}': {e}")
            return None

    async def resolve_destination_id(self, dest_name: Optional[str]) -> Optional[str]:
        """Look up destination UUID from database if available."""
        if not dest_name:
            return None
        pool = await self.retriever.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id::text FROM destinations WHERE name ILIKE $1 LIMIT 1",
                f"%{dest_name}%",
            )
            return row["id"] if row else None

    async def ingest_pilot_pages(self, pages: Optional[List[Dict[str, Optional[str]]]] = None) -> Dict[str, Any]:
        """Run pilot ingestion for specified Wikivoyage travel pages."""
        target_pages = pages or PILOT_WIKIVOYAGE_PAGES
        all_chunks: List[RAGChunk] = []
        ingested_pages = []

        for p_info in target_pages:
            page_name = p_info["page"]
            dest_name = p_info.get("destination_name")
            dest_id = await self.resolve_destination_id(dest_name)

            data = self.fetch_page_text(page_name)
            if not data or not data["extract"]:
                continue

            doc_id = f"wikivoyage-{page_name.lower().replace(' ', '_')}"
            chunks = self.chunker.chunk_document(
                document_id=doc_id,
                title=data["title"],
                text=data["extract"],
                source_name="wikivoyage",
                source_url=data["url"],
                license="CC BY-SA 3.0",
                attribution="Wikivoyage contributors",
                language="en",
                destination_id=dest_id,
                metadata={"canonical_destination": dest_name or page_name},
            )

            all_chunks.extend(chunks)
            ingested_pages.append({
                "page": page_name,
                "chunks_count": len(chunks),
                "url": data["url"],
            })

            # Rate limit respect
            await asyncio.sleep(0.5)

        # Store chunks in PostgreSQL pgvector
        inserted_count = await self.retriever.insert_chunks(all_chunks)

        return {
            "source": "Wikivoyage",
            "license": "CC BY-SA 3.0",
            "pages_ingested": len(ingested_pages),
            "pages_details": ingested_pages,
            "total_chunks_created": len(all_chunks),
            "total_chunks_saved": inserted_count,
        }

    async def fetch_verified_places(self) -> List[Dict[str, Any]]:
        """Verified places only: not deleted AND with at least one OSM place_sources row."""
        pool = await self.retriever.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT p.id::text AS id, p.name, p.latitude, p.longitude, p.destination_id::text AS destination_id,
                       d.name AS destination_name, c.name AS category,
                       (SELECT json_agg(json_build_object(
                                'source_name', ps.source_name, 'source_id', ps.source_id,
                                'raw_data', ps.raw_data, 'created_at', ps.created_at))
                          FROM place_sources ps WHERE ps.place_id = p.id AND ps.source_name = 'osm') AS sources
                FROM places p
                LEFT JOIN place_categories c ON p.category_id = c.id
                LEFT JOIN destinations d ON p.destination_id = d.id
                WHERE p.deleted_at IS NULL
                  AND EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id AND ps.source_name = 'osm')
                ORDER BY p.id
            """)
        places = []
        for r in rows:
            place = dict(r)
            place["sources"] = json.loads(place["sources"]) if isinstance(place["sources"], str) else place["sources"]
            places.append(place)
        return places

    async def ingest_canonical_places(self) -> Dict[str, Any]:
        """Idempotently (re)generate OSM knowledge documents for every verified place (TASK 07.5).

        - one document per verified place, built only from existing OSM tags (see osm_documents.py)
        - upsert on (content_hash, embedding_model): re-running never duplicates
        - OSM documents that are no longer produced (e.g. older format, or place lost its source) are
          copied to document_quarantine and removed, so no OSM-labelled document can outlive its provenance
        """
        places = await self.fetch_verified_places()
        osm_chunks: List[RAGChunk] = []
        for place in places:
            chunk = build_osm_place_chunk(place)
            if chunk is not None:
                osm_chunks.append(chunk)

        saved = await self.retriever.insert_chunks(osm_chunks)

        keep_ids = [c.document_id for c in osm_chunks]
        keep_hashes = [c.content_hash for c in osm_chunks]
        pool = await self.retriever.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                has_q = await conn.fetchval("SELECT to_regclass('document_quarantine') IS NOT NULL")
                stale_where = (
                    "source_name = 'osm' AND NOT (document_id = ANY($1::text[]) AND content_hash = ANY($2::text[]))"
                )
                if has_q:
                    await conn.execute(
                        f"""INSERT INTO document_quarantine (original_id, row_data, reason)
                            SELECT d.id, to_jsonb(d) - 'embedding', 'osm_document_superseded_by_task_07_5_regeneration'
                            FROM documents d WHERE {stale_where.replace('source_name', 'd.source_name').replace('document_id', 'd.document_id').replace('content_hash', 'd.content_hash')}""",
                        keep_ids, keep_hashes,
                    )
                removed = await conn.execute(f"DELETE FROM documents WHERE {stale_where}", keep_ids, keep_hashes)
        return {
            "source": "OpenStreetMap",
            "license": "ODbL 1.0",
            "embedding_model": self.retriever.embedder.model_name,
            "verified_places": len(places),
            "documents_generated": len(osm_chunks),
            "chunks_upserted": saved,
            "stale_osm_documents_quarantined_and_removed": int(removed.split()[-1]),
        }
