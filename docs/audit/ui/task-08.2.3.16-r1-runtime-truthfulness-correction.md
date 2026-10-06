# GoMate Profile & Settings — Runtime-Truthfulness & Capability-State Correction (TASK 08.2.3.16-R1 / R1.1)

**Status:** APPROVED R1 / R1.1 CONSISTENCY CLOSURE & DESIGN LOCK  
**Task:** TASK 08.2.3.16-R1 / R1.1 — GOMATE PROFILE & SETTINGS: FINAL RUNTIME-TRUTHFULNESS CONSISTENCY CLOSURE  
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

TASK 08.2.3.16-R1 and R1.1 resolve all remaining inconsistencies between visual mockups, capability matrices, backend reality, and user-facing copy for the **GoMate Profile & Settings** module. 

The core architecture defined in V1 (Three-Tier Privacy Model, Canonical TravelPreference ownership, Safety Contact strict isolation, and 5-tab root navigation) remains fully valid. R1/R1.1 performs rigorous semantic calibration and truthfulness hardening:
1. **Purged Inferred & Fake Badges:** Omitted "Đã xác thực" and "Du khách thích khám phá" badges where no backend verification pipeline or gamification/persona engine exists.
2. **Corrected Notification Runtime Classification:** Reclassified Notification Inbox from "ACTIVE" to `PARTIAL / SCHEMA PRESENT` (schema exists, controller/service/UI binding missing). Removed developer jargon (`Dự kiến V2`, `FCM/APNs`, `API target`) from UI. Converted unbacked switches to honest informational rows.
3. **Harmonized Buddy & Block List Privacy:** Replaced operational toggles for Buddy Discovery and Phone Sharing with informational preference presentation. Replaced fake `"0 người"` block count with honest copy `"Chức năng quản lý danh sách chặn đang được hoàn thiện"`.
4. **Hardened Password & Account Security Copy:** Removed active `[Đổi mật khẩu]` button and `"mật khẩu mã hóa bcrypt"` copy. Displayed neutral status `"Mật khẩu tài khoản: Đã thiết lập"` and `"Đổi mật khẩu: Chưa hỗ trợ trong phiên bản hiện tại"`.
5. **Calibrated Account Deletion Semantics:** Removed active `[Yêu cầu xóa tài khoản]` CTA and unapproved 30-day deletion claims. Replaced with neutral informational guidance.
6. **Enforced Edit Profile Write-Boundary (Option A):** Clearly separated writable fields (`displayName`, `avatar`, `bio` via `PUT /users/me`) from read-only account metadata.
7. **Eliminated Fabricated Profile Completeness Metrics:** Code audit confirmed 0 occurrences of `profileCompletion` or completion score algorithms. Removed `"65%"` metric and replaced with a neutral completion card.
8. **Closed R1.1 Consistency Contradictions:**
   - Enforced TravelPreference write-boundary (`profile-mobile-travel-preferences-v1-r1.png` created as read-only; no fake Save button).
   - Removed non-readable metadata demo values from Edit Profile.
   - Purged fake "Luôn bật" claim from safety notification rows.
   - Removed unbacked `[Liên hệ hỗ trợ]` button/badge (0 support infrastructure in repo).
   - Calibrated Buddy Discovery to "Đang hoàn thiện" and Phone to "Mặc định ẩn".

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
  - **Controls Corrected:** Converted non-functional switches to clean informational status rows (`Đang hoàn thiện`).
- **Affected Artifact Corrected:** `settings-mobile-notifications-v1-r1.png`

### 2.3. Buddy Privacy Controls & Block List Correction
- **Contradiction Found:** Neither Buddy Discovery toggle nor post-match phone reveal toggle has backend persistence API in `UsersController`. In addition, `UserBlock` model is completely missing from schema, making the V1 copy `"Chưa chặn người dùng nào (0 người)"` invalid (fabricating an empty state count implies a working datastore).
- **R1 Corrections:**
  - Buddy Discovery presented as informational preference target: `"Tìm bạn đồng hành: Chức năng khám phá bạn đồng hành đang được hoàn thiện"` (the claim `"Mặc định mở"` is removed as no matching runtime exists).
  - Phone Visibility presented as: `"Chia sẻ số điện thoại: Mặc định ẩn"` (the claim `"Luôn bảo mật"` is softened to `"Mặc định ẩn"` as architecture permits future post-match explicit consent).
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

### 2.5. Account Deletion & Support Action Audit Correction
- **Contradiction Found:** Hard deletion is blocked by FK RESTRICT constraints across 15+ models. Soft-delete + anonymization is an architecture target only (no API exists). V1 rendered an active destructive CTA `[Yêu cầu xóa tài khoản]` and claimed a 30-day anonymization workflow. Furthermore, git grep confirmed zero customer support ticketing, phone hotline, or support email in the codebase, making any `[Liên hệ hỗ trợ]` button or badge unbacked.
- **R1/R1.1 Corrections:**
  - Section title: `"Quản lý tài khoản"`.
  - Pure informational copy: *"Quy trình quản lý tài khoản chưa được hỗ trợ trực tiếp trong ứng dụng."*
  - Active destructive CTA and unbacked support button/badge purged from production-facing UI.
