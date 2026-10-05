# ADR-003: Trip Context Attributes Schema Extension

## Status
Accepted

## Date
2026-10-01

## Context
In the GoMate / WanderAI architecture, `Trip` is not simply a CRUD entity for a mobile list; it serves as the central context container for:
- AI Trip Planner & Travel Agent
- Personalized Destination & Place Recommendations
- Budget & Expense Tracking
- Companion Matching
- Interactive Maps & Itineraries
- Safety Monitoring & Check-ins

The existing `Trip` model in Prisma lacked explicit fields for:
- `currency` (to explicitly declare monetary denomination, defaulting to "VND")
- `travelStyle` (Backpacker, Budget, Comfort, Luxury)
- `interests` (String array, e.g. ["nature", "culture", "food"])

These fields are essential for the TripContext abstraction that downstream AI, recommendation, and companion services depend on.

## Decision
Extend the `Trip` Prisma model with:
1. `currency String @default("VND")`
2. `travelStyle TravelStyle? @map("travel_style")`
3. `interests String[] @default([])`

All additions are backwards-compatible:
- Existing queries without these fields continue to function.
- Default values ensure existing rows are automatically populated without NULL violations.
- Prisma migration is executed cleanly against PostgreSQL.

## Consequences
- The Trip model now fully supports rich trip context.
- NestJS DTOs can accept and validate travel style, currency, and interests.
- Flutter forms can capture travel preferences directly during trip creation.
- Downstream AI tools can consume the normalized TripContext object.
