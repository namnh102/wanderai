# W06 Metric & Aggregation Semantics Specification (`W06-INSTRUMENT-01C`)

- **Task ID:** `W06-INSTRUMENT-01C`
- **Evaluator Version:** `W06-CORE-EVALUATOR-01C-V1.0.0`
- **Opening-Hours Parser Version:** `W06-OPENING-HOURS-PARSER-01C-V1.0.0`
- **Aggregator Version:** `W06-BATCH-AGGREGATOR-01C-V1.0.0`
- **Measurement Contract Basis:** `W06-MEASUREMENT-CONTRACT-01` v1.1.0 ([`data/evaluation/w06/w06_measurement_contract_v1.json`](../../data/evaluation/w06/w06_measurement_contract_v1.json))

This document records the exact mathematical and denominator semantics implemented in `W06-INSTRUMENT-01C` without modifying historical Measurement Contract text.

---

## 1. Per-Scenario vs Batch Schedule Violation Semantics

- **Per-Scenario Diagnostic (`schedule_violation_event_density`):**
  - Renamed from `01B`'s per-scenario `schedule_violation_rate` to prevent naive averaging across scenarios:
    $$\text{schedule\_violation\_event\_density} = \frac{\text{schedule\_violation\_count}}{\text{all\_items\_count}}$$
- **Batch Metric (`schedule_violation_rate`):**
  - Defined strictly at the scenario level over `VALID`, evaluated scenarios (`schedule_evaluable_scenario_count`):
    $$\text{schedule\_violation\_rate} = \frac{\text{schedule\_violation\_scenario\_count}}{\text{schedule\_evaluable\_scenario\_count}}$$
  - Invalid provider/model runs (`INVALID_RUN`, `EVIDENCE_INTEGRITY_FAILURE`) are NOT classified as factual schedule violations; they remain non-passes in `CORE_SCENARIO_PASS_RATE_ALL_100`.

---

## 2. Per-Scenario vs Batch Estimated Budget Violation Semantics

- **Per-Scenario Severity Diagnostic (`budget_overrun_fraction`):**
  - Renamed from `01B`'s per-scenario `estimated_budget_violation_rate`:
    $$\text{budget\_overrun\_fraction} = \frac{\max(0, \text{estimated\_total\_cost} - \text{budget\_ceiling})}{\text{budget\_ceiling}}$$
    for scenarios with a positive non-null `budget_ceiling` (`null` when `budget_ceiling` is `null`).
- **Batch Metric (`estimated_budget_violation_rate`):**
  - Defined strictly at the scenario level over `VALID`, evaluated scenarios that specify a non-null budget (`budget_applicable_scenario_count`):
    $$\text{estimated\_budget\_violation\_rate} = \frac{\text{budget\_violation\_scenario\_count}}{\text{budget\_applicable\_scenario\_count}}$$
  - Scenarios with `budget = null` (`NOT_APPLICABLE`) and invalid provider runs are excluded from `budget_applicable_scenario_count`.

---

## 3. Opening-Hours Three-State & Day/Date Alignment Semantics

- **Item-Level States (`POI_VISIT` only):**
  - `COMPLIANT`: Grounded `place_id`, supported non-empty catalog `opening_hours`, valid aligned `YYYY-MM-DD` day date, valid `HH:MM` activity interval (`start_time < end_time`), and the entire visit interval `[start_min, end_min)` is contained within an open window on that weekday.
  - `VIOLATION`: All prerequisites above hold, and the scheduled visit interval conflicts with the known open hours (`CLOSED_ON_WEEKDAY` or `OUTSIDE_OPENING_HOURS_WINDOW`).
  - `UNKNOWN`: Any prerequisite is missing (`UNGROUNDED_POI_VISIT`, `MISSING_OPENING_HOURS`, `UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX`, `UNSUPPORTED_OPEN_ENDED_PLUS`, `UNSUPPORTED_HOLIDAY_SELECTOR`, `UNSUPPORTED_SYNTAX`, `UNKNOWN_DATE_CONTEXT`, `INVALID_VISIT_INTERVAL_FOR_OPENING_HOURS`).
  - `UNKNOWN != COMPLIANT` and `UNKNOWN != VIOLATION`. `UNKNOWN` items are excluded from `opening_hours_evaluable_items`.
- **Day / Date Alignment Rule (`scenario_date_alignment_pass`):**
  - Every `BenchmarkItineraryDay.date` must be a valid `YYYY-MM-DD` ISO date where Day `k` (`1..scenario.days`) equals `scenario.start_date + (k - 1) days` and Day `scenario.days` equals `scenario.end_date`.
  - Any missing, malformed, or misaligned date sets `scenario_date_alignment_pass = false` (`SCENARIO_DATE_ALIGNMENT_FAILURE`), marks that day's date context as untrusted (`UNKNOWN_DATE_CONTEXT`), and forces `core_scenario_pass = false` so date tampering can never evade an opening-hours constraint.

---

## 4. Final `core_scenario_pass` Formula

