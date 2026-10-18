# W06 DEV Selection Harness Fix 01 Report (`W06-DEV-SELECTION-HARNESS-FIX-01`, `AUDIT-CORRECTION-01`, `AUDIT-CORRECTION-02`, & `AUDIT-CORRECTION-03`)

## 1. Executive Summary

- **Task ID:** `W06-DEV-SELECTION-HARNESS-FIX-01`
- **Audit Correction IDs:**
  - `W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-01` (`chatgpt_audit_correction_required = true`)
  - `W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-02` (`audit_correction_02_required = true`)
  - `W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-03` (`audit_correction_03_required = true`)
- **Source Branch / Base SHA:** `develop` (`f81faa7de3988a20af1adc5b04601c49cf953d4a`)
- **Working Branch / PR:** `research/w06-dev-selection-harness-fix-01` (PR #49)
- **Previous Audited Commits on PR #49:**
  - `a35859764b1475d33e5e0dd752557a1876e38adb` (`FIX-01`)
  - `1b5fe2d08403a2f3fe25fb93ef9258dd047524d5` (`AUDIT-CORRECTION-01`)
  - `923c07d64919afd7fb706e67e4c2c229ef2cb368` (`AUDIT-CORRECTION-02`)
- **Historical QA Baseline:** `W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL` (`QA_CHECKS_TOTAL = 40`, `QA_PASS = 30`, `QA_FAIL = 10`; 5 CRITICAL, 5 MAJOR)
- **Historical QA-01 Evidence Preserved:** `true` (0 bytes modified across all 4 historical QA-01 files)
- **Live Provider Calls:** `0` (`PROVIDER_COST_USD = $0`)
- **Audit Correction Status:**
  - `exact_cost_end_to_end`: `PASS`
  - `latency_ns_selection_authority`: `PASS`
  - `code_sha_fail_closed`: `PASS`
  - `historical_qa_runtime_monkeypatch_removed`: `PASS`
  - `persisted_provenance_fail_closed`: `PASS`
  - `bundle_file_hashes_required`: `PASS`
  - `bundle_hash_authoritative_byte_read`: `PASS`
  - `same_mtime_same_size_cache_bypass_closed`: `PASS`
- **Fix & Audit Correction Regression Tests (`FIX-01` .. `FIX-35` + `AC-01` .. `AC-18` + `PC-01` .. `PC-18` + `PH-01` .. `PH-24`):** `95 / 95 PASSED`
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
  - Implemented `compute_canonical_cell_cost_decimal` and `compute_canonical_cell_cost_decimal_str`:
    - `C1` (`Google / gemini-3.8-flash`): `billable_output_tokens = output_tokens + (thought_tokens or 0)`.
    - `C2` (`OpenAI / gpt-6.1-sol`): `billable_output_tokens = output_tokens` (`reasoning_tokens` recorded for observability only, never added again).
    - `C3` (`Anthropic / claude-sonnet-5-5`): `billable_output_tokens = output_tokens` (`thinking_tokens` recorded for observability only, never added again).
    - Any nonzero `cached_input_tokens`, `cache_read_input_tokens`, or `cache_creation_input_tokens` returns `None` (`canonical_cost_usd_decimal = None`) so unpriced cache discounts cannot corrupt Criterion 4 cost comparability.
- **Verification Tests:** `FIX-20`, `FIX-21`, `FIX-22`, `FIX-23`.

### 3.5 `QA-29` (CRITICAL) — Fix Group F & Audit Correction A: Exact Canonical Cost End-to-End

- **Root Cause:** `_to_exact_decimal` initially formatted floats via `f"{value:.12f}"`, and in commit `a35859764b1475d33e5e0dd752557a1876e38adb` `DevCellExecutionReceipt.canonical_cost_usd` and `DevGroupAggregateMetrics.median_canonical_cost_usd` still stored IEEE-754 `float` values before Criterion 4 comparison.
- **Exact Code Change (Correction A):**
  - Added `DECIMAL_SCIENTIFIC_PRECISION = 100`, `format_canonical_decimal_str`, `parse_canonical_decimal_str`, and `compute_exact_decimal_median` (which strictly rejects `float` inputs and divides by `Decimal(2)` under `localcontext(prec=100)` for even sample sizes).
  - Added authoritative `canonical_cost_usd_decimal: Optional[str]` on `DevCellExecutionReceipt` (populated directly from `compute_canonical_cell_cost_decimal` in `execute_dev_cell_with_mock_transport` without passing through `float`) and `median_canonical_cost_usd_decimal: Optional[str]` on `DevGroupAggregateMetrics`.
  - Kept `canonical_cost_usd_display` / `canonical_cost_usd` and `median_canonical_cost_usd_display` / `median_canonical_cost_usd` as display-only floats that are never read by `aggregate_dev_cell_receipts` or `select_winning_candidate_dev_select`.
- **Verification Tests:** `FIX-24`, `AC-01`, `AC-02`, `AC-03`, `AC-04`.

### 3.6 `QA-30` (MAJOR) — Fix Group G & Audit Correction B: Authoritative Integer Nanoseconds Latency (`latency_ns`)

- **Root Cause:** Criterion 5 (`MEDIAN_LATENCY`) previously compared `median_latency_ms` derived from `float` `latency_ms`.
- **Exact Code Change (Correction B):**
  - Made integer nanoseconds `latency_ns: Optional[int]` on `DevCellExecutionReceipt` the sole authoritative per-cell latency field for scientific selection (`latency_ms` / `latency_ms_display` are display-only).
  - Updated `aggregate_dev_cell_receipts` to compute `median_latency_ns_decimal: Optional[str]` strictly from `r.latency_ns` via `compute_exact_decimal_median` (setting `median_latency_ns_decimal = None` if any assigned receipt lacks `latency_ns`).
  - Updated `select_winning_candidate_dev_select` Criterion 5 to compare `median_latency_ns_decimal` as exact `Decimal` values and fail closed with `LatencyAuthorityUnavailableError` if `median_latency_ns_decimal is None` for any survivor (never falling back to `latency_ms`).
- **Verification Tests:** `FIX-25`, `AC-05`, `AC-06`, `AC-07`, `AC-08`.

### 3.7 `QA-32` (MAJOR) — Fix Group H: Single-Prompt Lock Status & Pre-Live Prompt Freeze Verifier

- **Root Cause:** Single-prompt DEV-TUNE returned `SINGLE_PROMPT_P1_LOCKED_WITHOUT_COMPARISON` instead of Method Lock's `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON`, and no fail-closed verifier enforced a separate frozen prompt artifact prior to live execution.
- **Exact Code Change:**
  - Set `SINGLE_PROMPT_P1_LOCK_STATUS = "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"`.
  - Added `PromptFreezeFirewallError`, `DevPromptFreezeArtifact`, `build_dev_prompt_freeze_artifact`, `verify_prompt_candidate_freeze_artifact`, and `assert_prompt_freeze_before_live`.
- **Verification Tests:** `FIX-26`, `FIX-27`, `PC-08`, `PC-09`, `PH-04`, `PH-15`, `PH-16`.

### 3.8 `QA-33` (MAJOR) — Fix Group I, Audit Correction C, Audit Correction 02, & Audit Correction 03: Fail-Closed Persisted Provenance & Authoritative Byte-Read Code Bundle Hashing

- **Root Cause:**
  1. `DevCellExecutionManifest` and `DevCellExecutionReceipt` originally lacked `code_commit_sha` and `provider_config_sha256`, and `resolve_active_git_commit_sha` initially had a static fallback SHA (`EXPECTED_BASE_DEVELOP_SHA_FIX_01`).
  2. Audit Correction 02 introduced the three-part provenance model (`code_basis_commit_sha`, `scientific_code_bundle_sha256`, `runtime_head_sha`), but persisted models (`DevCellExecutionManifest`, `DevExecutionPlan`, `DevPromptFreezeArtifact`, `DevCellExecutionReceipt`, `StochasticityDiagnosticPlan`) still hydrated missing provenance fields from the active runtime environment during `model_validate`, `scientific_code_bundle_file_hashes` defaulted to `[]` and skipped bundle hash recomputation when empty, and `_SCIENTIFIC_CODE_BUNDLE_CACHE` cached bundle hashes by `(st_mtime_ns, st_size)`.
- **Exact Code Change (Audit Correction 03 — `BUILDERS CREATE PROVENANCE. MODELS VERIFY PROVENANCE.`):**
  1. **No Provenance Hydration on Load:**
     - Removed all calls to `resolve_active_git_commit_sha`, `compute_scientific_code_bundle_sha256`, `compute_scientific_code_bundle_file_hashes`, `compute_provider_config_sha256_for_candidate`, and `compute_provider_config_registry_sha256` from persisted model validators (`DevCellExecutionManifest`, `DevExecutionPlan`, `DevPromptFreezeArtifact`, `DevCellExecutionReceipt`, `StochasticityDiagnosticPlan`).
     - Required explicit `code_basis_commit_sha`, `code_commit_sha`, `scientific_code_bundle_sha256`, `provider_config_sha256` (on manifests/receipts), `runtime_head_sha` (on receipts), `provider_config_registry_sha256` (on prompt freeze artifacts), and `scientific_code_bundle_file_hashes` (on execution plans, prompt freeze artifacts, and stochasticity plans). Missing or mismatched fields fail closed during `model_validate`.
     - Added explicit `inspect_legacy_pre_fix_artifact` returning `LEGACY_ARTIFACT_NOT_ELIGIBLE_FOR_NEW_LIVE_EXECUTION` without fabricating provenance.
  2. **Required 13-File `scientific_code_bundle_file_hashes`:**
     - Removed `default_factory=list` from `scientific_code_bundle_file_hashes` and enforced in `ScientificCodeBundleManifest` that `scientific_code_bundle_file_hashes` is non-empty and its ordered `"path"` sequence equals `list(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS)` (exact 13-file path set) and recomputes to `scientific_code_bundle_sha256` (`fe82a932a4cb768efd0e80eeb120d773f4937dae67e1b9f2fb77ec00f516f1be`).
  3. **Authoritative Byte-Read Bundle Hashing (Zero Cache Bypass):**
     - Deleted `_SCIENTIFIC_CODE_BUNDLE_CACHE` completely so `compute_scientific_code_bundle(repo_root=..., authoritative=True)` always reads actual file bytes and computes LF-normalized SHA256, catching even same-size + restored-`st_mtime_ns` edits (`PH-20`, `PH-21`).
  4. **Historical Reload vs. Active Action-Boundary Provider Config Verification:**
     - Persisted model loading validates `provider_config_sha256` as 64-hex syntax and internal plan consistency, while `verify_cell_manifest_for_execution`, `verify_dev_execution_plan_for_execution`, `verify_prompt_candidate_freeze_artifact`, `execute_dev_cell_with_mock_transport`, `execute_dev_batch_with_mock_transport`, and `assert_batch_receipts_integrity` verify against active `compute_provider_config_sha256_for_candidate(candidate_id)`.
- **Verification Tests:** `FIX-28`, `AC-09` .. `AC-12`, `PC-01` .. `PC-15`, `PH-01` .. `PH-24`.

### 3.9 Audit Correction D — Removal of Runtime Monkeypatching in `conftest.py`

- **Root Cause:** `apps/ai-service/tests/conftest.py` in commit `a35859764b1475d33e5e0dd752557a1876e38adb` used `pytest_pycollect_makeitem` and `pytest_runtest_setup`/`pytest_runtest_teardown` to monkeypatch `dev_selection_harness` at runtime when running `test_w06_dev_selection_harness_qa_01.py`.
- **Exact Code Change (Correction D):**
  - Removed all runtime monkeypatching hooks and cached receipt loaders from `apps/ai-service/tests/conftest.py`.
  - Replaced with `pytest_collection_modifyitems` that marks items in `test_w06_dev_selection_harness_qa_01.py` with `pytest.mark.skip(reason="HISTORICAL_QA01_EVIDENCE_ONLY_CURRENT_HARNESS_REAUDITED_BY_QA02")`, leaving all 4 historical QA-01 files byte-identical.
- **Verification Tests:** `AC-13`, `AC-14`, `AC-15`.

---

## 4. Updated Failure Taxonomy Table (Method Lock + Code Bundle Integrity Outcomes)

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
| 11 | `SCIENTIFIC_CODE_BUNDLE_MISMATCH` | `SCIENTIFIC_CODE_BUNDLE_MISMATCH` | `False` | `False` | `True` | `ScientificCodeBundleIntegrityError` |

---

## 5. Provider Token & Billing Formula Table (`C1`, `C2`, `C3`)

| Candidate | Provider / Model ID | Billable Input Tokens | Billable Output Tokens | Reasoning / Thinking Token Rule | Nonzero Cache Token Rule |
|---|---|---|---|---|---|
| `C1` | `Google / gemini-3.8-flash` | `input_tokens` | `output_tokens + (thought_tokens or 0)` | Disjoint `thought_tokens` added once | `canonical_cost_usd_decimal = None` (non-comparable) |
| `C2` | `OpenAI / gpt-6.1-sol` | `input_tokens` | `output_tokens` | `reasoning_tokens` already included in `output_tokens` (never added again) | `canonical_cost_usd_decimal = None` (non-comparable) |
| `C3` | `Anthropic / claude-sonnet-5-5` | `input_tokens` | `output_tokens` | `thinking_tokens` already included in `output_tokens` (never added again) | `canonical_cost_usd_decimal = None` (non-comparable) |

---

## 6. Verification & Regression Test Matrix (`FIX-01` .. `FIX-35`, `AC-01` .. `AC-18`, `PC-01` .. `PC-18`, & `PH-01` .. `PH-24`)

| Test ID | Defect / Invariant Verified | Status |
|---|---|---|
| `FIX-01` .. `FIX-07` | `QA-14`: Strict unrescued primary parsing (`parse_primary_dev_plan_response`) | `PASS` |
| `FIX-08` .. `FIX-15` | `QA-15` & `QA-39`: `returned_model_id` integrity, batch stop, `PARTIAL_TIMEOUT`, `HARNESS_INTERNAL_ERROR` | `PASS` |
| `FIX-16` .. `FIX-19` | `QA-05`: Content-addressed Final-100 firewall & cross-partition label rejection | `PASS` |
| `FIX-20` .. `FIX-23` | `QA-27` & `QA-28`: Provider-aware token billing (`C1`, `C2`, `C3`) & cache guard | `PASS` |
| `FIX-24` & `AC-01` .. `AC-04` | `QA-29` / Correction A: Exact `Decimal` cost end-to-end (`canonical_cost_usd_decimal`, `median_canonical_cost_usd_decimal`) | `PASS` |
| `FIX-25` & `AC-05` .. `AC-08` | `QA-30` / Correction B: Authoritative integer `latency_ns` & exact `Decimal` median (`median_latency_ns_decimal`) | `PASS` |
| `FIX-26` .. `FIX-27`, `PC-08` .. `PC-09`, `PH-04`, `PH-15` .. `PH-16` | `QA-32` / Correction 02 / Correction 03: `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON`, artifact-lifecycle-safe prompt freeze verifier, & required 13-file `scientific_code_bundle_file_hashes` | `PASS` |
| `FIX-28`, `AC-09` .. `AC-12`, `PC-01` .. `PC-15`, & `PH-01` .. `PH-21` | `QA-33` / Correction C / Correction 02 / Correction 03: Fail-closed persisted provenance (no hydration on load), required 13-file `scientific_code_bundle_file_hashes`, authoritative byte-read bundle hash (same-size + same-mtime cache bypass closed), and action-boundary `provider_config_sha256` verification | `PASS` |
| `AC-13` .. `AC-15` | Correction D: No runtime monkeypatching in `conftest.py` & QA-01 files byte-identical | `PASS` |
| `FIX-29` .. `FIX-35`, `AC-16` .. `AC-18`, `PC-16` .. `PC-18`, & `PH-22` .. `PH-24` | All preserved scientific contracts, `DH-01`..`DH-35`, `FIX-01`..`FIX-35`, `AC-01`..`AC-18`, `PC-01`..`PC-18`, `PH-01`..`PH-24`, and 0 live calls | `PASS` |
