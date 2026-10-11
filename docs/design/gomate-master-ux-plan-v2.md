# GoMate — Master Product, UX & UI Plan v2.0

Date: 2026-10-04
Product: GoMate (WanderAI)
Status: Design foundation / implementation roadmap

## 1. Product Vision

GoMate is a Vietnamese travel companion that helps users discover places, understand verified place information, build trips, navigate, and delegate multi-step travel tasks to Wandy safely.

Brand personality:
- Warm
- Trustworthy
- Modern
- Local/Vietnamese
- Calm
- Practical
- Intelligent without being intimidating

Design direction:
- Bright, airy, low-cognitive-load interfaces.
- Subtle Vietnamese visual references rather than literal traditional decoration.
- Soft teal as the primary brand color, with restrained terracotta/warm-sand accents.
- Large readable typography, generous spacing, rounded surfaces, clear hierarchy.

## 2. Experience Principles

1. One primary action per screen region.
2. Information before decoration.
3. Never fabricate data.
4. Never hide important state changes.
5. AI proposes before it acts when a side effect exists.
6. Location quality is explicit, not implied.
7. Mobile first, tablet adaptive, desktop re-composed rather than merely stretched.
8. Every data screen supports loading, success, empty, partial, error, permission, and offline states.
9. Source attribution is visible when data is grounded by external sources.
10. Reusable components and tokens only; no screen-level visual constants.

## 3. Information Architecture

Primary navigation:
- Khám phá
- Bản đồ
- Wandy
- Chuyến đi
- An toàn

Secondary:
- Tìm kiếm
- Địa điểm
- Điểm đến
- Nhắc nhở
- Hồ sơ
- Cài đặt
- Thông báo

Wandy capability graph:
- Search place
- Search nearby
- Place details
- Location
- Trip creation
- Trip planning
- Navigation handoff
- Scheduling
- Safety
- Recommendation

## 4. Screen Inventory

### Entry & account
01 Splash
02 Onboarding
03 Login
04 Register
05 Forgot password
06 Location permission education
07 Profile
08 Settings

### Discover
09 Home
10 Search
11 Search results
12 Destination detail

### Map & place
13 Map
14 Place preview
15 Place detail

### Wandy
16 Wandy landing
17 Wandy conversation
18 Agent action confirmation/result

### Trips
19 Trip list
20 Trip overview
21 AI itinerary preview
22 Itinerary item detail/edit

### Scheduling
23 Reminder list
24 Create reminder
25 Agent scheduling confirmation

### Safety
26 Safety home
27 Emergency / share location
28 Trusted contacts

### System/support
29 Notifications
30 Error / offline / permission surfaces

## 5. Canonical User Journeys

### Discover a place
Home → Search → Search results → Preview → Detail

### Nearby discovery
Home/Map → Location permission → Current location → Nearby places → Preview → Detail

### AI trip planning
Home → Wandy → intent → Trip draft → AI plan → Preview → Confirm → Trip

### Navigation
Preview/Detail → Chỉ đường → external map app/browser

### Scheduling
Trip/Wandy → Create reminder → Review → Confirm → Notification

### Safety
Trip → Safety → action → Confirm → execution → status

### Agent orchestration
User intent → Intent parse → Plan → Tool calls → Confirmation (when needed) → Execute → Result → Undo where possible

## 6. Design Tokens

### Core colors
Primary: #0F766E
Primary soft: #CCFBF1
Background: #F8FAFC
Warm surface: #FFFCF7
Surface: #FFFFFF
Text primary: #0F172A
Text secondary: #475569
Text tertiary: #94A3B8
Border: #E2E8F0
Terracotta accent: #C96B4B
Warm sand: #E8D8C3

### Semantic
Success: #15803D
Warning: #B45309
Error: #B91C1C
Info: #2563EB

### Typography
Plus Jakarta Sans
Display 32/700
H1 28/700
H2 22/700
H3 18/600
Body L 16/400
Body M 14/400
Body S 13/400
Label 12/600
Button 14/600

### Spacing
4, 8, 12, 16, 20, 24, 32, 40, 48

### Radius
8, 12, 16, 20, 24, 999

### Elevation
Prefer borders and surface contrast. Use low-elevation shadows only for floating surfaces and bottom sheets.

## 7. Responsive Layout Rules

Mobile <720px
- Bottom navigation.
- Full-width content with 16px horizontal padding.
- Bottom sheets for contextual actions.

Tablet 720–1199px
- Navigation rail.
- Centered content column.
- Split panels when a second pane improves task completion.

Desktop ≥1200px
- Persistent sidebar.
- Max readable content width 720–900px depending on task.
- Map uses a larger working area with supporting detail/preview pane.
- Never stretch mobile cards across the viewport.

## 8. Component Library

AppButton
AppIconButton
AppCard
AppChip
AppTag
AppBadge
AppSearchBar
AppTextField
AppBottomSheet
AppTabs
AppSegmentedControl
AppDivider
AppLoading
AppSkeleton
AppEmptyState
AppErrorState
AppPermissionState
RatingView
DistanceView
VerifiedBadge
SourceCitation
LocationAccuracyBadge
PlaceCard
PlaceListTile
TripCard
ItineraryCard
AgentActionCard
ConfirmationSheet
ReminderCard
NotificationCard

