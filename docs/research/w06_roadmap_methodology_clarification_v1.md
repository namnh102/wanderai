# W06 Roadmap Methodology Clarification V1

- **Clarification ID:** `W06-ROADMAP-METHODOLOGY-CLARIFICATION-V1`
- **Linked Contract:** `W06-MEASUREMENT-CONTRACT-01` (`data/evaluation/w06/w06_measurement_contract_v1.json`, v1.1.0)
- **Linked Audit:** `W06-MEASUREMENT-AUDIT-01` (`data/evaluation/w06/w06_measurement_capability_audit_v1.json`)
- **Base `develop` SHA:** `495ed4f731db723366a585617472795540e8a914`
- **Locked Roadmap File:** `docs/roadmap/gomate-thesis-research-roadmap-v1.md` (**unchanged / non-destructively clarified**)

---

## 1. Purpose & Non-Destructive Principle

The thesis roadmap (`docs/roadmap/gomate-thesis-research-roadmap-v1.md`, lines 87–92 and 166–167) defines the high-level objectives for `AGENT-EVAL-01` (Week 6: Itinerary Agent Constraint Satisfaction Benchmarking). Following the forensic capability audit (`W06-MEASUREMENT-AUDIT-01`), this document records how each roadmap requirement is scientifically operationalized under the actual frozen repository evidence—**without** modifying or rewriting the historical roadmap file.

---

## 2. Locked Roadmap Requirements Preserved Unchanged

1. **100 Benchmark Trips / Test Prompts & Fixed Primary Denominator:**
   - The locked roadmap requirement of **100 test prompts / 100 benchmark trips** remains strictly in force (`benchmark_target_scenarios = 100`, allocated as `34` `ha-noi`, `33` `da-nang`, `33` `ha-long` across the `622` `REC-A-CORE-V2` POIs).
   - The primary scenario pass rate `CORE_SCENARIO_PASS_RATE_ALL_100 = core_scenario_pass_count / 100` uses the full 100-scenario denominator; invalid runs (`MOCK_OR_FALLBACK_RUN`, `API_ERROR`, `UNPARSABLE_MODEL_OUTPUT`, `MODEL_ID_MISMATCH`, `MISSING_REQUIRED_RUN_METADATA`) contribute `0` to the numerator and remain in the `100`-scenario denominator.
2. **100% Valid POI Grounding Target & Controlled Activity Scope:**
   - The locked roadmap requirement that **100% of generated POIs must map to verified catalog IDs (`Grounded POI Rate = 100%`)** remains strictly in force as the hard `GROUNDING_GATE` (`Grounded POI Rate == 1.0`).
   - Grounding is evaluated over all `POI_VISIT` items under the controlled `activity_kind` vocabulary (`POI_VISIT` | `TRANSIT_ONLY`), where `place_id` is required iff `activity_kind == "POI_VISIT"`, `TRANSIT_ONLY` is excluded from the grounding denominator (and forbidden from representing any named/visitable POI), and any missing/unknown `activity_kind` fails closed as `INVALID_OR_SCHEMA_NONCOMPLIANT_ITEM`.
   - Item-level `Grounded POI Rate` uncertainty is reported using a `95%` scenario-cluster bootstrap confidence interval (`resampling_unit = scenario`, `bootstrap_iterations = 10000`, `bootstrap_seed = 20261015`).
3. **Time-Slot Overlap / Schedule Conflict Evaluation:**
   - Enforced as a primary hard dimension (`SCHEDULE_VALIDITY`) checking strict `HH:MM` parsing, `start_time < end_time`, and zero intra-day interval overlaps.
4. **End-to-End Generation Latency & Token Efficiency:**
   - `generation_latency_ms` (`median`, `p95`) is measured around live provider calls. Token usage (`input_tokens`, `output_tokens`, `total_tokens`) is reported from authoritative provider metadata when available, or classified `NOT_EVALUABLE` (never estimated from string length).

