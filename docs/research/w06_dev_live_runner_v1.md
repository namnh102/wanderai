# W06 DEV Live Runner Architecture & Scientific Execution Contract (`v1.1.0`)

- **Task ID**: `W06-DEV-LIVE-RUNNER-01-OFFLINE` / `W06-DEV-LIVE-RUNNER-01-AUDIT-CORRECTION-01`
- **Receipt Artifact**: `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json` (`W06-DEV-LIVE-RUNNER-01-RECEIPT-V1`)
- **Production Module**: `apps/ai-service/app/evaluation/dev_live_runner.py` (`sha256: 6f7aeaa3dea243be6e8d0969a372777aa75d4d4894e7b1b8fa010d69f4bb6a8c`)
- **Scientific Code Bundle (14 files)**: `scientific_code_bundle_sha256 = f8e10a0c98e234d9eaa42b93bbb0eee11842c403b25a9d97debac1df93d80f27`
- **Test Suite**: `apps/ai-service/tests/test_w06_dev_live_runner_01.py` (`LR-01..LR-50` + `LRC-01..LRC-30`, 80 tests total)
- **Base `develop` SHA**: `b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50`
- **Live Execution Status**: `LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0.0`, `LIVE_AUTHORIZATION_PRESENT = false`, `PROMPT_FREEZE_STATUS = NOT_YET_FROZEN`, `DEV_MODEL_EXECUTION_ALLOWED = false`
- **Next Gate**: `W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL`

---

## 1. Runner Architecture & Separation of Concerns

`apps/ai-service/app/evaluation/dev_live_runner.py` is the dedicated production live-execution component for the frozen W06 DEV-TUNE, DEV-SELECT, and post-winner STOCHASTICITY scientific phases.

1. **Isolated from Historical Preflight Scripts**: Historical scripts (`live_smoke.py`, `live_revalidation_v2.py`) remain immutable Phase-01B/01C/01D preflight evidence and are not overloaded for DEV execution.
2. **Historical QA-02 Restored & Preserved**: Historical QA-02 files (`apps/ai-service/tests/test_w06_dev_selection_harness_qa_02.py`, `scripts/audit_w06_dev_selection_harness_qa_02.py`, `data/evaluation/w06/w06_dev_selection_harness_qa_02_receipt_v1.json`, `docs/research/w06_dev_selection_harness_qa_02.md`) are preserved byte-for-byte identical to `develop` (`b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50`), with `test_w06_dev_selection_harness_qa_02.py` marked `HISTORICAL_EVIDENCE_ONLY` in `apps/ai-service/tests/conftest.py` alongside `test_w06_dev_selection_harness_qa_01.py`.
3. **Included in Scientific Code Bundle**: `apps/ai-service/app/evaluation/dev_live_runner.py` is registered in `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` (14 total files), ensuring any change to production provider transports, HTTP call counting, request construction, usage normalization, transport journaling, or runner orchestration alters `scientific_code_bundle_sha256` (`f8e10a0c98e234d9eaa42b93bbb0eee11842c403b25a9d97debac1df93d80f27`) and invalidates stale pre-frozen execution plans.
4. **Offline by Default**: Running `dev_live_runner.py` without `--execute-live` and a verified phase-scoped authorization artifact operates strictly in offline/dry-run mode with zero provider network calls.

---

## 2. Production Provider Transports & HTTP-Boundary Request Counting

`dev_live_runner.py` contains the actual production provider transport implementations inside the 14-file scientific code bundle:

- **C1 (`GoogleGeminiProductionTransport` / `_invoke_c1_google_production`)**:
  - Uses `google.genai.Client` with `HttpOptions(timeout=55000, httpx_client=...)`, `ThinkingConfig(thinking_level=ThinkingLevel.MEDIUM, include_thoughts=False)`, `seed=2026101508`, `max_output_tokens=16384`, `response_mime_type="application/json"`, `response_json_schema=PortablePlannerAiPlanResponseV2.model_json_schema()`.
  - `temperature`, `top_p`, and `top_k` are strictly omitted (`None`) on `GenerateContentConfig`.
- **C2 (`OpenAIChatCompletionsProductionTransport` / `_invoke_c2_openai_production`)**:
  - Uses `openai.OpenAI(timeout=55.0, max_retries=0, http_client=...)` and `client.chat.completions.create(...)` with `model="gpt-6.1-sol"`, `reasoning_effort="medium"`, `seed=2026101508`, `service_tier="default"`, `max_completion_tokens=16384`, `response_format={"type": "json_schema", "json_schema": {"name": "PlannerAiPlanResponseV2", "strict": True, "schema": ...}}`.
  - `temperature`, `top_p`, `top_k`, `logprobs`, and `top_logprobs` are strictly omitted from SDK kwargs.
