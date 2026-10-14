# W06 Scientific Measurement Contract V1 (`W06-MEASUREMENT-CONTRACT-01`)

- **Contract ID:** `W06-MEASUREMENT-CONTRACT-01`
- **Contract Version:** `1.1.0` (`FIX-01` hardened)
- **Base `develop` SHA:** `495ed4f731db723366a585617472795540e8a914`
- **Prerequisite Audit:** `W06-MEASUREMENT-AUDIT-01` (`CLOSED` — [`data/evaluation/w06/w06_measurement_capability_audit_v1.json`](../../data/evaluation/w06/w06_measurement_capability_audit_v1.json))
- **Contract Status:** `DRAFT_FOR_SCIENTIFIC_GATE`
- **Repository Mutation Scope:** `CONTRACT_ARTIFACTS_AND_TESTS_ONLY`
- **Scientific Results Generated:** `false`
- **Production Behavior Modified:** `false`
- **Scenarios Generated:** `false`
- **Preregistration Created:** `false`
- **Final Benchmark Executed:** `false`

---

## 1. Contract Purpose

This document freezes the formal scientific measurement semantics for Week 6 (`AGENT-EVAL-01: Itinerary Agent Constraint & Grounding Evaluation`) prior to any W06 planner/evaluator instrumentation, scenario generation, or preregistration. Every definition in this contract is grounded in the empirical evidence established by `W06-MEASUREMENT-AUDIT-01` and aligned with the locked thesis roadmap (`docs/roadmap/gomate-thesis-research-roadmap-v1.md`).

---

## 2. Benchmark Population & Catalog Scope

- **Roadmap Target Population:** `TOTAL = 100` benchmark trips / test prompts.
- **Primary Evaluation Catalog:** `REC-A-CORE-V2` subset (`is_rec_a_core_v2 == true`) in `data/curated/gomate_places_freeze_v2.json` (`622` verified POIs across 3 primary destinations):
  - `ha-noi` (Hà Nội): `145` core POIs
  - `da-nang` (Đà Nẵng): `289` core POIs
  - `ha-long` (Hạ Long): `188` core POIs
  - **Total Primary Catalog:** `622` POIs
- **Primary 100-Scenario Destination Allocation:**
  - `ha-noi`: `34` scenarios
  - `da-nang`: `33` scenarios
  - `ha-long`: `33` scenarios
  - **Total:** `34 + 33 + 33 = 100` scenarios
- **Rule on Non-Core Destinations:** Only `REC-A-CORE-V2` destinations (`ha-noi`, `da-nang`, `ha-long`) are permitted in the primary 100-scenario grounded benchmark.
- **Disposition of Existing Repository Scenarios (`data/evaluation/planner/*.json`):**
  - `eval_ha_giang_3d` (Hà Giang, `0` frozen catalog POIs): `LEGACY_OUT_OF_CATALOG_DIAGNOSTIC` — excluded from the primary 100-scenario grounded benchmark.
  - `eval_moc_chau_3d` (Mộc Châu, `0` frozen catalog POIs): `LEGACY_OUT_OF_CATALOG_DIAGNOSTIC` — excluded from the primary 100-scenario grounded benchmark.
  - `eval_da_nang_4d` (Đà Nẵng): `DESIGN_EVIDENCE_ONLY_PENDING_SCENARIO_FREEZE` — may be used as design evidence, but is **not** automatically counted in the final frozen 100 scenarios until a dedicated scenario-freeze task explicitly validates and freezes it (noting its current `required_keywords` entry `"Hội An"` refers to non-core POIs).

---

## 3. Controlled Grounding Item Universe (`POI_VISIT` vs `TRANSIT_ONLY`)

To prevent grounding-denominator gaming, the future itinerary item schema for final W06 benchmarking must enforce a controlled `activity_kind` vocabulary with **only two** allowed values:

1. **`POI_VISIT`:**
   - Represents a visit to or use of a specific physical place.
   - Canonical `place_id` is **REQUIRED** (`place_id` required iff `activity_kind == "POI_VISIT"`).
   - **Included** in the `Grounded POI Rate` denominator (`all_poi_visit_items`).
   - Destination correctness validation applies.
   - Canonical duplicate-POI validation applies.
2. **`TRANSIT_ONLY`:**
   - Represents pure movement/transit between POI visits.
   - Canonical `place_id` is not required.
   - **Excluded** from the `Grounded POI Rate` denominator.
   - **Anti-Gaming Rule:** `TRANSIT_ONLY` must **not** represent a named attraction, restaurant, cafe, museum, park, venue, or any other visitable POI.

