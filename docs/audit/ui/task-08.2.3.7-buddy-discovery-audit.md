# GoMate Buddy Discovery — Capability Audit & Architecture Report (TASK 08.2.3.7)

**Status:** APPROVED ARCHITECTURAL AUDIT & UX FOUNDATION  
**Task:** TASK 08.2.3.7 — GOMATE BUDDY DISCOVERY CAPABILITY AUDIT + UX FOUNDATION V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Audit Overview

TASK 08.2.3.7 establishes the architectural baseline, data honesty contracts, and foundational UX specifications for **Buddy Discovery** (`Tìm bạn đồng hành`) in GoMate. 

Before generating visual mockups or designing user flows, an exhaustive audit was performed across:
1. **Prisma Database Schema (`apps/backend/prisma/schema.prisma`)**
2. **Backend Controllers & Services (`apps/backend/src/modules/`)**
3. **AI Recommendation & Matching Services (`apps/ai-service/`)**
4. **Mobile Client Router & Feature Modules (`apps/mobile/lib/`)**

### Key Audit Findings:
* **Database Reality:** Models exist for `Profile`, `TravelPreference`, and `Match` (status `PENDING`, `ACCEPTED`, `REJECTED`, with `score` and `explanation`). Models also exist for `TripMember`, `Group`, `GroupMember`, and `Message`.
* **API Reality:** **Zero Buddy Discovery endpoints currently exist.** There is no `GET /buddy`, `POST /buddy/match-request`, or candidate query in NestJS.
* **Algorithm Reality:** The `recommendation/` package in `apps/ai-service` is strictly an offline matrix/popularity recommender for **hotels** based on the ViHoRec dataset. There is currently **zero travel-buddy matching algorithm code** in the repository.
* **Safety & Privacy Gaps:** The database currently **lacks** a `Block` table, a `Report` table, and an `isDiscoverable` (privacy toggle) field on `User` or `Profile`.

---

## 2. Code, API & Database Inspection Details

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
* **User & Profile Tables (Nhóm 1):**
  * `User`: `id`, `email`, `role`, `isVerified`, `createdAt`, `updatedAt`, `deletedAt`. *(Missing: `isDiscoverable`, `isBlocked`)*.
  * `Profile`: `userId`, `displayName`, `avatar`, `bio`, `phone`, `dateOfBirth`, `nationality`, `languages`.
  * `TravelPreference`: `userId`, `travelStyle` (enum `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`), `budgetMin`, `budgetMax`, `preferredGroup` (enum `SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY`), `interests` (String[]), `avoidances` (String[]), `dietaryNeeds` (String[]).
* **Social & Matching Tables (Nhóm 6):**
  * `Match`: `id`, `senderId`, `receiverId`, `status` (enum `PENDING`, `ACCEPTED`, `REJECTED`), `score` (Float?), `explanation` (String?), `createdAt`. *(Unique constraint on `[senderId, receiverId]`)*.
  * `Group`: `id`, `name`, `description`, `tripId`.
  * `GroupMember`: `id`, `groupId`, `userId`, `role` ("admin", "member").
  * `Message`: `id`, `groupId`, `userId`, `content`, `createdAt`.
* **Missing Models (Safety Gaps):**
  * `Block` / `UserBlock`: Not found in schema.
  * `Report` / `UserReport`: Not found in schema.

### 2.2. Backend API Inspection (`apps/backend/src/modules/`)
* Scanned modules: `ai-proxy`, `auth`, `destinations`, `health`, `places`, `reviews`, `trips`, `users`, `videos`.
* `users.controller.ts`: Only exposes `GET /users/me` and `PUT /users/me`.
* `trips.controller.ts`: Exposes `POST /trips/:id/members` for adding members by email.
* **Verdict:** No endpoints exist for listing potential travel buddies, querying compatibility, or creating match requests.

### 2.3. AI Service Inspection (`apps/ai-service/`)
* `recommendation/service.py`: Contains `HotelRecommendationService` backed by `MostPopularRecommender` (ViHoRec dataset).
* `routers/planner.py`: Generates itineraries from trip context.
* `routers/chat.py`: Handles Wandy chat with RAG.
* **Verdict:** Travel-buddy matching algorithm does not exist in code; any match percentage displayed in UI would be fraudulent.

