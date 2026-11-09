"""RAG Service bridging FastAPI endpoints and pgvector RAGRetriever."""

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.rag.embedder import get_embedder  # noqa: F401
from app.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)

RetrievalStatus = Literal["ok", "empty", "error"]


@dataclass(frozen=True)
class RetrievalResult:
    """Tri-state RAG retrieval result distinguishing OK, EMPTY, and ERROR."""

    status: RetrievalStatus
    context: str
    chunks: List[Dict[str, Any]]
    sources: List[str]
    error_type: Optional[str] = None


class RAGService:
    """Service for embedding queries and retrieving grounded travel knowledge."""

    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self.retriever = retriever or RAGRetriever()
        self.embedder = self.retriever.embedder

    async def embed_query(self, query: str) -> list:
        """Embed a query text."""
        return self.embedder.embed_text(query)

    async def retrieve_with_status(self, query: str, top_k: int = 4) -> RetrievalResult:
        """Retrieve grounded chunks with explicit tri-state status (ok | empty | error)."""
        try:
            chunks = await self.retriever.search(query=query, top_k=top_k, min_similarity=0.35)
        except Exception as e:
            logger.warning(f"RAG search error ({type(e).__name__}): {e}")
            return RetrievalResult(
                status="error",
                context="",
                chunks=[],
                sources=[],
                error_type=type(e).__name__,
            )

        if not chunks:
            return RetrievalResult(
                status="empty",
                context="",
                chunks=[],
                sources=[],
            )

        context_lines = []
        for c in chunks:
            content = c.get("content", "")
            source = c.get("source_name", "open_data")
            license_str = c.get("license", "")
            attribution = c.get("attribution", "")

            context_lines.append(
                f"--- [Source: {source} ({license_str} - {attribution})] ---\n"
                f"{content}\n"
            )

        context_str = "\n".join(context_lines)
        sources = list(dict.fromkeys(c["source_url"] for c in chunks if c.get("source_url")))
        return RetrievalResult(
            status="ok",
            context=context_str,
            chunks=chunks,
            sources=sources,
        )

    async def search_similar(self, query: str, top_k: int = 4) -> str:
        """Search similar chunks and format them as grounding context for LLM prompts."""
        result = await self.retrieve_with_status(query, top_k=top_k)
        return result.context

    async def search_with_sources(self, query: str, top_k: int = 4) -> Tuple[str, List[Dict[str, Any]]]:
        """Legacy 2-tuple wrapper returning (context_str, chunks) for backward-compatible callers."""
        result = await self.retrieve_with_status(query, top_k=top_k)
        return result.context, result.chunks
