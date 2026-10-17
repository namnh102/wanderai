# W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL: Independent Scientific Red-Team QA Report

- **Task ID:** `W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL`
- **Role:** Independent scientific red-team / adversarial QA agent
- **Base `develop` SHA:** `68d05e72f25ea37c7da411d5dffcb65033ef8a95`
- **Target Under Audit:** `apps/ai-service/app/evaluation/dev_selection_harness.py` (unmodified during QA)
- **Live Provider Calls:** `0`
- **Provider Cost:** `$0.00`
- **Overall QA Verdict:** `FAIL` (`NEEDS_FIX`)
- **Next Gate:** `W06-DEV-SELECTION-HARNESS-FIX-01`

---

## 1. Executive Summary & Overall Verdict

An independent offline adversarial audit (`QA-01` through `QA-40`) was executed against `apps/ai-service/app/evaluation/dev_selection_harness.py` by re-deriving all expected invariants directly from the frozen W06 scientific authorities without trusting constants or helper assumptions inside the harness.

- **`QA_CHECKS_TOTAL`:** `40`
- **`QA_PASS`:** `30`
- **`QA_FAIL`:** `10`
- **`CRITICAL_FAILURES` (`5`):** `["QA-14", "QA-15", "QA-27", "QA-28", "QA-29"]`
- **`MAJOR_FAILURES` (`5`):** `["QA-05", "QA-30", "QA-32", "QA-33", "QA-39"]`
- **`OVERALL_QA`:** `FAIL`
- **`NEXT_GATE`:** `W06-DEV-SELECTION-HARNESS-FIX-01`

Per Section 28 of the QA specification, `apps/ai-service/app/evaluation/dev_selection_harness.py` was **not** patched or altered inside this QA task; all uncovered defects are preserved with reproducible adversarial test cases in `apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py` and machine-readable evidence in `data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json`.

---

## 2. Independent Oracle Derivations

### 2.1 Independent DEV Fixture & Marginal Oracle (`QA-02`, `QA-03`)
Derived directly from `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json`, `data/evaluation/w06/w06_dev_fixture_manifest_v1.json`, and `data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json`:
- **LF-normalized SHA256 (`w06_dev_fixtures_freeze_v1.json`):** `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`
- **Partition Counts:** `DEV_TOTAL = 80`, `DEV_TUNE = 20`, `DEV_SELECT = 60`
- **Overlap Invariants:** `all_dev_exact_overlap_with_final = 0`, `dev_tune_near_overlap_with_final = 0`
- **`DEV_TUNE` Marginals (`20`):**
  - `destination`: `{"ha-noi": 7, "da-nang": 7, "ha-long": 6}`
  - `days`: `{"2": 7, "3": 7, "4": 6}`
  - `interest_count`: `{"1": 7, "2": 7, "3": 6}`
  - `budget`: `{"B1": 5, "B2": 5, "B3": 5, "null": 5}`
  - `travel_style`: `{"BACKPACKER": 5, "BUDGET": 5, "COMFORT": 5, "LUXURY": 5}`
  - `weekend`: `{"true": 10, "false": 10}`
- **`DEV_SELECT` Marginals (`60`):**
  - `destination`: `{"ha-noi": 20, "da-nang": 20, "ha-long": 20}`
  - `days`: `{"2": 20, "3": 20, "4": 20}`
  - `interest_count`: `{"1": 20, "2": 20, "3": 20}`
  - `budget`: `{"B1": 15, "B2": 15, "B3": 15, "null": 15}`
  - `travel_style`: `{"BACKPACKER": 15, "BUDGET": 15, "COMFORT": 15, "LUXURY": 15}`
  - `weekend`: `{"true": 30, "false": 30}`

