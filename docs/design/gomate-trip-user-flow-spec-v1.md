# GoMate Trip Management — User Flow Specification V1

**Status:** APPROVED USER FLOW SPECIFICATION (REVISION R2 LOCKED)  
**Tasks:** TASK 08.2.3.5, TASK 08.2.3.5-R1 & TASK 08.2.3.5-R2 (Final State & Edit Contract Lock)  
**Applies to:** Mobile App (iOS / Android / Flutter Web Mobile) & Desktop Web (1440px)  
**Covers:** Core Flows T01 through T16  
**Source of Truth:** GoMate Master UX Plan V2, UX Architecture V1, Prisma Schema, NestJS Trips Module, Flutter Router & Trips Feature  

---

## 1. Flow Matrix Overview

| Flow ID | Flow Name | Primary Screen Mockup | Core Interaction | Capability Status |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Trip Discovery & List Navigation | `trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`, `trip-mobile-list-empty-r2.png`, `trip-mobile-list-loading-r2.png`, `trip-mobile-list-error-r2.png`, `trip-desktop-list.png` | Bottom Tab 5 tap, semantic tabs (Hiện tại & sắp tới / Đã kết thúc / Bản nháp), persistent search | **CURRENT** |
| **T02** | Trip Creation Flow | `trip-mobile-create-r1.png`, `trip-mobile-create-validation.png`, `trip-desktop-create.png` | Tap "+", fill Title, Destination, Dates, Budget, Style; CTA: "Tạo chuyến đi" | **CURRENT** |
| **T03** | Trip Edit Flow | `trip-mobile-edit-r2.png` | More Menu → Chỉnh sửa thông tin; edit Title, Dates, Budget, Style, Notes (NO status dropdown) | **CURRENT** |
| **T04** | Trip Deletion Flow | `trip-mobile-delete-confirmation.png` | More Menu → Xóa chuyến đi, destructive modal confirmation | **CURRENT** |
| **T05** | Trip Detail & Navigation | `trip-mobile-detail.png`, `trip-mobile-detail-empty-r1.png`, `trip-desktop-detail.png` | Tap trip card, browse hero metadata, identical title, day selector tabs | **CURRENT** |
| **T06** | Manual Activity Creation | `trip-mobile-add-activity-r1.png` | Tap "+ Thêm hoạt động", bottom sheet mapping 1:1 to API (activity, placeId?, time, cost, transportMode, notes) | **CURRENT** |
| **T07** | Activity Editing | `trip-mobile-edit-activity.png` | Tap item card → edit details, time, cost, notes | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |
| **T08** | Activity Deletion | `trip-mobile-delete-activity.png` | Swipe or item menu → Xóa hoạt động, instant budget/timeline update | **CURRENT** |
| **T09** | Timeline Reordering | `trip-mobile-reorder.png` | Tap "Sắp xếp lại", drag handles, persist updated sequence | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |
| **T10** | Add Place from Place Detail | `wandy-mobile-add-to-trip-action.png` | From Map / Place Detail, tap "Thêm vào chuyến đi", pick trip & day | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |
| **T11** | AI Planner Entry & Parameters | `trip-mobile-ai-entry.png` | Tap "Lập lịch trình bằng AI", review prompt, style, budget, days | **CURRENT** |
| **T12** | AI Plan Generation Feedback | `trip-mobile-ai-generating.png` | Active liveness indicator, elapsed timer (~20-40s), progress steps, NO fake % | **CURRENT** |
| **T13** | AI Plan Preview & Invariant Check | `trip-mobile-ai-preview.png`, `trip-desktop-ai-preview.png` | Inspect proposed days, variance, items; **NO DB WRITE** yet | **CURRENT** |
| **T14** | AI Plan Overwrite Confirmation | `trip-mobile-ai-overwrite.png` | Modal warning if trip has existing activities (`replaceExisting`) | **CURRENT** |
| **T15** | AI Plan Bulk Save / Commit | `trip-mobile-ai-success.png` | Tap "Áp dụng vào chuyến đi", atomic transaction, status → PLANNED | **CURRENT** |
| **T16** | Budget Tracking & Over-budget Alert | `trip-mobile-budget.png`, `trip-mobile-budget-warning.png`, `trip-mobile-budget-over.png`, `trip-desktop-detail-budget.png` | Real-time budget calculation, percentage tracks, threshold warnings | **CURRENT (UI Mockup) / PARTIAL (Backend compute)** |

