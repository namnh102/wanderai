# W06 DEV-TUNE Primary Live Results Freeze (`W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01`)

## 1. Purpose & Execution Authority

This document records the cryptographic freeze and offline integrity verification of the primary W06 DEV-TUNE live execution batch (`W06-DEV-TUNE-LIVE-EXECUTION-01`), executed on merged `develop` commit `4a276ca8ca5e836a92d34ec72569998a3617d915`.

- **Task ID:** `W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01`
- **Execution ID:** `W06-DEV-TUNE-LIVE-EXECUTION-01`
- **Execution Base / Pre-Live / Post-Live HEAD SHA:** `4a276ca8ca5e836a92d34ec72569998a3617d915`
- **Live Provider Calls in This Freeze Task (`LIVE_PROVIDER_CALLS_NEW`):** `0`
- **Raw Output Root (Read-Only Evidence):** `data/evaluation/w06/live_dev_tune_primary_v1`
- **Results Manifest:** `data/evaluation/w06/w06_dev_tune_live_results_manifest_v1.json`
  - `RESULTS_MANIFEST_FILE_SHA256 = 060c3da987638f8eeb96a6240e11b612d3b5e80e31be5046779c417fbca7be85`
- **Results Freeze Receipt:** `data/evaluation/w06/w06_dev_tune_live_results_freeze_01_receipt_v1.json`
  - `RESULTS_FREEZE_RECEIPT_FILE_SHA256 = 5f45c31a96b3827d64b927bccde154ad9345202fbfad6f8070c9f7927c40cbfe`

---

## 2. Frozen Upstream Authorities & Code Provenance