---

## 3. Privacy & Safety Gap Analysis

```
============================================================
IDENTIFIED SYSTEM GAPS & ARCHITECTURAL REQUIREMENTS
============================================================

1. GAP: DISCOVERABILITY TOGGLE (PRIVACY)
   - Issue: Prisma schema has no `isDiscoverable` boolean on User or Profile.
   - Impact: Without this, every registered user is either permanently public
     or permanently private.
   - Design Decision: Design specifies a dedicated "Quyền riêng tư" modal with
     an explicit `Hiển thị tìm bạn` toggle (default OFF until enabled).
   - Technical Requirement: Add `isDiscoverable Boolean @default(false)` to
     `Profile` in next schema migration.

2. GAP: USER BLOCKING (SAFETY)
   - Issue: No `Block` model exists to record bidirectional blocking.
   - Impact: A user cannot protect themselves from harassment or unwanted requests.
   - Technical Requirement: Add `UserBlock` model (`blockerId`, `blockedId`, `reason`).

3. GAP: USER REPORTING (SAFETY)
   - Issue: No `Report` model exists to flag malicious or fake accounts.
   - Technical Requirement: Add `UserReport` model (`reporterId`, `reportedUserId`,
     `category`, `details`, `status`).

4. GAP: MATCH SCORE PRECISION (DATA HONESTY)
   - Issue: No backend matching algorithm exists to compute a real 0-100 float.
   - Design Decision: STRICTLY BAN pseudo percentages ("98% match"). Enforce
     Explainable Compatibility Reasons ("Lý do phù hợp") based on visible overlap.
============================================================
```

---

## 4. Comprehensive Capability Matrix

| Capability | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Discovery Feed** | Missing | Missing | Missing Query | `buddy-mobile-discovery-v1.png` | **DESIGN TARGET** | Audited `apps/backend/src/modules/` — 0 endpoints. |
| **Profile Storage**| `GET/PUT /users/me` | Basic profile | `Profile` & `TravelPreference` | `gomate-design-system-ux-spec-v1.md` | **PARTIAL** | DB models exist, public read API missing. |
| **Matching Engine**| Missing | Missing | `Match.score` (Float) | Explainable criteria | **FUTURE** | AI service only has hotel ViHoRec recommender. |
| **Explainable Reasons**| Missing | Missing | `Match.explanation` | Checkmarked reasons box | **DESIGN TARGET** | Visualized in `buddy-mobile-discovery-v1.png`. |
| **Candidate Card** | Missing | Missing | Schema fields | `candidate-card` component | **DESIGN TARGET** | Built with avatar, overlap pill, tags, compat box. |
| **Filters** | Missing | Missing | Schema enums | Context selector + chips | **DESIGN TARGET** | Specified in contract V1. |
| **Match Request** | Missing | Missing | `Match` (status `PENDING`) | Handled in Task 08.2.3.9 | **PARTIAL (DB Only)** | `Match` model exists in schema. |
| **Accept / Reject** | Missing | Missing | `ACCEPTED` / `REJECTED` | Handled in Task 08.2.3.9 | **PARTIAL (DB Only)** | `MatchStatus` enum exists. |
| **Block User** | Missing | Missing | **MISSING FROM DB** | Handled in Safety | **UNSAFE / BLOCKED** | Requires new migration for `UserBlock`. |
| **Report User** | Missing | Missing | **MISSING FROM DB** | Handled in Safety | **UNSAFE / BLOCKED** | Requires new migration for `UserReport`. |
| **Privacy Toggle** | Missing | Missing | **MISSING FROM DB** | Top Bar "Quyền riêng tư" | **UNSAFE / BLOCKED** | Requires `isDiscoverable` migration. |
| **Direct Chat** | Missing | Missing | `Group` & `Message` | Phase UI-3 | **PARTIAL (DB Only)** | Group/Message tables exist; chat socket missing. |
| **Trip Sharing** | `POST :id/members`| Missing | `TripMember` | Trip Detail invite | **CURRENT (API) / PARTIAL (UI)**| API exists for invite by email; UI pending. |
| **Group Formation**| Missing | Missing | `Group` & `GroupMember` | Post-match journey | **PARTIAL (DB Only)** | Group models exist in schema. |