- **No Other Activity Kinds:** No other `activity_kind` value may be introduced into the final benchmark without a preregistered contract amendment.
- **Fail-Closed Rule for Unknown / Missing `activity_kind`:** Any itinerary item in a final benchmark output with a missing or unknown `activity_kind` is classified as `INVALID_OR_SCHEMA_NONCOMPLIANT_ITEM`, fails closed (causes `CORE_SCENARIO_PASS = false`), and may **never** silently disappear from the grounding evaluation.

---

## 4. Primary Hard Measurement Dimensions

### A. `CATALOG_GROUNDING`
- **Grounding Criterion:** Every itinerary item with `activity_kind == "POI_VISIT"` is grounded **if and only if**:
  1. It contains a canonical `place_id` field, **and**
  2. That `place_id` exists in the frozen `REC-A-CORE-V2` evaluation catalog (`622` core POIs).
- **Strict Exclusion:** Free-text `place_name` string matching alone is **never** sufficient for grounding.
- **Item-Level Metric:**
  $$\text{Grounded POI Rate} = \frac{\text{valid grounded POI\_VISIT items}}{\text{all POI\_VISIT items}}$$
- **Scenario-Level Metric:** `ALL_POIS_GROUNDED` (`true` iff all items have valid controlled `activity_kind`, the itinerary contains $\ge 1$ `POI_VISIT` item, and every `POI_VISIT` item is canonically grounded).
- **Roadmap Scientific Target:** `100%` (`1.0`).

### B. `DESTINATION_CORRECTNESS`
- **Criterion:** For every grounded `POI_VISIT` item's `place_id`, its `destination_slug` in the frozen catalog must match the requested benchmark scenario's `destination_slug`.
- **Strict Exclusion:** No free-text name-string or substring destination inference is permitted.
- **Metrics:**
  - Item-level: `Destination-Correct POI Rate` (`destination_correct_poi_rate`)
  - Scenario-level: `scenario_destination_valid` (`true` iff all `POI_VISIT` items are grounded and belong to the requested destination).

### C. `DUPLICATE_POI`
- **Criterion:** Duplicate detection operates strictly on canonical `place_id` across `POI_VISIT` items (free-text alias equality is insufficient).
- **Default Policy:** The same `place_id` must not appear more than once across `POI_VISIT` items in a single itinerary unless a future scenario explicitly preregisters revisits as allowed.
- **Metrics:** `duplicate_poi_violation_count`, `duplicate_poi_violation_rate`.

### D. `SCHEDULE_VALIDITY`
- **Criterion:** For every timed activity:
  1. `start_time` and `end_time` must parse under the frozen `HH:MM` 24-hour format (otherwise `TIME_PARSE_INVALID`).
  2. `start_time < end_time` strictly (otherwise `TIME_INTERVAL_INVALID`).
  3. Within the same itinerary day, timed intervals must not overlap (`end_time_earlier <= start_time_later`; otherwise `SCHEDULE_OVERLAP`).
- **Metric:** `schedule_violation_rate`.
- **Scenario Pass Rule:** Scenario schedule passes if and only if zero `TIME_PARSE_INVALID`, zero `TIME_INTERVAL_INVALID`, and zero `SCHEDULE_OVERLAP` occur.

### E. `DAY_STRUCTURE`
- **Checks:**
  1. `expected_number_of_days` (`len(days) == requested_days`)
  2. `minimum_required_items_per_day` (`len(day.items) >= min_items_per_day` for every day)
- **Claim Boundary:** Structural completeness check only; does **not** imply semantic itinerary quality.

---

## 5. Budget Semantics (`ESTIMATED_BUDGET_COMPLIANCE`)

- **Empirical Audit Fact:** Structured real-world numeric POI price coverage in `gomate_places_freeze_v2.json` is `0 / 759` (`0.00%`; only `6 / 759` POIs carry raw `charge` tags).
- **Forbidden Claims:** W06 **must not** claim `REAL_WORLD_BUDGET_ACCURACY` or `PRICE_GROUNDING`.
- **Operational Definition (`ESTIMATED_BUDGET_COMPLIANCE`):** For scenarios specifying a user budget ceiling, the sum of the planner's own declared item `estimated_cost` values across the itinerary must satisfy:
  $$\sum_{d \in \text{days}} \sum_{i \in d.\text{items}} i.\text{estimated\_cost} \le \text{requested\_budget}$$
