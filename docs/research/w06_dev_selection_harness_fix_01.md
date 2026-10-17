# W06 DEV Selection Harness Fix 01 Report (`W06-DEV-SELECTION-HARNESS-FIX-01`)

## 1. Executive Summary

- **Task ID:** `W06-DEV-SELECTION-HARNESS-FIX-01`
- **Source Branch / Base SHA:** `develop` (`f81faa7de3988a20af1adc5b04601c49cf953d4a`)
- **Working Branch:** `research/w06-dev-selection-harness-fix-01`
- **Historical QA Baseline:** `W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL` (`QA_CHECKS_TOTAL = 40`, `QA_PASS = 30`, `QA_FAIL = 10`; 5 CRITICAL, 5 MAJOR)
- **Historical QA-01 Evidence Preserved:** `true` (0 bytes modified across all 4 historical QA-01 files)
- **Live Provider Calls:** `0` (`PROVIDER_COST_USD = $0`)
- **Fix Regression Tests (`FIX-01` .. `FIX-35`):** `35 / 35 PASSED`
- **Existing Harness Tests (`test_w06_dev_selection_harness_01.py`):** `35 / 35 PASSED`
- **Fix Status:** `READY_FOR_RE_QA`
- **Next Gate:** `W06-DEV-SELECTION-HARNESS-QA-02-OFFLINE-RERUN`

---

## 2. Historical QA-01 Evidence Preservation Proof

In strict compliance with Sections 1 and 17, the historical adversarial QA-01 evidence files were left 100% untouched (`git diff f81faa7de3988a20af1adc5b04601c49cf953d4a` is empty for all four files):

| Historical QA-01 File | LF-Normalized SHA256 | Modified? |
|---|---|---|
| `data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json` | `51b7606ebca7b5a67b6e6514d2f0c4fa4c7933919be2a5c2ec8179b21b286c9f` | `NO` |
| `docs/research/w06_dev_selection_harness_qa_01.md` | `2620638d08d76dd619743f606e004c14fe5822635caafd130a258d5e052ff7d9` | `NO` |
| `scripts/audit_w06_dev_selection_harness.py` | `878f89ecd80e62a80c1ad23e9a48fa03ace4bb1b228c5ba1814c3cf632a3bd80` | `NO` |
| `apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py` | `b97615b4279a669e0064213681442a3c7506a5fc048f77ca9b5814d6c882bc18` | `NO` |

---

## 3. Root Cause, Exact Code Changes, and Proof by Defect ID

### 3.1 `QA-14` (CRITICAL) — Fix Group A: Remove Primary Semantic Rescue

