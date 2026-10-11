# TASK 07.5 — RAG Re-ingestion & Verified Place Knowledge Grounding

Branch: `feat/rag-verified-place-ingestion`

## A. Verified deterministic RAG

| Metric | Before | After |
|---|---|---|
| documents total | 561 | 821 |
| wikivoyage | 464 | 464 (fingerprint 66c2f19e… unchanged) |
| osm | 97 (old format) | 357 (one per verified place) |
| document_quarantine | 67 | 164 (+97 superseded old OSM documents) |
| NULL embeddings | 0 | 0 |
| duplicate content hashes | 0 | 0 |
| unsourced OSM documents | n/a | 0 |

Places: 480 total (357 verified with `place_sources.source_name='osm'`, 123 unsourced, hidden by default). Only verified places are ingested; 357/357 covered.

Reproducibility:
- Command: `cd apps/ai-service; python -m app.rag.ingest_osm --out <json>`
- Input: `places` JOIN `place_sources` (source_name='osm'); facts copied verbatim from OSM tags, missing attributes omitted.
- Model: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim). The CLI aborts if the real embedder is unavailable (no silent Mock fallback).
- Upsert key: (content_hash, embedding_model). Stale OSM documents go to `document_quarantine` (reason `osm_document_superseded_by_task_07_5_regeneration`) before deletion.
- Idempotency: run 2 removed 0 documents; totals unchanged (821 / 164).
- Evidence: `docs/audit/evidence/rag-db-before.txt`, `rag-eval-before.json`, `rag-eval-after.json`, `rag-ingest-run1.json`, `rag-ingest-run2.json`.

Retrieval (no LLM):
- Frozen queries RAG-EVAL-01..04 unchanged and identical before/after: 01 rank 2, 02 rank 2, 03 rank 4, 04 not in top 5 (pre-existing gap).
- "Địa điểm văn hóa ở Hà Nội" and "Giờ mở cửa Bảo tàng Hồ Chí Minh": returned documents are only `osm`/`wikivoyage`, each with a source URL; each OSM document maps to a real `place_sources` row (`https://www.openstreetmap.org/{source_id}`, ODbL 1.0); no synthetic/mock/unsourced document appears (`tests/test_grounding_contract.py`, `tests/test_rag_osm_ingestion.py`).

## B. Mock-grounding tests (NOT live Gemini)

Change set of commit `3150001` + follow-up:
- **Ingestion/retrieval (A):** `app/rag/{osm_documents,ingest_osm,evaluate,ingestion,retriever,chunker}.py`, `tests/test_rag_osm_ingestion.py`.
- **Chat grounding (B):** `app/routers/chat.py` (retrieved context + `sources`), `app/prompts/system_prompt.py` (grounding contract), `tests/test_chat_rag.py`, `tests/test_grounding_contract.py`, `tests/test_chat_live.py` (opt-in).

Grounding contract: Wandy may state place facts only if present in retrieved context or tool results; never invent; exact fallbacks "Chưa có thông tin giá trong dữ liệu hiện có.", "Chưa có thông tin giờ mở cửa trong dữ liệu hiện có.", "Chưa có đánh giá."; the old rules forcing VND prices and opening hours in every answer and the priced example were removed; budget numbers only from `calculate_budget`.

Mock-provider tests verify the exact message handed to the provider: contains retrieved context + user question + "không bịa" instruction (context before question); with no context it carries the no-invention instruction; a context lacking hours/price is passed through unpadded; the context fed to the provider never contains synthetic/mock documents.

## C. Live Gemini status — NOT VERIFIED

- Live check via NestJS `POST /ai/chat`: `sources` correctly returned (2 Wikivoyage URLs + 1 OSM URL `way/37933256`).
- The Gemini call returned HTTP 429 (RESOURCE_EXHAUSTED, mapped by the provider to "AI dang ban") on 3 attempts: 2026-10-04 02:39, 02:42, 02:43 (+07). Quota/provider issue, not a code error. No further retries were made.
- Opt-in test `tests/test_chat_live.py` (`CHAT_LIVE_TEST=1`, needs `GEMINI_API_KEY`) is skipped by default and FAILS on a quota fallback; it was not made to pass artificially.
- No claim is made about reduced hallucination; this task has no quantitative LLM evaluation.

## `sources` API contract (Flutter follow-up)

`POST /chat` and NestJS `POST /ai/chat` return `data.sources: string[]` — source URLs of retrieved documents (OSM node/way URLs, Wikivoyage page URLs), `[]` when nothing was retrieved. The Flutter chat model does not read `sources` yet; **follow-up task:** parse `sources` in `chat_model.dart` and show them as source chips with ODbL/CC BY-SA attribution. Out of scope here.

## Tests

Backend jest 58 passed; `nest build` exit 0; lint 0 errors / 44 warnings; AI pytest 87 passed + 2 skipped (both opt-in live tests); Flutter 62 passed; `flutter analyze` clean.

## Remaining limitations

- Live grounded Gemini reply unverified (quota).
- Flutter does not display `sources`.
- RAG-EVAL-04 (taxi safety) gap unchanged; one chunk per place; 123 unsourced places remain in the DB (hidden by default).
- `search_places` tool and planner are not grounded by RAG (unchanged).
