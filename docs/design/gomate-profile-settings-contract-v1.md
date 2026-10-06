# GoMate Profile & Settings — Capability Audit, Privacy Contract & Visual Design V1

**Status:** APPROVED ARCHITECTURAL CONTRACT & DESIGN LOCK (V1)  
**Task:** TASK 08.2.3.16 — GOMATE PROFILE & SETTINGS: CAPABILITY AUDIT, PRIVACY CONTRACT & VISUAL DESIGN V1  
**Date:** October 6, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model User`, `model Profile`, `model TravelPreference`, lines 40–108)
- Backend Source Code: [`apps/backend/src/modules/users/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/users/), [`apps/backend/src/modules/auth/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/auth/)
- Mobile Client Router: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
- Mobile Auth Repository: [`apps/mobile/lib/features/auth/data/auth_repository.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/auth/data/auth_repository.dart)
- Mobile Location Provider: [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart)
- Upstream Design Contracts:
  - [`docs/design/gomate-trip-user-flow-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-user-flow-spec-v1.md)
  - [`docs/design/gomate-group-foundation-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-foundation-contract-v1.md)
  - [`docs/design/gomate-shared-expense-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-expense-contract-v1.md)
  - [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)
- Master Visual Evidence Artifacts (12 Master Artifacts):
  - Mobile Profile Overview: [`profile-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1.png) ($390 \times 844$)
  - Desktop Profile Overview: [`profile-desktop-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1.png) ($1440 \times 900$)
  - Mobile Edit Profile: [`profile-mobile-edit-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1.png) ($390 \times 844$)
  - Mobile Travel Preferences: [`profile-mobile-travel-preferences-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1.png) ($390 \times 844$)
  - Mobile Settings Home: [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) ($390 \times 844$)
  - Desktop Settings Home: [`settings-desktop-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1.png) ($1440 \times 900$)
  - Mobile Privacy Settings: [`settings-mobile-privacy-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1.png) ($390 \times 844$)
  - Mobile Notification Settings: [`settings-mobile-notifications-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1.png) ($390 \times 844$)
  - Mobile Location Settings: [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) ($390 \times 844$)
  - Mobile Account & Security: [`settings-mobile-account-security-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1.png) ($390 \times 844$)
  - Mobile Logout Confirmation: [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) ($390 \times 844$)
  - Mobile Loading & Error States: [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) ($390 \times 844$)

---

## 1. Product Role & Mission

The **GoMate Profile & Settings** module governs the traveler's digital identity, travel preferences, privacy boundaries, application configurations, and session lifecycle.

### Core Architectural Principles:
1. **Clear Data Boundaries:** A traveler's identity is strictly divided into **Private Account Data**, **Public / Buddy Profile Data**, and **Trip Context Data**.
2. **Absolute Isolation of Safety Contacts:** Trusted emergency contacts configured in [`gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md) (`model SafetyContact`) are **STRICTLY PRIVATE** to the account owner and **MUST NEVER** appear on public profiles, Buddy discovery cards, trip member rosters, or group chats.
3. **No Fabricated Capabilities:** Capabilities missing in runtime (such as OS push notifications, server-side token revocation, direct account hard deletion, social follower metrics) are classified honestly and **NEVER** simulated as functional production toggles.
4. **Canonical Navigation Integrity:** Profile and Settings are accessed via the user account avatar/action in the application header or drawer, and are **NOT** added as an invalid 6th root bottom navigation tab.

---

## 2. Three-Tier Privacy Data Model