---

## 5. Master Mockup Verification (2 Artifacts)

Per Section 32 of instructions, exactly **two** master discovery mockups were produced and verified at `docs/audit/evidence/ui-08.2.3.7/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`buddy-mobile-discovery-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.7/buddy-mobile-discovery-v1.png) | Mobile | $390 \times 844$ | 1. GoMate 5-tab root navigation (Tab 5 `Chuyến đi` active).<br>2. App Bar with "Bạn đồng hành" + "Quyền riêng tư" badge button.<br>3. Context selector pill: "Đà Nẵng · 15/10 – 18/10/2026".<br>4. Filter chips row ("Tất cả", "Trùng lịch trình", "Thoải mái", "Ẩm thực").<br>5. Candidate Card 1 (Lê Hoàng Nam): verified badge, overlap pill, tags, compat box with 3 checkmarked reasons, [Bỏ qua] [Xem hồ sơ] buttons.<br>6. Candidate Card 2 (Trần Mai Linh): verified badge, tags, compat box with 2 reasons, [Bỏ qua] [Xem hồ sơ] buttons.<br>7. Privacy footer: "Hồ sơ chi tiết chỉ mở khi kết nối".<br>8. Zero browser scrollbars.<br>9. Evidence watermark outside production UI. | **PASS** |
| [`buddy-desktop-discovery-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.7/buddy-desktop-discovery-v1.png) | Desktop | $1440 \times 900$ | 1. Full-width top header with GoMate navigation + Privacy badge + user avatar.<br>2. 2-Column layout: Left sidebar ($330\text{px}$) with Active Trip Context, Filters (time, style, age), and Privacy Status Toggle ("Đang Bật").<br>3. Right canvas: Page title, Sort dropdown ("Mức độ phù hợp nhất ▼"), 2-column candidate cards grid.<br>4. Explanatory compatibility callout boxes with checkmarks.<br>5. Identical business rules and tokens as mobile.<br>6. Evidence watermark at bottom right. | **PASS** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.7)

- [x] **Buddy code/API audited:** All backend modules, mobile features, and AI services inspected.
- [x] **DB schema audited:** Exact field-by-field matrix constructed for `User`, `Profile`, `TravelPreference`, and `Match`.
- [x] **Current/Future separated:** Strict distinction between current DB models, missing APIs, and future algorithms.
- [x] **No fake match percentage:** Banned "98% match"; replaced with explainable reasons.
- [x] **Eligibility documented:** 7 explicit criteria for discovery eligibility defined.
- [x] **Privacy fields classified:** 4-tier classification (Public, Match-Context, Private by Default, Sensitive).
- [x] **Exact location hidden:** Only broad city name ("Đà Nẵng") exposed; real-time GPS coordinates strictly prohibited.
- [x] **Full itinerary hidden:** Minute-by-minute timeline hidden; only calendar overlap dates exposed.
- [x] **Consent invariant documented:** Discovery $\neq$ Match; two-way explicit consent required.
- [x] **Block/report dependencies documented:** Identified as critical DB migration requirements.
- [x] **Matching reasons explainable:** Compatibility box with checkmarked reasons specified.
- [x] **Empty/loading/error/privacy-off states defined:** 6 comprehensive states with recovery actions documented.
- [x] **Mobile master created:** `buddy-mobile-discovery-v1.png` rendered and verified ($390 \times 844$).
- [x] **Desktop master created:** `buddy-desktop-discovery-v1.png` rendered and verified ($1440 \times 900$).
- [x] **Vietnamese-first:** Canonical Vietnamese copy used across all components.
- [x] **Accessibility defined:** $\ge 44\text{dp}$ touch targets, semantic screen reader labels, color independence.
- [x] **Responsive defined:** Mobile ($390\text{px}$), Tablet ($768\text{px}$), Desktop ($1440\text{px}$) patterns detailed.
- [x] **No source changes:** 0 lines modified in `apps/`.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** Contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
