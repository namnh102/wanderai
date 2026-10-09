# GoMate Shared Itinerary — Canonical Trip Collaboration & Permission Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION  
**Task:** TASK 08.2.3.12 — GOMATE SHARED ITINERARY: CANONICAL TRIP COLLABORATION & PERMISSION CONTRACT V1  
**Module:** Shared Travel Itinerary (`/trips/:id/itinerary`)  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$), Tablet ($768 \times 1024$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Place`, `model Group`, `model GroupMember`, `model User`)
- Foundation Contracts: `docs/design/gomate-group-foundation-contract-v1.md`, `docs/design/gomate-group-chat-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Master View R1 (Budget Aligned): [`shared-itinerary-mobile-view-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-r1.png) ($390 \times 844$)
  - Mobile Master Edit V1: [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Conflict R1 (Generic Warning): [`shared-itinerary-mobile-conflict-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-r1.png) ($390 \times 844$)
  - Desktop Master Workstation R1 (Clean Badge): [`shared-itinerary-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-r1.png) ($1440 \times 900$)
  - Baseline V1 Pre-Correction Visuals: [`shared-itinerary-mobile-view-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-v1.png), [`shared-itinerary-mobile-conflict-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-v1.png), [`shared-itinerary-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-v1.png)

---

## 1. Product Role & Architectural Vision

The **Shared Itinerary** (`Lịch trình chung`) module provides the canonical, collaborative timeline workspace for travelers planning and executing a trip together in GoMate.

Unlike generic shared note-taking tools or isolated messaging apps where travel plans get fragmented across conversation threads, GoMate Shared Itinerary establishes:
1. **Single Source of Truth:** A unified chronological itinerary anchored directly to the parent `Trip`.
2. **Contextual Collaboration Layer:** An interactive shared viewing and editing experience rendered across Companion Groups, without creating redundant duplicate databases.
3. **Deterministic Planning Integrity:** Time-ordered activities with real geographic places, verifiable budget derivations, and human-confirmed AI assistance.

---

## 2. Current vs Target Capability Matrix

| Capability Dimension | Backend NestJS | Flutter Client | Database (`schema.prisma`) | AI Service | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Canonical Itinerary** | Current | Current | `model Itinerary`, `model ItineraryItem` | Current | Section 4 | **CURRENT** | Owned directly by `Trip`. Cascade deletes with Trip. |
| **View Itinerary** | Current | Current | `model TripMember`, `Trip.userId` | N/A | Section 7 | **CURRENT** | `GET /trips/:id` allows Trip Owner and Trip Members. |
| **Trip Authorization** | Current | Partial | `findById` guard | N/A | Section 6 | **CURRENT** | Throws 403 Forbidden for non-members. |
| **Group Access Bridge**| Missing | Missing | Loose `Group.tripId` | N/A | Section 5 | **DESIGN TARGET** | Navigates from Group to linked Trip context. |
| **Create Activity** | Current | Current | `model ItineraryItem` | N/A | Section 9 | **CURRENT** | `POST /trips/:id/itinerary` appends item. |
| **Edit Activity** | Missing | Missing | `model ItineraryItem` | N/A | Section 10 | **GAP / TARGET** | No `PUT /trips/:id/itinerary/:itemId` endpoint. |
| **Delete Activity** | Current | Current | `model ItineraryItem` | N/A | Section 11 | **CURRENT (Policy Risk)**| `DELETE /trips/:id/itinerary/:itemId` hard delete. TripMember can delete ANY item (Product/Permission Risk). |
| **Reorder Activity** | Missing | Missing | `ItineraryItem.orderIndex` | N/A | Section 12 | **GAP / TARGET** | `orderIndex` exists, but dedicated batch reorder endpoint is missing. |
| **Move Across Day** | Missing | Missing | `ItineraryItem.itineraryId` | N/A | Section 12 | **GAP / TARGET** | Requires changing `itineraryId` foreign key. |
| **Budget Derivation** | Current | Current | `ItineraryItem.estimatedCost` | Current | Section 13 | **CURRENT** | Integer VND derived daily/total. Separate from Expense. |
| **AI Generate Plan** | Current | Current | `AiSession` | Current | Section 14 | **CURRENT** | `POST /trips/:id/ai-plan` via Gemini LLM. |
| **AI Preview Sheet** | Current | Current | In-memory only | Current | Section 15 | **CURRENT** | Displays overview, daily items, budget analysis. |
| **AI Apply Plan** | Current | Current | `prisma.$transaction` | N/A | Section 16 | **CURRENT (Owner)**| `POST /trips/:id/itinerary/bulk` replaces items. |
| **Atomic Apply** | Current | Current | Prisma Transaction | N/A | Section 16 | **CURRENT** | All-or-nothing database transaction. |
| **Concurrent Edit Protection** | Missing | Missing | Missing `version` / `ETag` | N/A | Section 17 | **GAP** | Neither `Itinerary` nor `ItineraryItem` has versioning. |
| **Conflict Detection**| Missing | Missing | Missing `version` / `ETag` | N/A | Section 18 | **GAP / TARGET** | Runtime detection is missing; Conflict UX is design target. |
| **Change History** | Missing | Missing | Missing `createdBy` / log | N/A | Section 20 | **FUTURE / SCHEMA GAP** | No audit trail table in database. |
| **Realtime Sync** | Missing | Missing | Missing WebSocket | N/A | Section 17 | **FUTURE** | No realtime collaborative cursors or presence. |
| **Map Integration** | Current | Current | `Place` PostGIS coordinates | N/A | Section 21 | **CURRENT** | Opens existing verified places on map view. |
| **Push Notifications**| Missing | Missing | Missing Service | N/A | Section 22 | **FUTURE** | No FCM/APNs in repo; no instant delivery promises. |

---

## 3. Exact Data Model Audit

### 3.1. Verified Prisma Definitions (`apps/backend/prisma/schema.prisma`)

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
  role   String @default("member") // "owner", "member"

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

model Group {
  id          String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  name        String
  description String?
  tripId      String?  @map("trip_id") @db.Uuid
  createdAt   DateTime @default(now()) @map("created_at") @db.Timestamptz

  members  GroupMember[]
  messages Message[]

  @@map("groups")
}

model GroupMember {
  id      String @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  groupId String @map("group_id") @db.Uuid
  userId  String @map("user_id") @db.Uuid
  role    String @default("member") // "admin", "member"

  group Group @relation(fields: [groupId], references: [id], onDelete: Cascade)
  user  User  @relation(fields: [userId], references: [id])

  @@unique([groupId, userId])
  @@map("group_members")
}
```

---

## 4. Canonical Source of Truth Decision

> [!IMPORTANT]
> **Core Architectural Invariant:**
> $$\textbf{Trip} \longrightarrow \textbf{Canonical Itinerary} \longrightarrow \textbf{Group Shared Itinerary View}$$
> A Companion Group linked to a Trip **MUST NOT** own an independent or duplicate itinerary database table.

1. **Single Source of Truth:**
   - There is NO `model GroupItinerary`.
   - The itinerary data model is strictly rooted in `model Trip` (`Trip` $\rightarrow$ `Itinerary` $\rightarrow$ `ItineraryItem`).
   - "Shared Itinerary" is a **collaboration and visualization layer** presented to members participating in a Trip or linked Companion Group.
2. **Immutability of Itinerary across Group Lifecycle:**
   - Deleting a `Group` does **NOT** delete the canonical Trip itinerary.
   - Leaving a `Group` does **NOT** alter the Trip itinerary.
   - Removing a `GroupMember` does **NOT** delete or mutate itinerary activities.

---

## 5. Group ↔ Trip ↔ Itinerary Relationship

```
+-------------------------------------------------------------------------+
|                                  TRIP                                   |
|  - id: UUID                                                             |
|  - userId: UUID (Owner)                                                 |
|  - title, destination, startDate, endDate, totalBudget                  |
+--------------------+--------------------------------+-------------------+
                     | 1:N                            | 1:N
                     ▼                                ▼
       +---------------------------+    +---------------------------+
       |        TRIP MEMBER        |    |         ITINERARY         |
       | - userId                  |    | - dayNumber: Int (1..14)  |
       | - role: "owner" | "member"|    | - date, title             |
       +---------------------------+    +-------------+-------------+
                     ▲                                | 1:N
                     | Contextual bridge              ▼
       +-------------+-------------+    +---------------------------+
       |           GROUP           |    |      ITINERARY ITEM       |
       | - id: UUID                |    | - orderIndex: Int         |
       | - tripId: UUID (Linked)   |    | - startTime, endTime      |
       | - name, description       |    | - activity, placeId       |
       +-------------+-------------+    | - estimatedCost, notes    |
                     | 1:N              +---------------------------+
                     ▼
       +---------------------------+
       |       GROUP MEMBER        |
       | - userId                  |
       | - role: "admin" | "member"|
       +---------------------------+
```

---

## 6. Access Authorization & Permission Invariants

### 6.1. Explicit Permission Matrix

| User Relationship | View Itinerary | Add Activity | Delete Activity | Bulk Save / Apply | Run AI Preview | Runtime Authorization Guard |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Trip Owner** (`trip.userId == user.id`) | **YES** | **YES** | **YES** | **YES** | **YES** | Full admin rights (`TripsService`). |
| **Trip Member** (`trip.members.some`) | **YES** | **YES** (Current) | **YES** (Policy Risk)| **NO** (403 Forbidden)| **YES** (Preview only)| Passed `findById`; can delete ANY item (Policy Risk); blocked on bulk save. |
| **GroupMember only** (Not in TripMember)| **NO** (Blocked)| **NO** (Blocked)| **NO** (Blocked)| **NO** (Blocked) | **NO** (Blocked)| `findById` throws 403 `'Bạn không có quyền xem chuyến đi này'`. |
| **TripMember + GroupMember** | **YES** | **YES** | **YES** (Policy Risk)| **NO** (Owner only)| **YES** | Evaluated strictly via `TripMember` contract. |
| **Matched Buddy only** (No Trip invite)| **NO** | **NO** | **NO** | **NO** | **NO** | 403 Forbidden. No data leakage. |
| **Unrelated User (Stranger)** | **NO** | **NO** | **NO** | **NO** | **NO** | 403 Forbidden. |

### 6.2. Critical Permission Invariants Locked

> [!WARNING]
> **Permission Invariants:**
> $$\textbf{GroupMember} \centernot\implies \textbf{Itinerary Edit Permission}$$
> $$\textbf{Matched Buddy} \centernot\implies \textbf{Trip Access}$$

1. **Group Membership is Social Collaboration:** Being a member of a group chat does NOT grant arbitrary rights to overwrite the trip itinerary.
2. **Trip Access Requires Trip Membership:** Entry to Shared Itinerary from a Group must verify that the user is an active `TripMember` (or Trip Owner).
3. **Defense in Depth:** Client-side hidden buttons or UI states are NOT authorization. Every mutation is guarded on the NestJS backend.

---

## 7. View Permission Specification

- **Requirement:** A user entering the Shared Itinerary view must possess either:
  1. `trip.userId === currentUserId` (Trip Owner), OR
  2. `trip.members.some(m => m.userId === currentUserId)` (Trip Member).
- **Denial Behavior:** If a user attempts to access an itinerary without proper Trip authorization:
  - Backend responds: `403 Forbidden` (`{"statusCode": 403, "message": "Bạn không có quyền xem chuyến đi này"}`).
  - Client displays an explicit, friendly access denied view:
    *“Bạn không có quyền xem lịch trình của chuyến đi này.”*
  - Zero itinerary, destination, or member data is leaked in the HTTP response.

---

## 8. Edit Permission Specification & Policy Evolution

### 8.1. Current Backend Reality & Permission Risk Classification
- **Verified Code Behavior:**
  - `POST /trips/:id/itinerary` (add item) and `DELETE /trips/:id/itinerary/:itemId` (delete item) verify `findById(tripId, userId)`.
  - Therefore, both **Trip Owner** and **TripMember** can currently add items AND delete ANY item in the itinerary.
  - **Explicit Risk Classification:**
    $$\textbf{TripMember DELETE ANY ITEM} = \textbf{CURRENT BACKEND BEHAVIOR} + \textbf{PERMISSION / POLICY RISK}$$
    Because `findById` grants mutation access without validating creator identity, any TripMember can currently delete items created by the owner or other members. This is an acknowledged backend policy risk that must not be hidden.

### 8.2. Removal of Unsupported "Own Proposal" Semantics
- **Database Reality:** `model ItineraryItem` contains NO `createdBy`, `createdByUserId`, `ownerId`, `proposalBy`, or `proposalStatus` columns.
- **Contract Correction:** The contract strictly **removes** any claim that the backend can identify "activity created by this member" or "their own proposal". Current schema cannot prove item ownership.
- **Future Contribution Model:** Supporting *"TripMember may edit/delete only their own contributions"* requires a future database migration (e.g. `createdByUserId` or an `ItineraryProposal` model) and is classified strictly as **FUTURE SCHEMA / AUTHORIZATION WORK**.

### 8.3. Recommended Target Contributor Policy (Design Target V1)
- **Trip Owner:** Full editorial authority (Create, Edit, Delete, Reorder, AI Apply, Trip metadata update).
- **Trip Member:** Contributor authority (View itinerary, Add activities, Run AI preview). Delete, reorder, and bulk apply are restricted to Trip Owner until a granular contribution ownership model exists.
- **Read-Only Member Semantics:** `TripMember.role` currently only stores `"owner"` or `"member"`. There is no proven `"viewer"` or `"readonly"` role in current code. "Read-Only Trip Member" is classified strictly as a **FUTURE / POLICY TARGET**.

---

## 9. Activity Create Contract

- **Endpoint:** `POST /trips/:id/itinerary`
- **Request Payload:**
  ```json
  {
    "dayNumber": 1,
    "activity": "Ăn sáng Mì Quảng Bếp Trang",
    "startTime": "08:00",
    "endTime": "09:00",
    "placeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "notes": "Đặc sản mì Quảng tôm thịt trứng",
    "estimatedCost": 50000,
    "transportMode": "taxi"
  }
  ```
- **Execution Lifecycle:**
  1. Validates `dayNumber >= 1`.
  2. Upserts `Itinerary` for `(tripId, dayNumber)`.
  3. Computes `orderIndex = count + 1`.
  4. Persists `ItineraryItem` and links optional `placeId`.
  5. Returns created `ItineraryItem` with joined place summary (`id`, `name`, `address`).

---

## 10. Activity Edit Contract

- **Current Status:** **DESIGN TARGET / API GAP**.
- **Issue:** No single-item update endpoint (`PUT /trips/:id/itinerary/:itemId`) exists in `TripsController`. Single edits currently require either re-adding or executing an owner-only `bulkSaveItinerary`.
- **Target Specification:**
  - **Endpoint:** `PUT /trips/:id/itinerary/:itemId`
  - **Allowed Fields:** `activity`, `startTime`, `endTime`, `notes`, `estimatedCost`, `transportMode`, `placeId`.
  - **Guard:** Checks that item belongs to `tripId` and requester is authorized.

---

## 11. Activity Delete Contract

- **Endpoint:** `DELETE /trips/:id/itinerary/:itemId`
- **Current Behavior:** Hard delete on `model ItineraryItem`.
- **Destructive Confirmation Rule:** Client UI MUST present an explicit confirmation dialog before dispatching the delete request:
  *“Xác nhận xóa: Bạn có chắc chắn muốn xóa hoạt động này khỏi lịch trình không?”*
  Actions: `[Hủy]` (Neutral), `[Xóa]` (Destructive red).
- **Failure Recovery:** If delete fails on network or server error, the item remains visible in the UI and a snackbar notification surfaces the failure.

---

## 12. Reorder & Day Movement Contract

- **Current Status:** **DESIGN TARGET / DATA GAP**.
- **Model Reality:** `ItineraryItem.orderIndex` exists as an integer. However, there is no dedicated `PUT /trips/:id/itinerary/reorder` endpoint.
- **Target Reorder Specification:**
  - **Endpoint:** `PUT /trips/:id/itinerary/:dayNumber/reorder`
  - **Payload:** `{"itemIds": ["uuid-1", "uuid-2", "uuid-3"]}`
  - **Server Action:** Updates `orderIndex` within an atomic transaction.
- **Moving Across Days:**
  - Moving an activity from Day 1 to Day 2 requires updating `itineraryId`.
  - In V1 UI, drag-and-drop across different days is **NOT** claimed as current runtime behavior.

---

## 13. Budget Derivation & Consistency Contract

> [!NOTE]
> **Budget Isolation Invariant:**
> $$\textbf{Activity Estimated Cost} \centernot\equiv \textbf{Shared Expense Ledger}$$

1. **Data Source:** Activity cost is derived strictly from stored `ItineraryItem.estimatedCost` (integer VND).
2. **Canonical Mathematical Formulations:**
   $$\text{dailyEstimatedCost} = \sum_{i \in \text{items of day}} \text{ItineraryItem.estimatedCost}_i$$
   $$\text{tripEstimatedCost} = \sum_{\text{all days}} \text{dailyEstimatedCost}$$
   $$\text{remainingBudget} = \text{Trip.totalBudget} - \text{tripEstimatedCost}$$
   $$\text{budgetUsagePercentage} = \text{round}\left(\frac{\text{tripEstimatedCost}}{\text{Trip.totalBudget}} \times 100\%\right)$$
3. **Cross-Platform Demo Consistency Locked:**
   - Same Trip + same itinerary MUST produce identical totals on Mobile and Desktop:
     - **Day 1:** $300.000\text{ VND}$
     - **Day 2:** $850.000\text{ VND}$
     - **Day 3:** $1.200.000\text{ VND}$
     - **Day 4:** $450.000\text{ VND}$
     - **Trip Estimated Total:** $2.800.000\text{ VND}$
     - **Trip Total Budget:** $5.000.000\text{ VND}$
     - **Remaining Buffer:** $+2.200.000\text{ VND}$
     - **Budget Usage:** $56\%$ (Progress bar fill rendered at exactly $56\%$).
4. **Expense Boundary:** This metric is purely a **planning estimate**. It does NOT track actual transaction receipts, payment splits, or who owes whom. Shared expenses are isolated in **TASK 08.2.3.13**.

---

## 14. AI Planner Integration Boundary

1. **Human-in-the-Loop Invariant:**
   $$\textbf{AI Generation} \ne \textbf{Immediate Database Mutation}$$
   Wandy AI **never** autonomously modifies or overwrites the saved itinerary.
2. **End-to-End Workflow:**
   $$\text{User triggers AI} \longrightarrow \text{Wandy generates preview} \longrightarrow \text{User inspects preview} \longrightarrow \text{Explicit Apply CTA} \longrightarrow \text{Atomic DB persist}$$
3. **Entry Point Copy:**
   - Label: `"Đề xuất lại với Wandy AI"`
   - Supporting copy: *"Wandy tạo bản đề xuất để bạn xem trước, không tự động lưu đè lên lịch trình hiện tại."*

---

## 15. Preview & Confirmation Contract

- **Preview Endpoint:** `POST /trips/:id/ai-plan` (Payload: optional `additionalPrompt`, `preferredPace`).
- **Response Format:** Returns structured `PlanResponse` containing overview, days, items, and `budgetAnalysis`. **Nothing is written to PostgreSQL.**
- **Preview Modal:** The client opens an interactive sheet displaying:
  - Daily activities breakdown with times, estimated costs, and transport modes.
  - Budget variance comparison against trip budget.
  - Action buttons: `[Hủy]` and `[Áp dụng vào chuyến đi]`.

---

## 16. Atomic Apply Contract

- **Endpoint:** `POST /trips/:id/itinerary/bulk`
- **Authorization Guard:** Strictly Trip Owner (`trip.userId === userId`).
- **Transaction Guarantee:**
  ```typescript
  await this.prisma.$transaction(async (tx) => {
    if (dto.replaceExisting !== false) {
      await tx.itineraryItem.deleteMany({ where: { itinerary: { tripId } } });
      await tx.itinerary.deleteMany({ where: { tripId } });
    }
    // Upsert days and create all items sequentially...
    await tx.trip.update({
      where: { id: tripId },
      data: { isAiGenerated: true, status: TripStatus.PLANNED },
    });
  });
  ```
- **Atomicity:** Either all days and items persist successfully, or the entire transaction rolls back. Partial, half-saved itineraries are prevented.

---

## 17. Concurrency & Versioning Reality

1. **Database Audit Reality:**
   - `model Itinerary` and `model ItineraryItem` possess **zero versioning columns** (`version`, `revision`, `updatedAt`, `ETag`).
   - Only `model Trip` contains `@updatedAt`.
   - Therefore, concurrent editing protection is an **IMPLEMENTATION GAP**.
2. **Capability Classification:**
   - **Conflict Detection:** `DESIGN TARGET / IMPLEMENTATION GAP`.
   - **Conflict UX:** `DESIGN SPECIFICATION`.
   - **Runtime Conflict Detection:** `NOT CURRENT`. (The current runtime has no version checking or `If-Match` mechanism; it does NOT automatically refuse stale writes yet).
3. **Future Concurrency Architecture Requirement:**
   - Add `version Int @default(1)` on the itinerary aggregate or an optimistic concurrency token.
   - Future mutation requests send `expectedVersion`.
   - Backend evaluates: if `currentVersion !== expectedVersion` $\rightarrow$ throw `409 Conflict`.
   - Audit trail attribution (who changed what, timestamp, exact diff) requires future `createdBy` / `updatedBy` columns and an `itinerary_change_logs` table.

---

## 18. Conflict Handling & Resolution Specification (Design Target)

When concurrent modification is detected by future version-checking infrastructure:
1. **Generic Conflict UI Standard (Zero Fabricated Diff):**
   - Master Artifact: [`shared-itinerary-mobile-conflict-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-r1.png) ($390 \times 844$).
   - Title: *“Xung đột chỉnh sửa lịch trình”*
   - Message: *“Lịch trình trên máy chủ đã thay đổi trong khi bạn đang chỉnh sửa. Phiên bản hiện tại của bạn không còn là dữ liệu mới nhất.”*
   - Honest Boundary: The UI strictly omits actor names, timestamps, and diff details because no change logs or creator IDs exist in current database schema.
