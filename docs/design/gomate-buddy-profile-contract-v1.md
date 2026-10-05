# GoMate Buddy Profile — UX, Privacy & Connection Entry Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION  
**Task:** TASK 08.2.3.8 — GOMATE BUDDY PROFILE UX, PRIVACY & CONNECTION ENTRY CONTRACT V1  
**Module:** Travel Buddy Public Profile & Connection Entry (`/buddy/profile/:userId`)  
**Target Viewports:** Mobile ($390 \times 844$), Tablet ($768 \times 1024$), Desktop ($1440 \times 900$)  
**Source of Truth:** 
- Database Schema: `apps/backend/prisma/schema.prisma` (`User`, `Profile`, `TravelPreference`, `Match`, `TripMember`)
- Discovery Contract: `docs/design/gomate-buddy-discovery-contract-v1.md`
- Discovery Audits: `docs/audit/ui/task-08.2.3.7-buddy-discovery-audit.md`, `docs/audit/ui/task-08.2.3.7-r1-buddy-discovery-correction.md`
- Master Visual Artifacts:
  - Mobile Profile V1: `docs/audit/evidence/ui-08.2.3.8/buddy-mobile-profile-v1.png` ($390 \times 844$)
  - Desktop Profile V1: `docs/audit/evidence/ui-08.2.3.8/buddy-desktop-profile-v1.png` ($1440 \times 900$)

---

## 1. Product Role & Architectural Vision

The **Buddy Profile** screen (`Hồ sơ bạn đồng hành`) represents the **Public Profile View** in GoMate. It is opened when a user taps `"Xem hồ sơ"` on any candidate card in Buddy Discovery **prior to establishing a mutual connection**.

### 1.1. Core Non-Negotiable Invariants
1. **Travel-First Philosophy (Not a Dating Profile):**
   The screen structure, visual hierarchy, and interaction design prioritize **travel compatibility, shared trip windows, travel pace/budget harmony, and destination interests**. Superficial rating stars, followers, like counters, or dating-app "swiping" cards are strictly banned.
2. **Consent & Mutual Match Boundary:**
   $$\text{Discovery View} \neq \text{Profile View} \neq \text{Send Request} \neq \text{Connected}$$
   $$\textbf{CONNECTED / MATCHED} \iff \text{User A sends request} + \text{User B explicitly accepts}$$
   Viewing a public profile or sending a connection request grants **zero** access to private contact channels or minute-by-minute itineraries.
3. **Data Honesty & Anti-Fabrication:**
   - **No fake compatibility percentages** (e.g., "98% match"). Only factual, explainable bullet points backed by overlapping trip/preference fields are displayed.
   - **No fabricated hometown or city**: `Profile` schema lacks a city/residence field; candidate origin is strictly reflected via `nationality` (`"Việt Nam"`).
   - **No fake KYC / Identity claims**: `User.isVerified` reflects email/account verification during authentication. It is strictly labeled `"Tài khoản đã xác minh"`, never `"Đã xác minh danh tính"`.
4. **Age Privacy via Age Bands:**
   Exact `dateOfBirth` is sensitive personal data. Discovery and pre-match profiles strictly expose standardized 5-year **Age Bands** (`20–24 tuổi`, `25–29 tuổi`, `30–34 tuổi`, `35–39 tuổi`).
5. **Location & Itinerary Privacy:**
   - **Never expose exact real-time GPS coordinates** or live hotel addresses. Only broad destination overlaps (e.g., `"Đà Nẵng"`) are public.
   - **Never expose detailed minute-by-minute timelines** (e.g. "08:00 ăn sáng, 10:00 tắm biển"). Broad trip dates (e.g. `"15/10 – 18/10/2026"`) are the sole temporal overlap exposed.
6. **Information Architecture Parity (Canonical 5-Tab Root):**
   Buddy Profile is a contextual submodule accessed from travel context (`Trip Detail > Buddy Discovery > Buddy Profile`). Desktop top navigation preserves the canonical 5 root tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [active], `An toàn`) and uses breadcrumb navigation.

---

