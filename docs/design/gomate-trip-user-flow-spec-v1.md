# GoMate Trip Management — User Flow Specification V1

**Status:** APPROVED USER FLOW SPECIFICATION  
**Task:** TASK 08.2.3.5 — GOMATE TRIP MANAGEMENT VISUAL MOCKUP V1 + UX / BUSINESS FLOW DESIGN  
**Applies to:** Mobile App (iOS / Android / Flutter Web Mobile) & Desktop Web (1440px)  
**Covers:** Core Flows T01 through T16  
**Source of Truth:** GoMate Master UX Plan V2, UX Architecture V1, Prisma Schema, NestJS Trips Module, Flutter Trips Feature  

---

## 1. Flow Matrix Overview

| Flow ID | Flow Name | Primary Screen Mockup | Core Interaction | Capability Status |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Trip Discovery & List Navigation | `trip-mobile-list-upcoming.png`, `trip-mobile-list-past.png`, `trip-desktop-list.png` | Bottom Tab 4 tap, filter tabs (Sắp tới / Đã kết thúc / Nháp), search | **CURRENT** |
| **T02** | Trip Creation Flow | `trip-mobile-create.png`, `trip-mobile-create-validation.png`, `trip-desktop-create.png` | Tap "+ Tạo chuyến đi", fill Title, Destination, Dates, Budget, Style | **CURRENT** |
| **T03** | Trip Edit Flow | `trip-mobile-edit.png` | More Menu → Chỉnh sửa thông tin, update dates, budget, title | **CURRENT** |
| **T04** | Trip Deletion Flow | `trip-mobile-delete-confirmation.png` | More Menu → Xóa chuyến đi, destructive modal confirmation | **CURRENT** |
| **T05** | Trip Detail & Navigation | `trip-mobile-detail.png`, `trip-mobile-detail-empty.png`, `trip-desktop-detail.png` | Tap trip card, browse hero metadata, day selector tabs, timeline | **CURRENT** |
| **T06** | Manual Activity Creation | `trip-mobile-add-activity.png` | Tap "+ Thêm hoạt động", select place/custom, time range, cost, notes | **CURRENT** |
| **T07** | Activity Editing | `trip-mobile-edit-activity.png` | Tap item card → edit details, time, cost, notes | **FUTURE / PARTIAL** |
| **T08** | Activity Deletion | `trip-mobile-delete-activity.png` | Swipe or item menu → Xóa hoạt động, instant budget/timeline update | **CURRENT** |
| **T09** | Timeline Reordering | `trip-mobile-reorder.png` | Tap "Sắp xếp lại", drag handles, persist updated sequence | **FUTURE** |
| **T10** | Add Place from Place Detail | `wandy-mobile-add-to-trip-action.png` | From Map / Place Detail, tap "Thêm vào chuyến đi", pick trip & day | **PARTIAL** |
| **T11** | AI Planner Entry & Parameters | `trip-mobile-ai-entry.png` | Tap "Lập lịch trình bằng AI", review prompt, style, budget, days | **CURRENT** |
| **T12** | AI Plan Generation Feedback | `trip-mobile-ai-generating.png` | Active liveness indicator, elapsed timer (~20-40s), progress steps | **CURRENT** |
| **T13** | AI Plan Preview & Invariant Check | `trip-mobile-ai-preview.png`, `trip-desktop-ai-preview.png` | Inspect proposed days, variance, items; **NO DB WRITE** yet | **CURRENT** |
| **T14** | AI Plan Overwrite Confirmation | `trip-mobile-ai-overwrite.png` | Modal warning if trip has existing activities (`replaceExisting`) | **CURRENT** |
| **T15** | AI Plan Bulk Save / Commit | `trip-mobile-ai-success.png` | Tap "Áp dụng vào chuyến đi", atomic transaction, status → PLANNED | **CURRENT** |
| **T16** | Budget Tracking & Over-budget Alert | `trip-mobile-budget.png`, `trip-mobile-budget-warning.png`, `trip-mobile-budget-over.png`, `trip-desktop-detail-budget.png` | Real-time budget calculation, percentage tracks, threshold warnings | **CURRENT (UI Mockup) / PARTIAL (Backend compute)** |

