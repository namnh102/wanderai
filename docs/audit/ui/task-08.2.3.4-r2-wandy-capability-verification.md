# GoMate Wandy AI Copilot — Capability Verification & Documentation Reconciliation Audit (TASK 08.2.3.4-R2)

**Status:** COMPLETE & RECONCILED  
**Task:** TASK 08.2.3.4-R2 — WANDY AI COPILOT CAPABILITY VERIFICATION & DOCUMENTATION RECONCILIATION  
**Base:** TASK 08.2.3.4-R1 (Commit `e3905d2`)  
**Branch:** `feature/gomate-visual-mockups`  
**Classification Rules:**
- **CURRENT:** Verified by production source code, live API endpoint, and automated test.
- **PARTIAL:** Implemented in part or in another module, but the end-to-end Wandy flow is incomplete.
- **FUTURE:** Conceptual design, visual mockup, or architecture roadmap only.
- **BLOCKED:** Dependency or access clearance pending.

---

## 1. Scope & Objective

The objective of TASK 08.2.3.4-R2 is to perform an honest, rigorous engineering audit of all capability claims made in TASK 08.2.3.4 and 08.2.3.4-R1. Specifically, this task reconciles claims of `CURRENT`, `PARTIAL`, and `FUTURE` capabilities against actual production source code across Flutter (`apps/mobile/`), NestJS Backend (`apps/backend/`), FastAPI AI Service (`apps/ai-service/`), and test suites.

**Constraints Strictly Respected:**
- ZERO changes to Flutter/Dart UI code.
- ZERO changes to Backend/NestJS code.
- ZERO changes to AI Service/FastAPI code.
- ZERO changes to Database or Prisma schemas.
- ZERO changes to Visual Mockups or Design Tokens.
- Only documentation reconciliation and audit reporting.

---

## 2. Documents Reviewed

1. **Architecture & Project Status:**
   - `docs/project-status.md` (Baseline completed tasks 1–59, test suite counts).
   - `docs/architecture/trip-flow.md` (TripContext abstraction and lifecycle).
   - `docs/ai/ai-chat.md` (AI Chat system architecture and session memory).
   - `docs/api/ai-chat-api.md` (NestJS `/ai/chat` request/response contracts).
   - `docs/api/trips-api.md` (Trips CRUD and `/trips/:id/itinerary` contracts).
2. **Design Specifications & Prior Audits:**
   - `docs/design/gomate-wandy-visual-spec-v1.md` (Visual tokens, component spec, Section 7).
   - `docs/design/gomate-wandy-user-flow-spec-v1.md` (Flows W01–W12).
   - `docs/audit/ui/task-08.2.3.4-wandy-visual-audit.md` (V1 baseline audit).
   - `docs/audit/ui/task-08.2.3.4-r1-wandy-visual-audit.md` (R1 visual correction audit).
3. **Production Source Code (Audited via Direct Read):**
   - `apps/mobile/lib/features/ai_chat/data/chat_models.dart`
   - `apps/mobile/lib/features/ai_chat/data/chat_repository.dart`
   - `apps/mobile/lib/features/ai_chat/providers/chat_provider.dart`
   - `apps/mobile/lib/features/ai_chat/presentation/ai_chat_screen.dart`
   - `apps/mobile/lib/features/trips/presentation/trip_detail_screen.dart`
   - `apps/mobile/lib/features/places/presentation/place_detail_screen.dart`
   - `apps/backend/src/modules/ai-proxy/ai-proxy.controller.ts`
   - `apps/backend/src/modules/ai-proxy/ai-proxy.service.ts`
   - `apps/backend/src/modules/ai-proxy/dto/chat.dto.ts`
   - `apps/backend/src/modules/trips/trips.controller.ts`
   - `apps/ai-service/app/routers/chat.py`
   - `apps/ai-service/app/schemas/chat.py`
   - `apps/ai-service/app/services/rag.py`

---

## 3. Current Implementation State (Audited Reality)

### 3.1. Flutter Mobile Client (`apps/mobile/lib/features/ai_chat/`)
- **Presentation (`ai_chat_screen.dart`):** Renders a functional conversational chat with user message bubbles (Teal `#0F766E`), assistant message bubbles (White with `Icons.auto_awesome`), loading indicator ("Wandy đang suy nghĩ..."), and error banner with retry.
- **Citation Rendering:** Assistant bubbles render a `Nguồn tham khảo:` section with clickable chips launching external OpenStreetMap and Wikivoyage URLs via `url_launcher`.
- **Missing Elements:**
  - No place card widgets or place carousels.
  - No "Xem địa điểm" or "Xem chi tiết" navigation buttons.
  - No "Xem trên bản đồ" map-linking buttons.
  - No "Thêm vào chuyến đi" action buttons or `SelectTrip` bottom sheets.
  - No trip context header banner.
  - No agent confirmation dialogs or runtime safety triggers.

