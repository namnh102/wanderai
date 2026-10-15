# W06-INSTRUMENT-01D: Minimum POI Visits Per Day Amendment (`min_poi_visits_per_day = 2`)

- **Instrument ID:** `W06-INSTRUMENT-01D`
- **Instrument Version:** `1.0.0`
- **Source Methodology Lock:** `W06-SCENARIO-METHOD-LOCK-01` (`v1.0.0`, status `CLOSED`)
- **Base `develop` Commit:** `e5e1f450f68772b2fdc09e37eef58fd6bd5509ba`
- **Active Benchmark Prompt Version:** `TRAVEL_PLANNER_BENCHMARK_V2`
- **Active Core Evaluator Version:** `W06-CORE-EVALUATOR-01D-V1.0.0`
- **Machine-Readable Receipt:** `data/evaluation/w06/w06_instrument_01d_receipt_v1.json`

---

## 1. What Changed

`W06-INSTRUMENT-01D` is a **benchmark-only instrumentation amendment** that aligns the W06 planner benchmark prompt and deterministic core evaluator with the frozen `W06-SCENARIO-METHOD-LOCK-01` rule `min_poi_visits_per_day = 2` prior to final 100-scenario generation (`P11`):

1. **Benchmark Prompt (`apps/ai-service/app/prompts/planner_benchmark_prompt.py`):**
   - Preserved `BENCHMARK_PROMPT_VERSION_01A = "TRAVEL_PLANNER_BENCHMARK_V1"` and `TRAVEL_PLANNER_BENCHMARK_V1` for historical traceability.
   - Introduced `TRAVEL_PLANNER_BENCHMARK_V2` and set active `BENCHMARK_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"`.
   - Added explicit rules in Section `C. THỜI GIAN & CẤU TRÚC NGÀY (SCHEDULE & DAY STRUCTURE)` requiring every itinerary day to contain at least **2** items with `activity_kind == "POI_VISIT"`, explicitly excluding `TRANSIT_ONLY` items from the minimum count, and requiring every day to satisfy the threshold independently.
   - Updated the JSON output example in Section `E. ĐỊNH DẠNG ĐẦU RA (JSON ONLY)` so Day 1 demonstrates two `POI_VISIT` items (`order_index` `1` and `3`) plus one `TRANSIT_ONLY` item (`order_index` `2`) with non-overlapping 24-hour `HH:MM` intervals (`08:00-09:30`, `09:30-10:00`, `10:00-11:30`).
2. **Deterministic Core Evaluator (`apps/ai-service/app/evaluation/planner_benchmark_evaluator.py`):**
   - Preserved `EVALUATOR_VERSION_01B = "W06-CORE-EVALUATOR-01B-V1.0.0"` and `EVALUATOR_VERSION_01C = "W06-CORE-EVALUATOR-01C-V1.0.0"`.
   - Introduced `EVALUATOR_VERSION_01D = "W06-CORE-EVALUATOR-01D-V1.0.0"` and set active `EVALUATOR_VERSION = "W06-CORE-EVALUATOR-01D-V1.0.0"`.
   - Added `MIN_POI_VISITS_PER_DAY = 2`, `MINIMUM_POI_VISITS_PER_DAY_METHOD_STATUS = "FORMALLY_FROZEN_BY_W06_SCENARIO_METHOD_LOCK_01"`, and `MINIMUM_POI_VISITS_PER_DAY_RULE_SOURCE = "data/evaluation/w06/w06_scenario_method_lock_v1.json#minimum_poi_visits_per_day_policy"`.
   - Added explicit per-scenario fields on `ScenarioEvaluationResult`:
     - `minimum_poi_visits_per_day_required: int` (`2`)
     - `minimum_poi_visits_per_day_method_status: str`
     - `minimum_poi_visits_per_day_rule_source: str`
     - `poi_visit_count_by_day: list[int]`
     - `min_poi_visits_observed_per_day: int`
     - `minimum_poi_visits_per_day_pass: bool`
   - Replaced the legacy 1-total-item/day check in `day_structure_pass` with `day_structure_pass = day_count_pass and minimum_poi_visits_per_day_pass`.
   - Separated failure reason codes so `DAY_STRUCTURE_VIOLATION` is emitted when `not day_count_pass` and `MINIMUM_POI_VISITS_PER_DAY_VIOLATION` is emitted when `not minimum_poi_visits_per_day_pass`.

