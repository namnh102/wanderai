# W06 DEV-SELECT Execution-Environment Amendment 01 Preparation (`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP`)

## 1. Governance & Authority Firewall

- **Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP`
- **Artifact ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP-V1`
- **Authoritative Base (`develop`):** `811255a7dd00234d63184ab483e9f88b1f2d8554`
- **Prep Artifact Path:** `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_prep_v1.json`
- **Prep Artifact File SHA256 (LF):** `21ad72d89a35af7b4607ecd941a5873e7cd60d7e5c54621729d01e6954dfcc11`
- **Prep Artifact Internal SHA256:** `57794e675d4b279bc875762a000ce74a07173a181afbdb31d0149f01f94b53c9`
- **Scientific Code Bundle SHA256:** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` (unchanged)
- **Final Methodology Decision Authority:** `CHATGPT`

> [!IMPORTANT]
> This document and its companion JSON artifact **prepare** a methodology-amendment proposal only.
> - `AMENDMENT_APPROVED = false`
> - `AMENDED_LIVE_AUTHORIZED = false`
> - `AMENDED_LIVE_EXECUTED = false`
> - `MODEL_WINNER_SELECTED = false` (`SELECTED_MODEL_ID = null`)
> - `STOCHASTICITY_EXECUTION_STARTED = false`
> - `FINAL100_USED = false`
> - `LIVE_PROVIDER_CALLS_NEW = 0`

---

## 2. Primary Experiment Immutability

The existing 180-cell DEV-SELECT execution (`W06-DEV-SELECT-LIVE-EXECUTION-01`) is permanently preserved and classified as:

- **`PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK`**

### Cryptographic Bindings to Frozen Primary Evidence
- `RAW_EVIDENCE_TREE_SHA256 = d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817` (`1629` files, `16,264,062` bytes)
- `RESULTS_MANIFEST_FILE_SHA256 = 1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0`
- `RESULTS_FREEZE_RECEIPT_FILE_SHA256 = c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4`
- `DIAGNOSTIC_ARTIFACT_FILE_SHA256 = b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692`
- `DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256 = 509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8`

### Immutability Rules
1. Primary cells are **never** rerun, replaced, or deleted.
2. Primary per-candidate denominators remain strictly `60` (`C1 = 60`, `C2 = 60`, `C3 = 60`; total `180`).
3. Primary failure classifications (`execution_receipt.failure_classification`) remain unchanged (`HTTP_429 = 35`, `HTTP_5XX = 10`, `HTTP_ERROR = 60`, `NONE = 9`, `TIMEOUT = 66`).
4. The primary benchmark remains valid and reportable as the preregistered 55-second one-shot operational benchmark.

---

## 3. Evidence-Supported Reasons for Considering an Amendment

All reasons below are strictly derived from the frozen primary evidence and verified diagnostic (`W06-DEV-SELECT-FAILURE-DIAGNOSTIC-V1`):

### 3.1 Candidate C1 (`google / gemini-3.8-flash`)
- **`35/60` (`HTTP_429`):** 100% (`35/35`) are provider-declared Google Gemini API Free Tier daily request quota exhaustion (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quota_value = 20` requests/day on `generativelanguage.googleapis.com/generate_content_free_tier_requests`, latency `1,157.0..3,797.0 ms`).
- **`10/60` (`HTTP_5XX`):** 100% (`10/10`) are provider-declared `HTTP 503 UNAVAILABLE` high-demand/capacity failures (`"This model is currently experiencing high demand..."`, latency `1,828.0..43,812.0 ms`).
- **`14/60` (`TIMEOUT`):** Consists of `4` client `ReadTimeout` cells (`55,781.0..56,016.0 ms`, `4/4` within `[55,000, 57,000] ms`) and `10` provider `HTTP 504 DEADLINE_EXCEEDED` cells (`53,031.0..55,891.0 ms`, `9/10` within `[54,000, 57,000] ms`).
- **`1/60` (`NONE`):** `W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026` completed (`46,688.0 ms`, `2-day` scenario) and passed schema, grounding, and core evaluation.

