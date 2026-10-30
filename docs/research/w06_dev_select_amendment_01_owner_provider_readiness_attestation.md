# W06 DEV-SELECT Amendment 01 — Owner Provider Readiness Attestation Receipt

## 1. Purpose & Candidate Authority Status

- **Task ID**: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-RECEIPT-PREP`
- **Corrective Task ID**: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-CORRECTIVE-01`
- **Artifact ID**: `W06-DEV-SELECT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-V1`
- **Authoritative Base (`develop`)**: `ef78127ef06215849861e7d3358e24cb5222281e`
- **Owner Attestation Evidence Date**: `2026-10-30`
- **Observation Mode**: `MANUAL_PROVIDER_DASHBOARD_OBSERVATION_SANITIZED`
- **Attestation Scope**: `CANARY_READINESS_ATTESTATION_ONLY`
- **Receipt Candidate Status**: `PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE`
- **Repository Authoritative Before Merge**: `false`
- **Becomes Repository Authoritative After ChatGPT PASS + Normal Merge + Post-Merge CI**: `true`
- **Receipt File SHA256**: `91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06`
- **Receipt Internal SHA256**: `137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75`

> **Strictly Offline Readiness Attestation Only**: This receipt records sanitized owner-observed provider readiness for the 9-cell readiness canary gate. It does **NOT** authorize or execute any live provider or model generation call (`LIVE_PROVIDER_CALLS_NEW = 0`).

## 2. Sanitization & Secret / Account-Identifier Firewall

- `screenshots_stored_in_repository`: `false`
- `api_keys_stored`: `false`
- `api_key_prefixes_or_suffixes_stored`: `false`
- `payment_card_details_stored`: `false`
- `billing_account_ids_stored`: `false`
- `project_numeric_ids_stored`: `false`
- `organization_ids_stored`: `false`
- `email_addresses_stored`: `false`
- `personal_names_stored`: `false`
- `payment_transaction_identifiers_stored`: `false`
- `exact_prepaid_vnd_balance_stored`: `false`
- `exact_current_dollar_balance_stored`: `false`
- `env_file_read`: `false`
- `api_keys_inspected`: `false`

## 3. Sanitized Provider Readiness Attestation by Candidate

### 3.1 Google / `C1` (`gemini-3.8-flash`)

- `candidate_id`: `C1`
- `provider`: `GOOGLE`
- `exact_model_id`: `gemini-3.8-flash`
- `billing_surface`: `GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER`
- `billing_active`: `true`
- `paid_tier_active`: `true`
- `usage_tier`: `TIER_1`
- `positive_prepaid_credit_available`: `true`
- `exact_model_visible_in_rate_limit_dashboard`: `true`
- `standard_rpm_limit`: `1000`
- `standard_input_tpm_limit`: `2000000`
- `standard_rpd_limit`: `10000`
- `required_max_candidate_calls_under_frozen_amendment`: `63`
- `canary_assigned_calls`: `3`
- `rpm_sufficient_for_frozen_canary`: `true`
- `tpm_sufficient_for_frozen_canary`: `true`
- `rpd_sufficient_for_frozen_canary`: `true`
- `provider_readiness`: `READY_FOR_CANARY`

### 3.2 OpenAI / `C2` (`gpt-6.1-sol`) — Provenance-Separated Readiness Evidence

- `candidate_id`: `C2`
- `provider`: `OPENAI`
- `exact_model_id`: `gpt-6.1-sol`
- `billing_surface`: `OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER`
- **A. `OWNER_OBSERVED_ACCOUNT_STATE`** (directly observed by Project Owner in OpenAI dashboard; no doc-derived RPM/TPM values claimed as dashboard-observed):
  - `billing_active`: `true`
  - `positive_api_credit_available`: `true`
  - `api_credit_sufficient_for_canary_planning_envelope`: `true`
  - `usage_tier`: `BUILD`
  - `organization_spend_limit_blocking`: `false`
- **B. `OFFICIAL_PROVIDER_DERIVED_RATE_LIMIT_EVIDENCE`**:
  - `exact_model_id`: `gpt-6.1-sol`
  - `usage_tier`: `BUILD`
  - `standard_rpm_limit`: `5000`
  - `standard_tpm_limit`: `1000000`
  - `source`: `official OpenAI gpt-6.1-sol model documentation`
  - `authority_url`: `https://developers.openai.com/api/docs/models/gpt-6.1-sol`
  - `evidence_classification`: `OFFICIAL_PROVIDER_DOC_DERIVED_FROM_OWNER_OBSERVED_TIER`
  - `rpm_or_tpm_manually_observed_in_owner_dashboard`: `false`
  - `required_max_candidate_calls_under_frozen_amendment`: `63`
  - `canary_assigned_calls`: `3`
  - `rpm_sufficient_for_frozen_canary`: `true`
  - `tpm_sufficient_for_frozen_canary`: `true`
- **C. `HISTORICAL_MODEL_ACCESS_EVIDENCE`**:
  - `evidence_classification`: `FROZEN_REPOSITORY_HISTORICAL_EXECUTION_EVIDENCE`
  - `separate_from_owner_dashboard_observation`: `true`
  - `completed_primary_dev_select_c2_cells`: `8`
  - `total_completed_p1_c2_cells_in_repo`: `12`
  - `observed_provider_model_snapshot`: `gpt-6.1-sol-2026-08-05`
- `provider_readiness`: `READY_FOR_CANARY`

### 3.3 Anthropic / `C3` (`claude-sonnet-5-5`) — Per-Minute Rate Limits & Offline Capacity Proofs

