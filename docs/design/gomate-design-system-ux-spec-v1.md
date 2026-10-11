# GoMate — Design System & Full Screen/UX Specification

**Version:** 1.0.0  
**Scope:** Mobile-first Flutter application  
**Project:** GoMate / WanderAI — nền tảng du lịch thông minh dựa trên AI Agent, hệ thống gợi ý và kết nối bạn đồng hành  
**Basis:** Đề cương đồ án của TS. Nguyễn Tất Thắng + trạng thái UI/architecture hiện tại của GoMate  
**Status:** Design baseline for implementation

> **Lưu ý:** Phần yêu cầu lõi dưới đây được bám theo đề cương: AI itinerary agent có ràng buộc; hybrid recommendation; travel-buddy matching; profile/place/trip/review/preferences; safety check-in/SOS mô phỏng; Map/POI; social/booking chỉ ở mức tối thiểu. Các màu sắc, layout, component và micro-interaction là **đề xuất thiết kế UX của nhóm**, không phải yêu cầu bắt buộc từ đề cương.

---

# 1. Product UX Direction

## 1.1 Product promise

GoMate phải cho người dùng cảm giác:

> **“Tôi nói mình muốn chuyến đi như thế nào; GoMate hiểu bối cảnh, tìm địa điểm phù hợp, lập kế hoạch, gợi ý và giúp tôi tìm người đồng hành an toàn.”**

## 1.2 UX principles

### P1 — AI-first, not AI-only
AI là lớp hỗ trợ quyết định. Người dùng luôn có quyền xem, sửa, xác nhận hoặc hủy.

### P2 — Context before recommendation
Mọi recommendation quan trọng nên tận dụng context khi có: điểm đến, ngày, ngân sách, travel style, interests và lịch sử.

### P3 — Evidence before confidence
Không hiển thị rating/review/fact khi nguồn không có. Dữ liệu chưa xác minh phải được ẩn khỏi luồng người dùng mặc định.

### P4 — Explain before persuade
Recommendation và AI plan nên giải thích ngắn gọn “vì sao” thay vì chỉ đưa kết quả.

### P5 — Progressive disclosure
Màn hình đầu cho biết điều quan trọng; chi tiết sâu hơn mở khi người dùng cần.

### P6 — Safety is visible but calm
Safety không làm trải nghiệm du lịch trở nên đáng sợ; trạng thái nên rõ, thao tác SOS nổi bật nhưng không gây nhầm lẫn.

### P7 — Reversible actions
Delete, apply AI plan, match request và các hành động quan trọng phải có confirmation/undo phù hợp.

### P8 — Consistency over decoration
Mọi màn hình dùng cùng design tokens, spacing, button hierarchy, card shape, typography và state patterns.

---

# 2. Information Architecture

## 2.1 Main navigation — 5 tabs

| Tab | Tên hiển thị | Mục đích |
|---|---|---|
| 1 | **Trang chủ** | Context, quick actions, khám phá nhanh |
| 2 | **Bản đồ** | POI, nearby, search, category |
| 3 | **Wandy AI** | Chat + AI assistance |
| 4 | **Chuyến đi** | Trips, itinerary, AI planner |
| 5 | **Cá nhân** | Profile, preferences, safety, settings |

## 2.2 Core navigation graph

```text
Splash
  ↓
Onboarding (first launch only)
  ↓
Login / Register
  ↓
Home
 ├── Map
 │    ├── Search
 │    ├── Marker Preview
 │    └── Place Detail
 │          └── Add to Trip
 ├── Wandy AI
 │    ├── Chat
 │    └── Open/Generate Trip
 ├── Trips
 │    ├── Create Trip
 │    ├── Trip Detail
 │    │    ├── AI Planner Preview
 │    │    └── Add/Edit Itinerary
 │    └── Trip History
 └── Profile
      ├── Edit Profile
      ├── Travel Preferences
      ├── Buddy Matching
      ├── Safety Center
      └── Settings
```

## 2.3 Deep-link routes

```text
/login
/register
/
/map
/places/:id
/ai
/trips
/trips/new
/trips/:id
/trips/:id/plan-preview
/buddy
/buddy/:id
/match-requests
/safety
/profile
/profile/preferences
/settings
/reviews/new
```

---

# 3. Design Tokens

## 3.1 Color system

