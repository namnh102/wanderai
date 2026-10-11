# GoMate Design Audit & Verification Report: TASK 08.2.3.17-R2.2
# GoMate Authentication — Final Contract Consistency Closure

- **Task Reference:** `TASK 08.2.3.17-R2.2`
- **Module:** GoMate Authentication & Session Lifecycle (`docs/design/gomate-authentication-product-target-v2.md`)
- **Status:** **FINAL AUTH PRODUCT CONTRACT LOCKED**
- **Date:** October 7, 2026
- **Mode:** Final Micro-Fix & Multi-Document Reconciliation (Zero production changes, zero schema changes)

---

## 1. Residual Inconsistencies Found & Resolved

| # | Residual Issue | Prior Condition | Final Canonical Correction |
| :-: | :--- | :--- | :--- |
| **1** | **ResetPasswordDto Validation Message** | Stale message in conceptual DTO: `'Mật khẩu phải chứa ít nhất 1 chữ hoa, 1 chữ thường và 1 chữ số'` (thiếu nhánh ký tự đặc biệt). | Updated to exact canonical string: `'Mật khẩu tối thiểu 8 ký tự, có ít nhất 1 chữ hoa, 1 chữ thường, và ít nhất 1 chữ số hoặc ký tự đặc biệt.'` |
| **2** | **ChangePasswordDto Validator Parity** | `ChangePasswordDto` only had `@MinLength(8)` and lacked `@Matches(...)` complexity validator. | Symmetrically applied the identical `@Matches(...)` regex and message to `ChangePasswordDto.newPassword`. |
| **3** | **Vocabulary Completeness** | Matrices extensively utilized `MISSING` in Tier 1 column, but the formal classification vocabulary section omitted `MISSING` from its definitions. | Formalized the complete **Six-State Classification Vocabulary** across both Master Contract and Audit Report, explicitly stating that `Current = MISSING` combined with `Target = PRODUCT TARGET` is the expected non-contradictory relationship. |
| **4** | **Server Token Blacklist Classification** | Row 25 listed `Tier 1 = EXCLUDED` instead of `MISSING`. | Reconciled row 25 Tier 1 to `MISSING` (since runtime code is absent), while preserving `Tier 2 = FUTURE`. |

---

## 2. Password DTO Conceptual Correction

Both `ResetPasswordDto` and `ChangePasswordDto` now enforce the **100% identical** validation rule and error message:

```typescript
// CANONICAL CONCEPTUAL VALIDATOR (DESIGN CONTRACT ONLY - NO CODE IN APPS/)
@IsString()
@MinLength(8)
@Matches(
  /((?=.*\d)|(?=.*\W+))(?![.\n])(?=.*[A-Z])(?=.*[a-z]).*$/,
  {
    message:
      'Mật khẩu tối thiểu 8 ký tự, có ít nhất 1 chữ hoa, 1 chữ thường, và ít nhất 1 chữ số hoặc ký tự đặc biệt.',
  },
)
newPassword: string;
```

### Full DTO Implementations in Contract:
```typescript
// POST /auth/reset-password
export class ResetPasswordDto {
  @IsString()
  @IsNotEmpty()
  token: string;

  @IsString()
  @MinLength(8)
  @Matches(
    /((?=.*\d)|(?=.*\W+))(?![.\n])(?=.*[A-Z])(?=.*[a-z]).*$/,
    {
      message:
        'Mật khẩu tối thiểu 8 ký tự, có ít nhất 1 chữ hoa, 1 chữ thường, và ít nhất 1 chữ số hoặc ký tự đặc biệt.',
    },
  )
  newPassword: string;
}

// POST /auth/change-password
export class ChangePasswordDto {
  @IsString()
  @IsNotEmpty()
  currentPassword: string;

  @IsString()
  @MinLength(8)
  @Matches(
    /((?=.*\d)|(?=.*\W+))(?![.\n])(?=.*[A-Z])(?=.*[a-z]).*$/,
    {
      message:
        'Mật khẩu tối thiểu 8 ký tự, có ít nhất 1 chữ hoa, 1 chữ thường, và ít nhất 1 chữ số hoặc ký tự đặc biệt.',
    },
  )
  newPassword: string;
}
```

---

## 3. Six-State Classification Vocabulary

The architecture vocabulary is locked to 6 explicit states:

- **`CURRENT`:** Đã được xác minh có runtime code hoạt động trong repository.
- **`PARTIAL`:** Đã tồn tại một phần nhưng chưa hoàn chỉnh end-to-end.
- **`MISSING`:** Chưa có implementation trong current runtime.
- **`PRODUCT TARGET`:** Bắt buộc phải triển khai trước production-ready release.
- **`FUTURE`:** Để sau MVP / post-launch.
- **`EXCLUDED`:** Cố ý không nằm trong phạm vi sản phẩm hiện tại.

> [!NOTE]
> **Two-Tier Independence Invariant:**
> Một capability có thể có:
> - **Current Runtime:** `MISSING` (hoặc `PARTIAL`)
> - **Product Target:** `PRODUCT TARGET` (hoặc `FUTURE`, `EXCLUDED`)
>
> Đây KHÔNG phải là mâu thuẫn (contradiction) mà là bản chất của mô hình quản trị hai tầng: phản ánh trung thực hiện trạng code mà không ngăn cản việc thiết lập đích đến kiến trúc hoàn chỉnh.

---

## 4. Final 29-Capability Matrix Validation

| # | Capability Dimension | Tier 1 (Current Runtime V1) | Tier 2 (Product Target V2) | Technical Dependency / Implementation Plan |
| :-: | :--- | :---: | :---: | :--- |
| **1** | **Email / Password Login** | **CURRENT** | **CURRENT** | Verified runtime baseline; standard email normalization & bcrypt verify. |
| **2** | **Account Registration** | **CURRENT** | **CURRENT** | Verified runtime baseline; create `User` in PostgreSQL. |
| **3** | **Input Validation** | **CURRENT** | **CURRENT** | Client-side reactive validation + NestJS `ValidationPipe`. |
| **4** | **Duplicate Email Handling** | **CURRENT** | **CURRENT** | 400 Bad Request mapped to natural Vietnamese error copy. |
| **5** | **Wrong-Password Handling** | **CURRENT** | **CURRENT** | Generic 401 Unauthorized prevents username enumeration. |
| **6** | **Loading & Button Disabled State**| **CURRENT** | **CURRENT** | Inline CTA spinner and disabled inputs during requests. |
| **7** | **Network Error Handling** | **CURRENT** | **CURRENT** | Vietnamese messages for timeout and offline conditions. |
| **8** | **Client Logout** | **CURRENT** | **CURRENT** | Purges tokens from local storage; resets Riverpod state. |
| **9** | **Startup Session Restore** | **CURRENT** | **CURRENT** | Decodes token locally before attempting session restore. |
| **10**| **Secure Token Storage (Mobile)** | **PARTIAL** | **PRODUCT TARGET** | Migrate from `SharedPreferences` to `flutter_secure_storage` (KeyStore/Keychain). |
| **11**| **Global 401 Interceptor** | **PARTIAL** | **PRODUCT TARGET** | Dio error interceptor with queued retries on token refresh. |
| **12**| **Silent Token Refresh (Mobile)** | **PARTIAL** | **PRODUCT TARGET** | Client queue locking to avoid refresh loops & race conditions. |
| **13**| **Expired-Session Handling** | **PARTIAL** | **PRODUCT TARGET** | Clean in-app modal prompt redirecting to `/login` when refresh fails. |
| **14**| **Forgot Password Request** | **MISSING** | **PRODUCT TARGET** | Anti-enumeration response + background email dispatch. |
| **15**| **Reset Password Pipeline** | **MISSING** | **PRODUCT TARGET** | $15\text{m}$ one-time cryptographic token + password update via deep link. |
| **16**| **Authenticated Change Password** | **MISSING** | **PRODUCT TARGET** | Settings endpoint requiring current password + new password validation. |
| **17**| **Email Verification Pipeline** | **MISSING** | **PRODUCT TARGET** | Mail provider integration + verification token + unverified banner. |
| **18**| **Google Social OAuth** | **MISSING** | **PRODUCT TARGET** | Google Sign-In SDK + `POST /auth/oauth/google` IDToken validation. |
| **19**| **Apple Social OAuth** | **MISSING** | **PRODUCT TARGET** | Sign in with Apple SDK + `POST /auth/oauth/apple` credential validation. |
| **20**| **Account Linking Collision** | **MISSING** | **PRODUCT TARGET** | Prevents duplicate user; prompts password via `POST /auth/link-account`. |
| **21**| **Rate Limiting & Abuse Protection**| **MISSING** | **PRODUCT TARGET** | NestJS Throttler on `/auth/login`, `/auth/forgot-password`, `/auth/register`. |
| **22**| **Facebook Social Login** | **MISSING** | **EXCLUDED** | Deprioritized in favor of Google & Apple for travel MVP. |
| **23**| **Guest / Anonymous Browse** | **MISSING** | **EXCLUDED** | GoMate requires authenticated profile for itineraries, safety & sync. |
| **24**| **Remember Me Checkbox** | **MISSING** | **EXCLUDED** | Continuous session via hardware secure storage; no UI checkbox. |
| **25**| **Server Token Blacklist** | **MISSING** | **FUTURE** | Preserves stateless JWT; Redis blacklist deferred post-launch. |
| **26**| **Biometric Login (`local_auth`)** | **MISSING** | **FUTURE** | Hardware biometric unlock on top of secure storage deferred post-MVP. |
| **27**| **Active Sessions Management** | **MISSING** | **FUTURE** | Multi-device remote session revocation table deferred post-launch. |
| **28**| **Multi-Factor Auth (MFA / TOTP)**| **MISSING** | **FUTURE** | Authenticator app TOTP deferred post-MVP (guide/admin tier). |
| **29**| **Passwordless / Magic Link** | **MISSING** | **FUTURE** | Deferred post-launch; email/password and social OAuth prioritize MVP. |