For each scenario:
$$\text{core\_scenario\_pass} = \text{core\_scenario\_pass\_pre\_opening\_hours} \land \text{scenario\_date\_alignment\_pass} \land (\text{opening\_hours\_known\_violation\_count} == 0)$$

- `UNKNOWN` opening-hours items do not fail `core_scenario_pass` by themselves.
- Any known opening-hours `VIOLATION` (`opening_hours_known_violation_count > 0`) forces `core_scenario_pass = false`.
- Any `INVALID_RUN` or `EVIDENCE_INTEGRITY_FAILURE` forces `core_scenario_pass = false`.

---

## 5. Primary 100-Scenario Denominator & Invalid-Run Rule

- **Valid Run Rate:**
  $$\text{VALID\_RUN\_RATE} = \frac{\text{valid\_run\_count}}{\text{assigned\_scenario\_count}}$$
- **Primary Benchmark Pass Rate (`CORE_SCENARIO_PASS_RATE_ALL_100`):**
  $$\text{CORE\_SCENARIO\_PASS\_RATE\_ALL\_100} = \frac{\text{core\_scenario\_pass\_count}}{100}$$
  Every assigned scenario remains in the primary denominator (`100` in `FINAL_100` mode); invalid runs contribute `0` to `core_scenario_pass_count` and never disappear.
- **Secondary Diagnostic Rate (`conditional_core_pass_rate_on_valid_runs`):**
  $$\text{CORE\_SCENARIO\_PASS\_RATE\_CONDITIONAL\_ON\_VALID\_RUNS} = \frac{\text{core\_scenario\_pass\_count}}{\text{valid\_run\_count}}$$
  Reported strictly as a secondary diagnostic and never substituted for the primary rate.

---

## 6. Wilson Score 95% CI & Scenario-Cluster Bootstrap 95% CI

- **95% Wilson Score Confidence Interval (`WILSON_SCORE_95`):**
  Used for scenario-level binary proportions $\hat{p} = k / n$ with $z = 1.959963984540054$:
  $$\frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$
- **95% Scenario-Cluster Bootstrap CI (`95_PERCENT_SCENARIO_CLUSTER_BOOTSTRAP_CI`):**
  Used for item-level `Grounded POI Rate`:
  $$\text{Grounded POI Rate} = \frac{\sum_{s \in \text{valid}} \text{grounded\_item\_count}_s}{\sum_{s \in \text{valid}} \text{poi\_visit\_item\_count}_s}$$
  Resamples `scenario` clusters with replacement (`iterations = 10000`, `seed = 20261015`), summing grounded numerator and `POI_VISIT` denominator within each bootstrap sample. Individual POI items are never resampled independently.

---

## 7. Additive Clarification (`W06-INSTRUMENT-VALIDATION-01`)

- **Follow-up Note A Resolution (`core_scenario_pass_rate_all_assigned` vs `core_scenario_pass_rate_all_100`):**
  - `core_scenario_pass_rate_all_assigned = core_scenario_pass_count / assigned_scenario_count` (with `core_scenario_pass_rate_all_assigned_ci95`) is always computed across all aggregation modes (`FINAL_100` and non-final synthetic modes).
  - `core_scenario_pass_rate_all_100` and `core_scenario_pass_rate_all_100_ci95` are populated ONLY when `FINAL_100` mode is active (`final_100_mode == true` or `is_final_100_frozen == true`) with denominator strictly equal to `100`. Outside `FINAL_100` mode, both fields are `null` (`core_scenario_pass_rate_all_100_status = "NOT_APPLICABLE_NON_FINAL_100_MODE"`), preventing any `N != 100` synthetic run from being labeled `_all_100`.
- **Follow-up Note B Resolution (Future `P11` Assignment Manifest Hash Contract & Policy A):**
  - Any `FINAL_100` frozen assignment manifest must specify `is_final_100_frozen = true`, `hash_basis_version = "W06-ARTIFACT-HASH-BASIS-V1"`, `assignment_manifest_hash_basis = "SHA256_CANONICAL_JSON_UTF8_LF_BYTES"`, exact 100 scenarios (`34 ha-noi / 33 da-nang / 33 ha-long`), and a required 64-character lowercase hexadecimal `scenario_sha256` on every scenario entry.
  - Under **Policy A (`REJECT_NON_CANONICAL_FINAL_100_ASSIGNMENT_MANIFEST`)**, persisted `FINAL_100` assignment manifest files must match canonical UTF-8 JSON (`ensure_ascii = false`, `sort_keys = true`, `indent = 2`, single final LF) byte-for-byte or are rejected before aggregation.
- **Zero-Budget Denominator Rule (`budget = 0`):**
  - When `budget_ceiling == 0`, compliance remains well-defined (`estimated_total_cost == 0` is `COMPLIANT`; `estimated_total_cost > 0` is `VIOLATION`), while `budget_overrun_fraction` is `null` with `budget_overrun_fraction_status = "UNDEFINED_ZERO_BUDGET_DENOMINATOR"` (never dividing by zero and never emitting arbitrary `1.0`).
