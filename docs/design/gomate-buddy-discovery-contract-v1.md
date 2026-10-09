# GoMate Buddy Discovery — UX & Business Contract Specification V1 (R1 Locked)

**Status:** DESIGN LOCKED — PRIVACY, DATA HONESTY & IA AUDIT (R1)  
**Task:** TASK 08.2.3.7-R1 — GOMATE BUDDY DISCOVERY PRIVACY, DATA HONESTY & IA CORRECTION  
**Module:** Travel Buddy Matching & Discovery (`/buddy`)  
**Target Viewports:** Mobile ($390 \times 844$), Tablet ($768 \times 1024$), Desktop ($1440 \times 900$)  
**Source of Truth:** 
- Database Schema: `apps/backend/prisma/schema.prisma` (`User`, `Profile`, `TravelPreference`, `Match`, `TripMember`, `Group`, `Message`)
- Backend Users Module: `apps/backend/src/modules/users/`
- Mobile Router & Features: `apps/mobile/lib/core/router/`, `apps/mobile/lib/features/`
- Design Specifications: `docs/design/gomate-design-system-ux-spec-v1.md` (Sections 6.21–6.24), `docs/design/gomate-master-ux-plan-v2.md`
- Master Visual Artifacts:
  - Mobile R1: `docs/audit/evidence/ui-08.2.3.7/buddy-mobile-discovery-r1.png` ($390 \times 844$)
  - Desktop R1: `docs/audit/evidence/ui-08.2.3.7/buddy-desktop-discovery-r1.png` ($1440 \times 900$)

---

## 1. Product Role & Architectural Vision

The **Buddy Discovery** module (`Tìm bạn đồng hành`) is a core feature of **GoMate**, addressing the thesis objective: *"Xây dựng nền tảng du lịch thông minh dựa trên AI Agent, hệ thống gợi ý và kết nối bạn đồng hành."*

Its purpose is to connect independent travelers with compatible companions based on **overlapping destinations, shared travel windows, complementary budgets, and aligned travel styles**.

### 1.1. Core Non-Negotiable Invariants
1. **Travel-First, Not a Dating App:** Visual presentation, information hierarchy, and interaction design prioritize travel compatibility (destination, dates, itinerary preferences, budget pace) over superficial metrics. Swipe-based matching, "hot profiles", and dating-app mechanics are strictly excluded.
2. **Consent Invariant (Non-Negotiable):**
   $$\text{Discovery} \neq \text{Match}$$
   $$\text{Viewing Profile} \neq \text{Connected}$$
   $$\text{Sending Request} \neq \text{Matched}$$
   $$\textbf{MATCHED} \iff \text{User A sends request} + \text{User B explicitly accepts}$$
   A mutual match connection is established **only** after two-way explicit consent.
3. **Score Honesty Invariant (No Fake Percentages):** Pseudo-precision match percentages (e.g., "98% match", "92% phù hợp") are **strictly prohibited** until an empirically trained, deterministic matching engine is implemented and verified. GoMate enforces **Explainable Compatibility Reasons (Lý do phù hợp)** with clear, evidence-backed criteria.
4. **Verified Badge Semantics (Account Verification Only):** The badge represents `User.isVerified` (email/account authentication). It does **NOT** represent Citizen ID (CCCD), passport, KYC, or legal identity verification. It is strictly labeled:
   $$\textbf{Tài khoản đã xác minh}$$
   Never use *"Đã xác minh danh tính"*.
5. **Age Privacy Invariant (Age Bands):**
   Exact `dateOfBirth` is private. Discovery cards must **never** expose exact age or birth date. Candidates are presented within standardized 5-year age bands:
   - `20–24 tuổi`
   - `25–29 tuổi`
   - `30–34 tuổi`
   - `35–39 tuổi`
6. **Location & Itinerary Privacy Invariant:**
   - **Never expose exact real-time GPS coordinates** or live hotel pins on discovery cards. Location is strictly shared at the broad destination level (e.g., "Đà Nẵng").
   - **Never expose unshared minute-by-minute itineraries** prior to a mutual match. Only broad travel date overlaps (e.g., "15–18/10/2026") are exposed during discovery.
7. **Global IA Invariant (Canonical 5-Tab Root):**
   The application preserves exactly 5 root navigation tabs across mobile and desktop:
   - `Khám phá` (`/`)
   - `Bản đồ` (`/map`)
   - `Wandy AI` (`/ai`)
   - `Chuyến đi` (`/trips`)
   - `An toàn` (`/safety`)
   Buddy Discovery is a contextual submodule accessed from travel context (Trip Detail / Home), **not** an independent 6th root tab.