---

## 2. Detailed Flow Specifications

### FLOW T01: Trip Discovery & List Navigation
- **Entry Points:**
  - Mobile: Tapping Tab 4 (`Chuyến đi`) in the bottom navigation bar.
  - Desktop: Clicking `Chuyến đi` in the top navigation bar.
  - Home Screen: Tapping "Xem tất cả chuyến đi" in the Home dashboard.
- **User Intent:** View current travel commitments, review past travel memories, or locate a trip to edit.
- **Screen Mockups:**
  - `trip-mobile-list-upcoming.png`: Displays active & upcoming trips (e.g. "Đà Nẵng 4N3Đ").
  - `trip-mobile-list-past.png`: Displays completed trips ("Hà Nội mùa thu 2025").
  - `trip-mobile-list-empty.png`: First-time user view with travel illustration and CTA.
  - `trip-mobile-list-loading.png`: Shimmer skeleton loading state (< 300ms).
  - `trip-mobile-list-error.png`: Offline or network failure state with "Thử lại" button.
  - `trip-desktop-list.png`: 3-column responsive card grid on desktop (1440px).
- **Actions & System Transitions:**
  1. System checks authentication token; fetches `GET /trips`.
  2. Trips are split on client into:
     - **Sắp tới (Upcoming):** Trips where `endDate >= today` or status is `PLANNED` / `ONGOING` / `DRAFT`.
     - **Đã kết thúc (Past):** Trips where `endDate < today` or status is `COMPLETED`.
     - **Bản nháp (Draft):** Trips with status `DRAFT` (no finalized activities).
  3. Search query filters list locally by `title` or `destination`.
- **Loading State:** 3 pulsing skeleton cards matching trip card proportions.
- **Empty State:** Shows friendly GoMate luggage icon, text "Bạn chưa có chuyến đi nào sắp tới", and prominent "+ Tạo chuyến đi ngay" CTA.
- **Error State:** Network error banner, retains cached data if available; displays explicit error message and retry button.
- **Cancel / Back:** Tapping other tabs switches view immediately without losing list scroll position.
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips`) and Flutter (`trip_list_screen.dart`).

---

### FLOW T02: Trip Creation Flow
- **Entry Points:**
  - Floating Action Button (FAB) or Header "+ Tạo chuyến đi" in Trip List screen.
  - Wandy Copilot recommendation or Planner button from Home.
- **User Intent:** Initialize a new travel itinerary with high-level constraints.
- **Screen Mockups:**
  - `trip-mobile-create.png`: Full creation form on mobile.
  - `trip-mobile-create-validation.png`: Client-side validation errors (empty title, invalid date range).
  - `trip-desktop-create.png`: Centered modal dialog on desktop workspace.
- **Form Fields & Validation Rules:**
  1. **Tên chuyến đi (Title)** [Required]: Min 3 characters, max 100 characters. e.g. "Khám phá Đà Nẵng mùa thu".
  2. **Điểm đến (Destination)** [Required]: Autocomplete / text input. Validated against known destination scope.
  3. **Thời gian (Start & End Date)** [Required]:
     - `startDate >= today` (or past date permitted for logbooks).
     - `endDate >= startDate`.
     - System automatically computes number of days: `days = (endDate - startDate).inDays + 1`.
  4. **Ngân sách dự kiến (Estimated Budget)** [Optional]: Positive integer in VND. Default: 0.
  5. **Phong cách du lịch (Travel Style)** [Optional]: Choice chip: `Phượt (BACKPACKER)`, `Tiết kiệm (BUDGET)`, `Tiêu chuẩn (COMFORT)`, `Nghỉ dưỡng (LUXURY)`.
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
       "budget": 8000000,
       "travelStyle": "COMFORT"
     }
     ```
  4. On HTTP 201 Created: Navigates directly into the newly created Trip Detail screen (`trip-mobile-detail-empty.png`).
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
  3. User submits changes via `PUT /trips/:id` (or `PATCH /trips/:id`).
  4. On HTTP 200 OK: Toast "Cập nhật chuyến đi thành công", returns to Trip Detail with fresh data.
