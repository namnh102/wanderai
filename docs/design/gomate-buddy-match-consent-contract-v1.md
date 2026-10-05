# GoMate Buddy Match Request & Mutual Consent Lifecycle Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION  
**Task:** TASK 08.2.3.9 — GOMATE BUDDY MATCH REQUEST & MUTUAL CONSENT LIFECYCLE V1  
**Module:** Travel Buddy Match Request & Consent State Machine (`/buddy/matches`)  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:** 
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Match`, `enum MatchStatus`, `model User`, `model Profile`, `model TripMember`)
- Previous Contracts: `docs/design/gomate-buddy-discovery-contract-v1.md`, `docs/design/gomate-buddy-profile-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Confirm V1: `docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-confirm-v1.png` ($390 \times 844$)
  - Mobile Pending V1: `docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-v1.png` ($390 \times 844$)
  - Mobile Received V1: `docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-v1.png` ($390 \times 844$)
  - Mobile Accepted V1: `docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-v1.png` ($390 \times 844$)
  - Mobile Rejected V1: `docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-v1.png` ($390 \times 844$)
  - Desktop Requests V1: `docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-v1.png` ($1440 \times 900$)

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
   - Real-time GPS coordinates are **never exposed** in the Buddy ecosystem.
   - Account email, password hash, and emergency contacts are **never exposed**.
3. **Data Honesty & Anti-Fabrication:**
   - **No fake compatibility percentages**: Only factual, explainable overlap bullet points.
   - **Verification semantics**: `User.isVerified` means `"Tài khoản đã xác minh"` (account/email authentication), never `"Đã xác minh danh tính"`.
   - **No fake masked values**: Never render pseudo-private values like `09xx xxx xxx`.
4. **Information Architecture Parity (Canonical 5-Tab Root):**
   The application preserves the canonical 5 root tabs across devices (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [active], `An toàn`). Request management is reached contextually under Trip context.

---

## 2. Current vs Target Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence |
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
GOMATE BUDDY MUTUAL CONSENT STATE MACHINE
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
                                               [Push Notification]
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
                                        phone locked)          (Phone unlocked,
                                                                Trip sharing eligible)
============================================================
```

---

## 6. Send Request Surface (Confirmation Modal)

- **Entry Point:** Buddy Profile primary CTA button `"Gửi lời mời kết nối"`.
- **Anti-Accidental Invariant:** Tapping the CTA **must not** immediately trigger an API request. It opens a dedicated confirmation surface.
- **Component Anatomy (`buddy-mobile-request-confirm-v1.png`):**
  - Backdrop overlay: Dark translucent scrim (`rgba(15, 23, 42, 0.5)`).
  - Bottom sheet with rounded top corners ($20\text{px}$) and drag handle.
  - Title: `"Gửi lời mời kết nối?"`.
  - Context pill: `"Đồng hành cùng Lê Hoàng Nam · Chuyến đi: Đà Nẵng (15/10 – 18/10/2026) · 4 ngày"`.
  - Privacy note: `"🔒 Bảo mật thông tin: Người này chỉ được kết nối với bạn sau khi họ chấp nhận lời mời. Số điện thoại và lịch trình chi tiết của bạn sẽ không bị chia sẻ trước khi có sự đồng ý của cả hai."`.
  - Actions:
    - Left: `[Hủy]` (Neutral outline `#CBD5E1`). Dismisses sheet without mutation.
    - Right: `[Gửi lời mời]` (Pine Teal `#0F766E`, icon send). Triggers request creation.

---

## 7. Pending Sent State

- **Visual Reference:** `buddy-mobile-request-pending-v1.png`.
- **Sender View:**
  - Amber banner at top: `"Đã gửi lời mời kết nối · Đang chờ Lê Hoàng Nam phản hồi. Bạn sẽ nhận được thông báo khi lời mời được chấp nhận."`.
  - Primary button state: Disabled / Pending style (`#F0FDFA`, border `#99F6E4`, text `#0F766E`):
    `⏱ Đã gửi lời mời · Đang chờ phản hồi`
  - Secondary action: `"Hủy lời mời kết nối (Mục tiêu thiết kế)"`.
- **Privacy Enforcement:**
  - Phone number **remains 100% locked** (`Chỉ hiển thị sau khi kết nối`).
  - Hourly itinerary **remains 100% locked** (`Chỉ chia sẻ khi là bạn đồng hành`).
  - Real-time GPS **never exposed**.

---

## 8. Incoming Request Inbox (Pending Received)

- **Visual Reference:** `buddy-mobile-request-received-v1.png`, `buddy-desktop-requests-v1.png`.
- **Receiver View:**
  - Screen title: `"Lời mời đồng hành"`.
  - Request Card:
    - Sender Avatar, Display Name, `"Đã xác minh"` badge, Age Band (`25–29 tuổi`), Nationality (`Việt Nam`).
    - Timestamp: `"Gửi lúc 09:15 hôm nay"`.
    - Context pill: `"Muốn kết nối cho chuyến đi Đà Nẵng (15–18/10)"`.
    - Explainable reasons callout box (`✓ Trùng 4 ngày du lịch...`).
    - Privacy disclosure: `"🔒 Chấp nhận sẽ mở số điện thoại của cả hai để tiện liên lạc chuẩn bị chuyến đi."`.
  - Action Buttons:
    - Left: `[Từ chối]` (Slate `#F1F5F9`, border `#CBD5E1`, text `#64748B`, height 42px).
    - Right: `[Chấp nhận kết nối]` (Pine Teal `#0F766E`, text `#FFFFFF`, height 42px).
  - **Dark Pattern Prevention:** Both buttons have balanced visual weight; reject is fully accessible and neutral.