## 2. Current vs Target Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Capability Status | Implementation Reality |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Public Buddy Profile** | Missing | Missing | `Profile` & `TravelPreference` | `buddy-mobile-profile-v1.png` | **DESIGN TARGET** | DB models exist; public read API and UI missing. |
| **Profile Bio** | `GET/PUT /users/me` | Basic profile | `Profile.bio` (String?) | Bio snippet or fallback | **CURRENT (DB) / PARTIAL (API)**| Persisted in DB; public endpoint missing. |
| **Age Band Privacy** | Missing | Missing | `Profile.dateOfBirth` | 5-year age bands | **DESIGN TARGET** | Computed server-side; exact DOB masked. |
| **Travel Preferences**| Missing | Missing | `TravelPreference` | Style, group, budget tier | **PARTIAL (DB Only)** | Enums in DB; public read API missing. |
| **Compatibility Reasons**| Missing | Missing | `Match.explanation` | Checkmarked factual list | **DESIGN TARGET** | Explainable overlap criteria locked in UI. |
| **Private Contact Unlock**| Missing | Missing | `Profile.phone` | Locked section pre-match | **PARTIAL (DB Only)** | Model has phone; unlock logic requires match state. |
| **Trip Detail Sharing**| `POST :id/members`| Missing | `TripMember` | Post-match sharing | **CURRENT (API) / PARTIAL (UI)**| API exists for invite by email; UI pending. |
| **Connection Request** | Missing | Missing | `Match` (status `PENDING`) | Primary CTA button | **PARTIAL (DB Only)** | DB model exists; request API controller missing. |
| **Block User** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **Report User** | Missing | Missing | **MISSING FROM DB** | Safety action | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 3. Data Model & Field Mapping Matrix

| Field Name | Source Model | Persisted? | Public Pre-Match? | Private (Post-Match)? | Never Expose? | Current vs Target | Notes / Business Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `id` | `User` / `Profile` | YES | NO | NO | **YES** | Current | Anonymized internal UUID; never exposed in UI |
| `displayName` | `Profile` | YES | **YES** | NO | NO | Current | User screen name |
| `avatar` | `Profile` | YES | **YES** | NO | NO | Current | Profile image URL or initials fallback (e.g. "HN") |
| `isVerified` | `User` | YES | **YES** | NO | NO | Current | Strictly labeled `"Tài khoản đã xác minh"` |
| `bio` | `Profile` | YES | **YES** | NO | NO | Current | Short bio; fallback if null: `"Người dùng chưa thêm phần giới thiệu."` |
| `dateOfBirth` | `Profile` | YES | NO | NO | **YES** | Current | Masked to 5-year Age Band (e.g. `25–29 tuổi`) |
| `nationality` | `Profile` | YES | **YES** | NO | NO | Current | Country of origin (e.g. `"Việt Nam"`) |
| `city` / `hometown` | — | **NO** | NO | NO | NO | **Target** | **FUTURE PROFILE FIELD — NOT CURRENT DATA CONTRACT** |
| `languages` | `Profile` | YES | **YES** | NO | NO | Current | Array of languages spoken (e.g. `["Tiếng Việt", "English"]`) |
| `phone` | `Profile` | YES | NO | **YES** | NO | Current | **LOCKED PRE-MATCH**. Revealed only after mutual match consent |
| `email` | `User` | YES | NO | NO | **YES** | Current | Auth credential; strictly hidden from Buddy UI |
| `passwordHash` | `User` | YES | NO | NO | **YES** | Current | Sensitive hash; never exposed |
| `travelStyle` | `TravelPreference`| YES | **YES** | NO | NO | Current | Enum: `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY` |
| `budgetMin` / `Max` | `TravelPreference`| YES | NO | **YES (Tier)** | NO | Current | Masked to broad tier (e.g. `~2.0M/ngày`); no bank balance |
| `preferredGroup` | `TravelPreference`| YES | **YES** | NO | NO | Current | Enum: `SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP` |
| `interests` | `TravelPreference`| YES | **YES** | NO | NO | Current | Array of travel interest chips (up to 5 displayed) |
| `avoidances` | `TravelPreference`| YES | NO | **YES** | NO | Current | Negative preferences (used in matching algorithm) |
| `dietaryNeeds` | `TravelPreference`| YES | NO | **YES** | NO | Current | Dietary requirements (Vegetarian, Halal, etc.) |
| `destinationId` | `Trip` | YES | **YES (City)**| NO | NO | Current | Broad city overlap (e.g. `"Đà Nẵng"`) |
| `startDate` / `endDate`| `Trip` | YES | **YES (Window)**| NO | NO | Current | Calendar overlap window (e.g. `"15–18/10/2026"`) |
| `itineraries` (Detail) | `Itinerary` | YES | NO | **YES** | NO | Current | **LOCKED PRE-MATCH**. Detailed timeline shared post-match |
| `liveLocation` (GPS) | Runtime | NO | NO | NO | **YES** | Target | Real-time GPS coordinates strictly prohibited |
| `safetyContacts` | `SafetyContact` | YES | NO | NO | **YES** | Current | Emergency SOS contacts strictly private |

