"""WanderAI RAG Module: Ingestion, Chunking, Embedding, and pgvector Retrieval."""

from app.rag.chunker import SectionAwareChunker, RAGChunk
from app.rag.embedder import BaseEmbedder, SentenceTransformerEmbedder, MockEmbedder, get_embedder
from app.rag.retriever import RAGRetriever

__all__ = [
    "SectionAwareChunker",
    "RAGChunk",
    "BaseEmbedder",
    "SentenceTransformerEmbedder",
    "MockEmbedder",
    "get_embedder",
    "RAGRetriever",
]
