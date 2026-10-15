# W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01: Model & Architecture Selection Method Lock (`v1.0.0`)

## 1. Purpose, Preconditions & Provenance
This document records the frozen `W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01` (`data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json`, `v1.0.0`, status `FROZEN_BEFORE_DEV_MODEL_EXECUTION`) governing DEV fixture generation, technical capability preflight, shared prompt tuning on `DEV-TUNE`, candidate model/config comparison on `DEV-SELECT`, post-selection stochasticity diagnostics, and final single-configuration freezing prior to W06 preregistration and final benchmark execution.

### Preconditions
- **Base `develop` SHA:** `6043402ab102a6bc116aabc0319932208184e102`
- **`W06-SCENARIO-FREEZE-01`:** `CLOSED`
- **Frozen 100-Scenario Bundle (`data/evaluation/w06/w06_scenarios_freeze_v1.json`):** `c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1`
- **Frozen `P11` Assignment Manifest (`data/evaluation/w06/w06_p11_assignment_manifest_v1.json`):** `0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62`
- **Grok Council Phase 2:** `COMPLETE`
- **ChatGPT Methodology Decision:** `FINAL_FOR_DEV_SELECTION`

### Source & Decision Provenance
This methodology derives from:
1. W06 Research Scout Phase 1
2. W06 Architecture Auditor Phase 1
3. W06 Scientific Red Team Phase 1
4. W06 Grok Council Phase 2 cross-critique
5. Final ChatGPT methodology decision

**Methodology Ownership:** ChatGPT is the sole methodology owner (`methodology_owner = "ChatGPT"`, `grok_made_final_decision = false`).

---

## 2. Primary Architecture Lock
- **`architecture_id`:** `LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1`
- **`architecture_class`:** `DIRECT_ONE_CALL_PLUS_READ_ONLY_DETERMINISTIC_VALIDATION`
- **Preferred Thesis Label:** `LLM-based itinerary planner with deterministic grounding and validation`
- **Terminology Boundary:** Do NOT describe the primary system as autonomous or multi-agent (`autonomous_or_multi_agent_claim_allowed = false`).
- **Execution Invariants:**
  - `llm_calls_per_execution = 1`
  - `model_initiated_tool_calls = 0`
  - `validator_feedback_to_model = false`
  - `llm_repair_calls = 0`
  - `deterministic_semantic_repair_enabled = false`
  - `automatic_retry_count = 0`
  - `fallback_model_allowed = false`
  - `deterministic_catalog_before_model = true`
  - `offline_evaluator_is_scientific_score_authority = true`

---

## 3. Structured Output & Primary JSON Normalization Policies

### Structured Output Policy
- `native_structured_output_required_for_dev_select = true`
- Every candidate entering `DEV-SELECT` must demonstrate technical compatibility with the semantic `BenchmarkPlanResponse` schema during technical capability preflight.
- Do NOT encode the frozen catalog's `place_id` values as a provider-side enum (`encode_catalog_place_ids_as_provider_side_enum = false`).
- Provider decoding is evaluated as part of the evaluated `SYSTEM` (`provider_decoding_is_part_of_evaluated_system = true`), while offline Pydantic validation remains identical across all providers (`offline_pydantic_validation_identical_across_providers = true`).
- Structured-output mode is determined strictly by technical capability preflight, NOT by `DEV` performance. A candidate that cannot support the required semantic schema does not enter `DEV-SELECT`.

### Primary JSON Normalization Policy
- `raw_provider_artifact_preserved = true`
- `primary_substring_json_extraction = false`
- `primary_trailing_comma_repair = false`
- `primary_code_fence_removal = false`
- `primary_llm_json_repair = false`
- `primary_json_repair_enabled = false`
- No transformation that rescues malformed JSON may affect primary run status or primary scientific metrics (`malformed_json_rescue_affects_primary_metrics = false`).
- The legacy `clean_benchmark_json_response` helper may be retained strictly for `DIAGNOSTIC_ONLY_RECOVERY_REPORTING` to compute `LEGACY_RECOVERABLE_PARSE_RATE`, and must never replace the primary artifact.

---

## 4. Sampling, Retry/Failure & Harness Error Policies

