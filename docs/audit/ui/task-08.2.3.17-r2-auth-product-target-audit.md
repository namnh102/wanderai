# GoMate Design Audit & Verification Report: TASK 08.2.3.17-R2
# GoMate Authentication — Complete Product Target & Future Implementation Contract

- **Task Reference:** `TASK 08.2.3.17-R2`
- **Module:** GoMate Authentication & Session Lifecycle (`docs/design/gomate-authentication-product-target-v2.md`)
- **Status:** **PRODUCT TARGET LOCKED**
- **Date:** October 7, 2026
- **Mode:** Architectural Design, Capability Target Audit & Visual Mockups (Zero production changes, zero schema changes)

---

## 1. Executive Summary

This report delivers the comprehensive **Product Target (Tier 2)** for GoMate Authentication while maintaining total fidelity to the **Current Runtime Baseline (Tier 1)** locked in `TASK 08.2.3.17 V1`.

### Core Achievements
1. **Two-Tier Capability Governance:** Clearly segregates verified runtime features (`CURRENT`) from production requirements (`PRODUCT TARGET`). No un-implemented features (such as social login or password recovery) are misrepresented as operational.
2. **Anti-Enumeration Password Recovery:** Designed an end-to-end recovery pipeline returning identical generic responses regardless of user existence, backed by time-limited ($15\text{m}$) one-time cryptographic tokens.
3. **Social OAuth & Account Linking:** Architected Google and Apple sign-in flows with an explicit email collision policy that enforces **zero duplicate user records** and provides an authenticated account linking prompt.
4. **Session Hardening & Concurrency Locking:** Designed a robust client-side Dio 401 retry interceptor with request queuing to eliminate token refresh race conditions and infinite loops.
5. **Hardware-Backed Secure Storage:** Planned migration from plaintext `SharedPreferences` to `flutter_secure_storage` (Android Keystore / iOS Keychain).
6. **12 Master Product Target Visual Mockups:** Rendered all target screens at native resolutions ($390 \times 844$ and $1440 \times 900$) in a dedicated evidence directory (`docs/audit/evidence/ui-08.2.3.17-r2/`), completely preserving the 9 V1 baseline masters.

---

## 2. Current vs. Product Target Capability Matrix

| # | Capability Dimension | Tier 1 (Current Runtime V1) | Tier 2 (Product Target V2) | Technical Dependency & Implementation Plan |
| :-: | :--- | :---: | :---: | :--- |
| **1** | **Email Login** | **CURRENT** | **KEEP** | Standard email validation and case-insensitive normalization. |
| **2** | **Password Login** | **CURRENT** | **KEEP** | bcrypt comparison against hashed credentials. |
| **3** | **Register Account** | **CURRENT** | **ENHANCED** | Adds background trigger for email verification post-registration. |
| **4** | **Input Validation** | **CURRENT** | **KEEP** | Client-side reactive validation + NestJS `ValidationPipe`. |
| **5** | **Duplicate Email Behavior** | **CURRENT** | **KEEP** | 400 Bad Request mapped to natural Vietnamese error copy. |
| **6** | **Wrong-Password Behavior** | **CURRENT** | **KEEP** | Generic 401 Unauthorized prevents username enumeration. |
| **7** | **Loading State** | **CURRENT** | **KEEP** | Inline CTA spinner and disabled inputs during requests. |
| **8** | **Network Error Handling** | **CURRENT** | **KEEP** | Vietnamese messages for timeout and offline conditions. |
| **9** | **Global 401 Interceptor** | **PARTIAL** | **PRODUCT TARGET** | Dio error interceptor with queued retries on token refresh. |
| **10**| **Access Token Storage** | **CURRENT** (Plaintext) | **PRODUCT TARGET** | Migrates to `flutter_secure_storage` (Keystore/Keychain). |
| **11**| **Refresh Token Storage** | **CURRENT** (Plaintext) | **PRODUCT TARGET** | Hardware-backed encrypted storage for 7-day token. |
| **12**| **Silent Token Refresh** | **PARTIAL** (Backend only)| **PRODUCT TARGET** | Background refresh upon 401 without disrupting user flow. |
| **13**| **Startup Session Restore** | **CURRENT** | **ENHANCED** | Validates JWT expiry locally before attempting restore. |
| **14**| **Expired-Session Handling** | **PARTIAL** | **PRODUCT TARGET** | Re-login prompt modal redirecting to `/login`. |
| **15**| **Client Logout** | **CURRENT** | **KEEP** | Purges tokens from local storage; resets Riverpod state. |
| **16**| **Server Token Blacklist** | **EXCLUDED** | **FUTURE** | Preserves stateless JWT; Redis blacklist deferred. |
| **17**| **Forgot Password** | **MISSING** | **PRODUCT TARGET** | Email dispatcher + time-limited cryptographic reset token. |
| **18**| **Reset Password** | **MISSING** | **PRODUCT TARGET** | Deep link validation + password update endpoint. |
| **19**| **Change Password** | **MISSING** | **PRODUCT TARGET** | Authenticated settings screen requiring current password. |
| **20**| **Email Verification** | **FUTURE** | **PRODUCT TARGET** | Transactional email provider + verification token. |
| **21**| **Google Social Login** | **MISSING** | **PRODUCT TARGET** | Google Sign-In SDK + backend IDToken verification. |
| **22**| **Apple Social Login** | **MISSING** | **PRODUCT TARGET** | Sign in with Apple SDK (mandatory on iOS) + backend verification. |
| **23**| **Facebook Social Login** | **MISSING** | **OPTIONAL / FUTURE** | Deprioritized in favor of Google & Apple for travel MVP. |
| **24**| **Account Linking** | **MISSING** | **PRODUCT TARGET** | Seamlessly connects OAuth identity to existing email user. |
| **25**| **Rate Limiting (Brute-force)**| **MISSING** | **PRODUCT TARGET** | NestJS Throttler on `/auth/login` and `/auth/forgot-password`. |