- **Root Cause:** `execute_dev_cell_with_mock_transport` in `apps/ai-service/app/evaluation/dev_selection_harness.py` imported and called `parse_strict_benchmark_plan_response` as a fallback whenever `BenchmarkPlanResponse.model_validate` failed, synthesizing missing `plan_id`, `scenario_id`, `destination_slug`, `day_cost`, and `budget_analysis`.
- **Exact Code Change:**
  - Removed `parse_strict_benchmark_plan_response` import and fallback from `apps/ai-service/app/evaluation/dev_selection_harness.py`.
  - Implemented `parse_primary_dev_plan_response(raw_text)` which strictly executes:
    1. Reject empty strings and markdown code fences (` ``` `).
    2. `decoded_json = json.loads(raw_text)`.
    3. Verify explicit presence of all required top-level keys (`plan_id`, `scenario_id`, `destination_slug`, `destination`, `total_days`, `overview`, `best_time_to_visit`, `general_tips`, `budget_analysis`, `days`), required `budget_analysis` keys (`total_budget`, `estimated_cost`, `currency`, `is_over_budget`, `variance`), and required per-day keys (`day_number`, `title`, `day_cost`, `items`, with `day_cost is not None`).
    4. `BenchmarkPlanResponse.model_validate(decoded_json)` with `extra="forbid"` and zero field synthesis.
- **Verification Tests:** `FIX-01`, `FIX-02`, `FIX-03`, `FIX-04`, `FIX-05`, `FIX-06`, `FIX-07`.

### 3.2 `QA-15` (CRITICAL) & `QA-39` (MAJOR) — Fix Groups B & C: Model Integrity Batch-Stop & Complete Failure Taxonomy

- **Root Cause:**
  1. `execute_dev_cell_with_mock_transport` previously substituted missing `returned_model_id` with `requested_model_id` (`returned_model = mock_response.returned_model_id or cell_manifest.requested_model_id`).
  2. `DevCellFailureClassification` lacked `PARTIAL_TIMEOUT` and `HARNESS_INTERNAL_ERROR`.
  3. `aggregate_dev_cell_receipts`, `select_winning_prompt_dev_tune`, `select_winning_candidate_dev_select`, and `execute_dev_batch_with_mock_transport` did not fail closed or halt the batch on `MODEL_INTEGRITY_MISMATCH` or `HARNESS_INTERNAL_ERROR`.
- **Exact Code Change:**
  - Extended `DevCellFailureClassification` with `PARTIAL_TIMEOUT` and `HARNESS_INTERNAL_ERROR`.
  - Partitioned outcomes into `ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS` (`HTTP_429`, `HTTP_5XX`, `TIMEOUT`, `PARTIAL_TIMEOUT`, `MALFORMED_JSON`, `SEMANTIC_VALIDATION_FAILURE`, `REFUSAL` — `counts_in_denominator=True`, `batch_stop_required=False`) and `BATCH_STOP_FAILURE_CLASSIFICATIONS` (`MODEL_INTEGRITY_MISMATCH`, `HARNESS_INTERNAL_ERROR` — `counts_in_denominator=False`, `batch_stop_required=True`).
  - Removed `returned_model_id or requested_model_id` substitution; added `is_returned_model_id_compatible` requiring non-empty exact match or provider-pinned snapshot prefix (`<requested_model_id>-*`).
  - Added `BatchExecutionFatalStopError`, `ModelIntegrityBatchStopError`, `HarnessInternalBatchStopError`, and `assert_batch_receipts_integrity(cell_receipts)` and wired them into `execute_dev_batch_with_mock_transport`, `aggregate_dev_cell_receipts`, `select_winning_prompt_dev_tune`, and `select_winning_candidate_dev_select`.
- **Verification Tests:** `FIX-08`, `FIX-09`, `FIX-10`, `FIX-11`, `FIX-12`, `FIX-13`, `FIX-14`, `FIX-15`.

### 3.3 `QA-05` (MAJOR) — Fix Group D: Content-Addressed Final-100 Firewall & Partition Label Enforcement

- **Root Cause:** `assert_not_final100_path` only checked direct filenames/path suffixes and missed copied/renamed files with identical SHA256 content; `assert_not_final100_scenario` did not reject cross-partition pairings (`W06-DEV-TUNE-*` paired with `W06_DEV_SELECT` or vice versa).
- **Exact Code Change:**
  - Updated `assert_not_final100_path` to resolve symlinks and, whenever the target path exists as a file, compute its LF-normalized SHA256 and reject `FORBIDDEN_FINAL100_BUNDLE_SHA256` (`c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1`) and `FORBIDDEN_P11_MANIFEST_SHA256` (`0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62`).
  - Updated `assert_not_final100_scenario` to require `W06-DEV-TUNE-*` scenarios to have `fixture_label == "W06_DEV_TUNE"` and `W06-DEV-SELECT-*` scenarios to have `fixture_label == "W06_DEV_SELECT"`.
- **Verification Tests:** `FIX-16`, `FIX-17`, `FIX-18`, `FIX-19`.

### 3.4 `QA-27` (CRITICAL) & `QA-28` (CRITICAL) — Fix Group E: Provider-Aware Token Billing & Cache Guard

- **Root Cause:** `MockProviderTransportResponse` and `DevCellExecutionReceipt` omitted `thought_tokens`, `reasoning_tokens`, `thinking_tokens`, and cache token fields; `execute_dev_cell_with_mock_transport` omitted `thought_tokens` for C1 (Google), while `compute_canonical_cell_cost_usd` blindly added `thought_or_reasoning_tokens` to `output_tokens` for all candidates, double-counting C2 (`reasoning_tokens`) and C3 (`thinking_tokens`).
- **Exact Code Change:**
  - Added `thought_tokens`, `reasoning_tokens`, `thinking_tokens`, `cached_input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `raw_usage_metadata`, and `latency_ns` to `MockProviderTransportResponse` and `DevCellExecutionReceipt`.
  - Implemented `compute_canonical_cell_cost_decimal` and updated `compute_canonical_cell_cost_usd`:
    - `C1` (`Google / gemini-3.8-flash`): `billable_output_tokens = output_tokens + (thought_tokens or 0)`.
    - `C2` (`OpenAI / gpt-6.1-sol`): `billable_output_tokens = output_tokens` (`reasoning_tokens` recorded for observability only, never added again).
    - `C3` (`Anthropic / claude-sonnet-5-5`): `billable_output_tokens = output_tokens` (`thinking_tokens` recorded for observability only, never added again).
    - Any nonzero `cached_input_tokens`, `cache_read_input_tokens`, or `cache_creation_input_tokens` returns `None` (`canonical_cost_usd = None`) so unpriced cache discounts cannot corrupt Criterion 4 cost comparability.
- **Verification Tests:** `FIX-20`, `FIX-21`, `FIX-22`, `FIX-23`.

### 3.5 `QA-29` (CRITICAL) & `QA-30` (MAJOR) — Fix Groups F & G: Unrounded Cost & Latency Tiebreaks

- **Root Cause:** `_to_exact_decimal` converted floats using `Decimal(f"{value:.12f}")`, truncating/rounding differences beyond 12 decimal places in Criterion 4 (cost) and Criterion 5 (latency) tiebreaks.
- **Exact Code Change:**
  - Updated `_to_exact_decimal` to use `Decimal(str(value))` with zero decimal-place truncation, zero rounding, and zero epsilon tolerance.
- **Verification Tests:** `FIX-24`, `FIX-25`.

### 3.6 `QA-32` (MAJOR) — Fix Group H: Single-Prompt Lock Status & Pre-Live Prompt Freeze Verifier

- **Root Cause:** Single-prompt DEV-TUNE returned `SINGLE_PROMPT_P1_LOCKED_WITHOUT_COMPARISON` instead of Method Lock's `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON`, and no fail-closed verifier enforced a separate frozen prompt artifact prior to live execution.
- **Exact Code Change:**
  - Set `SINGLE_PROMPT_P1_LOCK_STATUS = "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"`.
  - Added `PromptFreezeFirewallError`, `DevPromptFreezeArtifact`, `build_dev_prompt_freeze_artifact`, `verify_prompt_candidate_freeze_artifact`, and `assert_prompt_freeze_before_live`.
- **Verification Tests:** `FIX-26`, `FIX-27`.

### 3.7 `QA-33` (MAJOR) — Fix Group I: Complete Per-Cell Provenance (`code_commit_sha` & `provider_config_sha256`)

- **Root Cause:** `DevCellExecutionManifest` and `DevCellExecutionReceipt` lacked `code_commit_sha` and `provider_config_sha256`, and `execute_dev_cell_with_mock_transport` hardcoded `EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS` into `BenchmarkRunManifest`.
- **Exact Code Change:**
  - Added validated 40-hex `code_commit_sha` and 64-hex `provider_config_sha256` fields to `DevCellExecutionManifest` and `DevCellExecutionReceipt`.
  - Updated `execute_dev_cell_with_mock_transport` to propagate `cell_manifest.code_commit_sha` into `BenchmarkRunManifest`.
- **Verification Tests:** `FIX-28`.

---

## 4. Updated Failure Taxonomy Table (10 Method Lock Outcomes)

| # | Method Lock Outcome | Harness Enum (`DevCellFailureClassification`) | Retry Allowed | Counts in Denominator | Batch Stop Required | Exception Raised by Batch Gate |
|---|---|---|---|---|---|---|
| 1 | `HTTP_429_RATE_LIMIT` | `HTTP_429` | `False` | `True` | `False` | None (ordinary cell failure) |
| 2 | `HTTP_5XX_PROVIDER_ERROR` | `HTTP_5XX` | `False` | `True` | `False` | None (ordinary cell failure) |
| 3 | `TIMEOUT` | `TIMEOUT` | `False` | `True` | `False` | None (ordinary cell failure) |
| 4 | `PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE` | `PARTIAL_TIMEOUT` | `False` | `True` | `False` | None (ordinary cell failure) |
| 5 | `MALFORMED_OUTPUT_NON_JSON` | `MALFORMED_JSON` | `False` | `True` | `False` | None (ordinary cell failure) |
| 6 | `SCHEMA_NONCOMPLIANCE` | `SEMANTIC_VALIDATION_FAILURE` (unrescued) | `False` | `True` | `False` | None (ordinary cell failure) |
| 7 | `PROVIDER_REFUSAL` | `REFUSAL` | `False` | `True` | `False` | None (ordinary cell failure) |
| 8 | `DOWNSTREAM_CONSTRAINT_FAILURE` | `NONE` (scored via `exact_grounding_pass` / `final_core_pass`) | `False` | `True` | `False` | None (valid schema cell) |
| 9 | `MODEL_ID_OR_RESOLVED_VERSION_MISMATCH` | `MODEL_INTEGRITY_MISMATCH` | `False` | `False` | `True` | `ModelIntegrityBatchStopError` |
| 10 | `HARNESS_OR_INFRASTRUCTURE_ERROR` | `HARNESS_INTERNAL_ERROR` | `False` | `False` | `True` | `HarnessInternalBatchStopError` |

---

## 5. Provider Token & Billing Formula Table (`C1`, `C2`, `C3`)

| Candidate | Provider / Model ID | Billable Input Tokens | Billable Output Tokens | Reasoning / Thinking Token Rule | Nonzero Cache Token Rule |
|---|---|---|---|---|---|
| `C1` | `Google / gemini-3.8-flash` | `input_tokens` | `output_tokens + (thought_tokens or 0)` | Disjoint `thought_tokens` added once | `canonical_cost_usd = None` (non-comparable) |
| `C2` | `OpenAI / gpt-6.1-sol` | `input_tokens` | `output_tokens` | `reasoning_tokens` already included in `output_tokens` (never added again) | `canonical_cost_usd = None` (non-comparable) |
| `C3` | `Anthropic / claude-sonnet-5-5` | `input_tokens` | `output_tokens` | `thinking_tokens` already included in `output_tokens` (never added again) | `canonical_cost_usd = None` (non-comparable) |

---

## 6. Verification & Regression Test Matrix (`FIX-01` .. `FIX-35`)

| Test ID | Defect / Invariant Verified | Status |
|---|---|---|
| `FIX-01` | Missing `plan_id` fails `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-02` | Missing `budget_analysis` fails `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-03` | Missing `scenario_id` fails `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-04` | Missing `destination_slug` fails `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-05` | Missing `day_cost` fails `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-06` | Primary parser does not import or call `parse_strict_benchmark_plan_response` | `PASS` |
| `FIX-07` | Complete valid `BenchmarkPlanResponse` passes `VALID_RUN_AND_SCHEMA_RATE` | `PASS` |
| `FIX-08` | `returned_model_id` mismatch records `MODEL_INTEGRITY_MISMATCH` and halts batch | `PASS` |
| `FIX-09` | Missing/empty `returned_model_id` is not substituted with `requested_model_id` | `PASS` |
| `FIX-10` | `MODEL_INTEGRITY_MISMATCH` enforces `counts_in_denominator=False` and `batch_stop_required=True` | `PASS` |
| `FIX-11` | `aggregate_dev_cell_receipts` rejects `MODEL_INTEGRITY_MISMATCH` | `PASS` |
| `FIX-12` | `select_winning_prompt_dev_tune` rejects `MODEL_INTEGRITY_MISMATCH` | `PASS` |
| `FIX-13` | `select_winning_candidate_dev_select` rejects `MODEL_INTEGRITY_MISMATCH` | `PASS` |
| `FIX-14` | `HARNESS_INTERNAL_ERROR` halts batch and raises `HarnessInternalBatchStopError` | `PASS` |
| `FIX-15` | `PARTIAL_TIMEOUT` preserves denominator (`counts_in_denominator=True`) | `PASS` |
| `FIX-16` | Copied `final100` file with alias name fails `assert_not_final100_path` by SHA256 | `PASS` |
| `FIX-17` | Copied P11 manifest with alias name fails `assert_not_final100_path` by SHA256 | `PASS` |
| `FIX-18` | `W06-DEV-TUNE-001` with `W06_DEV_SELECT` label fails `assert_not_final100_scenario` | `PASS` |
| `FIX-19` | `W06-DEV-SELECT-001` with `W06_DEV_TUNE` label fails `assert_not_final100_scenario` | `PASS` |
| `FIX-20` | `C1` (`gemini-3.8-flash`) cost includes `thought_tokens` once | `PASS` |
| `FIX-21` | `C2` (`gpt-6.1-sol`) cost does not double-count `reasoning_tokens` | `PASS` |
| `FIX-22` | `C3` (`claude-sonnet-5-5`) cost does not double-count `thinking_tokens` | `PASS` |
| `FIX-23` | Nonzero unsupported cache tokens disable cost comparability (`canonical_cost_usd=None`) | `PASS` |
| `FIX-24` | Cost tiebreak distinguishes `Decimal("0.0100000000001")` vs `Decimal("0.0100000000002")` | `PASS` |
| `FIX-25` | Latency tiebreak distinguishes `100.0000000000001` vs `100.0000000000002` | `PASS` |
| `FIX-26` | Single-prompt DEV-TUNE returns `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON` | `PASS` |
| `FIX-27` | Missing/unverified/mismatched prompt freeze artifact fails closed before live mode | `PASS` |
| `FIX-28` | `code_commit_sha` and `provider_config_sha256` validated on manifest and receipt | `PASS` |
| `FIX-29` | DEV-TUNE 10pp set-based reduction passes | `PASS` |
| `FIX-30` | DEV-SELECT 10pp set-based reduction passes | `PASS` |
| `FIX-31` | Non-pairwise 10pp rule (no chaining) passes | `PASS` |
| `FIX-32` | Exact `0.10` boundary survival passes | `PASS` |
| `FIX-33` | REC-A 622 catalog integrity (`145 + 289 + 188 = 622`) passes | `PASS` |
| `FIX-34` | Stochasticity 5-fixture gate (`W06-DEV-TUNE-001..005`, max 15 calls) passes | `PASS` |
| `FIX-35` | Zero live calls, frozen authorities verified, and QA-01 evidence immutable | `PASS` |
