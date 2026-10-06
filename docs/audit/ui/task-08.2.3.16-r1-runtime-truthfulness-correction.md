# GoMate Profile & Settings — Runtime-Truthfulness & Capability-State Correction (TASK 08.2.3.16-R1)

**Status:** APPROVED R1 CORRECTION & DESIGN LOCK  
**Task:** TASK 08.2.3.16-R1 — GOMATE PROFILE & SETTINGS: RUNTIME-TRUTHFULNESS & CAPABILITY-STATE CORRECTION  
**Date:** October 6, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Mode:** MICRO CORRECTION ONLY (No redesign, no production changes, no schema changes)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model User`, `model Profile`, `model TravelPreference`, `model SafetyContact`, `model Notification`)
- Backend Source Code: [`apps/backend/src/modules/users/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/users/), [`apps/backend/src/modules/auth/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/auth/)
- Mobile Client Router: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
- Mobile Location Provider: [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart)
- Upstream Design Contracts:
  - [`docs/design/gomate-profile-settings-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-profile-settings-contract-v1.md)
  - [`docs/audit/ui/task-08.2.3.16-profile-settings-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.16-profile-settings-audit.md)

---

## 1. Executive Summary & Objective

TASK 08.2.3.16-R1 resolves all remaining inconsistencies between visual mockups, capability matrices, backend reality, and user-facing copy for the **GoMate Profile & Settings** module. 

The core architecture defined in V1 (Three-Tier Privacy Model, Canonical TravelPreference ownership, Safety Contact strict isolation, and 5-tab root navigation) remains fully valid. R1 performs rigorous semantic calibration and truthfulness hardening:
1. **Purged Inferred & Fake Badges:** Omitted "Đã xác thực" and "Du khách thích khám phá" badges where no backend verification pipeline or gamification/persona engine exists.
2. **Corrected Notification Runtime Classification:** Reclassified Notification Inbox from "ACTIVE" to `PARTIAL / SCHEMA PRESENT` (schema exists, controller/service/UI binding missing). Removed developer jargon (`Dự kiến V2`, `FCM/APNs`, `API target`) from UI. Converted unbacked switches to honest informational rows.
3. **Harmonized Buddy & Block List Privacy:** Replaced operational toggles for Buddy Discovery and Phone Sharing with informational preference presentation. Replaced fake `"0 người"` block count with honest copy `"Chức năng quản lý danh sách chặn đang được hoàn thiện"`.
4. **Hardened Password & Account Security Copy:** Removed active `[Đổi mật khẩu]` button and `"mật khẩu mã hóa bcrypt"` copy. Displayed neutral status `"Mật khẩu tài khoản: Đã thiết lập"` and `"Đổi mật khẩu: Chưa hỗ trợ trong phiên bản hiện tại"`.
5. **Calibrated Account Deletion Semantics:** Removed active `[Yêu cầu xóa tài khoản]` CTA and unapproved 30-day deletion claims. Replaced with neutral informational guidance directing users to customer support.
6. **Enforced Edit Profile Write-Boundary (Option A):** Clearly separated writable fields (`displayName`, `avatar`, `bio` via `PUT /users/me`) from read-only account metadata (`phone`, `dateOfBirth`, `nationality`, `languages`).
7. **Eliminated Fabricated Profile Completeness Metrics:** Code audit confirmed 0 occurrences of `profileCompletion` or completion score algorithms. Removed `"65%"` metric and replaced with a generic informational card `"Hoàn thiện hồ sơ du lịch"`.

---

## 2. Inconsistencies Found & Detailed Corrections

### 2.1. Verification Badge Correction
- **Contradiction Found:** `User.isVerified` exists as a boolean column in `schema.prisma`, but neither NestJS nor Flutter implements an email/ID verification workflow. V1 mockups displayed `"Đã xác thực"` as if a verified-user UX existed.
- **R1 Rule:** Omit verification badge entirely from user-facing screens. Do NOT replace with fake `"Chưa xác thực"`.
- **Classification:** `PARTIAL` (DB FLAG ONLY, NO VERIFIED USER UX YET).
- **Affected Artifacts Corrected:**
  - `profile-desktop-overview-v1-r1.png`
  - `settings-desktop-home-v1-r1.png`
  - `settings-mobile-account-security-v1-r1.png`

### 2.2. Notification Reality & Copy Correction
- **Contradiction Found:** `model Notification` exists in PostgreSQL, but there is zero `NotificationController`, zero `NotificationService`, zero mobile inbox UI, zero FCM, and zero APNs. V1 copy claimed `"Hòm thư trong app: Hoạt động"` and used developer jargon (`Push OS: Dự kiến V2`, `FCM/APNs`). V1 also rendered active functional switches for non-persisted preferences.
- **R1 Corrections:**
  - **Classification Corrected:**
    - Notification schema/data model: `PARTIAL / SCHEMA PRESENT`
    - Notification runtime inbox: `MISSING / DESIGN TARGET`
    - OS Push Notifications: `MISSING / FUTURE`
    - Scheduled notification worker: `MISSING`
  - **UI Copy Corrected:** Replaced with neutral, production-facing Vietnamese copy:
    - `"Thông báo trong ứng dụng: Đang được hoàn thiện"`
    - `"Thông báo đẩy trên thiết bị: Chưa hỗ trợ"`
    - Subtext: *"Hệ thống đang hoàn thiện hòm thư lưu trữ thông báo lịch trình và cảnh báo an toàn. Thiết bị hiện chưa hỗ trợ nhận thông báo đẩy khi đóng ứng dụng."*
  - **Controls Corrected:** Converted non-functional switches to clean informational status rows (`Đang hoàn thiện`, `Luôn bật`).
- **Affected Artifact Corrected:** `settings-mobile-notifications-v1-r1.png`

### 2.3. Buddy Privacy Controls & Block List Correction
- **Contradiction Found:** Neither Buddy Discovery toggle nor post-match phone reveal toggle has backend persistence API in `UsersController`. In addition, `UserBlock` model is completely missing from schema, making the V1 copy `"Chưa chặn người dùng nào (0 người)"` invalid (fabricating an empty state count implies a working datastore).
- **R1 Corrections:**
  - Buddy Discovery & Phone Visibility presented as informational preference targets (`Mặc định mở`, `Luôn bảo mật`).
  - Block list copy replaced with honest notice: `"Chặn & báo cáo"` — *"Chức năng quản lý danh sách chặn đang được hoàn thiện"* (No fabricated numeric count).
  - Maintained locked privacy invariant: Match acceptance **NEVER** automatically reveals phone numbers.
- **Affected Artifact Corrected:** `settings-mobile-privacy-v1-r1.png`

### 2.4. Password & Account Security Copy Correction
- **Contradiction Found:** Auth module supports `register` and `login`, but `change-password` API is missing. V1 rendered an enabled button `[Đổi mật khẩu]` and displayed technical implementation details (`mật khẩu mã hóa bcrypt`) alongside developer-facing copy (`Dự kiến API`).
- **R1 Corrections:**
  - Password row displays: `"Mật khẩu tài khoản: Đã thiết lập"` (safely inferred from authenticated account).
  - Change password row displays: `"Đổi mật khẩu: Chưa hỗ trợ trong phiên bản hiện tại"` (Badge: `Chưa hỗ trợ`). Enabled button removed.
  - Developer-facing term `"Dự kiến API"` purged completely.
- **Affected Artifacts Corrected:**
  - `settings-mobile-account-security-v1-r1.png`
  - `settings-desktop-home-v1-r1.png`

### 2.5. Account Deletion Correction
- **Contradiction Found:** Hard deletion is blocked by FK RESTRICT constraints across 15+ models. Soft-delete + anonymization is an architecture target only (no API exists). V1 rendered an active destructive CTA `[Yêu cầu xóa tài khoản]` and claimed a 30-day anonymization workflow.
- **R1 Corrections:**
  - Section title: `"Quản lý tài khoản"`.
  - Neutral informational copy: *"Quy trình xóa tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng. Để yêu cầu xử lý hoặc khóa tài khoản, vui lòng liên hệ bộ phận hỗ trợ khách hàng GoMate."*
  - Active destructive CTA removed from production-facing UI.
- **Affected Artifacts Corrected:**
  - `settings-mobile-account-security-v1-r1.png`
  - `settings-desktop-home-v1-r1.png`

### 2.6. Edit Profile Write-Boundary Separation (Option A Master)
- **Contradiction Found:** Only `displayName`, `avatar`, and `bio` are writable via `PUT /users/me`. `phone` is read-only, while `dateOfBirth`, `nationality`, and `languages` are schema gaps omitted from backend select/update. V1 edit form visually grouped all fields under one generic form with a single `[Lưu]` button.
- **R1 Corrections (Option A Master Baseline):**
  - **Writable Section:** `Tên hiển thị *` (2-50 chars), `Giới thiệu ngắn` (max 200 chars), and `Ảnh đại diện`.
  - **Read-Only / Account Metadata Section:** Explicitly titled `"Thông tin bổ sung (Chỉ đọc)"` with note `* Các trường thông tin bổ sung hiện được lưu ở mức tài khoản và không thay đổi qua form này.`
  - Chip delete icons (`✕`) and `+ Thêm` buttons removed from read-only chips.
- **Affected Artifact Corrected:** `profile-mobile-edit-v1-r1.png`

### 2.7. Profile Completeness Metric Correction
- **Contradiction Found:** Code search for `profileCompletion`, `completionPercent`, `profileScore`, `completeness`, and `65%` confirmed **0 occurrences** across the entire codebase. V1 displayed a calculated `65%` progress bar.
- **R1 Corrections:** Removed numeric `65%` and progress meter. Replaced with generic informational card `"Hoàn thiện hồ sơ du lịch"` encouraging users to update their bio and preferences.
- **Affected Artifacts Corrected:**
  - `profile-mobile-overview-v1-r1.png`
  - `profile-desktop-overview-v1-r1.png`

### 2.8. Social Persona & Role Review
- **Contradiction Found:** V1 displayed an inferred persona badge `"Du khách thích khám phá"`.
- **R1 Corrections:** Inferred personality badges removed. Static account role badge `"Thành viên"` (mapped strictly from `UserRole.USER`) is retained.
- **Affected Artifact Corrected:** `profile-mobile-overview-v1-r1.png`

---

## 3. Demo Data Governance Policy

All mockup values (e.g., *Lê Hoàng Nam*, *nam.le@example.com*, *0912 345 678*, *15/09/2026*, *Việt Nam*, sample bio, sample travel style):
- **CLASSIFICATION:** **VISUAL DEMO DATA ONLY**.
- **INVARIANT:** Demo values are provided exclusively for visual-layout and typography verification.
- **AUDIT RESTRICTION:** They are **NOT** production claims and **NOT** evidence of runtime persistence. Under no circumstances may a capability be classified as `CURRENT` based solely on mockup demo data.

---

## 4. Master Visual Artifact Registry

Following R1 regeneration, all 12 visual screens have exactly one CURRENT master artifact. Superseded V1 artifacts are preserved on disk for audit history:

| Screen / State | Viewport | Current Master Artifact (R1 / V1) | Superseded V1 Artifact | Current Status |
| :--- | :---: | :--- | :--- | :---: |
| **1. Profile Overview (Mobile)** | Mobile ($390 \times 844$) | [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) | `profile-mobile-overview-v1.png` | **CURRENT MASTER** |
| **2. Profile Overview (Desktop)**| Desktop ($1440 \times 900$) | [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) | `profile-desktop-overview-v1.png` | **CURRENT MASTER** |
| **3. Edit Profile (Mobile)** | Mobile ($390 \times 844$) | [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) | `profile-mobile-edit-v1.png` | **CURRENT MASTER** |
| **4. Travel Preferences (Mobile)**| Mobile ($390 \times 844$) | [`profile-mobile-travel-preferences-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1.png) | *None (Unaffected)* | **CURRENT MASTER** |
| **5. Settings Home (Mobile)** | Mobile ($390 \times 844$) | [`settings-mobile-home-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-home-v1.png) | *None (Unaffected)* | **CURRENT MASTER** |
| **6. Settings Home (Desktop)** | Desktop ($1440 \times 900$) | [`settings-desktop-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-desktop-home-v1-r1.png) | `settings-desktop-home-v1.png` | **CURRENT MASTER** |
| **7. Privacy Settings (Mobile)** | Mobile ($390 \times 844$) | [`settings-mobile-privacy-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-privacy-v1-r1.png) | `settings-mobile-privacy-v1.png` | **CURRENT MASTER** |
| **8. Notification Settings (Mobile)**| Mobile ($390 \times 844$) | [`settings-mobile-notifications-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-notifications-v1-r1.png) | `settings-mobile-notifications-v1.png` | **CURRENT MASTER** |
| **9. Location Settings (Mobile)** | Mobile ($390 \times 844$) | [`settings-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-location-v1.png) | *None (Unaffected)* | **CURRENT MASTER** |
| **10. Account & Security (Mobile)**| Mobile ($390 \times 844$) | [`settings-mobile-account-security-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-account-security-v1-r1.png) | `settings-mobile-account-security-v1.png` | **CURRENT MASTER** |
| **11. Logout Confirm (Mobile)** | Mobile ($390 \times 844$) | [`settings-mobile-logout-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/settings-mobile-logout-confirm-v1.png) | *None (Unaffected)* | **CURRENT MASTER** |
| **12. Loading & Error (Mobile)** | Mobile ($390 \times 844$) | [`profile-mobile-loading-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-loading-error-v1.png) | *None (Unaffected)* | **CURRENT MASTER** |

