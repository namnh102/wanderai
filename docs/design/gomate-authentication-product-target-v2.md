# GoMate Authentication — Complete Product Target & Future Implementation Contract V2

- **Module:** GoMate Authentication & Session Lifecycle (Product Target Specification)
- **Status:** **PRODUCT TARGET LOCKED (V2 Master Specification)**
- **Audit Reference:** `TASK 08.2.3.17-R2`
- **Baseline Document:** [`docs/design/gomate-authentication-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-authentication-contract-v1.md) (Preserved as Current Runtime Baseline)
- **Applicable Platforms:** Flutter Mobile ($390 \times 844$), Web / Desktop Responsive ($1440 \times 900$)

---

## 1. Executive Summary & Two-Tier Architecture Governance

This document establishes the **Complete Product Target (V2)** for the GoMate Authentication and Session Lifecycle. It bridges the gap between current MVP capabilities and the production-grade requirements needed for official public release, while strictly maintaining honesty about current repository capabilities.

### Two-Tier Governance Model

```
┌────────────────────────────────────────────────────────────────────────┐
│                   GOMATE AUTHENTICATION ARCHITECTURE                   │
├───────────────────────────────────┬────────────────────────────────────┤
│   TIER 1: CURRENT RUNTIME (V1)    │    TIER 2: PRODUCT TARGET (V2)     │
│   (docs/...contract-v1.md)        │    (docs/...product-target-v2.md)  │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Email / Password Login          │ • Password Recovery (Forgot/Reset) │
│ • Account Registration            │ • Authenticated Password Change    │
│ • Basic Form Validation           │ • Email Verification Pipeline      │
│ • Client Token Storage (Plain)    │ • Social OAuth (Google, Apple)     │
│ • Manual Client Logout            │ • Account Conflict & Linking       │
│ • Auto-Login on Register          │ • Silent Refresh & Concurrency Lock│
│ • 15m Access / 7d Refresh Tokens  │ • Secure Storage (Keystore/Keych.) │
│                                   │ • Rate Limiting & Anti-Enumeration │
└───────────────────────────────────┴────────────────────────────────────┘
```

### Classification Vocabulary
- **`CURRENT`:** Code is verified in repository runtime (NestJS backend and Flutter client).
- **`PARTIAL`:** Implemented partially (e.g. backend exists but mobile integration is missing).
- **`PRODUCT TARGET`:** Mandatory for GoMate production readiness before launch; architecture and UX designed, but zero code implemented in this phase.
- **`FUTURE`:** Deferred post-MVP release (e.g. WebAuthn, biometric sync, Facebook login).
- **`EXCLUDED`:** Intentionally omitted (e.g. guest mode, server session state table).

---

## 2. Current vs. Product Target Capability Matrix

| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Dependency / Implementation Requirement |
| :-: | :--- | :---: | :---: | :--- |
| **1** | **Email Login** | **CURRENT** | **KEEP** | Preserved from V1 baseline. |
| **2** | **Password Login** | **CURRENT** | **KEEP** | Preserved from V1 baseline. |
| **3** | **Register Account** | **CURRENT** | **ENHANCED** | Adds email verification trigger post-registration. |
| **4** | **Input Validation** | **CURRENT** | **KEEP** | Client-side immediate feedback + NestJS `ValidationPipe`. |
| **5** | **Duplicate Email Behavior** | **CURRENT** | **KEEP** | Preserves 400 Bad Request mapped to natural Vietnamese. |
| **6** | **Wrong-Password Behavior** | **CURRENT** | **KEEP** | Generic 401 Unauthorized prevents username enumeration. |
| **7** | **Loading States** | **CURRENT** | **KEEP** | Button spinner + input disabling during requests. |
| **8** | **Network Error Handling** | **CURRENT** | **KEEP** | User-friendly Vietnamese connection error messages. |
| **9** | **Global 401 Interceptor** | **PARTIAL** | **PRODUCT TARGET** | `api_client.dart` Dio interceptor with request queuing. |
| **10**| **Access Token Storage** | **CURRENT** (Plain) | **PRODUCT TARGET** | Migrate from `SharedPreferences` to `flutter_secure_storage`. |
| **11**| **Refresh Token Storage** | **CURRENT** (Plain) | **PRODUCT TARGET** | Encrypted storage inside hardware-backed keystore/keychain. |
| **12**| **Silent Token Refresh** | **PARTIAL** (Backend only)| **PRODUCT TARGET** | Automated background token renewal without UX interruption. |
| **13**| **Startup Session Restore** | **CURRENT** | **ENHANCED** | Decodes token expiry locally before attempting restore. |
| **14**| **Expired-Session Handling** | **PARTIAL** | **PRODUCT TARGET** | Clean in-app modal prompt redirecting to `/login`. |
| **15**| **Client Logout** | **CURRENT** | **KEEP** | Complete token purging and state reset to unauthenticated. |
| **16**| **Server Token Blacklist** | **EXCLUDED** | **FUTURE** | Stateless JWT preserved; Redis blacklist deferred. |
| **17**| **Forgot Password** | **MISSING** | **PRODUCT TARGET** | Email dispatch + time-limited cryptographic reset token. |
| **18**| **Reset Password** | **MISSING** | **PRODUCT TARGET** | One-time token validation + password update endpoint. |
| **19**| **Change Password** | **MISSING** | **PRODUCT TARGET** | Authenticated settings endpoint requiring current password. |
| **20**| **Email Verification** | **FUTURE** | **PRODUCT TARGET** | Mail provider (Resend/SendGrid) + verification link/token. |
| **21**| **Google Social Login** | **MISSING** | **PRODUCT TARGET** | Google Sign-In SDK + backend IDToken verification. |
| **22**| **Apple Social Login** | **MISSING** | **PRODUCT TARGET** | Apple Sign-In SDK (required on iOS) + backend JWT verify. |
| **23**| **Facebook Social Login** | **MISSING** | **OPTIONAL / FUTURE** | Deprioritized in favor of Google & Apple for travel MVP. |
| **24**| **Account Conflict Linking** | **MISSING** | **PRODUCT TARGET** | Merges OAuth identities to existing email without duplicate users. |
| **25**| **Brute-Force Rate Limiting**| **MISSING** | **PRODUCT TARGET** | NestJS Throttler on `/auth/login` and `/auth/forgot-password`. |

---

## 3. End-to-End Authentication Target Flow Map

```
                                  [ GoMate App Launch ]
                                            │
                                            ▼
                             ┌──────────────────────────────┐
                             │ Session Check (Secure Store) │
                             └──────────────┬───────────────┘
                                            │
                       ┌────────────────────┴────────────────────┐
                       ▼                                         ▼
                 [Valid Token]                             [No/Bad Token]
                       │                                         │
                       ▼                                         ▼
               ┌───────────────┐                         ┌───────────────┐
               │  Main App     │                         │ Login Screen  │
               │  Shell (5 Tab)│                         │ (auth-target) │
               └───────┬───────┘                         └───────┬───────┘
                       │                                         │
       ┌───────────────┴───────────────┐       ┌─────────────────┼─────────────────┐
       ▼                               ▼       ▼                 ▼                 ▼
[Token Expires (401)]            [Settings] [Email/Pass]    [Google OAuth]    [Apple OAuth]
       │                               │       │                 │                 │
       ▼                               ▼       ▼                 ▼                 ▼
┌──────────────┐             ┌────────────────┐│        ┌─────────────────────────────┐
│Silent Refresh│             │Account & Secur.││        │Backend IDToken Verification │
└──────┬───────┘             └────────┬───────┘│        └──────────────┬──────────────┘
       │                              │        │                       │
 ┌─────┴─────┐                        ▼        │         ┌─────────────┴─────────────┐
 │           │               ┌────────────────┐│         ▼                           ▼
[OK]      [Failed]           │Change Password ││   [New Traveler]          [Existing Email Found]
 │           │               │(auth-target)   ││         │                           │
 ▼           ▼               └────────────────┘│         ▼                           ▼
Resume   Prompt Re-login                       │   Create User + Auto-Login   ┌─────────────────────┐
Request  (auth-expired)                        │                              │Account Conflict Card│
                                               │                              │(auth-conflict)      │
                                               │                              └──────────┬──────────┘
                                               │                                         │
                                               │                                [Link / Authenticate]
                                               │                                         │
                                               │                                         ▼
                                               │                              Merge Provider & Login
                                               │
                                ┌──────────────┴──────────────┐
                                ▼                             ▼
                        [Forgot Password]             [Register Account]
                                │                             │
                                ▼                             ▼
                     ┌─────────────────────┐       ┌─────────────────────┐
                     │ Enter Email Screen  │       │ Register Screen     │
                     │ (auth-forgot)       │       │ (Name, Email, Pass) │
                     └──────────┬──────────┘       └──────────┬──────────┘
                                │                             │
                                ▼                             ▼
                     ┌─────────────────────┐       ┌─────────────────────┐
                     │ Neutral Sent Screen │       │ Email Verification  │
                     │ (auth-sent)         │       │ Pending Notice      │
                     └──────────┬──────────┘       │ (auth-verify)       │
                                │                  └──────────┬──────────┘
                                ▼                             │
                     ┌─────────────────────┐                  ▼
                     │ Reset Password Link │           Verify Link Clicked
                     │ (auth-reset)        │                  │
                     └──────────┬──────────┘                  ▼
                                │                      User Marked isVerified
                                ▼
                     ┌─────────────────────┐
                     │ Success Screen      │
                     │ (auth-success)      │
                     └──────────┬──────────┘
                                │
                                ▼
                           Login Screen
```

---

## 4. Subsystem Target Specifications

### 4.1. Password Recovery Pipeline (Target A)

To protect traveler privacy and prevent account harvesting, password recovery strictly complies with **anti-enumeration principles**:

1. **Request Endpoint (`POST /auth/forgot-password`):**
   - User enters email address.
   - Server returns identical generic response regardless of whether the email exists in the database:
     `"Nếu email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu."`
   - Zero difference in HTTP response code (`200 OK`) and timing (constant-time execution).
2. **Cryptographic Reset Token:**
   - Generated via `crypto.randomBytes(32).toString('hex')`.
   - Stored in PostgreSQL `password_resets` table (hashed with SHA-256):
     - `id UUID`, `user_id UUID`, `token_hash VARCHAR(64)`, `expires_at TIMESTAMPTZ`, `used_at TIMESTAMPTZ`.
   - **Expiration:** Strictly $15\text{ minutes}$.
   - **One-time use:** Immediately invalidated upon successful reset (`used_at = now()`).
3. **Reset Screen (`auth-target-mobile-reset-password-r2.png`):**
   - User arrives via deep link (`gomate://reset-password?token=...`).
   - Fields: `Mật khẩu mới`, `Xác nhận mật khẩu mới`.
   - Validation rules: Minimum 8 characters, at least 1 uppercase letter, 1 lowercase letter, 1 number.
   - Endpoint: `POST /auth/reset-password` (`{ token, newPassword }`).
4. **Success Screen (`auth-target-mobile-reset-success-r2.png`):**
   - Icon: Green check circle.
   - Title: `Đặt lại mật khẩu thành công`.
   - Body: `Mật khẩu của bạn đã được cập nhật an toàn. Vui lòng đăng nhập bằng mật khẩu mới.`
   - Primary CTA: `[Đăng nhập ngay]` (Navigates to `/login`).

### 4.2. Authenticated Password Change Pipeline (Target B)

Accessible only within the authenticated app shell (`Settings` $\rightarrow$ `Tài khoản & Bảo mật` $\rightarrow$ `Đổi mật khẩu`):

1. **Screen (`auth-target-mobile-change-password-r2.png`):**
   - Fields:
     1. `Mật khẩu hiện tại` (validates with `bcrypt.compare`).
     2. `Mật khẩu mới` ($\ge 8$ chars, distinct from current password).
     3. `Xác nhận mật khẩu mới` (must match new password).
   - Visibility toggle on all 3 fields.
2. **Endpoint:** `POST /auth/change-password` (Headers: `Authorization: Bearer <token>`).
   - Body: `{ currentPassword, newPassword }`.
   - Error cases:
     - Current password mismatch: `400 Bad Request` $\rightarrow$ `"Mật khẩu hiện tại không chính xác."`.
     - Identical password: `400 Bad Request` $\rightarrow$ `"Mật khẩu mới không được trùng mật khẩu cũ."`.
3. **Success State (`auth-target-mobile-change-password-success-r2.png`):**
   - Clean confirmation dialog/screen: `"Đổi mật khẩu thành công"`.
   - Option to remain logged in (token refreshed) or re-login.

### 4.3. Email Verification Pipeline (Target C)

Ensures deliverability of travel itineraries, emergency alerts, and buddy matching notices:

1. **Lifecycle State:**
   - Registration creates `User` with `isVerified = false`.
   - Registration triggers background dispatch of verification email.
2. **User Experience (`auth-target-mobile-email-verification-r2.png`):**
   - Persistent informational banner or non-blocking prompt:
     `"Vui lòng xác thực email để bảo vệ tài khoản và nhận cập nhật chuyến đi."`
   - Actions: `[Mở ứng dụng Email]`, `[Gửi lại email xác thực]`.
   - Rate limiting: Resend button has a 60-second cooldown timer.
3. **Endpoint:** `POST /auth/verify-email` (`{ token }`) and `POST /auth/resend-verification`.
   - Deep link: `https://gomate.travel/verify-email?token=...`.
   - Successful verification updates `User.isVerified = true`.

### 4.4. Social OAuth & Account Linking Pipeline (Target D & E)

GoMate targets **Google** and **Apple** as the two tier-1 social identity providers (Facebook is optional/future):

1. **User Experience:**
   - Primary Login screen presents:
     - Divider: `── Hoặc đăng nhập với ──`
     - Social button 1: `Tiếp tục với Google` (Official Google G logo, white surface).
     - Social button 2: `Tiếp tục với Apple` (Official Apple logo, black surface).
2. **Provider Handshake & Loading (`auth-target-mobile-social-loading-r2.png`):**
   - Modal overlay during OAuth token exchange:
     `"Đang kết nối với Google..."` / `"Đang kết nối với Apple..."`.
3. **Account Conflict & Linking (`auth-target-mobile-social-conflict-r2.png`):**
   - **The Conflict Problem:** A user previously registered with `email: user@gmail.com` using Email/Password. Later, they click "Continue with Google" using the same email address.
   - **Strict Policy: ZERO DUPLICATE USERS.** The system shall NOT create a second account.
   - **Resolution Flow:**
     - Backend detects email collision with an existing password-based account.
     - Displays Conflict Screen:
       - Title: `Tài khoản đã tồn tại`
       - Message: `Email user@gmail.com đã được đăng ký bằng mật khẩu. Vui lòng nhập mật khẩu tài khoản hiện tại để liên kết với tài khoản Google.`
       - Field: `Mật khẩu tài khoản GoMate`.
       - CTA: `[Xác nhận và liên kết]`.
     - Upon confirmation, backend links `google_id` to existing `User` record and issues authentication tokens.

### 4.5. Client Session Hardening (Silent Refresh & Concurrency Lock) (Target F)

1. **Concurrency Lock Algorithm (Dio Interceptor):**
   ```dart
   // Conceptual Target Interceptor Logic
   bool _isRefreshing = false;
   final List<Completer<void>> _queue = [];
   
   onError: (DioException error, handler) async {
     if (error.response?.statusCode == 401 && !isAuthEndpoint) {
       if (!_isRefreshing) {
         _isRefreshing = true;
         try {
           final newTokens = await authRepo.refreshToken();
           _isRefreshing = false;
           // Release queued requests
           for (final c in _queue) { c.complete(); }
           _queue.clear();
           // Retry original request with new token
           return handler.resolve(await retry(error.requestOptions));
         } catch (refreshErr) {
           _isRefreshing = false;
           for (final c in _queue) { c.completeError(refreshErr); }
           _queue.clear();
           await authRepo.clearTokens();
           // Trigger session expired UX
           return handler.next(error);
         }
       } else {
         // Queue concurrent requests while refresh is in flight
         final completer = Completer<void>();
         _queue.add(completer);
         await completer.future;
         return handler.resolve(await retry(error.requestOptions));
       }
     }
     handler.next(error);
   }
   ```
2. **Preventing Refresh Loops:**
   - If `/auth/refresh` itself returns 401 $\rightarrow$ immediately abort, purge tokens, and redirect to `/login`. Never retry a failed refresh request.

### 4.6. Secure Storage Transition (Target G)

- **Target Package:** `flutter_secure_storage: ^9.0.0`
- **Android Target:** `EncryptedSharedPreferences` backed by Android KeyStore (AES-256 GCM).
- **iOS Target:** iOS Keychain Services with `kSecAttrAccessibleAfterFirstUnlock`.
- **Migration Strategy:** On startup, if tokens exist in `SharedPreferences`, migrate them to `FlutterSecureStorage` and delete the plaintext entries.

### 4.7. Abuse Prevention & Security Hardening (Target H)

1. **Rate Limiting (NestJS `@nestjs/throttler`):**
   - `POST /auth/login`: Maximum 5 attempts per 15 minutes per IP + email combination.
   - `POST /auth/forgot-password`: Maximum 3 requests per hour per IP.
   - `POST /auth/register`: Maximum 3 registrations per hour per IP.
2. **Logging Sanitization:**
   - Passwords, reset tokens, and authorization headers are scrubbed from server stdout and analytics events.

---

## 5. Conceptual Backend API Target Contract

```typescript
// TARGET DTO CONTRACTS (CONCEPTUAL ONLY - DO NOT IMPLEMENT IN CURRENT TASK)

// POST /auth/forgot-password
export class ForgotPasswordDto {
  @IsEmail()
  email: string;
}

// POST /auth/reset-password
export class ResetPasswordDto {
  @IsString()
  @IsNotEmpty()
  token: string;

  @IsString()
  @MinLength(8)
  @Matches(/((?=.*\d)|(?=.*\W+))(?![.\n])(?=.*[A-Z])(?=.*[a-z]).*$/, {
    message: 'Mật khẩu phải chứa ít nhất 1 chữ hoa, 1 chữ thường và 1 chữ số',
  })
  newPassword: string;
}

// POST /auth/change-password
export class ChangePasswordDto {
  @IsString()
  @IsNotEmpty()
  currentPassword: string;

  @IsString()
  @MinLength(8)
  newPassword: string;
}

// POST /auth/oauth/google
export class GoogleAuthDto {
  @IsString()
  @IsNotEmpty()
  idToken: string;
}

// POST /auth/oauth/apple
export class AppleAuthDto {
  @IsString()
  @IsNotEmpty()
  identityToken: string;

  @IsOptional()
  @IsString()
  fullName?: string;
}

// POST /auth/link-account
export class LinkAccountDto {
  @IsString()
  provider: 'google' | 'apple';

  @IsString()
  providerToken: string;

  @IsString()
  currentPassword: string;
}
```

---

## 6. Target Visual Mockup Evidence Registry (R2)

Rendered via headless Microsoft Edge (`--headless=new`, `--force-device-scale-factor=1`, `--hide-scrollbars`) at native resolutions and stored in `docs/audit/evidence/ui-08.2.3.17-r2/`:

| Mockup Artifact | Viewport | Target Resolution | Key UX Elements & Architecture Classification | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`auth-target-mobile-login-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-login-r2.png) | Mobile | $390 \times 844$ | Complete Product Target Login: Email/Password inputs, `Quên mật khẩu?` link, `Tiếp tục với Google`, `Tiếp tục với Apple` social buttons, `Đăng ký ngay` link. | **TARGET MASTER** |
| [`auth-target-mobile-forgot-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-forgot-password-r2.png) | Mobile | $390 \times 844$ | Password recovery email submission: Informational header, Email input, Primary CTA `[Gửi hướng dẫn đặt lại mật khẩu]`, Back button. | **TARGET MASTER** |
| [`auth-target-mobile-forgot-sent-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-forgot-sent-r2.png) | Mobile | $390 \times 844$ | Anti-enumeration confirmation screen: Mail sent icon, generic confirmation copy, `[Mở ứng dụng Email]`, countdown resend link. | **TARGET MASTER** |
| [`auth-target-mobile-reset-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-reset-password-r2.png) | Mobile | $390 \times 844$ | Deep-link password reset: New password, Confirm password, complexity requirements check-list, Primary CTA `[Cập nhật mật khẩu]`. | **TARGET MASTER** |
| [`auth-target-mobile-reset-success-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-reset-success-r2.png) | Mobile | $390 \times 844$ | Reset success confirmation: Green check badge, confirmation body, Primary CTA `[Đăng nhập ngay]`. | **TARGET MASTER** |
| [`auth-target-mobile-email-verification-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-email-verification-r2.png) | Mobile | $390 \times 844$ | Verification pending experience: Email illustration, instructions to check inbox, `[Xác nhận đã kích hoạt]`, `[Gửi lại email]`. | **TARGET MASTER** |
| [`auth-target-mobile-social-loading-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-social-loading-r2.png) | Mobile | $390 \times 844$ | OAuth in-flight state: Clean modal overlay with Google/Apple logo, spinner, `"Đang kết nối với Google..."`. | **TARGET MASTER** |
| [`auth-target-mobile-social-conflict-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-social-conflict-r2.png) | Mobile | $390 \times 844$ | Account linking prompt: Explains existing password account under same email, password verification input, `[Xác nhận và liên kết]`. | **TARGET MASTER** |
| [`auth-target-mobile-change-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-change-password-r2.png) | Mobile | $390 \times 844$ | Authenticated Change Password form (Settings): Current password, New password, Confirm password, Primary CTA `[Lưu mật khẩu mới]`. | **TARGET MASTER** |
| [`auth-target-mobile-change-password-success-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-change-password-success-r2.png) | Mobile | $390 \times 844$ | Password changed confirmation: Confirmation notice with option to return to Settings. | **TARGET MASTER** |
| [`auth-target-desktop-login-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-desktop-login-r2.png) | Desktop | $1440 \times 900$ | Product Target Desktop Login: 2-column layout with Google & Apple OAuth buttons, Email/Password, and Forgot Password link. | **TARGET MASTER** |
| [`auth-target-desktop-forgot-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-desktop-forgot-password-r2.png) | Desktop | $1440 \times 900$ | Product Target Desktop Forgot Password: Split layout with instructions card and email submission. | **TARGET MASTER** |

