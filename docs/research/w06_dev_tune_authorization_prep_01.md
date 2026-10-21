# W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01 — Scientific Live-Execution Authorization Preparation Report

## 0. Source State & Offline Discipline

| Field | Value |
|---|---|
| **Task ID** | `W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01` |
| **Role** | Scientific live-execution authorization preparation agent |
| **Repository** | `namnh102/wanderai` (`D:\Do_an\wanderai`) |
| **Source Branch** | `develop` |
| **Source `develop` SHA** | `443634e1f7583f334dec0315bb3816d249feb124` |
| **Preparation Branch** | `research/w06-dev-tune-live-authorization-prep-01` |
| **Preparation Artifact** | `data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json` |
| **Preparation Artifact SHA256** | `168d29741fd75884a9b3f066822a843bcc6fd56ed06d4c16b40b8129d4d62f33` |
| **`LIVE_PROVIDER_CALLS`** | `0` |
| **`PROVIDER_COST_USD`** | `0` |
| **`LIVE_AUTHORIZATION_ARTIFACT_CREATED`** | `false` |
| **`STAGE_A_CREATED`** | `false` |
| **`PROJECT_OWNER_AUTHORIZATION_STATUS`** | `NOT_GRANTED` |

---

## 1. Frozen Authorities

All upstream frozen authorities are verified byte-for-byte before constructing the preparation artifact:

| Authority | Path / Identifier | SHA256 |
|---|---|---|
| **Prompt Candidate Freeze Artifact** | `data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json` | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| **DEV-TUNE Execution Plan (Canonical Payload)** | `DevExecutionPlan.plan_sha256` | `582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae` |
| **DEV-TUNE Execution Plan (Persisted File)** | `data/evaluation/w06/w06_dev_tune_execution_plan_v1.json` | `652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74` |
| **Prompt Registry (`P1`, `P2`)** | `PromptRegistry.registry_sha256` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| **Scientific Code Bundle (14 files)** | `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| **Portable Generation Schema V2** | `COMMON_PORTABLE_GENERATION_SCHEMA_V2` | `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490` |
| **Semantic Post-Validation Schema** | `PlannerBenchmarkItineraryOutput` | `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555` |
| **Candidate Registry (`C1`, `C2`, `C3`)** | `DevCandidateRegistry.registry_sha256` | `4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058` |
| **Provider Config Registry** | `compute_provider_config_registry_sha256` | `3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938` |
| **Final100 Scenarios Freeze (Forbidden)** | `data/evaluation/w06/w06_scenarios_freeze_v1.json` | `c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1` |
| **P11 Assignment Manifest (Forbidden)** | `data/evaluation/w06/w06_p11_assignment_manifest_v1.json` | `0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62` |

---

## 2. Phase Being Prepared

- **`PHASE`**: `DEV_TUNE`
- This preparation strictly scopes future authorization to **`DEV_TUNE` only** (`120` cells).
- It explicitly does **NOT** authorize:
  - `DEV_SELECT` (`dev_select_authorized = false`)
  - `STOCHASTICITY` (`stochasticity_authorized = false`)
  - `FINAL100` (`final100_authorized = false`)

---

## 3. Exact Candidate Models

| Candidate ID | Provider | Requested Model ID | Env Key Name | Technical Preflight V2 Status | Provider Config SHA256 | Sampling / Reasoning Config | Omitted Parameters | Cells in `DEV-TUNE` |
|---|---|---|---|---|---|---|---|---:|
| **`C1`** | `google` | `gemini-3.8-flash` | `GEMINI_API_KEY` | `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2` | `d4d417bdeff3f4156ac9605f976b46780c1cb0866d87674f1cee51d8bf3f3217` | `{"seed": 2026101508, "thinking_level": "medium"}` | `["temperature", "top_p", "top_k"]` | `40` |
| **`C2`** | `openai` | `gpt-6.1-sol` | `OPENAI_API_KEY` | `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2` | `6201244268383e85106b4d6e6ad0f503e066de9def361cbafa685227e8ba332e` | `{"reasoning_effort": "medium", "seed": 2026101508, "service_tier": "default"}` | `["temperature", "top_p", "top_k", "logprobs", "top_logprobs"]` | `40` |
| **`C3`** | `anthropic` | `claude-sonnet-5-5` | `ANTHROPIC_API_KEY` | `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2` | `5ecff5a4e2899245d1cd113285d1193dad17b6ed4e7521bd10be3937650d2a29` | `{"effort": "high", "thinking": {"type": "adaptive"}}` | `["temperature", "top_p", "top_k", "seed"]` | `40` |

---

## 4. Exact Prompt Authorities

| Prompt ID | `prompt_version` | Candidate Definition ID | System Prompt SHA256 | User Prompt Template SHA256 | Semantic Prompt SHA256 | Cells in `DEV-TUNE` |
|---|---|---|---|---|---|---:|
| **`P1`** | `TRAVEL_PLANNER_BENCHMARK_V2` | `TRAVEL_PLANNER_BENCHMARK_V2` (baseline) | `fcdf591b819d26fd4ba71fe89ca4d5d2f18a9614a0c42a31c9a0e4ed4c7be76b` | `30a7f08643106c0a170a83a27a4fb1ff6be6c37b01e9cf64ff58e5fb48421a4b` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` | `60` |
| **`P2`** | `TRAVEL_PLANNER_BENCHMARK_V2` | `W06_DEV_TUNE_CANDIDATE_P2_V1` | `e7a6d0e3c78222114cf010ab0e1f27848b35e788fb25d27d60a10d50410fd880` | `30a7f08643106c0a170a83a27a4fb1ff6be6c37b01e9cf64ff58e5fb48421a4b` | `0679dd9463d6cebf04ccb5571a403331eea3ab6819bd6a0e8b2ee1fc08c99fdf` | `60` |