---

## 5. Acceptance Gate Checklist

| Verification Item | R1 Standard | Verification Evidence | Status |
| :--- | :--- | :--- | :---: |
| **1. No Fake "Đã xác thực" Badge** | Omit badge where no pipeline exists | Removed from desktop & mobile account views | **PASS** |
| **2. Notification Inbox Honest State** | Not claimed ACTIVE without runtime | Reclassified as `PARTIAL / SCHEMA PRESENT` | **PASS** |
| **3. Push OS Honest State** | Not presented as functional | Labeled `"Chưa hỗ trợ"` | **PASS** |
| **4. Unbacked Notification Controls** | Not shown as functional toggles | Converted to neutral informational rows | **PASS** |
| **5. Buddy Discovery Toggle** | Not shown as persisted toggle | Converted to preference target row | **PASS** |
| **6. Phone Sharing Setting** | Not shown as functional toggle | Preserved strict private default | **PASS** |
| **7. No Fake Block Count** | No fabricated `"0 người"` | Copy updated to `"Chặn & báo cáo: Đang hoàn thiện"` | **PASS** |
| **8. Change Password Capability** | Not shown as active capability | Labeled `"Chưa hỗ trợ trong phiên bản hiện tại"` | **PASS** |
| **9. Developer Jargon Purged** | No `"API target"`, `"Dự kiến V2"`, `"FCM/APNs"` | Clean production Vietnamese copy throughout | **PASS** |
| **10. Bcrypt Details Purged** | No implementation wording in UI | Replaced with `"Mật khẩu tài khoản: Đã thiết lập"` | **PASS** |
| **11. Account Deletion Honesty** | No fake runtime CTA or unapproved 30d claim | Neutral customer support guidance displayed | **PASS** |
| **12. Edit Profile Write Boundary** | Separate writable from read-only fields | Option A master implemented in R1 | **PASS** |
| **13. Profile Completeness Metric** | No fabricated 65% calculation | Removed 65%; generic informational card used | **PASS** |
| **14. Persona Badge Removed** | No unbacked personality labels | Inferred badge removed; static role `"Thành viên"` | **PASS** |
| **15. SafetyContact Isolation** | Tier 1 strict boundary | Zero exposure to profile or group views | **PASS** |
| **16. TravelPreference SSOT** | Unified preference engine | Preserved as single source of truth | **PASS** |
| **17. Location Boundary Preserved** | Foreground only | Background & continuous tracking excluded | **PASS** |
| **18. Canonical 5-Tab Navigation** | No 6th bottom nav tab added | Standard 5 tabs intact on all views | **PASS** |
| **19. Zero Production Code Changes** | `apps/` untouched | Verified via `git diff apps/` (0 lines) | **PASS** |
| **20. Schema Untouched** | `schema.prisma` untouched | Verified via `git diff` (0 lines) | **PASS** |
| **21. Unstaged Document Invariant** | `weekly-report-W01.docx` untouched | Must remain strictly unstaged and uncommitted | **PASS** |

---

## 6. Conclusion

TASK 08.2.3.16-R1 completely aligns the visual representation and architectural documentation of GoMate Profile & Settings with repository truth. The module is fully locked and prepared for downstream integration.
