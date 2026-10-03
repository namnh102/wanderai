# GoMate UI Architecture & Design System Specification

**Version:** 1.0.0  
**Status:** Living Architecture Document  
**Date:** 2026-10-04  
**Implementation:** Flutter 3.x with Riverpod 2.x and GoRouter 14.x  

---

## 1. Architectural Philosophy

GoMate's UI architecture follows a **mobile-first, token-driven, composable component** design principle:

```text
┌────────────────────────────────────────────────────────┐
│                   Design Tokens                        │
│   AppColors · AppTypography · AppSpacing · AppRadius   │
└──────────────────────────┬─────────────────────────────┘
                           │ drives
┌──────────────────────────▼─────────────────────────────┐
│                 Central ThemeData                      │
│             AppTheme.lightTheme / darkTheme            │
└──────────────────────────┬─────────────────────────────┘
                           │ consumed by
┌──────────────────────────▼─────────────────────────────┐
│              Shared Component Library                  │
│  AppButton · AppCard · AppChip · AppBadge · RatingView │
│  AppLoading · AppEmptyState · AppErrorState · Wrapper  │
└──────────────────────────┬─────────────────────────────┘
                           │ assembled into
┌──────────────────────────▼─────────────────────────────┐
│                   Feature Screens                      │
│       Home · Map · Wandy Chat · Trips · Profile        │
└────────────────────────────────────────────────────────┘
```

### Key Rules:
1. **Zero Ad-Hoc Styling:** Feature screens must never hardcode raw hex colors or random padding values. All styling inherits from `AppColors`, `AppSpacing`, `AppRadius`, and `Theme.of(context)`.
2. **Predictable State Handling:** Every data screen implements five standard visual states: *Initial, Loading, Loaded/Success, Empty, and Error*.
3. **Data Integrity in Presentation:** Rating values are never fabricated. If `rating == null`, display `"Chưa có đánh giá"`.
4. **Responsive Guardrails:** On desktop/web viewports, content is constrained by `ResponsiveWrapper` (max-width 640px for content, 900px for dashboards) to prevent distorted, stretched mobile layouts.

---

## 2. Design Tokens

### 2.1 Color System (`AppColors`)

- **Brand:**
  - `primary`: `#0F766E` (GoMate Teal-700) — Primary CTAs, active tab icons, AI brand accent.
  - `primaryContainer`: `#CCFBF1` (Teal-100) — Subtle active backgrounds and chips.
  - `onPrimary`: `#FFFFFF`
- **Semantic:**
  - `success`: `#15803D`, container: `#DCFCE7`
  - `warning`: `#B45309`, container: `#FEF3C7`
  - `error`: `#B91C1C`, container: `#FEE2E2`
  - `info`: `#2563EB`, container: `#DBEAFE`
- **Neutrals:**
  - `background`: `#F8FAFC` (Slate-50)
  - `surface`: `#FFFFFF`
  - `surfaceContainer`: `#F1F5F9` (Slate-100)
  - `textPrimary`: `#0F172A` (Slate-900)
  - `textSecondary`: `#475569` (Slate-600)
  - `textTertiary`: `#94A3B8` (Slate-400)
  - `border`: `#E2E8F0` (Slate-200)
- **Category Semantic Palette:**
  - Attraction: `#9333EA` (Purple-600)
  - Culture: `#4F46E5` (Indigo-600)
  - Nature: `#16A34A` (Green-600)
  - Beach: `#0284C7` (Sky-600)
  - Cafe: `#78350F` (Amber-900)
  - Restaurant: `#EA580C` (Orange-600)
  - Hotel: `#0D9488` (Teal-600)
  - Entertainment: `#DB2777` (Pink-600)

### 2.2 Typography (`AppTypography`)

- Font family: `Plus Jakarta Sans` (with robust Unicode diacritics support for Vietnamese).
- Strict typographic scale:
  - `display`: 30px / 700 bold
  - `h1`: 24px / 700 bold
  - `h2`: 20px / 700 bold
  - `h3`: 18px / 600 semi-bold
  - `bodyL`: 16px / 400 regular
  - `bodyM`: 14px / 400 regular
  - `bodyS`: 13px / 400 regular
  - `label`: 12px / 600 semi-bold
  - `button`: 14px / 600 semi-bold

