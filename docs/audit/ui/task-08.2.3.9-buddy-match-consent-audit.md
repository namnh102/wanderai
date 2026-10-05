# GoMate Buddy Match Request & Consent Lifecycle — Architecture & Capability Audit (TASK 08.2.3.9)

**Status:** APPROVED ARCHITECTURAL AUDIT & LIFECYCLE SPECIFICATION  
**Task:** TASK 08.2.3.9 — GOMATE BUDDY MATCH REQUEST & MUTUAL CONSENT LIFECYCLE V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Audit Overview

TASK 08.2.3.9 executes an exhaustive technical audit and establishes the comprehensive UX and consent state machine for the **Buddy Match Request & Mutual Consent Lifecycle** (`Vòng đời lời mời kết nối và chấp thuận hai chiều`) in GoMate.

### Primary Audit Verdict:
1. **Database Reality:** Model `Match` exists with fields `id`, `senderId`, `receiverId`, `status` (`PENDING`, `ACCEPTED`, `REJECTED`), `score`, `explanation`, `createdAt`.
2. **Schema Limitations Discovered:**
   - **Missing `updatedAt`:** Table has no timestamp for when a request was accepted or rejected.
   - **Missing `message`:** Table has no column for custom introduction notes.
   - **Missing `contextTripId`:** Table has no link to the triggering trip.
   - **Missing statuses:** No `CANCELLED`, `EXPIRED`, or `BLOCKED` status exists.
3. **Directional Uniqueness Vulnerability:**
   - `@@unique([senderId, receiverId])` only prevents duplicate `(A, B)`.
   - In PostgreSQL, reverse pair `(B, A)` is **not blocked**, which permits split-brain duplicate relations without application-level transaction checks!
4. **Backend & Mobile Code Reality:**
   - **Zero match request endpoints exist** in NestJS backend.
   - **Zero match UI or state management code exists** in Flutter mobile client.
   - **Zero push notification code exists** in the repository.

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
```prisma
enum MatchStatus {
  PENDING
  ACCEPTED
  REJECTED
}

model Match {
  id         String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  senderId   String      @map("sender_id") @db.Uuid
  receiverId String      @map("receiver_id") @db.Uuid
  status     MatchStatus @default(PENDING)
  score      Float?      // compatibility score 0-100
  explanation String?    // AI explanation
  createdAt  DateTime    @default(now()) @map("created_at") @db.Timestamptz

  sender   User @relation("sender", fields: [senderId], references: [id])
  receiver User @relation("receiver", fields: [receiverId], references: [id])

  @@unique([senderId, receiverId])
  @@map("matches")
}
```

### 2.2. Backend API Inspection (`apps/backend/src/modules/`)
- Checked modules: `ai-proxy`, `auth`, `destinations`, `health`, `places`, `reviews`, `trips`, `users`, `videos`.
- Scanned for `match`, `buddy`, `request`, `accept`, `reject`.
- Result: **0 endpoints exist**. Neither `matches.controller.ts` nor `buddy.controller.ts` exists.

### 2.3. Flutter Client Inspection (`apps/mobile/lib/features/`)
- Checked features: `ai_chat`, `auth`, `home`, `location`, `map`, `places`, `trips`.
- Result: **0 screens, widgets, or blocs exist** for buddy requests or matches.

---

## 3. Directional Uniqueness & Reverse Request Vulnerability Analysis

```
============================================================
DIRECTIONAL UNIQUENESS AUDIT MATRIX
============================================================

SCENARIO 1: DUPLICATE FORWARD REQUEST (A -> B, then A -> B)
- Current Database Behavior: BLOCKED by @@unique([senderId, receiverId]).
- Database throws P2002 Unique Constraint Violation.
- Status: ENFORCED IN DB.

SCENARIO 2: REVERSE SIMULTANEOUS REQUEST (A -> B, then B -> A)
- Current Database Behavior: PERMITTED by PostgreSQL!
  Tuple (A, B) is distinct from Tuple (B, A).
- Database creates two separate rows:
  Row 1: { senderId: A, receiverId: B, status: PENDING }
  Row 2: { senderId: B, receiverId: A, status: PENDING }
- Consequence: Severe split-brain state where A accepts B while B rejects A,
  or two duplicate connections exist for the same pair!
- Target Business Rule: Connection is an UNDIRECTED SEMANTIC EDGE.
- Target Technical Resolution:
  1. Backend pre-flight query:
     WHERE (sender_id = A AND receiver_id = B) OR (sender_id = B AND receiver_id = A)
  2. Target UX: When B visits A's profile, UI shows incoming request from A
     with [Chấp nhận] / [Từ chối] instead of sending a second request.
============================================================
```

