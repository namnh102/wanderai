# GoMate Authentication & Session Contract V1

- **Module:** GoMate Authentication & Session Lifecycle
- **Status:** **DESIGN LOCKED (V1 Master Specification)**
- **Audit Reference:** `TASK 08.2.3.17`
- **Applicable Platforms:** Flutter Mobile ($390 \times 844$), Web / Desktop Responsive ($1440 \times 900$)
- **Target Audience:** Frontend Engineers, Backend Engineers, QA Engineers, Security Auditors

---

## 1. Executive Summary & Design Principles

The GoMate Authentication module governs user identity, credentials validation, session persistence, route protection, and token lifecycles.

In strict compliance with GoMate architectural standards:
1. **Runtime Truthfulness:** The user experience reflects the verified capabilities of the NestJS backend and Flutter mobile client. Capabilities not implemented in runtime (OAuth social login, biometric authentication, forgot/reset password flows, server-side token revocation, and client-side silent refresh) are excluded from the current UI.
2. **Deterministic State Machine:** Authentication states follow a unidirectional lifecycle (`UNKNOWN` $\rightarrow$ `CHECKING_SESSION` $\rightarrow$ `AUTHENTICATED` / `UNAUTHENTICATED` $\rightarrow$ `AUTH_ERROR`).
3. **Fail-Closed Route Protection:** Protected application shells (Home, Map, Wandy AI, Trips, Safety) strictly require an authenticated state. Unauthenticated requests are immediately redirected to `/login`.
4. **Zero Developer Jargon:** UI screens present natural Vietnamese copy. Internal terminology (JWT, bcrypt, DTO, Redis, HTTP 401, Bearer token) is strictly forbidden in user-facing views.

---

## 2. Authentication State Machine

The GoMate client maintains a single source of truth for authentication state managed via Riverpod (`authProvider`):

```
       [ App Launch ]
              │
              ▼
       ┌───────────────┐
       │    UNKNOWN    │  (Splash / Session Check Screen)
       └──────┬────────┘
              │
              ▼
   ┌───────────────────────┐
   │   CHECKING_SESSION    │  (Read SharedPreferences)
   └───┬───────────────┬───┘
       │               │
  [Token exists]  [No token]
       │               │
       ▼               ▼
┌──────────────┐  ┌──────────────────┐
│AUTHENTICATED │  │ UNAUTHENTICATED  │◄────────────┐
└──────┬───────┘  └────────┬─────────┘             │
       │                   │                       │
       │                   │ [Submit Login/Reg]    │ [Logout]
       │                   ▼                       │
       │            ┌─────────────┐                │
       │            │   LOADING   │                │
       │            └──────┬──────┘                │
       │                   │                       │
       │          ┌────────┴────────┐              │
       │     [Success]           [Failure]         │
       │          │                 │              │
       │          ▼                 ▼              │
       │   ┌──────────────┐  ┌──────────────┐      │
       │   │AUTHENTICATED │  │  AUTH_ERROR  │──────┘
       │   └──────────────┘  └──────────────┘
       │
       │ [401 Unauthorized / Token Expired]
       ▼
┌──────────────────────────┐
│     SESSION_EXPIRED      │ ──► [User Tap "Đăng nhập lại"] ──► UNAUTHENTICATED
└──────────────────────────┘
```

### State Definitions

| State | Definition | UI Presentation | Navigation Route |
| :--- | :--- | :--- | :--- |
| **`UNKNOWN`** | Initial app startup before checking local storage. | Branded splash / spinner screen. | Root `/` (transient) |
| **`CHECKING_SESSION`** | Reading cached access token from `SharedPreferences`. | Branded splash / "Đang kiểm tra phiên đăng nhập...". | Root `/` (transient) |
| **`AUTHENTICATED`** | Valid access token present; user authorized. | Main Application Shell (5 tabs). | `/` (Home), `/map`, etc. |
| **`UNAUTHENTICATED`** | No token found or user explicitly logged out. | Clean Login or Register form. | `/login` or `/register` |
| **`LOADING`** | Network request in flight (login or register). | Disabled form fields + inline spinner on CTA. | Same route (`/login` or `/register`) |
| **`AUTH_ERROR`** | Invalid credentials, duplicate email, or network failure. | Populated form + floating error banner/SnackBar. | Same route (`/login` or `/register`) |
| **`SESSION_EXPIRED`** | Protected request returned 401 Unauthorized. | Session expiration dialog/banner prompting re-login. | Prompt $\rightarrow$ `/login` |

