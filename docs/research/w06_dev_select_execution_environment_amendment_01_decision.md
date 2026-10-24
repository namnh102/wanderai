# W06 DEV-SELECT Execution-Environment Amendment 01 Formal Decision Freeze (`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-FREEZE`)

## 1. Governance & Authority Bindings

- **Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-FREEZE`
- **Decision Artifact ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-DECISION-V1`
- **Canary Assignment Manifest ID:** `W06-DEV-SELECT-AMENDMENT-01-CANARY-ASSIGNMENT-MANIFEST-V1`
- **ChatGPT Final Methodology Decision for Freeze:** `APPROVED_FOR_FORMAL_FREEZE`
- **Final Methodology Decision Authority:** `CHATGPT`
- **Prep Gate Status:** `CLOSED`
- **Authoritative Base (`develop`):** `bc913ed61097f26db8eae87b9fe47d1869dc3ec5`
- **Prep Base (`develop`):** `811255a7dd00234d63184ab483e9f88b1f2d8554`
- **Prep Artifact Path:** `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_prep_v1.json`
- **Prep Artifact File SHA256 (LF):** `e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91`
- **Prep Artifact Internal SHA256:** `49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a`
- **Decision Artifact Path:** `data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json`
- **Decision Artifact File SHA256 (LF):** `2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf`
- **Decision Artifact Internal SHA256:** `38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a`
- **Canary Manifest Path:** `data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json`
- **Canary Manifest File SHA256 (LF):** `3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96`
- **Canary Manifest Internal SHA256:** `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518`
- **Scientific Code Bundle SHA256:** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` (unchanged)

> [!IMPORTANT]
> **Amendment Lifecycle & Live Execution Firewall:**
> - `AMENDMENT_METHODOLOGY_SELECTED = true`
> - `AMENDMENT_APPROVED = false` *(becomes `true` only in the authoritative decision receipt after ChatGPT audits and merges this formal-decision PR)*
> - `AMENDED_LIVE_AUTHORIZED = false` (`AMENDED_CANARY_LIVE_AUTHORIZED = false`, `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`)
> - `AMENDED_LIVE_EXECUTED = false`
> - `LIVE_PROVIDER_CALLS_NEW = 0`
> - `PRIMARY_EXPERIMENT_MUTATED = false`
> - `PRIMARY_RESULTS_REPLACED = false`
> - `PRIMARY_DENOMINATORS_CHANGED = false`
> - `MODEL_WINNER_SELECTED = false` (`SELECTED_MODEL_ID = null`)
> - `STOCHASTICITY_EXECUTION_STARTED = false`
> - `FINAL100_USED = false`

---

## 2. ChatGPT-Selected Frozen Policy Bundle (Sections 1..7)

| Policy Dimension | Selected Option ID / Value | Frozen Specification |
|---|---|---|
| **1. Track Classification** | `SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK` | Preserves the primary 180-cell benchmark (`PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK`) immutable and reportable. |
| **2. Fairness Policy** | `OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT` | Symmetric timeout and deterministic non-adaptive pacing across `C1`, `C2`, `C3` with pre-live provider-readiness verification and `retry = 0`. |
| **3. Timeout Policy** | `T3_CANDIDATE_180S` (`timeout_ms = 180000`) | Applied symmetrically to `C1`, `C2`, `C3` (`180,000 ms` / `180 s`). Removes the frozen 55s client-side cutoff from the secondary configuration and materially reduces client-side right-censoring risk. Does **NOT** guarantee completion; provider-side deadlines, capacity failures, quota errors, or other transport failures may still prevent observation. |
| **4. Pacing Policy** | `P1_FIXED_2000MS_INTER_CALL_DELAY` (`inter_call_delay_ms = 2000`) | `fixed = true`, `deterministic = true`, `adaptive = false`, `response_dependent = false`. Pacing bounds client-issued request cadence only. It **MUST NOT** be claimed to prevent provider HTTP 503/high-demand failures. |
| **5. Retry Policy** | `R0_STRICT_ZERO_RETRY` | `automatic_retry = 0`, `transport_retry = 0`, `manual_retry = 0`, `llm_repair = 0`, `semantic_repair = 0`, `fallback = false`. |
| **6. Fixture Policy** | `POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET` | Stage 1: exact `3` canary fixtures (`9` cells) + Stage 2: exact `60` `DEV-SELECT` comparative fixtures (`180` cells). |
| **7. Call-Budget Policy** | `S2_READINESS_CANARY_PLUS_COMPARATIVE_180` | `readiness_canary_assigned_calls = 9`, `comparative_assigned_calls = 180`, `maximum_generation_calls = 189`, `calls_per_candidate_max = 63` (`3` canary + `60` comparative per candidate). All variable `"3..9"` semantics are removed for the selected policy: the assigned canary matrix is **EXACTLY `9` cells**. |

---

## 3. Exact Frozen Canary Fixtures & Structural Rationale (Section 8)

All `3` canary fixtures are bound to `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json` (`SHA256 = bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`):

| Slot | Fixture ID | Destination | Days | Interest Count | Interests | Budget (VND) | Travel Style | Scenario SHA256 |
|---|---|---|---:|---:|---|---:|---|---|
| **A** | `W06-DEV-TUNE-007` | `Hà Nội` (`ha-noi`) | `4` | `3` | `coffee_culture`, `culture_history`, `nature_outdoor` | `8,000,000` | `LUXURY` | `b74f1551127fa35e67086ae3f82f6baf749251ef48fa95d80677bed495d8cd6d` |
| **B** | `W06-DEV-TUNE-011` | `Đà Nẵng` (`da-nang`) | `3` | `2` | `food_cuisine`, `shopping_local` | `1,500,000` | `BACKPACKER` | `48743d390e4168b8972978e5902a722804635bc9f0b9ecab5f20e06d2b3dfa97` |
| **C** | `W06-DEV-TUNE-015` | `Hạ Long` (`ha-long`) | `2` | `1` | `coffee_culture` | `4,000,000` | `COMFORT` | `265c1a354a32b71fe164bcc27c57f2782bb90f133bca973297fad5f4aa618298` |

### Fixture-Selection Rationale
- Chosen by **deterministic structural coverage only**:
  - all `3` destinations (`{Hà Nội, Đà Nẵng, Hạ Long}`) covered **exactly once**,
  - day counts (`{2, 3, 4}`) covered **exactly once**,
  - interest counts (`{1, 2, 3}`) covered **exactly once**.
- **No** prior model-quality output or prior canary success/failure was used to select or justify these fixture IDs (`prior_model_quality_output_used = false`, `prior_canary_success_or_failure_used = false`).

---

## 4. Exact 9-Cell Canary Call Matrix & Execution Order (Section 9)

- **Pacing:** Fixed `2,000 ms` (`2.0 s`) between consecutive canary cells (`8` intervals = `16,000 ms` total inter-cell delay).
- **Invariants:** All `9` cells are assigned once (`attempt_number = 1`). No alternate fixtures (`alternate_fixtures_permitted = false`), no reruns (`reruns_permitted = false`), no retries (`retries_permitted = false`).

| Order | Matrix Label | Cell ID | Fixture ID | Candidate | Requested Model | Timeout (`ms`) | Next-Cell Delay (`ms`) | Selection Weight |
|---:|---|---|---|---|---|---:|---:|---:|
| `01` | `01 W06-DEV-TUNE-007 × C1` | `W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | `C1` | `gemini-3.8-flash` | `180000` | `2000` | `0` |
| `02` | `02 W06-DEV-TUNE-007 × C2` | `W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | `C2` | `gpt-6.1-sol` | `180000` | `2000` | `0` |
| `03` | `03 W06-DEV-TUNE-007 × C3` | `W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | `C3` | `claude-sonnet-5-5` | `180000` | `2000` | `0` |
| `04` | `04 W06-DEV-TUNE-011 × C1` | `W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | `C1` | `gemini-3.8-flash` | `180000` | `2000` | `0` |
| `05` | `05 W06-DEV-TUNE-011 × C2` | `W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | `C2` | `gpt-6.1-sol` | `180000` | `2000` | `0` |
| `06` | `06 W06-DEV-TUNE-011 × C3` | `W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | `C3` | `claude-sonnet-5-5` | `180000` | `2000` | `0` |
| `07` | `07 W06-DEV-TUNE-015 × C1` | `W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | `C1` | `gemini-3.8-flash` | `180000` | `2000` | `0` |
| `08` | `08 W06-DEV-TUNE-015 × C2` | `W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | `C2` | `gpt-6.1-sol` | `180000` | `2000` | `0` |
| `09` | `09 W06-DEV-TUNE-015 × C3` | `W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | `C3` | `claude-sonnet-5-5` | `180000` | `0` | `0` |

