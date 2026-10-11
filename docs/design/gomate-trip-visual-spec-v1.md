# GoMate Trip Management — Visual Specification V1

**Status:** APPROVED DESIGN SPECIFICATION (REVISION R1 LOCKED)  
**Tasks:** TASK 08.2.3.5 & TASK 08.2.3.5-R1 (UX Contract & Visual Consistency Correction)  
**Target Viewports:** Mobile ($390 \times 844$), Tablet ($768 \times 1024$), Desktop ($1440 \times 900$)  
**Source of Truth:** GoMate Design System V1, UX Architecture V1, Master UX Plan V2, Prisma Schema  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.5/` (36 Mockups: 25 Mobile + 6 Desktop + 5 R1 Refinements)  

---

## 1. Executive Summary & Brand Direction

The **Trip Management** module (`Quản lý Chuyến đi`) serves as the planning, execution, and budgeting core of **GoMate**. It bridges geospatial discovery (Map & Place Detail) and generative intelligence (Wandy AI Copilot) into a coherent, organized travel plan.

Key design principles:
1. **Travel-First Clarity:** Prioritizes chronological and spatial sequencing. The user can view their day's schedule at a glance, understanding what comes next, where it is, and what it costs.
2. **Visual Consistency:** Strict harmony with GoMate's Deep Pine Teal (`#0F766E`), Soft Mint (`#CCFBF1`), and Slate neutrals, maintaining continuity across Home, Map, Place Detail, and Wandy Chat.
3. **Data Honesty & Invariant Integrity:**
   - Budget numbers are derived from verified item costs or explicit user budgets; no synthetic figures.
   - The AI Planner preview is strictly non-destructive and isolated from the database until confirmed.
   - No fake progress percentages during AI generation; use honest live elapsed timers and real step transitions.
   - Create Trip CTA strictly reads **"Tạo chuyến đi"** (decoupled from AI planning).
   - "Sở thích du lịch" is excluded from persistent Trip Create forms; interests belong to conversational AI Planner inputs.
   - Travel Style labels are strictly standardized to verified Vietnamese terms.
4. **Multi-Platform Ergonomics:**
   - *Mobile ($390 \times 844$):* Fast, one-handed mobile navigation with thumb-friendly bottom action bars, clear day selector pills, and vertical chronological timelines.
   - *Desktop ($1440 \times 900$):* High-efficiency 3-pane workstation featuring a persistent trip metadata sidebar, a spacious center timeline canvas, and an analytics/budget sidebar.

---

## 2. Visual Design Tokens & Standardized Enums

### 2.1. Color Palette

| Token Name | Hex Code | Role & Usage | WCAG AA Ratio vs Background |
| :--- | :--- | :--- | :--- |
| `primary` | `#0F766E` | Deep Pine Teal — Brand primary, active day tab, primary buttons, timeline dots | 7.4:1 (PASS) |
| `primaryDark` | `#115E59` | Dark Pine Teal — Gradient endpoints, pressed states | 9.8:1 (PASS) |
| `primaryContainer` | `#CCFBF1` | Soft Mint Teal — Status badges (`ĐÃ LÊN LỊCH`, `ĐANG DIỄN RA`), active accents | 11.2:1 vs Primary Text |
| `primaryLight` | `#F0FDFA` | Ultra-light Mint — AI banner background, active menu items | Neutral light base |
| `surface` | `#FFFFFF` | Pure White — Card surfaces, modal sheets, timeline cards | Base surface |
| `background` | `#F8FAFC` | Light Slate Gray — Screen backdrop, secondary form controls | Neutral backdrop |
| `textPrimary` | `#0F172A` | Deep Slate Navy — Trip titles, activity names, primary numbers | 15.2:1 (PASS) |
| `textSecondary` | `#64748B` | Medium Slate — Metadata rows, dates, secondary labels | 5.8:1 (PASS) |
| `textMuted` | `#94A3B8` | Light Slate — Placeholders, inactive drag handles, watermarks | 2.6:1 (Non-text/Disabled) |
| `borderLight` | `#E2E8F0` | Slate Border — Card outlines, timeline connector lines | Structural border |
| `borderFocus` | `#0D9488` | Teal Accent Border — Dashed AI banners, active input borders | 4.8:1 (PASS) |
| `budgetSafe` | `#10B981` | Emerald Green — Under-budget indicators, safe status badges | 4.6:1 (PASS) |
| `budgetWarning` | `#F59E0B` | Warm Amber — 85% to 100% budget threshold alerts | 4.5:1 (PASS) |
| `budgetDanger` | `#EF4444` | Crimson Red — Over-budget alerts (>100%), delete actions | 4.5:1 (PASS) |
| `tagFood` | `#FEF3C7` / `#92400E` | Amber Pill — Food & beverage activity categories | 6.2:1 (PASS) |
| `tagBeach` | `#E0F2FE` / `#0369A1` | Sky Blue Pill — Nature, sea, and beach activities | 6.5:1 (PASS) |
| `tagCulture` | `#F3E8FF` / `#6B21A8` | Purple Pill — Heritage, culture, and temple activities | 6.8:1 (PASS) |

