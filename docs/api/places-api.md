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

---

## GET /places/:id — Place Detail contract (TASK 08)

Factual, provenance-backed detail used by the Flutter Place Detail screen. **Nothing is invented**: every optional field is `null` when the database / OSM tags have no data.

**Validation:** `:id` must be a UUID → otherwise `400`. Unknown / soft-deleted → `404`.

**Added / derived fields**

| Field | Source | `null` when |
|-------|--------|-------------|
| `isVerified` | ≥ 1 row in `place_sources` (unchanged semantics) | — (boolean) |
| `address` | OSM `addr:housenumber`, `addr:street`, `addr:suburb`/`addr:district`, `addr:city` joined with `, ` | no `addr:*` tags, or place unverified |
| `openingHours` | OSM `opening_hours` tag (verbatim), else `places.opening_hours` | not tagged, or place unverified |
| `website` | OSM `website` / `contact:website` | not tagged, or place unverified |
| `phone` | OSM `phone` / `contact:phone` | not tagged, or place unverified |
| `description` | `places.description` | empty, or place unverified |
| `rating`, `reviewCount` | stored values / trusted reviews only | `rating` is `null` when unavailable — never defaulted |
| `source` | the OSM `place_sources` row | place has no OSM source |

`source`:

```json
{
  "name": "OpenStreetMap",
  "sourceId": "way/37933256",
  "canonicalUrl": "https://www.openstreetmap.org/way/37933256",
  "license": "ODbL 1.0",
  "attribution": "© OpenStreetMap contributors"
}
```

`placeSources[]` entries additionally carry `canonicalUrl`, `license`, `attribution`; the raw OSM tag blob (`rawData`) is **not** exposed.

Unverified (unsourced dev/test) places are still resolvable by id but expose no descriptive facts: `isVerified=false`, `source=null`, `placeSources=[]`, and `address/description/openingHours/website/phone = null`. `reviews` only ever contains `trusted=true` rows — synthetic/mock reviews never appear.

List semantics are unchanged: `GET /places` and `/places/nearby` still default to `verifiedOnly=true`.

**Tests:** `apps/backend/test/place-detail.e2e-spec.ts`.
