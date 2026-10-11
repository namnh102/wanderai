# GoMate Trip Management — UX Contract & Visual Consistency Correction (TASK 08.2.3.5-R1)

**Status:** APPROVED DESIGN CORRECTION AUDIT  
**Task:** TASK 08.2.3.5-R1 — GOMATE TRIP MANAGEMENT UX CONTRACT & VISUAL CONSISTENCY CORRECTION  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Branch:** `feature/gomate-visual-mockups`  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.5/` (5 Updated R1 Mockups)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.  

---

## 1. Executive Summary & Objectives

Following an exhaustive design review of TASK 08.2.3.5 (GoMate Trip Management Visual Mockup V1), 8 specific UX contract inconsistencies and visual discrepancies were identified. 

**TASK 08.2.3.5-R1** executes a surgical design correction to lock visual consistency, enforce API contract fidelity, and eliminate false assumptions:
- **No full redesign:** All sound foundations from V1 (Deep Pine Teal palette, typography, status tags, chronological timeline, budget thresholds, AI preview invariant, and desktop 3-column architecture) are 100% preserved.
- **Contract Fidelity:** Corrects CTA labels, form field persistence boundaries, enum terminology, and modal field mapping to reflect current NestJS + Prisma realities.
- **Evidence-Only Watermarking:** Confirms that demo watermarks exist strictly for evaluation evidence and are not part of runtime application code.

---

## 2. In-Depth Correction Analysis (Before → Issue → Contract Evidence → Correction → Final State)

### CORRECTION #1 — CREATE TRIP CTA DECOUPLING

- **Before:**
  The trip creation CTA button displayed: `"Tạo chuyến đi & Lên lịch"` (or implied automatic AI planning upon submission).
- **Issue:**
  This caused severe misunderstanding that `POST /trips` would simultaneously trigger the AI Planner and immediately generate an itinerary.
- **Contract Evidence:**
  - `POST /trips` in `trips.controller.ts` creates the `Trip` entity only (returns `{ id, title, destinationId, ... }`).
  - `POST /trips/:id/ai-plan` is a distinct, secondary user action triggered on the Trip Detail screen.
- **Correction:**
  - Changed CTA button label strictly to: **"Tạo chuyến đi"**.
  - Established explicit decoupled user flow: Create Trip (`POST /trips`) $\rightarrow$ Routes to Empty Trip Detail (`trip-mobile-detail-empty-r1.png`) $\rightarrow$ User explicitly chooses between `"Lập lịch trình bằng AI"` or `"Tự lên lịch thủ công"`.
- **Final State:**
  Verified in [`trip-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-create-r1.png) and [`trip-mobile-detail-empty-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-detail-empty-r1.png).

---

### CORRECTION #2 — TRIP CREATION FIELDS & PERSISTENCE BOUNDARY

- **Before:**
  The initial trip creation form included a "Sở thích du lịch" (Interests) field with tags.
- **Issue:**
  Improperly suggested that user interests were a required persistent configuration for standard trip entities, creating ambiguity about what is stored in the database.
- **Contract Evidence:**
  - `CreateTripDto` in `apps/backend/src/modules/trips/dto/create-trip.dto.ts` requires only: `title`, `destinationId` / `destination`, `startDate`, `endDate`, `totalBudget`, `currency`, `travelStyle`.
  - While `interests String[]` exists in the database schema, it is populated optionally during conversational AI planning, not during basic trip initialization.
- **Correction:**
  - **REMOVED "Sở thích du lịch"** from the current Trip Create form.
  - Relocated interests and custom travel preferences strictly to the AI Planner entry modal / conversational recommendation context.
- **Final State:**
  Verified in [`trip-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-create-r1.png).

---

### CORRECTION #3 — STANDARDIZED TRAVEL STYLE ENUM COPY

- **Before:**
  Inconsistent Vietnamese labels were used across screens (e.g. `COMFORT` was labeled "Tiêu chuẩn" on some cards and "Thoải mái" on others; `LUXURY` was labeled "Nghỉ dưỡng").