---

## 4. Public Profile Contract

Before a mutual match connection is established, the candidate profile renders strictly filtered, privacy-safe information:

### 4.1. Allowed Public Data
1. **Avatar:** User profile image, or fallback circular avatar with initials (e.g. `HN`).
2. **Display Name:** Full display name (e.g. `"Lê Hoàng Nam"`).
3. **Verification Badge:** Green shield icon with explicit label:
   $$\textbf{Tài khoản đã xác minh}$$
4. **Age Band:** Standardized 5-year bracket (e.g. `25–29 tuổi`).
5. **Nationality & Languages:** Persisted fields (e.g. `Việt Nam · Ngôn ngữ: Tiếng Việt, English`).
6. **About (Bio):** Raw text from `Profile.bio`. If null or empty string, fallback gracefully to:
   $$\textit{"Người dùng chưa thêm phần giới thiệu."}$$
7. **Travel Style:** Enum badge (e.g. `Thoải mái (Comfort)`, `Tiết kiệm (Budget)`).
8. **Preferred Group Style:** Enum badge (e.g. `Nhóm nhỏ (2–4 người)`).
9. **Budget Compatibility Tier:** Qualitative daily tier (e.g. `~2.0M / ngày`), never raw account balances.
10. **Interests:** Up to 5 selected tags from `TravelPreference.interests` (e.g. `Ẩm thực hải sản`, `Bãi biển Mỹ Khê`, `Nhiếp ảnh film`, `Văn hóa địa phương`).
11. **Context Compatibility Box:** Factual explanation of alignment with current active trip.

### 4.2. Strictly Forbidden Public Data
- **NO exact birth date or exact age** (`dateOfBirth` masked).
- **NO unpersisted hometown/residence** (no fabricated city names).
- **NO phone number or social links** (locked until mutual match).
- **NO minute-by-minute itinerary items** (locked until mutual match).
- **NO email address, password hash, or internal UUID**.
- **NO pseudo-scientific match percentages** (`98% match` is banned).

---

## 5. Privacy Tiers & Classification

```
============================================================
GOMATE PRIVACY TIERS FOR BUDDY PROFILE
============================================================

TIER 1: PUBLIC PRE-MATCH (Unconditionally visible on Profile)
- Display Name & Initials / Avatar
- Verified Badge: "Tài khoản đã xác minh"
- Standardized Age Band (e.g. "25–29 tuổi")
- Nationality ("Việt Nam") & Languages Spoken
- Short Bio ("Giới thiệu bản thân")
- Travel Style & Preferred Group Style
- Public Interest Chips (e.g. "Ẩm thực", "Nhiếp ảnh")

TIER 2: MATCH-CONTEXT COMPATIBILITY (Factual overlap with active trip)
- Destination overlap ("Đà Nẵng")
- Date overlap window ("Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10)")
- Budget alignment tier ("Thoải mái (~2.0M/ngày)")
- Explainable compatibility bullet points with checkmarks (✓)

TIER 3: LOCKED PRE-MATCH (Revealed only after mutual connection acceptance)
- Personal Phone Number (`Profile.phone`)
- Detailed Minute-by-Minute Itinerary & Hotel Names
- Direct In-App Chat Channel (`Group` / `Message`)

TIER 4: SENSITIVE / NEVER EXPOSED (Never rendered in UI)
- Account Email Address (`User.email`) & Password Hash
- Exact Date of Birth (`Profile.dateOfBirth`)
- Real-Time Live GPS Coordinates
- Emergency Contacts (`SafetyContact`) & SOS Alert Logs
- Internal Database UUIDs
============================================================
```

