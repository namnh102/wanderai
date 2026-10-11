# GoMate Design Audit & Verification Report: TASK 08.2.3.17
# GoMate Authentication — Capability Audit, Session Contract & Visual Design V1

- **Task Reference:** `TASK 08.2.3.17`
- **Module:** GoMate Authentication & Session Lifecycle (`docs/design/gomate-authentication-contract-v1.md`)
- **Status:** **DESIGN LOCKED (V1 Audit & Specification Baseline)**
- **Audit Date:** October 7, 2026
- **Mode:** Capability Audit, Architecture Contract & Visual Mockups V1 (Zero production code modifications)

---

## 1. Executive Summary

This audit establishes the definitive baseline of the GoMate Authentication and Session Lifecycle. By conducting an exhaustive, file-by-file inspection of `apps/backend/src/modules/auth/`, `apps/backend/src/modules/users/`, `apps/backend/prisma/schema.prisma`, `apps/mobile/lib/features/auth/`, `apps/mobile/lib/core/network/`, and `apps/mobile/lib/core/router/`, this document aligns the visual presentation and architectural claims with repository reality.

### Key Audit Findings
1. **Working Auth Pipeline:** The repository features a working email/password registration and login pipeline on both NestJS (`/auth/register`, `/auth/login`) and Flutter Mobile (`LoginScreen`, `RegisterScreen`).
2. **Auto-Login on Register:** Registration returns authentication tokens directly (`{ access_token, refresh_token }`), auto-authenticating the user into the main application without requiring a separate login step.
3. **Stateless JWT Tokens:** Authentication relies on signed JWTs ($15\text{m}$ access token, $7\text{d}$ refresh token). The backend has **zero server-side session registry** and **zero token revocation blacklist**.
4. **Client-Side Refresh Gap:** While the backend exposes `POST /auth/refresh`, the mobile client's `api_client.dart` and `auth_repository.dart` contain **zero logic calling this endpoint**. Silent refresh is therefore classified as `PARTIAL / FUTURE` for client runtime.
5. **No Password Recovery:** Forgot password, password reset, and change password pipelines do not exist in backend or mobile. All fake recovery buttons/links are strictly prohibited from visual mockups.
6. **No Social or Biometric Auth:** No OAuth strategies (Google, Apple, Facebook) or biometric libraries (`local_auth`) are implemented.

---

## 2. Capability Audit Matrix (25 Dimensions)