### 3.2 Candidate C2 (`openai / gpt-6.1-sol`)
- **`52/60` (`TIMEOUT`):** 100% (`52/52`) are client `APITimeoutError: Request timed out.` with latencies `55,078.0..55,797.0 ms` (`median = 55,132.5 ms`), 100% clustered immediately above the frozen `55,000 ms` timeout authority.
- **`8/60` (`NONE`):** All `8` completed cells passed schema, grounding, and core evaluation with latencies `35,812.0..53,094.0 ms` (`median = 45,898.5 ms`).
- **Scenario-Duration Truncation Pattern:** All `8/8` completed C2 cells were `2-day` scenarios (`days == 2`); `0/20` `3-day` scenarios and `0/20` `4-day` scenarios completed before the `55,000 ms` cutoff.

### 3.3 Candidate C3 (`anthropic / claude-sonnet-5-5`)
- **`60/60` (`HTTP_ERROR`):** 100% (`60/60`) failed with `HTTP 400 invalid_request_error` (`latency 594.0..2,609.0 ms`).
- **Provider-Declared Cause:** 100% (`60/60`) explicitly state: `"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."`
- **Zero Model Observability:** `0/60` C3 model generations were observed.

### 3.4 Harness & Binding Integrity Verification
- `REQUEST_IDENTITY_MATCH = 180/180`
- `CELL_HASH_CHAIN_VALID = 180/180`
- `RETRY_CALLS = 0`
- `RERUN_CELLS = 0`
- `MODEL_ID_MISMATCH_COUNT = 0`
- `HARNESS_OR_BINDING_INCONSISTENCY_OBSERVED = false`

---

## 4. Amendment Classification

If approved by ChatGPT, the amended execution is classified strictly as:

- **`SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK`**

It **must not** be described as:
- a replacement of the primary benchmark,
- a retroactive preregistration,
- a correction of primary results,
- a rerun of failed cells, or
- a continuation of the same primary batch.

Both tracks remain reportable in the thesis: the primary track documents strict preregistered 55s one-shot operational behavior, and the secondary stabilization track evaluates comparative planner quality under verified account provisioning and relaxed transport deadlines.

---

## 5. Amendment Scope Boundary (Frozen Scientific Invariants)

Unless ChatGPT explicitly amends them in a subsequent decision gate, all core scientific variables remain strictly frozen:

| Scientific Dimension | Frozen Authority | Proposed Change? |
|---|---|---|
| Selected Prompt | `P1` (`2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956`) | **No** (`prompt_retuning_proposed = false`) |
| Candidate C1 | `google / gemini-3.8-flash` (`seed=2026101508`, `thinking_level=medium`) | **No** |
| Candidate C2 | `openai / gpt-6.1-sol` (`seed=2026101508`, `reasoning_effort=medium`, `service_tier=default`) | **No** |
| Candidate C3 | `anthropic / claude-sonnet-5-5` (`effort=high`, `thinking=adaptive`) | **No** |
| Fourth Model Addition | Forbidden | **No** (`fourth_model_addition_proposed = false`) |
| Portable Generation Schema V2 | `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490` | **No** |
| Semantic Schema | `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555` | **No** |
| Evaluator Semantics | `planner_benchmark_evaluator.py` | **No** |
| Primary Selection Metrics | `VALID_RUN_AND_SCHEMA_RATE`, `EXACT_GROUNDING_PASS_RATE`, `FINAL_CORE_PASS_RATE` | **No** |
| Practical-Tie Survivor Rule | `0.10` (`10` percentage points / `6/60` cells) | **No** |
| Final100 Calibration Usage | Forbidden (`w06_scenarios_freeze_v1.json`) | **No** (`final100_used = false`) |

---

## 6. Execution-Environment Factors Under Review & Timeout Evidence Analysis (Sections 6 & 8)