---

## 2. Why It Changed & Source Methodology Decision

In `W06-MEASUREMENT-CONTRACT-01 v1.1.0` (`section_3_constraint_specifications.DAY_COUNT_AND_STRUCTURE_MATCH`), the minimum POI visits per day rule was explicitly noted as a pre-benchmark methodology parameter (`min_items_per_day >= 1` in initial 01B/01C instrumentation, with exact minimum POI visits per day to be locked before benchmark execution).

Subsequently, `W06-SCENARIO-METHOD-LOCK-01` (`data/evaluation/w06/w06_scenario_method_lock_v1.json`) formally froze:

- `min_poi_visits_per_day = 2`
- `required_activity_kind = "POI_VISIT"`
- `transit_only_counts_toward_minimum = false`
- Stage 1 Rule B catalog capacity requirement: `union_support(C) >= 2 * D` and `sum_support(C) >= 2 * D`, ensuring every eligible scenario in the 100-scenario design space has sufficient catalog capacity for at least `2 * D` distinct `POI_VISIT` items across `D` days.

Before `W06-INSTRUMENT-01D`, a gap existed between the frozen scenario methodology (`>= 2 POI_VISIT` items per day) and the 01A/01B/01C benchmark prompt and evaluator (`>= 1` total item per day). `W06-INSTRUMENT-01D` closes this gap before any final scenario generation (`P11`) or preregistration takes place.

---

## 3. Old vs. New Evaluator Behavior & `TRANSIT_ONLY` Exclusion

| Aspect | Legacy Behavior (`01B` / `01C`) | Amended Behavior (`01D`) |
|---|---|---|
| **Evaluator Version** | `W06-CORE-EVALUATOR-01C-V1.0.0` | `W06-CORE-EVALUATOR-01D-V1.0.0` |
| **Per-Day Item Count Rule** | `all(len(day.items) >= 1 for day in parsed_plan.days)` | `len(parsed_plan.days) > 0 and all(count >= 2 for count in poi_visit_count_by_day)` |
| **`TRANSIT_ONLY` Handling** | Counted toward `len(day.items)` | Excluded from `poi_visit_count_by_day` (`activity_kind == "POI_VISIT"` only) |
| **`min_items_observed_per_day`** | Used for pass/fail | Retained as a descriptive legacy total-item count only |
| **`day_structure_pass` Formula** | `day_count_pass and min_items_per_day_pass` | `day_count_pass and minimum_poi_visits_per_day_pass` |
| **Failure Reason Codes** | `DAY_STRUCTURE_VIOLATION` for both day-count mismatch and empty day | `DAY_STRUCTURE_VIOLATION` when `not day_count_pass`; `MINIMUM_POI_VISITS_PER_DAY_VIOLATION` when `not minimum_poi_visits_per_day_pass` |
| **Impact on `core_scenario_pass`** | Via `day_structure_pass` in `core_scenario_pass_pre_opening_hours` | Via `day_structure_pass` in `core_scenario_pass_pre_opening_hours` and final `core_scenario_pass` |

Specifically, for each day $d$ in `parsed_plan.days`:
$$\text{poi\_visit\_count\_by\_day}[d] = \sum_{item \in d.\text{items}} \mathbb{I}(\text{item.activity\_kind} == \text{"POI\_VISIT"})$$

A day with 1 `POI_VISIT` item and 10 `TRANSIT_ONLY` items has `poi_visit_count_by_day[d] == 1` and therefore fails `minimum_poi_visits_per_day_pass`.

---

## 4. Prompt and Evaluator Alignment

Both the benchmark prompt (`TRAVEL_PLANNER_BENCHMARK_V2`) and the deterministic evaluator (`W06-CORE-EVALUATOR-01D-V1.0.0`) enforce the exact same rule:

- The prompt instructs the planner model in Section `C` that every day must include at least 2 `POI_VISIT` items (`min_poi_visits_per_day = 2`) and that `TRANSIT_ONLY` items do not count toward this minimum.
- The prompt's Section `E` JSON format example no longer shows a 1-POI + 1-transit day (which would violate Section `C`), and instead shows 2 `POI_VISIT` items + 1 `TRANSIT_ONLY` item on Day 1.
- The evaluator deterministically checks `minimum_poi_visits_per_day_pass` on every evaluated run and fails closed (`minimum_poi_visits_per_day_pass = False`, `min_poi_visits_observed_per_day = 0`, `poi_visit_count_by_day = []`) on invalid or corrupted runs.

---

## 5. Why Schema `min_length=1` Was Intentionally Preserved

In `apps/ai-service/app/schemas/planner_benchmark.py`, `BenchmarkItineraryDay.items` continues to use `Field(..., min_length=1)` rather than `min_length=2`:

1. **Activity-Kind Specificity:** Schema `min_length=2` on `BenchmarkItineraryDay.items` only counts total list elements; a day with 1 `POI_VISIT` and 1 `TRANSIT_ONLY` has `len(items) == 2` and would pass `min_length=2` while still violating `min_poi_visits_per_day = 2`.
2. **Diagnostic Separation (Schema vs. Constraint Violation):** If a model returns a syntactically well-formed JSON plan where a day contains only 1 `POI_VISIT` item, that plan must parse cleanly into `BenchmarkPlanResponse` (`run_validity_status == "VALID"`) so the deterministic evaluator can evaluate all constraints and record a specific `MINIMUM_POI_VISITS_PER_DAY_VIOLATION`, rather than collapsing the entire run into an opaque `SCHEMA_VALIDATION_FAILURE`.

---

## 6. Orthogonality of Grounding, Destination, and Duplicate Constraints

`poi_visit_count_by_day` counts structural items declared with `activity_kind == "POI_VISIT"`. Other scientific constraints remain strictly orthogonal:

- **Duplicate POIs (`P4`):** A day with two `POI_VISIT` items referencing the same `place_id` satisfies `minimum_poi_visits_per_day_pass == True`, while failing `no_duplicate_places_pass == False` (`DUPLICATE_PLACE_VIOLATION`).
- **Catalog Grounding (`P2`):** A day with two `POI_VISIT` items referencing ungrounded `place_id`s satisfies `minimum_poi_visits_per_day_pass == True`, while failing `catalog_grounding_pass == False` (`UNGROUNDED_PLACE_ID`).
- **Destination Consistency (`P3`):** A day with two grounded `POI_VISIT` items belonging to a different destination satisfies `minimum_poi_visits_per_day_pass == True`, while failing `scenario_destination_valid == False` (`WRONG_DESTINATION_PLACE`).
- **`TRANSIT_ONLY` Named POI Violation (`P1`):** A `TRANSIT_ONLY` item that illegally carries a `place_name` triggers `TRANSIT_ONLY_NAMED_POI_VIOLATION` (`activity_kind_ separation_pass == False`), without being counted in `poi_visit_count_by_day`.

---

## 7. Scientific Claim Boundaries & Non-Execution Confirmation

- **Frozen Method Lock & Support Matrix Untouched:**
  - `data/evaluation/w06/w06_scenario_method_lock_v1.json` (`SHA256 = 5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9`)
  - `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`SHA256 = 68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4`)
- **Historical Measurement Contract & Receipts Untouched:**
  - `data/evaluation/w06/w06_measurement_contract_v1.json` and historical receipts (`01A`, `01B`, `01C`, `VALIDATION-01`) were not modified.
- **No Final Scenarios or Benchmark Executed:**
  - `real_scenarios_generated = false`
  - `p11_created = false`
  - `preregistration_created = false`
  - `gemini_called = false`
  - `scientific_results_generated = false`
  - `production_planner_modified = false`
  - `w5_modified = false`