### 2.2 Independent REC-A-CORE-V2 Catalog Oracle (`QA-06`, `QA-07`, `QA-08`)
Derived directly from `data/curated/gomate_places_freeze_v2.json` and `apps/ai-service/recommendation/reca/contract.py`:
- **REC-A-CORE-V2 Counts:** `{"ha-noi": 145, "da-nang": 289, "ha-long": 188}` (`total = 622`)
- **Da Nang Map/Discovery vs REC-A-CORE-V2 (`293` vs `289`):** Exactly `4` lodging-only (`HOSPITALITY` / `hotel` with zero activity vector norm) places in Da Nang (`4c4ca7e8-2586-57cb-af5d-5e2b72c7bd4d`, `5e1ca20e-b579-59b8-b243-9f13aa43c65f`, `6489aeb0-fb3d-584d-9ca9-d6172e9cc63f`, `db61c6ab-1fde-51fe-ac20-0deef2fc5981`) are excluded from the 289-POI REC-A-CORE-V2 catalog.
- **Secondary Destination Leakage:** `0` POIs from the `133` secondary-destination places appear in any harness catalog context.

---

## 3. Domain Rollup Summary

| Domain | Verdict | Failing Checks |
| :--- | :--- | :--- |
| `DEV_BUNDLE` | `PASS` | None (`QA-01`, `QA-02`, `QA-03` PASS) |
| `FINAL100_FIREWALL` | `FAIL` | `QA-05` (`MAJOR`) |
| `RECA_CATALOG_CONTEXT` | `PASS` | None (`QA-06`, `QA-07`, `QA-08` PASS) |
| `PROVIDER_SERIALIZATION` | `PASS` | None (`QA-09`, `QA-10`, `QA-11`, `QA-12` PASS) |
| `STRICT_PRIMARY_PARSER` | `FAIL` | `QA-14` (`CRITICAL`) |
| `MODEL_ID_INTEGRITY_STOP_BATCH` | `FAIL` | `QA-15` (`CRITICAL`) |
| `DENOMINATOR_PRESERVATION` | `PASS` | None (`QA-16`, `QA-17`, `QA-18` PASS) |
| `METRIC_MAPPING` | `PASS` | None (`QA-19`, `QA-20`, `QA-21`, `QA-22` PASS) |
| `TEN_PP_SELECTION` | `PASS` | None (`QA-23`, `QA-24`, `QA-25` PASS) |
| `COST_COMPARABILITY` | `PASS` | None (`QA-26` PASS) |
| `PROVIDER_BILLING_TOKEN_SEMANTICS` | `FAIL` | `QA-27` (`CRITICAL`), `QA-28` (`CRITICAL`) |
| `UNROUNDED_COST_TIEBREAK` | `FAIL` | `QA-29` (`CRITICAL`) |
| `UNROUNDED_LATENCY_TIEBREAK` | `FAIL` | `QA-30` (`MAJOR`) |
| `PROMPT_FREEZE_FIREWALL` | `FAIL` | `QA-32` (`MAJOR`) |
| `CODE_COMMIT_PROVENANCE` | `FAIL` | `QA-33` (`MAJOR`) |
| `CELL_IMMUTABILITY` | `PASS` | None (`QA-34`, `QA-35`, `QA-36` PASS) |
| `STOCHASTICITY_GATE` | `PASS` | None (`QA-37`, `QA-38` PASS) |
| `FAILURE_TAXONOMY` | `FAIL` | `QA-39` (`MAJOR`) |

---

## 4. Detailed Root-Cause Evidence for Uncovered Scientific Defects

