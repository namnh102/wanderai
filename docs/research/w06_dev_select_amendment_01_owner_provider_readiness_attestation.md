# W06 DEV-SELECT Amendment 01 — Owner Provider Readiness Attestation Receipt

## 1. Purpose & Candidate Authority Status

- **Task ID**: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-RECEIPT-PREP`
- **Artifact ID**: `W06-DEV-SELECT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-V1`
- **Authoritative Base (`develop`)**: `ef78127ef06215849861e7d3358e24cb5222281e`
- **Owner Attestation Evidence Date**: `2026-10-30`
- **Observation Mode**: `MANUAL_PROVIDER_DASHBOARD_OBSERVATION_SANITIZED`
- **Attestation Scope**: `CANARY_READINESS_ATTESTATION_ONLY`
- **Receipt Candidate Status**: `PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE`
- **Repository Authoritative Before Merge**: `false`
- **Becomes Repository Authoritative After ChatGPT PASS + Normal Merge + Post-Merge CI**: `true`
- **Receipt File SHA256**: `622878407081f5bb4566d8a29d827258031b52edecb067e0cf1ebe253a162a9d`
- **Receipt Internal SHA256**: `45af6219a72bcef6c79bd6b83d7a95f6c549342e13d73e266abe4ac1260edf86`

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

## 3. Sanitized Owner-Observed Provider Readiness by Candidate

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

### 3.2 OpenAI / `C2` (`gpt-6.1-sol`)

- `candidate_id`: `C2`
- `provider`: `OPENAI`
- `exact_model_id`: `gpt-6.1-sol`
- `billing_surface`: `OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER`
- `billing_active`: `true`
- `positive_api_credit_available`: `true`
- `api_credit_sufficient_for_canary_planning_envelope`: `true`
- `usage_tier`: `BUILD`
- `organization_spend_limit_blocking`: `false`
- `exact_model_access_supported_by`:
  - `current official gpt-6.1-sol model availability for Build tier`
  - `historical successful frozen primary C2 responses using the exact candidate family/config`
- `standard_rpm_limit`: `5000`
- `standard_tpm_limit`: `1000000`
- `required_max_candidate_calls_under_frozen_amendment`: `63`
- `canary_assigned_calls`: `3`
- `rpm_sufficient_for_frozen_canary`: `true`
- `tpm_sufficient_for_frozen_canary`: `true`
- `provider_readiness`: `READY_FOR_CANARY`

### 3.3 Anthropic / `C3` (`claude-sonnet-5-5`)

- `candidate_id`: `C3`
- `provider`: `ANTHROPIC`
- `exact_model_id`: `claude-sonnet-5-5`
- `billing_surface`: `ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL`
- `billing_active`: `true`
- `positive_credit_available`: `true`
- `exact_model_visible_in_rate_limit_dashboard`: `true`
- `account_tier`: `EVALUATION_TIER`
- `input_token_limit`: `500000`
- `output_token_limit`: `80000`
- `request_limit`: `1000`
- `canary_assigned_calls`: `3`
- `configured_max_output_tokens_per_call`: `16384`
- `configured_three_call_max_output_reference`: `49152` (`49152 < 80000`)
- `input_capacity_sufficient_for_frozen_canary_planning_envelope`: `true`
- `output_capacity_sufficient_for_frozen_canary_reference`: `true`
- `request_capacity_sufficient_for_frozen_canary`: `true`
- `provider_readiness`: `READY_FOR_CANARY`
- `generalized_as_readiness_proof_for_future_60_call_comparative_run`: `false`
- `comparative_readiness_must_be_rechecked_before_comparative_authorization`: `true`

## 4. Effective Readiness State & Non-Authorization Semantics

- `OWNER_PROVIDER_READINESS_ATTESTED`: `true`
- `C1_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `C2_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `C3_PROVIDER_READINESS`: `READY_FOR_CANARY`
- `ALL_CANARY_PROVIDER_READINESS`: `READY`
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
- Next Gate: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-CHATGPT-AUDIT`