- **C3 (`AnthropicMessagesProductionTransport` / `_invoke_c3_anthropic_production`)**:
  - Uses `anthropic.Anthropic(timeout=55.0, max_retries=0, http_client=...)` and `client.messages.create(...)` with `model="claude-sonnet-5-5"`, `max_tokens=16384`, `thinking={"type": "adaptive"}`, `output_config={"effort": "high", "format": {"type": "json_schema", "schema": ...}}`.
  - `seed`, `temperature`, `top_p`, and `top_k` are strictly omitted from SDK kwargs.
- **HTTP-Boundary Single-Request Enforcement (`DevCellHttpCallCounter`, `DevCountingHttpxTransport`, `DevCountingHttpx2Transport`)**:
  - Every cell invocation attaches a fresh `DevCellHttpCallCounter(max_requests=1)` at the HTTP client boundary.
  - Any second outbound HTTP request within a single cell raises `SingleCellHttpCallLimitExceededError` (`retry = 0` enforced at the transport boundary).
- **Deterministic Provider Exception Classification (`classify_provider_transport_exception`)**:
  - Maps HTTP `429` (`HTTP_429`), HTTP `5xx` (`HTTP_5XX`), timeouts (`TIMEOUT`), authentication errors (`AUTHENTICATION_FAILURE`), model access errors (`MODEL_ACCESS_FAILURE`), provider refusals (`REFUSAL`), and max-token truncations (`MAX_TOKEN_TRUNCATION`) into structured `DevTransportPayload` outcomes rather than misclassifying ordinary provider runtime errors as `HARNESS_INTERNAL_ERROR`.

---

## 3. Explicit Live Authorization Gate & Programmatic Capability Enforcement

Live provider execution cannot be triggered by an arbitrary Python caller or by passing an ad-hoc lambda/mock transport:

1. **No Implicit Defaults in `build_dev_live_authorization_artifact()`**:
   - `authorized_by`, `authorization_status`, and `authorization_reason` are mandatory explicit arguments with no default values. Only `authorized_by == "PROJECT_OWNER"` and `authorization_status == "AUTHORIZED"` are accepted.
   - Offline unit tests use `build_test_only_authorization_artifact()`, which embeds `[OFFLINE_TEST_ONLY]` in `authorization_reason` and is rejected by `issue_live_execution_capability()`.
2. **Unforgeable `LiveExecutionCapability`**:
   - Minted exclusively by `issue_live_execution_capability(execute_live=True, authorization_artifact=..., ...)` using a module-private token (`_LIVE_CAPABILITY_MINT_TOKEN`). Direct construction raises `LiveExecutionUnauthorizedError`.
3. **Strict Execution Mode & Transport Type Safety**:
   - `execute_single_dev_cell()` and `execute_live_dev_batch()` require explicit `execution_mode in {"LIVE_EXECUTION", "OFFLINE_MOCK_TEST"}`.
   - When `execution_mode == "LIVE_EXECUTION"`:
     - `execute_live` must be `True`.
     - A valid `LiveExecutionCapability` bound to the plan and authorization SHA-256 must be supplied.
     - `transport_fn` must be an instance of `ProductionDevProviderTransport` (built via `create_live_provider_transport_factory(capability=...)`). Passing `MockOfflineDevProviderTransport` or any arbitrary callable raises `LiveExecutionUnauthorizedError`.
   - When `execution_mode == "OFFLINE_MOCK_TEST"`:
     - `execute_live` must be `False` and `live_capability` must be `None`.
     - Passing `ProductionDevProviderTransport` raises `LiveExecutionUnauthorizedError`.

---

## 4. Two-Stage Plan-Before-Live Protocol & Git Commit/Blob Attestation

The runner enforces a strict two-stage separation between Stage A (offline freeze) and Stage B (batch execution) via `DevLiveStageAFreezeReceipt`:

1. **Stage A (`build_stage_a_freeze_receipt`)**:
   - Persists `execution_plan.json`, `prompt_freeze.json`, `live_authorization.json`, and `stage_a_freeze_receipt.json` (`DevLiveStageAFreezeReceipt`).
   - Records `stage_a_process_token`, `frozen_at_commit_sha`, and git object blob SHA-1 digests (`git hash-object`) for the frozen Stage A artifacts and all 14 files in `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS`.
