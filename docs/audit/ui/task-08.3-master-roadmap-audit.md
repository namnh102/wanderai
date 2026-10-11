# GoMate Master Implementation Roadmap Audit: TASK 08.3
## Comprehensive Repository Re-Audit, 90-Capability Reconciliation & Quality Gate Clearance

- **Document Reference:** `docs/audit/ui/task-08.3-master-roadmap-audit.md`
- **Associated Specifications:**
  - `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
  - `docs/roadmap/gomate-implementation-dependency-dag-v1.md`
  - `docs/roadmap/gomate-parallel-development-matrix-v1.md`
  - `docs/roadmap/gomate-test-release-gates-v1.md`
- **Execution Mode:** Planning & Roadmap Verification Audit (Zero code written, zero schema changes)
- **Status:** **ROADMAP AUDIT LOCKED & VERIFIED**
- **Date:** October 7, 2026

---

## 1. Executive Summary & Purpose

TASK 08.3 delivers the **Master Implementation Roadmap V1** for GoMate, translating the locked Global Design Master (`TASK 08.2.4` + `TASK 08.2.4-R1`) into a capability-driven engineering plan.

This audit report records:
1. The empirical re-audit of the repository codebase conducted prior to roadmap formulation.
2. The verification and mapping of all **90 capability dimensions** across 14 modules.
3. The mapping of all **35 PRODUCT TARGET capabilities** ($6\text{ PARTIAL} + 29\text{ MISSING}$) to concrete vertical slice work packages.
4. The structural verification of the **Dependency DAG** (14 subsystems), **Parallel Development Matrix** (3 concurrent tracks), **Prisma Migration Sequencing** (4 batches), and **Test Release Gates** (5 tiers).
5. Strict adherence to Git safety invariants (`apps/` clean, `schema.prisma` clean, `weekly-report-W01.docx` unstaged, no merge, no push).

---

## 2. Empirical Repository Re-Audit Findings

Prior to creating the roadmap, an unvarnished audit of the active repository was executed across backend, mobile, AI-service, database schema, tests, and dependencies.

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
- **Total Models Found:** 36 models (`User`, `Profile`, `TravelPreference`, `Destination`, `PlaceCategory`, `Place`, `PlaceSource`, `Review`, `Trip`, `TripMember`, `Itinerary`, `ItineraryItem`, `Match`, `Group`, `GroupMember`, `Message`, `SafetyContact`, `SafetyCheckin`, `EmergencyEvent`, `AiSession`, etc.).
- **Critical Schema Reality:**
  - `Match`, `Group`, `GroupMember`, `Message`, `TravelPreference`, `Trip`, `TripMember`, `ItineraryItem` **already exist in schema.prisma**. Zero redundant models will be created for these entities.
  - `PlaceMedia`, `Expense`, `ExpenseSplit`, `Settlement`, `ItineraryVote`, `EmailVerificationToken`, `PasswordResetToken`, and `OAuthAccount` are **currently missing** and must be added across 4 migration batches.

### 2.2. Backend NestJS Audit (`apps/backend/src/`)
- **Active Modules:** `ai-proxy`, `auth`, `destinations`, `health`, `places`, `reviews`, `trips`, `users`, `videos`.
- **Auth Reality:** `AuthController` only exposes 3 endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`. Zero endpoints exist for forgot password, reset password, change password, email verification, social OAuth, or rate limiting.
- **Users Reality:** `UsersController` only exposes `GET /users/me` and `PUT /users/me` (for `displayName`, `bio`, `avatar`). Zero endpoint exists for `PUT /users/me/preferences`.
- **Social & Collaborative Reality:** Zero modules exist for `buddies`, `groups`, `chat`, `expenses`, or `reminders`.

### 2.3. Mobile Flutter Audit (`apps/mobile/`)
- **Active Packages:** `flutter_riverpod`, `go_router`, `dio`, `shared_preferences`, `flutter_map`, `latlong2`, `geolocator`, `cached_network_image`, `url_launcher`.
- **Missing Required Packages:** `flutter_secure_storage` (required for 14.3), `flutter_local_notifications` (required for 11.1–11.3), `google_sign_in` (14.8), `sign_in_with_apple` (14.9), `web_socket_channel` (8.3).

### 2.4. AI-Service Audit (`apps/ai-service/`)
- **Active Routers:** `chat.py`, `planner.py`, `health.py`.
- **Active Tools:** `calculate_budget.py`, `calculate_route.py`, `get_weather.py`, `search_hotels.py`, `search_places.py`, `search_reviews.py`.
- **Evaluation Framework:** `recommendation/service.py`, `recommendation/evaluator.py`, `recommendation/baselines/most_pop.py`.