- **Affected Artifacts Corrected:**
  - `settings-mobile-account-security-v1-r1.png`
  - `settings-desktop-home-v1-r1.png`

### 2.6. Edit Profile Write-Boundary Separation (Option A Master)
- **Contradiction Found:** Only `displayName`, `avatar`, and `bio` are writable via `PUT /users/me`. `phone` is readable via `GET /users/me`. However, `dateOfBirth`, `nationality`, and `languages` are schema gaps omitted from backend select projection in `findById`. Rendering demo values for non-readable fields creates a false impression of existing data.
- **R1/R1.1 Corrections (Option A Master Baseline):**
  - **Writable Section:** `Tên hiển thị *` (2-50 chars), `Giới thiệu ngắn` (max 200 chars), and `Ảnh đại diện`.
  - **Read-Only / Account Metadata Section:** `Số điện thoại` (Riêng tư). Non-readable fields (DOB, nationality, languages) omitted and replaced with honest notice: *"Một số thông tin tài khoản bổ sung chưa khả dụng trong phiên bản hiện tại."*
  - Chip delete icons (`✕`), `+ Thêm` buttons, and unbacked inputs removed.
- **Affected Artifact Corrected:** `profile-mobile-edit-v1-r1.png`

### 2.7. Profile Completeness Metric Correction
- **Contradiction Found:** Code search for `profileCompletion`, `completionPercent`, `profileScore`, `completeness`, and `65%` confirmed **0 occurrences** across the entire codebase. V1 displayed a calculated `65%` progress bar and promised Wandy AI / Buddy matching optimizations.
- **R1/R1.1 Corrections:** Removed numeric `65%` and progress meter. Replaced with neutral informational copy: *"Cập nhật thông tin và sở thích du lịch để cá nhân hóa trải nghiệm GoMate."*
- **Affected Artifacts Corrected:**
  - `profile-mobile-overview-v1-r1.png`
  - `profile-desktop-overview-v1-r1.png`

### 2.8. Social Persona & Role Review
- **Contradiction Found:** V1 displayed an inferred persona badge `"Du khách thích khám phá"`.
- **R1 Corrections:** Inferred personality badges removed. Static account role badge `"Thành viên"` (mapped strictly from `UserRole.USER`) is retained.
- **Affected Artifact Corrected:** `profile-mobile-overview-v1-r1.png`

### 2.9. TravelPreference Write-Boundary Closure (R1.1)
- **Contradiction Found:** `TravelPreference` exists in PostgreSQL and is readable via `GET /users/me` (`include: { travelPreferences: true }`), but there is NO `PUT /users/me/preferences` endpoint. Leaving `profile-mobile-travel-preferences-v1.png` as an editable form with an active `[Lưu]` CTA contradicted repository reality.
- **R1.1 Corrections:**
  - Created `profile-mobile-travel-preferences-v1-r1.png` displaying travel preferences strictly as **read-only information**.
  - Removed all interactive selection toggles, chip tap affordances, and the `[Lưu]` / `[Lưu sở thích du lịch]` action button.
  - Added honest status notice: *"Sở thích du lịch: Chức năng chỉnh sửa sở thích đang được hoàn thiện."*
- **Affected Artifact Corrected:** `profile-mobile-travel-preferences-v1-r1.png` [Supersedes V1]

### 2.10. Notification "Luôn bật" Runtime Removal (R1.1)
- **Contradiction Found:** In the notification settings screen, the safety alert row was labeled `"Luôn bật"`. However, because zero notification workers, FCM, or APNs exist in the codebase, claiming that emergency safety notifications are runtime active was factually untrue.
- **R1.1 Corrections:**
  - All notification rows (including Cảnh báo an toàn khẩn cấp) are uniformly marked `"Đang hoàn thiện"`.
  - Honest disclosure that delivery infrastructure is in development.
- **Affected Artifact Corrected:** `settings-mobile-notifications-v1-r1.png`

---

## 3. Demo Data Governance Policy

All mockup values (e.g., *Lê Hoàng Nam*, *nam.le@example.com*, *0912 345 678*, *15/09/2026*, *Việt Nam*, sample bio, sample travel style):
- **CLASSIFICATION:** **VISUAL DEMO DATA ONLY**.
- **INVARIANT:** Demo values are provided exclusively for visual-layout and typography verification.
- **AUDIT RESTRICTION:** They are **NOT** production claims and **NOT** evidence of runtime persistence. Under no circumstances may a capability be classified as `CURRENT` based solely on mockup demo data.

---

## 4. Master Visual Artifact Registry

