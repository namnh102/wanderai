# TASK 07.5.1 — Live Wandy Grounding Verification & Source UI Audit Report

**Branch:** `feat/wandy-grounding-source-ui`  
**Date:** 2026-10-04  
**Audit Status:** Complete  

---

## 1. Objective & Scope

TASK 07.5.1 follows the successful merge of TASK 07.5 (`1a2bbf2`), focusing on:
1. End-to-end propagation of grounding sources from RAG knowledge retriever to the Flutter client.
2. Flutter Chat Model and presentation UI: parsing `sources` and rendering a compact, visually secondary "Nguồn tham khảo:" section with interactive chips.
3. Controlled live Gemini grounding verification via opt-in test (`test_chat_live.py`).
4. Comprehensive regression across Backend (Jest), AI Service (pytest), and Flutter Mobile.
5. End-to-end browser verification on Flutter Web with screenshot evidence.

**Out of Scope:**
- No redesign of the full application or chat screen.
- No recommendation algorithms (Collaborative Filtering, Hybrid RecSys).
- No buddy matching, booking, or review AI.

---

## 2. End-to-End Runtime Path & Architecture

The verified runtime path for grounded AI responses and citations:

```
[Flutter Mobile (Web/App)]
       │
       │ HTTP POST /ai/chat (Bearer JWT)
       ▼
[NestJS Backend Gateway (:3000)]
       │
       │ AiProxyService forwards payload
       ▼
[FastAPI AI Service (:8000)]
       │
       ├─► retrieve_grounding(message)
       │     └─► RAGService.search_with_sources(message, top_k=4)
       │           └─► pgvector Cosine Search (min_similarity=0.35)
       │                 └─► Returns: context_str & distinct source URLs
       │
       ├─► build_grounded_message(message, context)
       │     └─► Prepends factual context + strict no-hallucination instruction
       │
       ├─► Gemini 3.5 Flash Provider (with function calling tools)
       │     └─► Governed by grounded system prompt (app/prompts/system_prompt.py)
       │
       ▼ Returns ChatResponse(reply, session_id, tools_used, tool_calls, sources)
[NestJS TransformInterceptor]
       │
       ▼ Wraps into { success: true, data: { reply, session_id, tools_used, sources }, timestamp }
[Flutter ChatRepository & ChatNotifier]
       │
       ▼ Parses ChatResponse.sources -> ChatMessage.sources
[AiChatScreen Message Bubble]
       └─► Renders assistant bubble + compact "Nguồn tham khảo:" chip section
```

---

## 3. API Contract

The unified API contract is preserved and stabilized across all layers:

### `POST /ai/chat` (NestJS) / `POST /chat` (FastAPI)
```json
{
  "success": true,
  "data": {
    "reply": "Hà Nội có Bảo tàng Lịch sử Quốc gia và nhiều di tích cổ kính...",
    "session_id": "test-session-sources-1",
    "tools_used": ["search_places"],
    "tool_calls": [],
    "sources": [
      "https://en.wikivoyage.org/wiki/Hanoi",
      "https://en.wikivoyage.org/wiki/Vietnam",
      "https://www.openstreetmap.org/way/37933256"
    ]
  },
  "timestamp": "2026-10-04T03:11:15.000Z"
}
```

- `data.sources`: `string[]` — array of canonical public URLs (`https://www.openstreetmap.org/...` or `https://en.wikivoyage.org/...`).
- When no grounding documents are retrieved (or for greetings without travel context), `data.sources` defaults to empty array `[]`.

---

## 4. Flutter Source UI & Grounding UX

Implemented in `apps/mobile/lib/features/ai_chat/presentation/ai_chat_screen.dart`:
- **Placement:** Located directly inside assistant message bubbles below the primary text, visually secondary with a subtle divider and book icon.
- **Labels:** Derived safely from URL metadata:
  - OpenStreetMap: `OpenStreetMap (way/37933256)` or `OpenStreetMap (node/...)`
  - Wikivoyage: `Wikivoyage: Hanoi`, `Wikivoyage: Vietnam`
  - Generic / Fallback: Hostname or `Nguon tham khao`
- **Interactivity:** Chips are styled with rounded borders, hover highlight, and launch the external link via `url_launcher` without crashing. Full URLs are available on hover via `Tooltip`.
- **Overflow Protection:** Labels are wrapped in `ConstrainedBox(maxWidth: 220)` with `TextOverflow.ellipsis`, and wrapped inside `Wrap(spacing: 6, runSpacing: 6)`.
- **Invariants:**
  - Hidden completely when `sources` is empty.
  - Hidden completely for user messages.
  - Backward compatible with historical payloads missing `sources`.

