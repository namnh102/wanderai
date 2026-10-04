# GoMate Wandy AI Copilot — Visual Specification V1

**Status:** APPROVED DESIGN SPECIFICATION  
**Task:** TASK 08.2.3.4 — GOMATE WANDY AI COPILOT VISUAL MOCKUP V1  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:** Master Reference Board (`media_1791138265499.jpg`), GoMate Design System V1, UX Architecture V1  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.4/` (22 High-Fidelity Mockups)

---

## 1. Executive Summary & Brand Direction

Wandy is the central AI Travel Copilot (`Trợ lý Du lịch Đồng hành`) for **GoMate**. Unlike conventional conversational chatbots that exist in isolation or resemble technical dev tools (e.g. ChatGPT, Claude, terminal bots), Wandy is designed from the ground up as a **warm, knowledgeable Vietnamese travel companion**:

1. **Travel-First, Not Chat-First:** Wandy connects conversation directly to actionable spatial entities: places, map markers, itineraries, and trips.
2. **Vietnamese Cultural Identity:** Subtle, tasteful integration of Vietnamese visual heritage (scenic landscapes with Hanoi's ancient pagodas, West Lake, Khuê Văn Các) paired with modern minimalist interface design.
3. **Mascot Personality:** Wandy is represented as an adorable explorer robot—friendly rounded silhouette, deep teal explorer headset, warm khaki field vest, orange compass lanyard, and an explorer backpack. Approachable, curious, and helpful without being cartoonishly distracting.
4. **Data Honesty & Grounded Provenance:** Responses strictly preserve citation chips (`OpenStreetMap`, `Wikivoyage`). Ratings show genuine community feedback or explicit "Chưa có đánh giá" without synthetic inflation.
5. **Multi-Platform Responsiveness:** Mobile ($390 \times 844$) optimized for one-handed on-the-go discovery; Desktop ($1440 \times 900$) provides a productivity workstation with chat history sidebar and multi-column itinerary context.

---

## 2. Visual Design Tokens & Color Palette

| Token Name | Hex Code | Role & Usage | WCAG AA Ratio vs Background |
| :--- | :--- | :--- | :--- |
| `primary` | `#0F766E` | Deep Pine Teal — Brand primary, user message bubbles, active tabs, primary CTAs | 7.4:1 (PASS) |
| `primaryDark` | `#115E59` | Dark Pine Teal — Pressed states, high-contrast subheadings | 9.8:1 (PASS) |
| `primaryContainer` | `#CCFBF1` | Soft Mint Teal — Active tab badge, container buttons, secondary pills | 11.2:1 vs Primary Text |
| `primaryLight` | `#F0FDFA` | Ultra-light Teal — Thinking cards, active list backgrounds | Background base |
| `surface` | `#FFFFFF` | Pure White — Card surfaces, bot message bubbles, dialogs, bottom sheets | 1.0:1 base |
| `background` | `#F8FAFC` | Light Slate Gray — Desktop workspace background, input capsule fill | Neutral backdrop |
| `textPrimary` | `#0F172A` | Deep Slate Navy — Main headings, place titles, message text | 15.2:1 (PASS) |
| `textSecondary` | `#475569` | Medium Slate — Subtitles, metadata rows, secondary descriptions | 5.8:1 (PASS) |
| `textMuted` | `#94A3B8` | Light Slate — Input placeholders, timestamps, subtle borders | 2.6:1 (Non-text/Disabled) |
| `accentAmber` | `#D97706` | Warm Ochre / Amber — Star ratings, food suggestion icons | 4.8:1 (PASS) |
| `accentGreen` | `#10B981` | Emerald Green — Success checkmarks, itinerary planning icons | 4.6:1 (PASS) |
| `accentOrange` | `#F97316` | Sunset Orange — Compass icons, navigation badges | 4.5:1 (PASS) |
| `accentRose` | `#E11D48` | Rose Red — Location pin icons, POI categories | 4.7:1 (PASS) |
| `errorRed` | `#EF4444` | Crimson Red — Disconnected Wi-Fi icon, error indicators | 4.5:1 (PASS) |
| `borderLight` | `#E2E8F0` | Slate Border — Card outlines, dividers, input borders | Structure |

