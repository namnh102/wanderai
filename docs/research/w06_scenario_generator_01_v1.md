# W06-SCENARIO-GENERATOR-01: Deterministic W06 Scenario Generator Engine

- **Task ID:** `W06-SCENARIO-GENERATOR-01`
- **Version:** `1.0.0`
- **Generator Version:** `W06-SCENARIO-GENERATOR-01-V1.0.0`
- **Base `develop` SHA:** `fab7f63bb70a12ae332af82ae0f0261c35207ae0`
- **Frozen Seed:** `2026101506`
- **Generator Engine Module:** `apps/ai-service/app/evaluation/planner_scenario_generator.py`
- **Dry-Run CLI Wrapper:** `scripts/generate_w06_scenarios_dryrun.py`
- **Machine-Readable Receipt:** `data/evaluation/w06/w06_scenario_generator_01_receipt_v1.json`

---

## 1. What the Generator Implements & Why Deterministic Generation Is Required

`W06-SCENARIO-GENERATOR-01` implements the **deterministic W06 scenario generator engine** and **exact invariant verification machinery** governed by `W06-SCENARIO-METHOD-LOCK-01` (`v1.0.0`) and `W06-SCENARIO-SUPPORT-MATRIX-V1` (`v1.0.0`).

Deterministic scenario generation is required so that:
1. Every benchmark scenario input is constructed strictly from pre-committed catalog support evidence and frozen marginal targets without human cherry-picking, seed shopping, or inspection of model outputs.
2. Under the audited repository revision, frozen scientific inputs, recorded dependency environment, and seed `2026101506`, repeated executions produced identical canonical output and SHA256 (`3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`). This does not claim universal bit-for-bit reproducibility across arbitrary environments.
3. Every rejected candidate in the generator stream is deterministically logged with an auditable reason code from the frozen vocabulary and linked to its replacement candidate index.

---

## 2. Authoritative Source Artifacts & Runtime Hash Pinning

At runtime, the generator verifies and fails closed unless all frozen scientific authorities match the Method Lock (`method_lock["interest_mapping"]` and expected LF-normalized SHA256 digests):

| Artifact | Path | LF-Normalized SHA256 |
|---|---|---|
| **Scenario Method Lock** | `data/evaluation/w06/w06_scenario_method_lock_v1.json` | `5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9` |
| **Scenario Support Matrix** | `data/evaluation/w06/w06_scenario_support_matrix_v1.json` | `68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4` |
| **REC-A Interest Contract** | `apps/ai-service/recommendation/reca/contract.py` | `1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c` |
| **Benchmark Schema** | `apps/ai-service/app/schemas/planner_benchmark.py` | `3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712` |
| **Frozen Catalog V2** | `data/curated/gomate_places_freeze_v2.json` | `f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444` |

---

## 3. Seed Policy & Cryptographic Determinism

- **Single Frozen Seed:** `DEFAULT_SCENARIO_GENERATION_SEED = 2026101506` (`allowed_seed_count = 1`, `seed_shopping_allowed = false`).
- **Zero Global Random State / Zero Python `hash()` Dependency:** All tie-breaking uses `deterministic_tiebreak_digest(seed, canonical_key)`, which computes `SHA256("seed=<seed>|key=<canonical_key>")` over UTF-8 bytes.
- All dictionary and set iterations are explicitly sorted before indexing or serialization.

---

## 4. Executable Allocation Priority Order & Candidate Stream

The generator executes the frozen 10-level priority hierarchy from `W06-SCENARIO-METHOD-LOCK-01` in four strict sequential phases (`EXECUTABLE_PRIORITY_TRACE`):

### PHASE A (Priorities 1..3)
1. **`DESTINATION_ALLOCATION` (Priority 1 — exact destination allocation):** `ha-noi = 34`, `da-nang = 33`, `ha-long = 33` (total `100`).
2. **`DAYS_ALLOCATION` (Priority 2 — exact days marginal & destination $\times$ days cross-allocation):**
   - `ha-noi`: `2d = 11, 3d = 12, 4d = 11`
   - `da-nang`: `2d = 11, 3d = 11, 4d = 11`
   - `ha-long`: `2d = 11, 3d = 11, 4d = 11`
   - Global: `2d = 33, 3d = 34, 4d = 33`.
3. **`INTEREST_COUNT_ALLOCATION` (Priority 3 — exact interest-count marginal & destination $\times$ interest_count cross-allocation):**
   - `ha-noi`: `k1 = 11, k2 = 12, k3 = 11`
   - `da-nang`: `k1 = 11, k2 = 11, k3 = 11`
   - `ha-long`: `k1 = 11, k2 = 11, k3 = 11`
   - Global: `k1 = 33, k2 = 34, k3 = 33`.
   - Using a rotated 3D `(destination, days, interest_count)` cell grid (`4` or `3` per cell), the global `days × interest_count` table is `11` in 8 cells and `12` in `(3, 2)`, achieving the theoretical minimum cross-cell imbalance (`max - min = 1`).

### PHASE B (Priorities 4..6 — Locked Before Interest Selection)
4. **`BUDGET_ALLOCATION` (Priority 4 — exact budget applicability/tier marginal):** `B1 = 27`, `B2 = 27`, `B3 = 26`, `null = 20` (`80` budget-applicable, `20` null) assigned across all 100 slots.
5. **`TRAVEL_STYLE_ALLOCATION` (Priority 5 — exact travel-style marginal):** `BACKPACKER = 25`, `BUDGET = 25`, `COMFORT = 25`, `LUXURY = 25` (`DESCRIPTIVE_INPUT_VARIATION_ONLY`) assigned across all 100 slots.
6. **`WEEKEND_EXPOSURE_ALLOCATION` (Priority 6 — exact weekend-exposure marginal & contiguous dates):** `weekend_exposed = 50`, `non_weekend_exposed = 50` within `2026-11-02..2026-12-13` assigned across all 100 slots, freezing immutable `PhaseBLockedSlot` records (`phase_b_locked_slots_sha256 = 2ef58c4a2c74f8355330c0e6c7005cc5828d939da219ba56b776378a68fec4ae`).