---

## 3. Route Protection & Navigation Boundary

Route guarding is enforced deterministically by GoRouter (`app_router.dart`):

```
                   GoRouter Navigation Interceptor
                                 │
                 ┌───────────────┴───────────────┐
                 │ Current Auth Status Check     │
                 └───────────────┬───────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
  [Status: UNKNOWN]     [Status: UNAUTH]       [Status: AUTH]
          │                      │                      │
          ▼                      ▼                      ▼
    Allow Splash         Is current route       Is current route
   (No redirect)        /login or /register?   /login or /register?
                                 │                      │
                         ┌───────┴───────┐      ┌───────┴───────┐
                        Yes              No    Yes              No
                         │               │      │               │
                         ▼               ▼      ▼               ▼
                       Allow          Redirect Redirect       Allow
                       Route          to /login to / (Home)   Route
```

- **Unauthenticated Routes:**
  - `/login` — `LoginScreen` (outside `ShellRoute`, zero bottom navigation).
  - `/register` — `RegisterScreen` (outside `ShellRoute`, zero bottom navigation).
- **Protected Routes (Wrapped in `ShellRoute` with 5-tab Navigation):**
  - `/` — Home Screen (`Khám phá`)
  - `/map` — Map Screen (`Bản đồ`)
  - `/ai-chat` — Wandy AI Chat (`Wandy AI`)
  - `/trips` — Trip Management (`Chuyến đi`)
  - `/safety` — Safety & Emergency Directory (`An toàn`)
  - `/places/:id` — Place Detail
  - `/trips/:id` — Trip Detail

---

## 4. Backend API Contract & Payload Specifications

### 4.1. Endpoint Matrix

| Method | Endpoint | Request DTO | Auth Header | Success Response | Error Codes |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `POST` | `/auth/login` | `LoginDto` | None | `200 OK` + `{ access_token, refresh_token }` | `400 Bad Request`, `401 Unauthorized` |
| `POST` | `/auth/register` | `RegisterDto` | None | `201 Created` + `{ access_token, refresh_token }` | `400 Bad Request` (Email taken) |
| `POST` | `/auth/refresh` | `{ refresh_token: string }` | None | `200 OK` + `{ access_token, refresh_token }` | `401 Unauthorized` (Token invalid) |
| `GET` | `/users/me` | None | `Bearer <access_token>` | `200 OK` + User Profile JSON | `401 Unauthorized` |

### 4.2. Request DTO Specifications

#### Login Request (`LoginDto`)
```json
{
  "email": "user@example.com",
  "password": "mypassword123"
}
```
- `email`: Required, valid email format (`@IsEmail()`), sanitized to lowercase & trimmed.
- `password`: Required, minimum 6 characters (`@IsString()`, `@MinLength(6)`).

#### Register Request (`RegisterDto`)
```json
{
  "name": "Lê Hoàng Nam",
  "email": "lehoangnam@example.com",
  "password": "mypassword123"
}
```
- `name`: Required, non-empty string (`@IsNotEmpty()`). Persisted to `Profile.displayName`.
- `email`: Required, valid email (`@IsEmail()`), unique check against database.
- `password`: Required, minimum 6 characters (`@MinLength(6)`), hashed via bcrypt (12 salt rounds).
- *Excluded Fields:* Phone, nationality, birth date, gender, avatar, and travel preferences are strictly excluded from registration DTO.

### 4.3. Token Specifications & Cryptographic Lifecycle

