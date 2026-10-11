# OpenStreetMap (OSM) Travel POI Pipeline

## Overview
This pipeline ingests, validates, and normalizes geographic Points of Interest (POIs) across Vietnam from OpenStreetMap using the Overpass API.

## Data Provenance & License
- **Provider**: OpenStreetMap Contributors
- **License**: Open Database License (ODbL) 1.0
- **Attribution**: "© OpenStreetMap contributors"

## Pipeline Steps
1. **Collection (`collect_osm.py`)**:
   - Queries Overpass API for tourism, historic, beach, and restaurant POIs in Vietnam bounding boxes.
   - Saves raw elements to `data/raw/osm_vietnam_sample.json`.
2. **Parsing & Normalization (`parse_osm.py`)**:
   - Validates coordinates within Vietnam bounding box ($8.18 \le \text{lat} \le 23.39$, $102.14 \le \text{lon} \le 109.46$).
   - Maps OSM tags to GoMate category taxonomy.
   - Extracts bilingual names and structured addresses.
   - Saves normalized places to `data/processed/osm_places.json`.

## Usage
```bash
python data/pipelines/osm/collect_osm.py
python data/pipelines/osm/parse_osm.py
```