---

## 5. Live Gemini Verification Status

- **Status:** **`PENDING`**
- **Reason:** The Gemini provider returned `HTTP 429 RESOURCE_EXHAUSTED` (mapped by provider to fallback: *"Hien tai AI dang ban, ban doi 1 phut roi thu lai nhe!"*).
- **Controlled Test Run:**
  ```bash
  CHAT_LIVE_TEST=1 pytest tests/test_chat_live.py -v -s
  ```
  Result: Failed with `AssertionError: Gemini unavailable/quota: Hien tai AI dang ban, ban doi 1 phut roi thu lai nhe!`.
- **Policy Enforcement:** In accordance with project integrity rules, live test failures are **NOT** hidden or fabricated. Success will only be declared when a live Gemini response is genuinely received with quota available.

---

## 6. Automated Test Results

### Backend (Jest E2E)
- **Suite Count:** 9 passed, 9 total (added `test/ai-chat.e2e-spec.ts`)
- **Tests Count:** 62 passed, 62 total
  - `auth`: 4 passed
  - `destinations`: 5 passed
  - `places`: 8 passed
  - `trips`: 10 passed
  - `planner`: 9 passed
  - `verified-serving`: 8 passed
  - `provenance`: 12 passed
  - `health`: 2 passed
  - `ai-chat` (new): 4 passed (unauthenticated 401, empty message 400, sources preservation, empty sources preservation)
- **Build & Lint:** `nest build` exit 0; `eslint` 0 errors, 44 baseline warnings.

### AI Service (pytest)
- **Tests Count:** 87 passed, 2 skipped (opt-in live tests: `test_chat_live.py`, `test_planner_live.py`)
- **Coverage:** RAG ingestion, deterministic retrieval, grounding contracts, mock-grounding, tool execution.

### Mobile App (Flutter Test & Analyze)
- **Tests Count:** 70 passed, 70 total (added `test/chat_sources_test.dart`)
  - 4 model tests: parsing, empty sources, null/legacy sources backward compatibility, `ChatMessage.copyWith`.
  - 4 widget tests: assistant source section & chip rendering, hidden when empty, long URL overflow safety, chip tap handling.
- **Analyze:** `flutter analyze` clean (`No issues found!`).

---

## 7. Browser Verification Evidence

Conducted on Flutter Web at `http://127.0.0.1:5000`:
- **Account Created:** `browsertest_sources@wanderai.test`
- **Steps Verified:**
  1. Login & navigation to Home screen (`PASS`).
  2. Navigation to AI Agent tab (`PASS`, screenshot: `docs/audit/evidence/chat_empty.png`).
  3. Query submission: *"Tôi muốn biết thông tin về các địa điểm văn hóa ở Hà Nội."* (`PASS`).
  4. Rendering of assistant message with secondary "Nguồn tham khảo:" section and chips: `Wikivoyage: Hanoi`, `Wikivoyage: Vietnam`, `OpenStreetMap (way/37933256)` (`PASS`, screenshot: `docs/audit/evidence/chat_with_sources.png`).
  5. Clicking source chip opens URL in external tab with zero UI errors or freezes (`PASS`, screenshot: `docs/audit/evidence/chat_chip_clicked.png`).
  6. Browser console: No exceptions or layout warnings (`PASS`).

---

## 8. Security & Data Integrity Audit

- **No Secrets Exposed:** No API keys or internal environment variables leaked to Flutter client.
- **Public Citations Only:** Sources consist strictly of canonical OpenStreetMap and Wikivoyage URLs.
- **JWT Protection:** NestJS `/ai/chat` requires valid Bearer token; unauthorized calls return 401.

---

## 9. Remaining Limitations & Next Task

- **Limitations:** Live Gemini chat grounding response content unverified due to API quota (PENDING).
- **Exact Next Task:**
  - **TASK 07.6 — Place Detail Serving & Verified Data Presentation:**
    - Implement `GET /places/:id` authoritative place detail endpoint returning verified place metadata (OSM tags, address, opening hours, contact, coordinates, provenance).
    - Provide Flutter Place Detail screen displaying verified badges and ODbL attribution.