- **Capability Reality:** **CURRENT** in NestJS (`PATCH /trips/:id`) and Flutter (`trip_form_screen.dart?edit=true`).

---

### FLOW T04: Trip Deletion Flow
- **Entry Points:**
  - Trip Detail screen → Top App Bar More menu (`⋮`) → "Xóa chuyến đi" (red text).
  - Trip List item swipe-to-delete action.
- **User Intent:** Permanently discard a cancelled or test trip.
- **Screen Mockups:**
  - `trip-mobile-delete-confirmation.png`: Destructive confirmation dialog.
- **Actions & System Transitions:**
  1. Modal opens with title: "Xóa chuyến đi này?".
  2. Body text: "Hành động này không thể hoàn tác. Toàn bộ lịch trình chi tiết và dự toán chi phí của chuyến đi 'Đà Nẵng 4N3Đ' sẽ bị xóa vĩnh viễn."
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
  - `trip-mobile-detail-empty.png`: Fresh trip without itinerary items, showing AI Planner CTA card.
  - `trip-desktop-detail.png`: 3-pane desktop workspace (Trip specs on left, Timeline in center, Budget & AI insight on right).
- **Key UI Sections:**
  1. **Hero Card:** Destination banner gradient, trip title, date range, status badge (`ĐÃ LÊN LỊCH` / `DRAFT`), AI generated badge, quick stat strip (Số ngày, Số hoạt động, Tổng dự toán).
  2. **AI Planner CTA Banner:** Quick button "Tạo lịch trình bằng AI trong 30 giây" (shown when trip is sparse or empty).
  3. **Day Selector Tabs:** Horizontal scrollable pills: "Tất cả ngày", "Ngày 1 (15/10)", "Ngày 2 (16/10)", "Ngày 3 (17/10)", "Ngày 4 (18/10)".
  4. **Timeline Activity Stream:** Grouped by day, ordered by `orderIndex` and `startTime`.
  5. **Sticky Bottom Bar:** Real-time budget progress (`6.450.000 / 8.000.000 đ`) and "Xem Bản đồ" action button.
