# W06-DEV-SELECT-FAILURE-DIAGNOSTIC-01-OFFLINE — Evidence-Based Failure Pattern Diagnostic

## 1. Scope, Immutability, and Authority Bindings

This document reports the strictly offline, read-only, deterministic diagnostic analysis of the frozen 180-cell W06 DEV-SELECT execution (`data/evaluation/w06/live_dev_select_primary_v1`).

**This diagnostic does NOT repair, normalize, reclassify, or censor provider failures in the primary benchmark record.** All primary failure classifications (`execution_receipt.failure_classification`) and 60-cell per-candidate denominators remain untouched.

| Authority / Property | Frozen Value |
|---|---|
| `TASK_ID` | `W06-DEV-SELECT-FAILURE-DIAGNOSTIC-01-OFFLINE` |
| `DIAGNOSTIC_ARTIFACT_ID` | `W06-DEV-SELECT-FAILURE-DIAGNOSTIC-V1` |
| `BASE_DEVELOP_SHA` / `SOURCE_DEVELOP_SHA` | `beb5ec657bb4417bdeaf307356e6895070b64cdc` |
| `PRE_LIVE_EXECUTION_DEVELOP_SHA` | `eac86a38f6b457c9b6ff078f26c4f953a9fc98a7` |
| `RAW_EVIDENCE_FILE_COUNT` | `1629` |
| `RAW_EVIDENCE_TOTAL_BYTES` | `16264062` |
| `RAW_EVIDENCE_TREE_SHA256` (Before & After) | `d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817` |
| `RESULTS_MANIFEST_FILE_SHA256` | `1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0` |
| `RESULTS_MANIFEST_INTERNAL_SHA256` | `4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011` |
| `RESULTS_FREEZE_RECEIPT_FILE_SHA256` | `c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4` |
| `RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256` | `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a` |
| `DEV_SELECT_PLAN_FILE_SHA256` | `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a` |
| `DEV_SELECT_PLAN_INTERNAL_SHA256` | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `SCIENTIFIC_CODE_BUNDLE_SHA256` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| `LAUNCHER_LF_SHA256` | `cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf` |
| `DIAGNOSTIC_ARTIFACT_FILE_SHA256` | `b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692` |
| `DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256` | `509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8` |
| `LIVE_PROVIDER_CALLS_NEW` | `0` |
| `RAW_EVIDENCE_MUTATED` | `false` |

---

## 2. Primary vs. Secondary Diagnostic Taxonomy Overview

- **Primary Authority (Immutable):** `execution_receipt.failure_classification`
  - **TOTAL (180 cells):** `HTTP_429 = 35`, `HTTP_5XX = 10`, `HTTP_ERROR = 60`, `NONE = 9`, `TIMEOUT = 66`
  - **C1 (60 cells):** `HTTP_429 = 35`, `HTTP_5XX = 10`, `HTTP_ERROR = 0`, `NONE = 1`, `TIMEOUT = 14`
  - **C2 (60 cells):** `HTTP_429 = 0`, `HTTP_5XX = 0`, `HTTP_ERROR = 0`, `NONE = 8`, `TIMEOUT = 52`
  - **C3 (60 cells):** `HTTP_429 = 0`, `HTTP_5XX = 0`, `HTTP_ERROR = 60`, `NONE = 0`, `TIMEOUT = 0`

- **Secondary Diagnostic Taxonomy (`W06-DEV-SELECT-SECONDARY-TAXONOMY-V1`, Descriptive Only):**
  Assigned deterministically from status/error evidence in `provider_response_metadata.json` and `execution_receipt.json` without inspecting `candidate_id`:
  - **TOTAL (180 cells):**
    - `HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED = 60`
    - `CLIENT_TIMEOUT_REPORTED = 56`
    - `HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED = 35`
    - `HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED = 10`
    - `HTTP_5XX_OTHER = 10`
    - `SUCCESSFUL_PROVIDER_RESPONSE = 9`
    - (`HTTP_429_UNSPECIFIED = 0`, `HTTP_4XX_OTHER = 0`, `HTTP_ERROR_OTHER = 0`, `UNKNOWN_OR_INSUFFICIENT_EVIDENCE = 0`)

---

## 3. Candidate C1 (`gemini-3.8-flash`) Failure Audit

