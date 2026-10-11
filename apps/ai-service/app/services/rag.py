"""RAG Service bridging FastAPI endpoints and pgvector RAGRetriever."""

import logging
from typing import List, Dict, Any, Tuple, Optional
from app.rag.retriever import RAGRetriever
from app.rag.embedder import get_embedder

logger = logging.getLogger(__name__)


class RAGService:
    """Service for embedding queries and retrieving grounded travel knowledge."""

    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self.retriever = retriever or RAGRetriever()
        self.embedder = self.retriever.embedder

    async def embed_query(self, query: str) -> list:
        """Embed a query text."""
        return self.embedder.embed_text(query)

    async def search_similar(self, query: str, top_k: int = 4) -> str:
        """Search similar chunks and format them as grounding context for LLM prompts."""
        context_str, _ = await self.search_with_sources(query, top_k=top_k)
        return context_str

    async def search_with_sources(self, query: str, top_k: int = 4) -> Tuple[str, List[Dict[str, Any]]]:
        """Search similar chunks and return formatted context plus citation sources."""
        try:
            chunks = await self.retriever.search(query=query, top_k=top_k, min_similarity=0.35)
        except Exception as e:
            logger.warning(f"RAG search error: {e}")
            return "", []

        if not chunks:
            return "", []

        context_lines = []
        for c in chunks:
            title = c.get("title", "")
            heading = c.get("section_heading", "")
            content = c.get("content", "")
            source = c.get("source_name", "open_data")
            license_str = c.get("license", "")
            attribution = c.get("attribution", "")

            context_lines.append(
                f"--- [Source: {source} ({license_str} - {attribution})] ---\n"
                f"{content}\n"
            )

        context_str = "\n".join(context_lines)
        return context_str, chunks