- **Metric:** `estimated_budget_violation_rate`.
- **Interpretation Boundary:** Measures only compliance of the planner's own declared cost estimates with the requested budget ceiling; it does **not** establish real-world price accuracy.
- **Engineering Check (`ARITHMETIC_SELF_CONSISTENCY`):** Retained as a separate engineering integrity check verifying that `day_cost` and `budget_analysis.estimated_cost` equal the sum of item `estimated_cost` values. Arithmetic self-consistency must never be combined with or reported as factual budget accuracy.

---

## 6. Opening Hours Semantics (`EVIDENCE_CONDITIONAL_HARD`)

- **Empirical Audit Fact:** `opening_hours` coverage in `gomate_places_freeze_v2.json` is `101 / 622` core POIs (`16.24%`), and no parser currently exists in the repository.
- **Tier Classification:** `EVIDENCE_CONDITIONAL_HARD`.
- **Three-State Per-Item Evaluation Contract:**
  - `COMPLIANT`: opening-hours evidence exists in the frozen catalog, is parseable, the scheduled visit interval and date/day-of-week are known, and the visit complies.
  - `VIOLATION`: opening-hours evidence exists in the frozen catalog, is parseable, the scheduled visit interval and date/day-of-week are known, and the visit conflicts with known hours.
  - `UNKNOWN`: required opening-hours evidence or parseability is absent.
- **Strict `UNKNOWN` vs Known `VIOLATION` Rules:**
  - `UNKNOWN`:
    - is **NOT** `PASS` (`COMPLIANT`) and **NOT** `VIOLATION`
    - must never be silently converted into either `COMPLIANT` or `VIOLATION`
    - is excluded from the denominator of `opening_hours_compliance_rate_on_evaluable_items`
    - does **NOT** by itself fail `CORE_SCENARIO_PASS` (remains neutral with respect to `CORE_SCENARIO_PASS`)
  - **Known `VIOLATION`:**
    - **MUST** cause `CORE_SCENARIO_PASS = false` (`opening_hours_known_violation_count == 0` is required for `CORE_SCENARIO_PASS`).
- **Required Scenario-Level & Aggregate Reported Quantities:**
  - `opening_hours_evaluable_items`
  - `opening_hours_unknown_items`
  - `opening_hours_evidence_coverage`
  - `opening_hours_compliance_rate_on_evaluable_items` (denominator = **only** `opening_hours_evaluable_items`)
  - `opening_hours_known_violation_count`
  - `opening_hours_evidence_status` $\in \{\text{FULLY\_EVALUABLE}, \text{PARTIALLY\_EVALUABLE}, \text{NO\_EVALUABLE\_EVIDENCE}\}$ (`NO_EVALUABLE_EVIDENCE` is never treated as opening-hours success).

---

## 7. Geographic & Routing Semantics

- **Empirical Audit Fact:** Catalog latitude/longitude coverage is `759 / 759` (`100%`), but zero road-network routing graphs, OSRM/Valhalla/GraphHopper matrices, or empirical travel-time datasets exist in the repository.
- **Dimension Classifications:**
  - `TRAVEL_TIME = NOT_EVALUABLE`
  - `ROUTE_DISTANCE = NOT_EVALUABLE`
  - `GEO_DISTANCE_PROXY = SECONDARY_DIAGNOSTIC_ONLY`
- **Naming Rule:** Any future straight-line Haversine calculation between grounded POI coordinates must be named strictly `GEO_DISTANCE_PROXY` (diagnostic only in `AGENT-EVAL-01` V1) and must **never** be labeled `travel time`, `route distance`, or `routing quality`.

---

## 8. Preference Satisfaction Semantics

- **Empirical Audit Fact:** All `300` preference records (`preferences_n300_seed42.json` / `synthetic_preferences_v1.jsonl`) have `isSynthetic == true` (`0` independently verified real-user preference ground-truth records).
- **Classification:** `PREFERENCE_SATISFACTION = NOT_PRIMARY_EVALUABLE`.
- **Allowed Uses of Synthetic Profiles:** Scenario construction, engineering diagnostics, and coverage analysis.
- **Forbidden Claims:** Real-user preference satisfaction, user utility, or user acceptance. No LLM-as-judge may be used as a substitute for human preference ground truth.

---

