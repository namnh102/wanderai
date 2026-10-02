# Places API — WanderAI

## Base URL

`http://localhost:3000`

## Authentication

Places endpoints are **public** (no JWT required).

---

## Endpoints

### GET /places

List places with pagination, search, category, and verified filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | number | 1 | Page number |
| `limit` | number | 20 | Items per page |
| `search` | string | — | Case-insensitive search (name, nameEn, address) |
| `category` | string | — | Filter by category name (e.g., `attraction`, `restaurant`) |
| `destinationId` | UUID | — | Filter by destination |
| `verifiedOnly` | boolean | false | Only return places with provenance records |

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "Cầu Rồng",
        "nameEn": "Dragon Bridge",
        "address": "...",
        "latitude": 16.0612,
        "longitude": 108.2272,
        "rating": 4.5,
        "reviewCount": 120,
        "destination": { "id": "...", "name": "Đà Nẵng", "slug": "da-nang", "province": "Đà Nẵng" },
        "category": { "id": "...", "name": "attraction", "icon": "attractions", "color": "#9C27B0" },
        "placeSources": [{ "sourceName": "osm", "sourceId": "node/123", "confidenceScore": 1.0 }],
        "isVerified": true,
        "provenanceCount": 1
      }
    ],
    "total": 108,
    "page": 1,
    "limit": 20,
    "totalPages": 6
  }
}
```

---

### GET /places/nearby

Find places near a GPS coordinate using PostGIS `ST_DWithin`.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | number | required | Center latitude |
| `lng` | number | required | Center longitude |
| `radius` | number | 10 | Radius in kilometers |
| `limit` | number | 20 | Max results |
| `verifiedOnly` | boolean | false | Only verified places |

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Cầu Rồng",
      "nameEn": "Dragon Bridge",
      "address": "...",
      "latitude": 16.0612,
      "longitude": 108.2272,
      "rating": 4.5,
      "reviewCount": 120,
      "categoryName": "attraction",
      "destinationName": "Đà Nẵng",
      "isVerified": true,
      "distanceKm": 0.45
    }
  ]
}
```

**PostGIS Query:**
```sql
ST_DWithin(
  ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
  ST_SetSRID(ST_MakePoint($lng, $lat), 4326)::geography,
  $radiusKm * 1000
)
```

---

### GET /places/:id

Place detail with provenance and reviews.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Cầu Rồng",
    "...": "...",
    "placeSources": [
      {
        "id": "uuid",
        "sourceName": "osm",
        "sourceId": "node/12345",
        "rawName": "Cầu Rồng (Dragon Bridge)",
        "confidenceScore": 1.0,
        "createdAt": "2026-10-01T..."
      }
    ],
    "reviews": [],
    "isVerified": true,
    "provenanceCount": 1
  }
}
```

---

## Provenance

A place is considered **verified** when it has ≥1 record in the `place_sources` table.

| Source | Description |
|--------|-------------|
| `osm` | OpenStreetMap canonical import (ODbL 1.0) |
| `manual` | Manually verified entry |
| `google_places` | Google Places (if permitted) |

Synthetic/legacy seed places have **no** `place_sources` records and are excluded when `verifiedOnly=true`.

---

## Categories

| Key | Label | Icon | Color |
|-----|-------|------|-------|
| attraction | Tham quan | attractions | #9C27B0 |
| restaurant | Nhà hàng | restaurant | #FF5722 |
| hotel | Khách sạn | hotel | #2196F3 |
| temple | Đền/Chùa | temple_buddhist | #FF9800 |
| beach | Biển | beach_access | #00BCD4 |
| museum | Bảo tàng | museum | #607D8B |
| park | Công viên | park | #8BC34A |
| market | Chợ | store | #4CAF50 |
| cafe | Cà phê | local_cafe | #795548 |
| nightlife | Cuộc sống đêm | nightlife | #E91E63 |