---

## 2. Current vs Target Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Capability Status | Implementation Reality |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Buddy Discovery Feed** | Missing | Missing | Missing query | `buddy-mobile-discovery-r1.png` | **DESIGN TARGET** | Zero discovery API code exists currently. |
| **Profile Storage** | `GET/PUT /users/me` | Basic profile | `Profile` & `TravelPreference` | `gomate-design-system-ux-spec-v1.md` | **PARTIAL** | DB models exist; public read API and Buddy UI missing. |
| **Matching Algorithm** | Missing | Missing | `Match.score` (Float) | Explainable reasons | **FUTURE** | Hotel recommendation exists (ViHoRec); Buddy matching does not. |
| **Explainable Reasons** | Missing | Missing | `Match.explanation` | Checkmarked reasons box | **DESIGN TARGET** | Structured compatibility explanation locked in UI. |
| **Candidate Card** | Missing | Missing | Schema fields | `buddy-mobile-discovery-r1.png` | **DESIGN TARGET** | Card designed with strict privacy boundaries (age band, account verified). |
| **Filter Controls** | Missing | Missing | Schema enums | Destination, dates, style | **DESIGN TARGET** | Destination, dates, style, age filters specified. |
| **Match Request** | Missing | Missing | `Match` (status `PENDING`) | Handled in Task 08.2.3.9 | **PARTIAL (DB Only)** | Model exists; API and controller missing. |
| **Accept / Reject** | Missing | Missing | `ACCEPTED` / `REJECTED` | Handled in Task 08.2.3.9 | **PARTIAL (DB Only)** | Model exists; API missing. |
| **Block / Report** | Missing | Missing | **MISSING FROM DB** | Handled in Safety | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock` & `UserReport`. |
| **Privacy Toggle (ON/OFF)**| Missing | Missing | **MISSING FROM DB** | Top App Bar "Quyền riêng tư" | **UNSAFE / BLOCKED** | Requires `isDiscoverable` in User/Profile schema. |
| **Direct Chat** | Missing | Missing | `Group` & `Message` | Phase UI-3 | **PARTIAL (DB Only)** | Group/Message tables exist; chat socket missing. |
| **Trip Sharing** | `POST :id/members`| Missing | `TripMember` | Trip Detail invite | **CURRENT (API) / PARTIAL (UI)**| API exists for invite by email; UI pending. |

---

## 3. Data Model & Field Mapping Matrix

| Field Name | Source Model | Persisted? | Public on Discovery? | Match-Context Only? | Private by Default? | Sensitive / Never Disclosed? | Used for Matching? | Notes / R1 Lock |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `id` | `User` / `Profile` | YES | NO (Anonymized) | NO | YES | NO | Primary Key | Anonymized internal UUID |
| `displayName` | `Profile` | YES | **YES** | NO | NO | NO | Display only | User-chosen screen name |
| `avatar` | `Profile` | YES | **YES** | NO | NO | NO | Display only | Profile photo or initials |
| `isVerified` | `User` | YES | **YES** | NO | NO | NO | Trust filter | **Account/email verification only**, NOT identity/CCCD |
| `bio` | `Profile` | YES | **YES** (Snippet) | NO | NO | NO | Semantic NLP | Brief intro text |
| `nationality` | `Profile` | YES | **YES** | NO | NO | NO | Language filter | Country of origin (e.g. "Việt Nam") |
| `city` / `hometown` | — | **NO** | NO | NO | NO | NO | NO | **FUTURE PROFILE FIELD — NOT CURRENT DATA CONTRACT** |
| `languages` | `Profile` | YES | **YES** | NO | NO | NO | Comm filter | e.g. `["Tiếng Việt", "English"]` |
| `dateOfBirth` | `Profile` | YES | NO | **YES (Age band)** | YES (Exact DOB) | NO | Age range | **Masked to age band (e.g. "25–29 tuổi")** |
| `phone` | `Profile` | YES | NO | NO | **YES** | NO | Post-match | Locked until mutual connection |
| `email` | `User` | YES | NO | NO | NO | **YES** | Auth only | Never exposed in UI |
| `passwordHash` | `User` | YES | NO | NO | NO | **YES** | Auth only | Never exposed in UI |
| `travelStyle` | `TravelPreference` | YES | **YES** | NO | NO | NO | **Primary Input** | `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY` |
| `budgetMin` / `Max` | `TravelPreference` | YES | NO | **YES (Tier)** | NO | NO | **Primary Input** | Tier description (e.g. "~2.0M/ngày") |
| `preferredGroup` | `TravelPreference` | YES | **YES** | NO | NO | NO | Group filter | `SOLO`, `COUPLE`, `SMALL_GROUP`, etc. |
| `interests` | `TravelPreference` | YES | **YES** | NO | NO | NO | **Primary Input** | Array of travel interest tags |
| `avoidances` | `TravelPreference` | YES | NO | **YES (Negative)** | NO | NO | Conflict filter | Dietary or activity avoidances |
| `dietaryNeeds` | `TravelPreference` | YES | NO | **YES** | NO | NO | Dining overlap | Vegetarian, Halal, etc. |
| `destinationId` | `Trip` | YES | NO | **YES (City only)** | NO | NO | **Primary Input** | Broad destination overlap (e.g. "Đà Nẵng") |
| `startDate` / `endDate`| `Trip` | YES | NO | **YES (Window)** | NO | NO | **Primary Input** | Overlap duration (e.g. "Trùng 4 ngày (15–18/10)") |
| `itineraries` | `Itinerary` | YES | NO | NO | **YES** | NO | Post-match | Minute-by-minute timeline locked |
| `liveLocation` (GPS) | Runtime | NO | NO | NO | NO | **YES** | Prohibited | Real-time coordinates strictly banned |
| `safetyContacts` | `SafetyContact` | YES | NO | NO | NO | **YES** | Safety only | Emergency contacts private |
| `isDiscoverable` | *Needs Migration* | **NO** | NO | NO | **YES** | NO | Eligibility | **DESIGN TARGET — BLOCKED BY DATA MODEL** |

---

## 4. Privacy Classification

```
============================================================
GOMATE PRIVACY TIERS FOR BUDDY DISCOVERY (R1 LOCKED)
============================================================