### 3.2. NestJS Gateway (`apps/backend/src/modules/ai-proxy/`)
- **Endpoint:** `POST /ai/chat` protected by `JwtAuthGuard`.
- **Contract:** Accepts `{ message: string, session_id?: string }`.
- **Proxy Behavior:** Forwards to FastAPI port 8000 and wraps the response with `{ success: true, data: { reply, session_id, tools_used, tool_calls, sources }, timestamp }`.
- **Missing Parameters:** Does not accept `trip_id`, `destination`, or `TripContext`.

### 3.3. FastAPI AI Service (`apps/ai-service/app/routers/chat.py`)
- **Endpoint:** `POST /chat`.
- **RAG Grounding:** Calls `retrieve_grounding()` to query `RAGService` against 384-dimensional pgvector embeddings in `rag_documents`. Retrieved chunks from OSM and Wikivoyage are injected into the system prompt with strict no-hallucination instructions.
- **LLM Provider:** Invokes Gemini with 4 read-only function calling tools (`get_weather`, `search_places`, `calculate_budget`, `search_hotels`).
- **Response Format:** Returns a markdown string `reply` and array of URLs `sources`. Does **not** return structured canonical Place entities or place IDs.

---

## 4. Master Capability Verification Matrix

| Capability | Classification | Code Evidence | API Evidence | Test Evidence | Notes |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **A. Conversational Chat** | **CURRENT** | `chat_models.dart`, `chat_provider.dart`, `ai_chat_screen.dart` | `POST /ai/chat` (NestJS) $\rightarrow$ `POST /chat` (FastAPI) | `ai-chat.e2e-spec.ts` (4 pass), `test_chat.py` (pass) | Full end-to-end multi-turn conversational chat with session tracking. |
| **B. Spatial RAG Retrieval** | **CURRENT** | `retriever.py`, `rag.py`, `chat.py` (`retrieve_grounding`) | Embedded in `POST /chat` execution | `test_chat_rag.py` (4 pass) | pgvector similarity search against verified OSM/Wikivoyage docs. |
| **C. Source Citations** | **CURRENT** | `chat_models.dart` (`sources`), `ai_chat_screen.dart` (`_buildSourceChip`) | `data.sources: string[]` in `ChatResponse` | `ai-chat.e2e-spec.ts`, browser smoke test (TASK 07.6) | Tappable chips launch external browser URLs via `url_launcher`. |
| **D. Place Recommendations** | **PARTIAL** | Natural language text in `ChatMessage.content` | `reply: string` contains place names in Markdown | `test_chat.py` | Text recommendations exist; **NO** structured Place models, IDs, ratings, or UI cards exist in code. |
| **E. Trip Context Injection** | **FUTURE** (for Chat) / **CURRENT** (for Planner) | `ChatRequest` has no trip field; `ai_chat_screen.dart` has no context banner | `POST /ai/chat` contract has no `trip_id` | No chat context tests | Only supported in `POST /trips/:id/ai-plan`. Wandy Chat context is purely visual design. |
| **F. Manual Add-to-Trip** | **FUTURE** (from Wandy) / **CURRENT** (in Trips) | Generic `POST /trips/:id/itinerary` in `trips.controller.ts`; **ZERO** code in `ai_chat` | `POST /trips/:id/itinerary` (requires `dayNumber`, `activity`) | `trips.e2e-spec.ts` (pass) | Activity addition exists in `trip_detail_screen.dart`, but Wandy Chat has no connection to trips. |
| **G. Open Place Detail from Wandy** | **FUTURE** | `/places/:id` route exists; **NO** deep link or CTA in `ai_chat_screen.dart` | Wandy API returns no place IDs | None | Designed in Flow W06 and mockup `wandy-mobile-place-recommendation.png`, not in code. |
| **H. Open Map from Wandy** | **FUTURE** | `/map` route exists; **NO** deep link or CTA in `ai_chat_screen.dart` | No filter/marker navigation contract | None | Designed in Flow W07 and mockup `wandy-mobile-multi-place-results.png`, not in code. |
| **I. AI Planner Entry** | **PARTIAL** | AI Planner fully implemented in `trip_detail_screen.dart`; **NO** bridge from Wandy chat | `POST /trips/:id/ai-plan` + `/itinerary/bulk` | `planner.e2e-spec.ts`, `test_planner.py` | Feature exists under Trips, but Wandy has no entry bridge. Distinct from autonomous agent. |
| **J. Autonomous Itinerary Mutation** | **FUTURE** | Zero autonomous agent code in backend or frontend | No autonomous mutation API | None | Roadmap concept for Sprint 02+ multi-agent architecture. |
| **K. Autonomous Booking / Reminders** | **FUTURE** | Zero implementation in codebase | No booking/reminder endpoints | None | Roadmap concept for future tool integrations. |
| **L. Proactive Group Collaboration** | **FUTURE** | Trip member invite exists (`POST /trips/:id/members`), no proactive agent | No proactive agent endpoints | None | Roadmap concept. |
| **M. Agent Confirmation / Human-in-the-Loop** | **DESIGN INVARIANT** | Confirmation dialogs exist in mockups; zero runtime agent exists | N/A | N/A | UX safeguard rule (`ACTION MUTATION REQUIRES EXPLICIT USER CONFIRMATION`), not runtime code. |

