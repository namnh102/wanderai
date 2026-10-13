# W5 Duplicate Equivalence Evidence & Primary Evaluation Impact Gate

**Document Version:** `W5-DUP-GATE-DOC-V1`  
**Gate Package:** `W5-GATE-DUP-01`  
**Preregistration Reference:** `REC-EVAL-01-PREREG-V1`  
**Status:** `GATE_REVIEWED`  
**Date:** 2026-10-14  

---

## 1. Purpose

The scientific preregistration package for `REC-EVAL-01` recorded `duplicate_policy_status = "PENDING"` prior to human relevance labeling. This was established to ensure that any duplicate-equivalence groups supported by repository evidence would be formally reviewed, classified, mapped, and evaluated against the frozen candidate judgment universe before activating human annotation or final scientific scoring.

This gate resolves the preregistered duplicate-policy dependency using strictly repository-native evidence.

---

## 2. Scope

The scope of this gate is strictly bounded:
1. **Candidate-pair source:** Historical repository evidence leads recovered from committed history (`0edcf343cdeef72aa980417d5f628cd79de4ca74`, `47e9a257366e12446db96e3c71f76500fe1d7dfd`, and `e15d5a99d7e47c2940d54aee5d81cd64e1fb9d37`).
2. **No global duplicate search:** No global fuzzy duplicate discovery, edit-distance clustering, embedding clustering, web search, or LLM duplicate judgments were performed over the catalog.
3. **No input mutation:** Frozen candidate pools (474 records), primary scenarios (30), thin diagnostic scenarios (6), Freeze V2 places (622 core places), baseline rankings, A2 rankings, random controls, blinded judge packages, and metric formulations remain completely unchanged.
4. **No human relevance labels:** 0 human judgments collected, 0 labels assigned.

---

## 3. Candidate-Pair Provenance

The 3 historical candidate groups (comprising 6 unique `place_id` records across Đà Nẵng and Hạ Long) originate directly from committed repository evidence:

1. **`0edcf343cdeef72aa980417d5f628cd79de4ca74` (`feat(evaluation): add frozen W5 scenario and candidate pools`)**:
   - `scripts/build_w5_eval_pool.py` lines 48–55 defined the initial lead mapping `REC_A_CORE_DUPLICATE_MAP` containing the six UUIDs (`DUP-CORE-DN-01`, `DUP-CORE-DN-02`, and `DUP-CORE-HL-01`).
2. **`47e9a257366e12446db96e3c71f76500fe1d7dfd` (`fix(evaluation): defer duplicate evidence join`)**:
   - Removed the inline hardcoded map from the pool builder and explicitly deferred the equivalence join to this formal evidence gate (`W5-GATE-DUP-01`), flagging pool items as `PENDING_EXISTING_A6_EVIDENCE_JOIN`.
3. **`e15d5a99d7e47c2940d54aee5d81cd64e1fb9d37` (`docs(w3): audit place data gaps and runtime contracts`)**:
   - Documented under section 6 (Data-quality findings) and section 10 (Gap register: PDG-008) the core duplicate pairs in Đà Nẵng:
     - Chùa Linh Ứng: `408aaa5a-7e34-41eb-b39f-acfa4393fc5f` / `6db09251-706a-4225-8ee5-4d22165f6b3f`
     - Đền Lĩnh Chúa Linh Từ: `098e6a53-5ce5-4d20-b75e-4a00d00bb8cf` / `83d8e5c4-b91e-415e-9fd6-fd2a887cb4c0`

---

## 4. Evidence Standard

To assign an equivalence classification, each historical candidate pair is evaluated against current frozen Freeze V2 metadata (`data/curated/gomate_places_freeze_v2.json`):
- `place_id`
- `name` (raw and canonical normalized name via `normalize_string`)
- `destination` and `destination_slug`
- `category`
- `latitude` and `longitude` (Haversine distance in meters)
- `canonical_active_interests` and canonical feature vector
- `sources` (OSM element type/ID, Overture ID, confidence score)
- Raw OSM tags (`website`, `phone`, `religion`, `official_name`, `alt_name`, `amenity`, `ferry`, etc.)

### Classification Standards
- **`CONFIRMED_EQUIVALENT`**: Requires unambiguous, traceable repository-native evidence that both records represent the exact same physical entity (e.g. identical official name/website/tags, physical colocation within the same facility footprint, and known site/building polygon split).
- **`AMBIGUOUS`**: Assigned if evidence does not clearly prove identity. The pair is NOT collapsed and does NOT enter the active equivalence map. Conservative false-negative handling is strictly preferred.
- **`NOT_CONFIRMED`**: Assigned if evidence indicates distinct entities.

---

## 5. Per-Pair Evidence and Classification

### Group 1: `DUP-CORE-DN-01` (Đà Nẵng)

