# W06 DEV Selection Scientific Harness V1 (`W06-DEV-SELECTION-HARNESS-01-OFFLINE`)

## 1. Purpose & Scope

This document defines the offline scientific execution and selection harness for W06 `DEV-TUNE` (prompt selection) and `DEV-SELECT` (model candidate selection), implemented in `apps/ai-service/app/evaluation/dev_selection_harness.py`.

- **Task ID:** `W06-DEV-SELECTION-HARNESS-01-OFFLINE`
- **Base `develop` SHA:** `50884c610cebf455255b9d05f737d9558cabf2e7`
- **Execution Mode:** 100% offline (`LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0`)
- **Next Gate:** `W06-DEV-SELECTION-HARNESS-QA-01`

---

## 2. Frozen DEV Dataset & Final-100 Firewall

### 2.1 Frozen DEV Bundle (`80` Fixtures)
The harness loads and verifies the frozen DEV bundle (`data/evaluation/w06/w06_dev_fixtures_freeze_v1.json`, `SHA256 = bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`) and manifest (`data/evaluation/w06/w06_dev_fixture_manifest_v1.json`, `SHA256 = 15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98`):

- **`DEV-TUNE` (`20` fixtures: `W06-DEV-TUNE-001` .. `W06-DEV-TUNE-020`):**
  - `destination`: `ha-noi = 7`, `da-nang = 7`, `ha-long = 6`
  - `days`: `2 = 7`, `3 = 7`, `4 = 6`
  - `interest_count`: `1 = 7`, `2 = 7`, `3 = 6`
  - `budget`: `B1 = 5`, `B2 = 5`, `B3 = 5`, `null = 5`
  - `travel_style`: `BACKPACKER = 5`, `BUDGET = 5`, `COMFORT = 5`, `LUXURY = 5`
  - `weekend`: `true = 10`, `false = 10`
- **`DEV-SELECT` (`60` fixtures: `W06-DEV-SELECT-001` .. `W06-DEV-SELECT-060`):**
  - `destination`: `ha-noi = 20`, `da-nang = 20`, `ha-long = 20`
  - `days`: `2 = 20`, `3 = 20`, `4 = 20`
  - `interest_count`: `1 = 20`, `2 = 20`, `3 = 20`
  - `budget`: `B1 = 15`, `B2 = 15`, `B3 = 15`, `null = 15`
  - `travel_style`: `BACKPACKER = 15`, `BUDGET = 15`, `COMFORT = 15`, `LUXURY = 15`
  - `weekend`: `true = 30`, `false = 30`

### 2.2 Final-100 Firewall
The harness enforces fail-closed path and scenario-ID guards (`assert_not_final100_path`, `assert_not_final100_scenario_id`, `assert_not_final100_scenario`) that raise `Final100FirewallViolationError` if any code attempts to load, parse, inspect, build context for, or evaluate `data/evaluation/w06/w06_scenarios_freeze_v1.json`, `data/evaluation/w06/w06_p11_assignment_manifest_v1.json`, or any non-DEV scenario (`W06-S*`).

---

## 3. Candidate Registry & Model Configuration

All three candidates verified in `W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION` (`PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2`) are registered in fixed order `["C1", "C2", "C3"]`:

| Candidate | Provider | Model ID | Reasoning / Thinking | Seed | Omitted Sampling Params | Schema V2 SHA256 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `C1` | Google | `gemini-3.8-flash` | `thinking_level="medium"` | `2026101508` | `temperature, top_p, top_k` | `825a4ff9...de3c490` |
| `C2` | OpenAI | `gpt-6.1-sol` | `reasoning_effort="medium"`, `service_tier="default"` | `2026101508` | `temperature, top_p, top_k, logprobs, top_logprobs` | `825a4ff9...de3c490` |
| `C3` | Anthropic | `claude-sonnet-5-5` | `thinking={"type": "adaptive"}`, `effort="high"` | omitted | `temperature, top_p, top_k, seed` | `825a4ff9...de3c490` |