### Sampling Policy
- **Temperature:** If supported by the provider, `temperature = 0`; otherwise `temperature = "UNSUPPORTED"` and provider-required fixed behavior must be documented.
- **Seed:** If supported by the provider, `seed = 2026101508`; otherwise `seed = "UNSUPPORTED"`.
- Temperature and seed MUST NOT be selected based on `DEV` performance (`temperature_grid_search_allowed = false`, `seed_shopping_allowed = false`).
- Do not claim bitwise determinism across provider calls (`bitwise_determinism_claimed = false`).
- Thinking/reasoning level must be fixed during technical preflight, documented, and NOT tuned using `DEV-SELECT` scores.

### Retry & Failure Policy
- `sdk_automatic_retry = 0`
- `transport_retry = 0`
- Zero scenario retries after `HTTP_429`, `HTTP_5XX`, `TIMEOUT`, `PARTIAL_TIMEOUT`, `MALFORMED_MODEL_OUTPUT`, `SCHEMA_NONCOMPLIANCE`, `REFUSAL`, or `CONSTRAINT_FAILURE`. All such final outcomes remain in the assigned denominator.
- No fallback model or provider (`fallback_model_or_provider_allowed = false`).
- Any `MODEL_ID` / resolved-version integrity mismatch is a configuration integrity failure and must stop the batch before scientific reporting.
- Later harness validation must prove that a simulated transport/server failure produces exactly one provider request.

### Harness Error Policy
- `single_scenario_harness_rerun_allowed = false`
- On an objectively demonstrated `HARNESS_ERROR` during final execution:
  1. Stop the entire batch
  2. Preserve all old artifacts
  3. Do not silently continue
  4. Require formal amendment
  5. Re-freeze changed config/code
  6. Amend preregistration
  7. If a rerun is scientifically allowed, rerun the complete 100 scenarios as a new `run_id`
- `HARNESS_ERROR` determination must depend only on infrastructure/code evidence and logs, never on observed performance.
- If scientific metrics of the defective batch were already inspected before defect declaration, the original primary batch is considered compromised, and any later run must be disclosed as amended/secondary unless ChatGPT approves a formal scientific amendment.

---

## 5. DEV Model Candidates (`max_dev_select_candidates = 3`)

| Candidate ID | Provider | Model Identifier | Status |
|---|---|---|---|
| `C1` | `Google` | `gemini-3.8-flash` | `CANDIDATE_NOT_SELECTED_FINAL_MODEL` |
| `C2` | `OpenAI` | `gpt-6.1-sol` | `CANDIDATE_NOT_SELECTED_FINAL_MODEL` |
| `C3` | `Anthropic` | `claude-sonnet-5-5` | `CANDIDATE_NOT_SELECTED_FINAL_MODEL` |

- Exact provider documentation URL, access date, endpoint semantics, resolved/runtime model version/fingerprint (if exposed), and structured output capability must be reverified during technical preflight.
- No automatic substitution with another model or alias (`automatic_substitution_or_alias_allowed = false`).
- If a candidate fails technical preflight, record `FAILED_PREFLIGHT` and do NOT replace it after seeing `DEV` results.
- Do NOT add Gemini Flash-Lite or open-weight candidates later without a formal methodology amendment BEFORE `DEV-SELECT`.

---

## 6. DEV Fixture Methodology & Overlap Policy

### DEV Fixture Split & Balance (`dev_fixture_seed = 2026101507`)
- `seed_shopping = false`
- `total_dev_fixtures = 80` (`dev_tune_count = 20`, `dev_select_count = 60`)
- Final 100 scenarios remain strictly forbidden for model selection; DEV fixture IDs and paths must be clearly distinct from final W06 IDs.
- **`DEV-SELECT` (`N = 60`) Target Balance:**
  - `destination`: `ha-noi = 20`, `da-nang = 20`, `ha-long = 20`
  - `days`: `2 = 20`, `3 = 20`, `4 = 20`
  - `interest_count`: `1 = 20`, `2 = 20`, `3 = 20`
  - `budget`: `B1 = 15`, `B2 = 15`, `B3 = 15`, `null = 15`
  - `travel_style`: `BACKPACKER = 15`, `BUDGET = 15`, `COMFORT = 15`, `LUXURY = 15`
  - `weekend`: `true = 30`, `false = 30`
- **`DEV-TUNE` (`N = 20`):** Approximately balanced deterministically, with exact marginals recorded before model execution.

### Final / DEV Overlap Policy
- **Exact Signature:** `(destination_slug, days, sorted(interests), budget_tier_or_null, weekend_exposure, travel_style)`
  - Across all 80 DEV fixtures, exact signature overlap with the final 100 scenarios must equal `0`.
