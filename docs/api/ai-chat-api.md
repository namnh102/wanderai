# AI Chat API Contract

## Overview

The AI Chat feature connects the mobile client to the AI assistant (**Wandy**) through the NestJS API gateway, which proxies requests to the Python FastAPI AI service.

```
Flutter Mobile
      |
      | HTTP POST /ai/chat (Authorization: Bearer <token>)
      v
NestJS Backend (port 3000)
      |
      | HTTP POST /chat
      v
FastAPI AI Service (port 8000)
      |
      | google-genai SDK
      v
Gemini 3.5 Flash LLM (with Function Calling tools)
```

## Endpoint Specification

### `POST /ai/chat`

#### Authentication
- **Type**: Bearer JWT
- **Header**: `Authorization: Bearer <access_token>`
- **Required**: Yes (protected by `JwtAuthGuard`)
- **Unauthenticated response**: HTTP 401 Unauthorized

#### Request Body (`application/json`)

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `message` | string | Yes | Non-empty user prompt or question | `"Gợi ý điểm du lịch Đà Nẵng 3 ngày 2 đêm"` |
| `session_id` | string | No | UUID session identifier for multi-turn conversation memory | `"ef94af53-3d73-4dc8-b9dc-101f95dd90af"` |

#### Success Response (`HTTP 200 OK`)

All NestJS successful responses are wrapped by `TransformInterceptor`:

```json
{
  "success": true,
  "data": {
    "reply": "Xin chào! Mình là Wandy, AI Copilot du lịch chuyên nghiệp của WanderAI...",
    "session_id": "ef94af53-3d73-4dc8-b9dc-101f95dd90af",
    "tools_used": [
      "search_places",
      "get_weather"
    ],
    "tool_calls": [
      {
        "tool": "search_places",
        "args": { "destination": "Đà Nẵng", "category": "attraction" },
        "result": { ... }
      }
    ],
    "sources": [
      "https://www.openstreetmap.org/way/37933256",
      "https://en.wikivoyage.org/wiki/Hanoi"
    ]
  },
  "timestamp": "2026-10-01T08:17:01.291Z"
}
```

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Always `true` on successful execution |
| `data.reply` | string | The markdown-formatted response message from Wandy |
| `data.session_id` | string | The active session ID (preserved or newly generated) |
| `data.tools_used` | string[] | Array of tool names invoked during generation |
| `data.tool_calls` | object[] | Detailed execution log of tool invocations |
| `data.sources` | string[] | Public canonical source URLs (OpenStreetMap, Wikivoyage) that grounded the retrieved context; empty array `[]` if no documents retrieved |
| `timestamp` | string | ISO-8601 UTC timestamp of response |

#### Error Responses

Error responses are formatted by `HttpExceptionFilter`:

##### 1. 401 Unauthorized (Missing or expired JWT)
```json
{
  "success": false,
  "statusCode": 401,
  "message": "Unauthorized",
  "timestamp": "2026-10-01T08:20:00.000Z",
  "path": "/ai/chat"
}
```

##### 2. 400 Bad Request (Validation failure - e.g., empty message)
```json
{
  "success": false,
  "statusCode": 400,
  "message": "message should not be empty",
  "timestamp": "2026-10-01T08:20:00.000Z",
  "path": "/ai/chat"
}
```

##### 3. 503 Service Unavailable (FastAPI down or timeout)
```json
{
  "success": false,
  "statusCode": 503,
  "message": "AI Service không phản hồi. Vui lòng thử lại.",
  "timestamp": "2026-10-01T08:20:00.000Z",
  "path": "/ai/chat"
}
```

## Timeouts & Streaming

- **NestJS -> FastAPI Timeout**: 30,000 ms (30 seconds)
- **Client -> NestJS Timeout**: 35,000 ms (35 seconds)
- **Streaming**: Currently **NOT supported** by the NestJS proxy and FastAPI chat router. Normal buffered response is used.

## Example Usage

### cURL
```bash
curl -X POST http://localhost:3000/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"message": "Xin chào", "session_id": "optional-uuid"}'
```