```
+---------------------------------------------------------------------------------------------------+
|                                 GOMATE THREE-TIER PRIVACY MODEL                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ TIER 1: PRIVATE ACCOUNT DATA ] ──► ONLY Account Owner & System Auth                            |
|  - Email address (nam.le@example.com)                                                             |
|  - Phone number (unless explicitly consented post-match)                                          |
|  - Password hash / Security credentials                                                           |
|  - Active session tokens & devices                                                                |
|  - Safety Trusted Contacts (Mẹ, Bạn thân · Emergency SOS) [STRICT INVARIANT]                      |
|  - Notification preferences & delivery configs                                                    |
|  - Blocked users list & private checkins                                                          |
|                                                                                                   |
|  [ TIER 2: PUBLIC / BUDDY PROFILE DATA ] ──► Compatible Travelers & Buddy Discovery              |
|  - Display Name ("Lê Hoàng Nam")                                                                  |
|  - Avatar image URL                                                                               |
|  - Short traveler bio (max 200 chars)                                                             |
|  - Travel Style (Comfort, Backpacker, Budget, Luxury)                                             |
|  - Travel Interests (Beach, Culture, Cuisine, Nature)                                             |
|  - Languages spoken (Tiếng Việt, English)                                                         |
|  - Nationality / City (Việt Nam)                                                                  |
|                                                                                                   |
|  [ TIER 3: TRIP CONTEXT DATA ] ──► Bound to Specific Trip / Group Membership                      |
|  - Trip Role (HOST, MEMBER)                                                                       |
|  - Itinerary participation & assigned activities                                                  |
|  - Shared Expense ledger participation & balance shares                                           |
|  - Group chat messages & media within the trip channel                                            |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### 2.1. Strict Invariants Locked:
- **Safety Invariant:** `model SafetyContact` records belong exclusively to Tier 1. Zero leakage to social or group endpoints.
- **Matching Boundary:** A mutual Buddy match (`MatchStatus.ACCEPTED`) opens an in-app chat channel; it **DOES NOT** automatically expose the user's phone number or email without a secondary explicit user toggle.
- **Location Boundary:** Joining a trip or group **NEVER** grants other members background or continuous GPS access. Foreground location fixes remain on-demand only.

---

## 3. User & Profile Schema Reality Audit

### 3.1. Database Schema (`schema.prisma` lines 40–108) vs Backend Runtime

| Field / Feature | Prisma Schema | Backend Read (`GET /users/me`) | Backend Write (`PUT /users/me`) | Runtime Classification | Audit Evidence |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`User.id`** | `String @db.Uuid` | Yes | Read-Only | **CURRENT** | Primary key. |
| **`User.email`** | `String @unique` | Yes | Read-Only | **CURRENT** | Unique account login identifier. |
| **`User.passwordHash`** | `String` | Hidden | Auth Register/Login | **CURRENT** | Bcrypt hashed; no change password API. |
| **`User.role`** | `UserRole @default(USER)` | Yes | System Managed | **CURRENT** | `USER`, `ADMIN`, `MODERATOR`. |
| **`User.isVerified`** | `Boolean @default(false)` | Yes | System Managed | **PARTIAL** | DB flag exists; no verification flow. |
| **`User.createdAt`** | `DateTime @db.Timestamptz` | Yes | System Managed | **CURRENT** | Member since timestamp. |
| **`User.deletedAt`** | `DateTime? @db.Timestamptz` | Hidden | None | **PARTIAL** | Schema column only; no soft-delete runtime. |
| **`Profile.displayName`** | `String` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me`. |
| **`Profile.avatar`** | `String?` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me`. |
| **`Profile.bio`** | `String?` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me`. |
| **`Profile.phone`** | `String?` | Yes | No | **PARTIAL** | Selected in `findById`, but omitted from `PUT /users/me`. |
| **`Profile.dateOfBirth`** | `DateTime? @db.Date` | No | No | **SCHEMA GAP** | In schema, but omitted from `findById` and `updateProfile`. |
| **`Profile.nationality`** | `String?` | No | No | **SCHEMA GAP** | In schema, but omitted from `findById` and `updateProfile`. |
| **`Profile.languages`** | `String[] @default([])` | No | No | **SCHEMA GAP** | In schema, but omitted from `findById` and `updateProfile`. |
| **`Gender`** | Absent | Absent | Absent | **MISSING** | Neither schema nor backend supports gender. |
| **`Home City`** | Absent | Absent | Absent | **MISSING** | Schema only has `nationality`. |
| **`TravelPreference`** | 1:1 relation | Read-Only | No | **PARTIAL** | Selected in `findById`; zero update endpoint. |

### 3.2. Form Validation & Data Specification (Edit Profile V1)