- **Capability Reality:** **CURRENT** in NestJS (`GET /trips/:id`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T06: Manual Activity Creation (Add Itinerary Item)
- **Entry Points:**
  - Tapping "+ Thêm hoạt động" button below any day section in Trip Detail.
- **User Intent:** Manually add a specific spot, meal, flight, or custom task into the day's schedule.
- **Screen Mockups:**
  - `trip-mobile-add-activity.png`: Bottom sheet modal with activity details.
- **Form Fields:**
  1. **Ngày (Day)**: Dropdown selecting target day (defaults to currently viewed day).
  2. **Tên hoạt động (Activity Title)** [Required]: e.g. "Bữa trưa Hải sản Bé Mặn".
  3. **Địa điểm liên kết (Linked Place)** [Optional]: Search POI from database (PostGIS verified places).
  4. **Thời gian bắt đầu / kết thúc (Start & End Time)**: Time pickers (e.g. `11:30 - 13:00`).
  5. **Chi phí ước tính (Estimated Cost)**: Currency input in VND (e.g. `800.000 đ`).
  6. **Ghi chú & Phương tiện di chuyển**: Notes text area, transport mode selector (Đi bộ, Xe máy, Taxi/Grab, Ô tô).
- **Actions & System Transitions:**
  1. User fills fields and taps "Lưu hoạt động".
  2. Client sends `POST /trips/:id/itinerary` with payload:
     ```json
     {
       "dayNumber": 1,
       "placeId": "poi_hcm_042",
       "activity": "Bữa trưa Hải sản Bé Mặn",
       "startTime": "11:30",
       "endTime": "13:00",
       "estimatedCost": 800000,
       "notes": "Đặt bàn trước nếu đi cuối tuần",
       "transportMode": "TAXI"
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
- **Actions & System Transitions:**
  1. Modal opens with existing data.
  2. User modifies cost from 500.000 đ to 800.000 đ and taps "Cập nhật".
  3. Client updates the item.
  4. Timeline item updates visually; day subtotal and overall budget recalculate immediately.
- **Capability Reality:** **PARTIAL / FUTURE**.
  - *Current Code Reality:* NestJS backend does not expose `PATCH /trips/:id/itinerary/:itemId` (only create and delete exist). Flutter UI currently allows viewing and deleting.
  - *Design Specification:* Defines the exact payload and UI for the forthcoming update endpoint.

---

### FLOW T08: Activity Deletion
- **Entry Points:**
  - Swipe left on activity card in timeline or item menu → "Xóa hoạt động".
- **User Intent:** Remove an unwanted activity from the schedule.
- **Screen Mockups:**
  - `trip-mobile-delete-activity.png`: Slide action and confirmation dialog.
- **Actions & System Transitions:**
  1. Confirmation prompt: "Xóa hoạt động 'Ăn trưa Hải sản Bé Mặn' khỏi lịch trình Ngày 1?".
  2. User confirms → Client sends `DELETE /trips/:id/itinerary/:itemId`.
  3. Backend removes record from `ItineraryItem`.
  4. On HTTP 200 OK: Item animates out of timeline; remaining items adjust lines; total budget decrements.
- **Capability Reality:** **CURRENT** in NestJS (`DELETE /trips/:id/itinerary/:itemId`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T09: Timeline Reordering
- **Entry Points:**
  - Tapping "Sắp xếp lại" button in Trip Detail header.
- **User Intent:** Change sequence of activities within a day to optimize travel route or fix scheduling.
- **Screen Mockups:**
  - `trip-mobile-reorder.png`: Drag handles shown on each activity card; time indicators hidden or editable.
- **Actions & System Transitions:**
  1. Timeline enters edit/reorder mode.
  2. User drags an activity handle up or down.
  3. On drop: Client updates local list sequence and updates `orderIndex` properties.
  4. User taps "Hoàn tất" → Client syncs order.
- **Capability Reality:** **FUTURE**.
  - *Current Code Reality:* Schema has `orderIndex Int @default(0)`, but no reorder bulk API endpoint exists.
  - *Design Specification:* Specifies the drag-and-drop UX and batch update requirements for backend sprint.

---

### FLOW T10: Add Place to Trip from Place Detail
- **Entry Points:**
  - Place Detail screen (accessed from Map or Search) → Bottom CTA "Thêm vào chuyến đi".
  - Wandy AI recommendation card action button.
- **User Intent:** Direct bookmarking/scheduling of a discovered POI into an existing travel plan.
- **Screen Mockups:**
  - `wandy-mobile-add-to-trip-action.png`: Bottom sheet trip & day selector.
- **Actions & System Transitions:**
  1. Bottom sheet slides up displaying list of user's upcoming trips.
  2. User selects target trip (e.g. "Đà Nẵng 4N3Đ").
  3. Day chips appear: "Ngày 1", "Ngày 2", "Ngày 3", "Ngày 4".
  4. User selects "Ngày 2" and taps "Thêm vào lịch trình".
  5. System sends `POST /trips/:id/itinerary` with `placeId`, default times, and POI name.
  6. Toast: "Đã thêm [Tên địa điểm] vào Ngày 2 của chuyến đi Đà Nẵng".
- **Capability Reality:** **PARTIAL**.
  - *Current Code Reality:* Backend `POST /trips/:id/itinerary` supports `placeId`. Place Detail screen does not yet mount the Trip Picker dialog.
  - *Design Specification:* Fully specifies the picker modal interaction and parameters.

---

### FLOW T11: AI Planner Entry & Parameters Selection
- **Entry Points:**
  - Trip Detail screen → Prominent banner "Lập lịch trình bằng AI".
  - Empty Trip Detail screen CTA button.
  - Trip Creation success action: "Bạn có muốn Wandy AI lập lịch trình tự động ngay không?".
- **User Intent:** Delegate itinerary planning to GoMate's AI engine based on destination, dates, and budget.
- **Screen Mockups:**
  - `trip-mobile-ai-entry.png`: Modal showing trip constraints and optional custom prompt input.
- **Actions & System Transitions:**
  1. Dialog presents auto-filled parameters:
     - Điểm đến: Đà Nẵng
     - Thời gian: 4 ngày (15/10 - 18/10/2026)
     - Ngân sách: 8.000.000 đ
     - Phong cách: Tiêu chuẩn (Comfort)
  2. Optional prompt input field: "Ghi chú thêm cho AI (ví dụ: muốn đi nhiều điểm thiên nhiên, ăn hải sản, tránh leo núi...)".
  3. User taps "Bắt đầu tạo lịch trình".
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T12: AI Plan Generation & Live Feedback
- **Entry Points:**
  - Triggered immediately after tapping "Bắt đầu tạo lịch trình" in Flow T11.
- **User Intent:** Observe system progress and confirm that the generation is running properly.
- **Screen Mockups:**
  - `trip-mobile-ai-generating.png`: Dedicated liveness view with Wandy animated mascot, elapsed time counter, and dynamic status messages.
- **Liveness & Progress Design Rules:**
  - **NO FAKE PERCENTAGE BARS:** Never display arbitrary percentage ticks (e.g. "34% -> 72%") since LLM generation is non-deterministic.
  - **Live Elapsed Timer:** Shows `Đang xử lý (12s...)` with real clock ticking.
  - **Dynamic Step Cues:** Cycles through real lifecycle steps:
    1. *Phân tích địa điểm du lịch Đà Nẵng...*
    2. *Tối ưu hóa thứ tự di chuyển và thời gian...*
    3. *Cân đối ngân sách chi tiêu từng ngày...*
    4. *Hoàn thiện kế hoạch chi tiết...*
  - **Timeout Safeguard:** If elapsed time exceeds 60 seconds, provides graceful notice: "Quá trình tạo đang mất nhiều thời gian hơn dự kiến, vui lòng đợi thêm giây lát...".
- **Capability Reality:** **CURRENT** in Flutter and AI Service (Gemini 2.5 Flash / Pro).

---

### FLOW T13: AI Plan Preview & Invariant Check
- **Entry Points:**
  - Generation completes successfully from Flow T12.
- **User Intent:** Review the AI-generated schedule, check budget variance and activities, before deciding to save.
- **Screen Mockups:**
  - `trip-mobile-ai-preview.png`: Mobile preview sheet showing days, budget variance, and activities.
  - `trip-desktop-ai-preview.png`: Desktop split-view modal with parameter specs, AI rationale, and multi-day preview.
- **CRITICAL INVARIANT:**
  > **DATABASE MUTATION INVARIANT:**  
  > The AI Plan Preview step **MUST NEVER MUTATE THE DATABASE**.  
  > Calling `POST /trips/:id/ai-plan` generates an ephemeral preview in memory. The user's stored trip in PostgreSQL/Prisma remains 100% untouched until the user explicitly taps "Áp dụng vào chuyến đi".
- **Preview Content:**
  - **Budget Variance Bar:** Shows User Budget (`8.000.000 đ`) vs AI Estimated Cost (`6.850.000 đ`), variance (`-1.150.000 đ`), and status tag `HỢP LÝ / TIẾT KIỆM`.
  - **Day-by-Day Cards:** Each day lists proposed items with time slots, place names, categories, and estimated costs.
  - **AI Travel Tips:** Curated packing, timing, or local culture advice.
- **Actions Available:**
  - "Hủy bỏ": Discards generated preview, returns to Trip Detail without any change.
  - "Tạo lại": Re-runs generator with modified prompt.
  - "Áp dụng vào chuyến đi": Initiates commit flow (Flow T14 / T15).
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/ai-plan`) and Flutter UI preview sheet.

