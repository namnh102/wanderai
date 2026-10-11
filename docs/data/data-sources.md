# Data Sources & Ingestion Policy — WanderAI (GoMate)

## 1. Ethical & Legal Data Source Policy

WanderAI strictly enforces the following principles regarding travel and user data:

1. **No Unauthorized Scraping**: We do NOT scrape restricted commercial services (e.g. Google Maps, Booking.com, TripAdvisor, Agoda, TikTok) whose Terms of Service forbid automated data extraction.
2. **Open Data First**: We prioritize officially licensed open datasets, primarily:
   - **OpenStreetMap (OSM)**: Open Database License (ODbL) for accurate geographic locations, addresses, and tourism points of interest.
   - **Open-Meteo**: Free weather forecasting API for runtime atmospheric conditions.
   - **Academic Research Benchmarks**: CC BY 4.0 licensed datasets for sentiment analysis and traveler reviews.
3. **Data Provenance & Traceability**: Every real-world place record is linked to a source through `place_sources`. Raw payloads, source IDs, confidence scores, and timestamps are preserved.
4. **Synthetic Data Quarantine**: Pre-generated AI demo records are clearly flagged (`generated=true, trusted=false`) and isolated in `data/seed/` for UI mocking only. They are never commingled with verified geographic records without explicit provenance.

---

## 2. Approved Sources Registry

| Source Name | Data Type | License | Official URL | Permitted Usage | Storage Permission | Collection Method | Collection Date | Transformation Steps | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenStreetMap Vietnam** | Geographic POIs | ODbL 1.0 | https://overpass-api.de | Search, Map, Routing, Recommendations | Yes (with attribution) | Overpass API / spatial bounding box query | 2026-10-01 | JSON -> Tag extraction -> Category mapping -> Coordinate bounds check -> Entity resolution | Canonical source for real places and GPS |
| **Internal Review Test Fixtures (Unverified)** | Pipeline Test Data | UNKNOWN / UNVERIFIED | None (Internal) | Integration testing of ETL pipeline only. Prohibited for Review AI | Quarantined | Handcrafted test fixtures | 2026-10-01 | Text cleaning -> Rating normalization -> Linking test | UNVERIFIED test fixtures. Previous UIT-VSFC claim retracted as UIT-VSFC is student feedback, not travel reviews. |
| **Open-Meteo API** | Weather Forecast | Free / CC BY 4.0 | https://api.open-meteo.com | Real-time weather context for AI Agent | No (Runtime only) | REST API by coordinates | Runtime dynamic | JSON forecast -> Text summary | Free API, no key required |
| **Reference Categories** | Taxonomy | Open | Internal | Category filtering and taxonomy | Yes | Internal schema definition | 2026-09-01 | Direct seed into `place_categories` | 10 base categories |
| **User Generated Content** | Reviews & Videos | GoMate ToS | Application internal | All platform features | Yes | Mobile app submissions | Continuous | User verification & moderation | Future phase |

---

## 3. Prohibited Sources & Anti-Patterns

| Prohibited Source | Reason | Policy Enforcement |
| :--- | :--- | :--- |
| **Google Maps HTML Scraping** | Violates Google ToS Section 3.2.3 | Strictly prohibited. Use OSM for POI data. |
| **TikTok Video Download** | Violates Copyright and TikTok ToS | Strictly prohibited. |
| **Booking.com / Agoda Scraping** | Violates ToS and rate limiting | Strictly prohibited. Use academic CC-BY datasets for reviews. |
| **Arbitrary Uncredited Web Crawling** | Legal risk and untraceable provenance | All imported data must trace back to an authorized manifest entry. |

---

## 4. Provenance Record Schema (`place_sources`)

In PostgreSQL, every imported place record is registered in `place_sources`:

```sql
CREATE TABLE place_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id UUID NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    source_name VARCHAR(50) NOT NULL,   -- 'osm', 'google_places', 'manual'
    source_id VARCHAR(255) NOT NULL,    -- 'node/12345678', 'way/9876543'
    raw_name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    raw_data JSONB,
    confidence_score DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_place_sources UNIQUE (source_name, source_id)
);
```

This ensures full idempotency: re-running ingestion pipelines updates records in-place without duplicating canonical places.
