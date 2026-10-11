# GoMate Scheduling & Reminders — Capability & Architectural Audit (TASK 08.2.3.14)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.14 — GOMATE SCHEDULING & REMINDERS: CAPABILITY AUDIT, BUSINESS CONTRACT & VISUAL MOCKUP V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model Notification`, `model User`)
- Backend Code: [`apps/backend/src/`](file:///d:/Do_an/wanderai/apps/backend/src/)
- Mobile Code: [`apps/mobile/lib/`](file:///d:/Do_an/wanderai/apps/mobile/lib/)
- Core Contract: [`docs/design/gomate-scheduling-reminder-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-scheduling-reminder-contract-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Master List R1: [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) ($390 \times 844$)
  - Mobile Master Create R1: [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) ($390 \times 844$)
  - Mobile Master Detail R1: [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) ($390 \times 844$)
  - Mobile Master Edit R1: [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) ($390 \times 844$)
  - Mobile Master Empty V1: [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) ($390 \times 844$) [Preserved from V1]
  - Mobile Master Error R1: [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) ($390 \times 844$)
  - Mobile Channels & Permissions (SUPERSEDED / FUTURE CONCEPT): [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) ($390 \times 844$) [Kept for audit history; removed from Master V1 visual scope]
  - Desktop Master Workstation R1: [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict (R1 Revision)

TASK 08.2.3.14 (and R1 correction) executes a comprehensive repository capability and architectural audit for the Scheduling & Reminders experience in GoMate.

### Key Audit Findings & R1 Corrections:
1. **Repository Capability Reality (Total Infrastructure Gap):**
   - Neither `model Reminder`, `RemindersController`, nor any reminder service exists in the repository.
   - `model Notification` exists in `schema.prisma` (line 371) but represents an in-app notification inbox; it lacks reminder enums, has **zero backend controllers or services**, and has zero mobile UI bindings.
   - Zero scheduling decorators (`@nestjs/schedule`, `@Cron()`), zero queue managers (`bull`, `bullmq`), and zero push gateways (`firebase-admin`, `APNs`) exist in backend dependencies.
   - In the mobile client, `flutter_local_notifications` and `firebase_messaging` are **100% absent**.
   - **Verdict:** Scheduling and Reminders is an unbuilt, greenfield module. All specifications locked here represent the **Design Target and Business Contract V1**.
   - **In-App Reminder Center is a DESIGN TARGET / MISSING RUNTIME, not CURRENT.**
2. **First Principle Enforced:**
   $$\textbf{Reminder Persistence} \quad \ne \quad \textbf{Scheduler Engine} \quad \ne \quad \textbf{Notification Delivery}$$
   Database storage of a reminder date does not imply delivery. The UI and documentation strictly reject claiming background push notification delivery as a current capability.
3. **Canonical Ownership Locked (User-Owned):**
   - The user (`model User`) is the sole canonical owner of a reminder.
   - Contextual links to `Trip`, `Itinerary`, and `ItineraryItem` are strictly optional foreign keys.
   - The Companion Group is **NEVER** the owner; deleting a group has zero effect on personal trip reminders.
4. **V1 Scope Locked to One-Time Reminders Only:**
   - `RepeatRule` enum and `repeatRule` column are excluded from `model Reminder` V1. Recurring reminders require an occurrence-based data model (`ReminderOccurrence`) to track individual occurrence delivery and completion states, which is architected as **Future Recurrence Architecture**.
5. **Decoupled Delivery Transport:**
   - `DeliveryStatus` is removed from `model Reminder`. In V1, no background push delivery runtime exists; delivery state belongs to future dispatch infrastructure, not to the logical reminder intent record.
6. **Explicit Completion vs. Derived Overdue State:**
   - A reminder transitions to `COMPLETED` **ONLY** on explicit user action (e.g. checking the box) or explicit product completion; `completedAt = nowUtc`.
   - **Time passing does NOT automatically set `COMPLETED`.**
   - **`OVERDUE` is a derived UI filter/state (`status == SCHEDULED && scheduledAtUtc < nowUtc`), NOT a persisted enum.**
7. **Trip Deletion Lifecycle (Application-Layer Transactional Cancellation):**
   - Target schema specifies `trip onDelete: SetNull` as defensive referential behavior.
   - Reminders are cancelled transactionally at the application layer upon trip deletion:
     `UPDATE reminders SET status = 'CANCELLED', cancelled_at = NOW() WHERE trip_id = $tripId; DELETE FROM trips WHERE id = $tripId;`
   - Terminologically defined as **application-layer transactional cancellation** (not "cascade cancellation").
8. **Timezone Invariant & Schema Reality:**
   - Reminders are persisted as absolute UTC timestamps (`scheduledAtUtc`) alongside the geographical timezone string (`timezone = "Asia/Ho_Chi_Minh"`).
   - An audit of `apps/backend/prisma/schema.prisma` lines 390-425 (`model Trip`) and 110-135 (`model Destination`) demonstrates that neither model stores a `timezone` attribute. Automatic timezone derivation is classified as a **DESIGN TARGET / LOCATION-TIMEZONE MAPPING DEPENDENCY**. V1 UI pre-fills `Asia/Ho_Chi_Minh` for Vietnam trips and stores `timezone` directly on `Reminder`.
9. **Wandy AI Human-in-the-Loop Locked:**
   - Wandy proposes reminder suggestions via `+ Dùng gợi ý này`.
   - Tapping the CTA opens the Create Reminder form prefilled; autonomous database writes are strictly prohibited.
10. **Clean UI & Honesty Copy:**
   - All technical codes (e.g. "Mã phản hồi: 503"), backend jargon ("atomic reschedule"), and fake implementation status dashboards are purged from visual mockups. Footnote explicitly states: *"Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng."*

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)

Search command `Select-String -Path apps/backend/prisma/schema.prisma -Pattern "reminder|notification|schedule|cron|job|alert"` produced:
- Line 61: `notifications Notification[]` on `model User`.
- Line 361: `enum NotificationType { MATCH_REQUEST, MATCH_ACCEPTED, TRIP_INVITE, SAFETY_ALERT, NEW_COMMENT, NEW_LIKE, SYSTEM }`
- Line 371: `model Notification { id, userId, type, title, body, data, isRead, createdAt, user }`

**Findings:**
1. Zero reminder models exist in PostgreSQL.
2. `NotificationType` enum does not contain any `REMINDER` type.
3. `model User` has no device token fields (`pushToken`, `fcmToken`, `deviceToken`).

### 2.2. Backend Source Code Audit (`apps/backend/src/`)

Search command `Get-ChildItem -Path apps/backend/src -Recurse -Include *.ts | Select-String -Pattern "Reminder|Notification|Schedule|Cron|Bull|Worker|FCM|APNs|pushToken"` produced **0 matches**.

**Findings:**
- `model Notification` from `schema.prisma` is completely unreferenced in NestJS controllers or services.
- There are zero background tasks, zero cron jobs, and zero worker services running in the backend.

### 2.3. Backend Dependencies Audit (`apps/backend/package.json`)

Inspection of dependencies:
- `@nestjs/schedule`: **MISSING**
- `bull` / `bullmq`: **MISSING**
- `firebase-admin`: **MISSING**
- `@parse/node-apn`: **MISSING**
- `ioredis`: Installed (`^5.3.2`), but code grep confirmed **0 imports** in `apps/backend/src/`.

### 2.4. Mobile Client Dependencies & Code Audit (`apps/mobile/`)

Inspection of `apps/mobile/pubspec.yaml`:
- `flutter_local_notifications`: **MISSING**
- `firebase_messaging`: **MISSING**
- `workmanager` / `android_alarm_manager`: **MISSING**
- `timezone`: **MISSING** (`intl` is installed for date formatting).

Inspection of `apps/mobile/lib/`:
- Search for `reminder`, `nhắc`, `schedule` produced 0 feature matches (only `Icons.schedule` for opening hours and `AlertDialog` in trip details).

### 2.5. AI Service Audit (`apps/ai-service/`)

Inspection of `requirements.txt` and python sources:
- Zero cron, scheduling, or temporal tool libraries exist in FastAPI service.

---

## 3. Core Architectural Decisions (R1 Revision)

### 3.1. Ownership Decision: User owns Reminder
- `Reminder.userId` is required and points to `User.id` (`onDelete: Cascade`).
- `Reminder.tripId` is optional and points to `Trip.id` (`onDelete: SetNull`).
- `Reminder.itineraryItemId` is optional and points to `ItineraryItem.id` (`onDelete: SetNull`).
- Companion Groups have zero ownership relation with `Reminder`.

### 3.2. Lifecycle & State Model Decision: Explicit Completion & Derived Overdue
- `ReminderStatus` (`SCHEDULED`, `COMPLETED`, `CANCELLED`): Tracks the traveler's logical intent.
- `COMPLETED` is set **ONLY** on explicit user action (e.g. checkbox tap) or explicit product completion; `completedAt = nowUtc`. Time passing does **NOT** automatically mean completed.
- `OVERDUE` is a **derived temporal UI state** (`status == SCHEDULED && scheduledAtUtc < nowUtc`), **NOT** a database enum.
- Notification delivery state (`DeliveryStatus`) is removed from `model Reminder` and decoupled into future delivery transport architecture.

### 3.3. Timezone Contract & Destination Reality
- Absolute time instant `scheduledAtUtc` (`TIMESTAMPTZ`) guarantees universal consistency.
- `timezone` field persists original context (e.g. `Asia/Ho_Chi_Minh`, GMT+7) directly on `model Reminder`.
- *Prisma Audit Fact:* `model Trip` and `model Destination` lack a `timezone` column in `schema.prisma`. Automatic derivation is a `LOCATION-TIMEZONE MAPPING DEPENDENCY`. V1 pre-fills `Asia/Ho_Chi_Minh` for Vietnam trips.

### 3.4. Lifecycle Impact: Application-Layer Transactional Cancellation
- Deleting a `Trip`: Auto-cancels all associated reminders via an **application-layer transactional cancellation** (`UPDATE reminders SET status = 'CANCELLED', cancelled_at = NOW() WHERE trip_id = $id; DELETE FROM trips WHERE id = $id;`). Target schema uses `onDelete: SetNull` as defensive referential behavior.
- Deleting an `ItineraryItem`: Detaches the activity link (`itineraryItemId = null`), preserves the reminder with a neutral label `(Hoạt động liên kết không còn trong lịch trình.)`.

### 3.5. Rescheduling Transparency & Deduplication
- Editing due date/time replaces the scheduled instant atomically.
- Customer-facing copy: *"Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng."* (No developer jargon).
- Future dispatch worker enforces idempotency key: `reminderId + "_" + scheduledOccurrenceUtc`.

### 3.6. V1 Scope: Strictly One-Time Reminders
- V1 excludes `repeatRule`. Recurrence is deferred to an occurrence-based architecture (`ReminderOccurrence`) in future infrastructure.

---

## 4. Capability Matrix (24 Dimensions — R1 Aligned)

| Dimension | Database | Backend | Flutter | AI Service | Design Contract | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Reminder DB Model** | Missing | Missing | Missing | N/A | Section 6 | **SCHEMA GAP** | No `model Reminder` in `schema.prisma` (one-time target specified). |
| **2. Reminder API Endpoints** | Missing | Missing | Missing | N/A | Section 6, 11 | **DESIGN TARGET** | No CRUD endpoints in NestJS. |
| **3. Reminder Mobile UI** | Missing | Missing | Missing | N/A | Section 17 | **DESIGN LOCKED** | 6 R1 mockups + 1 preserved empty state; no Flutter code today. |
| **4. Trip Association** | Missing | Missing | Missing | N/A | Section 4, 6 | **DESIGN LOCKED** | Optional FK `tripId` pointing to `Trip.id` (`onDelete: SetNull`). |
| **5. Itinerary Association** | Missing | Missing | Missing | N/A | Section 4, 6 | **DESIGN LOCKED** | Optional FK `itineraryItemId` pointing to activity (`onDelete: SetNull`). |
| **6. Timezone Representation**| Missing | Missing | Missing | N/A | Section 7 | **DESIGN LOCKED** | `scheduledAtUtc` + stored `timezone` string; pre-filled `Asia/Ho_Chi_Minh`. |
| **7. Repeat Rule** | Excluded | Excluded | Excluded | N/A | Section 8 | **ONE-TIME ONLY** | Excluded from V1; future occurrence-based architecture (`ReminderOccurrence`). |
| **8. Server Scheduler Engine** | Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | No `@nestjs/schedule` in `package.json`. |
| **9. Delayed Job Worker** | Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | No background queue worker process. |
| **10. Redis Queue Integration**| Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | `ioredis` installed but zero imports in backend. |
| **11. Local Device Notification**| Missing| Missing | Missing | N/A | Section 10 | **FUTURE** | No `flutter_local_notifications` in `pubspec.yaml`. |
| **12. Remote Push (FCM)** | Missing | Missing | Missing | N/A | Section 10 | **FUTURE** | No `firebase-admin` or `firebase_messaging`. |
| **13. Remote Push (APNs)** | Missing | Missing | Missing | N/A | Section 10 | **FUTURE** | No APNs gateway library in backend. |
| **14. Push Token Storage** | Missing | Missing | Missing | N/A | Section 3 | **SCHEMA GAP** | No `deviceToken` or `fcmToken` in `User` model. |
| **15. Notification Permissions**| Missing| Missing | Missing | N/A | Section 15 | **DEFERRED** | Deferred to future; permission mockup marked superseded. |
| **16. Delivery Retry Policy** | Missing | Missing | Missing | N/A | Section 9 | **FUTURE SPEC** | Transport decoupled from reminder record; exponential backoff in future worker. |
| **17. Delivery Deduplication** | Missing | Missing | Missing | N/A | Section 13 | **FUTURE SPEC** | Idempotency key `reminderId_occurrence`. |
| **18. Cancellation Mechanics** | Missing | Missing | Missing | N/A | Section 11 | **DESIGN LOCKED** | `CANCELLED` status + `cancelledAt = nowUtc()`. |
| **19. Offline Behavior** | Missing | Missing | Missing | N/A | Section 14 | **DESIGN LOCKED** | Cached read; friendly error on offline write (zero tech codes). |
| **20. Wandy Reminder Suggestion**| Missing| Missing | Missing | Missing | Section 16 | **DESIGN LOCKED** | Informative suggestions with `+ Dùng gợi ý này` CTA. |
| **21. Wandy Autonomous Mutation**| Excluded| Excluded| Excluded| Excluded| Section 16 | **PROHIBITED** | Pre-fills form; user explicitly reviews and saves (HITL). |
| **22. Shared Trip Reminder** | Excluded| Excluded| Excluded| N/A | Section 5 | **FUTURE TARGET**| Requires explicit member opt-in consent. |
| **23. Trip Deletion Lifecycle** | Missing | Missing | Missing | N/A | Section 12 | **DESIGN LOCKED** | Application-layer transactional cancellation (`UPDATE SET CANCELLED`). |
| **24. Itinerary Deletion Lifecycle**| Missing| Missing | Missing | N/A | Section 12 | **DESIGN LOCKED** | Detachment (`itineraryItemId = null`) + neutral tag. |

---

## 5. Master Mockup Verification (R1 Revision)

The active Master V1 visual set consists of 7 mockups (6 updated R1 mockups + 1 preserved empty state), rendered at native resolutions using Microsoft Edge headless rendering and verified in `docs/audit/evidence/ui-08.2.3.14/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) | Mobile | $390 \times 844$ | 1. Filter chips: `Tất cả (3)`, `Hôm nay (1)`, `Sắp tới (2)`, `Đã qua (0)`.<br>2. Wandy card CTA: `+ Dùng gợi ý này ›` (opens prefilled form).<br>3. Clean customer footnote: `* Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng.`<br>4. Canonical 5-tab root nav (`Chuyến đi` active). | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) | Mobile | $390 \times 844$ | 1. Title, notes, date, time inputs.<br>2. Timezone box: `GMT+7 · Asia/Ho_Chi_Minh` (Việt Nam).<br>3. Repeat rule selector: **REMOVED** (One-time reminder only).<br>4. Privacy note: Private reminder.<br>5. Primary CTA `Lưu lời nhắc vào chuyến đi`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. Hero: Title, big time `07:00`, date, timezone `GMT+7`, status `ĐÃ LẬP LỊCH (Chờ đến giờ)`.<br>2. Context card with trip & activity links.<br>3. Metadata: Privacy (`Cá nhân`), Hiển thị (`Trong ứng dụng GoMate`). Zero fake push delivery channel status.<br>4. Actions: `Chỉnh sửa lời nhắc` / `Xóa lời nhắc`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) | Mobile | $390 \times 844$ | 1. Updated time `07:15` highlighted.<br>2. Informative reschedule banner: `Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng.` (Replaced developer jargon).<br>3. Repeat rule selector: **REMOVED**.<br>4. Primary CTA `[Lưu thay đổi lời nhắc]`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) | Mobile | $390 \times 844$ | 1. Centered clock illustration.<br>2. Title: `Chưa có lời nhắc nào`.<br>3. Primary CTA: `+ Thêm lời nhắc đầu tiên`. Preserved from V1. | **PASS (PRESERVED)** |
| [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) | Mobile | $390 \times 844$ | 1. Clean customer title: `Không thể tải danh sách lời nhắc`.<br>2. Clean travel copy: `Không thể kết nối tới GoMate lúc này. Vui lòng kiểm tra mạng và thử lại.`<br>3. Zero technical error codes (no 503), zero backend jargon.<br>4. Actions: `[Thử lại kết nối]` / `[Quay lại Chuyến đi]`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) | Mobile | $390 \times 844$ | *Archival only.* Depicts speculative OS channel settings. Excluded from V1 active master visual set because V1 contains zero notification runtime. | **SUPERSEDED / FUTURE CONCEPT** |
| [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`).<br>2. 3-column workstation layout.<br>3. Col 3: Wandy card with `+ Dùng gợi ý này` CTA, Timezone card, Privacy card. Removed fake delivery status dashboard and developer debug indicators. Zero scrollbars. | **PASS (R1 LOCKED)** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.14-R1)

- [x] **Repository fully audited:** Verified absence of reminder models, schedulers, and push gateways across `apps/`.
- [x] **No reminder capability assumed:** Documented greenfield state strictly as SCHEMA GAP & DESIGN TARGET.
- [x] **In-App is NOT Current:** In-App Reminder Center is documented as DESIGN TARGET / MISSING RUNTIME.
- [x] **Permission screen superseded:** `scheduling-mobile-permission-v1.png` marked as SUPERSEDED / FUTURE CONCEPT.
- [x] **V1 One-Time Reminders Only:** `RepeatRule` removed from target schema; recurrence deferred to `ReminderOccurrence` model.
- [x] **Decoupled Delivery Transport:** `deliveryStatus` removed from `model Reminder`.
- [x] **Target schema refined:** `id, userId, tripId?, itineraryId?, itineraryItemId?, title, notes?, scheduledAtUtc, timezone, status, createdAt, updatedAt, cancelledAt?, completedAt?`.
- [x] **Completed != Time Passed:** Explicit user/product completion sets `completedAt = nowUtc`.
- [x] **Overdue is derived UI state:** `status == SCHEDULED && scheduledAtUtc < nowUtc`; filter chips: `Tất cả`, `Hôm nay`, `Sắp tới`, `Đã qua`.
- [x] **Application-layer transactional cancellation:** Trip deletion cancels reminders transactionally in app layer; schema uses `trip onDelete: SetNull`.
- [x] **Timezone dependency documented:** `model Trip` and `model Destination` lack timezone in DB; V1 pre-fills `Asia/Ho_Chi_Minh` directly on `Reminder`.
- [x] **Clean UI & Copy:** No 503, no "atomic reschedule", no fake delivery status dashboard; honest footnote displayed.
- [x] **Wandy Human-in-the-Loop locked:** CTA `+ Dùng gợi ý này` opens prefilled Create Reminder form; no autonomous writes.
- [x] **6 R1 mockups rendered:** Verified via `view_file` at native resolutions.
- [x] **Empty state preserved:** `scheduling-mobile-empty-v1.png` kept as-is.
- [x] **Canonical root IA preserved:** Top desktop nav and mobile bottom nav strictly render `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`.
- [x] **No production changes:** `git diff apps/` is strictly empty.
- [x] **No Prisma changes:** `apps/backend/prisma/schema.prisma` is unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Working branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
