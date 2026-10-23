# W06-DEV-SELECT-AUTHORIZATION-PREP-01: DEV-SELECT Live-Authorization Preparation & Scientific-Scope Freeze

## 0. Executive Summary & Scientific Scope

This report records the offline preparation and cryptographic binding of the Project Owner authorization scope for the preregistered **W06 DEV-SELECT** experiment (`60 frozen DEV-SELECT fixtures W06-DEV-SELECT-001..W06-DEV-SELECT-060 × 3 frozen candidates C1/C2/C3 × 1 locked prompt P1 = 180 assigned cells`).

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
| `W06-DEV-TUNE-PROMPT-SELECTION-01` | `CLOSED` (`SELECTED_PROMPT_ID = P1`) | Artifact SHA256: `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8`, Internal SHA256: `1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570`, Receipt SHA256: `0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114` |
| `W06-DEV-SELECT-PLAN-FREEZE-01` | `CLOSED` (`180 assigned cells`) | Plan internal SHA256: `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d`, Plan file SHA256: `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a`, Receipt file SHA256: `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |
| `SOURCE_DEVELOP_SHA` | Merge of PR #60 into `develop` | `549ce2e6eab239f9053775477f5c2fe58a16c65f` |
| `PLAN_CODE_BASIS_COMMIT_SHA` | Frozen code basis inside DEV-SELECT plan | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |
| `PLAN_CODE_COMMIT_SHA` | Frozen code commit inside DEV-SELECT plan | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |

---

## 2. Authoritative Frozen DEV-SELECT Plan, Prompt & Candidate Scope

### 2.1 Execution Plan & Fixture Binding
- **Plan File:** `data/evaluation/w06/w06_dev_select_execution_plan_v1.json`
- **Plan Internal SHA256:** `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d`
- **Plan File SHA256:** `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a`
- **Plan-Freeze Receipt File:** `data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json`
- **Plan-Freeze Receipt File SHA256:** `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549`
- **Phase:** `DEV_SELECT`
- **Authoritative Scientific Fixture IDs (`60 fixtures`):** `W06-DEV-SELECT-001` through `W06-DEV-SELECT-060`
- **DEV Fixture Bundle (`data/evaluation/w06/w06_dev_fixtures_freeze_v1.json`) SHA256:** `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`
- **DEV Fixture Manifest (`data/evaluation/w06/w06_dev_fixture_manifest_v1.json`) SHA256:** `15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98`
- **DEV-Final Overlap Receipt (`data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json`) SHA256:** `285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa`
- **DEV Fixture Freeze Receipt (`data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json`) SHA256:** `437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026`
- **Assigned Cells / Unique Run IDs / Unique Cell Keys:** `180` / `180` / `180` (`60` per candidate, `180` for `P1`, `3` per fixture)
- **Final100 Firewall:** `FINAL100_USED = false`, `FINAL100_AUTHORIZED = false`, `FINAL100_BUNDLE_SHA256 = c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1`, `P11_ASSIGNMENT_MANIFEST_SHA256 = 0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62`

### 2.2 Locked Prompt Authority (`P1`)
- **Selected Prompt ID:** `P1` (`ALLOWED_PROMPT_IDS = ["P1"]`, `PROVIDER_SPECIFIC_PROMPT_VARIANTS = false`)
- **Prompt Authorization Rule:** The allowed prompt set for `DEV_SELECT` is strictly allow-listed to `["P1"]`; therefore future `DEV-SELECT` authorization allows **ONLY `P1`**. P2 and P3 are not authorized (nor is `P0`; no prompt omitted from a helper's `forbidden_prompt_ids` display is ever allowed, because authorization is strictly allow-listed to `["P1"]`).
- **Prompt Version:** `TRAVEL_PLANNER_BENCHMARK_V2`
- **Semantic Prompt SHA256:** `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11`
- **System Prompt SHA256:** `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e`
- **User Prompt Template SHA256:** `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de`

### 2.3 Candidate, Provider, Schema & Code Bundle Authorities

| Candidate | Provider | Requested Model ID | Provider Config SHA256 | Sampling / Reasoning Config | Omitted Parameters | Max Output Tokens | Timeout (ms) | Cells |
|---|---|---|---|---|---|---|---|---|
| `C1` | `Google` | `gemini-3.8-flash` | `d4d417bdeff3f4156ac9605f976b46780c1cb0866d87674f1cee51d8bf3f3217` | `seed=2026101508`, `thinking_level=medium` | `temperature`, `top_p`, `top_k` | `16384` | `55000` | `60` |
| `C2` | `OpenAI` | `gpt-6.1-sol` | `6201244268383e85106b4d6e6ad0f503e066de9def361cbafa685227e8ba332e` | `reasoning_effort=medium`, `seed=2026101508`, `service_tier=default` | `temperature`, `top_p`, `top_k`, `logprobs`, `top_logprobs` | `16384` | `55000` | `60` |
| `C3` | `Anthropic` | `claude-sonnet-5-5` | `5ecff5a4e2899245d1cd113285d1193dad17b6ed4e7521bd10be3937650d2a29` | `thinking.type=adaptive`, `effort=high` | `temperature`, `top_p`, `top_k`, `seed` | `16384` | `55000` | `60` |

- **Candidate Registry SHA256:** `4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058`
- **Provider Config Registry SHA256:** `3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938`
- **Portable Schema v2 SHA256:** `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`
- **Semantic Schema SHA256:** `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`
- **Scientific Code Bundle SHA256 (`14 files`):** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`