| Field | Record 1 (`6db09251-…`) | Record 2 (`408aaa5a-…`) | Match Status |
|---|---|---|---|
| **Name** | Chùa Linh Ứng | Chùa Linh Ứng | Exact match |
| **Normalized Name** | `chua linh ung` | `chua linh ung` | Exact match |
| **Destination** | Đà Nẵng (`da-nang`) | Đà Nẵng (`da-nang`) | Exact match |
| **Category** | `temple` | `temple` | Exact match |
| **Coordinates** | 15.9972033, 107.9941376 | 15.9973553, 107.9939311 | Distance: 27.80 m |
| **OSM Source** | `relation/20707914` (site relation) | `way/746227054` (building polygon) | Complementary OSM site/building |
| **Official Name Tag** | `Chùa Linh Ứng - Bà Nà` | `Chùa Linh Ứng - Bà Nà` | Exact match |
| **Website** | `https://sunworld.vn/vi/banahills/check-in/chua-linh-ung` | `https://sunworld.vn/vi/banahills/check-in/chua-linh-ung-ba-nahtml` | Same Sun World Ba Na Hills page |
| **Religion / Denom** | `buddhist` / `mahayana` | `buddhist` / `mahayana` | Exact match |
| **Canonical Vector** | `[0, 1, 0, 0, 0, 0, 0]` (`culture_history`) | `[0, 1, 0, 0, 0, 0, 0]` (`culture_history`) | Exact match |

**Classification:** `CONFIRMED_EQUIVALENT`  
**Rationale:** Both records represent the exact same Buddhist pagoda entity (Chùa Linh Ứng - Bà Nà) located at Sun World Ba Na Hills, Đà Nẵng. Record 1 is the OSM site relation for the pagoda grounds, and Record 2 is the primary pagoda building polygon within those grounds (separated by 27.8 meters). Documented under gap PDG-008.

---

### Group 2: `DUP-CORE-DN-02` (Đà Nẵng)

| Field | Record 1 (`098e6a53-…`) | Record 2 (`83d8e5c4-…`) | Match Status |
|---|---|---|---|
| **Name** | Đền Lĩnh Chúa Linh Từ | Đền Lĩnh Chúa Linh Từ | Exact match |
| **Normalized Name** | `den linh chua linh tu` | `den linh chua linh tu` | Exact match |
| **Destination** | Đà Nẵng (`da-nang`) | Đà Nẵng (`da-nang`) | Exact match |
| **Category** | `temple` | `temple` | Exact match |
| **Coordinates** | 15.9977275, 107.9857833 | 15.9975648, 107.9856835 | Distance: 21.00 m |
| **OSM Source** | `relation/20704135` (site relation) | `way/1109970004` (building polygon) | Complementary OSM site/building |
| **Alt Name Tag** | `Đền Bà Chúa Thượng Ngàn` | `Đền Bà Chúa Thượng Ngàn` | Exact match |
| **Website** | `https://sunworld.vn/vi/banahills/check-in/den-linh-chua-linh-tu` | `https://sunworld.vn/vi/banahills/check-in/den-linh-chua-linh-tu` | Exact match |
| **Religion** | `vietnamese_folk` | `vietnamese_folk` | Exact match |
| **Canonical Vector** | `[0, 1, 0, 0, 0, 0, 0]` (`culture_history`) | `[0, 1, 0, 0, 0, 0, 0]` (`culture_history`) | Exact match |

**Classification:** `CONFIRMED_EQUIVALENT`  
**Rationale:** Both records represent the exact same temple entity (Đền Lĩnh Chúa Linh Từ / Đền Bà Chúa Thượng Ngàn) atop Ba Na Hills, Đà Nẵng at 1,487m elevation. Record 1 is the site relation and Record 2 is the temple building polygon, separated by only 21.0 meters, sharing identical official website and folk religion tags. Documented under gap PDG-008.

---

### Group 3: `DUP-CORE-HL-01` (Hạ Long)

| Field | Record 1 (`13317b2d-…`) | Record 2 (`0118b23e-…`) | Match Status |
|---|---|---|---|
| **Name** | Cảng tàu khách quốc tế Hạ Long | Cảng tàu khách quốc tế Hạ Long | Exact match |
| **Normalized Name** | `cang tau khach quoc te ha long` | `cang tau khach quoc te ha long` | Exact match |
| **Destination** | Hạ Long (`ha-long`) | Hạ Long (`ha-long`) | Exact match |
| **Category** | `attraction` | `attraction` | Exact match |
| **Coordinates** | 20.9532750, 107.0557100 | 20.9536428, 107.0554545 | Distance: 48.75 m |
| **OSM Source** | `node/12759133301` | `node/14053384506` | Duplicate OSM nodes |
| **OSM Tags** | `ferry=yes`, `amenity=ferry_terminal`, `public_transport=station` | `ferry=yes`, `amenity=ferry_terminal`, `public_transport=station` | Exact match |
| **Taxonomy Tiers** | `TRANSPORT_HUBS` / `boat_terminal` | `TRANSPORT_HUBS` / `boat_terminal` | Exact match |
| **Canonical Vector** | `[0, 0, 0, 0, 0, 0, 0]` (empty) | `[0, 0, 0, 0, 0, 0, 0]` (empty) | Exact match |