## 9. State Model

Every data-driven screen:
- Initial
- Loading
- Loaded
- Empty
- Partial data
- Error
- Retry
- Offline
- Permission denied
- Unauthorized

Location-specific:
- Unknown
- Requesting
- Granted / good
- Granted / approximate
- Granted / poor
- Denied
- Service disabled
- Unavailable

## 10. Location UX Rules

- Do not prompt merely by opening Map.
- Ask for permission from a visible user action.
- Show accuracy quality when available.
- Distinguish location fix from map camera state.
- Never silently replace the user's map view because a fix changed.
- Distance shown in UI must be based on the current user fix.
- When location is unavailable, show a neutral explicit state instead of a fake distance.
- Use accuracy circle when meaningful.

## 11. Place UX Rules

Verified place:
- Show verified badge.
- Show factual OSM-derived metadata only.
- Show source and license attribution.

Unverified place:
- No verification badge.
- No source claim.
- No descriptive facts that are not provenance-backed.

Ratings:
- Real trusted rating only.
- Otherwise: “Chưa có đánh giá”.

Address:
- Only OSM addr:* / approved backend factual fields.
- Otherwise: “Chưa có thông tin địa chỉ.”

## 12. Wandy / Agent UX Rules

Wandy is a travel copilot, not a generic chatbot.

Conversation blocks:
- User message
- Assistant answer
- Source citations
- Suggested next actions
- Tool result cards
- Confirmation cards

Read-only actions can execute automatically when safe.
Side-effecting actions require confirmation.
High-impact actions always require explicit confirmation.

Agent action lifecycle:
Intent → Plan → Preview → Confirm → Execute → Result → Undo (when possible)

Examples requiring confirmation:
- Apply itinerary
- Create reminder
- Delete trip data
- Share location
- Book/commit an external transaction
- Emergency actions

## 13. Safety UX

Safety must be calm and obvious.

Primary information:
- Current sharing state
- Trusted contacts
- Trip sharing
- Emergency actions
- Location quality

Never make emergency actions difficult to reach, but never trigger them accidentally.

## 14. Motion

Motion exists to preserve orientation and provide feedback.

Default durations:
- Micro feedback: 120ms
- Standard control transition: 180ms
- Sheet transition: 280–320ms
- Navigation transition: 220–260ms

Avoid decorative animation loops.

## 15. Accessibility

- Minimum touch target 44×44 logical px.
- Full keyboard navigation on web/desktop.
- Semantic labels for map controls and agent actions.
- Do not encode meaning by color alone.
- Support text scaling.
- Preserve readable contrast.
- Focus order follows visual/task hierarchy.

## 16. Documentation Package

Create and maintain:
- docs/design/gomate-brand-guidelines.md
- docs/design/gomate-design-system-v2.md
- docs/design/gomate-components.md
- docs/design/gomate-screen-spec-v2.md
- docs/design/gomate-ux-flows-v2.md
- docs/design/gomate-agent-ux-v1.md
- docs/design/gomate-content-guidelines.md
- docs/architecture/ui-architecture-v2.md
- docs/architecture/navigation-architecture.md
- docs/architecture/location-architecture.md
- docs/architecture/agent-architecture.md
- docs/architecture/scheduling-architecture.md
- docs/architecture/safety-architecture.md

## 17. Implementation Order

Phase 0 — Baseline and branch hygiene
Phase 1 — Product/UX specification
Phase 2 — Design system v2
Phase 3 — App shell and navigation
Phase 4 — Home / Discover
Phase 5 — Search
Phase 6 — Map + Location
Phase 7 — Place Preview + Place Detail
Phase 8 — Wandy
Phase 9 — Trips
Phase 10 — AI Planner UX
Phase 11 — Scheduling
Phase 12 — Safety
Phase 13 — Agent foundation
Phase 14 — Agent tools
Phase 15 — Recommendation
Phase 16 — Profile / Settings / Notifications
Phase 17 — Responsive desktop
Phase 18 — Accessibility and motion audit
Phase 19 — Full E2E / UX audit
Phase 20 — Thesis and release documentation

## 18. Definition of Done

A feature is done only when all apply:
1. Business logic verified.
2. API/data contract verified.
3. UI states implemented.
4. Edge cases tested.
5. Automated tests pass.
6. Browser/device flow verified where applicable.
7. Documentation updated.
8. Working tree clean.
9. Post-merge regression passes.
10. Remote branch is synchronized when the feature is released.

## 19. Immediate Sprint

Do not start the full UI rewrite yet.

Immediate sequence:
1. Close and release TASK 08.1.1 location hardening.
2. Freeze this product/design specification.
3. Build the screen-by-screen UX specification.
4. Implement UI-01 App Shell.
5. Implement UI-02 Home.
6. Implement UI-03 Search.
7. Implement UI-04 Map using the proven location state machine.
8. Re-run E2E and visual QA after each module.

This keeps business logic stable while the presentation layer is modernized systematically.
