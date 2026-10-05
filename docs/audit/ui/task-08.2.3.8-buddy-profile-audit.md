# GoMate Buddy Profile — Capability Audit & Architecture Report (TASK 08.2.3.8)

**Status:** APPROVED ARCHITECTURAL AUDIT & UX SPECIFICATION  
**Task:** TASK 08.2.3.8 — GOMATE BUDDY PROFILE UX, PRIVACY & CONNECTION ENTRY CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Audit Overview

TASK 08.2.3.8 audits and specifies the UX contract, privacy boundaries, and connection entry point for the **Buddy Profile** (`Hồ sơ bạn đồng hành`) in GoMate.

The Buddy Profile is a **Public Pre-Match Profile** reached from Buddy Discovery when a traveler evaluates a potential companion. The screen must maintain strict data honesty, preserve privacy tiers, prevent algorithmic fabrication, and establish clear boundaries between public evaluation and private post-connection access.

### Key Audit Findings:
1. **Schema Reality (`schema.prisma`):**
   - Model `Profile` contains: `userId`, `displayName`, `avatar`, `bio`, `phone`, `dateOfBirth`, `nationality`, `languages`.
   - Model `TravelPreference` contains: `userId`, `travelStyle`, `budgetMin`, `budgetMax`, `preferredGroup`, `interests`, `avoidances`, `dietaryNeeds`.
   - Model `User` contains: `id`, `email`, `role`, `isVerified`, `deletedAt`.
   - Model `Match` contains: `senderId`, `receiverId`, `status` (`PENDING`, `ACCEPTED`, `REJECTED`), `score`, `explanation`.
2. **API Reality:**
   - Backend `users.controller.ts` exposes only `GET /users/me` and `PUT /users/me`.
   - **Zero public profile endpoints exist** (e.g. `GET /users/:id/public-profile` is missing).
   - **Zero match request endpoints exist** (e.g. `POST /buddy/matches` is missing).
3. **Safety & Privacy Reality:**
   - `User.isVerified` means **email/account verification only**. It does not represent KYC, CCCD, or legal identity verification.
   - `Profile` has **no city, province, hometown, or residence field**.
   - `UserBlock` and `UserReport` models are **missing from schema**.
   - `isDiscoverable` flag is **missing from schema**.

---

## 2. Code, API & Data Inspection Details

### 2.1. Prisma Schema Verification (`apps/backend/prisma/schema.prisma`)
* **User Model:**
  ```prisma
  model User {
    id            String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    email         String    @unique
    passwordHash  String    @map("password_hash")
    role          UserRole  @default(USER)
    isVerified    Boolean   @default(false) @map("is_verified")
    createdAt     DateTime  @default(now()) @map("created_at") @db.Timestamptz
    updatedAt     DateTime  @updatedAt @map("updated_at") @db.Timestamptz
    deletedAt     DateTime? @map("deleted_at") @db.Timestamptz
    profile       Profile?
    preferences   TravelPreference?
    ...
  }
  ```
  *Audit Semantics:* `isVerified` is set to `true` upon email verification link confirmation in auth module. It has zero relation to identity verification.

* **Profile Model:**
  ```prisma
  model Profile {
    id          String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    userId      String    @unique @map("user_id") @db.Uuid
    displayName String    @map("display_name")
    avatar      String?
    bio         String?
    phone       String?
    dateOfBirth DateTime? @map("date_of_birth") @db.Date
    nationality String?
    languages   String[]  @default([])
    createdAt   DateTime  @default(now()) @map("created_at") @db.Timestamptz
    updatedAt   DateTime  @updatedAt @map("updated_at") @db.Timestamptz
    user        User      @relation(fields: [userId], references: [id], onDelete: Cascade)
    @@map("profiles")
  }
  ```
  *Audit Semantics:* Missing fields: `city`, `province`, `hometown`, `residence`, `isDiscoverable`.

* **TravelPreference Model:**
  ```prisma
  model TravelPreference {
    id              String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    userId          String      @unique @map("user_id") @db.Uuid
    travelStyle     TravelStyle @default(COMFORT) @map("travel_style")
    budgetMin       Int         @default(0) @map("budget_min")
    budgetMax       Int         @default(10000000) @map("budget_max")
    preferredGroup  GroupSize   @default(SOLO) @map("preferred_group")
    interests       String[]    @default([])
    avoidances      String[]    @default([])
    dietaryNeeds    String[]    @default([]) @map("dietary_needs")
    ...
  }
  ```

