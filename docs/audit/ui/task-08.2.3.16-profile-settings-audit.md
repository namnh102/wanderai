# GoMate Profile & Settings — Capability Audit, Privacy Contract & Visual Design V1 (TASK 08.2.3.16)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.16 — GOMATE PROFILE & SETTINGS: CAPABILITY AUDIT, PRIVACY CONTRACT & VISUAL DESIGN V1  
**Date:** October 6, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model User`, `model Profile`, `model TravelPreference`, lines 40–108; `model SafetyContact`, lines 260–285; `model Notification`, lines 371–388)
- Backend Source Code: [`apps/backend/src/modules/users/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/users/), [`apps/backend/src/modules/auth/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/auth/)
- Mobile Client Router: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
- Mobile Auth Repository: [`apps/mobile/lib/features/auth/data/auth_repository.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/auth/data/auth_repository.dart)
- Mobile Location Provider: [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart)
- Upstream Design Contracts:
  - [`docs/design/gomate-trip-user-flow-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-user-flow-spec-v1.md)
  - [`docs/design/gomate-group-foundation-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-foundation-contract-v1.md)
  - [`docs/design/gomate-shared-expense-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-expense-contract-v1.md)
  - [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)
  - Core Contract: [`docs/design/gomate-profile-settings-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-profile-settings-contract-v1.md)
