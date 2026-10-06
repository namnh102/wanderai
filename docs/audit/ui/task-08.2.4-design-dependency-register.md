# GoMate Design Dependency Register: TASK 08.2.4
## Technical Preconditions, Schema Mutations & Execution Dependencies for Future Implementation

- **Document Reference:** `docs/audit/ui/task-08.2.4-design-dependency-register.md`
- **Scope:** Complete Engineering Dependency Register for Future Roadmap (TASK 08.3 Preparation)
- **Status:** **DEPENDENCY AUDIT LOCKED**
- **Date:** October 7, 2026
- **Mode:** Architectural Pre-Implementation Analysis (Zero code written, zero schema changes)

---

## 1. Executive Summary & Purpose

This register catalogues all technical dependencies, schema alterations, external integrations, and architectural preconditions across **14 canonical subsystems** required before future engineering implementation (`TASK 08.3`) can begin. It guarantees that no module will be scheduled for coding until its underlying database models, network contracts, security safeguards, and third-party prerequisites are explicitly accounted for.

### Master Roadmap Source-of-Truth Hierarchy (Invariant for TASK 08.3)
When planning and implementing tasks in `TASK 08.3`, all work items must strictly follow this authority priority:
$$\text{Repository Evidence} > \text{Capability Matrix (Capability Level)} > \text{Dependency Register (14 Subsystems)} > \text{Module Summary Prose}$$

1. **Repository Evidence (Supreme Truth):** Code running in `apps/backend/` and `apps/mobile/` takes precedence over any documentation claim.
2. **Capability-Level Matrix:** Authoritative registry of functional and architectural scope per capability ID.
3. **Dependency Register (14 Subsystems):** Authoritative registry of system preconditions, schema models, and service interfaces across all 14 dependency areas.
4. **Module Summary Prose:** Informational overview only; carries zero implementation authority.

---

## 2. Master Subsystem Dependency Register (14 Canonical Subsystems)

### 1. Place Media Pipeline & Image Provenance
- **Current Runtime Status:** `PARTIAL` (Static URLs in seed; missing dynamic media ingestion).
- **Architectural Target:** `PRODUCT TARGET`
- **Presentation vs. Pipeline Separation:**
  - *Place Detail Header & Layout Presentation:* `CURRENT` in repository runtime with fallback placeholder hero.
  - *Production Place Media Pipeline:* `PARTIAL` $\rightarrow$ `PRODUCT TARGET` (dynamic ingestion, CC license provenance, thumbnail generation, CDN/R2 storage).
