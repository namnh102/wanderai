# W06 DEV Live Runner Architecture & Scientific Execution Contract (`v1.2.0`)

- **Task ID**: `W06-DEV-LIVE-RUNNER-01-OFFLINE` / `W06-DEV-LIVE-RUNNER-01-AUDIT-CORRECTION-01` / `W06-DEV-LIVE-RUNNER-01-AUDIT-CORRECTION-02`
- **Receipt Artifact**: `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json` (`W06-DEV-LIVE-RUNNER-01-RECEIPT-V1`, `sha256: 84aa2b2a541c49dde712b7f604ee0a824113fa0b396dc0e45b343db0159c55e4`)
- **Production Module**: `apps/ai-service/app/evaluation/dev_live_runner.py` (`sha256: 9f3441c2ca290e9a33b4daa78eaaa58063978364d8375145fc7483b04ed8b817`)
- **Scientific Code Bundle (14 files)**: `scientific_code_bundle_sha256 = 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`
- **Test Suite**: `apps/ai-service/tests/test_w06_dev_live_runner_01.py` (`LR-01..LR-50` + `LRC-01..LRC-30` + `LRC2-01..LRC2-19`, 99 tests total)
- **Base `develop` SHA**: `b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50`
- **Live Execution Status**: `LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0.0`, `LIVE_AUTHORIZATION_PRESENT = false`, `PROMPT_FREEZE_STATUS = NOT_YET_FROZEN`, `DEV_MODEL_EXECUTION_ALLOWED = false`
- **Next Gate**: `W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL`

---

## 1. Runner Architecture & Separation of Concerns

`apps/ai-service/app/evaluation/dev_live_runner.py` is the dedicated production live-execution component for the frozen W06 DEV-TUNE, DEV-SELECT, and post-winner STOCHASTICITY scientific phases.

1. **Isolated from Historical Preflight Scripts**: Historical scripts (`live_smoke.py`, `live_revalidation_v2.py`) remain immutable Phase-01B/01C/01D preflight evidence and are not overloaded for DEV execution.
2. **Historical QA-02 Restored & Preserved**: Historical QA-02 files (`apps/ai-service/tests/test_w06_dev_selection_harness_qa_02.py`, `scripts/audit_w06_dev_selection_harness_qa_02.py`, `data/evaluation/w06/w06_dev_selection_harness_qa_02_receipt_v1.json`, `docs/research/w06_dev_selection_harness_qa_02.md`) are preserved byte-for-byte identical to `develop` (`b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50`), with `test_w06_dev_selection_harness_qa_02.py` marked `HISTORICAL_EVIDENCE_ONLY` in `apps/ai-service/tests/conftest.py` alongside `test_w06_dev_selection_harness_qa_01.py`.
3. **Included in Scientific Code Bundle**: `apps/ai-service/app/evaluation/dev_live_runner.py` is registered in `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` (14 total files), ensuring any change to production provider transports, HTTP call counting, request construction, usage normalization, transport journaling, or runner orchestration alters `scientific_code_bundle_sha256` (`0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`) and invalidates stale pre-frozen execution plans.
4. **Offline by Default**: Running `dev_live_runner.py` without `--execute-live` and a verified phase-scoped authorization artifact operates strictly in offline/dry-run mode with zero provider network calls.

---

## 2. Production Provider Transports & HTTP-Boundary Request Counting

`dev_live_runner.py` contains the actual production provider transport implementations inside the 14-file scientific code bundle:

- **C1 (`GoogleGeminiProductionTransport` / `_invoke_c1_google_production`)**:
  - Uses `google.genai.Client` with `HttpOptions(timeout=55000, httpx_client=...)`, `ThinkingConfig(thinking_level=ThinkingLevel.MEDIUM, include_thoughts=False)`, `seed=2026101508`, `max_output_tokens=16384`, `response_mime_type="application/json"`, `response_json_schema=PortablePlannerAiPlanResponseV2.model_json_schema()`.
  - `temperature`, `top_p`, and `top_k` are strictly omitted (`None`) on `GenerateContentConfig`.
