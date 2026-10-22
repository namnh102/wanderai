# W06-DEV-SELECT-AUTHORIZATION-PREP-01: DEV-SELECT Live-Authorization Preparation & Scientific-Scope Freeze

## 0. Executive Summary & Scientific Scope

This report records the offline preparation and cryptographic binding of the Project Owner authorization scope for the preregistered **W06 DEV-SELECT** experiment (`60 frozen DEV-SELECT fixtures × 3 frozen candidates C1/C2/C3 × 1 locked prompt P1 = 180 assigned cells`).

- **Task ID:** `W06-DEV-SELECT-AUTHORIZATION-PREP-01`
- **Artifact ID:** `W06-DEV-SELECT-AUTHORIZATION-PREP-01-V1`
- **Artifact Path:** `data/evaluation/w06/w06_dev_select_authorization_prep_v1.json`
- **Artifact File SHA256:** `60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8`
- **Source Branch / Commit:** `develop` @ `549ce2e6eab239f9053775477f5c2fe58a16c65f`
- **Project Owner Authorization Status:** `NOT_GRANTED`
- **Live Provider Calls / Cost in this Task:** `LIVE_PROVIDER_CALLS_NEW = 0`, `PROVIDER_COST_USD_NEW = 0`

This task **does not authorize live execution itself**, does not create a DEV-SELECT live-authorization artifact, does not create a Stage-A receipt, does not mint `LiveExecutionCapability`, does not construct `ProductionProviderTransport`, and does not start DEV-SELECT execution.

---

## 1. Closed Upstream Gates & Provenance Discipline

All required upstream gates are verified closed and cryptographically intact:

| Gate / Authority | Status / Identifier | SHA256 / Value |
|---|---|---|
| `W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01` | `CLOSED` | Raw evidence tree SHA256: `9b6089f478979ce32e968529c656358fc1bb751101527e017c1e4d5a695cd1e8` |
| `W06-DEV-TUNE-PROMPT-SELECTION-01` | `CLOSED` (`SELECTED_PROMPT_ID = P1`) | Artifact SHA256: `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8`, Receipt SHA256: `0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114` |
| `W06-DEV-SELECT-PLAN-FREEZE-01` | `CLOSED` (`180 assigned cells`) | Plan internal SHA256: `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d`, Plan file SHA256: `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a`, Receipt file SHA256: `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |
| `SOURCE_DEVELOP_SHA` | Merge of PR #60 into `develop` | `549ce2e6eab239f9053775477f5c2fe58a16c65f` |
| `PLAN_CODE_BASIS_COMMIT_SHA` | Frozen code basis inside DEV-SELECT plan | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |
| `PLAN_CODE_COMMIT_SHA` | Frozen code commit inside DEV-SELECT plan | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |

---

## 2. Authoritative Frozen DEV-SELECT Plan, Prompt & Candidate Scope

### 2.1 Execution Plan Binding
- **Plan File:** `data/evaluation/w06/w06_dev_select_execution_plan_v1.json`
- **Plan Internal SHA256:** `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d`
- **Plan File SHA256:** `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a`
- **Plan-Freeze Receipt File:** `data/evaluation/w06/w06_dev_select_plan_freeze_receipt_v1.json`
- **Plan-Freeze Receipt File SHA256:** `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549`
- **Phase:** `DEV_SELECT`
- **Fixtures:** `60` (`D021..D080`), `DEV_FIXTURE_BUNDLE_SHA256 = f4d91d7e23d0d5084020e3190f1ee8a8eb2ea3931a3d720eeab0e4028d1bf02a`
- **Assigned Cells / Unique Run IDs / Unique Cell Keys:** `180` / `180` / `180` (`60` per candidate, `180` for `P1`, `3` per fixture)
- **Final100 Firewall:** `FINAL100_USED = false`, `FINAL100_AUTHORIZED = false`, `FINAL100_BUNDLE_SHA256 = 74e7faaa3f9af6a4ab1ffeb7c10fdbe8fb42dc0fb6f4a835db5157c6beebad6e`, `P11_ASSIGNMENT_MANIFEST_SHA256 = b14357613aa7a736f24cd4fdbe3a221ec52cd8ec2b7ffefeb8efaa89f2d80e0a`

### 2.2 Locked Prompt Authority (`P1`)
- **Selected Prompt ID:** `P1` (`ALLOWED_PROMPT_IDS = ["P1"]`, `FORBIDDEN_PROMPT_IDS = ["P0", "P2"]`, `PROVIDER_SPECIFIC_PROMPT_VARIANTS = false`)
- **Prompt Version:** `TRAVEL_PLANNER_BENCHMARK_V2`
- **Semantic Prompt SHA256:** `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11`
- **System Prompt SHA256:** `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e`
- **User Prompt Template SHA256:** `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de`

### 2.3 Candidate, Provider, Schema & Code Bundle Authorities

| Candidate | Provider | Requested Model ID | Provider Config SHA256 | Sampling / Reasoning Config | Max Output Tokens | Timeout (ms) | Cells |
|---|---|---|---|---|---|---|---|
| `C1` | `Google` | `gemini-3.8-flash` | `512c693bf728fa0ba37da449fe22773e6261482041f0bc79a96f62f2ba48bf50` | `temperature=0.0`, `thinking_level=LOW` (`top_p`, `top_k`, `seed` omitted) | `16384` | `120000` | `60` |
| `C2` | `OpenAI` | `gpt-6.1-sol` | `3129a973e8e62921e780ef25f00ba3c5b2ec9950b5b5f19ba7a5e8f8fd355fa5` | `reasoning_effort=low`, `service_tier=default` (`temperature`, `top_p`, `seed` omitted) | `16384` | `120000` | `60` |
| `C3` | `Anthropic` | `claude-sonnet-5-5` | `0735bb9dc60d7e8fb94c8e71a9cf3a72844ff8cc061f47c4f6cb4cd5e572b80c` | `thinking=adaptive`, `effort=low` (`temperature`, `top_p`, `top_k` omitted) | `16384` | `120000` | `60` |

- **Candidate Registry SHA256:** `4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058`
- **Provider Config Registry SHA256:** `3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938`
- **Portable Schema v2 SHA256:** `8beec9cfba8cc38a7c7cc3cc821edefbd1fd6c278ebca8dc412276a0b74decf1`
- **Semantic Schema SHA256:** `2fb2e38caaa67f5eb6a2ca14eb585f0e233eb5d46fe2dc407e9458931a1bc06b`
- **Scientific Code Bundle SHA256 (`14 files`):** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`

---

## 3. Call Budget, Retry & Failure Policy

### 3.1 Call Budget & Retry Discipline
- `ASSIGNED_CELLS = 180`
- `MAXIMUM_LIVE_GENERATION_CALLS = 180`
- `RESERVE_CALLS_BEYOND_180 = 0`
- `RETRY_CALLS = 0` (`ATTEMPT_NUMBER = 1`, `SDK_RETRY = 0`, `TRANSPORT_RETRY = 0`, `MANUAL_RETRY = 0`, `AUTOMATIC_RETRY = 0`)
- `FALLBACK = false`, `BEST_OF = false`, `LLM_REPAIR = 0`, `DETERMINISTIC_SEMANTIC_REPAIR = false`, `TOOLS = false`
- `DEV_TUNE_RERUN_CALLS = 0`, `STOCHASTICITY_CALLS = 0`, `FINAL100_CALLS = 0`
- Maximum 1 outbound HTTP generation request per assigned cell.

### 3.2 Ordinary vs Batch-Fatal Failure Classification
- **Ordinary Denominator-Preserving Failures** (`HTTP_429`, `HTTP_5XX`, `TIMEOUT`, `PARTIAL_TIMEOUT`, `AUTHENTICATION_FAILURE`, `MODEL_ACCESS_FAILURE`, `MALFORMED_JSON`, `SEMANTIC_VALIDATION_FAILURE`, `REFUSAL`, `MAX_TOKEN_TRUNCATION`):
  - Count in denominator (`valid_run_and_schema = False`, `exact_grounding_pass = False`, `final_core_pass = False`), `retry = 0`, do **not** trigger a batch stop.