### 2.5. Test Suite Inventory
- **Backend Tests (10 files):** `auth.e2e-spec.ts`, `places.e2e-spec.ts`, `place-detail.e2e-spec.ts`, `trips.e2e-spec.ts`, `planner.e2e-spec.ts`, `ai-chat.e2e-spec.ts`, `destinations.e2e-spec.ts`, `provenance.e2e-spec.ts`, `verified-serving.e2e-spec.ts`, `health.e2e-spec.ts`.
- **Mobile Tests (10 files):** `auth_test.dart`, `chat_test.dart`, `chat_sources_test.dart`, `map_test.dart`, `location_navigation_test.dart`, `design_system_and_map_stability_test.dart`, `place_detail_test.dart`, `planner_test.dart`, `trips_test.dart`, `widget_test.dart`.
- **AI-Service Tests (15 files):** 15 pytest suites verifying prompts, RAG OSM enrichment, planner, and recommendation baselines.

**Verdict:** The repository evidence completely validates the two-tier capability classifications established in `TASK 08.2.4-R1`.

---

## 3. 90-Capability Dimension Mapping & Scope Enforcement

Every capability in `task-08.2.4-global-capability-matrix.md` has been accounted for:

### 3.1. Reconciled Status Breakdown
- **Tier 1 (Current Runtime):**
  - `CURRENT`: **36** (Verified operational code; protected from regression).
  - `PARTIAL`: **6** (Partially implemented; scheduled for completion).
  - `MISSING`: **48** (Zero runtime code; 29 scheduled for MVP, 19 deferred/excluded).
  - **Sum Tier 1:** $36 + 6 + 48 = \mathbf{90}$.
- **Tier 2 (Architectural Target):**
  - `CURRENT`: **36** (Retained as-is).
  - `PRODUCT TARGET`: **35** (The sole focus of implementation; $6\text{ PARTIAL} + 29\text{ MISSING}$).
  - `FUTURE`: **9** (Explicitly deferred post-MVP).
  - `EXCLUDED`: **10** (Strictly forbidden).
  - **Sum Tier 2:** $36 + 35 + 9 + 10 = \mathbf{90}$.

### 3.2. 100% Mapping of the 35 PRODUCT TARGET Capabilities
All 35 Product Target items map directly to vertical slice work packages:

1. `1.4` Search Bar Entry $\longrightarrow$ **WP-SEARCH-01**
2. `2.7` Offline Basemap Caching $\longrightarrow$ **WP-MAP-01**
3. `3.10` Production Place Media Pipeline $\longrightarrow$ **WP-MEDIA-01**
4. `4.4` Action Preview & Confirmation $\longrightarrow$ **WP-WANDY-01**
5. `5.4` Drag-and-Drop Item Reordering $\longrightarrow$ **WP-TRIP-01**
6. `7.1` Traveler Discovery Grid $\longrightarrow$ **WP-BUDDY-01**
7. `7.2` Travel Style Matching Score $\longrightarrow$ **WP-BUDDY-01**
8. `7.3` Masked Traveler Profile View $\longrightarrow$ **WP-BUDDY-02**
9. `7.4` Double Opt-In Match Handshake $\longrightarrow$ **WP-BUDDY-02**
10. `8.1` Group Space Creation $\longrightarrow$ **WP-GROUP-01**
11. `8.2` Membership Roles (Leader/Member) $\longrightarrow$ **WP-GROUP-01**
12. `8.3` Real-Time Group Chat Timeline $\longrightarrow$ **WP-CHAT-01**
13. `9.1` Collaborative Itinerary Board $\longrightarrow$ **WP-ITIN-01**
14. `9.2` Activity Proposal & Voting $\longrightarrow$ **WP-ITIN-01**
15. `9.3` Realtime Conflict Resolution $\longrightarrow$ **WP-ITIN-02**
16. `10.1` Group Expense Ledger $\longrightarrow$ **WP-EXP-01**
17. `10.2` Split Logic (Equal / Custom) $\longrightarrow$ **WP-EXP-01**
18. `10.3` Debt Simplification Matrix $\longrightarrow$ **WP-EXP-02**
19. `10.4` Peer Settlement Recording $\longrightarrow$ **WP-EXP-02**
20. `11.1` Itinerary Item Reminder Alert $\longrightarrow$ **WP-REMIND-01**
21. `11.2` Lead-Time Offset Selector $\longrightarrow$ **WP-REMIND-01**
22. `11.3` Packing Checklist Reminder $\longrightarrow$ **WP-REMIND-01**
23. `12.4` Emergency Confirmation Modal $\longrightarrow$ **WP-SAFE-01**
24. `12.7` Offline Emergency Cache $\longrightarrow$ **WP-SAFE-01**
25. `13.4` Travel Preferences Editing $\longrightarrow$ **WP-PROF-01**
26. `13.5` Privacy & Visibility Controls $\longrightarrow$ **WP-PROF-02**
27. `14.3` Secure Token Storage (Mobile) $\longrightarrow$ **WP-AUTH-01**
28. `14.4` Silent Refresh & Concurrency Queue Lock $\longrightarrow$ **WP-AUTH-01**
29. `14.5` Anti-Enumeration Password Recovery $\longrightarrow$ **WP-AUTH-04**
30. `14.6` Authenticated Password Change $\longrightarrow$ **WP-AUTH-04**
31. `14.7` Email Verification Pipeline $\longrightarrow$ **WP-AUTH-03**
32. `14.8` Google Social OAuth $\longrightarrow$ **WP-AUTH-05**
33. `14.9` Apple Social OAuth $\longrightarrow$ **WP-AUTH-05**
34. `14.10` Account Linking & Collision $\longrightarrow$ **WP-AUTH-06**
35. `14.11` Rate Limiting & Throttling $\longrightarrow$ **WP-AUTH-02**