### 6.1 Factor A: Provider Readiness & Account Provisioning
- **C1 (`Google`):** Paid tier / billing linkage and daily/per-minute quota sufficient for the planned C1 batch (`>=60..63` calls), eliminating the 20 RPD Free Tier ceiling.
- **C2 (`OpenAI`):** Confirm active billing credit balance and tier limits for `gpt-6.1-sol` (primary DEV-SELECT evidenced `0/60` billing/quota errors on C2, but higher timeout ceilings will allow more cells to complete and bill output tokens).
- **C3 (`Anthropic`):** Active billing and positive credit balance sufficient for the planned C3 batch (`>=60..63` calls), eliminating the `60/60` HTTP 400 credit balance rejection.

### 6.2 Factor B & Section 8: Request Timeout Policy Decision-Support Table

#### Frozen Primary Latency Evidence
- **C2 `NONE` (`n = 8`, all `2-day` trips):** `min = 35,812.0 ms`, `median = 45,898.5 ms`, `max = 53,094.0 ms`.
- **C2 `TIMEOUT` (`n = 52`, including `12/20` `2-day`, `20/20` `3-day`, `20/20` `4-day` trips):** `min = 55,078.0 ms`, `median = 55,132.5 ms`, `max = 55,797.0 ms` (`52/52` in `[55,000, 57,000] ms`).
- **C1 `NONE` (`n = 1`, `2-day` trip):** `46,688.0 ms`.
- **C1 `TIMEOUT` (`n = 14`):** `4` client `ReadTimeout` (`55,781.0..56,016.0 ms`) and `10` server `HTTP 504 DEADLINE_EXCEEDED` (`53,031.0..55,891.0 ms`; `1` in `<54,000 ms`, `8` in `[54,000, 55,000) ms`, `5` in `[55,000, 57,000] ms`).

> [!WARNING]
> **Counterfactual Firewall:**
> - **Permitted Statement (FACT / DERIVED PATTERN):** `55 seconds demonstrably censors many C2 requests at the configured boundary.`
> - **Forbidden Claim (NOT SUPPORTED):** Do **not** estimate counterfactual completion rates (e.g., `"120 seconds would yield X/60"`) or claim that any timeout value `"guarantees success"`.

| Option ID | Timeout | Worst-Case 180-Cell Unpaced | Worst-Case 180-Cell (+2s Pacing) | Worst-Case 189-Cell (+2s Pacing) | Worst-Case 90-Cell (+2s Pacing) | Censoring Risk | Stuck-Request Risk | Scientific & Engineering Rationale |
|---|---:|---:|---:|---:|---:|---|---|---|
| `T0_BASELINE_55S` | `55 s` (`55,000 ms`) | `2.75 h` (`9,900 s`) | `2.85 h` (`10,258 s`) | `2.99 h` (`10,771 s`) | `1.42 h` (`5,128 s`) | `DEMONSTRATED_HIGH` (`52/60` C2, `14/60` C1) | `LOW` | Frozen primary baseline; severely truncates 3-day and 4-day structured itinerary generation (`0/40` C2 3..4 day completions). |
| `T1_CANDIDATE_90S` | `90 s` (`90,000 ms`) | `4.50 h` (`16,200 s`) | `4.60 h` (`16,558 s`) | `4.83 h` (`17,386 s`) | `2.30 h` (`8,278 s`) | `MODERATE_TO_HIGH` | `LOW_TO_MODERATE` | Adds `+35 s` (`+63.6%`) headroom above `55 s`, but because C2 2-day trips already reached `53.1 s`, 4-day trips with medium/high reasoning may still exceed `90 s`. |
| `T2_CANDIDATE_120S` | `120 s` (`120,000 ms`) | `6.00 h` (`21,600 s`) | `6.10 h` (`21,958 s`) | `6.40 h` (`23,056 s`) | `3.05 h` (`10,978 s`) | `MODERATE_LOW` | `MODERATE` | More than doubles (`+118.2%`) the 55s cutoff, providing substantial headroom for 3-day and 4-day JSON generation while bounding worst-case 180-cell runtime to `~6.1 h`. |
| `T3_CANDIDATE_180S` | `180 s` (`180,000 ms`) | `9.00 h` (`32,400 s`) | `9.10 h` (`32,758 s`) | `9.55 h` (`34,396 s`) | `4.55 h` (`16,378 s`) | `LOW_CLIENT_SIDE` | `MODERATE_HIGH` | Provides `3.27x` (`+125 s`) client-side headroom for large `16,384` max-token structured outputs and adaptive/medium reasoning across all 2..4 day scenarios. (Upstream provider 504 gateway deadlines remain provider-controlled.) |
| `T4_OPTIONAL_UPPER_BOUND_240S` | `240 s` (`240,000 ms`) | `12.00 h` (`43,200 s`) | `12.10 h` (`43,558 s`) | `12.70 h` (`45,736 s`) | `6.05 h` (`21,778 s`) | `VERY_LOW_CLIENT_SIDE` | `HIGH` | Upper-bound reference only if extreme client headroom is desired; diminishing return over `180 s` due to upstream provider gateway timeouts. |

