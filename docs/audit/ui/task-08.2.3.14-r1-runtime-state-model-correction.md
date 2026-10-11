# GoMate Scheduling & Reminders — Runtime Honesty, State Model & V1 Scope Correction (TASK 08.2.3.14-R1)

**Status:** APPROVED ARCHITECTURAL ADDENDUM & DESIGN LOCK  
**Task:** TASK 08.2.3.14-R1 — GOMATE SCHEDULING & REMINDERS: RUNTIME HONESTY, STATE MODEL & V1 SCOPE CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Master Visual Evidence Artifacts:**
- Mobile Reminder List R1: [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) ($390 \times 844$)
- Mobile Create Reminder R1: [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) ($390 \times 844$)
- Mobile Reminder Detail R1: [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) ($390 \times 844$)
- Mobile Edit Reminder R1: [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) ($390 \times 844$)
- Mobile Empty State V1: [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) ($390 \times 844$) [Preserved from V1]
- Mobile Error State R1: [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) ($390 \times 844$)
- Mobile Channels & Permissions (SUPERSEDED / FUTURE CONCEPT): [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) ($390 \times 844$) [Kept for audit history; removed from Master V1 visual scope]
- Desktop Master Workstation R1: [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) ($1440 \times 900$)

---

## 1. Executive Summary

TASK 08.2.3.14-R1 executes targeted architectural, state model, and visual corrections for the GoMate Scheduling & Reminders module before final Design Lock.

This addendum formalizes 8 essential micro-corrections:
1. **In-App is NOT Current & Permission Screen Superseded:** Reclassified In-App Reminder Center as `DESIGN TARGET / MISSING RUNTIME`. Removed speculative OS channel permissions screen from active Master V1 set (`scheduling-mobile-permission-v1.png` designated as `SUPERSEDED / FUTURE CONCEPT`).
2. **V1 Scope Locked to One-Time Reminders Only:** Removed `RepeatRule` enum and `repeatRule` column from `model Reminder`. Recurrence is deferred to an occurrence-based data model (`ReminderOccurrence`) in **Future Recurrence Architecture**.
3. **Decoupled Delivery Transport:** Removed `deliveryStatus` from `model Reminder`. Delivery state belongs to future dispatch infrastructure, not to the logical reminder intent record.
4. **Target Schema Model Refined:** Target `model Reminder` specified with fields `id, userId, tripId?, itineraryId?, itineraryItemId?, title, notes?, scheduledAtUtc, timezone, status, createdAt, updatedAt, cancelledAt?, completedAt?`.
5. **Explicit Completion vs. Derived Overdue State:** `COMPLETED` is triggered solely by explicit user action or product completion (`completedAt = nowUtc`). Time passing does NOT set completed. `OVERDUE` is a derived temporal UI state (`status == SCHEDULED && scheduledAtUtc < nowUtc`), NOT a persisted enum. Filter chips: `Tất cả`, `Hôm nay`, `Sắp tới`, `Đã qua`.
6. **Application-Layer Transactional Cancellation for Trip Deletion:** Replaced vague "cascade cancellation" with precise application-layer transactional cancellation semantics. Database relation uses defensive `onDelete: SetNull`.
7. **Timezone Reality & Trip/Destination Schema Dependency:** Acknowledged codebase audit fact: `model Trip` and `model Destination` lack timezone columns in `schema.prisma`. Automatic derivation is classified as a `LOCATION-TIMEZONE MAPPING DEPENDENCY`. V1 pre-fills `Asia/Ho_Chi_Minh` directly on `model Reminder`.
8. **UI Copy Cleanup & Developer Jargon Removal:** Purged all technical error codes (no 503), backend phrases ("atomic reschedule"), and fake implementation dashboards from visual mockups. Wandy proposal CTA locked to `+ Dùng gợi ý này` (Human-in-the-Loop form prefill).

---

## 2. Micro-Correction Breakdown (Before → Risk → Evidence → Correction → Locked Contract)

