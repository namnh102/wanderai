# GoMate Trip Management — Visual & UX Audit (TASK 08.2.3.5)

**Status:** APPROVED DESIGN & CAPABILITY AUDIT  
**Task:** TASK 08.2.3.5 — GOMATE TRIP MANAGEMENT VISUAL MOCKUP V1 + UX / BUSINESS FLOW DESIGN  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Branch:** `feature/gomate-visual-mockups`  
**Evidence Artifacts:** `docs/audit/evidence/ui-08.2.3.5/` (31 Mockup Files: 25 Mobile + 6 Desktop)  
**Strict Implementation Invariant:** Zero changes to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, database schema, or API contracts.  

---

## 1. Source Documents Reviewed

The visual mockups, UX flows, and capability audit for the Trip Management module were developed strictly aligned with the foundational architecture documents:
1. `docs/design/gomate-design-system-ux-spec-v1.md` (Deep Pine Teal `#0F766E`, Mint `#CCFBF1`, typography, responsive rules).
2. `docs/design/gomate-master-ux-plan-v2.md` (Trip management lifecycle, multi-modal travel discovery).
3. `docs/design/gomate-ux-architecture-v1.md` (Routing `/trips`, `/trips/create`, `/trips/:id`, bottom navigation 5 tabs).
4. `docs/design/gomate-information-architecture.md` (Trip entity relations: Places, Users, Itinerary, Items, Budget).
5. `docs/design/gomate-user-flows.md` (User journeys: Create trip, browse timeline, AI Planner generation).
6. `docs/design/gomate-screen-specification.md` & `gomate-screen-spec-v2.md` (Screen layouts and component sizing).
7. `docs/design/gomate-interaction-specification.md` (Bottom sheets, modals, touch targets $\ge 44 \times 44\text{dp}$).
8. `docs/design/gomate-responsive-specification.md` (Mobile $390\text{px}$, Tablet $768\text{px}$, Desktop $1440\text{px}$).
9. `docs/api/trips-api.md` & `docs/architecture/trip-flow.md` (Backend API contracts and data flows).
10. `docs/audit/ui/task-08.2.3.4-wandy-visual-audit.md` & `task-08.2.3.4-r1-wandy-visual-audit.md` (Precedent design standards).

---

## 2. Technical Codebase Audit

An exhaustive code audit of the current Trip Management implementation was conducted across the backend and frontend:

### 2.1. Backend Module (`apps/backend/src/modules/trips/`)
- **Controller (`trips.controller.ts`):**
  - `POST /trips`: Creates a trip entity (`CreateTripDto`).
  - `GET /trips`: Retrieves all trips for the authenticated user.
  - `GET /trips/:id`: Retrieves trip details with nested `itinerary`, `items`, and `members`.
  - `PATCH /trips/:id`: Updates trip metadata (title, dates, budget, travelStyle).
  - `DELETE /trips/:id`: Deletes trip and cascades associated itinerary records.
  - `POST /trips/:id/itinerary`: Adds an `ItineraryItem` (dayNumber, placeId, activity, startTime, endTime, estimatedCost, notes, transportMode).
  - `DELETE /trips/:id/itinerary/:itemId`: Deletes a single `ItineraryItem`.
  - `POST /trips/:id/ai-plan`: Calls AI Service to generate an itinerary preview. **Invariant Verified:** Does NOT write to the database; strictly read-only preview.
  - `POST /trips/:id/itinerary/bulk`: Atomically saves multiple itinerary items within a transaction; supports `replaceExisting: boolean` to overwrite previous items.
  - **Notable Gaps Identified:**
    - No `PATCH /trips/:id/itinerary/:itemId` endpoint exists to edit an existing activity in place.
    - No endpoint exists to batch update `orderIndex` for drag-and-drop timeline reordering.
    - No endpoint exists to aggregate budget analytics by category.

### 2.2. Database Schema (`apps/backend/prisma/schema.prisma`)
- **Models:**
  - `Trip`: id, userId, title, destination, startDate, endDate, budget, status (`DRAFT`, `PLANNED`, `ONGOING`, `COMPLETED`, `CANCELLED`), travelStyle (`BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`), createdAt, updatedAt.
  - `Itinerary`: id, tripId, dayNumber, date, title.
  - `ItineraryItem`: id, itineraryId, placeId (optional FK to Place), activity, startTime, endTime, estimatedCost, notes, transportMode, orderIndex, isAiGenerated.
  - `TripMember`: id, tripId, userId, role (`OWNER`, `EDITOR`, `VIEWER`), status (`INVITED`, `ACCEPTED`, `DECLINED`).