TIER 1: PUBLIC / DISCOVERY (Visible on candidate card)
- Display Name & Avatar
- Verified Badge: "Tài khoản đã xác minh" (Account verification only)
- Age Band (e.g., "25–29 tuổi", "20–24 tuổi", NEVER exact DOB)
- Nationality (e.g., "Việt Nam", persisted in Profile.nationality)
- Languages Spoken (e.g., "Tiếng Việt, English")
- Travel Style Badge (e.g., "Thoải mái (Comfort)")
- Broad Interests (e.g., "Ẩm thực", "Bãi biển", "Nhiếp ảnh")
- Brief Bio Snippet

TIER 2: MATCH-CONTEXT ONLY (Visible only when matching against active trip)
- Overlapping Destination (e.g., "Đà Nẵng")
- Overlapping Travel Window (e.g., "Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10)")
- Budget Compatibility Tier (e.g., "~2.0M/ngày", never raw financial data)
- Explanatory Compatibility Bullet Points

TIER 3: PRIVATE BY DEFAULT (Locked until mutual Match Consent)
- Full Biography & Social Links
- Personal Phone Number (`Profile.phone`)
- Detailed Itinerary & Activity Timeline (requires explicit trip invite)
- Discovery Footer Copy: "Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối."

TIER 4: SENSITIVE / NEVER DISCOVERABLE (Zero discovery exposure)
- Email Address (`User.email`) & Password Hash
- Exact Real-Time GPS Coordinates / Live Map Pin
- Emergency Contacts (`SafetyContact`) & SOS Alert Logs
============================================================
```

---

## 5. Target Discovery Eligibility Contract

The rules governing candidate eligibility for the Buddy Discovery feed are structured into two categories to distinguish currently enforceable database constraints from target rules requiring schema additions:

### 5.1. Currently Enforceable (Current DB & Logic Reality)
1. **Account Verification:** `User.isVerified === true` (account/email authentication complete).
2. **Active Account:** `User.deletedAt === null`.
3. **Not Self:** `Candidate.id !== CurrentUser.id`.
4. **No Existing Match:** There is no existing `Match` record with `status === 'ACCEPTED'` between `CurrentUser` and `Candidate`.
5. **Context Destination Overlap:** Both users have trips associated with the same destination (`Trip.destinationId`).
6. **Date Window Overlap:** $\text{Trip}_A.\text{startDate} \le \text{Trip}_B.\text{endDate} \land \text{Trip}_A.\text{endDate} \ge \text{Trip}_B.\text{startDate}$.

### 5.2. Requires Implementation (Target Rules Blocked by Schema / Engine)
1. **Discoverability Flag:** `Profile.isDiscoverable === true` — **BLOCKED**: Requires database migration adding `isDiscoverable Boolean @default(false)` to `Profile`.
2. **Bidirectional Block Check:** Neither user has blocked the other — **BLOCKED**: Requires database migration adding `UserBlock` model.
3. **Report Status Filter:** Candidate is not under active abuse review — **BLOCKED**: Requires database migration adding `UserReport` model.
4. **Rejection Cooldown:** 30-day cooldown after `status === 'REJECTED'` — **REQUIRES IMPLEMENTATION**: Requires backend matching query filter checking `Match.updatedAt` timestamp.

---

## 6. Matching Inputs & Explainability Standard

### 6.1. Multi-Dimensional Matching Inputs
When the matching service evaluates two travelers, it operates across 4 core dimensions:
1. **Spatio-Temporal Overlap (Weight: Critical):** Destination match + overlapping calendar days.
2. **Travel Style Harmony (Weight: High):** Compatibility between `BACKPACKER`, `BUDGET`, `COMFORT`, and `LUXURY`.
3. **Interest Intersection (Weight: High):** Jaccard similarity across selected `interests` (e.g., Food, Culture, Nature, Photography).
4. **Budget Alignment (Weight: Medium):** Overlap between `budgetMin` and `budgetMax` per day.

### 6.2. Explainability Callout Box (Lý do phù hợp)
Instead of arbitrary match percentages, every Candidate Card must render a dedicated, structured **Compatibility Explanation Box** (`compat-box`):
- Header: `✦ Lý do phù hợp với chuyến đi của bạn:`
- Criterion 1 (Date/Time Overlap): `"✓ Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10)."`
- Criterion 2 (Interests): `"✓ Cùng thích ẩm thực hải sản và chụp ảnh hoàng hôn."`
- Criterion 3 (Style/Budget): `"✓ Phong cách du lịch tương đồng: Thoải mái (~2.0M/ngày)."`

**Strict Rule:** No pseudo-precision percentage metrics (e.g., "98% match", "92% phù hợp") until a tested and verified matching engine exists.

---

## 7. Candidate Card Contract

- **Component:** Candidate Card (`candidate-card`).
- **Visual Reference:** `buddy-mobile-discovery-r1.png`, `buddy-desktop-discovery-r1.png`.
- **Anatomy:**
  1. **User Header Row:**
     - Left: 44dp Avatar with initials or profile picture.
     - Center: Display Name + Verified Badge (`#0F766E`) labeled `"Tài khoản đã xác minh"`.
     - Metadata: Standardized Age Band (`25–29 tuổi` / `20–24 tuổi`), Nationality (`Việt Nam`), and Languages (`Tiếng Việt, English`).
     - Overlap Badge: Calendar icon + `"Đà Nẵng · Trùng N ngày (dd/mm – dd/mm)"` (Soft mint `#F0FDFA`, border `#CCFBF1`).
  2. **Tags Row:**
     - Travel style pill (Amber `#FEF3C7`, text `#92400E`).
     - Up to 4 interest pills (Slate `#F1F5F9`, text `#334155`).
  3. **Compatibility Box (`compat-box`):**
     - Explanatory bullet points with emerald checkmarks (`✓`).
  4. **Action Buttons Hierarchy:**
     - **Secondary Action (Left, Flex 1):** `"Bỏ qua"` (Slate `#F1F5F9`). Dismisses candidate from immediate feed without permanent block.
     - **Primary Action (Right, Flex 2):** `"Xem hồ sơ"` (Pine Teal `#0F766E`). Navigates to full public Buddy Profile (Task 08.2.3.8) to inspect bio, mutual interests, and travel style before sending any connection request.
     - **Negative Invariant:** **NO direct 1-tap "Gửi lời mời" button on discovery cards.** This prevents spamming and enforces deliberate, informed connection requests.
  5. **Footer Notice:**
     - Banner text: `"Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối."` (Resolves semantic conflict with "Xem hồ sơ").

