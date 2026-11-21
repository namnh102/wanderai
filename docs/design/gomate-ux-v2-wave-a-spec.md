# GoMate — UX V2 Wave A Design System & Concept Specification

**Status:** Candidate for Owner & Independent Review (`Wave A` — PR review-only)  
**Base Baseline:** `namnh102/wanderai` `develop` (`880ce7763c3006aaf59eff8ad2e2ebd9688ca371`)  
**Product Direction:** *"Vietnam travel editorial + trustworthy AI copilot"*

---

## 1. Visual Identity & Color System

GoMate V2 shifts from generic developer boilerplate (`WanderAI` flat cards + harsh grey tiles) to a calm, warm coastal-and-heritage editorial aesthetic built around deep teal, warm stone, and restrained terracotta/coral accents.

| Token | Hex | Role | Backward Compatibility |
|---|---|---|---|
| `AppColors.primary` | `#0F766E` | Core GoMate brand teal, active tabs, primary CTA | Existing V1 token preserved |
| `AppColors.primaryDeep` | `#123B43` | Deep Ocean Teal for editorial headers, hero cards, dark contrast | New V2 token |
| `AppColors.primaryContainer` | `#CCFBF1` | Soft mint-teal tint for badges, pills, active tab indicator | Existing V1 token preserved |
| `AppColors.background` | `#F8FAFC` | Default neutral scaffold surface (kept for V1 contract parity) | Existing V1 token preserved |
| `AppColors.warmBackground` | `#F7F9F6` | Soft Editorial Warm Stone canvas for Home V2 surface sections | New V2 token |
| `AppColors.surface` | `#FFFFFF` | Card, sheet, search bar, dock surface | Existing V1 token preserved |
| `AppColors.warmSurface` | `#FFFCF7` | Warm card wash for highlights and Wandy preview containers | New V2 token |
| `AppColors.accentCoral` | `#F07B5A` | Restrained warm coral for `"Nổi bật"` / editorial focal accents | New V2 token |
| `AppColors.accentCoralContainer` | `#FFEDE6` | Soft coral tint background | New V2 token |
| `AppColors.border` / `softBorder` | `#E2E8F0` / `#E2E9E6` | Hairline 1px borders instead of heavy drop shadows | Preserved + V2 warm border |

### Typography Hierarchy
Clean geometric sans typography (`Be Vietnam Pro` / `Plus Jakarta Sans` / Roboto fallback — zero network font blocking offline) with Vietnamese diacritic clearance (`height >= 1.25–1.5`, crisp weight separation `w500` / `w600` / `w700`).

---

## 2. Shared Component Contracts (`core/widgets`)

1. **`AppCard`** — Surface container (`16px` radius, `1px` `softBorder` or optional low-alpha shadow), uniform ripple ink feedback, safe `Clip.antiAlias`.
2. **`AppSectionHeader`** — Editorial title + optional count pill / `"Xem tất cả →"` button (`>=44px` hit target).
3. **`AppSearchBar`** — Tactile `>=48px` tall rounded field with search icon, clear action, or interactive Home search handoff.
4. **`AppStateBanner`** — Inline non-blocking info/warning/offline/GPS notice with optional CTA (`"Thử lại"`, `"Bật vị trí"`).
5. **`AppSkeletonBox` / `_HomeLoadingSkeleton`** — Static stone-tinted layout skeleton avoiding infinite animation timers so Flutter widget tests settle deterministically while communicating exact content structure.
6. **`AppBadge` & `RatingView`** — Strict DUX-02 integrity: `"Đã xác minh"` only when provenance exists; `"Chưa có đánh giá"` when `rating == null || rating == 0`.

---

## 3. Data Honesty & Truthful State Rules (Inherited & Enforced in Wave A)

- **Ratings:** Never synthesize `4.5` or `0.0`. Display real review-backed ratings or explicitly render `Chưa có đánh giá`.
- **Verified Places:** Only provenance-backed places (`GET /places?verifiedOnly=true`) appear in public discovery and show `Đã xác minh`.
- **Location / Distance:** Never auto-prompt OS location on opening Home or Map. Show neutral dashed `"Bật vị trí để xem địa điểm gần bạn"` card until user taps `"Bật vị trí"`, and surface `LocationAccuracyBadge` once a fix arrives.
- **Safety:** Never imply working emergency dispatch / SMS alerts while `/safety` is not yet backend-backed.
- **Offline / Error / AI Unavailable:** Surface honest recoverable inline banners or `AppErrorState` with `"Thử lại"`.

---

## 4. Screen Mockup Portfolio (`docs/design/mockups/v2/`)

| # | Mockup File | Viewport | Screen & Purpose |
|---|---|---|---|
| 1 | `01-login-v2.png` | `390x844` | GoMate Entry & Login — accented Vietnamese copy, clean inputs, visual calm |
| 2 | `02-home-discover-v2.png` | `390x844` | Home / Discover V2 — Greeting, Search, Wandy Copilot, REC-A Entry, Featured Destinations, Nearby / Verified Places |
| 3 | `03-map-explore-v2.png` | `390x844` | Map V2 — HOT basemap, fixed single-icon category chips, destination selector, preview sheet |
| 4 | `04-place-detail-v2.png` | `390x844` | Place Detail V2 — Verified badge, honest null states, factual OSM hours/address/source attribution, sticky CTA |
| 5 | `05-wandy-copilot-v2.png` | `390x844` | Wandy Copilot V2 — Grounded conversation, OSM source pills, fail-closed status notice |
| 6 | `06-trips-overview-v2.png` | `390x844` | Trips V2 — Accented Vietnamese copy, structured budget/dates, AI itinerary CTA |
| 7 | `07-profile-safety-v2.png` | `390x844` | Proposed Profile & Safety Hub (`Cá nhân`) with preferences, travel style, & truthful Safety access |
| 8 | `08-nav-v1-vs-v2-comparison.png` | `920x860` | Side-by-side comparison of Locked V1 Shell vs Proposed `UX-V2-NAV-01` |
| 9 | `09-home-desktop-v2.png` | `1440x900` | Responsive desktop composition (`maxWidth` column, multi-column grids) |

---

## 5. Pending Decision: `UX-V2-NAV-01` (Not Mutated in Code Yet)

**Locked V1 Production Shell (`apps/mobile/lib/core/router/app_router.dart`):**
1. `Trang chủ` (`/`)
2. `Bản đồ` (`/map`)
3. `Wandy AI` (`/ai`)
4. `An toàn` (`/safety` — currently placeholder `"Tính năng đang phát triển..."`)
5. `Chuyến đi` (`/trips`)
*(Notice Profile/Preferences and Logout currently live inside Home AppBar icons rather than a dedicated tab.)*

**Proposed V2 Architecture (`UX-V2-NAV-01` — Awaiting Owner Sign-off):**
1. `Khám phá` (`/`)
2. `Bản đồ` (`/map`)
3. `Wandy` (`/ai`)
4. `Chuyến đi` (`/trips` — includes Trip Safety Checklist / Share entry)
5. `Cá nhân` (`/profile` — houses Profile, Travel Preferences, App Settings, Logout, AND prominent **Trung tâm An toàn** card with clear status transparency)

**Safety Guarantee:** Safety is **never removed**—instead it moves from a bare top-level placeholder tab into prominent contextual access inside both **Chuyến đi** and **Cá nhân** once Safety backend modules are implemented in later waves, while keeping direct `/safety` route reachable. Code in `app_router.dart` remains locked at V1 5 tabs for Wave A.