---

## 9. Accept Contract & Post-Match Capabilities

- **State Transition:** `Match.status` transitions from `PENDING` to `ACCEPTED`.
- **Visual Reference:** `buddy-mobile-match-accepted-v1.png`.
- **Post-Match UI:**
  - Success banner: `✓ Hai bạn đã kết nối bạn đồng hành! Cả hai đã đồng ý kết nối cho chuyến đi Đà Nẵng 15–18/10.`
  - **Phone Number Unlocked:** Renders phone number (e.g. `0912 345 678`) with direct `[Gọi / Zalo]` action.
  - **Detailed Itinerary Remains Protected:** Displays informative lock card: `"Lịch trình chi tiết theo giờ: Lịch trình chi tiết vẫn được bảo vệ. Hãy mời bạn đồng hành vào chuyến đi để cùng xem và đồng bộ lịch trình."`.
  - Bottom action bar:
    - Secondary: `[Nhắn tin]` (Design Target / Future).
    - Primary: `[Mời vào chuyến đi]` (`#0F766E`).

---

## 10. Reject Contract & Cooldown Rule

- **State Transition:** `Match.status` transitions from `PENDING` to `REJECTED`.
- **Visual Reference:** `buddy-mobile-request-rejected-v1.png`.
- **Core Principles:**
  - **Reject $\neq$ Block:** Rejecting a request does not block the user, flag their account, or report them.
  - **No Shaming:** Copy is neutral and supportive: `"Bạn đã từ chối lời mời. Lời mời kết nối từ Lê Hoàng Nam đã được từ chối an toàn."`.
  - **Reassurance:** `"🔒 Bảo mật & Tôn trọng: Đối phương sẽ không nhận được thông báo mang tính tiêu cực và người này không bị chặn. Thông tin cá nhân của bạn vẫn được giữ kín tuyệt đối."`.
  - Primary recovery action: `[Tiếp tục tìm bạn đồng hành khác]`.
- **Cooldown Rule (Design Target):**
  - Once a request is rejected, the sender cannot send another request to the same receiver for **30 days**.
  - Current status: **DESIGN TARGET / REQUIRES BACKEND QUERY RULE** (Requires backend query filter checking `createdAt` or new `updatedAt` field).

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

| Data Field | Pre-Match | Pending Sent / Received | Accepted (Matched) | Explicit Share Required? | Never Share? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Display Name & Avatar** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Age Band (`25–29`)** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Nationality & Languages**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Bio Snippet** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Travel Style & Interests**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Trip Destination & Overlap**| **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Compatibility Reasons** | **PUBLIC** | **PUBLIC** | **PUBLIC** | NO | NO |
| **Personal Phone Number** | 🔒 LOCKED | 🔒 LOCKED | 🔓 **UNLOCKED** | NO (Unlocked on Match) | NO |
| **Detailed Hourly Itinerary**| 🔒 LOCKED | 🔒 LOCKED | 🔒 **LOCKED** | **YES (Trip Member Invite)**| NO |
| **Real-Time Live GPS** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Never Exposed)**|
| **Account Email** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Never Exposed)**|
| **Password Hash** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Never Exposed)**|
| **Emergency Contacts (SOS)**| ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Never Exposed)**|
| **Internal UUIDs** | ⛔ HIDDEN | ⛔ HIDDEN | ⛔ **HIDDEN** | NO | **YES (Never Exposed)**|

---

## 13. Trip Sharing Boundary

- **Existing API:** `POST /trips/:id/members` allows adding members by email.
- **Strict Boundary:** An `ACCEPTED` match connection **does NOT automatically make either user a member of the other's trip**.
- **Correct Workflow:**
  $$\text{MATCHED} \longrightarrow \text{User taps "Mời vào chuyến đi"} \longrightarrow \text{Trip Invite Dialog} \longrightarrow \text{TripMember}$$
- This preserves the owner's control over itinerary editing and cost splitting.

---

## 14. Chat & Notification Boundaries

### 14.1. In-App Chat Boundary
- Database models `Group` and `Message` exist, but **no WebSocket or real-time chat service** currently exists in NestJS.
- Action button `"Nhắn tin"` on the Matched screen is classified:
  $$\textbf{DESIGN TARGET / FUTURE (Phase UI-3)}$$

### 14.2. Notification Boundary
- There is currently **zero push notification code** (Firebase Cloud Messaging or APNs) in the backend repository.
- Events requiring notifications (`REQUEST_RECEIVED`, `REQUEST_ACCEPTED`, `REQUEST_REJECTED`) are classified:
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
