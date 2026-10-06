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
- Master Visual Evidence Artifacts (12 Master Artifacts · R1.1 Calibrated):
  - Mobile Profile Overview R1: [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Desktop Profile Overview R1: [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) ($1440 \times 900$) [Supersedes V1]
  - Mobile Edit Profile R1: [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Mobile Travel Preferences R1: [`profile-mobile-travel-preferences-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Mobile Settings Home: [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) ($390 \times 844$) [Current Master]
  - Desktop Settings Home R1: [`settings-desktop-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1-r1.png) ($1440 \times 900$) [Supersedes V1]
  - Mobile Privacy Settings R1: [`settings-mobile-privacy-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Mobile Notification Settings R1: [`settings-mobile-notifications-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Mobile Location Settings: [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) ($390 \times 844$) [Current Master]
  - Mobile Account & Security R1: [`settings-mobile-account-security-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1-r1.png) ($390 \times 844$) [Supersedes V1]
  - Mobile Logout Confirmation: [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) ($390 \times 844$) [Current Master]
  - Mobile Loading & Error States: [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) ($390 \times 844$) [Current Master]

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
| **`User.role`** | `UserRole @default(USER)` | Yes | System Managed | **CURRENT** | `USER`, `ADMIN`, `MODERATOR`. Rendered as static "Thành viên". |
| **`User.isVerified`** | `Boolean @default(false)` | Yes | System Managed | **PARTIAL** | DB flag only; NO verification workflow. Verification badge OMITTED from UI. |
| **`User.createdAt`** | `DateTime @db.Timestamptz` | Yes | System Managed | **CURRENT** | Member since timestamp. |
| **`User.deletedAt`** | `DateTime? @db.Timestamptz` | Hidden | None | **PARTIAL** | Schema column only; no soft-delete runtime. |
| **`Profile.displayName`** | `String` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me` (Writable). |
| **`Profile.avatar`** | `String?` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me` (Writable). |
| **`Profile.bio`** | `String?` | Yes | Yes | **CURRENT** | Updatable via `PUT /users/me` (Writable). |
| **`Profile.phone`** | `String?` | Yes | No | **PARTIAL** | Selected in `findById`, but omitted from `PUT /users/me` (Read-Only). |
| **`Profile.dateOfBirth`** | `DateTime? @db.Date` | No | No | **SCHEMA GAP** | In schema, but omitted from backend select/update (Read-Only in UI). |
| **`Profile.nationality`** | `String?` | No | No | **SCHEMA GAP** | In schema, but omitted from backend select/update (Read-Only in UI). |
| **`Profile.languages`** | `String[] @default([])` | No | No | **SCHEMA GAP** | In schema, but omitted from backend select/update (Read-Only in UI). |
| **`Gender / Pronouns`** | Absent | Absent | Absent | **MISSING** | Neither schema nor backend supports gender. |
| **`Home City`** | Absent | Absent | Absent | **MISSING** | Schema only has `nationality`. |
| **`TravelPreference`** | 1:1 relation | Read-Only | No | **PARTIAL** | Selected in `findById`; zero update endpoint. |

### 3.2. Form Validation & Write-Boundary Specification (Edit Profile V1-R1 Option A Master)

Under **Option A Master Baseline**, the Edit Profile UI strictly separates writable fields from read-only account metadata. The Save button persists **only** the writable fields supported by `PUT /users/me`:

1. **Writable Fields (Persisted via `PUT /users/me`):**
   - **Tên hiển thị (`displayName`)**: String, **Bắt buộc**, 2–50 ký tự (`value.trim().length >= 2 && value.trim().length <= 50`).
   - **Giới thiệu ngắn (`bio`)**: String, Tùy chọn, tối đa 200 ký tự với bộ đếm ký tự trực tiếp (`N / 200`).
   - **Ảnh đại diện (`avatar`)**: URL ảnh hoặc tải lên; hiển thị khung tròn có icon chỉnh sửa.

2. **Readable & Non-Readable Account Metadata (R1.1 Truth):**
   - **Số điện thoại (`phone`)**: Đọc được từ `GET /users/me`; hiển thị dưới dạng thẻ chỉ đọc (Read-Only) kèm huy hiệu `Riêng tư`.
   - **Ngày sinh, Quốc tịch, Ngôn ngữ**: Không được đọc qua `GET /users/me` hiện tại. Không hiển thị các giá trị demo này như dữ liệu tài khoản runtime.
   - **Ghi chú minh bạch**: *"Một số thông tin tài khoản bổ sung chưa khả dụng trong phiên bản hiện tại."*

---

## 4. Canonical Preference Ownership & Write-Boundary Model

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

### 4.1. Write-Boundary Status & UI Contract:
- **Runtime Classification:** **PARTIAL / READ CURRENT**, **WRITE = DESIGN TARGET**.
- `TravelPreference` được đọc thành công qua `GET /users/me` (`include: { travelPreferences: true }`), nhưng hiện tại **KHÔNG CÓ** endpoint `PUT /users/me/preferences`.
- Giao diện `profile-mobile-travel-preferences-v1-r1.png` hiển thị các sở thích dưới dạng **thông tin chỉ đọc (Read-Only)**, loại bỏ toàn bộ tương tác chọn lựa có thể gây hiểu nhầm, và loại bỏ nút `[Lưu]`.
- Thông báo trung thực: *"Sở thích du lịch: Chức năng chỉnh sửa sở thích đang được hoàn thiện."* (Tuyệt đối không dùng thuật ngữ kỹ sư như API, backend, V2).

### 4.2. Enums Locked:
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

### 5.1. Discovery Rules & Honest Controls:
1. **Phone Number Masking:** Phone number is **NEVER** public. Post-match phone sharing is an informational preference target; default state is **MẶC ĐỊNH ẨN (HIDDEN)** (not "Luôn bảo mật" as future post-match consent may allow sharing).
2. **Buddy Discovery Toggle:** In the absence of a preference persistence API, Buddy Discovery is presented as an informational preference target with status:
   `Tìm bạn đồng hành: Chức năng khám phá bạn đồng hành đang được hoàn thiện`
   (The claim "Mặc định mở" is removed as no persistence or matching runtime exists).
3. **Social Safety / Block List:** In the absence of a `UserBlock` table in PostgreSQL (audited as a SCHEMA GAP in Task 08.2.3.15), the UI displays:
   `Chặn & báo cáo: Chức năng quản lý danh sách chặn đang được hoàn thiện`
   (Fabrication of an empty-state count like "0 người" is strictly rejected).

---

## 6. Application Settings Architecture

Settings Home is organized into clear operational sections:

```
[ CÀI ĐẶT GOMATE ]
  ├── 1. Tài khoản & Bảo mật (Email, Mật khẩu tài khoản [Đã thiết lập], Phiên thiết bị)
  ├── 2. Hồ sơ & Sở thích du lịch (Xem hồ sơ, Thông tin sở thích TravelPreference)
  ├── 3. Quyền riêng tư & An toàn (Buddy Discovery [Đang hoàn thiện], Ẩn số điện thoại, Lối tắt SOS)
  ├── 4. Vị trí & Dữ liệu (Quyền GPS tiền cảnh, Minh bạch chia sẻ vị trí)
  ├── 5. Cài đặt thông báo (Thông báo trong ứng dụng, Lời nhắc)
  ├── 6. Giao diện & Ứng dụng (Tiếng Việt · Giao diện sáng · GoMate v1.0.0)
  ├── 7. Điều khoản & Hỗ trợ (Chính sách riêng tư, Hướng dẫn sử dụng)
  └── 8. Đăng xuất & Quản lý tài khoản (Đăng xuất [Xác nhận], Quản lý tài khoản)
```

---

## 7. Notification Runtime Reality & Settings

### 7.1. Capability Audit & Classification:
- **Notification Schema / Data Model:** **PARTIAL / SCHEMA PRESENT** (`model Notification` in `schema.prisma` lines 371–388).
- **Notification Runtime Inbox:** **MISSING / DESIGN TARGET** (Zero `NotificationController`, zero `NotificationService`, zero mobile inbox UI binding).
- **OS Push Notifications (FCM / APNs):** **MISSING / FUTURE** (Zero push SDKs in `pubspec.yaml`, zero push worker in backend).
- **Scheduled Push Reminders:** **MISSING** (Cron/worker infrastructure absent).

### 7.2. Settings Presentation Honesty (Purged Developer Jargon):
The notification settings screen strictly avoids developer jargon (`Dự kiến V2`, `FCM/APNs`, `API target`) and displays neutral, user-facing production copy:
> **Thông báo trong ứng dụng: Đang được hoàn thiện** · **Thông báo đẩy trên thiết bị: Chưa hỗ trợ**  
> *"Hệ thống đang hoàn thiện hòm thư lưu trữ thông báo lịch trình và cảnh báo an toàn. Thiết bị hiện chưa hỗ trợ nhận thông báo đẩy khi đóng ứng dụng."*

Controls are presented as informational rows (`Đang hoàn thiện`) rather than unbacked operational switches. Crucially, **all rows** (including Emergency Safety Alerts) are uniformly marked `Đang hoàn thiện` (the claim "Luôn bật" is removed since zero delivery runtime exists in the repository).

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
- **Password Status:** User-facing UI displays `"Mật khẩu tài khoản: Đã thiết lập"`. Internal implementation terms (`mật khẩu mã hóa bcrypt`) are strictly purged from UI.
- **Change Password API:** **MISSING / DESIGN TARGET**. UI renders an unavailable informational row: `"Đổi mật khẩu: Chưa hỗ trợ trong phiên bản hiện tại"` (enabled button and `Dự kiến API` purged).
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

### 10.2. Architecture Verdict & Production UI Boundary:
- **Status:** **POLICY / ARCHITECTURE GAP**.
- **Production UI Copy:**
  - Section title: `"Quản lý tài khoản"`.
  - Copy: *"Quy trình quản lý tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng."*
  - The enabled CTA `[Yêu cầu xóa tài khoản]`, unbacked `[Liên hệ hỗ trợ]` button/badge, and unapproved 30-day anonymization claims are **PURGED** from user-facing UI.
- **Contract Specification (Architecture Target in Documentation Only):**
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

## 12. Master Visual Mockup Evidence Registry (R1 Calibrated)

All 12 current master mockups were rendered via headless Microsoft Edge browser (`--headless=new`, `--force-device-scale-factor=1`) at native specifications and verified in `docs/audit/evidence/ui-08.2.3.16/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit (R1 Truth) | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `Hồ sơ cá nhân` + gear icon.<br>2. User avatar (N), display name "Lê Hoàng Nam", static role "Thành viên" (mapped from USER). Inferred personality badge removed.<br>3. Bio text.<br>4. Neutral informational card "Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate." (fake 65% and Wandy/Buddy matching claims removed).<br>5. Personal info & travel style (Comfort) + interest chips.<br>6. Actions: `[Chỉnh sửa hồ sơ]` + `[Quyền riêng tư]`.<br>7. Canonical 5-tab bottom navigation. | **CURRENT MASTER** |
| [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) | Desktop | $1440 \times 900$ | 1. Top nav: GoMate logo + badge `Hồ sơ du khách` + 5 canonical tabs + User pill.<br>2. 3-column workspace ($320\text{px} + 680\text{px} + 340\text{px}$).<br>3. Col 1: Profile summary, avatar, static role "Thành viên", fake "Đã xác thực" removed, completion card with neutral copy "Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate.", quick menu.<br>4. Col 2: Bio, basic info, TravelPreference details (Comfort, 1M-10M VND, 3-5 group, interest chips).<br>5. Col 3: Buddy Matching card ("Đang hoàn thiện"), Privacy Shield guarantee ("Mặc định ẩn"), Security shortcuts. | **CURRENT MASTER** |
| [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) | Mobile | $390 \times 844$ | **Option A Master Baseline:**<br>1. App bar `< Hủy`, `Chỉnh sửa hồ sơ`, `[Lưu]`.<br>2. Avatar edit overlay.<br>3. Writable Section (PUT /users/me): Tên hiển thị (2-50 chars) + Giới thiệu (78/200 chars).<br>4. Read-Only Section: Số điện thoại (Riêng tư); non-readable fields (DOB, nationality, languages) omitted with honest note: "Một số thông tin tài khoản bổ sung chưa khả dụng trong phiên bản hiện tại.".<br>5. Clear note: Additional info managed at account level.<br>6. Primary CTA: `[Lưu thay đổi hồ sơ]`. | **CURRENT MASTER** |
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

## 13. Current vs. Future Capability Matrix (24 Dimensions)

| Dimension | Current Codebase Status | Architectural Contract V1-R1 | Future Target |
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
| **12. Buddy Discovery Preference** | **MISSING** | **DESIGN TARGET** | Opt-in/opt-out flag for recommendation pool |
| **13. Post-Match Privacy Scope** | **DESIGN LOCKED** | **TIER 2 BOUNDARY** | Matched users get chat channel, NOT raw phone |
| **14. Location Foreground Fix** | **CURRENT** | **LOCKED** | `geolocator` fix with accuracy radius |
| **15. Background Location Tracking** | **EXCLUDED** | **STRICTLY PROHIBITED**| No continuous tracking without user presence |
| **16. Live Location Streaming** | **MISSING** | **EXCLUDED FROM V1** | Future ephemeral opt-in live sharing |
| **17. Notification Schema Store** | **PARTIAL** | **LOCKED** | `model Notification` in PostgreSQL |
| **18. Notification Inbox Runtime** | **MISSING** | **DESIGN TARGET** | Needs NestJS controller & mobile inbox UI |
| **19. OS Push Notifications (FCM/APNs)**| **MISSING** | **FUTURE SPECIFICATION**| Requires Firebase integration in V2 |
| **20. Password Change Feature** | **MISSING** | **DESIGN TARGET** | Add `PUT /auth/change-password` |
| **21. Client Logout Flow** | **CURRENT** | **LOCKED** | Remove tokens from `SharedPreferences` |
| **22. Server Token Revocation** | **MISSING** | **FUTURE SPECIFICATION**| Stateless JWT; token blacklist in Redis for V2 |
| **23. Account Hard Deletion** | **BLOCKED** | **POLICY / ARCH GAP** | FK restrict on 15+ models prevents hard delete |
| **24. Soft-Delete & Anonymization** | **DESIGN LOCKED** | **DESIGN TARGET** | Set `deletedAt`, sanitize PII, preserve ledgers |

---

## 14. Demo Data Governance Policy

All visual values in mockups (*Lê Hoàng Nam*, *nam.le@example.com*, *0912 345 678*, *15/09/2026*, *Việt Nam*, sample bio, sample travel style):
- **CLASSIFICATION:** **VISUAL DEMO DATA ONLY**.
- **RESTRICTION:** Provided strictly for typography, contrast, and layout verification.
- **INVARIANT:** Mockup data does **NOT** constitute evidence of runtime persistence or production capability. Under no circumstances may an audit classify a feature as `CURRENT` based on mockup demo data.
