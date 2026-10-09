# GoMate Da Nang OSM Fresh Collection Report (v2)

**Task:** MVP-SCOPE-01  
**Target Destination:** Đà Nẵng (Municipality Tourism Core)  
**Collection Date:** 2026-10-07  
**Status:** COMPLETE & FROZEN  

---

## 1. Collection Protocol & Network Safety

The fresh OpenStreetMap dataset collection for Da Nang was executed via the canonical upstream Overpass API:
- **Canonical Endpoint:** `https://overpass-api.de/api/interpreter`
- **User Agent:** `GoMate-Thesis-DataFoundation/1.0 (academic-reproducible-research; contact: thesis@wanderai.vn)`
- **Query File:** [`data/queries/osm/danang_v2.overpassql`](file:///d:/Do_an/wanderai/data/queries/osm/danang_v2.overpassql)
- **Geometry Format:** `out center meta;` (guarantees node/way/relation center coordinates, upstream version, changeset, timestamp, and metadata envelope).
- **Network Safety:** Executed with 120s timeout and exponential backoff retry. Attempt 1 received HTTP 504 gateway timeout; retry attempt 2 succeeded with HTTP 200 after 5s backoff. Zero mirror endpoints used.

---

## 2. Locked Bounding Box & Geographic Audit

The Da Nang tourism-core research bounding box was verified and locked:
$$\text{Bounding Box: } \text{South} = 15.95^\circ\text{N}, \text{West} = 107.95^\circ\text{E}, \text{North} = 16.20^\circ\text{N}, \text{East} = 108.35^\circ\text{E}$$

### 2.1. Spatial Inclusions & Landmark Coverage
- **Bà Nà Hills / Sun World Corridor:** Summit at $\sim (15.996^\circ\text{N}, 107.986^\circ\text{E})$, Cable Car base at $\sim (15.998^\circ\text{N}, 108.016^\circ\text{E})$ (Included).
- **Sơn Trà Peninsula / Linh Ứng Pagoda:** Peak at $\sim (16.119^\circ\text{N}, 108.278^\circ\text{E})$, Pagoda at $\sim (16.103^\circ\text{N}, 108.278^\circ\text{E})$ (Included).
- **Mỹ Khê & Coastal Tourism Zone:** Latitude $16.054^\circ\text{N} - 16.075^\circ\text{N}$, Longitude $108.243^\circ\text{E} - 108.254^\circ\text{E}$ (Included).
- **Ngũ Hành Sơn (Marble Mountains):** Latitude $\sim 16.002^\circ\text{N} - 16.007^\circ\text{N}$ (Included).
- **Hải Vân Pass (Southern Slope / Da Nang):** Latitude $\sim 16.19^\circ\text{N}$ (Included).
- **Hội An Ancient Town:** Latitude $\sim 15.880^\circ\text{N}$ (Strictly excluded; $15.880 < 15.95$).

---

## 3. Raw Snapshot Evidence & Provenance

| Metric / Parameter | Value / Artifact |
| :--- | :--- |
| **Raw JSON Artifact** | [`data/raw/osm/danang_2026-10-07_v2.json`](file:///d:/Do_an/wanderai/data/raw/osm/danang_2026-10-07_v2.json) |
| **Raw Artifact File Size** | 1,016,599 bytes |
| **Raw Element Count** | **2,497 elements** (nodes, ways, relations) |
| **Upstream `osm_base`** | `2026-10-07T15:18:56Z` |
| **Query Timestamp UTC** | `2026-10-07T15:20:56.380Z` |
| **Raw File SHA-256** | `f73b49124e5a09a834d5381febf3f5c5bcc5f5d6e343ef85d0650e3996cbcb47` |
| **Metadata File** | [`data/raw/osm/danang_collection_metadata_2026-10-07_v2.json`](file:///d:/Do_an/wanderai/data/raw/osm/danang_collection_metadata_2026-10-07_v2.json) |
| **License** | Open Database License (ODbL 1.0) |

---

## 4. Immutability Guarantee

The raw snapshot was cryptographically hashed immediately upon retrieval and is committed under Git tracking. No script or process may mutate or rewrite this raw payload.
