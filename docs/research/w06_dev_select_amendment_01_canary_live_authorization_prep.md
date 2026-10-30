# W06 DEV-SELECT Execution-Environment Amendment 01 — Amended Canary Live Authorization Prep

## 1. Gate & Authority Binding

- **Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP`
- **Artifact ID:** `W06-DEV-SELECT-AMENDMENT-01-CANARY-LIVE-AUTHORIZATION-PREP-V1`
- **Previous Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-POSTMERGE-CHATGPT-AUDIT` (`PASS`)
- **Authoritative Base (`develop`):** `df5a76d9d3734f77bf64abbe66d9d93492fabb3c`
- **PR #71 Merge Commit:** `df5a76d9d3734f77bf64abbe66d9d93492fabb3c` (`parent1 = ef78127ef06215849861e7d3358e24cb5222281e`, `parent2 = aa70f7bdea7cefee40894ba3c20f00bf9f01491d`)
- **PR #71 Post-Merge CI:** `run_id = 41112477246` (`event = push`, `conclusion = success`)
- **Effective Amendment Status:** `METHODOLOGY_APPROVED_OWNER_CANARY_READINESS_ATTESTED_CANARY_AUTHORIZATION_PROPOSED_LIVE_UNAUTHORIZED`
- **Internal SHA256:** `0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61`

### Bound Upstream Artifacts

