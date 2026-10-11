# GoMate Da Nang Overture Places Cross-Check Report (v2)

**Task:** MVP-SCOPE-01  
**Destination:** Đà Nẵng  
**Release Pinned:** 2026-09-23.1 (Schema v2.0.0)  
**Artifacts:**
- [`data/raw/overture/overture_danang_2026-09-23.1.parquet`](file:///d:/Do_an/wanderai/data/raw/overture/overture_danang_2026-09-23.1.parquet) (8,595,564 bytes, 65,688 records)
- [`data/curated/overture/danang_overture_crosscheck_v2.json`](file:///d:/Do_an/wanderai/data/curated/overture/danang_overture_crosscheck_v2.json)
- [`data/curated/overture/danang_overture_crosscheck_summary_v2.json`](file:///d:/Do_an/wanderai/data/curated/overture/danang_overture_crosscheck_summary_v2.json)

---

## 1. Objectives & Boundaries

Overture Maps Places serves exclusively as a **secondary provenance and quality cross-check source**. In accordance with thesis data contracts:
1. Canonical place identities, physical geometries, and core factual attributes are rooted solely in **OpenStreetMap**.
2. Overture records never overwrite OSM attributes or replace OSM IDs.
3. Auxiliary linkage occurs only under strict mathematical thresholds and explicit license verification.
4. **Zero Fallback Licensing:** Defaulting unverified licenses to CDLA Permissive 2.0 is strictly prohibited. Unresolved licenses are classified as `LICENSE_UNRESOLVED` and barred from automated linking.

---

## 2. Methodology & Matching Thresholds

A spatial grid index ($0.002^\circ \times 0.002^\circ \approx 220\text{m}$) was constructed over the 65,688 bounded Overture Places records.

### Matching Gates:
- **Candidate Condition:**
  $$\text{Distance} \le 150\text{m} \quad \land \quad (\text{Jaro-Winkler} \ge 0.85 \lor \text{Token Sort} \ge 0.88) \quad \land \quad \text{Category Compatible}$$
- **AUTO-LINK Gate (Database Provenance Link):**
  $$\text{Distance} \le 50\text{m} \quad \land \quad \text{Similarity} \ge 0.90 \quad \land \quad \text{Category Compatible} \quad \land \quad \text{Operating Active} \quad \land \quad \text{Approved License}$$
- **Approved License Set:**
  $$\mathcal{L}_{\text{approved}} = \{\text{CDLA Permissive 2.0}, \text{Apache 2.0}, \text{CC0 1.0}\}$$

---

## 3. Results & Cross-Check Statistics

Across the 2,497 normalized Da Nang OSM candidates:

| Classification | Count | Percentage | Action Taken |
| :--- | :--- | :--- | :--- |
| **AUTO_LINK** | **549** | **22.0%** | Eligible for auxiliary provenance record in `place_sources`. |
| **MANUAL_REVIEW_CANDIDATE** | 504 | 20.2% | Candidate logged for research review; no database mutation. |
| **UNMATCHED** | 1,444 | 57.8% | Preserved purely under canonical OSM provenance. |
| **LICENSE_UNRESOLVED** | 0 | 0.0% | Zero unresolved license anomalies detected. |
| **OPERATING_CONFLICTS** | 0 | 0.0% | Zero active OSM POIs marked closed by Overture. |
| **Total Candidates Evaluated** | **2,497** | **100.0%** | Full coverage of fresh candidate stream. |

### License Resolution Breakdown (Matched Candidates):
- **CDLA Permissive 2.0:** 1,025 records
- **Apache 2.0; CDLA Permissive 2.0:** 24 records
- **CC0 1.0; CDLA Permissive 2.0:** 4 records

---

## 4. Operating Status Conflict Protocol

If an Overture record is marked `permanently_closed` while the corresponding OSM entity remains active, the protocol specifies:
$$\text{Status} \rightarrow \text{SOURCE\_CONFLICT\_REVIEW\_REQUIRED}$$
In this Da Nang execution, zero operating status conflicts were encountered.