---

## 2. Detailed Flow Specifications

### FLOW T01: Trip Discovery & List Navigation
- **Entry Points:**
  - Mobile: Tapping Tab 5 (`Chuyến đi`) in the 5-tab bottom navigation bar (`_MainScaffold`).
  - Desktop: Clicking `Chuyến đi` in the top global navigation bar.
  - Home Screen: Tapping "Xem tất cả chuyến đi" in the Home dashboard.
- **User Intent:** View current travel commitments, review past travel memories, or locate a trip to edit.
- **Screen Mockups:**
  - `trip-mobile-list-upcoming-r1.png`: Displays ongoing & upcoming trips.
  - `trip-mobile-list-past-r1.png`: Displays completed trips.
  - `trip-mobile-list-empty-r2.png`: Empty state with friendly luggage illustration, "+ Tạo chuyến đi ngay" CTA, and 5-tab navigation.
  - `trip-mobile-list-loading-r2.png`: Shimmer skeleton loading cards with 5-tab navigation.
  - `trip-mobile-list-error-r2.png`: Network failure screen with retry button and 5-tab navigation.
  - `trip-desktop-list.png`: 3-column responsive card grid on desktop (1440px).
- **Search Control Contract (Locked Decision):**
  - **Rule (Option A): Persistent Search Across Populated Tabs.**
  - The search input is persistently visible below the filter tabs on all populated list views ("Hiện tại & sắp tới", "Đã kết thúc", "Bản nháp").
  - Typing in the search box dynamically filters the active tab's trips in real-time by `title` and `destination`.
  - On Empty and Error states, the search bar is suppressed to prioritize recovery actions.
- **Tab Categorization & Status Mapping:**
  - Tab 1: **"Hiện tại & sắp tới"** $\rightarrow$ Trips with status `ONGOING` (currently happening today) or `PLANNED` / `DRAFT` where `endDate >= today`.
  - Tab 2: **"Đã kết thúc"** $\rightarrow$ Trips with status `COMPLETED`, `CANCELLED` (see Section 3), or where `endDate < today`.
  - Tab 3: **"Bản nháp"** $\rightarrow$ Trips with status `DRAFT` and no finalized itinerary items.
- **Single Primary Action Principle:**
  - The top app bar features a single primary `+` button in the top right.
  - The duplicate Floating Action Button (FAB) is removed.
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips`) and Flutter (`trip_list_screen.dart`).

---

### FLOW T02: Trip Creation Flow
- **Entry Points:**
  - Header `+` button in Trip List screen.
  - Wandy Copilot recommendation or Planner button from Home.
- **User Intent:** Initialize a new travel itinerary with high-level constraints.
- **Screen Mockups:**
  - `trip-mobile-create-r1.png`: Full creation form on mobile with standardized fields and CTA.
  - `trip-mobile-create-validation.png`: Client-side validation errors.
  - `trip-desktop-create.png`: Centered modal dialog on desktop workspace.
- **Form Fields & Validation Rules:**
  1. **Tên chuyến đi (Title)** [Required]: Min 3 characters, max 100 characters. e.g. "Khám phá Đà Nẵng mùa thu".
  2. **Điểm đến (Destination)** [Required]: Text input / autocomplete.
  3. **Thời gian (Start & End Date)** [Required]: `startDate >= today`, `endDate >= startDate`.
  4. **Ngân sách dự kiến (Estimated Budget)** [Optional]: Positive integer in VND.
  5. **Phong cách du lịch (Travel Style)** [Optional]: Choice chip: `Phượt (BACKPACKER)`, `Tiết kiệm (BUDGET)`, `Thoải mái (COMFORT)`, `Sang trọng (LUXURY)`.
  - **Exclusion:** "Sở thích du lịch" is excluded from trip creation persistence; configured during AI planning.
- **CTA Decoupling:**
  - Primary button is strictly **"Tạo chuyến đi"**.
  - `POST /trips` creates the trip record and routes to empty Trip Detail. Does NOT automatically trigger AI planning.
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips`) and Flutter (`trip_form_screen.dart`).