---

## 6. Compatibility Section & Explainability Standard

The profile must render a dedicated, prominent **Compatibility Callout Box** highlighting alignment against the user's active planned trip:

### 6.1. Visual Specification
- Background: Soft Mint `#F0FDFA`
- Border: `#CCFBF1` (1px solid)
- Header: `✦ Phù hợp với chuyến đi Đà Nẵng (15–18/10)`
- Items: Formatted as clean factual statements with emerald checkmarks (`✓` `#10B981`):
  1. **Temporal Criterion:** `"✓ Trùng toàn bộ 4 ngày tại Đà Nẵng (15/10 – 18/10)."`
  2. **Interests Criterion:** `"✓ Cùng thích ẩm thực hải sản và chụp ảnh hoàng hôn."`
  3. **Style & Budget Criterion:** `"✓ Phong cách du lịch tương đồng: Thoải mái (~2.0M/ngày)."`

### 6.2. Non-Negotiable Ban on Score Percentages
- **Strictly Banned:** "98% phù hợp", "92% match", compatibility gauges, or progress bar scores.
- **Rationale:** No verified deterministic matching algorithm currently exists in the codebase. Displaying arbitrary numbers constitutes algorithmic fraud.

---

## 7. Private Information Locked Section

To set transparent expectations and build user trust, the profile renders an explicit **Locked Privacy Section** directly above the primary CTA:

### 7.1. Visual Anatomy
- Container: Border dashed (`#CBD5E1`), background neutral slate (`#F8FAFC`), radius 10px.
- Header: `{ICONS['lock_closed']} Thông tin riêng tư (Khóa trước khi kết nối)`.
- Explanatory Subtitle: `"Các thông tin sau chỉ được chia sẻ sau khi hai bên đồng ý kết nối:"`.
- Rows:
  - Row 1: `Số điện thoại cá nhân` $\longrightarrow$ `Chỉ hiển thị sau khi kết nối`
  - Row 2: `Lịch trình chi tiết theo giờ` $\longrightarrow$ `Chỉ chia sẻ khi là bạn đồng hành`
  - Desktop Row 3: `Vị trí thời gian thực (GPS)` $\longrightarrow$ `Tuyệt đối không chia sẻ`

### 7.2. Anti-Masking Invariant
- **Rule:** Never render fake masked phone numbers (e.g. `09xx xxx xxx` or `0912***789`). The UI displays an honest placeholder state explaining the unlock condition.

---

## 8. Connection CTA & Request Boundary

### 8.1. Primary Action Button
- Label: `"Gửi lời mời kết nối"`
- Visuals: Full-width button, Pine Teal `#0F766E`, radius 10px, height 44px, white bold text with send paper-plane icon.
- Architectural Status: **DESIGN TARGET**.
  - While the Prisma schema defines the `Match` model (`senderId`, `receiverId`, status `PENDING`), the NestJS backend **currently lacks** a match request controller and route (`POST /buddy/matches`).

### 8.2. Request Safety Helper Copy
Directly beneath the CTA button, a permanent helper note reinforces the consent invariant:
$$\textbf{"Người này chỉ được kết nối với bạn sau khi họ chấp nhận lời mời."}$$
This guarantees the user understands:
$$\text{Gửi lời mời} \neq \text{Kết nối ngay lập tức}$$

