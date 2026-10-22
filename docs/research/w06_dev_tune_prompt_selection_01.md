# W06-DEV-TUNE-PROMPT-SELECTION-01 — Deterministic Preregistered Prompt Selection & Freeze

## 1. Task Identity & Provenance

- **Task ID:** `W06-DEV-TUNE-PROMPT-SELECTION-01`
- **Selection Artifact ID:** `W06-DEV-TUNE-PROMPT-SELECTION-01-V1`
- **Receipt Artifact ID:** `W06-DEV-TUNE-PROMPT-SELECTION-01-RECEIPT-V1`
- **Source `develop` SHA:** `7c326b36dcb999b9e16b1ecad7c5596dc2bccce1`
- **Source Results-Freeze Gate Status:** `W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01 = CLOSED`
- **Selection Status:** `SELECTED`
- **Execution Mode:** Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`)

---

## 2. Authoritative Frozen Inputs & Pre-Selection Verification

Before performing prompt selection, the stateless offline results-freeze verifier (`is_verified_downstream_w06_dev_tune_live_results_tree` and `verify_and_summarize_live_results_evidence`) verified all upstream frozen authorities on disk:

| Authority / Artifact | SHA256 Digest / Value |
| --- | --- |
| `DEV_TUNE_PLAN_INTERNAL_SHA256` | `582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae` |
| `DEV_TUNE_PLAN_FILE_SHA256` | `652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74` |
| `PROMPT_FREEZE_SHA256` (`w06_dev_prompt_candidate_freeze_v1.json`) | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| `PROMPT_REGISTRY_SHA256` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| `P1_SEMANTIC_PROMPT_SHA256` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` |
| `P1_SYSTEM_PROMPT_SHA256` | `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e` |
| `P1_USER_PROMPT_TEMPLATE_SHA256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `P2_SEMANTIC_PROMPT_SHA256` | `0679dd9463d6cebf04ccb5571a403331eea3ab6819bd6a0e8b2ee1fc08c99fdf` |
| `P2_SYSTEM_PROMPT_SHA256` | `ab8ec41b7099c1c207217a55e1afd7e075d5de6be9b2fc14863329b5535e6c68` |
| `P2_USER_PROMPT_TEMPLATE_SHA256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `RAW_EVIDENCE_TREE_SHA256` (`1124` files, `11749420` bytes) | `9b6089f478979ce32e968529c656358fc1bb751101527e017c1e4d5a695cd1e8` |
| `RESULTS_MANIFEST_FILE_SHA256` (`w06_dev_tune_live_results_manifest_v1.json`) | `060c3da987638f8eeb96a6240e11b612d3b5e80e31be5046779c417fbca7be85` |
| `RESULTS_FREEZE_RECEIPT_FILE_SHA256` (`w06_dev_tune_live_results_freeze_01_receipt_v1.json`) | `5f45c31a96b3827d64b927bccde154ad9345202fbfad6f8070c9f7927c40cbfe` |
| `SCIENTIFIC_CODE_BUNDLE_SHA256` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| `LAUNCHER_LF_SHA256` (`scripts/run_w06_dev_tune_live_v1.py`) | `b2bdbe062ea9d9e52701bfb73027ab30237f7648835a0ea285961b0e70e4fbbc` |

---

## 3. Authoritative Selection Unit & Primary Failure Classification Authority

Prompt selection is pooled across the frozen equal candidate $\times$ fixture DEV-TUNE design:

- **Assigned cells per prompt:** `60` (`20 fixtures × 3 candidates` (`C1`, `C2`, `C3`))
- **Total assigned cells:** `120`
- **Denominator rule:** All `60` assigned cells per prompt are included in the denominator. Timeouts, HTTP errors, HTTP 429, HTTP 5xx, and invalid schema outputs are **never** discarded. No candidate reweighting and no per-provider prompt selection are permitted.

```text
PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY = execution_receipt.failure_classification
```

| Failure Classification (`execution_receipt.failure_classification`) | `P1` (`60` cells) | `P2` (`60` cells) | Total (`120` cells) |
| --- | --- | --- | --- |
| `NONE` | `23` | `21` | `44` |
| `TIMEOUT` | `35` | `22` | `57` |
| `HTTP_429` | `0` | `15` | `15` |
| `HTTP_5XX` | `2` | `1` | `3` |
| `HTTP_ERROR` | `0` | `1` | `1` |
| **TOTAL** | **`60`** | **`60`** | **`120`** |

---

## 4. Frozen Primary Counts & Deterministic 3-Criterion Evaluation

The preregistered 3-tier selection rule retains at each criterion all surviving prompts within `10.0` percentage points (`Fraction(10, 1)` / `Decimal("10.0")`) of the best surviving prompt rate:

| Criterion Order | Criterion ID | `P1` (`true` / `false` / `denom`) | `P1` Rate (%) | `P2` (`true` / `false` / `denom`) | `P2` Rate (%) | Best Surviving Rate (%) | `10.0` pp Survivor Threshold (%) | Output Survivors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Criterion 1** | `VALID_RUN_AND_SCHEMA_RATE` | `23 / 37 / 60` (`23/60`) | `38.333333333333%` (`115/3%`) | `21 / 39 / 60` (`21/60`) | `35.000000000000%` (`35/1%`) | `P1` (`38.333333333333%`) | `28.333333333333%` (`85/3%`) | `["P1", "P2"]` |
| **Criterion 2** | `EXACT_GROUNDING_PASS_RATE` | `23 / 37 / 60` (`23/60`) | `38.333333333333%` (`115/3%`) | `21 / 39 / 60` (`21/60`) | `35.000000000000%` (`35/1%`) | `P1` (`38.333333333333%`) | `28.333333333333%` (`85/3%`) | `["P1", "P2"]` |
| **Criterion 3** | `FINAL_CORE_PASS_RATE` | `20 / 40 / 60` (`20/60`) | `33.333333333333%` (`100/3%`) | `21 / 39 / 60` (`21/60`) | `35.000000000000%` (`35/1%`) | `P2` (`35.000000000000%`) | `25.000000000000%` (`25/1%`) | `["P1", "P2"]` |

- **Final Survivors after Criterion 3:** `["P1", "P2"]`
- **Tie-Break Policy:** `PREREGISTERED_ADMINISTRATIVE_ORDER_P1_BEFORE_P2`
- **Selected Prompt ID:** `P1`
- **Selection Reason:** `ADMINISTRATIVE_TIE_BREAK_AFTER_ALL_PROMPTS_SURVIVED_ALL_THREE_CRITERIA`
- **Cost / Latency / Significance / Provider-Specific Criteria Used:** `false`

---

## 5. Scientific Interpretation & Guardrails

### Formal Scientific Interpretation Statement

> P1 was selected by the preregistered administrative tie-break because both P1 and P2 remained within the 10-percentage-point survivor band through all three frozen criteria.

- `SUPERIORITY_CLAIM = false`
- Observed directional summary:
  - `P2` has a slightly higher `FINAL_CORE_PASS_RATE` (`21/60` = `35.00%` vs `20/60` = `33.33%`).
  - `P1` has a slightly higher `VALID_RUN_AND_SCHEMA_RATE` (`23/60` = `38.33%` vs `21/60` = `35.00%`) and `EXACT_GROUNDING_PASS_RATE` (`23/60` = `38.33%` vs `21/60` = `35.00%`).
  - Both prompts remained well within the `10.0` percentage-point survivor band on all three criteria.
- **Explicitly Forbidden False Claims:**
  - Must **NOT** claim that `P1` is statistically superior to `P2`.
  - Must **NOT** claim that `P1` is scientifically proven better than `P2`.
  - Must **NOT** claim that `P2` is inferior.
  - Must **NOT** claim that `P1` won all metrics.

---

## 6. Temporal Ordering Limitation

- All `60` `P1` cells (`indices 0..59`) executed before all `60` `P2` cells (`indices 60..119`).
- Prompt treatment was **not** temporally interleaved or randomized.
- All `15` primary `HTTP_429` classifications occurred in `P2/C1`.
- This pattern may reflect cumulative provider quota/rate-limit state over the batch execution window.
- **Prohibitions:**
  - Must **NOT** infer that `P2` causes `HTTP_429`.
  - Must **NOT** rerun or interleave DEV-TUNE cells after observing results.
  - Must **NOT** alter primary DEV-TUNE results.
- Because both `P1` and `P2` survive all three `10.0` percentage-point criteria, selecting `P1` is an administrative tie-break outcome rather than a superiority claim.

---

## 7. Model-Selection Firewall & Formal Prompt Lock for DEV-SELECT

### Model-Selection Firewall
- `MODEL_WINNER_SELECTED = false`
- `selected_model_id = null`
- Even though `C3` appears strongest diagnostically in `DEV-TUNE`, `DEV-TUNE` candidate rates are **never** used to select a model or eliminate a candidate.
- `DEV-SELECT` is the sole model-selection authority, and `DEV-SELECT` candidates remain exactly `["C1", "C2", "C3"]`.

### Formal Prompt Lock for Future `DEV-SELECT`
- **Allowed `DEV-SELECT` Prompt Set:** `["P1"]`
- **Forbidden Prompts in `DEV-SELECT`:** `["P2", "P3"]`
- **No prompt editing, no suffix modification, no user-template modification, and no provider-specific prompts.**
- **Locked `P1` Cryptographic Identity:**
  - `selected_prompt_id = P1`
  - `selected_prompt_version = TRAVEL_PLANNER_BENCHMARK_V2`
  - `selected_prompt_semantic_sha256 = 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11`
  - `selected_prompt_system_sha256 = 4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e`
  - `selected_prompt_user_template_sha256 = 19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de`

---

## 8. Committed Selection Artifacts & Digests

| Artifact Path | SHA256 Digest |
| --- | --- |
| `data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json` (file LF SHA256) | `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8` |
| `data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json` (internal self-SHA256) | `1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570` |
| `data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json` (file LF SHA256) | `0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114` |