> Đây là proposal visual baseline; có thể điều chỉnh theo brand/logo sau khi chốt mockup.

### Brand

- **Primary:** `#0F766E` — teal, dùng cho CTA, active state, AI/Wandy identity.
- **Primary container:** `#CCFBF1`
- **On primary:** `#FFFFFF`

### Semantic

- **Success:** `#15803D`
- **Success container:** `#DCFCE7`
- **Warning:** `#B45309`
- **Warning container:** `#FEF3C7`
- **Error:** `#B91C1C`
- **Error container:** `#FEE2E2`
- **Info:** `#2563EB`
- **Info container:** `#DBEAFE`

### Neutral

- **Background:** `#F8FAFC`
- **Surface:** `#FFFFFF`
- **Surface elevated:** `#FFFFFF`
- **Text primary:** `#0F172A`
- **Text secondary:** `#475569`
- **Text tertiary:** `#64748B`
- **Border:** `#E2E8F0`
- **Divider:** `#E2E8F0`
- **Disabled:** `#94A3B8`

## 3.2 Category colors

Use category color only as a secondary semantic cue; never rely on color alone.

| Category | Label | Icon | Color role |
|---|---|---|---|
| attraction | Tham quan | `place` | Purple |
| culture | Văn hóa | `account_balance` / `museum` | Indigo |
| nature | Thiên nhiên | `park` | Green |
| beach | Biển | `beach_access` | Blue |
| cafe | Cà phê | `local_cafe` | Brown |
| restaurant | Ẩm thực | `restaurant` | Orange |
| hotel | Lưu trú | `hotel` | Teal |
| entertainment | Giải trí | `celebration` | Pink |

## 3.3 Typography

Use a Vietnamese-capable sans-serif font. Preferred visual hierarchy:

| Token | Size | Weight | Use |
|---|---:|---:|---|
| Display | 30 | 700 | hero only |
| H1 | 24 | 700 | screen title |
| H2 | 20 | 700 | section title |
| H3 | 18 | 600 | card/section |
| Body L | 16 | 400 | primary reading |
| Body M | 14 | 400 | normal supporting text |
| Body S | 13 | 400 | metadata |
| Label | 12 | 600 | chips, badges |
| Button | 14 | 600 | CTA |

**Vietnamese text rule:** luôn sử dụng Unicode có dấu; không dùng chuỗi không dấu trong production UI.

## 3.4 Spacing

Base unit = **4 px**.

```text
4   xs
8   sm
12  md-small
16  md
20  lg-small
24  lg
32  xl
40  2xl
48  3xl
```

Default mobile horizontal padding: **16 px**.

## 3.5 Radius

- Small control: 8 px
- Card: 16 px
- Large hero: 20 px
- Bottom sheet top corners: 24 px
- Pill: 999 px

## 3.6 Elevation

Use elevation sparingly.

- Level 0: flat surface
- Level 1: cards
- Level 2: floating action / selected preview
- Level 3: modal/bottom sheet

---

# 4. Global Components

## 4.1 AppBar

### Standard

```text
[←]  Screen title                         [action]
```

### Rules
- Title maximum 1 line.
- Back navigation only when there is a valid parent.
- Avoid multiple competing actions.

## 4.2 Primary button

```text
┌──────────────────────────────┐
│       Lập lịch trình bằng AI │
└──────────────────────────────┘
```

Use for the single most important action.

## 4.3 Secondary button

Outlined/tonal button for alternatives.

## 4.4 AI button

Use sparkle/star icon + Wandy identity, but do not overuse gradients.

## 4.5 Chips

Three variants:

- Filter chip
- Selection chip
- Status chip

Never make a chip behave like a navigation button unless clearly indicated.

## 4.6 Place card

```text
┌───────────────────────────┐
│         IMAGE             │
│                    ✓      │
├───────────────────────────┤
│ Tên địa điểm              │
│ Category · Hà Nội         │
│ Chưa có đánh giá          │
└───────────────────────────┘
```

## 4.7 Verified badge

```text
✓ Đã xác minh
```

Must mean the underlying provenance condition was actually satisfied.

## 4.8 Rating component

States:

- Real rating → show stars + numeric value.
- No rating → `Chưa có đánh giá`.
- Never show fabricated default 4.5/0.

## 4.9 Loading