| Field | Type | Required | Constraints | UI Presentation | Validation Rule |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **Tên hiển thị (`displayName`)** | String | **Yes** | 2–50 characters, trimmed | Single-line text input | `value.trim().length >= 2 && value.trim().length <= 50` |
| **Giới thiệu (`bio`)** | String | No | Max 200 characters | Multi-line text area (3 rows) | `value.length <= 200` with live counter `N / 200` |
| **Ảnh đại diện (`avatar`)** | String | No | Valid URI or null | Circular avatar with camera icon | HTTP/HTTPS URL or upload reference |
| **Số điện thoại (`phone`)** | String | No | VN mobile 10 digits | Text input with lock badge | `^(03\|05\|07\|08\|09)[0-9]{8}$` |
| **Ngày sinh (`dateOfBirth`)** | Date | No | Age $\ge 16$ years | Date picker (DD/MM/YYYY) | Age calculated $\ge 16$ years old |
| **Quốc tịch (`nationality`)** | String | No | Standard country name | Dropdown / auto-complete | Valid country string (default "Việt Nam") |
| **Ngôn ngữ (`languages`)** | Array | No | Max 5 languages | Multi-select chips with add CTA | Standard language tags (Tiếng Việt, English, etc.) |

---

## 4. Canonical Preference Ownership Model

The GoMate architecture establishes [`model TravelPreference`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L91) as the **single source of truth** for all traveler preferences, shared across AI Itinerary Planning (Task 07.2) and Buddy Matching (future).

```prisma
model TravelPreference {
  id              String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  userId          String      @unique @map("user_id") @db.Uuid
  travelStyle     TravelStyle @default(COMFORT) @map("travel_style")
  budgetMin       Int         @default(0) @map("budget_min")        // VND integer
  budgetMax       Int         @default(10000000) @map("budget_max")  // VND integer
  preferredGroup  GroupSize   @default(SOLO) @map("preferred_group")
  interests       String[]    @default([])  // ["beach","mountain","culture","food"]
  avoidances      String[]    @default([])  // ["crowds","heights"]
  dietaryNeeds    String[]    @default([]) @map("dietary_needs")
  createdAt       DateTime    @default(now()) @map("created_at") @db.Timestamptz
  updatedAt       DateTime    @updatedAt @map("updated_at") @db.Timestamptz

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  @@map("travel_preferences")
}
```

### Enums Locked:
- **`TravelStyle`:** `BACKPACKER` (Phượt), `BUDGET` (Tiết kiệm), `COMFORT` (Thoải mái), `LUXURY` (Sang trọng).
- **`GroupSize`:** `SOLO` (Một mình), `COUPLE` (Cặp đôi), `SMALL_GROUP` (Nhóm nhỏ 3-5), `LARGE_GROUP` (Nhóm lớn 6+), `FAMILY` (Gia đình).

---

## 5. Privacy & Discovery Settings Specification

```
                             Buddy Discovery Toggle
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
                 [ ON ]                                  [ OFF ]
      Profile appears in Buddy Matching       Hidden from Buddy Discovery queries
      Compatible travelers see:               Existing friends/trips unaffected
      - Display Name & Avatar                 Direct invitations still permitted
      - Bio, Interests & Travel Style
      - Compatible Destination/Dates
      - Phone: HIDDEN (Default)
```

### 5.1. Discovery Rules:
1. **Phone Number Masking:** Phone number is **NEVER** public. A setting toggle `Hiển thị số điện thoại sau khi ghép đôi` allows users to opt-in to revealing their phone number to a mutual match; default state is **OFF**.
2. **Social Safety / Block List:** In the absence of a `UserBlock` table in PostgreSQL (audited as a SCHEMA GAP in Task 08.2.3.15), the UI displays `Danh sách người dùng đã chặn (0 người)` as an informational entry point.

---

## 6. Application Settings Architecture

Settings Home is organized into clear operational sections:

```
[ CÀI ĐẶT GOMATE ]
  ├── 1. Tài khoản & Bảo mật (Email, Đổi mật khẩu [API Target], Phiên thiết bị)
  ├── 2. Hồ sơ & Sở thích du lịch (Xem hồ sơ, Chỉnh sửa sở thích TravelPreference)
  ├── 3. Quyền riêng tư & An toàn (Buddy Discovery, Ẩn số điện thoại, Lối tắt SOS)
  ├── 4. Vị trí & Dữ liệu (Quyền GPS tiền cảnh, Minh bạch chia sẻ vị trí)
  ├── 5. Cài đặt thông báo (Hòm thư thông báo trong ứng dụng, Lời nhắc)
  ├── 6. Giao diện & Ứng dụng (Tiếng Việt · Giao diện sáng · GoMate v1.0.0)
  ├── 7. Điều khoản & Hỗ trợ (Chính sách riêng tư, Hướng dẫn sử dụng)
  └── 8. Đăng xuất & Quản lý tài khoản (Đăng xuất [Xác nhận], Xóa tài khoản)
```