### 6.3 Factor C: Pacing Policy Options (Non-Adaptive, Deterministic, `retry = 0`)
- **`P0_UNPACED_INTERLEAVED_C1_C2_C3` (`0 ms` delay):** Retains current `C1 -> C2 -> C3` ordering with `0 ms` sleep. Natural spacing exists when all 3 providers take `20..50 s`, but collapses if two providers fail rapidly.
- **`P1_FIXED_2000MS_INTER_CALL_DELAY` (`2,000 ms` delay):** Unconditional fixed `2.0 s` pause between consecutive cells (`+358 s` = `5.97 min` across `180` cells), guaranteeing `>=6.0 s` same-provider spacing even if two providers fail instantaneously.
- **`P2_FIXED_5000MS_INTER_CALL_DELAY` (`5,000 ms` delay):** Unconditional fixed `5.0 s` pause between consecutive cells (`+895 s` = `14.92 min` across `180` cells), guaranteeing `>=15.0 s` (`<=4 RPM`) same-provider spacing.

### 6.4 Factor D: Retry Policy Options
- **`R0_STRICT_ZERO_RETRY` (`retry = 0`, Default Proposed):** Preserves the single-attempt per-cell invariant (`automatic_retry = 0`, `transport_retry = 0`, `llm_repair = 0`, `manual_retry = 0`, `fallback = false`).
- **`R1_BOUNDED_TRANSPORT_RETRY_ALTERNATIVE` (`retry = 1`):** Marked **`NOT_RECOMMENDED_WITHOUT_MAJOR_METHODOLOGY_CHANGE`**.

---

## 7. Pre-Live Provider-Readiness Attestation Design

Before any amended comparative live batch is authorized, a dedicated pre-live readiness gate (`W06-DEV-SELECT-AMENDED-PRE-LIVE-PROVIDER-READINESS-GATE-V1`) must verify:

1. **C1 (`Google / gemini-3.8-flash` — `OWNER_ACTION_REQUIRED`):**
   - `GEMINI_API_KEY` boolean presence (`PRESENT`), without printing or hashing secret material.
   - Project/account billing linkage attested as Paid Tier (`billing_tier_status = PAID_TIER_ATTESTED`) without disclosing sensitive project/account IDs.
   - Daily quota (`RPD`) and rate limits (`RPM`/`TPM`) attested above planned C1 call volume (no `20 RPD` Free Tier ceiling).
2. **C2 (`OpenAI / gpt-6.1-sol` — `OWNER_ACTION_REQUIRED`):**
   - `OPENAI_API_KEY` boolean presence (`PRESENT`).
   - Active billing credit balance sufficient for planned C2 calls under extended timeout ceiling.
   - Model access verified for `gpt-6.1-sol`.
3. **C3 (`Anthropic / claude-sonnet-5-5` — `OWNER_ACTION_REQUIRED`):**
   - `ANTHROPIC_API_KEY` boolean presence (`PRESENT`).
   - Active billing and positive credit balance (`credit_balance_status = POSITIVE_SUFFICIENT_FOR_BATCH`), resolving the `60/60` HTTP 400 credit rejection.
   - Model access verified for `claude-sonnet-5-5`.