Prefer skeletons for content screens; circular progress only for short actions.

## 4.10 Error state

```text
Không thể tải dữ liệu
Kiểm tra kết nối và thử lại.
[ Thử lại ]
```

Avoid technical stack traces in UI.

## 4.11 Empty state

```text
[illustration]
Chưa có chuyến đi
Tạo chuyến đi đầu tiên để Wandy giúp bạn lập lịch.
[ Tạo chuyến đi ]
```

## 4.12 Toast/snackbar

Use for low-risk confirmation, not critical decisions.

---

# 5. Global UX States

Every data-driven screen must define:

```text
Initial
Loading
Success
Empty
Error
Refreshing
Offline/timeout where relevant
```

Every AI-driven screen must also define:

```text
Thinking
Generating
Generated
Invalid output
Provider unavailable
Timeout
Retry
```

---

# 6. Screen Specifications

# 6.1 Splash Screen

**Purpose:** bootstrap app and restore auth/session.

**Components:** Logo, minimal loading indicator.

**Behavior:**

```text
Start
 ↓
Restore auth
 ↓
Authenticated → Home
Unauthenticated → Login
```

**Acceptance:** no visible blank white screen while session initializes.

---

# 6.2 Onboarding

**Purpose:** explain value proposition in 2–3 screens.

### Slide 1
**Lên chuyến đi thông minh**
Wandy giúp bạn biến sở thích và ngân sách thành lịch trình.

### Slide 2
**Khám phá đúng nơi**
Tìm địa điểm theo vị trí, sở thích và ngữ cảnh.

### Slide 3
**Đi cùng người phù hợp**
Tìm bạn đồng hành dựa trên chuyến đi và sở thích, với consent rõ ràng.

CTA: `Bắt đầu`

Skip available.

---

# 6.3 Login

```text
WanderAI / GoMate
Đăng nhập

[ Email ]
[ Mật khẩu ]

[ Đăng nhập ]

Chưa có tài khoản? Đăng ký
```

States: validation, loading, invalid credentials, network error.

Do not expose auth details from backend.

---

# 6.4 Register

Fields:

- Họ tên
- Email
- Mật khẩu
- Xác nhận mật khẩu

CTA: `Tạo tài khoản`

After success → authenticated → Home.

---

# 6.5 Home Screen

**Purpose:** contextual dashboard, not generic destination gallery.

### Header

```text
Xin chào, Nam 👋
Bạn muốn đi đâu hôm nay?
```

### Search

`Tìm địa điểm, thành phố...`

### Wandy CTA

```text
┌────────────────────────────────┐
│ ✨ Wandy AI                    │
│ “Bạn nói mục tiêu, mình lo plan”│
│ [ Lập kế hoạch ]               │
└────────────────────────────────┘
```

### Quick actions

- Khám phá gần đây
- Tạo chuyến đi
- Gợi ý cho tôi
- Tìm bạn đồng hành

### Recommended section

Horizontal cards, 2–3 visible.

### UX rules

- Avoid huge empty hero area.
- Images must be real/licensed or clearly marked placeholder during development.
- No fabricated rating.

---

# 6.6 Explore/Search Screen

**Purpose:** text-first discovery.

Components:

- Search field
- Recent searches
- Category chips
- Sort/filter
- Place list/grid

Filters:

```text
Category
Distance
Open now (only when data exists)
Rating (only where rating exists)
```

Search results must state count and loading state.

---

# 6.7 Map Screen

**Purpose:** spatial discovery.

Layout:

```text
┌──────────────────────────────┐
│ 🔎 Tìm địa điểm...           │
├──────────────────────────────┤
│ Tất cả Văn hóa Thiên nhiên…  │
├──────────────────────────────┤
│                              │
│            MAP               │
│       📍     📍              │
│            📍                │
│                              │
│                 ◎ location   │
├──────────────────────────────┤
│ 24 địa điểm                  │
└──────────────────────────────┘
```

### Interactions

- Tap marker → preview sheet.
- Search → recenter to results.
- Category filter → update markers.
- Radius → 1/5/10/25 km.
- Location button → current position or safe fallback.

### Important

- Tile provider and place data are separate concerns.
- Keep OSM attribution visible when OSM data/tiles are used.
- Verified markers come from `verifiedOnly=true` path.

---

