# GoMate Scheduling & Reminders — Capability Audit, Business Contract & Visual Mockup V1

**Status:** APPROVED ARCHITECTURAL CONTRACT & DESIGN LOCK  
**Task:** TASK 08.2.3.14 — GOMATE SCHEDULING & REMINDERS: CAPABILITY AUDIT, BUSINESS CONTRACT & VISUAL MOCKUP V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$), Tablet ($768 \times 1024$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model Notification`, `model User`)
- Backend Code: [`apps/backend/src/`](file:///d:/Do_an/wanderai/apps/backend/src/)
- Mobile Client Code: [`apps/mobile/lib/`](file:///d:/Do_an/wanderai/apps/mobile/lib/)
- Upstream Design Contracts:
  - [`docs/design/gomate-trip-user-flow-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-user-flow-spec-v1.md)
  - [`docs/design/gomate-trip-visual-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-visual-spec-v1.md)
  - [`docs/design/gomate-shared-itinerary-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-itinerary-contract-v1.md)
  - [`docs/design/gomate-group-foundation-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-foundation-contract-v1.md)
  - [`docs/design/gomate-group-chat-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-chat-contract-v1.md)
  - [`docs/design/gomate-shared-expense-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-expense-contract-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Reminder List R1: [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) ($390 \times 844$)
  - Mobile Create Reminder R1: [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) ($390 \times 844$)
  - Mobile Reminder Detail R1: [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) ($390 \times 844$)
  - Mobile Edit Reminder R1: [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) ($390 \times 844$)
  - Mobile Empty State V1: [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) ($390 \times 844$) [Preserved from V1]
  - Mobile Error State R1: [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) ($390 \times 844$)
  - Mobile Channels & Permissions (SUPERSEDED / FUTURE CONCEPT): [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) ($390 \times 844$) [Kept for audit history; removed from Master V1 visual scope because V1 has no notification runtime]
  - Desktop Master Workstation R1: [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) ($1440 \times 900$)

---

## 1. Product Role & Mission

The **GoMate Scheduling & Reminders** module empowers travelers to record, track, and contextualize critical temporal milestones throughout a shared trip — such as hotel check-ins, transit departures, attraction opening slots, dinner reservations, and luggage preparations.

It bridges the gap between passive calendar viewing and active trip execution, ensuring travelers never miss key moments while remaining strictly honest about background infrastructure capabilities.

---

## 2. First Principle: Three-Tier Architectural Boundary

A strict architectural demarcation is locked across three distinct systems:

$$\textbf{Reminder Record} \quad \ne \quad \textbf{Scheduler Engine} \quad \ne \quad \textbf{Notification Delivery Transport}$$

```
+--------------------------+       +--------------------------+       +--------------------------+
|      REMINDER RECORD     |       |     SCHEDULER ENGINE     |       |   NOTIFICATION DELIVERY  |
|  (Data Persistence Tier) |       |  (Temporal Worker Tier)  |       |   (Device Transport Tier)|
+--------------------------+       +--------------------------+       +--------------------------+
| * PostgreSQL database    | ----> | * Delayed job evaluation | ----> | * FCM (Android)          |
| * Target model Reminder  |       | * Redis delay / BullMQ   |       | * APNs (iOS)             |
| * Scheduled UTC instant  |       | * Evaluates now >= due   |       | * Local OS AlarmManager  |
| * Context FKs (Trip/Item)|       | * Idempotent dispatch    |       | * Lock-screen vibration  |
+--------------------------+       +--------------------------+       +--------------------------+
```

### Critical Axioms:
1. **Database persistence does NOT trigger a notification:** Having a row in a PostgreSQL table with `scheduledAtUtc` does nothing on its own unless an active worker or OS alarm evaluates it.
2. **A scheduler engine does NOT deliver push notifications:** A cron or queue worker firing at `07:00` only executes backend logic; it cannot vibrate a mobile device without device tokens and push gateway credentials.
3. **A visual UI mockup does NOT prove delivery capability:** Displaying an alarm clock icon or a "Saved" banner does not imply background OS push notifications exist in runtime.

---

## 3. Repository Capability Reality (Audit Verdict)

A comprehensive codebase audit confirms the exact baseline:

1. **Database Schema (`apps/backend/prisma/schema.prisma`):**
   - **`model Reminder`:** **MISSING** (Schema Gap).
   - **`model Notification`:** **PARTIAL** (Schema model exists at line 371 with `type NotificationType`, `title`, `body`, `isRead`, but has zero controllers or services in `apps/backend/src/`).
   - `NotificationType` enum lacks any `REMINDER` or `SCHEDULED_ALARM` types.
   - User table has zero `pushToken`, `deviceToken`, or `fcmToken` fields.
2. **Backend Framework & Services (`apps/backend/`):**
   - Scheduling decorators (`@nestjs/schedule`, `@Cron()`): **MISSING** in `package.json`.
   - Message Queues & Workers (`bull`, `bullmq`): **MISSING** in `package.json`.
   - Redis: `ioredis` is installed in `package.json` (`^5.3.2`) but has **ZERO imports** in backend source code.
   - Push Gateways (`firebase-admin`, `@parse/node-apn`): **MISSING**.
3. **Mobile Client (`apps/mobile/`):**
   - `flutter_local_notifications`: **MISSING** in `pubspec.yaml`.
   - `firebase_messaging`: **MISSING** in `pubspec.yaml`.
   - Background fetch/worker (`workmanager`, `android_alarm_manager`): **MISSING**.
   - Timezone library: `intl` is present; native `timezone` package is **MISSING**.

**Audit Verdict:**
- Reminder persistence: **DESIGN TARGET / ARCHITECTURAL SPECIFICATION** (Unbuilt).
- Server-side scheduling: **MISSING / FUTURE TARGET**.
- Push notification delivery (FCM/APNs): **FUTURE INFRASTRUCTURE**.
- Device local notification: **FUTURE CLIENT CAPABILITY**.
- In-App upcoming reminder list: **ACTIVE DESIGN TARGET**.

---

## 4. Canonical Ownership Model

The canonical ownership of a reminder belongs strictly to [`model User`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L27-L68):

$$\textbf{User} \quad \mathbf{\xrightarrow{\quad owns \quad}} \quad \textbf{Reminder}$$

```
+--------------------+
|     model User     |
+--------------------+
         | 1
         |
         | N (userId)
         v
+--------------------+             +------------------------+
|   model Reminder   | ----------> | model Trip (optional)  |
+--------------------+  (tripId)   +------------------------+
         |                                     | 1
         | (itineraryItemId)                   | N
         v                                     v
+------------------------+         +------------------------+
| model ItineraryItem    | <------ |    model Itinerary     |
|       (optional)       |         +------------------------+
+------------------------+
```

### Structural Rules:
1. **Personal Scheduling Object:** A reminder is an individual's personal time anchor. Only the creator (`userId`) can view, edit, or cancel it.
2. **Context Sources (Optional References):**
   - `tripId?`: Contextual link to a shared Trip (e.g. "Check-in Khách sạn Mường Thanh").
   - `itineraryId?`: Contextual link to a specific day itinerary (e.g. "Chuẩn bị cho Ngày 2").
   - `itineraryItemId?`: Contextual link to an activity (e.g. "Khởi hành đi Cáp treo Bà Nà Hills").
   - Standalone reminder: All three foreign keys are `NULL` (e.g. "Mua quà cho gia đình trước khi về").
3. **Companion Group is NEVER the Owner:** A Companion Group ([`model Group`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L558-L569)) does **NOT** own reminders. Group Chat is merely a social communication room and contextual entry point. Deleting a group never deletes personal trip reminders.

---

## 5. Reminder Visibility Contract

Two visibility modes are architected:

### Mode A: Private Reminder (Mặc Định — V1 Design Lock)
- **Visibility:** Creator only (`userId === req.user.id`).
- **Isolation:** Other trip participants, including the Trip Owner and co-travelers, cannot see or query private reminders.
- **Notification Impact:** Zero notification noise or side-effects for other travelers.

### Mode B: Shared Trip Reminder (Design Target / Future Stage)
- **Requirements:** Must require explicit opt-in confirmation from other participants.
- **Prohibition:** The system must **NEVER** silently broadcast push alerts or add mandatory alarm jobs to other travelers' devices without their individual consent.
- **Classification:** V1 restricts all reminder creation to **Mode A (Private)**. Mode B is documented as **FUTURE EXTENSION**.

---

## 6. Required Target Data Model (Target Schema Specification)

To ensure zero schema contradictions during downstream implementation, the target relational schema is specified as follows:

```prisma
// Target Schema Specification (TASK 08.2.3.14-R1)
enum ReminderStatus {
  SCHEDULED   // Đã lập lịch, chờ đến giờ
  COMPLETED   // Đã hoàn thành (chỉ khi người dùng đánh dấu xong hoặc sản phẩm xác nhận hoàn tất)
  CANCELLED   // Đã hủy bởi người dùng hoặc qua transactional cancellation khi xóa chuyến đi
}

model Reminder {
  id                String          @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  userId            String          @map("user_id") @db.Uuid
  tripId            String?         @map("trip_id") @db.Uuid
  itineraryId       String?         @map("itinerary_id") @db.Uuid
  itineraryItemId   String?         @map("itinerary_item_id") @db.Uuid

  title             String          @db.VarChar(200)
  notes             String?         @db.Text
  scheduledAtUtc    DateTime        @map("scheduled_at_utc") @db.Timestamptz
  timezone          String          @default("Asia/Ho_Chi_Minh") @db.VarChar(50)

  status            ReminderStatus  @default(SCHEDULED)

  createdAt         DateTime        @default(now()) @map("created_at") @db.Timestamptz
  updatedAt         DateTime        @updatedAt @map("updated_at") @db.Timestamptz
  cancelledAt       DateTime?       @map("cancelled_at") @db.Timestamptz
  completedAt       DateTime?       @map("completed_at") @db.Timestamptz

  // Relations
  user              User            @relation(fields: [userId], references: [id], onDelete: Cascade)
  trip              Trip?           @relation(fields: [tripId], references: [id], onDelete: SetNull)
  itinerary         Itinerary?      @relation(fields: [itineraryId], references: [id], onDelete: SetNull)
  itineraryItem     ItineraryItem?  @relation(fields: [itineraryItemId], references: [id], onDelete: SetNull)

  @@index([userId, status])
  @@index([tripId])
  @@index([scheduledAtUtc])
  @@map("reminders")
}
```

> [!NOTE]
> **Architectural Schema Refinements in R1:**
> 1. **One-Time Reminders Only:** `RepeatRule` enum and `repeatRule` column are excluded from V1. Recurring reminders require an occurrence-based data model (`ReminderOccurrence`) where each instance tracks independent completion/delivery state; this is architected under **Future Recurrence Architecture**.
> 2. **Decoupled Delivery Transport:** `DeliveryStatus` is removed from `model Reminder`. In V1, no background push delivery runtime exists; delivery state belongs to future dispatch infrastructure, not to the logical reminder intent record.
> 3. **Defensive Referential Integrity:** `trip onDelete: SetNull` prevents database-level cascade errors. Cascade cancellation of reminders upon trip deletion is executed as an **application-layer transactional cancellation** (`UPDATE reminders SET status = 'CANCELLED' ... WHERE trip_id = $id; DELETE FROM trips WHERE id = $id;`).
> 4. **Completed Timestamp:** `completedAt` records the exact UTC instant when the user explicitly marked the reminder as finished.
> 5. Production `apps/backend/prisma/schema.prisma` is completely untouched.

---

## 7. Timezone Contract (Hợp Đồng Múi Giờ)

Timezone management is critical for travel applications where users cross meridians:

1. **Storage Invariant (Absolute UTC Instant):**
   - The database **NEVER** stores raw ambiguous time strings (e.g. `"07:00"`).
   - Time is strictly persisted as an absolute UTC timestamp: `scheduledAtUtc` (`TIMESTAMPTZ` in PostgreSQL, ISO 8601 UTC string in JSON: `2026-10-16T00:00:00.000Z`).
2. **Origin Timezone Invariant:**
   - The original geographical timezone identifier is saved explicitly on each reminder: `timezone = "Asia/Ho_Chi_Minh"`.
3. **Trip Destination Precedence & Schema Dependency:**
   - A reminder bound to a Trip defaults to the destination timezone (`Asia/Ho_Chi_Minh`, GMT+7) regardless of where the traveler's phone happens to be when setting the reminder.
   - *Database Schema Audit Finding:* A thorough audit of [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model Trip` lines 390–425 and `model Destination` lines 110–135) reveals that **neither model contains a timezone column**. Automatic destination-to-timezone resolution is classified as a **DESIGN TARGET / LOCATION-TIMEZONE MAPPING DEPENDENCY**. In V1, the system stores `timezone` directly on `Reminder` and pre-fills `Asia/Ho_Chi_Minh` for Vietnam trips.
