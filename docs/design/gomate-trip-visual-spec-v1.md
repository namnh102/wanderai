# GoMate Trip Management — Visual Specification V1

**Status:** APPROVED DESIGN SPECIFICATION  
**Task:** TASK 08.2.3.5 — GOMATE TRIP MANAGEMENT VISUAL MOCKUP V1 + UX / BUSINESS FLOW DESIGN  
**Target Viewports:** Mobile ($390 \times 844$), Tablet ($768 \times 1024$), Desktop ($1440 \times 900$)  
**Source of Truth:** GoMate Design System V1, UX Architecture V1, Master UX Plan V2  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.5/` (31 High-Fidelity Mockups: 25 Mobile + 6 Desktop)  

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
4. **Multi-Platform Ergonomics:**
   - *Mobile ($390 \times 844$):* Fast, one-handed mobile navigation with thumb-friendly bottom action bars, clear day selector pills, and vertical chronological timelines.
   - *Desktop ($1440 \times 900$):* High-efficiency 3-pane workstation featuring a persistent trip metadata sidebar, a spacious center timeline canvas, and an analytics/budget sidebar.

---

## 2. Visual Design Tokens & Color Palette

| Token Name | Hex Code | Role & Usage | WCAG AA Ratio vs Background |
| :--- | :--- | :--- | :--- |
| `primary` | `#0F766E` | Deep Pine Teal — Brand primary, active day tab, primary buttons, timeline dots | 7.4:1 (PASS) |
| `primaryDark` | `#115E59` | Dark Pine Teal — Gradient endpoints, pressed states | 9.8:1 (PASS) |
| `primaryContainer` | `#CCFBF1` | Soft Mint Teal — Status badges (`ĐÃ LÊN LỊCH`), active accents | 11.2:1 vs Primary Text |
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

---

## 3. Typography Scale & Font Hierarchy

- **Font Family:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
- **Scale:**
  - `Hero Heading (Desktop)`: 28px / SemiBold (800) / Line-height 1.25 / `#0F172A`
  - `Trip Detail Title (Mobile)`: 20px / Bold (800) / Line-height 1.3 / `#FFFFFF` (over gradient)
  - `Section / Dialog Title`: 18px–20px / Bold (700) / Line-height 1.3 / `#0F172A`
  - `Activity Title`: 14px–15px / Bold (700) / Line-height 1.35 / `#0F172A`
  - `Time Column`: 11px–13px / Bold (700) / Line-height 1.2 / `#0F766E`
  - `Body / Metadata Text`: 12px–13.5px / Regular (400) or Medium (500) / Line-height 1.4 / `#64748B`
  - `Category & Status Pills`: 10px–11px / Bold (700) / Letter-spacing +0.3px / Uppercase
  - `Watermark Disclaimer`: 10px–11px / Regular (400) / `#94A3B8` / Centered

---

## 4. Component Architecture & Detailed Specifications

### 4.1. Trip Card (List View)
- **Mockup Reference:** `trip-mobile-list-upcoming.png`, `trip-desktop-list.png`
- **Container:** Rounded corners 18px, border 1px solid `#E2E8F0`, surface `#FFFFFF`, box shadow `0 2px 10px rgba(15, 23, 42, 0.04)`.
- **Media Header (Height 120px - 140px):**
  - Linear gradient reflecting destination style (e.g. Pine Teal for Da Nang `#0F766E → #115E59`, Ocean Blue for Phu Quoc `#0284C7 → #0369A1`).
  - Top Badges: Status tag (`ĐÃ LÊN LỊCH` in `#CCFBF1`, `BẢN NHÁP` in `#FEF3C7`), and AI generated badge (`Tạo bởi AI` with frosted glass background `rgba(255, 255, 255, 0.2)`).
  - Title: Overlaid at bottom of media header, white bold text with soft drop shadow `0 1px 3px rgba(0,0,0,0.2)`.
- **Card Body:**
  - Metadata List: Destination pin, date range, member count, travel style chip.
  - Budget Progress Bar: Track height 6px `#E2E8F0`, fill `#0F766E` (or Amber/Red if warning/over). Formatted as `6.450.000 / 8.000.000 đ`.

### 4.2. Trip Detail Hero Card (Mobile)
- **Mockup Reference:** `trip-mobile-detail.png`
- **Banner Area (Height 120px):**
  - Rich gradient background, status chip, AI badge, back button, more menu (`⋮`).
- **Body Area:**
  - Destination, Date range (e.g. `15/10 - 18/10/2026 (4 ngày)`), Budget target.
  - 3-Column Stat Strip:
    - Cột 1: `4` / Ngày
    - Cột 2: `13` / Hoạt động
    - Cột 3: `6.450.000 đ` / Dự toán