### 2.3. Mobile Flutter Feature (`apps/mobile/lib/features/trips/`)
- **Presentation:**
  - `trip_list_screen.dart`: List of trips separated into Upcoming and Past; includes search and create CTA.
  - `trip_detail_screen.dart`: Hero header card, day tabs, timeline view, add activity dialog, AI Planner sheet.
  - `trip_form_screen.dart`: Create and edit trip forms with date pickers and validation.
- **Data & Repository:**
  - `trip_models.dart`: Dart representations of `Trip`, `Itinerary`, `ItineraryItem`.
  - `trip_repository.dart`: API client calls to NestJS endpoints.

---

## 3. Comprehensive Capability Matrix

The matrix below provides complete data honesty by classifying each feature into its verified code capability status:
- **CURRENT:** Completely supported by backend API and mobile Flutter screens today.
- **PARTIAL:** Backend endpoint or database model exists, but UI integration or client bridge is incomplete.
- **FUTURE:** Designed in visual mockups and UX flows, but awaiting backend/frontend implementation.
- **BLOCKED:** Blocked by third-party external dependency or security prerequisite.

| Feature ID | Feature Name | Backend API Endpoint | Flutter UI Screen / Widget | Capability Status | Current Code Reality vs Target Specification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CAP-01** | Trip List Discovery | `GET /trips` | `trip_list_screen.dart` | **CURRENT** | Fetches user trips, splits into upcoming/past, filters by search query. |
| **CAP-02** | Trip Creation | `POST /trips` | `trip_form_screen.dart` | **CURRENT** | Title, destination, start/end dates, budget, travel style validation. |
| **CAP-03** | Trip Metadata Edit | `PATCH /trips/:id` | `trip_form_screen.dart` | **CURRENT** | Updates title, dates, budget, travelStyle. |
| **CAP-04** | Trip Deletion | `DELETE /trips/:id` | `trip_detail_screen.dart` | **CURRENT** | Cascades deletion of itinerary items; modal confirmation prompt. |
| **CAP-05** | Trip Detail & Hero | `GET /trips/:id` | `trip_detail_screen.dart` | **CURRENT** | Renders hero gradient, destination, date range, day selector tabs. |
| **CAP-06** | Add Activity | `POST /trips/:id/itinerary` | `trip_detail_screen.dart` | **CURRENT** | Adds item with dayNumber, time, cost, notes, and optional placeId. |
| **CAP-07** | Delete Activity | `DELETE /trips/:id/itinerary/:itemId` | `trip_detail_screen.dart` | **CURRENT** | Removes item and updates timeline state. |
| **CAP-08** | Edit Activity | None (`PATCH` missing) | Dialog missing | **FUTURE / PARTIAL** | Backend has no edit activity endpoint; designed in `trip-mobile-edit-activity.png`. |
| **CAP-09** | Timeline Reordering | None (Batch order missing) | Reorder handles missing | **FUTURE** | `orderIndex` exists in DB, but no reorder API exists; designed in `trip-mobile-reorder.png`. |
| **CAP-10** | Add Place from Place Detail | `POST /trips/:id/itinerary` | Modal missing on Place Detail | **PARTIAL** | Backend accepts `placeId`; Place Detail screen does not yet open trip picker sheet. |
| **CAP-11** | AI Planner Entry | `POST /trips/:id/ai-plan` | `trip_detail_screen.dart` | **CURRENT** | Passes trip constraints + optional custom prompt. |
| **CAP-12** | AI Generating Feedback | AI Service | `trip_detail_screen.dart` | **CURRENT** | Live elapsed timer, dynamic step cues, NO fake progress percentage. |
| **CAP-13** | AI Plan Preview | `POST /trips/:id/ai-plan` | Preview bottom sheet | **CURRENT** | **Invariant Verified:** Purely in-memory preview; NO database mutation. |
| **CAP-14** | AI Overwrite Warning | Client check | Warning modal | **CURRENT** | Warns user if existing activities will be deleted on apply (`replaceExisting=true`). |
| **CAP-15** | AI Bulk Commit | `POST /trips/:id/itinerary/bulk` | Preview action | **CURRENT** | Atomic transaction: deletes old if confirmed, saves new items with `isAiGenerated: true`. |
| **CAP-16** | Budget Tracking Gauge | Client compute | Bottom bar / stat card | **CURRENT (UI) / PARTIAL (API)** | Real-time budget progress bar (<85% safe, 85-100% warning, >100% over). Category breakdown is Phase 2 API. |
| **CAP-17** | Trip Members & Sharing | `POST /trips/:id/members` | UI missing | **PARTIAL** | Prisma schema has `TripMember` table; UI invite/member modal not yet built. |
| **CAP-18** | Wandy Chat Trip Context | None | Chat missing `tripId` | **FUTURE** | AI Chat endpoint does not yet accept active `tripId` to reference itinerary during chat. |