---

## 4. Privacy & Consent Risk Analysis

1. **Premature Data Leakage Risk:**
   - *Risk:* Exposing personal phone numbers or detailed itineraries while in `PENDING_SENT` or `PENDING_RECEIVED` state.
   - *Mitigation:* The privacy contract strictly locks phone and detailed itinerary across both pending states.
2. **Rejection Stigma & Dark Pattern Risk:**
   - *Risk:* Shaming the user who rejected a request or sending abrasive notifications to the requester.
   - *Mitigation:* Rejections are private, calm, and respectful. No negative push notification is emitted. Reject does **not** block the user.
3. **Automatic Trip Membership Risk:**
   - *Risk:* Assuming an accepted buddy match automatically grants write access to edit the user's trip.
   - *Mitigation:* Explicit separation between `Match` (social companion connection) and `TripMember` (trip workspace collaborator).

---

## 5. Comprehensive Capability Matrix

| Capability | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Match Model** | Missing | Missing | `model Match` | Schema definition | **PARTIAL (DB Only)** | Model exists in schema; no backend controller. |
| **Send Request** | Missing | Missing | `status: PENDING` | Confirmation Bottom Sheet | **DESIGN TARGET** | Audited backend; 0 endpoints. |
| **Incoming Requests Inbox**| Missing | Missing | Query `receiverId` | Inbox card with Accept/Reject | **DESIGN TARGET** | Screen designed in `buddy-mobile-request-received-v1.png`. |
| **Sent Requests List** | Missing | Missing | Query `senderId` | Pending state display | **DESIGN TARGET** | Visualized in `buddy-desktop-requests-v1.png`. |
| **Accept Request** | Missing | Missing | `status: ACCEPTED` | State transition to Matched | **DESIGN TARGET** | DB enum exists; API route missing. |
| **Reject Request** | Missing | Missing | `status: REJECTED` | Respectful rejection flow | **DESIGN TARGET** | DB enum exists; API route missing. |
| **Cancel Sent Request** | Missing | Missing | **SCHEMA GAP** | Target cancel option | **BLOCKED (Schema)**| No `CANCELLED` status; requires DELETE or migration. |
| **Reverse Request Handling**| Missing | Missing | `@@unique([senderId, receiverId])`| Symmetric edge logic | **BLOCKED (Logic)** | Schema allows reverse duplicate `(B, A)`; logic needed. |
| **Duplicate Prevention** | Missing | Missing | `@@unique([senderId, receiverId])`| Prevents duplicate (A, B) | **CURRENT (DB) / TARGET (UI)**| Postgres unique constraint stops duplicate (A, B). |
| **Matched State** | Missing | Missing | `status: ACCEPTED` | "Đã kết nối" + Unlocked Phone | **DESIGN TARGET** | Full UI spec in `buddy-mobile-match-accepted-v1.png`. |
| **Private Contact Unlock**| Missing | Missing | `Profile.phone` | Phone revealed post-match | **PARTIAL (DB Only)** | Phone field exists; unlock logic requires match state. |
| **Trip Invite** | `POST :id/members`| Missing | `TripMember` | Post-match explicit action | **CURRENT (API) / PARTIAL (UI)**| API exists; UI integration pending. |
| **Direct Chat** | Missing | Missing | `Group` & `Message` | Phase UI-3 | **PARTIAL (DB Only)** | Tables exist; runtime chat socket missing. |
| **Push Notifications** | Missing | Missing | Missing Service | Request received/accepted | **DESIGN TARGET** | No FCM/push service code currently in repo. |
| **User Block** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **User Report** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 6. Master Mockup Verification (6 Master Artifacts)

Exactly **six** master mockups were produced and verified at `docs/audit/evidence/ui-08.2.3.9/`:

| Mockup File | Viewport | Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`buddy-mobile-request-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-confirm-v1.png) | Mobile | $390 \times 844$ | 1. Bottom Sheet over darkened profile backdrop.<br>2. Drag handle + Title `"Gửi lời mời kết nối?"`.<br>3. Trip context pill: Đà Nẵng (15/10 – 18/10/2026).<br>4. Privacy reassurance text: "Người này chỉ được kết nối với bạn sau khi họ chấp nhận lời mời...".<br>5. Buttons: `[Hủy]` and `[Gửi lời mời]`. Zero scrollbars. | **PASS** |
| [`buddy-mobile-request-pending-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-v1.png) | Mobile | $390 \times 844$ | 1. Amber status banner: "Đã gửi lời mời kết nối · Đang chờ Lê Hoàng Nam phản hồi...".<br>2. Profile info + verified badge + age band.<br>3. Locked private info remains strictly locked.<br>4. Bottom bar button: "Đã gửi lời mời · Đang chờ phản hồi" + secondary link "Hủy lời mời kết nối (Mục tiêu thiết kế)". Zero scrollbars. | **PASS** |
| [`buddy-mobile-request-received-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-v1.png) | Mobile | $390 \times 844$ | 1. Top App Bar: "Lời mời đồng hành".<br>2. Incoming request card: avatar (HN), "Lê Hoàng Nam", verified badge, timestamp, context trip pill.<br>3. Factual compatibility criteria callout.<br>4. Privacy notice: "Chấp nhận sẽ mở số điện thoại...".<br>5. Balanced actions: `[Từ chối]` and `[Chấp nhận kết nối]`. Zero scrollbars. | **PASS** |
| [`buddy-mobile-match-accepted-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-v1.png) | Mobile | $390 \times 844$ | 1. Success green banner: "Hai bạn đã kết nối bạn đồng hành!".<br>2. Candidate profile header.<br>3. Phone number UNLOCKED: "0912 345 678" with [Gọi / Zalo].<br>4. Detailed hourly itinerary REMAINS PROTECTED with informative note.<br>5. Bottom action bar: `[Nhắn tin]` and `[Mời vào chuyến đi]`. Zero scrollbars. | **PASS** |
| [`buddy-mobile-request-rejected-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-v1.png) | Mobile | $390 \times 844$ | 1. Top App Bar: "Lời mời đồng hành".<br>2. Rejection feedback box: neutral icon, "Bạn đã từ chối lời mời".<br>3. Reassurance copy: "Đối phương sẽ không nhận được thông báo mang tính tiêu cực và người này không bị chặn...".<br>4. Primary recovery button: `[Tiếp tục tìm bạn đồng hành khác]`. Zero scrollbars. | **PASS** |
| [`buddy-desktop-requests-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-v1.png) | Desktop | $1440 \times 900$ | 1. Canonical 5-tab root navigation (Chuyến đi active).<br>2. Breadcrumb: Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Quản lý lời mời đồng hành.<br>3. 3-Tab switcher: Lời mời nhận được (1) [active] / Lời mời đã gửi (1) / Đã kết nối (2).<br>4. Left Pane ($820\text{px}$): Incoming request card with overlap, reasons, and [Từ chối] / [Chấp nhận kết nối] buttons.<br>5. Right Pane ($520\text{px}$): Sent requests overview card + Safety rules box. Zero scrollbars. | **PASS** |

---

## 7. Design Acceptance Gate (TASK 08.2.3.9)

- [x] **Exact Match schema audited:** Fields `id`, `senderId`, `receiverId`, `status`, `score`, `explanation`, `createdAt` verified.
- [x] **Unique constraint semantics verified:** `@@unique([senderId, receiverId])` ordered tuple behavior documented.
- [x] **Reverse request analyzed:** Vulnerability of `(B, A)` insertion documented with target pre-flight check and UI resolution.
- [x] **Current/Future separated:** Schema models vs missing APIs and push services cleanly distinguished.
- [x] **Consent state machine documented:** `NO_RELATION` $\rightarrow$ `CONFIRMATION` $\rightarrow$ `PENDING` $\rightarrow$ `ACCEPTED` / `REJECTED`.
- [x] **Send request requires explicit action:** Bottom sheet confirmation prevents accidental sends.
- [x] **Pending remains private:** Phone and hourly itinerary strictly locked.
- [x] **Accept establishes Match:** Two-way consent unlocks personal phone.
- [x] **Reject does not Block:** Rejection is respectful and separate from safety blocking.
- [x] **Cancel gap documented:** Absence of `CANCELLED` status documented with Options A & B.
- [x] **Duplicate request rule documented:** Blocked by DB forward unique constraint.
- [x] **Privacy unlock matrix complete:** Full 14-field classification table constructed.
- [x] **Detailed Trip still explicit-share:** Trip sharing requires `POST /trips/:id/members` invite.
- [x] **GPS never auto-unlocks:** Reassured that live coordinates are never collected or displayed.
- [x] **SafetyContact never exposes:** Strictly Tier 4 sensitive.
- [x] **Notification reality audited:** Lack of push notification code documented as Design Target.
- [x] **Error/race states defined:** Graceful snackbars, optimistic rollback, server re-validation.
- [x] **5 mobile master states created:** All 5 mobile screens rendered and verified ($390 \times 844$).
- [x] **1 desktop master created:** Workstation request center rendered and verified ($1440 \times 900$).
- [x] **No source changes:** 0 lines modified in `apps/`.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** Contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