2. **Resolution Actions:**
   - Primary: `[Tải lại lịch trình mới nhất]` (Re-fetches canonical state from `GET /trips/:id`).
   - Secondary: `[Hủy bỏ thay đổi của bạn]`.

---

## 19. Save & Error State Machine

```
   [IDLE]
     │
     ▼ (User initiates edit / add)
 [EDITING]
     │
     ▼ (User taps Save / Apply)
  [SAVING] ───(Network / Server Error)───► [SAVE_FAILED]
     │                                           │
     │ (Server ACK 200/201)                      ▼ (User taps Thử lại)
     ▼                                      [SAVING]
  [SAVED]
     │
     ▼ (Return to timeline)
   [IDLE]
```

- **Error Copy Standard:** Raw HTTP codes (500, 502) are NEVER presented to users.
  Standard copy: *"Không thể lưu thay đổi vào lịch trình. Vui lòng kiểm tra kết nối mạng."* with action `[Thử lại]`.

---

## 20. Membership Lifecycle & Data Preservation

1. **Group Member Leaves / Removed:**
   - Leaving the Companion Group does NOT mutate the Trip itinerary.
   - If the user is still a `TripMember`, their itinerary access follows `TripMember` rules.
2. **Trip Member Removed:**
   - If a user loses Trip membership, their access to Shared Itinerary is revoked immediately (`403 Forbidden`).
   - GroupMember status cannot bypass revoked Trip membership.