# 6.8 Place Preview Sheet

**Purpose:** quick decision without leaving map.

```text
┌──────────────────────────────┐
│     drag handle              │
│ Lăng Chủ tịch Hồ Chí Minh   │
│ Văn hóa · ✓ Đã xác minh     │
│ Chưa có đánh giá             │
│ 1.2 km                       │
│                              │
│ [ Xem chi tiết ]             │
│ [ Thêm vào chuyến đi ]       │
└──────────────────────────────┘
```

When category changes, the sheet must either update to the new selection or close predictably; it must not preserve stale content.

---

# 6.9 Place Detail

**Purpose:** authoritative place view and aggregation point for future review/recommendation.

### Sections

1. Hero image (licensed/available)
2. Name
3. Category + verified badge
4. Address
5. Rating state
6. Opening hours when sourced
7. Contact/website when sourced
8. Location map
9. AI/RAG summary where evidence exists
10. Reviews
11. Actions

### Primary actions

```text
[ Thêm vào chuyến đi ]
[ Chỉ đường ]
[ Lưu ]
```

### No-data behavior

- No rating → `Chưa có đánh giá`
- No reviews → `Chưa có review được xác minh`
- No hours → do not invent hours
- No image → clean placeholder, not fake photo

---

# 6.10 AI Chat / Wandy

**Purpose:** general travel assistant.

### Header

```text
✨ Wandy
AI Travel Copilot
```

### Welcome

```text
Chào bạn 👋
Bạn đang muốn tìm hiểu hay lên kế hoạch cho chuyến đi nào?
```

### Quick prompts

- Gợi ý 3 điểm ở Đà Nẵng
- Tôi có 5 triệu, đi đâu 3 ngày?
- Lên lịch trình cho tôi
- Tìm địa điểm gần đây

### Message layout

User bubble right; Wandy bubble left.

### AI response extras

When available:

```text
Nguồn
• Wikivoyage
• OpenStreetMap
```

Future:

```text
[ Xem địa điểm ]
[ Thêm vào chuyến đi ]
```

### Error

```text
Wandy chưa thể trả lời lúc này.
[ Thử lại ]
```

---

# 6.11 Trip List

Header:

```text
Chuyến đi                         [+]
```

Cards show:

- Title
- Destination
- Dates
- Budget
- Status
- AI-generated badge when true

Empty state → create trip CTA.

---

# 6.12 Create Trip

### Fields

Required/minimum context:

- Tên chuyến đi
- Điểm đến
- Ngày bắt đầu
- Ngày kết thúc

Optional/high-value context:

- Ngân sách
- Currency
- Travel style
- Interests

### Form UX

Use sections:

```text
Thông tin chuyến đi
Lịch trình
Ngân sách
Sở thích
```

CTA sticky bottom:

`Tạo chuyến đi`

---

# 6.13 Edit Trip

Same structure as Create Trip.

Danger zone at bottom:

`Xóa chuyến đi`

with confirmation.

---

# 6.14 Trip Detail

### Header

```text
<  Chuyến đi Đà Nẵng        ⋯
```

### Overview card

```text
12 → 15 Nov
5.000.000 VND
COMFORT
Food · Beach
```

### Primary AI action

```text
✨ Lập lịch trình bằng AI
```

### Itinerary

Day tabs:

`Ngày 1 | Ngày 2 | Ngày 3`

Timeline:

```text
08:30
Mì Quảng

10:00
Check-in

14:30
Chùa Linh Ứng
```

### Actions

- Add activity
- Edit trip
- Generate AI plan
- Safety mode

---

# 6.15 AI Planner Prompt/Context Dialog

Purpose: gather optional user instruction without replacing authoritative TripContext.

Example:

```text
Bạn muốn Wandy ưu tiên điều gì?

☑ Ẩm thực
☑ Biển
☐ Chụp ảnh
☐ Nghỉ dưỡng

Ghi chú thêm
[........................]

[ Tiếp tục ]
```

Must never allow this free text to bypass trip ownership/validation.

---

# 6.16 AI Planner Preview

**This is a critical screen.**

```text
✨ Lịch trình do Wandy đề xuất

3 ngày · 18 hoạt động

Ngân sách
1.960.000 / 5.000.000 VND

✓ Trong ngân sách

────────────────
NGÀY 1
08:30 Mì Quảng
10:00 ...

────────────────
NGÀY 2
...

[ Hủy ]   [ Áp dụng vào chuyến đi ]
```