* **Match Model:**
  ```prisma
  model Match {
    id         String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    senderId   String      @map("sender_id") @db.Uuid
    receiverId String      @map("receiver_id") @db.Uuid
    status     MatchStatus @default(PENDING)
    score      Float?
    explanation String?
    createdAt  DateTime    @default(now()) @map("created_at") @db.Timestamptz
    ...
  }
  ```

---

## 3. Privacy Boundary & Field Classification Audit

```
============================================================
FIELD PRIVACY CLASSIFICATION AUDIT
============================================================

1. PUBLIC PRE-MATCH (Safe for unauthenticated discovery & profile viewing):
   - Profile.displayName: Screen name
   - Profile.avatar: Profile picture or initials
   - User.isVerified: Labeled "Tài khoản đã xác minh"
   - Profile.nationality: Country (e.g. "Việt Nam")
   - Profile.languages: Spoken languages (e.g. "Tiếng Việt, English")
   - Profile.bio: User description (fallback: "Người dùng chưa thêm phần giới thiệu.")
   - TravelPreference.travelStyle: Enum badge (e.g. "Thoải mái (Comfort)")
   - TravelPreference.preferredGroup: Enum badge (e.g. "Nhóm nhỏ (2–4 người)")
   - TravelPreference.interests: Up to 5 interest tags
   - Trip context: Destination city ("Đà Nẵng") & Overlapping dates ("15–18/10")

2. PRIVATE POST-MATCH ONLY (Locked behind mutual consent):
   - Profile.phone: Personal contact number
   - Itinerary.items: Detailed minute-by-minute itinerary & hotel pins
   - Group / Message: In-app direct communication channel

3. NEVER EXPOSE (Strictly prohibited from UI):
   - User.email: Account authentication credential
   - User.passwordHash: Security credential
   - Profile.dateOfBirth: Exact date of birth (must be masked to Age Band)
   - Real-time GPS: Live user coordinates
   - SafetyContact: Emergency SOS contacts
   - Internal UUIDs: id, userId, senderId, receiverId

4. UNSUPPORTED FIELDS (Must not be fabricated):
   - City / Hometown / Residence: Not in schema; eliminated from UI
   - Fake Match Scores: Banned; replaced by explainable reasons
   - Social Popularity / Star Ratings: Banned; no dating metrics
============================================================
```

---

## 4. Comprehensive Capability Matrix

| Capability | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Public Buddy Profile** | Missing | Missing | `Profile` & `TravelPreference` | `buddy-mobile-profile-v1.png` | **DESIGN TARGET** | Audited schema; public read API missing. |
| **Profile Bio** | `GET/PUT /users/me` | Basic profile | `Profile.bio` (String?) | Bio snippet or fallback | **CURRENT (DB) / PARTIAL (API)**| Bio persisted in DB; public endpoint missing. |
| **Age Band Privacy** | Missing | Missing | `Profile.dateOfBirth` | 5-year age bands | **DESIGN TARGET** | Computed server-side; exact DOB masked. |
| **Travel Preferences**| Missing | Missing | `TravelPreference` | Style, group, budget tier | **PARTIAL (DB Only)** | Enums in DB; public read API missing. |
| **Compatibility Reasons**| Missing | Missing | `Match.explanation` | Checkmarked factual list | **DESIGN TARGET** | Visualized in `buddy-mobile-profile-v1.png`. |
| **Private Contact Unlock**| Missing | Missing | `Profile.phone` | Locked section pre-match | **PARTIAL (DB Only)** | Model has phone; unlock logic requires match state. |
| **Trip Detail Sharing**| `POST :id/members`| Missing | `TripMember` | Post-match sharing | **CURRENT (API) / PARTIAL (UI)**| API exists for invite by email; UI pending. |
| **Connection Request** | Missing | Missing | `Match` (status `PENDING`) | Primary CTA button | **PARTIAL (DB Only)** | DB model exists; request API controller missing. |
| **Block User** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **Report User** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 5. Visual Artifacts Verification (2 Master Mockups)