| # | Capability Dimension | Backend Implementation | Mobile Implementation | Classification | Current Runtime Reality & Governance |
| :-: | :--- | :--- | :--- | :---: | :--- |
| **1** | **Email Login** | `POST /auth/login` validates email format | `LoginScreen` email field + validation | **CURRENT** | Case-insensitive trim, `@IsEmail()` check. |
| **2** | **Password Login** | `bcrypt.compare` against hashed password | `LoginScreen` password field + toggle | **CURRENT** | Validates $\ge 6$ chars, secure password masking. |
| **3** | **Register Account** | `POST /auth/register` creates User + Profile | `RegisterScreen` full form | **CURRENT** | Name, email, password; creates initial profile. |
| **4** | **Input Validation** | NestJS `ValidationPipe` (`class-validator`) | Flutter `FormState.validate()` | **CURRENT** | Client prevents invalid submission; server rejects 400. |
| **5** | **Duplicate Email Behavior** | Throws `BadRequestException` (400) | Maps to `"Email đã được sử dụng."` | **CURRENT** | Inline/floating error banner displayed. |
| **6** | **Wrong-Password Behavior** | Throws `UnauthorizedException` (401) | Maps to `"Email hoặc mật khẩu không đúng."` | **CURRENT** | Floating error SnackBar displayed. |
| **7** | **Loading State** | Async controller processing | Spinner inside CTA + disabled fields | **CURRENT** | `CircularProgressIndicator` prevents double submission. |
| **8** | **Network Error Handling** | Standard HTTP status responses | Maps timeout/connection error | **CURRENT** | Vietnamese copy for connection loss or timeout. |
| **9** | **Unauthorized (401) Handling** | `JwtAuthGuard` returns 401 on bad token | Handled per-feature; no global interceptor | **PARTIAL** | Returned by backend; global re-login redirect needed. |
| **10**| **Access Token Storage** | Signed JWT ($15\text{m}$ validity) | Plaintext `SharedPreferences` | **CURRENT** | Injected via Bearer header in `api_client.dart`. |
| **11**| **Refresh Token Storage** | Signed JWT ($7\text{d}$ validity) | Plaintext `SharedPreferences` | **CURRENT** | Stored on login/register; not currently used by client. |
| **12**| **Refresh Endpoint / Runtime** | `POST /auth/refresh` exists & verifies | No client call in `api_client.dart` | **PARTIAL** | Backend ready; Flutter client silent refresh missing. |
| **13**| **Startup Session Restore** | Validates JWT on incoming API calls | Checks `access_token != null` | **CURRENT** | Pure client-side check; auto-navigates to Home if set. |
| **14**| **Expired-Session Handling** | Returns 401 once $15\text{m}$ token expires | Feature queries fail; prompt designed | **PARTIAL** | User needs clear re-login modal on 401 expiration. |
| **15**| **Client-Side Logout** | None (server is stateless) | Removes tokens from `SharedPreferences` | **CURRENT** | Local token purge resets state to unauthenticated. |
| **16**| **Server-Side Token Revocation**| Zero token blacklist in DB/Redis | N/A | **EXCLUDED** | Stateless JWT; token valid until cryptographic expiry. |
| **17**| **Forgot Password** | 0 endpoints; no email dispatcher | 0 UI controls | **DESIGN TARGET** | Excluded from V1 mockups; backend pipeline pending. |
| **18**| **Reset Password** | 0 endpoints; no reset token logic | 0 UI controls | **DESIGN TARGET** | Excluded from V1 mockups. |
| **19**| **Change Password** | 0 endpoints in users module | Marked unavailable in Settings | **DESIGN TARGET** | Displayed as informational "Chưa hỗ trợ" in Settings. |
| **20**| **Email Verification** | `User.isVerified` column exists | 0 verification screens/triggers | **FUTURE** | Schema flag exists but no automated email verification. |
| **21**| **Social Login (OAuth)** | 0 Passport OAuth strategies | 0 social buttons | **FUTURE** | Google/Apple login excluded from V1 UI. |
| **22**| **Biometric Authentication** | 0 biometric endpoints | No `local_auth` in `pubspec.yaml` | **FUTURE** | Fingerprint/FaceID login excluded from V1 UI. |
| **23**| **Remember-Me Toggle** | N/A | SharedPreferences is always persistent | **EXCLUDED** | No toggle needed in V1; persistent session by default. |
| **24**| **Account Lock / Rate Limiting**| No Throttler configured on Auth | N/A | **FUTURE** | Brute-force protection planned for production hardening. |
| **25**| **Guest Mode** | All key endpoints guarded | Router forces redirect to `/login` | **EXCLUDED** | Strict authentication required for travel app shell. |

---

## 3. Backend & Mobile Architecture Alignment

### 3.1. Backend Execution Flow (`apps/backend/src/modules/auth/`)
1. **Registration Flow:**
   - Client sends `POST /auth/register` with `{ email, password, name }`.
   - `AuthService.register()` checks `prisma.user.findUnique({ where: { email } })`.
   - If user exists $\rightarrow$ throws `BadRequestException('Email đã được sử dụng')`.
   - If unique $\rightarrow$ hashes password using `bcrypt.hash(password, 12)`.
   - Creates `User` record with related `Profile` (`displayName: dto.name`).
   - Calls `generateTokens(user.id, user.email)` $\rightarrow$ returns `{ access_token, refresh_token }`.
2. **Login Flow:**
   - Client sends `POST /auth/login` with `{ email, password }`.
   - `AuthService.login()` queries `prisma.user.findUnique`.
   - If not found or `deletedAt != null` $\rightarrow$ throws `UnauthorizedException('Email hoặc mật khẩu không đúng')`.
   - Validates via `bcrypt.compare(password, user.passwordHash)`.
   - If valid $\rightarrow$ returns `{ access_token, refresh_token }`.