| Parameter | Access Token | Refresh Token |
| :--- | :--- | :--- |
| **Type** | Signed JSON Web Token (JWT) | Signed JSON Web Token (JWT) |
| **Payload Claims** | `{ sub: userId, email: string }` | `{ sub: userId, email: string }` |
| **Signing Secret** | `JWT_SECRET` | `JWT_REFRESH_SECRET` |
| **Cryptographic Algorithm**| HMAC-SHA256 (HS256) | HMAC-SHA256 (HS256) |
| **Validity Duration** | $15\text{ minutes}$ | $7\text{ days}$ |
| **Storage Location** | `SharedPreferences` (`access_token`) | `SharedPreferences` (`refresh_token`) |
| **Transport** | `Authorization: Bearer <access_token>` | Request body `{ refresh_token }` |
| **Client Silent Refresh** | **NOT IMPLEMENTED IN CLIENT** | **NOT IMPLEMENTED IN CLIENT** |
| **Server Revocation / Blacklist** | None (Stateless token) | None (Stateless token) |

---

## 5. User Experience & Screen Specifications

### 5.1. Mobile Login Screen (`auth-mobile-login-v1.png`)
- **Branding Area:**
  - Centered GoMate sparkle icon (`#0F766E`).
  - Title: `GoMate` ($24\text{px}$, font-weight 800, color `#0F766E`).
  - Subtitle: `Bạn đồng hành du lịch thông minh` ($13\text{px}$, color `#475569`).
- **Form Controls:**
  - `Email`: Text input with `mail_outline` prefix icon, placeholder `email@example.com`.
  - `Mật khẩu`: Password input with `lock_outline` prefix icon, visibility toggle button (`visibility` / `visibility_off`).
- **Primary CTA:**
  - `[Đăng nhập]` (Elevated Button, background `#0F766E`, color `#FFFFFF`, full-width, height $48\text{px}$).
- **Secondary Action:**
  - `Chưa có tài khoản? Đăng ký ngay` (TextButton, color `#0F766E`).
- **Strict Prohibitions:**
  - NO forgot-password link (feature does not exist in backend).
  - NO Google / Facebook / Apple social login buttons (OAuth not implemented).
  - NO biometric finger/face icon (local authentication not implemented).
  - NO "Ghi nhớ đăng nhập" checkbox (storage is unconditionally persistent).
  - NO 5-tab bottom navigation bar.

### 5.2. Mobile Register Screen (`auth-mobile-register-v1.png`)
- **App Bar:**
  - Title: `Tạo tài khoản` with back arrow `<`.
- **Form Controls (Strictly aligned with `RegisterDto`):**
  - `Họ và tên`: Text input with `person_outline` prefix icon, placeholder `Lê Hoàng Nam`.
  - `Email`: Text input with `mail_outline` prefix icon.
  - `Mật khẩu`: Password input with `lock_outline` prefix icon and visibility toggle.
  - `Xác nhận mật khẩu`: Password confirmation input with `lock_outline` prefix icon (client-side validation only; not transmitted to backend).
- **Primary CTA:**
  - `[Đăng ký]` (Elevated Button, background `#0F766E`, color `#FFFFFF`, full-width, height $48\text{px}$).
- **Secondary Action:**
  - `Đã có tài khoản? Đăng nhập` (TextButton, navigates to `/login`).
- **Privacy Notice:**
  - `Bằng việc đăng ký, bạn đồng ý với Điều khoản dịch vụ và Chính sách quyền riêng tư của GoMate.` ($11\text{px}$, color `#64748B`, text-align center).
- **Auto-Login Behavior:**
  - Upon successful registration, the backend returns tokens immediately. The mobile app automatically saves them and transitions to `AUTHENTICATED` without requiring a redundant login step.

### 5.3. Error & Loading States