### 2.2. Standardized TravelStyle Enum Mapping (Locked)

| Prisma Enum Value | Canonical Vietnamese Label | Secondary Subtitle | Design Note |
| :--- | :--- | :--- | :--- |
| `BACKPACKER` | **Phượt** | Tự do, khám phá | Replaces informal slang |
| `BUDGET` | **Tiết kiệm** | Tối ưu chi phí | Standardized |
| `COMFORT` | **Thoải mái** | Cân bằng, tiện nghi | **Locked:** Replaces ambiguous "Tiêu chuẩn" |
| `LUXURY` | **Sang trọng** | Trải nghiệm cao cấp | **Locked:** Replaces "Nghỉ dưỡng" |

---

## 3. Typography Scale & Font Hierarchy

- **Font Family:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
- **Scale:**
  - `Hero Heading (Desktop)`: 28px / SemiBold (800) / Line-height 1.25 / `#0F172A`
  - `Trip Detail Title (Mobile)`: 19px–20px / Bold (800) / Line-height 1.3 / `#FFFFFF` (over gradient)
  - `Section / Dialog Title`: 18px–20px / Bold (700) / Line-height 1.3 / `#0F172A`
  - `Activity Title`: 14px–15px / Bold (700) / Line-height 1.35 / `#0F172A`
  - `Time Column`: 11px–13px / Bold (700) / Line-height 1.2 / `#0F766E`
  - `Body / Metadata Text`: 12px–13.5px / Regular (400) or Medium (500) / Line-height 1.4 / `#64748B`
  - `Category & Status Pills`: 10px–11px / Bold (700) / Letter-spacing +0.3px / Uppercase
  - `Watermark Disclaimer`: 9.5px–11px / Regular (400) / `#94A3B8` / Centered

---

## 4. Component Architecture & Detailed Specifications

### 4.1. Trip List Screen & Cards (List View)
- **Mockup Reference:** `trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`, `trip-desktop-list.png`
- **Single Primary Action Principle:**
  - The top app bar hosts a single primary `+` button in the top right.
  - The duplicate Floating Action Button (FAB) at the bottom right is **REMOVED** to adhere strictly to the One Primary Action principle.
- **Filter Tabs Bar:**
  - `Hiện tại & sắp tới (N)`: Active ongoing trips (`ONGOING`) and future trips (`PLANNED`).
  - `Đã kết thúc (N)`: Historical trips (`COMPLETED`).
  - `Bản nháp (N)`: Draft itineraries (`DRAFT`).
