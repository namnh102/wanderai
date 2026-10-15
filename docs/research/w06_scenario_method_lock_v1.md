# W06 Scenario-Generation Methodology Lock (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0)

## 1. Document Metadata & Governance Status

| Field | Value |
| :--- | :--- |
| **Method Lock ID** | `W06-SCENARIO-METHOD-LOCK-01` |
| **Version** | `1.0.0` |
| **Base `develop` SHA** | `de0c664f9831caaeda34a996d90f6d6d98643848` |
| **Status** | `LOCKED_PENDING_INSTRUMENT_AMENDMENT` |
| **Machine-Readable Lock Artifact** | `data/evaluation/w06/w06_scenario_method_lock_v1.json` |
| **Pre-Freeze Support Matrix Artifact** | `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`94835f42c67260939548fbde21e41924227feae6d4d78d0e787a4edaaf45a36d`) |
| **Operational Generation Policy** | `docs/research/w06_scenario_generation_policy_v1.md` |
| **Instrumentation Amendment Required** | `true` (`min_poi_visits_per_day = 2` not yet formally enforced in `planner_benchmark_evaluator.py`) |
| **Real 100 Scenarios Generated** | `false` |
| **`P11` Manifest Created** | `false` |
| **W06 Preregistration Created** | `false` |
| **Gemini Live API Called** | `false` |
| **Scientific Results Generated** | `false` |

### Scientific Basis
This methodology lock freezes the scenario-generation contract prior to any final 100-scenario creation (`P11`), grounding its rules in:
- `W06-MEASUREMENT-AUDIT-01` (`CLOSED`)
- `W06-MEASUREMENT-CONTRACT-01` v1.1.0 (`CLOSED`)
- `W06-INSTRUMENT-01A` (`CLOSED`)
- `W06-INSTRUMENT-01B` (`CLOSED`)
- `W06-INSTRUMENT-01C` (`CLOSED`)
- `W06-INSTRUMENT-VALIDATION-01` (`CLOSED`)
- `W06-SCENARIO-RESEARCH-01`, `W06-SCENARIO-RESEARCH-02`, `W06-SCENARIO-RESEARCH-03`, `W06-SCENARIO-COUNCIL-PHASE-2`, and the ChatGPT methodology decision.

---

## 2. Primary Benchmark Population & Destination Allocation

- **Primary Benchmark Target:** `benchmark_target = 100`
- **Catalog Scope:** `REC-A-CORE-V2` only (`data/curated/gomate_places_freeze_v2.json` filtered by `is_rec_a_core_v2 == true`; 622 total core POIs).
- **Destination Allocation (Exact Marginals):**
  - `ha-noi`: `34` scenarios (`145` core POIs)
  - `da-nang`: `33` scenarios (`289` core POIs)
  - `ha-long`: `33` scenarios (`188` core POIs)
- **Restriction:** No other destination is permitted in the primary 100-scenario benchmark.

---

## 3. Minimum POI Visits Per Day & Instrumentation Amendment Gate

- **Frozen Constant:** `min_poi_visits_per_day = 2`
- **Definition:** Every itinerary day must contain at least **two** items with `activity_kind == "POI_VISIT"`. Items with `activity_kind == "TRANSIT_ONLY"` do **not** count toward this minimum.
- **Instrumentation Amendment Requirement (`instrumentation_amendment_required = true`):**
  - The currently merged evaluator (`apps/ai-service/app/evaluation/planner_benchmark_evaluator.py`, `W06-CORE-EVALUATOR-01C-V1.0.0`) records `MINIMUM_ITEMS_PER_DAY_CONTRACT_STATUS = "NOT_FORMALLY_FROZEN"` and checks `min_items_observed_per_day >= 1`.
  - Per task boundary rules, the evaluator is **not** modified in `W06-SCENARIO-METHOD-LOCK-01`. A dedicated instrumentation amendment task must formally enforce `min_poi_visits_per_day == 2` on `POI_VISIT` items per day before final scenario freeze and execution.

---

## 4. Trip Length & Interest-Count Marginals

### 4.1 Trip Length Target (`days`)
- **Allowed Values:** `{2, 3, 4}` only (no other trip length permitted in primary 100).
- **Locked Marginal Totals:**
  - `2 days`: `33` scenarios
  - `3 days`: `34` scenarios
  - `4 days`: `33` scenarios
  - **Total:** `100` scenarios

### 4.2 Interest Count Target (`len(interests)`)
- **Allowed Values:** `{1, 2, 3}` canonical interests per scenario.
- **Locked Marginal Totals:**
  - `1 interest`: `33` scenarios
  - `2 interests`: `34` scenarios
  - `3 interests`: `33` scenarios
  - **Total:** `100` scenarios
- **Canonical Interest Taxonomy Only (7 categories):**
  1. `food_cuisine`
  2. `culture_history`
  3. `nature_outdoor`
  4. `coffee_culture`
  5. `beach_island`
  6. `shopping_local`
  7. `nightlife_entertainment`

---

## 5. Authoritative Interest Mapping & Cryptographic Provenance

No new interest-mapping heuristic is created for W06. Catalog support is determined exclusively by the existing REC-A feature contract implementation:

| Provenance Field | Value |
| :--- | :--- |
| **Source Commit SHA** | `de0c664f9831caaeda34a996d90f6d6d98643848` |
| **Source File Path** | `apps/ai-service/recommendation/reca/contract.py` |
| **Authoritative Function** | `poi_to_canonical_vector` |
| **Source File Hash Basis** | `SHA256_LF_NORMALIZED_SOURCE_BYTES` |
| **Source File LF-Normalized SHA256** | `1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c` |
| **Catalog File Path** | `data/curated/gomate_places_freeze_v2.json` |
| **Catalog Hash Basis (`SOURCE_CATALOG`)** | `SHA256_LF_NORMALIZED_SOURCE_BYTES` |
| **Catalog LF-Normalized SHA256** | `f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444` |
| **Pre-Freeze Support Matrix File** | `data/evaluation/w06/w06_scenario_support_matrix_v1.json` |
| **Pre-Freeze Support Matrix SHA256** | `94835f42c67260939548fbde21e41924227feae6d4d78d0e787a4edaaf45a36d` |

### Individual Canonical Interest Support Counts (`REC-A-CORE-V2`)

| Canonical Interest | `ha-noi` (`145` core POIs) | `da-nang` (`289` core POIs) | `ha-long` (`188` core POIs) |
| :--- | ---: | ---: | ---: |
| `food_cuisine` | 21 | 52 | 37 |
| `culture_history` | 37 | 53 | 16 |
| `nature_outdoor` | 12 | 8 | 10 |
| `coffee_culture` | 8 | 49 | 21 |
| `beach_island` | 1 | 10 | 3 |
| `shopping_local` | 3 | 21 | 15 |
| `nightlife_entertainment` | 12 | 11 | 5 |
| **Total Mapped Activity POIs** | **94** | **204** | **107** |
| **Unmapped (Hospitality / Other) POIs** | **51** | **85** | **81** |
| **Multi-Interest Overlap POIs** | **0** | **0** | **0** |

---

## 6. Two-Stage Support Eligibility Rule & Support Classes

Let:
- $d \in \{2, 3, 4\}$ be the scenario trip length (`days`),
- $m = 2$ be `min_poi_visits_per_day`,
- $I \subseteq \text{CANONICAL\_INTERESTS}$ ($|I| \in \{1, 2, 3\}$) be the scenario's requested interest set,
- $S_i$ be the set of `REC-A-CORE-V2` `place_id`s in the scenario destination matching interest $i$, with cardinality $n_i = |S_i|$,
- $U(I) = \left|\bigcup_{i \in I} S_i\right|$ be the exact set-union support across requested interests.

### Eligibility Conditions
A scenario interest combination $I$ at destination and trip length $d$ is **PRIMARY ELIGIBLE** if and only if both rules hold:
1. **RULE A (Per-Interest Floor):** For every requested interest $i \in I$:
   $$n_i \ge d$$
2. **RULE B (Total Union Capacity):**
   $$U(I) = \left|\bigcup_{i \in I} S_i\right| \ge d \times m \quad \text{and} \quad \sum_{i \in I} n_i \ge d \times m$$
   *(Although current `REC-A-CORE-V2` evidence contains 0 overlapping multi-interest POIs so $\sum_{i \in I} n_i = U(I)$, implementations must compute $U(I)$ directly via `place_id` set union rather than assuming zero overlap forever.)*

### Frozen Support Classes
- **`EXCLUDED`:** Fails Rule A (`CATALOG_SUPPORT_BELOW_THRESHOLD`) or fails Rule B (`TOTAL_INTEREST_CAPACITY_INSUFFICIENT`). **Cannot enter the primary 100 benchmark.**
- **`STRESS`:** Passes both Rule A and Rule B, and at least one requested interest $i \in I$ satisfies:
  $$d \le n_i < d \times m$$
  **May enter the primary 100 benchmark.** There is **no fixed stress percentage target**.
- **`CLEAR`:** Passes both Rule A and Rule B, and every requested interest $i \in I$ satisfies:
  $$n_i \ge d \times m$$

### Pre-Freeze Support Matrix Summary (`w06_scenario_support_matrix_v1.json`)

| Destination | Days ($d$) | $k=1$ (`Elig / Clear / Stress / Excl`) | $k=2$ (`Elig / Clear / Stress / Excl`) | $k=3$ (`Elig / Clear / Stress / Excl`) | Total ($63$ combos) (`Elig / Clear / Stress / Excl`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`ha-noi`** | `2` | `5 / 5 / 0 / 2` | `15 / 10 / 5 / 6` | `20 / 10 / 10 / 15` | `40 / 25 / 15 / 23` |
| **`ha-noi`** | `3` | `5 / 5 / 0 / 2` | `15 / 10 / 5 / 6` | `20 / 10 / 10 / 15` | `40 / 25 / 15 / 23` |
| **`ha-noi`** | `4` | `5 / 5 / 0 / 2` | `10 / 10 / 0 / 11` | `10 / 10 / 0 / 25` | `25 / 25 / 0 / 38` |
| **`da-nang`** | `2` | `7 / 7 / 0 / 0` | `21 / 21 / 0 / 0` | `35 / 35 / 0 / 0` | `63 / 63 / 0 / 0` |
| **`da-nang`** | `3` | `7 / 7 / 0 / 0` | `21 / 21 / 0 / 0` | `35 / 35 / 0 / 0` | `63 / 63 / 0 / 0` |
| **`da-nang`** | `4` | `7 / 7 / 0 / 0` | `21 / 21 / 0 / 0` | `35 / 35 / 0 / 0` | `63 / 63 / 0 / 0` |
| **`ha-long`** | `2` | `6 / 6 / 0 / 1` | `21 / 15 / 6 / 0` | `35 / 20 / 15 / 0` | `62 / 41 / 21 / 1` |
| **`ha-long`** | `3` | `5 / 5 / 0 / 2` | `21 / 10 / 11 / 0` | `35 / 10 / 25 / 0` | `61 / 25 / 36 / 2` |
| **`ha-long`** | `4` | `5 / 5 / 0 / 2` | `15 / 10 / 5 / 6` | `20 / 10 / 10 / 15` | `40 / 25 / 15 / 23` |

### Claim Boundary for Interests
Interest support is **scenario feasibility metadata only**. It does **not** make `PREFERENCE_SATISFACTION` a primary W06 metric, and W06 must never claim that the planner satisfies real-user preferences or utility.

---

## 7. Budget, Travel Style, Date, Opening-Hours, Difficulty & Infeasibility Policies

### 7.1 Budget Policy (`NOMINAL_BENCHMARK_BUDGET_TIERS`)
- **Same-Model Calibration Forbidden:** Same-model Gemini budget calibration is strictly `FORBIDDEN`. No model output may determine benchmark budget ceilings.
- **Applicability Split:**
  - `budget_applicable_scenarios = 80`
  - `budget_null_scenarios = 20` (`budget = null`)
- **Nominal Benchmark Tiers (among the 80 budget-applicable scenarios):**
  - `B1`: `500,000 VND` per trip day $\rightarrow$ `27` scenarios (`1,000,000` / `1,500,000` / `2,000,000` VND for `2` / `3` / `4` days)
  - `B2`: `1,000,000 VND` per trip day $\rightarrow$ `27` scenarios (`2,000,000` / `3,000,000` / `4,000,000` VND for `2` / `3` / `4` days)
  - `B3`: `2,000,000 VND` per trip day $\rightarrow$ `26` scenarios (`4,000,000` / `6,000,000` / `8,000,000` VND for `2` / `3` / `4` days)
- **Formula:** $\text{scenario.budget} = \text{daily\_nominal\_tier\_vnd} \times \text{scenario.days}$
- **Semantic Boundary:** These tiers are `NOMINAL_BENCHMARK_BUDGET_TIERS`. They are **not** real-world travel prices, validated cost estimates, or price ground truth. The evaluated metric remains `ESTIMATED_BUDGET_COMPLIANCE`. Frequency of zero `estimated_cost` items is descriptive only and may not independently fail a scenario.

### 7.2 Travel Style Policy
- **Frozen Vocabulary (4 values):** `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY`
- **Marginal Counts:** `25` scenarios each (`25 × 4 = 100`).
- **Role:** `DESCRIPTIVE_INPUT_VARIATION_ONLY` (no primary metric; no inferential subgroup claim).

### 7.3 Date Policy
- **Generation Window:** `2026-11-02` through `2026-12-13` (inclusive; 6 full weeks, Monday to Sunday).
- **Contiguity:** Trip dates `[start_date, end_date]` must be contiguous with `(end_date - start_date).days + 1 == scenario.days`.
- **Weekend Exposure Marginal:**
  - `weekend_exposed = 50` (date range contains at least one Saturday or Sunday)
  - `non_weekend_exposed = 50` (date range contains only Monday–Friday)
- **Role:** `INPUT_VARIATION_ONLY` (no scientific weekday/weekend subgroup; no weekend-opening-hours performance claims).

### 7.4 Opening Hours Policy
- **Primary 100 Policy:** `NATURAL_EXPOSURE_ONLY` (no OH-enriched quota; no primary scenario may be selected because it has more opening-hours evidence).
- **Mandatory Future Reporting:** `opening_hours_evidence_coverage`, `known_opening_hours_violations`, `UNKNOWN_count_and_rate`, and `per_destination_evidence_coverage`.
- **Separate OH Probe Set:** `DEFERRED_FOR_W06_V1` (not created).

### 7.5 Difficulty & Infeasible Scenario Policies
- **Difficulty Policy:** `NO_FORMAL_DIFFICULTY_TIER`. Labels `EASY`, `MEDIUM`, `HARD` are forbidden as scientific strata. Allowed pre-run descriptive metadata: `days`, `interest_count`, `support_class`, `budget_tier`, `weekend_exposure`, `travel_style`.
- **Infeasible Scenario Policy:** `INFEASIBLE_DIAGNOSTIC_POLICY = "DEFERRED_OUTSIDE_PRIMARY_W06_V1"`. Zero intentionally infeasible scenarios in the primary 100, no infeasible diagnostic set created, and no claim that the planner detects infeasibility or refusal.
- **Stress Policy:** No manual stress quota (`fixed_stress_percentage = null`). `STRESS` status derives solely from the frozen support rules; the future generator must not systematically exclude eligible `STRESS` candidates and should round-robin/balance `CLEAR` and `STRESS` where feasible without violating higher-priority locked marginals.

---

## 8. Generation Seed, Priority Order, Near-Duplicate & Execution Policies

- **Frozen Generation Seed:** `scenario_generation_seed = 2026101506` (one seed only; no seed shopping; committed before generation).
- **Execution Policy:** `executions_per_scenario = 1`, `automatic_retry_count = 0`, `PRIMARY_RESULT_INTERPRETATION = "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION"`. Invalid executions remain non-pass in the assigned denominator.
- **Subgroup Policy:** Primary/required reporting covers `overall`, `per_destination`, and `equal_destination_macro`. All other axes (`budget_applicability`, `trip_length`, `interest_count`, `support_class`, `travel_style`, `weekday_weekend`, `individual_interest`) are `SECONDARY_DESCRIPTIVE_ONLY` with no p-values and no inferential subgroup claims. The scenario-level bootstrap resampling unit remains unchanged.

---

## 9. Historical Discrepancies Record

- **`historical_charge_tag_count_discrepancy = "NON_BLOCKING_HISTORICAL_COUNT_DISCREPANCY"`:**
  `W06-MEASUREMENT-AUDIT-01` noted `6/759` all-catalog POIs with raw `charge` strings (which included 2 non-core POIs matching `charge` outside `tags.charge`) alongside `4/622` `REC-A-CORE-V2` POIs with `tags.charge`. Structured numeric `priceMin`/`priceMax` coverage is `0/759` (`0/622` core) in all cases. Historical Measurement Contract text is preserved unmodified.
- **`historical_parser_currently_exists_false = "EXPECTED_HISTORICAL_STATE_SUPERSEDED_BY_IMPLEMENTATION"`:**
  In `w06_measurement_contract_v1.json` (frozen at `W06-MEASUREMENT-CONTRACT-01`), `opening_hours_semantics.audit_evidence.parser_currently_exists` was recorded as `false` prior to `W06-INSTRUMENT-01C` implementing `opening_hours_evaluator.py`. Historical contract text is preserved unmodified.