- **Controlled Experiment Parity:**
  - Across all 20 `DEV-TUNE` fixtures (`W06-DEV-TUNE-001`..`W06-DEV-TUNE-020`), `rendered_user_prompt_P1 == rendered_user_prompt_P2` (`all_20_rendered_user_prompts_byte_identical = true`).
  - For `W06-DEV-TUNE-001`, both `P1` and `P2` have `user_prompt_sha256 = c632a1f607203a81c9422164a7910c5f82211437d74af9c91bb6b370c1da3c17`.
  - Across all 60 `(fixture_id, candidate_id)` cell pairs in `w06_dev_tune_execution_plan_v1.json`, the only differing manifest fields between `P1` and `P2` are `["prompt_id", "run_id", "system_prompt_sha256"]`.

---

## 5. Exact Experiment Matrix

- **Fixtures:** `20` (`W06-DEV-TUNE-001` through `W06-DEV-TUNE-020`)
- **Prompts:** `2` (`P1`, `P2`)
- **Candidates:** `3` (`C1`, `C2`, `C3`)
- **Attempts per cell:** `1`
- **Total cells:** `20 × 2 × 3 × 1 = 120`
  - **Cells per prompt:** `P1 = 60`, `P2 = 60`
  - **Cells per candidate:** `C1 = 40`, `C2 = 40`, `C3 = 40`
  - **Cells per fixture:** `6` (`P1×C1`, `P1×C2`, `P1×C3`, `P2×C1`, `P2×C2`, `P2×C3`)

---

## 6. Call Budget Policy

| Policy Parameter | Frozen Value |
|---|---|
| `maximum_live_generation_calls` | `120` |
| `reserve_calls_beyond_120` | `0` |
| `retry_calls` | `0` |
| `diagnostic_calls` | `0` |
| `dev_select_calls` | `0` |
| `stochasticity_calls` | `0` |
| `final100_calls` | `0` |
| `max_outbound_http_requests_per_cell` | `1` |
| `no_hidden_calls` | `true` |

