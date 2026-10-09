# GoMate Buddy Discovery — Privacy, Data Honesty & IA Correction Report (TASK 08.2.3.7-R1)

**Status:** APPROVED DESIGN & CONTRACT CORRECTION (R1 LOCKED)  
**Task:** TASK 08.2.3.7-R1 — GOMATE BUDDY DISCOVERY PRIVACY, DATA HONESTY & IA CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Purpose

TASK 08.2.3.7-R1 executes targeted micro-corrections for **Buddy Discovery V1** to lock privacy tiers, data honesty invariants, and information architecture parity prior to commencing Buddy Profile design.

This audit-driven refinement addresses 9 specific areas identified during post-V1 review:
1. **Verified Badge Semantics:** Distinguishing email/account verification from identity (CCCD/KYC) verification.
2. **Hometown / Residence Removal:** Eliminating unpersisted city data from discovery cards.
3. **Age Privacy:** Masking exact age/DOB into standardized 5-year age bands.
4. **Profile Privacy Notice:** Clarifying public profile access vs private post-match data to resolve CTA conflict.
5. **Match Explanation Wording:** Removing percentage-like phrasing in favor of concrete calendar overlap language.
6. **Global IA Parity:** Reconciling desktop navigation back to the canonical 5 root tabs.
7. **Discoverability Toggle Honesty:** Formally categorizing `isDiscoverable` as a design target blocked by schema.
8. **Safety Dependency Honesty:** Maintaining `Block` and `Report` as unsafe/blocked dependencies.
9. **Eligibility Contract Restructuring:** Dividing discovery eligibility into currently enforceable vs target rules.

---

## 2. Item-by-Item Correction Matrix

### Item 1 — Verified Badge Semantics
- **Before:** V1 mockup showed a verified checkmark icon next to user names, risking interpretation as government ID or legal identity verification.
- **Risk:** Legal liability and user mistrust; users may believe candidates have been KYC-verified with CCCD/Passport when only basic email verification occurred.
- **Source Evidence:**
  - `apps/backend/prisma/schema.prisma` (`User.isVerified Boolean @default(false)`).
  - `apps/backend/src/modules/auth/` sets `isVerified` upon email confirmation link/token.
  - No KYC, citizen ID, or biometric verification exists in GoMate.
- **Correction:** The badge is explicitly labeled `"Tài khoản đã xác minh"`. It is strictly forbidden to use `"Đã xác minh danh tính"`.
- **Final Contract:** UI renders `{ICONS['verified']} Tài khoản đã xác minh` (Mint `#F0FDFA`, Teal `#0F766E`, border `#CCFBF1`).

---

### Item 2 — Hometown / Residence Data Honesty
- **Before:** V1 candidate cards displayed `"TP. Hồ Chí Minh"` (Candidate 1) and `"Hà Nội"` (Candidate 2).
- **Risk:** Data fabrication; the mobile UI presents fields that do not exist in the database, breaking backend integration contracts.
- **Source Evidence:**
  - `apps/backend/prisma/schema.prisma` (`model Profile` contains: `userId`, `displayName`, `avatar`, `bio`, `phone`, `dateOfBirth`, `nationality`, `languages`).
  - No `city`, `province`, `hometown`, or `residence` field exists in `Profile`.
- **Correction:** Specific city names are removed from candidate cards. Replaced with `Profile.nationality` (`"Việt Nam"`). Hometown/residence is marked: `FUTURE PROFILE FIELD — NOT CURRENT DATA CONTRACT`.
- **Final Contract:** Candidate metadata row displays: `25–29 tuổi · Việt Nam · Tiếng Việt, English`.

---

### Item 3 — Age Privacy (Standardized Age Bands)
- **Before:** V1 displayed exact ages: `"26 tuổi"`, `"24 tuổi"`.
- **Risk:** Privacy leakage; exact age combined with name, avatar, and travel dates facilitates reverse identification / doxxing before any mutual consent.
- **Source Evidence:**
  - `Profile.dateOfBirth DateTime?` stores exact DOB.
  - Privacy best practice dictates masking DOB into age brackets for unverified third parties in discovery feeds.
