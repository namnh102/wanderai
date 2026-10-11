# Review Processing & Linking Pipeline

## 1. Overview
The review processing pipeline cleans, normalizes, anonymizes, and deterministically links travel reviews from CC BY 4.0 academic research datasets to GoMate canonical places (`places.id`).

## 2. Directory Structure
```
data/pipelines/reviews/
├── clean_reviews.py   # Text validation, rating clamping, PII strip, aspect formatting
├── link_reviews.py    # Name similarity & city matching against places_canonical.json
└── README.md          # Pipeline documentation
```

## 3. Data Processing Steps
1. **Cleaning (`clean_reviews.py`):**
   - Filters out texts shorter than 10 characters.
   - Normalizes ratings to float within $[1.0, 5.0]$.
   - Extracts structured aspect sentiment tags (`aspect`, `score`, `comment`).
   - Writes to `data/processed/reviews_normalized.json`.

2. **Entity Linking (`link_reviews.py`):**
   - Compares review target name with canonical place names and alternate raw names from `place_sources`.
   - Applies Vietnamese diacritic normalization and token Jaccard similarity.
   - Adjusts score with city geographic alignment.
   - **Thresholding Strategy:**
     - $\ge 0.85$: `linked` — Authoritative UUID link (`place_id` assigned).
     - $0.60 - 0.84$: `review_queue` — Provisional link requiring manual curation.
     - $< 0.60$: `unmatched` — No match (`place_id = null`).
   - Writes to `data/curated/reviews_curated.json`.

## 4. Execution
```bash
# Step 1: Clean raw reviews
python data/pipelines/reviews/clean_reviews.py

# Step 2: Link reviews to canonical places
python data/pipelines/reviews/link_reviews.py
```
