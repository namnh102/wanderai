# W06-MODEL-PREFLIGHT-01A-OFFLINE — Offline Model/Provider Technical Preflight Specification & Evidence

- **Artifact ID:** `W06-MODEL-PREFLIGHT-01A-OFFLINE`
- **Task ID:** `W06-MODEL-PREFLIGHT-01A-OFFLINE`
- **Version:** `1.0.0`
- **Status:** `OFFLINE_PREFLIGHT_COMPLETE_PENDING_PHASE_01B_LIVE_SMOKE`
- **Base `develop` SHA:** `ff40f42db163a21dfc85d467073e99f628e0154a`
- **Method Lock Authority:** `data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json` (`6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c`)
- **Offline Receipt Path:** `data/evaluation/w06/w06_model_preflight_01a_offline_receipt_v1.json`

---

## 1. Execution Scope & Strict Offline Boundary

This phase (`W06-MODEL-PREFLIGHT-01A-OFFLINE`) performs **offline technical preflight only**:
- `LIVE_CALLS_MADE = 0` (`gemini_called = false`, `openai_called = false`, `claude_called = false`, `grok_called = false`)
- `FINAL_100_USED = false`
- `DEV_TUNE_EXECUTED = false`
- `DEV_SELECT_EXECUTED = false`
- `WINNING_MODEL_SELECTED = false`
- `PREREGISTERED = false`
- `FINAL_BENCHMARK_EXECUTED = false`

A runtime guard (`W06_PREFLIGHT_LIVE_ALLOWED = false` by default) is enforced in `apps/ai-service/app/evaluation/model_preflight/base.py`. Any attempt to execute a request without an explicit offline `mock_transport` while `W06_PREFLIGHT_LIVE_ALLOWED` is `false` raises `LiveProviderCallForbiddenError` (`LIVE_PROVIDER_CALL_FORBIDDEN`).

---

## 2. Frozen Primary Architecture & One-Call Invariants

- **Architecture ID:** `LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1`
- **Architecture Class:** `DIRECT_ONE_CALL_PLUS_READ_ONLY_DETERMINISTIC_VALIDATION`
- **Enforced Per-Execution Invariants:**
  - `llm_calls_per_execution = 1`
  - `model_initiated_tool_calls = 0` (`tools = None`; `automatic_function_calling` disabled on Google)
  - `llm_repair_calls = 0`
  - `fallback = false`
  - `primary_json_repair = false` (`clean_benchmark_json_response` is **not** called in the primary parse path; primary parsing uses `json.loads` directly on the raw response text followed by strict `BenchmarkPlanResponse` validation)
  - `raw_provider_response_preserved = true` (`SHA256_EXACT_PERSISTED_UTF8_BYTES`)

---

## 3. Environment & Dependency Lock Verification

### 3.1 Secret Hygiene & `.env` Presence Audit (Redacted)
- `.gitignore` rule `.env` is active; `git check-ignore -v apps/ai-service/.env` confirms `apps/ai-service/.env` is git-ignored and untracked.
- `apps/ai-service/app/config.py` `Settings` defines:
  - `GEMINI_API_KEY: str = ""`
  - `OPENAI_API_KEY: str = ""`
  - `ANTHROPIC_API_KEY: str = ""`
  - Production `PLANNER_MODEL: str = "gemini-3.5-flash"` is preserved unchanged.
- Presence in `apps/ai-service/.env` (values, lengths, prefixes, suffixes, and hashes are never logged or persisted):
  - `GEMINI_API_KEY`: `PRESENT`
  - `OPENAI_API_KEY`: `PRESENT`
  - `ANTHROPIC_API_KEY`: `PRESENT`
- Tracked-file secret scan across all tracked repository files:
  - `secret_leak_count = 0`
  - `affected_file_paths = []`

### 3.2 Locked Provider & Transport Dependencies
Locked in `apps/ai-service/requirements-w06-provider-lock.txt` (`SHA256 = fd3d6364c3eeb3ae024c6b7248d7f9c8e497987e7cd3f8b06ad67d18e16d0085`):
- `python`: `3.11.9`
- `google-genai==2.25.0`
- `openai==3.17.0`
- `anthropic==1.15.0`
- `httpx==0.28.1`
- `httpcore==1.0.9`
- `httpx2==2.13.0`
- `httpcore2==2.13.0`
- `pydantic==2.13.4`
- `pydantic-core==2.46.4`
- `anyio==4.13.0`