### 2.1. In-App Runtime Reality & OS Permission Screen Superseded

- **Before:** V1 documentation loosely classified In-App Reminder Center as "Đang hoạt động" (Active/Current) and included a dedicated mobile permission screen ([`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png)) configuring OS notification channels.
- **Risk:** Fabricating capabilities that do not exist in the repository; confusing future design targets with live code; presenting OS permission switches when Flutter has zero notification plugins installed.
- **Evidence:**
  - `apps/backend/src/` has 0 reminder controllers or notification services.
  - `apps/mobile/pubspec.yaml` contains 0 notification packages (`flutter_local_notifications` is missing).
- **Correction:**
  - In-App Reminder Center is explicitly reclassified as **DESIGN TARGET / MISSING RUNTIME**.
  - `scheduling-mobile-permission-v1.png` is removed from active Master V1 visual scope and designated as **SUPERSEDED / FUTURE CONCEPT** (retained in repository for audit history).
- **Locked Contract:**
  V1 client contains no OS notification permission screens. Active visual scope contains 7 mockups (6 R1 + 1 empty state).

---

### 2.2. V1 Scope: Strictly One-Time Reminders & Removal of `repeatRule`

- **Before:** Target `model Reminder` included `repeatRule RepeatRule @default(NONE)` with enum values `NONE`, `DAILY`, `WEEKLY`.
- **Risk:**
  - Modeling flaw: Storing recurrence on a single reminder record with a single status field fails in real-world travel. Each occurrence has its own independent lifecycle (e.g. Occurrence 1 completed, Occurrence 2 upcoming, Occurrence 3 missed).
  - Scope creep: Building recurrence without background workers or occurrence generation leads to broken UX.
- **Evidence:** Database architecture analysis of travel reminder lifecycle.
- **Correction:**
  - Completely remove `RepeatRule` enum and `repeatRule` column from `model Reminder` V1.
  - V1 is strictly locked to **one-time reminders** (which covers $>95\%$ of travel itinerary needs: check-in, departure, opening slot, reservation).
  - Recurrence is moved to **Future Recurrence Architecture**, which requires a parent-child relationship:
    ```
    model Reminder (Parent Rule/Definition)
       └── 1 : N ──> model ReminderOccurrence (id, reminderId, scheduledAtUtc, status, deliveryStatus, completedAt)
    ```
- **Locked Contract:**
  No `repeatRule` selector in Create/Edit screens; target schema is strictly one-time.

---

### 2.3. Decoupling Delivery Transport & Removal of `deliveryStatus`

- **Before:** `model Reminder` included `deliveryStatus DeliveryStatus @default(PENDING)` with values `PENDING`, `DELIVERED`, `FAILED`.
- **Risk:**
  - Violates First Principle: Conflates logical reminder intent with transport delivery mechanics.
  - In V1, no background push delivery runtime exists. Storing `DELIVERED` on a database record that only renders inside an in-app list creates a false architectural model.
- **Evidence:** Codebase audit confirming zero FCM, APNs, or local alarm workers.
- **Correction:**
  - Remove `DeliveryStatus` enum and `deliveryStatus` column from `model Reminder`.
  - Delivery state belongs to future dispatch/occurrence workers, not to the logical reminder intent record.
- **Locked Contract:**
  Target `model Reminder` tracks only logical fields: `id, userId, tripId?, itineraryId?, itineraryItemId?, title, notes?, scheduledAtUtc, timezone, status, createdAt, updatedAt, cancelledAt?, completedAt?`.

---

### 2.4. Completion Semantics & Derived Overdue UI State

- **Before:** V1 draft stated that `COMPLETED` occurred when the user marked done "or the event concluded / time passed".
- **Risk:**
  - Ambiguity: If time passing automatically marks a reminder as complete, travelers who missed an alert would see their unhandled reminder silently vanish into "completed" history.
  - Persisting "OVERDUE" in database enums creates state-sync lag (requires constant cron polling to update status from `SCHEDULED` to `OVERDUE`).
- **Evidence:** User experience analysis for critical travel milestones.
- **Correction:**
  - `COMPLETED` is set **ONLY** on explicit user action (e.g. tapping the checkbox in list/detail) or explicit product completion; `completedAt = nowUtc` is written.
  - **Time passing does NOT automatically set `COMPLETED`.**
  - **`OVERDUE` is a derived temporal UI state, NOT a persisted enum:**
    $$\text{isOverdue} = (\text{status} == \text{SCHEDULED}) \land (\text{scheduledAtUtc} < \text{nowUtc})$$
  - Filter chips on client: `Tất cả`, `Hôm nay`, `Sắp tới`, `Đã qua` (Overdue).
- **Locked Contract:**
  Explicit user completion required; overdue dynamically computed by client.

---

### 2.5. Application-Layer Transactional Cancellation for Trip Deletion

- **Before:** V1 documentation used the term "cascade cancellation" without defining database vs. application semantics.
- **Risk:**
  - Technical conflict: In PostgreSQL/Prisma, database-level cascade (`onDelete: Cascade`) physically deletes rows (`DELETE`), whereas business requirements require soft cancellation (`status = CANCELLED`, `cancelledAt = now()`) to preserve audit history and prevent orphaned jobs.
  - Prisma schema uses `trip onDelete: SetNull` as defensive referential behavior.
- **Evidence:** [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) referential integrity patterns.
- **Correction:**
  - Formally designate the cancellation mechanism as **application-layer transactional cancellation**:
    ```sql
    BEGIN TRANSACTION;
      UPDATE reminders
      SET status = 'CANCELLED', cancelled_at = NOW()
      WHERE trip_id = $tripId AND status = 'SCHEDULED';
      
      DELETE FROM trips WHERE id = $tripId;
    COMMIT;
    ```
  - Prohibit the phrase "cascade cancellation".
  - Itinerary item deletion detaches the link (`itineraryItemId = null`) and preserves the reminder with neutral label: *(Hoạt động liên kết không còn trong lịch trình.)*.
- **Locked Contract:**
  Application-layer transactional cancellation locked; database `onDelete: SetNull`.

---

### 2.6. Timezone Reality & Trip/Destination Schema Dependency

- **Before:** Contract stated that trip-related reminders automatically inherit destination timezone from `Trip`.
- **Risk:**
  - Schema contradiction: A developer attempting to query `trip.timezone` or `destination.timezone` will discover that neither field exists in `schema.prisma`.
- **Evidence:**
  - [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) lines 390–425 (`model Trip`): has `id, title, destinationId, startDate, endDate, visibility, budget, createdAt, updatedAt` — **NO timezone field**.
  - Lines 110–135 (`model Destination`): has `id, name, slug, description, country, region, imageUrl, isPopular, createdAt, updatedAt` — **NO timezone field**.
- **Correction:**
  - Acknowledge this codebase reality explicitly.
  - Classify automatic destination timezone derivation as a **DESIGN TARGET / LOCATION-TIMEZONE MAPPING DEPENDENCY**.
  - In V1, the client pre-fills `Asia/Ho_Chi_Minh` (GMT+7) for Vietnam trips and stores `timezone` directly on `model Reminder`.
- **Locked Contract:**
  Direct timezone persistence on `model Reminder`; schema dependency documented.

---

### 2.7. UI Copy Cleanup & Developer Jargon Removal

- **Before:**
  - `scheduling-mobile-error-v1.png` displayed: *"Mã phản hồi: 503 · Không thể kết nối máy chủ"* and technical offline notes.
  - `scheduling-mobile-edit-v1.png` displayed: *"Atomic reschedule"* and repeat rule selectors.
  - `scheduling-desktop-v1.png` Col 3 displayed: Implementation debug indicators (*"Thông báo nội bộ app: Đang hoạt động"*, *"Khử trùng lặp (Idempotent): Khóa V1"*).
- **Risk:**
  - Exposing internal engineering jargon and HTTP status codes to end-users in production-intent mockups.
  - Misleading users into thinking an active notification delivery service is running.
- **Correction:**
  - Mobile Error R1: Displays clean customer title (*"Không thể tải danh sách lời nhắc"*) and travel copy (*"Không thể kết nối tới GoMate lúc này. Vui lòng kiểm tra mạng và thử lại."*). Zero codes, zero stacktraces.
  - Mobile Edit R1: Replaced developer jargon with traveler-oriented copy: *"Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng."*. Purged repeat selector.
  - Desktop R1: Replaced technical delivery dashboard in Col 3 with helpful travel guidance: Wandy AI Copilot suggestion, Timezone storage explanation, and Privacy explanation.
  - All mockups include honest footnote: `* Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng.`
- **Locked Contract:**
  All 6 updated mockups re-rendered and verified.

---

### 2.8. Wandy AI Human-in-the-Loop CTA Contract

- **Before:** Wandy suggestion CTA was labeled ambiguously (`+ Đặt lời nhắc này`).
- **Risk:** Implying that tapping the CTA immediately schedules or writes a reminder in the background without user review.
- **Correction:**
  - Wandy CTA is standardized to `+ Dùng gợi ý này` (Mobile) and `+ Dùng gợi ý này` (Desktop).
  - Tapping the CTA navigates to the **Create Reminder** form pre-filled with Wandy's suggested title, date, time, and context link.
  - The traveler must review the parameters and explicitly tap `[Lưu lời nhắc vào chuyến đi]`.
  - Autonomous database writes are strictly forbidden.
- **Locked Contract:**
  Human-in-the-Loop form prefill locked.

---

## 3. Master Visual Evidence Verification (R1 Revision)

The active Master V1 visual set consists of 7 mockups (6 updated R1 mockups + 1 preserved empty state), rendered via Microsoft Edge headless browser at native resolutions:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`scheduling-mobile-list-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-list-r1.png) | Mobile | $390 \times 844$ | 1. Filter chips: `Tất cả (3)`, `Hôm nay (1)`, `Sắp tới (2)`, `Đã qua (0)` [Overdue derived state].<br>2. Wandy card: `+ Dùng gợi ý này ›` (HITL form prefill entry).<br>3. Clean customer footnote: `* Lời nhắc này được lưu trong GoMate. Thiết bị sẽ không tự phát cảnh báo ngoài ứng dụng.`<br>4. Canonical 5-tab root nav (`Chuyến đi` active). | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-create-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-create-r1.png) | Mobile | $390 \times 844$ | 1. Fields: Title, notes, date, time inputs.<br>2. Timezone box: `GMT+7 · Asia/Ho_Chi_Minh` (Việt Nam).<br>3. Repeat rule selector: **REMOVED** (One-time reminder only).<br>4. Privacy note: Private reminder.<br>5. Primary CTA `Lưu lời nhắc vào chuyến đi`. Contained cleanly in $844\text{px}$. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. Hero: Title, big time `07:00`, date, timezone `GMT+7`, status `ĐÃ LẬP LỊCH (Chờ đến giờ)`.<br>2. Context card with trip & activity links.<br>3. Metadata: Privacy (`Cá nhân (Chỉ bạn thấy)`), Hiển thị (`Trong ứng dụng GoMate`). Zero fake push delivery channel status.<br>4. Actions: `Chỉnh sửa lời nhắc` / `Xóa lời nhắc`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-edit-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-edit-r1.png) | Mobile | $390 \times 844$ | 1. Updated time `07:15` highlighted in teal.<br>2. Informative reschedule banner: `Khi đổi thời gian, mốc nhắc cũ sẽ được thay thế để tránh tạo lời nhắc trùng.` (Replaced developer jargon).<br>3. Repeat rule selector: **REMOVED**.<br>4. Primary CTA `[Lưu thay đổi lời nhắc]`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-empty-v1.png) | Mobile | $390 \times 844$ | 1. Centered clock illustration.<br>2. Title: `Chưa có lời nhắc nào`.<br>3. Primary CTA: `+ Thêm lời nhắc đầu tiên`. Preserved from V1. | **PASS (PRESERVED)** |
| [`scheduling-mobile-error-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-error-r1.png) | Mobile | $390 \times 844$ | 1. Clean customer title: `Không thể tải danh sách lời nhắc`.<br>2. Clean travel copy: `Không thể kết nối tới GoMate lúc này. Vui lòng kiểm tra mạng và thử lại.`<br>3. Zero technical error codes (no 503), zero backend jargon.<br>4. Actions: `[Thử lại kết nối]` / `[Quay lại Chuyến đi]`. | **PASS (R1 LOCKED)** |
| [`scheduling-mobile-permission-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-mobile-permission-v1.png) | Mobile | $390 \times 844$ | *Archival only.* Depicts speculative OS channel settings. Excluded from V1 active master visual set because V1 contains zero notification runtime. | **SUPERSEDED / FUTURE CONCEPT** |
| [`scheduling-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.14/scheduling-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`).<br>2. 3-column workstation layout.<br>3. Col 3: Wandy card with `+ Dùng gợi ý này` CTA, Timezone card, Privacy card. Removed fake delivery status dashboard and developer debug indicators. Zero scrollbars. | **PASS (R1 LOCKED)** |