- **Issue:**
  Violated design system consistency by using multiple Vietnamese terms for the same underlying Prisma enum value.
- **Contract Evidence:**
  `apps/backend/prisma/schema.prisma` lines 25-30:
  ```prisma
  enum TravelStyle {
    BACKPACKER // Phượt
    BUDGET     // Tiết kiệm
    COMFORT    // Thoải mái
    LUXURY     // Sang trọng
  }
  ```
- **Correction:**
  Locked canonical Vietnamese translations across all documentation and mockups:
  - `BACKPACKER` $\rightarrow$ **Phượt**
  - `BUDGET` $\rightarrow$ **Tiết kiệm**
  - `COMFORT` $\rightarrow$ **Thoải mái** (Replaces "Tiêu chuẩn")
  - `LUXURY` $\rightarrow$ **Sang trọng** (Replaces "Nghỉ dưỡng")
- **Final State:**
  Consistently reflected across [`trip-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-create-r1.png), [`trip-mobile-list-upcoming-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-upcoming-r1.png), and [`trip-mobile-list-past-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-past-r1.png).

---

### CORRECTION #4 — ADD ACTIVITY CONTRACT MAPPING (1:1 WITH API)

- **Before:**
  The Add Activity modal merged "Tên hoạt động / Địa điểm" into a single ambiguous input field and omitted transport mode.
- **Issue:**
  Did not match the backend database schema where `activity` is the required descriptive name and `placeId` is an optional foreign key link to a canonical `Place`.
- **Contract Evidence:**
  `apps/backend/src/modules/trips/dto/create-itinerary-item.dto.ts` and Prisma `ItineraryItem`:
  - `dayNumber`: integer
  - `activity`: string (Tên hoạt động *)
  - `placeId?`: optional UUID (Địa điểm liên kết)
  - `startTime`: "HH:mm"
  - `endTime`: "HH:mm"
  - `estimatedCost`: integer VND
  - `transportMode`: string (`walk`, `motorbike`, `taxi`, `car`, `bus`)
  - `notes`: string
- **Correction:**
  Redesigned the bottom sheet with 8 distinct form fields mapping 1:1 to verified API parameters:
  - Dropdown: `Ngày lịch trình` (`dayNumber`)
  - Text input: `Tên hoạt động *` (`activity`)
  - Search input: `Địa điểm liên kết (tùy chọn)` (`placeId`)
  - Time pickers: `Giờ bắt đầu` / `Giờ kết thúc` (`startTime`, `endTime`)
  - Number input: `Chi phí ước tính` (`estimatedCost`)
  - Choice chips: `Phương tiện di chuyển` (`transportMode`)
  - Textarea: `Ghi chú` (`notes`)
  - Submit CTA: `Lưu hoạt động`
- **Final State:**
  Verified in [`trip-mobile-add-activity-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-add-activity-r1.png).

---

### CORRECTION #5 — TRIP LIST SEMANTIC CATEGORIZATION

- **Before:**
  Trip list tabs were labeled "Sắp tới" and "Đã qua", but the first tab also contained trips with status `ONGOING` (currently taking place today).
- **Issue:**
  A trip marked with badge `ĐANG DIỄN RA` (Ongoing) sitting under a tab named strictly "Sắp tới" (Upcoming) created semantic cognitive dissonance.
- **Contract Evidence:**
  `TripStatus` enum in Prisma contains: `DRAFT`, `PLANNED`, `ONGOING`, `COMPLETED`, `CANCELLED`.
- **Correction:**
  Updated tab copy to accurate semantic labels:
  - Tab 1: **"Hiện tại & sắp tới"** (Houses both `ONGOING` and `PLANNED` trips).
  - Tab 2: **"Đã kết thúc"** (Houses historical `COMPLETED` trips).
  - Tab 3: **"Bản nháp"** (Houses unfinished `DRAFT` trips).
