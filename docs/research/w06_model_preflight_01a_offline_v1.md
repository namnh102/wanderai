# W06-MODEL-PREFLIGHT-01A-OFFLINE — Offline Model/Provider Technical Preflight Specification & Evidence

- **Artifact ID:** `W06-MODEL-PREFLIGHT-01A-OFFLINE`
- **Task ID:** `W06-MODEL-PREFLIGHT-01A-OFFLINE` (`W06-MODEL-PREFLIGHT-01A-FIX-01`)
- **Version:** `1.1.0`
- **Status:** `READY_FOR_LIVE_PREFLIGHT` (`OFFLINE_PREFLIGHT_COMPLETE_PENDING_PHASE_01B_LIVE_SMOKE`)
- **Base `develop` SHA:** `ff40f42db163a21dfc85d467073e99f628e0154a`
- **Method Lock Authority:** `data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json` (`6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c`)
- **Offline Receipt Path:** `data/evaluation/w06/w06_model_preflight_01a_offline_receipt_v1.json`

---

## 1. Execution Scope & Strict Offline Boundary

This phase (`W06-MODEL-PREFLIGHT-01A-OFFLINE`) performs **offline technical preflight only**:
- `live_provider_calls_allowed = false`
- `live_provider_calls_performed = false`
- `provider_cost_usd = 0`
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

## 3. Environment, Secret Hygiene & Dependency Lock Verification

### 3.1 Secret Hygiene & Error Redaction (`sanitize_secret_error_text`)
- `.gitignore` rule `.env` is active; `git check-ignore -v apps/ai-service/.env` confirms `apps/ai-service/.env` is git-ignored and untracked.
- Production `apps/ai-service/app/config.py` and `apps/ai-service/requirements.txt` remain untouched at `develop` (`ff40f42db163a21dfc85d467073e99f628e0154a`).
- Preflight-only key presence inspection (`inspect_preflight_env_key_presence` in `apps/ai-service/app/evaluation/model_preflight/base.py`) checks key presence without exposing secret values, lengths, prefixes, suffixes, or hashes:
  - `GEMINI_API_KEY`: `PRESENT`
  - `OPENAI_API_KEY`: `PRESENT`
  - `ANTHROPIC_API_KEY`: `PRESENT`
- Before any exception or provider error text is stored in `error_detail` or receipt records, `sanitize_secret_error_text()` redacts any occurrence of active env secrets as well as secret-like token patterns (`sk-*`, `sk-proj-*`, `sk-ant-*`, `AIza*`, `Bearer *`, `x-api-key`, `x-goog-api-key`) to `[REDACTED_SECRET]`.
- Tracked-file secret scan across all tracked repository files:
  - `secret_leak_count = 0`
  - `affected_file_paths = []`

### 3.2 Locked Provider & Transport Dependencies
Locked in `apps/ai-service/requirements-w06-provider-lock.txt` (`SHA256 = fd3d6364c3eeb3ae024c6b7248d7f9c8e497987e7cd3f8b06ad67d18e16d0085`) and referenced from `apps/ai-service/requirements-dev.txt`:
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

## 4. Semantic Schema vs Strict Structured-Output Generation Schema

- **Common Schema Source:** `BenchmarkPlanResponse` (`apps/ai-service/app/evaluation/model_preflight/schema_adapter.py`)
- **`SEMANTIC_SCHEMA_SHA256` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES` of raw `BenchmarkPlanResponse.model_json_schema()`):**
  `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`
- **`COMMON_GENERATION_SCHEMA_SHA256` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES` of `build_strict_generation_json_schema()`):**
  `5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c`
- **Projection Whitelist Guard (`verify_strict_generation_schema_projection`):**
  The strict generation schema transformation is verified to apply **only** the whitelisted technical projections:
  - enforce `additionalProperties: false` on every object node (`$defs` and root)
  - materialize an explicit sorted `required` array listing all object properties
  - strip `default` metadata on required properties so strict JSON Schema validators accept nullable `anyOf` fields without default-value conflicts
  - preserve every semantic field name, type, constraint (`minLength`, `minimum`, `maximum`, `pattern`, `enum`), `$defs` structure, and nullable `anyOf` union
- **Grounding Integrity Guard:** `place_id` is verified **not** to be encoded as a provider-side enum of catalog IDs (`schema_encodes_place_id_as_catalog_enum == False`).
- **Provider Technical Wiring:**
  - `C1` (`Google` / `gemini-3.8-flash`): `GenerateContentConfig(response_mime_type="application/json", response_json_schema=COMMON_BENCHMARK_PLAN_JSON_SCHEMA)`
  - `C2` (`OpenAI` / `gpt-6.1-sol`): `response_format={"type": "json_schema", "json_schema": {"name": "BenchmarkPlanResponse", "strict": True, "schema": COMMON_BENCHMARK_PLAN_JSON_SCHEMA}}`
  - `C3` (`Anthropic` / `claude-sonnet-5-5`): `output_config={"effort": "high", "format": {"type": "json_schema", "schema": COMMON_BENCHMARK_PLAN_JSON_SCHEMA}}`

