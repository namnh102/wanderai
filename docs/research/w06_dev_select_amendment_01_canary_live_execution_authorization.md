# W06 DEV-SELECT Amendment 01 — Canary Live Execution Authorization Receipt (V1)

## 1. Gate & Task Identity

- **Artifact ID:** `W06-DEV-SELECT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-V1`
- **Prep Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP`
- **Previous Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-POSTMERGE-CHATGPT-AUDIT` (`PASS`)
- **Authorized Future Live Execution Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`
- **Next Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP-CHATGPT-AUDIT`
- **Receipt Path:** `data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`
- **Receipt FILE SHA256:** `e68c7ad76e9261aaf687660dd20441118ec192a727a6cbf88b15cf4f0268d684`
- **Receipt INTERNAL SHA256:** `d045b1c5e45675dd330515aad5e591e9efb94e219d4418aa739eb8b2270ad8c5`

## 2. Operational Governance & Prep Firewall

- `CANARY_LIVE_EXECUTION_AUTHORIZED = true` inside the JSON receipt payload as required by the merged launcher verifier.
- **Receipt PREP / Offline QA Only:** This receipt is NOT operationally executable during the PREP task.
- Live execution (`python scripts/run_w06_dev_select_amendment_01_canary_live_v1.py --execute-live --confirm-frozen-9-canary-cells`) MUST NOT be invoked until:
  1. Receipt PR passes exact-head CI;
  2. ChatGPT audits receipt PR = `PASS`;
  3. Receipt PR is normally merged into `develop`;
  4. Post-merge `push` CI passes on `develop`;
  5. ChatGPT post-merge audit = `PASS`;
  6. ChatGPT explicitly issues `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`.
- `LIVE_PROVIDER_CALLS_NEW = 0`
- `ENV_FILE_READ = false`
- `API_KEYS_INSPECTED = false`

## 3. Cryptographic & Git Provenance of Merged Launcher (PR #73)

- **Launcher Path:** `scripts/run_w06_dev_select_amendment_01_canary_live_v1.py`
- **Launcher Identity / Version:** `W06-AMENDMENT-01-CANARY-LIVE-LAUNCHER-V1` / `1.0.0`
- **Launcher File LF SHA256:** `7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2`
- **Launcher PR Number:** `#73` (`MERGED`)
- **PR #73 Base (`develop` Parent 1):** `1ebe30c251958542088a3056dcfc6b780dac3a88`
- **Accepted PR #73 HEAD (Parent 2):** `c6c984aef8712538c8c29587caff1e0bbb36afaa`
- **PR #73 Merge Commit on `develop`:** `3e103587ab0324717c03af14e236dc37fc579295`
- **Authorized Code-Basis Commit SHA:** `3e103587ab0324717c03af14e236dc37fc579295`
- **Post-Merge `push` CI Run ID:** `41181343010` (`conclusion = success` across `ai-service`, `backend`, `data-contract`, `mobile`)
- **Scientific Code Bundle SHA256:** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`

## 4. Bound Upstream Authorities

| Authority | Path | FILE SHA256 | INTERNAL SHA256 |
| :--- | :--- | :--- | :--- |
| Canary Authorization PREP | `data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json` | `21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61` | `0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61` |
| Canary Authorization PREP Markdown | `docs/research/w06_dev_select_amendment_01_canary_live_authorization_prep.md` | `d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da` | `N/A` |
| Canary Assignment Manifest | `data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json` | `3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96` | `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518` |
| Owner Provider Readiness Attestation | `data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json` | `91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06` | `137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75` |

## 5. Frozen Candidate Set & Locked Prompt

- **Prompt ID:** `P1` (Semantic SHA256: `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11`)
- **Candidates:**
  - `C1`: Google — `gemini-3.8-flash`
  - `C2`: OpenAI — `gpt-6.1-sol`
  - `C3`: Anthropic — `claude-sonnet-5-5`

## 6. Frozen Fixtures & Exact 9-Cell Execution Order

- **Exact Canary Fixtures:** `W06-DEV-TUNE-007, W06-DEV-TUNE-011, W06-DEV-TUNE-015`

| Order Index | Short Label | Fixture ID | Candidate ID | Cell ID |
| :---: | :---: | :--- | :---: | :--- |
| 1 | `007 / C1` | `W06-DEV-TUNE-007` | `C1` | `W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007` |
| 2 | `007 / C2` | `W06-DEV-TUNE-007` | `C2` | `W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007` |
| 3 | `007 / C3` | `W06-DEV-TUNE-007` | `C3` | `W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007` |
| 4 | `011 / C1` | `W06-DEV-TUNE-011` | `C1` | `W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011` |
| 5 | `011 / C2` | `W06-DEV-TUNE-011` | `C2` | `W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011` |
| 6 | `011 / C3` | `W06-DEV-TUNE-011` | `C3` | `W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011` |
| 7 | `015 / C1` | `W06-DEV-TUNE-015` | `C1` | `W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015` |
| 8 | `015 / C2` | `W06-DEV-TUNE-015` | `C2` | `W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015` |
| 9 | `015 / C3` | `W06-DEV-TUNE-015` | `C3` | `W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015` |

## 7. Frozen Runtime Contract

- `concurrency = 1`
- `timeout_policy_id = T3_CANDIDATE_180S` (`timeout_ms = 180000`)
- `pacing_policy_id = P1_FIXED_2000MS_INTER_CALL_DELAY` (`inter_call_delay_ms = 2000`, `delay_before_first_call_ms = 0`, `delay_after_last_call_ms = 0`, `maximum_scheduled_delays = 8`)
- `retry_policy_id = R0_STRICT_ZERO_RETRY` (`retry = 0`, `automatic_retry = 0`, `transport_retry = 0`, `manual_retry = 0`, `llm_repair = 0`, `semantic_repair = 0`)
- `fallback = false`
- `generation_calls_per_assigned_cell = 1`
- `max_provider_generation_calls = 9`

## 8. Downstream & Primary Experiment Firewalls

- `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`
- `COMPARATIVE_EXECUTED = false`
- `canary_pass_does_not_auto_authorize_comparative = true`
- `MODEL_WINNER_SELECTED = false`
- `SELECTED_MODEL_ID = null`
- `STOCHASTICITY_EXECUTION_STARTED = false`
- `FINAL100_USED = false`
- `FINAL100_STATUS = NO-GO`
- `PRIMARY_EXPERIMENT_MUTATED = false`
- `PRIMARY_RESULTS_REPLACED = false`
- `PRIMARY_DENOMINATORS_CHANGED = false`
- **Authoritative Primary DEV-SELECT Strict Rates:** `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`
