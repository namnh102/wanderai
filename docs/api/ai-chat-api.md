# AI Chat API Contract

## Overview

Mobile and web clients interact with **Wandy** exclusively through the public NestJS gateway (`POST /ai/chat`, `DELETE /ai/chat/:sessionId`). NestJS authenticates the user via `JwtAuthGuard` and forwards requests to the internal FastAPI AI service (`POST /chat`, `DELETE /chat/{session_id}`) with a short-lived HMAC-SHA256 internal assertion header (`X-WanderAI-Internal-Assertion`). FastAPI `:8000` is an internal-only service and must never be called directly by mobile clients. For end-to-end architecture, session lifecycle, and UI behavior, see [AI Chat Architecture & Integration](../ai/ai-chat.md).

```text
Flutter Mobile (API_BASE_URL)
      |
      | HTTP POST /ai/chat | DELETE /ai/chat/:sessionId
      | Header: Authorization: Bearer <access_token>
      v
NestJS Backend (port 3000 — AiProxyController -> AiChatProxyService)
      |
      | HTTP POST /chat | DELETE /chat/{session_id}
      | Header: X-WanderAI-Internal-Assertion: v1.<payload_b64url>.<sig_b64url>
      v
FastAPI AI Service (internal port 8000 — routers/chat.py)
      |
      +-- RAGService.retrieve_with_status (governed pgvector retrieval: ok | empty | error)
      |
      +-- GeminiProvider (gemini-3.5-flash; tools: get_weather, search_places, calculate_budget)
```

---

## Internal Service Assertion Contract (NestJS → FastAPI)

FastAPI chat endpoints require `X-WanderAI-Internal-Assertion` signed with `AI_INTERNAL_AUTH_SECRET` (`>= 32` chars, `>= 8` unique chars, distinct from `JWT_SECRET` and `JWT_REFRESH_SECRET`):
- **Token format:** `v1.<base64url(canonical_sorted_json)>.<base64url(hmac_sha256)>`
- **Claims:** `iss` (`"wanderai-backend"`), `aud` (`"wanderai-ai-service"`), `sub` (authenticated `user.id`), `act` (`"POST:/chat"` or `"DELETE:/chat/<urlEncodedSessionId>"`), `sid` (trimmed `session_id` or `""`), `iat`, `exp` (`60s` default TTL, `120s` max, `15s` clock skew tolerance).
- **Fail-closed behavior:** Missing/weak `AI_INTERNAL_AUTH_SECRET` on NestJS or FastAPI returns `503`; missing/invalid/expired header on FastAPI returns `401`; mismatched `user_id` or `session_id` between assertion and request body/path returns `403`.

---

## Public Gateway Endpoints

### 1. `POST /ai/chat`

#### Authentication
- **Type:** Bearer JWT (`JwtAuthGuard`)
- **Header:** `Authorization: Bearer <access_token>`
- **Unauthenticated / inactive user response:** `HTTP 401 Unauthorized`

#### Request Body (`application/json`)

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `message` | string | Yes | Non-empty user prompt (`@IsNotEmpty()` in `ChatDto` + non-whitespace check in FastAPI) | `"Gợi ý điểm du lịch Đà Nẵng 3 ngày 2 đêm"` |
| `session_id` | string | No | Session identifier for per-user multi-turn in-memory history (minted as UUID if omitted) | `"ef94af53-3d73-4dc8-b9dc-101f95dd90af"` |

#### Success Response (`HTTP 200 OK`)

All successful NestJS responses are wrapped by `TransformInterceptor`:

```json
{
  "success": true,
  "data": {
    "reply": "Dưới đây là một số địa điểm tại Đà Nẵng dựa trên kho dữ liệu hiện có...",
    "session_id": "ef94af53-3d73-4dc8-b9dc-101f95dd90af",
    "tools_used": [
      "search_places",
      "get_weather"
    ],
    "tool_calls": [
      {
        "tool": "search_places",
        "args": { "destination": "Đà Nẵng", "category": "attraction" },
        "result": { "...": "..." }
      }
    ],
    "sources": [
      "https://www.openstreetmap.org/way/37933256",
      "https://en.wikivoyage.org/wiki/Da_Nang"
    ],
    "retrieval_status": "ok"
  },
  "timestamp": "2026-11-11T07:00:00.000Z"
}
```

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Always `true` on `2xx` responses |
| `data.reply` | string | Markdown-formatted reply from Wandy |
| `data.session_id` | string | Active per-user session ID (preserved or newly generated UUID) |
| `data.tools_used` | string[] | Deduplicated production tool names invoked (`get_weather`, `search_places`, `calculate_budget` — `search_hotels` is excluded from production) |
| `data.tool_calls` | object[] | Execution log of tool invocations (sanitized against `synthetic=true` / `verified=false` payloads) |
| `data.sources` | string[] | Deduplicated `https://` candidate source URLs from governed RAG chunks (`[]` when `retrieval_status` is `"empty"`). **Note:** These are retrieved corpus candidate URLs, **not** claim-level verified citations; UI displays `"Nguồn dữ liệu truy xuất (chưa đối chiếu từng chi tiết trả lời):"` and W07 gate `G5` remains `HOLD`. |
| `data.retrieval_status` | `"ok" \| "empty"` | Grounding retrieval outcome on `200 OK` (`"error"` never returns `200` — it fails closed with HTTP `503` before invoking Gemini) |
| `timestamp` | string | ISO-8601 UTC timestamp |

