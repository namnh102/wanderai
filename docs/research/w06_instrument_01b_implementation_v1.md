# W06 Deterministic Core Constraint Evaluator (`W06-INSTRUMENT-01B`)

- **Task ID:** `W06-INSTRUMENT-01B`
- **Receipt Version:** `1.0.0`
- **Base `develop` SHA:** `770ead820e16716ce29a1a39d54a12b8a2246a3b`
- **Contract Basis:** `W06-MEASUREMENT-CONTRACT-01` v1.1.0 (`data/evaluation/w06/w06_measurement_contract_v1.json`)
- **Instrumentation 01A Basis:** `W06-INSTRUMENT-01A` v1.1.0 (`data/evaluation/w06/w06_instrument_01a_receipt_v1.json`)
- **Machine-Readable Receipt:** [`data/evaluation/w06/w06_instrument_01b_receipt_v1.json`](../../data/evaluation/w06/w06_instrument_01b_receipt_v1.json)

---

## 1. Purpose & Scientific Boundaries

`W06-INSTRUMENT-01B` implements the deterministic single-scenario core constraint evaluator (`apps/ai-service/app/evaluation/planner_benchmark_evaluator.py`) and CLI (`scripts/evaluate_w06_planner_run.py`) for W06 benchmark evidence produced by `W06-INSTRUMENT-01A`:
- **Deterministic Only:** Makes zero LLM calls, zero external network calls, zero random operations, and performs zero fuzzy string matching.
- **Pre-Opening-Hours Gate Only (`core_scenario_pass_pre_opening_hours`):** Opening-hours parsing and three-state (`COMPLIANT` / `VIOLATION` / `UNKNOWN`) evaluation are explicitly deferred to `W06-INSTRUMENT-01C`. `ScenarioEvaluationResult` records `opening_hours_status = "NOT_EVALUATED_IN_01B"` and `final_core_scenario_pass_status = "NOT_COMPUTED_IN_01B_REQUIRES_01C_OPENING_HOURS"`, and deliberately omits any `core_scenario_pass` / `CORE_SCENARIO_PASS` field so pre-opening-hours results cannot be mistaken for final contract pass results.
- **No Weighted Composite Score:** Every dimension is reported independently.

---

## 2. Evaluated Dimensions & Fail-Closed Rules

1. **Artifact Hash Integrity Verification (`W06-ARTIFACT-HASH-BASIS-V1`):**
   - Verifies `scenario_sha256` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`), `catalog_sha256` (`SHA256_LF_NORMALIZED_SOURCE_BYTES`), and `parsed_response_sha256` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`) against `run_manifest.json` before evaluating planner constraints.
   - Any mismatch produces `evaluation_status = "EVIDENCE_INTEGRITY_FAILURE"`, `evidence_integrity_valid = false`, and `core_scenario_pass_pre_opening_hours = false`.
2. **Run Validity Gate:**
   - Requires `run_manifest.run_status == "VALID"`. Any non-`VALID` status (`LIVE_PROVIDER_REQUIRED`, `MOCK_OR_FALLBACK_RUN`, `API_ERROR`, `UNPARSABLE_MODEL_OUTPUT`, `MODEL_ID_MISMATCH`, `SCHEMA_NONCOMPLIANT_OUTPUT`, `MISSING_REQUIRED_RUN_METADATA`) produces `evaluation_status = "INVALID_RUN"`, `run_valid = false`, and `core_scenario_pass_pre_opening_hours = false` while preserving the original `run_status`.
3. **Catalog Grounding (`CATALOG_GROUNDING`):**
   - Checks every `POI_VISIT` item's `place_id` by exact key lookup in the `622` `REC-A-CORE-V2` POIs from `data/curated/gomate_places_freeze_v2.json`.
   - `all_pois_grounded` is `true` iff `poi_visit_item_count >= 1` and `ungrounded_item_count == 0`. Free-text `place_name` never rescues an invalid `place_id`.
4. **Destination Correctness (`DESTINATION_CORRECTNESS`):**
   - Verifies that every grounded `POI_VISIT` item's catalog `destination_slug` matches `scenario.destination_slug`.
   - `scenario_destination_valid` is `true` iff `all_pois_grounded` is `true` and `destination_incorrect_item_count == 0`.
5. **Duplicate POI (`DUPLICATE_POI`):**
   - Counts repeated canonical `place_id` values across all `POI_VISIT` items. Under the default policy (`allow_revisit_place_ids == false`), any repeated `place_id` fails `duplicate_poi_pass`. When `allow_revisit_place_ids == true`, repeated `place_id` values are permitted.
