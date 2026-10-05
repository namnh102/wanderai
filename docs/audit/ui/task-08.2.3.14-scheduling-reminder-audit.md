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
  - Mobile Master List V1: [`scheduling-mobile-list-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-v1.png) ($390 \times 844$)
  - Mobile Master Create V1: [`scheduling-mobile-create-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-v1.png) ($390 \times 844$)
  - Mobile Master Detail V1: [`scheduling-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-v1.png) ($390 \times 844$)
  - Mobile Master Edit V1: [`scheduling-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Master Empty V1: [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) ($390 \times 844$)
  - Mobile Master Error V1: [`scheduling-mobile-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-v1.png) ($390 \times 844$)
  - Mobile Master Permission V1: [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) ($390 \times 844$)
  - Desktop Master Workstation V1: [`scheduling-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-v1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.14 executes a comprehensive repository capability and architectural audit for the Scheduling & Reminders experience in GoMate.

### Key Audit Findings:
1. **Repository Capability Reality (Total Infrastructure Gap):**
   - Neither `model Reminder`, `RemindersController`, nor any reminder service exists in the repository.
   - `model Notification` exists in `schema.prisma` (line 371) but represents an in-app notification inbox; it lacks reminder enums, has **zero backend controllers or services**, and has zero mobile UI bindings.
   - Zero scheduling decorators (`@nestjs/schedule`, `@Cron()`), zero queue managers (`bull`, `bullmq`), and zero push gateways (`firebase-admin`, `APNs`) exist in backend dependencies.
   - In the mobile client, `flutter_local_notifications` and `firebase_messaging` are **100% absent**.
   - **Verdict:** Scheduling and Reminders is an unbuilt, greenfield module. All specifications locked here represent the **Design Target and Business Contract V1**.
2. **First Principle Enforced:**
   $$\textbf{Reminder Persistence} \quad \ne \quad \textbf{Scheduler Engine} \quad \ne \quad \textbf{Notification Delivery}$$
   Database storage of a reminder date does not imply delivery. The UI and documentation strictly reject claiming background push notification delivery as a current capability.
3. **Canonical Ownership Locked (User-Owned):**
   - The user (`model User`) is the sole canonical owner of a reminder.
   - Contextual links to `Trip`, `Itinerary`, and `ItineraryItem` are strictly optional foreign keys.
   - The Companion Group is **NEVER** the owner; deleting a group has zero effect on personal trip reminders.
4. **Visibility & Privacy Boundary:**
   - V1 locks all reminders to **Private Mode (Creator-only)**.
   - Shared Trip Reminders are classified as a future design target requiring explicit participant opt-in consent.
5. **Timezone Invariant Locked:**
   - Reminders are persisted as absolute UTC timestamps (`scheduledAtUtc`) alongside the geographical timezone string (`timezone = "Asia/Ho_Chi_Minh"`).
   - Trip destination timezone takes precedence when setting trip-related reminders.
6. **Delivery Honesty:**
   - In-app reminder tracking is locked as active design target.
   - Push notifications (FCM/APNs) are classified as **FUTURE INFRASTRUCTURE**.
7. **Wandy AI Human-in-the-Loop Locked:**
   - Wandy may propose reminder suggestions based on upcoming activities.
   - Autonomous creation, modification, or cancellation of reminders without human confirmation is strictly forbidden.

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

## 3. Core Architectural Decisions

### 3.1. Ownership Decision: User owns Reminder
- `Reminder.userId` is required and points to `User.id` (`onDelete: Cascade`).
- `Reminder.tripId` is optional and points to `Trip.id` (`onDelete: SetNull`).
- `Reminder.itineraryItemId` is optional and points to `ItineraryItem.id` (`onDelete: SetNull`).
- Companion Groups have zero ownership relation with `Reminder`.

### 3.2. Lifecycle Decoupling Decision: Logical Status vs Delivery Status
- `ReminderStatus` (`SCHEDULED`, `COMPLETED`, `CANCELLED`): Tracks the traveler's intent and lifecycle.
- `DeliveryStatus` (`PENDING`, `DELIVERED`, `FAILED`): Tracks the technical notification transport outcome.
- Transient transport failures (airplane mode, offline) never mutate `ReminderStatus` away from `SCHEDULED`.

### 3.3. Timezone Contract Decision
- Absolute time instant `scheduledAtUtc` (`TIMESTAMPTZ`) guarantees universal consistency.
- `timezone` field persists original context (e.g. `Asia/Ho_Chi_Minh`, GMT+7).
- Cross-timezone travel preserves the destination clock hour rather than shifting unpredictably.

### 3.4. Cascade & Detachment Decision
- Deleting a `Trip`: Auto-cancels all associated reminders (`status = CANCELLED`, `cancelledAt = now()`).
- Deleting an `ItineraryItem`: Detaches the activity link (`itineraryItemId = null`), preserves the reminder with an informative label `(Hoạt động lịch trình liên kết đã được xóa)`.

### 3.5. Atomic Rescheduling & Deduplication Decision
- Editing due date/time replaces the scheduled instant atomically.
- Future dispatch worker enforces idempotency key: `reminderId + "_" + scheduledOccurrenceUtc`.

---

## 4. Capability Matrix (24 Dimensions)

| Dimension | Database | Backend | Flutter | AI Service | Design Contract | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Reminder DB Model** | Missing | Missing | Missing | N/A | Section 6 | **SCHEMA GAP** | No `model Reminder` in `schema.prisma`. |
| **2. Reminder API Endpoints** | Missing | Missing | Missing | N/A | Section 6, 11 | **DESIGN TARGET** | No CRUD endpoints in NestJS. |
| **3. Reminder Mobile UI** | Missing | Missing | Missing | N/A | Section 17 | **DESIGN LOCKED** | 7 mobile mockups locked; no Flutter code today. |
| **4. Trip Association** | Missing | Missing | Missing | N/A | Section 4, 6 | **DESIGN LOCKED** | Optional FK `tripId` pointing to `Trip.id`. |
| **5. Itinerary Association** | Missing | Missing | Missing | N/A | Section 4, 6 | **DESIGN LOCKED** | Optional FK `itineraryItemId` pointing to activity. |
| **6. Timezone Representation**| Missing | Missing | Missing | N/A | Section 7 | **DESIGN LOCKED** | `scheduledAtUtc` + `timezone` string. |
| **7. Repeat Rule** | Missing | Missing | Missing | N/A | Section 8 | **DESIGN TARGET** | Enums `NONE`, `DAILY`, `WEEKLY`. |
| **8. Server Scheduler Engine** | Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | No `@nestjs/schedule` in `package.json`. |
| **9. Delayed Job Worker** | Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | No background queue worker process. |
| **10. Redis Queue Integration**| Missing | Missing | Missing | N/A | Section 2 | **FUTURE** | `ioredis` installed but zero imports in backend. |
| **11. Local Device Notification**| Missing| Missing | Missing | N/A | Section 10 | **FUTURE** | No `flutter_local_notifications` in `pubspec.yaml`. |
| **12. Remote Push (FCM)** | Missing | Missing | Missing | N/A | Section 10 | **FUTURE** | No `firebase-admin` or `firebase_messaging`. |
| **13. Remote Push (APNs)** | Missing | Missing | Missing | N/A | Section 10 | **FUTURE** | No APNs gateway library in backend. |
| **14. Push Token Storage** | Missing | Missing | Missing | N/A | Section 3 | **SCHEMA GAP** | No `deviceToken` or `fcmToken` in `User` model. |
| **15. Notification Permissions**| Missing| Missing | Missing | N/A | Section 15 | **FUTURE** | Independent storage vs. OS permission locked. |
| **16. Delivery Retry Policy** | Missing | Missing | Missing | N/A | Section 9 | **DESIGN SPEC** | Decoupled state machine; exponential backoff. |
| **17. Delivery Deduplication** | Missing | Missing | Missing | N/A | Section 13 | **DESIGN SPEC** | Idempotency key `reminderId_occurrence`. |
| **18. Cancellation Mechanics** | Missing | Missing | Missing | N/A | Section 11 | **DESIGN LOCKED** | `CANCELLED` status + atomic job invalidation. |
| **19. Offline Behavior** | Missing | Missing | Missing | N/A | Section 14 | **DESIGN LOCKED** | Cached read; friendly error on offline write. |
| **20. Wandy Reminder Suggestion**| Missing| Missing | Missing | Missing | Section 16 | **DESIGN LOCKED** | Informative prompt suggestions. |
| **21. Wandy Autonomous Mutation**| Excluded| Excluded| Excluded| Excluded| Section 16 | **PROHIBITED** | Human-in-the-loop confirmation strictly required. |
| **22. Shared Trip Reminder** | Excluded| Excluded| Excluded| N/A | Section 5 | **FUTURE TARGET**| Requires explicit member opt-in consent. |
| **23. Trip Deletion Lifecycle** | Missing | Missing | Missing | N/A | Section 12 | **DESIGN LOCKED** | Auto-cancellation of bound reminders. |
| **24. Itinerary Deletion Lifecycle**| Missing| Missing | Missing | N/A | Section 12 | **DESIGN LOCKED** | Detachment (`itineraryItemId = null`) + tag. |

---

## 5. Master Mockup Verification (8 Master Artifacts)

All 8 master mockups were generated via headless Edge rendering at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.14/`:

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

## 6. Design Acceptance Gate (TASK 08.2.3.14)

- [x] **Repository fully audited:** Verified absence of reminder models, schedulers, and push gateways across `apps/`.
- [x] **No reminder capability assumed:** Documented greenfield state strictly as SCHEMA GAP & DESIGN TARGET.
- [x] **Reminder != Notification:** Strictly separated persistence from notification delivery.
- [x] **Notification != Scheduler:** Clarified that a scheduler evaluates time while notification delivers alerts.
- [x] **Ownership defined:** `User` owns reminder; `Trip` and `ItineraryItem` are optional contexts.
- [x] **Trip relation defined:** Optional foreign key `tripId` with cascade cancellation on trip deletion.
- [x] **Itinerary relation defined:** Optional foreign key `itineraryItemId` with detachment on item deletion.
- [x] **Timezone contract defined:** Absolute UTC `scheduledAtUtc` + `timezone` string (`Asia/Ho_Chi_Minh`).
- [x] **Repeat boundary defined:** Locked to `NONE`, `DAILY`, `WEEKLY`; RFC 5545 RRULE excluded.
- [x] **Reminder lifecycle defined:** `SCHEDULED`, `COMPLETED`, `CANCELLED`.
- [x] **Delivery lifecycle separated:** `PENDING`, `DELIVERED`, `FAILED`.
- [x] **Delete/cancel rules defined:** Cancelling marks `CANCELLED` and invalidates pending jobs.
- [x] **Trip deletion behavior defined:** Reminders auto-cancelled when trip is deleted.
- [x] **Itinerary deletion behavior defined:** Reminders detached when linked activity is deleted.
- [x] **Retry boundary defined:** Exponential backoff specified for future delivery engine.
- [x] **Deduplication target defined:** Idempotency key `reminderId + "_" + scheduledOccurrenceUtc`.
- [x] **Notification infra truthfully classified:** In-app active; FCM/APNs lock-screen push classified as FUTURE.
- [x] **Wandy Human-in-the-loop locked:** Autonomous reminder creation/edits strictly forbidden.
- [x] **Mobile mockups created:** All 7 mobile mockups generated and verified ($390 \times 844$).
- [x] **Desktop mockup created:** Desktop workstation generated and verified ($1440 \times 900$).
- [x] **Canonical root IA preserved:** Top desktop nav and mobile bottom nav strictly render `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`.
- [x] **No fake push claims:** UI explicitly states push notifications are in development.
- [x] **No production changes:** `git diff apps/` is strictly empty.
- [x] **No Prisma changes:** `apps/backend/prisma/schema.prisma` is unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Working branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