---

## 5. Candidate-by-Candidate Offline Capability Matrix

| Field / Capability | `C1` (`Google` — `READY_FOR_LIVE_PREFLIGHT`) | `C2` (`OpenAI` — `READY_FOR_LIVE_PREFLIGHT`) | `C3` (`Anthropic` — `READY_FOR_LIVE_PREFLIGHT`) |
|---|---|---|---|
| **Requested Model ID** | `gemini-3.8-flash` | `gpt-6.1-sol` | `claude-sonnet-5-5` |
| **Live Model ID Status** | `PENDING_LIVE_CONFIRMATION` | `PENDING_LIVE_CONFIRMATION` | `PENDING_LIVE_CONFIRMATION` |
| **SDK Package & Version** | `google-genai==2.25.0` | `openai==3.17.0` | `anthropic==1.15.0` |
| **Endpoint Semantics** | `models.generate_content` (`VERIFIED_BY_SDK_SURFACE`) | `chat.completions.create` (`SDK_PARAMETER_EXISTS`, model compatibility `PENDING_LIVE_CONFIRMATION`) | `messages.create` (`VERIFIED_BY_SDK_SURFACE`) |
| **Structured Output Mode** | `NATIVE_RESPONSE_JSON_SCHEMA` (`VERIFIED_BY_SDK_SURFACE`) | `NATIVE_JSON_SCHEMA_STRICT` (`SDK_PARAMETER_EXISTS`, runtime `PENDING_LIVE_CONFIRMATION`) | `NATIVE_OUTPUT_CONFIG_JSON_SCHEMA` (`VERIFIED_BY_SDK_SURFACE`) |
| **`temperature`** | Omitted (`None`, provider default `1.0` per Gemini 3 thinking guidance) | `0.0` (`SDK_PARAMETER_EXISTS`, model-level `PENDING_LIVE_CONFIRMATION`) | Omitted (`None`, incompatible with adaptive thinking on Claude Sonnet 5.5) |
| **`seed`** | `2026101508` (`SDK_PARAMETER_EXISTS`, model-level `PENDING_LIVE_CONFIRMATION`) | `2026101508` (`SDK_PARAMETER_EXISTS`, model-level `PENDING_LIVE_CONFIRMATION`) | Omitted (`None`, `UNSUPPORTED` by Anthropic Messages API) |
| **`top_p`** | Omitted (`None`) | Omitted (`None`) | Omitted (`None`) |
| **`top_k`** | Omitted (`None`) | Omitted (`None`, `UNSUPPORTED`) | Omitted (`None`, incompatible with adaptive thinking) |
| **Thinking / Reasoning** | `ThinkingConfig(thinking_level="medium")` (`VERIFIED_BY_SDK_SURFACE`) | `reasoning_effort=None` (`SDK_PARAMETER_EXISTS`, model-level `PENDING_LIVE_CONFIRMATION`) | `thinking={"type": "adaptive"}`, `output_config.effort="high"` (`VERIFIED_BY_SDK_SURFACE`) |
| **`max_output_tokens`** | `16384` (`max_output_tokens`) | `16384` (`max_completion_tokens`) | `16384` (`max_tokens`) |
| **`timeout`** | `55000` ms (`HttpOptions.timeout`) | `55000` ms (`55.0` s) | `55000` ms (`55.0` s) |
| **Retry = 0 Mechanism** | `HttpRetryOptions(attempts=1)` (`OFFLINE_TEST_VERIFIED`) | `OpenAI(max_retries=0)` (`OFFLINE_TEST_VERIFIED`) | `Anthropic(max_retries=0)` (`OFFLINE_TEST_VERIFIED`) |
| **Returned Model Field** | `GenerateContentResponse.model_version` | `ChatCompletion.model` | `Message.model` |
| **Offline Status & Blockers** | `READY_FOR_LIVE_PREFLIGHT`, `blockers = []` | `READY_FOR_LIVE_PREFLIGHT`, `blockers = []` | `READY_FOR_LIVE_PREFLIGHT`, `blockers = []` |

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

Both serialize with identical `system_prompt_sha256`, `user_prompt_sha256`, `SEMANTIC_SCHEMA_SHA256`, and `COMMON_GENERATION_SCHEMA_SHA256` across `C1`, `C2`, and `C3`.

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
