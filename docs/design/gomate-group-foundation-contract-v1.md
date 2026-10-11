# GoMate Group Foundation, Membership, Role & Lifecycle Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION  
**Task:** TASK 08.2.3.10 — GOMATE GROUP FOUNDATION: MEMBERSHIP, ROLE & LIFECYCLE CONTRACT V1  
**Module:** Travel Companion Group Foundation (`/groups`, `/trips/:id/group`)  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$), Tablet ($768 \times 1024$)  
**Source of Truth:** 
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Group`, `model GroupMember`, `model Trip`, `model TripMember`, `model Match`, `model Message`)
- Trip Contract: `docs/design/gomate-trip-user-flow-spec-v1.md`, `docs/design/gomate-trip-visual-spec-v1.md`
- Buddy Contracts: `docs/design/gomate-buddy-discovery-contract-v1.md`, `docs/design/gomate-buddy-profile-contract-v1.md`, `docs/design/gomate-buddy-match-consent-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Master Detail R1: [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png) ($390 \times 844$)
  - Desktop Master Detail R1: [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png) ($1440 \times 900$)
  - Baseline V1 Visuals (Pre-Correction): [`group-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-v1.png), [`group-desktop-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-v1.png)

---

## 1. Product Role & Architectural Vision

The **Group Foundation** establishes the collaborative and communication nexus for travel companions in **GoMate**. 
Unlike generic social media groups (which prioritize viral content, likes, follows, and public browsing), a GoMate Group is a **private, trip-oriented coordination space** designed for real-world travel logistics.

It acts as the anchor container for three downstream modular capabilities:
1. **Group Chat (TASK 08.2.3.11):** Real-time text and media coordination.
2. **Shared Itinerary (TASK 08.2.3.12):** Synchronized day-by-day activity tracking.
3. **Shared Expense (TASK 08.2.3.13):** Cost splitting and shared bill balancing.

---

