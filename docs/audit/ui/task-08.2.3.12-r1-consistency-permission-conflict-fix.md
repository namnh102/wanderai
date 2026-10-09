# GoMate Shared Itinerary — Consistency, Permission & Conflict Honesty Fix (TASK 08.2.3.12-R1)

**Status:** APPROVED MICRO-CORRECTION & DESIGN LOCK  
**Task:** TASK 08.2.3.12-R1 — GOMATE SHARED ITINERARY DATA CONSISTENCY, PERMISSION & CONFLICT HONESTY FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model GroupMember`, `model Place`, `model User`)
- Backend Code: `apps/backend/src/modules/trips/trips.controller.ts`, `apps/backend/src/modules/trips/trips.service.ts`
- Core Contracts: `docs/design/gomate-shared-itinerary-contract-v1.md`, `docs/audit/ui/task-08.2.3.12-shared-itinerary-audit.md`
- Master Visual Artifacts:
  - Mobile Master View R1: [`shared-itinerary-mobile-view-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-r1.png) ($390 \times 844$)
  - Mobile Master Edit V1 (Preserved): [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Conflict / Save Error R1: [`shared-itinerary-mobile-conflict-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-r1.png) ($390 \times 844$)
  - Desktop Master Workstation R1: [`shared-itinerary-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-r1.png) ($1440 \times 900$)
  - Baseline V1 Visuals (Pre-Correction): [`shared-itinerary-mobile-view-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-v1.png), [`shared-itinerary-mobile-conflict-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-v1.png), [`shared-itinerary-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-v1.png)

---

## 1. Executive Summary & Objective

TASK 08.2.3.12-R1 executes targeted micro-corrections for the **GoMate Shared Itinerary Canonical Trip Collaboration & Permission Contract V1** prior to Design Lock.

No Flutter production code, NestJS backend, FastAPI AI service, Prisma schema, or API contracts are altered. This task specifically resolves 5 consistency, permission honesty, and concurrency overclaims identified during audit review, regenerates the 3 affected master mockups (`-r1.png`), updates the audit documentation, and locks the architectural contract for downstream implementation.

---

## 2. Comprehensive Correction Audit Matrix (Before → Risk → Evidence → Correction → Locked Contract)

### 2.1. Correction #1 — Budget Demo Consistency Across Mobile & Desktop

- **Before:**
  - Mobile V1 mockup displayed: Dự tính `3.200.000 đ` / Ngân sách `5.000.000 đ` ($64\%$ fill).
  - Desktop V1 mockup displayed: Dự tính `2.800.000 đ` (sum of Day 1: $300\text{k}$ + Day 2: $850\text{k}$ + Day 3: $1.200\text{k}$ + Day 4: $450\text{k}$), remaining $+2.200.000\text{ đ}$ ($56\%$ fill).
- **Risk:** Cross-platform inconsistency between mockups undermines specification authority and introduces ambiguity for QA and UI engineers regarding the canonical calculation.
- **Evidence:**
  - Both screens represent the exact same 4-day itinerary for "Khám phá Đà Nẵng 4N3Đ".
  - The sum of daily activities across all days is:
    $$\text{tripEstimatedCost} = 300.000 + 850.000 + 1.200.000 + 450.000 = 2.800.000\text{ VND}$$
  - With a total budget of $5.000.000\text{ VND}$:
    $$\text{remainingBudget} = 5.000.000 - 2.800.000 = +2.200.000\text{ VND} \quad (56\% \text{ utilization})$$
- **Correction:**
  - Reconciled Mobile View R1 (`shared-itinerary-mobile-view-r1.png`) to display strictly:
    $$\textbf{Dự tính: 2.800.000 đ / 5.000.000 đ (56% bar fill)}$$
  - Desktop Workstation R1 (`shared-itinerary-desktop-r1.png`) consistently matches this exact calculation.
- **Locked Contract:** Budget derivation follows deterministic summation of all `ItineraryItem.estimatedCost` values across the trip. Mobile and desktop mockups are $100\%$ synchronized at $2.800.000\text{ đ}$ ($56\%$).

---

### 2.2. Correction #2 — Current TripMember Permission Reality & Policy Risk

- **Before:** V1 documentation implied that Trip Members were constrained by nuanced item ownership or could only edit their own proposals.
- **Risk:** Masked backend implementation reality, creating a false impression of existing row-level authorization and permission safeguards that do not exist in the codebase.
- **Evidence:**
  - `apps/backend/src/modules/trips/trips.service.ts`:
    - `addItineraryItem(tripId, userId, dto)` calls `this.findById(tripId, userId)`.
    - `deleteItineraryItem(tripId, itemId, userId)` calls `this.findById(tripId, userId)` and then directly executes `this.prisma.itineraryItem.delete({ where: { id: itemId } })`.
    - `findById` only verifies `trip.userId === userId || trip.members.some((m) => m.userId === userId)`.
  - **Result:** Any user holding a `TripMember` record can delete ANY activity in the itinerary, regardless of who created it.
- **Correction:**
  - Explicitly documented the current backend behavior.
  - Classified this behavior as:
    $$\textbf{TripMember DELETE ANY ITEM = CURRENT BACKEND BEHAVIOR + PERMISSION / PRODUCT POLICY RISK}$$
  - Defined the Target Contributor Policy:
    - **Trip Owner:** Full edit authority (Add, Edit, Delete, Reorder, Apply AI Plan).
    - **Trip Member:** Contributor authority (View, Propose / Add activity, Preview AI Plan). Deleting arbitrary activities, batch reordering, and bulk AI overwrites are restricted to the Trip Owner.
- **Locked Contract:** Contract Section 8 transparently discloses current backend permissions, highlights the policy risk, and specifies the target role policy without misrepresenting current runtime checks.

---

### 2.3. Correction #3 — Removal of Unsupported "Own Proposal" Semantics

- **Before:** Conceptual descriptions suggested that a Trip Member could "delete only their own proposal" or that "activity ownership" was tracked.
- **Risk:** Contradicted the Prisma schema by assuming data fields that do not exist, leading engineers to expect per-item ownership tracking out of the box.
- **Evidence:**
  - `model ItineraryItem` in `apps/backend/prisma/schema.prisma` contains:
    `id`, `itineraryId`, `placeId`, `orderIndex`, `startTime`, `endTime`, `activity`, `notes`, `estimatedCost`, `transportMode`.
  - There is **NO `userId`**, **NO `createdBy`**, and **NO `ownerId`** column on `model ItineraryItem`.
  - The backend cannot determine which member added an item at runtime.
  - Additionally, `TripMember.role` is a plain string column defaulting to `"member"`, but the service does not enforce a read-only role.
- **Correction:**
  - Removed all claims of "deleting only own proposals" or per-item ownership from V1 capabilities.
  - Formally classified:
    $$\textbf{Contribution Ownership (createdBy / own proposal) = FUTURE SCHEMA / AUTHORIZATION WORK}$$
    $$\textbf{Read-Only Trip Member Role = FUTURE / POLICY TARGET}$$
- **Locked Contract:** Item-level authorship requires a future database migration (`createdBy String @db.Uuid`). In V1, additions append to the shared itinerary without individual author tags.

---

### 2.4. Correction #4 — Conflict UX Honesty & Concurrency Classification

- **Before:** V1 conflict mockup (`shared-itinerary-mobile-conflict-v1.png`) rendered high-fidelity speculative metadata:
  - User avatar and name: `"Lê Hoàng Nam"`
  - Precise relative timestamp: `"09:32 hôm nay"`
  - Granular diff summary box: `"Thêm điểm Chợ Đêm Helio"`
- **Risk:** Implied that the backend currently detects concurrent edits, tracks modifying actors in real time, computes diffs, and pushes change events to clients.
- **Evidence:**
  - Neither `Itinerary` nor `ItineraryItem` has `version`, `revision`, `updatedAt`, `ETag`, or `If-Match` headers.
  - There is no audit log or change history table.
  - There is no WebSocket gateway pushing conflict events to mobile clients.
- **Correction:**
  - Formally classified:
    $$\textbf{Conflict Detection = DESIGN TARGET / IMPLEMENTATION GAP}$$
    $$\textbf{Conflict UX = DESIGN SPECIFICATION (NOT CURRENT RUNTIME)}$$
  - Regenerated Mobile Conflict R1 (`shared-itinerary-mobile-conflict-r1.png`) using canonical title and clean, generic conflict copy:
    - **Tiêu đề (Modal Title):** *“Xung đột chỉnh sửa lịch trình”*
    - **Nội dung (Warning Message):** *“Lịch trình trên máy chủ đã thay đổi trong khi bạn đang chỉnh sửa. Phiên bản hiện tại của bạn không còn là dữ liệu mới nhất.”*
  - Removed all fabricated actor names, timestamps, and diff boxes.
  - Preserved clear, actionable CTAs:
    - Primary: `[Tải lại lịch trình mới nhất]`
    - Secondary: `[Hủy bỏ thay đổi của bạn]`
- **Locked Contract:** Conflict detection requires future optimistic concurrency control (`version Int` on `Trip` / `Itinerary`). Conflict UX is locked as a protective design specification that guides safe error handling without fabricating telemetry data.

---

### 2.5. Correction #5 — Removal of Technical Developer / Task Labels from UI

- **Before:** Desktop V1 mockup displayed downstream integration card with developer ticket label: `"Sắp có · TASK 08.2.3.13"`.
- **Risk:** Leaking internal Jira/project management ticket numbers into production user interfaces violates visual polish standards.
- **Evidence:** End users should see clean, contextual feature availability copy, never internal task codes.
- **Correction:**
  - Purged `"TASK 08.2.3.13"` from the desktop downstream card.
  - Updated badge to clean, user-facing label:
    $$\textbf{"Sắp có"}$$
  - Regenerated Desktop Workstation R1 (`shared-itinerary-desktop-r1.png`).
- **Locked Contract:** Production UI frames contain exclusively user-facing copy. Technical ticket references belong strictly in markdown audit and contract documentation.

---

## 3. Master Mockup Verification (R1 Artifacts)

All 3 affected master mockups were regenerated using headless Edge rendering and verified against design invariants:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`shared-itinerary-mobile-view-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `Lịch trình chung` with subtitle `Khám phá Đà Nẵng 4N3Đ`.<br>2. Trip Hero: Date range `15/10 - 18/10/2026 (4 ngày)`, role badge `Bạn là Chủ chuyến đi`.<br>3. **Budget Consistency Locked:** Progress bar shows Dự tính `2.800.000 đ` / Ngân sách `5.000.000 đ` ($56\%$ fill), perfectly matching desktop totals.<br>4. Day selector scroll with active pill `Ngày 1 · 15/10`.<br>5. Day header: `Ngày 1: Biển Mỹ Khê & Bán đảo Sơn Trà` with day cost badge `300.000 đ`.<br>6. Timeline: 4 chronological activities with order numbers, time badges, verified place addresses, costs, and transport modes.<br>7. Bottom action bar: `Wandy AI` and `Chỉnh sửa lịch trình`.<br>8. Canonical 5-tab root navigation (Chuyến đi active). Zero developer tags. | **PASS** |
| [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) | Mobile | $390 \times 844$ | *(Preserved intact from V1)*<br>1. App bar with `Hủy` (left), title `Chỉnh sửa lịch trình`, and `Lưu` (right).<br>2. Hint banner: `Kéo giữ biểu tượng bên trái để sắp xếp lại thứ tự hoạt động`.<br>3. Day pills with activity counts: `Ngày 1 (4)`, `Ngày 2 (3)`, etc.<br>4. Edit list: Drag handles `≡`, editable time/activity, delete action `🗑️`.<br>5. Action: `+ Thêm hoạt động vào Ngày 1`.<br>6. Wandy AI proposal card with explicit disclaimer: `Wandy tạo bản xem trước, không tự động lưu đè`. | **PASS** |
| [`shared-itinerary-mobile-conflict-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-r1.png) | Mobile | $390 \times 844$ | 1. Background timeline dimmed under dark backdrop overlay.<br>2. Modal sheet with warning alert icon in amber circle.<br>3. Title: `Xung đột chỉnh sửa lịch trình`.<br>4. **Honest Generic Warning:** `Lịch trình trên máy chủ đã thay đổi trong khi bạn đang chỉnh sửa. Phiên bản hiện tại của bạn không còn là dữ liệu mới nhất.`<br>5. **Honesty Verification:** Zero fabricated actor names, zero fake timestamps, zero speculative diff boxes.<br>6. Actions: Primary `Tải lại lịch trình mới nhất` and secondary `Hủy bỏ thay đổi của bạn`. No raw HTTP error codes. | **PASS** |
| [`shared-itinerary-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Top navbar: Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`) + User badge.<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Lịch trình chung`.<br>3. Col 1 ($340\text{px}$): 4-day navigation list ($300\text{k} + 850\text{k} + 1.200\text{k} + 450\text{k} = 2.800.000\text{ đ}$), 3 members with verified checks and roles, chat link `Mở Trò chuyện nhóm đồng hành`.<br>4. Col 2 ($740\text{px}$): Day header with `Bản đồ`, `Thêm hoạt động`, `Chỉnh sửa`, 4 timeline cards with times, costs, notes, and transport modes.<br>5. Col 3 ($340\text{px}$): Budget analysis card with progress bar ($2.800.000\text{ đ} / 5.000.000\text{ đ}$, $56\%$, $+2.200.000\text{ đ}$ còn lại), Wandy AI assistant card with disclaimer.<br>6. **Clean Downstream Card:** Displays clean user-facing badge `Sắp có` (zero technical `T08.2.3.13` labels). Zero scrollbars. | **PASS** |

---

## 4. Design Acceptance Gate (TASK 08.2.3.12-R1)

- [x] **Budget demo consistency verified:** Mobile view and desktop workstation show strictly identical budget figures ($2.800.000\text{ đ}$ estimated / $5.000.000\text{ đ}$ total budget / $56\%$ progress bar / $+2.200.000\text{ đ}$ remaining).
- [x] **TripMember permission reality documented:** Accurately recorded that `POST /trips/:id/itinerary` and `DELETE /trips/:id/itinerary/:itemId` use `findById()`, enabling both Trip Owner and TripMember to add and delete ANY item.
- [x] **TripMember delete any item classified as policy risk:** Documented as `CURRENT BACKEND BEHAVIOR + PERMISSION / PRODUCT POLICY RISK`.
- [x] **Target contributor policy defined:** Trip Owner has full edit authority; Trip Member has contributor authority (propose/add). Arbitrary deletion and bulk AI overwrite belong to Owner.
- [x] **Unsupported "own proposal" rule removed:** Identified that `model ItineraryItem` has no `createdBy` or `ownerId` column; marked granular contribution ownership as `FUTURE SCHEMA / AUTHORIZATION WORK`.
- [x] **Read-only member role classified:** Documented as `FUTURE / POLICY TARGET`.
- [x] **Conflict detection classified honestly:** Documented as `DESIGN TARGET / IMPLEMENTATION GAP` (runtime detection is NOT CURRENT).
- [x] **Conflict UX defined honestly:** Mobile conflict mockup (`shared-itinerary-mobile-conflict-r1.png`) uses generic warning copy without fabricated actors, timestamps, or diff boxes.
- [x] **Technical task ID removed from UI:** Desktop UI renders clean user-facing `"Sắp có"` badge; zero `T08.2.3.13` tags.
- [x] **Master mockups regenerated:** `shared-itinerary-mobile-view-r1.png`, `shared-itinerary-mobile-conflict-r1.png`, and `shared-itinerary-desktop-r1.png` rendered and verified.
- [x] **Edit mockup preserved:** `shared-itinerary-mobile-edit-v1.png` preserved intact.
- [x] **Contract and audit docs synchronized:** `docs/design/gomate-shared-itinerary-contract-v1.md` and `docs/audit/ui/task-08.2.3.12-shared-itinerary-audit.md` fully updated.
- [x] **No source code changes:** `git diff apps/` is strictly empty.
- [x] **No database changes:** `schema.prisma` unmodified.
- [x] **No API changes:** API contracts unmodified.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