---

## 5. Visual Evidence Verification

Confirmed directly against rendered mockups in `docs/audit/evidence/ui-08.2.3.17-r2/`:

1. **`auth-target-mobile-login-r2.png`:**
   - `Quên mật khẩu?` link: **Present**
   - `Tiếp tục với Google` button: **Present**
   - `Tiếp tục với Apple` button: **Present**
   - Guest CTA button: **ZERO (Complies with EXCLUDED)**
   - Remember Me checkbox: **ZERO (Complies with EXCLUDED)**
2. **`auth-target-mobile-reset-password-r2.png`:**
   - Security checklist:
     - `✓ Tối thiểu 8 ký tự`
     - `✓ Ít nhất 1 chữ hoa và 1 chữ thường`
     - `✓ Ít nhất 1 chữ số hoặc ký tự đặc biệt`
   - Parity with DTO: **100% Match**
3. **No visual regeneration needed:** Both artifacts already physically conform to canonical requirements.

---

## 6. Git Invariant Verification

- `git diff apps/` ➔ **TRỐNG (0 dòng thay đổi)**
- `git diff apps/backend/prisma/` ➔ **TRỐNG (0 dòng thay đổi)**
- `docs/weekly-reports/W01/weekly-report-W01.docx` ➔ **UNSTAGED & UNCOMMITTED**

---

## 7. Acceptance Gate Checklist

| Checklist Item | Standard | Status |
| :--- | :--- | :---: |
| **ResetPasswordDto conceptual message** | Matches canonical password policy | **PASS** |
| **ChangePasswordDto conceptual rule** | Exactly identical to ResetPasswordDto | **PASS** |
| **Password prose = regex = message = visual** | 100% unified across all docs and mockups | **PASS** |
| **MISSING defined in vocabulary** | Officially defined in six-state vocabulary | **PASS** |
| **29 capability vocabulary** | Strictly uses the 6 valid state tokens | **PASS** |
| **No scope expansion** | Scope locked strictly as per canonical list | **PASS** |
| **12 mockups unchanged** | Verified valid without regeneration | **PASS** |
| **git diff apps/ EMPTY** | 0 production changes | **PASS** |
| **git diff apps/backend/prisma/ EMPTY** | 0 database schema changes | **PASS** |
| **weekly-report-W01.docx unstaged** | Preserved uncommitted | **PASS** |
| **No merge, no push** | Fully branch-isolated | **PASS** |

---

## 8. Final Verdict

All residual contract inconsistencies are resolved and locked.

$$\mathbf{TASK\ 08.2.3.17-R2.2\ =\ FINAL\ AUTH\ PRODUCT\ CONTRACT\ LOCKED}$$

*Execution terminates here. Do NOT start Global Design Review or Task 08.3.*