---

## 3. Evidence-Bounded Operational Clarifications

### 3.1 Budget Compliance $\rightarrow$ `ESTIMATED_BUDGET_COMPLIANCE`
- **Roadmap Text:** *"Total budget compliance ($|\text{Cost} - \text{Budget}| \le \text{Threshold}$)"* / *"budget violation rate"*.
- **Empirical Evidence (`W06-MEASUREMENT-AUDIT-01`):** `gomate_places_freeze_v2.json` contains `0 / 759` (`0.00%`) structured numeric price records (`priceMin`/`priceMax`) and only `6 / 759` (`0.79%`) raw OSM `charge` tags.
- **Operational Clarification:** W06 operationalizes budget evaluation as **`ESTIMATED_BUDGET_COMPLIANCE`** (whether the sum of the planner's declared item `estimated_cost` values is $\le$ the requested scenario budget ceiling), reported via `estimated_budget_violation_rate` alongside `ARITHMETIC_SELF_CONSISTENCY`. W06 does **not** claim `REAL_WORLD_BUDGET_ACCURACY` or `PRICE_GROUNDING`.

### 3.2 Opening Hours Compliance $\rightarrow$ `EVIDENCE_CONDITIONAL_HARD` Three-State (`COMPLIANT` / `VIOLATION` / `UNKNOWN`)
- **Roadmap Text:** *"opening hours compliance"*.
- **Empirical Evidence (`W06-MEASUREMENT-AUDIT-01`):** Only `101 / 622` (`16.24%`) of `REC-A-CORE-V2` POIs possess raw OSM `opening_hours` tags in `gomate_places_freeze_v2.json`.
- **Operational Clarification:** Opening hours is classified as **`EVIDENCE_CONDITIONAL_HARD`** using a strict three-state model (`COMPLIANT`, `VIOLATION`, `UNKNOWN`):
  - `UNKNOWN` is neither `PASS` nor `VIOLATION`, is excluded from the denominator of `opening_hours_compliance_rate_on_evaluable_items`, and does **not** by itself fail `CORE_SCENARIO_PASS` (remains neutral).
  - Any **known `VIOLATION`** on an evaluable item (`opening_hours_known_violation_count > 0`) **MUST** cause `CORE_SCENARIO_PASS = false`.
  - Scenario-level `opening_hours_evidence_status` (`FULLY_EVALUABLE`, `PARTIALLY_EVALUABLE`, `NO_EVALUABLE_EVIDENCE`) is reported explicitly, and `NO_EVALUABLE_EVIDENCE` is never treated as opening-hours success.

### 3.3 Travel Time & Routing $\rightarrow$ `NOT_EVALUABLE` (`GEO_DISTANCE_PROXY` Diagnostic Only)
- **Empirical Evidence (`W06-MEASUREMENT-AUDIT-01`):** No road-network routing engine or travel-time dataset exists in the repository (`calculate_route.py` uses straight-line Haversine distance divided by `50 km/h`).
- **Operational Clarification:** `TRAVEL_TIME` and `ROUTE_DISTANCE` are classified as `NOT_EVALUABLE` in W06 V1. Any straight-line Haversine computation over catalog coordinates is strictly labeled `GEO_DISTANCE_PROXY` (diagnostic only) and never claimed as travel time or route quality.

### 3.4 Preference Satisfaction $\rightarrow$ `NOT_PRIMARY_EVALUABLE`
- **Empirical Evidence (`W06-MEASUREMENT-AUDIT-01`):** All `300` preference profiles in the repository are synthetic (`isSynthetic = true`, `0` verified real-user preference ground-truth records).
- **Operational Clarification:** `PREFERENCE_SATISFACTION` is classified as `NOT_PRIMARY_EVALUABLE` for W06 claims of real-user utility or acceptance. Synthetic profiles may be used only for deterministic scenario construction, coverage analysis, and engineering diagnostics.