Following R1 and R1.1 regeneration, all 12 visual screens have exactly one CURRENT master artifact. All 8 superseded V1 artifacts are preserved on disk for audit history:

| Screen / State | Viewport | Current Master Artifact (R1 / V1) | Superseded V1 Artifact | Current Status |
| :--- | :---: | :--- | :--- | :---: |
| **1. Profile Overview (Mobile)** | Mobile ($390 \times 844$) | [`profile-mobile-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-overview-v1-r1.png) | `profile-mobile-overview-v1.png` | **CURRENT MASTER** |
| **2. Profile Overview (Desktop)**| Desktop ($1440 \times 900$) | [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) | `profile-desktop-overview-v1.png` | **CURRENT MASTER** |
| **3. Edit Profile (Mobile)** | Mobile ($390 \times 844$) | [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) | `profile-mobile-edit-v1.png` | **CURRENT MASTER** |
| **4. Travel Preferences (Mobile)**| Mobile ($390 \times 844$) | [`profile-mobile-travel-preferences-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-travel-preferences-v1-r1.png) | `profile-mobile-travel-preferences-v1.png` | **CURRENT MASTER** |
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

| Verification Item | R1 / R1.1 Standard | Verification Evidence | Status |
| :--- | :--- | :--- | :---: |
| **1. No Fake "Đã xác thực" Badge** | Omit badge where no pipeline exists | Removed from desktop & mobile account views | **PASS** |
| **2. Notification Inbox Honest State** | Not claimed ACTIVE without runtime | Reclassified as `PARTIAL / SCHEMA PRESENT` | **PASS** |
| **3. Push OS Honest State** | Not presented as functional | Labeled `"Chưa hỗ trợ"` | **PASS** |
| **4. Unbacked Notification Controls** | Not shown as functional toggles | Converted to neutral informational rows | **PASS** |
| **5. Notification "Luôn bật" Purged** | No runtime claim for safety alerts | All rows marked `"Đang hoàn thiện"` | **PASS** |
| **6. Buddy Discovery Copy** | Honest capability notice | Marked `"Đang hoàn thiện"` (no `"Mặc định mở"`) | **PASS** |
| **7. Phone Sharing Copy** | Honest privacy status | Marked `"Mặc định ẩn"` (no `"Luôn bảo mật"`) | **PASS** |
| **8. No Fake Block Count** | No fabricated `"0 người"` | Copy updated to `"Chặn & báo cáo: Đang hoàn thiện"` | **PASS** |
| **9. Change Password Capability** | Not shown as active capability | Labeled `"Chưa hỗ trợ trong phiên bản hiện tại"` | **PASS** |
| **10. Developer Jargon Purged** | No `"API target"`, `"Dự kiến V2"`, `"FCM/APNs"` | Clean production Vietnamese copy throughout | **PASS** |
| **11. Bcrypt Details Purged** | No implementation wording in UI | Replaced with `"Mật khẩu tài khoản: Đã thiết lập"` | **PASS** |
| **12. Account Management Notice** | Pure informational text | No fake support button/badge (0 support in repo) | **PASS** |
| **13. Edit Profile Write Boundary** | Separate writable from read-only fields | Non-readable demo metadata omitted with notice | **PASS** |
| **14. TravelPreference Read-Only** | No unbacked write CTA | `profile-mobile-travel-preferences-v1-r1.png` is read-only | **PASS** |
| **15. Profile Completeness Metric** | No fabricated 65% calculation | Removed 65%; neutral completion copy used | **PASS** |
| **16. Persona Badge Removed** | No unbacked personality labels | Inferred badge removed; static role `"Thành viên"` | **PASS** |
| **17. SafetyContact Isolation** | Tier 1 strict boundary | Zero exposure to profile or group views | **PASS** |
| **18. TravelPreference SSOT** | Unified preference engine | Preserved as single source of truth | **PASS** |
| **19. Location Boundary Preserved** | Foreground only | Background & continuous tracking excluded | **PASS** |
| **20. Canonical 5-Tab Navigation** | No 6th bottom nav tab added | Standard 5 tabs intact on all views | **PASS** |
| **21. Zero Production Code Changes** | `apps/` untouched | Verified via `git diff apps/` (0 lines) | **PASS** |
| **22. Schema Untouched** | `schema.prisma` untouched | Verified via `git diff` (0 lines) | **PASS** |
| **23. Unstaged Document Invariant** | `weekly-report-W01.docx` untouched | Must remain strictly unstaged and uncommitted | **PASS** |

---

## 6. Conclusion

TASK 08.2.3.16-R1 and R1.1 completely align the visual representation and architectural documentation of GoMate Profile & Settings with repository truth. All contradictions regarding travel preference writes, non-readable fields, emergency notification claims, buddy matching defaults, and support buttons are definitively closed. The module is fully locked and ready for downstream implementation when scheduled.