## 2. Current vs Target Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Group Model** | Missing | Missing | `model Group` | Section 3 | **PARTIAL (DB Only)** | Model exists in schema; no backend controller. |
| **GroupMember Model** | Missing | Missing | `model GroupMember` | Section 4 | **PARTIAL (DB Only)** | Model exists; plain string role `"admin" / "member"`. |
| **Group ↔ Trip Link** | Missing | Missing | `Group.tripId` (unlinked) | Section 5 | **PARTIAL (DB Only) / GAP** | Loose UUID column; no formal `@relation` to `Trip`. Trip 1 ↔ 0..1 Group is a **LOCKED V1 PRODUCT RULE** (not DB-enforced). |
| **Member Capacity** | Missing | Missing | **MISSING FROM DB** | Section 3, 21 | **SCHEMA GAP / UNCONSTRAINED** | Schema lacks `maxMembers`. UI renders plain member count `(3)`, no `/5` denominator. |
| **Create Group** | Missing | Missing | `model Group` | Section 7 | **DESIGN TARGET** | 0 endpoints in NestJS; Trip Owner eligibility rule locked. |
| **Join / Accept Group** | Missing | Missing | `GroupMember` | Section 8 | **DESIGN TARGET** | Requires explicit consent; auto-enrollment forbidden. |
| **Invite Member** | Missing | Missing | Missing Endpoint | Section 11 | **DESIGN TARGET** | Cannot reuse email API; requires `TripMember` prerequisite. |
| **Leave Group** | Missing | Missing | Missing Endpoint | Section 12 | **DESIGN TARGET** | Member leaves freely; Owner transfer rule locked. Message retention is DB-supported; anonymous display is DESIGN TARGET. |
| **Remove Member** | Missing | Missing | Missing Endpoint | Section 13 | **DESIGN TARGET** | Admin/Owner privilege; does NOT unmatch or strip Trip. |
| **Owner Role** | Missing | Missing | **SCHEMA GAP** | Section 9 | **SCHEMA GAP / DERIVED TARGET**| Schema lacks `creatorId` / `owner` enum; derived from linked `Trip.userId` by logic. |
| **Admin Role** | Missing | Missing | `role = "admin"` | Section 9 | **PARTIAL (DB String) / TARGET**| Comment has `"admin"`; enforcement logic missing. No Postgres enum exists. |
| **Delete Group** | Missing | Missing | `Cascade` on GroupMember| Section 14 | **DESIGN TARGET** | Schema cascades members & messages; Owner-only action. |
| **Group Chat** | Missing | Missing | `model Message` | TASK 08.2.3.11 | **PARTIAL (DB Only) / FUTURE** | DB tables exist; runtime WebSocket missing. UI displays clean "Sắp có". |
| **Shared Itinerary** | Missing | Missing | `model Itinerary` (Trip) | TASK 08.2.3.12 | **FUTURE** | Scoped to `TripMember` role, not raw GroupMember. UI displays clean "Sắp có". |
| **Shared Expense** | Missing | Missing | **MISSING FROM DB** | TASK 08.2.3.13 | **SCHEMA GAP / FUTURE** | Zero expense models currently in `schema.prisma`. UI displays clean "Sắp có". |
| **Notifications** | Missing | Missing | Missing Service | Section 19 | **DESIGN TARGET** | Zero FCM/APNs in repo; no notification overclaims. |
| **User Block / Report**| Missing | Missing | **MISSING FROM DB** | Section 20 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`/`UserReport`. |

---

## 3. Group Schema Audit

### 3.1. Exact Prisma Schema (`apps/backend/prisma/schema.prisma`)
```prisma
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
```

### 3.2. Detailed Field Analysis Matrix

| Field | Type | Nullable | Relation | Current Purpose | Schema Gap & Limitation |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `id` | `String @db.Uuid` | NO | Primary Key | Unique group identifier | None (Standard UUID v4). |
| `name` | `String` | NO | None | Group display title | None. |
| `description` | `String?` | YES | None | Optional group objective | None. |
| `tripId` | `String? @db.Uuid` | YES | **NO RELATION** | Stores associated Trip UUID | **CRITICAL GAP:** Not defined as a foreign key `@relation` to `Trip`. `Trip` model has no `groups Group[]`. Database does not enforce relational integrity. |
| `createdAt` | `DateTime` | NO | None | Timestamp of creation | None. |
| `creatorId` / `ownerId` | — | — | — | — | **CRITICAL GAP:** `Group` has no creator or owner column! Impossible to determine group ownership from `Group` table alone. |
| `updatedAt` | — | — | — | — | **GAP:** Missing `@updatedAt`. Cannot track last modified time. |
| `status` | — | — | — | — | **GAP:** Missing status enum (`ACTIVE`, `ARCHIVED`, `CLOSED`). |
| `privacy` | — | — | — | — | **GAP:** Missing privacy flag (`PRIVATE`, `PUBLIC`). Defaults to private by business rule. |
| `maxMembers` | — | — | — | — | **GAP:** Missing membership capacity ceiling. Database schema contains NO capacity limit. Displaying fake denominators (e.g. `(3/5)`) is strictly forbidden; UI must render plain member count (e.g. `(3)`). |

---

## 4. GroupMember Model Audit

### 4.1. Exact Prisma Schema
```prisma
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

### 4.2. Detailed Field Analysis Matrix

| Field | Type | Nullable | Relation | Current Purpose | Schema Gap & Limitation |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `id` | `String @db.Uuid` | NO | Primary Key | Unique membership record | None. |
| `groupId` | `String @db.Uuid` | NO | `Group` (onDelete: Cascade) | Foreign key to Group | Group deletion cleanly cascades to members. |
| `userId` | `String @db.Uuid` | NO | `User` (No onDelete specified) | Foreign key to User | Defaults to RESTRICT in Postgres; User deletion fails if memberships exist. |
| `role` | `String` | NO | Plain String (`@default("member")`) | Stores member role | **GAP:** Plain String, not a Postgres enum. Comment suggests `"admin", "member"`, lacking explicit `"owner"`. There is NO database `OWNER` enum in Postgres. |
| `joinedAt` / `createdAt`| — | — | — | — | **GAP:** Missing timestamp. Cannot record when a user joined. |
| `status` | — | — | — | — | **GAP:** Missing membership lifecycle status (`INVITED`, `ACTIVE`, `MUTED`). |
| `invitedBy` | — | — | — | — | **GAP:** Missing inviter audit trail. |

---

## 5. Group ↔ Trip Relationship

