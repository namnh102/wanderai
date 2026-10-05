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
  - Mobile Reminder List V1: [`scheduling-mobile-list-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-v1.png) ($390 \times 844$)
  - Mobile Create Reminder V1: [`scheduling-mobile-create-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-v1.png) ($390 \times 844$)
  - Mobile Reminder Detail V1: [`scheduling-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-v1.png) ($390 \times 844$)
  - Mobile Edit Reminder V1: [`scheduling-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Empty State V1: [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) ($390 \times 844$)
  - Mobile Error State V1: [`scheduling-mobile-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-v1.png) ($390 \times 844$)
  - Mobile Channels & Permissions V1: [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) ($390 \times 844$)
  - Desktop Master Workstation V1: [`scheduling-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-v1.png) ($1440 \times 900$)

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
// Target Schema Specification (TASK 08.2.3.14)
enum ReminderStatus {
  SCHEDULED   // Đã lập lịch, chờ đến giờ
  COMPLETED   // Đã hoàn thành (đã đánh dấu xong hoặc thời điểm đã trôi qua)
  CANCELLED   // Đã hủy bởi người dùng hoặc do xóa chuyến đi
}

enum RepeatRule {
  NONE        // Không lặp lại (Mặc định V1)
  DAILY       // Hàng ngày
  WEEKLY      // Hàng tuần
}

enum DeliveryStatus {
  PENDING     // Đang chờ đến mốc thời gian đánh giá
  DELIVERED   // Đã chuyển giao thành công (in-app hoặc push)
  FAILED      // Gửi thất bại / thiết bị mất kết nối / không có token
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

  repeatRule        RepeatRule      @default(NONE) @map("repeat_rule")
  status            ReminderStatus  @default(SCHEDULED)
  deliveryStatus    DeliveryStatus  @default(PENDING) @map("delivery_status")

  createdAt         DateTime        @default(now()) @map("created_at") @db.Timestamptz
  updatedAt         DateTime        @updatedAt @map("updated_at") @db.Timestamptz
  cancelledAt       DateTime?       @map("cancelled_at") @db.Timestamptz

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
> This schema is an architectural target specification for contract locking. Production `apps/backend/prisma/schema.prisma` is completely untouched.

---

## 7. Timezone Contract (Hợp Đồng Múi Giờ)

Timezone management is critical for travel applications where users cross meridians:

1. **Storage Invariant (Absolute UTC Instant):**
   - The database **NEVER** stores raw ambiguous time strings (e.g. `"07:00"`).
   - Time is strictly persisted as an absolute UTC timestamp: `scheduledAtUtc` (`TIMESTAMPTZ` in PostgreSQL, ISO 8601 UTC string in JSON: `2026-10-16T00:00:00.000Z`).
2. **Origin Timezone Invariant:**
   - The original geographical timezone identifier is saved explicitly: `timezone = "Asia/Ho_Chi_Minh"`.
3. **Trip Destination Precedence (V1 Rule):**
   - A reminder bound to a Trip defaults to the destination timezone (`Asia/Ho_Chi_Minh`, GMT+7) regardless of where the traveler's phone happens to be when setting the reminder.
4. **Timezone Crossing Behavior:**
   - If a traveler flies from Tokyo (GMT+9) to Da Nang (GMT+7) and created a reminder for *"07:00 Đà Nẵng"*, the reminder must evaluate to `07:00 GMT+7` (which is `00:00 UTC`), NOT `07:00 GMT+9`.
5. **UI Transparency:**
   - The UI always renders the explicit timezone badge: `🕒 07:00 (GMT+7)` to eliminate ambiguity.

---

## 8. Repeat Rule Contract

1. **V1 Supported Enums:**
   - `NONE`: One-time reminder (95% of travel use cases).
   - `DAILY`: Recurs every 24 hours at the same localized clock hour.
   - `WEEKLY`: Recurs every 7 days at the same localized day and clock hour.
2. **Exclusions from V1:**
   - Complex recurrence expressions (RFC 5545 RRULE, e.g. "every 2nd Tuesday of the month") are **EXCLUDED BY DESIGN**.
3. **Classification:**
   - Without an active backend cron/queue worker, recurring reminders are classified as **DESIGN TARGET / FUTURE INFRASTRUCTURE**.

---

## 9. Status State Machine (Logical vs. Delivery)

A core source of truth in GoMate is the clean decoupling of logical reminder intent from notification transport results:

```
[ LOGICAL STATUS STATE MACHINE ]
                  +---------------+
                  |   SCHEDULED   | <----+ (Atomic Reschedule)
                  +---------------+      |
                    /           \        |
    (User Marks Done /           (User Cancels /
     Event Concluded)             Trip Deleted)
                  v               v
           +-----------+    +-----------+
           | COMPLETED |    | CANCELLED |
           +-----------+    +-----------+

[ NOTIFICATION DELIVERY STATE MACHINE (SEPARATE) ]
                  +---------------+
                  |    PENDING    |
                  +---------------+
                    /           \
       (Transport Dispatched /   (Device Unreachable /
        Shown In-App)             Permission Blocked)
                  v               v
           +-----------+    +-----------+
           | DELIVERED |    |  FAILED   |
           +-----------+    +-----------+
```

### Invariant Rules:
1. A reminder can be in state `SCHEDULED` while its delivery state is `PENDING`.
2. If delivery fails (e.g. user phone is offline or in flight mode), `deliveryStatus = FAILED`, but `reminder.status` remains `SCHEDULED` so the user can still see it when opening the app.
3. Cancelling a reminder moves `status -> CANCELLED`, sets `cancelledAt = now()`, and automatically invalidates any pending delivery jobs.

---

## 10. Delivery Honesty & Channel Architecture

Because the repository currently contains zero FCM/APNs SDKs, GoMate adheres to strict runtime transparency:

$$\textbf{Honest Channel: In-App Reminder Center} \quad \ne \quad \textbf{Future Channel: Lock-Screen Push Alerts}$$

| Channel | Description | Current Runtime Status | Contract Classification |
| :--- | :--- | :---: | :--- |
| **In-App Reminder Center** | Displays upcoming reminders, highlighted cards, and day itineraries when the app is opened | Missing (Unbuilt) | **DESIGN TARGET (V1)** |
| **Device Local Notifications** | Triggers local OS alarm sound/vibration via device OS when app is in background | Missing | **FUTURE CLIENT CAPABILITY** |
| **Remote Push (FCM/APNs)** | Server-initiated wake-up push notification sent to device lock-screen via APNs / Firebase | Missing | **FUTURE INFRASTRUCTURE** |

> [!IMPORTANT]
> **No Fake Push Promises:** The client UI strictly avoids promising: *"Bạn sẽ nhận thông báo đẩy trên màn hình khóa"* as a current feature. The UI honestly labels: *"Lời nhắc được lưu và hiển thị trong ứng dụng. Tính năng thông báo đẩy qua thiết bị đang được nâng cấp."*

---

## 11. Create, Edit & Delete Lifecycle (Atomic Rescheduling)

### 1. Create Flow:
- Entry points: Trip Detail header, Itinerary day action, or Wandy AI proposal.
- Form fields: Title \*, Notes, Date \*, Time \*, Timezone, Context Association (optional), Repeat Rule.
- Validation: `title` non-empty (max 200 chars), `scheduledAtUtc` valid date, `userId` matches authenticated JWT.
- Primary CTA: `[Lưu lời nhắc vào chuyến đi]`.

### 2. Edit Flow:
- User may modify any field (title, notes, time, date, linked activity).
- **Atomic Reschedule Rule:** Changing the scheduled time atomically updates `scheduledAtUtc` and invalidates any previous scheduled dispatch job. Orphan jobs and duplicate reminders are prohibited.

### 3. Delete / Cancel Flow:
- Action triggers confirmation modal:
  - Title: *"Xóa lời nhắc này?"*
  - Supporting copy: *"Lời nhắc sẽ bị xóa khỏi chuyến đi và hủy mọi lịch trình thông báo liên quan."*
  - Primary: `[Xóa]` (Danger red) | Secondary: `[Hủy]`.
- System marks `status = CANCELLED`, `cancelledAt = now()`.

---

## 12. Trip & Itinerary Lifecycle Impact

1. **Trip Deletion Policy:**
   - If a `Trip` is deleted, all reminders linked to that trip (`reminder.tripId === trip.id`) are **AUTOMATICALLY CANCELLED** (`status = CANCELLED`, `cancelledAt = now()`).
   - Rationale: Contextual reminders (e.g. check-in, shuttle bus) lose their validity when the entire trip is deleted.
2. **Itinerary Day / Activity Deletion Policy:**
   - If an `ItineraryItem` is deleted from the timeline, any linked reminder is **DETACHED, NOT DELETED**:
     - `reminder.itineraryItemId = null`
     - `reminder.tripId` is preserved
     - The reminder card displays an informative badge: `(Hoạt động lịch trình liên kết đã được xóa)`
   - Rationale: The traveler's personal scheduled reminder and notes must not be silently discarded just because a collaborator modified the shared itinerary.

---

## 13. Deduplication & Idempotency Key

To protect against duplicate notifications resulting from network retries, worker restarts, or app reinstalls, future delivery systems must enforce an explicit idempotency key:

$$\textbf{idempotencyKey} = \text{reminderId} + \text{"\_"} + \text{scheduledOccurrenceUtc}$$

*Example:* `c4613a80-1234-5678_2026-10-16T00:00:00Z`

The delivery worker checks Redis/DB for the presence of this key before attempting any push dispatch.

---

## 14. Offline Behavior & Graceful Degradation

1. **Offline Viewing:** Previously loaded reminders stored in client cache (e.g. SQLite / SharedPreferences) remain readable in offline mode.
2. **Offline Mutations:** No background sync queue exists in V1. If network connection is lost during create, edit, or delete actions, the UI displays a clean, friendly error state ([`scheduling-mobile-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-v1.png)) and does not claim fake offline persistence.

---

## 15. Permission Boundary (Storage vs. OS Notification)

$$\textbf{Reminder Persistence Permission} \quad \ne \quad \textbf{Device OS Notification Permission}$$

1. **Independent Storage:** A user can always create, view, edit, and organize trip reminders in GoMate even if they have denied the operating system's notification permissions (`POST_NOTIFICATIONS` on Android 13+ or iOS APNs permission).
2. **Permission Disclosure:** As illustrated in [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png), the UI clearly distinguishes between in-app reminder storage and device push permissions.

---

## 16. Wandy AI Scheduling Boundary

Wandy AI Copilot serves as an intelligent advisor:
- **Allowed Informative Actions:**
  - Suggest reminders based on itinerary activities (e.g. "Bạn có lịch trình đi Bà Nà Hills lúc 08:00 sáng mai. Bạn có muốn đặt nhắc nhở chuẩn bị lúc 07:00 không?").
  - Propose optimal lead times (e.g. recommending 1 hour before cable car departure).
- **Strictly Prohibited Autonomous Mutations:**
  - Wandy **MUST NOT** autonomously create, edit, or delete reminders in the database.
  - Every Wandy proposal requires a **Human-in-the-Loop Confirmation Modal** before any database write occurs.

---

## 17. Master Visual Mockup Evidence

All 8 master mockups were rendered at native viewport resolutions using Microsoft Edge headless rendering and verified in `docs/audit/evidence/ui-08.2.3.14/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`scheduling-mobile-list-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-v1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `Nhắc lịch chuyến đi` with subtitle `Khám phá Đà Nẵng 4N3Đ`.<br>2. Filter bar: `Tất cả (3)` [Active], `Hôm nay (1)`, `Sắp tới (2)`, `Đã qua (0)`.<br>3. Wandy suggestion box with `[+ Đặt lời nhắc này ›]`.<br>4. Section "Hôm nay": Hotel check-in card with time `14:00 (GMT+7)`.<br>5. Section "Ngày mai": Bà Nà Hills departure `07:00 (GMT+7)` and lunch reservation `11:30 (GMT+7)`.<br>6. Honesty footnote: In-app management active; push in progress.<br>7. Canonical 5-tab root navigation (`Chuyến đi` active). | **PASS** |
| [`scheduling-mobile-create-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-v1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy` (left), title `Tạo lời nhắc mới`, and `Lưu` (right).<br>2. Title input `Khởi hành đi Bà Nà Hills` + Notes textarea.<br>3. Date picker `16/10/2026` + Time picker `07:00`.<br>4. Timezone box: `GMT+7 · Asia/Ho_Chi_Minh` (Việt Nam).<br>5. Context link: `Ngày 2 · Hoạt động #1: Đi cáp treo Bà Nà Hills`.<br>6. Repeat chips: `Không lặp lại` [Active], `Hàng ngày`, `Hàng tuần`.<br>7. Privacy note: Private reminder.<br>8. Primary CTA `Lưu lời nhắc vào chuyến đi`. Contained cleanly in $844\text{px}$. | **PASS** |
| [`scheduling-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-v1.png) | Mobile | $390 \times 844$ | 1. App bar with back button, `Chi tiết lời nhắc`, and action overflow.<br>2. Hero card: Clock icon, title, big time `07:00`, date `Thứ Sáu, 16/10/2026`, timezone `GMT+7`, and badge `ĐÃ LẬP LỊCH`.<br>3. Context card: Trip name, linked activity, and quick link `[Xem hoạt động trong Lịch trình chung ›]`.<br>4. Notes card: Detailed shuttle bus pickup notes.<br>5. Metadata card: Repeat rule (None), Privacy (Private), Channel (In-app GoMate).<br>6. Actions: `Chỉnh sửa lời nhắc` (outline teal) and `Xóa lời nhắc` (outline red). | **PASS** |
| [`scheduling-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-v1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy`, title `Chỉnh sửa lời nhắc`, and `Cập nhật`.<br>2. Editable fields populated with current data.<br>3. Updated time `07:15` highlighted in teal.<br>4. Atomic reschedule banner: Explaining atomic replacement of old schedule to prevent duplicate alerts.<br>5. Primary CTA `[Lưu thay đổi lời nhắc]`. | **PASS** |
| [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Nhắc lịch chuyến đi` + Trip subtitle.<br>2. Centered illustration: Alarm clock in soft teal circle.<br>3. Title: `Chưa có lời nhắc nào`.<br>4. Informative travel copy.<br>5. Primary CTA: `+ Thêm lời nhắc đầu tiên`.<br>6. Travel tip card explaining integration with shared itinerary and Wandy AI.<br>7. Canonical 5-tab root navigation. | **PASS** |
| [`scheduling-mobile-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-v1.png) | Mobile | $390 \times 844$ | 1. App bar with trip context.<br>2. Warning icon in soft red circle.<br>3. Friendly error title: `Không thể tải danh sách lời nhắc`.<br>4. Honest explanation: Network connection failure; offline cache currently unavailable.<br>5. Actions: `[Thử lại kết nối]` (Primary teal) and `[Quay lại Chuyến đi]` (Secondary outline).<br>6. Human-friendly response code note (503), zero raw stacktraces.<br>7. Canonical 5-tab root navigation. | **PASS** |
| [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Kênh & Quyền thông báo` + Subtitle.<br>2. Header card: Bell icon and transparent architecture title.<br>3. Channel cards: In-app (`ĐANG HOẠT ĐỘNG`), Lock-screen push (`ĐANG NÂNG CẤP`).<br>4. Independence explanation: Independent storage vs. OS push permissions.<br>5. Default alert offset selector (15 min, 30 min, 1 hour).<br>6. Canonical 5-tab root navigation. | **PASS** |
| [`scheduling-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-v1.png) | Desktop | $1440 \times 900$ | 1. Top navbar: Logo `GoMate` + badge `Trip Workspace` + Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`) + User pill.<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhắc lịch` + Owner badge.<br>3. Col 1 ($310\text{px}$): Trip summary, sidebar filter navigation with count badges, quick links.<br>4. Col 2 ($800\text{px}$ flex): Search toolbar + `+ Tạo lời nhắc mới`, 3 comprehensive reminder cards with checkboxes, times, tags, and notes; honesty footnote at bottom.<br>5. Col 3 ($330\text{px}$): Wandy AI Copilot suggestion card with confirmation CTA, notification delivery channel status card, timezone specification card. Zero scrollbars. | **PASS** |

---

## 18. Current vs. Future Capability Matrix (24 Dimensions)

| Dimension | Current Runtime Status | Architectural Contract V1 | Future Target |
| :--- | :---: | :---: | :--- |
| **1. Reminder DB Model** | **MISSING** | **SCHEMA SPECIFICATION** | PostgreSQL `model Reminder` migration |
| **2. Reminder API Endpoints** | **MISSING** | **DESIGN TARGET** | NestJS `RemindersController` CRUD |
| **3. Reminder Mobile UI** | **MISSING** | **DESIGN LOCKED** | Flutter riverpod feature module |
| **4. Trip Association** | **MISSING** | **DESIGN LOCKED** | Optional FK `tripId` referencing `Trip.id` |
| **5. Itinerary Association** | **MISSING** | **DESIGN LOCKED** | Optional FK `itineraryItemId` referencing activity |
| **6. Timezone Representation**| **MISSING** | **DESIGN LOCKED** | Absolute UTC `scheduledAtUtc` + `timezone` string |
| **7. Repeat Rule** | **MISSING** | **DESIGN TARGET** | Enum: `NONE`, `DAILY`, `WEEKLY` |
| **8. Server Scheduler Engine** | **MISSING** | **FUTURE INFRASTRUCTURE**| `@nestjs/schedule` or BullMQ worker |
| **9. Delayed Job Worker** | **MISSING** | **FUTURE INFRASTRUCTURE**| Background queue evaluation worker |
| **10. Redis Queue Integration**| **MISSING** | **FUTURE INFRASTRUCTURE**| BullMQ delayed queue over Redis |
| **11. Local Device Notification**| **MISSING**| **FUTURE CLIENT CAPABILITY** | `flutter_local_notifications` plugin |
| **12. Remote Push (FCM)** | **MISSING** | **FUTURE INFRASTRUCTURE**| Firebase Cloud Messaging gateway |
| **13. Remote Push (APNs)** | **MISSING** | **FUTURE INFRASTRUCTURE**| Apple Push Notification service |
| **14. Push Token Storage** | **MISSING** | **SCHEMA GAP** | `UserDevice` table storing FCM/APNs tokens |
| **15. Notification Permissions**| **MISSING**| **FUTURE CLIENT CAPABILITY** | OS runtime permission request flow |
| **16. Delivery Retry Policy** | **MISSING** | **DESIGN SPECIFICATION** | Exponential backoff for transient failures |
| **17. Delivery Deduplication** | **MISSING** | **DESIGN SPECIFICATION** | Idempotency key: `reminderId_occurrence` |
| **18. Cancellation Mechanics** | **MISSING** | **DESIGN LOCKED** | `CANCELLED` status + atomic job invalidation |
| **19. Offline Behavior** | **MISSING** | **DESIGN LOCKED** | Cached read; friendly error on offline write |
| **20. Wandy Reminder Suggestion**| **MISSING**| **DESIGN LOCKED** | Informative prompt suggestions |
| **21. Wandy Autonomous Mutation**| **EXCLUDED**| **STRICTLY PROHIBITED** | Human-in-the-loop confirmation modal |
| **22. Shared Trip Reminder** | **EXCLUDED** | **DESIGN TARGET / FUTURE** | Requires explicit member opt-in consent |
| **23. Trip Deletion Lifecycle** | **MISSING** | **DESIGN LOCKED** | Auto-cancellation of bound reminders |
| **24. Itinerary Deletion Lifecycle**| **MISSING**| **DESIGN LOCKED** | Detachment (`itineraryItemId = null`) + tag |
