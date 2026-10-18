# W06 DEV Live Runner Architecture & Scientific Execution Contract (`v1.0.0`)

- **Task ID**: `W06-DEV-LIVE-RUNNER-01-OFFLINE`
- **Receipt Artifact**: `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json` (`W06-DEV-LIVE-RUNNER-01-RECEIPT-V1`)
- **Production Module**: `apps/ai-service/app/evaluation/dev_live_runner.py`
- **Test Suite**: `apps/ai-service/tests/test_w06_dev_live_runner_01.py`
- **Base `develop` SHA**: `b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50`
- **Live Execution Status**: `LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0.0`, `LIVE_AUTHORIZATION_PRESENT = false`, `PROMPT_FREEZE_STATUS = NOT_YET_FROZEN`
- **Next Gate**: `W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL`

---

## 1. Runner Architecture & Separation of Concerns

`apps/ai-service/app/evaluation/dev_live_runner.py` is the dedicated production live-execution component for the frozen W06 DEV-TUNE, DEV-SELECT, and post-winner STOCHASTICITY scientific phases.

1. **Isolated from Historical Preflight Scripts**: Historical scripts (`live_smoke.py`, `live_revalidation_v2.py`) remain immutable Phase-01B/01C/01D preflight evidence and are not overloaded for DEV execution.
2. **Included in Scientific Code Bundle**: `apps/ai-service/app/evaluation/dev_live_runner.py` is registered in `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` (14 total files), ensuring any change to request construction, usage normalization, transport journaling, or runner orchestration alters `scientific_code_bundle_sha256` and invalidates stale pre-frozen execution plans.
3. **Offline by Default**: Running `dev_live_runner.py` without `--execute-live` and a verified phase-scoped authorization artifact operates strictly in offline/dry-run mode with zero provider network calls.

---

## 2. Explicit Live Authorization Gate (`DevLiveAuthorizationArtifact`)

Live provider execution requires **two** independent conditions simultaneously:
1. Explicit CLI/runtime action flag (`execute_live=True` / `--execute-live`).
2. A disk-persisted, cryptographically verified `DevLiveAuthorizationArtifact` (`verify_dev_live_authorization_artifact()`).

The authorization contract validates:
- `authorized_by == "PROJECT_OWNER"` and `authorization_status == "AUTHORIZED"`.
- `phase` in `{"DEV_TUNE", "DEV_SELECT", "STOCHASTICITY"}` (`FINAL100` is unconditionally rejected).
- Exact binding to `execution_plan_sha256`, `prompt_freeze_sha256`, `scientific_code_bundle_sha256`, `provider_config_registry_sha256`, `candidate_registry_sha256`, and `code_commit_sha`.
- Exact candidate list: `["C1", "C2", "C3"]` for `DEV_TUNE` and `DEV_SELECT`; `[winner_candidate_id]` for `STOCHASTICITY`.
- Exact call-budget match:
  - `DEV_TUNE`: `60` calls (1 prompt) or `120` calls (2 prompts).
  - `DEV_SELECT`: `180` calls (1 frozen prompt × 3 candidates × 60 fixtures).
  - `STOCHASTICITY`: `15` calls (`1` winner × `5` frozen diagnostic fixtures × `3` repeats, requiring a verified `DEV_SELECT` winner receipt).
- Zero secret fields or secret token patterns inside the authorization JSON (`assert_no_secrets_in_payload`).

---

## 3. Two-Stage Plan-Before-Live Protocol

The runner enforces a strict two-stage separation between experimental planning and live execution:

1. **Stage A (Freeze Before Live)**:
   - Freeze `DevExecutionPlan` (`execution_plan.json`), `DevPromptFreezeArtifact` (`prompt_freeze.json`), `DevLiveAuthorizationArtifact` (`live_authorization.json`), candidate registry, provider config hashes, and per-cell `DevCellExecutionManifest` instances on disk before any live call.