### 5.1. Current Database Reality
- `Group.tripId` is an unconstrained, nullable UUID column.
- There is **no Prisma foreign key relation**: `trip Trip? @relation(fields: [tripId], references: [id])` does **not** exist in `schema.prisma`.
- `Trip` model has **zero references** to `Group` (no `groups Group[]`).
- Therefore, the database currently treats `Group` and `Trip` as loosely coupled entities.

### 5.2. Target Product & Business Rule
1. **Canonical Association:** In GoMate V1, every companion group is fundamentally anchored to a specific travel context (`Trip`).
2. **Cardinality Contract:**
   $$\textbf{Trip } 1 \longleftrightarrow 0..1 \textbf{ Primary Companion Group}$$
   - A Trip may have at most **one active primary Companion Group** for coordination.
   - Classification: **`LOCKED V1 PRODUCT RULE`**, NOT a database-enforced constraint. The current database schema does not have a `unique` constraint on `Group.tripId`. Backend application logic must enforce single active primary group per trip upon creation.
   - (Multi-subgroup creation per trip is deferred to future enterprise/tour phases; marked `PRODUCT DECISION REQUIRED` for future extensions).
3. **Standalone Groups (tripId = null):**
   - While `tripId` is nullable in schema, GoMate V1 UI **does not support creating orphan or unassociated groups**. Group creation is only accessible from within an existing Trip.

---

## 6. MATCH $\neq$ TRIP MEMBER $\neq$ GROUP MEMBER Invariant

To preserve data privacy, operational clarity, and consent integrity, the system strictly isolates the three relationship layers:

```
========================================================================
GOMATE RELATIONSHIP SEPARATION INVARIANT
========================================================================

    [MATCH] (Social Peer)
       │
       ╘══≠══> [TRIP MEMBER] (Workspace Collaborator)
                  │
                  ╘══≠══> [GROUP MEMBER] (Communication Space)

    MATCHED       ≠ TRIP_MEMBER  (No automatic itinerary edit rights)
    TRIP_MEMBER   ≠ GROUP_MEMBER (No automatic group chat enrollment)
    GROUP_MEMBER  ≠ TRIP_MEMBER  (No automatic trip management rights)

CANONICAL ONBOARDING FLOW:
    [MATCHED]
       │
       ▼ (Explicit Trip Invite)
    [TRIP MEMBER] (Trip workspace collaborator)
       │
       ▼ (Group Invite)
    [PENDING INVITE]
       │
       ▼ (Explicit Consent / Accept)
    [GROUP MEMBER] (Communication space participant)

* Locked Rule: An Accepted Match who is NOT a TripMember is NOT YET ELIGIBLE
  to be invited into a Trip-bound Companion Group.
========================================================================
```

### 6.1. Comprehensive Relationship Matrix

| Dimension | MATCH (`model Match`) | TRIP MEMBER (`model TripMember`) | GROUP MEMBER (`model GroupMember`) |
| :--- | :--- | :--- | :--- |
| **What It Represents** | Binary peer-to-peer social connection between two individual travelers. | Formal co-traveler / workspace collaborator on a specific `Trip`. | Participant in the shared communication and coordination room. |
| **Who Creates It** | Initiated by User A $\rightarrow$ Explicitly accepted by User B. | Added by Trip Owner (currently via email; target: via safe adapter). | Invited by Group Owner/Admin $\rightarrow$ Explicitly accepted by user. |
| **Permissions Granted** | View unlocked public profile; view mutual phone number. | View detailed trip schedule; edit itinerary items (if permitted); view trip budget. | Send messages in group chat; view member list; receive group coordination updates. |
| **Permissions NOT Granted** | **No** Trip editing; **no** direct group entry without joining Trip; **no** GPS sharing. | **No** automatic phone unlock (unless Matched); **no** group chat bypass without invite. | **No** Trip ownership; **no** authority to delete trip or modify core trip metadata. |
| **Data Unlocked** | Personal phone number (mutual consent). | Minute-by-minute itinerary activities; destination context; budget estimates. | Group chat message thread; group member nicknames; shared group notes. |
| **How It Ends** | Unmatch (or Block if implemented). | Removed by Trip Owner or user leaves trip. | Leaves group voluntarily or removed by Group Admin/Owner. |

---

## 7. Group Creation Eligibility

