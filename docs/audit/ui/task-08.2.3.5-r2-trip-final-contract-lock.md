# GoMate Trip Management — Final State & Edit Contract Lock (TASK 08.2.3.5-R2)

**Status:** APPROVED FINAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.5-R2 — GOMATE TRIP MANAGEMENT FINAL STATE & EDIT CONTRACT LOCK  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Branch:** `feature/gomate-visual-mockups`  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.5/` (4 Updated R2 Mockups)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.  

---

## 1. Executive Summary & Purpose

**TASK 08.2.3.5-R2** performs the final micro-correction and contract lock for the GoMate Trip Management module following review of R1. 

Key objectives accomplished:
1. **Root List State Navigation Consistency:** Regenerated Empty, Loading, and Error mockups with the authoritative 5-tab root navigation and updated semantic filter tabs.
2. **Search Control Invariant:** Standardized persistent search control across all populated list views (Option A).
3. **CANCELLED Status Business Rule:** Audited code handling of `CANCELLED` status; classified as `UX DECISION REQUIRED / FUTURE CONTRACT` and locked canonical design target rules.
4. **Edit Trip Contract Audit:** Conducted an exhaustive audit of `UpdateTripDto` vs Flutter `trip_form_screen.dart`, confirming that `status` is NOT user-editable in the form, and generated `trip-mobile-edit-r2.png`.
5. **Future Design Target Labeling:** Formally documented `trip-mobile-edit-activity.png` and `trip-mobile-reorder.png` as `DESIGN TARGET — NOT CURRENT IMPLEMENTATION`.
6. **Watermark Rule Standard:** Confirmed watermarks are strictly evidence markers and not part of production UI.

---

## 2. Root State Reconciliation

In V1, three root list states displayed outdated 4-tab navigation and old terminology ("Sắp tới", "Đã qua"). These have been regenerated in R2 to maintain 100% visual consistency:

| # | Mockup File Name | Viewport | Size | Resolution | Technical Corrections Applied |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **01** | [`trip-mobile-list-empty-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-empty-r2.png) | Mobile | 34,990 B | $390 \times 844$ | 1. 5-tab root navigation (Tab 5 `Chuyến đi` active).<br>2. Filter tabs: "Hiện tại & sắp tới (0)", "Đã kết thúc (0)", "Bản nháp (0)".<br>3. Header single `+` button; NO duplicate FAB.<br>4. Luggage illustration + "+ Tạo chuyến đi ngay" CTA. |
| **02** | [`trip-mobile-list-loading-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-loading-r2.png) | Mobile | 26,862 B | $390 \times 844$ | 1. 5-tab root navigation.<br>2. Semantic filter tabs: "Hiện tại & sắp tới" active.<br>3. Shimmer skeleton cards.<br>4. NO FAB. |
| **03** | [`trip-mobile-list-error-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-error-r2.png) ([`trip-mobile-list-error-r2-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-list-error-r2-final.png)) | Mobile | 28,149 B | $390 \times 844$ | 1. 5-tab root navigation.<br>2. Semantic filter tabs.<br>3. Offline alert icon + human-friendly error message *"Không thể tải danh sách chuyến đi. Vui lòng kiểm tra kết nối mạng và thử lại."*<br>4. **R2.1 Clean Error UI:** Raw technical error code `ERR_NETWORK_DISCONNECTED (503)` suppressed from primary UI and preserved strictly in diagnostic/evidence logs.<br>5. "Thử lại" retry action. |

---

## 3. Search Control Contract (Locked Decision)

```
============================================================
SEARCH CONTROL CONTRACT DECISION
============================================================

DECISION: OPTION A — PERSISTENT SEARCH ACROSS POPULATED TABS

1. Specification:
   The search box is persistently positioned beneath the filter
   tabs on all populated Trip List tabs ("Hiện tại & sắp tới",
   "Đã kết thúc", "Bản nháp").

2. Behavior:
   - Typing in the search input performs client-side real-time
     filtering on the active tab's list by `title` and `destination`.
   - Clear button (✕) resets search instantly.
   - On Empty states and Error states, search is suppressed to
     focus user attention on creation or recovery CTAs.
```

---

## 4. CANCELLED Status Business Rule & Lifecycle

### 4.1. Code Reality Audit
- **Prisma Schema (`schema.prisma`):** `enum TripStatus { DRAFT, PLANNED, ONGOING, COMPLETED, CANCELLED }`.
- **Backend Service (`trips.service.ts`):** `findAll` fetches all trips where `deletedAt: null`, without filtering out `CANCELLED`. `update` accepts `status?: TripStatus`.
- **Flutter Client (`trip_list_screen.dart`):** `_buildStatusChip` only defines cases for `PLANNED`, `ONGOING`, `COMPLETED`, and falls through to `default` ('Ban nhap') for any other status. No cancel button exists in UI.
- **Classification:** **`UX DECISION REQUIRED / FUTURE CONTRACT`**

### 4.2. Locked Design Target Rules (Future Contract)
1. **List Tab Allocation:** Trips with status `CANCELLED` appear under the **"Đã kết thúc"** tab (they are no longer active commitments).
2. **Badge Representation:**
   - Label: `ĐÃ HỦY`
   - Token: Background `#FEE2E2`, Text `#DC2626`, Border `#FECACA`.
3. **Editability:** Strictly **READ-ONLY**. Itinerary timeline items cannot be added, edited, or reordered once a trip is cancelled.
4. **Reopening Action:** A More Menu option "Khôi phục chuyến đi" is designed for Phase 2 to transition a cancelled trip back to `DRAFT` or `PLANNED`.
5. **Deletion Allowed:** Soft/hard delete via `DELETE /trips/:id` remains active.

---

## 5. UpdateTripDto Exact Field Matrix (Backend vs Flutter vs Design)

An exhaustive audit of `UpdateTripDto`, `TripsService.update`, and Flutter `trip_form_screen.dart` yields the following exact matrix:

| Field Name | Type | Backend Support (`UpdateTripDto`) | Flutter Support (`trip_form_screen.dart`) | Capability Status | Design Target (Edit Screen) |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `title` | `String` | YES (required length) | YES (`TextFormField`) | **CURRENT** | **Show as editable text input** |
| `destinationId` / `destination` | `UUID / String` | YES (`destinationId`) | NO (not in edit form) | **PARTIAL** | **Show as read-only reference** (Destination change is Phase 2) |
| `startDate` | `DateString` | YES | YES (`showDatePicker`) | **CURRENT** | **Show as editable date picker** |
| `endDate` | `DateString` | YES | YES (`showDatePicker`) | **CURRENT** | **Show as editable date picker** |
| `totalBudget` | `Int` | YES | YES (`_budgetController`) | **CURRENT** | **Show as editable numeric input** (paired with currency) |
| `currency` | `String` | YES (`VND`, `USD`) | YES (`DropdownButtonFormField<String> _currency`) | **CURRENT** | **Show as currency selector (`VND` / `USD`)** alongside budget |
| `travelStyle` | `TravelStyle` | YES (Enum) | YES (`ChoiceChip` list) | **CURRENT** | **Show as 4 locked chips** (Phượt, Tiết kiệm, Thoải mái, Sang trọng) |
| `description` | `String` | YES | YES (`TextFormField`) | **CURRENT** | **Show as editable textarea** |
| `status` | `TripStatus` | YES (in DTO) | **NO (not in UI form)** | **CURRENT (System Lifecycle)** | **STRICTLY EXCLUDED FROM FORM** (Status is not a user dropdown) |
| `interests` | `String[]` | YES | YES (Chips in form) | **PARTIAL / CONTEXT** | **Omitted from core trip edit** (Managed in AI recommendation context) |

---

## 6. Edit Trip Correction & Verification

In V1, `trip-mobile-edit.png` incorrectly presented a "Trạng thái chuyến đi" dropdown. As proven by our audit:
- Flutter `trip_form_screen.dart` contains no status dropdown.
- Trip status is managed by lifecycle invariants (`DRAFT` $\rightarrow$ `PLANNED` on bulk save, `ONGOING` on active date, `COMPLETED` on post-end-date).
- Showing an arbitrary status dropdown violates the architecture.

In R2.1, the currency handling was specifically audited:
- In `trip_form_screen.dart`, currency is rendered inside a `Row` alongside budget: `Expanded(flex: 3, child: _buildTextField(... 'Ngân sách'))` and `Expanded(flex: 2, child: DropdownButtonFormField<String>(value: _currency, items: ['VND', 'USD']))`.
- Both `budget` and `currency` are passed to `UpdateTripRequest` upon saving changes.
- Therefore, `currency` is verified as **`CURRENT`** capability.

**Resolution:** Generated [`trip-mobile-edit-r2-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-edit-r2-final.png) (and updated [`trip-mobile-edit-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.5/trip-mobile-edit-r2.png)):
- **Tên chuyến đi:** Editable text field.
- **Điểm đến:** Read-only reference with location pin icon.
- **Thời gian:** Start/End date pickers.
- **Ngân sách dự kiến & Tiền tệ (R2.1):** 2-column input row containing numeric budget input (`15.000.000`) and currency dropdown selector (`VND` / `USD`).
- **Phong cách du lịch:** 4 locked chips with `Thoải mái` selected.
- **Mô tả / Ghi chú:** Textarea.
- **Status Dropdown:** **REMOVED**. Replaced by informational notice on system lifecycle management.
- **CTA:** "Lưu thay đổi".

---

## 7. Future Design Target Labeling (Contract Integrity)

To prevent false assumptions during code reviews and audits, the following designs are officially designated:

| Artifact | Screen Name | Technical Reality | Official Documentation Designation |
| :--- | :--- | :--- | :--- |
| `trip-mobile-edit-activity.png` | Sửa hoạt động | Backend lacks `PATCH /trips/:id/itinerary/:itemId` | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |
| `trip-mobile-reorder.png` | Sắp xếp lại timeline | Backend lacks batch `orderIndex` update API | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |
| `wandy-mobile-add-to-trip-action.png` | Thêm vào chuyến đi | Place Detail screen lacks trip picker sheet | **DESIGN TARGET — NOT CURRENT IMPLEMENTATION** |

*(Per Section 7 of instructions, these labels exist strictly in documentation and audit records; no artificial "FUTURE" stamps are injected into production UI mockups).*

---

## 8. Final Comprehensive Capability Matrix (Locked)

| Feature | Backend API Endpoint | Flutter Screen | Capability Status | Current vs Target Behavior |
| :--- | :--- | :--- | :---: | :--- |
| **Trip List** | `GET /trips` | `trip_list_screen.dart` | **CURRENT** | Fetches user trips, splits into tabs, real-time search. |
| **Trip Create** | `POST /trips` | `trip_form_screen.dart` | **CURRENT** | Validates title, destination, dates, budget, travel style. CTA: "Tạo chuyến đi". |
| **Trip Edit** | `PATCH /trips/:id` | `trip_form_screen.dart` | **CURRENT** | Updates title, dates, budget, travel style, description. No status dropdown. |
| **Trip Delete** | `DELETE /trips/:id` | `trip_detail_screen.dart` | **CURRENT** | Cascades deletion of child itinerary items with confirmation dialog. |
| **Trip Detail** | `GET /trips/:id` | `trip_detail_screen.dart` | **CURRENT** | Hero card, day selector tabs, timeline activities, bottom bar. |
| **Add Activity** | `POST /trips/:id/itinerary` | `trip_detail_screen.dart` | **CURRENT** | Maps 1:1 to API (`dayNumber`, `activity`, `placeId?`, time, cost, `transportMode`, notes). |
| **Delete Activity** | `DELETE /trips/:id/itinerary/:itemId` | `trip_detail_screen.dart` | **CURRENT** | Deletes activity and updates timeline and budget immediately. |
| **Edit Activity** | None (`PATCH` missing) | Dialog missing | **DESIGN TARGET** | Target mockup: `trip-mobile-edit-activity.png`. Pending Sprint 02 API. |
| **Reorder Activities** | None (batch reorder missing) | Reorder handles missing | **DESIGN TARGET** | Target mockup: `trip-mobile-reorder.png`. Pending Sprint 02 API. |
| **Add Place from Map** | `POST /trips/:id/itinerary` | Sheet missing on Place Detail | **DESIGN TARGET** | Target mockup: `wandy-mobile-add-to-trip-action.png`. Pending UI bridge. |
| **AI Planner Entry** | `POST /trips/:id/ai-plan` | `trip_detail_screen.dart` | **CURRENT** | Passes trip constraints and optional custom prompt. |
| **AI Generation Liveness** | AI Service | `trip_detail_screen.dart` | **CURRENT** | Live ticking timer, dynamic steps, NO fake progress percentage. |
| **AI Plan Preview** | `POST /trips/:id/ai-plan` | Preview bottom sheet | **CURRENT** | **Invariant Verified:** Purely in-memory preview; NO database mutation. |
| **AI Overwrite Warning** | Client check | Warning modal | **CURRENT** | Warns user if existing activities will be deleted on apply (`replaceExisting=true`). |
| **AI Bulk Commit** | `POST /trips/:id/itinerary/bulk` | Preview action | **CURRENT** | Atomic transaction: deletes old if confirmed, saves new items with `isAiGenerated: true`. |
| **Budget Gauge** | Client compute | Bottom bar / stat card | **CURRENT (UI) / PARTIAL (API)** | Real-time budget progress bar (<85% safe, 85-100% warning, >100% over). Category breakdown is Phase 2 API. |
| **Trip Members** | `POST /trips/:id/members` | UI missing | **PARTIAL** | Prisma schema has `TripMember` table; UI invite/member modal not yet built. |
| **Wandy Chat Context** | None | Chat missing `tripId` | **FUTURE** | AI Chat endpoint does not yet accept active `tripId` to reference itinerary during chat. |

---

## 9. Final Trip Acceptance Gate

- [x] **Empty State:** Uses new semantic filters ("Hiện tại & sắp tới", "Đã kết thúc", "Bản nháp") and 5-tab navigation.
- [x] **Error State:** Uses 5-tab navigation and semantic filters.
- [x] **Loading State:** Uses 5-tab navigation and semantic filters.
- [x] **No Remaining "Đã qua" Terminology:** Fully replaced by "Đã kết thúc".
- [x] **Search Behavior Consistent:** Option A (Persistent across populated lists) locked.
- [x] **CANCELLED Status Reconciled:** Explicitly categorized as `UX DECISION REQUIRED / FUTURE CONTRACT` with locked design target rules.
- [x] **UpdateTripDto Audited:** Exact 10-field matrix documented.
- [x] **Edit Trip Mockup Matches Contract:** `trip-mobile-edit-r2.png` created with exact editable fields and NO status dropdown.
- [x] **R2.1 Currency Audit:** Verified editable dropdown (`VND` / `USD`) in `trip_form_screen.dart`, reflected in `trip-mobile-edit-r2-final.png` (`trip-mobile-edit-r2.png`).
- [x] **R2.1 Human-Friendly Error State:** Raw technical error code `ERR_NETWORK_DISCONNECTED (503)` removed from primary UI in `trip-mobile-list-error-r2-final.png` (`trip-mobile-list-error-r2.png`).
- [x] **Unsupported Status Edit Not Presented as Current:** Fully removed from edit UI.
- [x] **Edit Activity Marked Design Target:** Documented as `DESIGN TARGET — NOT CURRENT IMPLEMENTATION`.
- [x] **Reorder Marked Design Target:** Documented as `DESIGN TARGET — NOT CURRENT IMPLEMENTATION`.
- [x] **Current/Future Boundary Unchanged:** Strict data honesty maintained.
- [x] **No Source Code Changes:** 0 lines modified in `apps/`.
- [x] **No DB/Schema Changes:** `schema.prisma` unmodified.
- [x] **No API Changes:** Contracts intact.
- [x] **No Merge:** Preserved on branch `feature/gomate-visual-mockups`.
- [x] **No Push:** Local commit only until user authorization.
