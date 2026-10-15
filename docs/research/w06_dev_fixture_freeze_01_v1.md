# W06 DEV-Only Scenario Fixture Freeze (`W06-DEV-FIXTURE-FREEZE-01`)

- **Task ID:** `W06-DEV-FIXTURE-FREEZE-01`
- **Status:** `FROZEN_FOR_DEV_EXECUTION_ONLY`
- **Base `develop` SHA:** `2873b161b241573cf9d5db2df64b3e1594a1a595`
- **Governing Methodology Lock:** `W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01` (`data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json`)
- **DEV Fixture Generation Seed:** `2026101507` (`DEV_FIXTURE_GENERATION_SEED = 2026101507`)
- **Hash Basis:** `SHA256_CANONICAL_JSON_UTF8_LF_BYTES` (`json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"` encoded as UTF-8 LF bytes)

---

## 1. Role of `DEV-TUNE` vs `DEV-SELECT` & Why Final-100 Is Forbidden for Selection

The 80 DEV-only scenario fixtures (`DEV-TUNE = 20`, `DEV-SELECT = 60`) are strictly isolated development and model/configuration selection inputs:

1. **`DEV-TUNE` (`20` fixtures, IDs `W06-DEV-TUNE-001..020`, `fixture_label = "W06_DEV_TUNE"`):**
   - Used exclusively before `DEV-SELECT` for prompt tuning, structured-output wiring verification, and post-selection stochasticity probes on the 5 deterministically pre-designated fixtures.
2. **`DEV-SELECT` (`60` fixtures, IDs `W06-DEV-SELECT-001..060`, `fixture_label = "W06_DEV_SELECT"`):**
   - Used once for the single pre-locked `DEV-SELECT` comparison across candidate models (`1` execution per candidate per fixture, `0` retries, `0` repair) to select the single winning primary model/configuration.
3. **Why `final-100` (`W06-SCENARIO-001..100`) Is Forbidden for Model Selection:**
   - Using any final benchmark scenario to tune prompts, compare candidate models, or pick the winning configuration would contaminate the held-out final evaluation with selection bias and post-hoc cherry-picking. The `final-100` scenario bundle (`data/evaluation/w06/w06_scenarios_freeze_v1.json`) is strictly reserved for the single preregistered primary benchmark run after `DEV-SELECT` closes.

---

## 2. Frozen Seed & Deterministic Generation Policy

- **Frozen Seed:** `DEV_FIXTURE_GENERATION_SEED = 2026101507`
- **Rules:**
  - Single frozen seed only (`seed_shopping = false`).
  - Zero model/provider calls during fixture generation.
  - Zero dependence on Python's randomized `hash()`; all tie-breaking uses SHA256 digests (`deterministic_tiebreak_digest(seed, key)`) and explicitly sorted sequences.
  - Separate generator module (`apps/ai-service/app/evaluation/planner_dev_fixture_generator.py`); the authoritative final scenario generator (`apps/ai-service/app/evaluation/planner_scenario_generator.py`) is untouched.

---

## 3. Exact Marginal Balances

### 3.1 `DEV-TUNE` (`20` Fixtures)

| Dimension | Locked Exact Marginal Counts |
| :--- | :--- |
| **Destination** | `ha-noi = 7`, `da-nang = 7`, `ha-long = 6` |
| **Days** | `2 = 7`, `3 = 7`, `4 = 6` |
| **Interest Count** | `1 = 7`, `2 = 7`, `3 = 6` |
| **Budget Tier** | `B1 = 5`, `B2 = 5`, `B3 = 5`, `null = 5` |
| **Travel Style** | `BACKPACKER = 5`, `BUDGET = 5`, `COMFORT = 5`, `LUXURY = 5` |
| **Weekend Exposure** | `weekend_exposed = 10`, `non_weekend_exposed = 10` |

### 3.2 `DEV-SELECT` (`60` Fixtures)

| Dimension | Locked Exact Marginal Counts |
| :--- | :--- |
| **Destination** | `ha-noi = 20`, `da-nang = 20`, `ha-long = 20` |
| **Days** | `2 = 20`, `3 = 20`, `4 = 20` |
| **Interest Count** | `1 = 20`, `2 = 20`, `3 = 20` |
| **Budget Tier** | `B1 = 15`, `B2 = 15`, `B3 = 15`, `null = 15` |
| **Travel Style** | `BACKPACKER = 15`, `BUDGET = 15`, `COMFORT = 15`, `LUXURY = 15` |
| **Weekend Exposure** | `weekend_exposed = 30`, `non_weekend_exposed = 30` |

---

