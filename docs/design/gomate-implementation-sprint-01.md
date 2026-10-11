# GoMate — Sprint 01 Implementation Plan

## Goal

Stabilize the existing foundation and create the first production UI layer without changing validated business contracts.

## Task 0 — Release TASK 08.1.1

- Verify feature branch is clean.
- Merge with --no-ff into develop.
- Run Backend 76+, AI 87 + 2 skipped, Flutter 152+.
- Run browser smoke for location, distance, navigation and map behavior.
- Push develop.
- Record final baseline.

## Task 1 — Freeze design tokens

Create/update:
- AppColors
- AppTypography
- AppSpacing
- AppRadius
- ThemeData
- motion tokens
- responsive breakpoints

Acceptance:
- No screen uses unexplained hardcoded design values.

## Task 2 — UI-01 App Shell

Implement:
- mobile bottom nav
- tablet rail
- desktop sidebar
- global responsive scaffold
- persistent router

Acceptance:
- navigation round-trip passes
- zero GlobalKey errors
- zero RenderFlex overflow

## Task 3 — UI-02 Home

Implement:
- greeting
- search entry
- Wandy action card
- nearby section
- destination section
- empty/error/loading states

Acceptance:
- responsive at 390px, 768px, 1280px
- all visible data is factual

## Task 4 — UI-03 Search

Implement:
- search bar
- suggestions
- categories
- result list
- no-result state

Acceptance:
- search does not disturb unrelated map state
- keyboard and mouse interactions work on web

## Task 5 — UI-04 Map re-presentation

Only after UI-01..03.

Preserve the current validated logic:
- HOT tiles
- verifiedOnly=true
- Haversine distance
- explicit location permission
- accuracy state
- no automatic camera movement
- category switching clears stale preview

## Per-task evidence

For each task store:
- test output
- browser screenshots
- console capture
- API contract evidence when changed
- audit note
- commit hash

## Release gate

Do not begin the next UI module if:
- automated tests fail
- browser smoke fails
- a key business contract changes unexpectedly
- docs and implementation disagree