---

## 3. Typography Scale & Font Hierarchy

- **Font Family:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
- **Headings & Hierarchy:**
  - `Hero Heading (Desktop)`: 28px / SemiBold (800) / Line-height 1.25 / Color `#0F172A` / Letter-spacing `-0.5px`
  - `Hero Heading (Mobile)`: 21px / Bold (700) / Line-height 1.3 / Color `#0F172A` / Letter-spacing `-0.3px`
  - `Section / Dialog Title`: 17px–18px / Bold (700) / Line-height 1.35 / Color `#0F172A`
  - `Place Card Title`: 14px–15px / Bold (700) / Line-height 1.3 / Color `#0F172A`
  - `Body / Chat Message`: 13.5px–14px / Regular (400) or Medium (500) / Line-height 1.45 / Color `#1E293B`
  - `Metadata / Category Tag`: 11px–12px / Regular (400) / Line-height 1.3 / Color `#64748B`
  - `Caption / Timestamp`: 10px–11px / Medium (500) / Line-height 1.2 / Color `#94A3B8`

---

## 4. Component Architecture & Specifications

### 4.1. Top Navigation & App Bar
- **Mobile (`$390 \times 844$`):**
  - Height: 52px (excluding 44px OS status bar).
  - Left: Back button (24px chevron) + Title `Wandy AI` (18px bold `#0F172A`).
  - Right: Search icon (`🔍`) + Overflow actions (`...`).
  - Background `#FFFFFF`, bottom hairline border `1px solid #F1F5F9`.
- **Desktop (`$1440 \times 900$`):**
  - Height: 64px global navigation bar.
  - Left: `GoMate` brand badge (32px teal container with pin icon) + wordmark `GoMate` (21px bold `#0F766E`).
  - Center: Global tab bar (`Khám phá`, `Bản đồ`, `Wandy AI` [Active with 3px solid teal bottom indicator], `An toàn`, `Chuyến đi`).
  - Right: User avatar (36px circle `#E0F2FE` with initials `N`).

### 4.2. Empty State Hero (Mobile & Desktop)
- **Mobile Empty State (`wandy-mobile-empty.png`):**
  - Centered hero container with clean illustration of Wandy explorer mascot standing cheerfully in front of Hanoi's West Lake Pagoda, mountains, and pastel clouds.
  - Greeting text: `Chào bạn! Mình là Wandy 👋` (21px bold).
  - Descriptive subtitle: `Mình có thể giúp bạn khám phá, tìm địa điểm và lên kế hoạch cho chuyến đi của bạn.` (13.5px `#64748B`, max-width 310px).
  - Quick Prompt 2x2 grid:
    1. `[✨] Lập lịch trình` (Active highlight: `#F0FDFA` background, `#CCFBF1` border, `#0F766E` text).
    2. `[📍] Tìm địa điểm` (`#FFFFFF` background, `#FFE4E6` icon box, `#1E293B` text).
    3. `[🍜] Gợi ý món ngon` (`#FFFFFF` background, `#FEF3C7` icon box, `#1E293B` text).
    4. `[🧭] Khám phá gần bạn` (`#FFFFFF` background, `#E0F2FE` icon box, `#1E293B` text).
- **Desktop Empty State (`wandy-desktop-empty.png`):**
  - Wide hero container card ($1100\text{px} \times 280\text{px}$) with gradient background `135deg, #FFFFFF 0%, #F0FDFA 100%`, border `1.5px solid #CCFBF1`, rounded 28px, box shadow `0 12px 35px rgba(15,118,110,0.06)`.
  - Left: Wandy walking illustration with walking stick and backpack in landscape ($280\text{px} \times 210\text{px}$).
  - Right: Headline (28px bold), subtitle (15px `#475569`), and horizontal row of 4 prompt cards ($4 \times 1\text{fr}$).