---

## 8. Fairness Policy Options (Section 9)

| Option ID | Summary | Advantages | Scientific Weaknesses | Engineering Weaknesses | Cost Implications | Defense / Thesis Implications | Risk to Final100 Quality |
|---|---|---|---|---|---|---|---|
| **`OPTION_A_MINIMAL_ENVIRONMENT_REPAIR`** | Fix provider billing/quota + raise timeout to one fixed candidate value (`e.g. 120s/180s`); unpaced `P0`; `retry=0`; same `P1`, `C1..C3`, and metrics. | Minimal change relative to primary run; isolates billing/quota and timeout truncation directly. | Secondary post-hoc track requires dual reporting; no inter-call spacing if a provider fails fast. | Does not smooth burst request cadence against `HTTP 503` high-demand spikes. | `S1 (180 calls)`: `$12.357` LOW to `$24.03` HIGH (runner registry pricing). | Clear parsimonious contrast between 55s primary run and repaired environment. | `LOW_TO_MODERATE` |
| **`OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT`** | Fix provider billing/quota + pre-live readiness attestation + stronger timeout ceiling (`e.g. 180s`) + fixed deterministic pacing (`e.g. 2.0s`); `retry=0`. | Addresses quota/billing, timeout truncation, and burst pacing symmetrically across all 3 candidates; prevents launching against unprovisioned accounts. | Combines timeout relaxation and fixed pacing in one stabilization track. | Adds `~6..15 min` deterministic pacing overhead and longer wait on hung sockets. | `S2 (189 calls)`: `$12.97485` LOW to `$25.2315` HIGH (runner registry pricing). | Strongest defense: systematic diagnosis followed by pre-attested, fair stabilization before Final100. | `LOW` |
| **`OPTION_C_NO_AMENDED_COMPARATIVE_BENCHMARK`** | Accept primary `180`-cell results as sole comparative basis; select winner under original rules; stabilize environment only after winner selection. | `$0.00` additional DEV-SELECT spend; zero secondary comparative runs. | **Severe:** selects winner with `0/60` C3 generations, `35/60` C1 Free Tier 429s, and `52/60` C2 55s timeouts (`0/40` on 3..4 day trips). | Multi-day itinerary generation remains unverified before Final100. | `$0.00` now, but high risk of wasted spend or failure in Stochasticity / Final100. | Difficult to defend claiming comparative model selection when C3 never generated a single token. | `HIGH` |

---

## 9. Dataset / Fixture Policy Analysis (Section 10)

All options strictly forbid reading, inspecting, or calibrating on `Final100` (`data/evaluation/w06/w06_scenarios_freeze_v1.json`).

| Policy ID | Fixture Specification | Post-Hoc Bias Risk | Comparability to Primary | Overfitting Risk | Final100 Leakage Risk | Implementation Complexity |
|---|---|---|---|---|---|---|
| **`POLICY_F1_REUSE_EXISTING_DEV_SELECT_60`** | Reuse exact `60` `DEV-SELECT` fixtures (`W06-DEV-SELECT-001..060`). | `LOW` (no prompt, model, or schema change; only environment stabilization). | `HIGHEST` (`1-to-1` across all 60 scenarios and exact marginal balance). | `VERY_LOW` (`P1` and models remain frozen). | `ZERO` | `LOW` |
| **`POLICY_F2_SECONDARY_STABILIZATION_FROM_NON_FINAL_FROZEN_DEV`** | Construct a `30`-fixture stratified subset from `w06_dev_fixtures_freeze_v1.json` (`DEV-TUNE` / `DEV-SELECT`). | `LOW_TO_MODERATE` (requires a post-hoc subset selection rule). | `LOWER` (loses 1-to-1 cell correspondence and halves sample size). | `LOW` (overlaps with `DEV-TUNE` stochasticity fixtures if `DEV-TUNE` is used). | `ZERO` | `MODERATE` |
| **`POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET`** | Stage 1: `3` deterministic readiness canary fixtures (`2/3/4` days from `DEV-TUNE` or `W06-PREFLIGHT-SMOKE-001`, `3..9` calls, zero selection weight) + Stage 2: exact `60` `DEV-SELECT` comparative fixtures (`180` calls). | `LOW` (Stage 1 is binary readiness verification; Stage 2 is full `DEV-SELECT-60`). | `HIGHEST` (`1-to-1` on all `60` comparative scenarios). | `VERY_LOW` (canary cannot alter prompts, schemas, or models). | `ZERO` | `LOW_TO_MODERATE` |