---

## 5. Detailed Evidence per Critical Verification Item

### 5.1. Critical Verification #1: Manual Add-to-Trip
- **Audited Claim in R1:** *"Manual Add-to-Trip = CURRENT"*
- **Reality:** **FALSE for Wandy Copilot.**
- **Detailed Findings:**
  1. *Flutter Wandy UI:* In `apps/mobile/lib/features/ai_chat/presentation/ai_chat_screen.dart`, there is no `SelectTrip` bottom sheet, no "Thêm vào chuyến đi" button, and no reference to `tripProvider` or `TripModel`.
  2. *Flutter Trips UI:* In `apps/mobile/lib/features/trips/presentation/trip_detail_screen.dart`, a user can tap "Thêm hoạt động" to open a local form dialog (`_showAddItemDialog`) which adds an activity string to that specific trip.
  3. *Backend API:* `POST /trips/:id/itinerary` exists and works, but takes `{ dayNumber, activity, startTime, endTime, estimatedCost, notes }`. It does not accept a `placeId` from Wandy.
  4. *Conclusion:* The ability to add a place recommended by Wandy into a trip is **FUTURE** (visual mockup `wandy-mobile-add-to-trip-action.png`).

### 5.2. Critical Verification #2: Place Recommendations
- **Audited Claim in R1:** *"Place Recommendations = CURRENT"*
- **Reality:** **PARTIAL.**
- **Detailed Findings:**
  1. *Backend Response:* `ChatResponse` returned by FastAPI and NestJS only provides `reply: string` and `sources: string[]`. There is no structured JSON array of recommended places.
  2. *Flutter UI:* `ai_chat_screen.dart` renders text in `SelectableText(message.content)`. There is no horizontal card carousel, no rich place thumbnail, no distance calculation, and no rating badge.
  3. *Conclusion:* Wandy recommends places only as conversational text sentences. Structured place cards with metadata linkages are **PARTIAL** (designed in mockups, awaiting implementation).

### 5.3. Critical Verification #3: Trip Context Injection
- **Audited Claim in R1:** *"Trip Context Injection = CURRENT"*
- **Reality:** **FUTURE for Wandy Chat.**
- **Detailed Findings:**
  1. *Chat Contracts:* `ChatRequest` in Flutter, `ChatDto` in NestJS, and `ChatRequest` in FastAPI only accept `message` and `session_id`. They do not accept `trip_id`, `destination`, or `TripContext`.
  2. *Flutter State:* `ChatState` only tracks `messages`, `status`, `sessionId`, `errorMessage`, `lastFailedMessage`. There is no active trip state attached to chat.
  3. *Where TripContext Actually Exists:* TripContext is used exclusively by the AI Planner route (`POST /trips/:id/ai-plan` via `planWithTripContext` in `ai-proxy.service.ts`).
  4. *Conclusion:* Passing active trip context into Wandy Chat is a **FUTURE** capability (designed in `wandy-mobile-context-trip.png` and `wandy-desktop-chat-context.png`).

### 5.4. Critical Verification #4: Open Map / Place Detail
- **Audited Reality:** **FUTURE.**
- **Detailed Findings:**
  1. In `ai_chat_screen.dart`, the only navigation or interaction is `_launchSourceUrl(url)` which opens external browser links.
  2. There is no call to `context.push('/places/:id')` or `context.go('/map')`.
  3. Wandy does not receive canonical place IDs from the backend, preventing deep-linking.
  4. Both flows (W06 and W07) are **FUTURE** implementation items.

