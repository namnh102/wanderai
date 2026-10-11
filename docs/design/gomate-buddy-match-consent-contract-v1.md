# GoMate Buddy Match Request & Mutual Consent Lifecycle Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION (REFINED — R1)  
**Task:** TASK 08.2.3.9 / TASK 08.2.3.9-R1 — GOMATE BUDDY MATCH CONSENT RUNTIME HONESTY & INTEGRATION CONTRACT FIX  
**Module:** Travel Buddy Match Request & Consent State Machine (`/buddy/matches`)  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:** 
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Match`, `enum MatchStatus`, `model User`, `model Profile`, `model TripMember`)
- Trip Controller Audit: `apps/backend/src/modules/trips/trips.controller.ts` & `trips.service.ts` (`POST /trips/:id/members`)
- Previous Contracts: `docs/design/gomate-buddy-discovery-contract-v1.md`, `docs/design/gomate-buddy-profile-contract-v1.md`
- Master Visual Artifacts (R1 Refined):
  - Mobile Confirm V1: [`buddy-mobile-request-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-confirm-v1.png) ($390 \times 844$)
  - Mobile Pending R1: [`buddy-mobile-request-pending-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-r1.png) ($390 \times 844$)
  - Mobile Received R1: [`buddy-mobile-request-received-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-r1.png) ($390 \times 844$)
  - Mobile Accepted R1: [`buddy-mobile-match-accepted-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-r1.png) ($390 \times 844$)
  - Mobile Rejected R1: [`buddy-mobile-request-rejected-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-r1.png) ($390 \times 844$)
  - Desktop Requests R1: [`buddy-desktop-requests-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-r1.png) ($1440 \times 900$)

---

## 1. Product Role & Architectural Vision

The **Match Request & Mutual Consent Lifecycle** defines the formal protocol by which two independent travelers in **GoMate** transition from viewing public candidate profiles to establishing a verified, consent-backed travel companion relationship.

### 1.1. Core Non-Negotiable Invariants
1. **Core Consent Invariant:**
   $$\text{Discovery View} \neq \text{Profile View} \neq \text{Send Request} \neq \text{Connected}$$
   $$\textbf{MATCHED} \iff \text{User A sends request} + \text{User B explicitly ACCEPTS}$$
   There is **no automatic connection, no swipe matching, and no unilateral connection**.
2. **Post-Match Data Boundaries (Not Everything Unlocks):**
   $$\text{MATCHED} \centernot\implies \text{Full Itinerary Access}$$
   $$\text{MATCHED} \centernot\implies \text{Live GPS Tracking}$$
   - Personal phone number unlocks according to mutual consent.
   - Detailed minute-by-minute itinerary **remains locked** until an explicit Trip Sharing invite is extended and accepted.
   - **GPS Scope Correction (Fix #6):** *"Vị trí thời gian thực không được chia sẻ trong kết nối bạn đồng hành."* (This scoped invariant does not constrain explicit, user-controlled location sharing in future safety emergency features).
   - Account email, password hash, and emergency contacts are **strictly Tier 4 / never exposed**.
3. **Data Honesty & Anti-Fabrication:**
   - **No fake compatibility percentages**: Only factual, explainable overlap bullet points.
   - **Verification semantics (Fix #2)**: `User.isVerified` canonically renders as `"Tài khoản đã xác minh"` (account/email authentication), never ambiguous `"Đã xác minh"` or `"Đã xác minh danh tính"`.
   - **No fake masked values**: Never render pseudo-private values like `09xx xxx xxx`.
   - **Demo Data Disclaimer (Fix #4 & #13)**: The unlocked phone number on the accepted mockup is strictly marked as visual demo data (`Dữ liệu mẫu hiển thị · Không phải số thực tế`), never representing real personal information.
4. **Information Architecture Parity (Canonical 5-Tab Root):**
   The application preserves the canonical 5 root tabs across devices (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [active], `An toàn`). Request management is reached contextually under Trip context.

---

## 2. Current vs Target Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Match Model** | Missing | Missing | `model Match` | Schema definition | **PARTIAL (DB Only)** | Model exists in schema; no backend controller. |
| **Send Request** | Missing | Missing | `status: PENDING` | Confirmation Bottom Sheet | **DESIGN TARGET** | Audited backend; 0 endpoints. |
| **Incoming Requests Inbox**| Missing | Missing | Query `receiverId` | Inbox card with Accept/Reject | **DESIGN TARGET** | Screen designed in `buddy-mobile-request-received-r1.png`. |
| **Sent Requests List** | Missing | Missing | Query `senderId` | Pending state display | **DESIGN TARGET** | Visualized in `buddy-desktop-requests-r1.png`. |
| **Accept Request** | Missing | Missing | `status: ACCEPTED` | State transition to Matched | **DESIGN TARGET** | DB enum exists; API route missing. |
| **Reject Request** | Missing | Missing | `status: REJECTED` | Respectful rejection flow | **DESIGN TARGET** | DB enum exists; API route missing. |
| **Cancel Sent Request** | Missing | Missing | **SCHEMA GAP** | Target cancel option | **BLOCKED (Schema)**| No `CANCELLED` status; requires DELETE or migration. |
| **Reverse Request Handling**| Missing | Missing | `@@unique([senderId, receiverId])`| Symmetric edge logic | **BLOCKED (Logic)** | Schema allows reverse duplicate `(B, A)`; symmetric logic needed. |
| **Duplicate Prevention** | Missing | Missing | `@@unique([senderId, receiverId])`| Prevents duplicate (A, B) | **CURRENT (DB) / TARGET (UI)**| Postgres unique constraint stops duplicate (A, B). |
| **Matched State** | Missing | Missing | `status: ACCEPTED` | "Đã kết nối" + Unlocked Phone | **DESIGN TARGET** | Full UI spec in `buddy-mobile-match-accepted-r1.png`. |
| **Private Contact Unlock**| Missing | Missing | `Profile.phone` | Phone revealed post-match | **PARTIAL (DB Only) / DESIGN TARGET (Logic)** | Phone exists in DB; unlock logic requires match state. |
| **Trip Invite from Buddy** | `POST :id/members` | Missing | `TripMember` | Safe Member Adapter Required | **PARTIAL / API ADAPTER REQUIRED** | Current API requires `email`, violating privacy. Adapter needed. |
| **Direct Chat** | Missing | Missing | `Group` & `Message` | Deferred to Group Chat Task | **PARTIAL (DB Only) / FUTURE** | DB models exist; chat UI removed from Accepted mockup. |
| **Push Notifications** | Missing | Missing | Missing Service | Status checks via polling/inbox| **DESIGN TARGET** | Zero FCM/APNs in repo; no notification overclaims. |
| **User Block** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **User Report** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 3. Match Schema Audit

### 3.1. Exact Prisma Model
```prisma
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

enum MatchStatus {
  PENDING
  ACCEPTED
  REJECTED
}
```

### 3.2. Critical Schema Limitations
1. **Missing `updatedAt`:** The `Match` table lacks an `updatedAt DateTime @updatedAt` column. The backend currently cannot record when a request was accepted or rejected without relying on `createdAt` or adding a new column.
2. **Missing `message` field:** There is no personal message or introduction field stored in `Match`. A custom note cannot be persisted without a schema migration.
3. **Missing `contextTripId`:** There is no foreign key linking a `Match` record to the specific `Trip` context in which it was initiated.
4. **No Cascade Delete:** `sender` and `receiver` relations default to Restrict / No Action.
5. **Restricted Status Enum:** Only `PENDING`, `ACCEPTED`, `REJECTED` exist. Statuses `CANCELLED`, `EXPIRED`, `BLOCKED` **do not exist**.

---

## 4. Directional Uniqueness & Reverse Request Audit

### 4.1. Current Database Behavior
In PostgreSQL, `@@unique([senderId, receiverId])` enforces uniqueness on the **ordered tuple** `(sender_id, receiver_id)`.
- If User A sends User B a request, row `(A, B, PENDING)` is created.
- If User A attempts to send User B another request, the database **rejects** the duplicate with a unique constraint violation (`P2002`).
- **CRITICAL GAP:** If User B attempts to send User A a request while `(A, B, PENDING)` is active, PostgreSQL **allows** inserting row `(B, A, PENDING)` because `(B, A) != (A, B)`.

### 4.2. Target Business Rule
A travel companion connection is an **undirected, symmetric semantic relationship**:
$$\text{Rel}(A, B) \equiv \text{Rel}(B, A)$$
Under no circumstances should two simultaneous `PENDING` records exist between the same pair of users.

### 4.3. Target Resolution Protocol
1. **Application-Level Pre-Flight Check:**
   Before creating any request, the backend query must verify:
   ```sql
   WHERE (sender_id = :A AND receiver_id = :B)
      OR (sender_id = :B AND receiver_id = :A)
   ```
2. **Reverse Request UX:**
   If User B visits User A's profile and taps `"Gửi lời mời kết nối"`, the client must detect the existing `(A, B, PENDING)` record and display:
   $$\textbf{"Lê Hoàng Nam đã gửi lời mời cho bạn."}$$
   with direct action buttons: `[Từ chối]` and `[Chấp nhận kết nối]`, rather than sending a redundant reverse request.

---

## 5. Consent State Machine

```
============================================================
GOMATE BUDDY MUTUAL CONSENT STATE MACHINE (R1)
============================================================

                [User A taps "Gửi lời mời kết nối"]
                                ↓
                      REQUEST_CONFIRMATION
                        (Bottom Sheet)
                        /            \
                [User taps Hủy]     [User taps Xác nhận]
                      ↓                      ↓
                 NO_RELATION           REQUEST_SENDING
                                       /             \
                                  [Failure]       [Success]
                                     ↓                ↓
                                SEND_ERROR       PENDING_SENT
                                (Retry toast)    (Profile locked)
                                                      |
                                         [Inbox Fetch / Polling /
                                          Target Notification Service]
                                                      ↓
                                               PENDING_RECEIVED
                                            (Receiver's Inbox/Card)
                                                /          \
                                [Tap Từ chối]          [Tap Chấp nhận]
                                      ↓                       ↓
                                  REJECTING               ACCEPTING
                                  /       \               /       \
                             [Fail]    [Success]     [Fail]    [Success]
                                ↓          ↓            ↓          ↓
                           REJECT_ERROR REJECTED   ACCEPT_ERROR MATCHED
                                       (No block,              (ACCEPTED)
                                        phone locked,          (Phone unlocked,
                                        privacy intact)         Trip sharing eligible
                                                                via Safe Adapter)
============================================================
```

---

## 6. Send Request Surface (Confirmation Modal)

- **Entry Point:** Buddy Profile primary CTA button `"Gửi lời mời kết nối"`.
- **Anti-Accidental Invariant:** Tapping the CTA **must not** immediately trigger an API request. It opens a dedicated confirmation surface.
- **Component Anatomy ([`buddy-mobile-request-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-confirm-v1.png)):**
  - Backdrop overlay: Dark translucent scrim (`rgba(15, 23, 42, 0.5)`).
  - Bottom sheet with rounded top corners ($20\text{px}$) and drag handle.
  - Title: `"Gửi lời mời kết nối?"`.
  - Context pill: `"Đồng hành cùng Lê Hoàng Nam · Chuyến đi: Đà Nẵng (15/10 – 18/10/2026) · 4 ngày"`.
  - Privacy note: `"🔒 Bảo mật thông tin: Người này chỉ được kết nối với bạn sau khi họ chấp nhận lời mời. Số điện thoại và lịch trình chi tiết của bạn sẽ không bị chia sẻ trước khi có sự đồng ý của cả hai."`.
  - Actions:
    - Left: `[Hủy]` (Neutral outline `#CBD5E1`). Dismisses sheet without mutation.
    - Right: `[Gửi lời mời]` (Pine Teal `#0F766E`, icon send). Triggers request creation.

