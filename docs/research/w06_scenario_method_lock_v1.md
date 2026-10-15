# W06 Scenario-Generation Methodology Lock (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0)

## 1. Document Metadata & Governance Status

| Field | Value |
| :--- | :--- |
| **Method Lock ID** | `W06-SCENARIO-METHOD-LOCK-01` |
| **Version** | `1.0.0` |
| **Base `develop` SHA** | `de0c664f9831caaeda34a996d90f6d6d98643848` |
| **Status** | `LOCKED_PENDING_INSTRUMENT_AMENDMENT` |
| **Machine-Readable Lock Artifact** | `data/evaluation/w06/w06_scenario_method_lock_v1.json` |
| **Pre-Freeze Support Matrix Artifact** | `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4`) |
| **Operational Generation Policy** | `docs/research/w06_scenario_generation_policy_v1.md` |
| **Joint Method Feasibility Gate** | `PASS` (`DETERMINISTIC_OFFLINE_CELL_ASSIGNMENT_AND_EXACT_CONSTRAINT_VERIFICATION`) |
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

## 4. Trip Length, Interest-Count Marginals & Authoritative Cross-Allocations

### 4.1 Trip Length Target (`days`)
- **Allowed Values:** `{2, 3, 4}` only (no other trip length permitted in primary 100).
- **Locked Marginal Totals:** `2 days = 33`, `3 days = 34`, `4 days = 33` (total `100`).

### 4.2 Authoritative Destination $\times$ Days Cross-Allocation (`destination_days_cross_allocation`)

| Destination | `2 days` | `3 days` | `4 days` | **TOTAL** |
| :--- | ---: | ---: | ---: | ---: |
| **`ha-noi`** | 11 | 12 | 11 | **34** |
| **`da-nang`** | 11 | 11 | 11 | **33** |
| **`ha-long`** | 11 | 11 | 11 | **33** |
| **TOTAL** | **33** | **34** | **33** | **100** |

### 4.3 Interest Count Target (`len(interests)`)
- **Allowed Values:** `{1, 2, 3}` canonical interests per scenario.
- **Locked Marginal Totals:** `1 interest = 33`, `2 interests = 34`, `3 interests = 33` (total `100`).
- **Canonical Interest Taxonomy Only (7 categories):**
  `food_cuisine`, `culture_history`, `nature_outdoor`, `coffee_culture`, `beach_island`, `shopping_local`, `nightlife_entertainment`.

### 4.4 Authoritative Destination $\times$ Interest-Count Cross-Allocation (`destination_interest_count_cross_allocation`)

| Destination | `k=1` | `k=2` | `k=3` | **TOTAL** |
| :--- | ---: | ---: | ---: | ---: |
| **`ha-noi`** | 11 | 12 | 11 | **34** |
| **`da-nang`** | 11 | 11 | 11 | **33** |
| **`ha-long`** | 11 | 11 | 11 | **33** |
| **TOTAL** | **33** | **34** | **33** | **100** |

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
| **Pre-Freeze Support Matrix SHA256** | `68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4` |

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

## 7. Near-Duplicate Signature, Scoped Repeat Caps & Joint Method Feasibility

### 7.1 Canonical Scenario Signature
```text
(destination_slug, days, sorted(interests), budget_tier_or_null, weekend_exposure, travel_style)
```
Exact duplicate signatures are `FORBIDDEN`; free-text notes cannot create uniqueness.

### 7.2 Scoped Interest-Combination Repeat-Cap Formula
$$\text{repeat\_cap}(\text{destination}, \text{interest\_count}) = \left\lceil \frac{\text{assigned\_scenario\_count}(\text{destination}, \text{interest\_count})}{\text{number\_of\_distinct\_eligible\_interest\_combinations}(\text{destination}, \text{interest\_count})} \right\rceil$$

Repeat counting applies to `(destination_slug, sorted(interests))` across the entire benchmark (different `days`, `budget_tier_or_null`, `weekend_exposure`, or `travel_style` do not reset the repetition counter).