- **Card Container:** Rounded corners 18px, border 1px solid `#E2E8F0`, surface `#FFFFFF`, box shadow `0 2px 8px rgba(15, 23, 42, 0.04)`.
- **Media Header (Height 110px):**
  - Linear gradient reflecting destination style.
  - Top Badges: `● ĐANG DIỄN RA` (`#CCFBF1`), `ĐÃ LÊN LỊCH` (`rgba(255,255,255,0.25)`), `ĐÃ KẾT THÚC` (`#F1F5F9`).
  - Title: Overlaid at bottom of media header with soft drop shadow.
- **Card Body:**
  - Metadata List: Destination pin, date range with current day indicator (e.g. `Ngày 2 / 4`), members count, travel style (`Thoải mái` / `Sang trọng`).
  - Budget Progress Bar: Track height 5px `#E2E8F0`, fill `#0F766E`. Formatted as `4.850.000 / 8.000.000 đ`.

### 4.2. Trip Creation Screen
- **Mockup Reference:** `trip-mobile-create-r1.png`, `trip-desktop-create.png`
- **Fields (Strictly Matching `CreateTripDto`):**
  - Tên chuyến đi [Required]: Single-line text input.
  - Điểm đến [Required]: Autocomplete / text input with pin icon.
  - Thời gian bắt đầu / kết thúc [Required]: Date picker controls with auto-computed duration.
  - Tổng ngân sách dự kiến (VND) [Optional]: Numeric currency input.
  - Phong cách du lịch [Optional]: 4 choice chips with locked labels (`Phượt`, `Tiết kiệm`, `Thoải mái`, `Sang trọng`).
  - **No Interests Field:** "Sở thích du lịch" is omitted from persistence form; passed as conversational prompt during AI planning.
- **Primary CTA:**
  - Button text: **"Tạo chuyến đi"** (NOT "Tạo chuyến đi & Lên lịch").
  - Decoupled from AI Planner: Creates `Trip` record only and routes to empty Trip Detail.

### 4.3. Trip Detail Hero Card & Empty State
- **Mockup Reference:** `trip-mobile-detail.png`, `trip-mobile-detail-empty-r1.png`
- **Title Consistency Invariant:**
  - Top App Bar Title and Hero Card Title must use the exact same `Trip.title` (e.g. `"Kỳ nghỉ Hạ Long 3N2Đ"`).
- **Empty State Options (Dual CTAs):**
  - Option 1 (AI Recommended): Dashed teal card with Wandy mascot/sparkle icon, title "Lập lịch trình thông minh với Wandy AI", button "Lập lịch trình bằng AI ✨".
  - Divider: "- HOẶC -".
  - Option 2 (Manual): Dashed neutral card, title "Tự lên lịch thủ công", button "+ Thêm".

### 4.4. Add Activity Bottom Sheet
- **Mockup Reference:** `trip-mobile-add-activity-r1.png`
- **Direct 1:1 Contract Mapping with `ItineraryItem`:**
  1. `dayNumber`: Dropdown selector [Ngày 1 — 15/10/2026 ▼].
  2. `activity` (Tên hoạt động) [Required]: Independent text input (e.g. "Bữa trưa Hải sản Bé Mặn").
  3. `placeId?` (Địa điểm liên kết) [Optional]: Separate search box with pin icon and verified badge.
  4. `startTime` / `endTime`: Time pickers.
  5. `estimatedCost`: Integer VND input.
  6. `transportMode`: Choice chips (`Đi bộ`, `Xe máy`, `Taxi / Grab` [Selected], `Ô tô riêng`, `Xe buýt`).
  7. `notes`: Textarea for notes and tips.
  8. Action Button: **"Lưu hoạt động"** (`#0F766E`).

### 4.5. Chronological Timeline Component
- **Mockup Reference:** `trip-mobile-timeline.png`, `trip-mobile-detail.png`
- **Left Time & Line Column (Width 48px):**
  - Time text: 11px bold `#0F766E`.
  - Dot: 12px circular dot `#0F766E`, outer ring 2.5px `#CCFBF1`.
  - Connector line: Width 2px, `#E2E8F0`.
