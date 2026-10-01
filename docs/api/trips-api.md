# Trips API Contract

## Overview

The Trips module manages user travel plans, budgets, travel styles, and manual itineraries. Every endpoint is protected with JWT authentication (`JwtAuthGuard`) and enforces strict owner/member authorization.

Base path: `/trips`  
Authentication: `Authorization: Bearer <access_token>`

---

## Endpoints

### 1. `POST /trips` — Create Trip

Create a new trip for the authenticated user. The creator is automatically added as a `TripMember` with role `owner`.

- **Authentication**: Required (`Bearer <token>`)
- **Request Body (`application/json`)**:
  | Field | Type | Required | Description | Constraints |
  |---|---|---|---|---|
  | `title` | string | Yes | Trip name | Non-empty |
  | `destinationId` | string (UUID) | No | Destination ID | Must exist in `destinations` table |
  | `startDate` | string | No | Start date (YYYY-MM-DD) | Must be before or equal to `endDate` |
  | `endDate` | string | No | End date (YYYY-MM-DD) | Must be after or equal to `startDate` |
  | `totalBudget` | integer | No | Total estimated budget (VND) | Must be $\ge 0$ |
  | `currency` | string | No | Currency code | `"VND"` or `"USD"`, defaults to `"VND"` |
  | `travelStyle` | string | No | Travel style | `"BACKPACKER"`, `"BUDGET"`, `"COMFORT"`, `"LUXURY"` |
  | `interests` | string[] | No | Array of interests | e.g. `["nature", "food"]` |
  | `description` | string | No | Trip description / notes | Free text |

- **Success Response (`201 Created`)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "uuid",
      "userId": "uuid",
      "title": "Hà Giang mùa hoa tam giác mạch",
      "destinationId": "uuid",
      "startDate": "2026-10-15T00:00:00.000Z",
      "endDate": "2026-10-18T00:00:00.000Z",
      "totalBudget": 4500000,
      "currency": "VND",
      "travelStyle": "COMFORT",
      "interests": ["nature", "culture"],
      "status": "DRAFT",
      "createdAt": "...",
      "updatedAt": "...",
      "destination": { "id": "...", "name": "Hà Giang", "province": "Hà Giang" },
      "members": [{ "userId": "...", "role": "owner" }]
    },
    "timestamp": "..."
  }
  ```

- **Error Codes**:
  - `401 Unauthorized`: Missing or invalid JWT
  - `400 Bad Request`: Validation failure (empty title, invalid date range `endDate < startDate`, negative budget)
  - `404 Not Found`: `destinationId` not found

---

### 2. `GET /trips` — List My Trips

Retrieve all non-deleted trips created by or shared with the authenticated user, ordered by `createdAt DESC`.

- **Authentication**: Required
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "uuid",
        "title": "Hà Giang mùa hoa tam giác mạch",
        "startDate": "2026-10-15T00:00:00.000Z",
        "endDate": "2026-10-18T00:00:00.000Z",
        "totalBudget": 4500000,
        "currency": "VND",
        "travelStyle": "COMFORT",
        "status": "DRAFT",
        "destination": { "id": "...", "name": "Hà Giang" },
        "_count": { "members": 1, "itineraries": 3 }
      }
    ],
    "timestamp": "..."
  }
  ```

---

### 3. `GET /trips/:id` — Trip Detail

Retrieve full trip details including destination, daily itineraries, itinerary items, and members.

- **Authentication**: Required
- **Authorization**: User must be the owner or an accepted member.
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "uuid",
      "title": "Hà Giang mùa hoa",
      "itineraries": [
        {
          "id": "uuid",
          "dayNumber": 1,
          "items": [
            {
              "id": "uuid",
              "orderIndex": 1,
              "startTime": "08:00",
              "endTime": "11:30",
              "activity": "Check-in Cột cờ Lũng Cú",
              "estimatedCost": 200000
            }
          ]
        }
      ],
      "members": [...]
    },
    "timestamp": "..."
  }
  ```
- **Error Codes**:
  - `404 Not Found`: Trip not found or deleted
  - `403 Forbidden`: User is neither owner nor member of this trip

---

### 4. `PUT /trips/:id` — Update Trip

Update trip metadata. Only the owner can update the trip.

- **Authentication**: Required
- **Authorization**: Only `trip.userId === authenticatedUser.id`
- **Request Body**: Partial `UpdateTripDto`
- **Error Codes**:
  - `404 Not Found`: Trip not found
  - `403 Forbidden`: User is not the owner
  - `400 Bad Request`: Invalid dates or negative budget

---

### 5. `DELETE /trips/:id` — Delete Trip (Soft Delete)

Soft-deletes the trip by setting `deletedAt = now()`.

- **Authentication**: Required
- **Authorization**: Only `trip.userId === authenticatedUser.id`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": { "message": "Đã xóa chuyến đi thành công" },
    "timestamp": "..."
  }
  ```
- **Error Codes**:
  - `404 Not Found`: Trip not found
  - `403 Forbidden`: User is not the owner

---

### 6. `POST /trips/:id/itinerary` — Add Itinerary Item

Add an activity/item to a specific day of the trip.

- **Request Body**:
  ```json
  {
    "dayNumber": 1,
    "activity": "Ngắm hoàng hôn Mã Pí Lèng",
    "startTime": "16:00",
    "endTime": "18:00",
    "estimatedCost": 150000,
    "notes": "Nhớ mang áo ấm"
  }
  ```
- **Success Response (`201 Created`)** with created item.