---

## 7. Notification Runtime Reality & Settings

### 7.1. Capability Audit:
- **In-App Notification Inbox:** **CURRENT** in schema (`model Notification` in `schema.prisma` lines 371–388 with types `MATCH_REQUEST`, `MATCH_ACCEPTED`, `TRIP_INVITE`, `SAFETY_ALERT`, `NEW_COMMENT`, `NEW_LIKE`, `SYSTEM`).
- **OS Push Notifications (FCM / APNs):** **MISSING**. Zero push SDKs in `pubspec.yaml`, zero push worker in backend `package.json`.
- **Scheduled Push Reminders:** **MISSING**. Cron/worker infrastructure absent (Task 08.2.3.14).

### 7.2. Settings Presentation Honesty:
The notification settings screen displays an informative banner:
> **Hòm thư trong app: Hoạt động** · **Thông báo đẩy (Push OS): Dự kiến V2**  
> *"Hệ thống hiện ghi nhận và lưu trữ thông báo lịch trình & an toàn trong ứng dụng. Tính năng thông báo đẩy màn hình khóa (FCM/APNs) đang được hoàn thiện."*

Toggles represent in-app notification routing preferences rather than non-existent OS push streams.

---

## 8. Location Settings Boundary

Reusing the established truth from [`gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md):
- **Foreground GPS Fix:** **CURRENT** via `geolocator: ^13.0.2` with accuracy grading ($\pm\text{meters}$).
- **Background Location Tracking:** **EXCLUDED / MISSING**. GoMate does not run background tracking services.
- **Continuous Live Location Sharing:** **EXCLUDED / FUTURE SPECIFICATION**.
- **Location Settings Actions:** Displays current permission state (`Đang bật · ±15 m`), links to OS system settings (`openAppSettings()`), and provides a cache clear action `[Xóa bộ nhớ đệm vị trí]`.

---

## 9. Security, Session & Logout Contract

### 9.1. Current Authentication Reality:
- Client-side token storage in `SharedPreferences` (`access_token`, `refresh_token`).
- Token validation via JWT Bearer header (`JwtAuthGuard`).
- **Change Password API:** **MISSING / DESIGN TARGET** (No endpoint in `auth.controller.ts`).
- **Server-Side Token Revocation / Blacklist:** **MISSING**. JWTs expire stateless after 7 days.

### 9.2. Logout Protocol (Locked):
$$\text{User taps [Đăng xuất]} \quad \longrightarrow \quad \text{Modal confirmation} \quad \longrightarrow \quad \text{Clear SharedPreferences} \quad \longrightarrow \quad \text{Set AuthStatus.unauthenticated} \quad \longrightarrow \quad \text{Router redirects to /login}$$

No false claim of server-side revocation is made.

---

## 10. Account Deletion Contract & Anonymization

### 10.1. Relational Integrity Audit:
Hard deleting a user (`DELETE FROM users WHERE id = ...`) will immediately throw a **PostgreSQL Foreign Key Constraint Violation** due to non-cascading relations across 15+ models:
- `Trip`, `TripMember`
- `Review`, `Video`, `Comment`, `Like`, `Save`, `Follow`
- `Match` (sender, receiver)
- `GroupMember`, `Message`
- `SafetyContact`, `SafetyCheckin`
- Shared Expense & Settlement balances (violates accounting audit trail locked in Task 08.2.3.13-R1)

### 10.2. Architecture Verdict:
- **Status:** **POLICY / ARCHITECTURE GAP**.
- **Contract Specification:** Production account deletion must follow the **Soft-Delete + Anonymization (Tombstone) Pattern**:
  1. Set `User.deletedAt = now()`.
  2. Redact personal attributes: `Profile.displayName = "Người dùng GoMate"`, `Profile.avatar = null`, `Profile.bio = null`, `Profile.phone = null`.
  3. Purge sensitive credentials: `User.passwordHash = random_bytes`, `User.email = "deleted_<uuid>@anonymized.gomate"`.
  4. Preserve Shared Expense transaction ledger and trip histories without personal identity linkages.

---

## 11. Navigation & Access Integration

Profile and Settings are **NOT** added to the canonical 5-tab root navigation bar (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn`).