- `candidate_id`: `C3`
- `provider`: `ANTHROPIC`
- `exact_model_id`: `claude-sonnet-5-5`
- `billing_surface`: `ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL`
- **Owner-Observed Account-Specific Dashboard State (`PER_MINUTE` window)**:
  - `billing_active`: `true`
  - `positive_credit_available`: `true`
  - `exact_model_visible_in_rate_limit_dashboard`: `true`
  - `account_tier`: `EVALUATION_TIER`
  - `requests_per_minute_limit`: `1000`
  - `input_tokens_per_minute_limit`: `500000`
  - `output_tokens_per_minute_limit`: `80000`
  - `rate_limit_dimensions`: `['RPM', 'ITPM', 'OTPM']`
  - `rate_limit_window`: `PER_MINUTE`
  - `generic_public_claude_tier_table_substituted`: `false`
- **Offline Numeric Input Capacity Proof (`W06-DEV-TUNE-007`, `W06-DEV-TUNE-011`, `W06-DEV-TUNE-015`)**:
  - `C3_INPUT_CAPACITY_STATUS`: `PROVEN_SUFFICIENT_FOR_CANARY_BY_DETERMINISTIC_OFFLINE_BOUND`
  - `W06-DEV-TUNE-007` (`ha-noi`): `authoritative_p1_usage_available = false`, `exact_historical_p1_input_tokens = null`, `serialized_wire_request_utf8_bytes = 50794` (`DETERMINISTIC_SERIALIZED_WIRE_PAYLOAD_UTF8_BYTE_UPPER_BOUND`)
  - `W06-DEV-TUNE-011` (`da-nang`): `authoritative_p1_usage_available = true`, `exact_historical_p1_input_tokens = 41165` (`serialized_wire_request_utf8_bytes = 89229`)
  - `W06-DEV-TUNE-015` (`ha-long`): `authoritative_p1_usage_available = true`, `exact_historical_p1_input_tokens = 28412` (`serialized_wire_request_utf8_bytes = 61683`)
  - `three_call_input_reference_source`: `HYBRID_FROZEN_HISTORICAL_C3_DEV_TUNE_P1_USAGE_AND_DETERMINISTIC_SERIALIZED_WIRE_BYTE_UPPER_BOUND`
  - `three_call_input_token_reference`: `120371` (`120371 < 500000 ITPM (pure wire-byte upper bound 201706 < 500000 ITPM)`)
  - `three_call_pure_serialized_wire_utf8_byte_upper_bound`: `201706` (`< 500000 ITPM`)
  - `future_execution_guaranteed_to_consume_exact_same_tokens`: `false`
- **Offline Conservative Output Upper-Bound Reference & Request Capacity Proof**:
  - `canary_assigned_calls`: `3`
  - `configured_max_output_tokens_per_call`: `16384`
  - `conservative_three_call_configured_output_upper_bound_reference`: `49152` (`49152 < 80000 OTPM`)
  - `max_tokens_setting_itself_consumes_or_reserves_otpm_claimed`: `false`
  - `three_call_request_comparison`: `3 < 1000 RPM`
- `provider_readiness`: `READY_FOR_CANARY`
- `generalized_as_readiness_proof_for_future_60_call_comparative_run`: `false`
- `comparative_readiness_must_be_rechecked_before_comparative_authorization`: `true`

## 4. Effective Readiness State & Non-Authorization Semantics

- `OWNER_PROVIDER_READINESS_ATTESTED`: `true`
- `C1_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `C2_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `C3_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `ALL_CANARY_PROVIDER_READINESS`: `READY`
- `readiness_implications`:
  - `provider_availability_guaranteed`: `false`
  - `all_9_canary_calls_guaranteed_to_complete`: `false`
  - `schema_or_core_quality_guaranteed`: `false`
  - `provider_5xx_impossible`: `false`
  - `provider_high_demand_failures_impossible`: `false`
  - `comparative_execution_authorized`: `false`
  - `final100_authorized`: `false`
- `READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION`: `true`
- `CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9`: `true`
- `CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE`: `true`
- `AMENDED_CANARY_LIVE_AUTHORIZED`: `false`
- `AMENDED_COMPARATIVE_LIVE_AUTHORIZED`: `false`
- `AMENDED_LIVE_AUTHORIZED`: `false`
- `AMENDED_LIVE_EXECUTED`: `false`
- `CANARY_EXECUTED`: `false`
- `COMPARATIVE_EXECUTED`: `false`
- `LIVE_PROVIDER_CALLS_NEW`: `0`

## 5. Bound Upstream Authorities & Frozen Scientific Policy

- `develop` base SHA: `ef78127ef06215849861e7d3358e24cb5222281e`
- Provider Readiness / Pricing PREP (`data/evaluation/w06/w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json`): file `ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006`, internal `07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e`
- Public Pricing Snapshot (`data/evaluation/w06/w06_dev_select_amendment_01_public_pricing_snapshot_v1.json`): file `2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6`, internal `bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe`
- Approval Receipt (`data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_approval_receipt_v1.json`): file `171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5`, internal `d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991`
- Formal Decision (`data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json`): file `2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf`, internal `38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a`
- Canary Manifest (`data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json`): file `3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96`, internal `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518`
- Primary Results-Freeze Receipt (`data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json`): file `c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4`, internal `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a`
- Scientific Code Bundle SHA256: `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`
- Primary Strict Metric Rates Preserved: `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60` (erroneous report `0/60, 43/60, 0/60` rejected)
- Fairness / Environment Policy: `OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT`, `timeout_ms = 180000`, `inter_call_delay_ms = 2000`, zero retries/repairs/fallbacks, `9 + 180 = 189` calls (`63` max per candidate)
- Next Gate: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-CORRECTIVE-01-CHATGPT-AUDIT`