4. **Timezone Crossing Behavior:**
   - If a traveler flies from Tokyo (GMT+9) to Da Nang (GMT+7) and created a reminder for *"07:00 Đà Nẵng"*, the reminder must evaluate to `07:00 GMT+7` (which is `00:00 UTC`), NOT `07:00 GMT+9`.
5. **UI Transparency:**
   - The UI always renders the explicit timezone badge: `🕒 07:00 (GMT+7)` to eliminate ambiguity.

---

## 8. One-Time Reminder Scope & Future Recurrence Architecture

### V1 Scope: Strictly One-Time Reminders
- GoMate V1 locks scheduling strictly to **one-time reminders** (`repeatRule` is excluded from `model Reminder`).
- This covers $>95\%$ of travel itinerary workflows (hotel check-in, shuttle pickup, attraction entry window, dinner reservation).

### Future Recurrence Architecture (Deferred)
- Recurring reminders (`DAILY`, `WEEKLY`, RFC 5545 RRULE) cannot be modeled soundly with a single `model Reminder` status field, because each recurring instance possesses an independent lifecycle:
  - Occurrence $N$ may be completed, while Occurrence $N+1$ remains scheduled.
  - Occurrence $N$ may have failed delivery, while Occurrence $N-1$ succeeded.
- Sound recurrence requires a dedicated two-tier relational model:
  ```
  model Reminder (Parent Rule/Definition)
     └── 1 : N ──> model ReminderOccurrence (id, reminderId, scheduledAtUtc, status, deliveryStatus, completedAt)
  ```