### Required states

- Generated
- Over budget
- Existing itinerary warning
- AI unavailable
- Invalid response
- Timeout

### Critical rule

`Generate` = preview only.  
`Apply` = persistent change after explicit confirmation.

---

# 6.17 Itinerary Item Editor

Fields:

- Time
- Activity/place
- Notes
- Estimated cost
- Duration if supported

Validation:

- Valid day
- Valid time
- Non-negative cost

---

# 6.18 Recommendation Home

**Purpose:** main research/product surface for hybrid recommendation.

Header:

```text
Gợi ý cho bạn
```

Context explanation:

```text
Dựa trên:
• Đà Nẵng
• 3 ngày
• Ngân sách 5 triệu
• Bạn thích Food + Beach
```

### Recommendation card

```text
┌──────────────────────────────┐
│ Địa điểm                     │
│ ★ Recommended                │
│                              │
│ Phù hợp với bạn vì           │
│ ✓ cùng sở thích              │
│ ✓ phù hợp ngân sách          │
│ ✓ gần lịch trình             │
│                              │
│ [ Xem chi tiết ]             │
└──────────────────────────────┘
```

Avoid presenting a numeric “match percentage” unless the algorithm and meaning are explicitly defined. Prefer `Mức độ phù hợp` or `Phù hợp vì...` in MVP UI.

---

# 6.19 Recommendation Detail / Why Recommended

Sections:

1. Place
2. Recommendation reasons
3. Context matched
4. Similar alternatives
5. Actions

Example:

```text
Vì sao được gợi ý?
✓ Cùng nhóm sở thích: Ẩm thực
✓ Phù hợp khu vực Đà Nẵng
✓ Phù hợp ngân sách
```

This screen is particularly useful for explainability and thesis demo.

---

# 6.20 Travel Preferences

Fields should map directly to recommendation/matching context.

```text
Sở thích
☑ Food
☑ Beach
☐ Nature
☐ Culture

Phong cách
○ Budget
○ Comfort
○ Luxury

Nhịp độ
○ Thư thả
○ Cân bằng
○ Dày lịch trình
```

No sensitive attributes.

---

# 6.21 Buddy Discovery

Header:

```text
Tìm bạn đồng hành
```

Context:

```text
Chuyến đi: Đà Nẵng
12–15 Nov
```

Candidate cards:

```text
Người dùng A
Đà Nẵng · Food · Beach
Phù hợp với chuyến đi

[ Xem hồ sơ ]
[ Gửi lời mời ]
```

Do not expose unnecessary personal information.

---

# 6.22 Buddy Profile

Show only information necessary for matching:

- Display name
- Trip context
- Travel style
- Interests
- Availability window where applicable
- Match explanations

Never infer or expose sensitive attributes.

---

# 6.23 Match Request / Consent

```text
Bạn muốn gửi lời mời đồng hành?

Chuyến đi
Đà Nẵng · 12–15 Nov

Thông tin chia sẻ:
☑ Điểm đến
☑ Khoảng thời gian
☑ Sở thích du lịch

[ Hủy ] [ Gửi lời mời ]
```

Receiving side:

```text
[ Chấp nhận ] [ Từ chối ]
```

Match is established only after required consent.

---

# 6.24 Match Result

```text
Đã kết nối

Hai bạn có nhiều điểm phù hợp cho chuyến đi này.

[ Xem chuyến đi ]
[ Trò chuyện ]
```

Minimal social/chat only, consistent with thesis scope.

---

# 6.25 Safety Center

```text
🛡️ An toàn chuyến đi

Safety Mode
○ Tắt

Chuyến đi hiện tại
Đà Nẵng · 12–15 Nov

[ Bật Safety Mode ]
```

Secondary:

- Emergency contact
- Check-in settings
- Safety tips

---

# 6.26 Safety Check-in

When active:

```text
Safety Mode đang bật

Lần check-in tiếp theo
18:30

[ Tôi an toàn ]
```

Missed check-in:

```text
Bạn chưa check-in.
Bạn có ổn không?

[ Tôi an toàn ]
[ Xem SOS ]
```

---

# 6.27 SOS Mock

Clearly mark:

```text
SOS MÔ PHỎNG
```

No fake claims about contacting emergency responders unless a real integration exists.

Flow:

```text
SOS
 ↓
Confirmation
 ↓
Show simulated emergency action
 ↓
Log event
```

---

# 6.28 Review Composer

```text
Đánh giá địa điểm

★★★★☆

Bạn muốn chia sẻ điều gì?
[...............................]

[ Đăng đánh giá ]
```

If review AI is not yet available, do not show fake analysis.

---

# 6.29 Review Intelligence

Future screen after licensed review data / native reviews are available.

Sections:

```text
Tổng quan cảm nhận

Điểm tích cực
• Cleanliness
• Service

Điểm cần lưu ý
• Price

Aspect sentiment
████████ Positive
████ Negative
```

Research data and first-party reviews must remain distinguishable in backend/UI.

---

# 6.30 Profile

```text
Xin chào, Nam

[ Ảnh ]
Nam
email@example.com

Hồ sơ du lịch
Sở thích
Chuyến đi
Bạn đồng hành

Cài đặt
Đăng xuất
```

---

# 6.31 Settings

Sections:

- Account
- Notification
- Privacy
- Data & permissions
- AI preferences
- About / licenses

Include a data-source/attribution page for open-data sources used in the app.

---

# 7. UX Flows — Critical Business Journeys

# 7.1 New traveler journey

```text
Onboarding
 ↓
Register
 ↓
Profile basics
 ↓
Preferences
 ↓
Home
 ↓
Explore / Recommendation
```

## 7.2 AI trip planning journey

```text
Home / Trips
 ↓
Create Trip
 ↓
Set destination/date/budget/style/interests
 ↓
Trip Detail
 ↓
Lập lịch trình bằng AI
 ↓
Optional prompt
 ↓
Authoritative TripContext
 ↓
Wandy / Gemini
 ↓
Validation
 ↓
Preview
 ↓
User confirms
 ↓
Atomic save
 ↓
Itinerary
```

## 7.3 Discover place journey

```text
Home
 ↓
Map / Search
 ↓
Filter
 ↓
Marker
 ↓
Preview
 ↓
Place Detail
 ↓
Add to Trip
```

## 7.4 Recommendation journey

```text
User context
 ↓
Candidate generation
 ↓
Content signal
+
Collaborative signal
+
Popularity fallback
 ↓
Hybrid ranking
 ↓
Explain
 ↓
Place Detail
```

## 7.5 Buddy journey

```text
Trip/preferences
 ↓
Candidate filtering
 ↓
Compatibility scoring
 ↓
Candidate list
 ↓
View profile
 ↓
Send request
 ↓
Consent
 ↓
Match
```

## 7.6 Safety journey

```text
Trip
 ↓
Safety Center
 ↓
Enable Safety Mode
 ↓
Check-in
 ↓
Missed?
 ├── No → continue
 └── Yes → reminder
              ↓
         unresolved
              ↓
            SOS mock
```

---

# 8. UX Copy Standards

## 8.1 Language

Primary app language: **Vietnamese**.

Technical/source metadata can retain English where appropriate.

## 8.2 Good examples

Use:

- `Chưa có đánh giá`
- `Đã xác minh`
- `Lập lịch trình bằng AI`
- `Áp dụng vào chuyến đi`
- `Thử lại`
- `Tìm bạn đồng hành`
- `Gửi lời mời`
- `Tôi an toàn`

Avoid:

- `No rating`
- `AI Generate`
- `Apply`
- `Match 82%`

unless the wording is intentionally part of the finalized bilingual UX.

## 8.3 AI language

Do not imply certainty:

Bad:

> “Đây chắc chắn là lựa chọn tốt nhất.”

Preferred:

> “Mình gợi ý địa điểm này vì phù hợp với sở thích và ngân sách của bạn.”

---

# 9. Accessibility

Minimum requirements:

- Contrast ratio suitable for normal text.
- Tap targets ≥ 44×44 px where feasible.
- Do not rely solely on color to distinguish categories/status.
- Every icon-only action has semantic tooltip/label.
- Dynamic text should not clip critical content.
- Screen readers should receive meaningful labels.
- Errors should be announced near the affected field.

---

# 10. Responsive / Device Rules

## Mobile baseline

Primary target: Flutter mobile portrait.