Instead, they are accessed via:
1. **Avatar / User Pill in App Header:** Tapping the avatar navigates to `/profile`.
2. **Settings Shortcut in Profile:** Tapping the gear icon navigates to `/settings`.
3. **Deep Routes:**
   - `/profile` (Profile Overview)
   - `/profile/edit` (Edit Profile)
   - `/profile/preferences` (Travel Preferences)
   - `/settings` (Settings Home)
   - `/settings/privacy` (Privacy & Buddy Settings)
   - `/settings/notifications` (Notification Settings)
   - `/settings/location` (Location Transparency)
   - `/settings/security` (Account & Security)

---

## 12. Master Visual Mockup Evidence (12 Artifacts)

All 12 mockups were rendered via headless Microsoft Edge browser at native specifications and verified in `docs/audit/evidence/ui-08.2.3.16/`:

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

## 13. Current vs. Future Capability Matrix (24 Dimensions)

| Dimension | Current Codebase Status | Architectural Contract V1 | Future Target |
| :--- | :---: | :---: | :--- |
| **1. User Entity & Auth Identity** | **CURRENT** | **LOCKED** | Standard JWT authentication via NestJS |
| **2. Display Name & Avatar** | **CURRENT** | **LOCKED** | Full CRUD via `users.service.ts` |
| **3. Traveler Bio** | **CURRENT** | **LOCKED** | Updatable via `PUT /users/me` |
| **4. Phone Number Storage** | **PARTIAL** | **LOCKED** | Stored in `Profile`, needs update API endpoint |
| **5. Phone Number Privacy** | **DESIGN LOCKED** | **TIER 1 (PRIVATE)** | Never public; explicit post-match consent |
| **6. Nationality & Languages** | **SCHEMA GAP** | **DESIGN TARGET** | Add to `UsersService.updateProfile` |
| **7. Date of Birth / Age** | **SCHEMA GAP** | **DESIGN TARGET** | Age verification $\ge 16$ years old |
| **8. Travel Preferences (Style/Interests)**| **PARTIAL** | **LOCKED** | `model TravelPreference` single source of truth |
| **9. Budget Range** | **PARTIAL** | **LOCKED** | `budgetMin` / `budgetMax` in integer VND |
| **10. Preferred Group Size** | **SCHEMA ONLY** | **DESIGN TARGET** | Connect `preferredGroup` enum to UI |
| **11. Safety Contacts Isolation** | **LOCKED** | **STRICT INVARIANT** | Never shown on profile or Buddy matching |
| **12. Buddy Discovery Toggle** | **MISSING** | **DESIGN TARGET** | Opt-in/opt-out flag for recommendation pool |
| **13. Post-Match Privacy Scope** | **DESIGN LOCKED** | **TIER 2 BOUNDARY** | Matched users get chat channel, NOT raw phone |
| **14. Location Foreground Fix** | **CURRENT** | **LOCKED** | `geolocator` fix with accuracy radius |
| **15. Background Location Tracking** | **EXCLUDED** | **STRICTLY PROHIBITED**| No continuous tracking without user presence |
| **16. Live Location Streaming** | **MISSING** | **EXCLUDED FROM V1** | Future ephemeral opt-in live sharing |
| **17. In-App Notification Store** | **CURRENT** | **LOCKED** | `model Notification` in PostgreSQL |
| **18. OS Push Notifications (FCM/APNs)**| **MISSING** | **FUTURE SPECIFICATION**| Requires Firebase integration in V2 |
| **19. App Settings UI** | **MISSING** | **DESIGN LOCKED** | Grouped settings tree defined in V1 |
| **20. Password Change Feature** | **MISSING** | **DESIGN TARGET** | Add `PUT /auth/change-password` |
| **21. Client Logout Flow** | **CURRENT** | **LOCKED** | Remove tokens from `SharedPreferences` |
| **22. Server Token Revocation** | **MISSING** | **FUTURE SPECIFICATION**| Stateless JWT; token blacklist in Redis for V2 |
| **23. Account Hard Deletion** | **BLOCKED** | **POLICY / ARCH GAP** | FK restrict on 15+ models prevents hard delete |
| **24. Soft-Delete & Anonymization** | **DESIGN LOCKED** | **DESIGN TARGET** | Set `deletedAt`, sanitize PII, preserve ledgers |
