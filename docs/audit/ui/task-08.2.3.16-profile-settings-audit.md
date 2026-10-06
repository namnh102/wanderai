# GoMate Profile & Settings — Capability Audit, Privacy Contract & Visual Design V1 (TASK 08.2.3.16 · R1 Calibrated)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK (R1 CALIBRATED)  
**Task:** TASK 08.2.3.16 / TASK 08.2.3.16-R1 — GOMATE PROFILE & SETTINGS: CAPABILITY AUDIT, PRIVACY CONTRACT & VISUAL DESIGN V1  
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
  - R1 Correction Audit: [`docs/audit/ui/task-08.2.3.16-r1-runtime-truthfulness-correction.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.16-r1-runtime-truthfulness-correction.md)
- Master Visual Evidence Artifacts (12 Current Master Artifacts in `docs/audit/evidence/ui-08.2.3.16/`):
  1. Mobile Profile Overview R1: [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  2. Desktop Profile Overview R1: [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) ($1440 \times 900$) [Supersedes V1]
  3. Mobile Edit Profile R1: [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  4. Mobile Travel Preferences R1: [`profile-mobile-travel-preferences-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  5. Mobile Settings Home: [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) ($390 \times 844$) [Current Master]
  6. Desktop Settings Home R1: [`settings-desktop-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1-r1.png) ($1440 \times 900$) [Supersedes V1]
  7. Mobile Privacy Settings R1: [`settings-mobile-privacy-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  8. Mobile Notification Settings R1: [`settings-mobile-notifications-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  9. Mobile Location Settings: [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) ($390 \times 844$) [Current Master]
  10. Mobile Account & Security R1: [`settings-mobile-account-security-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  11. Mobile Logout Confirmation: [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) ($390 \times 844$) [Current Master]
  12. Mobile Loading & Error States: [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) ($390 \times 844$) [Current Master]

---

## 1. Executive Summary & Audit Verdict (R1 Revision)

TASK 08.2.3.16 (and R1 revision) establishes the comprehensive capability audit, architectural contract, privacy model, and visual design baseline for the **GoMate Profile & Settings** experience.

### Key Audit Findings & Architectural Verdicts:
1. **Separation of Concerns & Three-Tier Privacy Model:**
   - Identity is rigorously divided into:
     - **Tier 1 (Private Account Data):** Email, phone, security credentials, active sessions, notification routing preferences, and **Safety Trusted Contacts** (`model SafetyContact`).
     - **Tier 2 (Public / Buddy Profile Data):** Display name, avatar, bio, travel style, travel interests, languages, nationality.
     - **Tier 3 (Trip Context Data):** Trip role, activity participation, expense ledger shares.
2. **Strict Invariant — Absolute Isolation of Safety Contacts:**
   - Trusted emergency contacts configured in [`gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md) (`model SafetyContact`) belong **EXCLUSIVELY to Tier 1**.
   - Under NO circumstances may safety contacts leak into public traveler profiles, Buddy discovery cards, trip member rosters, or group chats.
3. **Buddy Matching & Block List Privacy Boundary:**
   - A mutual Buddy match creates an in-app chat channel. It **DOES NOT** expose raw phone numbers or email addresses without secondary explicit user opt-in.
   - In the absence of a `UserBlock` model in PostgreSQL, empty-state counts like `"0 người"` are rejected. Copy honestly states: `"Chặn & báo cáo: Chức năng quản lý danh sách chặn đang được hoàn thiện"`.
4. **Canonical Preference Ownership Model:**
   - [`model TravelPreference`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L91) in PostgreSQL is the **single canonical source of truth** for all travel preferences (travel style, budget range, preferred group size, interests, avoidances, dietary needs).
   - Serves both the AI Itinerary Planning Engine (Task 07.2) and the future Buddy Matching engine.
5. **Notification Reality & Honest UI Presentation:**
   - **Notification Schema / Data Model:** `PARTIAL / SCHEMA PRESENT` (`model Notification` in PostgreSQL).
   - **Notification Runtime Inbox:** `MISSING / DESIGN TARGET` (Zero NestJS controller, zero NestJS service, zero mobile UI inbox binding).
   - **OS Push Notifications (FCM / APNs):** `MISSING / FUTURE`.
   - **UI Copy:** Purged developer terms (`Dự kiến V2`, `FCM/APNs`, `API target`). Uses neutral copy: `"Thông báo trong ứng dụng: Đang được hoàn thiện"` and `"Thông báo đẩy trên thiết bị: Chưa hỗ trợ"`. Controls rendered as informational status rows.
6. **Account Verification & Role Honesty:**
   - `User.isVerified` is a database flag only without an implemented verification pipeline (`PARTIAL`). The `"Đã xác thực"` badge is **OMITTED ENTIRELY** from user-facing screens.
   - Inferred personality badges (`"Du khách thích khám phá"`) are removed; static role `"Thành viên"` (mapped from `UserRole.USER`) is retained.
7. **Profile Completeness Metric:**
   - Search across code confirmed 0 occurrences of completion score algorithms (`profileCompletion`, `completeness`, `65%`). The `"65%"` fake metric and Wandy/buddy matching claims were replaced with neutral copy: *"Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate."*
8. **Edit Profile Write-Boundary Separation (Option A Master):**
   - Only `displayName`, `avatar`, and `bio` are writable via `PUT /users/me`.
   - `phone` is read-only; non-readable metadata (`dateOfBirth`, `nationality`, `languages`) are omitted from runtime display with notice: *"Một số thông tin tài khoản bổ sung chưa khả dụng trong phiên bản hiện tại."*
9. **Password & Account Deletion Reality:**
   - Password status: `"Mật khẩu tài khoản: Đã thiết lập"` (bcrypt wording purged).
   - Change password API is `MISSING / DESIGN TARGET`; enabled button removed; shows `"Chưa hỗ trợ trong phiên bản hiện tại"`.
   - Account deletion: Hard delete blocked by 15+ FK RESTRICT constraints (`POLICY / ARCHITECTURE GAP`). Active deletion CTA and fake support buttons removed; UI displays pure informational notice: *"Quy trình quản lý tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng."* Soft-delete + anonymization is an architecture target in documentation only.
10. **Navigation Integrity:**
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
   - Root `ShellRoute` has exactly 5 bottom navigation tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn`).
   - Profile route (`/profile`) is defined as a standalone sub-route, accessed from the user area.
   - **Verdict:** Complies with navigation integrity; no 6th tab added.
2. **Push Notifications:**
   - Search for `firebase_messaging`, `flutter_local_notifications`, or `push_notifications` in `pubspec.yaml` yields **0 matches**.
   - **Verdict:** Push notification runtime is 100% missing.
3. **Session Management (`apps/mobile/lib/features/auth/data/auth_repository.dart`):**
   - `logout()` executes `_sharedPreferences.remove('access_token')` and `_sharedPreferences.remove('refresh_token')`.
   - **Verdict:** Client token erasure is CURRENT; server revocation is MISSING.

---

## 3. Comprehensive Capability Classification Matrix (R1 Calibrated)

| Capability / Field | Codebase Status | Classification | Architectural Verdict & Remediation |
| :--- | :---: | :---: | :--- |
| **User ID & Email** | Prisma & NestJS | **CURRENT** | Primary key and login identifier. Read-only in profile. |
| **Password & Bcrypt Hash** | Prisma & Auth | **CURRENT** | Hashed in PostgreSQL. Displayed as `"Đã thiết lập"`. |
| **User Role** | Prisma Enum | **CURRENT** | `USER`, `ADMIN`, `MODERATOR`. Rendered as static `"Thành viên"`. |
| **Account Verification (`isVerified`)** | Prisma Column | **PARTIAL** | DB flag only; NO verification workflow. Verification badge OMITTED from UI. |
| **Display Name** | Prisma & API | **CURRENT** | Full CRUD supported via `PUT /users/me`. Required (2–50 chars). |
| **Avatar Persistence & URL Update** | Prisma & API | **PARTIAL** | DB column & `PUT /users/me` avatar URL string update. Device photo picker & multipart upload are MISSING (DESIGN TARGET). |
| **Traveler Bio** | Prisma & API | **CURRENT** | Updatable via `PUT /users/me`. Max 200 characters with counter. |
| **Phone Number (Storage)** | Prisma Column | **PARTIAL** | Selected in read, but omitted from update DTO (Read-only in UI). |
| **Phone Number (Privacy)** | Design Contract | **TIER 1 (PRIVATE)** | Strictly masked. Never shown publicly; explicit post-match opt-in. |
| **Date of Birth / Age** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection (Read-only). |
| **Nationality** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection (Read-only). |
| **Languages Spoken** | Prisma Column | **SCHEMA GAP** | Present in `model Profile`, omitted from backend DTO & selection (Read-only). |
| **Gender / Pronouns** | None | **MISSING** | Neither schema nor backend supports gender. Omitted from V1. |
| **Home City** | None | **MISSING** | Not in schema. Replaced by `nationality` in V1. |
| **Travel Style (Enum)** | Prisma Enum | **PARTIAL** | `TravelStyle` (`BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`). |
| **Budget Min / Max** | Prisma Int | **PARTIAL** | Integer VND amounts in `TravelPreference`. |
| **Preferred Group Size** | Prisma Enum | **SCHEMA GAP** | `GroupSize` (`SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY`). |
| **Travel Interests & Avoidances** | Prisma Arrays | **PARTIAL** | `String[]` arrays in `TravelPreference`. |
| **Dietary Needs** | Prisma Array | **SCHEMA GAP** | `dietaryNeeds` in schema; needs UI chip integration. |
| **TravelPreference Update API** | Backend API | **DESIGN TARGET** | Need `PUT /users/me/preferences` endpoint. |
| **Safety Trusted Contacts** | Prisma Model | **TIER 1 STRICT** | `model SafetyContact`. Isolated from public profile & buddy matching. |
| **Buddy Discovery Preference** | Backend API | **DESIGN TARGET** | Informational preference target (`Đang hoàn thiện`). |
| **Post-Match Privacy Scope** | Design Contract | **TIER 2 BOUNDARY**| Matching gives in-app chat; does NOT reveal phone/email. |
| **UserBlock Model** | Absent | **SCHEMA GAP** | Copy: `"Chặn & báo cáo: Đang hoàn thiện"` (No fake "0 người"). |
| **User Online Presence / Status** | None | **MISSING / EXCLUDED** | Zero presence service/heartbeat. "Đang hoạt động" presence claim strictly purged from UI. |
| **Foreground GPS Fix** | Mobile Geolocator | **CURRENT** | On-demand GPS fix with accuracy circle ($\pm\text{meters}$). |
| **Background Location Tracking** | Client/Server | **EXCLUDED** | GoMate does not run background tracking services. |
| **Continuous Live Location Sharing** | Client/Server | **EXCLUDED / FUTURE**| Prohibited in V1. Ephemeral opt-in sharing reserved for V2. |
| **Notification Schema Store** | Prisma Model | **PARTIAL** | `model Notification` exists in PostgreSQL. |
| **Notification Inbox Runtime** | Mobile/Backend | **MISSING / DESIGN TARGET**| Needs NestJS controller/service & mobile inbox UI. |
| **OS Push Notifications (FCM/APNs)**| Client/Server | **MISSING / FUTURE**| Labeled `"Chưa hỗ trợ"` in UI. |
| **Scheduled Push Reminders** | Backend Cron | **MISSING** | Cron/worker infrastructure absent. |
| **Password Change Feature** | Backend API | **DESIGN TARGET** | Labeled `"Chưa hỗ trợ trong phiên bản hiện tại"`. |
| **Client Token Erasure (Logout)** | Mobile SharedPreferences | **CURRENT** | Purges access & refresh tokens on confirmation. |
| **Server-Side Token Revocation** | Backend Redis | **MISSING / FUTURE**| Stateless JWTs. Blacklist table/cache reserved for V2. |
| **Direct Account Hard Deletion** | PostgreSQL FK | **BLOCKED (GAP)** | 15+ FK RESTRICT constraints block `DELETE FROM users`. |
| **Soft-Delete + Anonymization** | Design Contract | **DESIGN TARGET** | Architecture target in docs only; UI shows neutral support help. |

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
1. **Safety Contacts Isolation:** Under no circumstances may `model SafetyContact` records be serialized in `/users/me/profile`, `/buddy/discover`, `/trips/:id/members`, or `/groups/:id/members`. Emergency contacts are used solely for the SOS dispatch flow.
2. **Matching Boundary:** A mutual Buddy match creates a chat channel; it **DOES NOT** expose raw phone numbers or email addresses without secondary explicit consent.

---

### 4.2. Canonical Travel Preference Model (`model TravelPreference`)

[`model TravelPreference`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L91) is the unified preference engine for both AI Itinerary Planning (Task 07.2) and Buddy Matching (future).
- Enums enforced: `TravelStyle` (`BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`), `GroupSize` (`SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY`).
- Budget stored as integer VND (not floating point) to prevent rounding discrepancies with Shared Expense (Task 08.2.3.13-R1).

---

### 4.3. Notification Capability Reality (In-App vs. Push OS)

$$\textbf{In-App Inbox Persistence} \quad \ne \quad \textbf{OS Push Notification Delivery}$$

- **Repository Truth:**
  - `model Notification` exists in PostgreSQL (`id`, `userId`, `type`, `title`, `body`, `isRead`).
  - Neither Firebase Cloud Messaging (FCM) nor Apple Push Notification service (APNs) is configured.
  - Zero push tokens (`pushToken`, `fcmToken`) are stored on `model User`.
- **UI Honesty Protocol:**
  - Notification Settings screen displays neutral copy:
    > **Thông báo trong ứng dụng: Đang được hoàn thiện** · **Thông báo đẩy trên thiết bị: Chưa hỗ trợ**  
    > *"Hệ thống đang hoàn thiện hòm thư lưu trữ thông báo lịch trình và cảnh báo an toàn. Thiết bị hiện chưa hỗ trợ nhận thông báo đẩy khi đóng ứng dụng."*
  - Controls are presented as informational rows rather than non-functional operational switches.

---

### 4.4. Geolocation Privacy & Tracking Boundaries
- `user_location_provider.dart` uses `geolocator: ^13.0.2` for **on-demand foreground fixes only**.
- GoMate **NEVER** tracks user location in the background.
- Joining a trip or group **NEVER** broadcasts real-time GPS coordinates to other members.

---

### 4.5. Session Lifecycle & Logout Protocol
- Access tokens expire after 7 days; refresh tokens are stored in `SharedPreferences`.
- Logout protocol:
  $$\text{User taps [Đăng xuất]} \quad \longrightarrow \quad \text{Modal confirmation} \quad \longrightarrow \quad \text{Purge SharedPreferences} \quad \longrightarrow \quad \text{Set AuthStatus.unauthenticated} \quad \longrightarrow \quad \text{Navigate to /login}$$
- The confirmation dialog states that the session on this device will end. No false claims of server-side revocation are made.

---

### 4.6. Account Deletion Architectural Assessment
- Hard deleting a user throws immediate FK constraint violations across 15+ models and corrupts Shared Expense accounting records.
- Direct hard deletion is classified as a **POLICY / ARCHITECTURE GAP**.
- UI displays pure informational notice: *"Quy trình quản lý tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng."* (No unbacked customer support contact link, button, or badge).
- Soft-delete + anonymization remains an **ARCHITECTURE TARGET** in documentation only.

---

## 5. Master Visual Mockup Evidence Matrix (12 Master Artifacts · R1 Calibrated)

All 12 current master visual mockups were rendered via headless Microsoft Edge browser (`--headless=new`, `--force-device-scale-factor=1`) at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.16/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit (R1 Calibrated) | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `Hồ sơ cá nhân` + gear icon.<br>2. User avatar (N), display name "Lê Hoàng Nam", static role "Thành viên" (mapped from USER). Inferred personality badge removed.<br>3. Bio text.<br>4. Neutral informational card "Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate." (fake 65% and Wandy/buddy matching claims removed).<br>5. Personal info & travel style (Comfort) + interest chips.<br>6. Actions: `[Chỉnh sửa hồ sơ]` + `[Quyền riêng tư]`.<br>7. Canonical 5-tab bottom navigation. | **CURRENT MASTER** |
| [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) | Desktop | $1440 \times 900$ | 1. Top nav: GoMate logo + badge `Hồ sơ du khách` + 5 canonical tabs + User pill.<br>2. 3-column workspace ($320\text{px} + 680\text{px} + 340\text{px}$).<br>3. Col 1: Profile summary, avatar, static role "Thành viên", fake "Đã xác thực" removed, completion card with neutral copy "Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate.", quick menu.<br>4. Col 2: Bio, basic info (Họ tên, SĐT [Riêng tư], Vai trò; unsupported "Đang hoạt động" presence claim completely removed), TravelPreference details (Comfort, 1M-10M VND, 3-5 group, interest chips).<br>5. Col 3: Buddy Matching card ("Đang hoàn thiện"), Privacy Shield guarantee ("Mặc định ẩn"), Security shortcuts. | **CURRENT MASTER** |
| [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) | Mobile | $390 \times 844$ | **Option A Master Baseline (R1.2 Calibrated):**<br>1. App bar: `< Chỉnh sửa hồ sơ` (duplicate AppBar [Lưu] button removed).<br>2. Avatar presentation without false camera upload affordance (native picker / multipart upload is DESIGN TARGET).<br>3. Writable Section (PUT /users/me): Tên hiển thị (2-50 chars) + Giới thiệu (78/200 chars).<br>4. Read-Only Section: Số điện thoại (Riêng tư); non-readable metadata (DOB, nationality, languages) omitted with honest note: "Một số thông tin tài khoản bổ sung chưa khả dụng trong phiên bản hiện tại.".<br>5. Clear note: Additional info managed at account level.<br>6. Single Primary CTA: `[Lưu thay đổi hồ sơ]`. | **CURRENT MASTER** |
| [`profile-mobile-travel-preferences-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1-r1.png) | Mobile | $390 \times 844$ | **Option A Read-Only Master Baseline:**<br>1. App bar `< Hồ sơ`, `Sở thích du lịch` (no Save button).<br>2. Informational note: "Sở thích du lịch: Chức năng chỉnh sửa sở thích đang được hoàn thiện."<br>3. TravelStyle cards (Thoải mái displayed read-only).<br>4. GroupSize chips (Nhóm nhỏ 3-5 displayed read-only).<br>5. Budget range: 1.000.000 đ – 10.000.000 đ.<br>6. Interest chips: Biển, Văn hóa, Ẩm thực, Chụp ảnh (no toggle affordances).<br>7. Read-only presentation; no Save CTA. | **CURRENT MASTER** |
| [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Cài đặt`.<br>2. User header card with avatar & `Hồ sơ ›` link.<br>3. Grouped sections: Tài khoản & Bảo mật, Trải nghiệm du lịch, Quyền riêng tư & An toàn, Ứng dụng.<br>4. Red logout action: `[Đăng xuất tài khoản]`.<br>5. Canonical 5-tab bottom navigation. | **CURRENT MASTER** |
| [`settings-desktop-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1-r1.png) | Desktop | $1440 \times 900$ | 1. Top nav: GoMate logo + badge `Hồ sơ du khách` + 5 canonical tabs + User pill.<br>2. 2-column workspace ($320\text{px} + 1020\text{px}$).<br>3. Left menu: Settings categories.<br>4. Right panel: Account info card (fake "Đã xác thực" removed), Password card ("Đã thiết lập", change password unavailable), Privacy (Buddy matching "Đang hoàn thiện", Phone "Mặc định ẩn") & Location summary, Danger zone (Account management pure informational guidance, no fake CTA/button). | **CURRENT MASTER** |
| [`settings-mobile-privacy-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `< Quyền riêng tư`.<br>2. Buddy discovery: "Chức năng khám phá bạn đồng hành đang được hoàn thiện" (no fake "Mặc định mở") & Phone visibility: "Mặc định ẩn" (no "Luôn bảo mật").<br>3. Location boundary disclosure card (no auto sharing).<br>4. Social safety: Chặn & báo cáo (Đang hoàn thiện, no fake "0 người"), Báo cáo vi phạm.<br>5. SOS security commitment banner (trusted contacts isolated). | **CURRENT MASTER** |
| [`settings-mobile-notifications-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `< Cài đặt thông báo`.<br>2. Honest runtime status: `Thông báo trong ứng dụng: Đang được hoàn thiện` vs `Thông báo đẩy trên thiết bị: Chưa hỗ trợ` (dev terms FCM/APNs, V2 purged).<br>3. Informational status rows: ALL rows marked "Đang hoàn thiện" including safety alerts (no "Luôn bật" runtime claim).<br>4. Reminders section (Schedule reminders marked "Đang hoàn thiện"). | **CURRENT MASTER** |
| [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Vị trí & Dữ liệu`.<br>2. Foreground permission status (±15 m · Tốt) + `[Mở Cài đặt hệ thống]` button.<br>3. Location validity principles: Foreground only, no background tracking, no continuous live broadcast.<br>4. Location cache clear action. | **CURRENT MASTER** |
| [`settings-mobile-account-security-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `< Tài khoản & Bảo mật`.<br>2. Account info: Email (fake "Đã xác thực" removed), Joined date, Role (Thành viên USER).<br>3. Password: "Đã thiết lập" (bcrypt detail purged); Change password: "Chưa hỗ trợ trong phiên bản hiện tại" (enabled button & API target purged).<br>4. Danger Zone card: Pure informational notice "Quy trình quản lý tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng" (fake action button & contact link purged). | **CURRENT MASTER** |
| [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) | Mobile | $390 \times 844$ | 1. Dark semi-transparent modal overlay ($65\%$ opacity).<br>2. Centered confirmation dialog with logout icon.<br>3. Title `Đăng xuất khỏi GoMate?`.<br>4. Clear session expiration warning.<br>5. Primary CTA `[Đăng xuất]` (Red) + Secondary CTA `[Hủy bỏ]`. | **CURRENT MASTER** |
| [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) | Mobile | $390 \times 844$ | 1. Dual demonstration layout.<br>2. Top card: Loading skeleton with animated placeholders.<br>3. Bottom card: Network error state with warning icon, error explanation, and `[Thử lại]` action button.<br>4. Canonical 5-tab bottom navigation. | **CURRENT MASTER** |

### Superseded V1 Artifacts (Preserved on Disk for Audit History):
- `profile-mobile-overview-v1.png` → Superseded by `profile-mobile-overview-v1-r1.png`
- `profile-desktop-overview-v1.png` → Superseded by `profile-desktop-overview-v1-r1.png`
- `profile-mobile-edit-v1.png` → Superseded by `profile-mobile-edit-v1-r1.png`
- `profile-mobile-travel-preferences-v1.png` → Superseded by `profile-mobile-travel-preferences-v1-r1.png`
- `settings-desktop-home-v1.png` → Superseded by `settings-desktop-home-v1-r1.png`
- `settings-mobile-privacy-v1.png` → Superseded by `settings-mobile-privacy-v1-r1.png`
- `settings-mobile-notifications-v1.png` → Superseded by `settings-mobile-notifications-v1-r1.png`
- `settings-mobile-account-security-v1.png` → Superseded by `settings-mobile-account-security-v1-r1.png`

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
| **7. Notification Reality** | Honest Push OS disclosure | Notification schema present; runtime inbox missing; OS push unsupported. | **PASS** |
| **8. Location Tracking Reality** | Foreground only | Background & continuous sharing strictly excluded | **PASS** |
| **9. Session & Logout Protocol** | Clear token purge flow | Modal confirmation + SharedPreferences purge | **PASS** |
| **10. Account Deletion Reality** | FK RESTRICT gap addressed | Neutral customer support guidance in UI | **PASS** |
| **11. Desktop Responsive Parity** | 2 desktop mockups ($1440 \times 900$) | Full desktop layout rendered and verified | **PASS** |
| **12. Error & Loading States** | Loading skeleton & network error | Visualized in `profile-mobile-loading-error-v1.png` | **PASS** |
| **13. Evidence Artifacts Complete** | 12 master mockups in `docs/audit/evidence/` | All 12 current master PNGs rendered and verified on disk | **PASS** |
| **14. Unstaged Document Invariant** | `weekly-report-W01.docx` untouched | Must remain strictly unstaged and uncommitted | **PASS** |

---

## 7. Demo Data Governance Policy

All visual values in mockups (*Lê Hoàng Nam*, *nam.le@example.com*, *0912 345 678*, *15/09/2026*, *Việt Nam*, sample bio, sample travel style):
- **CLASSIFICATION:** **VISUAL DEMO DATA ONLY**.
- **RESTRICTION:** Provided strictly for typography, contrast, and layout verification.
- **INVARIANT:** Mockup data does **NOT** constitute evidence of runtime persistence or production capability. Under no circumstances may an audit classify a feature as `CURRENT` based on mockup demo data.