### 4.1 `QA-14` (`CRITICAL` — `PRIMARY_SEMANTIC_RESCUE_DETECTED`)
- **Location:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1552-L1563`
- **Mechanism:** Inside `execute_dev_cell_with_mock_transport`, the harness inspects the decoded JSON dictionary:
  ```python
  if "plan_id" in decoded_json and "budget_analysis" in decoded_json:
      plan_response = BenchmarkPlanResponse.model_validate(decoded_json)
  else:
      plan_response = parse_strict_benchmark_plan_response(
          raw_text=raw_text_stripped,
          scenario=scenario,
          run_id=cell_manifest.run_id,
      )
  ```
- **Scientific Impact:** Whenever a provider response omits `plan_id` or `budget_analysis` (both required by Portable Generation Schema V2 and `BenchmarkPlanResponse`), the harness falls back to `parse_strict_benchmark_plan_response`, which synthesizes missing `plan_id`, `scenario_id`, `destination_slug`, `day_cost`, and `budget_analysis` from the input scenario and silently drops unknown top-level keys (`extra_unsupported_field_without_plan_id_accepted = True`). This violates the `NO_REGEX_EXTRACTION_NO_MARKDOWN_STRIPPING_NO_JSON_REPAIR` / no-semantic-rescue rule of `w06_model_arch_selection_method_lock_v1.json`.

### 4.2 `QA-15` (`CRITICAL` — `MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH`)
- **Locations:**
  - `apps/ai-service/app/evaluation/dev_selection_harness.py:L1504`
  - `apps/ai-service/app/evaluation/dev_selection_harness.py:L1536-L1540`
  - `apps/ai-service/app/evaluation/dev_selection_harness.py:L1699-L1772`
- **Mechanism:**
  1. Line 1504 sets `returned_model_id = mock_response.returned_model_id or cell_manifest.requested_model_id`, silently masking an empty or `None` `returned_model_id` as a valid match.
  2. When `returned_model_id` is an unrelated model (e.g., `"gpt-4o-mini"` when `"gemini-3.8-flash"` was requested), lines 1536–1540 record `DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH` with `counts_in_denominator=True`, and `aggregate_dev_cell_receipts` / `select_winning_candidate_dev_select` proceed to compute rates and select a winner without raising a configuration-integrity batch-stop error.
- **Scientific Impact:** Violates `w06_model_arch_selection_method_lock_v1.json` (`model_id_or_resolved_version_mismatch = CONFIGURATION_INTEGRITY_FAILURE_STOP_BATCH_BEFORE_SCIENTIFIC_REPORTING`).

### 4.3 `QA-27` (`CRITICAL` — `PROVIDER_BILLING_TOKEN_SEMANTICS`)
- **Locations:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1398-L1401`, `L1455-L1457`, `L1624-L1628`
- **Mechanism:** `MockProviderTransportResponse` and `DevCellExecutionReceipt` only expose `input_tokens`, `output_tokens`, and `total_tokens`, omitting C1's disjoint `thought_tokens` (`usage_metadata.thoughts_token_count`) and all provider cache token fields (`cached_content_token_count`, `cached_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`). Furthermore, `execute_dev_cell_with_mock_transport` calls `compute_canonical_cell_cost_usd` without passing `thought_or_reasoning_tokens`.
- **Scientific Impact:** Undercounts C1 (`gemini-3.8-flash`) billable output tokens whenever thinking is active (`thinking_level="medium"`), and fails to verify or price cache token usage across C1, C2, and C3.

### 4.4 `QA-28` (`CRITICAL` — `REASONING_THINKING_DOUBLE_COUNT`)
- **Location:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1355-L1373`
- **Mechanism:** `compute_canonical_cell_cost_usd` unconditionally executes:
  ```python
  billed_out = output_tokens + (thought_or_reasoning_tokens or 0)
  ```
  regardless of `cost_record.candidate_id`.
- **Scientific Impact:** For C2 (`gpt-6.1-sol`) and C3 (`claude-sonnet-5-5`), official provider documentation and the 01D live receipt prove that `completion_tokens`/`output_tokens` **already includes** `reasoning_tokens`/`thinking_tokens`. Adding `thought_or_reasoning_tokens` again inflates C2 cost (`$0.015804` vs true `$0.011454` on 01D token counts) and C3 cost (`$0.035691` vs true `$0.023691`).

### 4.5 `QA-29` (`CRITICAL` — `COST_TIEBREAK_NOT_UNROUNDED`)
- **Locations:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1775-L1777`, `L2120-L2126`
- **Mechanism:** `_to_exact_decimal(value: float)` converts floats via `Decimal(f"{value:.12f}")`.
- **Scientific Impact:** When `C1` has median cost `0.0100000000001` and `C2` has median cost `0.0100000000002` (with `C2` faster on latency), both costs round to `Decimal("0.010000000000")`, producing a false tie `["C1", "C2"]` at `MEDIAN_COST_PER_SCENARIO` and allowing `C2` to win at `MEDIAN_LATENCY` instead of `C1` winning at `MEDIAN_COST_PER_SCENARIO`.