---

## 5. Canary Selection Weight, Operational PASS Rule & Canary Gate Rule (Sections 10..12)

### 5.1 Canary Selection Weight (`selection_weight = 0`)
Canary results **MUST NOT**:
- select a model,
- contribute to the DEV-SELECT comparative denominator (`60`),
- contribute to stochasticity,
- contribute to Final100, or
- alter prompt/model/schema/evaluator parameters.

### 5.2 Per-Cell Operational Canary PASS Rule
Each assigned canary cell is `OPERATIONAL_PASS` only if **all** of the following hold:
1. correct frozen candidate/config is requested;
2. exactly `1` outbound generation request is attempted;
3. `retry` count = `0`;
4. no API auth rejection;
5. no billing/credit rejection;
6. no quota/rate-limit rejection;
7. no model-access rejection;
8. no client timeout;
9. no provider transport failure;
10. no HTTP/provider `4xx`/`5xx` failure;
11. successful provider response is received;
12. request/cell identity evidence is valid;
13. returned model identity, when supplied by provider, does not mismatch the frozen candidate.

> [!IMPORTANT]
> **Planner Quality Firewall:**
> Schema validity, exact grounding, opening-hour compliance, budget metric, or `FINAL_CORE_PASS` **MUST NOT** determine operational canary `PASS`/`FAIL`.
> A successful provider response that fails schema/core evaluation remains **`OPERATIONAL_PASS`**.

