# ADR-005: Map Provider Selection

## Status

SUPERSEDED by ADR-006 (Tile provider superseded by OpenStreetMap Humanitarian / OSM-FR)

## Date

2026-10-02

## Context

WanderAI needs a map component in the Flutter mobile app to display verified canonical places from PostgreSQL/PostGIS. Requirements:

1. Must work on Android (primary target) and Web (development)
2. Must support markers for place display
3. Must support user location (optional, graceful degradation)
4. Must not require paid services for MVP/thesis scope
5. Must have clear attribution terms

### Options Considered

| Option | License | Cost | Markers | Flutter Support | Offline |
|--------|---------|------|---------|-----------------|---------|
| **flutter_map + OpenStreetMap tiles** | BSD-3 (package) + ODbL (data) | Free (tile servers vary) | ✅ Custom markers | ✅ Mature | Possible |
| Google Maps Flutter | Proprietary | Free tier (\$200/mo credit) | ✅ Native | ✅ Official | No |
| Mapbox GL | Proprietary | Free tier (25K loads/mo) | ✅ Custom | ⚠️ Unofficial | Possible |

### Decision Factors

1. **Cost**: Google Maps requires billing account; Mapbox has usage limits. flutter_map with OSM tiles is free.
2. **Data consistency**: WanderAI already uses OSM as canonical place source (ODbL 1.0). Using OSM tiles for rendering creates a consistent data story for the thesis.
3. **API key complexity**: Google Maps requires per-platform API key configuration (AndroidManifest.xml, AppDelegate.swift, index.html). flutter_map requires no API keys with default OSM tiles.
4. **Academic thesis**: Using fully open-source stack (PostGIS + OSM tiles + flutter_map) is stronger for reproducibility arguments.
5. **Tile attribution**: OpenStreetMap requires `© OpenStreetMap contributors` attribution. flutter_map provides built-in `RichAttributionWidget`.

## Decision

Use **flutter_map** (BSD-3) with **OpenStreetMap tile server** for map rendering.

Place data comes from **WanderAI PostgreSQL/PostGIS** (canonical OSM-sourced places), NOT from any external places API.

### Architecture

```
PostgreSQL/PostGIS (canonical places)
         ↓
    NestJS API
    GET /places/nearby
    GET /places?verifiedOnly=true
         ↓
    Flutter (Dio)
         ↓
    flutter_map (rendering)
    + OpenStreetMap tiles (basemap)
    + Custom markers (from DB)
```

## Tile Provider

Default OpenStreetMap tile server (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) for development/thesis.

**Production note**: For production scale, switch to a dedicated tile provider (e.g., self-hosted, Stadia Maps, or MapTiler with appropriate plan). The current OSM tile server usage policy allows low-volume, attributed usage.

## Attribution

Required: `© OpenStreetMap contributors` displayed on the map at all times.

## Consequences

- No API key management needed
- Free for thesis/development use
- Map rendering is separate from place data (clean architecture)
- Limited to raster tiles (no 3D, no vector styling)
- Must respect OSM tile usage policy for production