---

## 8. Filter Specifications

The discovery interface provides two tiers of contextual filtering:

1. **Context Selector (Primary):**
   - Dropdown pill anchored at top: `"Tìm bạn cho chuyến đi: Đà Nẵng (15/10 – 18/10/2026) ▼"`.
   - Allows switching between the user's active planned trips or searching globally by destination.
2. **Filter Chips (Secondary Horizontal Scroll):**
   - `Tất cả (N)`: Active default.
   - `Trùng lịch trình (N)`: Filters only candidates with $\ge 2$ overlapping days.
   - `Thoải mái (Comfort)`: Filter by travel style enum.
   - `Ẩm thực & Biển`: Filter by combined high-affinity interests.
   - `Bộ lọc khác ⚙`: Opens modal/sheet for age band, group size, and language filters.

---

## 9. Screen States & Recovery Actions

| State Name | Visual Characteristics | User Feedback Message | Primary Recovery Action |
| :--- | :--- | :--- | :--- |
| **LOADING** | Shimmer skeleton cards (avatar, lines, boxes). | None (Indeterminate shimmer). | None. |
| **DISCOVERY RESULTS**| Populated candidate cards (2 on mobile, grid on desktop). | `"Gợi ý du khách phù hợp · Lý do minh bạch"`. | Tap `"Xem hồ sơ"` or `"Bỏ qua"`. |
| **NO MATCHES (EMPTY)**| Friendly luggage icon (`#94A3B8`). | `"Chưa tìm thấy bạn đồng hành phù hợp cho chuyến đi này."` | `"Mở rộng thời gian & sở thích"`. |
| **FILTERED EMPTY** | Search illustration with filter icon. | `"Không có du khách nào phù hợp với bộ lọc hiện tại."` | `"Đặt lại bộ lọc"` (Teal `#0F766E`). |
| **ERROR** | Neutral alert circle (`#EF4444`). | `"Không thể tải danh sách gợi ý bạn đồng hành. Vui lòng kiểm tra kết nối mạng."` | `"Thử lại lần nữa"`. |
| **PRIVACY DISABLED**| Shield lock icon (`#64748B`). | `"Bạn đang ẩn khỏi tính năng tìm bạn đồng hành."` | `"Bật tìm bạn đồng hành"` (Navigates to Privacy Settings). |

