# Data Sources Registry — WanderAI

## Approved Data Sources

| Source | Type | License | URL | Data Provided | Storage Permitted | Collection Method |
|--------|------|---------|-----|---------------|-------------------|-------------------|
| OpenStreetMap | Geographic | ODbL (Open) | https://overpass-api.de | Destinations, Places, POIs, coordinates | Yes (with attribution) | Overpass API bulk query |
| Open-Meteo | Weather | Free, no key | https://api.open-meteo.com | Temperature, rain, wind, UV | Runtime only (no storage) | REST API at runtime |
| Mendeley CX Vietnamese Hotel Reviews | Reviews | CC BY 4.0 | https://data.mendeley.com | 10,000+ hotel reviews | Yes (with citation) | Download dataset |
| Kaggle Vietnam Tourism | Knowledge | Check license per dataset | https://kaggle.com | Travel guides, tips | If license permits | Download dataset |
| Unsplash | Images | Unsplash License | https://unsplash.com | Cover images | Hotlink only | REST API |
| User-generated | Mixed | Owned by GoMate | N/A | Reviews, videos, interactions | Yes | User upload |
| Faker.js | Test users | N/A | npm faker | Synthetic user profiles | Yes | Script generation |

## Prohibited Sources

| Source | Reason |
|--------|--------|
| Google Maps scraping | Violates ToS |
| TikTok video download | Copyright violation |
| Booking.com scraping | Violates ToS |
| Any web scraping without explicit API authorization | Legal risk |

## Data Provenance Template

Every dataset must record:
- **source:** Name of the data source
- **url:** Where the data was obtained
- **license:** License type and restrictions
- **collection_date:** When the data was collected
- **permitted_usage:** What the data can be used for
- **redistribution_restriction:** Whether data can be shared
- **transformation_steps:** How raw data was processed
