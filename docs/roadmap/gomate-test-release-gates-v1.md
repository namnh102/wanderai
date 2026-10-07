# GoMate Test Strategy, Release Gates & Non-Regression Contracts V1
## Multi-Tier Quality Assurance, Security Invariants & Operational Verification

- **Document Reference:** `docs/roadmap/gomate-test-release-gates-v1.md`
- **Scope:** Engineering Quality Assurance & Non-Regression Invariants for GoMate
- **Status:** **TEST & RELEASE GATES LOCKED**
- **Date:** October 7, 2026
- **Companion Specifications:**
  - `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
  - `docs/roadmap/gomate-implementation-dependency-dag-v1.md`

---

## 1. Executive Summary & Verification Mandate

Every work package implemented under `TASK 08.3` must pass through a multi-tier testing pipeline before merging. Most critically, the implementation of new `PRODUCT TARGET` capabilities must **never break or regress** the 36 verified operational `CURRENT` capabilities.

This specification establishes:
1. The **5-Tier Quality Gate Pipeline**.
2. **Workstream-Specific Testing Protocols** (Backend, Flutter, AI-Service, Database, Security).
3. The **11 Immutable Non-Regression Contracts**.
4. **Rollback & Failure Recovery Procedures**.

---

## 2. Multi-Tier Quality Gate Pipeline

Before any feature branch can merge into `develop`, it must satisfy all 5 consecutive gates:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE 5-TIER RELEASE GATE PIPELINE                │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 1: STATIC ANALYSIS & CONTRACT LINTING                             │
│ • Backend: npm run lint && npx tsc --noEmit                            │
│ • Mobile: flutter analyze --no-fatal-infos                             │
│ • Database: npx prisma validate && npx prisma format --check           │
│ • Invariant: Zero lint errors, zero missing type declarations          │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 2: UNIT & STATE ISOLATION TESTS                                   │
│ • Backend: Jest unit tests for domain services and DTO validation      │
│ • Mobile: flutter test test/ for widget states, providers, notifiers   │
│ • AI-Service: pytest tests/test_*.py for prompts and tool schemas      │
│ • Invariant: Minimum 80% statement coverage on newly introduced logic  │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 3: INTEGRATION & API CONTRACT TESTS                               │
│ • Backend: Supertest E2E specs against live test PostgreSQL database   │
│ • Mobile: Mocktail / DioAdapter HTTP contract integration tests        │
│ • Invariant: 100% endpoint status code and payload schema parity       │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 4: SECURITY, PRIVACY & ABUSE AUDIT                                │
│ • IDOR checks: User A cannot mutate or read User B's private entities  │
│ • Rate limiting: Exceeding threshold returns HTTP 429                  │
│ • Token expiration: Expired tokens trigger silent refresh or 401       │
│ • Privacy: Phone numbers and private emails strictly masked in responses│
├────────────────────────────────────────────────────────────────────────┤
│ GATE 5: REAL-BROWSER & DEVICE SMOKE VERIFICATION                       │
│ • Flutter Web smoke test on real headless Chrome / device              │
│ • Console inspection: Zero 'GlobalKey' errors, zero 'RenderFlex' leaks │
│ • Navigation round-trip: Back button returns to caller with state intact│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Workstream-Specific Testing Protocols

### 3.1. Backend Testing Protocol (NestJS / PostgreSQL)
1. **DTO Validation Tests:** Every endpoint must test both valid payloads and malformed inputs (assert HTTP 400 with localized validation messages).
2. **Database Integrity Tests:** Verify foreign key constraints, cascade deletes, and unique indices (e.g. `@@unique([groupId, userId])` prevents duplicate group memberships).
3. **Database Performance Benchmarks:** Spatial queries (PostGIS `ST_DWithin`) and full-text searches must execute in $< 50\text{ms}$ on seeded databases.

### 3.2. Mobile Testing Protocol (Flutter / Riverpod)
1. **Widget State Tests:** Every screen must test 5 canonical visual states:
   - `LoadingState`: Skeleton shimmer or progress indicator renders cleanly.
   - `EmptyState`: Meaningful Vietnamese copy with clear CTA.
   - `ContentState`: Correct data binding with zero text clipping.
   - `ErrorState`: Friendly error message with retry button.
   - `OfflineState`: Graceful fallback to cached data or local asset.
2. **Navigation Stack Tests:** Verify deep-link pushes and AppBar back pops preserve prior screen state.
3. **Responsive Density Tests:** Verify $390\text{px}$ mobile viewport renders with **0px horizontal overflow** (`A RenderFlex overflowed...` = **FATAL FAIL**).

### 3.3. AI-Service Testing Protocol (FastAPI / Gemini)
1. **Tool Grounding Contract Tests:** AI planner and Wandy must only cite verified place IDs existing in the PostGIS database.
2. **Action Preview Guard Tests:** AI engines must never directly mutate database records without client-side user confirmation payload (`isUserConfirmed == true`).
3. **Prompt Injection & Guardrail Tests:** Adversarial prompts attempting to elicit system prompt leaks, fake emergency numbers, or autonomous bookings must be neutralized.

### 3.4. Security & Privacy Testing Protocol
1. **Anti-Enumeration Test:** Forgot-password endpoint must return identical HTTP 200 responses and comparable response times for registered and unregistered emails.
2. **Phone Number Masking Test:** Public buddy and group profile endpoints must sanitize phone numbers (`+84 *** *** 123` or omitted).
3. **Account Linking Collision Test:** Logging in with Google using an existing password email must trigger HTTP 409 conflict and require password validation before linking.

---

## 4. The 11 Immutable Non-Regression Contracts

Any PR that causes a regression in any of the following **11 Invariants** will be automatically rejected:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE 11 IMMUTABLE NON-REGRESSION CONTRACTS            │
├────┬─────────────────────────┬─────────────────────────────────────────┤
│ #  | Capability Area         │ Immutable Operational Requirement       │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 1  │ Map Camera Preservation │ Returning from Place Detail to Map      │
│    │                         │ strictly preserves pan/zoom coordinates.│
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 2  │ Foreground Geolocation  │ GPS fix is strictly on-demand on user   │
│    │                         │ tap; continuous background track is OFF.│
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 3  │ Haversine Distance Calc │ Distance chip reflects client-side      │
│    │                         │ formula based on real active fix.       │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 4  │ OSM Attribution Bar     │ Basemap tiles & POIs retain visible     │
│    │                         │ "OpenStreetMap contributors" copyright. │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 5  │ Place Data Honesty      │ Places lacking ratings show "Chưa có    │
│    │                         │ đánh giá"; zero fabricated 4.5 averages.│
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 6  │ Wandy Source Chips      │ Recommendations stream with grounded    │
│    │                         │ clickable source provenance chips.      │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 7  │ AI Planner Safeguard    │ Itinerary generation renders preview    │
│    │                         │ sheet; requires explicit overwrite OK.  │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 8  │ Emergency Non-Autonomy  │ Emergency calls must NEVER become       │
│    │                         │ autonomous. Baseline provides native    │
│    │                         │ dialer (`tel:`); once confirmation modal│
│    │                         │ is implemented (WP-SAFE-01), it becomes │
│    │                         │ mandatory before dialer dispatch.       │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 9  │ Profile & Privacy       │ Zero fake presence indicators; private  │
│    │ Boundary                │ fields masked. Before WP-PROF-01: prefs │
│    │                         │ remain read-only. After WP-PROF-01: edit│
│    │                         │ allowed ONLY via validated auth API.    │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 10 │ 5-Tab Navigation Parity │ Mobile bottom bar and Desktop sidebar   │
│    │                         │ share 100% identical 5-tab taxonomy.    │
├────┼─────────────────────────┼─────────────────────────────────────────┤
│ 11 │ Zero GlobalKey Errors   │ Browser console across multi-screen     │
│    │                         │ session must report 0 GlobalKey leaks.  │
└────┴─────────────────────────┴─────────────────────────────────────────┘
```