- **Batch-Fatal Integrity Failures** (`MODEL_INTEGRITY_MISMATCH`, `HARNESS_INTERNAL_ERROR`, `SCIENTIFIC_CODE_BUNDLE_MISMATCH`, `PROVIDER_CONFIG_MISMATCH`, `PROMPT_INTEGRITY_MISMATCH`, `EXECUTION_PLAN_INTEGRITY_MISMATCH`, `AUTHORIZATION_INTEGRITY_MISMATCH`, `STAGE_A_INTEGRITY_MISMATCH`, `RUNTIME_HEAD_DRIFT`, `CALL_BUDGET_INTEGRITY_FAILURE`):
  - Immediately halt the batch fail-closed (`STOP_BATCH_IMMEDIATELY_FAIL_CLOSED`).

---

## 4. Key Presence, Runtime / SDK Versions & Conservative 180-Cell Cost Envelope

### 4.1 Secret-Free Key Presence Status
- `GEMINI_API_KEY`: `PRESENT`
- `OPENAI_API_KEY`: `PRESENT`
- `ANTHROPIC_API_KEY`: `PRESENT`
- Zero key values, prefixes, suffixes, lengths, or hashes are read, printed, or persisted.

### 4.2 Runtime & SDK Versions
- `PYTHON_VERSION`: `3.11.9`
- `GOOGLE_GENAI_VERSION`: `2.25.0`
- `OPENAI_VERSION`: `3.17.0`
- `ANTHROPIC_VERSION`: `1.15.0`
- `HTTPX_VERSION`: `0.28.1`
- `HTTPX2_VERSION`: `2.13.0`
- `ENVIRONMENT_VERSION_DRIFT`: `false`

### 4.3 Conservative 180-Cell Planning Cost Envelope
- **Rendered `P1` User-Prompt UTF-8 Byte Statistics across the 60 `DEV-SELECT` Fixtures (`D021..D080`):**
  - `MIN_RENDERED_USER_PROMPT_BYTES = 40418`
  - `MAX_RENDERED_USER_PROMPT_BYTES = 74597`
  - `TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES = 3304906`
  - `P1_SYSTEM_PROMPT_BYTES = 263`
- **Conservative 180-Cell Planning Cost Envelope (`60 cells × C1 + 60 cells × C2 + 60 cells × C3`):**
  - `PLANNING_COST_ENVELOPE_LOW_USD = 7.31` (`$7.3125 USD` exact decimal)
  - `PLANNING_COST_ENVELOPE_HIGH_USD = 14.74` (`$14.7375 USD` exact decimal)
  - `CONDITIONAL_16384_BILLABLE_OUTPUT_REFERENCE_USD = 35.01` (`$35.0124 USD` exact decimal)
  - `HARD_MAX_COST_USD = NOT_DEFENSIBLY_COMPUTABLE`
- **Historical Observational DEV-TUNE Context (`data/evaluation/w06/w06_dev_tune_live_results_v1_manifest.json`):**
  - `120` authoritative cost cells totaling `$2.8388 USD` (`C1 = $0.1449`, `C2 = $1.0156`, `C3 = $1.6783`), recorded strictly as observational context and never extrapolated as a scientific selection, stop, or retry criterion.

---

## 5. Exact Project Owner Authorization Sentence (Status: `NOT_GRANTED`)

```text
I authorize W06 DEV-SELECT live execution for exactly the frozen 180-cell plan de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d (plan file c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a), bound by plan-freeze receipt 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549, using locked prompt P1 from prompt-selection artifact e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8 (semantic SHA 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11), candidates C1/C2/C3, maximum 180 generation calls, zero retry, no DEV-TUNE rerun, no stochasticity, and no Final100.
```

- **Exact UTF-8 SHA256 (`PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256`):** `6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7`
- **Current Authorization Status:** `PROJECT_OWNER_AUTHORIZATION_STATUS = NOT_GRANTED`
