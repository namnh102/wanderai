# W06 Scenario Generation Operational Policy (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0)

## 1. Purpose & Scope

This document defines the operational governance, deterministic generation procedure, rejection logging, manual QA blinding rules, and pre-freeze pilot prohibitions for the W06 100-scenario benchmark (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0, anchored at `develop` commit `de0c664f9831caaeda34a996d90f6d6d98643848`).

- **Authoritative Machine-Readable Lock:** `data/evaluation/w06/w06_scenario_method_lock_v1.json`
- **Authoritative Pre-Freeze Support Matrix:** `data/evaluation/w06/w06_scenario_support_matrix_v1.json`
- **Status:** `LOCKED_PENDING_INSTRUMENT_AMENDMENT` (`min_poi_visits_per_day = 2` must be formally enforced in the W06 evaluator before final scenario freeze and execution).

---

## 2. Deterministic Seed Policy

- **Frozen Seed:** `scenario_generation_seed = 2026101506`
- **Single-Seed Rule:** One seed only (`allowed_seed_count = 1`).
- **Anti-Seed-Shopping Rule:** Seed shopping is strictly `FORBIDDEN`. The seed `2026101506` is committed in `W06-SCENARIO-METHOD-LOCK-01` before any scenario generator is implemented or executed.

---

## 3. Generator Priority Order & Determinism Rules