- **C2 (`OpenAIChatCompletionsProductionTransport` / `_invoke_c2_openai_production`)**:
  - Uses `openai.OpenAI(timeout=55.0, max_retries=0, http_client=...)` and `client.chat.completions.create(...)` with `model="gpt-6.1-sol"`, `reasoning_effort="medium"`, `seed=2026101508`, `service_tier="default"`, `max_completion_tokens=16384`, `response_format={"type": "json_schema", "json_schema": {"name": "BenchmarkPlanResponse", "strict": True, "schema": ...}}`.
  - `temperature`, `top_p`, `top_k`, `logprobs`, and `top_logprobs` are strictly omitted from SDK kwargs.
- **C3 (`AnthropicMessagesProductionTransport` / `_invoke_c3_anthropic_production`)**:
  - Uses `anthropic.Anthropic(timeout=55.0, max_retries=0, http_client=...)` and `client.messages.create(...)` with `model="claude-sonnet-5-5"`, `max_tokens=16384`, `thinking={"type": "adaptive"}`, `output_config={"effort": "high", "format": {"type": "json_schema", "schema": ...}}`.
  - `seed`, `temperature`, `top_p`, and `top_k` are strictly omitted from SDK kwargs.
- **HTTP-Boundary Single-Request Enforcement (`DevCellHttpCallCounter`, `DevCountingHttpxTransport`, `DevCountingHttpx2Transport`)**:
  - Every cell invocation attaches a fresh `DevCellHttpCallCounter(max_requests=1)` at the HTTP client boundary.
  - Any second outbound HTTP request within a single cell raises `SingleCellHttpCallLimitExceededError` (`retry = 0` enforced at the transport boundary).
- **Deterministic Provider Exception Classification (`classify_provider_transport_exception`)**:
  - Maps HTTP `429` (`HTTP_429`), HTTP `5xx` (`HTTP_5XX`), timeouts (`TIMEOUT`), authentication errors (`AUTHENTICATION_FAILURE`), model access errors (`MODEL_ACCESS_FAILURE`), provider refusals (`REFUSAL`), and max-token truncations (`MAX_TOKEN_TRUNCATION`) into structured `DevCellFailureClassification` outcomes rather than misclassifying ordinary provider runtime errors as `HARNESS_INTERNAL_ERROR`.

---

## 3. Explicit Live Authorization Gate, Action-Boundary Re-Attestation & Orchestration Guard

Live provider execution cannot be triggered by an arbitrary Python caller or by passing an ad-hoc lambda/mock transport:

1. **No Implicit Defaults in `build_dev_live_authorization_artifact()`**:
   - `authorized_by_role`, `authorization_status`, and `authorized_at_utc` are mandatory explicit arguments with no default values. Only `authorized_by_role == "PROJECT_OWNER"` and `authorization_status == "AUTHORIZED"` are accepted.
   - Offline unit tests use `build_test_only_authorization_artifact()`.
2. **`LiveExecutionCapability` as a Fail-Closed Orchestration Guard (`FAIL_CLOSED_ORCHESTRATION_GUARD`)**:
   - Minted by `issue_live_execution_capability(execute_live=True, ...)` using a module-private guard token (`_CAPABILITY_MINT_GUARD`). Direct construction raises `LiveExecutionNotAuthorizedError`.
   - `LiveExecutionCapability` is a fail-closed orchestration guard, NOT a substitute for action-boundary Stage-A and git verification.