- **Final State:**
  Verified in [`trip-mobile-list-upcoming-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-upcoming-r1.png) and [`trip-mobile-list-past-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-past-r1.png).

---

### CORRECTION #6 — REMOVAL OF DUPLICATE CREATE ACTION

- **Before:**
  The Trip List screen simultaneously contained both a `+` icon in the Top App Bar and a floating action button (FAB) `+` in the bottom right corner.
- **Issue:**
  Violated the "One Primary Action Principle", causing visual competition and redundancy.
- **Correction:**
  - Kept the top app bar primary `+` button in the top right.
  - **REMOVED the duplicate Floating Action Button (FAB).**
- **Final State:**
  Clean, uncluttered list view verified in [`trip-mobile-list-upcoming-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-upcoming-r1.png).

---

### CORRECTION #7 — TRIP TITLE & IDENTITY CONSISTENCY

- **Before:**
  In `trip-mobile-detail-empty.png`, the Top App Bar displayed `"Hạ Long 3N2Đ"` while the Hero Card displayed `"Kỳ nghỉ Hạ Long 3N2Đ"`.
- **Issue:**
  Discrepancy in the entity identity across two elements on the same screen representing the exact same trip.
- **Correction:**
  Enforced the strict rule: Both the Top App Bar and the Hero Card must render the exact same string bound to `Trip.title`.
- **Final State:**
  Both positions display strictly `"Kỳ nghỉ Hạ Long 3N2Đ"`. Verified in [`trip-mobile-detail-empty-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-detail-empty-r1.png).

---

### CORRECTION #8 — GLOBAL NAVIGATION RECONCILIATION

- **Before:**
  Some V1 mockups rendered a 4-tab bottom navigation bar (`Khám phá`, `Bản đồ`, `Chuyến đi`, `Wandy AI`), whereas UX Architecture documents referenced a 5-tab structure.
- **Technical Audit & Evidence:**
  - Inspection of `apps/mobile/lib/core/router/app_router.dart` confirmed that the current Flutter production code implements a 5-destination shell:
    1. `/` $\rightarrow$ `Trang chủ` / `Khám phá` (Icons.explore)
    2. `/map` $\rightarrow$ `Bản đồ` (Icons.map)
    3. `/ai` $\rightarrow$ `Wandy AI` (Icons.auto_awesome)
    4. `/safety` $\rightarrow$ `An toàn` (Icons.shield)
    5. `/trips` $\rightarrow$ `Chuyến đi` (Icons.luggage)
  - `docs/design/gomate-ux-architecture-v1.md` Section 3 also specifies 5 tabs.
- **Final Design Decision:**
  The **5-tab navigation architecture is confirmed as the authoritative standard**.
  Updated mobile mockups rendering the persistent root navigation (`trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`) display the full 5 tabs with Tab 5 (`Chuyến đi`) active.

---

## 3. Watermark Evidence Notice

> [!NOTE]
> **WATERMARK IS EVIDENCE-ONLY, NOT PRODUCTION UI**  
> The watermark string `VISUAL DEMO DATA — NOT PRODUCTION DATA` included in mockups is an evidence-only marker designed to prevent any misinterpretation of mockups as live database output during academic or professional reviews. It does not exist in production code or runtime Flutter widgets.

---

## 4. Audit Table of 5 Regenerated R1 Mockups