| Destination | Interest Count ($k$) | Assigned Scenarios | Distinct Eligible Combinations (across $d \in \{2,3,4\}$) | `repeat_cap(destination, k)` | Max Slot Capacity |
| :--- | :---: | ---: | ---: | ---: | ---: |
| **`ha-noi`** | `1` | 11 | 5 | **3** | 15 |
| **`ha-noi`** | `2` | 12 | 15 | **1** | 15 |
| **`ha-noi`** | `3` | 11 | 20 | **1** | 20 |
| **`da-nang`** | `1` | 11 | 7 | **2** | 14 |
| **`da-nang`** | `2` | 11 | 21 | **1** | 21 |
| **`da-nang`** | `3` | 11 | 35 | **1** | 35 |
| **`ha-long`** | `1` | 11 | 6 | **2** | 12 |
| **`ha-long`** | `2` | 11 | 21 | **1** | 21 |
| **`ha-long`** | `3` | 11 | 35 | **1** | 35 |

- **Old Pooled Conflict Status:** `RESOLVED_BY_DESTINATION_INTEREST_COUNT_SCOPED_REPEAT_CAP` (single-interest capacity is $15 + 14 + 12 = 41 \ge 33$).
- **Joint Method Feasibility Gate (`JOINT_METHOD_FEASIBILITY = PASS`):** Deterministic offline verification confirms simultaneous compatibility of all locked marginals, cross-allocations, support eligibility rules (`0` `EXCLUDED` combinations), scoped repeat caps (`0` violations), and 100 unique canonical scenario signatures without using any Gemini/model output or generating final scenario files.

---

## 8. Budget, Travel Style, Date, Opening-Hours, Difficulty, Seed & Execution Policies

- **Budget Policy (`NOMINAL_BENCHMARK_BUDGET_TIERS`):** Same-model Gemini budget calibration is `FORBIDDEN`. `budget_applicable_scenarios = 80`, `budget_null_scenarios = 20`. Nominal tiers: `B1 = 500,000 VND/day` (`27` scenarios), `B2 = 1,000,000 VND/day` (`27` scenarios), `B3 = 2,000,000 VND/day` (`26` scenarios); `scenario.budget = daily_nominal_tier_vnd * scenario.days`. Metric remains `ESTIMATED_BUDGET_COMPLIANCE`; zero `estimated_cost` frequency is `DESCRIPTIVE_ONLY`.
- **Travel Style Policy:** `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY` (`25` each); `DESCRIPTIVE_INPUT_VARIATION_ONLY`.
- **Date Policy:** `2026-11-02` through `2026-12-13`, contiguous dates, `weekend_exposed = 50` and `non_weekend_exposed = 50`; `INPUT_VARIATION_ONLY`.
- **Opening Hours Policy:** `NATURAL_EXPOSURE_ONLY` in primary 100 (no OH quota); separate OH probe set `DEFERRED_FOR_W06_V1`.
- **Difficulty & Infeasibility Policies:** `NO_FORMAL_DIFFICULTY_TIER` (`EASY`/`MEDIUM`/`HARD` forbidden); `INFEASIBLE_DIAGNOSTIC_POLICY = "DEFERRED_OUTSIDE_PRIMARY_W06_V1"`.
- **Frozen Seed:** `scenario_generation_seed = 2026101506` (one seed only; no seed shopping).
- **Execution & Subgroup Policies:** `executions_per_scenario = 1`, `automatic_retry_count = 0`, `PRIMARY_RESULT_INTERPRETATION = "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION"`. Primary reporting: `overall`, `per_destination`, `equal_destination_macro`; all other axes are `SECONDARY_DESCRIPTIVE_ONLY`.

---

## 9. Historical Discrepancies Record

- `historical_charge_tag_count_discrepancy = "NON_BLOCKING_HISTORICAL_COUNT_DISCREPANCY"`
- `historical_parser_currently_exists_false = "EXPECTED_HISTORICAL_STATE_SUPERSEDED_BY_IMPLEMENTATION"`
- Historical Measurement Contract text (`w06_measurement_contract_v1.json` / `.md`) is preserved unmodified.