3. **Token Refresh Flow:**
   - Client sends `POST /auth/refresh` with `{ refresh_token }`.
   - Verifies cryptographic signature using `JWT_REFRESH_SECRET`.
   - Issues fresh token pair.

### 3.2. Mobile Execution Flow (`apps/mobile/lib/features/auth/`)
1. **Startup Restoration (`AuthNotifier._init`):**
   - App launches $\rightarrow$ `AuthState.unknown()`.
   - Checks `SharedPreferences` for existing `access_token`.
   - If found $\rightarrow$ `AuthState.authenticated()`. Router allows access to `/`.
   - If not found $\rightarrow$ `AuthState.unauthenticated()`. Router redirects to `/login`.
2. **Login Flow (`LoginScreen._login`):**
   - User inputs email and password $\rightarrow$ client form validates format ($\ge 6$ chars, contains `@`).
   - Sets `_loading = true` (shows spinner on button).
   - Calls `authProvider.notifier.login(email, password)`.
   - On success $\rightarrow$ tokens written to `SharedPreferences`, state becomes `authenticated`, GoRouter auto-redirects to `/`.
   - On failure $\rightarrow$ `authProvider` captures Vietnamese error string, displays floating error SnackBar.
3. **Registration Flow (`RegisterScreen._register`):**
   - Validates name, email, password, and confirmation match.
   - Calls `authProvider.notifier.register(name, email, password)`.
   - On success $\rightarrow$ auto-logs in with received tokens and navigates to `/`.
4. **Client-Side Logout:**
   - Removes `access_token` and `refresh_token` from `SharedPreferences`.
   - Resets state to `AuthState.unauthenticated()`.
   - GoRouter immediately redirects active session to `/login`.

---

## 4. Visual Evidence Registry (TASK 08.2.3.17 Mockups)

All visual mockups were rendered using headless Microsoft Edge (`--headless=new`, `--force-device-scale-factor=1`, `--hide-scrollbars`) at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.17/`:

| Mockup Artifact | Viewport | Target Resolution | Key UX Elements & Runtime Verification | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`auth-mobile-login-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-login-v1.png) | Mobile | $390 \times 844$ | 1. GoMate branding header (Logo + Title + Subtitle).<br>2. Email input with prefix icon.<br>3. Password input with lock icon & show/hide visibility toggle.<br>4. Primary CTA `[Đăng nhập]` (Teal `#0F766E`, full width).<br>5. Navigation link `Chưa có tài khoản? Đăng ký ngay`.<br>6. Zero fake forgot-password, zero social login, zero bottom navigation. | **FINAL MASTER** |
| [`auth-mobile-login-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-login-error-v1.png) | Mobile | $390 \times 844$ | Populated login form with floating red error banner displaying verified runtime error: `"Email hoặc mật khẩu không đúng."`. | **FINAL MASTER** |
| [`auth-mobile-login-loading-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-login-loading-v1.png) | Mobile | $390 \times 844$ | In-flight loading state: form fields disabled, primary CTA renders white `CircularProgressIndicator`, preventing duplicate submissions. | **FINAL MASTER** |
| [`auth-mobile-register-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-register-v1.png) | Mobile | $390 \times 844$ | 1. App bar with back button `<` and title `Tạo tài khoản`.<br>2. Exact DTO fields: Họ và tên, Email, Mật khẩu, Xác nhận mật khẩu.<br>3. Primary CTA `[Đăng ký]`.<br>4. Navigation link `Đã có tài khoản? Đăng nhập`.<br>5. Privacy notice. Zero unrequested fields (no phone, birthdate, avatar). | **FINAL MASTER** |
| [`auth-mobile-register-error-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-register-error-v1.png) | Mobile | $390 \times 844$ | Populated registration form with floating red error banner displaying verified runtime error: `"Email đã được sử dụng."`. | **FINAL MASTER** |
| [`auth-mobile-session-check-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-session-check-v1.png) | Mobile | $390 \times 844$ | Startup splash / session check screen: GoMate branding, centered teal spinner, and honest label `"Đang kiểm tra phiên đăng nhập..."`. | **FINAL MASTER** |
| [`auth-mobile-session-expired-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-mobile-session-expired-v1.png) | Mobile | $390 \times 844$ | 401 Unauthorized handling: clean in-app prompt `"Phiên đăng nhập đã hết hạn"` with re-login action `[Đăng nhập lại]`. | **FINAL MASTER** |
| [`auth-desktop-login-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-desktop-login-v1.png) | Desktop | $1440 \times 900$ | 2-column desktop experience: Left branding hero container with GoMate value propositions; Right centered auth card ($420\text{px}$) with clean inputs and primary CTA. Zero horizontal scrollbar. | **FINAL MASTER** |
| [`auth-desktop-register-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17/auth-desktop-register-v1.png) | Desktop | $1440 \times 900$ | 2-column desktop experience: Left branding hero; Right registration card ($440\text{px}$) with exact DTO fields. Zero horizontal scrollbar. | **FINAL MASTER** |

