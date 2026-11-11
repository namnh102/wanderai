# AI Chat Architecture & Integration

## Overview

The AI Chat system connects the Flutter mobile client to **Wandy** (AI Travel Copilot) exclusively through the authenticated NestJS API gateway (`API_BASE_URL`), which signs short-lived HMAC-SHA256 internal assertions to the internal Python FastAPI service running fail-closed `pgvector` RAG retrieval and Gemini function calling. For HTTP request/response schemas and status codes, see [AI Chat API Contract](../api/ai-chat-api.md).

## Architecture

```text
Flutter Mobile (Client — apps/mobile)
  │
  ├─ AiChatScreen (Presentation)
  │     ├─ Renders messages & retry actions
  │     ├─ Shows candidate-source disclaimer only when retrieval_status == "ok"
  │     └─ Shows ungrounded notice when retrieval_status == "empty"
  │
  ├─ ChatNotifier (State Management — Riverpod)
  │     ├─ Optimistically renders user bubble & tracks active sessionId
  │     ├─ Guards against stale responses via monotonic _sessionEpoch
  │     ├─ Clears session locally & calls DELETE /ai/chat/:sessionId on clear
  │     └─ Handles 401 -> logout(), 403 -> reset sessionId, 429/502/503 -> retryable error
  │
  ├─ ChatRepository (Data Access — Dio bound to AppConstants.apiBaseUrl)
  │     ├─ POST /ai/chat (35s send/receive timeout)
  │     └─ DELETE /ai/chat/:sessionId (10s send/receive timeout)
  │
  ▼  HTTP POST /ai/chat | DELETE /ai/chat/:sessionId (Authorization: Bearer <access_token>)
NestJS Backend (Port 3000 — apps/backend)
  │
  ├─ JwtAuthGuard & CurrentUser (verifies active JWT user)
  ├─ ChatDto (class-validator validation)
  ├─ AiProxyController -> AiChatProxyService (src/modules/ai-proxy/internal-auth.ts)
  │     ├─ Mints X-WanderAI-Internal-Assertion: v1.<payload_b64url>.<hmac_sha256_b64url>
  │     │    (iss="wanderai-backend", aud="wanderai-ai-service", sub=user.id,
  │     │     act="POST:/chat" | "DELETE:/chat/<encodedSid>", sid=sessionId, 60s TTL)
  │     └─ Axios forward (30s timeout for POST /chat, 10s timeout for DELETE /chat/:sid)
  │
  ▼  Internal HTTP POST /chat | DELETE /chat/{session_id} (X-WanderAI-Internal-Assertion)
FastAPI AI Service (Internal Port 8000 — apps/ai-service)
  │
  ├─ security/internal_auth.py (require_internal_principal)
  │     └─ Verifies HMAC signature, TTL/skew (15s), action, user_id & session_id binding
  ├─ routers/chat.py + services/rag.py (RAGService.retrieve_with_status)
  │     └─ Governed SQL filter (GOVERNED_PRODUCTION_DOCUMENT_SQL); tri-state: ok | empty | error
  └─ services/chat_llm.py (GeminiProvider wrapping gemini-3.5-flash)
        ├─ Production tools ONLY: get_weather, search_places, calculate_budget
        ├─ Sanitizes synthetic/unverified tool payloads (_sanitize_tool_result_for_llm)
        └─ Per-user bounded in-memory sessions + monotonic generation tokens
```

## Request, Grounding & Session Lifecycle

### 1. Gateway Authentication & Internal HMAC Assertion
1. **Mobile gateway call:** Flutter sends `POST {API_BASE_URL}/ai/chat` with `Authorization: Bearer <access_token>` and `{message, session_id}` (never calling FastAPI `:8000` directly).
2. **JWT verification:** NestJS `JwtAuthGuard` authenticates the active user (`401` on missing/expired token or soft-deleted user).
3. **Signed internal assertion:** `AiChatProxyService` signs header `X-WanderAI-Internal-Assertion` (`v1.<base64url(canonical_json)>.<base64url(hmac_sha256)>`) using `AI_INTERNAL_AUTH_SECRET` (`>= 32` chars, `>= 8` unique chars, distinct from `JWT_SECRET` and `JWT_REFRESH_SECRET`; fails closed with `503` if misconfigured).
4. **FastAPI principal & session binding:** `require_internal_principal` verifies the HMAC signature, `iss`/`aud`, `exp`/`iat` (`60s` default TTL, `120s` max, `15s` clock skew), and exact `act`. `chat.py` rejects mismatched `body.user_id` or `session_id` with `403`.

### 2. Fail-Closed Tri-State RAG Grounding (`retrieval_status`)
`RAGService.retrieve_with_status(query, top_k=4)` queries PostgreSQL `documents` restricted by `GOVERNED_PRODUCTION_DOCUMENT_SQL` (requiring governed sources, `user_citable = TRUE`, and excluding `ci_fixture`, synthetic, or disallowed commercial rows):
- **`retrieval_status = "error"` (Fail-Closed `503`):** If `DATABASE_URL` is missing or embedding/PostgreSQL retrieval fails, FastAPI aborts **before** calling Gemini and returns HTTP `503` (`"Kho dữ liệu tri thức du lịch tạm thời không khả dụng. Vui lòng thử lại sau."`).
- **`retrieval_status = "empty"`:** If PostgreSQL is healthy but zero governed chunks match, FastAPI injects `NO_CONTEXT_INSTRUCTION` (forbidding fabricated addresses, opening hours, prices, phone numbers, or ratings), runs Gemini, and returns `sources: []` with `retrieval_status: "empty"`.
- **`retrieval_status = "ok"`:** Injects numbered governed context chunks (`[1]..[n]`) + grounding rules and returns deduplicated `https://` `source_url` candidates in `sources` with `retrieval_status: "ok"`.