### 5.3 Canary Gate Rule (`9/9` Required)
- `CANARY_GATE_PASS` requires operational `PASS` for **all `9` assigned cells** (`9/9`).
- If **any one** of the `9` cells operationally fails:
  - `CANARY_GATE_PASS = false`
  - `AMENDED_COMPARATIVE_AUTHORIZED = false`
  - **No automatic** retry, rerun, replacement fixture, timeout increase, pacing change, provider-specific parameter change, or prompt/model/schema modification is permitted.
  - Execution returns immediately to **`CHATGPT_HOLD`**.

---

## 6. Comparative Batch Policy & Separate Authorization Gate (Section 13)

If and only if the future frozen canary result is independently audited `PASS` by ChatGPT **AND** a **separate** ChatGPT authorization gate approves the comparative run:
- **Comparative Fixtures:** Exact `W06-DEV-SELECT-001..W06-DEV-SELECT-060` (`60` fixtures from `w06_dev_fixtures_freeze_v1.json`)
- **Candidates:** `C1`, `C2`, `C3`
- **Assigned Comparative Cells:** `60 × 3 = 180`
- **Prompt:** `P1` unchanged
- **Schema:** Portable Generation Schema V2 (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`) unchanged
- **Evaluator:** unchanged
- **Primary Model-Selection Metrics:** `VALID_RUN_AND_SCHEMA_RATE`, `EXACT_GROUNDING_PASS_RATE`, `FINAL_CORE_PASS_RATE`
- **Practical-Tie Survivor Threshold:** `10` percentage points (`0.1` / `6` of `60` cells) unchanged
- **Mandatory Two-Gate Separation:** Canary `PASS` **MUST NOT** automatically launch comparative execution (`canary_pass_automatically_launches_comparative_execution = false`, `separate_chatgpt_authorization_gate_required_before_180_comparative_calls = true`).

---

## 7. Provider-Readiness Boundary & Pricing Status (Sections 19..20)

### 7.1 Provider-Readiness Boundary (`OWNER_AND_PROVIDER_ATTESTATION` != `LIVE_READINESS_CANARY`)
- **C1 (`Google / gemini-3.8-flash`):** Paid/billing-enabled tier; daily/request quota and RPM/TPM limits sufficient for the exact total authorized C1 call count (under selected `S2` = max `63` C1 calls), with no Free Tier `20-RPD` ceiling.
- **C2 (`OpenAI / gpt-6.1-sol`):** Active billing/credit, verified model access, and sufficient account limits for the exact authorized C2 volume (under selected `S2` = max `63` C2 calls).
- **C3 (`Anthropic / claude-sonnet-5-5`):** Active billing, positive credits sufficient for the exact authorized C3 volume (under selected `S2` = max `63` C3 calls), and verified model access.
- **Secret Safety:** Zero secrets, key hashes, prefixes, organization IDs, billing IDs, or project IDs in artifacts or logs.

### 7.2 Pricing Boundary
- `current_price_input_status = EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION`
- `hard_maximum_claimed = false`
- Historical `LOW`/`HIGH` envelopes from frozen repository price snapshots (`2026-10-16` runner registry and `2026-10-17` Preflight 01D receipt) remain planning references only; they are **not** hard cost caps.