### PHASE C (Priorities 7..9 — Executed Under Locked Priorities 1..6)
7. **`SCENARIO_ELIGIBILITY` (Priority 7 — Two-Stage Rule A & Rule B):**
   - **Rule A:** $\forall i \in C,\; n_i \ge \text{days}$. Failure logs `CATALOG_SUPPORT_BELOW_THRESHOLD`.
   - **Rule B:** Direct set union $|\bigcup_{i \in C} P_i| \ge 2 \times \text{days}$ AND $\sum_{i \in C} n_i \ge 2 \times \text{days}$. Failure logs `TOTAL_INTEREST_CAPACITY_INSUFFICIENT`.
   - `EXCLUDED` combinations are never permitted (`excluded_combinations_used = 0`).
8. **`DUPLICATE_REPEAT_CAP` (Priority 8 — Duplicate / Near-Duplicate & Repeat-Cap Rules):**
   - **Repeat Counting Key:** `(destination_slug, sorted(interests))` across all days, budgets, weekend exposures, and travel styles.
   - **Frozen Repeat Caps:** `ha-noi: {1: 3, 2: 1, 3: 1}`, `da-nang: {1: 2, 2: 1, 3: 1}`, `ha-long: {1: 2, 2: 1, 3: 1}`. Exceeding the cap logs `INTEREST_COMBINATION_REPEAT_CAP`.
   - **Canonical Scenario Signature:** `(destination_slug, days, sorted(interests), budget_tier_or_null, weekend_exposure, travel_style)`. Exact duplicates are forbidden (`duplicate_canonical_signatures = 0`); collisions against locked Phase B attributes log `NEAR_DUPLICATE_SIGNATURE`.
9. **`CLEAR_STRESS_COVERAGE` (Priority 9 — CLEAR / STRESS Coverage):**
   - Within each destination, the candidate selector alternates preferred support class (`CLEAR` / `STRESS`) in round-robin order among admissible combinations at the minimum usage count.
   - No fixed `STRESS` quota is imposed; in the dry-run assignment (`seed = 2026101506`), `CLEAR = 81` and `STRESS = 19` (`ha-noi: 26 CLEAR / 8 STRESS`, `da-nang: 33 CLEAR / 0 STRESS`, `ha-long: 22 CLEAR / 11 STRESS`).
   - If Phase C cannot satisfy any slot under its locked Priority 1..6 assignments, the generator fails closed with `STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT` and never alters Priorities 1..6.

### PHASE D (Priority 10)
10. **`CROSS_DIMENSION_IMBALANCE` (Priority 10 — Minimize & Report Remaining Cross-Dimension Imbalance):**
    - Computes and verifies the complete marginal and cross-dimension balance report (`CrossBalanceReport`).

---

## 5. Budget, Date, and Travel Style Semantics

- **Nominal Budget Formula:**
  - `B1`: `500000 * days` VND (`1000000`, `1500000`, `2000000`)
  - `B2`: `1000000 * days` VND (`2000000`, `3000000`, `4000000`)
  - `B3`: `2000000 * days` VND (`4000000`, `6000000`, `8000000`)
  - `null`: `budget = None`, `currency = "VND"`
  - These tiers are nominal benchmark ceilings only and do not represent real-world price ground truth.
- **Contiguous Date Window:**
  - Every scenario's `[start_date, end_date]` lies inside `2026-11-02..2026-12-13` with `end_date = start_date + (days - 1) days`.
  - `weekend_exposure == True` iff `[start_date, end_date]` includes at least one Saturday or Sunday.

---

## 6. Rejection Logging & Fail-Closed Behavior

Every rejected candidate in the generator stream is recorded as a `CandidateRejectionEntry` with:
- `candidate_index`
- `candidate_sha256`
- `reason_code` (strictly restricted to the 10 frozen codes in `ALLOWED_REJECTION_REASON_CODES`)
- `rule_version` (`"W06-SCENARIO-METHOD-LOCK-01-V1.0.0"`)
- `replacement_candidate_index`

If any runtime authority hash, marginal target, repeat cap, date window, or support constraint is infeasible or violated, the generator raises `ScenarioGenerationInfeasibleError` with `protocol_status = "STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT"`.

---

## 7. Dry-Run vs. Final-Freeze Distinction & Scientific Boundaries

- All dry-run outputs carry `run_mode = "DRY_RUN"`, `fixture_label = "SYNTHETIC_GENERATOR_QA"`, `scenario_id = "W06-DRYRUN-001".."W06-DRYRUN-100"`, and `is_final_100_scenarios = False`.
- The CLI wrapper (`scripts/generate_w06_scenarios_dryrun.py`) defaults to stdout and refuses to write to `data/evaluation/w06/`, `data/curated/`, or any filename containing `p11`, `final_100`, or `prereg`.
- **Boundary Confirmations:**
  - `real_scenarios_generated = false`
  - `final_scenarios_generated = false`
  - `p11_created = false`
  - `preregistration_created = false`
  - `gemini_called = false`
  - `scientific_results_generated = false`
  - `w5_modified = false`
  - `production_planner_modified = false`
  - `historical_measurement_contract_modified = false`
