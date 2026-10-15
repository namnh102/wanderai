# W06-SCENARIO-FREEZE-01: Primary 100-Scenario Materialization and P11 Assignment Freeze (`v1.0.0`)

## 1. Purpose & Preconditions
This document records the deterministic materialization and immutable scientific freeze of the W06 primary 100-scenario assignment (`W06-SCENARIOS-FREEZE-01`) and the `P11` Frozen Assignment Manifest (`W06-P11-FROZEN-ASSIGNMENT-MANIFEST`).

- **Base `develop` SHA:** `b36dffa0f4a0e20ca4a970cf93b09650ad778c78`
- **Preconditions:**
  - `W06-SCENARIO-METHOD-LOCK-01` = `CLOSED`
  - `W06-INSTRUMENT-01D` = `CLOSED`
  - `W06-SCENARIO-GENERATOR-01` = `CLOSED` (`SCENARIO_GENERATOR_VERSION = "W06-SCENARIO-GENERATOR-01-V1.0.0"`)
  - `W06-SCENARIO-GENERATOR-QA-01` = `CLOSED`
- **Frozen Generator Seed:** `2026101506`
- **Audited Source Dry-Run Bundle SHA256:** `3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769`

---

## 2. Strict 1:1 Slot Mapping & Final ID Convention
The final frozen 100-scenario bundle is derived **1:1** in exact `slot_index` order (`1..100`) from the audited deterministic generator dry-run output without reshuffling, rerolling, re-optimizing, replacing candidates, rebalancing, or altering any scenario attribute:

$$\text{Dry-run slot } N \ (\texttt{W06-DRYRUN-NNN}) \longrightarrow \text{Final scenario } N \ (\texttt{W06-SCENARIO-NNN}), \quad N \in \{1, \dots, 100\}.$$

### Permitted Normalization Only
Every final scenario object is validated through `BenchmarkScenarioInput` (`apps/ai-service/app/schemas/planner_benchmark.py`) and contains **only** the 13 schema fields:
- `scenario_id`: `W06-DRYRUN-NNN` $\rightarrow$ `W06-SCENARIO-NNN`
- `fixture_label`: `"SYNTHETIC_GENERATOR_QA"` $\rightarrow$ `null` (`None`)
- `destination_slug`, `destination`, `days`, `start_date`, `end_date`, `budget`, `currency` (`"VND"`), `travel_style`, `interests`, `notes`, `allow_revisit_place_ids` (`false`): **preserved with 100% exact equality**.

### Separation of Input Schema vs. Audit Metadata
- `fixture_label` becomes `null` because `SYNTHETIC_GENERATOR_QA` is a QA-only safety guard label used during generator dry-run testing; final frozen benchmark scenarios represent real scientific inputs.
- Generator/evaluation audit fields (`candidate_index`, `budget_tier_or_null`, `weekend_exposure`, `interest_count`, `support_class`, `union_support`, `sum_support`, `rule_a_passed`, `rule_b_passed`, `canonical_signature`, `rejection_log`, `executable_priority_trace`) are **excluded** from `BenchmarkScenarioInput` so that no audit/difficulty metadata leaks into the planner input contract. Those audit fields are recorded in `P11` (`data/evaluation/w06/w06_p11_assignment_manifest_v1.json`) only.

---

