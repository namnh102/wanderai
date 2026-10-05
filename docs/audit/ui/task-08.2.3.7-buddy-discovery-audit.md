# GoMate Buddy Discovery — Capability Audit & Architecture Report (TASK 08.2.3.7 / R1)

**Status:** APPROVED ARCHITECTURAL AUDIT & UX FOUNDATION (R1 REFINED)  
**Task:** TASK 08.2.3.7 / TASK 08.2.3.7-R1 — GOMATE BUDDY DISCOVERY PRIVACY, DATA HONESTY & IA CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Audit Overview

TASK 08.2.3.7 and its refinement R1 establish the architectural baseline, data honesty contracts, and foundational UX specifications for **Buddy Discovery** (`Tìm bạn đồng hành`) in GoMate. 

Before generating visual mockups or designing user flows, an exhaustive audit was performed across:
1. **Prisma Database Schema (`apps/backend/prisma/schema.prisma`)**
2. **Backend Controllers & Services (`apps/backend/src/modules/`)**
3. **AI Recommendation & Matching Services (`apps/ai-service/`)**
4. **Mobile Client Router & Feature Modules (`apps/mobile/lib/`)**

### Key Audit Findings & R1 Refinements:
* **Database Reality:** Models exist for `Profile`, `TravelPreference`, and `Match` (status `PENDING`, `ACCEPTED`, `REJECTED`, with `score` and `explanation`). Models also exist for `TripMember`, `Group`, `GroupMember`, and `Message`.
* **API Reality:** **Zero Buddy Discovery endpoints currently exist.** There is no `GET /buddy`, `POST /buddy/match-request`, or candidate query in NestJS.
* **Algorithm Reality:** The `recommendation/` package in `apps/ai-service` is strictly an offline matrix/popularity recommender for **hotels** based on the ViHoRec dataset. There is currently **zero travel-buddy matching algorithm code** in the repository.
* **Verified Badge Semantics (R1 Audit):** `User.isVerified` represents basic account/email authentication upon registration. It has zero relationship to legal KYC, Citizen ID (CCCD), or passport verification. Therefore, it is strictly labeled `"Tài khoản đã xác minh"`, and never `"Đã xác minh danh tính"`.
* **Hometown / Residence Reality (R1 Audit):** `Profile` schema contains `nationality` and `languages`, but **no city, hometown, or residence field**. Displaying specific cities like "TP. Hồ Chí Minh" or "Hà Nội" on candidate cards is fraudulent against current schema and has been eliminated.
* **Age Privacy Reality (R1 Audit):** `Profile.dateOfBirth` is private personal data. Exposing exact age ("26 tuổi", "24 tuổi") violates privacy principles; Discovery strictly enforces standardized 5-year **Age Bands** (`25–29 tuổi`, `20–24 tuổi`).
* **Navigation IA Parity (R1 Audit):** GoMate maintains 5 canonical root tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn`). Desktop V1's independent 6th root tab was eliminated in R1, anchoring Buddy Discovery as a contextual submodule within Trip context.
* **Safety & Privacy Gaps:** The database currently **lacks** a `Block` table, a `Report` table, and an `isDiscoverable` (privacy toggle) field on `User` or `Profile`.

---

## 2. Code, API & Database Inspection Details

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
* **User & Profile Tables (Nhóm 1):**
  * `User`: `id`, `email`, `role`, `isVerified`, `createdAt`, `updatedAt`, `deletedAt`. *(Semantics: `isVerified` = email/account verified; Missing: `isDiscoverable`, `isBlocked`)*.
  * `Profile`: `userId`, `displayName`, `avatar`, `bio`, `phone`, `dateOfBirth`, `nationality`, `languages`. *(Missing: `city`, `province`, `hometown`)*.
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
IDENTIFIED SYSTEM GAPS & ARCHITECTURAL REQUIREMENTS (R1)
============================================================

1. GAP: DISCOVERABILITY TOGGLE (PRIVACY)
   - Issue: Prisma schema has no `isDiscoverable` boolean on User or Profile.
   - Impact: Without this, every registered user is either permanently public
     or permanently private.
   - Status: DESIGN TARGET — BLOCKED BY DATA MODEL.
   - Requirement: Add `isDiscoverable Boolean @default(false)` to `Profile`.

2. GAP: USER BLOCKING (SAFETY)
   - Issue: No `Block` model exists to record bidirectional blocking.
   - Impact: A user cannot protect themselves from harassment or unwanted requests.
   - Status: UNSAFE / BLOCKED DEPENDENCY.
   - Requirement: Add `UserBlock` model (`blockerId`, `blockedId`, `reason`).

3. GAP: USER REPORTING (SAFETY)
   - Issue: No `Report` model exists to flag malicious or fake accounts.
   - Status: UNSAFE / BLOCKED DEPENDENCY.
   - Requirement: Add `UserReport` model (`reporterId`, `reportedUserId`,
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
| **Discovery Feed** | Missing | Missing | Missing Query | `buddy-mobile-discovery-r1.png` | **DESIGN TARGET** | Audited `apps/backend/src/modules/` — 0 endpoints. |
| **Profile Storage**| `GET/PUT /users/me` | Basic profile | `Profile` & `TravelPreference` | `gomate-design-system-ux-spec-v1.md` | **PARTIAL** | DB models exist, public read API missing. |
| **Matching Engine**| Missing | Missing | `Match.score` (Float) | Explainable criteria | **FUTURE** | AI service only has hotel ViHoRec recommender. |
| **Explainable Reasons**| Missing | Missing | `Match.explanation` | Checkmarked reasons box | **DESIGN TARGET** | Visualized in `buddy-mobile-discovery-r1.png`. |
| **Candidate Card** | Missing | Missing | Schema fields | `candidate-card` component | **DESIGN TARGET** | Built with avatar, age band, verified badge, tags. |
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

## 5. Master Mockup Verification (R1 Refined Artifacts)

Exactly **two** master discovery mockups were produced and verified at `docs/audit/evidence/ui-08.2.3.7/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :---: | :--- | :---: |
| [`buddy-mobile-discovery-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.7/buddy-mobile-discovery-r1.png) | Mobile | $390 \times 844$ | 1. GoMate 5-tab root navigation (Tab 5 `Chuyến đi` active).<br>2. App Bar with "Bạn đồng hành" + "Quyền riêng tư" badge button.<br>3. Context selector pill: "Đà Nẵng · 15/10 – 18/10/2026".<br>4. Filter chips row ("Tất cả", "Trùng lịch trình", "Thoải mái", "Ẩm thực").<br>5. Candidate Card 1 (Lê Hoàng Nam): verified badge ("Tài khoản đã xác minh"), age band (`25–29 tuổi`), nationality (`Việt Nam`), overlap pill, tags, compat box with 3 checkmarked reasons, [Bỏ qua] [Xem hồ sơ] buttons.<br>6. Candidate Card 2 (Trần Mai Linh): verified badge ("Tài khoản đã xác minh"), age band (`20–24 tuổi`), nationality (`Việt Nam`), tags, compat box with 2 reasons, [Bỏ qua] [Xem hồ sơ] buttons.<br>7. Privacy footer: "Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối."<br>8. Zero browser scrollbars.<br>9. Evidence watermark outside production UI. | **PASS** |
| [`buddy-desktop-discovery-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.7/buddy-desktop-discovery-r1.png) | Desktop | $1440 \times 900$ | 1. Full-width top header with canonical 5-tab GoMate navigation (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` active, `An toàn`).<br>2. Breadcrumb context: `Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành`.<br>3. 2-Column layout: Left sidebar ($330\text{px}$) with Active Trip Context, Filters (time, style, age), and Privacy Status Toggle labeled `Mục tiêu thiết kế — Cần bổ sung isDiscoverable trong DB`.<br>4. Right canvas: Page title, Sort dropdown ("Mức độ phù hợp nhất ▼"), 2-column candidate cards grid with age bands, "Tài khoản đã xác minh", and clean date overlap wording.<br>5. Evidence watermark at bottom right. | **PASS** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.7-R1)

- [x] **No identity-verification overclaim:** Verified badge strictly labeled "Tài khoản đã xác minh", never "Đã xác minh danh tính".
- [x] **Unsupported hometown data removed:** Removed "TP. Hồ Chí Minh" and "Hà Nội" from candidates; backed by Profile.nationality ("Việt Nam").
- [x] **Age uses age band:** Converted exact ages ("26 tuổi", "24 tuổi") to standard 5-year age bands ("25–29 tuổi", "20–24 tuổi").
- [x] **Public profile vs private info wording corrected:** Updated footer notice to "Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối.".
- [x] **No fake compatibility %:** Banned percentage metrics; explainable bullet reasons locked.
- [x] **Date overlap wording is clear:** Replaced "Trùng 100% thời gian..." with "Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10).".
- [x] **Desktop/mobile IA reconciled:** Desktop top nav restored to 5 canonical root tabs with `Chuyến đi` active; Buddy framed as contextual submodule.
- [x] **isDiscoverable clearly DESIGN TARGET:** Privacy toggle explicitly marked `Mục tiêu thiết kế — Cần bổ sung isDiscoverable trong DB`.
- [x] **Block clearly BLOCKED:** Retained as `UNSAFE / BLOCKED DEPENDENCY`.
- [x] **Report clearly BLOCKED:** Retained as `UNSAFE / BLOCKED DEPENDENCY`.
- [x] **Eligibility labeled TARGET where unsupported:** Section 5 separated into Currently Enforceable vs Requires Implementation.
- [x] **Mobile R1 created:** `buddy-mobile-discovery-r1.png` rendered and verified ($390 \times 844$).
- [x] **Desktop R1 created:** `buddy-desktop-discovery-r1.png` rendered and verified ($1440 \times 900$).
- [x] **No source changes:** 0 lines modified in `apps/`.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** Contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