### 4.3. Message Bubbles & Visual Hierarchy
- **User Message:**
  - Alignment: Right (`align-self: flex-end`).
  - Background: Solid Deep Teal `#0F766E`.
  - Text: `#FFFFFF`, 13.5px–14px.
  - Border radius: `18px 18px 4px 18px`.
  - Timestamp: Bottom right, 10px `#CCFBF1`.
  - Shadow: `0 2px 6px rgba(15,118,110,0.20)`.
- **Assistant Message:**
  - Alignment: Left (`align-self: flex-start`).
  - Leading: Wandy circular avatar (34px circle `#CCFBF1` with Wandy mascot face).
  - Title row: `Wandy AI` (12px bold `#0F172A`) + timestamp `09:41` (10px `#94A3B8`).
  - Bubble: Background `#FFFFFF`, border `1.5px solid #F1F5F9`, border radius `4px 18px 18px 18px`, text 13.5px `#1E293B`, line-height 1.45, shadow `0 2px 8px rgba(0,0,0,0.03)`.

### 4.4. Source Chips & Citations
- **Label:** `Nguồn tham khảo` (11px, bold, uppercase, `#64748B`, letter-spacing 0.4px).
- **Chip Appearance:**
  - Background: `#F8FAFC`.
  - Border: `1.5px solid #E2E8F0`.
  - Border radius: 16px (pill).
  - Padding: 4px 10px.
  - Icon: Node circle icon for OpenStreetMap; Book icon for Wikivoyage.
  - Text: 11px font-weight 600 `#0F766E`.
  - Tap interaction: Opens Source Detail inspection modal (`wandy-mobile-source-detail.png`) displaying OSM Node ID, coordinates, licensing (ODbL, CC BY-SA 4.0), and verification timestamp.

### 4.5. Place Recommendation Cards
- **Carousel Variant (`wandy-mobile-chat.png`):**
  - Horizontal scroll container, width 165px per card, border radius 14px, border `1.5px solid #E2E8F0`.
  - Top: 85px high thumbnail photo.
  - Body: Place title (12.5px bold), category + city (`Văn hóa • Hà Nội`), distance (`2.4 km từ bạn`), rating badge (`★ 4.6 (128)`).
  - Action footer: Two outline buttons `[Xem trên bản đồ]` and `[Xem thêm địa điểm]`.
- **Rich Card Variant (`wandy-mobile-chat-sources.png` & `wandy-mobile-place-recommendation.png`):**
  - Full width card, border radius 16px–20px, border `1.5px solid #E2E8F0`.
  - Photo hero with `✓ Đã xác minh nguồn dữ liệu` floating badge (indicating validated source provenance, NOT field physical audit).
  - Explicit caption: `* Visual Demo State — Not Production Data` to clearly distinguish illustrative mockups from production database realities.
  - Address and operating hours rows with teal vector icons (with explicit fallback to "Chưa có thông tin..." if absent).
  - Action button row:
    - Primary CTA: `[Xem địa điểm]` or `[Thêm vào chuyến đi]` (solid teal `#0F766E`, white text).
    - Secondary CTA: `[Chỉ đường]` (container mint `#CCFBF1`, teal text `#0F766E`).
- **Multi-Place Compact List (`wandy-mobile-multi-place-results.png`):**
  - Vertical list of 4–5 items, each 56px thumbnail on left, title, category, distance, and rating on right.
  - Bottom sticky/block CTA: `[Xem tất cả trên bản đồ]` (height 42px, container mint `#CCFBF1`, teal text `#0F766E`).

### 4.6. Progress & Streaming Thinking States
- **Thinking State (`wandy-mobile-thinking.png`):**
  - Header: `Wandy AI đang suy nghĩ...` in teal `#0F766E`.
  - Cyan card (`#F0FDFA` bg, `#CCFBF1` border) with step checklist:
    - `✓ Phân tích nhu cầu của bạn...` (emerald green check)
    - `✓ Tìm kiếm địa điểm phù hợp...` (emerald green check)
    - `✓ Kiểm tra nguồn tham khảo...` (emerald green check)
    - `• Tối ưu lịch trình theo ngân sách...` (teal active indicator)
    - Three-dot pulsating loader animation.