## 3. Canonical Serialization & Cryptographic Hashes
All frozen JSON artifacts are serialized deterministically as UTF-8 LF bytes (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`):
```python
(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
```
No wall-clock timestamps are embedded inside `w06_scenarios_freeze_v1.json` or `w06_p11_assignment_manifest_v1.json`. Under the audited repository revision, frozen scientific inputs, recorded dependency/runtime environment, and seed 2026101506, the two recorded clean regeneration runs produced identical canonical bytes and SHA256 values. This does not claim universal bit-for-bit reproducibility across arbitrary platforms, runtimes, dependency sets, or environments.

| Artifact | Path | Canonical UTF-8 LF SHA256 |
|---|---|---|
| **Final 100-Scenario Bundle** | `data/evaluation/w06/w06_scenarios_freeze_v1.json` | `c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1` |
| **P11 Assignment Manifest** | `data/evaluation/w06/w06_p11_assignment_manifest_v1.json` | `0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62` |
| **Per-Scenario Hashes (`N=100`)** | Recorded per row in `P11` (`scenario_sha256`) | 100 distinct SHA256 hashes over individual `BenchmarkScenarioInput` JSON objects |

---

## 4. Meaning of P11 & Immutability Rule
`P11` (`data/evaluation/w06/w06_p11_assignment_manifest_v1.json`) freezes the complete 100-scenario assignment, slot order (`1..100`), per-scenario SHA256s, and stratification metadata **before** model/agent selection, **before** preregistration, and **before** any final benchmark execution:
- `P11` is **NOT** an assignment of scenarios to different models or providers. Every evaluated model/configuration in W06 is evaluated over the same frozen 100 scenarios.
- `created_before_model_selection = true`
- `created_before_preregistration = true`
- `created_before_final_execution = true`
- `model_output_used = false`
- **Immutability Rule:** Any future change to scenario semantic content, scenario order, per-scenario hash, or `P11` assignment requires an explicit scientific amendment and invalidates the existing freeze.
- **Historical Artifact Rule:** Pre-existing frozen authorities (including `w06_scenario_method_lock_v1.json`) remain byte-for-byte immutable; operational progression is recorded in `w06_scenario_freeze_01_receipt_v1.json`.

---

## 5. Independently Verified Frozen Marginals & Support Invariants
- **Destination:** `ha-noi = 34`, `da-nang = 33`, `ha-long = 33` (`100` total)
- **Days:** `2d = 33`, `3d = 34`, `4d = 33`
- **Destination $\times$ Days:** `ha-noi: 11/12/11`, `da-nang: 11/11/11`, `ha-long: 11/11/11`
- **Interest Count ($k$):** `k1 = 33`, `k2 = 34`, `k3 = 33`
- **Destination $\times$ Interest Count:** `ha-noi: 11/12/11`, `da-nang: 11/11/11`, `ha-long: 11/11/11`
- **Budget Tier:** `B1 = 27`, `B2 = 27`, `B3 = 26`, `null = 20` (`budget = daily_nominal_vnd * days`)
- **Travel Style:** `BACKPACKER = 25`, `BUDGET = 25`, `COMFORT = 25`, `LUXURY = 25`
- **Weekend Exposure:** `weekend_exposed = 50`, `non_weekend_exposed = 50` (date window `2026-11-02 .. 2026-12-13`, all spans contiguous)
- **Catalog Support & Eligibility:**
  - Rule A failures ($\text{support}(i) \ge d$): `0`
  - Rule B failures ($|\bigcup_{i \in C} P(i)| \ge 2d \land \sum_{i \in C} |P(i)| \ge 2d$): `0`
  - Support classes: `CLEAR = 81`, `STRESS = 19`, `EXCLUDED = 0`
  - Repeat-cap violations (`ha-noi: 3/1/1`, `da-nang: 2/1/1`, `ha-long: 2/1/1`): `0`
  - Duplicate canonical signatures: `0`

---

## 6. Scientific Boundaries & Historical Test Compatibility
- `method_lock_modified = false`
- `support_matrix_modified = false`
- `generator_modified = false`
- `qa_verifier_modified = false`
- `catalog_modified = false`
- `reca_contract_modified = false`
- `measurement_contract_modified = false`
- `historical_scientific_artifacts_modified = false`
- `methodology_modified = false`
- `independent_hash_verifier_uses_producer_hash_helpers = false`
- `reproducibility_claim_bounded = true`
- `historical_test_compatibility_update = true`
- `historical_test_compatibility_files`:
  - `apps/ai-service/tests/test_planner_scenario_generator.py`
  - `tests/test_w06_instrument_01d.py`
  - `tests/test_w06_scenario_method_lock.py`
  *(Earlier phase tests originally asserted that no `P11` file existed on disk prior to `W06-SCENARIO-FREEZE-01`. Once `W06-SCENARIO-FREEZE-01` legitimately created `data/evaluation/w06/w06_p11_assignment_manifest_v1.json`, those three tests were updated to allow only that exact canonical `P11` filename when `data/evaluation/w06/w06_scenario_freeze_01_receipt_v1.json` exists and parses with `task_id == "W06-SCENARIO-FREEZE-01"`, `final_scenario_count == 100`, and `p11_path == "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"`, while continuing to reject any other `p11` or `assignment_manifest` file.)*
- `model_selection_started = false`
- `gemini_called = false`, `openai_called = false`, `claude_called = false`, `grok_called = false`
- `preregistration_created = false`
- `benchmark_execution_started = false`
- `scientific_performance_results_generated = false`