### 4.6 `QA-05` (`MAJOR` — `FINAL100_ALIAS_FIREWALL`)
- **Location:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L318-L365`
- **Mechanism:** `assert_not_final100_path` checks only the filename and resolved path against `FORBIDDEN_FINAL100_BUNDLE_PATH`, without computing the file's LF-normalized SHA256 against `FORBIDDEN_FINAL100_SHA256` (`7999c7fc47ebcecd0cb8aeccfb3fb13afe2cb3fb7ebdc5ebce0efbf7eb1812f4`) when `w06_scenarios_freeze_v1.json` is copied to a different filename (e.g., `copied_bundle.json`). Additionally, `assert_not_final100_scenario` checks `scenario_id` prefix and `fixture_label` independently, allowing a cross-partition mismatch (`scenario_id="W06-DEV-TUNE-001"` with `fixture_label="W06_DEV_SELECT"`).

### 4.7 `QA-30` (`MAJOR` — `LATENCY_TIEBREAK_ROUNDING`)
- **Locations:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1775-L1777`, `L2162-L2166`
- **Mechanism:** `median_latency_ms` is converted via `_to_exact_decimal(value)` (`Decimal(f"{value:.12f}")`).
- **Scientific Impact:** Distinct IEEE-754 floats that differ after the 12th decimal place (e.g., `C1 = 1.0000000000002` ms vs `C2 = 1.0000000000001` ms, where `C2 < C1`) are both rounded to `Decimal("1.000000000000")`, collapsing a strict latency ordering into a false tie and selecting `C1` via `FINAL_ADMINISTRATIVE_TIEBREAK_C1_GT_C2_GT_C3` instead of `C2` at `MEDIAN_LATENCY`.

### 4.8 `QA-32` (`MAJOR` — `PROMPT_FREEZE_REQUIRED_BEFORE_LIVE`)
- **Location:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1894-L1905`
- **Mechanism:**
  1. The harness does not implement a pre-live prompt freeze gate requiring a separate frozen prompt artifact (`prompt_ids`, `prompt_sha256`, `system_prompt`, `user_template`, `created_before_live`, `candidate_list`, `dev_tune_plan_sha256`, `call_budget`) before live DEV-TUNE execution.
  2. When only `P1` is registered, `select_winning_prompt_dev_tune` returns `selected_at_stage="SINGLE_FROZEN_PROMPT_P1_LOCKED_WITHOUT_COMPARISON"` instead of the exact canonical status `"LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"`.

### 4.9 `QA-33` (`MAJOR` — `SCIENTIFIC_CODE_COMMIT_PROVENANCE`)
- **Locations:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L1053-L1086`, `L1376-L1408`, `L1598`
- **Mechanism:** `DevCellExecutionManifest` and `DevCellExecutionReceipt` omit `code_commit_sha` and `provider_config_sha256`, and `execute_dev_cell_with_mock_transport` (line 1598) hardcodes `base_develop_sha=EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS` (`50884c610cebf455255b9d05f737d9558cabf2e7`) in `BenchmarkRunManifest` instead of recording the active scientific code commit SHA.

### 4.10 `QA-39` (`MAJOR` — `FAILURE_TAXONOMY_MAPPING`)
- **Locations:** `apps/ai-service/app/evaluation/dev_selection_harness.py:L300-L316`, `L1699-L1772`
- **Mechanism:** `DevCellFailureClassification` omits `PARTIAL_TIMEOUT` (`PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE`) and `HARNESS_INTERNAL_ERROR` (`HARNESS_OR_INFRASTRUCTURE_ERROR`), and `aggregate_dev_cell_receipts` does not stop the batch when `MODEL_INTEGRITY_MISMATCH` or a harness error occurs.

---

## 5. Provider Token Billing Semantics Audit (`QA-27`, `QA-28`)

Access Date: `2026-10-18` (Zero live generation calls).

