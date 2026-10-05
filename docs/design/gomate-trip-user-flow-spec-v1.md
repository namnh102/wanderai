# GoMate Trip Management — User Flow Specification V1

**Status:** APPROVED USER FLOW SPECIFICATION (REVISION R1 LOCKED)  
**Tasks:** TASK 08.2.3.5 & TASK 08.2.3.5-R1 (UX Contract & Visual Consistency Correction)  
**Applies to:** Mobile App (iOS / Android / Flutter Web Mobile) & Desktop Web (1440px)  
**Covers:** Core Flows T01 through T16  
**Source of Truth:** GoMate Master UX Plan V2, UX Architecture V1, Prisma Schema, NestJS Trips Module, Flutter Router & Trips Feature  

---

## 1. Flow Matrix Overview

| Flow ID | Flow Name | Primary Screen Mockup | Core Interaction | Capability Status |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Trip Discovery & List Navigation | `trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`, `trip-desktop-list.png` | Bottom Tab 5 tap, semantic tabs (Hiện tại & sắp tới / Đã kết thúc / Bản nháp), search | **CURRENT** |
| **T02** | Trip Creation Flow | `trip-mobile-create-r1.png`, `trip-mobile-create-validation.png`, `trip-desktop-create.png` | Tap "+ Tạo chuyến đi", fill Title, Destination, Dates, Budget, Style; CTA: "Tạo chuyến đi" | **CURRENT** |
| **T03** | Trip Edit Flow | `trip-mobile-edit.png` | More Menu → Chỉnh sửa thông tin, update dates, budget, title | **CURRENT** |
| **T04** | Trip Deletion Flow | `trip-mobile-delete-confirmation.png` | More Menu → Xóa chuyến đi, destructive modal confirmation | **CURRENT** |
| **T05** | Trip Detail & Navigation | `trip-mobile-detail.png`, `trip-mobile-detail-empty-r1.png`, `trip-desktop-detail.png` | Tap trip card, browse hero metadata, identical title, day selector tabs | **CURRENT** |
| **T06** | Manual Activity Creation | `trip-mobile-add-activity-r1.png` | Tap "+ Thêm hoạt động", bottom sheet mapping 1:1 to API (activity, placeId?, time, cost, transportMode, notes) | **CURRENT** |
| **T07** | Activity Editing | `trip-mobile-edit-activity.png` | Tap item card → edit details, time, cost, notes | **FUTURE / PARTIAL** |
| **T08** | Activity Deletion | `trip-mobile-delete-activity.png` | Swipe or item menu → Xóa hoạt động, instant budget/timeline update | **CURRENT** |
| **T09** | Timeline Reordering | `trip-mobile-reorder.png` | Tap "Sắp xếp lại", drag handles, persist updated sequence | **FUTURE** |
| **T10** | Add Place from Place Detail | `wandy-mobile-add-to-trip-action.png` | From Map / Place Detail, tap "Thêm vào chuyến đi", pick trip & day | **PARTIAL** |
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
  - `trip-mobile-list-upcoming-r1.png`: Displays ongoing & upcoming trips (e.g. "Đà Nẵng 4N3Đ").
  - `trip-mobile-list-past-r1.png`: Displays completed trips ("Hà Nội Mùa Thu 2025").
  - `trip-mobile-list-empty.png`: First-time user view with travel illustration and CTA.
  - `trip-mobile-list-loading.png`: Shimmer skeleton loading state (< 300ms).
  - `trip-mobile-list-error.png`: Offline or network failure state with "Thử lại" button.
  - `trip-desktop-list.png`: 3-column responsive card grid on desktop (1440px).