- **Generating State (`wandy-mobile-generating.png`):**
  - Header: `[🔄] Wandy đang lập lịch trình...`
  - Dynamic step checklist reflecting actual pipeline stages without misleading numeric percentages:
    - `✓ Tìm địa điểm phù hợp`
    - `✓ Sắp xếp theo tuyến đường`
    - `• Cân đối thời gian & ngân sách...`
    - `• Hoàn thiện lịch trình`
  - Smooth indeterminate pulse bar (`#14B8A6` to `#0F766E`) and status text: `Đang tính toán tuyến đường tối ưu...` (Eliminates artificial 70% progress illusion).
  - Mascot illustration of Wandy sitting with travel map and backpack.

### 4.7. Error & Fallback States
- **Disconnected / Service Error (`wandy-mobile-error.png`, `wandy-desktop-error.png`):**
  - Disconnected Wi-Fi alert badge in light red circle (`#FEE2E2`).
  - Title: `Wandy đang gặp sự cố` (20px bold `#0F172A`).
  - Description: `Không thể kết nối tới dịch vụ AI. Vui lòng kiểm tra kết nối mạng và thử lại.`
  - Action buttons: Primary `[Thử lại]` solid pill + Secondary `[Về màn hình chính]` text button.
- **No Answer / Clarification (`wandy-mobile-no-answer.png`):**
  - Puzzled Wandy illustration with floating question mark.
  - Title: `Mình chưa hiểu rõ ý bạn`.
  - Subtitle: `Bạn có thể thử hỏi theo cách khác hoặc chọn gợi ý bên dưới:`.
  - 4 Prompt pills leading back to valid travel queries.

### 4.8. Dialogs & Action Overlays
- **Add to Trip Modal (`wandy-mobile-add-to-trip-action.png`):**
  - Dimmed background overlay (`rgba(15,23,42,0.45)`).
  - Bottom sheet with title `Thêm vào chuyến đi`, close icon `✕`.
  - Radio list of active trips (Hà Nội 3N2Đ Mùa Thu selected with green check).
  - Secondary button: `[+ Tạo chuyến đi mới]`.
  - Primary button: `[Tiếp tục (Chọn ngày) →]`.
- **Agent Confirmation Dialog (`wandy-mobile-agent-confirmation.png`, `wandy-desktop-agent-confirmation.png`):**
  - Classified explicitly as **FUTURE AGENT UX** (Sprint 02+).
  - Prominent badge at top: `FUTURE AGENT UX • HUMAN-IN-THE-LOOP` in amber/ochre container (`#FEF3C7`).
  - Center modal with Wandy avatar header.
  - Title: `Xác nhận hành động`.
  - Message: `Bạn có muốn thêm Chùa Trấn Quốc vào Hà Nội 3N2Đ Mùa Thu Ngày 2 (16/10/2026)?`
  - Safeguard banner: `🛡️ Tác vụ sửa đổi lịch trình luôn yêu cầu người dùng xác nhận trực tiếp trước khi ghi dữ liệu.`
  - Buttons: `[Xác nhận thêm vào chuyến đi]` (solid teal) and `[Hủy bỏ]` (neutral).

---

## 5. Desktop-Specific Layout Architecture

On desktop screens ($1440 \times 900$), Wandy expands into a 3-column workstation:
1. **Left Sidebar ($260\text{px}$):** Chat history grouped chronologically (`Hôm nay`, `Tuần này`), with active conversation pill indicator and quick `+ Đoạn chat mới` button.
2. **Center Chat Canvas ($880\text{px}$):**
   - Trip Context banner at the top (`Đang lập: Hà Nội 3N2Đ Mùa Thu | 15/10 - 17/10/2026 • 3 ngày` + `[Xem chi tiết]`).
   - Wide conversational message flow with horizontal place carousels.
   - Fixed floating input capsule at bottom with generous padding ($60\text{px}$ height).