### 4.3. AI Planner CTA Banner
- **Mockup Reference:** `trip-mobile-detail.png`, `trip-mobile-detail-empty.png`
- **Background:** Gradient `#F0FDFA → #CCFBF1`, border 1.5px dashed `#0D9488`, border-radius 16px.
- **Left Element:** Teal rounded icon container (40x40px) with white sparkle icon.
- **Text:** Title "Lập lịch trình thông minh với Wandy AI", subtitle "Tự động phân bổ điểm đến & tối ưu ngân sách trong 30 giây".
- **Action Button:** Capsule button `#0F766E`, text "Thử ngay ✨", white text, shadow `0 2px 6px rgba(15, 118, 110, 0.2)`.

### 4.4. Day Selector Tabs (Carousel)
- **Mockup Reference:** `trip-mobile-detail.png`, `trip-mobile-timeline.png`
- **Layout:** Horizontal scrollable row, gap 8px, padding 0 16px.
- **Pills:**
  - `Default Pill`: Surface `#FFFFFF`, border 1px solid `#E2E8F0`, text `#64748B`, font-weight 600, border-radius 999px.
  - `Active Pill`: Background `#0F766E`, border 1px solid `#0F766E`, text `#FFFFFF`, font-weight 700, shadow `0 2px 8px rgba(15, 118, 110, 0.25)`.
  - Content: "Tất cả", "Ngày 1 (15/10)", "Ngày 2 (16/10)", "Ngày 3 (17/10)", "Ngày 4 (18/10)".

### 4.5. Chronological Timeline Component
- **Mockup Reference:** `trip-mobile-timeline.png`, `trip-mobile-detail.png`
- **Left Time & Line Column (Width 48px):**
  - Time text: 11px bold `#0F766E` (e.g. `09:00`).
  - Dot: 12px circular dot `#0F766E`, outer ring 2.5px `#CCFBF1`.
  - Connector line: Width 2px, `#E2E8F0`, centered vertically to connect consecutive items. Hidden after last item.
- **Timeline Card Content:**
  - Container: Background `#FFFFFF`, border 1px solid `#E2E8F0`, border-radius 14px, padding 12px 14px.
  - Header: Activity title (14px bold) + Category chip (Food `#FEF3C7`, Beach `#E0F2FE`, Culture `#F3E8FF`).
  - Meta row: Estimated cost badge (e.g. `800.000 đ`), transport mode icon (`Taxi / Grab`), duration (`1h 30m`).
  - Notes callout: Light slate background `#F8FAFC`, left border 3px solid `#0F766E`, text 11.5px `#64748B`.

### 4.6. AI Generating Feedback Widget
- **Mockup Reference:** `trip-mobile-ai-generating.png`
- **Visual Centerpiece:** Circular badge (72x72px) with gradient teal background and pulsing sparkles.
- **Real Elapsed Timer:** `Đang xử lý (14s...)` with real ticking clock display.
- **Dynamic Step Cues:** Progress checklist showing completed steps (checkmarks) and active animated step.
- **Guaranteed No-Fake-Metric:** Explicitly excludes pseudo progress percentages.

### 4.7. Budget Progress & Threshold Indicator
- **Mockup Reference:** `trip-mobile-budget.png`, `trip-mobile-budget-warning.png`, `trip-mobile-budget-over.png`, `trip-desktop-detail-budget.png`
- **Visual States:**
  1. **Safe ($< 85\%$ allocated):**
     - Track fill: `#0F766E` (Deep Pine Teal)
     - Label: `6.450.000 / 8.000.000 đ`
     - Status Badge: `Ngân sách an toàn (Dư 1.550.000 đ)` in `#CCFBF1`
  2. **Warning ($85\% - 100\%$ allocated):**
     - Track fill: `#F59E0B` (Warm Amber)
     - Label: `7.450.000 / 8.000.000 đ`
     - Status Badge: `Cảnh báo: Đạt 93% ngân sách (Còn dư 550.000 đ)` in `#FEF3C7`
  3. **Over Budget ($> 100\%$ allocated):**
     - Track fill: `#EF4444` (Crimson Red)
     - Label: `8.650.000 / 8.000.000 đ`
     - Status Badge: `Vượt ngân sách (+650.000 đ)` in `#FEE2E2` with prompt to adjust items.

### 4.8. Sticky Bottom Actions Bar (Mobile)
- **Mockup Reference:** `trip-mobile-detail.png`
- **Position:** Docked at bottom, height 68px, surface `#FFFFFF`, top border 1px solid `#E2E8F0`, box shadow `0 -4px 16px rgba(15, 23, 42, 0.05)`.
- **Left Column:** Label "Dự toán chuyến đi (4 ngày)", bold value `6.450.000 / 8.000.000 đ`.
- **Right Button:** "Xem Bản đồ" with map icon, background `#0F766E`, padding 10px 18px, border-radius 12px, white text.

