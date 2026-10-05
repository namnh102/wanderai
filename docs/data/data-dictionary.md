# Data Dictionary — GoMate / WanderAI

## 1. Overview
This document defines the physical and domain schemas for GoMate travel entities, source provenance tracking, and user-generated/benchmark reviews.

---

## 2. Core Entities

### User (`users`)
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key (`gen_random_uuid()`) |
| `email` | VARCHAR(255) | No | Unique email address |
| `passwordHash` | TEXT | No | Bcrypt hashed password (cost factor 10) |
| `role` | ENUM | No | `USER`, `ADMIN`, `MODERATOR` |
| `isVerified` | BOOLEAN | No | Verification status flag |
| `createdAt` | TIMESTAMPTZ | No | UTC timestamp |
| `updatedAt` | TIMESTAMPTZ | No | UTC timestamp |
| `deletedAt` | TIMESTAMPTZ | Yes | Soft delete timestamp |

### Profile (`profiles`)
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key |
| `userId` | UUID | No | Unique FK → `users.id` (1:1) |
| `displayName` | VARCHAR(255) | No | User's full public display name |
| `avatar` | TEXT | Yes | URL to avatar image asset |
| `bio` | TEXT | Yes | Biography / travel bio |
| `phone` | VARCHAR(20) | Yes | Contact phone number |
| `dateOfBirth` | DATE | Yes | Birth date |
| `nationality` | VARCHAR(50) | Yes | Nationality |
| `languages` | TEXT[] | No | Preferred spoken languages |

### Destination (`destinations`)
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | GoMate canonical Destination ID |
| `name` | VARCHAR(255) | No | Vietnamese destination name (e.g., "Đà Nẵng") |
| `nameEn` | VARCHAR(255) | Yes | English destination name (e.g., "Da Nang") |
| `slug` | VARCHAR(255) | No | URL-safe slug, unique (e.g., "da-nang") |
| `description` | TEXT | Yes | Overview description |
| `province` | VARCHAR(100) | Yes | Province or municipality |
| `region` | VARCHAR(50) | Yes | `north`, `central`, `south` |
| `latitude` | FLOAT8 | Yes | WGS84 latitude |
| `longitude` | FLOAT8 | Yes | WGS84 longitude |
| `coverImage` | TEXT | Yes | Header banner image |
| `rating` | FLOAT8 | No | Aggregated rating (default 0) |
| `reviewCount` | INTEGER | No | Total review count |
| `isPopular` | BOOLEAN | No | Trending/curated priority flag |

### Place Category (`place_categories`)
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key |
| `name` | VARCHAR(100) | No | Unique taxonomy key: `attraction`, `hotel`, `restaurant`, `cafe`, `beach`, `temple`, `market`, `museum`, `park`, `nightlife`, `culture`, `other` |
| `icon` | VARCHAR(100) | Yes | Material icon identifier |
| `color` | VARCHAR(20) | Yes | Hex color code |

### Place (`places`) — Canonical Entity
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | **Authoritative GoMate canonical ID** (never external ID) |
| `destinationId` | UUID | No | FK → `destinations.id` |
| `categoryId` | UUID | Yes | FK → `place_categories.id` |
| `name` | VARCHAR(255) | No | Canonical display name in Vietnamese |
| `nameEn` | VARCHAR(255) | Yes | English name |
| `description` | TEXT | Yes | Description |
| `address` | TEXT | Yes | Standardized street/ward/city address |
| `latitude` | FLOAT8 | Yes | PostGIS-indexed WGS84 latitude ($8.18 \le \text{lat} \le 23.39$) |
| `longitude` | FLOAT8 | Yes | PostGIS-indexed WGS84 longitude ($102.14 \le \text{lon} \le 109.46$) |
| `priceMin` | INTEGER | Yes | Minimum price in integer VND |
| `priceMax` | INTEGER | Yes | Maximum price in integer VND |
| `openingHours` | VARCHAR(255)| Yes | Operating schedule |
| `coverImage` | TEXT | Yes | Primary image |
| `images` | TEXT[] | No | Additional images array |
| `rating` | FLOAT8 | No | Dynamic rating aggregated from linked reviews |
| `reviewCount` | INTEGER | No | Number of linked reviews |

### Place Source (`place_sources`) — Provenance & Entity Resolution
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key |
| `placeId` | UUID | No | FK → `places.id` (onDelete: Cascade) |
| `sourceName` | VARCHAR(50) | No | Source provider (`osm`, `academic_benchmark`, `manual`, `google_places`) |
| `sourceId` | VARCHAR(255)| No | External ID (e.g. `node/268491823`) |
| `rawName` | VARCHAR(255)| No | Original name from source before normalization |
| `latitude` | FLOAT8 | Yes | Raw source latitude |
| `longitude` | FLOAT8 | Yes | Raw source longitude |
| `rawData` | JSONB | Yes | Complete raw tag/attribute payload from upstream |
| `confidenceScore`| FLOAT8 | No | Match confidence composite score ($0.0 \le s \le 1.0$) |
| `createdAt` | TIMESTAMPTZ | No | Ingestion timestamp |
| **Constraint** | UNIQUE(`sourceName`, `sourceId`) | — | Prevents duplicate ingestion of identical external POIs |

### Review (`reviews`)
> [!WARNING]
> The current reviews records in the database are internal test fixtures for pipeline mechanics and are marked UNVERIFIED. Authentic travel reviews must be acquired and verified before Review AI (Task 07).

| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key |
| `userId` | UUID | No | FK → `users.id` (author / curator bot) |
| `placeId` | UUID | No | FK → `places.id` (canonical destination) |
| `rating` | FLOAT8 | No | Clamped score ($1.0 \le r \le 5.0$) |
| `content` | TEXT | No | Review text ($\ge 10$ characters) |
| `images` | TEXT[] | No | Photo attachments |
| `visitDate` | DATE | Yes | Date of visit |
| `createdAt` | TIMESTAMPTZ | No | Timestamp |
| `updatedAt` | TIMESTAMPTZ | No | Timestamp |

### Review Aspect (`review_aspects`)
| Field | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | UUID | No | Primary key |
| `reviewId` | UUID | No | FK → `reviews.id` (onDelete: Cascade) |
| `aspect` | VARCHAR(50) | No | Aspect category (`cleanliness`, `location`, `service`, `value`, `food`) |
| `score` | FLOAT8 | No | Clamped score ($1.0 \le s \le 5.0$) |
| `comment` | TEXT | Yes | Specific aspect remark |

---

## 3. Storage and Currency Invariants
1. **Currency Rule:** All monetary amounts are integers in Vietnamese Dong (VND). Float/double for money is prohibited.
2. **Timezone Rule:** All database timestamps are `TIMESTAMPTZ` in UTC. Clients format into local timezone (`Asia/Ho_Chi_Minh`).
3. **Geographic Coordinates:** Stored as `FLOAT8` in WGS84 coordinate reference system (EPSG:4326), queried with PostGIS geometry/geography functions.