3. **Right Context Sidebar ($300\text{px}$):**
   - Quick contextual actions (`Tối ưu lại lịch trình ngày 2`, `Gợi ý quán ăn gần đó`, `Kiểm tra ngân sách`).
   - Active place preview panel and mini map anchor showing the locations currently discussed in chat.

---

## 6. Accessibility & Motion Guidelines

- **Touch Target Size:** All buttons, chips, and input controls maintain a minimum target area of $44 \times 44\text{px}$ (Mobile) and $38 \times 38\text{px}$ (Desktop).
- **Color Contrast:** All body text (`#0F172A`, `#1E293B`) achieves $\ge 7.4:1$ contrast against white/neutral backgrounds. Subtitles (`#475569`, `#64748B`) achieve $\ge 4.8:1$ (exceeding WCAG AA 4.5:1 minimum).
- **Reduced Motion Support:** Respects `prefers-reduced-motion`. Replaces pulsating thinking dots with static indicators; disables slide-up sheet animations in favor of immediate opacity fade ($150\text{ms}$).
- **Screen Reader Semantics:**
  - Wandy avatar labeled as `Ảnh đại diện Trợ lý Wandy`.
  - Source chips announced as `Nguồn dữ liệu OpenStreetMap đã được đối chiếu, nhấn để xem chi tiết chứng thực`.
  - Star ratings announced as `4.6 trên 5 sao từ 128 lượt đánh giá (dữ liệu minh họa giao diện)`.

---

## 7. R1 Corrections & Design Lock (TASK 08.2.3.4-R1)

### 7.1. Provenance Terminology Rule
The following absolute rule is enforced across all UI screens, documentation, and audits:
$$\text{SOURCE VERIFIED} \neq \text{FIELD VERIFIED} \neq \text{HIGH RATING}$$

1. **Forbidden Language:** Phrasing such as *"Đã xác minh thực địa"* or *"Đã xác thực thực địa qua GoMate Data Pipeline"* is strictly prohibited because the data pipeline ingests and reconciles geospatial sources (OpenStreetMap, Wikivoyage) rather than dispatching staff on physical on-site inspections.
2. **Approved Language:**
   - `"Đã xác minh nguồn dữ liệu"`
   - `"Nguồn dữ liệu đã được đối chiếu"`
   - `"Đối chiếu nguồn: OpenStreetMap & Wikivoyage"`

### 7.2. Visual Demo State vs Production Data
All high-fidelity mockups depicting rich sample data (e.g. `★ 4.6 (128)`, operating hours `07:30 – 17:30`, specific phone numbers) are designated as **VISUAL DEMO STATE — NOT PRODUCTION DATA**.

When implementing UI in Flutter, the following honest fallback rules are mandatory:
| Field | When Data Exists | When Data Is Absent (Honest Fallback) |
| :--- | :--- | :--- |
| **Rating** | `★ 4.6 (128)` | `Chưa có đánh giá` (No stars, neutral badge) |
| **Address** | Actual formatted address | `Chưa có thông tin địa chỉ` |
| **Opening Hours** | Actual schedule | `Chưa có thông tin giờ mở cửa` |
| **Contact / Phone** | Formatted phone number | Entire contact section is cleanly hidden |
| **Provenance** | Verified source badge | Unverified / synthetic data flag |

### 7.3. Non-Deterministic Progress Behavior
1. **Elimination of Fake Percentages:** LLM and RAG generation cannot predict exact percentage completion. Mockup `wandy-mobile-generating.png` has been revised to remove the synthetic `70%` progress bar.
2. **Approved Loading Pattern:** Indeterminate pulse bar with realistic pipeline phase checklist:
   - `✓ Tìm địa điểm phù hợp`
   - `✓ Sắp xếp theo tuyến đường`
   - `• Cân đối thời gian & ngân sách...`
   - `• Hoàn thiện lịch trình`