3. **Group Disbanded:**
   - Disbanding a Group cascades deletions only to `GroupMember` and `Message`.
   - The bound `Trip` and its `Itinerary` remain completely intact.
4. **Trip Deleted (Soft Delete):**
   - Trip is soft-deleted via `deletedAt = now()`.
   - `findById` filter `deletedAt: null` safely conceals the itinerary from all members.

---

## 21. Privacy & Place Provenance

1. **Place Provenance:**
   - Itinerary items referencing `model Place` inherit canonical OpenStreetMap data.
   - Coordinates, addresses, and place names are never fabricated. Missing factual fields remain honestly missing.
2. **Map Integration:**
   - The `"Xem trên bản đồ"` action extracts real `Place.latitude` and `Place.longitude` coordinates to render the interactive route/markers on the Map screen.

---

## 22. Boundaries with Chat & Expense

- **Group Chat Boundary:** Shared Itinerary is a structured planning workspace, not a chat room. It contains a navigational link to `"Mở Trò chuyện nhóm đồng hành"`, but does not embed message threads.
- **Shared Expense Boundary:** Itinerary displays estimated costs for budgeting purposes. Real expense tracking, bill splitting, and debt settlements belong strictly to **TASK 08.2.3.13**.

---

## 23. Multi-Platform Specifications

