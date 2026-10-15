# W06 Scenario Generation Operational Policy (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0)

## 1. Purpose & Scope

This document defines the operational governance, deterministic generation procedure, cross-allocation tables, scoped repeat-cap rules, rejection logging, manual QA blinding rules, and pre-freeze pilot prohibitions for the W06 100-scenario benchmark (`W06-SCENARIO-METHOD-LOCK-01` v1.0.0, anchored at `develop` commit `de0c664f9831caaeda34a996d90f6d6d98643848`).

- **Authoritative Machine-Readable Lock:** `data/evaluation/w06/w06_scenario_method_lock_v1.json`
- **Authoritative Pre-Freeze Support Matrix:** `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4`)
- **Status:** `LOCKED_PENDING_INSTRUMENT_AMENDMENT` (`min_poi_visits_per_day = 2` must be formally enforced in the W06 evaluator before final scenario freeze and execution).

---

## 2. Deterministic Seed Policy

- **Frozen Seed:** `scenario_generation_seed = 2026101506`
- **Single-Seed Rule:** One seed only (`allowed_seed_count = 1`).
- **Anti-Seed-Shopping Rule:** Seed shopping is strictly `FORBIDDEN`. The seed `2026101506` is committed in `W06-SCENARIO-METHOD-LOCK-01` before any scenario generator is implemented or executed.

---

## 3. Generator Priority Order & Authoritative Cross-Allocations

The future scenario generator must be 100% deterministic given `scenario_generation_seed = 2026101506`, the frozen catalog `data/curated/gomate_places_freeze_v2.json` (`f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`), and the frozen support matrix `data/evaluation/w06/w06_scenario_support_matrix_v1.json` (`68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4`).

### Strict Priority Hierarchy
The generator must enforce constraints in the following exact priority order:
1. **Exact destination allocation** (`ha-noi = 34`, `da-nang = 33`, `ha-long = 33`; `REC-A-CORE-V2` only)
2. **Exact days marginal** (`2 days = 33`, `3 days = 34`, `4 days = 33` and authoritative `destination_days_cross_allocation`: `ha-noi = 11/12/11`, `da-nang = 11/11/11`, `ha-long = 11/11/11`)
3. **Exact interest-count marginal** (`1 interest = 33`, `2 interests = 34`, `3 interests = 33` and authoritative `destination_interest_count_cross_allocation`: `ha-noi = 11/12/11`, `da-nang = 11/11/11`, `ha-long = 11/11/11`)
4. **Exact budget applicability/tier marginal** (`80` budget-applicable: `B1 = 27`, `B2 = 27`, `B3 = 26`; `20` `budget = null`)
5. **Exact travel-style marginal** (`BACKPACKER = 25`, `BUDGET = 25`, `COMFORT = 25`, `LUXURY = 25`)
6. **Exact weekend-exposure marginal** (`weekend_exposed = 50`, `non_weekend_exposed = 50` within `2026-11-02 .. 2026-12-13`)
7. **Scenario eligibility** (Two-stage support rule: Rule A $n_i \ge d$ for every requested interest $i$, and Rule B $\text{union\_support} \ge 2d \land \sum n_i \ge 2d$)
8. **Duplicate / near-duplicate rules** (Unique canonical scenario signature + scoped `repeat_cap(destination, interest_count)`)
9. **`CLEAR` / `STRESS` coverage** (Round-robin / balance `CLEAR` and `STRESS` where feasible without violating higher-priority locked marginals; never systematically exclude eligible `STRESS` candidates)
10. **Minimize remaining cross-dimension imbalance** (Without requiring perfect factorial balance)

**Model Blinding Rule:** The generator may **NOT** inspect Gemini or any other model output at any stage.

---

## 4. Near-Duplicate Signature & Scoped Interest-Combination Repeat Cap Policy

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

### 4.2 Authoritative Scoped Interest-Combination Repeat Cap
Before candidate sampling, for each `(destination, interest_count)` cell ($k \in \{1, 2, 3\}$), the generator computes:
$$\text{repeat\_cap}(\text{destination}, \text{interest\_count}) = \left\lceil \frac{\text{assigned\_scenario\_count}(\text{destination}, \text{interest\_count})}{\text{number\_of\_distinct\_eligible\_interest\_combinations}(\text{destination}, \text{interest\_count})} \right\rceil$$

- **Denominator Scope:** Distinct eligible interest combinations for that `destination` and `interest_count` across the allowed day set $\{2, 3, 4\}$ under the frozen support rules.
- **Repeat Counting Key:** `(destination_slug, sorted(interests))` across the entire benchmark. Variations in `days`, `budget_tier_or_null`, `weekend_exposure`, or `travel_style` do **not** reset the interest-combination repetition counter.
- **Reproduced Repeat Caps:**
  - `ha-noi`: `k=1 -> ceil(11/5) = 3`, `k=2 -> ceil(12/15) = 1`, `k=3 -> ceil(11/20) = 1`
  - `da-nang`: `k=1 -> ceil(11/7) = 2`, `k=2 -> ceil(11/21) = 1`, `k=3 -> ceil(11/35) = 1`
  - `ha-long`: `k=1 -> ceil(11/6) = 2`, `k=2 -> ceil(11/21) = 1`, `k=3 -> ceil(11/35) = 1`
- **Historical Pooled Repeat-Cap Conflict Resolution (`RESOLVED_BY_DESTINATION_INTEREST_COUNT_SCOPED_REPEAT_CAP`):**
  - The old unpooled interpretation (`repeat_cap_over_any_days = 1` across $k \in \{1,2,3\}$) is **not** authoritative.
  - Under the scoped formula, total single-interest slot capacity is $5 \times 3 + 7 \times 2 + 6 \times 2 = 15 + 14 + 12 = 41 \ge 33$, and offline joint feasibility (`JOINT_METHOD_FEASIBILITY = PASS`) is proven before scenario generation.
- **Fail-Closed Infeasibility Protocol:** No interest combination may exceed `repeat_cap(destination, interest_count)` unless the generator proves that the locked marginals are otherwise mathematically infeasible (`STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT`).

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
  - `scenario_input`, `catalog_evidence`, `support_matrix`, `schema_validity`, `date_validity`, `deterministic_generation_metadata`
- **Forbidden Reviewer Inspection Inputs:**
  - `Gemini_output`, `planner_pass_fail`, `planner_estimated_cost`, `future_scientific_result`
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
  - `synthetic_fixture_tests`, `offline_generator_qa`, `schema_validation`, `support_matrix_validation`

---

## 8. Execution, Subgroup & Cross-Balance Reporting Policies

- **Execution Policy:** `executions_per_scenario = 1`, `automatic_retry_count = 0`, invalid execution remains non-pass in assigned denominator, `PRIMARY_RESULT_INTERPRETATION = "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION"`.
- **Subgroup Policy:** Primary/required reporting: `overall`, `per_destination`, `equal_destination_macro`. Secondary axes (`budget_applicability`, `trip_length`, `interest_count`, `support_class`, `travel_style`, `weekday_weekend`, `individual_interest`) are `SECONDARY_DESCRIPTIVE_ONLY` (no p-values, no inferential claims, scenario-level bootstrap unit unchanged).
- **Cross-Balance Reporting Policy:** Perfect factorial balance is not required (`require_perfect_factorial_balance = false`). The generator must report `all_locked_marginal_counts`, `cross_tab_counts`, `max_min_cross_cell_imbalance`, and `unavoidable_imbalance`, and must never optimize based on model performance.