- Because no recurrence worker or occurrence generator exists in the repository, recurrence is classified as **FUTURE RECURRENCE ARCHITECTURE** and excluded from V1 UI forms.

---

## 9. Status State Machine & Derived UI States

A fundamental principle in GoMate Scheduling V1 is the strict separation between persisted lifecycle status and derived temporal UI states:

$$\textbf{Persisted Status (DB)} \in \{\text{SCHEDULED}, \text{COMPLETED}, \text{CANCELLED}\}$$

$$\textbf{OVERDUE is a Derived UI State, NOT a Persisted Enum}$$

```
+-----------------------------------------------------------------------------------+
|                           LOGICAL STATUS STATE MACHINE                            |
+-----------------------------------------------------------------------------------+

                          +---------------+
                          |   SCHEDULED   | <----+ (Atomic Reschedule)
                          +---------------+      |
                            /           \        |
            (Explicit User /             (Explicit User /
             Product Action)              Trip Deletion)
                            v               v
                     +-----------+    +-----------+
                     | COMPLETED |    | CANCELLED |
                     +-----------+    +-----------+
```

### Invariant Rules:
1. **Completion Requires Explicit Action:**
   - A reminder transitions to `COMPLETED` **ONLY** when the user explicitly checks it off (e.g. tapping the checkbox in the list or detail view) or an explicit product workflow marks it complete.
   - Upon completion, `completedAt = nowUtc` is persisted.
   - **Time passing does NOT automatically set `COMPLETED`.** A reminder whose time has elapsed remains in its active logical state until handled.