---

## 4. Verification of High-Fidelity Mockups (31 Total)

All 31 requested mockups have been generated in the project workspace at `docs/audit/evidence/ui-08.2.3.5/` using headless browser rendering.

| # | Mockup File Name | Viewport | Dimensions | File Size | Description & UI State |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **01** | `trip-mobile-list-upcoming.png` | Mobile | $390 \times 844$ | 39,682 B | Upcoming trips list with status badges, budget tracks, and card media |
| **02** | `trip-mobile-list-past.png` | Mobile | $390 \times 844$ | 29,923 B | Past / completed trips list with history dates and completed status |
| **03** | `trip-mobile-list-empty.png` | Mobile | $390 \times 844$ | 28,638 B | First-time empty state with friendly luggage illustration and create CTA |
| **04** | `trip-mobile-list-loading.png` | Mobile | $390 \times 844$ | 19,831 B | Shimmer skeleton loading placeholder cards |
| **05** | `trip-mobile-list-error.png` | Mobile | $390 \times 844$ | 21,153 B | Network connection failure error screen with retry button |
| **06** | `trip-mobile-create.png` | Mobile | $390 \times 844$ | 33,462 B | Trip creation form: Title, Destination, Dates, Budget, Travel Style |
| **07** | `trip-mobile-create-validation.png` | Mobile | $390 \times 844$ | 24,798 B | Form validation errors: missing title, invalid date range |
| **08** | `trip-mobile-edit.png` | Mobile | $390 \times 844$ | 19,692 B | Trip edit form pre-populated with current trip attributes |
| **09** | `trip-mobile-delete-confirmation.png` | Mobile | $390 \times 844$ | 21,743 B | Destructive confirmation dialog before deleting trip and cascading items |
| **10** | `trip-mobile-detail.png` | Mobile | $390 \times 844$ | 67,817 B | Main Trip Detail screen: hero card, day tabs, timeline items, bottom bar |
| **11** | `trip-mobile-detail-empty.png` | Mobile | $390 \times 844$ | 34,439 B | Empty trip detail screen showing AI Planner CTA banner |
| **12** | `trip-mobile-timeline.png` | Mobile | $390 \times 844$ | 30,310 B | Chronological timeline view with time slots, dots, and activity cards |
| **13** | `trip-mobile-add-activity.png` | Mobile | $390 \times 844$ | 24,779 B | Add activity modal sheet: Day picker, title, place search, time, cost |
| **14** | `trip-mobile-edit-activity.png` | Mobile | $390 \times 844$ | 22,998 B | Edit activity modal sheet pre-populated with existing schedule item |
| **15** | `trip-mobile-delete-activity.png` | Mobile | $390 \times 844$ | 12,684 B | Activity deletion confirmation dialog |
| **16** | `trip-mobile-reorder.png` | Mobile | $390 \times 844$ | 23,584 B | Timeline reorder mode with drag handles on each activity card |
| **17** | `trip-mobile-budget.png` | Mobile | $390 \times 844$ | 33,039 B | Normal budget state (< 85% allocated, teal progress bar) |
| **18** | `trip-mobile-budget-warning.png` | Mobile | $390 \times 844$ | 33,765 B | Warning budget state (85% - 100% allocated, amber progress bar) |
| **19** | `trip-mobile-budget-over.png` | Mobile | $390 \times 844$ | 33,557 B | Over-budget alert state (> 100% allocated, crimson red progress bar) |
| **20** | `trip-mobile-ai-entry.png` | Mobile | $390 \times 844$ | 36,315 B | AI Planner entry modal showing trip parameters and custom prompt input |
| **21** | `trip-mobile-ai-generating.png` | Mobile | $390 \times 844$ | 22,477 B | AI generation in progress: live elapsed timer, status steps, NO fake % |
| **22** | `trip-mobile-ai-preview.png` | Mobile | $390 \times 844$ | 40,029 B | AI plan preview sheet: budget variance, proposed days, activities |
| **23** | `trip-mobile-ai-overwrite.png` | Mobile | $390 \times 844$ | 16,127 B | Overwrite warning modal when trip already contains existing activities |
| **24** | `trip-mobile-ai-success.png` | Mobile | $390 \times 844$ | 19,813 B | Success state notification after bulk committing AI plan |
| **25** | `trip-mobile-ai-error.png` | Mobile | $390 \times 844$ | 16,830 B | AI generation failure state with retry option |
| **26** | `trip-desktop-list.png` | Desktop | $1440 \times 900$ | 144,985 B | Desktop 3-column responsive trip cards grid with search and status tabs |
| **27** | `trip-desktop-create.png` | Desktop | $1440 \times 900$ | 50,359 B | Desktop centered modal dialog for creating a new trip |
| **28** | `trip-desktop-detail.png` | Desktop | $1440 \times 900$ | 142,680 B | Desktop 3-pane workspace: Left overview, center timeline, right budget |
| **29** | `trip-desktop-detail-budget.png` | Desktop | $1440 \times 900$ | 106,142 B | Desktop budget view: category allocation bars, stat cards, day-by-day table |
| **30** | `trip-desktop-ai-preview.png` | Desktop | $1440 \times 900$ | 157,322 B | Desktop AI preview modal: parameter specs, reasoning, multi-day schedule |
| **31** | `trip-desktop-error.png` | Desktop | $1440 \times 900$ | 35,670 B | Desktop network/server error view with retry and return home actions |

