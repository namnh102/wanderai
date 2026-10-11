# GoMate Group Foundation — Membership Eligibility & Runtime Honesty Correction (TASK 08.2.3.10-R1)

**Status:** APPROVED MICRO-CORRECTION & DESIGN LOCK  
**Task:** TASK 08.2.3.10-R1 — GOMATE GROUP FOUNDATION MEMBERSHIP ELIGIBILITY & RUNTIME HONESTY CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Group`, `model GroupMember`, `model Trip`, `model TripMember`, `model Match`, `model Message`)
- Core Contracts: `docs/design/gomate-group-foundation-contract-v1.md`, `docs/design/gomate-buddy-match-consent-contract-v1.md`, `docs/design/gomate-trip-user-flow-spec-v1.md`
- Master Visual Artifacts:
  - Mobile Master R1: [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png) ($390 \times 844$)
  - Desktop Master R1: [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png) ($1440 \times 900$)
  - Baseline V1 Visuals (Pre-Correction): [`group-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-v1.png), [`group-desktop-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-v1.png)

---

## 1. Executive Summary & Objective

TASK 08.2.3.10-R1 executes targeted micro-corrections for the **GoMate Group Foundation, Membership, Role & Lifecycle V1** prior to Design Lock.

No Flutter production code, NestJS backend, FastAPI AI service, Prisma schema, or API contracts are altered. This task specifically resolves 8 core data honesty, semantic, and eligibility gaps identified during peer audit, regenerates the 2 master mockups (`-r1.png`), and locks the architectural contract for downstream implementation.

---

## 2. Comprehensive Correction Audit Matrix (Before → Risk → Schema Evidence → Correction → Final Contract)

### 2.1. Correction #1 — Group Eligibility & Prerequisite Chain

- **Before:** V1 contract allowed an Accepted Match (`MatchStatus === ACCEPTED`) to be directly invited into the Companion Group of a Trip, bypassing Trip membership.
- **Risk:** In a Trip-bound Companion Group, discussing itinerary and travel logistics with someone who is not a formal member of the Trip creates a severe operational and privacy anomaly.
- **Schema Evidence:**
  - `model Match`: Peer-to-peer connection (`userId`, `matchedUserId`, `status`). Has no relation to `Trip` or `Group`.
  - `model TripMember`: Workspace collaborator (`tripId`, `userId`, `role`).
  - `model Group`: Coordination room (`tripId` UUID column).
- **Correction:**
  - **MATCHED does NOT imply TRIP_MEMBER.**
  - An Accepted Match must first join the Trip as a `TripMember` via explicit Trip invite before they can receive a Group invitation.
  - Canonical flow locked:
    $$\text{MATCHED} \longrightarrow \text{Explicit Trip Invite} \longrightarrow \text{TripMember} \longrightarrow \text{Group Invite} \longrightarrow \text{Explicit Join} \longrightarrow \text{GroupMember}$$
- **Final Contract:** An Accepted Match who has not joined the Trip is classified as **`NOT YET ELIGIBLE`** for Companion Group membership.

---

### 2.2. Correction #2 — Member Mockup Data & TripMember Co-presence

- **Before:** In `group-mobile-detail-v1.png` and `group-desktop-detail-v1.png`, member Lê Hoàng Nam was captioned: *"Bạn đồng hành đã kết nối (Match ACCEPTED)"*, which could be misinterpreted as meaning Match alone granted group membership.
- **Risk:** Misleading visual evidence implying peer matching directly injects users into private travel coordination groups.
- **Schema Evidence:** `model GroupMember` requires a valid `userId`. The group is associated with `tripId` (`Khám phá Đà Nẵng 4N3Đ`).
- **Correction:**
  - Standardized Member 2 sub-line to: `"Bạn đồng hành · Thành viên chuyến đi"`.
  - Re-verified that all 3 displayed members (Chủ chuyến đi, Bạn đồng hành, Thành viên chuyến đi) satisfy TripMember eligibility.
- **Final Contract:** UI explicitly indicates co-presence as a `TripMember` (`Thành viên chuyến đi`) for all companion group participants.

---

### 2.3. Correction #3 — Member Capacity Honesty (Removal of Fake Denominator)

- **Before:** Mockups displayed `"Thành viên nhóm (3/5)"` and `"Danh sách thành viên (3/5)"`.
- **Risk:** Fabricated a system limit of 5 members, implying a database capacity ceiling that does not exist.
- **Schema Evidence:** `apps/backend/prisma/schema.prisma` models `Group` and `GroupMember` have **NO `maxMembers` column**. The table allows arbitrary rows.
- **Correction:**
  - Removed the fake `/5` denominator across mobile and desktop mockups.
  - Re-rendered section titles as `"Thành viên nhóm (3)"` and `"Danh sách thành viên (3)"`.
- **Final Contract:** `maxMembers` is classified as **`SCHEMA GAP / UNCONSTRAINED`**. UI must display plain member count, never fake limits.

---

### 2.4. Correction #4 — Owner Semantics (Derived from Trip Owner)

- **Before:** V1 visual displayed `"Bạn (Admin)"` alongside `"Trưởng nhóm (Owner)"`, and previous contract text ambiguously implied a database-persisted `OWNER` role.
- **Risk:** Confused Admin operational privileges with Owner governance, and obscured the missing database ownership column.
- **Schema Evidence:**
  - `model Group`: `creatorId` = **MISSING**, `ownerId` = **MISSING**.
  - `model GroupMember`: `role String @default("member")` with comment `"admin", "member"`. No `"owner"` string exists in the comment.
- **Correction:**
  - Group Leader / Owner is derived entirely from the linked `Trip.userId` by application logic.
  - Classified strictly as **`DESIGN TARGET — DERIVED FROM TRIP OWNER`**.
  - In visual UI, the current user is rendered as `"Bạn"`, `"Chủ chuyến đi"`, with role badge `"Trưởng nhóm"`.
- **Final Contract:** Group Owner is an application-derived persona from `Trip.userId`, not a database-persisted group column.

---

### 2.5. Correction #5 — Role Data Honesty (Plain String vs Enum)

- **Before:** Contract referenced Owner, Admin, Member without emphasizing that database stores a plain string without enum constraints.
- **Risk:** Developers might assume Prisma enforces an `enum GroupRole { OWNER, ADMIN, MEMBER }`.
- **Schema Evidence:** `model GroupMember` line 95: `role String @default("member") // "admin", "member"`.
- **Correction:**
  - Explicitly documented that `role` is a plain PostgreSQL `text`/`varchar` column.
  - Documented that `Trip Owner != Group Admin`. Trip Owner possesses absolute group lifecycle control (disband, ownership transfer), whereas Admin is an operational role (`role = "admin"`).
- **Final Contract:** 3-tier hierarchy (`Derived Group Leader`, `Admin`, `Member`) is enforced at the application/API layer. No database `OWNER` enum exists.

---

### 2.6. Correction #6 — Leave Message Anonymization Reality

- **Before:** Contract stated that when a user leaves the group, their message history is automatically anonymized to `[Thành viên đã rời nhóm]`.
- **Risk:** Implied that the database schema or a database trigger automatically removes or nulls the author reference.
- **Schema Evidence:** `model Message` line 70: `userId String @map("user_id") @db.Uuid` is a **required non-nullable field** with `user User @relation(fields: [userId], references: [id])`.
- **Correction:**
  - Database does **NOT** automatically anonymize messages upon member exit.
  - Message retention is **`DB-supported`** (the `Message` row remains persisted with `userId`).
  - Rendering `[Thành viên đã rời nhóm]` or masking the user's name is a **`DESIGN TARGET`** client/presentation layer rendering rule.
- **Final Contract:** Message retention is DB-persisted; anonymization is a display-layer business rule.

---

### 2.7. Correction #7 — Technical Annotations Removed from Production UI

- **Before:** V1 mockups displayed developer tracking annotations directly in UI cards:
  - `"Trò chuyện nhóm · Chờ WebSocket (TASK 08.2.3.11)"`
  - `"Lịch trình chung · MỤC TIÊU THIẾT KẾ"`
  - `"Chi tiêu chuyến đi · CHƯA CÓ DB"`
- **Risk:** Leaking internal architectural tickets and database limitations to end users degrades visual fidelity and realism.
- **Schema Evidence:** Internal tickets (`TASK 08.2.3.xx`) and schema gaps belong to audit documents, not user-facing application frames.
- **Correction:**
  - Regenerated mockups using clean, human-friendly production copy:
    - `"Trò chuyện nhóm"` · badge `"Sắp có"`
    - `"Lịch trình chung"` · badge `"Sắp có"`
    - `"Chi tiêu chuyến đi"` · badge `"Sắp có"`
  - Moved technical classifications to the audit documents and contract tables.
- **Final Contract:** Production UI displays clean disabled states with `"Sắp có"`; technical gap annotations are restricted to engineering audit logs.

---

### 2.8. Correction #8 — Safely Scoped GPS Location Wording

- **Before:** Contract contained an absolute global assertion: *"GPS tuyệt đối không được phát tán trong nhóm."*
- **Risk:** Creating an overly rigid absolute rule that could contradict future opt-in safety features (e.g. voluntary real-time location sharing during active travel).
- **Schema Evidence:** Neither `Group` nor `GroupMember` contains location fields. Geolocation is an on-demand device permission.
- **Correction:**
  - Replaced absolute statement with safely scoped product copy:
    > *"Việc tham gia nhóm không tự động chia sẻ vị trí thời gian thực. Mọi tính năng chia sẻ vị trí trong tương lai phải yêu cầu hành động và sự đồng ý rõ ràng của người dùng."*
- **Final Contract:** Preserves future location-sharing architecture while strictly guaranteeing that group entry never triggers ambient tracking.

---

## 3. Product Rules & Boundary Classifications

### 3.1. One-Group-Per-Trip Rule Classification
- **Contract Rule:** A Trip has at most one active primary Companion Group ($\text{Trip } 1 \longleftrightarrow 0..1 \text{ Primary Group}$).
- **Classification:** **`LOCKED V1 PRODUCT RULE`**, NOT a database-enforced constraint.
- **Implementation Note:** `schema.prisma` currently lacks `@unique` on `Group.tripId`. Backend NestJS creation logic must check for existing active groups before creating a new one.

### 3.2. Group Creation Form Omission
- `group-mobile-create-v1.png` continues to be **SKIPPED** in this task.
- Creating a group mutation form without `creatorId` persistence and without a formal foreign key relation between `Group` and `Trip` would constitute an ungrounded design artifact.

### 3.3. Group Mutation Action Honesty
- Actions on the Group Detail screen (`Mời thành viên`, `Rời nhóm`, `Giải tán nhóm`) are strictly classified as **`DESIGN TARGET`**.
- There are currently **0 endpoints** in NestJS backend for group mutations.

---

## 4. Master Mockup Verification (R1 Refined Artifacts)

| Mockup File | Viewport | Dimensions | Verified R1 Honesty Corrections | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`group-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. Header shows `Thành viên nhóm (3)` without `/5`.<br>2. Owner labeled as `"Bạn"`, `"Chủ chuyến đi"`, badge `"Trưởng nhóm"`.<br>3. Member 2 verified as `"Bạn đồng hành · Thành viên chuyến đi"`.<br>4. Downstream rows use clean `"Sắp có"` badges (no developer task IDs or `"CHƯA CÓ DB"`).<br>5. Leave action labeled cleanly as `"Rời khỏi nhóm đồng hành"`.<br>6. Zero scrollbars; crisp typography. | **PASS** |
| [`group-desktop-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.10/group-desktop-detail-r1.png) | Desktop | $1440 \times 900$ | 1. Col 1: Linked trip info + scoped GPS notice: *"Việc tham gia nhóm không tự động chia sẻ vị trí thời gian thực."*<br>2. Col 2: `Danh sách thành viên (3)` without fake `/5`; verified badges; clean invite action.<br>3. Col 3: Clean downstream module cards with `"Sắp có"` badges; danger zone disband button.<br>4. Top navigation: Canonical 5 tabs with `"Chuyến đi"` active. Zero scrollbars. | **PASS** |

---

## 5. Final Capability Matrix

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

## 6. Design Acceptance Gate (TASK 08.2.3.10-R1)

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
