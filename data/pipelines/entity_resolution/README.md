# Entity Resolution Pipeline

## Overview
The Entity Resolution pipeline merges multiple heterogeneous data sources into GoMate Canonical Places while preserving data provenance.

## Candidate Matching Signals
1. **Name Similarity ($w=0.50$)**: Token Jaccard similarity + accent-insensitive phonetics + substring match.
2. **Geographic Proximity ($w=0.35$)**: Haversine distance in meters:
   - $\le 50$m $\implies 1.0$
   - $\le 200$m $\implies 0.85$
   - $\le 500$m $\implies 0.65$
   - $\le 1000$m $\implies 0.35$
   - $> 1000$m $\implies 0.0$
3. **Category Taxonomy Alignment ($w=0.15$)**: Exact category match = 1.0; compatible group = 0.6; mismatch = 0.0.

## Decision Thresholds
- **$\ge 0.80$ (High Confidence Match)**: Automatically merge as an additional source record under the canonical place.
- **$0.60 \le \text{Score} < 0.80$ (Review Needed)**: Candidate flagged for human inspection.
- **$< 0.60$ (Unmatched)**: Create new GoMate canonical place with a unique UUID.

## Output
- `data/curated/places_canonical.json`: Validated canonical places with source lineage.
- `data/curated/entity_resolution_report.json`: Statistics report on match distribution.
