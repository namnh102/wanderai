# GoMate Shared Itinerary — Capability & Permission Audit (TASK 08.2.3.12)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.12 — GOMATE SHARED ITINERARY: CANONICAL TRIP COLLABORATION & PERMISSION CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model GroupMember`, `model Place`, `model User`)
- Backend Code: `apps/backend/src/modules/trips/trips.controller.ts`, `apps/backend/src/modules/trips/trips.service.ts`
- Mobile Code: `apps/mobile/lib/features/trips/`
- AI Service: `apps/ai-service/app/routers/planner.py`
- Core Contract: `docs/design/gomate-shared-itinerary-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Master View V1: [`shared-itinerary-mobile-view-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-v1.png) ($390 \times 844$)
  - Mobile Master Edit V1: [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Conflict / Save Error V1: [`shared-itinerary-mobile-conflict-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-v1.png) ($390 \times 844$)
  - Desktop Master Workstation V1: [`shared-itinerary-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-v1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.12 executes an exhaustive technical audit of the GoMate itinerary and trip collaboration capabilities.

### Key Audit Findings:
1. **Canonical Itinerary Source of Truth:**
   - The itinerary data model belongs strictly to `model Trip` (`Trip` $\rightarrow$ `Itinerary` $\rightarrow$ `ItineraryItem`).
   - There is **NO `GroupItinerary` model** in `schema.prisma`. A Companion Group does not own a parallel or duplicate database table.
   - Deleting a Group, leaving a Group, or removing a GroupMember **never mutates or deletes the canonical Trip itinerary**.
2. **Authorization Reality:**
   - `findById(tripId, userId)` guards trip access. Both the **Trip Owner** and **Trip Members** can view the itinerary.
   - Individual item add (`POST /trips/:id/itinerary`) and delete (`DELETE /trips/:id/itinerary/:itemId`) are currently accessible to all Trip Members.
   - Bulk save / AI plan apply (`POST /trips/:id/itinerary/bulk`) is strictly locked to the **Trip Owner** (`trip.userId === userId`). Non-owners receive `403 Forbidden`.
   - **GroupMember status alone does NOT grant Trip access.** A user in a Group without a corresponding `TripMember` record is blocked with `403 Forbidden`.
3. **Mutation APIs & Operational Gaps:**
   - Add activity and delete activity endpoints are fully operational.
   - Single activity editing (`PUT /trips/:id/itinerary/:itemId`) is **MISSING** from the REST API.
   - Reordering activities and moving activities across days are **MISSING** dedicated batch endpoints.
4. **AI Planner Boundary:**
   - `POST /trips/:id/ai-plan` generates an in-memory preview using Gemini LLM and `TripContext`. **Zero database writes occur.**
   - Persistence happens only when the Trip Owner explicitly confirms and submits `POST /trips/:id/itinerary/bulk`.
   - Applying the plan executes within an atomic PostgreSQL transaction (`prisma.$transaction`).
5. **Concurrency & Versioning Reality:**
   - Neither `Itinerary` nor `ItineraryItem` has versioning columns (`version`, `revision`, `updatedAt`, `ETag`).
   - Concurrent modification protection is an **IMPLEMENTATION GAP**.
   - The contract defines an explicit conflict resolution UX (`shared-itinerary-mobile-conflict-v1.png`) instructing users to reload rather than silently overwriting.

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)

```prisma
model Trip {
  id              String       @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  userId          String       @map("user_id") @db.Uuid
  destinationId   String?      @map("destination_id") @db.Uuid
  title           String
  description     String?
  startDate       DateTime?    @map("start_date") @db.Date
  endDate         DateTime?    @map("end_date") @db.Date
  totalBudget     Int?         @map("total_budget")
  currency        String       @default("VND")
  travelStyle     TravelStyle? @map("travel_style")
  interests       String[]     @default([])
  status          TripStatus   @default(DRAFT)
  coverImage      String?      @map("cover_image")
  isAiGenerated   Boolean      @default(false) @map("is_ai_generated")
  createdAt       DateTime     @default(now()) @map("created_at") @db.Timestamptz
  updatedAt       DateTime     @updatedAt @map("updated_at") @db.Timestamptz
  deletedAt       DateTime?    @map("deleted_at") @db.Timestamptz

  user        User         @relation(fields: [userId], references: [id])
  destination Destination? @relation(fields: [destinationId], references: [id])
  members     TripMember[]
  itineraries Itinerary[]

  @@map("trips")
}

model TripMember {
  id     String @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tripId String @map("trip_id") @db.Uuid
  userId String @map("user_id") @db.Uuid
  role   String @default("member")

  trip Trip @relation(fields: [tripId], references: [id], onDelete: Cascade)
  user User @relation(fields: [userId], references: [id])

  @@unique([tripId, userId])
  @@map("trip_members")
}

model Itinerary {
  id        String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tripId    String    @map("trip_id") @db.Uuid
  dayNumber Int       @map("day_number")
  date      DateTime? @db.Date
  title     String?

  trip  Trip            @relation(fields: [tripId], references: [id], onDelete: Cascade)
  items ItineraryItem[]

  @@unique([tripId, dayNumber])
  @@map("itineraries")
}

model ItineraryItem {
  id            String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  itineraryId   String   @map("itinerary_id") @db.Uuid
  placeId       String?  @map("place_id") @db.Uuid
  orderIndex    Int      @map("order_index")
  startTime     String?  @map("start_time")
  endTime       String?  @map("end_time")
  activity      String
  notes         String?
  estimatedCost Int?     @map("estimated_cost")
  transportMode String?  @map("transport_mode")

  itinerary Itinerary @relation(fields: [itineraryId], references: [id], onDelete: Cascade)
  place     Place?    @relation(fields: [placeId], references: [id])

  @@map("itinerary_items")
}
```

### 2.2. Backend Controller & Service Inspection (`TripsService`)

1. **Authorization Check in `findById`:**
   ```typescript
   // apps/backend/src/modules/trips/trips.service.ts
   const isMember = trip.members.some((m) => m.userId === userId);
   if (trip.userId !== userId && !isMember) {
     throw new ForbiddenException('Bạn không có quyền xem chuyến đi này');
   }
   ```
2. **Owner-Only Guard on Bulk Save / AI Apply:**
   ```typescript
   // apps/backend/src/modules/trips/trips.service.ts:404
   if (trip.userId !== userId) {
     throw new ForbiddenException('Chỉ chủ chuyến đi mới có quyền lưu lịch trình');
   }
   ```
3. **Atomic Transaction in `bulkSaveItinerary`:**
   ```typescript
   // apps/backend/src/modules/trips/trips.service.ts:412
   await this.prisma.$transaction(async (tx) => {
     if (dto.replaceExisting !== false) {
       await tx.itineraryItem.deleteMany({ where: { itinerary: { tripId } } });
       await tx.itinerary.deleteMany({ where: { tripId } });
     }
     for (const day of dto.days) {
       const itinerary = await tx.itinerary.upsert({ ... });
       // create itinerary items...
     }
     await tx.trip.update({
       where: { id: tripId },
       data: { isAiGenerated: true, status: TripStatus.PLANNED },
     });
   });
   ```

### 2.3. Mobile Client Inspection (`apps/mobile/lib/features/trips/`)

1. **Trip Detail Screen (`trip_detail_screen.dart`):**
   - Renders days sequentially with items displaying `orderIndex`, `activity`, `startTime`, `estimatedCost`, `notes`.
   - Contains modal `_showAddItineraryDialog` calling `POST /trips/:id/itinerary`.
   - Contains item delete action calling `DELETE /trips/:id/itinerary/:itemId`.
   - Contains AI plan generator `_handleGenerateAiPlan` calling `POST /trips/:id/ai-plan`.
   - Displays `_showAiPlanPreviewModal` with `Ap dung vao chuyen di` calling `POST /trips/:id/itinerary/bulk`.

### 2.4. AI Planner Inspection (`apps/ai-service/app/routers/planner.py`)

- Endpoint: `POST /planner`
- Prompt builder: `build_planner_prompt` takes destination, days (1..14), dates, budget, travel style, interests, and custom prompt.
- LLM Output: Parsed into `PlanResponse` (overview, days, items with estimated costs, general tips, budget analysis).
- Pure computation: Does NOT interact with database directly.

---

## 3. Data Model Audit Matrix

| Model | Field | Type | Relation / Constraint | Nullable | Current Purpose | Limitation / Gap |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **`Trip`** | `id` | `Uuid` | Primary Key | NO | Unique trip identifier | Generated via `gen_random_uuid()` |
| | `userId` | `Uuid` | FK -> `User.id` | NO | Creator / Owner of the trip | Single owner model |
| | `destinationId` | `Uuid` | FK -> `Destination.id` | YES | Linked destination POI pool | Optional |
| | `title` | `String` | None | NO | Trip title | Max length unconstrained in DB |
| | `description` | `String` | None | YES | Trip overview notes | Optional |
| | `startDate` | `Date` | None | YES | First day of trip | Date only (no time) |
| | `endDate` | `Date` | None | YES | Last day of trip | Date only (no time) |
| | `totalBudget` | `Int` | None | YES | Total trip budget (VND) | Integer VND; no currency conversion |
| | `currency` | `String` | Default `"VND"` | NO | Currency symbol | Default VND |
| | `travelStyle` | `TravelStyle` | Enum | YES | `backpacker`, `budget`, etc. | Single enum |
| | `interests` | `String[]` | Array | NO | Interest tags | Plain string array |
| | `status` | `TripStatus` | Default `DRAFT` | NO | `DRAFT`, `PLANNED`, etc. | Lifecycle status |
| | `coverImage` | `String` | None | YES | Cover photo URL | Optional |
| | `isAiGenerated` | `Boolean` | Default `false` | NO | Flag if planned by AI | Set on bulk save |
| | `createdAt` | `Timestamptz`| Default `now()` | NO | Creation timestamp | System managed |
| | `updatedAt` | `Timestamptz`| `@updatedAt` | NO | Last update timestamp | Auto-updated by Prisma |
| | `deletedAt` | `Timestamptz`| None | YES | Soft-delete timestamp | Soft delete flag |
| **`TripMember`** | `id` | `Uuid` | Primary Key | NO | Membership record | Generated via `gen_random_uuid()` |
| | `tripId` | `Uuid` | FK -> `Trip.id` (Cascade) | NO | Bound trip | Cascade deleted with Trip |
| | `userId` | `Uuid` | FK -> `User.id` (Restrict) | NO | Bound user | `@@unique([tripId, userId])` |
| | `role` | `String` | Default `"member"` | NO | Membership role | String column (`"owner"`, `"member"`) |
| **`Itinerary`** | `id` | `Uuid` | Primary Key | NO | Single day itinerary record | One record per day |
| | `tripId` | `Uuid` | FK -> `Trip.id` (Cascade) | NO | Bound trip | `@@unique([tripId, dayNumber])` |
| | `dayNumber` | `Int` | None | NO | Day sequence index (1..14) | 1-indexed day number |
| | `date` | `Date` | None | YES | Calendar date of this day | Optional; derived from startDate |
| | `title` | `String` | None | YES | Daily highlight title | e.g. "Ngày 1: Biển Mỹ Khê" |
| **`ItineraryItem`** | `id` | `Uuid` | Primary Key | NO | Activity record | One record per activity |
| | `itineraryId` | `Uuid` | FK -> `Itinerary.id` (Cascade) | NO | Bound day | Cascade deleted with Itinerary |
| | `placeId` | `Uuid` | FK -> `Place.id` (Restrict) | YES | Canonical POI reference | Nullable for manual activities |
| | `orderIndex` | `Int` | None | NO | Chronological position in day | Integer sequence (1, 2, 3...) |
| | `startTime` | `String` | None | YES | Start time string | e.g. `"09:00"`, string format |
| | `endTime` | `String` | None | YES | End time string | e.g. `"11:00"`, string format |
| | `activity` | `String` | None | NO | Activity description / name | Text string |
| | `notes` | `String` | None | YES | Travel tips / notes | Text string |
| | `estimatedCost`| `Int` | None | YES | Estimated cost in VND | Integer VND |
| | `transportMode`| `String` | None | YES | Transport mode | `"walk"`, `"taxi"`, `"bus"`, etc. |
| **`Group`** | `id` | `Uuid` | Primary Key | NO | Group identifier | Independent companion group |
| | `tripId` | `Uuid` | Loose FK (no Prisma relation) | YES | Linked trip UUID | Nullable, no cascade constraint |
| | `name` | `String` | None | NO | Group name | e.g. "Nhóm Đà Nẵng 4N3Đ" |
| **`GroupMember`** | `id` | `Uuid` | Primary Key | NO | Group member record | Independent from TripMember |
| | `groupId` | `Uuid` | FK -> `Group.id` (Cascade) | NO | Bound group | `@@unique([groupId, userId])` |
| | `userId` | `Uuid` | FK -> `User.id` (Restrict) | NO | Member user | |
| | `role` | `String` | Default `"member"` | NO | `"admin"`, `"member"` | Group role |

---

## 4. Capability Matrix (20 Dimensions)

| Dimension | Backend | Flutter | Database | AI Service | Design Contract | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Canonical Itinerary** | Yes | Yes | `Trip` owns `Itinerary` | Yes | Section 4 | **CURRENT** | `Trip` owns `Itinerary` $\rightarrow$ `ItineraryItem`. |
| **View Itinerary** | Yes | Yes | `TripMember` | N/A | Section 7 | **CURRENT** | `GET /trips/:id` returns itinerary items. |
| **Trip Authorization** | Yes | Partial | `findById` guard | N/A | Section 6 | **CURRENT** | Throws 403 Forbidden for non-members. |
| **Group Access Bridge**| Missing | Missing | Loose `Group.tripId` | N/A | Section 5 | **DESIGN TARGET** | Navigates from Group to linked Trip context. |
| **Create Activity** | Yes | Yes | `ItineraryItem` | N/A | Section 9 | **CURRENT** | `POST /trips/:id/itinerary` appends item. |
| **Edit Activity** | Missing | Missing | `ItineraryItem` | N/A | Section 10 | **GAP / TARGET** | No `PUT /trips/:id/itinerary/:itemId` endpoint. |
| **Delete Activity** | Yes | Yes | `ItineraryItem` | N/A | Section 11 | **CURRENT** | `DELETE /trips/:id/itinerary/:itemId` hard delete. |
| **Reorder Activity** | Missing | Missing | `ItineraryItem.orderIndex` | N/A | Section 12 | **GAP / TARGET** | `orderIndex` exists, but batch reorder API missing. |
| **Move Across Day** | Missing | Missing | `ItineraryItem.itineraryId` | N/A | Section 12 | **GAP / TARGET** | Requires changing `itineraryId` foreign key. |
| **Cost / Budget Summary**| Yes | Yes | `estimatedCost` | Yes | Section 13 | **CURRENT** | Integer VND derived. Separate from expense ledger. |
| **AI Generate** | Yes | Yes | `AiSession` | Yes | Section 14 | **CURRENT** | `POST /trips/:id/ai-plan` via Gemini LLM. |
| **AI Preview** | Yes | Yes | Memory only | Yes | Section 15 | **CURRENT** | Preview sheet displays days, items, budget analysis. |
| **AI Apply** | Yes (Owner) | Yes | `prisma.$transaction` | N/A | Section 16 | **CURRENT (Owner)**| `POST /trips/:id/itinerary/bulk` replaces items. |
| **Atomic Apply** | Yes | Yes | Prisma Transaction | N/A | Section 16 | **CURRENT** | All-or-nothing database transaction. |
| **Concurrent Edit Protection** | Missing | Missing | No `version` column | N/A | Section 17 | **GAP** | Neither `Itinerary` nor `ItineraryItem` has versioning. |
| **Conflict Detection** | Missing | Missing | No `updatedAt` on Items | N/A | Section 18 | **DESIGN TARGET** | Target UX prompts user to reload latest version. |
| **Change History** | Missing | Missing | No audit log table | N/A | Section 20 | **FUTURE** | No `createdBy` / change history in database. |
| **Realtime Sync** | Missing | Missing | No WebSocket gateway | N/A | Section 17 | **FUTURE** | No realtime collaborative cursors or presence. |
| **Map Integration** | Yes | Yes | `Place` PostGIS coords | N/A | Section 21 | **CURRENT** | Opens existing verified places on map view. |
| **Push Notifications**| Missing | Missing | No notification service| N/A | Section 22 | **FUTURE** | No FCM/APNs in repo; no instant delivery promises. |

---

## 5. Master Mockup Verification (4 Master Artifacts)

All 4 master mockups were generated and verified at `docs/audit/evidence/ui-08.2.3.12/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`shared-itinerary-mobile-view-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-v1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `Lịch trình chung` with subtitle `Khám phá Đà Nẵng 4N3Đ`.<br>2. Trip Hero: Date range `15/10 - 18/10/2026 (4 ngày)`, role badge `Bạn là Chủ chuyến đi`, budget progress bar (Dự tính `3.200.000 đ` / Ngân sách `5.000.000 đ`).<br>3. Day selector scroll with active pill `Ngày 1 · 15/10`.<br>4. Day header: `Ngày 1: Biển Mỹ Khê & Bán đảo Sơn Trà` with day cost badge `300.000 đ`.<br>5. Timeline items: 4 chronological activities with order numbers, time badges, verified place addresses, costs, and transport modes.<br>6. Bottom action bar: `Wandy AI` and `Chỉnh sửa lịch trình`.<br>7. Canonical 5-tab root navigation (Chuyến đi active). Zero developer tags. | **PASS** |
| [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy` (left), title `Chỉnh sửa lịch trình`, and `Lưu` (right).<br>2. Hint banner: `Kéo giữ biểu tượng bên trái để sắp xếp lại thứ tự hoạt động`.<br>3. Day pills with activity counts: `Ngày 1 (4)`, `Ngày 2 (3)`, etc.<br>4. Edit list: Drag handles `≡` on the left, editable time and activity names, delete action `🗑️` on the right.<br>5. Action: `+ Thêm hoạt động vào Ngày 1`.<br>6. Wandy AI proposal card with explicit disclaimer: `Wandy tạo bản xem trước, không tự động lưu đè`.<br>7. Clean production UI; no fake realtime avatars. | **PASS** |
| [`shared-itinerary-mobile-conflict-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-v1.png) | Mobile | $390 \times 844$ | 1. Background timeline dimmed under dark backdrop overlay.<br>2. Modal sheet with warning alert icon in amber circle.<br>3. Title: `Xung đột chỉnh sửa lịch trình`.<br>4. Explanatory text: `Lịch trình vừa được cập nhật bởi một thành viên khác trong nhóm...`<br>5. Detail box: Shows modifying user (`Lê Hoàng Nam`), timestamp (`09:32 hôm nay`), and change summary (`Thêm điểm Chợ Đêm Helio`).<br>6. Actions: Primary `Tải lại lịch trình mới nhất` and secondary `Hủy bỏ thay đổi của bạn`. No raw HTTP error codes. | **PASS** |
| [`shared-itinerary-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-v1.png) | Desktop | $1440 \times 900$ | 1. Top navbar: Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`) + User badge.<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Lịch trình chung`.<br>3. Col 1 ($340\text{px}$): 4-day navigation list with activity counts and costs, 3 members with verified checks and roles, chat link `Mở Trò chuyện nhóm đồng hành`.<br>4. Col 2 ($740\text{px}$): Day header with `Bản đồ`, `Thêm hoạt động`, `Chỉnh sửa`, 4 timeline cards with times, costs, notes, and transport modes.<br>5. Col 3 ($340\text{px}$): Budget analysis card with progress bar, Wandy AI assistant card with disclaimer, downstream expense card (`Sắp có · TASK 08.2.3.13`). Zero scrollbars. | **PASS** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.12)

- [x] **Exact Trip/Itinerary schema audited:** Models `Trip`, `TripMember`, `Itinerary`, `ItineraryItem`, `Group`, `GroupMember` verified in `schema.prisma`.
- [x] **No duplicate Group itinerary introduced:** Zero `GroupItinerary` model; confirmed Trip as single source of truth.
- [x] **Trip itinerary remains canonical source:** Group collaboration is an interactive visualization over the canonical Trip itinerary.
- [x] **GroupMember != edit permission locked:** Group membership does not grant automatic itinerary editing rights.
- [x] **Match != itinerary access locked:** Matched candidate without Trip invitation receives 403 Forbidden.
- [x] **TripMember role audited:** `TripMember.role` defaults to `"member"`. Owner has full edit authority; bulk save is owner-only.
- [x] **View permission proven:** `findById` allows Trip Owner and Trip Members; blocks strangers.
- [x] **Edit permission proven:** Add and delete items are verified by `findById`; bulk save verifies `trip.userId === userId`.
- [x] **Create capability audited:** `POST /trips/:id/itinerary` appends items with `dayNumber`, `activity`, `placeId`, `cost`.
- [x] **Edit capability audited:** Single-item edit endpoint is an open API GAP.
- [x] **Delete capability audited:** `DELETE /trips/:id/itinerary/:itemId` executes hard delete with confirmation dialog.
- [x] **Reorder capability audited:** `orderIndex` is persisted, but dedicated batch reorder endpoint is an API GAP.
- [x] **Day movement audited:** Moving across days requires updating foreign key `itineraryId`; documented as target GAP.
- [x] **Budget data source audited:** Derived from stored integer `estimatedCost`; completely separate from Shared Expense.
- [x] **Shared Expense kept separate:** Explicitly isolated from itinerary activities (deferred to TASK 08.2.3.13).
- [x] **AI generation != mutation:** Wandy AI generates in-memory preview via `POST /trips/:id/ai-plan`; no immediate DB write.
- [x] **Preview before Apply locked:** Client inspects preview sheet before triggering explicit save CTA.
- [x] **Apply authorization defined:** Only the Trip Owner can invoke `POST /trips/:id/itinerary/bulk`.
- [x] **Atomic apply reality audited:** Bulk save runs inside `prisma.$transaction`.
- [x] **Concurrency/versioning audited:** Identified lack of versioning on Itinerary models as an implementation gap.
- [x] **Conflict UX defined:** Conflict modal prompts reload and prevents silent data overwrite.
- [x] **No fake realtime collaboration:** Zero simulated live cursor presence or false auto-sync claims.
- [x] **Membership-loss behavior defined:** Leaving group does not delete itinerary; losing trip membership revokes access.
- [x] **Group deletion does not delete Trip itinerary:** Cascade deletes only `GroupMember` and `Message`.
- [x] **Mobile view created:** [`shared-itinerary-mobile-view-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-v1.png) verified ($390 \times 844$).
- [x] **Mobile edit created:** [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) verified ($390 \times 844$).
- [x] **Mobile conflict/error created:** [`shared-itinerary-mobile-conflict-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-v1.png) verified ($390 \times 844$).
- [x] **Desktop master created:** [`shared-itinerary-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-v1.png) verified ($1440 \times 900$).
- [x] **Canonical root IA preserved:** Desktop renders `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`.
- [x] **No source changes:** `git diff apps/` is empty.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
