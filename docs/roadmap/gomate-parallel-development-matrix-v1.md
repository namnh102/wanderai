# GoMate Parallel Development Matrix & Branch Strategy V1
## Multi-Agent Concurrency, Shared File Collision Avoidance & Migration Sequencing

- **Document Reference:** `docs/roadmap/gomate-parallel-development-matrix-v1.md`
- **Scope:** Engineering Governance for Multi-Agent / Multi-Chat Parallel Execution
- **Status:** **CONCURRENCY & BRANCH STRATEGY LOCKED**
- **Date:** October 7, 2026
- **Companion Specifications:**
  - `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
  - `docs/roadmap/gomate-implementation-dependency-dag-v1.md`

---

## 1. Executive Summary & Parallelism Governance

When multiple autonomous coding agents or engineering streams work concurrently on the GoMate repository, unstructured commits create merge conflicts, schema locks, and state corruption.

This document establishes the **Parallel Development Matrix**, identifying:
1. Which work packages can run concurrently with **zero conflict risk** (`PARALLEL SAFE`).
2. Which packages require **contract-first coordination** (`PARALLEL WITH COORDINATION`).
3. Which packages must execute **strictly sequentially** (`SERIAL ONLY`).
4. The exact **shared bottleneck files** in Flutter and NestJS that trigger concurrency locks.
5. The **Branching Model** and **Prisma Database Migration Sequencing**.

---

## 2. Shared File Collision Risk Analysis

Any work package touching one of the following **6 Critical Shared Files** cannot be classified as `PARALLEL SAFE` with respect to other packages touching the same file:

| Bottleneck File Path | Component Role | Collision Risk Level | Concurrency Mitigation Rule |
| :--- | :--- | :---: | :--- |
| `apps/backend/prisma/schema.prisma` | Core Database Schema | **CRITICAL** | Only one agent may mutate schema at a time. Schema changes must be merged via standalone migration PRs before dependent feature branches branch off. |
| `apps/mobile/lib/core/router/app_router.dart` | GoRouter Route Table | **HIGH** | Feature modules must declare their sub-routes in isolated `*routes.dart` files; `app_router.dart` only imports and includes them. |
| `apps/mobile/lib/core/network/api_client.dart` | Dio HTTP Client & Interceptors | **HIGH** | `WP-AUTH-01` must completely land token interceptor before other streams touch network logic. |
| `apps/mobile/lib/main.dart` | App Bootstrapper & Plugin Init | **HIGH** | Plugin registrations (`flutter_local_notifications`, `flutter_secure_storage`) must be consolidated sequentially. |
| `apps/mobile/lib/core/theme/` | Shared Design Tokens & Theme | **MEDIUM** | Design tokens are locked (`TASK 08.2.4`); zero styling modifications permitted. |
| `apps/backend/src/app.module.ts` | NestJS Root Dependency Graph | **MEDIUM** | Each new module must be appended to `imports` in a clean, non-conflicting block. |

---

## 3. Parallel Development Compatibility Matrix

This matrix evaluates pairwise concurrency between major workstreams:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               PARALLEL EXECUTION COMPATIBILITY MATRIX                             │
├────────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────────┤
│ Workstream Pair    │ Auth     │ Profile  │ Media    │ Safety   │ Map      │ Buddy    │ Group/Chat│
├────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼───────────┤
│ **Auth Hardening** │ —        │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ COORD    │ COORD     │
│ **Profile/Prefs**  │ SAFE     │ —        │ SAFE     │ SAFE     │ SAFE     │ COORD    │ SAFE      │
│ **Place Media**    │ SAFE     │ SAFE     │ —        │ SAFE     │ SAFE     │ SAFE     │ SAFE      │
│ **Safety Offline** │ SAFE     │ SAFE     │ SAFE     │ —        │ SAFE     │ SAFE     │ SAFE      │
│ **Map Basemap**    │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ —        │ SAFE     │ SAFE      │
│ **Buddy Match**    │ COORD    │ COORD    │ SAFE     │ SAFE     │ SAFE     │ —        │ SERIAL    │
│ **Group & Chat**   │ COORD    │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SERIAL   │ —         │
│ **Shared Itin**    │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ COORD     │
│ **Shared Expense** │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ COORD     │
│ **Reminders**      │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE      │
│ **Wandy Bridge**   │ COORD    │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE     │ SAFE      │
└────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴───────────┘
```

