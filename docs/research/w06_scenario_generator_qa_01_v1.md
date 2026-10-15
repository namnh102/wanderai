# W06-SCENARIO-GENERATOR-QA-01: Independent Adversarial QA of the W06 Scenario Generator

- **Task ID:** `W06-SCENARIO-GENERATOR-QA-01`
- **Version:** `1.0.0`
- **Base `develop` SHA:** `e86c6363ecd0442028e5161b8c8be8fc8c8ab77e`
- **Audited Generator Version:** `W06-SCENARIO-GENERATOR-01-V1.0.0`
- **Frozen Seed:** `2026101506`
- **Independent Verifier Script:** `scripts/audit_w06_scenario_generator_dryrun.py`
- **Adversarial QA Test Suite:** `tests/test_w06_scenario_generator_qa_01.py`
- **Machine-Readable QA Receipt:** `data/evaluation/w06/w06_scenario_generator_qa_01_receipt_v1.json`

---

## 1. Purpose & Independence Model

`W06-SCENARIO-GENERATOR-QA-01` conducts an **independent adversarial QA** of the closed deterministic W06 scenario generator (`apps/ai-service/app/evaluation/planner_scenario_generator.py`) prior to any final 100-scenario freeze.

### Why Self-Verification Alone Is Insufficient
When a generator engine validates its own output via internal helper functions (`verify_dry_run_bundle_invariants()`, `verify_combination_direct_support()`, `build_cross_balance_report()`), any bug in the generator's internal counting, set-union support logic, repeat-cap key construction, or cross-table aggregation could be shared between the generator and its internal verifier.

### Independent Recomputation Strategy
The QA verifier (`scripts/audit_w06_scenario_generator_dryrun.py`) enforces strict verification independence:
1. It treats the generator output (`DryRunGeneratorBundle` JSON obtained via CLI `--output-json` in a temporary directory or public entry point) as untrusted external data.
2. It **never** calls `verify_dry_run_bundle_invariants()`, `verify_combination_direct_support()`, `load_direct_catalog_interest_sets()`, or `build_cross_balance_report()` from the generator module, and **never** trusts `bundle["invariants_verified"]`, `slot["rule_a_passed"]`, `slot["rule_b_passed"]`, or `slot["support_class"]`.
3. It independently loads the four frozen scientific authorities (`w06_scenario_method_lock_v1.json`, `w06_scenario_support_matrix_v1.json`, `gomate_places_freeze_v2.json`, and `poi_to_canonical_vector` from `apps/ai-service/recommendation/reca/contract.py`) and independently recomputes every marginal, cross-allocation, Rule A/B support metric, repeat-cap counter, canonical signature, date window, budget formula, rejection log invariant, and cross-balance table.

---

## 2. Independent Audit Findings

### 2.1 Baseline External Dry-Run Audit (`PASS`)
- Executed via the public dry-run CLI (`scripts/generate_w06_scenarios_dryrun.py`) using a temporary directory that is automatically deleted after reading.
- Verified both CLI stdout summary and full canonical JSON bundle (`SHA256 = 3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`).
- All 100 slots carry `run_mode = "DRY_RUN"`, `fixture_label = "SYNTHETIC_GENERATOR_QA"`, `allow_revisit_place_ids = false`, `currency = "VND"`, and `is_final_100_scenarios = false`.
- Independently verified exact marginals and cross-matrices:
  - `destination`: `{"ha-noi": 34, "da-nang": 33, "ha-long": 33}`
  - `days`: `{"2": 33, "3": 34, "4": 33}` and exact `destination × days` matrix (`11/12/11`, `11/11/11`, `11/11/11`)
  - `interest_count`: `{"1": 33, "2": 34, "3": 33}` and exact `destination × interest_count` matrix (`11/12/11`, `11/11/11`, `11/11/11`)
  - `budget`: `{"B1": 27, "B2": 27, "B3": 26, "null": 20}` with exact `daily_nominal * days` VND formula
  - `travel_style`: `{"BACKPACKER": 25, "BUDGET": 25, "COMFORT": 25, "LUXURY": 25}`
  - `weekend_exposure`: `{"weekend_exposed": 50, "non_weekend_exposed": 50}` across contiguous trips inside `2026-11-02..2026-12-13`

### 2.2 Independent Rule A / Rule B Audit (`PASS`)
- Independently rebuilt `destination -> canonical_interest -> set(place_id)` directly from `data/curated/gomate_places_freeze_v2.json` (`is_rec_a_core_v2 == true`) using `poi_to_canonical_vector`.
- Recomputed Rule A ($\forall i \in C,\; n_i \ge \text{days}$) and Rule B (direct `place_id` set union $|\bigcup_{i \in C} P_i| \ge 2 \times \text{days}$ and $\sum_{i \in C} n_i \ge 2 \times \text{days}$) across all 100 slots:
  - `rule_a_failures = 0`
  - `rule_b_failures = 0`
  - `excluded_combinations_used = 0`
  - Independently recomputed `support_class` (`CLEAR = 81`, `STRESS = 19`) matches both slot metadata and `w06_scenario_support_matrix_v1.json`.

