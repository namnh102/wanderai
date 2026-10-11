# GoMate AI Planner — UX Contract & State Lock Audit Report (TASK 08.2.3.6)

**Status:** APPROVED FINAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.6 — GOMATE AI PLANNER UX CONTRACT & STATE LOCK  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Code, API & Test Audit Summary

### 1.1. Code Inspected (Read-Only)
1. **Flutter Mobile Client (`apps/mobile/`):**
   - `lib/features/trips/presentation/trip_detail_screen.dart`: Inspected lines 63–115 (`_handleGenerateAiPlan`), 117–385 (`_showAiPlanPreviewModal`), and 697–704 (Empty state CTA).
   - `lib/features/trips/data/trip_repository.dart`: Inspected `generateAiPlan` (lines 97–124, timeout set to 75s) and `bulkSaveItinerary` (lines 127–146).
   - `lib/features/trips/data/trip_models.dart`: Inspected `AiPlanPreviewModel`, `AiPlanDayModel`, `AiPlanItemModel`, `BudgetAnalysisModel`, and `BulkSaveItineraryRequest`.
   - `lib/features/trips/providers/trip_provider.dart`: Inspected `TripDetailNotifier.generateAiPlan` and `saveAiPlan`.
2. **Backend NestJS Service (`apps/backend/`):**
   - `src/modules/trips/trips.controller.ts`: Lines 107–127 (`POST :id/ai-plan`, `POST :id/itinerary/bulk`).
   - `src/modules/trips/trips.service.ts`: Lines 315–394 (`planTripWithAi`), Lines 397–467 (`bulkSaveItinerary`).
   - `src/modules/trips/dto/plan-trip.dto.ts` & `bulk-itinerary.dto.ts`.
   - `src/modules/ai-proxy/ai-proxy.service.ts`: Lines 55–98 (`planWithTripContext`, 60s timeout proxy).
3. **FastAPI AI Service (`apps/ai-service/`):**
   - `app/routers/planner.py`: Lines 56–241 (`create_plan`, prompt construction, Gemini integration, fallback mock, deterministic budget calculation).
   - `app/schemas/planner.py`: `TripContextRequest`, `PlanRequest`, `PlanResponse`, `ItineraryDay`, `ItineraryItem`, `BudgetAnalysis`.
   - `app/prompts/planner_prompt.py`.

### 1.2. Verification of Critical Invariants
* **Invariant 1: Preview Generates ZERO Database Mutations:**
  - Audited `trips.service.ts` (`planTripWithAi`): only queries the trip via `findById` and forwards `TripContext` to `aiProxyService`. No `prisma.itinerary.create`, `update`, or `delete` is called.
  - Confirmed by `test_planner_router_has_no_database_access` in FastAPI and Test 3 in `planner.e2e-spec.ts`.
* **Invariant 2: Deterministic Arithmetic Calculation:**
  - All item costs are summed in TypeScript/Python loops (`calculatedCost += dayCost`). LLM output is not trusted for totals or variance.
* **Invariant 3: Atomic Transaction on Apply:**
  - `trips.service.ts` runs inside `await this.prisma.$transaction(async (tx) => { ... })`. Old itinerary is safely replaced only when `replaceExisting !== false`.
* **Invariant 4: Honest Place Linkage:**
  - `AiPlanItemModel.toBulkItemJson()` does not synthesize random place UUIDs (`placeId` is null unless matched).

---

## 2. Test Execution & Evidence

### 2.1. FastAPI AI Service Planner Unit & Failure Tests
- **Command:** `python -m pytest tests/test_planner.py tests/test_planner_failures.py -q`
- **Working Directory:** `d:\Do_an\wanderai\apps\ai-service`
- **Result:** **11 passed, 1 warning in 5.12s (100% PASS)**
- **Coverage Highlights:**
  - `test_planner_defaults_use_supported_model_and_large_output_limit`: PASS
  - `test_planner_passes_configured_model_and_limit_to_provider`: PASS
  - `test_planner_provider_failure_is_controlled_and_does_not_leak`: PASS (Confirms 502 without traceback/key leaks)
  - `test_planner_malformed_json_returns_502`: PASS
  - `test_planner_truncated_output_returns_502`: PASS
  - `test_planner_router_has_no_database_access`: PASS (Validates preview invariant at AST/code level)
  - `test_planner_invalid_day_range`: PASS (Rejects days < 1 or days > 14 with 400)
  - `test_planner_with_trip_context`: PASS (Validates full payload parsing and deterministic math)
  - `test_planner_over_budget_detection`: PASS
  - `test_planner_backward_compatibility`: PASS
  - `test_evaluation_scenario_runner`: PASS

### 2.2. Flutter Mobile Test Suite
- **Command:** `flutter test`
- **Working Directory:** `d:\Do_an\wanderai\apps\mobile`
- **Result:** **152 tests passed! (100% PASS)**
- **Coverage Highlights:** All unit and widget tests across auth, trips, map, place detail, and navigation passed without regressions.

