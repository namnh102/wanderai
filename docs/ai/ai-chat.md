# AI Chat Architecture & Integration

## Overview

The AI Chat system integrates the Flutter mobile client with Wandy (AI Travel Copilot) via a NestJS API gateway proxy and a Python FastAPI backend running Gemini with function calling tools.

## Architecture

```
Flutter Mobile (Client)
  │
  ├─ AiChatScreen (Presentation)
  │     └─ Listens to ChatState (Riverpod)
  │
  ├─ ChatNotifier (State Management)
  │     ├─ Optimistically renders user bubble
  │     ├─ Tracks active sessionId across turns
  │     └─ Handles 401 token expiration -> triggers logout
  │
  ├─ ChatRepository (Data Access)
  │     └─ Uses Dio with 35s timeout
  │
  ▼  HTTP POST /ai/chat (Authorization: Bearer <access_token>)
NestJS Backend (Port 3000)
  │
  ├─ JwtAuthGuard & CurrentUser (Auth verification)
  ├─ ChatDto (class-validator validation)
  ├─ AiProxyController & AiProxyService (Reverse proxy)
  │     └─ Axios forward with 30s timeout
  │
  ▼  HTTP POST /chat
FastAPI AI Service (Port 8000)
  │
  ├─ chat.py router
  ├─ gemini.py provider (google-genai SDK, model: gemini-3.5-flash)
  │     └─ Tools: get_weather, search_places, calculate_budget, search_hotels
  └─ In-memory session history (per sessionId)
```

## Request & Response Flow

1. **User input**: User types a question in Flutter and taps Send.
2. **Local validation**: Non-empty check in Flutter; empty strings are rejected.
3. **Optimistic update**: User bubble appears immediately; UI enters `ChatStatus.loading`.
4. **Gateway call**: Flutter calls `POST http://localhost:3000/ai/chat` passing Bearer token and JSON `{message, session_id}`.
5. **Gateway authentication**: NestJS `JwtAuthGuard` validates the JWT token.
   - If missing/invalid -> returns `401 Unauthorized`.
   - Flutter `ChatNotifier` intercepts 401 and calls `authProvider.notifier.logout()`, redirecting to `/login`.
6. **Proxy forwarding**: NestJS forwards to `FastAPI:8000/chat`.
7. **LLM & Tool Calling**: Gemini 3.5 Flash evaluates system prompt and calls functions if necessary (weather, places, budget, hotels).
8. **Response Return**: FastAPI returns `{reply, session_id, tools_used, tool_calls}`.
9. **Gateway format**: NestJS wraps in `{success: true, data: {...}, timestamp: "..."}`.
10. **State update**: Flutter app receives response, appends assistant message, and updates `sessionId` for subsequent conversation turns.

## Timeout & Error Handling

| Scenario | Handled By | Resulting User Message |
|---|---|---|
| Request takes > 35s | Dio in Flutter | `AI phan hoi qua lau. Vui long thu lai.` |
| Network disconnect | Dio in Flutter | `Khong the ket noi may chu. Vui long kiem tra mang.` |
| Token expired / 401 | Flutter ChatNotifier | Log out user, redirect to `/login` |
| Empty message | Flutter UI & Backend DTO | Rejected locally; 400 Bad Request if sent |
| AI Service unavailable (503) | NestJS & Flutter | `Dich vu AI dang ban hoac qua tai. Vui long thu lai sau.` |

## Conversation Memory & Limitations

- **Current Session Memory**: In-memory only. The session preserves messages in Flutter state and on the FastAPI server by `session_id` for the duration of the current run.
- **No Persistent Database Storage**: Messages are not yet saved into the PostgreSQL `ai_messages` or `ai_sessions` tables. This is intentional for TASK 03 to keep the MVP slice lightweight and will be implemented in a dedicated AI persistence milestone.
- **Streaming**: Not currently supported by the backend proxy or FastAPI router. Standard buffered responses are used.