- **UX & Business Logic Corrections (R1):**
  1. **Tab Semantics Corrected:**
     - Tab 1: **"Hiện tại & sắp tới"** (Active trips `ONGOING` and scheduled future trips `PLANNED` / `DRAFT`). This completely resolves the semantic flaw where an active trip with badge `ĐANG DIỄN RA` was placed under a purely "Sắp tới" tab.
     - Tab 2: **"Đã kết thúc"** (Trips with status `COMPLETED` or `endDate < today`). Standardized terminology replaces informal "Đã qua" / "Đã đi".
     - Tab 3: **"Bản nháp"** (Trips with status `DRAFT` and no finalized itinerary).
  2. **Single Primary Action Principle:**
     - The top app bar features a single primary `+` button in the top right.
     - The duplicate Floating Action Button (FAB) at the bottom right is **REMOVED** to maintain interface hierarchy and prevent visual clutter.
  3. **Global Navigation Alignment:**
     - Renders the full 5-tab bottom navigation bar (`Khám phá`, `Bản đồ`, `Wandy AI`, `An toàn`, `Chuyến đi` [Active]), matching `apps/mobile/lib/core/router/app_router.dart`.
- **Actions & System Transitions:**
  1. System checks authentication token; fetches `GET /trips`.
  2. Client filters list into tabs based on status and dates.
  3. Search query filters list locally by `title` or `destination`.
- **Loading State:** 3 pulsing skeleton cards matching trip card proportions.
- **Empty State:** Shows friendly GoMate luggage icon, text "Bạn chưa có chuyến đi nào sắp tới", and prominent "+ Tạo chuyến đi ngay" CTA.
- **Error State:** Network error banner, retains cached data if available; displays explicit error message and retry button.
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips`) and Flutter (`trip_list_screen.dart`).

---

### FLOW T02: Trip Creation Flow
- **Entry Points:**
  - Header `+` button in Trip List screen (`trip-mobile-list-upcoming-r1.png`).
  - Wandy Copilot recommendation or Planner button from Home.
- **User Intent:** Initialize a new travel itinerary with high-level constraints.
- **Screen Mockups:**
  - `trip-mobile-create-r1.png`: Full creation form on mobile with standardized fields and CTA.
  - `trip-mobile-create-validation.png`: Client-side validation errors (empty title, invalid date range).
  - `trip-desktop-create.png`: Centered modal dialog on desktop workspace.
- **UX & Contract Corrections (R1):**
  1. **CTA Decoupling ("Tạo chuyến đi"):**
     - The primary submit button is strictly labeled **"Tạo chuyến đi"** (NOT "Tạo chuyến đi & Lên lịch").
     - **Decoupled Lifecycle:** `POST /trips` only creates the trip entity. It does NOT automatically trigger `POST /trips/:id/ai-plan`.
     - After successful creation, user lands on the empty Trip Detail screen (`trip-mobile-detail-empty-r1.png`), where they explicitly choose between "Lập lịch trình bằng AI" or "Tự lên lịch thủ công".
  2. **Field Persistence Accuracy (No Interests in Trip Create):**
     - Verified `CreateTripDto` & Prisma `Trip` creation fields: `title`, `destinationId` / `destination`, `startDate`, `endDate`, `totalBudget`, `currency`, `travelStyle`.
     - The "Sở thích du lịch" (Interests) field is **REMOVED** from the initial Trip Creation UI. Interests are conversational prompt parameters passed during AI Planner execution, not persistent trip creation requirements.
  3. **Standardized Travel Style Labels:**
     - The 4 enum options for `TravelStyle` are locked to single canonical Vietnamese labels:
       - `BACKPACKER` → **Phượt** (Tự do, khám phá)
       - `BUDGET` → **Tiết kiệm** (Tối ưu chi phí)
       - `COMFORT` → **Thoải mái** (Cân bằng, tiện nghi — replaces ambiguous "Tiêu chuẩn")
       - `LUXURY` → **Sang trọng** (Trải nghiệm cao cấp — replaces "Nghỉ dưỡng")
- **Form Fields & Validation Rules:**
  1. **Tên chuyến đi (Title)** [Required]: Min 3 characters, max 100 characters. e.g. "Khám phá Đà Nẵng mùa thu".
  2. **Điểm đến (Destination)** [Required]: Text input / autocomplete.
  3. **Thời gian (Start & End Date)** [Required]:
     - `startDate >= today` (or past date permitted for logbooks).
     - `endDate >= startDate`.
     - System automatically computes number of days: `days = (endDate - startDate).inDays + 1`.
  4. **Ngân sách dự kiến (Estimated Budget)** [Optional]: Positive integer in VND. Default: 0.
  5. **Phong cách du lịch (Travel Style)** [Optional]: Choice chip: `Phượt`, `Tiết kiệm`, `Thoải mái`, `Sang trọng`.
- **Actions & System Transitions:**
  1. User fills fields and taps "Tạo chuyến đi".
  2. Client validates inputs; if invalid, displays inline red helper text under faulty fields (`trip-mobile-create-validation.png`).
  3. If valid, sends `POST /trips` payload:
     ```json
     {
       "title": "Khám phá Đà Nẵng mùa thu",
       "destination": "Đà Nẵng",
       "startDate": "2026-10-15T00:00:00.000Z",
       "endDate": "2026-10-18T23:59:59.000Z",
       "totalBudget": 8000000,
       "currency": "VND",
       "travelStyle": "COMFORT"
     }
     ```
  4. On HTTP 201 Created: Navigates directly into the newly created Trip Detail screen (`trip-mobile-detail-empty-r1.png`).
- **Cancel / Back:** Tapping "Hủy" or back arrow prompts confirmation if any field is dirty ("Hủy bỏ thay đổi?").
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips`) and Flutter (`trip_form_screen.dart`).