When the Project Owner later grants live authorization, `DevLiveAuthorizationArtifact` must bind:
- `allowed_phase = "DEV_TUNE"`
- `maximum_live_generation_calls = 120`
- `allowed_candidate_ids = ["C1", "C2", "C3"]`
- `allowed_execution_plan_sha256 = "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"`
- `allowed_prompt_freeze_sha256 = "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"`

---

## 7. Retry / Repair / Fallback / Failure Policy

### 7.1 Execution Constraints
- `attempt_number = 1`
- `sdk_retry = 0`
- `transport_retry = 0`
- `manual_retry = 0`
- `automatic_retry = 0`
- `fallback = false`
- `best_of = false`
- `llm_repair = 0`
- `deterministic_semantic_repair = false`
- `tools = false`
- No cell may be retried until success.

### 7.2 Ordinary Provider / Validation Failures (Denominator-Preserving)
The following 10 failure classes count in the denominator (`N = 60` per prompt / `N = 20` per `(prompt, candidate)` slice) with `VALID_RUN_AND_SCHEMA = false`, `EXACT_GROUNDING_PASS = false`, `FINAL_CORE_PASS = false`, and `retry = 0`:
1. `HTTP_429`
2. `HTTP_5XX`
3. `TIMEOUT`
4. `PARTIAL_TIMEOUT`
5. `AUTHENTICATION_FAILURE`
6. `MODEL_ACCESS_FAILURE`
7. `MALFORMED_JSON`
8. `SEMANTIC_VALIDATION_FAILURE`
9. `REFUSAL`
10. `MAX_TOKEN_TRUNCATION`

### 7.3 Batch-Fatal Integrity Failures (Immediate Fail-Closed Stop)
The following 8 integrity failures trigger an immediate fail-closed batch stop (`batch_stop_required = true`, never silently absorbed into the denominator):
1. `MODEL_INTEGRITY_MISMATCH`
2. `HARNESS_INTERNAL_ERROR`
3. `SCIENTIFIC_CODE_BUNDLE_MISMATCH`
4. `PROVIDER_CONFIG_MISMATCH`
5. `PROMPT_FREEZE_INTEGRITY_FAILURE`
6. `EXECUTION_PLAN_INTEGRITY_FAILURE`
7. `AUTHORIZATION_INTEGRITY_FAILURE`
8. `STAGE_A_INTEGRITY_FAILURE`

---

## 8. Candidate-Aware Pricing Evidence

Pricing evidence is extracted offline from the repository's two frozen pricing authorities (`data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json` verified `2026-10-17` and `DEFAULT_COST_COMPARABILITY_BY_CANDIDATE` in `apps/ai-service/app/evaluation/dev_live_runner.py` verified `2026-10-16`):

| Candidate | Pricing Source | Pricing Checked At (UTC) | Phase 01D Price Basis (per 1M tokens) | Runner Registry Price Basis (per 1M tokens) | Conservative Envelope Basis (Elementwise Max) | Reasoning / Thought Billing Treatment | Cache Billing Treatment |
|---|---|---|---|---|---|---|---|
| **`C1` (`google / gemini-3.8-flash`)** | `https://ai.google.dev/gemini-api/docs/pricing` (`w06_model_preflight_01d_v2_live_receipt_v1.json`) | `2026-10-17T00:00:00Z` | Input: `\$0.75` / Output+Thought: `\$3.75` | Input: `\$0.30` / Output+Thought: `\$2.50` | Input: `\$0.75` / Output+Thought: `\$3.75` | `candidates_token_count` and `thoughts_token_count` are reported **disjointly**; billable output = `output_tokens + thought_tokens` (`OUTPUT_AND_THOUGHT_DISJOINT_SUMMED_AT_OUTPUT_RATE`). | No explicit context caching configured; any provider-automatic cached tokens are recorded in `cached_input_tokens` and never subtracted from input cost unless verified. |
| **`C2` (`openai / gpt-6.1-sol`)** | `https://platform.openai.com/docs/pricing` (`w06_model_preflight_01d_v2_live_receipt_v1.json`) | `2026-10-17T00:00:00Z` | Input: `\$2.00` / Output: `\$10.00` | Input: `\$2.50` / Output: `\$10.00` | Input: `\$2.50` / Output: `\$10.00` | `output_tokens_details.reasoning_tokens` is a **subset** of `output_tokens` (`REASONING_SUBSET_OF_OUTPUT_BILLED_AT_OUTPUT_RATE`, avoiding double-counting). | No explicit prompt caching configured; automatic prefix cache hits reported in `input_tokens_details.cached_tokens` are conservatively costed at full uncached input rate in pre-run budgeting. |
| **`C3` (`anthropic / claude-sonnet-5-5`)** | `https://docs.anthropic.com/en/docs/about-claude/pricing` (`w06_model_preflight_01d_v2_live_receipt_v1.json`) | `2026-10-17T00:00:00Z` | Input: `\$2.00` / Output: `\$10.00` | Input: `\$3.00` / Output: `\$15.00` | Input: `\$3.00` / Output: `\$15.00` | Adaptive thinking tokens are included in `usage.output_tokens` and billed at the standard output token rate (`ADAPTIVE_THINKING_INCLUDED_IN_OUTPUT_TOKENS_AT_OUTPUT_RATE`). | No `cache_control` breakpoints configured (`cache_creation_input_tokens = 0`, `cache_read_input_tokens = 0` expected). |