- **Current API Reality:** **0 endpoints exist** in NestJS backend (`POST /groups` is missing).
- **Target Eligibility Rule:**
  1. Only the **Trip Owner** (`Trip.userId === CurrentUser.id`) is authorized to create the primary Companion Group for a trip.
  2. A Trip Member or an Accepted Buddy **cannot unilaterally create** a group bound to someone else's trip without explicit owner initiation.
  3. A user can only create a group if `Trip.deletedAt === null` and no active group is already bound to that `tripId`.
- **Classification:** `DESIGN TARGET` (API and UI form to be implemented).

---

## 8. Member Entry Contract

### 8.1. Explicit Consent vs Auto-Enrollment
- **Architecture Stance:** **Explicit Consent Required.**
- In GoMate, being added as a `TripMember` **does NOT automatically force** the user into a social group chat. Unsolicited auto-enrollment into chat spaces violates user autonomy and privacy.
- **Entry Protocol:**
  $$\text{TripMember} \xrightarrow{\text{Owner sends Group Invite}} \text{Pending Invite} \xrightarrow{\text{Candidate taps [Tham gia]}} \text{GroupMember}$$

---

## 9. Role & Permission Matrix

### 9.1. Role Hierarchy & Honest Semantics
Because `Group` lacks `creatorId` / `ownerId` columns and `GroupMember.role` contains only plain strings (`"admin"`, `"member"`), the role structure is classified as follows:
1. **TRƯỞNG NHÓM / CHỦ CHUYẾN ĐI (`DESIGN TARGET — DERIVED FROM TRIP OWNER`):**
   - Derived directly from `Trip.userId` of the linked trip by application logic.
   - **NOT** a database-persisted enum or column on `Group`.
   - UI Display Standard: `"Bạn"`, `"Chủ chuyến đi"`, badge `"Trưởng nhóm"`. Avoid confusing `"Bạn (Admin)"` + `"Trưởng nhóm (Owner)"`.
2. **ADMIN (`Quản trị viên` — `PARTIAL DB STRING / TARGET`):**
   - Assigned member with operational moderation privileges (invite members, moderate chat messages).
   - In DB, `role` is plain string `"admin"` (no enum constraint).
3. **MEMBER (`Thành viên` — `CURRENT DB STRING`):**
   - Standard participant in the communication space (`role = "member"`). Database default.

### 9.2. Permission Enforcement Matrix

| Action | OWNER (Trip Owner) | ADMIN | MEMBER | Capability Status | Enforcement Layer |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **View Group & Members** | YES | YES | YES | **DESIGN TARGET** | GroupMember Authorization Guard |
| **Edit Group Name / Description** | YES | YES | NO | **DESIGN TARGET** | Backend API Guard (`role in [owner, admin]`) |
| **Invite New Member** | YES | YES | NO | **DESIGN TARGET** | Backend API Guard (`role in [owner, admin]`) |
| **Remove Member** | YES | YES (Members only) | NO | **DESIGN TARGET** | Backend API Guard (Admin cannot remove Owner) |
| **Promote Member to Admin** | YES | NO | NO | **DESIGN TARGET** | Owner-only privilege |
| **Demote Admin to Member** | YES | NO | NO | **DESIGN TARGET** | Owner-only privilege |
| **Leave Group** | YES (With Transfer) | YES | YES | **DESIGN TARGET** | Section 12 lifecycle rule |
| **Delete Group (Disband)** | YES | NO | NO | **DESIGN TARGET** | Owner-only destructive action |
| **View Linked Trip Detail** | YES | Conditioned | Conditioned | **CURRENT (Trip)** | Requires `TripMember` record on `Trip` |
| **Edit Shared Itinerary** | YES | Conditioned | Conditioned | **TASK 08.2.3.12** | Requires `TripMember` role (NOT Group role) |
| **Send Message in Chat** | YES | YES | YES | **TASK 08.2.3.11** | Group Chat WebSocket Gateway |

---

## 10. Invite Contract & Privacy Isolation

- **Current API Gap:** Zero group invite endpoints exist.
- **Strict Privacy Isolation:**
  - Group invitations **MUST NOT use or require `User.email`**.
  - `User.email` is **Tier 4 — SYSTEM PRIVATE / NEVER EXPOSED**.
  - The Group invite dialog must resolve candidates via internal `userId` selected from eligible connected pools (e.g. Existing Trip Members, Accepted Buddies).