- **Correction:** Discovery cards mask exact age into standardized 5-year age bands: `20–24 tuổi`, `25–29 tuổi`, `30–34 tuổi`, `35–39 tuổi`.
- **Final Contract:** Candidate 1 displays `25–29 tuổi`; Candidate 2 displays `20–24 tuổi`. Exact DOB remains Tier 4 sensitive.

---

### Item 4 — Profile Privacy Notice Copy
- **Before:** V1 footer banner read: `"Hồ sơ chi tiết chỉ mở khi kết nối"`.
- **Risk:** Semantic contradiction; each candidate card has a primary CTA `"Xem hồ sơ"`. Users would be confused whether tapping the button opens anything or is blocked until connecting.
- **Source Evidence:**
  - UX flow: Discovery Card $\rightarrow$ Public Buddy Profile (Bio, styles, interests) $\rightarrow$ Send Request $\rightarrow$ Accept $\rightarrow$ Private contact/itinerary unlocked.
- **Correction:** Replaced footer copy with: `"Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối."`
- **Final Contract:** Users understand that public profile is viewable prior to request, but private details (phone, full itinerary) require mutual consent.

---

### Item 5 — Match Explanation Wording (Date Overlap)
- **Before:** V1 compatibility box stated: `"Trùng 100% thời gian tại Đà Nẵng (15/10 – 18/10)."`.
- **Risk:** Resembles fake algorithmic match percentages (e.g. "100% match"), violating the project's data honesty invariant against pseudo-precision scores.
- **Source Evidence:**
  - `docs/design/gomate-design-system-ux-spec-v1.md` Section 6.21 bans fake compatibility percentages.
- **Correction:** Replaced with explicit calendar duration phrasing: `"Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10)."`.
- **Final Contract:** All compatibility criteria use qualitative or concrete factual statements with emerald checkmarks (`✓`).

---

### Item 6 — Global Navigation & IA Reconciliation
- **Before:** Mobile used canonical 5 root tabs with `Chuyến đi` active. Desktop V1 independently invented an additional 6th top-nav link `"Bạn đồng hành"`.
- **Risk:** Divergent information architecture between mobile and desktop; desktop suggested `/buddy` was a root destination, while mobile treated it as a contextual travel submodule.
- **Source Evidence:**
  - `apps/mobile/lib/core/router/app_router.dart`: Defines 5 root tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `An toàn`, `Chuyến đi`).
  - `docs/design/gomate-master-ux-plan-v2.md`: Confirms 5 canonical root tabs.
- **Correction:** Desktop top nav restored to exactly 5 canonical root tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` active, `An toàn`). Buddy Discovery is framed as a contextual submodule via breadcrumbs: `Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành`.
- **Final Contract:** 5-tab root IA invariant is strictly preserved across all device form factors.

---

### Item 7 — Discoverability Toggle Honesty
- **Before:** Desktop sidebar rendered `"Hiển thị tìm bạn: Đang Bật"`, implying a live production preference.
- **Risk:** Overclaiming implementation readiness; toggling discovery does not work in backend because the schema lacks the flag.
- **Source Evidence:**
  - `apps/backend/prisma/schema.prisma`: Neither `User` nor `Profile` has `isDiscoverable`.
- **Correction:** Formally classified as `DESIGN TARGET — BLOCKED BY DATA MODEL`. In the desktop mockup, the toggle is explicitly badged: `Mục tiêu thiết kế — Cần bổ sung isDiscoverable trong DB`.
- **Final Contract:** UI demonstrates target privacy design while documentation and visual cues prevent false claims of backend backing.

---

### Item 8 — Block & Report Dependency Honesty
- **Before:** Safety contracts mentioned blocking and reporting without highlighting runtime absence.
- **Risk:** Security vulnerability; users in discovery have no mechanism to block bad actors.
- **Source Evidence:**
  - `apps/backend/prisma/schema.prisma`: Zero models for `Block`, `UserBlock`, `Report`, or `UserReport`.
- **Correction:** Status explicitly maintained as `UNSAFE / BLOCKED DEPENDENCY`. Discovery cannot be launched to production until safety migrations are applied.
- **Final Contract:** Documented as mandatory prerequisite for Buddy module implementation.

---

### Item 9 — Target Discovery Eligibility Contract Restructuring
- **Before:** Single eligibility list mixing current Prisma checks with nonexistent models (`isDiscoverable`, `Block`).
- **Risk:** Confusing frontend engineers into assuming backend APIs enforce all 7 rules today.
- **Source Evidence:**
  - Audited `schema.prisma` vs target business specifications.
- **Correction:** Contract restructured into two clear sections: `Currently Enforceable` (account verified, not deleted, not self, active trip overlap) vs `Requires Implementation` (isDiscoverable, blocking, abuse reports, rejection cooldown).
- **Final Contract:** Crystal-clear handoff for database migrations and service queries.

---

## 3. Visual Artifacts Verification (R1 Regenerated)

Both master visual artifacts were regenerated and verified in `docs/audit/evidence/ui-08.2.3.7/`:

```
============================================================
REGENERATED MASTER ARTIFACTS (TASK 08.2.3.7-R1)
============================================================