---

## 10. Call-Budget Options & Cost Planning (Sections 11 & 12)

### 10.1 Call-Budget Alternatives
- **`S1_FULL_COMPARATIVE_180`:** `3 candidates × 60 comparative cells = 180 calls` (`0` canary calls). High statistical power (`n = 60`/candidate); moderate operational risk if an account issue is discovered mid-batch.
- **`S2_READINESS_CANARY_PLUS_COMPARATIVE_180`:** `3..9 engineering readiness canary calls + 180 comparative cells = 183..189 calls max`. Highest scientific and operational confidence; halts at `<=9` calls if any provider readiness check fails.
- **`S3_REDUCED_STRATIFIED_COMPARATIVE_90`:** `3 candidates × 30 stratified comparative cells = 90 calls`. Halves cost and runtime (`0.50x`), but increases binomial sampling variance (`1 cell = 3.33%` vs `1.67%`).

### 10.2 Cost Planning Envelopes & Pricing Status
- **Current Price Input Status:** `EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION`
- **Hard Maximum Claimed:** `false` (providers may update public rates, bill internal thinking tokens differently relative to `max_output_tokens = 16,384`, or bill partial generation before client timeout).
- **Separated Cost Categories:**
  1. `planning_estimate`: Pre-execution analytical envelope (`LOW` / `HIGH` / `CONDITIONAL_MAX_OUTPUT_REFERENCE`).
  2. `authoritative_provider_receipt_cost`: Post-execution deterministic cost from `usage_metadata` in `execution_receipt.json`.
  3. `provider_invoice`: Actual external billing statement on Google Cloud / OpenAI / Anthropic consoles.

#### Cost Envelopes Under Frozen Runner Registry Rates (`2026-10-16`: C1 `$0.30/$2.50`, C2 `$2.50/$10.00`, C3 `$3.00/$15.00` per 1M tokens)
| Budget Option | Calls | `LOW_PLANNING_ENVELOPE` | `HIGH_PLANNING_ENVELOPE` | `CONDITIONAL_MAX_OUTPUT_REFERENCE` (`16,384` out/call) |
|---|---:|---:|---:|---:|
| **`S1_FULL_COMPARATIVE_180`** | `180` (`60`/cand) | **`$12.357`** (`C1=$1.107, C2=$4.50, C3=$6.75`) | **`$24.03`** (`C1=$2.07, C2=$9.00, C3=$12.96`) | **`$38.0136`** (`C1=$3.1776, C2=$14.3304, C3=$20.5056`) |
| **`S2_READINESS_CANARY_PLUS_COMPARATIVE_180`** | `189` (`63`/cand) | **`$12.97485`** (`C1=$1.16235, C2=$4.725, C3=$7.0875`) | **`$25.2315`** (`C1=$2.1735, C2=$9.45, C3=$13.608`) | **`$39.91428`** (`C1=$3.33648, C2=$15.04692, C3=$21.53088`) |
| **`S3_REDUCED_STRATIFIED_COMPARATIVE_90`** | `90` (`30`/cand) | **`$6.1785`** (`C1=$0.5535, C2=$2.25, C3=$3.375`) | **`$12.015`** (`C1=$1.035, C2=$4.50, C3=$6.48`) | **`$19.0068`** (`C1=$1.5888, C2=$7.1652, C3=$10.2528`) |