Per task instructions, exactly **two** master mockups were produced and verified at `docs/audit/evidence/ui-08.2.3.8/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`buddy-mobile-profile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.8/buddy-mobile-profile-v1.png) | Mobile | $390 \times 844$ | 1. Status bar & App Bar with back navigation + "Báo cáo" action.<br>2. Identity card: avatar (HN), "Lê Hoàng Nam", "Tài khoản đã xác minh" badge, "25–29 tuổi · Việt Nam", languages.<br>3. Compatibility card: "Phù hợp với chuyến đi Đà Nẵng (15–18/10)" with 3 factual checkmarked reasons.<br>4. About section: raw bio text without fabrication.<br>5. Travel preferences: "Thoải mái (Comfort)", "Nhóm nhỏ (2–4 người)", "~2.0M / ngày", 4 interest chips.<br>6. Locked privacy card: phone and hourly itinerary clearly locked.<br>7. Fixed bottom action bar: "Gửi lời mời kết nối" CTA + safety helper text: "Người này chỉ được kết nối với bạn sau khi họ chấp nhận lời mời."<br>8. Zero browser scrollbars, clean pixel rendering. | **PASS** |
| [`buddy-desktop-profile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.8/buddy-desktop-profile-v1.png) | Desktop | $1440 \times 900$ | 1. Canonical 5-tab root navigation (Khám phá, Bản đồ, Wandy AI, Chuyến đi [active], An toàn).<br>2. Breadcrumb: Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành > Hồ sơ Lê Hoàng Nam.<br>3. 2-Column workstation layout:<br>   - Left ($440\text{px}$): Identity (80dp avatar, verified badge, age band, nationality, bio box), Locked privacy card (phone, itinerary, GPS), Safety action box.<br>   - Right ($900\text{px}$): Compatibility hero card, Preferences & experience tags, Action footer with "Quay lại danh sách" and "Gửi lời mời kết nối".<br>4. Zero browser scrollbars, pixel-perfect workstation view. | **PASS** |

---

## 6. Architecture & Implementation Dependencies

1. **Backend Public Profile Route (Target):**
   - Endpoint: `GET /users/:id/public-profile`
   - Response DTO: Filtered payload exposing only Tier 1 public fields and computed Age Band. Must never return `email`, `phone`, `dateOfBirth`, or `passwordHash`.
2. **Backend Match Request Route (Target):**
   - Endpoint: `POST /buddy/matches`
   - Body: `{ receiverId: string, contextTripId: string, message?: string }`
   - Business Logic: Validates eligibility, creates `Match` with status `PENDING`, emits push notification.
3. **Safety System Migration (Mandatory Prerequisite):**
   - Migration adding `UserBlock` and `UserReport` tables to Prisma schema.
   - Migration adding `isDiscoverable Boolean @default(false)` to `Profile`.

---

## 7. Design Acceptance Gate (TASK 08.2.3.8)

- [x] **Profile schema audited:** Complete field-by-field matrix documented.
- [x] **Public fields traceable:** All displayed fields map to real schema properties.
- [x] **Unsupported hometown absent:** No fabricated cities; backed by `Profile.nationality`.
- [x] **Account verification semantics correct:** Strictly labeled `"Tài khoản đã xác minh"`, never `"Đã xác minh danh tính"`.
- [x] **Age band preserved:** Exact DOB hidden; `25–29 tuổi` displayed.
- [x] **GPS hidden:** Real-time coordinates completely absent.
- [x] **Detailed itinerary hidden:** Minute-by-minute timeline locked.
- [x] **Private contact locked:** Phone number displayed in locked section with unlock condition.
- [x] **Never-expose fields documented:** Email, passwordHash, GPS, EmergencyEvent, internal UUIDs prohibited.
- [x] **No fake match percentage:** Banned percentage scores; explainable reasons with checkmarks locked.
- [x] **Compatibility reasons explainable:** Factual, human-readable criteria specified.
- [x] **Connection CTA marked DESIGN TARGET:** DB model exists, API route pending.
- [x] **Match lifecycle deferred to 08.2.3.9:** Pending/Accept/Reject lifecycle cleanly separated.
- [x] **Mobile master created:** `buddy-mobile-profile-v1.png` rendered and verified ($390 \times 844$).
- [x] **Desktop master created:** `buddy-desktop-profile-v1.png` rendered and verified ($1440 \times 900$).
- [x] **Canonical 5-root IA preserved:** Desktop top nav matches authoritative 5 root tabs.
- [x] **Vietnamese-first:** Canonical Vietnamese copy across all components.
- [x] **Accessibility defined:** Touch targets $\ge 44\text{dp}$, semantic labels, WCAG AA contrast.
- [x] **No source changes:** 0 lines modified in `apps/`.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** Contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
