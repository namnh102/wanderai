# W06 Opening-Hours Evaluation, Final Scenario Gate & Statistical Aggregation Engine (`W06-INSTRUMENT-01C`)

- **Task ID:** `W06-INSTRUMENT-01C`
- **Receipt Version:** `1.0.0`
- **Base `develop` SHA:** `98d01c1e2a83b6fe96699b802d1e0ff80cdd3758`
- **Measurement Contract Basis:** `W06-MEASUREMENT-CONTRACT-01` v1.1.0 ([`data/evaluation/w06/w06_measurement_contract_v1.json`](../../data/evaluation/w06/w06_measurement_contract_v1.json))
- **Prior Instrumentation Basis:** `W06-INSTRUMENT-01A` v1.1.0 & `W06-INSTRUMENT-01B` v1.0.0
- **Machine-Readable Receipt:** [`data/evaluation/w06/w06_instrument_01c_receipt_v1.json`](../../data/evaluation/w06/w06_instrument_01c_receipt_v1.json)
- **Opening-Hours Parser Coverage Inventory:** [`data/evaluation/w06/w06_opening_hours_parser_coverage_v1.json`](../../data/evaluation/w06/w06_opening_hours_parser_coverage_v1.json)
- **Metric Semantics Specification:** [`docs/research/w06_instrument_01c_metric_semantics_v1.md`](w06_instrument_01c_metric_semantics_v1.md)

---

## 1. Purpose & Scientific Boundaries

`W06-INSTRUMENT-01C` completes the benchmark evaluation and statistical aggregation instrumentation for W06:
1. **Conservative OSM `opening_hours` Evaluator (`apps/ai-service/app/evaluation/opening_hours_evaluator.py`):**
   - Evaluates grounded `POI_VISIT` items into three explicit states (`COMPLIANT`, `VIOLATION`, `UNKNOWN`) with deterministic reason codes.
   - Never guesses on unsupported syntax (`UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX`, `UNSUPPORTED_OPEN_ENDED_PLUS`, `UNSUPPORTED_HOLIDAY_SELECTOR`, `UNSUPPORTED_SYNTAX`).
2. **Day / Date Alignment Integrity & Final `core_scenario_pass` (`apps/ai-service/app/evaluation/planner_benchmark_evaluator.py`):**
   - Validates `BenchmarkItineraryDay.date` as strict ISO `YYYY-MM-DD` aligned with `scenario.start_date .. scenario.end_date`.
   - Computes `core_scenario_pass = core_scenario_pass_pre_opening_hours AND scenario_date_alignment_pass AND opening_hours_known_violation_count == 0`.
3. **Deterministic Batch Statistical Aggregator (`apps/ai-service/app/evaluation/planner_benchmark_aggregator.py` & `scripts/aggregate_w06_planner_evaluations.py`):**
   - Enforces authoritative assignment-manifest denominator membership (including strict `FINAL_100` mode: `34 ha-noi`, `33 da-nang`, `33 ha-long`).
   - Retains invalid runs as non-passes in `CORE_SCENARIO_PASS_RATE_ALL_100`.
   - Computes 95% Wilson score confidence intervals for binary scenario rates and 95% scenario-cluster bootstrap confidence intervals (`10000` iterations, `seed=20261015`) for item-level `Grounded POI Rate`.
   - Reports per-destination stratification and unweighted equal-destination macro averages.

**Strict Non-Claims:**
- `final_100_scenarios_generated = false`
- `final_100_scenario_manifest_created = false`
- `final_benchmark_executed = false`
- `scientific_results_generated = false`
- `preregistration_created = false`

---

## 2. Opening-Hours Pre-Flight Inventory & Parser Coverage

Across the `622` `REC-A-CORE-V2` catalog POIs in `data/curated/gomate_places_freeze_v2.json`:
- **Core POIs with non-empty `opening_hours`:** `101` (`73` unique strings)
- **Supported by `W06-OPENING-HOURS-PARSER-01C-V1.0.0`:** `91 / 101` (`0.90099`)
- **Unsupported (classified as `UNKNOWN`, never guessed):** `10 / 101`:
  - `UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX`: `8` records (`Mo-Su 18:00-02:00` x2, `Fr-Su 18:00-00:00`, `Mo-Su 09:00-00:00`, `Mo-Su 11:00-01:00`, `Mo-Su 11:30-01:00`, `Mo-Su 20:00-03:00`, `Mo-Su 20:00-2:00`)
  - `UNSUPPORTED_OPEN_ENDED_PLUS`: `1` record (`Mo-Su 05:30+`)
  - `UNSUPPORTED_HOLIDAY_SELECTOR`: `1` record (`Tu-Th,Sa-Su,PH 08:00-11:30,13:00-16:30`)

---

## 3. Prerequisite Implementation Matrix (`P1`–`P12`)

| Prerequisite | Status after `W06-INSTRUMENT-01C` | Notes |
|---|---|---|
| `P1` | `IMPLEMENTED` | Controlled `POI_VISIT` / `TRANSIT_ONLY` schema + `TRANSIT_ONLY_NAMED_POI_VIOLATION` anti-gaming check. |
| `P2` | `IMPLEMENTED` | Deterministic `REC-A-CORE-V2` catalog membership check (`grounded_poi_rate`, `all_pois_grounded`). |
| `P3` | `IMPLEMENTED` | Canonical `place_id` destination membership check (`destination_correct_poi_rate`, `scenario_destination_valid`). |
| `P4` | `IMPLEMENTED` | Canonical `place_id` duplicate check (`duplicate_poi_violation_count`, `duplicate_poi_pass`). |
| `P5` | `IMPLEMENTED` | Strict `HH:MM` parser, `start_time < end_time` check, and half-open `[start, end)` intra-day overlap checker. |
| `P6` | `IMPLEMENTED` | `ESTIMATED_BUDGET_COMPLIANCE` and `ARITHMETIC_SELF_CONSISTENCY`. |
| `P7` | `IMPLEMENTED` | Conservative three-state OSM `opening_hours` parser & evaluator (`COMPLIANT` / `VIOLATION` / `UNKNOWN`) + final `core_scenario_pass`. |
| `P8` | `IMPLEMENTED` | Fail-closed invalid-run handling and primary 100-scenario denominator retention in `planner_benchmark_aggregator.py`. |
| `P9` | `IMPLEMENTED` | Persists `scenario_input.json`, `raw_provider_response.txt`, `parsed_plan_response.json`, `run_manifest.json`, `scenario_evaluation.json`, and batch aggregation JSON. |
| `P10` | `IMPLEMENTED` | Full cryptographic SHA-256 verification and traceability across runner, single-scenario evaluator, and batch aggregator under `W06-ARTIFACT-HASH-BASIS-V1`. |
| `P11` | `NOT_IMPLEMENTED` | Frozen 100-scenario benchmark manifest (`34 ha-noi`, `33 da-nang`, `33 ha-long`) deferred to dedicated scenario-freeze task. |
| `P12` | `IMPLEMENTED` | Benchmark execution, evaluation, and aggregation paths isolated from production `POST /planner` mock fallback. |
