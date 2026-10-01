# Data Dictionary — WanderAI

## Core Entities

### User
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| email | VARCHAR(255) | Unique, required |
| passwordHash | TEXT | Bcrypt hashed |
| name | VARCHAR(255) | Display name |
| avatar | TEXT | URL to avatar image |
| role | ENUM | USER, ADMIN, MODERATOR |
| createdAt | TIMESTAMPTZ | UTC |

### Destination
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | GoMate canonical ID |
| name | VARCHAR(255) | Vietnamese name |
| nameEn | VARCHAR(255) | English name |
| slug | VARCHAR(255) | URL-friendly unique identifier |
| description | TEXT | Rich text description |
| province | VARCHAR(100) | Province/City |
| region | ENUM | north, central, south |
| latitude | FLOAT8 | WGS84 |
| longitude | FLOAT8 | WGS84 |
| rating | FLOAT4 | Aggregated from reviews (0-5) |
| isPopular | BOOLEAN | Curated flag |
| coverImage | TEXT | URL |

### Place
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | GoMate canonical ID |
| destinationId | UUID | FK → Destination |
| name | VARCHAR(255) | Vietnamese name |
| category | ENUM | attraction, restaurant, hotel, cafe, tour, transport, hospital, pharmacy, police |
| latitude | FLOAT8 | WGS84 precise |
| longitude | FLOAT8 | WGS84 precise |
| address | TEXT | Full address |
| priceRange | VARCHAR(50) | e.g. "50000-200000" VND |
| rating | FLOAT4 | Aggregated |
| phone | VARCHAR(20) | Contact |
| website | TEXT | URL |
| openingHours | JSONB | {mon: "08:00-17:00", ...} |

### PlaceSource (NEW — required for Entity Resolution)
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| placeId | UUID | FK → Place (canonical) |
| sourceName | VARCHAR(50) | 'osm', 'google_places', 'youtube', 'manual' |
| sourceId | VARCHAR(255) | External ID (OSM node ID, Google Place ID) |
| rawName | VARCHAR(255) | Name as reported by source |
| latitude | FLOAT8 | Coordinates from source |
| longitude | FLOAT8 | Coordinates from source |
| rawData | JSONB | Original payload |
| confidenceScore | FLOAT4 | Match confidence 0-1 |
| createdAt | TIMESTAMPTZ | UTC |

### Trip
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| userId | UUID | FK → User (owner) |
| destinationId | UUID | FK → Destination |
| name | VARCHAR(255) | Trip title |
| startDate | DATE | Trip start |
| endDate | DATE | Trip end |
| budget | INTEGER | VND (integer, never float) |
| travelStyle | ENUM | budget, standard, luxury |
| status | ENUM | DRAFT, PLANNED, ACTIVE, COMPLETED, CANCELLED |

### Review
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| userId | UUID | FK → User |
| placeId | UUID | FK → Place |
| rating | INTEGER | 1-5 stars |
| content | TEXT | Review text |
| sentiment | FLOAT4 | AI-computed -1 to 1 |
| aspects | JSONB | {food: 0.8, service: 0.6, ...} |

## Currency Rule
All monetary values stored as INTEGER in VND. Never use float for money.

## Timezone Rule
All timestamps stored as TIMESTAMPTZ in UTC. Frontend converts to Asia/Ho_Chi_Minh.