---

### FLOW T14: AI Plan Overwrite Confirmation
- **Entry Points:**
  - User taps "Áp dụng vào chuyến đi" while the trip ALREADY contains manual itinerary items.
- **User Intent:** Confirm whether existing manual activities should be replaced or kept.
- **Screen Mockups:**
  - `trip-mobile-ai-overwrite.png`: Safety warning dialog.
- **Actions & System Transitions:**
  1. System checks: `existingItemCount > 0`.
  2. Dialog appears:
     - Title: "Thay thế lịch trình hiện tại?"
     - Body: "Chuyến đi này đang có 4 hoạt động đã được lên lịch. Áp dụng lịch trình mới từ AI sẽ xóa toàn bộ các hoạt động cũ và thay thế bằng kế hoạch mới."
     - Option: `[x] Xóa hoạt động cũ và áp dụng toàn bộ` (`replaceExisting: true`).
  3. User taps "Hủy": Returns to preview without changes.
  4. User taps "Xác nhận thay thế": Proceeds to Flow T15 commit.
- **Capability Reality:** **CURRENT** in NestJS (`replaceExisting` boolean parameter) and Flutter (`trip_detail_screen.dart`).

---

### FLOW T15: AI Plan Bulk Save / Transaction Commit
- **Entry Points:**
  - Confirmation from Flow T14 (or direct commit if trip was empty).