#### 1. Login Invalid Credentials (`auth-mobile-login-error-v1.png`)
- **Trigger:** Backend returns `401 Unauthorized`.
- **Presentation:** Floating SnackBar or inline warning banner (`#FEE2E2` background, `#B91C1C` border/text).
- **Message:** `"Email hoặc mật khẩu không đúng."` (Mapped in `auth_provider.dart` line 77).

#### 2. Register Duplicate Email (`auth-mobile-register-error-v1.png`)
- **Trigger:** Backend returns `400 Bad Request` with message containing `"đã được sử dụng"`.
- **Presentation:** Floating SnackBar or inline warning banner (`#FEE2E2` background, `#B91C1C` border/text).
- **Message:** `"Email đã được sử dụng."` (Mapped in `auth_provider.dart` line 83).

#### 3. Login / Register In-Flight Loading (`auth-mobile-login-loading-v1.png`)
- **Trigger:** Request submitted, waiting for API response.
- **Presentation:** Form fields set to read-only/disabled; CTA button displays a centered `CircularProgressIndicator` (stroke width 2, color `#FFFFFF`) and disables user interactions.

#### 4. Network Timeout / Failure
- **Trigger:** `DioExceptionType.connectionTimeout` or `connectionError`.
- **Message:** `"Không thể kết nối máy chủ. Vui lòng thử lại."` or `"Không có kết nối mạng."`.

### 5.4. Session Lifecycle States

#### 1. Startup Session Check (`auth-mobile-session-check-v1.png`)
- **State:** `AuthStatus.unknown` during `_init()`.
- **UI:** Minimalist splash screen with GoMate logo, spinner, and label `"Đang kiểm tra phiên đăng nhập..."`.
- **Behavior:** Reads `access_token` from `SharedPreferences`. If present, immediately transitions to `AUTHENTICATED` and loads `/`. If missing, transitions to `UNAUTHENTICATED` and redirects to `/login`.

#### 2. Session Expired State (`auth-mobile-session-expired-v1.png`)
- **Trigger:** Protected API call receives `401 Unauthorized` after access token expiration ($15\text{m}$).
- **UI:** Modal prompt or full-width banner:
  - Icon: Shield / Clock warning (`#D97706`).
  - Title: `Phiên đăng nhập đã hết hạn`.
  - Body: `Phiên làm việc của bạn đã hết hạn sau thời gian không hoạt động. Vui lòng đăng nhập lại để tiếp tục sử dụng đầy đủ các tính năng của GoMate.`
  - Action: `[Đăng nhập lại]` (Clears cached tokens, transitions to `UNAUTHENTICATED`, and navigates to `/login`).

---

## 6. Desktop Responsive Layout Specifications

For large viewports ($1440 \times 900$), the authentication experience utilizes a balanced two-column presentation:
- **Left Column ($60\%$ width, $\approx 864\text{px}$):**
  - Brand hero container with subtle GoMate Teal gradient (`#0F766E` to `#115E59`).
  - Large GoMate wordmark, value proposition highlights ("Lập lịch trình du lịch thông minh cùng AI", "Khám phá địa điểm địa phương xác thực", "Quản lý chi tiêu và an toàn chuyến đi").
  - Clean travel illustration or geometric motif.
- **Right Column ($40\%$ width, $\approx 576\text{px}$):**
  - Centered elevated authentication card ($420\text{px}$ max width).
  - Clean input fields, $\ge 44\text{px}$ touch targets, and full-width CTA.
  - Zero horizontal scrollbar at $1440\text{px}$.

---

## 7. Security Truthfulness & Copy Rules

| Domain | Strictly Forbidden Copy | Required Truthful Copy | Rationale |
| :--- | :--- | :--- | :--- |
| **Token Revocation** | `"Đã thu hồi phiên trên máy chủ"` | `"Đã đăng xuất khỏi thiết bị này"` | Tokens are stateless JWTs; backend has no server-side blacklist. |
| **Device Scope** | `"Đăng xuất khỏi tất cả thiết bị"` | `"Đăng xuất tài khoản"` | No central session registry exists across multiple devices. |
| **Verification** | `"Tài khoản đã xác minh"` | Omit verification claims | `User.isVerified` has no automated verification pipeline. |
| **Encryption Jargon** | `"Mật khẩu mã hóa bcrypt 12 vòng"` | `"Mật khẩu được bảo vệ an toàn"` | Never expose cryptographic library details to end users. |
| **Token Jargon** | `"Lưu trữ JWT trong SharedPreferences"` | Omit internal storage mechanism | Technical implementation detail. |

