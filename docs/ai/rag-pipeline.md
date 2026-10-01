# RAG Pipeline — WanderAI

## Status: FOUNDATION (no documents ingested yet)

## Architecture

```
Documents (travel guides, destination info, safety tips)
    ↓
Cleaning (normalize unicode, remove HTML/markdown noise)
    ↓
Chunking (500-token chunks with 50-token overlap)
    ↓
Embedding (sentence-transformers model)
    ↓
pgvector (stored in `documents` table)
    ↓
Retrieval (cosine similarity search, top-k=5)
    ↓
Context assembly (chunk text + metadata)
    ↓
LLM (Gemini) with context → Response with citations
```

## Database Table

The `documents` table already exists in Prisma schema:
- id, title, content, source, url, license
- chunkId, embeddingModel, embedding (vector)
- createdAt, updatedAt

## Planned Document Sources

| Source | Type | Count | Status |
|--------|------|-------|--------|
| Vietnam destination guides | Text | ~50 | NOT_STARTED |
| Safety travel tips | Text | ~20 | NOT_STARTED |
| Restaurant/hotel descriptions | Text | ~100 | NOT_STARTED |
| FAQ/common questions | Text | ~30 | NOT_STARTED |

## Citation Requirement

Every RAG answer must include:
- document_id
- chunk_id
- retrieval_score
- source URL (when available)

## Next Steps

1. Collect a small pilot corpus (10-20 documents)
2. Implement chunking script
3. Generate embeddings
4. Store in pgvector
5. Implement retrieval endpoint
6. Test with sample queries
7. Measure retrieval quality