### 2.3 Independent Repeat-Cap Audit (`PASS`)
- Independently counted `(destination_slug, tuple(sorted(interests)))` pooled across all `days`, `budget`, `weekend_exposure`, and `travel_style` values:
  - `ha-noi`: max observed `k1 = 3 <= 3`, `k2 = 1 <= 1`, `k3 = 1 <= 1`
  - `da-nang`: max observed `k1 = 2 <= 2`, `k2 = 1 <= 1`, `k3 = 1 <= 1`
  - `ha-long`: max observed `k1 = 2 <= 2`, `k2 = 1 <= 1`, `k3 = 1 <= 1`
  - `repeat_cap_violations = 0`

### 2.4 Independent Canonical Duplicate Signature Audit (`PASS`)
- Independently constructed `(destination_slug, days, sorted(interests), budget_tier_or_null, weekend_exposure, travel_style)` for all 100 slots (ignoring `scenario_id`, `notes`, `candidate_index`, and dates):
  - `unique_canonical_signatures = 100`
  - `duplicate_canonical_signatures = 0`

### 2.5 Priority-Order & Phase-C Failure Preservation Audit (`PASS`)
- Verified `executable_priority_trace` equals the exact 10-step frozen sequence (`DESTINATION_ALLOCATION` .. `CROSS_DIMENSION_IMBALANCE`).
- Verified via public Phase A / Phase B structures (`PhaseBLockedSlot`) that all 100 slots have Priorities 1..6 locked (`phase_b_locked_slots_sha256 = 2ef58c4a2c74f8355330c0e6c7005cc5828d939da219ba56b776378a68fec4ae`) with no `interests` attribute prior to Phase C, and that forced Phase C failures raise `ScenarioGenerationInfeasibleError` (`STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT`) while preserving the exact Phase B Priority 1..6 slot assignments and hash.

### 2.6 Fresh-Process Determinism QA (`PASS`)
- Executed the public dry-run CLI in four separate fresh Python subprocesses with seed `2026101506`:
  - `normal`: `3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`
  - `PYTHONHASHSEED=0`: `3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`
  - `PYTHONHASHSEED=1`: `3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`
  - `PYTHONHASHSEED=42`: `3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`
- **Bounded Reproducibility Claim:** Under the audited repository revision, frozen scientific inputs, recorded dependency environment, and seed `2026101506`, repeated fresh-process executions across `PYTHONHASHSEED` settings produced identical canonical output and SHA256. This does not claim universal bit-for-bit reproducibility across arbitrary environments.

### 2.7 Output Verifier Mutation Testing (`20/20 PASS`)
- Tested `QA-MUT-01` through `QA-MUT-20` on single-property mutated deep copies of the valid dry-run bundle; the independent verifier rejected all 20 mutations with `IndependentDryRunAuditError`.

### 2.8 Scientific Authority Mutation Testing (`7/7 PASS`)
- Tested `QA-AUTH-01` through `QA-AUTH-07` using temporary copies/overrides (Method Lock byte mutation, Support Matrix byte mutation, frozen Catalog byte mutation, REC-A contract byte mutation, wrong generator seed, frozen priority order mutation, repeat-cap methodology mutation); the generator failed closed with `ScenarioGenerationInfeasibleError` on all 7 cases.

### 2.9 Rejection Log, Artifact Safety & Cross-Balance Audits (`PASS`)
- **Rejection Log Audit:** `rejection_log_count = 776` (`CATALOG_SUPPORT_BELOW_THRESHOLD = 393`, `INTEREST_COMBINATION_REPEAT_CAP = 360`, `TOTAL_INTEREST_CAPACITY_INSUFFICIENT = 23`), all codes in frozen vocabulary, zero forbidden model/planner output keys, and all `replacement_candidate_index` pointers valid.
- **Artifact Safety Audit:** CLI refuses to write to `data/evaluation/w06/`, `data/curated/`, or any filename containing `final_100`, `p11`, or `prereg`.
- **Cross-Balance Independent Audit:** All 11 cross-tabulation tables and `max_min_cross_cell_imbalance` independently recomputed from raw slots match `CrossBalanceReport` identically.

---

## 3. Non-Interference & Scientific Boundaries

- `generator_modified = false` (`623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1`)
- `method_lock_modified = false` (`5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9`)
- `support_matrix_modified = false` (`68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4`)
- `catalog_modified = false` (`f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`)
- `reca_contract_modified = false` (`1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c`)
- `measurement_contract_modified = false` (`0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298`)
- `final_scenarios_generated = false`
- `p11_created = false`
- `preregistration_created = false`
- `gemini_called = false`, `openai_called = false`, `claude_called = false`, `grok_called = false`
- `scientific_results_generated = false`