- **Timeline Card Content:**
  - Container: Background `#FFFFFF`, border 1px solid `#E2E8F0`, border-radius 14px, padding 12px 14px.
  - Header: Activity title + Category chip (Food `#FEF3C7`, Beach `#E0F2FE`, Culture `#F3E8FF`).
  - Meta row: Estimated cost badge, transport mode icon, duration.
  - Notes callout: Slate background `#F8FAFC`, left border 3px solid `#0F766E`.

### 4.6. AI Generating Feedback Widget
- **Mockup Reference:** `trip-mobile-ai-generating.png`
- **Visual Centerpiece:** Circular badge (72x72px) with gradient teal background and pulsing sparkles.
- **Real Elapsed Timer:** `Đang xử lý (14s...)` with real ticking clock display.
- **Dynamic Step Cues:** Progress checklist showing completed steps and active step.
- **Guaranteed No-Fake-Metric:** Explicitly excludes pseudo progress percentages.

### 4.7. Budget Progress & Threshold Indicator
- **Mockup Reference:** `trip-mobile-budget.png`, `trip-mobile-budget-warning.png`, `trip-mobile-budget-over.png`, `trip-desktop-detail-budget.png`
- **Visual States:**
  1. **Safe ($< 85\%$):** Track fill `#0F766E`, status badge `Ngân sách an toàn`.
  2. **Warning ($85\% - 100\%$):** Track fill `#F59E0B`, status badge `Cảnh báo: Đạt 93% ngân sách`.
  3. **Over Budget ($> 100\%$):** Track fill `#EF4444`, status badge `Vượt ngân sách (+650.000 đ)`.

### 4.8. Global 5-Tab Navigation Bar Component (Mobile)
- **Mockup Reference:** `trip-mobile-list-upcoming-r1.png`, `trip-mobile-list-past-r1.png`
- **Layout:** Fixed docked bar at bottom, height 64px, surface `#FFFFFF`, top border 1px solid `#E2E8F0`.
- **Destinations (1:1 with Router):**
  1. Tab 1: `Khám phá` (compass/explore icon)
  2. Tab 2: `Bản đồ` (map icon)
  3. Tab 3: `Wandy AI` (sparkles icon)
  4. Tab 4: `An toàn` (shield icon)
  5. Tab 5: `Chuyến đi` (luggage icon — Active state in `#0F766E`)

---

## 5. Global Navigation Reconciliation

```
============================================================
GLOBAL NAVIGATION RECONCILIATION
============================================================

CURRENT IMPLEMENTATION:
In `apps/mobile/lib/core/router/app_router.dart`:
The app router uses `_MainScaffold` with 5 destinations:
1. `/`        -> Trang chủ / Khám phá (Icons.explore)
2. `/map`     -> Bản đồ (Icons.map)
3. `/ai`      -> Wandy AI (Icons.auto_awesome)
4. `/safety`  -> An toàn (Icons.shield)
5. `/trips`   -> Chuyến đi (Icons.luggage)

DESIGN SPEC:
`docs/design/gomate-ux-architecture-v1.md` Section 3 establishes
the 5-tab root shell (Home, Map, Wandy AI, Safety, Trips).

FINAL DESIGN DECISION:
The 5-tab navigation architecture is confirmed as the authoritative
standard across both code and design specifications.
Trip mockups rendering root navigation (upcoming-r1, past-r1)
display the full 5 tabs with Tab 5 (`Chuyến đi`) active.
```

---

## 6. Watermark Evidence Notice

> [!NOTE]
> **WATERMARK IS EVIDENCE-ONLY, NOT PRODUCTION UI**  
> The watermark string `VISUAL DEMO DATA — NOT PRODUCTION DATA` included in mockups is an evidence-only marker designed to prevent any misinterpretation of mockups as live database output during academic or professional reviews. It does not exist in production code or runtime Flutter widgets.