## 9. Primary Scenario Pass (`CORE_SCENARIO_PASS`), Invalid Run Denominator & Hard Grounding Gate

### `CORE_SCENARIO_PASS`
A scenario achieves `CORE_SCENARIO_PASS = true` **if and only if** all conditions hold simultaneously:
1. The benchmark run itself is `VALID` (not mock/fallback, no API/parse error, complete metadata).
2. All itinerary items have a valid controlled `activity_kind` (`POI_VISIT` or `TRANSIT_ONLY`; zero `INVALID_OR_SCHEMA_NONCOMPLIANT_ITEM`).
3. Required `DAY_STRUCTURE` passes (expected day count and minimum items per day).
4. All `POI_VISIT` items are canonically grounded (`ALL_POIS_GROUNDED == true`).
5. All grounded `POI_VISIT` items belong to the requested destination (`scenario_destination_valid == true`).
6. Canonical `DUPLICATE_POI` policy passes (`duplicate_poi_violation_count == 0` under default policy).
7. `SCHEDULE_VALIDITY` passes (zero parse errors, zero invalid intervals, zero intra-day overlaps).
8. `ESTIMATED_BUDGET_COMPLIANCE` passes when a budget ceiling is specified.
9. For all `OPENING_HOURS` evaluable items, there are **zero known `VIOLATION`s** (`opening_hours_known_violation_count == 0`; `UNKNOWN` items remain neutral).

- **No Composite Weighted Score:** Do not construct any weighted composite score across dimensions. Report each dimension independently.

### Frozen Primary 100-Scenario Denominator (`CORE_SCENARIO_PASS_RATE_ALL_100`)
- The primary final benchmark has exactly $N = 100$ assigned scenarios:
  $$\text{VALID\_RUN\_RATE} = \frac{\text{valid\_run\_count}}{100}$$
  $$\text{CORE\_SCENARIO\_PASS\_RATE\_ALL\_100} = \frac{\text{core\_scenario\_pass\_count}}{100}$$
- Every `INVALID` run (`MOCK_OR_FALLBACK_RUN`, `API_ERROR`, `UNPARSABLE_MODEL_OUTPUT`, `MODEL_ID_MISMATCH`, `MISSING_REQUIRED_RUN_METADATA`) is **not** a successful scenario and contributes `0` to the numerator while **remaining in the 100-scenario primary denominator**.
- Optionally report `CORE_SCENARIO_PASS_RATE_CONDITIONAL_ON_VALID_RUNS = core_scenario_pass_count / valid_run_count`, labeled strictly `SECONDARY_DIAGNOSTIC_ONLY` (never replacing `CORE_SCENARIO_PASS_RATE_ALL_100`).

### `GROUNDING_GATE`
- Because the locked roadmap mandates `100%` valid POI grounding (`= 100%`), `GROUNDING_GATE = PASS` **if and only if** `Grounded POI Rate == 1.0` across all `POI_VISIT` items in the final benchmark; otherwise `GROUNDING_GATE = FAIL`.
- No arbitrary numerical pass thresholds are invented for other dimensions; all rates are reported with uncertainty intervals.

---

## 10. Statistical Reporting & Cluster-Aware Uncertainty

- **Scenario-Level Binary Rates:** Report point estimate + `95%` Wilson confidence interval (including scenario-level `ALL_POIS_GROUNDED`, `CORE_SCENARIO_PASS_RATE_ALL_100`, `VALID_RUN_RATE`, etc.).
- **Item-Level `Grounded POI Rate` Uncertainty (Cluster-Aware):**
  - Report item-level point estimate + **`95%` scenario-cluster bootstrap confidence interval**.
  - **Resampling Unit:** `scenario` (NOT individual POI item), because multiple `POI_VISIT` items within one generated itinerary originate from the same model call and cannot be treated as independent Bernoulli observations.
  - **Frozen Bootstrap Parameters:** `bootstrap_iterations = 10000`, `bootstrap_seed = 20261015`.
- **Stratifications:** Report overall micro average, per-destination results (`ha-noi`, `da-nang`, `ha-long`), and the equal-destination macro average (so the `34 / 33 / 33` split does not privilege `ha-noi`).
- **Hypothesis Testing:** No statistical significance claim is permitted unless a comparison hypothesis is formally preregistered prior to benchmark execution.
- **Performance Metrics:**
  - `generation_latency_ms`: measured directly around the live provider API call; report `median` and `p95`.
  - Token efficiency: capture authoritative provider usage metadata (`input_tokens`, `output_tokens`, `total_tokens`) when returned by the provider; otherwise classify `TOKEN_EFFICIENCY = NOT_EVALUABLE`. String-length token estimation is strictly forbidden.