- **User Intent:** Persist the AI-generated itinerary into PostgreSQL.
- **Screen Mockups:**
  - `trip-mobile-ai-success.png`: Success toast and auto-transition to updated Trip Detail.
- **Actions & Database Transaction:**
  1. Client sends `POST /trips/:id/itinerary/bulk` payload containing all items and `replaceExisting: true`.
  2. Backend wraps operation in a Prisma transaction (`$transaction`):
     - If `replaceExisting === true`: deletes all existing `ItineraryItem` rows for the trip.
     - Creates new `ItineraryItem` rows with `isAiGenerated = true`.
     - Updates `Trip` record: `status = PLANNED`.
  3. Returns HTTP 201 with created items count.
  4. Client updates local store, dismisses preview modal, shows success notification, and renders newly loaded timeline.
- **Capability Reality:** **CURRENT** in NestJS (`POST /trips/:id/itinerary/bulk`) and Flutter.

---

### FLOW T16: Budget Tracking & Over-budget Alerting
- **Entry Points:**
  - Accessible via Trip Detail bottom bar, Budget tab, or Desktop Right Sidebar.
- **User Intent:** Monitor total planned spending against budget limits to prevent overspending.
- **Screen Mockups:**
  - `trip-mobile-budget.png`: Standard safe state (< 85% allocated, green indicator).
  - `trip-mobile-budget-warning.png`: Warning state (85% - 100% allocated, amber indicator `Cảnh báo: Đạt 89% ngân sách`).
  - `trip-mobile-budget-over.png`: Over-budget state (> 100% allocated, red alert `Vượt ngân sách: 8.650.000 / 8.000.000 đ (+650.000 đ)`).
  - `trip-desktop-detail-budget.png`: In-depth desktop breakdown with category progress bars and day-by-day cost tables.
- **Budget Threshold Invariants:**
  1. $\text{Ratio} = \frac{\sum \text{estimatedCost}}{\text{budget}} \times 100\%$
  2. **Safe ($0\% - 85\%$):** Primary Teal `#0F766E`, message "Ngân sách an toàn (Dư ... đ)".
  3. **Near Limit ($85\% - 100\%$):** Amber Warning `#F59E0B`, message "Tiệm cận hạn mức (Còn dư ... đ)".
  4. **Over Budget ($> 100\%$):** Destructive Red `#EF4444`, message "Vượt ngân sách (+... đ)". Suggests trimming activities.
- **Capability Reality:** **CURRENT (UI Mockup) / PARTIAL (Backend compute)**.
  - Client computes budget sum from `itineraryItems[].estimatedCost`.
  - Full analytics by category (Lưu trú, Ẩm thực, Di chuyển) are part of Phase 2 backend aggregation.

---

## 3. Summary of System Invariants

1. **Preview Isolation Invariant:** `POST /trips/:id/ai-plan` is strictly idempotent and read-only regarding database records; it returns JSON preview data without creating `ItineraryItem` records.
2. **Explicit Commit Invariant:** Database mutation only occurs when `POST /trips/:id/itinerary/bulk` is sent with user confirmation.
3. **Budget Honesty Invariant:** All displayed currency values are computed from real item costs or user inputs; no synthetic or unverified totals are presented.
4. **Cascade Deletion Invariant:** Deleting a trip removes all child itinerary items cleanly in a single transaction.