3. **Action-Boundary Stage-A Re-Attestation (`reattest_stage_a_at_live_action_boundary` & `LiveExecutionContext`)**:
   - Both `execute_live_dev_cell(..., execution_mode="LIVE_EXECUTION")` and `execute_live_dev_batch(..., execution_mode="LIVE_EXECUTION")` re-attest the live execution context against current runtime state immediately before any budget reservation or outbound transport call:
     - Current active git `HEAD` (`runtime_head_sha`) matches `live_capability.runtime_head_sha`.
     - `stage_a_commit_sha` is an ancestor of `runtime_head_sha`.
     - Stage-A artifacts (`execution_plan.json`, `prompt_freeze.json`, `live_authorization.json`, `stage_a_freeze_receipt.json`) and all 14 scientific code bundle files exist on disk, are tracked and clean in `git status --porcelain`, and match their committed git blob SHA-1s (`git hash-object` vs `git rev-parse <commit>:<path>`).
     - `scientific_code_bundle_sha256`, `provider_config_registry_sha256`, `execution_plan.plan_sha256`, `prompt_freeze_sha256`, `authorization_artifact_sha256`, and `stage_a_receipt_sha256` match the capability and on-disk Stage-A artifacts.
   - `execute_live_dev_batch` locks a verified `LiveExecutionContext` before the first cell and re-verifies every cell against that locked context so any mid-batch repo or config drift fails closed before transport.
4. **Strict Execution Mode & Transport Type Safety**:
   - `execute_live_dev_cell()` and `execute_live_dev_batch()` require explicit `execution_mode in {"LIVE_EXECUTION", "OFFLINE_MOCK_TEST"}`.
   - When `execution_mode == "LIVE_EXECUTION"`, `transport` must be an instance of `ProductionDevProviderTransport`. Passing `MockDevProviderTransport` or any arbitrary callable raises `LiveExecutionNotAuthorizedError`.
   - When `execution_mode == "OFFLINE_MOCK_TEST"`, `live_capability` must be `None` and passing `ProductionDevProviderTransport` raises `LiveExecutionNotAuthorizedError`.

---

## 4. Two-Stage Plan-Before-Live Protocol, Required Process Token & Git Attestation

The runner enforces a strict two-stage separation between Stage A (offline freeze) and Stage B (batch/cell execution) via `DevLiveStageAFreezeReceipt`:

1. **Stage A (`build_stage_a_freeze_receipt`)**:
   - `DevLiveStageAFreezeReceipt.stage_a_process_token` is a required, non-empty string (`min_length=1`); missing, `null`, empty, or whitespace-only tokens are rejected (`STAGE_A_PROCESS_TOKEN_MISSING`, `STAGE_A_PROCESS_TOKEN_NULL`, `STAGE_A_PROCESS_TOKEN_EMPTY`).
   - Production `build_stage_a_freeze_receipt(...)` automatically stamps `stage_a_process_token = _CURRENT_PROCESS_INVOCATION_TOKEN` internally and does NOT expose a caller-controlled `stage_a_process_token` parameter.
   - Offline tests that require synthetic historical process tokens must explicitly call `build_test_only_stage_a_freeze_receipt(...)`.
2. **Stage B (`verify_stage_a_freeze_receipt` & `reattest_stage_a_at_live_action_boundary`)**:
   - Rejects same-process Stage A -> Stage B execution whenever `receipt.stage_a_process_token == _CURRENT_PROCESS_INVOCATION_TOKEN` (`STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN`).
   - For `execution_mode == "LIVE_EXECUTION"`, verifies via `git merge-base --is-ancestor`, `git status --porcelain`, and `git rev-parse <commit>:<path>` that `stage_a_commit_sha` is an ancestor of `runtime_head_sha` and all Stage A artifacts plus all 14 scientific code bundle blobs are committed and clean in git history.

---

## 5. Immutable Per-Cell Artifact Layout, Authoritative Execution Timestamps & Raw-Evidence-First Ordering

Each cell writes immutable artifacts to `<batch_output_dir>/cells/<run_id>/` via atomic temp-file + `os.fsync` + `os.replace` (`write_immutable_atomic_bytes`), failing closed with `ImmutableCellExecutionError` if any target file already exists:

1. **Single Authoritative Execution-Start Timestamp (`execution_started_at_utc`)**:
   - At the action boundary immediately before `transport_journal_starting.json`, `execute_live_dev_cell` captures `execution_started_at_utc = str(utc_now_clock()).strip()` ONCE (defaulting to `datetime.now(timezone.utc).isoformat()`, or an injected deterministic clock in offline tests). No hardcoded timestamp constant is ever used.
   - The exact same `execution_started_at_utc` value is recorded in `transport_journal_starting.json` (`execution_started_at_utc` and `timestamp_utc`), `request_manifest.json` (`execution_started_at_utc`), `run_manifest.json` (`BenchmarkRunManifest.execution_timestamp_utc`), and `provider_response_metadata.json` (`execution_started_at_utc`).