---

### FLOW T03: Trip Edit Flow
- **Entry Points:**
  - Trip Detail screen → Top App Bar More menu (`⋮`) → "Chỉnh sửa thông tin chuyến đi".
- **User Intent:** Update title, dates, budget, travel style, or notes of an existing trip.
- **Screen Mockups:**
  - `trip-mobile-edit-r2.png`: Edit form pre-populated with verified editable fields.
- **Field Contract & Status Rule (Locked):**
  - **Editable Fields:**
    - `title`: Tên chuyến đi (TextFormField)
    - `startDate` & `endDate`: Ngày bắt đầu / kết thúc (Date pickers)
    - `totalBudget`: Tổng ngân sách dự toán (Numeric input)
    - `travelStyle`: Phong cách du lịch (Choice chips: Phượt / Tiết kiệm / Thoải mái / Sang trọng)
    - `description`: Mô tả / Ghi chú (Textarea)
    - `destination`: Displayed as read-only destination reference (Destination change is PARTIAL in backend only).
  - **STRICT EXCLUSION — NO STATUS DROPDOWN:**
    - The Status dropdown is **REMOVED** from the user edit form.
    - Trip status (`TripStatus`) is governed strictly by system lifecycle invariants (`DRAFT` $\rightarrow$ `PLANNED` on bulk commit, `ONGOING` on active date, `COMPLETED` on post-end-date, `CANCELLED` via explicit menu action).
- **Date Shrink Invariant Rule:**
  - If user shrinks the date range and activities exist on cut days:
    - Warning modal: "Thu hẹp thời gian sẽ ảnh hưởng đến các hoạt động trong ngày bị cắt. Bạn có chắc muốn tiếp tục?"
- **Capability Reality:** **CURRENT** in NestJS (`PATCH /trips/:id`) and Flutter (`trip_form_screen.dart?existingTrip=...`).

---

### FLOW T04: Trip Deletion Flow
- **Entry Points:**
  - Trip Detail screen → Top App Bar More menu (`⋮`) → "Xóa chuyến đi" (red text).
- **User Intent:** Permanently discard a cancelled or test trip.
- **Screen Mockups:**
  - `trip-mobile-delete-confirmation.png`: Destructive confirmation dialog.
- **Actions & System Transitions:**
  1. Modal opens: "Xóa chuyến đi này?".
  2. User taps "Xóa chuyến đi" $\rightarrow$ sends `DELETE /trips/:id`.
  3. Backend cascades deletion of associated `Itinerary` and `ItineraryItem` rows.
  4. Returns to Trip List with confirmation snackbar.
