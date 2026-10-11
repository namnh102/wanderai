# Authentication Flow

## Architecture

```
Flutter App
    |
    v
LoginScreen / RegisterScreen
    |
    v
AuthNotifier (Riverpod StateNotifier)
    |
    v
AuthRepository
    |
    v
Dio (API Client with JWT interceptor)
    |
    v
NestJS POST /auth/login | /auth/register
    |
    v
AuthService (bcrypt, Prisma, JwtService)
    |
    v
PostgreSQL (users table)
    |
    v
JWT access_token + refresh_token
    |
    v
SharedPreferences (local storage)
    |
    v
GoRouter redirect (auth state → route)
```

## API Contract

### POST /auth/login
Request: `{email: string, password: string}`
Success 200: `{success: true, data: {access_token: "...", refresh_token: "..."}, timestamp: "..."}`
Error 401: `{success: false, statusCode: 401, message: "Email hoac mat khau khong dung"}`
Error 400: `{success: false, statusCode: 400, message: "validation error"}`

### POST /auth/register
Request: `{email: string, password: string, name: string}`
Success 201: `{success: true, data: {access_token: "...", refresh_token: "..."}, timestamp: "..."}`
Error 400: `{success: false, statusCode: 400, message: "Email da duoc su dung"}`

### POST /auth/refresh
Request: `{refresh_token: string}`
Success 200: `{success: true, data: {access_token: "...", refresh_token: "..."}}`

## Auth State Machine

```
App Start
    |
    v
[unknown] --> restoreSession()
    |
    +-- token exists --> [authenticated]
    |
    +-- no token    --> [unauthenticated] --> /login
    
Login success --> [authenticated] --> /
Login failure --> [unauthenticated] (with error message)
Logout        --> [unauthenticated] --> /login
```

## Route Protection (GoRouter)

- `unknown` state: no redirect (let auth init complete)
- `unauthenticated` + not on login/register: redirect to `/login`
- `authenticated` + on login/register: redirect to `/`

## Token Storage

**Mechanism:** SharedPreferences
**Keys:** `access_token`, `refresh_token`

**Limitation:** SharedPreferences stores tokens in plaintext on disk.
For thesis MVP, this is acceptable. For production, use `flutter_secure_storage`
with platform-specific encryption (Keychain on iOS, EncryptedSharedPreferences on Android).

## Error Mapping

| HTTP Status | Condition | User Message |
|-------------|-----------|-------------|
| 401 | Wrong credentials | Email hoac mat khau khong dung. |
| 400 | Duplicate email | Email da duoc su dung. |
| 400 | Validation error | (message from server) |
| timeout | Network timeout | Khong the ket noi may chu. Vui long thu lai. |
| connection | No network | Khong co ket noi mang. |
| other | Server error | Co loi xay ra. Vui long thu lai. |

## Test Coverage

| Test | Type | File |
|------|------|------|
| Login screen renders | Widget | auth_test.dart |
| Invalid email rejected | Widget | auth_test.dart |
| Short password rejected | Widget | auth_test.dart |
| Register screen renders | Widget | auth_test.dart |
| Auth state transitions | Unit | auth_test.dart |
| Login updates state | Unit | auth_test.dart |
| Logout clears state | Unit | auth_test.dart |
| Session restore (no token) | Unit | auth_test.dart |
| Session restore (with token) | Unit | auth_test.dart |
| App starts | Widget | widget_test.dart |
| Backend login/register E2E | Integration | auth.e2e-spec.ts |