2. **Before Transport**:
   - `request_manifest.json` (frozen wire request metadata, `execution_started_at_utc`, and `provider_wire_request`).
   - `transport_journal_starting.json` (`status = "TRANSPORT_STARTING"`, `execution_started_at_utc`, `timestamp_utc`).
3. **Immediately After Transport Returns (Before Any Validation/Parsing/Evaluation)**:
   - Captures `transport_completed_at_utc = str(utc_now_clock()).strip()` separately from `execution_started_at_utc`.
   - `transport_journal_completed.json` (`status = "TRANSPORT_COMPLETED"`, `execution_started_at_utc`, `transport_completed_at_utc`, `timestamp_utc = transport_completed_at_utc`; never overwrites `transport_journal_starting.json`).
   - `raw_provider_response.txt` (exact UTF-8 raw text returned by provider, even when empty, truncated, or malformed).
   - `raw_usage_metadata.json` (raw provider usage payload + normalized token summary).
   - `provider_response_metadata.json` (returned `model_id`, `finish_reason`, `latency_ns`, `latency_ms`, `actual_http_request_count`, `execution_started_at_utc`, `transport_completed_at_utc`, `generation_parameters` with `temperature_status = "OMITTED"`).
4. **After Deterministic Parsing & Evaluation**:
   - `parsed_plan_response.json` (written only when strict primary parsing succeeds).
   - `run_manifest.json` (`BenchmarkRunManifest` with `execution_timestamp_utc = execution_started_at_utc`, `execution_mode`, and `code_commit_sha = runtime_head_sha`).
   - `evaluation_result.json` (`ScenarioEvaluationResult` from `evaluate_dev_cell_scenario`).
   - `execution_receipt.json` (`DevCellExecutionReceipt` binding all artifact SHA-256 digests).

---

## 6. Transport-Start Journal, Call-Budget Ledger, Failure Taxonomy & Firewalls

- **Crash Ambiguity Stop**: If `transport_journal_starting.json` exists without `transport_journal_completed.json` or `execution_receipt.json`, the runner writes `transport_journal_unknown_after_transport.json` (`ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT`) and raises `CrashAmbiguityBatchStopError`.
- **Call-Budget Ledger (`DevCallBudgetLedger`)**: Enforces phase call caps (`60`, `120`, `180`, `15`), candidate whitelist, and scenario fixture whitelist; reserves before transport (only after action-boundary Stage-A re-attestation passes) and permanently consumes on transport start with no failed-call refunds.
- **Failure Taxonomy**:
  - Ordinary denominator-0.0 scenario failures (batch continues): `TIMEOUT`, `PARTIAL_TIMEOUT`, `HTTP_429`, `HTTP_5XX`, `MALFORMED_PROVIDER_PAYLOAD`, `REFUSAL`, `EMPTY_RESPONSE`, `MAX_TOKEN_TRUNCATION`, `INVALID_JSON`, `SCHEMA_VALIDATION_FAILURE`.
  - Batch-fatal integrity stops (raw evidence persisted first, then batch halts): `MODEL_INTEGRITY_MISMATCH`, `AUTHENTICATION_FAILURE`, `MODEL_ACCESS_FAILURE`, `BILLING_QUOTA_EXHAUSTION`, `HARNESS_INTERNAL_ERROR` (`SINGLE_CELL_HTTP_CALL_LIMIT_EXCEEDED`, runner bug), `ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT`.
- **Secret Hygiene & Final-100 Firewall**: Redacts and blocks secret patterns (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AIza...`, `sk-ant-...`, `sk-proj-...`, `sk-...`, `Bearer ...`) across all artifacts and blocks any `final100` path, scenario ID, or phase (`Final100FirewallViolationError`).