---

## 3. Call Budget, Retry, Failure Policy & Offline Network Kill-Switch

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

### 3.3 Offline Network Kill-Switch & Compatibility Hardening
- Both `scripts/prepare_w06_dev_select_authorization.py` and the non-scientific plan-freeze verifier wrapper `scripts/freeze_w06_dev_select_plan.py` import the actual installed `httpx2` package (`httpx2 == 2.13.0`, never aliased to `httpx`) and block outbound requests across `socket`, `urllib.request`, `httpx`, and `httpx2` (`Client.send`, `AsyncClient.send`, `HTTPTransport.handle_request`, and `AsyncHTTPTransport.handle_async_request`).

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
- **Rendered `P1` User-Prompt UTF-8 Byte Statistics across the 60 `DEV-SELECT` Fixtures (`W06-DEV-SELECT-001`..`W06-DEV-SELECT-060`):**
  - `MIN_RENDERED_USER_PROMPT_BYTES = 40418`
  - `MAX_RENDERED_USER_PROMPT_BYTES = 74597`
  - `TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES = 3304906`
  - `P1_SYSTEM_PROMPT_BYTES = 263`
- **Conservative 180-Cell Planning Cost Envelope (`60 cells × C1 + 60 cells × C2 + 60 cells × C3`):**
  - `PLANNING_COST_ENVELOPE_LOW_USD = 7.31` (`$7.3125 USD` exact decimal)
  - `PLANNING_COST_ENVELOPE_HIGH_USD = 14.74` (`$14.7375 USD` exact decimal)
  - `CONDITIONAL_16384_BILLABLE_OUTPUT_REFERENCE_USD = 35.01` (`$35.0124 USD` exact decimal)
  - `HARD_MAX_COST_USD = NOT_DEFENSIBLY_COMPUTABLE`
- **Historical Observational DEV-TUNE Context (`data/evaluation/w06/w06_dev_tune_live_results_manifest_v1.json`):**
  - **Accounting Mode:** `AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY`
  - `AUTHORITATIVE_COST_CELL_COUNT = 42`
  - `AUTHORITATIVE_RECEIPT_COST_TOTAL_USD = 6.5555805`
  - **Candidate Available-Only Authoritative Costs:**
    - `C1`: `4` cells, `0.080954` USD
    - `C2`: `5` cells, `0.3768775` USD
    - `C3`: `33` cells, `6.097749` USD
  - **Explicit Restrictions:** This figure is `AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY` (covering the 42 DEV-TUNE cells with uncachedcomparable receipt cost); it is **NOT** a final provider invoice, **NOT** an extrapolated hard budget, and **NOT** a scientific selection criterion.

---

## 5. Exact Project Owner Authorization Sentence (Status: `NOT_GRANTED`)

```text
I authorize W06 DEV-SELECT live execution for exactly the frozen 180-cell plan de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d (plan file c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a), bound by plan-freeze receipt 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549, using locked prompt P1 from prompt-selection artifact e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8 (semantic SHA 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11), candidates C1/C2/C3, maximum 180 generation calls, zero retry, no DEV-TUNE rerun, no stochasticity, and no Final100.
```

- **Exact UTF-8 SHA256 (`PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256`):** `6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7`
- **Current Authorization Status:** `PROJECT_OWNER_AUTHORIZATION_STATUS = NOT_GRANTED`