The future scenario generator must be 100% deterministic given `scenario_generation_seed = 2026101506`, the frozen catalog `data/curated/gomate_places_freeze_v2.json` (`f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`), and the frozen support matrix `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`94835f42c67260939548fbde21e41924227feae6d4d78d0e787a4edaaf45a36d`).

### Strict Priority Hierarchy
The generator must enforce constraints in the following exact priority order:
1. **Exact destination allocation** (`ha-noi = 34`, `da-nang = 33`, `ha-long = 33`; `REC-A-CORE-V2` only)
2. **Exact days marginal** (`2 days = 33`, `3 days = 34`, `4 days = 33`)
3. **Exact interest-count marginal** (`1 interest = 33`, `2 interests = 34`, `3 interests = 33`)
4. **Exact budget applicability/tier marginal** (`80` budget-applicable: `B1 = 27`, `B2 = 27`, `B3 = 26`; `20` `budget = null`)
5. **Exact travel-style marginal** (`BACKPACKER = 25`, `BUDGET = 25`, `COMFORT = 25`, `LUXURY = 25`)
6. **Exact weekend-exposure marginal** (`weekend_exposed = 50`, `non_weekend_exposed = 50` within `2026-11-02 .. 2026-12-13`)
7. **Scenario eligibility** (Two-stage support rule: Rule A $n_i \ge d$ for every requested interest $i$, and Rule B $\text{union\_support} \ge 2d \land \sum n_i \ge 2d$)
8. **Duplicate / near-duplicate rules** (Unique canonical scenario signature + dynamic interest-combination repeat cap)
9. **`CLEAR` / `STRESS` coverage** (Round-robin / balance `CLEAR` and `STRESS` where feasible without violating higher-priority locked marginals; never systematically exclude eligible `STRESS` candidates)
10. **Minimize remaining cross-dimension imbalance** (Without requiring perfect factorial balance)

**Model Blinding Rule:** The generator may **NOT** inspect Gemini or any other model output at any stage.

---

## 4. Near-Duplicate Signature & Interest-Combination Repeat Cap Policy

### 4.1 Canonical Scenario Signature
Every candidate scenario is mapped to its 6-tuple canonical signature:
```text
(
  destination_slug,
  days,
  sorted(interests),
  budget_tier_or_null,
  weekend_exposure,
  travel_style
)
```
- **Exact Duplicate Signature:** `FORBIDDEN`. No two scenarios in the primary 100 may share the same canonical signature.
- **Free-Text Notes Rule:** Free-text `notes` cannot create uniqueness (`free_text_notes_can_create_uniqueness = false`).

### 4.2 Dynamic Interest-Combination Repeat Cap
Before candidate sampling for a destination, the generator must compute:
$$\text{repeat\_cap} = \left\lceil \frac{\text{destination\_scenario\_count}}{\text{number\_of\_distinct\_eligible\_interest\_combinations\_for\_destination}} \right\rceil$$

- **Hard Cap Rule:** No interest combination may exceed `repeat_cap` unless the generator formally proves that the locked marginals are otherwise mathematically infeasible.
- **Fail-Closed Infeasibility Protocol:** If the locked marginals and `repeat_cap` are mathematically infeasible together, the generator must **STOP** immediately. It must **not** silently relax `repeat_cap` or any locked marginal; a formal method amendment is required.
- **Precomputed Feasibility Diagnostic (`k=1` Pigeonhole Note):**
  - Across all 63 interest combinations ($k \in \{1, 2, 3\}$), the number of distinct combinations eligible for at least one day length $d \in \{2, 3, 4\}$ is `40` (`ha-noi`), `63` (`da-nang`), and `62` (`ha-long`), giving unpooled $\lceil 34/40 \rceil = 1$, $\lceil 33/63 \rceil = 1$, $\lceil 33/62 \rceil = 1$.
  - However, for $k=1$ (single-interest scenarios), the number of distinct eligible 1-interest combinations is `5` (`ha-noi`), `7` (`da-nang`), and `6` (`ha-long`, at $d=2$; `5` at $d \in \{3, 4\}$), totaling at most $5 + 7 + 6 = 18$ distinct `(destination, 1-interest)` pairs across the entire catalog, whereas Priority 3 locks `1 interest = 33` scenarios.
  - Consequently, an unstratified `repeat_cap = 1` applied to $k=1$ caps 1-interest scenarios at $18 < 33$ by the pigeonhole principle. When the scenario generator task is executed, this exact mathematical proof governs whether `repeat_cap` is evaluated per `(destination, interest_count)` cell or via formal method amendment rather than silent relaxation.

---

## 5. Candidate Rejection Log Policy

Every rejected candidate encountered during deterministic generation or manual QA must be recorded in a deterministic rejection log.

### Required Deterministic Fields
1. `candidate_index` (integer position in the deterministic generator stream)
2. `candidate_sha256` (canonical JSON UTF-8 LF SHA256 of the candidate scenario input)
3. `reason_code` (one of the 10 controlled codes below)
4. `rule_version` (`"W06-SCENARIO-METHOD-LOCK-01-V1.0.0"`)
5. `replacement_candidate_index` (integer index of the replacement candidate from the deterministic stream, if applicable; otherwise `null`)

### Controlled Rejection Reason Vocabulary (Exact 10 Codes)
1. `CATALOG_SUPPORT_BELOW_THRESHOLD`
2. `TOTAL_INTEREST_CAPACITY_INSUFFICIENT`
3. `SCHEMA_INVALID`
4. `DATE_RANGE_INVALID`
5. `NEAR_DUPLICATE_SIGNATURE`
6. `INTEREST_COMBINATION_REPEAT_CAP`
7. `ALLOCATION_CELL_FULL`
8. `NON_CANONICAL_FIELD`
9. `TEXT_AMBIGUOUS_NOTES`
10. `MANUAL_QA_REJECT`

**Strict Prohibitions:**
- The rejection log must **not** include model output (`include_model_output_allowed = false`).
- No rejection reason may depend on Gemini/model behavior (`reason_may_depend_on_gemini_behavior = false`).

---

## 6. Blinded Manual QA Policy

- **Allowed Reviewer Inspection Inputs:**
  - `scenario_input`
  - `catalog_evidence`
  - `support_matrix`
  - `schema_validity`
  - `date_validity`
  - `deterministic_generation_metadata`
- **Forbidden Reviewer Inspection Inputs:**
  - `Gemini_output`
  - `planner_pass_fail`
  - `planner_estimated_cost`
  - `future_scientific_result`
- **Rejection & Replacement Protocol:**
  - Any manual QA rejection requires logging one allowed `reason_code` from Section 5.
  - Replacement must be the **next deterministic eligible candidate in the generator stream** (`NEXT_DETERMINISTIC_ELIGIBLE_CANDIDATE_IN_GENERATOR_STREAM`).
  - Hand-written replacement scenarios are strictly `FORBIDDEN` (`hand_written_replacement_scenario_allowed = false`).

---

## 7. Pre-Freeze Pilot Policy

- **Forbidden Before Final Scenario Freeze:**
  - Gemini or model-behavior pilots influencing scenario design (`FORBIDDEN`)
  - Same-model budget calibration (`FORBIDDEN`)
  - Sending any final scenario to Gemini prior to `P11` freeze and W06 preregistration (`FORBIDDEN`)
- **Allowed Pre-Freeze Activities:**
  - `synthetic_fixture_tests`
  - `offline_generator_qa`
  - `schema_validation`
  - `support_matrix_validation`

---

## 8. Execution, Subgroup & Cross-Balance Reporting Policies

### 8.1 Execution Policy
- `executions_per_scenario = 1`
- `automatic_retry_count = 0`
- Invalid execution remains a non-pass in the assigned denominator (`invalid_execution_remains_non_pass_in_assigned_denominator = true`).
- `PRIMARY_RESULT_INTERPRETATION = "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION"`
- Do **not** claim stable expected performance across repeated stochastic executions.

### 8.2 Subgroup Policy
- **Primary / Required Reporting:** `overall`, `per_destination`, `equal_destination_macro`.
- **Secondary Descriptive-Only Axes (`SECONDARY_DESCRIPTIVE_ONLY`):** `budget_applicability`, `trip_length`, `interest_count`, `support_class`, `travel_style`, `weekday_weekend`, `individual_interest`.
- **Inferential Prohibitions:** No p-values and no inferential subgroup claims on secondary axes. The frozen scenario-level bootstrap resampling unit (`scenario`) is unchanged.

### 8.3 Cross-Balance Reporting Policy
- Perfect factorial balance is **not** required (`require_perfect_factorial_balance = false`).
- The future generator must deterministically report:
  1. `all_locked_marginal_counts`
  2. `cross_tab_counts`
  3. `max_min_cross_cell_imbalance`
  4. `unavoidable_imbalance`
- The generator must never optimize scenario selection or cross-balance based on model performance.