1. MOBILE MASTER (390 x 844):
   - Path: docs/audit/evidence/ui-08.2.3.7/buddy-mobile-discovery-r1.png
   - Resolution: 390 x 844 px
   - Elements Verified:
     * App Bar: "Bạn đồng hành" + "Quyền riêng tư" badge
     * Context Pill: "Đà Nẵng · 15/10 – 18/10/2026"
     * Verified Pill: "Tài khoản đã xác minh"
     * Candidate 1 Meta: "25–29 tuổi · Việt Nam · Tiếng Việt, English"
     * Candidate 1 Overlap: "Trùng toàn bộ 4 ngày tại Đà Nẵng (15–18/10)."
     * Candidate 2 Meta: "20–24 tuổi · Việt Nam · Tiếng Việt"
     * Privacy Banner: "Thông tin riêng tư chỉ hiển thị sau khi hai bên kết nối."
     * Bottom Nav: 5 canonical tabs (Chuyến đi active)
     * No browser scrollbars, clean pixel rendering.

2. DESKTOP MASTER (1440 x 900):
   - Path: docs/audit/evidence/ui-08.2.3.7/buddy-desktop-discovery-r1.png
   - Resolution: 1440 x 900 px
   - Elements Verified:
     * Top Header: 5 canonical root tabs (Khám phá, Bản đồ, Wandy AI, Chuyến đi [active], An toàn)
     * Breadcrumb: "Chuyến đi > Khám phá Đà Nẵng 4N3Đ > Bạn đồng hành"
     * Left Sidebar: Active Trip + Filters (20–29 tuổi) + Privacy Status Toggle
     * Toggle Pill: "Mục tiêu thiết kế — Cần bổ sung isDiscoverable trong DB"
     * Right Canvas: 2-column cards grid with "Tài khoản đã xác minh", age bands, clean overlap wording
     * No browser scrollbars, clean workstation layout.
============================================================
```

---

## 4. Capability Status Matrix (Post-R1 Lock)

| Capability Area | Capability Status | Implementation Reality |
| :--- | :---: | :--- |
| **Buddy Discovery Feed** | **DESIGN TARGET** | Zero discovery API code exists currently. |
| **Buddy Matching Algorithm** | **FUTURE** | Hotel recommendation exists (ViHoRec); Buddy matching does not. |
| **Match Request** | **PARTIAL (DB Only)** | `Match` model exists in schema; API controller missing. |
| **User Block** | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **User Report** | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |
| **Discoverability Toggle** | **UNSAFE / BLOCKED** | Requires `isDiscoverable` migration in `Profile`. |
| **Verified Badge** | **CURRENT (Auth Semantics)** | Strictly reflects email/account verification. |

---

## 5. Source Code Integrity Verification

```powershell
git diff apps/
# Result: EMPTY (0 files modified)
```

No changes were made to Flutter client, NestJS backend, AI service, Prisma schema, or API contracts.
File `docs/weekly-reports/W01/weekly-report-W01.docx` remains unstaged.