---

### FLOW T03: Trip Edit Flow
- **Entry Points:**
  - Trip Detail screen → Top App Bar More menu (`⋮`) → "Chỉnh sửa thông tin chuyến đi".
- **User Intent:** Update dates, budget, destination, or title of an existing trip.
- **Screen Mockups:**
  - `trip-mobile-edit.png`: Edit form pre-populated with current trip attributes.
- **Actions & Invariant Rules:**
  1. Pre-fills existing values from trip entity.
  2. **Date Shrink Invariant Rule:** If user reduces the date range (e.g. from 4 days to 3 days) and activities exist on Day 4:
     - Warning modal: "Thu hẹp thời gian sẽ ảnh hưởng đến các hoạt động trong ngày bị cắt. Bạn có chắc muốn tiếp tục?"
  3. User submits changes via `PATCH /trips/:id`.
  4. On HTTP 200 OK: Toast "Cập nhật chuyến đi thành công", returns to Trip Detail with fresh data.
- **Capability Reality:** **CURRENT** in NestJS (`PATCH /trips/:id`) and Flutter (`trip_form_screen.dart?edit=true`).

---

### FLOW T04: Trip Deletion Flow
- **Entry Points:**
  - Trip Detail screen → Top App Bar More menu (`⋮`) → "Xóa chuyến đi" (red text).
- **User Intent:** Permanently discard a cancelled or test trip.
- **Screen Mockups:**
  - `trip-mobile-delete-confirmation.png`: Destructive confirmation dialog.
- **Actions & System Transitions:**
  1. Modal opens with title: "Xóa chuyến đi này?".
  2. Body text: "Hành động này không thể hoàn tác. Toàn bộ lịch trình chi tiết và dự toán chi phí của chuyến đi sẽ bị xóa vĩnh viễn."
  3. User taps "Hủy" → closes modal, no change.
  4. User taps "Xóa chuyến đi" (destructive red button) → sends `DELETE /trips/:id`.
  5. Backend cascades deletion of associated `Itinerary` and `ItineraryItem` rows.
  6. On success: Returns to Trip List, displays snackbar "Đã xóa chuyến đi thành công".