- **Near Overlap Definition:**
  $$\text{destination\_slug}_{\text{dev}} = \text{destination\_slug}_{\text{final}} \ \land \ \text{sorted(interests)}_{\text{dev}} = \text{sorted(interests)}_{\text{final}} \ \land \ \text{budget\_tier\_or\_null}_{\text{dev}} = \text{budget\_tier\_or\_null}_{\text{final}} \ \land \ |\text{days}_{\text{dev}} - \text{days}_{\text{final}}| \le 1$$
  - `DEV-TUNE` near overlap with final 100 = `0` (if 20 `DEV-TUNE` fixtures satisfying zero near overlap cannot be constructed deterministically, **STOP** — do not relax silently).
  - `DEV-SELECT` exact overlap with final 100 = `0`; near overlap may exist and its count must be reported.
- **Blinded Automated Overlap Checker:** May load both DEV and final data, but must output only `counts`, `hashes`, `PASS_FAIL`, and `aggregate_diagnostics` without printing final scenario semantic content into normal logs or operator reports.

---

## 7. Shared Prompt Tuning Protocol on `DEV-TUNE`
- **Maximum Shared Semantic Prompt Versions:** `max_shared_semantic_prompt_versions_on_dev_tune = 2`.
- **Deterministic Prompt IDs:** `P1` and `P2` (or only `P1` if a second prompt is never created).
- **Single-Prompt Rule:** If only `P1` exists, lock `P1` without a performance comparison (`LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON`).
- **Adapter Boundary:** No provider-specific semantic prompts (`provider_specific_semantic_prompts_allowed = false`); technical API/schema adapters are not separate semantic prompts (`API_SYNTAX`, `STRUCTURED_OUTPUT_WIRING`).
- **Two-Prompt Comparison Protocol (`P1` vs. `P2`):**
  - Evaluate on the exact same `20` `DEV-TUNE` fixtures across every candidate that **PASSED** technical preflight.
  - For each `(prompt_version, candidate, dev_tune_fixture)` cell: `1` execution, `0` automatic retry, `0` repair, `0` best-of-$N$.
  - Maximum prompt-tune executions: $2 \times 20 \times \text{number\_of\_preflight\_passed\_candidates} \le 120$.
  - Compute pooled equal-weight rates across all `candidate × DEV-TUNE fixture` cells.
  - Compare `P1` and `P2` using the **same best-relative 10pp survivor algorithm** across:
    1. `VALID_RUN_AND_SCHEMA_RATE`
    2. `EXACT_GROUNDING_PASS_RATE`
    3. `FINAL_CORE_PASS_RATE`
  - Do NOT use cost or latency to select the semantic prompt (`use_cost_or_latency_for_prompt_selection_allowed = false`).
  - If `P1` and `P2` remain tied through all three criteria, deterministically select `P1` (`tie_after_criterion_3_winner = "P1"`).
  - Do NOT create `P3` after viewing results (`create_p3_after_viewing_results_allowed = false`).
- **Prompt Lock Before `DEV-SELECT`:** Record `selected_prompt_version_id`, `selected_prompt_hash`, `all_attempted_prompt_version_ids`, and `all_attempted_prompt_hashes` before `DEV-SELECT` begins. No semantic prompt edit is allowed after `DEV-SELECT` begins.

---

## 8. `DEV-SELECT` Execution & Deterministic Set-Based Survivor Selection Rule

### `DEV-SELECT` Execution Policy
- For every candidate config and every `DEV-SELECT` fixture: `executions = 1`, `automatic_retry = 0`, `repair = 0`.
- Maximum model executions in one `DEV-SELECT`: $3 \times 60 = 180$.
- Best-of-$N$ selection is forbidden (`best_of_n_selection_allowed = false`).

### Step 1: Set-Based Best-Relative Survivor Algorithm (Criteria 1–3)
- Initialize `current_survivors` = all candidates that **PASSED** technical preflight and entered `DEV-SELECT`.
- Iterate through the three scientific rate criteria in exact order:
  1. `VALID_RUN_AND_SCHEMA_RATE`
  2. `EXACT_GROUNDING_PASS_RATE`
  3. `FINAL_CORE_PASS_RATE`