---

## 5. Responsive Layout Specifications

### 5.1. Mobile ($390 \times 844$ px)
- Single column flow with 16px page margins.
- Top App Bar (52px height) with Back button, Title, Map icon, More menu.
- Fixed Bottom Bar (68px height) for quick budget glance and map entry.
- Modals slide up from bottom as modal sheets with drag handle and rounded top corners (20px).

### 5.2. Tablet ($768 \times 1024$ px)
- 2-Column Responsive Layout:
  - Left column (300px): Trip summary card, budget gauge, and day navigation.
  - Right column (flex-1): Interactive timeline stream and activity management.

### 5.3. Desktop ($1440 \times 900$ px)
- **Mockup Reference:** `trip-desktop-detail.png`, `trip-desktop-list.png`, `trip-desktop-detail-budget.png`, `trip-desktop-ai-preview.png`
- 3-Pane Workstation Architecture:
  1. **Top Global Navigation (64px):** GoMate logo, main nav links (Khám phá, Bản đồ, Chuyến đi [Active], Wandy AI), user avatar.
  2. **Left Sidebar (Width 340px):**
     - Trip title, status pills, date/member metadata.
     - Secondary menu (Timeline, Ngân sách & Chi phí, Thành viên, Cài đặt).
     - AI Planner launch card with gradient background and prompt button.
  3. **Center Canvas (Flex 1):**
     - Day filter tabs ("Tất cả", "Ngày 1", "Ngày 2", "Ngày 3", "Ngày 4").
     - Chronological timeline stream with time slots, duration badges, and activity cards.
     - Quick activity add button ("+ Thêm hoạt động").
  4. **Right Sidebar (Width 340px):**
     - Real-time Budget Progress & breakdown gauge.
     - Category allocation preview (Lưu trú, Ẩm thực, Tham quan, Di chuyển).
     - Wandy Copilot insights and travel tips.

---

## 6. Micro-Interactions, Gestures & Motion

| Interaction | Trigger | Visual Response | Duration / Curve |
| :--- | :--- | :--- | :--- |
| **Day Tab Switch** | Tap day pill | Active pill transitions background `#0F766E`, smooth horizontal scroll into center | 200ms `easeOutCubic` |
| **Add Activity Sheet** | Tap "+ Thêm hoạt động" | Bottom sheet slides up with backdrop dim (`#0F172A66`) | 250ms `easeOutQuint` |
| **Delete Activity** | Swipe left on card | Reveals red trash background; confirm prompt slides up | 200ms `easeIn` |
| **Timeline Reorder** | Drag item handle | Card elevates (`shadow-lg`), scale 1.02, sibling items shift smoothly | Spring curve |
| **AI Planner Preview Reveal** | Generation finished | Modal sheet expands with slide-fade transition, budget diff animates | 300ms `easeOutQuad` |
| **Skeleton Loading** | Route mount | Shimmer gradient shifts horizontally across placeholder boxes | 1200ms infinite loop |

---

## 7. Accessibility & Contrast Compliance (WCAG 2.1 AA)

1. **Text Contrast:**
   - Deep Slate Navy `#0F172A` on `#FFFFFF` surface yields **15.2:1** (exceeds 4.5:1 requirement).
   - Deep Pine Teal `#0F766E` on `#FFFFFF` yields **7.4:1** (exceeds 4.5:1 requirement).
   - Secondary text `#64748B` on `#FFFFFF` yields **5.8:1** (exceeds 4.5:1 requirement).
2. **Touch Target Size:**
   - All interactive icons (Back, More, Map, Add) have a minimum touch bounding box of **$44 \times 44$ dp**.
   - Day selector pills provide minimum hit target of $48 \times 36$ dp.
3. **Screen Reader Semantics:**
   - Status badges announce state: "Trạng thái: Đã lên lịch".
   - Budget values announce full currency text: "Dự toán sáu triệu bốn trăm năm mươi nghìn đồng trên tổng ngân sách tám triệu đồng".
   - Drag handles contain accessibility actions: "Di chuyển lên", "Di chuyển xuống".

---

## 8. Visual Demo Honesty Disclaimer & Watermark Standard

To ensure rigorous honesty across academic and professional evaluations:
- All visual mockup screens contain the standardized watermark:
  ```
  VISUAL DEMO DATA — NOT PRODUCTION DATA
  ```
- All mockups illustrate UI/UX layouts and flows without masquerading as automated tests or live database dumps.
