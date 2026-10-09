# GoMate Group Foundation — Architecture & Capability Audit (TASK 08.2.3.10)

**Status:** APPROVED ARCHITECTURAL AUDIT & FOUNDATION SPECIFICATION  
**Task:** TASK 08.2.3.10 — GOMATE GROUP FOUNDATION: MEMBERSHIP, ROLE & LIFECYCLE CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.10 executes an in-depth capability audit and establishes the foundational business, membership, and lifecycle contracts for **GoMate Group** (`Nhóm đồng hành chuyến đi`).

### Primary Audit Verdict:
1. **Database Reality:**
   - `model Group` exists in `apps/backend/prisma/schema.prisma` with fields `id`, `name`, `description`, `tripId`, `createdAt`.
   - `model GroupMember` exists with fields `id`, `groupId`, `userId`, `role` (plain String).
   - `model Message` exists with fields `id`, `groupId`, `userId`, `content`, `createdAt`.
2. **Critical Schema Limitations Discovered:**
   - **Missing Ownership Field:** `model Group` has **no `creatorId` or `ownerId` column**! Ownership must currently be deduced from business logic linking back to `Trip.userId`.
   - **Unlinked Group ↔ Trip Relation:** `Group.tripId` is an unconstrained UUID column with **no `@relation` to `Trip`**. `Trip` model has no `groups Group[]`.
   - **Missing Timestamps & Statuses:** `GroupMember` has no `joinedAt` or `createdAt`. `Group` has no `updatedAt` or `status` enum (`ACTIVE`, `ARCHIVED`, `CLOSED`).
   - **Role Enum Gap:** `GroupMember.role` is a plain `String` with comment `"admin", "member"`, lacking a Postgres enum and lacking explicit `"owner"`.
3. **Backend & Mobile Code Reality:**
   - **0 endpoints exist** for Group or GroupMember in NestJS backend (`apps/backend/src/modules/` has no `groups` or `chat` module).
   - **0 screens, widgets, or blocs exist** in Flutter client (`apps/mobile/lib/features/` has no `groups` feature).
   - **Runtime Chat / WebSocket is missing** (Chat = `PARTIAL DB / FUTURE`).
   - **Shared Expense is completely missing** from database (`model Expense` does not exist).
4. **Relationship Isolation Locked:**
   $$\text{MATCH} \centernot\implies \text{TRIP\_MEMBER} \centernot\implies \text{GROUP\_MEMBER}$$
   Group membership does not unlock phone numbers, does not grant Trip editing permissions, and does not bypass mutual consent.

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
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

model Message {
  id        String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  groupId   String   @map("group_id") @db.Uuid
  userId    String   @map("user_id") @db.Uuid
  content   String
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz

  group Group @relation(fields: [groupId], references: [id], onDelete: Cascade)
  user  User  @relation(fields: [userId], references: [id])

  @@map("messages")
}
```

### 2.2. Backend Modules Audit (`apps/backend/src/modules/`)
- Existing modules: `ai-proxy`, `auth`, `destinations`, `health`, `places`, `reviews`, `trips`, `users`, `videos`.
- Scanned for: `groups`, `group-members`, `chat`, `messages`, `expenses`.
- Result: **0 Group/Chat controllers exist**. `AppModule` contains no group provider.

### 2.3. Flutter Client Audit (`apps/mobile/lib/`)
- Existing features: `ai_chat`, `auth`, `home`, `location`, `map`, `places`, `trips`.
- `app_router.dart`: 0 routes exist for `/groups` or `/trips/:id/group`.

---

## 3. Schema Gap & Model Analysis Matrix

| Model | Field / Feature | Schema Status | Architectural Gap & Risk | Contract Recommendation |
| :--- | :--- | :---: | :--- | :--- |
| `Group` | `creatorId` / `ownerId` | **MISSING** | Group has no record of who created it. Cannot enforce Owner permissions at DB level. | Add `creatorId String @db.Uuid` or map via `Trip.userId`. |
| `Group` | `tripId` Relation | **UNCONSTRAINED** | No foreign key `@relation` to `Trip`. Orphan groups can exist without database constraint. | Add `trip Trip? @relation(fields: [tripId], references: [id])`. |
| `Group` | `status` | **MISSING** | No status tracking (`ACTIVE`, `ARCHIVED`, `CLOSED`). | Add `GroupStatus` enum in future migration. |
| `Group` | `updatedAt` | **MISSING** | Missing modification timestamp. | Add `updatedAt DateTime @updatedAt`. |
| `GroupMember` | `role` | **STRING ONLY** | Plain `String` instead of enum; lacks `"owner"`. | Enforce 3-tier hierarchy (`owner`, `admin`, `member`) in logic. |
| `GroupMember` | `joinedAt` | **MISSING** | Cannot audit when a user joined. | Add `joinedAt DateTime @default(now())`. |
| `GroupMember` | `status` | **MISSING** | No invite lifecycle (`INVITED`, `ACTIVE`, `LEFT`). | Add `GroupMemberStatus` enum. |
| `User` Deletion | Relation Cascade | **RESTRICT** | `GroupMember.user` defaults to RESTRICT. Deleting user account fails if in groups. | Implement soft-delete or cascade cleanup. |

---

## 4. Relationship Isolation Audit

```
========================================================================
RELATIONSHIP COMPARISON & ONBOARDING MATRIX
========================================================================

