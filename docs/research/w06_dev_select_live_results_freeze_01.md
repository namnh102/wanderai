# W06 DEV-SELECT Live Results Freeze 01

## 1. Executive Summary

This document records the immutable freeze and offline cryptographic verification (`W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01`) of the one-shot 180-cell `DEV_SELECT` live execution evidence produced in `W06-DEV-SELECT-LIVE-EXECUTION-01` under `data/evaluation/w06/live_dev_select_primary_v1`.

All work in `W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01` was performed strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`). No cell was rerun, retried, edited, repaired, normalized, or deleted.

---

## 2. Frozen Upstream Authorities & Freeze Hashes

| Authority / Artifact | Value / SHA-256 |
|---|---|
| `TASK_ID` | `W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01` |
| `BASE_DEVELOP_SHA` | `eac86a38f6b457c9b6ff078f26c4f953a9fc98a7` |
| `CODE_BASIS_COMMIT_SHA` | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |
| `STAGE_A_COMMIT_SHA` | `e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863` |
| `SCIENTIFIC_CODE_BUNDLE_SHA256` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| `LAUNCHER_LF_SHA256` (`scripts/run_w06_dev_select_live_v1.py`) | `cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf` |
| `LAUNCHER_GIT_BLOB_SHA` | `ad597560ca149f8b78786c63feb64d63ac399971` |
| `DEV_SELECT_PLAN_INTERNAL_SHA256` | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `DEV_SELECT_PLAN_FILE_SHA256` | `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a` |
| `PLAN_FREEZE_RECEIPT_FILE_SHA256` | `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |
| `PROMPT_FREEZE_SHA256` | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| `PROMPT_REGISTRY_SHA256` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| `PROMPT_SELECTION_ARTIFACT_FILE_SHA256` | `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8` |
| `AUTHORIZATION_ID` | `W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1` |
| `AUTHORIZATION_ARTIFACT_FILE_SHA256` | `247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7` |
| `AUTHORIZATION_ARTIFACT_INTERNAL_SHA256` | `31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504` |
| `STAGE_A_RECEIPT_FILE_SHA256` | `dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26` |
| `STAGE_A_RECEIPT_INTERNAL_SHA256` | `1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014` |
| `PREFLIGHT_REQUEST_SET_SHA256` | `3ef997b8833399095b9bf5953ae200d45dd85acb7b253c5b6975adf1b01667e2` |
| `PREFLIGHT_ARTIFACT_PATH_SET_SHA256` | `2a058ebd180cf3fe557549f5d2d3eff66d72f5320155b0e73bbb6b31f412d544` |
| `RAW_EVIDENCE_FILE_COUNT` | `1629` |
| `RAW_EVIDENCE_TOTAL_BYTES` | `16264062` |
| `RAW_EVIDENCE_MAX_FILE_BYTES` | `96143` |
| `RAW_EVIDENCE_TREE_SHA256` | `d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817` |
| `RESULTS_MANIFEST_FILE_SHA256` (`w06_dev_select_live_results_manifest_v1.json`) | `1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0` |
| `RESULTS_MANIFEST_INTERNAL_SHA256` | `4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011` |
| `RESULTS_FREEZE_RECEIPT_FILE_SHA256` (`w06_dev_select_live_results_freeze_01_receipt_v1.json`) | `c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4` |
| `RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256` | `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a` |

---

## 3. Completeness, Zero-Retry Proof, and Failure Taxonomy

- **Assigned cells:** `180` (`C1 = 60`, `C2 = 60`, `C3 = 60`, locked prompt `P1`)
- **Cell directories:** `180`
- **Live provider calls attempted:** `180` (`maximum_allowed_live_provider_calls = 180`)
- **Retry calls:** `0` (`attempt_number = 1` and `actual_http_request_count = 1` for all `180` cells)
- **Rerun cells:** `0`
- **Parsed plan responses:** `9` (`C1 = 1`, `C2 = 8`, `C3 = 0`)
- **Request identity match:** `180/180`
- **Per-cell hash chain validity:** `180/180`

### Primary Failure Classification (`execution_receipt.failure_classification`)

| Candidate | `NONE` | `TIMEOUT` | `HTTP_429` | `HTTP_5XX` | `HTTP_ERROR` | Total |
|---|---:|---:|---:|---:|---:|---:|
| `C1` (`gemini-3.8-flash`) | `1` | `14` | `35` | `10` | `0` | `60` |
| `C2` (`gpt-6.1-sol`) | `8` | `52` | `0` | `0` | `0` | `60` |
| `C3` (`claude-sonnet-5-5`) | `0` | `0` | `0` | `0` | `60` | `60` |
| **Total** | **`9`** | **`66`** | **`35`** | **`10`** | **`60`** | **`180`** |