2. **Stage B (`verify_stage_a_freeze_receipt` inside `execute_live_dev_batch`)**:
   - Requires `stage_a_freeze_receipt_path` on disk and verifies its SHA-256, artifact digests, and `scientific_code_bundle_sha256`.
   - Rejects same-process Stage A + Stage B execution when `current_process_token == receipt.stage_a_process_token`.
   - For `execution_mode == "LIVE_EXECUTION"`, verifies via `git merge-base --is-ancestor` and `git cat-file -e <commit>:<path>` that `frozen_at_commit_sha` is an ancestor of `runtime_head_sha` and all Stage A artifacts plus all 14 scientific code bundle blobs are committed in git history with matching git blob SHA-1s (`PlanBeforeLiveProtocolError` on uncommitted or tampered files).

---

## 5. Immutable Per-Cell Artifact Layout & Raw-Evidence-First Ordering

Each cell writes immutable artifacts to `<batch_output_dir>/cells/<run_id>/` via atomic temp-file + `os.fsync` + `os.replace` (`write_immutable_atomic_bytes`), failing closed with `ImmutableCellExecutionError` if any target file already exists:

1. **Before Transport**:
   - `request_manifest.json` (`BenchmarkRunManifest` + frozen wire request metadata and `wire_request_sha256`).
     - Truthfully records `generation_parameters` with `temperature_status = "OMITTED"` (never `temperature = 0.0`) and candidate-specific settings (`thinking_level`, `reasoning_effort`, `effort`, `seed`, `omitted_parameters`).
     - Truthfully records `execution_mode` (`OFFLINE_MOCK_VERIFICATION`, `LIVE_DEV_TUNE`, `LIVE_DEV_SELECT`, or `STOCHASTICITY_DIAGNOSTIC`) and `code_commit_sha = runtime_head_sha` alongside `code_basis_commit_sha`, `runtime_head_sha`, and `scientific_code_bundle_sha256`.
   - `transport_journal_starting.json` (`status = "TRANSPORT_STARTING"`).
2. **Immediately After Transport Returns (Before Any Validation/Parsing/Evaluation)**:
   - `transport_journal_completed.json` (`status = "TRANSPORT_COMPLETED"`, separate append-only file; never overwrites `transport_journal_starting.json`).
   - `raw_provider_response.txt` (exact UTF-8 raw text returned by provider, even when empty, truncated, or malformed).
   - `raw_usage_metadata.json` (raw provider usage payload + normalized token summary).
   - `provider_response_metadata.json` (returned `model_id`, `finish_reason`, `latency_ns`, `latency_ms`, `http_request_count`, `transport_status`, `error_classification`, sanitized error detail).
3. **After Deterministic Parsing & Evaluation**:
   - `parsed_plan_response.json` (written only when strict primary parsing succeeds).
   - `evaluation_result.json` (`ScenarioEvaluationResult` from `evaluate_dev_cell_scenario` or non-success denominator record).
   - `execution_receipt.json` (`DevCellExecutionReceipt` binding all artifact SHA-256 digests).

---

## 6. Transport-Start Journal, Call-Budget Ledger, Failure Taxonomy & Firewalls

- **Crash Ambiguity Stop**: If `transport_journal_starting.json` exists without `transport_journal_completed.json` or `execution_receipt.json`, the runner writes `transport_journal_unknown_after_transport.json` (`ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT`) and raises `CrashAmbiguityBatchStopError`.
- **Call-Budget Ledger (`DevCallBudgetLedger`)**: Enforces phase call caps (`60`, `120`, `180`, `15`), candidate whitelist, and scenario fixture whitelist; reserves before transport and permanently consumes on transport start with no failed-call refunds.
- **Failure Taxonomy**:
  - Ordinary denominator-0.0 scenario failures (batch continues): `PROVIDER_TIMEOUT`, `PROVIDER_TRANSPORT_ERROR` (`HTTP_429`, `HTTP_5XX`), `PROVIDER_REFUSAL`, `EMPTY_OR_TRUNCATED_OUTPUT` (`MAX_TOKEN_TRUNCATION`), `INVALID_JSON_OUTPUT`, `SCHEMA_VALIDATION_ERROR`.
  - Batch-fatal integrity stops (raw evidence persisted first, then batch halts): `MODEL_ID_MISMATCH`, `CONFIGURATION_INTEGRITY_ERROR` (`AUTHENTICATION_FAILURE`, `MODEL_ACCESS_FAILURE`), `HARNESS_INTERNAL_ERROR` (`SINGLE_CELL_HTTP_CALL_LIMIT_EXCEEDED`, runner bug), `ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT`.
- **Secret Hygiene & Final-100 Firewall**: Redacts and blocks secret patterns (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AIza...`, `sk-ant-...`, `sk-proj-...`, `sk-...`, `Bearer ...`) across all artifacts and blocks any `final100` path, scenario ID, or phase (`Final100FirewallViolationError`).