---

## 3. Subsystem Architecture Specifications

### 3.1. Password Recovery (Anti-Enumeration & Token Lifecycle)
- **Generic Response:** Regardless of email presence, `/auth/forgot-password` returns `200 OK` with:
  `"Nếu email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu."`
- **Token Security:** 32-byte cryptographically secure random token, stored as SHA-256 hash in database, valid for strictly 15 minutes, invalidated immediately after use.
- **Complexity:** Requires minimum 8 characters, mixed case, and numbers.

### 3.2. Social Login & Account Linking
- **Provider Targets:** Google and Apple.
- **Collision Invariant:** When an incoming OAuth identity matches an existing email registered via password, the system prevents duplicate account creation. It prompts the user for their password once to link the provider ID to the canonical `User` record.

### 3.3. Session Hardening & Refresh Lock
- **Interceptor Architecture:** A queue-based Dio interceptor handles 401 errors. The first failing request acquires the refresh lock and calls `POST /auth/refresh`. Subsequent 401s are enqueued. Upon success, all enqueued requests are retried with the new access token. If refresh fails, tokens are cleared and the user is redirected to `/login`.

---

## 4. Visual Evidence Registry (R2 Target Master Mockups)

Rendered via headless Microsoft Edge (`--headless=new`, `--force-device-scale-factor=1`, `--hide-scrollbars`) at native specifications in `docs/audit/evidence/ui-08.2.3.17-r2/`:

| Mockup Artifact | Viewport | Target Resolution | Key UX Elements & Architecture Classification | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`auth-target-mobile-login-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-login-r2.png) | Mobile | $390 \times 844$ | Target Login: Email/Password inputs, `Quên mật khẩu?` link, Google & Apple OAuth buttons, Register navigation. | **TARGET MASTER** |
| [`auth-target-mobile-forgot-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-forgot-password-r2.png) | Mobile | $390 \times 844$ | Recovery request screen: Explanatory header, email field, `[Gửi hướng dẫn đặt lại mật khẩu]`. | **TARGET MASTER** |
| [`auth-target-mobile-forgot-sent-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-forgot-sent-r2.png) | Mobile | $390 \times 844$ | Neutral confirmation: Mail sent icon, generic confirmation copy, `[Mở ứng dụng Email]`, countdown resend link. | **TARGET MASTER** |
| [`auth-target-mobile-reset-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-reset-password-r2.png) | Mobile | $390 \times 844$ | Password reset form: New password, Confirm password, complexity requirements check-list, `[Cập nhật mật khẩu]`. | **TARGET MASTER** |
| [`auth-target-mobile-reset-success-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-reset-success-r2.png) | Mobile | $390 \times 844$ | Success confirmation: Green check badge, confirmation body, `[Đăng nhập ngay]`. | **TARGET MASTER** |
| [`auth-target-mobile-email-verification-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-email-verification-r2.png) | Mobile | $390 \times 844$ | Email verification prompt: Instructions to verify, `[Xác nhận đã kích hoạt]`, `[Gửi lại email]`. | **TARGET MASTER** |
| [`auth-target-mobile-social-loading-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-social-loading-r2.png) | Mobile | $390 \times 844$ | OAuth in-flight state: Clean modal overlay with Google/Apple logo, spinner, `"Đang kết nối với Google..."`. | **TARGET MASTER** |
| [`auth-target-mobile-social-conflict-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-social-conflict-r2.png) | Mobile | $390 \times 844$ | Account linking prompt: Explains existing password account under same email, password verification input, `[Xác nhận và liên kết]`. | **TARGET MASTER** |
| [`auth-target-mobile-change-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-change-password-r2.png) | Mobile | $390 \times 844$ | Authenticated Change Password form (Settings): Current password, New password, Confirm password, `[Lưu mật khẩu mới]`. | **TARGET MASTER** |
| [`auth-target-mobile-change-password-success-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-mobile-change-password-success-r2.png) | Mobile | $390 \times 844$ | Password changed confirmation: Confirmation notice with option to return to Settings. | **TARGET MASTER** |
| [`auth-target-desktop-login-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-desktop-login-r2.png) | Desktop | $1440 \times 900$ | Product Target Desktop Login: 2-column layout with Google & Apple OAuth buttons, Email/Password, and Forgot Password link. | **TARGET MASTER** |
| [`auth-target-desktop-forgot-password-r2.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.17-r2/auth-target-desktop-forgot-password-r2.png) | Desktop | $1440 \times 900$ | Product Target Desktop Forgot Password: Split layout with instructions card and email submission. | **TARGET MASTER** |

---

## 5. Implementation Dependency Roadmap (AUTH-01 to AUTH-12)

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
[ AUTH-04: Email Dispatcher Provider Setup ]
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

---

## 6. Verification & Acceptance Checklist

| Checklist Item | Required Standard | Observed Status | Verdict |
| :--- | :--- | :--- | :---: |
| **1. Baseline V1 Preserved** | 9 master V1 mockups untouched | Retained in `docs/audit/evidence/ui-08.2.3.17/` | **PASS** |
| **2. Two-Tier Classification** | Strict CURRENT vs PRODUCT TARGET separation | All 25 dimensions categorized | **PASS** |
| **3. Anti-Enumeration Design** | Generic responses for forgot-password | Defined in contract and mockups | **PASS** |
| **4. Account Linking Policy** | No duplicate users on email match | Conflict resolution flow specified | **PASS** |
| **5. Silent Refresh Architecture** | Concurrency queue & loop prevention | Complete Dart pseudo-code designed | **PASS** |
| **6. Secure Storage Plan** | Migration from plaintext SharedPreferences | Keychain & Keystore target specified | **PASS** |
| **7. Target Visual Mockups** | 12 new artifacts rendered | Stored in `docs/audit/evidence/ui-08.2.3.17-r2/` | **PASS** |
| **8. Production Code Untouched** | `apps/` 100% clean | `git diff apps/` returns 0 lines | **PASS** |
| **9. Database Schema Untouched** | `schema.prisma` 100% clean | `git diff apps/backend/prisma/` returns 0 lines | **PASS** |
| **10. Weekly Report Unstaged** | `weekly-report-W01.docx` untouched | Preserved unstaged in working tree | **PASS** |

---

## 7. Final Verdict

The GoMate Authentication Product Target (V2) has been fully designed, audited, and visually validated.

$$\mathbf{TASK\ 08.2.3.17-R2\ =\ PRODUCT\ TARGET\ LOCKED}$$

*Execution terminates here. Downstream tasks (Global Design Review or Task 08.3) remain strictly on hold.*