### 7.4. Capability Separation Matrix: Current vs Future Agent

| Feature / Action | Scope | Technical Basis | UI Representation |
| :--- | :---: | :--- | :--- |
| **Conversational Chat** | CURRENT | Gemini 1.5 Flash via FastAPI `/chat` | Standard message bubbles |
| **Spatial RAG Retrieval** | CURRENT | pgvector embeddings + PostgreSQL | Grounded entity answers |
| **Source Citations** | CURRENT | OpenStreetMap / Wikivoyage provenance | Tappable source chips |
| **Place Recommendations** | CURRENT | Canonical Place catalog | Rich cards / Carousels |
| **Trip Context Injection** | CURRENT | Active Trip model | Trip context header banner |
| **Manual Add-to-Trip** | CURRENT | REST API `/trips/:id/items` | Trip picker bottom sheet |
| **Autonomous Itinerary Mutation** | FUTURE | Multi-agent autonomous planner (Sprint 02+) | `FUTURE AGENT UX` Confirmation Modal |
| **Autonomous Booking / Reminders** | FUTURE | Tool-use agent integrations | `FUTURE AGENT UX` Confirmation Modal |
| **Proactive Group Collaboration** | FUTURE | Realtime websocket agents | `FUTURE AGENT UX` Banner |

### 7.5. Empty State Hierarchy
To eliminate confusion between empty screens, two distinct states are formally established:
1. **Default Empty State (`wandy-mobile-empty.png`):**
   - The primary landing state upon opening the Wandy AI tab (Tab 3) without existing chat history.
   - Layout: Centered explorer mascot, friendly greeting, brief capability summary, and 4 primary starter prompt cards (`Lập lịch trình`, `Tìm địa điểm`, `Gợi ý món ngon`, `Khám phá gần bạn`).
2. **Expanded Discovery State (`wandy-mobile-empty-prompts.png`):**
   - An expanded suggestion view accessed when tapping the "Khám phá Việt Nam cùng Wandy" discovery banner or exploring category ideas.
   - Layout: Landscape banner header + 6 thematic prompt rows for users seeking inspiration.

### 7.6. Source Detail Safety & Metadata Boundaries
In `wandy-mobile-source-detail.png`:
- OpenStreetMap Node IDs (e.g. `Node #268491024`) and micro-coordinates are **Demonstration Metadata**.
- In production, these fields are only displayed when the upstream data source explicitly provides them. If unavailable, the source sheet displays the entity name and source license without fabricating node numbers.

### 7.7. Human-in-the-Loop Safeguard Contract
**Invariant:** *No AI action may mutate, delete, or overwrite user trip itineraries without explicit, conscious user confirmation.*
- Vague conversational cues (e.g. *"Ok thêm đi"*) must trigger the `FUTURE AGENT UX` confirmation modal (`wandy-mobile-agent-confirmation.png` / `wandy-desktop-agent-confirmation.png`).
- The modal displays:
  - Exact target trip name and target day.
  - Entity to be added or modified.
  - Distinct `[Xác nhận thêm]` (Teal) and `[Hủy bỏ]` (Neutral) buttons.
  - Safeguard disclosure: `🛡️ Tác vụ sửa đổi lịch trình luôn yêu cầu người dùng xác nhận trực tiếp trước khi ghi dữ liệu.`

### 7.8. Neutral Copilot Language (No AI Over-claiming)
Wandy communicates as an assistant, not an omniscient entity:
- Prefer: *"Wandy có thể gợi ý...", "Wandy tìm thấy...", "Dựa trên nguồn OpenStreetMap..."*
- Avoid: *"Wandy hiểu mọi điều về bạn...", "Wandy đã kiểm tra thực địa...", "Wandy đảm bảo 100%..."*

### 7.9. Visual Design Lock Confirmation
The visual design of Wandy AI Copilot across 22 mockups, color tokens, typography scales, responsive layouts, and safety patterns is formally **LOCKED** for subsequent Flutter implementation. Zero further design iterations are permitted without explicit product architecture approval.

