# Map Flow — WanderAI

## Architecture

```
┌──────────────────┐
│  Flutter MapScreen│
│  (flutter_map)    │
└────────┬─────────┘
         │ Dio (JWT)
    ┌────▼────┐
    │ NestJS  │  GET /places/nearby
    │ :3000   │  GET /places?verifiedOnly=true
    └────┬────┘
         │ Prisma + Raw SQL
    ┌────▼──────────────┐
    │ PostgreSQL/PostGIS │
    │ places table       │
    │ place_sources table│
    │ place_categories   │
    └────────────────────┘
```

## Data Flow

```
User opens Map tab
    ↓
Try get GPS location (optional)
    ↓ success → use user location
    ↓ denied  → use default (Hanoi: 21.0285, 105.8542)
    ↓
GET /places/nearby?lat=...&lng=...&radius=10&verifiedOnly=true
    ↓
PostGIS: ST_DWithin(..., radius_meters)
    ↓
Return places with distanceKm, isVerified
    ↓
Render markers on flutter_map
    ↓
User taps marker
    ↓
Show PlacePreviewSheet (name, category, rating, distance, verified badge)
```

## Map Provider (ADR-005, superseded by ADR-006)

- **Rendering**: flutter_map v7 + OpenStreetMap Humanitarian (HOT) raster tiles
- **Place data**: WanderAI PostgreSQL/PostGIS (NOT Google Places)
- **Tile URL**: `https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png` (fallback: `https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png`)
- **Attribution**: `© OpenStreetMap contributors` / `Tiles: Humanitarian OpenStreetMap Team / OSM France` (always visible)

## Location Permission

| State | Behavior |
|-------|----------|
| Not requested | Request permission on map open |
| Granted | Use GPS location, show blue dot |
| Denied | Use Hanoi default, no error shown |
| Denied forever | Use Hanoi default silently |
| Service disabled | Use Hanoi default silently |

## Nearby Search

- Radius options: 1 km, 5 km, 10 km, 25 km
- Default: 10 km
- PostGIS query: `ST_DWithin(point1::geography, point2::geography, radius_meters)`
- Results ordered by distance ASC, limited to 100

## Category Filtering

Categories from `place_categories` table:

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

## Text Search

- Debounce: 500ms
- Backend: `GET /places?search=...&verifiedOnly=true`
- Matches: name, nameEn, address (case-insensitive)
- Results filtered to places with coordinates

## Provenance / Verified Filter

- Map only shows places with `verifiedOnly=true`
- A place is "verified" if it has ≥1 record in `place_sources` table
- Source provenance (e.g., `sourceName: "osm"`) displayed in preview
- Synthetic/legacy places are excluded from the map

## States

| State | UI |
|-------|-----|
| Initial | Map renders, loading indicator |
| Loading | Small pill "Đang tải..." |
| Loaded | Markers displayed, count badge |
| Empty | "Không tìm thấy địa điểm" message |
| Error | Error message with "Thử lại" button |