2. **Stage B (Execute Frozen Plan)**:
   - `execute_live_dev_batch()` verifies that `plan_artifact_path`, `prompt_freeze_artifact_path`, and `authorization_artifact_path` exist on disk and match the in-memory objects byte-for-byte (`PlanBeforeLiveProtocolError` on mismatch or missing Stage A artifacts).
   - Combined create-plan-and-execute invocations (`create_plan_in_same_step=True`) are rejected fail-closed.
   - Any cell whose `(run_id, candidate_id, prompt_id, scenario_id, repeat_index)` is not a member of the frozen `DevExecutionPlan` is rejected before transport.

---

## 4. Immutable Per-Cell Artifact Layout & Raw-Evidence-First Ordering

Each cell writes immutable artifacts to `<batch_output_dir>/cells/<run_id>/` via atomic temp-file + `os.fsync` + `os.replace` (`write_immutable_atomic_bytes`), failing closed with `ImmutableCellExecutionError` if any target file already exists:

1. **Before Transport**:
   - `request_manifest.json` (`BenchmarkRunManifest` + frozen wire request metadata and `wire_request_sha256`).
   - `transport_journal_starting.json` (`status = "TRANSPORT_STARTING"`).
2. **Immediately After Transport Returns (Before Any Validation/Parsing/Evaluation)**:
   - `transport_journal_completed.json` (`status = "TRANSPORT_COMPLETED"`, separate append-only file; never overwrites `transport_journal_starting.json`).
   - `raw_provider_response.txt` (exact UTF-8 raw text returned by provider, even when empty, truncated, or malformed).
   - `raw_usage_metadata.json` (raw provider usage payload + normalized token summary).
   - `provider_response_metadata.json` (returned `model_id`, `finish_reason`, `latency_ns`, `latency_ms`, `transport_status`, sanitized error detail).
3. **After Deterministic Parsing & Evaluation**:
   - `parsed_plan_response.json` (written only when strict primary parsing succeeds).
   - `evaluation_result.json` (`ScenarioEvaluationResult` from `evaluate_dev_cell_scenario` or non-success denominator record).
   - `execution_receipt.json` (`DevCellExecutionReceipt` binding all artifact SHA-256 digests).

---

## 5. Transport-Start Journal & Crash Ambiguity Semantics

To eliminate silent double-billing or unrecorded crash retries:
- `inspect_and_guard_cell_directory_before_transport()` inspects `<cell_dir>` prior to every cell execution.
- If `transport_journal_starting.json` exists without `transport_journal_completed.json` or `execution_receipt.json`, the runner records `transport_journal_unknown_after_transport.json` with `attempt_status = "ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT"` and raises `CrashAmbiguityBatchStopError`, stopping the batch immediately without re-invoking the provider.
- If `execution_receipt.json` or `transport_journal_completed.json` already exists, the runner raises `ImmutableCellExecutionError` (`CELL_ALREADY_EXECUTED_IMMUTABLE`).

---

## 6. Call-Budget Ledger (`DevCallBudgetLedger`)

`DevCallBudgetLedger` tracks every cell reservation and transport consumption:
- Enforces phase call caps (`60`, `120`, `180`, or `15`), candidate whitelist, and scenario fixture whitelist.
- Rejects duplicate `run_id` or duplicate `(phase, candidate_id, prompt_id, scenario_id, repeat_index)` with `DuplicateDevCellAttemptError`.
- Reserves `1` call prior to transport (`reserve_before_transport`) and permanently consumes `1` call once transport starts (`mark_transport_consumed`).
- **No Failed-Call Refund**: Transport errors, timeouts, malformed JSON, and schema rejections still consume the call budget (`refund_call` is forbidden).

---

## 7. Frozen Provider Request Mapping

`build_frozen_provider_wire_request()` constructs deterministic wire payloads for the 3 locked candidates:

