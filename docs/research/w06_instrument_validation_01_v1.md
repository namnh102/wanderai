# W06 Pre-Scenario-Freeze Adversarial Validation & Scientific Hardening Gate (`W06-INSTRUMENT-VALIDATION-01`)

- **Gate ID:** `W06-INSTRUMENT-VALIDATION-01`
- **Gate Version:** `1.0.0`
- **Gate Purpose:** `PRE_SCENARIO_FREEZE_MEASUREMENT_SYSTEM_VALIDATION`
- **Base `develop` SHA:** `8d599bd8fe1a167a64c375c43148928daeb94dca`
- **Measurement Contract Basis:** `W06-MEASUREMENT-CONTRACT-01` v1.1.0 (`7fd5364ed4671c06b0c911b6fd53bd9f54cbc322`)
- **Closed Instrumentation Modules:**
  - `W06-INSTRUMENT-01A` (`CLOSED`)
  - `W06-INSTRUMENT-01B` (`CLOSED`)
  - `W06-INSTRUMENT-01C` (`CLOSED`)
- **Overall Gate Verdict:** `PASS` (`44 / 44` adversarial validation suites `W06-VAL-01..44` passing; `0` failures)

---

## 1. Resolution of Follow-up Note A (Metric Name Safety Outside `FINAL_100`)

- **Problem Addressed:**
  - Previously, `core_scenario_pass_rate_all_100` was populated even when `final_100_mode == false` using `assigned_scenario_count` as the denominator, allowing synthetic non-100 runs (e.g., `N = 3`) to populate a field named `_all_100`.
- **Hardened Contract in [`planner_benchmark_aggregator.py`](../../apps/ai-service/app/evaluation/planner_benchmark_aggregator.py):**
  - Added `core_scenario_pass_rate_all_assigned` and `core_scenario_pass_rate_all_assigned_ci95` (`core_scenario_pass_count / assigned_scenario_count`), which are always populated across all aggregation modes.
  - Restricted `core_scenario_pass_rate_all_100` and `core_scenario_pass_rate_all_100_ci95` strictly to `FINAL_100` mode (`final_100_mode == true` or `is_final_100_frozen == true`) with denominator `100` (`core_scenario_pass_rate_all_100_status = "FINAL_100_PRIMARY_METRIC"`).
  - Outside `FINAL_100` mode, `core_scenario_pass_rate_all_100 = null`, `core_scenario_pass_rate_all_100_ci95 = null`, and `core_scenario_pass_rate_all_100_status = "NOT_APPLICABLE_NON_FINAL_100_MODE"`.

---

## 2. Resolution of Follow-up Note B & Assignment Manifest Canonical Hash Policy

- **Future `P11` Assignment Manifest Contract:**
  - `is_final_100_frozen = true`
  - `hash_basis_version = "W06-ARTIFACT-HASH-BASIS-V1"`
  - `assignment_manifest_hash_basis = "SHA256_CANONICAL_JSON_UTF8_LF_BYTES"`
  - Exact `100` unique scenarios allocated `34 ha-noi / 33 da-nang / 33 ha-long`
  - Every `AssignedScenarioSpec` in `FINAL_100` mode must include a non-null 64-character lowercase hexadecimal `scenario_sha256` (`^[0-9a-f]{64}$`). Missing, malformed, or uppercase SHA256 values fail closed.
- **Canonical Serialization & Policy A (`REJECT_NON_CANONICAL_FINAL_100_ASSIGNMENT_MANIFEST`):**
  - Canonical manifest bytes are UTF-8 JSON (`ensure_ascii = false`, `sort_keys = true`, `indent = 2`, single trailing LF).
  - Under **Policy A**, `load_and_validate_assignment_manifest_bytes` and `aggregate_evaluations_from_disk` verify that any `FINAL_100` manifest file on disk matches its canonical byte representation byte-for-byte before aggregation, rejecting reordered keys or non-canonical formatting.
  - `P11` itself remains `NOT_IMPLEMENTED` (`real_100_scenarios_generated = false`, `real_100_assignment_manifest_created = false`).

---

## 3. Zero-Budget (`budget = 0`) Denominator Hardening

- In [`planner_benchmark_evaluator.py`](../../apps/ai-service/app/evaluation/planner_benchmark_evaluator.py):
  - When `budget_ceiling == 0` and `estimated_total_cost == 0`: `budget_status = "COMPLIANT"`, `estimated_budget_compliant = true`, `estimated_budget_violation_amount = 0`, `budget_overrun_fraction = null`, `budget_overrun_fraction_status = "UNDEFINED_ZERO_BUDGET_DENOMINATOR"`.
  - When `budget_ceiling == 0` and `estimated_total_cost > 0`: `budget_status = "VIOLATION"`, `estimated_budget_compliant = false`, `estimated_budget_violation_amount = estimated_total_cost`, `budget_overrun_fraction = null`, `budget_overrun_fraction_status = "UNDEFINED_ZERO_BUDGET_DENOMINATOR"`, `core_scenario_pass = false`.
  - Never divides by zero and never emits an arbitrary `1.0` overrun fraction when `budget == 0`.

---

## 4. Adversarial Gate Coverage Summary (`W06-VAL-01` .. `W06-VAL-44`)

| Gate Domain | Test IDs | Status |
|---|---|---|
| Follow-up Note A & Non-Final Denominator Name Safety (`N=3`, `N=100`) | `W06-VAL-01`, `W06-VAL-02` | `PASS` |
| Follow-up Note B, Future `P11` Hash Contract & Policy A Canonical Enforcement | `W06-VAL-03` .. `W06-VAL-05` | `PASS` |
| Evidence Integrity Tampering & Invalid Run Statuses (`6.A`–`6.J`) | `W06-VAL-06` .. `W06-VAL-15` | `PASS` |
| Grounding, Destination, Duplicate POI, Zero `POI_VISIT` & `TRANSIT_ONLY` Anti-Gaming | `W06-VAL-16` .. `W06-VAL-20` | `PASS` |
| Schedule Format, Interval Direction, Intra-Day vs Cross-Day Overlap & Date Alignment | `W06-VAL-21` .. `W06-VAL-23` | `PASS` |
| Budget (`null`, `>0`, `0` compliant/violation) & Arithmetic Self-Consistency | `W06-VAL-24` .. `W06-VAL-26` | `PASS` |
| Opening-Hours 3-State Semantics & `622/101/73/91/10` Corpus Reproduction | `W06-VAL-27` .. `W06-VAL-30` | `PASS` |
| Exhaustive Final `core_scenario_pass` Truth Table | `W06-VAL-31` | `PASS` |
| Count-Based Grounding Aggregation, Cluster Bootstrap, Wilson CI & Macro Edge Cases | `W06-VAL-32` .. `W06-VAL-38` | `PASS` |
| `FINAL_100` Fail-Closed Assignment Validation (`99`, `101`, `34/34/32`, `33/34/33`, etc.) | `W06-VAL-39` .. `W06-VAL-42` | `PASS` |
| Byte-Level Determinism, Input-Order Invariance, Production Isolation & Boundaries | `W06-VAL-43`, `W06-VAL-44` | `PASS` |

---

## 5. Scientific Boundaries

- `real_100_scenarios_generated = false`
- `real_100_assignment_manifest_created = false`
- `P11_implemented = false`
- `final_benchmark_executed = false`
- `scientific_performance_results_generated = false`
- `preregistration_created = false`
- `Gemini_called = false`
- `W5_modified = false`
- `production_planner_behavior_modified = false`
- `historical_measurement_contract_modified = false`
