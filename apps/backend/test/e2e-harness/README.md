# Live NestJS E2E Test Harness (`apps/backend/test/e2e-harness`)

Test-harness-only runner that boots the unmodified NestJS `AppModule` (with `main.ts`'s `ValidationPipe`, `HttpExceptionFilter`, `TransformInterceptor`, and CORS options) on `127.0.0.1:${E2E_API_PORT:-3000}` and serves out-of-band `E2E_*` test hooks on a separate `127.0.0.1:${E2E_HOOK_PORT:-3001}` HTTP server. Zero test hooks or endpoints exist in `apps/backend/src/`.

## Files
- `e2e-live-server.ts`: Bootstraps `AppModule` via `@nestjs/testing`, overriding only `PrismaService`, `MAIL_TRANSPORT` (`InMemoryTestMailTransport`), `GOOGLE_OAUTH_VERIFIER`, and `FACEBOOK_OAUTH_VERIFIER`. Prints `READY {...}` JSON on stdout when both servers are listening and exits cleanly on `SIGINT`/`SIGTERM`.
- `in-memory-prisma.service.ts`: Stateful in-memory Prisma test double implementing `user`, `profile`, `travelPreference`, `passwordResetToken`, `oAuthAccount`, `destination`, `place`, `youtubePoiUpdate`, `trip`, `tripMember`, `itinerary`, `itineraryItem`, promise-mutex `$transaction`, real `PrismaClientKnownRequestError` (`P2002`), R4 mutation traps on `document`/`placeSource`/`$executeRaw`, and seeded Hạ Long / Tháp Đồng Hồ (`65562a67-84ff-44a0-990d-31917a2a9bd0`) / null-field verified POI (`75562a67-84ff-44a0-990d-31917a2a9bd1`) / 22 extra verified Hạ Long POIs / unverified POI (`00000000-0000-4000-8000-000000000999`) / 2 baseline `Document` rows.
- `test-oauth-verifiers.ts`: Deterministic `TestGoogleOAuthVerifier` and `TestFacebookOAuthVerifier` supporting `E2E_GOOGLE_TEST_ID_TOKEN`, `E2E_FACEBOOK_TEST_ACCESS_TOKEN`, `valid-email:<email>`, `no-email*`, `provider-error*`, and invalid tokens.

## Startup Command (from `D:\Do_an\wanderai_beta_integration\apps\backend`)
```powershell
$env:E2E_API_PORT="3000"
$env:E2E_HOOK_PORT="3001"
$env:YOUTUBE_EVENTS_INTERNAL_SECRET="e2e-youtube-internal-secret"
$env:YOUTUBE_WEBSUB_SECRET="e2e-websub-hmac-secret"
pnpm exec ts-node -r tsconfig-paths/register test/e2e-harness/e2e-live-server.ts
```

## Environment Contract for `tests/e2e_beta/run_e2e.mjs --mode=live`
- `E2E_MAIL_OUTBOX_URL=http://127.0.0.1:3001/mail-outbox`
- `E2E_EXPIRED_RESET_SEED_URL=http://127.0.0.1:3001/seed-expired-reset-token`
- `E2E_DB_STATS_URL=http://127.0.0.1:3001/db-stats`
- `E2E_GOOGLE_TEST_ID_TOKEN=valid-google-token`
- `E2E_FACEBOOK_TEST_ACCESS_TOKEN=valid-fb-token`
- `E2E_YOUTUBE_INTERNAL_SECRET=e2e-youtube-internal-secret`
- `E2E_WEBSUB_SECRET=e2e-websub-hmac-secret`

Run `tests/e2e_beta/run_e2e.mjs` from repo root:
```powershell
node tests/e2e_beta/run_e2e.mjs --mode=live --base-url=http://127.0.0.1:3000 --repo-root=. --mobile-dir=apps/mobile --w07-prep-dir=../w07_offline_retrieval_prep
```