| Authority | File SHA256 | Internal SHA256 |
| --- | --- | --- |
| Owner Provider Readiness Attestation (`data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json`) | `91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06` | `137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75` |
| Canary Assignment Manifest (`data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json`) | `3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96` | `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518` |
| Amendment Formal Decision (`data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json`) | `2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf` | `38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a` |
| Amendment Approval Receipt (`data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approval_receipt_v1.json`) | `171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5` | `d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991` |
| Provider Readiness & Pricing Prep (`data/evaluation/w06/w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json`) | `ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006` | `07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e` |
| Public Pricing Snapshot (`data/evaluation/w06/w06_dev_select_amendment_01_public_pricing_snapshot_v1.json`) | `2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6` | `bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe` |
| Amendment Prep (`data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_prep_v1.json`) | `e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91` | `49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a` |
| Primary Results Freeze Receipt (`data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json`) | `c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4` | `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a` |
| Primary Results Manifest (`data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json`) | `1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0` | `4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011` |
| Failure Diagnostic (`data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json`) | `b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692` | `509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8` |
| Scientific Code Bundle | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` | N/A |

## 2. Frozen Canary Candidates & Fixtures

- **C1:** `GOOGLE` / `gemini-3.8-flash` (`assigned_canary_calls = 3`)
- **C2:** `OPENAI` / `gpt-6.1-sol` (`assigned_canary_calls = 3`)
- **C3:** `ANTHROPIC` / `claude-sonnet-5-5` (`assigned_canary_calls = 3`)
- **Candidate Substitution Permitted:** `False`
- **Fourth Model Permitted:** `False`
- **Exact Canary Fixtures:** `W06-DEV-TUNE-007, W06-DEV-TUNE-011, W06-DEV-TUNE-015`
- **Additional / Replacement / Final100 Fixtures Permitted:** `False` / `False` / `False`

## 3. Exact 9-Cell Canary Execution Order

| Order | Short Label | Cell ID | Fixture ID | Destination | Candidate | Provider | Model | Timeout (ms) | Delay Before Next (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `007 / C1` | `W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | Hà Nội (`ha-noi`) | `C1` | `GOOGLE` | `gemini-3.8-flash` | `180000` | `2000` |
| 2 | `007 / C2` | `W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | Hà Nội (`ha-noi`) | `C2` | `OPENAI` | `gpt-6.1-sol` | `180000` | `2000` |
| 3 | `007 / C3` | `W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007` | `W06-DEV-TUNE-007` | Hà Nội (`ha-noi`) | `C3` | `ANTHROPIC` | `claude-sonnet-5-5` | `180000` | `2000` |
| 4 | `011 / C1` | `W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | Đà Nẵng (`da-nang`) | `C1` | `GOOGLE` | `gemini-3.8-flash` | `180000` | `2000` |
| 5 | `011 / C2` | `W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | Đà Nẵng (`da-nang`) | `C2` | `OPENAI` | `gpt-6.1-sol` | `180000` | `2000` |
| 6 | `011 / C3` | `W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011` | `W06-DEV-TUNE-011` | Đà Nẵng (`da-nang`) | `C3` | `ANTHROPIC` | `claude-sonnet-5-5` | `180000` | `2000` |
| 7 | `015 / C1` | `W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | Hạ Long (`ha-long`) | `C1` | `GOOGLE` | `gemini-3.8-flash` | `180000` | `2000` |
| 8 | `015 / C2` | `W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | Hạ Long (`ha-long`) | `C2` | `OPENAI` | `gpt-6.1-sol` | `180000` | `2000` |
| 9 | `015 / C3` | `W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015` | `W06-DEV-TUNE-015` | Hạ Long (`ha-long`) | `C3` | `ANTHROPIC` | `claude-sonnet-5-5` | `180000` | `0` |

- **Total Maximum Canary Generation Calls:** `9`

## 4. Frozen Runtime Policy

- **Timeout:** `180000 ms` (`T3_CANDIDATE_180S`)
- **Fixed Inter-Call Delay:** `2000 ms` (`P1_FIXED_2000MS_INTER_CALL_DELAY`; `8` intervals = `16000 ms`)
- **Automatic Retry:** `0`
- **Transport Retry:** `0`
- **Manual Retry:** `0`
- **LLM Repair:** `0`
- **Semantic Repair:** `0`
- **Fallback:** `False`
- **Generation Calls per Assigned Cell:** `1`
- **Adaptive Pacing / Dynamic Timeout / Special Treatment / Retry After Error Permitted:** `False` / `False` / `False` / `False`

## 5. Canary Purpose, Operational PASS Criterion, Aggregate Decision & Fail-Stop Rule

- **Purpose:** `OPERATIONAL_EXECUTION_ENVIRONMENT_READINESS_CHECK` (NOT planner-quality model selection, NOT scientific superiority evaluation, NOT comparative benchmark, NOT Final100 evaluation).
- **Operational PASS Conditions per Cell:**
  - `correct_candidate_provider_model_config_used = True`
  - `exactly_one_generation_call_attempted = True`
  - `no_authentication_failure = True`
  - `no_billing_or_credit_failure = True`
  - `no_client_timeout = True`
  - `no_http_4xx_failure = True`
  - `no_http_5xx_failure = True`
  - `no_model_access_failure = True`
  - `no_provider_transport_failure = True`
  - `no_quota_or_rate_limit_rejection = True`
  - `provider_returns_response = True`
  - `required_provider_model_identity_evidence_captured = True`
  - `retry_count_equals_zero = True`
- **Planner Schema Validity / Final-Core Quality Redefines Operational PASS:** `False` / `False`
- **Aggregate Canary Decision Requirement:** `9/9` (`ALL_9_CANARY_OPERATIONAL_PASS == true`; partial/majority/2-of-3/provider-average thresholds forbidden).
- **Fail-Stop Rule:**
  - `fail_closed_on_any_operational_cell_failure = True`
  - `preserve_exact_failure_evidence = True`
  - `retry_on_failure_permitted = False`
  - `replace_fixture_on_failure_permitted = False`
  - `rerun_same_cell_permitted = False`
  - `continue_under_improvised_rule_permitted = False`
  - `rerun_because_failure_may_have_been_temporary_permitted = False`
  - `comparative_remains_unauthorized_on_failure = True`
  - `return_to_chatgpt_audit_on_failure = True`

## 6. Proposed vs Effective Authorization & Firewalls

- **`CANARY_LIVE_AUTHORIZATION_PROPOSED`:** `True`
- **`AMENDED_CANARY_LIVE_AUTHORIZED`:** `False`
- **`AMENDED_COMPARATIVE_LIVE_AUTHORIZED`:** `False`
- **`CANARY_EXECUTED` / `COMPARATIVE_EXECUTED`:** `False` / `False`
- **`LIVE_PROVIDER_CALLS_NEW`:** `0`
- **`ENV_FILE_READ` / `API_KEYS_INSPECTED`:** `False` / `False`
- **`MODEL_WINNER_SELECTED` / `SELECTED_MODEL_ID`:** `False` / `None`
- **`STOCHASTICITY_EXECUTION_STARTED`:** `False`
- **`FINAL100_USED` / `FINAL100_STATUS`:** `False` / `NO-GO`
- **Primary Strict Rates Unchanged:** `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`
- **Required Gates Before Effective Live Canary Authorization:**
  - 1. This PREP PR passes exact-head CI
  - 2. ChatGPT independently audits the PREP PR
  - 3. ChatGPT returns PASS
  - 4. The authorization artifact PR is merged normally into develop
  - 5. Post-merge CI on develop succeeds
  - 6. ChatGPT explicitly issues the live-canary execution task

- **Next Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP-CHATGPT-AUDIT`