DIMENSION           MATCH                    TRIP MEMBER              GROUP MEMBER
------------------------------------------------------------------------
Scope               Individual Peer-to-Peer  Trip Planning Workspace  Social & Chat Room
Prisma Model        model Match              model TripMember         model GroupMember
Permissions         View phone               Edit itinerary / budget  Send messages
Data Unlocked       Phone number             Hourly schedule          Chat thread
Email Visible?      NEVER (Tier 4)           NEVER to UI              NEVER (Tier 4)
GPS Visible?        NEVER in Buddy           NEVER                    NEVER (Not auto-shared)
Automatic Entry?    No (Mutual Consent)      No (Explicit Add)        No (Explicit Invite)
------------------------------------------------------------------------
CANONICAL ONBOARDING PREREQUISITE FLOW:
    [MATCHED] ──> [Explicit Trip Invite] ──> [TRIP MEMBER] ──> [Group Invite] ──> [GROUP MEMBER]
* Accepted Match alone is NOT YET ELIGIBLE to join a trip-bound Companion Group.
========================================================================
```

---

## 5. Comprehensive Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Group Model** | Missing | Missing | `model Group` | Contract Section 3 | **PARTIAL (DB Only)** | Model exists in schema; no backend controller. |
| **GroupMember Model** | Missing | Missing | `model GroupMember` | Contract Section 4 | **PARTIAL (DB Only)** | Model exists; plain string role `"admin" / "member"`. |
| **Group ↔ Trip Link** | Missing | Missing | `Group.tripId` (unlinked) | Contract Section 5 | **PARTIAL (DB Only) / GAP** | Loose UUID column; no formal `@relation` to `Trip`. Trip 1 ↔ 0..1 Group is a **LOCKED V1 PRODUCT RULE** (not DB-enforced). |
| **Member Capacity** | Missing | Missing | **MISSING FROM DB** | Contract Section 3, 21 | **SCHEMA GAP / UNCONSTRAINED** | Schema lacks `maxMembers`. UI renders plain member count `(3)`, no `/5` denominator. |
| **Create Group** | Missing | Missing | `model Group` | Contract Section 7 | **DESIGN TARGET** | 0 endpoints in NestJS; Trip Owner eligibility rule locked. |
| **Join / Accept Group** | Missing | Missing | `GroupMember` | Contract Section 8 | **DESIGN TARGET** | Requires explicit consent; auto-enrollment forbidden. |
| **Invite Member** | Missing | Missing | Missing Endpoint | Contract Section 11 | **DESIGN TARGET** | Cannot reuse email API; requires `TripMember` prerequisite. |
| **Leave Group** | Missing | Missing | Missing Endpoint | Contract Section 12 | **DESIGN TARGET** | Member leaves freely; Owner transfer rule locked. Message retention is DB-supported; anonymous display is DESIGN TARGET. |
| **Remove Member** | Missing | Missing | Missing Endpoint | Contract Section 13 | **DESIGN TARGET** | Admin/Owner privilege; does NOT unmatch or strip Trip. |
| **Owner Role** | Missing | Missing | **SCHEMA GAP** | Contract Section 9 | **SCHEMA GAP / DERIVED TARGET**| Schema lacks `creatorId` / `owner` enum; derived from linked `Trip.userId` by logic. |
| **Admin Role** | Missing | Missing | `role = "admin"` | Contract Section 9 | **PARTIAL (DB String) / TARGET**| Comment has `"admin"`; enforcement logic missing. No Postgres enum exists. |
| **Delete Group** | Missing | Missing | `Cascade` on GroupMember| Contract Section 14 | **DESIGN TARGET** | Schema cascades members & messages; Owner-only action. |
| **Group Chat** | Missing | Missing | `model Message` | TASK 08.2.3.11 | **PARTIAL (DB Only) / FUTURE** | DB tables exist; runtime WebSocket missing. UI displays clean "Sắp có". |
| **Shared Itinerary** | Missing | Missing | `model Itinerary` (Trip) | TASK 08.2.3.12 | **FUTURE** | Scoped to `TripMember` role, not raw GroupMember. UI displays clean "Sắp có". |
| **Shared Expense** | Missing | Missing | **MISSING FROM DB** | TASK 08.2.3.13 | **SCHEMA GAP / FUTURE** | Zero expense models currently in `schema.prisma`. UI displays clean "Sắp có". |
| **Notifications** | Missing | Missing | Missing Service | Contract Section 19 | **DESIGN TARGET** | Zero FCM/APNs in repo; no notification overclaims. |
| **User Block / Report**| Missing | Missing | **MISSING FROM DB** | Contract Section 20 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`/`UserReport`. |

