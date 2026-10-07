# GoMate Master Implementation Roadmap V1
## Capability-Driven Engineering Execution Plan & Vertical Slice Specification

- **Document Reference:** `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
- **Scope:** Complete Engineering Implementation Strategy for GoMate (Modules 1 to 14)
- **Status:** **ENGINEERING ROADMAP LOCKED**
- **Date:** October 7, 2026
- **Architecture Baseline:** Locked Global Design Master (`TASK 08.2.4` & `TASK 08.2.4-R1`)
- **Execution Mode:** Planning & Scheduling Specification Only (Zero code changes, zero schema migrations)

---

## 1. Executive Summary & Governance Framework

This master roadmap translates the locked GoMate Global Design Master into an executable, capability-driven engineering plan. It establishes the technical work packages, dependency ordering, database migration sequencing, parallel execution streams, and testing gates necessary to deliver a production-ready application.

### 1.1. Source-of-Truth Hierarchy
In accordance with the governance invariant locked in `TASK 08.2.4-R1`, all work package specifications and implementation priorities strictly adhere to the following hierarchy:

$$\text{Repository Evidence} > \text{Capability Matrix (Capability Level)} > \text{Dependency Register (14 Subsystems)} > \text{Module Summary Prose}$$

1. **Repository Evidence (Supreme Truth):** Code currently running in `apps/backend/`, `apps/mobile/`, and `apps/ai-service/` overrules any documentation claim. A module labeled "RUNTIME BASELINE EXISTS" is explicitly recognized as possessing an operational foundation, **not** as feature-complete.
2. **Capability Matrix at Capability Level:** Authoritative registry of functional and architectural scope per individual capability ID.
3. **Dependency Register:** Authoritative registry of system preconditions, schema models, and service interfaces across all 14 canonical subsystems.
4. **Module Summary Prose:** Informational overview only; carries zero implementation authority.

### 1.2. Audited Capability Registry Reconciliation (90 Dimensions)
The roadmap derives its implementation scope strictly from the canonical 90-capability dimension register:

```
┌────────────────────────────────────────────────────────────────────────┐
│               TIER 1: CURRENT RUNTIME BREAKDOWN (AUDITED)               │
├───────────────────────────────────┬──────────────┬─────────────────────┤
│ Status                            │ Count        │ Action in Roadmap   │
├───────────────────────────────────┼──────────────┼─────────────────────┤
│ CURRENT (Operational Code)        │ 36           │ Preserve & Protect  │
│ PARTIAL (Incomplete / Fragmented) │ 6            │ Complete to Target  │
│ MISSING (Zero Runtime Code)       │ 48           │ Implement if Target │
├───────────────────────────────────┼──────────────┼─────────────────────┤
│ TOTAL AUDITED DIMENSIONS          │ 90           │ 100.0% Audited      │
└───────────────────────────────────┴──────────────┴─────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│               TIER 2: ARCHITECTURAL TARGET BREAKDOWN                   │
├───────────────────────────────────┬──────────────┬─────────────────────┤
│ Status                            │ Count        │ Action in Roadmap   │
├───────────────────────────────────┼──────────────┼─────────────────────┤
│ CURRENT (Retained in Target)      │ 36           │ Retain As-Is        │
│ PRODUCT TARGET (Mandatory Launch) │ 35           │ Full Implementation │
│ FUTURE (Post-MVP Deferred)        │ 9            │ Exclude from MVP    │
│ EXCLUDED (Intentionally Omitted)  │ 10           │ Strictly Forbidden  │
├───────────────────────────────────┼──────────────┼─────────────────────┤
│ TOTAL AUDITED DIMENSIONS          │ 90           │ 100.0% Classified   │
└───────────────────────────────────┴──────────────┴─────────────────────┘
```

**Implementation Scope Invariant:**
- **Roadmap Focus:** Exactly **35 PRODUCT TARGET capabilities** ($6\text{ PARTIAL} + 29\text{ MISSING}$).
- **Preserved Baseline:** **36 CURRENT capabilities** must remain intact with zero regression.
- **Deferred:** **9 FUTURE capabilities** must NOT be scheduled for the initial production launch.
- **Forbidden:** **10 EXCLUDED capabilities** must NEVER be implemented.

---

## 2. Vertical Slice Engineering Architecture

Work packages are structured as **vertical slices** encompassing:
$$\text{Prisma Schema} \longrightarrow \text{NestJS API} \longrightarrow \text{Flutter UI / Riverpod} \longrightarrow \text{Automated Tests} \longrightarrow \text{Runtime Smoke Verification}$$

### Master Work Package Directory

| Work Package ID | Workstream / Subsystem | Primary Capability IDs | Current Runtime | Target Specification | Parallel Class | Estimated Effort |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **WP-AUTH-01** | Secure Storage & Silent Refresh | `14.3`, `14.4` | `PARTIAL` | `PRODUCT TARGET` | Serial Only | M (1.5d) |
| **WP-AUTH-02** | Rate Limiting & Throttling | `14.11` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | S (0.5d) |
| **WP-AUTH-03** | Email Dispatcher & Verification | `14.7` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | M (1.5d) |
| **WP-AUTH-04** | Password Recovery & Change | `14.5`, `14.6` | `MISSING` | `PRODUCT TARGET` | Coordination | M (2.0d) |
| **WP-AUTH-05** | Social OAuth (Google & Apple) | `14.8`, `14.9` | `MISSING` | `PRODUCT TARGET` | Coordination | L (3.0d) |
| **WP-AUTH-06** | Account Linking & Collision | `14.10` | `MISSING` | `PRODUCT TARGET` | Serial Only | M (1.5d) |
| **WP-PROF-01** | Travel Preference Persistence | `13.4` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | M (1.5d) |
| **WP-PROF-02** | Privacy & Visibility Controls | `13.5` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | S (0.5d) |
| **WP-MEDIA-01**| Production Place Media Pipeline | `3.10` | `PARTIAL` | `PRODUCT TARGET` | Parallel Safe | L (3.5d) |
| **WP-SAFE-01** | Safety Modal & Offline Asset Cache | `12.4`, `12.7` | `PARTIAL` | `PRODUCT TARGET` | Parallel Safe | S (0.5d) |
| **WP-MAP-01**  | Offline Basemap Tile Caching | `2.7` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | M (1.5d) |
| **WP-BUDDY-01**| Buddy Discovery & Vector Matching | `7.1`, `7.2` | `MISSING` | `PRODUCT TARGET` | Coordination | L (3.5d) |
| **WP-BUDDY-02**| Masked Profile & Double Opt-In | `7.3`, `7.4` | `MISSING` | `PRODUCT TARGET` | Coordination | M (2.0d) |
| **WP-GROUP-01**| Group Space & Membership Roles | `8.1`, `8.2` | `MISSING` | `PRODUCT TARGET` | Coordination | M (2.0d) |
| **WP-CHAT-01** | WebSocket Chat Timeline | `8.3` | `MISSING` | `PRODUCT TARGET` | Coordination | L (3.5d) |
| **WP-ITIN-01** | Shared Itinerary Board & Voting | `9.1`, `9.2` | `MISSING` | `PRODUCT TARGET` | Coordination | L (3.0d) |
| **WP-ITIN-02** | Concurrency & Conflict Lock | `9.3` | `MISSING` | `PRODUCT TARGET` | Serial Only | M (1.5d) |
| **WP-TRIP-01** | Drag-and-Drop Reorder Persist | `5.4` | `PARTIAL` | `PRODUCT TARGET` | Parallel Safe | S (0.5d) |
| **WP-EXP-01**  | Expense Ledger & Split Logic | `10.1`, `10.2` | `MISSING` | `PRODUCT TARGET` | Coordination | M (2.0d) |
| **WP-EXP-02**  | Debt Simplification & Settlement | `10.3`, `10.4` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | M (1.5d) |
| **WP-REMIND-01**| Local Notifications & Reminders | `11.1–11.3` | `MISSING` | `PRODUCT TARGET` | Parallel Safe | M (1.5d) |
| **WP-WANDY-01**| Guarded Action Bridge (Preview/Confirm)| `4.4` | `MISSING` | `PRODUCT TARGET` | Coordination | M (2.0d) |
| **WP-SEARCH-01**| Global Multi-Destination Search | `1.4` | `PARTIAL` | `PRODUCT TARGET` | Parallel Safe | S (0.5d) |

---

## 3. Detailed Workstream Specifications (Workstreams A through M)

---

### Workstream A: Authentication & Session Hardening
*Primary Objectives: Hardware-backed mobile token persistence, silent refresh with concurrency lock, anti-enumeration recovery, social OAuth, and rate limiting.*

#### WP-AUTH-01: Mobile Hardware-Backed Token Storage & Dio 401 Silent Refresh Queue Lock
- **Capability IDs:** `14.3` (Secure Token Storage), `14.4` (Silent Refresh & Queue Lock)
- **Current Runtime:** `PARTIAL` (Backend issues 15m/7d tokens via `@Post('refresh')`; mobile stores tokens in unencrypted `SharedPreferences` and lacks Dio 401 retry interceptor).
- **Target State:** Tokens encrypted via Keychain/Keystore; Dio interceptor catches 401, locks request queue, triggers refresh, updates tokens, and retries queued requests.
- **Prisma Schema Changes:** None (Tokens are stateless JWTs).
- **Backend NestJS Changes:** Verify `AuthService.refreshToken` invalidates expired refresh tokens and properly generates new token pairs.
- **Flutter Changes:**
  - Add `flutter_secure_storage: ^9.0.0` to `apps/mobile/pubspec.yaml`.
  - Create `SecureTokenStorage` implementing token read/write/clear.
  - Refactor `ApiClient` Dio interceptors: add synchronized `QueuedInterceptor` with lock flag.
- **Testing Requirements:**
  - Unit: Dio interceptor concurrency test with 5 simultaneous requests receiving 401.
  - Integration: Verify only 1 `/auth/refresh` call is made; all 5 requests retry and succeed.
  - Manual: Set access token expiry to 10s in local env; navigate app continuously; verify seamless continuity.
- **Estimated Effort:** 1.5 Days (Backend: 0.25d, Flutter: 0.75d, Testing: 0.5d).
- **Parallel Class:** `SERIAL ONLY` (Modifies `ApiClient` core network infrastructure).

#### WP-AUTH-02: Rate Limiting & Abuse Prevention
- **Capability IDs:** `14.11` (Rate Limiting & Throttling)
- **Current Runtime:** `MISSING` (No throttler configured on NestJS endpoints).
- **Target State:** `@nestjs/throttler` applied globally with strict limits on `/auth/login` (5 req/min), `/auth/register` (3 req/min), and `/auth/forgot-password` (3 req/hour per IP).
- **Prisma Schema Changes:** None.
- **Backend NestJS Changes:**
  - Add `@nestjs/throttler: ^5.0.0` to `apps/backend/package.json`.
  - Register `ThrottlerModule` in `AppModule`.
  - Apply `@UseGuards(ThrottlerGuard)` and `@Throttle()` decorators on auth controller endpoints.
- **Flutter Changes:**
  - Handle `429 Too Many Requests` in `ApiClient` error handler; show localized user-friendly snackbar (*"Quá nhiều yêu cầu. Vui lòng thử lại sau."*).
- **Testing Requirements:**
  - Integration: Issue 6 consecutive requests to `/auth/login`; assert 6th returns HTTP 429.
- **Estimated Effort:** 0.5 Day (Backend: 0.25d, Flutter: 0.1d, Testing: 0.15d).
- **Parallel Class:** `PARALLEL SAFE`.

#### WP-AUTH-03: Transactional Email Dispatcher & Verification Pipeline
- **Capability IDs:** `14.7` (Email Verification Pipeline)
- **Current Runtime:** `MISSING` (`User.isVerified` exists in Prisma; zero email pipeline).
- **Target State:** SendGrid/Resend SMTP client sends verification email with signed link; unverified users see dismissible reminder banner in app shell.
- **Prisma Schema Changes:**
  ```prisma
  model EmailVerificationToken {
    id        String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    userId    String   @map("user_id") @db.Uuid
    tokenHash String   @unique @map("token_hash")
    expiresAt DateTime @map("expires_at") @db.Timestamptz
    createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz
    user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
    @@map("email_verification_tokens")
  }
  ```
- **Backend NestJS Changes:**
  - Add `EmailModule` with SMTP/API transport.
  - Endpoints: `POST /auth/verify-email`, `POST /auth/resend-verification`.
- **Flutter Changes:**
  - Show warning banner on Home screen if `user.isVerified == false` with `[Gửi lại email]`.
  - Handle deep-link `gomate://verify-email?token=...`.