## Tablet / web

- Content max width for forms/cards.
- Map can become split-view:

```text
┌───────────────┬───────────────────┐
│ Search/List   │       Map         │
│               │                   │
│ Place cards   │ markers           │
└───────────────┴───────────────────┘
```

## Keyboard

Forms and chat must avoid keyboard covering active controls.

---

# 11. Data/UX Integrity Rules

These are mandatory for implementation.

### DUX-01
Never display unverified places in normal user-facing discovery unless explicitly enabled for development/testing.

### DUX-02
Never invent rating.

### DUX-03
Never invent review content.

### DUX-04
Never claim a source is OSM/Wikivoyage/etc. unless provenance exists.

### DUX-05
AI-generated itinerary is a proposal until user confirms.

### DUX-06
Safety UI must label simulation where appropriate.

### DUX-07
Matching cannot use sensitive inferred attributes.

### DUX-08
Recommendation explanation must correspond to actual model/context signals.

---

# 12. Component State Matrix

| Component | Normal | Loading | Empty | Error | Disabled |
|---|---|---|---|---|---|
| Place Card | data | skeleton | n/a | fallback | muted |
| Rating | stars/value | skeleton | Chưa có đánh giá | hide | muted |
| Map | markers | map loader | Không có địa điểm | retry | controls disabled |
| AI Chat | messages | typing | welcome | retry | input disabled |
| AI Planner | generate | generating | n/a | retry | button disabled |
| Trip List | cards | skeleton | create CTA | retry | n/a |
| Recommendation | ranked cards | skeleton | broader suggestions | retry | n/a |
| Buddy List | candidates | skeleton | no compatible candidates | retry | invite disabled |
| Safety | status | enabling | setup CTA | retry | mock state |

---

# 13. Design-to-Code Rules for Antigravity

## 13.1 Folder convention

```text
lib/
├── core/
│   ├── theme/
│   ├── constants/
│   ├── router/
│   └── widgets/
├── features/
│   ├── auth/
│   ├── home/
│   ├── map/
│   ├── places/
│   ├── ai_chat/
│   ├── trips/
│   ├── recommendations/
│   ├── buddy/
│   ├── safety/
│   ├── reviews/
│   └── profile/
```

## 13.2 Reusable components

Centralize:

```text
AppButton
AppTextField
AppCard
AppChip
AppSectionHeader
VerifiedBadge
RatingView
AsyncStateView
EmptyState
ErrorState
```

Do not recreate one-off versions in each screen.

## 13.3 Theme

One `ThemeData` / design token source.

No hard-coded ad-hoc colors throughout feature screens.

## 13.4 API/UX contract

Every screen spec should map to:

```text
Screen
 ↓
State
 ↓
Repository
 ↓
API
 ↓
Model
```

No API calls directly from deeply nested presentation widgets.

---

# 14. Traceability Matrix

| UX / Screen | Core thesis relation | Main backend/data |
|---|---|---|
| Home | entry/context | destinations/recommendation |
| Map | POI foundation | PostGIS/OSM |
| Place Detail | place context | places/place_sources |
| Wandy Chat | AI Agent | NestJS → FastAPI → Gemini/RAG |
| Trip Detail | itinerary workspace | trips/itinerary |
| AI Planner Preview | AI Agent | TripContext/planner |
| Recommendation | recommender | content/CF/popularity |
| Buddy Discovery | matching | preferences/trip context |
| Consent | privacy | match request/consent |
| Safety Center | safety MVP | check-in/SOS simulation |
| Review | review data | native/licensed review data |
| Review Intelligence | research extension | ABSA/review pipeline |
| Profile | preference vectors | user/profile/preferences |

---

# 15. MVP vs Future

## Must-have for thesis core

```text
Auth
Profile/preferences
Place discovery
Map
Trip CRUD
AI itinerary agent
Recommendation
Travel buddy matching
Consent
Safety check-in/SOS mock
Evaluation surfaces
```

## Supporting

```text
RAG
Review Intelligence
Place Detail
Weather
Route
```

## Minimal / stretch

```text
Social feed
Booking redirect/mock
```

This follows the thesis scope that social/booking are minimal-support modules rather than full social network/OTA products.

---

# 16. Implementation Priority

## Phase UI-1 — Foundation