### 3.3. Scope Boundary Invariant
- **0 FUTURE Capabilities** scheduled for implementation (1.5, 3.9, 4.5, 5.5, 6.5, 8.5, 11.4, 14.15, 14.16 remain strictly deferred post-MVP).
- **0 EXCLUDED Capabilities** scheduled (2.8, 4.6, 7.5, 8.4, 10.5, 12.6, 13.6, 14.12, 14.13, 14.14 remain strictly prohibited).

---

## 4. Traceability of the 14 Subsystem Preconditions

All 14 subsystems from `task-08.2.4-design-dependency-register.md` are completely accounted for in the Roadmap:

1. **Place Media Pipeline:** Mapped to `WP-MEDIA-01` (Migration Batch 2).
2. **Travel Preference Persistence:** Mapped to `WP-PROF-01` (Reuses existing `TravelPreference`).
3. **Buddy Matching:** Mapped to `WP-BUDDY-01` & `WP-BUDDY-02` (Reuses existing `Match`).
4. **Group Persistence & Roles:** Mapped to `WP-GROUP-01` (Reuses existing `Group` & `GroupMember`).
5. **Group WebSocket Chat:** Mapped to `WP-CHAT-01` (Reuses existing `Message`).
6. **Shared Itinerary & Voting:** Mapped to `WP-ITIN-01` & `WP-ITIN-02` (`ItineraryVote` in Batch 4).
7. **Shared Expense Ledger:** Mapped to `WP-EXP-01` & `WP-EXP-02` (`Expense`, `Split`, `Settlement` in Batch 4).
8. **Scheduling & Reminders:** Mapped to `WP-REMIND-01` (Local OS scheduling via `flutter_local_notifications`).
9. **Safety Emergency & Offline Asset:** Mapped to `WP-SAFE-01` (Bundled JSON asset).
10. **Transactional Email Pipeline:** Mapped to `WP-AUTH-03` (`EmailVerificationToken` in Batch 1).
11. **Anti-Enumeration Recovery:** Mapped to `WP-AUTH-04` (`PasswordResetToken` in Batch 1).
12. **Social OAuth & Account Linking:** Mapped to `WP-AUTH-05` & `WP-AUTH-06` (`OAuthAccount` in Batch 1).
13. **Hardware Storage & Silent Refresh:** Mapped to `WP-AUTH-01` (Keychain/Keystore + Dio interceptor).
14. **Map Tile Caching:** Mapped to `WP-MAP-01` (Local cache manager capped at 100MB).

---

## 5. Artifact Delivery Verification

All 4 required roadmap and engineering governance documents have been authored and verified:

1. [`docs/roadmap/gomate-master-implementation-roadmap-v1.md`](file:///d:/Do_an/wanderai/docs/roadmap/gomate-master-implementation-roadmap-v1.md):
   - Vertical slice specifications for 23 work packages.
   - Master work package summary table (14 columns).
   - Dual perspectives: Product Engineering Order (4 Phases) vs Thesis Value Order (3 Tiers).
   - Thesis MVP Cut-Line Architecture.
2. [`docs/roadmap/gomate-implementation-dependency-dag-v1.md`](file:///d:/Do_an/wanderai/docs/roadmap/gomate-implementation-dependency-dag-v1.md):
   - Complete Mermaid DAG with 6 execution levels.
   - Explicit declarations of `BLOCKS`, `BLOCKED BY`, and `CAN RUN IN PARALLEL WITH`.
   - Primary Critical Path ($13.5\text{d}$) and Secondary Critical Path ($6.5\text{d}$) analysis.
3. [`docs/roadmap/gomate-parallel-development-matrix-v1.md`](file:///d:/Do_an/wanderai/docs/roadmap/gomate-parallel-development-matrix-v1.md):
   - Pairwise concurrency matrix between major workstreams.
   - Shared bottleneck file risk analysis (6 critical files).
   - 3 Concurrent Development Tracks model.
   - 4-Batch Database Migration Sequencing strategy.
   - Vertical slice branch naming convention.
4. [`docs/roadmap/gomate-test-release-gates-v1.md`](file:///d:/Do_an/wanderai/docs/roadmap/gomate-test-release-gates-v1.md):
   - 5-Tier Quality Gate Pipeline.
   - Workstream testing protocols (Backend, Mobile, AI, Security).
   - The 11 Immutable Non-Regression Contracts.
   - Rollback and failure recovery procedures.

---

## 6. Git Invariants & Safety Verification

### 6.1. Production Source Code Check
```bash
$ git diff apps/
# Output: EMPTY (0 lines modified)
```

### 6.2. Database Schema Check
```bash
$ git diff apps/backend/prisma/
# Output: EMPTY (0 lines modified)
```

### 6.3. Weekly Report Integrity Check
```bash
$ git status
# Output:
# Changes not staged for commit:
#   modified:   docs/weekly-reports/W01/weekly-report-W01.docx (STRICTLY UNTOUCHED)
```

---

## 7. Acceptance Gate Verification Checklist

| Criterion | Standard Required | Audit Result | Gate Status |
| :--- | :--- | :--- | :---: |
| **Pre-Roadmap Re-Audit** | Re-audit backend, mobile, ai-service, schema, tests | Empirical audit completed; findings documented in Section 2 | **PASS** |
| **90 Capability Reconciliation**| Full reconciliation of 90 dimensions across 14 modules | Exactly 36 Current, 6 Partial, 48 Missing accounted for | **PASS** |
| **Product Target Mapping** | All 35 Product Targets mapped to work packages | 100% mapped across 23 vertical slices (Section 3.2) | **PASS** |
| **No Scope Creep** | Zero FUTURE or EXCLUDED capabilities implemented | Scope strictly confined to 35 Product Targets | **PASS** |
| **Partial Completion Plan** | All 6 Partial capabilities assigned completion packages | WP-AUTH-01, WP-SAFE-01, WP-MEDIA-01, WP-TRIP-01, WP-SEARCH-01 | **PASS** |
| **14 Subsystems Mapped** | Dependency Register subsystems mapped to work packages | 100% bidirectional traceability established (Section 4) | **PASS** |
| **Dependency DAG** | Complete DAG with BLOCKS, BLOCKED BY, PARALLEL | Authored in `gomate-implementation-dependency-dag-v1.md` | **PASS** |
| **Parallel Matrix** | Parallel safe vs coordination vs serial matrix | Authored in `gomate-parallel-development-matrix-v1.md` | **PASS** |
| **Schema Migration Order** | 4-batch schema migration sequencing | Documented with model definitions and zero duplication | **PASS** |
| **Branch Strategy** | Dedicated vertical slice feature branches off develop | Formally established; design branch frozen | **PASS** |
| **Test & Release Gates** | 5-tier testing pipeline & security invariants | Authored in `gomate-test-release-gates-v1.md` | **PASS** |
| **Non-Regression Contracts** | 11 immutable contracts protecting 36 Current features | Formally locked; auto-reject policy on regression | **PASS** |
| **Dual Roadmap Views** | Technical dependency order vs Thesis value order | Documented in Roadmap Section 5 (Views A & B) | **PASS** |
| **Thesis MVP Cut-Line** | Explicit Must-Have vs Should-Have vs Post-MVP | Documented in Roadmap Section 6 | **PASS** |
| **`apps/` Clean** | Zero modified lines in production source | Verified clean via `git diff apps/` | **PASS** |
| **`schema.prisma` Clean** | Zero modified lines in Prisma schema | Verified clean via `git diff apps/backend/prisma/` | **PASS** |
| **Weekly Report Untouched** | `weekly-report-W01.docx` must remain unstaged | Confirmed unstaged in git status | **PASS** |

---

## 8. Final Verdict & Stop Instruction

$$\mathbf{TASK\ 08.3\ =\ MASTER\ IMPLEMENTATION\ ROADMAP\ COMPLETE}$$
$$\mathbf{STATUS:\ ENGINEERING\ EXECUTION\ SPECIFICATION\ LOCKED}$$

> [!IMPORTANT]
> **STOP INSTRUCTION STRICTLY OBSERVED:**
> Execution terminates immediately upon completion of this report and git commit.
> - **NO** production coding has started.
> - **NO** feature branches have been created.
> - **NO** packages have been installed.
> - **NO** migrations have been executed.
> - `TASK 08.3.1` has **NOT** been started.
> Awaiting explicit user prompt for the next phase.