6. **`TRANSIT_ONLY` Anti-Gaming (`TRANSIT_ONLY_NAMED_POI_VIOLATION`):**
   - In addition to `01A`'s `place_id = null` rule, `01B` enforces that `TRANSIT_ONLY` items must have `place_name = null`. Any `TRANSIT_ONLY` item carrying a non-null `place_name` is flagged as `TRANSIT_ONLY_NAMED_POI_VIOLATION` and fails `core_scenario_pass_pre_opening_hours`.
   - *Documented limitation:* This check is strictly deterministic over structured fields (`activity_kind`, `place_id`, `place_name`) and does not perform NLP or fuzzy semantic inspection of free-text `activity` / `notes` fields.
7. **Day Structure (`DAY_STRUCTURE`):**
   - Verifies `len(days) == scenario.days`, `total_days == scenario.days`, sequential day numbering `1..scenario.days`, and non-empty items per day (`len(day.items) >= 1`).
   - Because `data/evaluation/w06/w06_measurement_contract_v1.json` does not freeze a numeric minimum-items-per-day constant `> 1`, `minimum_items_per_day_contract_status` is explicitly reported as `"NOT_FORMALLY_FROZEN"` with full provenance to the Measurement Contract, `BenchmarkItineraryDay` schema (`min_length=1`), and legacy `data/evaluation/planner/evaluate_planner.py:L39` (`min_items_per_day=1`).
8. **Schedule Validity (`SCHEDULE_VALIDITY`):**
   - Strictly parses 24-hour `HH:MM` (`00:00`–`23:59`), enforces `start_time < end_time`, and checks intra-day non-overlap under half-open interval semantics `[start, end)` (so back-to-back `09:00–10:00` and `10:00–11:00` do not overlap, and different days are evaluated independently).
9. **Estimated Budget Compliance (`ESTIMATED_BUDGET_COMPLIANCE`) & `ARITHMETIC_SELF_CONSISTENCY`:**
   - Evaluates compliance of the sum of item `estimated_cost` values against `scenario.budget` (`COMPLIANT`, `VIOLATION`, or `NOT_APPLICABLE` when `scenario.budget is null`), without claiming real-world price accuracy.
   - Separately verifies `ARITHMETIC_SELF_CONSISTENCY` (`day.day_cost == sum(day.items)` and `budget_analysis.estimated_cost == sum(all_items)`).
10. **Haversine Geographic Distance Proxy (`GEO_DISTANCE_PROXY`):**
    - Computes `geo_leg_count`, `total_geo_distance_proxy_km`, `mean_leg_geo_distance_proxy_km`, and `max_leg_geo_distance_proxy_km` across consecutive grounded `POI_VISIT` items (excluding `TRANSIT_ONLY` items).
    - Strictly diagnostic only; never labeled as travel time, route distance, or routing quality, and never affects `core_scenario_pass_pre_opening_hours`.

---

## 3. Prerequisite Implementation Matrix (`P1`–`P12`)

| Prerequisite | Status after `W06-INSTRUMENT-01B` | Notes |
|---|---|---|
| `P1` | `IMPLEMENTED` | `POI_VISIT` / `TRANSIT_ONLY` schema + `TRANSIT_ONLY_NAMED_POI_VIOLATION` anti-gaming check implemented. |
| `P2` | `IMPLEMENTED` | Deterministic `REC-A-CORE-V2` catalog membership check implemented (`grounded_poi_rate`, `all_pois_grounded`). |
| `P3` | `IMPLEMENTED` | Canonical `place_id` destination membership check implemented (`destination_correct_poi_rate`, `scenario_destination_valid`). |
| `P4` | `IMPLEMENTED` | Canonical `place_id` duplicate check implemented (`duplicate_poi_violation_count`, `duplicate_poi_pass`). |
| `P5` | `IMPLEMENTED` | Strict `HH:MM` parser, `start_time < end_time` check, and half-open `[start, end)` intra-day overlap checker implemented. |
| `P6` | `IMPLEMENTED` | `ESTIMATED_BUDGET_COMPLIANCE` and `ARITHMETIC_SELF_CONSISTENCY` implemented. |
| `P7` | `NOT_IMPLEMENTED` | Opening-hours parser and three-state evaluator deferred to `W06-INSTRUMENT-01C`. |
| `P8` | `PARTIALLY_IMPLEMENTED` | Single-run runner and evaluator fail closed on non-`VALID` runs; 100-scenario batch denominator aggregation belongs to `01C`. |
| `P9` | `IMPLEMENTED` | Persists `scenario_input.json`, `raw_provider_response.txt`, `parsed_plan_response.json`, `run_manifest.json`, and `scenario_evaluation.json`. |
| `P10` | `PARTIALLY_IMPLEMENTED` | Per-run manifest, artifact-specific hash verification, and `evaluator_code_sha256` implemented; batch manifest belongs to `01C`. |
| `P11` | `NOT_IMPLEMENTED` | Frozen 100-scenario manifest deferred to dedicated scenario-freeze task. |
| `P12` | `IMPLEMENTED` | Benchmark execution and evaluation path isolated from production `POST /planner` mock fallback. |