### 8.3. Request Lifecycle Scope Boundary
- This task (08.2.3.8) **locks the entry point and UI presentation** of the profile and CTA button.
- The interactive request lifecycle (Request Dialog, Confirmation, Toast, Pending state, Receiver's Inbox, Accept/Reject actions) is explicitly deferred to:
  $$\textbf{TASK 08.2.3.9 — GOMATE BUDDY MATCH REQUEST & CONSENT LIFECYCLE}$$

---

## 9. Screen States & Fallback Handling

| State Name | Visual Presentation | Fallback Copy / Behavior | Primary User Action |
| :--- | :--- | :--- | :--- |
| **PROFILE LOADING** | Shimmer skeleton cards for avatar, title, compat box, bio, and locked section. | Indeterminate animation ($<1.5\text{s}$). | None (Wait). |
| **PROFILE READY** | Full populated profile with verified badge, age band, bio, style tags, and compat box. | Standard presentation. | Tap `"Gửi lời mời kết nối"`. |
| **PARTIAL: MISSING BIO** | Identity card and preferences render normally; About box shows placeholder. | `"Người dùng chưa thêm phần giới thiệu."` (No fake generated text). | Tap `"Gửi lời mời kết nối"`. |
| **PARTIAL: NO AVATAR** | Circular avatar renders user's initials (e.g. `HN`) on teal background. | Initials fallback (No random stock photos). | Tap `"Gửi lời mời kết nối"`. |
| **PARTIAL: NO PREFERENCES**| Travel style section displays neutral empty state. | `"Chưa có thông tin về sở thích du lịch."` | Tap `"Gửi lời mời kết nối"`. |
| **PROFILE ERROR** | Red alert circle icon with error card. | `"Không thể tải thông tin hồ sơ du khách. Vui lòng kiểm tra kết nối mạng."` | `"Thử lại"`. |
| **PROFILE NOT AVAILABLE** | Luggage icon with neutral text (User deleted or blocked). | `"Hồ sơ này hiện không còn khả dụng."` | `"Quay lại danh sách"`. |

---

## 10. Multi-Platform & Responsive Rules

### 10.1. Mobile ($390 \times 844$) — `buddy-mobile-profile-v1.png`
- Single-column vertical scroll flow.
- Top App Bar with back navigation arrow, title `"Hồ sơ bạn đồng hành"`, and right action `"Báo cáo"` (flag icon).
- Fixed bottom action bar anchoring `"Gửi lời mời kết nối"` with safety helper text.
- Clean layout without browser scrollbars.

### 10.2. Tablet ($768 \times 1024$)
- Centered 2-column layout: Left column ($320\text{px}$) sticky identity and locked data; Right column ($400\text{px}$) compatibility, about, preferences, and action button.

### 10.3. Desktop ($1440 \times 900$) — `buddy-desktop-profile-v1.png`
- Full-width top header ($64\text{px}$) preserving canonical 5-tab root navigation: `Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` (active teal underline), `An toàn`.
- Contextual breadcrumb trail: `Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành > Hồ sơ Lê Hoàng Nam`.
- 2-Column Workstation Layout:
  - **Left Column ($440\text{px}$):**
    - Identity Card (80dp avatar, name, verified badge, age band, nationality, languages, full bio box).
    - Locked Privacy Card with status indicators for phone, itinerary, and live GPS.
    - Safety Notice Box: `"Báo cáo vi phạm hoặc chặn người dùng (Mục tiêu thiết kế)"`.
  - **Right Column ($900\text{px}$):**
    - Compatibility Hero Card with 3 checked factual criteria.
    - Preferences & Interests Card (3-column grid for style, group, budget; tag cloud for experiences).
    - Connection Action Footer Card: Heading, helper text, `"Quay lại danh sách"` secondary button, and `"Gửi lời mời kết nối"` primary button.

---

## 11. Accessibility Contract

- **Touch Target Minimum:** All interactive controls (back arrow, report button, connection CTA, back button) satisfy $\ge 44 \times 44\text{ dp}$.
- **Screen Reader Announcements:** Profile components are wrapped in semantic labels:
  *"Hồ sơ bạn đồng hành của Lê Hoàng Nam, tài khoản đã xác minh, độ tuổi 25 đến 29, quốc tịch Việt Nam. Phù hợp với chuyến đi Đà Nẵng vì trùng toàn bộ 4 ngày từ 15 đến 18 tháng 10 và phong cách du lịch Thoải mái. Thông tin riêng tư như số điện thoại và lịch trình chi tiết đang được khóa. Nút bấm: Gửi lời mời kết nối."*
- **Color Independence:** Compatibility indicators use explicit text and checkmark icons (`✓`), never color-only cues.
- **Contrast Ratios:** All text elements meet or exceed WCAG AA ($> 4.5:1$ against `#FFFFFF` / `#F8FAFC`).