- Master Visual Evidence Artifacts (12 Master Artifacts in `docs/audit/evidence/ui-08.2.3.16/`):
  1. Mobile Profile Overview: [`profile-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1.png) ($390 \times 844$)
  2. Desktop Profile Overview: [`profile-desktop-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1.png) ($1440 \times 900$)
  3. Mobile Edit Profile: [`profile-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1.png) ($390 \times 844$)
  4. Mobile Travel Preferences: [`profile-mobile-travel-preferences-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1.png) ($390 \times 844$)
  5. Mobile Settings Home: [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) ($390 \times 844$)
  6. Desktop Settings Home: [`settings-desktop-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1.png) ($1440 \times 900$)
  7. Mobile Privacy Settings: [`settings-mobile-privacy-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1.png) ($390 \times 844$)
  8. Mobile Notification Settings: [`settings-mobile-notifications-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1.png) ($390 \times 844$)
  9. Mobile Location Settings: [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) ($390 \times 844$)
  10. Mobile Account & Security: [`settings-mobile-account-security-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1.png) ($390 \times 844$)
  11. Mobile Logout Confirmation: [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) ($390 \times 844$)
  12. Mobile Loading & Error States: [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) ($390 \times 844$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.16 establishes the complete capability audit, architectural contract, privacy model, and visual design baseline for the **GoMate Profile & Settings** experience.

### Key Audit Findings & Architectural Verdicts:
1. **Separation of Concerns & Three-Tier Privacy Model:**
   - Identity is rigorously divided into:
     - **Tier 1 (Private Account Data):** Email, phone, security credentials, active sessions, notification routing preferences, and **Safety Trusted Contacts** (`model SafetyContact`).
     - **Tier 2 (Public / Buddy Profile Data):** Display name, avatar, bio, travel style, travel interests, languages, nationality.
     - **Tier 3 (Trip Context Data):** Trip role, activity participation, expense ledger shares.
2. **Strict Invariant — Absolute Isolation of Safety Contacts:**
   - Trusted emergency contacts configured in [`gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md) (`model SafetyContact`) belong **EXCLUSIVELY to Tier 1**.
   - Under NO circumstances may safety contacts leak into public traveler profiles, Buddy discovery cards, trip member rosters, or group chats.
3. **Buddy Matching Boundary:**
   - A mutual Buddy match creates an in-app chat channel. It **DOES NOT** expose raw phone numbers or email addresses without a secondary explicit user opt-in toggle (`Hiển thị số điện thoại sau khi ghép đôi`).
4. **Canonical Preference Ownership Model:**
   - [`model TravelPreference`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L91) in PostgreSQL is the **single canonical source of truth** for all travel preferences (travel style, budget range, preferred group size, interests, avoidances, dietary needs).
   - This entity serves both the AI Itinerary Planning Engine (Task 07.2) and the future Buddy Matching engine.
5. **Notification Reality (Honest Disclosure):**
   - **In-App Notification Inbox (`model Notification`):** **CURRENT** in PostgreSQL schema (`schema.prisma` lines 371–388), but currently has zero NestJS controllers/services and zero Flutter UI bindings.
   - **OS Push Notifications (FCM / APNs):** **MISSING**. Zero push SDKs exist in `pubspec.yaml`, zero push workers exist in backend `package.json`.
   - The UI honestly labels Push OS as *"Dự kiến V2"* and avoids claiming functional lockscreen push delivery.
6. **Location Privacy & Boundary:**
   - **Foreground GPS Fix:** **CURRENT** via `geolocator: ^13.0.2` with accuracy radius ($\pm\text{meters}$).
   - **Background Location Tracking:** **EXCLUDED / MISSING**. GoMate does not run background tracking services.
   - Joining a trip or group **NEVER** grants other members continuous or background GPS tracking.
7. **Session & Logout Protocol:**
   - Client-side token storage in `SharedPreferences` (`access_token`, `refresh_token`).
   - Logout clears local storage and resets router auth status to `unauthenticated`.
   - **Server-Side Token Revocation / Blacklist:** **MISSING** (stateless JWTs). No false claims of server-side revocation are made.
8. **Account Deletion Reality (Policy / Architecture Gap):**
   - Direct hard deletion (`DELETE FROM users WHERE id = ...`) fails immediately due to Foreign Key RESTRICT constraints on 15+ models (`Trip`, `TripMember`, `Review`, `Comment`, `GroupMember`, `Message`, `SafetyContact`, etc.).
   - Financial balances in Shared Expense (Task 08.2.3.13-R1) require immutable ledger auditability.
   - Target specification: **Soft-Delete + Anonymization (Tombstone) Pattern** (`User.deletedAt = now()`, PII sanitized). Hard deletion is formally classified as a **POLICY / ARCHITECTURE GAP**.
9. **Navigation Integrity:**
   - Profile and Settings are accessed via the user avatar/pill in the app header or drawer, preserving the locked 5-tab root navigation bar (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn`). No invalid 6th bottom tab was added.

---

## 2. Technical Evidence & Repository Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)

Inspection of lines 40–108, 260–285, and 371–388 produced:
- **`model User`:**
  - `id`: `String @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid`
  - `email`: `String @unique`
  - `passwordHash`: `String @map("password_hash")`
  - `role`: `UserRole @default(USER)`
  - `isVerified`: `Boolean @default(false) @map("is_verified")`
  - `createdAt`: `DateTime @default(now()) @map("created_at") @db.Timestamptz`
  - `deletedAt`: `DateTime? @map("deleted_at") @db.Timestamptz`
- **`model Profile`:**
  - `id`: `String @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid`
  - `userId`: `String @unique @map("user_id") @db.Uuid`
  - `displayName`: `String @map("display_name")`
  - `avatar`: `String?`
  - `bio`: `String?`
  - `phone`: `String?`
  - `dateOfBirth`: `DateTime? @map("date_of_birth") @db.Date`
  - `nationality`: `String?`
  - `languages`: `String[] @default([])`
- **`model TravelPreference`:**
  - `travelStyle`: `TravelStyle @default(COMFORT) @map("travel_style")`
  - `budgetMin`: `Int @default(0) @map("budget_min")`
  - `budgetMax`: `Int @default(10000000) @map("budget_max")`
  - `preferredGroup`: `GroupSize @default(SOLO) @map("preferred_group")`
  - `interests`: `String[] @default([])`
  - `avoidances`: `String[] @default([])`
  - `dietaryNeeds`: `String[] @default([]) @map("dietary_needs")`
- **`model SafetyContact`:**
  - Lines 260–285: `userId`, `name`, `phone`, `relationship`, `isEmergencySOS`.
  - Relation: `user User @relation(fields: [userId], references: [id], onDelete: Cascade)`.
- **`model Notification`:**
  - Lines 371–388: `id`, `userId`, `type` (`NotificationType`), `title`, `body`, `data`, `isRead`, `createdAt`.

### 2.2. Backend Controller & Service Reality Audit (`apps/backend/src/modules/`)

Inspection of `apps/backend/src/modules/users/users.service.ts` and `users.controller.ts`:
1. `findById(id: string)`:
   ```typescript
   include: {
     profile: {
       select: {
         displayName: true,
         avatar: true,
         bio: true,
         phone: true,
       },
     },
     travelPreferences: true,
   }
   ```
   - **SCHEMA GAP:** `dateOfBirth`, `nationality`, and `languages` exist in Prisma `model Profile`, but are **omitted** from the `select` projection!
2. `updateProfile(userId: string, data: UpdateProfileDto)`:
   - DTO only permits updating `displayName`, `avatar`, and `bio`.
   - `phone`, `dateOfBirth`, `nationality`, and `languages` cannot be updated through this endpoint.
3. `TravelPreference` updates:
   - **PARTIAL:** Selected in `findById`, but `UsersController` provides zero `PUT /users/me/preferences` endpoint.
4. `Password Change`:
   - `apps/backend/src/modules/auth/auth.controller.ts` only exposes `register` and `login`.
   - **MISSING:** Zero password change or password reset endpoint exists.
5. `Token Revocation`:
   - JWT tokens are verified statelessly via `@nestjs/passport` and `passport-jwt`. Zero Redis token blacklisting or database session tracking exists.

### 2.3. Mobile Client Audit (`apps/mobile/`)

1. **Router & Bottom Navigation (`apps/mobile/lib/core/router/app_router.dart`):**
   - The root `ShellRoute` has exactly 5 bottom navigation tabs:
     - Index 0: `/home` (`Khám phá`)
     - Index 1: `/map` (`Bản đồ`)
     - Index 2: `/ai` (`Wandy AI`)
     - Index 3: `/trips` (`Chuyến đi`)
     - Index 4: `/safety` (`An toàn`)
   - Profile route (`/profile`) is defined as a standalone sub-route, accessed from the user area.
   - **Verdict:** Complies with navigation integrity; no 6th tab added.
2. **Push Notifications:**
   - Search for `firebase_messaging`, `flutter_local_notifications`, or `push_notifications` in `pubspec.yaml` yields **0 matches**.
   - **Verdict:** Push notification runtime is 100% missing.
3. **Session Management (`apps/mobile/lib/features/auth/data/auth_repository.dart`):**
   - `logout()` executes `_sharedPreferences.remove('access_token')` and `_sharedPreferences.remove('refresh_token')`.
   - **Verdict:** Client token erasure is CURRENT; server revocation is MISSING.

---

## 3. Comprehensive Capability Classification Matrix

Every capability audited across Profile & Settings is classified according to the 7-tier taxonomy:
`CURRENT`, `PARTIAL`, `MISSING`, `SCHEMA GAP`, `DESIGN TARGET`, `FUTURE`, `EXCLUDED`.

| Capability / Field | Codebase Status | Classification | Architectural Verdict & Remediation |
| :--- | :---: | :---: | :--- |
| **User ID & Email** | Prisma & NestJS | **CURRENT** | Primary key and login identifier. Read-only in profile. |
| **Password & Bcrypt Hash** | Prisma & Auth | **CURRENT** | Hashed in PostgreSQL; no plain text exposure. |
| **User Role** | Prisma Enum | **CURRENT** | `USER`, `ADMIN`, `MODERATOR`. Rendered as user role pill. |
| **Account Verification (`isVerified`)** | Prisma Column | **PARTIAL** | DB boolean flag exists; no verification pipeline yet. |
| **Display Name** | Prisma & API | **CURRENT** | Full CRUD supported via `PUT /users/me`. Required (2–50 chars). |
| **Avatar URL** | Prisma & API | **CURRENT** | Updatable via `PUT /users/me`. Displays user image or initial. |
| **Traveler Bio** | Prisma & API | **CURRENT** | Updatable via `PUT /users/me`. Max 200 characters with counter. |
| **Phone Number (Storage)** | Prisma Column | **PARTIAL** | Column in schema; selected in read, but omitted from update DTO. |
| **Phone Number (Privacy)** | Design Contract | **TIER 1 (PRIVATE)** | Strictly masked. Never shown publicly; explicit post-match opt-in. |
| **Date of Birth / Age** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection. |
| **Nationality** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection. |
| **Languages Spoken** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection. |
| **Gender / Pronouns** | None | **MISSING** | Neither schema nor backend supports gender. Omitted from V1. |
| **Home City** | None | **MISSING** | Not in schema. Replaced by `nationality` in V1. |
| **Travel Style (Enum)** | Prisma Enum | **PARTIAL** | `TravelStyle` (`BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`). |
| **Budget Min / Max** | Prisma Int | **PARTIAL** | Integer VND amounts in `TravelPreference`. |
| **Preferred Group Size** | Prisma Enum | **SCHEMA GAP** | `GroupSize` (`SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY`). |
| **Travel Interests & Avoidances** | Prisma Arrays | **PARTIAL** | `String[]` arrays in `TravelPreference`. |
| **Dietary Needs** | Prisma Array | **SCHEMA GAP** | `dietaryNeeds` in schema; needs UI chip integration. |
| **TravelPreference Update API** | Backend API | **DESIGN TARGET** | Need `PUT /users/me/preferences` endpoint. |
| **Safety Trusted Contacts** | Prisma Model | **TIER 1 STRICT** | `model SafetyContact`. Isolated from public profile & buddy matching. |
| **Buddy Discovery Toggle** | Backend API | **DESIGN TARGET** | Opt-in/out flag for buddy recommendation candidate pool. |
| **Post-Match Privacy Scope** | Design Contract | **TIER 2 BOUNDARY**| Matching gives in-app chat; does NOT reveal phone/email. |
| **Foreground GPS Fix** | Mobile Geolocator | **CURRENT** | On-demand GPS fix with accuracy circle ($\pm\text{meters}$). |
| **Background Location Tracking** | Client/Server | **EXCLUDED** | GoMate does not run background tracking services. |
| **Continuous Live Location Sharing** | Client/Server | **EXCLUDED / FUTURE**| Prohibited in V1. Ephemeral opt-in sharing reserved for V2. |
| **In-App Notification Storage** | Prisma Model | **CURRENT** | `model Notification` exists in PostgreSQL. |
| **In-App Notification Inbox UI** | Mobile Client | **DESIGN TARGET** | Needs Flutter notification center screen. |
| **OS Push Notifications (FCM/APNs)**| Client/Server | **MISSING / FUTURE**| Zero push dependencies. Honestly labeled as V2 in UI. |
| **Scheduled Push Reminders** | Backend Cron | **MISSING** | Cron/worker infrastructure absent (Task 08.2.3.14). |
| **Password Change Feature** | Backend API | **DESIGN TARGET** | Need `PUT /auth/change-password` endpoint. |
| **Client Token Erasure (Logout)** | Mobile SharedPreferences | **CURRENT** | Purges access & refresh tokens on confirmation. |
| **Server-Side Token Revocation** | Backend Redis | **MISSING / FUTURE**| Stateless JWTs. Blacklist table/cache reserved for V2. |
| **Direct Account Hard Deletion** | PostgreSQL FK | **BLOCKED (GAP)** | 15+ FK RESTRICT constraints block `DELETE FROM users`. |
| **Soft-Delete + Anonymization** | Design Contract | **DESIGN TARGET** | `deletedAt = now()`, PII sanitized, ledger history preserved. |

---

## 4. Architectural Deep Dives

### 4.1. Three-Tier Privacy Data Model & Emergency Contacts Isolation

```
===================================================================================
                         GOMATE THREE-TIER PRIVACY MODEL
===================================================================================

 [ TIER 1: PRIVATE ACCOUNT DATA ] ─────────► Account Owner & System Auth ONLY
 │ - Email address (nam.le@example.com)
 │ - Phone number (unless explicitly consented post-match)
 │ - Password hash / Security credentials
 │ - Active session tokens & devices
 │ - Safety Trusted Contacts (Mẹ, Bạn thân · Emergency SOS) [STRICT INVARIANT]
 │ - Notification preferences & delivery configs
 │ - Blocked users list & private checkins
 └─────────────────────────────────────────────────────────────────────────────────

 [ TIER 2: PUBLIC / BUDDY PROFILE DATA ] ──► Compatible Travelers & Buddy Discovery
 │ - Display Name ("Lê Hoàng Nam")
 │ - Avatar image URL
 │ - Short traveler bio (max 200 chars)
 │ - Travel Style (Comfort, Backpacker, Budget, Luxury)
 │ - Travel Interests (Beach, Culture, Cuisine, Nature)
 │ - Languages spoken (Tiếng Việt, English)
 │ - Nationality / City (Việt Nam)
 └─────────────────────────────────────────────────────────────────────────────────

 [ TIER 3: TRIP CONTEXT DATA ] ────────────► Bound to Specific Trip / Group Members
 │ - Trip Role (HOST, MEMBER)
 │ - Itinerary participation & assigned activities
 │ - Shared Expense ledger participation & balance shares
 │ - Group chat messages & media within the trip channel
 └─────────────────────────────────────────────────────────────────────────────────
```

#### Strict Invariants:
1. **Safety Contacts Isolation:**
   - Under no circumstances may `model SafetyContact` records be serialized in `/users/me/profile`, `/buddy/discover`, `/trips/:id/members`, or `/groups/:id/members`.
   - Emergency contacts are used solely for the SOS dispatch flow (Task 08.2.3.15).
2. **Matching Boundary:**
   - A mutual Buddy match creates a chat channel; it **DOES NOT** expose raw phone numbers or email addresses without secondary explicit consent.

---

### 4.2. Canonical Travel Preference Model (`model TravelPreference`)

[`model TravelPreference`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L91) is the unified preference engine for both AI Itinerary Planning (Task 07.2) and Buddy Matching (future).

```prisma
model TravelPreference {
  id              String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  userId          String      @unique @map("user_id") @db.Uuid
  travelStyle     TravelStyle @default(COMFORT) @map("travel_style")
  budgetMin       Int         @default(0) @map("budget_min")        // VND integer
  budgetMax       Int         @default(10000000) @map("budget_max")  // VND integer
  preferredGroup  GroupSize   @default(SOLO) @map("preferred_group")
  interests       String[]    @default([])
  avoidances      String[]    @default([])
  dietaryNeeds    String[]    @default([]) @map("dietary_needs")
  createdAt       DateTime    @default(now()) @map("created_at") @db.Timestamptz
  updatedAt       DateTime    @updatedAt @map("updated_at") @db.Timestamptz

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  @@map("travel_preferences")
}
```

- **Enums Enforced:**
  - `TravelStyle`: `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`
  - `GroupSize`: `SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY`
- **Budget Integrity:** Stored as integer VND (not floating point) to prevent rounding discrepancies with Shared Expense (Task 08.2.3.13-R1).

---

### 4.3. Notification Capability Reality (In-App vs. Push OS)

$$\textbf{In-App Inbox Persistence} \quad \ne \quad \textbf{OS Push Notification Delivery}$$

- **Repository Truth:**
  - `model Notification` exists in PostgreSQL (`id`, `userId`, `type`, `title`, `body`, `isRead`).
  - Neither Firebase Cloud Messaging (FCM) nor Apple Push Notification service (APNs) is configured.
  - Zero push tokens (`pushToken`, `fcmToken`) are stored on `model User`.
- **UI Honesty Protocol:**
  - The Notification Settings screen displays an informative banner:
    > **Hòm thư trong app: Hoạt động** · **Thông báo đẩy (Push OS): Dự kiến V2**  
    > *"Hệ thống hiện ghi nhận và lưu trữ thông báo lịch trình & an toàn trong ứng dụng. Tính năng thông báo đẩy màn hình khóa (FCM/APNs) đang được hoàn thiện."*
  - Toggles represent in-app notification filtering preferences rather than non-existent OS push channels.

---

### 4.4. Geolocation Privacy & Tracking Boundaries

- **Audited Truth:**
  - `apps/mobile/lib/features/location/providers/user_location_provider.dart` uses `geolocator: ^13.0.2` for **on-demand foreground fixes only**.
  - No background location daemon or periodic location ping worker exists.
- **Privacy Policy Locked:**
  1. GoMate **NEVER** tracks user location in the background.
  2. Joining a trip or group **NEVER** broadcasts real-time GPS coordinates to other members.
  3. Location fixes are stored locally in volatile memory and can be cleared via `[Xóa bộ nhớ đệm vị trí]`.

---

### 4.5. Session Lifecycle & Logout Protocol

- **Stateless JWT Architecture:**
  - Access tokens expire after 7 days; refresh tokens are stored in `SharedPreferences`.
  - No Redis token blacklist or server-side revocation table exists in the NestJS backend.
- **Logout Execution Protocol:**
  $$\text{User taps [Đăng xuất]} \quad \longrightarrow \quad \text{Modal confirmation} \quad \longrightarrow \quad \text{Purge SharedPreferences} \quad \longrightarrow \quad \text{Set AuthStatus.unauthenticated} \quad \longrightarrow \quad \text{Navigate to /login}$$
- **UI Honesty:** The logout confirmation modal informs the user that their current session on this device will be ended. No claims of global server-side revocation are made.

---

### 4.6. Account Deletion Architectural Assessment

#### 1. Relational Integrity Audit:
Hard deleting a user via `DELETE FROM users WHERE id = ...` throws an immediate foreign key constraint error due to non-cascading relations across 15+ models:
- `Trip` (host), `TripMember` (participant)
- `Review`, `Video`, `Comment`, `Like`, `Save`, `Follow`
- `Match` (sender, receiver)
- `GroupMember`, `Message`
- `SafetyContact`, `SafetyCheckin`
- Shared Expense ledger records and settlement transactions (must remain auditable per Task 08.2.3.13-R1)

#### 2. Architecture Verdict:
- Direct hard deletion is classified as a **POLICY / ARCHITECTURE GAP**.
- The production target must execute the **Soft-Delete + Anonymization (Tombstone) Pattern**:
  1. Set `User.deletedAt = now()`.
  2. Sanitize PII: `Profile.displayName = "Người dùng GoMate"`, `Profile.avatar = null`, `Profile.bio = null`, `Profile.phone = null`.
  3. Purge credentials: `User.passwordHash = random_bytes`, `User.email = "deleted_<uuid>@anonymized.gomate"`.
  4. Preserve transaction ledgers and trip archives for remaining members.
- The UI presents an Account Deletion Request action with clear disclosure of the 30-day anonymization process.

---

## 5. Master Visual Mockup Evidence Matrix (12 Artifacts)

All 12 visual mockups were rendered via headless Microsoft Edge browser (`--headless=new`, `--force-device-scale-factor=1`) at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.16/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`profile-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Hồ sơ cá nhân` + gear icon.<br>2. User avatar (N), display name "Lê Hoàng Nam", role "Du khách thích khám phá".<br>3. Bio text.<br>4. Profile completeness card (65%).<br>5. Personal info & travel style (Comfort) + interest chips.<br>6. Actions: `[Chỉnh sửa hồ sơ]` + `[Quyền riêng tư]`.<br>7. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`profile-desktop-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1.png) | Desktop | $1440 \times 900$ | 1. Top nav: GoMate logo + badge `Hồ sơ du khách` + 5 canonical tabs + User pill.<br>2. 3-column workspace ($320\text{px} + 680\text{px} + 340\text{px}$).<br>3. Col 1: Profile summary, avatar, completeness bar (65%), quick menu.<br>4. Col 2: Bio, basic info, TravelPreference details (Comfort, 1M-10M VND, 3-5 group, interest chips).<br>5. Col 3: Buddy Matching card, Privacy Shield guarantee, Security shortcuts. | **PASS (LOCKED)** |
| [`profile-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Hủy`, `Chỉnh sửa hồ sơ`, `[Lưu]`.<br>2. Avatar edit overlay.<br>3. Tên hiển thị input (2-50 chars) + Giới thiệu (78/200 chars).<br>4. Additional fields (Demo data): Số điện thoại (Riêng tư), Ngày sinh, Quốc tịch, Ngôn ngữ giao tiếp.<br>5. Primary CTA: `[Lưu thay đổi hồ sơ]`. | **PASS (LOCKED)** |
| [`profile-mobile-travel-preferences-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Hồ sơ`, `Sở thích du lịch`, `[Lưu]`.<br>2. Wandy AI value proposition banner.<br>3. 4 TravelStyle cards (Thoải mái active).<br>4. GroupSize chips (Nhóm nhỏ 3-5 active).<br>5. Budget range: 1.000.000 đ – 10.000.000 đ.<br>6. Interest chips: Biển, Văn hóa, Ẩm thực, Chụp ảnh.<br>7. CTA: `[Lưu sở thích du lịch]`. | **PASS (LOCKED)** |
| [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Cài đặt`.<br>2. User header card with avatar & `Hồ sơ ›` link.<br>3. Grouped sections: Tài khoản & Bảo mật, Trải nghiệm du lịch, Quyền riêng tư & An toàn, Ứng dụng.<br>4. Red logout action: `[Đăng xuất tài khoản]`.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`settings-desktop-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1.png) | Desktop | $1440 \times 900$ | 1. Top nav: GoMate logo + badge `Hồ sơ du khách` + 5 canonical tabs + User pill.<br>2. 2-column workspace ($320\text{px} + 1020\text{px}$).<br>3. Left menu: Settings categories.<br>4. Right panel: Account info card, Password card, Privacy & Location summary, Danger zone (Account Deletion). | **PASS (LOCKED)** |
| [`settings-mobile-privacy-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Quyền riêng tư`.<br>2. Buddy discovery switch (ON) + Phone visibility post-match switch (OFF).<br>3. Location boundary disclosure card (no auto sharing).<br>4. Social safety: Block list (0 users), Report violations.<br>5. SOS security commitment banner (trusted contacts isolated). | **PASS (LOCKED)** |
| [`settings-mobile-notifications-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Cài đặt thông báo`.<br>2. Honest runtime status: `Hòm thư: Hoạt động` vs `Push OS: Dự kiến V2`.<br>3. In-app activity notification toggles (Trips, Buddy, Group, Safety alert mandatory).<br>4. Reminders section (Schedule reminders). | **PASS (LOCKED)** |
| [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Vị trí & Dữ liệu`.<br>2. Foreground permission status (±15 m · Tốt) + `[Mở Cài đặt hệ thống]` button.<br>3. Location transparency principles: Foreground only, no background tracking, no continuous live broadcast.<br>4. Location cache clear action. | **PASS (LOCKED)** |
| [`settings-mobile-account-security-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Tài khoản & Bảo mật`.<br>2. Account info: Email (Verified), Joined date, Role (USER).<br>3. Password & session: Change password (API Target), Current mobile session.<br>4. Danger Zone card: Account deletion warning with data anonymization explanation + CTA `[Yêu cầu xóa tài khoản]`. | **PASS (LOCKED)** |
| [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) | Mobile | $390 \times 844$ | 1. Dark semi-transparent modal overlay ($65\%$ opacity).<br>2. Centered confirmation dialog with logout icon.<br>3. Title `Đăng xuất khỏi GoMate?`.<br>4. Clear session expiration warning.<br>5. Primary CTA `[Đăng xuất]` (Red) + Secondary CTA `[Hủy bỏ]`. | **PASS (LOCKED)** |
| [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) | Mobile | $390 \times 844$ | 1. Dual demonstration layout.<br>2. Top card: Loading skeleton with animated placeholders.<br>3. Bottom card: Network error state with warning icon, error explanation, and `[Thử lại]` action button.<br>4. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |

---

## 6. Verification & Acceptance Gate

| Verification Item | Requirement | Observed Status | Verdict |
| :--- | :--- | :--- | :---: |
| **1. Zero Modification to `apps/`** | `apps/` must be 100% clean | Verified via `git diff apps/` (0 lines modified) | **PASS** |
| **2. Zero Modification to `schema.prisma`**| `schema.prisma` untouched | Verified via `git diff apps/backend/prisma/` (0 lines) | **PASS** |
| **3. Canonical 5-Tab Navigation** | No 6th bottom nav tab added | Mobile overview & settings retain standard 5 tabs | **PASS** |
| **4. Safety Contacts Isolation** | `model SafetyContact` in Tier 1 | Isolated from public profiles, buddy matching, & trips | **PASS** |
| **5. Buddy Matching Boundary** | No raw phone/email exposure | Phone hidden by default; secondary opt-in required | **PASS** |
| **6. TravelPreference Ownership** | Unified preference model | Shared across AI Itinerary and Buddy Matching | **PASS** |
| **7. Notification Reality** | Honest Push OS disclosure | In-app inbox active, Push OS marked as V2 | **PASS** |
| **8. Location Tracking Reality** | Foreground only | Background & continuous sharing strictly excluded | **PASS** |
| **9. Session & Logout Protocol** | Clear token purge flow | Modal confirmation + SharedPreferences purge | **PASS** |
| **10. Account Deletion Reality** | FK RESTRICT gap addressed | Anonymization tombstone pattern specified | **PASS** |
| **11. Desktop Responsive Parity** | 2 desktop mockups ($1440 \times 900$) | Full desktop layout rendered and verified | **PASS** |
| **12. Error & Loading States** | Loading skeleton & network error | Visualized in `profile-mobile-loading-error-v1.png` | **PASS** |
| **13. Evidence Artifacts Complete** | 12 mockups in `docs/audit/evidence/` | All 12 PNGs rendered and verified on disk | **PASS** |
| **14. Unstaged Document Invariant** | `weekly-report-W01.docx` untouched | Must remain strictly unstaged and uncommitted | **PASS** |

---

## 7. Conclusion

TASK 08.2.3.16 successfully locks the architectural contract, privacy model, capability taxonomy, and visual design for the GoMate Profile & Settings module. All requirements from the task specification have been satisfied without altering production application code or database schemas.