- **Testing Requirements:**
  - Unit: Token expiry (24h) and one-time consumption.
  - Integration: Verification transitions `User.isVerified` from `false` to `true`.
- **Estimated Effort:** 1.5 Days (Backend: 0.75d, Flutter: 0.5d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL SAFE`.

#### WP-AUTH-04: Anti-Enumeration Password Recovery & Authenticated Password Change
- **Capability IDs:** `14.5` (Anti-Enumeration Password Recovery), `14.6` (Authenticated Password Change)
- **Current Runtime:** `MISSING` (Zero password recovery endpoints in backend or screens in Flutter).
- **Target State:** Generic 200 response on forgot password; signed 15m reset token sent via email; authenticated change password enforces canonical regex.
- **Prisma Schema Changes:**
  ```prisma
  model PasswordResetToken {
    id        String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    userId    String    @map("user_id") @db.Uuid
    tokenHash String    @unique @map("token_hash")
    expiresAt DateTime  @map("expires_at") @db.Timestamptz
    usedAt    DateTime? @map("used_at") @db.Timestamptz
    createdAt DateTime  @default(now()) @map("created_at") @db.Timestamptz
    user      User      @relation(fields: [userId], references: [id], onDelete: Cascade)
    @@map("password_reset_tokens")
  }
  ```
- **Backend NestJS Changes:**
  - Endpoints: `POST /auth/forgot-password`, `POST /auth/reset-password`, `PUT /auth/change-password`.
  - Shared validator: `@MinLength(8)`, `@Matches(/((?=.*\d)|(?=.*\W+))(?![.\n])(?=.*[A-Z])(?=.*[a-z]).*$/)`.
- **Flutter Changes:**
  - Screens: `ForgotPasswordScreen`, `ResetPasswordScreen`, `ChangePasswordScreen`.
  - Wire deep link routing for `gomate://reset-password?token=...`.
- **Testing Requirements:**
  - Security: Assert `/auth/forgot-password` returns 200 with identical response time for existing vs non-existent emails.
  - Validation: Assert passwords `< 8` chars or missing uppercase/numbers fail validation.
- **Estimated Effort:** 2.0 Days (Backend: 0.75d, Flutter: 0.75d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Depends on WP-AUTH-03 for email dispatch).

#### WP-AUTH-05: Social OAuth Integration (Google & Apple)
- **Capability IDs:** `14.8` (Google Social OAuth), `14.9` (Apple Social OAuth)
- **Current Runtime:** `MISSING` (Only email/password registration exists).
- **Target State:** Client obtains Google/Apple IDToken; backend verifies token authenticity against provider public keys and signs canonical GoMate JWT.
- **Prisma Schema Changes:**
  ```prisma
  model OAuthAccount {
    id             String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    userId         String   @map("user_id") @db.Uuid
    provider       String   // "google", "apple"
    providerUserId String   @map("provider_user_id")
    createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz
    user           User     @relation(fields: [userId], references: [id], onDelete: Cascade)
    @@unique([provider, providerUserId])
    @@map("oauth_accounts")
  }
  ```
- **Backend NestJS Changes:**
  - Endpoints: `POST /auth/oauth/google`, `POST /auth/oauth/apple`.
  - Verification: `google-auth-library` and `jwks-rsa` for Apple JWT verification.
- **Flutter Changes:**
  - Add `google_sign_in: ^6.2.0`, `sign_in_with_apple: ^6.1.0`.
  - Render branded social buttons on Login and Register screens.
- **Testing Requirements:**
  - Mock integration tests with valid/invalid provider tokens.
- **Estimated Effort:** 3.0 Days (Backend: 1.25d, Flutter: 1.25d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL WITH COORDINATION`.

#### WP-AUTH-06: Account Linking & Collision Resolution
- **Capability IDs:** `14.10` (Account Linking & Collision)
- **Current Runtime:** `MISSING` (No handling of matching emails between OAuth and password accounts).
- **Target State:** If Google/Apple email matches existing password user, prompt user for password to link accounts without creating duplicates.
- **Prisma Schema Changes:** Leverages `OAuthAccount` model from WP-AUTH-05.
- **Backend NestJS Changes:**
  - Endpoint: `POST /auth/link-account` accepting `{ email, password, oauthProvider, oauthToken }`.
- **Flutter Changes:**
  - Screen: `AccountConflictModal` rendering conflict warning and password entry.
- **Testing Requirements:**
  - Integration: Register via email/password $\rightarrow$ attempt Google login with same email $\rightarrow$ expect 409 conflict $\rightarrow$ submit password $\rightarrow$ expect account linked.
- **Estimated Effort:** 1.5 Days (Backend: 0.5d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `SERIAL ONLY` (Directly blocked by WP-AUTH-05).

---

### Workstream B: Profile & Travel Preferences
*Primary Objectives: Allow travelers to persist their travel preferences, pace, and dietary needs, and toggle privacy discovery settings.*

#### WP-PROF-01: Travel Preference Persistence & Validation API
- **Capability IDs:** `13.4` (Travel Preferences Editing)
- **Current Runtime:** `MISSING` (`TravelPreference` exists in Prisma and is read via `GET /users/me`, but `PUT /users/me/preferences` does not exist).
- **Target State:** Full CRUD on user travel preferences with structured validation; interactive preference editor in Flutter settings.
- **Prisma Schema Changes:** Existing `TravelPreference` model is fully adequate. Add index `@@index([userId])`.
- **Backend NestJS Changes:**
  - Add endpoint: `PUT /users/me/preferences` in `UsersController`.
  - DTO: `UpdateTravelPreferencesDto` with `travelStyle`, `budgetMin`, `budgetMax`, `preferredGroup`, `interests`, `avoidances`, `dietaryNeeds`.
- **Flutter Changes:**
  - Transition `settings-mobile-travel-preferences` from read-only chips to interactive multi-select chips.
  - Implement `updatePreferences` in `UserRepository` and `ProfileNotifier`.
- **Testing Requirements:**
  - Integration: `PUT /users/me/preferences` updates fields in PostgreSQL and returns sanitized preferences.
  - Unit: Invalid budget ranges (`budgetMin > budgetMax`) rejected with HTTP 400.
- **Estimated Effort:** 1.5 Days (Backend: 0.5d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL SAFE` (Does not modify shared auth/router files).

#### WP-PROF-02: Privacy & Visibility Controls
- **Capability IDs:** `13.5` (Privacy & Visibility Controls)
- **Current Runtime:** `MISSING` (Profile discovery opt-out toggles are visual-only).
- **Target State:** Persist `isDiscoverable` and `showActivityStatus` on User model; buddy matching excludes non-discoverable travelers.
- **Prisma Schema Changes:**
  - Add fields to `User`: `isDiscoverable Boolean @default(true) @map("is_discoverable")`.
- **Backend NestJS Changes:**
  - Update `PUT /users/me` to accept `isDiscoverable`.
- **Flutter Changes:**
  - Wire toggle switches in `settings-mobile-privacy-v1-r1.png`.
- **Testing Requirements:**
  - Integration: Setting `isDiscoverable = false` hides user from buddy discovery search.
- **Estimated Effort:** 0.5 Day (Backend: 0.2d, Flutter: 0.2d, Testing: 0.1d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream C: Place & Media Pipeline
*Primary Objectives: Production media ingestion, Creative Commons license verification, thumbnail generation, and CDN storage.*

#### WP-MEDIA-01: Production Place Media Pipeline & CC License Provenance
- **Capability IDs:** `3.10` (Production Place Media Pipeline)
- **Current Runtime:** `PARTIAL` (Place detail layout renders hero with fallback image; no dynamic media pipeline).
- **Target State:** Ingest licensed photos (Wikivoyage / Wikimedia Commons / OpenStreetMap); store metadata with attribution and license type; serve WebP thumbnails via CDN/S3.
- **Prisma Schema Changes:**
  ```prisma
  model PlaceMedia {
    id           String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    placeId      String   @map("place_id") @db.Uuid
    url          String
    thumbnailUrl String   @map("thumbnail_url")
    licenseType  String   @map("license_type") // "CC-BY-4.0", "CC-BY-SA-3.0", "Public Domain"
    author       String?
    sourceUrl    String   @map("source_url")
    width        Int?
    height       Int?
    createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
    place        Place    @relation(fields: [placeId], references: [id], onDelete: Cascade)
    @@index([placeId])
    @@map("place_media")
  }
  ```
- **Backend NestJS Changes:**
  - Module: `MediaModule`.
  - Service: `MediaIngestionService` fetching Wikimedia Commons API images by place coordinates/name.
  - Endpoints: `GET /places/:id/media`.
- **Flutter Changes:**
  - Update `PlaceDetailScreen` hero: load from `place.media[0].url` with shimmer placeholder; render attribution caption overlay (`© Author, CC-BY`).
- **Testing Requirements:**
  - Integration: Media endpoint returns verified license attribution and valid image URLs.
  - Non-regression: Places with 0 media continue displaying fallback asset with 0 crashes.
- **Estimated Effort:** 3.5 Days (Backend: 1.5d, Flutter: 1.0d, Testing: 1.0d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream D: Safety & Emergency Hardening
*Primary Objectives: Mandatory confirmation modal prior to native dialer dispatch and bundled offline emergency directory cache.*

#### WP-SAFE-01: Safety Confirmation Safeguard Modal & Bundled Offline Directory Cache
- **Capability IDs:** `12.4` (Emergency Confirmation Modal), `12.7` (Offline Emergency Cache)
- **Current Runtime:** `PARTIAL` (National hotlines and Da Nang *8899 operational in UI and dialer launches, but confirmation modal and offline JSON caching are incomplete).
- **Target State:** Tapping any emergency number opens a clear modal requiring explicit confirmation before calling; directory is bundled as a local asset guaranteeing 100% offline availability.
- **Prisma Schema Changes:** None.
- **Backend NestJS Changes:** None.
- **Flutter Changes:**
  - Bundle `assets/data/emergency_directory.json` containing national numbers (112, 113, 114, 115) and legal citations.
  - Implement `EmergencyConfirmationDialog` with warning icon, title, message, and `[Xác nhận gọi]` / `[Hủy]` CTAs.
  - Update `SafetyNotifier` to load bundled JSON when offline.
- **Testing Requirements:**
  - Widget: Tapping hotline verifies dialog opens; tapping `[Hủy]` cancels dialer dispatch; tapping `[Xác nhận gọi]` verifies `url_launcher` receives `tel:112`.
  - Offline: Disable internet on device; verify `/safety` renders complete directory without errors.
- **Estimated Effort:** 0.5 Day (Flutter: 0.35d, Testing: 0.15d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream E: Map & Basemap Resilience
*Primary Objectives: Cache raster/vector basemap tiles locally to prevent grey tiles in low-connectivity areas.*

#### WP-MAP-01: Offline Basemap Tile Caching & Cache Quota Manager
- **Capability IDs:** `2.7` (Offline Basemap Caching)
- **Current Runtime:** `MISSING` (Tiles stream live from Humanitarian OSM; blocked connections render blank grid).
- **Target State:** Local tile cache storing up to 100MB of tiles in device temporary directory; fallback to cached tiles when offline.
- **Prisma Schema Changes:** None.
- **Backend Changes:** None.
- **Flutter Changes:**
  - Add `flutter_map_cbt_tile_provider` or `cached_network_image` tile provider for `flutter_map`.
  - Implement LRU cache eviction policy capped at 100MB.
- **Testing Requirements:**
  - Widget: Map loads tiles; simulate network cutoff; assert cached viewport displays tiles without network error.
- **Estimated Effort:** 1.5 Days (Flutter: 1.0d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream F: Buddy Matching & Mutual Consent
*Primary Objectives: Travel style compatibility scoring, anonymous discovery grid, masked profiles, and double opt-in consent handshake.*

#### WP-BUDDY-01: Traveler Discovery Grid & Vector Compatibility Matching
- **Capability IDs:** `7.1` (Traveler Discovery Grid), `7.2` (Travel Style Matching Score)
- **Current Runtime:** `MISSING` (`Match` model exists in Prisma; zero backend logic or UI screens).
- **Target State:** Query compatible travelers matching destination and dates; compute vector cosine similarity between `TravelPreference` embeddings; return discovery grid with compatibility percentage.
- **Prisma Schema Changes:**
  - Utilize existing `Match` model. Add `@@index([status])`.
- **Backend NestJS Changes:**
  - Module: `BuddiesModule` (`BuddiesController`, `BuddiesService`).
  - Endpoint: `GET /buddies/discover?destinationId=...&dates=...`.
  - Algorithm: Compute preference overlap (travelStyle, budget, interests) to generate a score (0–100%).
- **Flutter Changes:**
  - Create `BuddyDiscoveryScreen` with destination/style filters and compatibility score badges (`92% Tương thích`).
- **Testing Requirements:**
  - Unit: Compatibility scoring algorithm with identical vs opposing preferences.
  - Integration: Discovery endpoint excludes current user and users with `isDiscoverable = false`.
- **Estimated Effort:** 3.5 Days (Backend: 1.75d, Flutter: 1.25d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Blocked by WP-PROF-01).

#### WP-BUDDY-02: Masked Traveler Profile & Double Opt-In Match Handshake
- **Capability IDs:** `7.3` (Masked Traveler Profile View), `7.4` (Double Opt-In Match Handshake)
- **Current Runtime:** `MISSING` (Zero implementation).
- **Target State:** Public profile view strictly masks phone and private email; sending connection request transitions `Match.status = PENDING`; recipient acceptance transitions `Match.status = ACCEPTED`.
- **Prisma Schema Changes:** Existing `Match` model fully supports `PENDING`, `ACCEPTED`, `REJECTED`, `BLOCKED`.
- **Backend NestJS Changes:**
  - Endpoints: `GET /buddies/:id/profile`, `POST /buddies/:id/request`, `POST /buddies/:id/accept`, `POST /buddies/:id/reject`.
  - Privacy guard: DTO sanitizer strips `phone`, `email`, and exact coordinates.
- **Flutter Changes:**
  - Screen: `BuddyProfileScreen` with `[Gửi lời mời kết nối]`.
  - Screen: `MatchRequestsSheet` reviewing incoming requests.
- **Testing Requirements:**
  - Privacy: Assert `GET /buddies/:id/profile` never contains phone numbers.
  - State machine: Verify `PENDING` $\rightarrow$ `ACCEPTED` handshake.
- **Estimated Effort:** 2.0 Days (Backend: 1.0d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Directly blocked by WP-BUDDY-01).

---

### Workstream G: Group Management & Membership
*Primary Objectives: Group space creation from accepted buddy matches or trip invite codes; role-based membership permissions.*

#### WP-GROUP-01: Group Space Persistence & Role-Based Permissions
- **Capability IDs:** `8.1` (Group Space Creation), `8.2` (Membership Roles: Leader/Member)
- **Current Runtime:** `MISSING` (`Group` and `GroupMember` exist in Prisma; zero backend logic or UI screens).
- **Target State:** Create group from confirmed buddy match or trip; assign `leader` and `member` roles; manage group settings.
- **Prisma Schema Changes:** Existing `Group` and `GroupMember` models are adequate.
- **Backend NestJS Changes:**
  - Module: `GroupsModule` (`GroupsController`, `GroupsService`).
  - Endpoints: `POST /groups`, `GET /groups/:id`, `POST /groups/:id/members`, `DELETE /groups/:id/members/:userId`.
- **Flutter Changes:**
  - Screen: `GroupSpaceScreen` with header, member list, and role badges.
- **Testing Requirements:**
  - Auth: Assert only `leader` can edit group details or remove members.
- **Estimated Effort:** 2.0 Days (Backend: 1.0d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Blocked by WP-BUDDY-02).

---

### Workstream H: Real-Time Group Chat Timeline
*Primary Objectives: WebSocket-based group chat with JWT authentication, message timeline, and immutable sender attribution.*

#### WP-CHAT-01: Real-Time WebSocket Message Timeline & Delivery
- **Capability IDs:** `8.3` (Real-Time Group Chat Timeline)
- **Current Runtime:** `MISSING` (`Message` model exists in Prisma; zero WebSocket gateway or mobile chat view).
- **Target State:** WebSocket gateway (`@nestjs/websockets`) authenticates via JWT; broadcasts messages to joined group rooms; persists to `Message` table; Flutter renders timeline with sender identity. Strictly zero fake online status.
- **Prisma Schema Changes:** Existing `Message` model is adequate.
- **Backend NestJS Changes:**
  - Gateway: `ChatGateway` implementing `OnGatewayConnection` with JWT handshake.
  - Handlers: `joinGroup`, `sendMessage`, `leaveGroup`.
  - Persistence: Store message in PostgreSQL `messages` table before broadcast.
- **Flutter Changes:**
  - Add `web_socket_channel: ^3.0.0`.
  - Screen: `GroupChatTab` inside Group Space with auto-scroll timeline and input bar.
- **Testing Requirements:**
  - WebSocket: Verify unauthorized connections are terminated.
  - End-to-end: Two simulated clients join same group room; message sent by Client 1 arrives at Client 2 in $< 500\text{ms}$.
- **Estimated Effort:** 3.5 Days (Backend: 1.75d, Flutter: 1.25d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Blocked by WP-GROUP-01).

---

### Workstream I: Collaborative Shared Itinerary & Reordering
*Primary Objectives: Multi-user itinerary view with activity voting, conflict resolution lock, and persistent item reordering.*

#### WP-ITIN-01: Collaborative Itinerary Board & Activity Voting
- **Capability IDs:** `9.1` (Collaborative Itinerary Board), `9.2` (Activity Proposal & Voting)
- **Current Runtime:** `MISSING` (Solo trip itinerary exists; group shared itinerary does not).
- **Target State:** Group members view shared itinerary; propose new activities; vote with thumbs up/down; display vote tallies.
- **Prisma Schema Changes:**
  ```prisma
  model ItineraryVote {
    id         String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    itemId     String   @map("item_id") @db.Uuid
    userId     String   @map("user_id") @db.Uuid
    vote       Boolean  // true = upvote, false = downvote
    createdAt  DateTime @default(now()) @map("created_at") @db.Timestamptz
    item       ItineraryItem @relation(fields: [itemId], references: [id], onDelete: Cascade)
    user       User          @relation(fields: [userId], references: [id], onDelete: Cascade)
    @@unique([itemId, userId])
    @@map("itinerary_votes")
  }
  ```
- **Backend NestJS Changes:**
  - Endpoints: `POST /trips/:id/itinerary/items/:itemId/vote`, `GET /trips/:id/itinerary/shared`.
- **Flutter Changes:**
  - Screen: `SharedItineraryTab` with item proposal cards and interactive vote counters.
- **Testing Requirements:**
  - Concurrency: Ensure user can only submit one vote per item (updates on re-vote).
- **Estimated Effort:** 3.0 Days (Backend: 1.5d, Flutter: 1.0d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Blocked by WP-GROUP-01).

#### WP-ITIN-02: Real-Time Itinerary Concurrency & Conflict Lock
- **Capability IDs:** `9.3` (Realtime Conflict Resolution)
- **Current Runtime:** `MISSING` (Zero concurrency controls).
- **Target State:** Leader lock mechanism: when an item is being edited, lock is acquired with a 60s auto-expiry to prevent race conditions.
- **Prisma Schema Changes:**
  - Add to `ItineraryItem`: `lockedBy String? @map("locked_by") @db.Uuid`, `lockedAt DateTime? @map("locked_at") @db.Timestamptz`.
- **Backend NestJS Changes:**
  - Guard: Acquire and release lock endpoints.
- **Flutter Changes:**
  - Show "Đang chỉnh sửa bởi [Tên]" indicator when locked by another user.
- **Testing Requirements:**
  - Integration: Second user receives HTTP 409 Conflict when attempting to edit a locked item.
- **Estimated Effort:** 1.5 Days (Backend: 0.75d, Flutter: 0.5d, Testing: 0.25d).
- **Parallel Class:** `SERIAL ONLY` (Directly blocked by WP-ITIN-01).

#### WP-TRIP-01: Drag-and-Drop Item Reordering Persistence
- **Capability IDs:** `5.4` (Drag-and-Drop Item Reordering)
- **Current Runtime:** `PARTIAL` (Flutter `ReorderableListView` reorders items in local UI state; no backend persistence endpoint).
- **Target State:** Tapping/dragging items calls backend batch reorder endpoint to persist updated `orderIndex` in PostgreSQL.
- **Prisma Schema Changes:** None (`ItineraryItem.orderIndex` already exists).
- **Backend NestJS Changes:**
  - Endpoint: `PUT /trips/:id/itinerary/reorder` accepting `[{ itemId, orderIndex }]`.
- **Flutter Changes:**
  - Hook `onReorder` in `ItineraryTab` to dispatch batch update.
- **Testing Requirements:**
  - Integration: Reorder items $\rightarrow$ reload trip $\rightarrow$ verify order is preserved in database.
- **Estimated Effort:** 0.5 Day (Backend: 0.25d, Flutter: 0.15d, Testing: 0.1d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream J: Shared Expense Ledger
*Primary Objectives: Group bill tracking, equal/custom split calculations, debt simplification matrix, and settlement recording without financial payment processing.*

#### WP-EXP-01: Group Expense Ledger & Multi-Party Split Engine
- **Capability IDs:** `10.1` (Group Expense Ledger), `10.2` (Split Logic: Equal / Custom)
- **Current Runtime:** `MISSING` (Zero expense tracking in database or UI).
- **Target State:** Record shared bills (payer, amount, category, date, receipt note); calculate split amounts across selected participants.
- **Prisma Schema Changes:**
  ```prisma
  model Expense {
    id        String         @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    groupId   String         @map("group_id") @db.Uuid
    payerId   String         @map("payer_id") @db.Uuid
    title     String
    amount    Int            // VND integer
    category  String         // "food", "transport", "hotel", "ticket", "other"
    date      DateTime       @db.Date
    notes     String?
    createdAt DateTime       @default(now()) @map("created_at") @db.Timestamptz
    splits    ExpenseSplit[]
    group     Group          @relation(fields: [groupId], references: [id], onDelete: Cascade)
    payer     User           @relation(fields: [payerId], references: [id])
    @@map("expenses")
  }

  model ExpenseSplit {
    id        String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    expenseId String   @map("expense_id") @db.Uuid
    userId    String   @map("user_id") @db.Uuid
    amount    Int      // Split share in VND integer
    isSettled Boolean  @default(false) @map("is_settled")
    expense   Expense  @relation(fields: [expenseId], references: [id], onDelete: Cascade)
    user      User     @relation(fields: [userId], references: [id])
    @@unique([expenseId, userId])
    @@map("expense_splits")
  }
  ```
- **Backend NestJS Changes:**
  - Module: `ExpensesModule` (`ExpensesController`, `ExpensesService`).
  - Endpoints: `POST /groups/:id/expenses`, `GET /groups/:id/expenses`.
- **Flutter Changes:**
  - Screen: `SharedExpenseTab` inside Group Space with bill listing, total spent, and `[Thêm chi phí]` form.
- **Testing Requirements:**
  - Math: Assert sum of splits equals total bill amount.
- **Estimated Effort:** 2.0 Days (Backend: 1.0d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL WITH COORDINATION` (Blocked by WP-GROUP-01).

#### WP-EXP-02: Minimum Cash Flow Debt Simplification & Settlement Recording
- **Capability IDs:** `10.3` (Debt Simplification Matrix), `10.4` (Peer Settlement Recording)
- **Current Runtime:** `MISSING` (Zero implementation).
- **Target State:** Graph-based minimum cash flow algorithm calculates minimum number of peer settlement transactions; users mark peer debts as settled. Strictly no banking/payment gateway claims.
- **Prisma Schema Changes:**
  ```prisma
  model Settlement {
    id         String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    groupId    String   @map("group_id") @db.Uuid
    debtorId   String   @map("debtor_id") @db.Uuid
    creditorId String   @map("creditor_id") @db.Uuid
    amount     Int      // VND integer
    settledAt  DateTime @default(now()) @map("settled_at") @db.Timestamptz
    notes      String?
    group      Group    @relation(fields: [groupId], references: [id], onDelete: Cascade)
    debtor     User     @relation("debtor", fields: [debtorId], references: [id])
    creditor   User     @relation("creditor", fields: [creditorId], references: [id])
    @@map("settlements")
  }
  ```
- **Backend NestJS Changes:**
  - Endpoint: `GET /groups/:id/settlement-plan`, `POST /groups/:id/settlements`.
  - Algorithm: Greedy settlement matrix resolver minimizing transaction count.
- **Flutter Changes:**
  - Screen: `SettlementPlanSheet` displaying simplified debtor-to-creditor arrows and `[Đã thanh toán]` action.
- **Testing Requirements:**
  - Algorithm: Test N-person circular debts (A owes B, B owes C, C owes A); verify optimal simplified transactions.
- **Estimated Effort:** 1.5 Days (Backend: 0.75d, Flutter: 0.5d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL SAFE` (Blocked by WP-EXP-01).

---

### Workstream K: Scheduling & Reminders
*Primary Objectives: Local notification alerts for trip itinerary items with configurable lead-time offsets and packing checklist reminders.*

#### WP-REMIND-01: Local Notification Scheduler, Offsets & Packing Reminders
- **Capability IDs:** `11.1` (Itinerary Item Reminder Alert), `11.2` (Lead-Time Offset Selector), `11.3` (Packing Checklist Reminder)
- **Current Runtime:** `MISSING` (Zero local notification packages in Flutter).
- **Target State:** Tapping `[Đặt nhắc nhở]` on itinerary item opens modal with offsets (15m, 1h, 1d); schedules local OS notification via `flutter_local_notifications`; persists scheduled state across app restarts.
- **Prisma Schema Changes:** None (Pure client-side OS notification scheduling).
- **Backend Changes:** None.
- **Flutter Changes:**
  - Add `flutter_local_notifications: ^17.2.0`, `timezone: ^0.9.4`.
  - Service: `NotificationService` handling permissions, exact alarm scheduling, and cancellation.
  - Dialog: `ReminderOffsetDialog` with radio options and confirmation.
- **Testing Requirements:**
  - Widget: Schedule reminder with 15m offset; verify scheduled notification ID in `NotificationService`.
  - Restart: Verify scheduled reminders persist after simulated app reload.
- **Estimated Effort:** 1.5 Days (Flutter: 1.0d, Testing: 0.5d).
- **Parallel Class:** `PARALLEL SAFE`.

---

### Workstream L: Guarded Wandy Action Bridge
*Primary Objectives: Enable Wandy to trigger side-effecting operations (modifying trips, setting reminders) strictly through the Intent $\rightarrow$ Preview $\rightarrow$ Explicit Confirmation $\rightarrow$ Execution pattern.*

#### WP-WANDY-01: Guarded Action Bridge (Intent $\rightarrow$ Preview $\rightarrow$ Confirmation)
- **Capability IDs:** `4.4` (Action Preview & Confirmation)
- **Current Runtime:** `MISSING` (Wandy provides conversational advice and place citations; cannot trigger structured trip actions).
- **Target State:** When user asks *"Thêm Chùa Một Cột vào chuyến đi Hà Nội ngày 2"*, Wandy generates structured action intent; client renders preview card with proposed mutation; user explicitly taps `[Xác nhận]` before backend executes. Strictly zero autonomous execution.
- **Prisma Schema Changes:** None.
- **AI-Service Changes:**
  - Add structured tool schema `propose_trip_addition` returning `{ tripId, dayNumber, placeId, activity, estimatedCost }`.
- **Backend NestJS Changes:**
  - Validate action payload against user permissions.
- **Flutter Changes:**
  - Render `ActionPreviewCard` in chat bubble with `[Xác nhận thêm]` and `[Hủy]` buttons.
  - Execute API call upon user tap; append grounded confirmation message.
- **Testing Requirements:**
  - Security: Verify backend rejects action if user is not trip owner.
  - Guardrail: Verify AI engine never mutates trip without explicit client confirmation payload.
- **Estimated Effort:** 2.0 Days (AI Service: 0.5d, Backend: 0.5d, Flutter: 0.75d, Testing: 0.25d).
- **Parallel Class:** `PARALLEL WITH COORDINATION`.

---

### Workstream M: Global Search Discovery
*Primary Objectives: Cross-destination search query across destinations, places, and categories.*

#### WP-SEARCH-01: Cross-Destination Search Entry & Indexing
- **Capability IDs:** `1.4` (Search Bar Entry)
- **Current Runtime:** `PARTIAL` (Search works within active destination on Map; Home search bar is static).
- **Target State:** Search bar on Home queries places and destinations across Vietnam via backend ILIKE / PostGIS query; renders instant suggestion list.
- **Prisma Schema Changes:** Add `@@index([name])` on `Place` and `Destination`.
- **Backend NestJS Changes:**
  - Endpoint: `GET /search?q=...` returning unified `{ destinations: [], places: [] }`.
- **Flutter Changes:**
  - Wire Home search field to trigger `SearchDelegate` or push `/search`.
- **Testing Requirements:**
  - Integration: Querying "Đà Nẵng" returns destination entity and top POIs.
- **Estimated Effort:** 0.5 Day (Backend: 0.25d, Flutter: 0.15d, Testing: 0.1d).
- **Parallel Class:** `PARALLEL SAFE`.

---

## 4. Master Work Package Summary Table

| ID | Work Package Name | Capability IDs | Current | Target | Blocked By | Parallel Class | Schema? | Backend? | Flutter? | AI? | Effort | Thesis Priority | Execution Order |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **WP-AUTH-01** | Secure Storage & Silent Refresh | `14.3, 14.4` | `PARTIAL` | `PRODUCT TARGET` | None | Serial Only | No | Yes | Yes | No | M (1.5d) | Enabler (P3) | **Seq 01** |
| **WP-AUTH-02** | Rate Limiting & Throttling | `14.11` | `MISSING` | `PRODUCT TARGET` | None | Parallel Safe | No | Yes | Yes | No | S (0.5d) | Security (P3)| **Seq 02** |
| **WP-PROF-01** | Travel Preference Persistence | `13.4` | `MISSING` | `PRODUCT TARGET` | None | Parallel Safe | No | Yes | Yes | No | M (1.5d) | Core Thesis (P1)| **Seq 03** |
| **WP-SAFE-01** | Safety Modal & Offline Asset Cache | `12.4, 12.7` | `PARTIAL` | `PRODUCT TARGET` | None | Parallel Safe | No | No | Yes | No | S (0.5d) | Stability (P3) | **Seq 04** |
| **WP-MAP-01**  | Offline Basemap Tile Caching | `2.7` | `MISSING` | `PRODUCT TARGET` | None | Parallel Safe | No | No | Yes | No | M (1.5d) | Stability (P3) | **Seq 05** |
| **WP-MEDIA-01**| Production Place Media Pipeline | `3.10` | `PARTIAL` | `PRODUCT TARGET` | None | Parallel Safe | Yes | Yes | Yes | No | L (3.5d) | Data Quality (P1)| **Seq 06** |
| **WP-TRIP-01** | Drag-and-Drop Reorder Persist | `5.4` | `PARTIAL` | `PRODUCT TARGET` | None | Parallel Safe | No | Yes | Yes | No | S (0.5d) | UX Polish (P2) | **Seq 07** |
| **WP-SEARCH-01**| Global Multi-Destination Search | `1.4` | `PARTIAL` | `PRODUCT TARGET` | None | Parallel Safe | No | Yes | Yes | No | S (0.5d) | Discovery (P2) | **Seq 08** |
| **WP-AUTH-03** | Email Dispatcher & Verification | `14.7` | `MISSING` | `PRODUCT TARGET` | WP-AUTH-01 | Parallel Safe | Yes | Yes | Yes | No | M (1.5d) | Enabler (P3) | **Seq 09** |
| **WP-AUTH-04** | Password Recovery & Change | `14.5, 14.6` | `MISSING` | `PRODUCT TARGET` | WP-AUTH-03 | Coordination | Yes | Yes | Yes | No | M (2.0d) | Security (P3) | **Seq 10** |
| **WP-PROF-02** | Privacy & Visibility Controls | `13.5` | `MISSING` | `PRODUCT TARGET` | WP-PROF-01 | Parallel Safe | Yes | Yes | Yes | No | S (0.5d) | Privacy (P1) | **Seq 11** |
| **WP-WANDY-01**| Guarded Action Bridge | `4.4` | `MISSING` | `PRODUCT TARGET` | WP-AUTH-01 | Coordination | No | Yes | Yes | Yes | M (2.0d) | Core AI (P1) | **Seq 12** |
| **WP-BUDDY-01**| Buddy Discovery & Vector Matching | `7.1, 7.2` | `MISSING` | `PRODUCT TARGET` | WP-PROF-01 | Coordination | No | Yes | Yes | No | L (3.5d) | Core Thesis (P1)| **Seq 13** |
| **WP-BUDDY-02**| Masked Profile & Double Opt-In | `7.3, 7.4` | `MISSING` | `PRODUCT TARGET` | WP-BUDDY-01, WP-PROF-02 | Coordination | No | Yes | Yes | No | M (2.0d) | Privacy (P1) | **Seq 14** |
| **WP-AUTH-05** | Social OAuth (Google & Apple) | `14.8, 14.9` | `MISSING` | `PRODUCT TARGET` | WP-AUTH-01 | Coordination | Yes | Yes | Yes | No | L (3.0d) | Enabler (P3) | **Seq 15** |
| **WP-AUTH-06** | Account Linking & Collision | `14.10` | `MISSING` | `PRODUCT TARGET` | WP-AUTH-05, WP-AUTH-04 | Serial Only | No | Yes | Yes | No | M (1.5d) | Enabler (P3) | **Seq 16** |
| **WP-REMIND-01**| Local Notifications & Reminders | `11.1–11.3` | `MISSING` | `PRODUCT TARGET` | None | Parallel Safe | No | No | Yes | No | M (1.5d) | Utility (P2) | **Seq 17** |
| **WP-GROUP-01**| Group Space & Membership Roles | `8.1, 8.2` | `MISSING` | `PRODUCT TARGET` | WP-BUDDY-02 | Coordination | No | Yes | Yes | No | M (2.0d) | Collab (P2) | **Seq 18** |
| **WP-CHAT-01** | WebSocket Chat Timeline | `8.3` | `MISSING` | `PRODUCT TARGET` | WP-GROUP-01, WP-AUTH-01 | Coordination | No | Yes | Yes | No | L (3.5d) | Collab (P2) | **Seq 19** |
| **WP-ITIN-01** | Shared Itinerary Board & Voting | `9.1, 9.2` | `MISSING` | `PRODUCT TARGET` | WP-GROUP-01 | Coordination | Yes | Yes | Yes | No | L (3.0d) | Collab (P2) | **Seq 20** |
| **WP-ITIN-02** | Concurrency & Conflict Lock | `9.3` | `MISSING` | `PRODUCT TARGET` | WP-ITIN-01 | Serial Only | Yes | Yes | Yes | No | M (1.5d) | Collab (P2) | **Seq 21** |
| **WP-EXP-01**  | Expense Ledger & Split Logic | `10.1, 10.2` | `MISSING` | `PRODUCT TARGET` | WP-GROUP-01 | Coordination | Yes | Yes | Yes | No | M (2.0d) | Collab (P2) | **Seq 22** |
| **WP-EXP-02**  | Debt Simplification & Settlement | `10.3, 10.4` | `MISSING` | `PRODUCT TARGET` | WP-EXP-01 | Parallel Safe | Yes | Yes | Yes | No | M (1.5d) | Collab (P2) | **Seq 23** |

---

## 5. Dual Implementation Perspectives

### 5.1. View A: Product Engineering Order (Technical Dependency Driven)
Organized by technical foundation and unblocking sequences:

```
PHASE 1: CORE RESILIENCE & DATA TRUTH (Weeks 1–3)
├── WP-AUTH-01: Mobile Secure Storage & Dio Silent Refresh Queue Lock
├── WP-AUTH-02: NestJS Throttler Rate Limiting
├── WP-PROF-01: Travel Preference Write Endpoint & Validation
├── WP-SAFE-01: Safety Confirmation Modal & Offline Asset Cache
├── WP-MAP-01:  Offline Basemap Tile Caching
├── WP-MEDIA-01: Production Place Media Pipeline & CC Provenance
└── WP-SEARCH-01: Global Search Indexing

PHASE 2: AUTH RECOVERY & ACTION GUARD (Weeks 4–6)
├── WP-AUTH-03: Transactional Email Verification Pipeline
├── WP-AUTH-04: Anti-Enumeration Password Recovery & Authenticated Change
├── WP-PROF-02: Privacy & Visibility Controls
├── WP-WANDY-01: Guarded Action Bridge (Preview/Confirm)
├── WP-TRIP-01: Drag-and-Drop Reordering Persistence
└── WP-REMIND-01: Local Notification Scheduling

PHASE 3: SOCIAL IDENTITY & BUDDY DISCOVERY (Weeks 7–9)
├── WP-AUTH-05: Social OAuth Integration (Google & Apple)
├── WP-AUTH-06: Account Linking Collision Resolver
├── WP-BUDDY-01: Traveler Discovery Grid & Vector Compatibility Matching
└── WP-BUDDY-02: Masked Profile View & Mutual Consent Handshake

PHASE 4: GROUP COLLABORATION & EXPENSES (Weeks 10–13)
├── WP-GROUP-01: Group Space Persistence & Role-Based Permissions
├── WP-CHAT-01:  Real-Time WebSocket Message Timeline
├── WP-ITIN-01:  Shared Itinerary Board & POI Voting
├── WP-ITIN-02:  Real-Time Concurrency Lock
├── WP-EXP-01:   Shared Expense Ledger & Multi-Party Split
└── WP-EXP-02:   Debt Simplification Matrix & Settlement Recording
```

---

### 5.2. View B: Thesis Value Order (Academic Contribution Driven)
Prioritized according to academic contribution, research evaluation, and scientific defense:

```
TIER 1: CORE THESIS SCIENTIFIC CONTRIBUTIONS (MUST DEFEND)
1. AI Recommendation & Planning Grounding:
   - WP-WANDY-01: Guarded Action Bridge (Preview $\rightarrow$ Confirm execution)
   - WP-PROF-01: Travel Preference Vector Ingestion & Structured Representation
   - WP-TRIP-01: User Feedback & Interactive Plan Mutation Persistence
2. Ground-Truth Data Quality & Provenance Integrity:
   - WP-MEDIA-01: Licensed Media Pipeline & CC Attribution Preservation
   - Provenance Verification (Existing verified OSM/Wikivoyage serving)
3. Privacy-Preserving Social Discovery:
   - WP-BUDDY-01: Vector Compatibility Scoring Algorithm
   - WP-BUDDY-02: Masked Identity & Double Opt-In Mutual Handshake
   - WP-PROF-02: Privacy Discoverability Controls

TIER 2: DISTINCTIVE USER EXPERIENCE (HIGH EVALUATION VALUE)
4. Group Collaborative Dynamics:
   - WP-GROUP-01: Group Graph & Membership Governance
   - WP-ITIN-01: Collaborative Itinerary Proposal & Democratic Voting
   - WP-EXP-01 & WP-EXP-02: Minimum Cash Flow Debt Simplification Algorithm
5. Real-Time Interaction:
   - WP-CHAT-01: Group WebSocket Timeline

TIER 3: SYSTEM INTEGRITY & OPERATIONAL RELIABILITY (HYGIENE FACTORS)
6. Security & Session Continuity:
   - WP-AUTH-01: Silent Refresh Concurrency Lock
   - WP-AUTH-02: Rate Limiting
   - WP-AUTH-03 & WP-AUTH-04: Email Verification & Anti-Enumeration Recovery
   - WP-AUTH-05 & WP-AUTH-06: Social OAuth & Account Linking
7. Offline Resilience & Safety:
   - WP-SAFE-01: Emergency Safeguard Modal & Bundled Asset Directory
   - WP-MAP-01: Basemap Caching
   - WP-REMIND-01: Local Notification Scheduling
```

---

## 6. Thesis MVP Cut Line

To ensure guaranteed completion before academic evaluation and thesis submission, work packages are categorized by necessity:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THESIS MVP CUT-LINE ARCHITECTURE                │
├────────────────────────────────────────────────────────────────────────┤
│ 1. MUST-HAVE FOR THESIS DEFENSE MVP (Core Contribution - 14 Packages)   │
│    • WP-AUTH-01: Silent refresh queue & secure storage                 │
│    • WP-PROF-01: Travel preference persistence                         │
│    • WP-PROF-02: Privacy & discoverability controls                    │
│    • WP-MEDIA-01: Place media ingestion & CC provenance                │
│    • WP-SAFE-01: Safety emergency confirmation modal                   │
│    • WP-WANDY-01: Guarded AI action bridge                             │
│    • WP-TRIP-01: Itinerary reorder persistence                         │
│    • WP-SEARCH-01: Global multi-destination search                     │
│    • WP-BUDDY-01: Traveler discovery & vector compatibility            │
│    • WP-BUDDY-02: Masked profile & double opt-in consent               │
│    • WP-GROUP-01: Group space & member roles                           │
│    • WP-ITIN-01: Collaborative itinerary & voting                      │
│    • WP-EXP-01: Shared expense ledger & split engine                   │
│    • WP-EXP-02: Debt simplification matrix & settlements               │
├────────────────────────────────────────────────────────────────────────┤
│ 2. SHOULD-HAVE FOR PRODUCTION POLISH (Secondary Hygiene - 9 Packages)   │
│    • WP-AUTH-02: Rate limiting & abuse protection                      │
│    • WP-AUTH-03: Transactional email verification                      │
│    • WP-AUTH-04: Password recovery & change endpoints                  │
│    • WP-AUTH-05: Google & Apple social OAuth                           │
│    • WP-AUTH-06: Account linking collision resolution                  │
│    • WP-MAP-01: Offline basemap tile caching                           │
│    • WP-CHAT-01: Real-time WebSocket chat                              │
│    • WP-ITIN-02: Concurrency edit lock                                 │
│    • WP-REMIND-01: Local notification reminders                        │
├────────────────────────────────────────────────────────────────────────┤
│ 3. POST-MVP / FUTURE (Explicitly Deferred - 9 Capabilities)             │
│    • 1.5 Machine Learning personalized rankings                        │
│    • 3.9 User photo upload & community reviews                         │
│    • 4.5 Voice input & speech-to-text audio synthesis                  │
│    • 5.5 Trip archiving & offline PDF export                           │
│    • 6.5 Multi-city TSP route optimization                             │
│    • 8.5 Media & voice message sharing in group chat                   │
│    • 11.4 External calendar sync (Google / iCal)                       │
│    • 14.15 Redis server token blacklist                                │
│    • 14.16 Hardware biometric authentication (`local_auth`)            │
├────────────────────────────────────────────────────────────────────────┤
│ 4. EXCLUDED (Strictly Prohibited - 10 Capabilities)                    │
│    • 2.8 Realtime turn-by-turn GPS navigation                          │
│    • 4.6 Autonomous tool execution without user consent                │
│    • 7.5 Realtime geolocation proximity radar                          │
│    • 8.4 Phantom "Đang hoạt động" presence indicators                  │
│    • 10.5 In-app banking / monetary payment processing                 │
│    • 12.6 Autonomous emergency phone dialing                           │
│    • 13.6 Unverified active presence indicators                        │
│    • 14.12 Facebook social login                                       │
│    • 14.13 Guest / anonymous browse                                    │
│    • 14.14 Remember Me persistent checkbox                             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Execution Phasing & Milestone Gates

```
MILESTONE 1: CORE PLATFORM HARDENING (End of Week 3)
- Gate Criteria:
  1. Dio silent refresh handles concurrent 401s without user disruption.
  2. Travel preferences persist to PostgreSQL via PUT /users/me/preferences.
  3. Emergency calls require confirmation dialog; offline asset directory renders when disconnected.
  4. Place detail renders licensed images with attribution overlay.

MILESTONE 2: AI ACTION GUARD & AUTH MATURITY (End of Week 6)
- Gate Criteria:
  1. Wandy generates preview cards for trip mutations; requires explicit confirmation.
  2. Password recovery returns generic 200 and validates canonical complexity.
  3. Drag-and-drop itinerary reordering persists to database.

MILESTONE 3: SOCIAL TRAVEL & PRIVACY CONTRACT (End of Week 9)
- Gate Criteria:
  1. Buddy discovery ranks travelers by travel preference compatibility score.
  2. Phone numbers are strictly masked on public traveler profiles.
  3. Double opt-in handshake transitions match status from PENDING to ACCEPTED.

MILESTONE 4: COLLABORATIVE GROUP EXPERIENCE (End of Week 13)
- Gate Criteria:
  1. Group space provides unified tabs for Chat, Shared Itinerary, and Shared Expenses.
  2. Shared itinerary items support member voting tallies.
  3. Debt simplification matrix computes optimal settlement plan.
  4. Zero regressions across all 36 CURRENT capabilities.
```

---

## 8. Summary & Transition to DAG

The implementation plan defined in this document is completely capability-driven, mathematically reconciled with the 90-dimension capability matrix, and enforces the source-of-truth hierarchy.

Next immediate companion documents:
1. `docs/roadmap/gomate-implementation-dependency-dag-v1.md` (Concrete Directed Acyclic Graph)
2. `docs/roadmap/gomate-parallel-development-matrix-v1.md` (Multi-Agent Concurrency Strategy)
3. `docs/roadmap/gomate-test-release-gates-v1.md` (Quality Assurance & Non-Regression Gates)