## 4. Overlap Definitions, Constraints & Leakage-Safe Auditing

### 4.1 Exact Signature & Exact-Overlap Rule
- **Exact Signature:**
  `(destination_slug, days, sorted(interests), budget_tier_or_null, weekend_exposure, travel_style)`
- **Requirements (All Verified = `0` Violations):**
  - Exact overlap between all 80 DEV fixtures and `final-100`: **`0`**
  - Duplicate exact signatures within `DEV-TUNE`: **`0`**
  - Duplicate exact signatures within `DEV-SELECT`: **`0`**
  - Duplicate exact signatures across `DEV-TUNE` and `DEV-SELECT`: **`0`**
  - All 80 DEV exact signatures are strictly unique (`all_dev_unique_exact_signatures = true`).

### 4.2 Near-Overlap Definition & Partition Rules
- **Near-Overlap Definition:**
  `same destination_slug AND same sorted(interests) AND same budget_tier_or_null AND abs(days_dev - days_final) <= 1`
- **`DEV-TUNE` Rule (Strict Zero Near-Overlap):**
  - `DEV-TUNE` is generated first because it enforces `dev_tune_near_overlap_with_final == 0`.
  - Actual `DEV-TUNE` near-overlap count with `final-100`: **`0`**.
- **`DEV-SELECT` Rule (Counted & Disclosed):**
  - `DEV-SELECT` is generated after `DEV-TUNE` from the remaining deterministic candidate space with zero exact overlap against both `final-100` and `DEV-TUNE`.
  - Near-overlap with `final-100` is permitted for `DEV-SELECT` and must be reported:
    - `dev_select_near_overlap_with_final = 10`
    - `dev_select_near_overlap_rate = 0.166667` (`10 / 60`)

### 4.3 Leakage-Safe Overlap Auditing
- Automated overlap verification loads `data/evaluation/w06/w06_scenarios_freeze_v1.json` and `data/evaluation/w06/w06_p11_assignment_manifest_v1.json` in memory only to compute set membership against exact signatures and near-overlap keys.
- Neither the generator, the receipts (`w06_dev_final_overlap_receipt_v1.json`, `w06_dev_fixture_freeze_01_receipt_v1.json`), nor `scripts/verify_w06_dev_fixture_freeze.py` ever print `final-100` scenario IDs, interests, dates, budgets, or scenario JSON to operator logs (`final_semantics_printed_to_operator_logs = false`).

---

## 5. Interest-Combination Diversity & Fail-Closed Behavior

### 5.1 Deterministic Diversity Tie-Break
- Without introducing any artificial repeat cap beyond frozen authorities, candidate selection prefers the admissible combination with the lowest current reuse count of `(destination_slug, sorted(interests))`, followed by alternating `CLEAR`/`STRESS` coverage preference and SHA256 tie-break (`seed = 2026101507`).
- **Observed Diversity Across All 80 DEV Fixtures:**
  - Distinct `(destination_slug, sorted(interests))` pairs used: **`70`** (out of 80 fixtures)
  - `max_interest_combination_reuse`: **`2`**
  - `mean_interest_combination_reuse`: **`1.142857`**
  - Support class distribution: `CLEAR = 58`, `STRESS = 22`, `EXCLUDED = 0` (`DEV-TUNE`: `CLEAR = 15, STRESS = 5`; `DEV-SELECT`: `CLEAR = 43, STRESS = 17`).

### 5.2 Fail-Closed Protocol
- If 20 `DEV-TUNE` fixtures with zero near-overlap cannot be produced, the generator fails closed immediately with `DevFixtureFreezeInfeasibleError` and status `DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE`.
- If any exact `DEV-SELECT` marginal balance or authority hash invariant cannot be satisfied, the generator fails closed with status `STOP_REQUIRE_FORMAL_METHOD_AMENDMENT`.

---

## 6. Frozen Artifacts & SHA256 Digests

| Artifact | Path | Canonical UTF-8 LF SHA256 |
| :--- | :--- | :--- |
| **DEV Fixture Bundle** | `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json` | `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050` |
| **DEV Fixture Manifest** | `data/evaluation/w06/w06_dev_fixture_manifest_v1.json` | `15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98` |
| **DEV/Final Overlap Receipt** | `data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json` | `285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa` |
| **DEV Freeze Receipt** | `data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json` | `437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026` |

---

## 7. Scientific Boundaries

- `provider_calls = 0` (`Gemini = false`, `OpenAI = false`, `Claude = false`, `Grok = false`)
- `winning_model_selected = false`
- `dev_model_outputs_generated = false`
- `preregistration_created = false`
- `final_benchmark_executed = false`