---

## 8. Capability Audit Matrix (25 Dimensions)

| Dimension | Current Runtime Status | Architectural Classification | Notes |
| :--- | :---: | :---: | :--- |
| **1. Email Login** | Implemented | **CURRENT** | `POST /auth/login` validates email format. |
| **2. Password Login** | Implemented | **CURRENT** | `bcrypt.compare` against hashed password. |
| **3. Register Account** | Implemented | **CURRENT** | `POST /auth/register` creates User + Profile. |
| **4. Input Validation** | Implemented | **CURRENT** | Client Form + NestJS `ValidationPipe`. |
| **5. Duplicate Email Handling** | Implemented | **CURRENT** | 400 Bad Request mapped to Vietnamese message. |
| **6. Wrong Password Handling** | Implemented | **CURRENT** | 401 Unauthorized mapped to Vietnamese message. |
| **7. Loading State** | Implemented | **CURRENT** | Button spinner + field disable in Flutter. |
| **8. Network Error Handling** | Implemented | **CURRENT** | Mapped timeout and connection errors. |
| **9. Unauthorized (401) Handling**| Partial | **PARTIAL** | Returned by backend; global interceptor missing. |
| **10. Access Token Storage** | Implemented | **CURRENT** | Stored in `SharedPreferences` (plaintext). |
| **11. Refresh Token Storage** | Implemented | **CURRENT** | Stored in `SharedPreferences` (plaintext). |
| **12. Refresh Endpoint / Runtime** | Partial | **PARTIAL** | Backend endpoint exists; client does not call it. |
| **13. Startup Session Restore** | Implemented | **CURRENT** | Client presence check on `access_token`. |
| **14. Expired-Session Handling** | Partial | **PARTIAL** | 15m expiration causes 401; UX prompt designed. |
| **15. Client-Side Logout** | Implemented | **CURRENT** | Clears tokens from `SharedPreferences`. |
| **16. Server-Side Token Revocation**| Missing | **EXCLUDED** | Stateless JWT; zero blacklist in backend. |
| **17. Forgot Password** | Missing | **DESIGN TARGET** | No backend endpoint or email service. |
| **18. Reset Password** | Missing | **DESIGN TARGET** | No reset token verification service. |
| **19. Change Password** | Missing | **DESIGN TARGET** | Marked unavailable in Settings. |
| **20. Email Verification** | Missing | **FUTURE** | DB boolean exists; zero verification pipeline. |
| **21. Social Login (OAuth)** | Missing | **FUTURE** | No Google, Apple, or Facebook passport strategies. |
| **22. Biometric Authentication** | Missing | **FUTURE** | No `local_auth` package or biometric key store. |
| **23. Remember Me Toggle** | Missing | **EXCLUDED** | Storage is unconditionally persistent. |
| **24. Account Lock / Rate Limiting**| Missing | **FUTURE** | No NestJS Throttler on `/auth/login`. |
| **25. Guest Mode** | Missing | **EXCLUDED** | Strict route redirect to `/login` for unauthenticated. |

---

## 9. Architectural Invariants

- **Invariant 1:** The registration process automatically logs the user in upon success, directly transitioning to the main shell.
- **Invariant 2:** No social login, biometric, or password reset triggers shall be rendered in any visual mockup without backend support.
- **Invariant 3:** The unauthenticated views (`/login`, `/register`) shall never render the 5-tab bottom navigation bar.
- **Invariant 4:** All user-facing error messages shall be natural Vietnamese, never exposing HTTP status codes or backend stack traces.