---

### 2. `DELETE /ai/chat/:sessionId`

Deletes the authenticated user's in-memory conversation session and invalidates any concurrent in-flight `POST /ai/chat` turn from re-persisting stale history.

#### Authentication & Path Parameters
- **Header:** `Authorization: Bearer <access_token>` (required)
- **Path parameter `sessionId`:** Non-empty session identifier owned by the authenticated user (idempotent `200 OK` if session does not exist or already expired; `403` if owned by another user).

#### Success Response (`HTTP 200 OK`)

```json
{
  "success": true,
  "data": {
    "message": "Chat history cleared"
  },
  "timestamp": "2026-11-11T07:01:00.000Z"
}
```

---

## Error Responses

Error responses are normalized by NestJS `HttpExceptionFilter`:

### `400 Bad Request` (Empty/whitespace `message` or blank `sessionId`)
```json
{
  "success": false,
  "statusCode": 400,
  "message": "message should not be empty",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```

### `401 Unauthorized` (Missing, invalid, or expired JWT)
```json
{
  "success": false,
  "statusCode": 401,
  "message": "Unauthorized",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```

### `403 Forbidden` (Cross-user `session_id` access/deletion or principal binding mismatch)
```json
{
  "success": false,
  "statusCode": 403,
  "message": "Không có quyền truy cập phiên trò chuyện này.",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```

### `429 Too Many Requests` (Upstream LLM quota / rate limit)
```json
{
  "success": false,
  "statusCode": 429,
  "message": "Hệ thống AI đang quá tải yêu cầu. Vui lòng thử lại sau ít phút.",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```

### `502 Bad Gateway` (Upstream Gemini provider failure / empty output)
```json
{
  "success": false,
  "statusCode": 502,
  "message": "Dịch vụ AI tạm thời không thể tạo phản hồi. Vui lòng thử lại sau.",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```

### `503 Service Unavailable` (Fail-closed RAG error, missing `AI_INTERNAL_AUTH_SECRET` / `GEMINI_API_KEY`, or FastAPI unreachable/timeout)
```json
{
  "success": false,
  "statusCode": 503,
  "message": "Kho dữ liệu tri thức du lịch tạm thời không khả dụng. Vui lòng thử lại sau.",
  "timestamp": "2026-11-11T07:02:00.000Z",
  "path": "/ai/chat"
}
```
*(Other `503` messages depending on failure source: `"Dịch vụ AI chưa được cấu hình khóa xác thực nội bộ."`, `"Dịch vụ AI hiện chưa sẵn sàng. Vui lòng thử lại sau."`, or `"AI Service không phản hồi. Vui lòng thử lại."`.)*

---

## Timeouts & Streaming

- **Client → NestJS (`POST /ai/chat`):** `35,000 ms` (`sendTimeout` & `receiveTimeout`)
- **NestJS → FastAPI (`POST /chat`):** `30,000 ms`
- **Client → NestJS & NestJS → FastAPI (`DELETE /ai/chat/:sessionId`):** `10,000 ms`
- **Streaming:** Currently **NOT supported**; buffered JSON responses are returned.

## Example Usage (cURL)

```bash
# Send a chat turn
curl -X POST http://localhost:3000/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{"message": "Xin chào, gợi ý điểm tham quan ở Đà Nẵng", "session_id": "ef94af53-3d73-4dc8-b9dc-101f95dd90af"}'

# Clear the current user's chat session
curl -X DELETE http://localhost:3000/ai/chat/ef94af53-3d73-4dc8-b9dc-101f95dd90af \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