| Candidate | Provider / Model | Official Documentation URLs | Billable Input Field | Billable Output Field | Reasoning / Thinking Token Relationship | Cache Token Treatment | Harness Defect |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `C1` | Google / `gemini-3.8-flash` | `https://ai.google.dev/gemini-api/docs/thinking`<br>`https://ai.google.dev/gemini-api/docs/tokens`<br>`https://ai.google.dev/gemini-api/docs/caching` | `usage_metadata.prompt_token_count` | `usage_metadata.candidates_token_count + usage_metadata.thoughts_token_count` | **Disjoint (`MUST_BE_ADDED`):** `candidates_token_count` excludes `thoughts_token_count`. Confirmed by official docs (*"When thinking is turned on, response pricing is the sum of output tokens and thinking tokens"*) and 01D live receipt (`514 + 599 + 3179 = 4292`). | `usage_metadata.cached_content_token_count` is billed at reduced cached-input rate; must be `0` or priced separately for comparability. | `MockProviderTransportResponse`, `DevCellExecutionReceipt`, and `execute_dev_cell_with_mock_transport` omit `thought_tokens` and cache token fields, undercounting C1 output tokens. |
| `C2` | OpenAI / `gpt-6.1-sol` | `https://developers.openai.com/api/docs/guides/reasoning`<br>`https://platform.openai.com/docs/guides/reasoning` | `usage.prompt_tokens` (or `usage.input_tokens`) | `usage.completion_tokens` (or `usage.output_tokens`) | **Inclusive (`ALREADY_INCLUDED`):** `completion_tokens_details.reasoning_tokens` is an observability breakdown already included in `completion_tokens`. Confirmed by official docs (`75 + 1186 = 1261` with `reasoning_tokens=1024`) and 01D live receipt (`577 + 1030 = 1607` with `reasoning_tokens=435`). | `prompt_tokens_details.cached_tokens` is billed at discounted cached-input rate; must be `0` or priced separately. | `compute_canonical_cell_cost_usd` blindly adds `thought_or_reasoning_tokens` to `output_tokens` for all candidates, double-counting C2 `reasoning_tokens`. |
| `C3` | Anthropic / `claude-sonnet-5-5` | `https://platform.claude.com/docs/en/build-with-claude/thinking`<br>`https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost` | `usage.input_tokens` (+ `cache_creation_input_tokens` / `cache_read_input_tokens` if used) | `usage.output_tokens` | **Inclusive (`ALREADY_INCLUDED`):** Official docs state *"output_tokens remains the inclusive, authoritative total used for billing. output_tokens_details.thinking_tokens is a read-only breakdown for observability."* Confirmed by 01D live receipt (`1062 + 1367 = 2429`). | `cache_creation_input_tokens` (`1.25x`/`2x`) and `cache_read_input_tokens` (`0.1x`) have distinct multipliers; must be verified `0` or priced separately. | `compute_canonical_cell_cost_usd` blindly adds `thought_or_reasoning_tokens` to `output_tokens` for all candidates, double-counting C3 `thinking_tokens`. |

---

## 6. Section 26 Failure Taxonomy Mapping Table (`QA-39`)