---

## 5. Rollback Strategy & Incident Recovery

### 5.1. Database Migration Rollback Strategy
Every Prisma migration must include a verified down-migration SQL script in `apps/backend/prisma/migrations/<migration_name>/down.sql`.
- **Destructive Changes Strictly Prohibited:** No migration may drop existing columns or tables without a 2-sprint deprecation grace period.
- **Rollback Execution:**
  ```bash
  npx prisma migrate resolve --rolled-back <migration_name>
  psql -U postgres -d wanderai -f down.sql
  ```

### 5.2. Client Feature Flag Architecture
High-impact capabilities (e.g. Social OAuth, WebSocket Chat, AI Action Bridge) must be wrapped in client-side feature flags:
```dart
if (FeatureFlags.isSocialOAuthEnabled) {
  GoogleSignInButton(),
}
```
If a critical defect emerges in production, the feature can be toggled off instantly via remote config without redeploying the app binary.

### 5.3. Graceful Network Degradation
- If WebSocket chat disconnects, the app falls back to polling `/groups/:id/messages` every 10 seconds.
- If tile streaming fails, the map falls back to cached local vector/raster tiles.
- If online emergency APIs fail, the app falls back to bundled `emergency_directory.json`.

---

## 6. Verification Summary & Sign-off

Compliance with this Test Strategy and Non-Regression Contract guarantees that the implementation of `TASK 08.3` proceeds with **maximum software engineering rigor, zero functional degradation, and bulletproof production stability**.