2. **Derived Temporal State: Overdue (`Đã qua`):**
   - If `status === SCHEDULED` and `scheduledAtUtc < nowUtc`, the client renders the reminder with an overdue visual indicator.
   - It is categorized under the **`Đã qua`** filter tab.
   - Overdue is dynamically computed:
     $$\text{isOverdue} = (\text{status} == \text{SCHEDULED}) \land (\text{scheduledAtUtc} < \text{nowUtc})$$
3. **Filter Semantics:**
   - **Tất cả:** All active and overdue reminders for the trip (`status == SCHEDULED || status == COMPLETED`).
   - **Hôm nay:** Reminders where `scheduledAtUtc` falls within current local trip date.
   - **Sắp tới:** Reminders where `scheduledAtUtc > nowUtc` and not today.
   - **Đã qua:** Reminders where `status == SCHEDULED && scheduledAtUtc < nowUtc`.
4. **Cancellation:**
   - Setting `status = CANCELLED` writes `cancelledAt = nowUtc`. Cancelled reminders are hidden from standard active views.

---

## 10. Delivery Honesty & Channel Architecture

Because the repository currently contains zero FCM/APNs SDKs and zero local notification plugins, GoMate adheres to strict runtime transparency:

$$\textbf{In-App Reminder Center (DESIGN TARGET / MISSING RUNTIME)} \quad \ne \quad \textbf{Lock-Screen Push Alerts (FUTURE INFRASTRUCTURE)}$$