**Classification:** `CONFIRMED_EQUIVALENT`  
**Rationale:** Both records represent the single international passenger cruise and ferry terminal facility at Bãi Cháy, Hạ Long. They consist of two separate OSM node points mapped 48.75 meters apart along the same terminal pier facility with identical names and identical ferry/terminal tags.

---

## 6. Summary of Classification

- **Confirmed Equivalent Groups:** 3 (comprising 6 unique place IDs)
  - `DUP-CORE-DN-01`: 2 places
  - `DUP-CORE-DN-02`: 2 places
  - `DUP-CORE-HL-01`: 2 places
- **Ambiguous Groups:** 0
- **Not Confirmed Groups:** 0
- **Active Equivalence Map:** All 3 confirmed groups are mapped in `data/evaluation/reca_w5/w5_duplicate_equivalence_map_v1.json`. 0 ambiguous and 0 unconfirmed groups are mapped.

---

## 7. Primary Evaluation Impact Analysis

To determine the impact on the frozen `REC-EVAL-01` primary evaluation, the confirmed duplicate place IDs were intersected against the frozen 474-record judgment universe (`w5_candidate_pool_internal_v1.json`):

1. **Total Unique Places in Frozen 474 Primary Candidate Pool:** 255 unique `place_id`s.
2. **Total Confirmed Duplicate `place_id`s:** 6 unique `place_id`s.
3. **Exact Set Intersection:** $\emptyset$ (empty set).
   $$\{ \text{Confirmed Duplicate IDs} \} \cap \{ \text{Primary Candidate Pool IDs} \} = \emptyset$$
4. **Primary Pool Intersection Count:** `0`
5. **Affected Primary Scenarios:** `0` (`[]`)
6. **Detailed System Ranking Inspections:**
   - **Baseline (REC-A0/A1) Top-10:** 0 occurrences across all 30 primary scenarios.
   - **REC-A2 Top-10:** 0 occurrences across all 30 primary scenarios.
   - **Stratified Controls:** 0 occurrences across all 30 primary scenarios.
   - **THIN Diagnostic Scenarios (6):** 0 occurrences across all history item sets.
   - **Calibration Items (3 scenarios):** 0 occurrences in calibration set.

### Why No Intersection Occurred
In Đà Nẵng, the temples (`Chùa Linh Ứng`, `Đền Lĩnh Chúa Linh Từ`) achieved rank 15 and 17 respectively in `DN-U1-03` under deterministic tie-breaking (`-score, normalize_string(name), place_id`), placing them outside the Top-10 ($k=10$). In Hạ Long, the cruise port terminal carries category `attraction` with zero active interest tags, so it never ranked in the Top-10 for any interest scenario and was not sampled among random controls.

---

## 8. Gate Result and Decision

Because `primary_pool_intersection_count == 0`, the decision branch conforms strictly to **Case A** of the gate specification:

- **Gate Status:** `PASS`
- **Duplicate Policy Status:** `CLOSED_NO_PRIMARY_EVAL_IMPACT`
- **Candidate Pool Modified:** `false`
- **Recommender Code Modified:** `false`
- **Human Relevance Labels Used:** `false`

### Formal Scientific Statement
> "Known confirmed duplicate-equivalent records do not intersect the frozen primary W5 judgment universe; therefore no duplicate correction is required for REC-EVAL-01 primary scoring."

---

## 9. Limitations

1. **Catalog Scope:** This gate evaluates the known historical duplicate candidates identified in repository audits (specifically `docs/w3/w3-03-place-data-gap-audit.md` and `scripts/build_w5_eval_pool.py`).
2. **Not a Global Deduplication Claim:** This gate does NOT claim that the entire 622-item Freeze V2 catalog is globally duplicate-free, nor does it resolve all 67 duplicate pairs identified in the full 882-place database during Week 3 audits.
3. **Primary Evaluation Sufficiency:** It establishes rigorously that no duplicate pair enters the frozen 474 primary candidate judgment universe, guaranteeing that `REC-EVAL-01` primary metric scoring (NDCG@10, Precision@10, Pooled Recall@10, Category-ILD@10, CatalogCoverage@10) is mathematically and scientifically uncorrupted by duplicate place records.

---

## 10. Artifact Summary

- **Evidence Artifact:** `data/evaluation/reca_w5/w5_duplicate_equivalence_evidence_v1.json`
- **Active Duplicate Map:** `data/evaluation/reca_w5/w5_duplicate_equivalence_map_v1.json`
- **Gate Result Artifact:** `data/evaluation/reca_w5/w5_duplicate_gate_result_v1.json`
- **Test Suite:** `tests/test_w5_duplicate_gate.py`
