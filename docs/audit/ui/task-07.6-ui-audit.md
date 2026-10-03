# TASK 07.6 — Flutter UI & Map UX Audit Report

**Date:** 2026-10-04  
**Project:** GoMate / WanderAI  
**Target Branch:** `feature/ui-foundation-map-stability`  
**Auditor:** Antigravity Agent  
**Design Reference:** `docs/design/gomate-design-system-ux-spec-v1.md`  

---

## 1. Executive Summary & Purpose

This audit evaluates the Flutter client (`apps/mobile`) prior to implementing TASK 07.6. The goal of TASK 07.6 is to establish centralized GoMate design tokens, create shared reusable UI components, stabilize responsive web/desktop layouts, polish Wandy AI chat (preserving verified source chips), and address two critical map UX issues:
1. Basemap tile failure (grey tiles caused by ISP blocking of `tile.openstreetmap.org`).
2. Stale place preview sheet dangling on category filter switches.
3. Flutter console warning/exception: "Multiple widgets used the same GlobalKey".

---

## 2. Codebase Audit by Subsystem

### 2.1 Design Tokens & Theming (`lib/core/theme/app_theme.dart`)
- **Current State:**
  - `primary`: `#00685F` (Old teal) instead of GoMate v1 `#0F766E`.
  - `primaryContainer`: `#008378` instead of GoMate v1 `#CCFBF1`.
  - `surface`: `#FAF8FF` instead of `#FFFFFF` / background `#F8FAFC`.
  - `onSurface`: `#131B2E` instead of `#0F172A`.
  - `outline`: `#6D7A77` instead of `#E2E8F0`.
  - Semantic tokens (Success `#15803D`, Warning `#B45309`, Info `#2563EB`) are completely missing from the theme definition.
  - Spacing scale (4, 8, 12, 16, 20, 24, 32, 40, 48 px) and Corner Radius tokens (8, 12, 16, 20, 24, 999 px) are not defined as programmatic constants, leading to magic numbers across screens.
  - Category colors are scattered across widgets instead of unified in a design tokens structure.

### 2.2 Navigation & Routing (`lib/core/router/app_router.dart`)
- **Current State:**
  - Tab names mix English and unaccented Vietnamese: `'Kham pha'`, `'Bản đồ'`, `'AI Agent'`, `'An toan'`, `'Chuyen di'`. Must be standardized to Vietnamese diacritics per GoMate UX spec (`Trang chủ`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `Cá nhân` / `An toàn`).
  - **CRITICAL BUG - GlobalKey Collision:**
    ```dart
    final _rootNavigatorKey = GlobalKey<NavigatorState>();
    final _shellNavigatorKey = GlobalKey<NavigatorState>();

    final appRouterProvider = Provider<GoRouter>((ref) {
      final authState = ref.watch(authProvider);
      return GoRouter(
        navigatorKey: _rootNavigatorKey,
        ...
    ```
    Every time `authProvider` emits a new state (e.g. unknown -> authenticated, or user login/logout), `appRouterProvider` re-evaluates and constructs a new `GoRouter` instance passing the *same* static `_rootNavigatorKey` and `_shellNavigatorKey`. Flutter throws `"Multiple widgets used the same GlobalKey"` because the old navigator has not fully unmounted when the new navigator tries to register the key.
  - **Remedy:** Do not re-instantiate `GoRouter` on auth changes. Use a persistent router instance and trigger route redirects via `refreshListenable` listening to auth state transitions.

### 2.3 Map Screen & Basemap Provider (`lib/features/map/`)
- **Current State:**
  - `FlutterMap` uses `urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'`.
  - **Network Test Results (2026-10-04 from local environment):**
    - `https://tile.openstreetmap.org/0/0/0.png`: **FAILED** (`Unable to connect to the remote server` — DNS blocked in Vietnam).
    - `https://a.basemaps.cartocdn.com/rastertiles/voyager/0/0/0.png`: **SUCCESS** (Status 200, 582ms, `image/png`).
    - `https://b.basemaps.cartocdn.com/rastertiles/voyager/0/0/0.png`: **SUCCESS** (Status 200, 147ms, `image/png`).
    - `https://a.basemaps.cartocdn.com/rastertiles/voyager/13/6505/3671.png` (Hanoi tile): **SUCCESS** (Status 200, 2049 bytes).
  - **Preview Sheet Stale State:**
    In `MapNotifier.setCategory(category)`:
    ```dart
    void setCategory(String? category) {
      if (category == 'all') category = null;
      state = state.copyWith(
        selectedCategory: category,
        clearCategory: category == null,
      );
      ...
    ```
    `state.selectedPlace` is NOT cleared! When the user selects a place in "Nhà hàng", then taps "Khách sạn", the bottom preview sheet continues displaying the previous restaurant place.
  - **Rating Representation:**
    `place_preview_sheet.dart` already checks `if (place.rating != null)` and renders `'Chưa có đánh giá'`, which is honest and compliant. However, this logic must be unified into a reusable `RatingView` component so other screens never fallback to 4.5 or 0.0.