---

## 4. Primary Model-Selection Metrics (60-Cell Unconditional Denominators)

All candidate denominators remain strictly `60` (`180` total). Transport failures (`HTTP_429`, `HTTP_5XX`, `TIMEOUT`, `HTTP_ERROR`) are never excluded from the denominator.

| Candidate | `VALID_RUN_AND_SCHEMA` | `EXACT_GROUNDING_PASS` | `FINAL_CORE_PASS` |
|---|---:|---:|---:|
| `C1` (`gemini-3.8-flash`) | `1 / 60` (`true: 1, false: 59`) | `1 / 60` (`true: 1, false: 59`) | `1 / 60` (`true: 1, false: 59`) |
| `C2` (`gpt-6.1-sol`) | `8 / 60` (`true: 8, false: 52`) | `8 / 60` (`true: 8, false: 52`) | `8 / 60` (`true: 8, false: 52`) |
| `C3` (`claude-sonnet-5-5`) | `0 / 60` (`true: 0, false: 60`) | `0 / 60` (`true: 0, false: 60`) | `0 / 60` (`true: 0, false: 60`) |
| **Total** | **`9 / 180` (`true: 9, false: 171`)** | **`9 / 180` (`true: 9, false: 171`)** | **`9 / 180` (`true: 9, false: 171`)** |

---

## 5. Model Integrity & Authoritative Cost Evidence

### Model Integrity (`MODEL_ID_MISMATCH_COUNT = 0`)

- **`C1` (`gemini-3.8-flash`):** `assigned = 60`, `verified_returned_model_matches = 1`, `transport_failure_unverified = 59`, `mismatch = 0`
- **`C2` (`gpt-6.1-sol`):** `assigned = 60`, `verified_returned_model_matches = 8`, `transport_failure_unverified = 52`, `mismatch = 0`
- **`C3` (`claude-sonnet-5-5`):** `assigned = 60`, `verified_returned_model_matches = 0`, `transport_failure_unverified = 60`, `mismatch = 0`

Transport-failure cells without a returned model identifier (`null`) are recorded as `transport_failure_unverified` and are not model mismatches.

### Authoritative Receipt Cost (`AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY`)

- **`AUTHORITATIVE_COST_CELL_COUNT`:** `9` (`C1 = 1`, `C2 = 8`, `C3 = 0`)
- **`TOTAL_CANONICAL_COST_USD`:** `0.6468966` (`C1 = 0.0266516`, `C2 = 0.620245`, `C3 = 0`)
- Missing `171` transport-failed cells are not estimated into this authoritative sum. This figure is labeled `AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY` (not a final provider invoice).

---

## 6. Scientific Interpretation Boundaries & Downstream Firewall

1. **No Model Selection Yet (Section 10):**
   - `MODEL_WINNER_SELECTED = false`
   - `selected_model_id = null`
   - This task freezes raw `DEV_SELECT` live evidence only. Descriptive rates are reported above, but no formal model-selection artifact or winner declaration is produced in this task.
2. **`C1` Interpretation Boundary (Section 13):**
   - `C1` observed `35 HTTP_429`, `10 HTTP_5XX`, `14 TIMEOUT`, and `1 NONE`.
   - No reruns after quota recovery are permitted, `HTTP_429` cells remain in the `60`-cell denominator, failures are not attributed to prompt `P1`, and intrinsic Gemini model quality is not claimed from the single successful cell.
3. **`C2` Interpretation Boundary (Section 14):**
   - `C2` observed `52 TIMEOUT` and `8 NONE` (`8 / 60`).
   - This descriptive rate represents one-shot performance of the full frozen `C2` provider/model/configuration under the recorded `W06 DEV-SELECT` environment and must not be claimed as intrinsic GPT model quality in isolation.
4. **`C3` Interpretation Boundary (Section 12):**
   - `C3` observed `60 / 60` primary `HTTP_ERROR` and `0` parsed plan outputs.
   - This does not claim that Claude model quality is zero, that Claude is incapable of itinerary planning, or that `C3` is scientifically inferior because outputs were bad; the observed evidence is that the frozen `C3` provider/model configuration produced `60 / 60` `HTTP_ERROR` under the one-shot frozen `DEV_SELECT` execution environment, and no retries are permitted to separate provider availability from model capability.
5. **Downstream Firewall (Section 20):**
   - `MODEL_WINNER_SELECTED = false`
   - `STOCHASTICITY_EXECUTION_STARTED = false`
   - `FINAL100_USED = false`
   - `LIVE_PROVIDER_CALLS_NEW = 0`