> [!NOTE]
> Under the frozen method lock (`W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01` Section 8.2), `DEV-TUNE` prompt selection (`P1` vs `P2`) depends strictly on `VALID_RUN_AND_SCHEMA_RATE`, `EXACT_GROUNDING_PASS_RATE`, `FINAL_CORE_PASS_RATE`, and `P1` conservative tie-retention. Cost is **never** used as a criterion in `DEV-TUNE` prompt selection.

---

## 9. Conservative Cost Envelope (`ESTIMATED_EXPECTED_COST` vs `HARD_MAX_COST`)

Across the 20 `DEV-TUNE` fixtures, the rendered user prompt size ranges from `40,417` to `74,586` UTF-8 bytes (mean `55,314` bytes; total `1,106,286` bytes across 20 fixtures), and the system prompt is `263` bytes (`P1`) or `951` bytes (`P2`).

| Envelope Quantity | Value | Basis & Scientific Honesty Justification |
|---|---|---|
| **`ESTIMATED_EXPECTED_COST_USD`** | **`\$4.88 - \$9.82 USD`** (`CONSERVATIVE_AUTHORIZATION_PLANNING_RANGE`) | Computed across `120` cells (`40` cells per candidate, `retry = 0`) using the elementwise maximum price basis (`C1: \$0.75/\$3.75`, `C2: \$2.50/\$10.00`, `C3: \$3.00/\$15.00` per 1M tokens) under 8,000–14,000 input tokens and 2,500–5,500 billable output+thinking tokens per cell (`C1: \$0.62–\$1.25`, `C2: \$1.80–\$3.60`, `C3: \$2.46–\$4.98`). |
| **`HARD_MAX_COST_USD`** | **`NOT_DEFENSIBLY_COMPUTABLE`** | Exact pre-execution token counts require provider-proprietary tokenizers (which cannot be called offline) and provider-internal structured-output grammar injection into `input_tokens`; furthermore, in `C1` (`google / gemini-3.8-flash`) `thoughts_token_count` is billed disjointly from `candidates_token_count` (`billable_output_tokens = output_tokens + thought_tokens`). Therefore an unconditional deterministic `HARD_MAX_COST` is reported as `NOT_DEFENSIBLY_COMPUTABLE` to prevent false precision. (For reference only, a conditional 16,384-token total billable-output cap at 16,000 input tokens per cell corresponds to `\$23.34 USD` across 120 cells.) |

---

## 10. Secret-Free Key Presence Check

Key presence was checked offline without printing, logging, hashing, or persisting any secret value, length, prefix, or suffix:

| Environment Variable | Local Workstation Status | CI Offline Requirement |
|---|---|---|
| `GEMINI_API_KEY` | `PRESENT` | Not required (`MISSING` allowed in offline CI) |
| `OPENAI_API_KEY` | `PRESENT` | Not required (`MISSING` allowed in offline CI) |
| `ANTHROPIC_API_KEY` | `PRESENT` | Not required (`MISSING` allowed in offline CI) |

---

## 11. Live Readiness Matrix

| Readiness Item | Status |
|---|---|
| `prompt_freeze` (`2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956`) | `READY` |
| `dev_tune_plan` (`582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae`) | `READY` |
| `runner` (`dev_live_runner.py` + `w06_dev_live_runner_01_receipt_v1.json`) | `READY` |
| `runner_qa` (`w06_dev_live_runner_qa_01_receipt_v1.json`, `60/60 PASS`) | `READY` |
| `candidate_registry` (`C1`, `C2`, `C3`) | `READY` |
| `provider_configs` (`3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938`) | `READY` |
| `schema_v2` (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`) | `READY` |
| `scientific_bundle` (`0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`) | `READY` |
| `final100_firewall` | `READY` |
| **`all_scientific_prereqs`** | **`READY`** |
| **`authorization_state`** | **`NOT_YET_GRANTED`** |
| **`stage_a_state`** | **`NOT_YET_CREATED`** |
| **`key_presence` (local operational status)** | `GEMINI_API_KEY=PRESENT`, `OPENAI_API_KEY=PRESENT`, `ANTHROPIC_API_KEY=PRESENT` |

---

## 12. Pre-Authorization Firewall Verification

| Firewall Invariant | Observed Value |
|---|---|
| `LIVE_AUTHORIZATION_ARTIFACT_CREATED` | `false` |
| `STAGE_A_RECEIPT_CREATED` | `false` |
| `TRANSPORT_JOURNAL_CREATED` | `false` |
| `PROVIDER_RESULT_DIRECTORIES_CREATED` | `false` |
| `LIVE_PROVIDER_CALLS` | `0` |
| `PROVIDER_COST_USD` | `0.0` |

---

## 13. Proposed Project Owner Authorization Text

- **`PROJECT_OWNER_AUTHORIZATION_STATUS`**: `NOT_GRANTED`
- **Proposed Authorization Sentence (for future Project Owner decision only):**

> `"I authorize W06 DEV-TUNE live execution for exactly the frozen 120-cell plan 582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae, using frozen prompt artifact 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956, candidates C1/C2/C3, maximum 120 generation calls, zero retry, no DEV-SELECT, no stochasticity, and no Final100."`

---

## 14. Verification Summary (`AP-01` through `AP-30`)

All 30 offline authorization-preparation checks executed under the outbound-network kill-switch (`NetworkKillSwitchGuard`) passed (`30/30 PASS`, `0 FAIL`):

| Check ID | Domain | Description | Status |
|---|---|---|---|
| `AP-01` | `SOURCE_STATE` | Source `develop` SHA `443634e1f7583f334dec0315bb3816d249feb124` exists and is ancestor of `HEAD` | `PASS` |
| `AP-02` | `FROZEN_AUTHORITIES` | Prompt freeze artifact SHA256 matches `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` and passes runner/harness validation | `PASS` |
| `AP-03` | `FROZEN_AUTHORITIES` | `DEV-TUNE` execution plan SHA256 matches `582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae` | `PASS` |
| `AP-04` | `FROZEN_AUTHORITIES` | Persisted `DEV-TUNE` execution plan file SHA256 matches `652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74` | `PASS` |
| `AP-05` | `SCIENTIFIC_CODE_BUNDLE` | 14-file scientific code bundle SHA256 matches `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` | `PASS` |
| `AP-06` | `PHASE_SCOPE` | Prepared phase is strictly `DEV_TUNE` across prep artifact and all 120 plan cells | `PASS` |
| `AP-07` | `CANDIDATE_MODELS` | Candidate models are exactly `C1` (`google/gemini-3.8-flash`), `C2` (`openai/gpt-6.1-sol`), `C3` (`anthropic/claude-sonnet-5-5`) | `PASS` |
| `AP-08` | `PROMPT_AUTHORITIES` | Prompts are exactly `P1` and `P2` with frozen semantic SHA256s, registry SHA256, and rendered user prompt parity across all 20 fixtures | `PASS` |
| `AP-09` | `EXPERIMENT_MATRIX` | `DEV-TUNE` fixture list is exactly the 20 frozen `W06-DEV-TUNE-001`..`020` scenarios | `PASS` |
| `AP-10` | `EXPERIMENT_MATRIX` | Experiment matrix is 20 fixtures × 2 prompts × 3 candidates × 1 attempt = 120 unique assigned cells | `PASS` |
| `AP-11` | `CALL_BUDGET_POLICY` | Maximum live generation calls is 120 with zero reserve/retry/diagnostic calls and at most 1 HTTP request per cell | `PASS` |
| `AP-12` | `EXECUTION_POLICY` | `attempt_number=1` and all retry counters (`sdk`, `transport`, `manual`, `automatic`) equal `0` across policy and all 120 cells | `PASS` |
| `AP-13` | `EXECUTION_POLICY` | `fallback=false` and `best_of=false` across policy and all 120 cells | `PASS` |
| `AP-14` | `EXECUTION_POLICY` | `llm_repair=0` and `deterministic_semantic_repair=false` across policy and all 120 cells | `PASS` |
| `AP-15` | `EXECUTION_POLICY` | `tools=false` across policy and all 120 cells | `PASS` |
| `AP-16` | `FAILURE_POLICY` | All 10 ordinary provider/validation failures remain denominator-preserving with zero retry | `PASS` |
| `AP-17` | `FAILURE_POLICY` | All 8 batch-fatal integrity failures trigger immediate fail-closed batch stop | `PASS` |
| `AP-18` | `PHASE_FIREWALL` | Preparation does NOT authorize or start `DEV_SELECT` | `PASS` |
| `AP-19` | `PHASE_FIREWALL` | Preparation does NOT authorize or start `STOCHASTICITY` | `PASS` |
| `AP-20` | `FINAL100_FIREWALL` | Preparation does NOT authorize or use `Final100` | `PASS` |
| `AP-21` | `PRE_AUTHORIZATION_FIREWALL` | No `DevLiveAuthorizationArtifact`, `authorization_id`, or `AUTHORIZED` status exists | `PASS` |
| `AP-22` | `PRE_AUTHORIZATION_FIREWALL` | No Stage-A freeze receipt, transport journal, or live cell result directory exists | `PASS` |
| `AP-23` | `AUTHORIZATION_STATUS` | `project_owner_authorization_status` is `NOT_GRANTED`, scientific prereqs are `READY`, authorization is `NOT_YET_GRANTED`, Stage-A is `NOT_YET_CREATED` | `PASS` |
| `AP-24` | `OWNER_AUTHORIZATION_TEXT` | Proposed Project Owner authorization sentence contains exact plan and prompt freeze SHA256s and all scope constraints | `PASS` |
| `AP-25` | `SECRET_HYGIENE` | Key presence records strictly `PRESENT`/`MISSING` without any secret values or hashes | `PASS` |
| `AP-26` | `NETWORK_ISOLATION` | Zero outbound network calls and zero live provider calls occurred | `PASS` |
| `AP-27` | `PRICING_EVIDENCE` | Explicit provider pricing evidence and candidate-aware billing treatment recorded for `C1`, `C2`, and `C3` | `PASS` |
| `AP-28` | `COST_ENVELOPE` | Cost envelope distinguishes `ESTIMATED_EXPECTED_COST` range from `HARD_MAX_COST = NOT_DEFENSIBLY_COMPUTABLE` without false precision | `PASS` |
| `AP-29` | `SCIENTIFIC_CODE_BUNDLE` | All 14 production scientific files are 100% byte-for-byte unchanged | `PASS` |
| `AP-30` | `FINAL100_FIREWALL` | `Final100` scenarios freeze and `P11` assignment manifest are untouched and unused | `PASS` |