---

## 4. Verification Check & Design Lock Gate (TASK 08.2.3.14-R1)

- [x] **Repository Audit Honesty:** Confirmed 0 reminder models, 0 scheduler workers, and 0 push notification packages across `apps/`.
- [x] **In-App is NOT Current:** Documented as `DESIGN TARGET / MISSING RUNTIME`.
- [x] **Permission Mockup Superseded:** `scheduling-mobile-permission-v1.png` designated as `SUPERSEDED / FUTURE CONCEPT` and removed from active Master set.
- [x] **One-Time Reminders Locked:** `RepeatRule` removed; recurrence deferred to `ReminderOccurrence` architecture.
- [x] **Decoupled Delivery Transport:** `deliveryStatus` removed from `model Reminder`.
- [x] **Refined Target Schema:** Complete 14-field specification locked with `completedAt` timestamp.
- [x] **Explicit Completion Semantics:** `COMPLETED` requires explicit user/product action; time passing does not auto-complete.
- [x] **Derived Overdue State:** `OVERDUE` dynamically derived by client (`status == SCHEDULED && scheduledAtUtc < nowUtc`); filter chips: `Tất cả`, `Hôm nay`, `Sắp tới`, `Đã qua`.
- [x] **Application-Layer Transactional Cancellation:** Trip deletion cancels reminders transactionally in application layer (`UPDATE SET CANCELLED`); database uses `onDelete: SetNull`.
- [x] **Timezone Dependency Documented:** Documented that neither `Trip` nor `Destination` possesses a `timezone` field in `schema.prisma`. V1 pre-fills `Asia/Ho_Chi_Minh` directly on `Reminder`.
- [x] **Clean Customer Copy:** Purged "503", "atomic reschedule", and debug dashboards. Added honest footnote.
- [x] **Wandy Human-in-the-Loop Locked:** `+ Dùng gợi ý này` opens prefilled Create Reminder form; zero autonomous DB writes.
- [x] **Visual Mockups Rendered & Inspected:** 6 R1 mockups rendered and verified via `view_file`; 1 empty state preserved.
- [x] **Canonical Root IA Maintained:** Top desktop nav and mobile bottom nav strictly render `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`.
- [x] **Zero Production Changes:** `git diff apps/` is strictly empty.
- [x] **Zero Prisma Changes:** `apps/backend/prisma/schema.prisma` is unmodified.
- [x] **Zero API Changes:** API contracts intact.
- [x] **No Merge & No Push:** Working branch `feature/gomate-visual-mockups` preserved; commit local only.