---

## 4. Common Semantic Schema & Technical Structured-Output Wiring

- **Common Schema Source:** `BenchmarkPlanResponse` (`apps/ai-service/app/evaluation/model_preflight/schema_adapter.py`)
- **`COMMON_SCHEMA_SHA256` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`):**
  `5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c`
- **Grounding Integrity Guard:** `place_id` is verified **not** to be encoded as a provider-side enum of catalog IDs (`schema_encodes_place_id_as_catalog_enum == False`).
- **Provider Technical Wiring:**
  - `C1` (`Google` / `gemini-3.8-flash`): `GenerateContentConfig(response_mime_type="application/json", response_json_schema=COMMON_BENCHMARK_PLAN_JSON_SCHEMA)`
  - `C2` (`OpenAI` / `gpt-6.1-sol`): `response_format={"type": "json_schema", "json_schema": {"name": "BenchmarkPlanResponse", "strict": True, "schema": COMMON_BENCHMARK_PLAN_JSON_SCHEMA}}`
  - `C3` (`Anthropic` / `claude-sonnet-5-5`): `output_config={"format": {"type": "json_schema", "schema": COMMON_BENCHMARK_PLAN_JSON_SCHEMA}}`

---

## 5. Candidate-by-Candidate Offline Capability Matrix

| Field / Capability | `C1` (`Google`) | `C2` (`OpenAI`) | `C3` (`Anthropic`) |
|---|---|---|---|
| **Requested Model ID** | `gemini-3.8-flash` | `gpt-6.1-sol` | `claude-sonnet-5-5` |
| **Live Model ID Status** | `PENDING_LIVE_CONFIRMATION` | `PENDING_LIVE_CONFIRMATION` | `PENDING_LIVE_CONFIRMATION` |
| **SDK Package & Version** | `google-genai==2.25.0` | `openai==3.17.0` | `anthropic==1.15.0` |
| **Endpoint Semantics** | `models.generate_content` (`VERIFIED_BY_SDK_SURFACE`) | `chat.completions.create` (`VERIFIED_BY_SDK_SURFACE`) | `messages.create` (`VERIFIED_BY_SDK_SURFACE`) |
| **Structured Output Mode** | `NATIVE_RESPONSE_JSON_SCHEMA` (`VERIFIED_BY_SDK_SURFACE`) | `NATIVE_JSON_SCHEMA_STRICT` (`VERIFIED_BY_SDK_SURFACE`) | `NATIVE_OUTPUT_CONFIG_JSON_SCHEMA` (`VERIFIED_BY_SDK_SURFACE`) |
| **`temperature`** | `0.0` (`VERIFIED_BY_SDK_SURFACE`) | `0.0` (`VERIFIED_BY_SDK_SURFACE`) | `UNSUPPORTED` on `anthropic==1.15.0` `messages.create` signature (fixed provider default behavior documented) |
| **`seed`** | `2026101508` (`VERIFIED_BY_SDK_SURFACE`) | `2026101508` (`VERIFIED_BY_SDK_SURFACE`) | `UNSUPPORTED` |
| **`top_p`** | `None` (`VERIFIED_BY_SDK_SURFACE`) | `None` (`VERIFIED_BY_SDK_SURFACE`) | `UNSUPPORTED` |
| **`top_k`** | `None` (`VERIFIED_BY_SDK_SURFACE`) | `UNSUPPORTED` | `UNSUPPORTED` |
| **Thinking / Reasoning** | `thinking_config=None` (`VERIFIED_BY_SDK_SURFACE`) | `reasoning_effort=None` (`VERIFIED_BY_SDK_SURFACE`) | `thinking={"type": "disabled"}` (`VERIFIED_BY_SDK_SURFACE`) |
| **`max_output_tokens`** | `16384` (`max_output_tokens`) | `16384` (`max_completion_tokens`) | `16384` (`max_tokens`) |
| **`timeout`** | `55000` ms (`HttpOptions.timeout`) | `55000` ms (`55.0` s) | `55000` ms (`55.0` s) |
| **Retry = 0 Mechanism** | `HttpRetryOptions(attempts=1)` (`OFFLINE_TEST_VERIFIED`) | `OpenAI(max_retries=0)` (`OFFLINE_TEST_VERIFIED`) | `Anthropic(max_retries=0)` (`OFFLINE_TEST_VERIFIED`) |
| **Returned Model Field** | `GenerateContentResponse.model_version` | `ChatCompletion.model` | `Message.model` |

---

## 6. Offline Retry = 0 & Failure Classification Proof

All three candidate adapters (`C1`, `C2`, `C3`) are verified offline using `httpx.MockTransport` / `httpx2.MockTransport` across six failure modes:
1. `HTTP 429` (`PreflightFailureClassification.HTTP_429`): `request_attempt_count == 1`, `fallback_called == False`, `llm_repair_calls == 0`
2. `HTTP 500` (`PreflightFailureClassification.HTTP_5XX`): `request_attempt_count == 1`, `fallback_called == False`, `llm_repair_calls == 0`
3. `timeout` (`PreflightFailureClassification.TIMEOUT`): `request_attempt_count == 1`, `fallback_called == False`, `llm_repair_calls == 0`
4. `malformed_response` (`PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT`): `request_attempt_count == 1`, `raw_artifact_preserved == True`, `primary_json_repair_called == False`
5. `refusal` (`PreflightFailureClassification.REFUSAL`): `request_attempt_count == 1`, `raw_artifact_preserved == True`, `fallback_called == False`
6. `wrong_returned_model_id` (`PreflightFailureClassification.CONFIGURATION_INTEGRITY_FAILURE` / `BenchmarkRunStatus.MODEL_ID_MISMATCH`): `request_attempt_count == 1`, `fallback_called == False`, raises `ConfigurationIntegrityError` when `raise_on_integrity_failure=True`.

---

## 7. Synthetic Technical Smoke Fixtures

Two synthetic smoke fixtures are defined in `apps/ai-service/app/evaluation/model_preflight/base.py` without reading or overlapping with the final 100 scenarios or the 80 DEV fixtures:
- `W06-PREFLIGHT-SMOKE-001` (`ha-noi`, 2 days, `culture_history`, `COMFORT`, 2 synthetic POIs)
- `W06-PREFLIGHT-SMOKE-002` (`da-nang`, 2 days, `food_cuisine`, `BUDGET`, 2 synthetic POIs)

Both serialize with identical `system_prompt_sha256`, `user_prompt_sha256`, and `COMMON_SCHEMA_SHA256` across `C1`, `C2`, and `C3`.

---

## 8. Read-Only Opening-Hours Catalog Coverage Audit

Computed read-only over `data/curated/gomate_places_freeze_v2.json` (`SHA256 = f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`) using parser `W06-OPENING-HOURS-PARSER-01C-V1.0.0`:
- `total_reca_core_pois = 622`
- `raw_opening_hours_present_count = 101` (`raw_presence_rate = 0.162379`)
- `raw_opening_hours_missing_count = 521`
- `known_opening_hours_count = 91` (`parser_supported_opening_hours_count = 91`, `coverage_rate = 0.146302`)
- `parser_unsupported_opening_hours_count = 10`
- `unknown_opening_hours_count = 531` (`521` missing + `10` unsupported syntax)
- **Per-Destination Breakdown:**
  - `ha-noi`: `total_reca_core_pois = 145`, `raw_opening_hours_present_count = 27`, `known_opening_hours_count = 23`, `parser_unsupported_opening_hours_count = 4`, `unknown_opening_hours_count = 122`, `coverage_rate = 0.158621`
  - `da-nang`: `total_reca_core_pois = 289`, `raw_opening_hours_present_count = 59`, `known_opening_hours_count = 53`, `parser_unsupported_opening_hours_count = 6`, `unknown_opening_hours_count = 236`, `coverage_rate = 0.183391`
  - `ha-long`: `total_reca_core_pois = 188`, `raw_opening_hours_present_count = 15`, `known_opening_hours_count = 15`, `parser_unsupported_opening_hours_count = 0`, `unknown_opening_hours_count = 173`, `coverage_rate = 0.079787`