### 3. Production Toolset & Synthetic Output Guard
- Active production `_TOOLS` in `apps/ai-service/app/routers/chat.py` contains **only** three tools:
  1. `get_weather` (`WeatherTool`)
  2. `search_places` (`SearchPlacesTool`)
  3. `calculate_budget` (`BudgetTool`)
- `search_hotels` (`SearchHotelsTool`) is **excluded** from production `_TOOLS` because no verified live hotel inventory is connected.
- `_sanitize_tool_result_for_llm` intercepts tool outputs marked `synthetic=True` or `verified=False` so synthetic fallback records cannot reach Gemini as factual data.
- Missing/placeholder `GEMINI_API_KEY` or upstream Gemini failures fail closed (`503` unavailable, `429` rate limit, `502` upstream error) instead of returning mock text.

### 4. Candidate Source UI Disclaimer & Scientific Factuality Boundary
- When `retrieval_status == "ok"` and `sources` is non-empty, `AiChatScreen` renders `https://` source chips under the explicit disclaimer:
  > `"Nguồn dữ liệu truy xuất (chưa đối chiếu từng chi tiết trả lời):"`
- When `retrieval_status == "empty"`, `AiChatScreen` displays:
  > `"Chưa có nguồn đối chiếu trực tiếp trong kho dữ liệu."`
- **Important boundary:** `sources` are **retrieved corpus candidate URLs** from the RAG step, **not** claim-level verified citations for every sentence in `reply`. Scientific factuality and claim-attribution verification (`W07` gate `G5`) remain `HOLD` under W07 Scientific Protocol v1.0. Android 15 emulator smoke verified AI Chat transport/UI using an offline-stubbed LLM client (zero paid API calls) and is **not** a W07 scientific factuality `PASS`.

### 5. Per-User Session Isolation & Concurrent `DELETE` Safety
- `GeminiProvider` in `apps/ai-service/app/services/chat_llm.py` binds each `session_id` to `owner_user_id = principal.user_id`. Cross-user access or deletion raises `SessionOwnershipError` → HTTP `403`.
- Clearing chat history calls `DELETE /ai/chat/:sessionId` → `DELETE /chat/{session_id}`, removing server history and incrementing `_sessionEpoch` on mobile.
- Every session turn snapshots a monotonic, non-reusable lifecycle `generation` token (`_allocate_generation_locked`). If an in-flight `POST /chat` races with `DELETE`, TTL expiry, or capacity eviction (including same-`session_id` ABA recreation), `_commit_turn` detects the missing/changed generation under lock and skips persistence (`persisted=False`), returning the response without resurrecting deleted history.

## Timeout & Error Handling

| Scenario | Layer | Resulting Mobile Behavior / User Message |
|---|---|---|
| Client request exceeds `35s` (`POST`) / `10s` (`DELETE`) | Flutter Dio (`ChatNotifier`) | `AI phan hoi qua lau. Vui long thu lai.` |
| Network unreachable / DNS / socket error | Flutter Dio (`ChatNotifier`) | `Khong the ket noi may chu. Vui long kiem tra mang.` |
| Missing/expired JWT (`401`) | NestJS `JwtAuthGuard` + `ChatNotifier` | Calls `authProvider.notifier.logout()`, increments `_sessionEpoch`, clears `sessionId`, shows `Phien dang nhap het han. Vui long dang nhap lai.`, redirects to `/login` |
| Cross-user session or mismatched assertion (`403`) | FastAPI `chat.py` / `chat_llm.py` + `ChatNotifier` | Resets `sessionId` so next retry starts a fresh session; shows `Phien tro chuyen khong hop le hoac da het quyen truy cap. Vui long thu lai.` |
| Empty/invalid message or blank `sessionId` (`400`) | Flutter UI, NestJS `ChatDto`, FastAPI | Rejected locally; `Tin nhan khong hop le.` if `400` returned |
| Gemini quota / rate limit (`429`) | FastAPI `LLMRateLimitError` → NestJS → Flutter | `He thong AI dang qua tai yeu cau (429). Vui long doi mot lat roi thu lai.` |
| Upstream LLM error (`502`) or RAG/LLM/Auth-config/Timeout unavailable (`503`) | FastAPI / NestJS `AiChatProxyService` → Flutter | `Dich vu AI dang ban hoac qua tai. Vui long thu lai sau.` (retryable via `retryLastMessage`) |

## Conversation Memory & Limitations

- **Bounded In-Memory Session Store (`SESSION_STORAGE_LIMITATION = "in_memory_ephemeral_per_instance"`):** Sessions live in FastAPI process memory bounded by `MAX_ACTIVE_SESSIONS = 500`, `DEFAULT_SESSION_TTL_SECONDS = 3600` (1 hour), and `MAX_HISTORY_ITEMS = 40` (`20` user/model turns). Restarting FastAPI or scaling across multiple workers clears/does not share in-memory history.
- **No Persistent PostgreSQL Chat History Yet:** Turns are intentionally not persisted to PostgreSQL chat tables in the current runtime slice.
- **Buffered Responses Only:** Streaming (SSE/WebSocket) is not currently enabled on `/ai/chat` or `/chat`.