| Channel | Description | Current Repository Reality | Contract Classification |
| :--- | :--- | :---: | :--- |
| **In-App Reminder Center** | Displays upcoming reminders, status pills, and itinerary milestones when the app is opened | Missing (Unbuilt) | **DESIGN TARGET (V1)** |
| **Device Local Notifications** | Triggers local OS alarm sound/vibration via device OS when app is backgrounded | Missing | **FUTURE CLIENT CAPABILITY** |
| **Remote Push (FCM/APNs)** | Server-initiated wake-up push notification sent to device lock-screen via APNs / Firebase | Missing | **FUTURE INFRASTRUCTURE** |

> [!IMPORTANT]
> **No Fake Push Promises:** The client UI strictly avoids promising: *"Bạn sẽ nhận thông báo đẩy trên màn hình khóa"* as a current feature. The UI displays an honest user footnote:
> *"Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng."*

---

## 11. Create, Edit & Delete Lifecycle (One-Time & HITL)

### 1. Create Flow:
- **Entry points:** Trip Detail header, Itinerary day action, or Wandy AI proposal CTA.
- **Form fields:** Tiêu đề lời nhắc \*, Ghi chú chi tiết, Ngày nhắc \*, Giờ nhắc \*, Múi giờ áp dụng (prefilled `GMT+7 · Asia/Ho_Chi_Minh`), Liên kết ngữ cảnh (Tùy chọn: Chuyến đi / Hoạt động lịch trình).
- **Validation:** `title` non-empty (max 200 chars), `scheduledAtUtc` valid date, `userId` matches authenticated JWT.
- **Repeat rule:** Excluded from V1 form (one-time reminders only).
- **Primary CTA:** `[Lưu lời nhắc vào chuyến đi]`.

### 2. Edit Flow:
- User may modify any field (title, notes, time, date, linked activity).
- **Reschedule Transparency (User-Facing Copy):**
  Instead of developer jargon ("atomic reschedule"), the UI provides clear travel-oriented copy:
  *"Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng."*
- **Primary CTA:** `[Lưu thay đổi lời nhắc]`.

### 3. Delete / Cancel Flow:
- Action triggers confirmation modal:
  - Title: *"Xóa lời nhắc này?"*
  - Supporting copy: *"Lời nhắc sẽ bị xóa khỏi chuyến đi."*
  - Primary: `[Xóa]` (Danger red) | Secondary: `[Hủy]`.
- System marks `status = CANCELLED`, `cancelledAt = nowUtc()`.

---

## 12. Trip & Itinerary Lifecycle Impact (Application-Layer Cancellation)

1. **Trip Deletion Policy (Application-Layer Transactional Cancellation):**
   - The target schema uses `trip onDelete: SetNull` as defensive referential behavior.
   - When a user deletes a Trip, cancellation of associated reminders is executed at the **application layer within a single database transaction**:
     ```sql
     BEGIN TRANSACTION;
       UPDATE reminders
       SET status = 'CANCELLED', cancelled_at = NOW()
       WHERE trip_id = $tripId AND status = 'SCHEDULED';
       
       DELETE FROM trips WHERE id = $tripId;
     COMMIT;
     ```
   - *Terminology Guardrail:* This is an **application-layer transactional cancellation**, NOT a database "cascade cancellation".