- At each criterion:
  $$\text{best\_score} = \max_{c \in \text{current\_survivors}} \text{score}[c]$$
  $$\text{next\_survivors} = \{ c \in \text{current\_survivors} \mid \text{best\_score} - \text{score}[c] \le 0.10 \}$$
  where `0.10` equals exactly `10` percentage points. Replace `current_survivors` with `next_survivors`.
- Tie comparison is **ALWAYS** relative to `best_score` among `current_survivors` (`pairwise_chaining_allowed = false`).
- If `len(current_survivors) == 1` after any criterion, select that survivor immediately.
- **Non-Transitive Reference Example:** If `C1 = 0.90`, `C2 = 0.82`, `C3 = 0.74`, then `best_score = 0.90`, `next_survivors = ["C1", "C2"]`, and `C3` is eliminated (`0.90 - 0.74 = 0.16 > 0.10`).

### Step 2: Cost & Latency Criteria (Criteria 4–5)
- **Criterion 4 (`MEDIAN_COST_PER_SCENARIO`):**
  - If >1 survivor remains after Criterion 3 and authoritative/comparable cost exists for **ALL** `current_survivors`, keep only candidate(s) with the minimum unrounded canonical median cost.
  - If cost is unavailable or non-comparable for **ANY** current survivor, **SKIP** cost for **ALL** current survivors and record `COST_CRITERION_SKIPPED_NOT_COMPARABLE` (do NOT penalize only the provider lacking comparable price metadata).
  - If `len(current_survivors) == 1`, select it immediately.
- **Criterion 5 (`MEDIAN_LATENCY`):**
  - If >1 survivor remains, keep candidate(s) with the minimum unrounded canonical median latency.
  - If `len(current_survivors) == 1`, select it immediately.

### Step 3: Deterministic Administrative Exact-Tie Order (`C1 > C2 > C3`)
- Subjective pinability tie-breaking is removed (`subjective_pinability_tie_break_allowed = false`, `human_judgment_after_dev_select_allowed = false`).
- If multiple candidates remain exactly tied after Criterion 5, select the first candidate according to the frozen administrative order:
  $$\texttt{FINAL\_EXACT\_TIE\_CANDIDATE\_ORDER} = [\texttt{C1}, \texttt{C2}, \texttt{C3}] \quad (\texttt{C1} > \texttt{C2} > \texttt{C3})$$
- This administrative tie-break does **NOT** constitute evidence that `C1` is scientifically superior; it exists solely to guarantee one deterministic final configuration (`final_primary_config_count = 1`).
- Stop permanently after the single `DEV-SELECT` comparison and report every candidate's results.

---

## 9. Bounded Post-`DEV-SELECT` Stochasticity Diagnostic Policy
- `stochasticity_diagnostic_may_affect_selection = false`
- `stochasticity_diagnostic_timing = "AFTER_DEV_SELECT_WINNER_SELECTED"`
- `stochasticity_diagnostic_dataset = "DEV_TUNE"`
- `stochasticity_diagnostic_fixture_count = 5` (the five lexicographically smallest frozen `DEV-TUNE` scenario IDs)
- `stochasticity_diagnostic_selected_config_only = true`
- `diagnostic_executions_per_fixture = 3`, `automatic_retry = 0`, `best_of_n = false`
- **Maximum diagnostic calls:** $5 \times 3 = 15$.
- These diagnostic outputs may estimate observed output variability and be reported as a limitation/diagnostic, but **MUST NOT** alter the selected model, prompt, or sampling configuration, and **MUST NOT** trigger another `DEV-SELECT`.

---

## 10. Opening-Hours Coverage Audit, Pre-Preregistration Freeze Fields & Boundaries
- Authorizes a later read-only audit over `data/curated/gomate_places_freeze_v2.json` computing `total_reca_core_pois`, `known_opening_hours_count`, `unknown_opening_hours_count`, `coverage_rate`, `per_destination_coverage`, `catalog_sha256`, and `parser_version` without inspecting final scenario model outputs or modifying frozen scenarios.
- Before preregistration, the final configuration freeze must pin all 37 required configuration, environment, prompt, schema, sampling, retry, artifact-hash, taxonomy, ordering, logging, and commit fields specified in `required_pre_preregistration_config_freeze_fields`.
- **Task Execution Boundaries:** `gemini_called = false`, `openai_called = false`, `claude_called = false`, `grok_called = false`, `dev_fixtures_generated = false`, `dev_model_outputs_generated = false`, `winning_model_selected = false`, `preregistration_created = false`, `final_benchmark_executed = false`.