---

## 7. Pending Sent State (Fix #1)

- **Visual Reference:** [`buddy-mobile-request-pending-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-r1.png).
- **Sender View:**
  - Amber banner at top with **truthful copy (no notification promise)**:
    $$\textbf{"Đang chờ Lê Hoàng Nam phản hồi. Bạn có thể kiểm tra trạng thái tại mục Lời mời đồng hành."}$$
  - Primary button state: Disabled / Pending style (`#F0FDFA`, border `#99F6E4`, text `#0F766E`):
    `⏱ Đã gửi lời mời · Đang chờ phản hồi`
  - Secondary action: `"Hủy lời mời kết nối (Mục tiêu thiết kế)"`.
- **Privacy Enforcement:**
  - Phone number **remains 100% locked** (`Chỉ hiển thị sau khi kết nối`).
  - Hourly itinerary **remains 100% locked** (`Chỉ chia sẻ khi là bạn đồng hành`).
  - Real-time location is not shared in the Buddy companion connection.

---

## 8. Incoming Request Inbox (Fix #2)

- **Visual Reference:** [`buddy-mobile-request-received-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-r1.png), [`buddy-desktop-requests-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-r1.png).
- **Receiver View:**
  - Screen title: `"Lời mời đồng hành"`.
  - Request Card:
    - Sender Avatar, Display Name, canonical verification label: **`"Tài khoản đã xác minh"`**, Age Band (`25–29 tuổi`), Nationality (`Việt Nam`).
    - Timestamp: `"Gửi lúc 09:15 hôm nay"`.
    - Context pill: `"Muốn kết nối cho chuyến đi Đà Nẵng (15–18/10)"`.
    - Factual compatibility criteria callout (`✓ Trùng 4 ngày du lịch...`).
    - Privacy disclosure: `"🔒 Chấp nhận sẽ mở số điện thoại của cả hai để tiện liên lạc chuẩn bị chuyến đi."`.
  - Action Buttons:
    - Left: `[Từ chối]` (Slate `#F1F5F9`, border `#CBD5E1`, text `#64748B`, height 42px).
    - Right: `[Chấp nhận kết nối]` (Pine Teal `#0F766E`, text `#FFFFFF`, height 42px).
  - **Dark Pattern Prevention:** Both buttons have balanced visual weight; reject is fully accessible and neutral.

---

## 9. Accept Contract & Post-Match Capabilities (Fix #4 & #5)

- **State Transition:** `Match.status` transitions from `PENDING` to `ACCEPTED`.
- **Visual Reference:** [`buddy-mobile-match-accepted-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-r1.png).
- **Post-Match UI:**
  - Success banner: `✓ Hai bạn đã kết nối bạn đồng hành! Cả hai đã đồng ý kết nối cho chuyến đi Đà Nẵng 15–18/10.`
  - **Phone Number Unlocked with Honest Action (Fix #4):**
    - Renders unlocked phone: `0912 345 678`.
    - Action: `[Sao chép số]` (`btn-copy-phone`) — no Zalo deep-link assumptions or untested third-party integrations.
    - Prominent disclaimer: `"Dữ liệu mẫu hiển thị · Không phải số thực tế (Visual demo data)"`.
  - **Detailed Itinerary Remains Protected:** Displays informative lock card: `"Lịch trình chi tiết theo giờ: Lịch trình chi tiết vẫn được bảo vệ. Hãy mời bạn đồng hành vào chuyến đi để cùng xem và đồng bộ lịch trình."`.
  - **Chat Boundary Honesty (Fix #5):**
    - `"Nhắn tin"` button is **removed** from the accepted screen because runtime chat/WebSocket is currently missing. Chat entry is strictly deferred to the dedicated Group Chat task.
    - Bottom bar renders only: `[+ Mời vào chuyến đi (Mục tiêu thiết kế)]` (Pine Teal `#0F766E`, height 44px).

---

## 10. Reject Contract & Cooldown Rule (Fix #7 & #8)

- **State Transition:** `Match.status` transitions from `PENDING` to `REJECTED`.
- **Visual Reference:** [`buddy-mobile-request-rejected-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-r1.png).
- **Core Principles:**
  - **Reject $\neq$ Block:** Rejecting a request does not block the user, flag their account, or report them.
  - **No Notification Claims (Fix #8):** Replaced overclaiming notification copy with neutral privacy copy:
    $$\textbf{"Bạn đã từ chối lời mời. Thông tin cá nhân của bạn vẫn được giữ kín. Người này không bị chặn trong hệ thống GoMate."}$$
  - Primary recovery action: `[Tiếp tục tìm bạn đồng hành khác]`.
- **Cooldown Rule Policy (Fix #7):**
  - **Status:** `DESIGN TARGET / PRODUCT POLICY REQUIRED`.
  - Specification: **"Configurable rejection cooldown — TBD"**.
  - No fixed hard-coded duration (such as "30 days") is locked into runtime contracts until formal product policy and database schema support (`updatedAt` or audit table) are introduced.

---

## 11. Cancel Sent Request Gap & Strategy

### 11.1. Technical Gap
The database currently lacks a `CANCELLED` status in `MatchStatus` (`PENDING`, `ACCEPTED`, `REJECTED`).

### 11.2. Architectural Options
- **Target Option A (Hard Delete):**
  - When the sender cancels a pending request, the backend executes `DELETE FROM matches WHERE id = :id AND status = 'PENDING'`.
  - *Advantage:* Requires no schema migration; returns pair to `NO_RELATION` state.
  - *Drawback:* Loses audit trail of previous requests.
- **Target Option B (Status Migration):**
  - Add `CANCELLED` to `MatchStatus` enum in Prisma.
  - When cancelled, update `status = 'CANCELLED'`.
  - *Advantage:* Preserves historical records for abuse prevention and cooldown tracking.
  - *Recommendation:* Adopt Option B in future schema migration; use Option A as interim backend implementation.

---

## 12. Privacy Unlock Matrix

| Data Field | Pre-Match | Pending Sent / Received | Accepted (Matched) | Explicit Share Required? | Never Share? | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Display Name & Avatar** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Profile baseline |
| **Age Band (`25–29`)** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Safe demographic band |
| **Nationality & Languages**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Cultural compatibility |
| **Bio Snippet** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Public bio text |
| **Travel Style & Interests**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Matching tags |
| **Trip Destination & Overlap**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Context trip dates |
| **Compatibility Reasons** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO | Explainable criteria |
| **Personal Phone Number** | 🔒 LOCKED | 🔒 LOCKED | 🔓 **UNLOCKED** | NO (Unlocked on Match) | NO | Direct communication post-match |
| **Detailed Hourly Itinerary**| 🔒 LOCKED | 🔒 LOCKED | 🔒 **LOCKED** | **YES (Trip Member Invite)**| NO | Requires Trip Member role |
| **Real-Time Live Location** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Buddy Scope)**| Not shared in Buddy companion connection |
| **Account Email** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Tier 4)** | **Never exposed to Buddy UI** |
| **Password Hash** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Tier 4)** | System internal |
| **Emergency Contacts (SOS)**| ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Tier 4)** | Safety SOS only |
| **Internal UUIDs** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Tier 4)** | System internal |

---

## 13. Trip Invite Contract Mismatch & Safe Adapter Architecture (Fix #3)

### 13.1. Critical Privacy & API Collision
- **Existing Endpoint Audit:** `POST /trips/:id/members` in `apps/backend/src/modules/trips/trips.controller.ts`:
  ```typescript
  class InviteMemberDto {
    @IsEmail({}, { message: 'Email không hợp lệ' })
    @IsNotEmpty()
    email: string;
  }
  ```
- **Privacy Collision:** In GoMate's privacy contract, `User.email` is **Tier 4 — SYSTEM PRIVATE / NEVER EXPOSED / NEVER DISCOVERABLE**.
- **Conflict:** When User A accepts a match with User B, the client UI **cannot and must not retrieve or expose User B's email address** simply to invoke `POST /trips/:id/members`. Supplying email to the Buddy frontend would break the fundamental privacy architecture.
- **Reclassification:**
  - "Mời vào chuyến đi" is reclassified from `CURRENT API / PARTIAL UI` to:
    $$\textbf{PARTIAL / DESIGN TARGET — REQUIRES SAFE USER-ID OR MATCH-ID ADAPTER}$$

### 13.2. Recommended Safe Adapter Contract
The backend Trip module must introduce a dedicated, safe member addition endpoint that operates without exposing user emails:

**Option 1 (Recommended — Match-Based):**
```http
POST /trips/:tripId/members/from-match
Authorization: Bearer <token>
Content-Type: application/json

{
  "matchId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
*Backend Resolution:*
1. Validates that `matchId` exists and `match.status === 'ACCEPTED'`.
2. Validates that current authenticated user is either `match.senderId` or `match.receiverId`.
3. Validates that caller is the owner of `tripId`.
4. Adds the other party to `TripMember` with role `member`.
5. Returns member record without exposing email to the Buddy UI.

**Option 2 (User-ID Based):**
```http
POST /trips/:tripId/members/by-user
Authorization: Bearer <token>
Content-Type: application/json

{
  "userId": "4fa85f64-5717-4562-b3fc-2c963f66afa7"
}
```
*Backend Resolution:* Validates active mutual consent between caller and target `userId` before creating `TripMember`.

---

## 14. Chat & Notification Boundaries (Fix #1 & #5)

### 14.1. In-App Chat Boundary
- Database models `Group` and `Message` exist, but **runtime chat/WebSocket is missing**.
- Action button `"Nhắn tin"` has been **removed** from the primary accepted mockup.
- Chat entry point and group formation will be designed comprehensively in the dedicated Group Chat task.

### 14.2. Notification Boundary
- There is currently **zero push notification code** (Firebase Cloud Messaging or APNs) in the backend repository.
- No UI surfaces in GoMate promise instant push alerts (e.g. *"Bạn sẽ nhận được thông báo khi..."* is removed).
- Users check incoming and pending request status via the `"Lời mời đồng hành"` inbox or client polling.
- Push notification events remain:
  $$\textbf{DESIGN TARGET — REQUIRES NOTIFICATION SERVICE}$$

---

## 15. Error Handling & Race Conditions

### 15.1. Error Contracts
- `SEND_ERROR`: `"Không thể gửi lời mời kết nối. Vui lòng kiểm tra mạng và thử lại."`
- `ACCEPT_ERROR`: `"Không thể chấp nhận lời mời. Vui lòng thử lại."`
- `REJECT_ERROR`: `"Không thể từ chối lời mời. Vui lòng thử lại."`
- All errors display user-friendly snackbars; never expose raw HTTP codes (500, 503) or Prisma exception names.

### 15.2. Race Condition Resolution
- **Scenario:** Receiver accepts request on mobile, but desktop inbox still shows `PENDING`.
- **Handling:** Every user interaction re-validates current server state. If the request was already accepted, the client smoothly updates to `MATCHED` without duplicate mutation errors.

---

## 16. Multi-Platform & Accessibility Contract

- **Mobile Viewports ($390 \times 844$):** 5 clean master screens representing the complete lifecycle without browser scrollbars.
- **Desktop Workstation ($1440 \times 900$):** Canonical 5-tab root navigation (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` active, `An toàn`), breadcrumbs, 3-tab request manager, balanced 2-column workstation layout.
- **Accessibility:** Touch targets $\ge 44 \times 44\text{ dp}$. Screen reader announcements for state changes:
  - *"Đã gửi lời mời kết nối tới Lê Hoàng Nam, đang chờ phản hồi."*
  - *"Hai bạn đã kết nối bạn đồng hành. Số điện thoại liên hệ đã mở khóa."*
  - *"Bạn đã từ chối lời mời kết nối."*