### FACT (`DIRECT_PROVIDER_DECLARATION` & `DIRECT_FROZEN_METADATA`)
- **Primary Classification Counts (`60` cells):** `HTTP_429 = 35`, `HTTP_5XX = 10`, `TIMEOUT = 14`, `NONE = 1`, `HTTP_ERROR = 0`.
- **Secondary Diagnostic Counts (`60` cells):**
  - `HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED = 35` (from primary `HTTP_429`)
  - `HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED = 10` (from primary `HTTP_5XX`)
  - `CLIENT_TIMEOUT_REPORTED = 4` (from primary `TIMEOUT`)
  - `HTTP_5XX_OTHER = 10` (from primary `TIMEOUT`)
  - `SUCCESSFUL_PROVIDER_RESPONSE = 1` (from primary `NONE`, `W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026`, `latency_ms = 46688.0`)
- **Normalized Failure Signatures (`4` distinct signatures across `59` failed C1 cells):**
  1. **Signature `946296a8f9d0d3c1c5b28f21eea57b65fd86d75e36b4cf5298ceafd747ab6abb` (`count = 35`, `HTTP_429` -> `HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED`, `DIRECT_PROVIDER_DECLARATION`):**
     - HTTP status `429`, `ClientError`, status `RESOURCE_EXHAUSTED`.
     - Explicitly declares Free Tier daily quota exhaustion (`limit: 20` on `generativelanguage.googleapis.com/generate_content_free_tier_requests`, `quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
     - Latency: `min = 1157.0 ms`, `median = 1297.0 ms`, `max = 3797.0 ms`.
  2. **Signature `7b688d19f5c20337b772eabaf551b65c0a4850f6722e454c56579cac4fb74d32` (`count = 10`, `HTTP_5XX` -> `HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED`, `DIRECT_PROVIDER_DECLARATION`):**
     - HTTP status `503`, `ServerError`, status `UNAVAILABLE`.
     - Explicitly declares: `"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."`
     - Latency: `min = 1828.0 ms`, `median = 6062.5 ms`, `max = 43812.0 ms`.
  3. **Signature `39fddef667aff00fc8e219fa1a10b9473bf0e5ef66b6ecad59e9802de75eb4d6` (`count = 4`, `TIMEOUT` -> `CLIENT_TIMEOUT_REPORTED`, `DIRECT_FROZEN_METADATA`):**
     - Exception `ReadTimeout: The read operation timed out` (no HTTP status code).
     - Latency: `min = 55781.0 ms`, `median = 55843.5 ms`, `max = 56016.0 ms` (`4/4` within `[55000, 57000] ms`).
  4. **Signature `8bba4fad484aa8e79d093a5aa52c92a93e9b789605a1d3f19dcf343d4ad3f0e2` (`count = 10`, `TIMEOUT` -> `HTTP_5XX_OTHER`, `DIRECT_PROVIDER_DECLARATION`):**
     - HTTP status `504`, `ServerError`, status `DEADLINE_EXCEEDED`, message: `"Deadline expired before operation could complete."`
     - Mapped to primary `TIMEOUT` by `dev_live_runner.py` (`status_code in (408, 504)`) and assigned secondary label `HTTP_5XX_OTHER` because the frozen error payload is an HTTP 504 `ServerError` rather than a client-reported socket timeout.
     - Latency: `min = 53031.0 ms`, `median = 54696.0 ms`, `max = 55891.0 ms` (`1` in `< 54000 ms`, `8` in `[54000, 55000) ms`, `1` in `[55000, 57000] ms`).
- **C1 Primary `TIMEOUT` (`14` cells) Boundary Bucket Counts (`55000 ms` authority):**
  - `latency < 54000 ms`: `1` (`53031.0 ms`)
  - `54000 <= latency < 55000 ms`: `8` (`54640.0 .. 54953.0 ms`)
  - `55000 <= latency <= 57000 ms`: `5` (`55781.0 .. 56016.0 ms`)
  - `latency > 57000 ms`: `0`
  - `NEAR_FROZEN_55S_TIMEOUT_BOUNDARY` (`54000.0 <= latency_ms <= 57000.0`): `13 / 14`.

### DERIVED PATTERN (`DERIVED_DETERMINISTIC_PATTERN`)
- During the first 20 C1 scenarios (`W06-DEV-SELECT-001`..`020`), C1 experienced `10` HTTP `503 UNAVAILABLE` high-demand errors and `10` deadline/timeout failures (`8` HTTP `504 DEADLINE_EXCEEDED` and `2` client `ReadTimeout`).
- Starting at `W06-DEV-SELECT-021` (execution ordinal `61`) and continuously across all `31` C1 cells from `W06-DEV-SELECT-030` through `W06-DEV-SELECT-060` (ordinals `88..178`), C1 returned HTTP `429 RESOURCE_EXHAUSTED` citing the Free Tier 20 requests/day limit.

### NOT SUPPORTED (`INSUFFICIENT_EVIDENCE` / Forbidden Inference)
- It is **NOT SUPPORTED** to infer that intrinsic `gemini-3.8-flash` itinerary planning quality is poor (`1/60`) from provider Free Tier daily quota (`HTTP_429`), temporary high-demand (`HTTP_503`), or 55-second deadline (`HTTP_504` / `ReadTimeout`) failures.
- It is **NOT SUPPORTED** to infer that `gemini-3.8-flash` would achieve `100%` pass if quota/capacity errors were removed (extrapolating from `1` completed cell is scientifically invalid).

---

## 4. Candidate C2 (`gpt-6.1-sol`) Timeout Audit

### FACT (`DIRECT_FROZEN_METADATA`)
- **Primary Classification Counts (`60` cells):** `NONE = 8`, `TIMEOUT = 52`, `HTTP_429 = 0`, `HTTP_5XX = 0`, `HTTP_ERROR = 0`.
- **Secondary Diagnostic Counts (`60` cells):** `SUCCESSFUL_PROVIDER_RESPONSE = 8`, `CLIENT_TIMEOUT_REPORTED = 52`.
- **Normalized Failure Signatures (`1` distinct signature across `52` failed C2 cells):**
  - **Signature `b2a113ff0b0aacd241e36a9e8c368211f236016cfa9e5a04c4619eca7659659f` (`count = 52`, `TIMEOUT` -> `CLIENT_TIMEOUT_REPORTED`, `DIRECT_FROZEN_METADATA`):**
    - Exception `APITimeoutError: Request timed out.` (no HTTP status code).
- **C2 `TIMEOUT` (`52` cells) Latency & Boundary Bucket Counts (`55000 ms` authority):**
  - `latency_ms_min = 55078.0`, `latency_ms_median = 55132.5`, `latency_ms_max = 55797.0`
  - `latency < 54000 ms`: `0`
  - `54000 <= latency < 55000 ms`: `0`
  - `55000 <= latency <= 57000 ms`: `52`
  - `latency > 57000 ms`: `0`
  - `NEAR_FROZEN_55S_TIMEOUT_BOUNDARY` (`54000.0 <= latency_ms <= 57000.0`): `52 / 52`.
- **C2 `NONE` (`8` cells) Latency Distribution:**
  - `latency_ms_min = 35812.0`, `latency_ms_median = 45898.5`, `latency_ms_max = 53094.0`.
  - All `8/8` completed C2 responses passed `valid_run_and_schema`, `exact_grounding_pass`, and `final_core_pass`.

### DERIVED PATTERN (`DERIVED_DETERMINISTIC_PATTERN`)
- `52/52` (`100%`) of C2 failure latencies cluster tightly in `[55078.0, 55797.0] ms`, immediately above the frozen `55000 ms` client timeout threshold.
- Descriptive comparison between C2 `NONE` (`8` cells) and C2 `TIMEOUT` (`52` cells):
  - **Trip Days:** `8/8` (`100%`) of C2 `NONE` cells are `2`-day scenarios (`days == 2`), whereas `0/20` of `3`-day scenarios and `0/20` of `4`-day scenarios completed before `55000 ms` (`TIMEOUT` days: `2-day = 12`, `3-day = 20`, `4-day = 20`).
  - **Interest Count:** C2 `NONE` has `1 interest = 6`, `2 interests = 2`, `3 interests = 0`; C2 `TIMEOUT` has `1 interest = 14`, `2 interests = 18`, `3 interests = 20`.
  - **Destination:** C2 `NONE` has `ha-noi = 4`, `da-nang = 2`, `ha-long = 2`; C2 `TIMEOUT` has `da-nang = 18`, `ha-long = 18`, `ha-noi = 16`.
  - **Canonical Wire Request Bytes:** C2 `NONE` has `min = 54698`, `median = 60242.5`, `max = 93198`; C2 `TIMEOUT` has `min = 54675`, `median = 65832.5`, `max = 93386`.

### NOT SUPPORTED (`INSUFFICIENT_EVIDENCE` / Forbidden Inference)
- It is **NOT SUPPORTED** to call `NEAR_FROZEN_55S_TIMEOUT_BOUNDARY` a proven causal root cause or to claim that the model is "inherently too slow".
- It is **NOT SUPPORTED** to claim what C2's schema/grounding/core pass rate would have been on the 52 timed-out cells had the timeout been higher.

---

## 5. Candidate C3 (`claude-sonnet-5-5`) Specific Audit

### FACT (`DIRECT_PROVIDER_DECLARATION` & `DIRECT_FROZEN_METADATA`)
- **Primary Classification Counts (`60` cells):** `HTTP_ERROR = 60`, `NONE = 0`, `TIMEOUT = 0`, `HTTP_429 = 0`, `HTTP_5XX = 0`.
- **Secondary Diagnostic Counts (`60` cells):** `HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED = 60`.
- **Per-Cell Evidence Verification (`60/60` cells):**
  - HTTP status `400` count: `60 / 60`.
  - Provider error types: outer `type = "error"`, inner `error.type = "invalid_request_error"` (`60 / 60`).
  - Provider-declared billing/credit cause count: `60 / 60` (`"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."`).
  - Distinct normalized error signatures: `1` (`63f1ba405c213c414dfb7faf404557d487727b24c12cd3d4d43bceeff88999f5`, differing across raw cells only in volatile `'request_id': 'req_...'`).
  - Latency: `min = 594.0 ms`, `median = 765.5 ms`, `max = 2609.0 ms`.
  - `returned_model_id is null` for all failures: `true` (`60 / 60`).
  - `actual_http_request_count == 1` for all 60: `true` (`60 / 60`).
- **Permitted Finding:**
  > “The frozen C3 provider/model configuration produced 60/60 provider-declared billing/credit rejection responses during this one-shot DEV-SELECT execution.”

### DERIVED PATTERN (`DERIVED_DETERMINISTIC_PATTERN`)
- All 60 C3 requests were rejected fast at the provider API gateway (`594.0 .. 2609.0 ms`) before any model generation occurred, uniformly across all quartiles (`Q1..Q4 = 15` each) and all scenario complexities.

### NOT SUPPORTED (`INSUFFICIENT_EVIDENCE` / Forbidden Inference)
- It is **NOT SUPPORTED** (and strictly forbidden) to conclude:
  - “Claude quality = zero”
  - “Claude cannot solve the task”
  - “C3 semantic performance is inferior”

---

## 6. Cross-Candidate Timeline (`execution_started_at_utc`)

### FACT (`DIRECT_FROZEN_METADATA`)
- Batch execution started at `2026-10-23T16:46:54.495406+00:00` (ordinal `1`, `W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001`) and completed transport at `2026-10-23T18:01:28.117382+00:00` (ordinal `180`, `W06-DEV-SELECT-P1-C3-W06-DEV-SELECT-060`).
- Cells executed strictly in interleaved candidate order (`C1 -> C2 -> C3`) across fixtures `001..060`.

### DERIVED PATTERN (`DERIVED_DETERMINISTIC_PATTERN`)

| Quartile (Ordinals) | Candidate C1 (`60`) | Candidate C2 (`60`) | Candidate C3 (`60`) |
|---|---|---|---|
| **Q1 (`1..45`, fixtures `001..015`)** | `HTTP_5XX=8, TIMEOUT=7` | `NONE=4, TIMEOUT=11` | `HTTP_ERROR=15` |
| **Q2 (`46..90`, fixtures `016..030`)** | `HTTP_429=5, HTTP_5XX=2, NONE=1, TIMEOUT=7` | `NONE=2, TIMEOUT=13` | `HTTP_ERROR=15` |
| **Q3 (`91..135`, fixtures `031..045`)** | `HTTP_429=15` | `NONE=2, TIMEOUT=13` | `HTTP_ERROR=15` |
| **Q4 (`136..180`, fixtures `046..060`)** | `HTTP_429=15` | `TIMEOUT=15` | `HTTP_ERROR=15` |

- **C1 Transition Pattern:** `C1` transitions from mixed `HTTP_5XX` (`503`) and `TIMEOUT` (`504`/`ReadTimeout`) in `Q1` and early `Q2` to `100%` `HTTP_429` (`429 RESOURCE_EXHAUSTED`) from ordinal `88` (`W06-DEV-SELECT-030`) through ordinal `178` (`W06-DEV-SELECT-060`).
- **C2 Transition Pattern:** `C2` records `4` `NONE` in `Q1`, `2` `NONE` in `Q2`, `2` `NONE` in `Q3`, and `0` `NONE` in `Q4`, coinciding with the fixture ordering within each destination block where shorter `2`-day scenarios appear earlier in each 20-fixture destination slice (`001..005` in `ha-noi`, `021..022` in `da-nang`, `042..043` in `ha-long`).
- **C3 Transition Pattern:** Invariant `HTTP_ERROR` (`59 transitions HTTP_ERROR->HTTP_ERROR`) across `Q1..Q4`.

### NOT SUPPORTED (`INSUFFICIENT_EVIDENCE` / Forbidden Inference)
- Temporal correlation across quartiles is descriptive only and must **not** be claimed as an independent causal effect.

---

## 7. Request-Complexity Descriptives

### FACT & DERIVED PATTERN (`DERIVED_DETERMINISTIC_PATTERN`)

| Candidate & Primary Group | Count | Wire Request Bytes (`min / median / max`) | Destinations (`da-nang / ha-long / ha-noi`) | Trip Days (`2 / 3 / 4`) | Interests (`1 / 2 / 3`) | Latency ms (`min / median / max`) |
|---|---:|---|---|---|---|---|
| **C1 `ALL`** | `60` | `54115 / 65258.5 / 92826` | `20 / 20 / 20` | `20 / 20 / 20` | `20 / 20 / 20` | `1157.0 / 2492.0 / 56016.0` |
| **C1 `HTTP_429`** | `35` | `65159 / 65334.0 / 92826` | `15 / 20 / 0` | `9 / 12 / 14` | `11 / 12 / 12` | `1157.0 / 1297.0 / 3797.0` |
| **C1 `HTTP_5XX`** | `10` | `54128 / 54203.5 / 54297` | `0 / 0 / 10` | `4 / 4 / 2` | `4 / 4 / 2` | `1828.0 / 6062.5 / 43812.0` |
| **C1 `TIMEOUT`** | `14` | `54115 / 54284.5 / 92766` | `4 / 0 / 10` | `6 / 4 / 4` | `5 / 4 / 5` | `53031.0 / 54844.0 / 56016.0` |
| **C1 `NONE`** | `1` | `92804 / 92804.0 / 92804` | `1 / 0 / 0` | `1 / 0 / 0` | `0 / 0 / 1` | `46688.0 / 46688.0 / 46688.0` |
| **C2 `ALL`** | `60` | `54675 / 65832.5 / 93386` | `20 / 20 / 20` | `20 / 20 / 20` | `20 / 20 / 20` | `35812.0 / 55125.0 / 55797.0` |
| **C2 `NONE`** | `8` | `54698 / 60242.5 / 93198` | `2 / 2 / 4` | `8 / 0 / 0` | `6 / 2 / 0` | `35812.0 / 45898.5 / 53094.0` |
| **C2 `TIMEOUT`** | `52` | `54675 / 65832.5 / 93386` | `18 / 18 / 16` | `12 / 20 / 20` | `14 / 18 / 20` | `55078.0 / 55132.5 / 55797.0` |
| **C3 `HTTP_ERROR`** | `60` | `54558 / 65698.0 / 93269` | `20 / 20 / 20` | `20 / 20 / 20` | `20 / 20 / 20` | `594.0 / 765.5 / 2609.0` |

### NOT SUPPORTED (`INSUFFICIENT_EVIDENCE` / Forbidden Inference)
- Request-complexity comparisons are descriptive only and do not authorize scenario modification, stratification changes, or statistical superiority claims.

---

## 8. Harness / Binding Integrity Check (`DIRECT_FROZEN_METADATA`)

Independent verification across all 180 frozen cell directories confirms that observed failures were **not** accompanied by any harness or binding inconsistency:
- `REQUEST_IDENTITY_MATCH = 180/180`
- `CELL_HASH_CHAIN_VALID = 180/180`
- `RETRY_CALLS = 0`
- `RERUN_CELLS = 0`
- `MODEL_ID_MISMATCH_COUNT = 0`
- `attempt_number != 1` cells = `0`
- `actual_http_request_count != 1` cells = `0`
- `duplicate_logical_cell_count` = `0`
- `HARNESS_OR_BINDING_INCONSISTENCY_OBSERVED = false`

---

## 9. Scientific Interpretation & Governance Firewalls

- **PRIMARY DEV-SELECT RESULTS ARE NOT CHANGED.**
- **NO CELL IS EXCLUDED FROM DENOMINATOR.**
- **NO RETRY IS PERMITTED BY THIS TASK.**
- **NO RERUN IS AUTHORIZED.**
- **NO MODEL WINNER IS SELECTED (`MODEL_WINNER_SELECTED = false`, `selected_model_id = null`).**
- **NO SELECTION CRITERION IS MODIFIED.**
- **NO COST/LATENCY TIEBREAK IS APPLIED.**
- **NO STOCHASTICITY RUN IS STARTED (`STOCHASTICITY_EXECUTION_STARTED = false`).**
- **FINAL100 REMAINS UNTOUCHED (`FINAL100_USED = false`).**
- **Provider/billing/quota/timeout failures remain part of the original frozen 60-cell denominator per candidate.**
- **Methodology Amendment Authority:** This diagnostic provides evidence reporting only. Antigravity does not decide whether a methodology amendment or next gate is required; that decision belongs exclusively to ChatGPT after independent audit.