| Authority / Artifact | Identifier / Path | SHA256 / Value |
|---|---|---|
| Execution Plan | `data/evaluation/w06/w06_dev_tune_execution_plan_v1.json` | `plan_sha256`: `582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae`<br>File LF SHA256: `652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74` |
| Prompt Candidate Freeze | `data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json` | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| Prompt Registry (`[P1, P2]`) | `build_frozen_p1_p2_registry()` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| Live Authorization (`W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1`) | `data/evaluation/w06/w06_dev_tune_live_authorization_v1.json` | File LF SHA256: `b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4`<br>Internal SHA256: `fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83` |
| Stage-A Pre-Live Freeze Receipt | `data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json` | File LF SHA256: `a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31`<br>Internal SHA256: `a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f` |
| Scientific Code Bundle | `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| Dedicated Live Launcher | `scripts/run_w06_dev_tune_live_v1.py` | LF SHA256: `b2bdbe062ea9d9e52701bfb73027ab30237f7648835a0ea285961b0e70e4fbbc`<br>Git Blob SHA: `bf8c24f64d81b42fe6eab5dd14ef19a0e7500712` |
| Preflight Request Set | 120 serialized wire requests | `438365622e97f9a7062bca5ef9f472ebf48b5d3438c8484d8b0ea8eba4761dc3` |
| Preflight Artifact Path Set | 120 planned cell artifact path maps | `eebd7a95fa2eb2ea17bffec7d81478594df565423c8a2d893e41a45ab4adc8a8` |

---

## 3. Immutable Raw Evidence Tree Verification

All files under `data/evaluation/w06/live_dev_tune_primary_v1` were hashed over exact raw bytes (`hashlib.sha256(p.read_bytes()).hexdigest()`) without any modification, reformatting, or line-ending normalization:

- `RAW_EVIDENCE_FILE_COUNT = 1124`
- `RAW_EVIDENCE_TOTAL_BYTES = 11749420` (11.75 MB)
- `RAW_EVIDENCE_MAX_FILE_BYTES = 96816` (96.8 KB, well below the 90 MiB per-file threshold)
- `RAW_EVIDENCE_TREE_SHA256 = 9b6089f478979ce32e968529c656358fc1bb751101527e017c1e4d5a695cd1e8`

### Per-Cell File Completeness & Integrity

- **Assigned Cells / Cell Directories:** `120 / 120` (0 missing, 0 unknown/extra, 0 top-level stray files)
- **Always-Present Cell Files (`120` each = `1,080` files):**
  - `request_manifest.json`: `120`
  - `transport_journal_starting.json`: `120`
  - `transport_journal_completed.json`: `120`
  - `raw_provider_response.txt`: `120`
  - `provider_response_metadata.json`: `120`
  - `raw_usage_metadata.json`: `120`
  - `run_manifest.json`: `120`
  - `evaluation_result.json`: `120`
  - `execution_receipt.json`: `120`
- **Conditionally-Present Cell Files:**
  - `parsed_plan_response.json`: `44` (present in all 44 schema-valid runs; absent in all 76 transport-failed runs)
- **Request Identity Match vs. Frozen Preflight:** `120/120`
- **Per-Cell Receipt Hash Chain Valid:** `120/120`
- **Transport Journal Integrity:** `120` starting, `120` completed, `0` ambiguous
- **Retry / Rerun Discipline:** `retry_calls = 0`, `rerun_cells = 0`, `attempt_number = 1` across all 120 cells, `actual_http_request_count = 1` across all 120 cells
- **Model Integrity (`MODEL_ID_MISMATCH_COUNT = 0`):**
  - `C1`: requested `gemini-3.8-flash`, returned `gemini-3.8-flash` (`4` valid cells) / `null` (`36` failed cells)
  - `C2`: requested `gpt-6.1-sol`, returned `gpt-6.1-sol` (`7` valid cells) / `null` (`33` failed cells)
  - `C3`: requested `claude-sonnet-5-5`, returned `claude-sonnet-5-5` (`33` valid cells) / `null` (`7` failed cells)

---

## 4. Recomputed Execution Summary & Prompt × Candidate Breakdown

### 4.1 Failure Classification Counts (`120` cells)

| Failure Classification | Total | `C1` (`gemini-3.8-flash`) | `C2` (`gpt-6.1-sol`) | `C3` (`claude-sonnet-5-5`) | `P1` (`60` cells) | `P2` (`60` cells) |
|---|---:|---:|---:|---:|---:|---:|
| `NONE` | **44** | 4 | 7 | 33 | 23 | 21 |
| `TIMEOUT` | **57** | 18 | 33 | 6 | 35 | 22 |
| `HTTP_429` | **15** | 15 | 0 | 0 | 0 | 15 |
| `HTTP_5XX` | **3** | 3 | 0 | 0 | 2 | 1 |
| `HTTP_ERROR` | **1** | 0 | 0 | 1 | 0 | 1 |
| **Total** | **120** | **40** | **40** | **40** | **60** | **60** |

### 4.2 Primary Evaluation Metrics by Prompt & Candidate

| Slice | Cells | `VALID_RUN_AND_SCHEMA` (`true` / `false`) | `EXACT_GROUNDING_PASS` (`true` / `false`) | `FINAL_CORE_PASS` (`true` / `false`) |
|---|---:|---|---|---|
| **Total** | **120** | **44** / 76 | **44** / 76 | **41** / 79 |
| **By Candidate: `C1`** | 40 | 4 / 36 | 4 / 36 | 1 / 39 |
| **By Candidate: `C2`** | 40 | 7 / 33 | 7 / 33 | 7 / 33 |
| **By Candidate: `C3`** | 40 | 33 / 7 | 33 / 7 | 33 / 7 |
| **By Prompt: `P1`** | 60 | 23 / 37 | 23 / 37 | 20 / 40 |
| **By Prompt: `P2`** | 60 | 21 / 39 | 21 / 39 | 21 / 39 |
| **`P1_C1`** | 20 | 3 / 17 | 3 / 17 | 0 / 20 |
| **`P1_C2`** | 20 | 4 / 16 | 4 / 16 | 4 / 16 |
| **`P1_C3`** | 20 | 16 / 4 | 16 / 4 | 16 / 4 |
| **`P2_C1`** | 20 | 1 / 19 | 1 / 19 | 1 / 19 |
| **`P2_C2`** | 20 | 3 / 17 | 3 / 17 | 3 / 17 |
| **`P2_C3`** | 20 | 17 / 3 | 17 / 3 | 17 / 3 |

---

## 5. Authoritative Cost Accounting (`AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY`)

Cost totals are recomputed strictly from `Decimal(str(receipt["canonical_cost_usd_decimal"]))` over cells where `authoritative_usage_available == true` and `canonical_cost_usd_decimal is not None`:

- **Cost Accounting Label:** `AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY`
- **Authoritative Cost Cells:** `42` (out of 44 valid runs)
- **Total Canonical Cost (USD):** `6.5555805`
  - `C1` (`4` cells): `0.080954` USD
  - `C2` (`5` authoritative non-cached cells): `0.3768775` USD
  - `C3` (`33` cells): `6.097749` USD
- **Non-Comparable Cached Valid Cells (`2` cells in `C2`):**
  - `W06-DEV-TUNE-P2-C2-W06-DEV-TUNE-009`
  - `W06-DEV-TUNE-P2-C2-W06-DEV-TUNE-011`
  - In these 2 `C2` cells, OpenAI reported `prompt_tokens_details.cached_tokens > 0`. Under our frozen scientific pricing contract, cached-token cells cannot be priced using standard uncached input rates without distorting cross-cell cost comparability, so `authoritative_usage_available` is recorded as `false` and `canonical_cost_usd_decimal` is `null`.

---

## 6. Scientific Design Note: Temporal Execution-Order Limitation (Section 13)

In `w06_dev_tune_execution_plan_v1.json`, all 60 `P1` cells (`001..060`) were scheduled and executed before all 60 `P2` cells (`061..120`). Prompt treatment was **not** temporally interleaved or randomized.

- All `15` observed `HTTP_429` rate-limit failures occurred in `P2/C1` (`w06_dev_tune_v1_061..120` for candidate `C1`), whereas `P1/C1` experienced `0` `HTTP_429` failures (`14` `TIMEOUT`, `3` `HTTP_5XX`, `3` `NONE`).
- **Mandatory Scientific Interpretation Guardrail:** Because `P2` executed immediately after `P1` without temporal interleaving, the concentration of `HTTP_429` in `P2/C1` may reflect cumulative provider quota/rate-limit state over time and **MUST NOT** be interpreted as causal evidence that prompt `P2` induces `HTTP 429` errors.
- No retroactive reordering or interleaved rerun is permitted on this frozen primary execution dataset.

---

## 7. Prompt-Selection Preview Only (`WINNING_PROMPT_SELECTED = false`)

This task freezes raw live execution evidence only and **does not** create the formal prompt-selection artifact (`WINNING_PROMPT_SELECTED = false`).

For transparency, applying the frozen 3-tier prompt-selection hierarchy with its 10 percentage-point survivor band to the 120 frozen cells yields:

1. **Criterion 1 (`VALID_RUN_AND_SCHEMA_RATE`):**
   - `P1`: `23 / 60` (`38.333333%`)
   - `P2`: `21 / 60` (`35.000000%`)
   - Absolute difference: `3.333333` percentage points ($\le 10.0$ pp band) $\rightarrow$ **Survivors: `["P1", "P2"]`**
2. **Criterion 2 (`EXACT_GROUNDING_PASS_RATE`):**
   - `P1`: `23 / 60` (`38.333333%`)
   - `P2`: `21 / 60` (`35.000000%`)
   - Absolute difference: `3.333333` percentage points ($\le 10.0$ pp band) $\rightarrow$ **Survivors: `["P1", "P2"]`**
3. **Criterion 3 (`FINAL_CORE_PASS_RATE`):**
   - `P1`: `20 / 60` (`33.333333%`)
   - `P2`: `21 / 60` (`35.000000%`)
   - Absolute difference: `1.666667` percentage points ($\le 10.0$ pp band) $\rightarrow$ **Survivors: `["P1", "P2"]`**
4. **Administrative Tie-Break Preview:**
   - Because both `P1` and `P2` survive all three criteria within the 10 percentage-point tolerance band, the deterministic administrative tie-break (`P1` before `P2`) would select `P1` in the subsequent formal prompt-selection task, without claiming statistical or scientific superiority of `P1` over `P2`.

---

## 8. Model-Selection & Final100 Firewalls

- `WINNING_PROMPT_SELECTED = false`
- `MODEL_WINNER_SELECTED = false`
- `DEV_SELECT_EXECUTION_STARTED = false`
- `STOCHASTICITY_EXECUTION_STARTED = false`
- `FINAL100_USED = false`
  - `data/evaluation/w06/w06_scenarios_freeze_v1.json` SHA256 = `6fe99fb53fd5ef03fb3fb9eb3eb1cb2fd4ec7be1dc2ac2fb4f4fb7f3b3fb635c`
  - `data/evaluation/w06/w06_p11_assignment_manifest_v1.json` SHA256 = `b08b6fb84f01d0db828fb40f40f903e2a5086a3dc21fd2ebba2fd8446cd283d9`

---

## 9. Historical Lifecycle Compatibility (Section 23)

To allow committing the verified post-Stage-A live execution evidence under `data/evaluation/w06/live_dev_tune_primary_v1` along with `w06_dev_tune_live_results_manifest_v1.json` and `w06_dev_tune_live_results_freeze_01_receipt_v1.json` while keeping all earlier W06 gate tests green and fail-closed against any unverified or tampered output tree, narrow cryptographic downstream exemptions (`is_verified_downstream_w06_dev_tune_live_results_file` / `is_verified_downstream_w06_dev_tune_live_results_tree`) were wired into:

1. `scripts/prepare_w06_dev_tune_authorization.py`
2. `scripts/issue_w06_dev_tune_live_authorization.py`
3. `scripts/freeze_w06_dev_tune_stage_a.py`
4. `apps/ai-service/tests/test_w06_dev_tune_live_launcher_01.py`

No historical frozen JSON receipt (`w06_dev_tune_authorization_prep_01_v1.json`, `w06_dev_tune_live_authorization_v1.json`, `w06_dev_tune_stage_a_freeze_receipt_v1.json`, `w06_dev_prompt_candidate_freeze_v1.json`, `w06_dev_tune_execution_plan_v1.json`) and no file in `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` or `scripts/run_w06_dev_tune_live_v1.py` was modified.
