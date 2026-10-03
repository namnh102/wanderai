# ADR-006: Reachable Basemap Tile Provider Selection (CARTO Voyager)

## Status

ACCEPTED

## Date

2026-10-04

## Context

In ADR-005, `flutter_map` with standard OpenStreetMap raster tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) was selected as the map rendering foundation.

During extensive testing (TASK 07.1 through TASK 07.4) and browser verification on Windows/Chrome, map tiles consistently failed to load, presenting a blank grey grid. Network diagnostics on 2026-10-04 revealed that `tile.openstreetmap.org` is DNS-blocked or connection-throttled on major Vietnamese telecommunications networks (VNPT, Viettel, FPT).

A dependable, reachable basemap tile provider is required that:
1. Is accessible from Vietnam without VPN or proxy workarounds.
2. Serves standard raster PNG tiles compatible with `flutter_map` `TileLayer`.
3. Preserves OpenStreetMap data consistency and academic reproducibility.
4. Requires no paid API keys for MVP/thesis evaluation.
5. Complies with open data attribution and licensing requirements.

---

## Empirical Benchmark & Evaluation

On 2026-10-04, HTTP HEAD and GET requests were executed directly from the project host environment:

| Candidate Endpoint | Protocol | Latency | Status Code | Content-Type | Result |
|---|---|---|---|---|---|
| `https://tile.openstreetmap.org/0/0/0.png` | HTTPS | — | Connect Refused | — | **FAILED** (Blocked) |
| `https://a.basemaps.cartocdn.com/rastertiles/voyager/0/0/0.png` | HTTPS | 582 ms | 200 OK | `image/png` | **PASSED** |
| `https://b.basemaps.cartocdn.com/rastertiles/voyager/0/0/0.png` | HTTPS | 147 ms | 200 OK | `image/png` | **PASSED** |
| `https://a.basemaps.cartocdn.com/light_all/0/0/0.png` | HTTPS | 118 ms | 200 OK | `image/png` | **PASSED** |
| `https://tiles.openfreemap.org/planet/0/0/0.png` | HTTPS | 790 ms | 200 OK | `application/octet-stream` | **INCOMPATIBLE** (Vector PBF) |
| `https://a.basemaps.cartocdn.com/rastertiles/voyager/13/6505/3671.png` (Hanoi) | HTTPS | 134 ms | 200 OK | `image/png` (2,049 bytes) | **PASSED** |

---

## Decision

1. **Adopt CARTO Voyager Basemap Tiles:**  
   Configure `flutter_map` `TileLayer` to use:  
   `urlTemplate: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'`  
   with `subdomains: ['a', 'b', 'c', 'd']`.

2. **Style Selection Rationale:**  
   CARTO Voyager is tailored for city navigation, points of interest, and travel visualization. Its balanced contrast ensures custom GoMate POI markers (attraction, restaurant, beach, etc.) remain visually prominent without clutter.

3. **Separation of Basemap and Place Data:**  
   The basemap provides geographical context only. All POI places and marker data originate exclusively from the local PostgreSQL/PostGIS database via NestJS `/places/nearby` (`verifiedOnly=true`).

4. **Attribution Requirement:**  
   Display attribution on the map surface via `RichAttributionWidget`:  
   - `© OpenStreetMap contributors`  
   - `© CARTO`

---

## Consequences

- **Positive:** Resolves the grey map tile failure across all environments (Web and Mobile).
- **Positive:** Extremely fast tile response (~140 ms) via globally distributed CDN.
- **Positive:** Zero API key configuration required for development and academic demonstration.
- **Positive:** Clean compliance with OpenStreetMap ODbL and CARTO basemap attribution guidelines.
- **Trade-off:** Free usage tier is subject to fair-use volume; production deployment at commercial scale would migrate to self-hosted raster tiles or an enterprise tile service plan.