| Candidate | Provider | Model ID | API Surface | Frozen Config | Schema Surface |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `C1` | `google` | `gemini-3.8-flash` | `google_genai_generate_content_v1` | `thinking_level=medium`, `include_thoughts=False`, `seed=2026101508`, `max_output_tokens=16384`, `timeout_ms=55000`, `omitted=["temperature","top_p","top_k"]` | `response_mime_type="application/json"`, Portable Schema V2 |
| `C2` | `openai` | `gpt-6.1-sol` | `openai_chat_completions_v1` | `reasoning_effort=medium`, `service_tier=default`, `seed=2026101508`, `max_completion_tokens=16384`, `timeout_ms=55000`, `omitted=["temperature","top_p","top_k","top_logprobs","logprobs"]` | `response_format.type="json_schema"`, `strict=True`, Portable Schema V2 |
| `C3` | `anthropic` | `claude-sonnet-5-5` | `anthropic_messages_create_v1` | `thinking.type=adaptive`, `output_config.effort=high`, `max_tokens=16384`, `timeout_ms=55000`, `omitted=["seed","temperature","top_p","top_k"]` | `output_config.format.type="json_schema"`, Portable Schema V2 |

All three candidates receive identical RECA grounding context (`build_deterministic_dev_scenario_context`), identical shared system prompt (`PREFLIGHT_SHARED_SYSTEM_PROMPT`), and identical frozen user prompt template (`prompt_spec.template_text`), with zero tools, zero retries, and zero fallback models.

---

## 8. Usage Metadata Normalization & Exact Decimal Costing

`normalize_candidate_usage_metadata()` maps provider-native usage fields into `BenchmarkUsageMetadata` while preserving `raw_usage_metadata.json`:
- **C1 (`google`)**: `prompt_token_count -> input_tokens`, `candidates_token_count -> output_tokens`, `total_token_count -> total_tokens`, `thoughts_token_count -> thought_tokens`, `cached_content_token_count -> cached_input_tokens`.
- **C2 (`openai`)**: `input_tokens`, `output_tokens`, `total_tokens`, `output_tokens_details.reasoning_tokens -> reasoning_tokens`, `input_tokens_details.cached_tokens -> cached_input_tokens`.
- **C3 (`anthropic`)**: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `thinking_tokens`.
- Canonical cell cost is computed via `compute_canonical_cell_cost_decimal()` from `dev_selection_harness.py` (exact `Decimal` arithmetic including C1 `thought_tokens` at output rate and C3 `thinking_tokens` when not already bundled in `output_tokens`).

---

## 9. Failure Taxonomy, No-Retry Rule, and Batch-Fatal Rule

- **Zero Retries**: SDK retries, HTTP transport retries, and manual cell retries are strictly `0`.
- **Scenario-Level Scored Zero Outcomes** (`final_Planning_Score = 0.0`, retained in denominator $N=20$ or $N=60$, batch continues):
  - `PROVIDER_TIMEOUT`
  - `PROVIDER_TRANSPORT_ERROR`
  - `EMPTY_OR_TRUNCATED_OUTPUT`
  - `INVALID_JSON_OUTPUT`
  - `SCHEMA_VALIDATION_ERROR`
- **Batch-Fatal Integrity Stops** (raw evidence persisted first, then batch halts immediately via `ModelIntegrityBatchStopError`, `HarnessInternalBatchStopError`, or `CrashAmbiguityBatchStopError`):
  - `MODEL_ID_MISMATCH` (incompatible returned model ID or snapshot)
  - `CONFIGURATION_INTEGRITY_ERROR`
  - `HARNESS_INTERNAL_ERROR`
  - `ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT` (crash ambiguity)

---

## 10. Secret Sanitization & Final-100 Firewall

- **Secret Hygiene**: `sanitize_runner_text()`, `sanitize_runner_structure()`, and `assert_no_secrets_in_payload()` redact and block `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AIza...`, `sk-ant-...`, `sk-proj-...`, `sk-...`, and `Bearer ...` patterns across all artifacts, receipts, and error messages. Offline tests and dry-runs never read `.env` or environment API keys.
- **Final-100 Firewall**: Every scenario, scenario ID, file path, and authorization phase is checked against `assert_not_final100_path()`, `assert_not_final100_scenario_id()`, and `assert_not_final100_scenario()`, raising `Final100FirewallViolationError` on any Final-100 contact.