- **Endpoint Target Specification:**
  ```http
  POST /groups/:groupId/invites
  Authorization: Bearer <token>
  Content-Type: application/json

  {
    "userId": "4fa85f64-5717-4562-b3fc-2c963f66afa7"
  }
  ```

---

## 11. Invite Eligibility

| User Relation to Group / Trip | Can Invite to Group? | Current Implementation | Target Specification | Rationale & Privacy Boundary |
| :--- | :---: | :---: | :---: | :--- |
| **Unrelated User (Stranger)** | NO | Blocked | **NOT ELIGIBLE** | Must have prior connection and join Trip first. |
| **Pending Match Candidate** | NO | Blocked | **NOT ELIGIBLE** | Mutual consent not yet finalized. |
| **Accepted Match only (Buddy)**| NO | Missing API | **NOT YET ELIGIBLE** | Must join Trip first via explicit Trip invite (`Match -> TripMember -> GroupMember`). |
| **TripMember (Not in Group)** | **YES** | Missing API | **ELIGIBLE FOR GROUP INVITE** | Already collaborating on the trip schedule. |
| **Existing GroupMember** | NO | DB Unique constraint | **ALREADY MEMBER** | `@@unique([groupId, userId])` prevents duplicate. |
| **Blocked User** | NO | Missing Model | **UNSAFE / BLOCKED DEPENDENCY** | Safety module dependency. |

---

## 12. Leave Group Lifecycle

- **Standard Member Leave:**
  - Any regular member or admin can leave the group at any time via `POST /groups/:groupId/leave`.
  - Triggering leave prompts a confirmation modal: *"Bạn có chắc chắn muốn rời nhóm đồng hành này?"*.
  - **Message History & Anonymization Reality:**
    - In `model Message`, `userId` is a mandatory foreign key relation to `User.id`.
    - PostgreSQL database does **NOT** automatically anonymize messages upon member leave.
    - **Message retention is DB-supported** (existing messages remain linked to `userId`).
    - Displaying `[Thành viên đã rời nhóm]` or masked names is a **`DESIGN TARGET`** client/presentation rendering rule, not a database trigger or column behavior.
- **Owner Leave Edge Case (Product Rule Locked):**
  - **Rule:** The Group Owner (Trip Owner) **cannot abandon the group as an orphan**.
  - If the Owner wishes to leave, they must choose one of two explicit options:
    1. **Transfer Ownership:** Designate an existing member/admin as the new Owner.
    2. **Disband Group:** Fully delete the group for all participants.

---

## 13. Remove Member Lifecycle

- **Authority:** Only Owner and Admins can remove members. (Admins cannot remove other Admins or the Owner).
- **Separation Invariant:**
  $$\text{Remove from Group} \centernot\implies \text{Remove from TripMember} \centernot\implies \text{Unmatch}$$
  Removing a participant from the Group Chat space removes their access to internal messages, but **does NOT alter their TripMember status or unmatch their Buddy connection** unless separate explicit actions are confirmed.

---

## 14. Delete Group Lifecycle & Cascade Audit

- **Authority:** Only the Group Owner can delete (disband) the group.
- **Prisma Schema Cascade Verification:**
  - `GroupMember`: `group Group @relation(fields: [groupId], references: [id], onDelete: Cascade)` $\rightarrow$ **Cleanly cascade deletes**.
  - `Message`: `group Group @relation(fields: [groupId], references: [id], onDelete: Cascade)` $\rightarrow$ **Cleanly cascade deletes**.
  - `Trip`: `Group` has no formal relation to `Trip` $\rightarrow$ **Trip and its Itinerary remain completely unaffected**.

---

## 15. User Account Deletion & Relational Gaps

- **Current DB Reality:**
  - `GroupMember.user`: `user User @relation(fields: [userId], references: [id])` has **NO `onDelete` specified**.
  - PostgreSQL defaults to `RESTRICT / NO ACTION`.
  - **Consequence:** If a User account is deleted directly from the database, PostgreSQL will **throw a foreign key violation error** if the user still belongs to any `GroupMember` or has sent any `Message`.
- **Target Specification:** In future migrations, `GroupMember` and `Message` should implement soft-delete (`deletedAt`) or explicit application-level cleanup before user deletion.

---

## 16. Privacy & Sensitive Field Boundaries

