# ADR-002: Fake Seed Data Must Be Replaced

## Status
Accepted

## Context
Current seed data (50 destinations, 57 places) was AI-generated with approximate coordinates and fabricated ratings. The user explicitly requested real data multiple times.

## Problem
- Destination coordinates are approximate (city center, not specific POI)
- Ratings are fabricated (not from real reviews)
- Descriptions are AI-generated
- No data provenance metadata
- No `place_sources` table for tracking data origin
- Many destinations have 0 places (Moc Chau, Mai Chau, Cat Ba, Tam Dao, etc.)
- 0 reviews, 0 RAG documents

## Decision
1. Keep existing seed data temporarily for backend API testing
2. Build a real data pipeline using:
   - OpenStreetMap Overpass API (ODbL license) for destinations and places
   - Mendeley CX Vietnamese Hotel Reviews (CC BY 4.0) for reviews
   - Open-Meteo API for weather (runtime, no storage needed)
   - User-generated content for videos
3. Add `place_sources` table to Prisma schema
4. Create `docs/data/data-sources.md` with provenance metadata
5. Replace fake data incrementally as real data pipeline is built

## Consequences
- Data pipeline development becomes a prerequisite before AI features
- AI Planner and Recommendation will produce more accurate results
- Requires OSM Overpass API knowledge and ETL scripts
- Some destinations may have limited OSM data coverage