- **Execution Invariants:** `llm_calls_per_execution = 1`, `automatic_retry = 0`, `transport_retry = 0`, `manual_retry = 0`, `fallback = False`, `llm_repair = 0`, `deterministic_semantic_repair = False`, `tools = False`, `max_output_tokens = 16384`, `timeout_ms = 55000`.
- Any fourth candidate (`C4`), model substitution, or alias replacement is rejected with `CandidateRegistryIntegrityError`.

---

## 4. Prompt Registry Infrastructure

- Supports at most `2` shared semantic prompt candidates (`P1`, `P2`).
- Rejects `P3` or `> 2` prompts or provider-specific prompt variants with `PromptRegistryIntegrityError`.
- Single-prompt registration requires `prompt_id == "P1"`.
- Cell budgets:
  - `DEV-TUNE` with `1` prompt: `20 × 3 × 1 = 60` cells
  - `DEV-TUNE` with `2` prompts: `20 × 3 × 2 = 120` cells
  - `DEV-SELECT` with `1` locked prompt: `60 × 3 × 1 = 180` cells

---

## 5. Primary Scientific Metrics & Denominator Policy

Every assigned cell remains in the denominator (`n_assigned`). Failures (authentication, model access, HTTP error, `429`, `5xx`, timeout, malformed JSON, schema-invalid output, semantic validation failure, refusal, max-token truncation, model-integrity mismatch) remain in `n_assigned` with `0` numerator contribution.

The three primary scientific rates are computed and reported separately (no weighted composite score is permitted):
1. `VALID_RUN_AND_SCHEMA_RATE` (`n_valid_schema / n_assigned`)
2. `EXACT_GROUNDING_PASS_RATE` (`n_exact_grounding_pass / n_assigned`)
3. `FINAL_CORE_PASS_RATE` (`n_core_pass / n_assigned`)

---

## 6. Selection Algorithms (Set-Based Relative-to-Best 10pp Rule)

Both `DEV-TUNE` and `DEV-SELECT` apply set-based relative-to-best survivor reduction on Criteria 1–3:
$$\text{best} = \max_{s \in S} \text{score}(s), \quad S_{\text{next}} = \{s \in S \mid \text{best} - \text{score}(s) \le 0.10\}$$
Pairwise chaining is strictly forbidden (e.g., for scores $A=0.90, B=0.82, C=0.73$, $\text{best}=0.90$, so $C$ is eliminated because $0.90 - 0.73 = 0.17 > 0.10$).

- **`DEV-TUNE` Prompt Selection:**
  - Evaluates Criteria 1 → 2 → 3 across pooled `candidate × DEV-TUNE fixture` cells (`60` per prompt).
  - If multiple prompts survive Criterion 3, selects `P1` administratively (`is_administrative_tiebreak = True`).
  - Never uses cost, latency, human preference, or `final100`.
- **`DEV-SELECT` Model Selection:**
  - Evaluates Criteria 1 → 2 → 3 across `60` `DEV-SELECT` fixtures on the locked prompt.
  - If multiple candidates survive Criterion 3:
    - **Criterion 4 (`MEDIAN_COST_PER_SCENARIO`):** Applied ONLY if authoritative, comparable canonical cost exists for ALL current survivors (`COST_CRITERION_APPLIED`), retaining the minimum unrounded canonical median cost. If ANY survivor lacks comparable cost, cost is skipped for ALL survivors (`COST_CRITERION_SKIPPED_NOT_COMPARABLE`).
    - **Criterion 5 (`MEDIAN_LATENCY`):** Retains the minimum unrounded canonical median latency.
    - **Final Administrative Tiebreak:** Fixed order `C1 > C2 > C3` (`administrative_tiebreak_claims_scientific_superiority = False`).

---

## 7. Post-Winner Stochasticity Diagnostic Gate

- Strictly gated AFTER `DEV-SELECT` selects a winning candidate (`StochasticityGateViolationError` if called before winner selection).
- Uses the `5` lexicographically smallest frozen `DEV-TUNE` scenario IDs (`W06-DEV-TUNE-001` .. `W06-DEV-TUNE-005`) × `3` executions per fixture = `15` maximum calls (`retry = 0`, `best_of_n = False`, `diagnostic_only = True`).