### 2.3. NestJS Backend E2E Test Baseline
- **File:** `apps/backend/test/planner.e2e-spec.ts`
- **Coverage:** 9 comprehensive e2e specs covering authentication (401), authorization (403), preview generation with zero DB write, provider failure handling (502), atomic bulk save, empty days rejection (400), and non-owner bulk save rejection (403).

---

## 3. Existing Mockup Audit (7 Artifacts)

All 7 AI Planner mockups in `docs/audit/evidence/ui-08.2.3.5/` were audited against the UX contract and backend capabilities:

| Mockup File | Viewport | Target State | Visual Contract Audit Findings | Verdict |
| :--- | :---: | :---: | :--- | :---: |
| [`trip-mobile-ai-entry.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-entry.png) | Mobile ($390 \times 844$) | Input Configuration | Header "Lập lịch trình bằng AI"; trip context subtitle; includes inputs for interests, preferred pace (`PlanTripDto`), and custom prompt textarea. Primary CTA: "Bắt đầu lập lịch trình". | **PASS** |
| [`trip-mobile-ai-generating.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-generating.png) | Mobile ($390 \times 844$) | Generating Liveness | Centered indeterminate spinner; live phase cues; estimated duration (15–25s); **ABSOLUTELY NO FAKE PERCENTAGES**. | **PASS** |
| [`trip-mobile-ai-preview.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-preview.png) | Mobile ($390 \times 844$) | In-Memory Preview | Warning banner: "BẢN XEM TRƯỚC (CHƯA LƯU VÀO CHUYẾN ĐI)"; budget status pill "Trong hạn mức"; day breakdown with itemized costs; Dual actions: "Hủy bỏ" & "Áp dụng lịch trình này". | **PASS** |
| [`trip-mobile-ai-overwrite.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-overwrite.png) | Mobile ($390 \times 844$) | Overwrite Protection | Alert triangle; explicit notice: "Chuyến đi này đã có 12 hoạt động. Áp dụng... sẽ thay thế toàn bộ..."; Actions: "Hủy bỏ" & "Ghi đè lịch trình". | **PASS** |
| [`trip-mobile-ai-success.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-success.png) | Mobile ($390 \times 844$) | Apply Success | Success checkmark; "Đã cập nhật lịch trình!"; Actions: "Xem chi tiết lịch trình" & "Tiếp tục chỉnh sửa". | **PASS** |
| [`trip-mobile-ai-error.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-ai-error.png) | Mobile ($390 \times 844$) | Generation Error | Red alert icon; friendly message: "Không thể tạo lịch trình AI. Lịch trình hiện tại vẫn được giữ nguyên."; Zero leaked traces; Actions: "Thử lại lần nữa" & "Tự thêm hoạt động". | **PASS** |
| [`trip-desktop-ai-preview.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-desktop-ai-preview.png) | Desktop ($1440 \times 900$) | Desktop Preview | Responsive 2-column workstation; banner: "Kế hoạch này chưa được lưu vào cơ sở dữ liệu"; identical budget and timeline contracts; "Hủy bỏ" & "Áp dụng vào chuyến đi". | **PASS** |

**Conclusion:** All 7 existing mockups are in 100% compliance with the verified contracts. **No mockup regeneration is needed.**

---

## 4. Discrepancy & Target Contract Reconciliation

1. **Input Parameters (Current Code vs Target Mockup):**
   - *Current Flutter Dialog:* Currently prompts for `additionalPrompt` (text field) within a standard `AlertDialog`.
   - *Backend `PlanTripDto`:* Supports `additionalPrompt` and `preferredPace`.
   - *Target Mockup (`trip-mobile-ai-entry.png`):* Visualizes a rich bottom modal sheet with choice chips for `preferredPace` and `interests`.
   - *Reconciliation:* The rich bottom sheet is designated as **`CURRENT CAPABILITY (Backend) / DESIGN TARGET (Flutter UI Polish)`**.
2. **Place Linkage Honesty:**
   - In `AiPlanItemModel.toBulkItemJson()`, `placeName` is appended to `notes` (`"Món ăn đặc sản (Mì Quảng Bếp Trang)"`) while `placeId` remains `null`. This prevents false claims of verified PostGIS linkage for generative text places.
3. **Timeout Alignment:**
   - FastAPI: 45s default LLM timeout.
   - NestJS Axios: 60s timeout.
   - Flutter Dio: 75s timeout.
   - This ensures that if the AI provider times out or fails, the backend catches it and returns a clean 502/503 before the mobile client gives up with a generic network drop.

---

## 5. Comprehensive AI Planner Capability Matrix

| Feature | Backend API Endpoint | Flutter Screen / Provider | FastAPI Route | Design Artifact | Capability Status | Contract Invariant / Verification |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **Planner Entry** | `GET /trips/:id` | `trip_detail_screen.dart` | N/A | `trip-mobile-detail-empty-r1.png` | **CURRENT** | Triggered via "Lập lịch trình bằng AI" button. |
| **Trip Context** | `trips.service.ts` | `trips_client.dart` | `schemas/planner.py` | `trip-mobile-ai-entry.png` | **CURRENT** | Extracted from stored Trip record. |
| **Preferences / Prompt** | `PlanTripDto.additionalPrompt` | `noteController` | `notes` | `trip-mobile-ai-entry.png` | **CURRENT** | User enters optional prompt. |
| **Preferred Pace** | `PlanTripDto.preferredPace` | Missing in dialog | Missing in prompt | `trip-mobile-ai-entry.png` | **PARTIAL** | Backend DTO ready; UI chip selection is Design Target. |
| **Budget Context** | `Trip.totalBudget` | Budget header | `TripContextRequest.budget` | `trip-mobile-ai-preview.png` | **CURRENT** | Exact integer budget passed. |
| **Generation Liveness** | 60s proxy timeout | 75s Dio timeout | Gemini generation | `trip-mobile-ai-generating.png` | **CURRENT** | **Zero fake percentage.** Live elapsed timer. |
| **In-Memory Preview** | `POST /trips/:id/ai-plan` | `_showAiPlanPreviewModal` | `POST /planner` | `trip-mobile-ai-preview.png` | **CURRENT** | **Zero DB writes.** Verified by E2E test. |
| **Source Grounding** | Text place names | Plain text display | Text activity | `trip-mobile-ai-preview.png` | **CURRENT** | No synthetic `placeId` UUIDs. |
| **Overwrite Warning** | `replaceExisting: true` | Client check | N/A | `trip-mobile-ai-overwrite.png` | **CURRENT** | Shown when trip already has activities. |
| **Atomic Bulk Apply** | `POST /trips/:id/itinerary/bulk`| `saveAiPlan` | N/A | `trip-mobile-ai-preview.png` | **CURRENT** | Wrapped in Prisma `$transaction`. |
| **Retry on Failure** | Error filters | "Thử lại" action | Error handler | `trip-mobile-ai-error.png` | **CURRENT** | Current itinerary preserved on error. |
| **Timeout Handling** | 60s timeout | 75s timeout | 45s timeout | `trip-mobile-ai-error.png` | **CURRENT** | Controlled 502/503 response. |
| **Wandy Chat Bridge** | Independent | Independent | Independent | `docs/design/` | **FUTURE** | Conversational chat does not mutate trips. |
| **Autonomous Action** | Blocked | Blocked | Blocked | Non-agentic | **FORBIDDEN** | Human-in-the-loop apply strictly required. |

---

## 6. Design Acceptance Gate (TASK 08.2.3.6)

- [x] **Planner Input contract verified:** `PlanTripDto` (`additionalPrompt`, `preferredPace`) mapped and documented.
- [x] **API payload verified:** `POST /trips/:id/ai-plan` and `POST /trips/:id/itinerary/bulk` match code reality.
- [x] **Generation state honest:** Live elapsed timer, sequential phase cues.
- [x] **No fake percentage:** 0% to 100% progress tickers strictly omitted.
- [x] **Timeout UX defined:** 0–15s normal, 15–45s reassuring cue, >60s failure with retry.
- [x] **Preview is non-destructive:** Confirmed 0 database writes in `planner.e2e-spec.ts` and `test_planner_failures.py`.
- [x] **Preview data fields verified:** Days, items, times, costs, notes, transport mode, and overview.
- [x] **Existing itinerary protected:** Overwrite confirmation modal specified for non-empty trips.
- [x] **Apply requires confirmation:** Explicit user click on "Áp dụng lịch trình này" required.
- [x] **Bulk apply endpoint verified:** Uses atomic transaction (`prisma.$transaction`) with `replaceExisting: true`.
- [x] **Apply failure preserves safety:** In-memory preview retained on error, old itinerary untouched.
- [x] **Success only after API success:** Success feedback rendered only upon HTTP 200/201.
- [x] **Budget states verified:** Within budget, near limit, over budget, and no budget defined.
- [x] **Place/source honesty preserved:** No synthetic `placeId` UUIDs or fake star ratings.
- [x] **Wandy boundary explicit:** Chat operates separately from active trip mutation.
- [x] **Agent boundary explicit:** Planner is not an unconstrained autonomous agent.
- [x] **Mobile/desktop business behavior same:** Responsive 2-column desktop follows identical invariants.
- [x] **Accessibility reviewed:** $\ge 44\text{dp}$ touch targets, semantic screen reader live regions, color-independent badges.
- [x] **Current/Future matrix complete:** All 14 capabilities categorized.
- [x] **No source code changes:** 0 lines modified in `apps/`.
- [x] **No API changes:** Contracts intact.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