- **Capability Reality:** **CURRENT** in NestJS (`DELETE /trips/:id`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T05: Trip Detail Navigation & Tab Switching
- **Entry Points:**
  - Tapping any trip card in Trip List or Home Screen.
- **User Intent:** View complete itinerary timeline, check budget status, review notes, or open map.
- **Screen Mockups:**
  - `trip-mobile-detail.png`: Populated itinerary with day tabs and timeline items.
  - `trip-mobile-detail-empty-r1.png`: Fresh trip without itinerary items, showing identical title and dual CTA choices.
  - `trip-desktop-detail.png`: 3-pane desktop workspace.
- **Title Consistency Rule:**
  - Both Top App Bar and Hero Card display the exact same `Trip.title` (e.g. `"Kỳ nghỉ Hạ Long 3N2Đ"`).
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips/:id`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T06: Manual Activity Creation (Add Itinerary Item)
- **Entry Points:**
  - Tapping "+ Thêm hoạt động" button below any day section in Trip Detail.
- **User Intent:** Manually add a specific spot, meal, flight, or custom task into the day's schedule.
- **Screen Mockups:**
  - `trip-mobile-add-activity-r1.png`: Bottom sheet modal mapping 1:1 to API contract.
- **Form Fields (Mapped 1:1 to `ItineraryItem`):**
  1. `dayNumber` [Required]: Dropdown selecting target day.
  2. `activity` [Required]: String name (e.g. "Bữa trưa Hải sản Bé Mặn").
  3. `placeId?` [Optional]: Search POI from verified PostGIS database.
  4. `startTime` / `endTime` [Optional]: Time pickers ("HH:mm").
  5. `estimatedCost` [Optional]: Integer VND.
  6. `transportMode` [Optional]: Choice chips (Đi bộ, Xe máy, Taxi / Grab, Ô tô riêng, Xe buýt).
  7. `notes` [Optional]: Textarea for notes and tips.
  8. Submit CTA: "Lưu hoạt động".
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/itinerary`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T07: Activity Editing
- **Entry Points:**
  - Tapping an existing activity card in the timeline or tapping item options (`⋮`) → "Chỉnh sửa".
- **User Intent:** Adjust start time, modify cost, update notes, or change the linked destination.
- **Screen Mockups:**
  - `trip-mobile-edit-activity.png`
- **Capability Status:** **DESIGN TARGET — NOT CURRENT IMPLEMENTATION**  
  *Technical Reality:* NestJS backend does not yet expose `PATCH /trips/:id/itinerary/:itemId` (only create and delete exist). Flutter UI currently allows viewing and deleting. The mockup represents the validated target for Sprint 02.

---

### FLOW T08: Activity Deletion
- **Entry Points:**
  - Swipe left on activity card in timeline or item menu → "Xóa hoạt động".
- **Screen Mockups:**
  - `trip-mobile-delete-activity.png`
- **Actions & System Transitions:**
  - User confirms prompt $\rightarrow$ sends `DELETE /trips/:id/itinerary/:itemId`.
  - Item animates out; day subtotal and overall budget decrement immediately.
- **Capability Reality:** **CURRENT** in NestJS (`DELETE /trips/:id/itinerary/:itemId`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T09: Timeline Reordering
- **Entry Points:**
  - Tapping "Sắp xếp lại" button in Trip Detail header.
- **Screen Mockups:**
  - `trip-mobile-reorder.png`
- **Capability Status:** **DESIGN TARGET — NOT CURRENT IMPLEMENTATION**  
  *Technical Reality:* Prisma schema has `orderIndex Int @default(0)`, but no batch reorder API endpoint exists in backend. The mockup defines the drag-and-drop interaction target for Sprint 02.

---

### FLOW T10: Add Place to Trip from Place Detail
- **Entry Points:**
  - Place Detail screen → Bottom CTA "Thêm vào chuyến đi".
- **Screen Mockups:**
  - `wandy-mobile-add-to-trip-action.png`
- **Capability Status:** **DESIGN TARGET — NOT CURRENT IMPLEMENTATION**  
  *Technical Reality:* Backend `POST /trips/:id/itinerary` supports `placeId`, but the Place Detail screen does not yet mount the Trip Picker sheet.

---

### FLOW T11: AI Planner Entry & Parameters Selection
- **Entry Points:**
  - Trip Detail screen → Banner "Lập lịch trình bằng AI".
  - Empty Trip Detail screen CTA button (`trip-mobile-detail-empty-r1.png`).
- **Screen Mockups:**
  - `trip-mobile-ai-entry.png`
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T12: AI Plan Generation & Live Feedback
- **Entry Points:**
  - Triggered after confirming AI Planner parameters.
- **Screen Mockups:**
  - `trip-mobile-ai-generating.png`
- **Liveness Invariants:**
  - **NO FAKE PERCENTAGE:** Uses real ticking elapsed timer `Đang xử lý (12s...)` and dynamic lifecycle steps.
- **Capability Reality:** **CURRENT** in Flutter and AI Service.

---

### FLOW T13: AI Plan Preview & Invariant Check
- **Entry Points:**
  - Generation completes successfully.
- **Screen Mockups:**
  - `trip-mobile-ai-preview.png`, `trip-desktop-ai-preview.png`
- **CRITICAL INVARIANT:**
  > **DATABASE MUTATION INVARIANT:**  
  > The AI Plan Preview step **MUST NEVER MUTATE THE DATABASE**.  
  > `POST /trips/:id/ai-plan` generates an ephemeral preview in memory. The user's stored trip in PostgreSQL/Prisma remains 100% untouched until the user explicitly taps "Áp dụng vào chuyến đi".
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter UI preview sheet.

---

### FLOW T14: AI Plan Overwrite Confirmation
- **Entry Points:**
  - User taps "Áp dụng vào chuyến đi" while trip has existing activities.
- **Screen Mockups:**
  - `trip-mobile-ai-overwrite.png`
- **Actions:** Prompts confirmation before setting `replaceExisting: true`.
- **Capability Reality:** **CURRENT** in NestJS and Flutter.

---

### FLOW T15: AI Plan Bulk Save / Transaction Commit
- **Entry Points:**
  - Confirmation from Flow T14.
- **Screen Mockups:**
  - `trip-mobile-ai-success.png`
- **Actions:** Sends `POST /trips/:id/itinerary/bulk` in a Prisma transaction, updates `Trip.status = PLANNED`.
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/itinerary/bulk`) and Flutter.

---

### FLOW T16: Budget Tracking & Over-budget Alerting
- **Entry Points:**
  - Trip Detail bottom bar, Budget tab, Desktop Right Sidebar.
- **Screen Mockups:**
  - `trip-mobile-budget.png` (Safe < 85%)
  - `trip-mobile-budget-warning.png` (Warning 85% - 100%)
  - `trip-mobile-budget-over.png` (Over budget > 100%)
  - `trip-desktop-detail-budget.png`
- **Capability Reality:** **CURRENT (UI Mockup) / PARTIAL (Backend compute)**.

---

## 3. CANCELLED Status Business Rule (UX Decision & Future Contract)

```
============================================================
CANCELLED STATUS BUSINESS RULE & CONTRACT SPECIFICATION
============================================================

TECHNICAL AUDIT (CURRENT REALITY):
1. Prisma Schema: `TripStatus` enum contains `CANCELLED`.
2. Backend API: `findAll` returns cancelled trips (`deletedAt: null`).
3. Flutter App: `_buildStatusChip` lacks a CANCELLED case and falls
   through to default ('Ban nhap'). No cancel button exists in UI.
4. CLASSIFICATION: UX DECISION REQUIRED / FUTURE CONTRACT.

LOCKED DESIGN TARGET SPECIFICATION (FUTURE CONTRACT):
1. List Category: Filtered strictly into the "Đã kết thúc" tab
   (since cancelled trips are no longer active or upcoming).
2. Badge Representation:
   - Label: `ĐÃ HỦY`
   - Token: Background `#FEE2E2`, Text `#DC2626`, Border `#FECACA`.
3. Editability: Strictly READ-ONLY.
   - Itinerary timeline items cannot be added, edited, or reordered.
   - Budget tracking displays historical spending at the time of cancellation.
4. Reopening Capability:
   - A More Menu action "Khôi phục chuyến đi" allows transitioning
     status back to `DRAFT` or `PLANNED` (requires dedicated backend endpoint).
5. Deletion Allowed: YES.
   - Hard/soft deletion via `DELETE /trips/:id` remains available.
```

---

## 4. Global Navigation Reconciliation

| Aspect | Technical Reality |
| :--- | :--- |
| **Current Implementation** | `apps/mobile/lib/core/router/app_router.dart` implements a 5-tab `NavigationBar`:<br>1. `/` (`Trang chủ` / `Khám phá`)<br>2. `/map` (`Bản đồ`)<br>3. `/ai` (`Wandy AI`)<br>4. `/safety` (`An toàn`)<br>5. `/trips` (`Chuyến đi`) |
| **Design Specification** | `docs/design/gomate-ux-architecture-v1.md` Section 3 establishes 5 tabs. |
| **Final Design Decision** | **5-Tab Architecture is confirmed as the authoritative standard.** All root list mockups (`trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`, `trip-mobile-list-empty-r2.png`, `trip-mobile-list-loading-r2.png`, `trip-mobile-list-error-r2.png`) render 5 tabs with Tab 5 (`Chuyến đi`) active. |

---

## 5. Watermark Evidence Notice

> [!NOTE]
> **WATERMARK IS EVIDENCE-ONLY, NOT PRODUCTION UI**  
> The watermark string `VISUAL DEMO DATA — NOT PRODUCTION DATA` included in mockups is an evidence-only marker designed to prevent any misinterpretation of mockups as live database output during academic or professional reviews. It does not exist in production code or runtime Flutter widgets.
