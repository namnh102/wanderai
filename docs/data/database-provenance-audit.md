# Database Provenance Audit Report

**Audit Date:** 2026-10-01T17:25:00+07:00  
**Target Environment:** Local PostgreSQL Development Database (`wanderai_db`)  
**Auditor:** GoMate Data Integrity & Provenance Auditor  

---

## 1. Executive Summary

| Table | Total Rows | Verified Canonical | Legacy / Synthetic | Unverified | Notes |
|:---|:---|:---|:---|:---|:---|
| `destinations` | **50** | 50 (Geographic baselines) | 0 | 0 | Prototyped across northern, central, and southern Vietnam |
| `place_categories` | **12** | 12 (Core taxonomy) | 0 | 0 | Standardized category taxonomy |
| `places` | **220** | **108** | **112** | 0 | 108 OSM canonical vs 112 legacy seed places |
| `place_sources` | **110** | **110** | 0 | 0 | Lineage tracking linked to 108 canonical places |
| `reviews` | **9** | **0** | **9** (Test fixtures) | 9 | 1 legacy seed + 8 pipeline test fixtures |
| `review_aspects` | **16** | **0** | **16** (Test fixtures) | 16 | Aspect ratings attached to the 8 test reviews |

---

## 2. Places Breakdown (220 Total Records)

### Category A: Verified Canonical Places (108 records, 49.1%)
- **Source:** OpenStreetMap Overpass API (ODbL 1.0)
- **Provenance:** Every record has at least 1 verified entry in `place_sources` with external OSM ID (e.g. `node/268491823`, `node/859302194`).
- **Entity Resolution:** 106 single-source canonical places + 2 multi-source resolved canonical places (total 110 sources).
- **Status:** `VERIFIED_CANONICAL` (Production Ready).

### Category B: Legacy Seed Places (112 records, 50.9%)
- **Source:** `database/seed/places.json` / `data/seed/synthetic_places.json`
- **Provenance:** 0 entries in `place_sources` (`placeSources.length === 0`).
- **Destination Distribution:**
  - Hà Nội: 12
  - Đà Nẵng: 8
  - Hội An: 8
  - TP. Hồ Chí Minh: 8
  - Phú Quốc: 8
  - Đà Lạt: 8
  - Sapa: 8
  - Huế: 8
  - Hạ Long: 6
  - Nha Trang: 6
  - Hà Giang: 6
  - Ninh Bình: 6
  - Phong Nha: 4
  - Quy Nhơn: 4
  - Cần Thơ: 4
  - Mũi Né: 4
  - Côn Đảo: 4
- **Status:** `LEGACY_SYNTHETIC` (Development Seed Only).
- **Action:** Must be tagged or filtered so they are not served as verified production canonical records.

---

## 3. Reviews Audit (9 Records)

- **Total Reviews:** 9
  - 1 legacy seed review (`rev_initial_001` created by `seed.ts` on legacy place)
  - 8 reviews imported via `prisma/import-curated.ts`
- **Claimed Provenance:** "UIT-VSFC & Mendeley Open Research Data (CC BY 4.0)"
- **Audit Findings:**
  - UIT-VSFC is the *Vietnamese Students' Feedback Corpus* (University course sentiment analysis), NOT tourism or hotel reviews.
  - The review text was authored during development as test fixtures.
  - No external academic corpus was downloaded.
- **Classification:** `SYNTHETIC_TEST_FIXTURE` (Unverified).
- **Compliance Directive:**
  - Must NOT be used to train Review AI or extract tourist sentiment for production recommendations.
  - Kept as integration test fixtures only until genuine travel review datasets are ingested under an audited open license.

---

## 4. Preservation & Non-Destructive Policy
Per engineering invariants, NO database records have been deleted destructively. The separation between `VERIFIED_CANONICAL` (places with `place_sources`) and `LEGACY_SYNTHETIC` (places without `place_sources`) is enforced via query filtering and metadata flags.