---

## 10. Multi-Platform & Responsive Rules

### 10.1. Mobile ($390 \times 844$) — `buddy-mobile-discovery-r1.png`
- Single-column vertical card stack.
- Docked GoMate 5-tab root navigation at bottom (Tab 5 `Chuyến đi` active).
- Sticky Top App Bar with back navigation and direct `"Quyền riêng tư"` badge button.
- Horizontal scrollable filter chip carousel.
- Candidate cards featuring "Tài khoản đã xác minh", age bands (`25–29 tuổi`), and clear overlap explanations.

### 10.2. Tablet ($768 \times 1024$)
- Split view: Left pane ($320\text{px}$) sticky context & filter sidebar; Right pane ($448\text{px}$) vertical card feed.

### 10.3. Desktop ($1440 \times 900$) — `buddy-desktop-discovery-r1.png`
- Full-width desktop header ($64\text{px}$) with canonical 5-tab root navigation: `Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` (active), `An toàn`.
- Contextual breadcrumbs in content header: `Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành`.
- 2-Column responsive workstation:
  - **Left Sidebar ($330\text{px}$):**
    - Active Trip Context Card.
    - Checkbox & Range Filter Criteria Card.
    - Privacy & Discoverability Toggle Status Card, explicitly marked: `Mục tiêu thiết kế — Cần bổ sung isDiscoverable trong DB`.
  - **Right Main Canvas:**
    - Results header with count, breadcrumb, and Sort Dropdown (`"Mức độ phù hợp nhất ▼"`).
    - 2-Column Responsive Candidates Grid displaying rich cards with bios, overlap badges, tags, and compatibility callouts.

---

## 11. Accessibility Contract

- **Touch Target Dimensions:** All interactive controls (`Xem hồ sơ`, `Bỏ qua`, filter chips, dropdowns) have touch targets $\ge 44 \times 44\text{ dp}$.
- **Screen Reader Announcements:** Candidate cards are wrapped in semantic labels:
  *"Lê Hoàng Nam, tài khoản đã xác minh, độ tuổi 25 đến 29, quốc tịch Việt Nam. Điểm đến Đà Nẵng, trùng toàn bộ 4 ngày từ 15 đến 18 tháng 10. Phong cách Thoải mái. Sở thích: Ẩm thực, Bãi biển, Nhiếp ảnh. Phù hợp vì trùng toàn bộ thời gian chuyến đi và chung sở thích ẩm thực."*
- **Color Independence:** Compatibility indicators use explicit text and checkmark icons (`✓`), never color-only cues.
- **Contrast Ratios:** All body text meets WCAG AA ($> 4.5:1$ against `#FFFFFF` / `#F8FAFC`).