| Method-Lock Outcome | Harness Classification | Retry Allowed | Preserves Denominator | Expected Stop Batch | Observed Stop Batch | Mapping Valid |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HTTP_429_RATE_LIMIT` | `HTTP_429` | `False` | `True` | `False` | `False` | `True` |
| `HTTP_5XX_PROVIDER_ERROR` | `HTTP_5XX` | `False` | `True` | `False` | `False` | `True` |
| `TIMEOUT` | `TIMEOUT` | `False` | `True` | `False` | `False` | `True` |
| `PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE` | `UNMAPPED_NO_PARTIAL_TIMEOUT_ENUM_VALUE` | `False` | `True` | `False` | `False` | **`False`** |
| `MALFORMED_OUTPUT_NON_JSON` | `MALFORMED_JSON` | `False` | `True` | `False` | `False` | `True` |
| `SCHEMA_NONCOMPLIANCE` | `SEMANTIC_VALIDATION_FAILURE (rescued when plan_id/budget_analysis omitted)` | `False` | `True` | `False` | `False` | **`False`** |
| `PROVIDER_REFUSAL` | `REFUSAL` | `False` | `True` | `False` | `False` | `True` |
| `DOWNSTREAM_CONSTRAINT_FAILURE` | `NONE (evaluated downstream via exact_grounding_pass / final_core_pass)` | `False` | `True` | `False` | `False` | `True` |
| `MODEL_ID_OR_RESOLVED_VERSION_MISMATCH` | `MODEL_INTEGRITY_MISMATCH` | `False` | `False` | `True` | `False` | **`False`** |
| `HARNESS_OR_INFRASTRUCTURE_ERROR` | `UNMAPPED_NO_HARNESS_ERROR_ENUM_OR_STOP_BATCH_GUARD` | `False` | `False` | `True` | `False` | **`False`** |

---

## 7. Complete 40-Check QA Matrix (`QA-01` .. `QA-40`)

| Check ID | Description | Severity | Status | Summary of Expected vs Observed |
| :--- | :--- | :--- | :--- | :--- |
| `QA-01` | source/base integrity | `CRITICAL` | `PASS` | Base `develop` SHA is `68d05e72f25ea37c7da411d5dffcb65033ef8a95`; all 11 frozen authorities present; `dev_selection_harness.py` unmodified. |
| `QA-02` | DEV bundle integrity | `CRITICAL` | `PASS` | `bundle_sha256 = bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`, `80 = 20 + 60`, exact/near overlap with final100 = `0`. |
| `QA-03` | DEV marginals | `CRITICAL` | `PASS` | Independent marginal counts on `DEV_TUNE` (`20`) and `DEV_SELECT` (`60`) match harness and manifest 100%. |
| `QA-04` | final100 direct firewall | `CRITICAL` | `PASS` | Direct/relative/absolute paths to `w06_scenarios_freeze_v1.json` and `w06_p11_assignment_manifest_v1.json` and `W06-S*` IDs raise `Final100FirewallViolationError`. |
| `QA-05` | final100 alias/symlink firewall | `MAJOR` | **`FAIL`** | Copied final100 bundle under a different filename bypasses `assert_not_final100_path` (no SHA256 check) and raises `ValueError` instead of `Final100FirewallViolationError` in loader; `W06-DEV-TUNE-001` with `W06_DEV_SELECT` label is not blocked by `assert_not_final100_scenario`. |
| `QA-06` | REC-A exact 622 catalog | `CRITICAL` | `PASS` | `ha-noi=145`, `da-nang=289`, `ha-long=188` (`total=622`), deterministic `place_id` ordering verified across fixtures. |
| `QA-07` | DN 289 not 293 | `CRITICAL` | `PASS` | All 4 Da Nang lodging-only (`HOSPITALITY`) POIs excluded; Da Nang catalog count is `289`, not `293`. |
| `QA-08` | no secondary leakage | `CRITICAL` | `PASS` | `0` of `133` secondary-destination places appear in any REC-A catalog context. |
| `QA-09` | provider semantic-input equality | `CRITICAL` | `PASS` | `C1`, `C2`, `C3` receive identical `scenario_sha256`, `catalog_context_sha256`, `system_prompt_sha256`, `user_prompt_sha256`, `semantic_schema_sha256`, and `portable_generation_schema_v2_sha256`. |
| `QA-10` | C1 config | `CRITICAL` | `PASS` | `gemini-3.8-flash`, `thinking_level="medium"`, `seed=2026101508`, `temperature/top_p/top_k` omitted, `max_output_tokens=16384`, `retry=0`, `tools=False`, Schema V2 SHA256 matched. |
| `QA-11` | C2 config | `CRITICAL` | `PASS` | `gpt-6.1-sol`, `reasoning_effort="medium"`, `seed=2026101508`, `service_tier="default"`, `temperature/top_p/top_k` omitted, `max_completion_tokens=16384`, `max_retries=0`, `tools=False`, Schema V2 SHA256 matched. |
| `QA-12` | C3 config | `CRITICAL` | `PASS` | `claude-sonnet-5-5`, `thinking={"type": "adaptive"}`, `effort="high"`, `seed/temperature/top_p/top_k` omitted, `max_tokens=16384`, `max_retries=0`, `tools=False`, Schema V2 SHA256 matched. |
| `QA-13` | strict raw JSON only | `CRITICAL` | `PASS` | Markdown fences, leading/trailing prose, trailing commas, wrong primitive types, and <2 items/day are rejected as invalid schema (`valid_run_and_schema=False`). |
| `QA-14` | no semantic rescue | `CRITICAL` | **`FAIL`** | `PRIMARY_SEMANTIC_RESCUE_DETECTED`: when `plan_id` or `budget_analysis` is omitted, harness falls back to `parse_strict_benchmark_plan_response` and synthesizes missing semantic fields. |
| `QA-15` | model-ID mismatch stops batch | `CRITICAL` | **`FAIL`** | `MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH`: missing `returned_model_id` defaults to `requested_model_id`, and mismatched `returned_model_id` is scored as an ordinary failed cell without stopping the batch. |
| `QA-16` | ordinary provider failures preserve denominator | `CRITICAL` | `PASS` | `TIMEOUT` / `HTTP_429` / `HTTP_5XX` / `REFUSAL` preserve `n_assigned = 60` (`59/60 = 0.9833333333333333`). |
| `QA-17` | missing receipt fails closed | `CRITICAL` | `PASS` | `59` receipts for `60` assigned fixtures raises `DenominatorIntegrityError`. |
| `QA-18` | duplicate receipt fails closed | `CRITICAL` | `PASS` | Duplicate `(candidate_id, prompt_id, fixture_id)` receipt (61 receipts or 60 with duplicate) and `attempted=False` raise `DenominatorIntegrityError`. |
| `QA-19` | exact grounding mapping | `CRITICAL` | `PASS` | Invalid `place_id` (Case B) and cross-destination `place_id` (Case C) yield `valid_run_and_schema=True`, `exact_grounding_pass=False`, `final_core_pass=False`. |
| `QA-20` | core mapping | `CRITICAL` | `PASS` | Grounding, destination, duplicate, minimum 2 POI/day, schedule, opening-hours, and `ESTIMATED_BUDGET_COMPLIANCE` map accurately to `core_scenario_pass`; travel-time and preference satisfaction are excluded; no composite score exists. |
| `QA-21` | opening-hours semantics | `CRITICAL` | `PASS` | Known opening-hours violation (`20:00-21:30` vs `Mo-Su 08:00-17:00`) fails `final_core_pass`; `opening_hours=None` (`UNKNOWN`) is neutral (`final_core_pass=True`). |
| `QA-22` | minimum 2 POI/day | `CRITICAL` | `PASS` | 1 `POI_VISIT`/day (Case F) and 1 `POI_VISIT` + 1 `TRANSIT_ONLY`/day (Case G) both fail `final_core_pass` while keeping `exact_grounding_pass=True`. |
| `QA-23` | 10pp non-pairwise | `CRITICAL` | `PASS` | `C1=0.90`, `C2=0.82`, `C3=0.73` eliminates `C3` against `best_current_survivor=0.90` (`0.73 < 0.80`), not chained pairwise against `0.82`. |
| `QA-24` | exact 10pp boundary | `CRITICAL` | `PASS` | `0.80` vs `0.90` survives (`Decimal("0.80") >= Decimal("0.90") - Decimal("0.10")`); `0.799999999999` is eliminated. |
| `QA-25` | early survivor stopping | `CRITICAL` | `PASS` | Selection stops immediately at Criterion 1, 2, or 3 as soon as `len(survivors) == 1`. |
| `QA-26` | cost comparability all-current-survivors | `CRITICAL` | `PASS` | Missing cost on eliminated `C3` does not skip cost stage for surviving `C1, C2`; missing cost on surviving `C2` skips cost stage with `COST_CRITERION_SKIPPED_NOT_COMPARABLE`. |
| `QA-27` | provider token billing semantics | `CRITICAL` | **`FAIL`** | Transport and receipt schemas omit C1 disjoint `thought_tokens` (`thoughts_token_count`) and provider cache token fields. |
| `QA-28` | no reasoning/thinking double count | `CRITICAL` | **`FAIL`** | `compute_canonical_cell_cost_usd` adds `thought_or_reasoning_tokens` to `output_tokens` for C2 and C3, double-counting inclusive reasoning/thinking tokens. |
| `QA-29` | unrounded cost comparison | `CRITICAL` | **`FAIL`** | `COST_TIEBREAK_NOT_UNROUNDED`: `_to_exact_decimal` rounds `0.0100000000001` and `0.0100000000002` via `:.12f` into a false tie, letting `C2` win on latency. |
| `QA-30` | unrounded latency comparison | `MAJOR` | **`FAIL`** | `LATENCY_TIEBREAK_ROUNDING`: `_to_exact_decimal` rounds `1.0000000000002` ms and `1.0000000000001` ms via `:.12f` into a false tie, selecting `C1` via administrative tiebreak instead of `C2` at `MEDIAN_LATENCY`. |
| `QA-31` | P1/P2 registry status | `CRITICAL` | `PASS` | `prompt_semantic_freeze_status = INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE`; supports `P1` and `["P1", "P2"]`; rejects `P3`, post-hoc prompts, and provider-specific prompts. |
| `QA-32` | prompt freeze required before live | `MAJOR` | **`FAIL`** | No pre-live prompt freeze artifact gate; single-prompt DEV-TUNE returns `SINGLE_FROZEN_PROMPT_P1_LOCKED_WITHOUT_COMPARISON` instead of `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON`. |
| `QA-33` | scientific code commit provenance | `MAJOR` | **`FAIL`** | `DevCellExecutionManifest` and `DevCellExecutionReceipt` omit `code_commit_sha` and `provider_config_sha256`; mock execution hardcodes `EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS`. |
| `QA-34` | cell immutability | `CRITICAL` | `PASS` | Second execution in same cell directory or reusing `run_id` directory for different fixture/candidate raises `CellExecutionImmutabilityError`. |
| `QA-35` | plan reproducibility | `CRITICAL` | `PASS` | Two clean subprocesses produce byte-for-byte identical `DEV_TUNE` (`cf6f3966069f5c86d9696a8d3992876a4b492238336eb278da76cf318e564c81`) and `DEV_SELECT` (`f8538f7499ad3f19beda709697cc01bdf5bb5daef17cd2d985d0da6b79ddfe59`) plans. |
| `QA-36` | exact 60/120/180 cell budgets | `CRITICAL` | `PASS` | `DEV_TUNE` (`P1`) = `60` cells, `DEV_TUNE` (`P1+P2`) = `120` cells, `DEV_SELECT` = `180` cells (`attempt_number=1`, no best-of-N). |
| `QA-37` | stochasticity pre-winner block | `CRITICAL` | `PASS` | Calling `build_stochasticity_diagnostic_plan` with `None`, `winner_selected=False`, or mismatched `locked_prompt_id` raises `StochasticityPolicyError`. |
| `QA-38` | stochasticity exact 15 design | `CRITICAL` | `PASS` | Exact 5 fixtures (`W06-DEV-TUNE-001..005`) $\times 3 = 15$ calls on selected winner only; `may_alter_*` flags are all `False`. |
| `QA-39` | failure taxonomy mapping | `MAJOR` | **`FAIL`** | 4 of 10 method-lock outcomes (`PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE`, `SCHEMA_NONCOMPLIANCE`, `MODEL_ID_OR_RESOLVED_VERSION_MISMATCH`, `HARNESS_OR_INFRASTRUCTURE_ERROR`) lack valid enum / stop-batch / non-rescue mapping. |
| `QA-40` | no live / no DEV / no final100 evidence | `CRITICAL` | `PASS` | AST/source inspection confirms zero live SDK client calls in `dev_selection_harness.py`; `live_provider_calls=0`, `provider_cost_usd=0`, `final100_used=False`, `winner_selected=False`. |