*(Corresponding envelopes under the `2026-10-17` Preflight 01D receipt rates — C1 `$0.75/$3.75`, C2 `$2.00/$10.00`, C3 `$2.00/$10.00` — are `$10.5525` LOW / `$20.565` HIGH / `$32.5872` CONDITIONAL_MAX for `S1`, `$11.080125` LOW / `$21.59325` HIGH / `$34.21656` CONDITIONAL_MAX for `S2`, and `$5.27625` LOW / `$10.2825` HIGH / `$16.2936` CONDITIONAL_MAX for `S3`.)*

---

## 11. Advisory Recommendation (`ANTY_ANALYTICAL_RECOMMENDATION`)

- **Advisory Status:** `advisory_only = true`, `recommendation_implemented = false`
- **Final Decision Authority:** `FINAL_METHODOLOGY_DECISION_AUTHORITY = CHATGPT`
- **Recommended Policy Bundle for ChatGPT Consideration:**
  - **Track Classification:** `SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK`
  - **Fairness Policy:** `OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT`
  - **Timeout Policy:** `T3_CANDIDATE_180S` (`180,000 ms` applied symmetrically to `C1`, `C2`, `C3`)
  - **Pacing Policy:** `P1_FIXED_2000MS_INTER_CALL_DELAY` (`2,000 ms` deterministic non-adaptive spacing)
  - **Retry Policy:** `R0_STRICT_ZERO_RETRY` (`retry = 0`)
  - **Fixture Policy:** `POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET` (`3` readiness canary fixtures × `3` candidates = `9` canary calls, followed by the exact `60` `DEV-SELECT` comparative fixtures = `180` calls)
  - **Call-Budget Option:** `S2_READINESS_CANARY_PLUS_COMPARATIVE_180` (`189` calls maximum)

---

## 12. Project Owner Action Matrix (Section 14)

All owner actions carry status `PENDING_CHATGPT_AMENDMENT_DECISION` and marker `OWNER_ACTION_REQUIRED`:

| Action ID | Provider | Mandatory / Optional | Required Before Gate | Reason | Secret-Safe Verification Method | Status |
|---|---|---|---|---|---|---|
| `POA-01` | `anthropic (C3 / claude-sonnet-5-5)` | `MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED` | `W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE` | `60/60` primary C3 cells failed with HTTP 400 low credit balance. | Owner confirms positive credit balance in Anthropic Console + future readiness gate records boolean status & HTTP 200 without key/hash/org disclosure. | `PENDING_CHATGPT_AMENDMENT_DECISION` |
| `POA-02` | `google (C1 / gemini-3.8-flash)` | `MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED` | `W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE` | `35/60` primary C1 cells failed with HTTP 429 Free Tier `20 RPD` quota exhaustion. | Owner confirms Paid Tier billing linkage in Google AI Studio / Cloud Console + boolean readiness attestation without project/key disclosure. | `PENDING_CHATGPT_AMENDMENT_DECISION` |
| `POA-03` | `openai (C2 / gpt-6.1-sol)` | `MANDATORY_IF_AMENDED_COMPARATIVE_TRACK_APPROVED` | `W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE` | Longer timeout ceiling (`120..180s`) allows all 60 C2 cells to complete and bill output tokens. | Owner confirms positive OpenAI credit balance + boolean readiness attestation without key/org disclosure. | `PENDING_CHATGPT_AMENDMENT_DECISION` |
| `POA-04` | `all_providers (C1, C2, C3)` | `OPTIONAL_FOR_OPERATIONAL_READINESS_MANDATORY_FOR_COST_TIEBREAK_AUTHORITY` | `W06-DEV-SELECT-AMENDED-LIVE-AUTHORIZATION-AND-READINESS-GATE` | Refresh `2026-10-16` / `2026-10-17` repository pricing snapshots (`EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION`). | Record public provider pricing URLs, access date, and per-million USD rates in amended authorization plan. | `PENDING_CHATGPT_AMENDMENT_DECISION` |