### 5.5. AI Planner vs Autonomous Agent
- **AI Planner (`CURRENT` in Trips):** A deterministic, user-initiated generation flow. The user opens an existing trip in `trip_detail_screen.dart`, taps "Lập lịch trình bằng AI", inspects a preview with budget analysis, and confirms with "Áp dụng". This is verified by `planner.e2e-spec.ts` and `test_planner.py`.
- **Wandy Autonomous Agent (`FUTURE`):** An autonomous entity executing background tool mutations, scheduling, or reordering without explicit manual form wizards. This does not exist in code.

### 5.6. Human-in-the-Loop: Design Invariant vs Runtime Enforcement
- **Design Invariant:** The visual rule established in `gomate-wandy-visual-spec-v1.md` §7.7 states that any AI action mutating user data must require explicit confirmation. The confirmation dialogs (`wandy-mobile-agent-confirmation.png`, `wandy-desktop-agent-confirmation.png`) serve as UX specifications.
- **Runtime Reality:** Because no autonomous background agent exists to initiate mutations, there is no runtime agent interception middleware in production code. The rule is currently a **Design Invariant**, not an implemented agent security feature.

---

## 6. Documentation Discrepancies Reconciled

The following reconciliations were made to ensure that documentation matches codebase reality:

1. **`docs/design/gomate-wandy-visual-spec-v1.md` Section 7.4:**
   - Corrected **Place Recommendations** from `CURRENT` to `PARTIAL`.
   - Corrected **Trip Context in Chat** from `CURRENT` to `FUTURE`.
   - Corrected **Manual Add-to-Trip from Wandy** from `CURRENT` to `FUTURE`.
   - Added explicit entries for **Open Place Detail** (`FUTURE`) and **Open Map** (`FUTURE`).
   - Clarified **AI Planner Engine** as `PARTIAL` (implemented in Trips, entry bridge from Wandy is Future).
   - Re-classified **Agent Confirmation** as a `DESIGN INVARIANT`.
2. **`docs/audit/ui/task-08.2.3.4-r1-wandy-visual-audit.md` Section 4 & 5:**
   - Corrected Section 4 title to "Current & Partial Capabilities (Audited Production Reality)".
   - Removed inaccurate statements claiming "Place Entity Bridge" and "Manual Add to Trip" were fully implemented for Wandy.
   - Clarified Section 5 roadmap items.

---

## 7. Automated Test Suite Results

- **Mobile Client:**
  - `flutter analyze`: `No issues found! (ran in 4.4s)`.
  - `flutter test`: `+152: All tests passed!` (152/152 passed).
- **AI Service:**
  - Database test dependency: `wanderai-postgres` (PostgreSQL 16 + pgvector) and `wanderai-redis` running and healthy in WSL2 Docker container, listening on `localhost:5432` / `localhost:6379`.
  - `python -m pytest tests/ -q`: **87 passed, 2 skipped, 0 failed** in 47.82s (EXIT_CODE = 0).
  - Targeted Chat / RAG / Grounding / Planner / Tools test suite (`tests/test_chat.py`, `tests/test_chat_rag.py`, `tests/test_rag.py`, `tests/test_grounding_contract.py`, `tests/test_planner.py`, `tests/test_tools.py`): **34 passed, 0 failed** in 22.32s (EXIT_CODE = 0).
  - Skipped tests (2): `tests/test_live_e2e.py` and `tests/test_rag_benchmark.py` (explicit opt-in / benchmark tests requiring live Gemini API keys).
- **Source Code Integrity:**
  - `git diff apps/`: **100% CLEAN** (Zero lines of application code modified).

---

## 8. Final Acceptance & Recommendation

### Quality Gate Verification
- [x] All `CURRENT` claims backed by verifiable code, API, and test evidence.
- [x] Mockups are strictly treated as visual targets, never cited as implementation proof.
- [x] Manual Add-to-Trip accurately verified (Current in Trips form, Future from Wandy).
- [x] Place Recommendations accurately classified as Partial.
- [x] Trip Context accurately verified (Current in Trips Planner, Future in Wandy Chat).
- [x] Deep-linking to Map and Place Detail accurately classified as Future.
- [x] AI Planner clearly distinguished from Autonomous Agent.
- [x] Human-in-the-Loop accurately designated as a Design Invariant.
- [x] Documentation reconciled across all specification files.
- [x] Zero changes to source code, database, or API contracts.
- [x] Zero changes to approved visual design or mockups.

### Recommendation for Next Task (Implementation Sprint)
With the visual design locked (R1) and capability boundaries verified against code reality (R2), the project foundation is solid. The next logical task should transition into:
1. **TASK 08.2.4 (or Implementation Sprint):** Implementing the visual components in Flutter (`WandyChatScreen` redesign, Mascot avatar, Rich Place Card widget, and Source detail bottom sheet) without breaking existing RAG grounding contracts.