---

## 5. Strict Constraints Compliance Audit

- [x] **Zero Code Changes in Production Apps:**
  - `git status` shows no modifications to `apps/mobile/lib/`, `apps/backend/src/`, `apps/ai-service/app/`.
- [x] **Zero Database / Schema Changes:**
  - `prisma/schema.prisma` is completely unmodified.
  - No new database migrations or table alterations were introduced.
- [x] **Zero API Contract Breaking Changes:**
  - All existing DTOs (`CreateTripDto`, `UpdateTripDto`, `CreateItineraryItemDto`, `BulkCreateItineraryItemDto`) remain intact.
- [x] **Data Honesty Invariants Enforced:**
  - AI Plan Preview does NOT write to the database (`POST /trips/:id/ai-plan` remains read-only).
  - Bulk save uses explicit user confirmation (`POST /trips/:id/itinerary/bulk`).
  - No fake progress percentages were rendered in AI generating states.
  - All mockups include the standardized visual demo data watermark.

---

## 6. Engineering Handoff Recommendations & Next Steps

For the upcoming implementation sprint (Sprint 02):
1. **Activity Edit API:** Implement `PATCH /trips/:id/itinerary/:itemId` in NestJS `trips.controller.ts` and `trips.service.ts` allowing granular activity updates.
2. **Batch Reordering API:** Implement `PUT /trips/:id/itinerary/reorder` accepting an array of `{ itemId: string, orderIndex: number }` within a Prisma transaction.
3. **Place Detail Integration:** Mount the "Thêm vào chuyến đi" dialog on `place_detail_screen.dart`, calling `tripRepository.addItineraryItem`.
4. **Category Budget Analytics:** Implement a backend aggregation query on `ItineraryItem` grouping costs by place category (`FOOD`, `HOTEL`, `SIGHTSEEING`, `TRANSPORT`).
5. **Wandy Chat Trip Context:** Update `POST /ai/chat` payload to accept `tripId?: string`, enabling Wandy to ground conversational responses directly in the user's active travel schedule.