---

## 7. Implementation Dependency Map & Execution Roadmap

To ensure maintainability and security, future engineering execution shall proceed in strict sequential order:

```
[ AUTH-01: Secure Token Storage ]
              │
              ▼
[ AUTH-02: Global 401 & Silent Refresh Interceptor ]
              │
              ▼
[ AUTH-03: Rate Limiting & Throttler Setup ]
              │
              ▼
[ AUTH-04: Email Dispatcher Provider (Resend/SendGrid) ]
              │
              ▼
[ AUTH-05: Forgot & Reset Password Backend Pipeline ]
              │
              ▼
[ AUTH-06: Forgot & Reset Password Mobile Flutter UI ]
              │
              ▼
[ AUTH-07: Change Password Authenticated Endpoint & UI ]
              │
              ▼
[ AUTH-08: Email Verification Pipeline & Banner UI ]
              │
              ▼
[ AUTH-09: Google OAuth Handshake & Token Validation ]
              │
              ▼
[ AUTH-10: Apple OAuth Handshake & Token Validation ]
              │
              ▼
[ AUTH-11: Account Collision & Provider Linking Engine ]
              │
              ▼
[ AUTH-12: End-to-End Security Audit & Penetration Testing ]
```

### Milestone Specifications

1. **AUTH-01 (Secure Storage):** Add `flutter_secure_storage` to `apps/mobile/pubspec.yaml`; refactor `AuthRepository` to store `access_token` and `refresh_token` in Keychain / Keystore.
2. **AUTH-02 (Silent Refresh Interceptor):** Enhance `api_client.dart` with a queue-backed Dio 401 retry interceptor that calls `POST /auth/refresh`.
3. **AUTH-03 (Rate Limiting):** Install `@nestjs/throttler` in `apps/backend/`; configure guards on auth controllers.
4. **AUTH-04 (Email Delivery):** Configure transactional email service in NestJS config for sending password resets and verification links.
5. **AUTH-05 & 06 (Password Recovery):** Implement `POST /auth/forgot-password` and `POST /auth/reset-password`; build Flutter recovery flow screens.
6. **AUTH-07 (Change Password):** Add `POST /auth/change-password`; build Settings screen.
7. **AUTH-08 (Email Verification):** Add verification token table in schema; build verification link handler.
8. **AUTH-09 & 10 (Social OAuth):** Integrate Google Sign-In and Sign in with Apple SDKs in Flutter; add IDToken verification endpoints in backend.
9. **AUTH-11 (Account Linking):** Implement conflict detection and account linking transactions in Prisma.
10. **AUTH-12 (E2E QA):** Verify anti-enumeration, rate-limiting thresholds, token expiration, and concurrency locks via Playwright and Flutter integration tests.

---

## 8. Architectural Invariants & Governance Declaration

1. **Runtime Honesty Preserved:** Nothing in this V2 Product Target document alters the classification of `TASK 08.2.3.17 V1`. The current codebase baseline remains strictly limited to email/password authentication without social login, password recovery, or silent refresh.
2. **Visual Evidence Isolation:** The 9 master visual mockups of V1 (`docs/audit/evidence/ui-08.2.3.17/`) remain untouched and authoritative for current runtime reality. All product target visuals reside exclusively in `docs/audit/evidence/ui-08.2.3.17-r2/`.
3. **Zero Production Mutation:** This task is purely architectural and visual design. No production code in `apps/` and no database migrations were created.