- **Prisma Schema Dependencies:**
  - `PlaceMedia` model: `id UUID`, `place_id UUID`, `url TEXT`, `thumbnail_url TEXT`, `license_type VARCHAR`, `author TEXT`, `source_url TEXT`, `created_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Module: `MediaModule`.
  - Service: Image optimization (sharp/WebP), license provenance validator, CDN asset uploader.
- **Frontend Flutter Dependencies:**
  - Package: `cached_network_image: ^3.3.0`.
  - Widgets: Shimmer loading skeleton, fallback category placeholder asset, attribution caption sheet.
- **Third-Party / Infrastructure:** S3-compatible object storage (Cloudflare R2 / AWS S3) or Wikimedia Commons API pipeline.
- **Security & Privacy:** Verification of public domain or Creative Commons license; sanitization of EXIF metadata before storage.

### 2. Travel Preference Persistence & Recommendation Profile
- **Current Runtime Status:** `PARTIAL` (`TravelPreference` model exists in Prisma; missing write endpoint).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - Existing model `TravelPreference` in `schema.prisma`.
  - Needs verification of composite unique constraint: `@@unique([user_id, preference_key])`.
- **Backend NestJS Dependencies:**
  - Endpoint: `PUT /users/me/preferences`.
  - DTO: `UpdateTravelPreferencesDto` validating `travelStyle`, `pace`, `budgetRange`, `dietaryRestrictions`.
- **Frontend Flutter Dependencies:**
  - State: Update `ProfileNotifier` to transition from read-only chips to interactive multi-select chips.
  - Network: Add `updatePreferences` method in `UserRepository`.

### 3. Buddy Matching & Mutual Consent Handshake
- **Current Runtime Status:** `MISSING` (Zero runtime code; complete visual contract in `TASK 08.2.3.7-9`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `BuddyProfile`: `id UUID`, `user_id UUID UNIQUE`, `is_discoverable BOOLEAN`, `bio TEXT`, `languages TEXT[]`.
  - `BuddyMatchRequest`: `id UUID`, `sender_id UUID`, `receiver_id UUID`, `status ENUM('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Module: `BuddyModule`.
  - Algorithm: Vector similarity scoring over `TravelPreference` embeddings.
  - Endpoints: `GET /buddies/discover`, `POST /buddies/request`, `POST /buddies/respond`.
- **Frontend Flutter Dependencies:**
  - Screens: Buddy discovery grid, masked traveler profile, received invitations drawer.
- **Privacy & Security:** Phone number and email strictly masked; zero unconsented direct messaging allowed.

### 4. Group Persistence & Membership Graph
- **Current Runtime Status:** `MISSING` (Zero runtime code; design contract locked in `TASK 08.2.3.10`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `Group`: `id UUID`, `title VARCHAR`, `trip_id UUID NULL`, `created_by UUID`, `created_at TIMESTAMPTZ`.
  - `GroupMember`: `id UUID`, `group_id UUID`, `user_id UUID`, `role ENUM('LEADER', 'MEMBER')`, `joined_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Module: `GroupModule`.
  - Endpoints: `POST /groups`, `GET /groups/:id`, `POST /groups/:id/members`, `DELETE /groups/:id/members/:userId`.
- **Frontend Flutter Dependencies:**
  - Widgets: Group space shell, member avatar stack, role management dialog.

### 5. Group Real-Time Chat Timeline
- **Current Runtime Status:** `MISSING` (Zero runtime code; design contract locked in `TASK 08.2.3.11`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `GroupMessage`: `id UUID`, `group_id UUID`, `sender_id UUID`, `content TEXT`, `created_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Gateway: `@WebSocketGateway({ namespace: '/chat' })` with JWT authentication handshake.
  - Event Listeners: `sendMessage`, `messageReceived`, `typingIndicator`.
- **Frontend Flutter Dependencies:**
  - Package: `web_socket_channel: ^2.4.0`.
  - UI: Reverse `ListView.builder`, optimistic message rendering, timestamp formatting.
- **Data Honesty:** Messages are immutable; timestamps must reflect server UTC receipt.

### 6. Shared Itinerary Collaborative Board
- **Current Runtime Status:** `MISSING` (Design contract locked in `TASK 08.2.3.12`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `SharedItineraryItem`: `id UUID`, `group_id UUID`, `day_number INT`, `place_id UUID`, `order_index INT`, `proposed_by UUID`.
  - `ItineraryVote`: `id UUID`, `item_id UUID`, `user_id UUID`, `vote_type ENUM('UP', 'DOWN')`.
- **Backend NestJS Dependencies:**
  - Service: Realtime event broadcast on item add/reorder/vote.
- **Frontend Flutter Dependencies:**
  - UI: Drag-and-drop board with vote score badge and creator avatar.

### 7. Shared Expense Ledger & Settlement Calculation
- **Current Runtime Status:** `MISSING` (Design contract locked in `TASK 08.2.3.13`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `Expense`: `id UUID`, `group_id UUID`, `payer_id UUID`, `amount DECIMAL(12,2)`, `title VARCHAR`, `category VARCHAR`, `date DATE`.
  - `ExpenseSplit`: `id UUID`, `expense_id UUID`, `user_id UUID`, `amount DECIMAL(12,2)`.
  - `Settlement`: `id UUID`, `group_id UUID`, `debtor_id UUID`, `creditor_id UUID`, `amount DECIMAL(12,2)`, `settled_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Algorithm: Graph debt simplification (min-cash-flow greedy algorithm).
- **Frontend Flutter Dependencies:**
  - UI: Expense ledger list, split breakdown modal, balance summary card.
- **Security & Scope:** Non-financial peer ledger; zero payment gateway or banking integration.

### 8. Scheduling & Local Reminder Delivery
- **Current Runtime Status:** `MISSING` (Design contract locked in `TASK 08.2.3.14`).
- **Architectural Target:** `PRODUCT TARGET`
- **Frontend Flutter Dependencies:**
  - Package: `flutter_local_notifications: ^17.0.0`, `timezone: ^0.9.0`.
  - Services: `NotificationService` handling initialization, channel creation, and exact alarm scheduling (`scheduleExactNotification`).
- **Operating System Permissions:**
  - Android: `SCHEDULE_EXACT_ALARM`, `POST_NOTIFICATIONS` in `AndroidManifest.xml`.
  - iOS: User notification authorization prompt in `Info.plist`.
- **Data Honesty:** Only schedule notifications explicitly requested by the user.

### 9. Safety Emergency Hotline & Offline Asset Storage
- **Current Runtime Status:** `PARTIAL` (Screen renders hotlines; missing offline cache & confirmation modal).
- **Architectural Target:** `PRODUCT TARGET`
- **Frontend Flutter Dependencies:**
  - Package: `url_launcher: ^6.2.0` (for `tel:` protocol).
  - Assets: Bundled JSON file `assets/data/emergency_hotlines_v1.json` containing national and provincial numbers with legal basis metadata.
- **Safeguard Invariant:** Explicit confirmation modal dialog before calling `url_launcher.launchUrl(Uri.parse('tel:...'))`.

### 10. Transactional Email Dispatcher & Verification Pipeline
- **Current Runtime Status:** `MISSING` (Zero runtime code; target contract in `TASK 08.2.3.17-R2`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `EmailVerificationToken`: `id UUID`, `user_id UUID`, `token_hash VARCHAR(64)`, `expires_at TIMESTAMPTZ`, `used_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Provider: Resend SDK (`resend`) or SendGrid.
  - Endpoints: `POST /auth/verify-email`, `POST /auth/resend-verification`.
  - HTML Templates: Verification email template with deep link.

### 11. Anti-Enumeration Password Recovery Pipeline
- **Current Runtime Status:** `MISSING` (Design contract in `TASK 08.2.3.17-R2`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `PasswordResetToken`: `id UUID`, `user_id UUID`, `token_hash VARCHAR(64)`, `expires_at TIMESTAMPTZ`, `used_at TIMESTAMPTZ`.
- **Backend NestJS Dependencies:**
  - Endpoints: `POST /auth/forgot-password` (anti-enumeration 200 OK generic), `POST /auth/reset-password` (one-time 15m token).
- **Frontend Flutter Dependencies:**
  - Screens: Forgot Password screen, Neutral Sent screen, Reset Password screen with deep link listener.

### 12. Social OAuth & Account Linking Collision Resolver
- **Current Runtime Status:** `MISSING` (Design contract in `TASK 08.2.3.17-R2`).
- **Architectural Target:** `PRODUCT TARGET`
- **Prisma Schema Dependencies:**
  - `OAuthAccount`: `id UUID`, `user_id UUID`, `provider ENUM('GOOGLE', 'APPLE')`, `provider_user_id VARCHAR`, `created_at TIMESTAMPTZ`.
  - Constraint: `@@unique([provider, provider_user_id])`.
- **Backend NestJS Dependencies:**
  - Packages: `google-auth-library`, `apple-signin-auth`.
  - Endpoints: `POST /auth/oauth/google`, `POST /auth/oauth/apple`, `POST /auth/link-account`.
- **Frontend Flutter Dependencies:**
  - Packages: `google_sign_in: ^6.2.0`, `sign_in_with_apple: ^5.1.0`.
  - UI: Google and Apple login buttons, Account Conflict linking card.

### 13. Hardware-Backed Secure Storage & Silent Refresh Queue
- **Current Runtime Status:** `PARTIAL` (Plaintext SharedPreferences in mobile runtime).
- **Architectural Target:** `PRODUCT TARGET`
- **Frontend Flutter Dependencies:**
  - Package: `flutter_secure_storage: ^9.0.0`.
  - Integration: Refactor `api_client.dart` with queue-based Dio 401 retry interceptor that acquires a refresh lock, calls `POST /auth/refresh`, and drains queued requests.
- **Security Invariants:** Android KeyStore (AES-256 GCM) & iOS Keychain (`kSecAttrAccessibleAfterFirstUnlock`).

### 14. Map Basemap Tile Caching & Offline Fallback
- **Current Runtime Status:** `MISSING` (Tiles stream live from Humanitarian OSM; gray tiles when network blocked).
- **Architectural Target:** `PRODUCT TARGET`
- **Frontend Flutter Dependencies:**
  - Package: `flutter_map_cache: ^1.5.0` or local tile package reader (`latlong2`).
  - Cache: Cache up to 100MB of vector or raster tiles in temporary app directory.

---

## 3. Dependency Phasing & Execution Order for TASK 08.3

```
┌────────────────────────────────────────────────────────────────────────┐
│              RECOMMENDED EXECUTION PHASING FOR TASK 08.3               │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: CORE INFRASTRUCTURE & AUTH HARDENING                          │
│ • AUTH-01: flutter_secure_storage & Dio silent refresh queue           │
│ • AUTH-02: NestJS Throttler rate limiting                              │
│ • AUTH-03: Transactional email provider & verification pipeline        │
│ • AUTH-04: Forgot / Reset password anti-enumeration endpoints & UI     │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: SOCIAL IDENTITY & PROFILE WRITES                              │
│ • AUTH-05: Google & Apple OAuth SDKs + IDToken verification            │
│ • AUTH-06: Account linking collision resolution engine                 │
│ • PROF-01: PUT /users/me/preferences & responsive settings sync        │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: PLACE ENRICHMENT & SAFETY HARDENING                           │
│ • SAFE-01: Bundled offline emergency JSON asset & confirmation dialog  │
│ • MAP-01: Tile cache integration for offline resilience                │
│ • MEDIA-01: Place image ingestion pipeline & CC licensing check        │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 4: SOCIAL TRAVEL & COLLABORATIVE EXPERIENCES                     │
│ • BUDDY-01: Travel preference vector embedding & discovery grid        │
│ • BUDDY-02: Mutual consent handshake & masked profile exchange         │
│ • GROUP-01: Group space, WebSocket real-time chat & roles              │
│ • EXPENSE-01: Shared expense ledger & min-cash-flow settlement logic   │
│ • REMIND-01: Local notification scheduling for itinerary items         │
└────────────────────────────────────────────────────────────────────────┘
```

**Verdict:** All dependencies across backend, frontend, database, third-party services, and operating systems have been catalogued and phased. GoMate is 100% prepared for future implementation scheduling without architectural unknowns.
