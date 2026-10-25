# W06 DEV-SELECT Amendment 01 — Provider Readiness & Current Pricing PREP

## 1. Governance & Scope Boundary

- **Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-PREP`
- **Corrective Task ID:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-CORRECTIVE-01`
- **Authoritative Base:** `develop@c2e5126b7e1d3aa25ef6e46352e030c346fc733a` (PR #69 merged, post-merge CI run `40099797847` green)
- **Public Pricing Snapshot Artifact:** `data/evaluation/w06/w06_dev_select_amendment_01_public_pricing_snapshot_v1.json`
  - `file_sha256`: `2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6`
  - `internal_sha256`: `bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe`
- **Provider Readiness & Pricing PREP Artifact:** `data/evaluation/w06/w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json`
  - `file_sha256`: `ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006`
  - `internal_sha256`: `07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e`
- **Effective Amendment Status:** `METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED`
- **Next Gate:** `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-CORRECTIVE-01-CHATGPT-AUDIT`

**Strict Execution & Privacy Firewalls:**
- `LIVE_PROVIDER_CALLS_NEW = 0` (`CANARY_EXECUTED = false`, `COMPARATIVE_EXECUTED = false`)
- `AMENDED_CANARY_LIVE_AUTHORIZED = false`, `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_EXECUTED = false`
- `C1_PROVIDER_READINESS = NOT_YET_ATTESTED`, `C2_PROVIDER_READINESS = NOT_YET_ATTESTED`, `C3_PROVIDER_READINESS = NOT_YET_ATTESTED`
- `OWNER_ACTION_OCCURRED = false`, `ENV_FILE_READ = false`, `API_KEYS_INSPECTED = false`
- `MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`, `STOCHASTICITY_EXECUTION_STARTED = false`, `FINAL100_USED = false` (`NO-GO`)
- `PRIMARY_EXPERIMENT_MUTATED = false`, `PRIMARY_RESULTS_REPLACED = false`, `PRIMARY_DENOMINATORS_CHANGED = false`

## 2. Report Correction Firewall & Primary Metric Authority

Independently read from `data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json` (`1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0`) and cross-checked against `data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json` (`c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4` / internal `7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a`):

| Metric | C1 (`gemini-3.8-flash`) | C2 (`gpt-6.1-sol`) | C3 (`claude-sonnet-5-5`) | Total |
| --- | --- | --- | --- | --- |
| `VALID_RUN_AND_SCHEMA` | `1/60` | `8/60` | `0/60` | `9/180` |
| `EXACT_GROUNDING_PASS` | `1/60` | `8/60` | `0/60` | `9/180` |
| `FINAL_CORE_PASS` | `1/60` | `8/60` | `0/60` | `9/180` |

- **Rejected Erroneous Report Tuple:** `C1 = 0/60, C2 = 43/60, C3 = 0/60` is explicitly rejected by regression guard (`validate_primary_metric_tuple`) as non-authoritative.

## 3. Exact Billing Surface & Official Public Pricing Summary

| Candidate | Provider / Model | Determined Billing Surface | Input / 1M | Output / 1M | Official Source URL | Retrieved (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| `C1` | `GOOGLE` / `gemini-3.8-flash` | Gemini Developer API (AI Studio / `generativelanguage.googleapis.com`) Standard Paid Tier (promotional through `2026-12-31`) | `$0.75` | `$3.75` (incl. thinking) | `https://ai.google.dev/gemini-api/docs/pricing` (`https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash`) | `2026-10-25T03:05:48Z` |
| `C2` | `OPENAI` / `gpt-6.1-sol` | OpenAI Standard API (`api.openai.com` `/v1/chat/completions`, `service_tier='default'`, `<=272K` input) | `$2.00` (cached `$0.10`, assumed `0%`) | `$10.00` (incl. reasoning) | `https://developers.openai.com/api/docs/pricing` (`https://developers.openai.com/api/docs/models/gpt-6.1-sol`) | `2026-10-25T03:05:50Z` |
| `C3` | `ANTHROPIC` / `claude-sonnet-5-5` | Anthropic Claude API First-Party Direct (`api.anthropic.com` `/v1/messages`, `service_tier='standard'`, global, caching disabled) | `$2.00` | `$10.00` (incl. thinking) | `https://docs.anthropic.com/en/docs/about-claude/pricing` (`https://www.anthropic.com/claude/sonnet`) | `2026-10-25T03:05:51Z` |

- **OpenAI Long-Context (`>272,000` input tokens) Surcharge Status:** `NOT_APPLICABLE_PROVEN` (maximum serialized UTF-8 wire payload across all 63 frozen C2 requests is `89,435` bytes on `W06-DEV-SELECT-032`, strictly `<90,000` tokens under any byte-level BPE tokenizer, and empirical `prompt_tokens` across all 12 completed P1 C2 cells is `16,086..29,633` tokens).

## 4. Cost Analysis Across S2 Call Scopes

| Scope | Calls | Category | C1 (`gemini-3.8-flash`) | C2 (`gpt-6.1-sol`) | C3 (`claude-sonnet-5-5`) | Total (USD) |
| --- | --- | --- | --- | --- | --- | --- |
| **A. Readiness Canary** | `9` (`3`/cand) | `EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE` | `$0.129986` | `$0.213327` | `$0.370762` | **`$0.714076`** |
| **A. Readiness Canary** | `9` (`3`/cand) | `CONSERVATIVE_PLANNING_ENVELOPE` | `$0.202500` | `$0.432000` | `$0.552000` | **`$1.186500`** |
| **A. Readiness Canary** | `9` (`3`/cand) | `CONFIGURED_MAX_OUTPUT_16384_REFERENCE` (not hard max) | `$0.274320` | `$0.683520` | `$0.743520` | **`$1.701360`** |
| **B. Amended Comparative** | `180` (`60`/cand) | `EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE` | `$2.599729` | `$4.266544` | `$7.415247` | **`$14.281520`** |
| **B. Amended Comparative** | `180` (`60`/cand) | `CONSERVATIVE_PLANNING_ENVELOPE` | `$4.050000` | `$8.640000` | `$11.040000` | **`$23.730000`** |
| **B. Amended Comparative** | `180` (`60`/cand) | `CONFIGURED_MAX_OUTPUT_16384_REFERENCE` (not hard max) | `$5.486400` | `$13.670400` | `$14.870400` | **`$34.027200`** |
| **C. Total Amendment Track** | `189` (`63`/cand) | `EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE` | `$2.729715` | `$4.479871` | `$7.786009` | **`$14.995596`** |
| **C. Total Amendment Track** | `189` (`63`/cand) | `CONSERVATIVE_PLANNING_ENVELOPE` | `$4.252500` | `$9.072000` | `$11.592000` | **`$24.916500`** |
| **C. Total Amendment Track** | `189` (`63`/cand) | `CONFIGURED_MAX_OUTPUT_16384_REFERENCE` (not hard max) | `$5.760720` | `$14.353920` | `$15.613920` | **`$35.728560`** |

- **Historical Observed Primary Reference:** `9` authoritative cost cells = `0.6468966 USD` (`C1 = 0.0266516 USD`, `C2 = 0.620245 USD`, `C3 = 0 USD`). Not scaled blindly to 189 calls.
- **Hard Maximum Status:** `NOT_DEFENSIBLY_COMPUTABLE` (`hard_maximum_usd = null`).