- **Mobile Viewport ($390 \times 844$):**
  - Single-column timeline with sticky status bar, trip hero with budget progress, horizontal day pills, chronological activity cards, bottom actions (`Wandy AI`, `Chỉnh sửa lịch trình`), and canonical 5-tab root navigation.
  - Master Artifacts:
    - View R1 (Budget Aligned): [`shared-itinerary-mobile-view-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-view-r1.png)
    - Edit V1: [`shared-itinerary-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-edit-v1.png)
    - Conflict R1 (Generic Warning): [`shared-itinerary-mobile-conflict-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-mobile-conflict-r1.png)
- **Desktop Viewport ($1440 \times 900$):**
  - Canonical 5-tab root navigation (`Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`).
  - Contextual breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Lịch trình chung`.
  - 3-column workstation:
    - Left ($340\text{px}$): Day navigation list with item counts and costs, member permissions summary, chat link.
    - Center ($740\text{px}$): Day header with actions (`Bản đồ`, `Thêm hoạt động`, `Chỉnh sửa`), detailed timeline items with addresses, costs, notes, transport modes.
    - Right ($340\text{px}$): Budget analysis card with progress bar, Wandy AI assistant card with disclaimer, downstream expense card (`Chi tiêu chuyến đi` · `Sắp có`, clean badge without technical task ID).
  - Master Artifact: [`shared-itinerary-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.12/shared-itinerary-desktop-r1.png)
- **Tablet Viewport ($768 \times 1024$):** 2-column layout (Left: Day & member summary, Right: Itinerary timeline and budget).

---

## 24. Accessibility Standards

- Interactive touch targets $\ge 44 \times 44\text{ dp}$.
- Semantic accessibility labels:
  - Reorder grip: `"Kéo để thay đổi thứ tự hoạt động"`
  - Delete button: `"Xóa hoạt động khỏi lịch trình"`
  - Day selector: `"Chọn Ngày 1, ngày 15 tháng 10"`
- Visual contrast: All text meets WCAG AA standards ($\ge 4.5:1$ against backgrounds).

---

## 25. Evolution Pathway

```
========================================================================
SHARED ITINERARY EVOLUTION PATHWAY
========================================================================

    [CURRENT DB & API FOUNDATION]
    - Trip -> Itinerary (dayNumber) -> ItineraryItem (activity, cost)
    - POST /trips/:id/itinerary (Add Item)
    - DELETE /trips/:id/itinerary/:itemId (Delete Item)
    - POST /trips/:id/ai-plan (Preview Plan)
    - POST /trips/:id/itinerary/bulk (Atomic Save - Owner Only)

        │
        ▼ (TASK 08.2.3.12: DESIGN CONTRACT LOCK)
    - Single source of truth: Trip owns itinerary (No GroupItinerary)
    - GroupMember != Edit permission locked
    - AI Generation != Mutation locked (Preview first)
    - Concurrency conflict resolution UX locked
    - 4 Master visual mockups (View, Edit, Conflict, Desktop)

        │
        ▼ (FUTURE BACKEND & PRISMA MIGRATIONS)
    - Endpoint: PUT /trips/:id/itinerary/:itemId (Single Item Edit)
    - Endpoint: PUT /trips/:id/itinerary/:day/reorder (Batch Reorder)
    - Migration: version / updatedAt on Itinerary & ItineraryItem (Optimistic Lock)
    - Migration: audit_logs (Change History & Attribution)
    - Realtime: WebSocket sync for collaborative editing cursors
========================================================================
```