- **Capability Reality:** **CURRENT** in NestJS (`DELETE /trips/:id`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T05: Trip Detail Navigation & Tab Switching
- **Entry Points:**
  - Tapping any trip card in Trip List or Home Screen.
- **User Intent:** View complete itinerary timeline, check budget status, review notes, or open map.
- **Screen Mockups:**
  - `trip-mobile-detail.png`: Populated itinerary with day tabs and timeline items.
  - `trip-mobile-detail-empty-r1.png`: Fresh trip without itinerary items, showing identical title and dual CTA choices.
  - `trip-desktop-detail.png`: 3-pane desktop workspace (Trip specs on left, Timeline in center, Budget & AI insight on right).
- **UX & Contract Corrections (R1):**
  1. **Title Consistency Rule:**
     - The Top App Bar title and the Hero Card title **MUST ALWAYS BE IDENTICAL**, bound to `Trip.title`.
     - In `trip-mobile-detail-empty-r1.png`, both App Bar and Hero display strictly: `"Kỳ nghỉ Hạ Long 3N2Đ"`.
  2. **Clear Empty State Options:**
     - Option 1 (Recommended): "Lập lịch trình thông minh với Wandy AI" CTA banner with sparkles button.
     - Option 2: "Tự lên lịch thủ công" card with "+ Thêm" button.
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips/:id`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T06: Manual Activity Creation (Add Itinerary Item)
- **Entry Points:**
  - Tapping "+ Thêm hoạt động" button below any day section in Trip Detail.
- **User Intent:** Manually add a specific spot, meal, flight, or custom task into the day's schedule.
- **Screen Mockups:**
  - `trip-mobile-add-activity-r1.png`: Redesigned bottom sheet modal mapping 1:1 to API contract.
- **UX & Contract Corrections (R1):**
  - **Separation of Activity Name and Linked Place:**
    - `activity` (Tên hoạt động) is a distinct required string field (e.g. "Bữa trưa Hải sản Bé Mặn").
    - `placeId` (Địa điểm liên kết) is an optional separate search/selection field linking to verified database places (`Place` model).
  - **Explicit Transport Mode:** Added `transportMode` selector chips (`walk`, `motorbike`, `taxi`, `car`, `bus`).
- **Form Fields (Mapped 1:1 to API):**
  1. **Ngày lịch trình (`dayNumber`)** [Required]: Dropdown selecting target day (defaults to currently viewed day).
  2. **Tên hoạt động (`activity`)** [Required]: String e.g. "Bữa trưa Hải sản Bé Mặn".
  3. **Địa điểm liên kết (`placeId?`)** [Optional]: Search POI from verified PostGIS database.
  4. **Giờ bắt đầu (`startTime`) / Giờ kết thúc (`endTime`)** [Optional]: Time pickers (e.g. `11:30 - 13:00`).
  5. **Chi phí ước tính (`estimatedCost`)** [Optional]: Integer in VND (e.g. `800.000 đ`).
  6. **Phương tiện di chuyển (`transportMode`)** [Optional]: Choice chips (Đi bộ / Xe máy / Taxi-Grab / Ô tô / Xe buýt).
  7. **Ghi chú (`notes`)** [Optional]: Textarea for notes and tips.
- **Actions & System Transitions:**
  1. User fills fields and taps "Lưu hoạt động".
  2. Client sends `POST /trips/:id/itinerary` with payload:
     ```json
     {
       "dayNumber": 1,
       "placeId": "123e4567-e89b-12d3-a456-426614174000",
       "activity": "Bữa trưa Hải sản Bé Mặn",
       "startTime": "11:30",
       "endTime": "13:00",
       "estimatedCost": 800000,
       "transportMode": "taxi",
       "notes": "Nên đặt bàn trước nếu đi cuối tuần, chọn bàn sát lan can nhìn ra biển."
     }
     ```
  3. On HTTP 201 Created: Timeline refreshes; budget total increments automatically by 800.000 đ.
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/itinerary`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T07: Activity Editing
- **Entry Points:**
  - Tapping an existing activity card in the timeline or tapping item options (`⋮`) → "Chỉnh sửa".
- **User Intent:** Adjust start time, modify cost, update notes, or change the linked destination.
- **Screen Mockups:**
  - `trip-mobile-edit-activity.png`: Modal pre-populated with activity data.
- **Capability Reality:** **FUTURE / PARTIAL** (Backend lacks `PATCH /trips/:id/itinerary/:itemId`).

---

### FLOW T08: Activity Deletion
- **Entry Points:**
  - Swipe left on activity card in timeline or item menu → "Xóa hoạt động".
- **User Intent:** Remove an unwanted activity from the schedule.
- **Screen Mockups:**
  - `trip-mobile-delete-activity.png`: Slide action and confirmation dialog.
- **Actions & System Transitions:**
  1. Confirmation prompt: "Xóa hoạt động khỏi lịch trình?".
  2. User confirms → Client sends `DELETE /trips/:id/itinerary/:itemId`.
  3. On HTTP 200 OK: Item animates out of timeline; remaining items adjust lines; total budget decrements.
- **Capability Reality:** **CURRENT** in NestJS (`DELETE /trips/:id/itinerary/:itemId`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T09: Timeline Reordering
- **Entry Points:**
  - Tapping "Sắp xếp lại" button in Trip Detail header.
- **User Intent:** Change sequence of activities within a day.
- **Screen Mockups:**
  - `trip-mobile-reorder.png`: Drag handles shown on each activity card.
- **Capability Reality:** **FUTURE** (`orderIndex` exists in DB, batch API endpoint pending).

---

### FLOW T10: Add Place to Trip from Place Detail
- **Entry Points:**
  - Place Detail screen → Bottom CTA "Thêm vào chuyến đi".
- **Screen Mockups:**
  - `wandy-mobile-add-to-trip-action.png`: Bottom sheet trip & day selector.
- **Capability Reality:** **PARTIAL** (Backend API exists; UI modal on Place Detail pending).

---

### FLOW T11: AI Planner Entry & Parameters Selection
- **Entry Points:**
  - Trip Detail screen → Banner "Lập lịch trình bằng AI".
  - Empty Trip Detail screen CTA button (`trip-mobile-detail-empty-r1.png`).
- **User Intent:** Delegate itinerary planning to Wandy AI.
- **Screen Mockups:**
  - `trip-mobile-ai-entry.png`: Modal showing trip constraints and optional custom prompt input.
- **Actions & System Transitions:**
  1. Dialog presents auto-filled parameters (Điểm đến, Thời gian, Ngân sách, Phong cách).
  2. Optional prompt input field: "Ghi chú thêm cho AI...".
  3. User taps "Bắt đầu tạo lịch trình".
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T12: AI Plan Generation & Live Feedback
- **Entry Points:**
  - Triggered immediately after tapping "Bắt đầu tạo lịch trình" in Flow T11.
- **Screen Mockups:**
  - `trip-mobile-ai-generating.png`: Dedicated liveness view with Wandy animated mascot, elapsed timer, and dynamic status messages.
- **Liveness & Progress Design Rules:**
  - **NO FAKE PERCENTAGE BARS:** Strictly no arbitrary progress percentages (e.g. "45%").
  - **Live Elapsed Timer:** Real clock timer display `Đang xử lý (12s...)`.
  - **Dynamic Step Cues:** Real lifecycle steps: *Phân tích địa điểm... → Tối ưu lộ trình... → Cân đối ngân sách...*.
- **Capability Reality:** **CURRENT** in Flutter and AI Service.

---

### FLOW T13: AI Plan Preview & Invariant Check
- **Entry Points:**
  - Generation completes successfully from Flow T12.
- **Screen Mockups:**
  - `trip-mobile-ai-preview.png`, `trip-desktop-ai-preview.png`.
- **CRITICAL INVARIANT:**
  > **DATABASE MUTATION INVARIANT:**  
  > The AI Plan Preview step **MUST NEVER MUTATE THE DATABASE**.  
  > Calling `POST /trips/:id/ai-plan` generates an ephemeral preview in memory. The user's stored trip in PostgreSQL/Prisma remains 100% untouched until the user explicitly taps "Áp dụng vào chuyến đi".
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter UI preview sheet.

---

### FLOW T14: AI Plan Overwrite Confirmation
- **Entry Points:**
  - User taps "Áp dụng vào chuyến đi" while the trip ALREADY contains manual itinerary items.
- **Screen Mockups:**
  - `trip-mobile-ai-overwrite.png`: Safety warning dialog.
- **Actions & System Transitions:**
  1. System checks: `existingItemCount > 0`.
  2. Dialog prompts confirmation: "Thay thế lịch trình hiện tại? Thao tác sẽ xóa các hoạt động cũ."
  3. User confirms → Proceeds to Flow T15 commit with `replaceExisting: true`.
- **Capability Reality:** **CURRENT** in NestJS (`replaceExisting` boolean parameter) and Flutter.

---

### FLOW T15: AI Plan Bulk Save / Transaction Commit
- **Entry Points:**
  - Confirmation from Flow T14 (or direct commit if trip was empty).
- **Screen Mockups:**
  - `trip-mobile-ai-success.png`: Success toast and auto-transition to updated Trip Detail.
- **Actions & Database Transaction:**
  1. Client sends `POST /trips/:id/itinerary/bulk` payload containing all items and `replaceExisting: true`.
  2. Backend wraps operation in a Prisma transaction (`$transaction`).
  3. Updates `Trip` record: `status = PLANNED`.
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/itinerary/bulk`) and Flutter.

---

### FLOW T16: Budget Tracking & Over-budget Alerting
- **Entry Points:**
  - Accessible via Trip Detail bottom bar, Budget tab, or Desktop Right Sidebar.
- **Screen Mockups:**
  - `trip-mobile-budget.png`: Safe state (< 85% allocated, teal indicator).
  - `trip-mobile-budget-warning.png`: Warning state (85% - 100% allocated, amber indicator).
  - `trip-mobile-budget-over.png`: Over-budget state (> 100% allocated, crimson red alert).
  - `trip-desktop-detail-budget.png`: In-depth desktop breakdown with category allocation.
- **Budget Threshold Invariants:**
  1. **Safe ($0\% - 85\%$):** Primary Teal `#0F766E`, message "Ngân sách an toàn".
  2. **Near Limit ($85\% - 100\%$):** Amber Warning `#F59E0B`, message "Tiệm cận hạn mức".
  3. **Over Budget ($> 100\%$):** Destructive Red `#EF4444`, message "Vượt ngân sách".
- **Capability Reality:** **CURRENT (UI Mockup) / PARTIAL (Backend compute)**.

---

## 3. Global Navigation Reconciliation

| Aspect | Technical Reality |
| :--- | :--- |
| **Current Implementation** | `apps/mobile/lib/core/router/app_router.dart` implements a 5-tab `NavigationBar`:<br>1. `/` (`Trang chủ` / `Khám phá`)<br>2. `/map` (`Bản đồ`)<br>3. `/ai` (`Wandy AI`)<br>4. `/safety` (`An toàn`)<br>5. `/trips` (`Chuyến đi`) |
| **Design Specification** | `docs/design/gomate-ux-architecture-v1.md` Section 3 specifies 5 tabs (Home, Map, Wandy AI, Safety, Trips). |
| **Final Design Decision** | **5-Tab Architecture is confirmed as the authoritative standard.** All mobile mockups rendering the persistent root navigation (`trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`) display the full 5 tabs with Tab 5 (`Chuyến đi`) active. |

---

## 4. Watermark Evidence Notice

> [!NOTE]
> **WATERMARK IS EVIDENCE-ONLY, NOT PRODUCTION UI**  
> The watermark string `VISUAL DEMO DATA — NOT PRODUCTION DATA` included at the base of mockups is an evidence-only marker designed to prevent any misinterpretation of mockups as live database output during academic or professional reviews. It does not exist in production code or runtime Flutter widgets.