1. Design tokens
2. Theme
3. Global components
4. Navigation shell
5. Splash/Login/Register

## Phase UI-2 — Current working flows

6. Home
7. Map
8. Place Preview
9. Place Detail
10. AI Chat
11. Trips
12. Trip Detail
13. Planner Preview

## Phase UI-3 — Thesis core

14. Recommendation
15. Recommendation explanation
16. Preferences
17. Buddy Discovery
18. Buddy Profile
19. Consent
20. Match Result

## Phase UI-4 — Supporting

21. Safety Center
22. Check-in
23. SOS mock
24. Reviews
25. Review Intelligence

## Phase UI-5 — Polish

26. Profile
27. Settings
28. Empty/error/loading states
29. Accessibility
30. Visual regression screenshots

---

# 17. Acceptance Criteria for Visual QA

A screen is considered visually complete only when:

- [ ] Correct design tokens are used.
- [ ] Vietnamese text has correct diacritics.
- [ ] No unnecessary large empty area.
- [ ] Loading/empty/error states exist.
- [ ] Primary CTA is obvious.
- [ ] Tap targets are usable.
- [ ] No text clipping/overflow.
- [ ] No fake rating/review/data.
- [ ] Verified badge corresponds to real provenance.
- [ ] Navigation back/forward is predictable.
- [ ] Screen works with real backend data.
- [ ] Screenshot reviewed manually.

---

# 18. Visual QA Checklist for Current GoMate

## Home

- [ ] Replace placeholder hero imagery when a licensed source is available.
- [ ] Reduce excessive whitespace.
- [ ] Add clear Wandy CTA.
- [ ] Add contextual recommendation block.

## Map

- [ ] Fix basemap/tile rendering on the user's actual Chrome/network.
- [ ] Keep 357 verified OSM places as data source.
- [ ] Use Vietnamese category labels.
- [ ] Close/update preview correctly when filter changes.
- [ ] Investigate duplicate GlobalKey console error.

## AI Chat

- [ ] Improve message hierarchy.
- [ ] Improve loading/typing state.
- [ ] Add source citation UI after RAG is stable.
- [ ] Add contextual action buttons later.

## Trips

- [ ] Improve trip card hierarchy.
- [ ] Keep AI-generated state visible but subtle.
- [ ] Highlight primary AI planner CTA.

## Place Detail

- [ ] Introduce as the single canonical place presentation surface.
- [ ] Reuse same rating/provenance rules everywhere.

---

# 19. Definition of Design Done

The GoMate UI/UX baseline is complete when:

1. All primary screens share one visual system.
2. Core flows are navigable end-to-end.
3. Each screen defines success/loading/empty/error states.
4. AI flows clearly distinguish generated proposals from saved user data.
5. Recommendation and matching surfaces explain their context.
6. Safety interactions clearly distinguish simulation from real emergency integration.
7. Unverified/synthetic data is never presented as verified real-world information.
8. Mobile layout has been manually reviewed in Chrome/device.
9. Critical flows have screenshots as evidence.
10. Implementation is traced to requirements/use cases and backend contracts.

---

# 20. Implementation Note

This document is the **UX source of truth**, not a replacement for backend/API contracts or the formal thesis requirements specification.

Recommended sequence:

```text
Design System
    ↓
Screen/UX Spec
    ↓
Use Case / FR / NFR
    ↓
API Contract
    ↓
Flutter implementation
    ↓
Automated tests
    ↓
Manual visual QA
    ↓
Screenshot evidence
```

---

# 21. Thesis Alignment

The design is intentionally centered on the three capabilities highlighted in the supervisor's outline:

```text
AI Agent / itinerary
        +
Hybrid Recommendation
        +
Travel Buddy Matching
```

The supervisor's outline also calls for profile, places, trips, reviews and preference vectors; constraint-aware itineraries; matching with privacy/consent; safety check-in/SOS simulation; quantitative evaluation; and a small user study. The UI therefore treats those capabilities as first-class product flows rather than isolated screens.

---

# 22. Next Design Revision

After implementation of this v1 baseline, the next revision should be based on actual screenshots and browser/device testing, not abstract preference alone.

Priority review order:

```text
Home
→ Map
→ Place Detail
→ Wandy AI
→ Trip Detail
→ AI Planner
→ Recommendation
→ Buddy
→ Safety
```