---

## 11. Valid / Invalid Run Contract & Reproducibility

- **Valid Run Requirements:** Confirmed live provider execution, expected `model_id` recorded, benchmark configuration recorded, frozen `scenario_id`, frozen catalog SHA256, and evaluator version/SHA256 recorded.
- **Fail-Closed Invalid Run Conditions:** `MOCK_OR_FALLBACK_RUN`, `API_ERROR`, `UNPARSABLE_MODEL_OUTPUT`, `MODEL_ID_MISMATCH`, `MISSING_REQUIRED_RUN_METADATA`. Invalid runs are never counted as successful scenarios, remain in the `100`-scenario primary denominator, must be reported separately, and may never be hidden via silent retries.
- **Reproducibility Standard (`AUDITABLE_PROCESS_REPRODUCIBILITY`):** Exact bitwise LLM output determinism is not claimed. Every benchmark run must persist: `scenario_input`, `raw_provider_response`, `parsed_plan_response`, `execution_timestamp_utc`, `provider`, `model_id`, `generation_parameters`, `api_execution_mode`, `latency`, `usage_metadata_if_available`, `scenario_sha256`, `catalog_sha256`, `evaluator_sha256`, `code_commit_sha`, `raw_response_sha256`, and `parsed_response_sha256`.

---

## 12. Required Instrumentation Prerequisites (`P1`–`P12`)

Before final W06 preregistration and benchmark execution, implementation tasks must deliver:
- **P1:** Controlled `activity_kind` (`POI_VISIT` | `TRANSIT_ONLY`) on every itinerary item, with canonical `place_id` REQUIRED iff `activity_kind == "POI_VISIT"` (and fail-closed `INVALID_OR_SCHEMA_NONCOMPLIANT_ITEM` on missing/unknown `activity_kind`).
- **P2:** Deterministic catalog membership validation against `REC-A-CORE-V2` for all `POI_VISIT` items.
- **P3:** Destination membership validation by canonical `place_id` for all `POI_VISIT` items.
- **P4:** Canonical duplicate-place validation by `place_id` across `POI_VISIT` items.
- **P5:** `HH:MM` time parser, `start_time < end_time` check, and intra-day overlap checker.
- **P6:** Estimated-budget ceiling checker separated from price-grounding claims.
- **P7:** Opening-hours parser with explicit three-state (`COMPLIANT` / `VIOLATION` / `UNKNOWN`) handling where known `VIOLATION` fails `CORE_SCENARIO_PASS` and `UNKNOWN` remains neutral.
- **P8:** Benchmark harness that rejects mock/fallback execution (`FAIL CLOSED`) and retains invalid runs in the primary 100-scenario denominator.
- **P9:** Raw + parsed output persistence for evaluation runs.
- **P10:** Cryptographic reproducibility run manifest.
- **P11:** Frozen 100-scenario manifest (`34` `ha-noi`, `33` `da-nang`, `33` `ha-long`) with per-scenario SHA256.
- **P12:** Benchmark-only execution path incapable of returning canned mock output as scientific evidence.

*(None of `P1`–`P12` are implemented in `W06-MEASUREMENT-CONTRACT-01`.)*

---

## 13. Scenario Design Contract, Interest Taxonomy & Legacy Evaluator Status

- **Scenario Design Freeze:** All 100 scenarios must be frozen prior to final benchmark execution, varying destination, trip length, travel style, interest profile, budget ceiling, and weekday/weekend dates. Scenarios must be created independently of final model outputs; no scenario may be added, removed, or edited due to poor model performance.
- **Interest Taxonomy Rule:** The canonical scientific interest taxonomy is the 7 `CANONICAL_INTERESTS` (`food_cuisine`, `culture_history`, `nature_outdoor`, `coffee_culture`, `beach_island`, `shopping_local`, `nightlife_entertainment`). Future W06 scenarios must either (A) use canonical keys directly or (B) use a frozen deterministic mapping from scenario aliases to canonical keys.
- **Legacy Evaluator Status:** `data/evaluation/planner/evaluate_planner.py` is classified as `LEGACY_INSUFFICIENT_FOR_FINAL_AGENT_EVAL`. It is preserved unchanged for existing unit tests, and its outputs must never be relabeled as final W06 scientific results.