---

## 5. Security Truthfulness & Privacy Governance

1. **Token Persistence:** Plaintext storage in `SharedPreferences` is documented as an MVP constraint. Upgrading to `flutter_secure_storage` is tracked as a future security enhancement.
2. **Stateless JWT Governance:** Because tokens are self-contained and not stored in a server session table, client logout removes local tokens. The system does not claim "Phiên đã bị hủy trên máy chủ".
3. **No Phony Account Recovery:** Password reset is omitted from the UI to avoid deceiving users with non-functional workflows.

---

## 6. Verification & Acceptance Checklist

| Checklist Item | Required Standard | Observed State | Verdict |
| :--- | :--- | :--- | :---: |
| **1. Login Mockup Alignment** | Reflects actual `/auth/login` endpoint | Email, password, visibility toggle, CTA | **PASS** |
| **2. Register Mockup Alignment** | Reflects actual `RegisterDto` fields | Name, email, password, confirm password | **PASS** |
| **3. Fake Forgot Password Purged** | No non-functional password reset links | Omitted entirely from login views | **PASS** |
| **4. Fake Social Login Purged** | No non-functional Google/Apple buttons | Omitted entirely from auth views | **PASS** |
| **5. Fake Verification Purged** | No unbacked "Đã xác minh" claims | Omitted from registration views | **PASS** |
| **6. Auto-Login on Register** | Accurately documents immediate token return | Documented in contract & audit | **PASS** |
| **7. Refresh Token Classification** | Accurately classifies backend vs mobile reality | Classified as PARTIAL (missing client call) | **PASS** |
| **8. Session Expiry Handling** | 401 Unauthorized handling designed | Visual mockup and UX flow defined | **PASS** |
| **9. Error & Loading Coverage** | Complete states designed | Error banners and button spinners verified | **PASS** |
| **10. Mobile 390px Responsive** | Zero horizontal overflow or clipped text | All mobile mockups fit in $390\text{px}$ | **PASS** |
| **11. Desktop 1440px Responsive** | Zero horizontal scrollbar | All desktop mockups fit in $1440\text{px}$ | **PASS** |
| **12. Production Code Untouched** | `apps/` 100% clean | `git diff apps/` returns 0 lines | **PASS** |
| **13. Database Schema Untouched** | `schema.prisma` 100% clean | `git diff apps/backend/prisma/` returns 0 lines | **PASS** |
| **14. Weekly Report Preserved** | `weekly-report-W01.docx` untouched | Preserved unstaged in working tree | **PASS** |

---

## 7. Final Decision

The GoMate Authentication module has been thoroughly audited and documented. All visual mockups, session states, error flows, and capability matrices strictly adhere to verified repository capabilities.

$$\mathbf{TASK\ 08.2.3.17\ =\ DESIGN\ LOCKED}$$

*Execution terminates here. Global Design Review and downstream tasks remain strictly on hold.*