2. **Itinerary Day / Activity Deletion Policy:**
   - If an `ItineraryItem` is deleted from the shared timeline, any linked reminder is **DETACHED, NOT DELETED**:
     - `reminder.itineraryItemId = null`
     - `reminder.tripId` is preserved
     - The reminder card displays a neutral, informative badge: `(Hoạt động liên kết không còn trong lịch trình.)`
   - Rationale: The traveler's personal scheduled reminder and notes must not be silently discarded just because a collaborator modified the shared itinerary.

---

## 13. Deduplication & Idempotency Key (Future Architecture)

To protect against duplicate notifications resulting from network retries, worker restarts, or app reinstalls, future delivery systems must enforce an explicit idempotency key:

$$\textbf{idempotencyKey} = \text{reminderId} + \text{"\_"} + \text{scheduledOccurrenceUtc}$$

*Example:* `c4613a80-1234-5678_2026-10-16T00:00:00Z`

The delivery worker checks Redis/DB for the presence of this key before attempting any push dispatch.

---

## 14. Offline Behavior & Friendly Error Handling

1. **Offline Viewing:** Previously loaded reminders stored in client cache remain readable in offline mode.
2. **Offline Mutations & Honest Error State:**
   - No background sync queue exists in V1.
   - If network connection fails during reminder loading or mutations, the UI displays a clean, user-friendly error view ([`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png)):
     - Title: *"Không thể tải danh sách lời nhắc"*
     - Copy: *"Không thể kết nối tới GoMate lúc này. Vui lòng kiểm tra mạng và thử lại."*
     - Actions: `[Thử lại kết nối]` (Primary teal) and `[Quay lại Chuyến đi]` (Secondary outline).
     - Technical error codes (e.g. "503", stacktraces, backend terms) are **STRICTLY PROHIBITED** from customer UI.

---

## 15. Permission Boundary & OS Notification Deferral

$$\textbf{In-App Reminder Management} \quad \ne \quad \textbf{Device OS Notification Permissions}$$

1. **Independent In-App Management:** A user can always create, view, edit, and organize trip reminders in GoMate inside the application regardless of device notification permissions.
2. **OS Notification Screen Deferred:**
   - Because GoMate V1 has zero notification runtime (no local notification plugin, no FCM/APNs SDK), no OS notification permission request or channel configuration screen exists in V1 runtime.
   - The conceptual mockup [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) is formally designated as **SUPERSEDED / FUTURE CONCEPT** and retained strictly in audit history.

---

## 16. Wandy AI Scheduling Boundary (Human-in-the-Loop)

Wandy AI Copilot serves as an intelligent advisor:
- **Allowed Informative Actions:**
  - Suggest reminders based on itinerary activities (e.g. *"Bạn có lịch trình đi Bà Nà Hills sáng mai lúc 08:00. Bạn có muốn đặt nhắc nhở chuẩn bị lúc 07:00 không?"*).
  - Propose optimal lead times.
- **Strictly Prohibited Autonomous Mutations:**
  - Wandy **MUST NOT** autonomously create, edit, or delete reminders in the database.
  - Tapping `+ Dùng gợi ý này` opens the **Create Reminder** form pre-filled with Wandy's suggested parameters (Title, Date, Time, Context). The traveler reviews the values and taps `[Lưu lời nhắc vào chuyến đi]` to commit. Zero invisible writes occur.
  - Every Wandy proposal requires a **Human-in-the-Loop Confirmation Modal** before any database write occurs.

---

## 17. Master Visual Mockup Evidence (R1 Revision)

The active Master V1 visual set consists of 7 mockups (6 updated R1 mockups + 1 preserved empty state), rendered at native viewport resolutions using Microsoft Edge headless rendering and verified in `docs/audit/evidence/ui-08.2.3.14/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `Nhắc lịch chuyến đi` with subtitle `Khám phá Đà Nẵng 4N3Đ`.<br>2. Filter bar: `Tất cả (3)` [Active], `Hôm nay (1)`, `Sắp tới (2)`, `Đã qua (0)` [Derived overdue state].<br>3. Wandy suggestion box with `[+ Dùng gợi ý này ›]` (HITL entry).<br>4. Section "Hôm nay": Hotel check-in card with time `14:00 (GMT+7)`.<br>5. Section "Ngày mai": Bà Nà Hills departure `07:00 (GMT+7)` and lunch reservation `11:30 (GMT+7)`.<br>6. Honesty footnote: `* Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng.`<br>7. Canonical 5-tab root navigation (`Chuyến đi` active). | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy` (left), title `Tạo lời nhắc mới`, and `Lưu` (right).<br>2. Title input `Khởi hành đi Bà Nà Hills` + Notes textarea.<br>3. Date picker `16/10/2026` + Time picker `07:00`.<br>4. Timezone box: `GMT+7 · Asia/Ho_Chi_Minh` (Việt Nam).<br>5. Context link: `Ngày 2 · Hoạt động #1: Đi cáp treo Bà Nà Hills`.<br>6. Repeat rule selector: **REMOVED** (One-time reminder only).<br>7. Privacy note: Private reminder.<br>8. Primary CTA `Lưu lời nhắc vào chuyến đi`. Contained cleanly in $844\text{px}$. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. App bar with back button, `Chi tiết lời nhắc`, and action overflow.<br>2. Hero card: Clock icon, title, big time `07:00`, date `Thứ Sáu, 16/10/2026`, timezone `GMT+7`, and badge `ĐÃ LẬP LỊCH (Chờ đến giờ)`.<br>3. Context card: Trip name, linked activity, and quick link `[Xem hoạt động trong Lịch trình chung ›]`.<br>4. Notes card: Detailed shuttle bus pickup notes.<br>5. Metadata card: Privacy (`Cá nhân (Chỉ bạn thấy)`), Hiển thị (`Trong ứng dụng GoMate`). Zero fake push delivery status.<br>6. Actions: `Chỉnh sửa lời nhắc` (outline teal) and `Xóa lời nhắc` (outline red). | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy`, title `Chỉnh sửa lời nhắc`, and `Cập nhật`.<br>2. Editable fields populated with current data.<br>3. Updated time `07:15` highlighted in teal.<br>4. Informative reschedule banner: `Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng.` (Replaced developer jargon).<br>5. Repeat rule selector: **REMOVED**.<br>6. Primary CTA `[Lưu thay đổi lời nhắc]`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Nhắc lịch chuyến đi` + Trip subtitle.<br>2. Centered illustration: Alarm clock in soft teal circle.<br>3. Title: `Chưa có lời nhắc nào`.<br>4. Informative travel copy.<br>5. Primary CTA: `+ Thêm lời nhắc đầu tiên`.<br>6. Travel tip card explaining integration with shared itinerary and Wandy AI.<br>7. Canonical 5-tab root navigation. | **PASS (PRESERVED)** |
| [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) | Mobile | $390 \times 844$ | 1. App bar with trip context.<br>2. Warning icon in soft red circle.<br>3. Clean customer error title: `Không thể tải danh sách lời nhắc`.<br>4. Clean travel copy: `Không thể kết nối tới GoMate lúc này. Vui lòng kiểm tra mạng và thử lại.`<br>5. Actions: `[Thử lại kết nối]` (Primary teal) and `[Quay lại Chuyến đi]` (Secondary outline).<br>6. Zero technical error codes (no 503), zero backend terminology.<br>7. Canonical 5-tab root navigation. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) | Mobile | $390 \times 844$ | *Archival only.* Depicts speculative OS channel settings. Excluded from V1 active master visual set because V1 contains zero notification runtime. | **SUPERSEDED / FUTURE CONCEPT** |
| [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Top navbar: Logo `GoMate` + badge `Trip Workspace` + Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`) + User pill.<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhắc lịch` + Owner badge.<br>3. Col 1 ($310\text{px}$): Trip summary, sidebar filter navigation with count badges (`Tất cả lời nhắc 3`, `Hôm nay (15/10) 1`, `Sắp tới 2`, `Đã hoàn thành 0`), quick links.<br>4. Col 2 ($800\text{px}$ flex): Search toolbar + `+ Tạo lời nhắc mới`, 3 comprehensive reminder cards with checkboxes, times, tags, and notes; honesty footnote at bottom.<br>5. Col 3 ($330\text{px}$): Wandy AI Copilot suggestion card with `+ Dùng gợi ý này` CTA, Timezone specification card, Privacy card. Removed all fake delivery status dashboard indicators and developer debug labels. Zero scrollbars. | **PASS (R1 LOCKED)** |

---

## 18. Current vs. Future Capability Matrix (24 Dimensions — R1 Aligned)

| Dimension | Current Runtime Status | Architectural Contract V1 (R1) | Future Target |
| :--- | :---: | :---: | :--- |
| **1. Reminder DB Model** | **MISSING** | **SCHEMA SPECIFICATION** | PostgreSQL `model Reminder` migration (one-time, no repeatRule) |
| **2. Reminder API Endpoints** | **MISSING** | **DESIGN TARGET** | NestJS `RemindersController` CRUD |
| **3. Reminder Mobile UI** | **MISSING** | **DESIGN LOCKED (R1)** | Flutter riverpod feature module |
| **4. Trip Association** | **MISSING** | **DESIGN LOCKED** | Optional FK `tripId` referencing `Trip.id` |
| **5. Itinerary Association** | **MISSING** | **DESIGN LOCKED** | Optional FK `itineraryItemId` referencing activity |
| **6. Timezone Representation**| **MISSING** | **DESIGN LOCKED** | Absolute UTC `scheduledAtUtc` + stored `timezone` string |
| **7. Repeat Rule** | **EXCLUDED**| **ONE-TIME REMINDER ONLY** | Occurrence-based model (`ReminderOccurrence`) in Future Architecture |
| **8. Server Scheduler Engine** | **MISSING** | **FUTURE INFRASTRUCTURE**| `@nestjs/schedule` or BullMQ worker |
| **9. Delayed Job Worker** | **MISSING** | **FUTURE INFRASTRUCTURE**| Background queue evaluation worker |
| **10. Redis Queue Integration**| **MISSING** | **FUTURE INFRASTRUCTURE**| BullMQ delayed queue over Redis |
| **11. Local Device Notification**| **MISSING**| **FUTURE CLIENT CAPABILITY** | `flutter_local_notifications` plugin |
| **12. Remote Push (FCM)** | **MISSING** | **FUTURE INFRASTRUCTURE**| Firebase Cloud Messaging gateway |
| **13. Remote Push (APNs)** | **MISSING** | **FUTURE INFRASTRUCTURE**| Apple Push Notification service |
| **14. Push Token Storage** | **MISSING** | **SCHEMA GAP** | `UserDevice` table storing FCM/APNs tokens |
| **15. Notification Permissions**| **MISSING**| **DEFERRED TO FUTURE** | OS runtime permission flow (when push/alarm runtime is implemented) |
| **16. Delivery Retry Policy** | **MISSING** | **FUTURE SPECIFICATION** | Exponential backoff for transient failures |
| **17. Delivery Deduplication** | **MISSING** | **FUTURE SPECIFICATION** | Idempotency key: `reminderId_occurrence` |
| **18. Cancellation Mechanics** | **MISSING** | **DESIGN LOCKED** | `CANCELLED` status + `cancelledAt = nowUtc()` |
| **19. Offline Behavior** | **MISSING** | **DESIGN LOCKED (R1)** | Cached read; friendly error on offline write (zero tech codes) |
| **20. Wandy Reminder Suggestion**| **MISSING**| **DESIGN LOCKED (R1)** | Informative suggestions with `+ Dùng gợi ý này` CTA |
| **21. Wandy Autonomous Mutation**| **EXCLUDED**| **STRICTLY PROHIBITED** | Pre-fills form; user explicitly reviews and saves (HITL) |
| **22. Shared Trip Reminder** | **EXCLUDED** | **DESIGN TARGET / FUTURE** | Requires explicit member opt-in consent |
| **23. Trip Deletion Lifecycle** | **MISSING** | **DESIGN LOCKED** | Application-layer transactional cancellation (`UPDATE SET CANCELLED`) |
| **24. Itinerary Deletion Lifecycle**| **MISSING**| **DESIGN LOCKED** | Detachment (`itineraryItemId = null`) + neutral tag |