---

## 6. Master Mockup Verification (R1 Refined Artifacts)

Both master mockups were updated and verified at `docs/audit/evidence/ui-08.2.3.10/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `"Nhóm đồng hành"`.<br>2. Group Hero card with avatar `ĐN`, title, description, and trip context pill (`Khám phá Đà Nẵng 4N3Đ`).<br>3. Member section labeled honestly as `Thành viên nhóm (3)` (fake `/5` removed).<br>4. Owner rendered as `"Bạn"`, `"Chủ chuyến đi"`, badge `"Trưởng nhóm"` (avoiding false DB enum claims).<br>5. Member 2 (Lê Hoàng Nam) verified as `"Bạn đồng hành · Thành viên chuyến đi"`.<br>6. Downstream modules cleanly displayed with neutral `"Sắp có"` badges (no developer task IDs or `"CHƯA CÓ DB"` leaked to UI).<br>7. Canonical 5 bottom tabs with `"Chuyến đi"` active. Zero scrollbars. | **PASS** |
| [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png) | Desktop | $1440 \times 900$ | 1. Top navigation with 5 canonical tabs (Chuyến đi active).<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành chuyến đi`.<br>3. Col 1 ($360\text{px}$): Group info, linked trip metadata, and safely scoped privacy notice: *"Việc tham gia nhóm không tự động chia sẻ vị trí thời gian thực."*<br>4. Col 2 ($640\text{px}$): Member management list `Danh sách thành viên (3)` without fake `/5`, verified badges, invite button, role permissions summary.<br>5. Col 3 ($380\text{px}$): Downstream modules (`"Sắp có"`) and Disband group danger zone. Zero scrollbars. | **PASS** |

*(Pre-correction V1 artifacts preserved for historical comparison: [`group-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-v1.png), [`group-desktop-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-v1.png).)*

*(Note on `group-mobile-create-v1.png`: In accordance with the prompt condition, group creation form mockup was omitted because `creatorId` and `Trip` relation schema gaps require database resolution before locking form mutations).*

---

## 7. Design Acceptance Gate (TASK 08.2.3.10-R1)

- [x] **Accepted Match alone cannot directly join Group:** Prerequisite locked (`Match -> TripMember -> GroupMember`).
- [x] **TripMember prerequisite locked:** Only TripMembers are eligible for Group invitation.
- [x] **GroupMember still requires explicit consent:** No automatic enrollment upon becoming TripMember.
- [x] **No fake 3/5 member capacity:** Header shows `Thành viên nhóm (3)` without `/5`.
- [x] **Owner semantics are derived-target only:** Derived from `Trip.userId`; no DB enum claimed.
- [x] **Owner not confused with Admin:** Labeled as `"Bạn"`, `"Chủ chuyến đi"`, badge `"Trưởng nhóm"`.
- [x] **Message anonymization not claimed as DB behavior:** Retention is DB-supported; anonymous display is client rendering rule.
- [x] **No TASK IDs shown as production copy:** Technical labels removed from mockup UI frames.
- [x] **No "CHƯA CÓ DB" shown to end users:** Clean neutral `"Sắp có"` badges used in UI.
- [x] **GPS wording scoped safely:** *"Việc tham gia nhóm không tự động chia sẻ vị trí thời gian thực. Mọi tính năng chia sẻ vị trí trong tương lai phải yêu cầu hành động và sự đồng ý rõ ràng của người dùng."*
- [x] **One-group-per-trip classified as V1 product rule:** Explicitly documented as locked product rule, not current DB constraint.
- [x] **Group mutation actions remain DESIGN TARGET:** Documented with zero API overclaims.
- [x] **Mobile R1 created:** [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png) verified ($390 \times 844$).
- [x] **Desktop R1 created:** [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png) verified ($1440 \times 900$).
- [x] **No source changes:** `git diff apps/` is empty.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