Group is a shared space, making data leakage protection paramount:
1. **Account Email:** Strictly Tier 4 — NEVER rendered anywhere in group headers, member cards, or tooltips.
2. **Phone Number:** Group membership **does NOT reveal phone numbers**. A member's phone number is only visible if the viewing user has an independent `MatchStatus === ACCEPTED` relationship with that member.
3. **Real-Time GPS:** Việc tham gia nhóm không tự động chia sẻ vị trí thời gian thực. Mọi tính năng chia sẻ vị trí trong tương lai phải yêu cầu hành động và sự đồng ý rõ ràng của người dùng.
4. **Emergency / Safety Contacts:** Strictly private to the individual traveler; never disclosed to group peers.

---

## 17. Trip Data Access Boundary

- **Principle of Least Privilege:**
  $$\text{GroupMember} \centernot\implies \text{Trip Edit Permission}$$
- Being in the group chat does **not** grant rights to create, reorder, or delete itinerary items in the Trip module.
- Itinerary modification authority is strictly governed by `model TripMember` (`role: "owner"` vs `"member"`).

---

## 18. Downstream Module Boundaries

### 18.1. Group Chat Boundary (TASK 08.2.3.11)
- The database contains `model Message`, but **runtime WebSocket / Chat gateway is missing**.
- **Production UI Honesty:** The user-facing mockup renders a clean row `"Trò chuyện nhóm"` with a neutral `"Sắp có"` badge. Internal technical labels (`TASK 08.2.3.11`, `Chờ WebSocket`) are strictly restricted to engineering audit documentation.
- No interactive chat stream or fake messages are rendered in this foundation task.

### 18.2. Shared Itinerary Boundary (TASK 08.2.3.12)
- Itinerary activities belong to `model Itinerary` and `model ItineraryItem`.
- The user-facing mockup renders `"Lịch trình chung"` with a neutral `"Sắp có"` badge, linking to the forthcoming collaborative itinerary viewer.

### 18.3. Shared Expense Boundary (TASK 08.2.3.13)
- The database currently has **zero expense models** (`model Expense` is missing).
- The user-facing mockup renders `"Chi tiêu chuyến đi"` with a neutral `"Sắp có"` badge. Internal developer labels (`CHƯA CÓ DB`) are never exposed to end users.

---

## 19. Notification Boundary

- Push notification service (FCM/APNs) is absent.
- The Group module does **not promise instant push notifications** (e.g. *"Bạn sẽ nhận thông báo khi có tin nhắn mới"*).
- Member updates rely on pull/inbox refresh until notification infrastructure is implemented.

---

## 20. Safety & Moderation Boundary

- User blocking (`model UserBlock`) and user reporting (`model UserReport`) are missing from the schema.
- Group moderation controls currently do not show functional Block/Report actions, preventing runtime overclaims (`UNSAFE / BLOCKED`).

---

## 21. Multi-Platform Specifications

- **Mobile Viewport ($390 \times 844$):** Full single-column layout with status bar, hero card, trip context pill, 3-member list `Thành viên nhóm (3)` with verification and role badges (`Trưởng nhóm`, `Thành viên`), downstream module entry rows with clean `"Sắp có"` badges, leave group action, and canonical 5-tab navigation. Zero browser scrollbars. Master visual: [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png).
- **Desktop Viewport ($1440 \times 900$):** 3-column workstation layout:
  - Left ($360\text{px}$): Group identity, linked trip metadata, scoped privacy notice.
  - Center ($640\text{px}$): Member management list `Danh sách thành viên (3)`, verified badges, invite button, role permission summary.
  - Right ($380\text{px}$): Downstream modules (`"Sắp có"`) and Disband group danger zone. Zero scrollbars. Master visual: [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png).

---

## 22. Accessibility & Vietnamese-First Standards

- Touch targets $\ge 44 \times 44\text{ dp}$.
- Canonical Vietnamese terminology:
  - `"Nhóm đồng hành"` (Group)
  - `"Trưởng nhóm (Chủ chuyến đi)"` (Owner)
  - `"Quản trị viên"` (Admin)
  - `"Thành viên nhóm"` (Member)
  - `"Chuyến đi liên kết"` (Linked Trip)
  - `"Rời khỏi nhóm đồng hành"` (Leave Group)
  - `"Giải tán nhóm"` (Disband Group)
  - `"Tài khoản đã xác minh"` (Verified Account)
