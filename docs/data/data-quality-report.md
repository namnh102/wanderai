# Data Quality Report — Real Travel Pipeline

**Generated:** 2026-10-01 16:56:04  
**Pipeline Scope:** OpenStreetMap POIs & CC BY 4.0 Travel Reviews

---

## 1. Executive Summary
- **Canonical Places Evaluated:** 108
- **Curated Reviews Evaluated:** 9
- **Coordinate Integrity:** 100.0% within Vietnam national bounds
- **Source Provenance Coverage:** 100.0% traceable to authoritative external IDs
- **Review Linking Rate:** 88.9% auto-linked to canonical entities

---

## 2. Canonical Places Quality Metrics

| Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- |
| Total Canonical Places | $\ge 100$ | **108** | PASS |
| Missing Place Names | 0 | **0** | PASS |
| Missing Coordinates | 0 | **0** | PASS |
| Out of Bounds Coordinates | 0 | **0** | PASS |
| Coordinate Validity Rate | 100% | **100.0%** | PASS |
| Missing Source Lineage | 0 | **0** | PASS |
| Source Provenance Rate | 100% | **100.0%** | PASS |
| Duplicate Geo Clusters (<10m) | $\le 5$ | **0** | PASS |
| Invalid Categories | 0 | **0** | PASS |
| Rating Range Violations | 0 | **0** | PASS |

### Geographic Bounding Box Check:
- Latitude: $[8.18, 23.39]$
- Longitude: $[102.14, 109.46]$
- Result: **All points strictly within territory.**

---

## 3. Curated Reviews Quality Metrics

| Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- |
| Total Reviews | $\ge 5$ | **9** | PASS |
| Missing Content | 0 | **0** | PASS |
| Content Length (< 10 chars) | 0 | **0** | PASS |
| Rating Range ($[1.0, 5.0]$) | 100% | **9 / 9** | PASS |
| Auto-Linked to Place UUID | $\ge 80\%$ | **8 (88.9%)** | PASS |
| Review Queue Pending | Flagged | **0** | OK |
| Unmatched Isolated | Quarantined | **1** | OK |

---

## 4. Synthetic Data Isolation Verification
- **Synthetic Files Directory:** `data/seed/synthetic_destinations.json`, `data/seed/synthetic_places.json`
- **Curated Files Directory:** `data/curated/places_canonical.json`, `data/curated/reviews_curated.json`
- **Cross-contamination Check:** ZERO synthetic records present in curated production datasets.
