# ADR-006: Reachable Basemap Tile Provider Selection (OpenStreetMap Humanitarian / OSM-FR)

## Status

SUPERSEDED & UPDATED (2026-10-04, TASK 07.6.1)

## Date

2026-10-04

## Context

In ADR-005, `flutter_map` with standard OpenStreetMap raster tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) was selected as the map rendering foundation.

During extensive testing (TASK 07.1 through TASK 07.4) and browser verification on Windows/Chrome, map tiles consistently failed to load, presenting a blank grey grid. Network diagnostics revealed that `tile.openstreetmap.org` is connection-throttled or actively refused (`WinError 10061`) on major Vietnamese telecommunications networks (VNPT, Viettel, FPT).

In TASK 07.6, CARTO Voyager (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png`) was initially tested. While HTTP 200 responses were received, visual inspection of rendered tiles in browser QA revealed that CARTO recently introduced a diagonal watermark across unauthenticated raster tiles:
```
"API KEY REQUIRED carto.com/basemaps/apikey"
```
Because WanderAI/GoMate is an academic thesis MVP with a strict constraint against committing secret API keys to client-side code, CARTO tiles cannot be used in production serving without violating the no-watermark, no-secret-key requirement.

A legitimate, dependable, reachable basemap tile provider is required that:
1. Is accessible from Vietnam without connection refusal or proxy workarounds.
2. Serves standard raster PNG tiles compatible with `flutter_map` `TileLayer`.
3. Displays **NO watermark** (specifically no "API KEY REQUIRED").
4. Requires no secret API keys for development, testing, and academic evaluation.
5. Preserves 100% genuine OpenStreetMap data consistency and academic reproducibility.
6. Complies with open data attribution and licensing requirements.

---

## Empirical Benchmark & Evaluation (TASK 07.6.1)

On 2026-10-04, HTTP GET requests and visual tile inspections were executed directly from the project host environment:

| Candidate Endpoint | Protocol | Latency | Status Code | Visual Inspection / Watermark | CORS Header | Result |
|---|---|---|---|---|---|---|
| `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | HTTPS | — | Connect Refused | N/A | — | **FAILED** (Blocked by ISP) |
| `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/...` | HTTPS | 147 ms | 200 OK | **"API KEY REQUIRED" watermark** | `*` | **FAILED** (Unauthenticated watermark) |
| `https://server.arcgisonline.com/ArcGIS/rest/.../World_Street_Map/...` | HTTPS | 185 ms | 200 OK | Clean, but proprietary non-OSM cartography | `*` | **REJECTED** (Not pure OSM) |
| `https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png` | HTTPS | 210 ms | 200 OK | Clean, but strict Wikimedia robot policy | `*` | **RESERVED** |
| `https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png` | HTTPS | 220 ms | 200 OK | **Clean, no watermark, UTF-8 VN labels** | `*` | **PASSED** (OSM France) |
| `https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png` | HTTPS | 165 ms | 200 OK | **Clean, no watermark, high contrast for POIs** | `*` | **PASSED** (Humanitarian OSM) |

---

## Decision

1. **Adopt OpenStreetMap Humanitarian (HOT) Basemap Tiles:**  
   Configure `flutter_map` `TileLayer` to use:  
   `urlTemplate: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png'`  
   with `subdomains: ['a', 'b', 'c']`.

2. **Configure OpenStreetMap France (OSM-FR) Fallback:**  
   Configure `fallbackUrl: 'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png'` ensuring fault-tolerant redundancy if any tile request fails.

3. **Style Selection Rationale:**  
   Humanitarian OpenStreetMap Team (HOT) style is designed for high visual contrast: soft road and background colors make GoMate's custom category markers (attractions, dining, accommodation, culture, beach, nature) stand out prominently without visual competition from busy map text.

4. **Separation of Basemap and Place Data:**  
   The basemap provides geographical context only. All POI places and marker data originate exclusively from the local PostgreSQL/PostGIS database via NestJS `/places/nearby` (`verifiedOnly=true`).

5. **Attribution Requirement:**  
   Display attribution on the map surface via `RichAttributionWidget`:  
   - `© OpenStreetMap contributors`  
   - `Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France`

---

## Consequences

- **Positive:** Resolves the grey map tile failure across all environments (Web and Mobile).
- **Positive:** **Completely eliminates the "API KEY REQUIRED" watermark** with clean, unencumbered raster cartography.
- **Positive:** 100% genuine OpenStreetMap data, maintaining full provenance and academic integrity.
- **Positive:** Zero API key configuration required; no risk of secret exposure.
- **Positive:** High availability and fault tolerance via dual HOT/OSM-FR endpoints.
- **Positive:** Full CORS support (`Access-Control-Allow-Origin: *`) for Flutter Web.
