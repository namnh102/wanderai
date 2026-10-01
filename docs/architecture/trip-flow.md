# Trip Planning & CRUD Flow Architecture

## Overview

In WanderAI (GoMate), `Trip` is not simply a CRUD entity for a mobile list; it serves as the **central context container** binding together all future intelligent features:

```
                          ┌─────────────────────────────┐
                          │         TRIP CONTEXT        │
                          │ - trip_id                   │
                          │ - destination               │
                          │ - start_date & end_date     │
                          │ - budget & currency         │
                          │ - travel_style              │
                          │ - interests                 │
                          │ - itineraries (daily items) │
                          └──────────────┬──────────────┘
                                         │
        ┌────────────────┬───────────────┼───────────────┬────────────────┐
        ▼                ▼               ▼               ▼                ▼
   AI Travel Agent  Recommendation    Booking       Companion       Safety &
     (Planner)        (Places)      (Hotels/Tours)   Matching       Check-ins
```

---

## Architecture Flow

```
Flutter Mobile
  │
  ├─ TripListScreen (My trips list, empty state, pull-to-refresh)
  ├─ TripFormScreen (Create / edit form with validation)
  ├─ TripDetailScreen (Overview, day-by-day itineraries, add/delete activities)
  │
  ├─ TripListNotifier / TripDetailNotifier (Riverpod state management)
  │     └─ Handles loading, optimistic list updates, error banners
  │
  ├─ TripRepository (Dio data access layer)
  │     └─ Uses authenticated apiClient with Bearer token
  │
  ▼  HTTP REST (POST, GET, PUT, DELETE /trips)
NestJS API Gateway
  │
  ├─ JwtAuthGuard (Enforces valid JWT authentication)
  ├─ ValidationPipe (Enforces CreateTripDto, UpdateTripDto, AddItineraryDto)
  ├─ TripsController & TripsService
  │     ├─ Ownership verification (403 if modifying another's trip)
  │     ├─ Date consistency (startDate <= endDate)
  │     ├─ Budget validation (budget >= 0)
  │     ├─ Soft delete via deletedAt
  │     └─ Automatic TripMember creation (creator as 'owner')
  │
  ▼  Prisma ORM Client
PostgreSQL Database (Docker port 5432)
  │
  ├─ trips (id, user_id, destination_id, title, start_date, end_date, total_budget, currency, travel_style, interests, status)
  ├─ trip_members (trip_id, user_id, role)
  ├─ itineraries (trip_id, day_number)
  └─ itinerary_items (itinerary_id, place_id, activity, start_time, end_time, estimated_cost, notes)
```

---

## Security & Authorization Rules

1. **Authentication**: All endpoints require `Authorization: Bearer <access_token>`. Unauthenticated requests return `401 Unauthorized`.
2. **Access Control**:
   - `GET /trips/:id`: Only the trip owner or accepted trip members can view the trip. Other users receive `403 Forbidden`.
   - `PUT /trips/:id`: Only the owner can update the trip. Other users receive `403 Forbidden`.
   - `DELETE /trips/:id`: Only the owner can delete the trip. Other users receive `403 Forbidden`.
3. **Data Integrity**:
   - If `endDate < startDate`, the request is rejected with `400 Bad Request`.
   - If `totalBudget < 0`, the request is rejected with `400 Bad Request`.
   - If `destinationId` does not exist, the request is rejected with `404 Not Found`.

---

## TripContext Abstraction

Every `TripModel` exposes `toTripContext()`:

```dart
class TripContext {
  final String tripId;
  final String destination;
  final DateTime? startDate;
  final DateTime? endDate;
  final int? budget;
  final String currency;
  final String? travelStyle;
  final List<String> interests;
  final List<ItineraryModel> itinerary;
}
```

This normalized object can be serialized and passed directly into:
- The AI Agent (`POST /ai/plan` or `/ai/chat`)
- The Recommendation Engine for personalized place scoring
- The Safety check-in daemon to monitor trip dates and locations