### Detailed Concurrency Scenarios Evaluated
1. **Auth Backend vs. Safety Frontend (`PARALLEL SAFE`):**
   - *Rationale:* Auth backend modifies `apps/backend/src/modules/auth/` and `schema.prisma` (tokens); Safety frontend modifies `apps/mobile/lib/features/safety/` and bundles `assets/data/emergency_directory.json`. Zero overlapping files. Can run in completely separate chats.
2. **Media Pipeline vs. Buddy Schema (`PARALLEL WITH COORDINATION`):**
   - *Rationale:* Both touch `schema.prisma`. Must merge `schema.prisma` changes sequentially (Media first $\rightarrow$ migrate $\rightarrow$ Buddy second $\rightarrow$ migrate).
3. **Reminder Frontend vs. OAuth Backend (`PARALLEL SAFE`):**
   - *Rationale:* Reminders use `flutter_local_notifications` in `apps/mobile/lib/features/trips/`; OAuth backend integrates `google-auth-library` in `apps/backend/src/modules/auth/`. Zero overlapping files.
4. **Buddy Matching vs. Group Creation (`SERIAL ONLY`):**
   - *Rationale:* Groups are created from accepted Buddy Matches (`WP-BUDDY-02`). Group space requires `Match.status == ACCEPTED` foreign key context.
5. **Group Chat vs. Shared Itinerary vs. Shared Expense (`PARALLEL WITH COORDINATION`):**
   - *Rationale:* Once `WP-GROUP-01` (Group Space & Membership) lands, Chat (`WP-CHAT-01`), Shared Itinerary (`WP-ITIN-01`), and Shared Expense (`WP-EXP-01`) operate on separate tabs within the Group Space and can be developed concurrently across 3 separate streams.

---

## 4. Multi-Track Concurrent Execution Model

To maximize development velocity without merge conflicts, work packages are organized into **3 Independent Concurrent Tracks**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   3 CONCURRENT DEVELOPMENT TRACKS                      │
├────────────────────────────────────────────────────────────────────────┤
│ TRACK 1: SECURITY, IDENTITY & SOCIAL TRAVEL (Track Lead: Agent A)      │
│ 1. WP-AUTH-01: Secure Storage & Silent Refresh Queue Lock              │
│ 2. WP-AUTH-02: Rate Limiting & Throttling                              │
│ 3. WP-PROF-01: Travel Preference Persistence & Validation API          │
│ 4. WP-PROF-02: Privacy & Visibility Controls                           │
│ 5. WP-BUDDY-01: Traveler Discovery Grid & Vector Compatibility         │
│ 6. WP-BUDDY-02: Masked Profile View & Double Opt-In Handshake          │
│ 7. WP-GROUP-01: Group Space Persistence & Role Permissions             │
├────────────────────────────────────────────────────────────────────────┤
│ TRACK 2: DATA TRUTH, MEDIA, MAP & OFFLINE RESILIENCE (Agent B)         │
│ 1. WP-SAFE-01: Emergency Confirmation Modal & Offline Asset Cache      │
│ 2. WP-MAP-01:  Offline Basemap Tile Caching & Quota Manager            │
│ 3. WP-MEDIA-01: Production Place Media Pipeline & CC Provenance        │
│ 4. WP-SEARCH-01: Global Cross-Destination Search Entry                 │
│ 5. WP-REMIND-01: Local Notification Scheduling & Packing Alerts        │
├────────────────────────────────────────────────────────────────────────┤
│ TRACK 3: AI COPILOT & COLLABORATIVE GROUP APPS (Agent C)               │
│ 1. WP-TRIP-01: Drag-and-Drop Itinerary Reordering Persistence          │
│ 2. WP-WANDY-01: Guarded Action Bridge (Preview $\rightarrow$ Confirm)  │
│ [Unlocks after Track 1 completes WP-GROUP-01]:                         │
│ 3. WP-CHAT-01: Real-Time WebSocket Message Timeline                    │
│ 4. WP-ITIN-01 & 02: Shared Itinerary Board, Voting & Concurrency Lock  │
│ 5. WP-EXP-01 & 02: Shared Expense Ledger & Debt Simplification Matrix  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Branch Strategy & Git Workflow

### 5.1. Preservation Invariants
1. **Design Branch Frozen:** Branch `feature/gomate-visual-mockups` contains all locked mockups and design documentation. **Zero implementation code will be committed to this branch.**
2. **Develop Isolation:** All feature work branches off `develop` and merges back into `develop` only after passing automated test gates.

### 5.2. Vertical Slice Branch Naming Convention
Every branch corresponds to exactly one vertical slice work package:

```
develop
│
├── feature/auth-secure-storage-refresh     (WP-AUTH-01)
├── feature/auth-rate-limiting              (WP-AUTH-02)
├── feature/auth-email-verification         (WP-AUTH-03)
├── feature/auth-password-recovery          (WP-AUTH-04)
├── feature/auth-social-oauth               (WP-AUTH-05)
├── feature/auth-account-linking            (WP-AUTH-06)
│
├── feature/profile-preferences             (WP-PROF-01)
├── feature/profile-privacy-controls        (WP-PROF-02)
│
├── feature/place-media-pipeline            (WP-MEDIA-01)
├── feature/safety-offline-safeguard        (WP-SAFE-01)
├── feature/map-tile-caching                (WP-MAP-01)
├── feature/trip-reorder-persistence        (WP-TRIP-01)
├── feature/search-cross-destination        (WP-SEARCH-01)
│
├── feature/wandy-action-bridge             (WP-WANDY-01)
├── feature/reminders-local-notifications   (WP-REMIND-01)
│
├── feature/buddy-discovery-matching        (WP-BUDDY-01)
├── feature/buddy-consent-handshake         (WP-BUDDY-02)
│
├── feature/group-space-roles               (WP-GROUP-01)
├── feature/group-chat-websocket            (WP-CHAT-01)
├── feature/shared-itinerary-voting         (WP-ITIN-01)
├── feature/shared-itinerary-lock           (WP-ITIN-02)
├── feature/shared-expense-split            (WP-EXP-01)
└── feature/shared-expense-simplification   (WP-EXP-02)
```

### 5.3. Merge & Rebase Policy
- **Feature Branches:** Kept updated with `git rebase origin/develop` daily.
- **Squash-and-Merge:** Every work package merges into `develop` as a single semantic squash commit with full test verification evidence.
- **Pre-Merge Invariant:** A PR cannot be merged if `git diff apps/backend/prisma/` introduces un-migrated schema changes.

---

## 6. Database Migration Sequencing Strategy

To prevent migration conflicts, all schema changes are sequenced in **4 Discrete Migration Batches**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                 PRISMA SCHEMA MIGRATION EXECUTION ORDER                │
├────────────────────────────────────────────────────────────────────────┤
│ BATCH 1: AUTHENTICATION HARDENING (Prerequisite for Phase 1)           │
│ • Create table: email_verification_tokens                              │
│ • Create table: password_reset_tokens                                  │
│ • Create table: oauth_accounts                                         │
│ • Add field: User.is_discoverable (BOOLEAN DEFAULT TRUE)               │
├────────────────────────────────────────────────────────────────────────┤
│ BATCH 2: PLACE MEDIA & ASSET PROVENANCE                                │
│ • Create table: place_media (with place_id FK and license_type)        │
│ • Add index: place_media_place_id_idx                                  │
│ • Add index: places_name_idx, destinations_name_idx (Search perf)      │
├────────────────────────────────────────────────────────────────────────┤
│ BATCH 3: COLLABORATIVE SOCIAL TRAVEL (Buddy & Group)                   │
│ • Note: Match, Group, GroupMember, Message tables ALREADY EXIST!       │
│ • Add index: matches_status_idx                                        │
│ • Add index: group_members_group_id_user_id_idx                        │
├────────────────────────────────────────────────────────────────────────┤
│ BATCH 4: GROUP SHARED ITINERARY & EXPENSE LEDGERS                      │
│ • Create table: itinerary_votes                                        │
│ • Add fields: itinerary_items.locked_by, locked_at                     │
│ • Create table: expenses                                               │
│ • Create table: expense_splits                                         │
│ • Create table: settlements                                            │
└────────────────────────────────────────────────────────────────────────┘
```

### Schema Model Reuse Audit (Zero Duplication Rule)
- `Match`: **REUSED** (Exists in `schema.prisma`; zero duplication).
- `Group`: **REUSED** (Exists in `schema.prisma`; zero duplication).
- `GroupMember`: **REUSED** (Exists in `schema.prisma`; zero duplication).
- `Message`: **REUSED** (Exists in `schema.prisma`; zero duplication).
- `TravelPreference`: **REUSED** (Exists in `schema.prisma`; zero duplication).
- `ItineraryItem`: **REUSED & EXTENDED** (`lockedBy`, `lockedAt` added; zero duplicate tables).

---

## 7. Parallel Execution Summary & Gate Clearance

By enforcing:
1. Strict segregation of the 3 Concurrent Tracks,
2. Explicit isolation of the 6 Shared Bottleneck Files,
3. A formal 4-Batch Database Migration Sequence, and
4. Independent vertical slice branches off `develop`,

GoMate guarantees **zero merge collisions, zero schema deadlocks, and maximum multi-agent engineering velocity**.
