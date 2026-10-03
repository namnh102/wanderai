# TASK 07.5 — RAG Re-ingestion & Verified Place Knowledge Grounding

Branch: `feat/rag-verified-place-ingestion`

## Before → After (DB)

| Metric | Before | After |
|---|---|---|
| documents total | 561 | 821 |
| wikivoyage | 464 | 464 (fingerprint 66c2f19e… unchanged) |
| osm | 97 (old format) | 357 (one per verified place) |
| document_quarantine | 67 | 164 (+97 superseded old OSM docs) |
| NULL embeddings | 0 | 0 |
| duplicate content hashes | 0 | 0 |
| unsourced OSM documents | n/a | 0 |

Places: 480 total (357 verified with `place_sources.source_name='osm'`, 123 unsourced, hidden by default). Only verified places are ingested.

## Reproducibility

- Command: `cd apps/ai-service; python -m app.rag.ingest_osm --out <json>`
- Input: `places` JOIN `place_sources` (source_name='osm'); facts copied verbatim from OSM tags, missing attributes omitted.
- Model: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim). CLI aborts if the real embedder is unavailable (no silent Mock fallback).
- Upsert key: (content_hash, embedding_model). Stale OSM docs are copied to `document_quarantine` (reason `osm_document_superseded_by_task_07_5_regeneration`) then deleted.
- Idempotency: run 2 removed 0 docs, totals unchanged (821 / 164).
- Evidence: `docs/audit/evidence/rag-db-before.txt`, `rag-eval-before.json`, `rag-eval-after.json`, `rag-ingest-run1.json`, `rag-ingest-run2.json`, `rag-live-chat.json`.

## Retrieval evaluation (frozen queries, unchanged)

BEFORE and AFTER are identical: RAG-EVAL-01 rank 2, 02 rank 2, 03 rank 4, 04 NOT found in top 5 (pre-existing gap, taxi safety). Top-5 is all Wikivoyage in both.

Grounding probes (new): "Địa điểm nào thuộc Văn hóa ở Hà Nội?" returns an OSM culture doc at rank 4 in the top 8. "Giờ mở cửa của Bảo tàng Hồ Chí Minh là gì?" returns the matching OSM docs at ranks 1–3 (53 OSM docs have opening hours).

## Chat wiring finding

The live `/chat` endpoint had NO RAG; `TravelAgent.handle_chat` (which uses RAG) is dead code. Minimal change in `app/routers/chat.py`: `retrieve_grounding` (top_k=4, never raises), `build_grounded_message`, and `ChatResponse.sources`. Gemini provider untouched.

Live check via NestJS `POST /ai/chat`: `sources` returned the 2 Wikivoyage URLs and 1 OSM URL. The Gemini call returned HTTP 429 (RESOURCE_EXHAUSTED) on 3 attempts, so reply quality with grounding is NOT verified live. No hallucination-improvement claim is made.

## Tests

Backend jest 58 passed; `nest build` exit 0; lint 0 errors / 44 warnings; AI pytest 75 passed + 1 skipped; Flutter 62 passed; `flutter analyze` clean.

## Limitations

- Live grounded reply unverified (Gemini quota 429).
- The system prompt (unchanged) asks for VND prices and opening hours, which conflicts with strict grounding.
- Frozen query RAG-EVAL-04 gap remains.
- One chunk per place.
- 123 unsourced places remain in the DB (hidden by default).
- `sources` not yet shown in the Flutter UI.
