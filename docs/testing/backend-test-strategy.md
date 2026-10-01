# Backend Test Strategy

## Framework
- **Runner:** Jest 29
- **HTTP Testing:** Supertest 7
- **NestJS Integration:** @nestjs/testing
- **Language:** TypeScript via ts-jest

## Test Types

### E2E Integration Tests (`test/*.e2e-spec.ts`)
Full application bootstrap with real database connection.
Tests verify HTTP endpoints end-to-end including:
- Request routing
- DTO validation (class-validator)
- Service logic
- Database queries (Prisma)
- Response transformation (TransformInterceptor wraps in `{success, data, timestamp}`)
- Error handling (HttpExceptionFilter)

## Database Strategy

**Current approach:** Tests use the development database (same `DATABASE_URL` from `.env`).

**Test data isolation:**
- Auth tests create a unique test user with timestamped email (`test_auth_{timestamp}@wanderai.test`)
- Auth tests clean up created users in `afterAll`
- Destination tests read existing seeded data (non-destructive)
- Health tests have no database dependency

**Future improvement:** When test volume grows, introduce a dedicated test database or use Prisma `$transaction` rollback pattern.

**DO NOT:**
- Delete development data during tests
- Reset/truncate tables
- Use production database
- Hard-code real credentials

## Commands

```bash
# Run all E2E tests
npx jest --config test/jest-e2e.json --verbose

# Run specific test file
npx jest --config test/jest-e2e.json test/health.e2e-spec.ts

# Run with coverage
npx jest --config test/jest-e2e.json --coverage
```

## Current Test Coverage

| File | Tests | Assertions |
|------|-------|-----------|
| health.e2e-spec.ts | 2 | HTTP 200, response structure, valid timestamp |
| auth.e2e-spec.ts | 7 | Login success/fail, register success/duplicate, validation errors |
| destinations.e2e-spec.ts | 5 | List structure, fields, limit, region filter, popular |
| **Total** | **14** | |

## Known Limitations

1. Tests share the development database — no isolated test DB yet
2. No unit tests for individual services (only E2E)
3. No test for authenticated endpoints (trips, reviews — need JWT in test)
4. ESLint has 27 warnings (all `any` type / unused vars, 0 errors)
5. No CI pipeline yet