### 2.3 Spacing Scale (`AppSpacing`)

Based on a strict 4-pixel grid system:
- `xs`: 4 px
- `sm`: 8 px
- `mdSmall`: 12 px
- `md`: 16 px (default page padding)
- `lgSmall`: 20 px
- `lg`: 24 px
- `xl`: 32 px
- `xxl`: 40 px
- `xxxl`: 48 px

### 2.4 Corner Radius (`AppRadius`)

- `sm`: 8 px (input controls, badges, chips)
- `md`: 12 px (buttons, dialogs)
- `lg`: 16 px (cards, preview containers)
- `xl`: 20 px (hero banners)
- `sheet`: 24 px (bottom sheet top corners)
- `pill`: 999 px (tags, circular buttons)

---

## 3. Shared Reusable Component Library (`lib/core/widgets/`)

| Component | Responsibility | Props / States |
|---|---|---|
| `AppButton` | Unified button component | `Primary`, `Secondary`, `AI / Sparkle`, `Tonal`, `isLoading`, `onPressed` |
| `AppCard` | Elevated or outlined container | `child`, `padding`, `onTap`, `hasBorder` |
| `AppChip` | Category & filter chip | `label`, `icon`, `isSelected`, `onTap`, `color` |
| `AppBadge` | Verified badge / status indicator | `isVerified`, `customLabel`, `color` |
| `RatingView` | Honest rating display | `rating: double?`, `reviewCount: int?` ("Chưa có đánh giá" when null) |
| `AppLoading` | Standardized loader | `message`, `compact` |
| `AppEmptyState` | Illustrated empty state | `title`, `description`, `actionLabel`, `onAction` |
| `AppErrorState` | User-friendly error message | `message`, `onRetry` |
| `ResponsiveWrapper` | Web/desktop viewport constraint | `maxWidth: double`, `child` |

---

## 4. Navigation Architecture & GlobalKey Management

To eliminate the Flutter console warning `"Multiple widgets used the same GlobalKey"`:
- The `GoRouter` instance must be lifecycle-managed and persistent.
- Auth state changes do not rebuild the `GoRouter` instance. Instead, a `ChangeNotifier` bridge or `refreshListenable` informs `GoRouter` to re-execute its `redirect` function.
- Root and Shell `GlobalKey<NavigatorState>` instances are created once and maintained across the lifetime of the application.

---

## 5. Map UX & Spatial Discovery Architecture

### 5.1 Layering Model
```text
┌────────────────────────────────────────────────────────┐
│ Search & Category Bar (Positioned Top)                 │
├────────────────────────────────────────────────────────┤
│ Place Count Badge & Radius Controls (Floating)         │
├────────────────────────────────────────────────────────┤
│ Place Preview Sheet (Bottom Sheet, dynamic)            │
├────────────────────────────────────────────────────────┤
│ Custom POI Markers (PostGIS LatLng + Category Icons)   │
├────────────────────────────────────────────────────────┤
│ CARTO Voyager Raster Basemap (TileLayer)               │
└────────────────────────────────────────────────────────┘
```

### 5.2 Basemap Provider
- Provider: **CARTO Voyager** (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png`).
- Fully accessible from Vietnamese ISPs (Status 200, ~140ms response).
- High visual readability behind colorful POI markers.

### 5.3 Preview Sheet State Machine
- When a marker is tapped: `selectedPlace` is set in `MapState`, triggering the preview sheet.
- When category filter changes: `selectedPlace` is **explicitly cleared** (`clearSelectedPlace: true`), preventing stale preview sheets.
- When search query changes: `selectedPlace` is **explicitly cleared**.
- When map surface is tapped: `selectedPlace` is cleared.

---

## 6. Wandy AI Chat & Evidence Preservation

- Wandy AI chat operates as a contextual conversational travel copilot.
- Grounding citations from TASK 07.5.1 are strictly preserved in `ChatMessage.sources`.
- Sources are rendered as compact, interactive chips (`OpenStreetMap`, `Wikivoyage`) below the assistant reply.
- Tapping a source chip opens the canonical source URL in an external browser via `url_launcher`.