### 2.4 Home Screen (`lib/features/home/presentation/home_screen.dart`)
- **Current State:**
  - Content spans unbounded width (`GridView.builder` with 2 columns stretched on a 1920px desktop window).
  - Lacks a welcoming header and Wandy AI CTA card as described in Section 6.5 of `gomate-design-system-ux-spec-v1.md`.
  - Loading state uses a simple raw `CircularProgressIndicator` instead of GoMate skeleton / loading component.

### 2.5 Wandy AI Chat (`lib/features/ai_chat/presentation/ai_chat_screen.dart`)
- **Current State:**
  - In TASK 07.5.1, grounded chat sources were added (`_buildSourceChip`, `_formatSourceLabel`, `_launchSourceUrl`).
  - The feature is fully functional and tested.
  - UI refinement needed: Align font tokens, colors (`#0F766E`), border radius (`16 px`), and responsive max-width wrapper on desktop/web. Preserve all source chip interactions without disruption.

---

## 3. Architecture & Design Alignment Matrix

| Spec Requirement (v1) | Current Codebase | Audit Finding | Action in Task 07.6 |
|---|---|---|---|
| Primary Color `#0F766E` | `#00685F` | Outdated palette | Update in `AppColors` & `AppTheme` |
| Primary Container `#CCFBF1` | `#008378` | Outdated palette | Update in `AppColors` & `AppTheme` |
| Surface `#FFFFFF`, Bg `#F8FAFC` | `#FAF8FF` | Outdated palette | Update in `AppColors` & `AppTheme` |
| Text Primary `#0F172A` | `#131B2E` | Outdated palette | Update in `AppColors` & `AppTheme` |
| Spacing Scale (4, 8, 12, 16...) | Hardcoded literals | Inconsistent spacing | Create `AppSpacing` tokens |
| Radius Scale (8, 12, 16, 20, 24) | Hardcoded literals | Inconsistent radius | Create `AppRadius` tokens |
| Basemap Tiles Reachable | `tile.openstreetmap.org` (blocked) | Grey tiles | Switch to CARTO Voyager OSM raster tiles |
| Map Preview Reset on Filter | `selectedPlace` retained | Stale sheet bug | Add `clearSelectedPlace: true` on category/search change |
| Nullable Rating Handling | Partially in preview | Potential leaks | Centralize in `RatingView` ("Chưa có đánh giá") |
| Desktop/Web Responsive Layout | Unconstrained stretching | Mobile UI stretched | Wrap in `ResponsiveLayout` / max-width 640/900px |
| Router GlobalKey Exception | GlobalKeys recreated | Fatal console error | Fix GoRouter instantiation via ChangeNotifier/Listenable |
| Wandy Grounding Sources | Implemented in 07.5.1 | Fully functional | Preserve 100%, apply design tokens |

---

## 4. Implementation Steps for TASK 07.6

1. **ADR-006:** Author `docs/architecture/decisions/ADR-006-map-tile-provider.md` documenting tile network benchmarks and selection.
2. **Design System Tokens:**
   - Create `apps/mobile/lib/core/theme/app_colors.dart`
   - Create `apps/mobile/lib/core/theme/app_spacing.dart`
   - Create `apps/mobile/lib/core/theme/app_radius.dart`
   - Create `apps/mobile/lib/core/theme/app_typography.dart`
   - Refactor `apps/mobile/lib/core/theme/app_theme.dart`
3. **Shared Reusable UI Components (`apps/mobile/lib/core/widgets/`):**
   - `AppButton` (Primary, Secondary, AI Sparkle variants)
   - `AppCard` (Elevation, border, rounded corners)
   - `AppChip` (Filter, selection, category badges)
   - `AppBadge` (Verified badge with checkmark)
   - `RatingView` (Real stars + score, or "Chưa có đánh giá")
   - `AppLoading` (Centered branded progress indicator)
   - `AppEmptyState` (Friendly empty states with action button)
   - `AppErrorState` (Friendly error message with retry button)
   - `ResponsiveWrapper` (Max-width container centered on web/desktop)
4. **Router & GlobalKey Fix:**
   - Refactor `apps/mobile/lib/core/router/app_router.dart` to prevent Navigator recreation and fix Vietnamese tab labels.
5. **Map UX Fixes:**
   - Update `apps/mobile/lib/features/map/presentation/map_screen.dart` with CARTO Voyager raster tiles and proper attribution.
   - Clear preview sheet in `apps/mobile/lib/features/map/providers/map_provider.dart` on category and search changes.
   - Update `apps/mobile/lib/features/map/presentation/widgets/place_preview_sheet.dart` to use shared `RatingView`, `AppBadge`, and design tokens.
6. **Home & Wandy Polish:**
   - Wrap Home screen in `ResponsiveWrapper`, add header and Wandy AI CTA card.
   - Wrap Chat screen in `ResponsiveWrapper`, ensure design tokens apply seamlessly while keeping source chips intact.
7. **Automated & Manual Verification:**
   - Run Flutter tests and analyzer.
   - Verify backend e2e tests & AI service tests.
   - Run browser QA and capture screenshot evidence in `docs/audit/evidence/ui-07.6/`.