| # | Tên tệp Mockup | Độ phân giải | Kích thước | Các điểm đã sửa đổi trong R1 |
| :---: | :--- | :---: | :---: | :--- |
| **01** | [`trip-mobile-list-upcoming-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-upcoming-r1.png) | $390 \times 844$ | 80,438 B | 1. Tab "Hiện tại & sắp tới" chứa chuyến đi `ONGOING`.<br>2. Xóa FAB, giữ 1 nút `+` trên header.<br>3. Bổ sung bottom nav 5 tab chuẩn router.<br>4. TravelStyle chuẩn "Thoải mái". |
| **02** | [`trip-mobile-list-past-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-past-r1.png) | $390 \times 844$ | 65,814 B | 1. Tab "Đã kết thúc" chuẩn hóa.<br>2. Xóa FAB.<br>3. Bottom nav 5 tab chuẩn router.<br>4. TravelStyle chuẩn "Thoải mái", "Sang trọng". |
| **03** | [`trip-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-create-r1.png) | $390 \times 844$ | 37,552 B | 1. CTA chuẩn hóa thành "Tạo chuyến đi" (tách rời AI planner).<br>2. Xóa trường "Sở thích du lịch".<br>3. Khóa 4 nhãn TravelStyle: Phượt, Tiết kiệm, Thoải mái, Sang trọng. |
| **04** | [`trip-mobile-add-activity-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-add-activity-r1.png) | $390 \times 844$ | 36,284 B | 1. Tách biệt `activity` và `placeId`.<br>2. Bổ sung `transportMode` dạng chip.<br>3. Map 1:1 đầy đủ 8 trường API `ItineraryItem`. |
| **05** | [`trip-mobile-detail-empty-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-detail-empty-r1.png) | $390 \times 844$ | 95,444 B | 1. Đồng nhất 100% tiêu đề App Bar và Hero: "Kỳ nghỉ Hạ Long 3N2Đ".<br>2. Hiển thị rõ ràng 2 lựa chọn: Lập lịch bằng AI hoặc Thêm thủ công. |

---

## 5. Unchanged Correct Parts (Preserved from V1)

All verified, compliant architectural elements from V1 were strictly preserved:
- GoMate visual palette (`#0F766E`, `#CCFBF1`, `#F8FAFC`).
- Typography hierarchy and font scales.
- Card radius (18px/20px) and elevation box shadows.
- Status badges (`ĐÃ LÊN LỊCH`, `ĐANG DIỄN RA`, `BẢN NHÁP`, `ĐÃ KẾT THÚC`).
- Vertical chronological timeline with time col, dot, and connector lines.
- AI Planner generation feedback with live elapsed timer (NO fake progress percentages).
- Database mutation invariant: AI preview remains strictly in-memory until user commits.
- Overwrite warning dialog when applying AI plans over existing manual activities.
- Desktop 3-pane workstation layout ($1440 \times 900$).

---

## 6. Acceptance Gate Checklist

- [x] **Create Trip CTA:** No longer implies automatic AI planning; reads strictly "Tạo chuyến đi".
- [x] **Interests Removed:** "Sở thích du lịch" removed from current persistent Trip Create form.
- [x] **Travel Style Standardized:** Locked to `Phượt`, `Tiết kiệm`, `Thoải mái`, `Sang trọng`.
- [x] **Add Activity Contract:** Maps 1:1 to API (`dayNumber`, `activity`, `placeId?`, `startTime`, `endTime`, `estimatedCost`, `transportMode`, `notes`).
- [x] **Place Separated from Activity:** `activity` is string name, `placeId` is optional POI search.
- [x] **Transport Mode Included:** Chips for walk, motorbike, taxi, car, bus.
- [x] **Active/Upcoming Semantics:** Changed to "Hiện tại & sắp tới" to properly house `ONGOING` trips.
- [x] **Past Terminology:** Changed to "Đã kết thúc".
- [x] **Duplicate Action Removed:** Removed FAB; kept single primary `+` on Header.
- [x] **Title Consistency:** App Bar and Hero Card share exact identical `Trip.title`.
- [x] **Global Bottom Navigation Reconciled:** 5-tab architecture confirmed as authoritative.
- [x] **Watermark Documented:** Explicitly noted as evidence-only marker, not production UI.
- [x] **No Source Code Changes:** `apps/` directory unmodified (0 diff).
- [x] **No API Changes:** Existing DTOs and endpoints unmodified.
- [x] **No DB Changes:** `schema.prisma` unmodified.
- [x] **No Merge:** Preserved on branch `feature/gomate-visual-mockups`.
- [x] **No Push:** Local commit only.
