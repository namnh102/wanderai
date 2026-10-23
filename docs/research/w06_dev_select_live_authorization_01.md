# W06 DEV-SELECT Live Authorization Report (`W06-DEV-SELECT-LIVE-AUTHORIZATION-01`)

## 1. Executive Summary & Scientific Boundary

Task `W06-DEV-SELECT-LIVE-AUTHORIZATION-01` formally converts the explicit Project Owner chat authorization into the production `DevLiveAuthorizationArtifact` (`data/evaluation/w06/w06_dev_select_live_authorization_v1.json`) and its cryptographic verification receipt (`data/evaluation/w06/w06_dev_select_live_authorization_01_receipt_v1.json`) required by the frozen W06 DEV-SELECT runner.

- **Task ID:** `W06-DEV-SELECT-LIVE-AUTHORIZATION-01`
- **Source Branch & Commit:** `develop` @ `1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f`
- **Frozen Plan Code Basis Commit (`code_basis_commit_sha`):** `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`
- **Authorization Artifact ID:** `W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1`
- **Authorization Receipt ID:** `W06-DEV-SELECT-LIVE-AUTHORIZATION-01-RECEIPT-V1`
- **Authorized By Role:** `PROJECT_OWNER`
- **Authorization Status:** `AUTHORIZED`
- **Authorization Source:** `PROJECT_OWNER_EXPLICIT_CHAT_AUTHORIZATION`
- **Authorized At UTC:** `2026-10-23T05:47:00Z` (formal artifact-issuance UTC timestamp immediately following explicit Project Owner authorization; not a fabricated historical chat timestamp)

### Strict Offline Firewall Invariants
- `LIVE_PROVIDER_CALLS_NEW = 0`
- `PROVIDER_COST_USD_NEW = 0`
- `STAGE_A_CREATED = false`
- `LIVE_EXECUTION_CAPABILITY_ISSUED = false`
- `PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED = false`
- `TRANSPORT_JOURNAL_CREATED = false`
- `DEV_SELECT_LIVE_RESULT_DIRECTORY_CREATED = false`
- `DEV_SELECT_EXECUTION_STARTED = false`
- `MODEL_WINNER_SELECTED = false`
- `STOCHASTICITY_EXECUTION_STARTED = false`
- `FINAL100_USED = false`

---

## 2. Exact Project Owner Authorization Evidence

### Exact Authorization Sentence (633 Characters)

```text
I authorize W06 DEV-SELECT live execution for exactly the frozen 180-cell plan de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d (plan file c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a), bound by plan-freeze receipt 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549, using locked prompt P1 from prompt-selection artifact e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8 (semantic SHA 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11), candidates C1/C2/C3, maximum 180 generation calls, zero retry, no DEV-TUNE rerun, no stochasticity, and no Final100.
```

- **Character Count:** `633`
- **Exact UTF-8 SHA256:** `6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7`
- **Authorization-Prep Artifact (`data/evaluation/w06/w06_dev_select_authorization_prep_v1.json`) File SHA256:** `60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8` (preserved byte-identical; its `project_owner_authorization_status = NOT_GRANTED` records the historical status at prep creation time).

---

## 3. Cryptographic Authority Bindings

| Authority / Artifact | Value / SHA256 |
|---|---|
| `allowed_phase` | `DEV_SELECT` |
| `allowed_execution_plan_sha256` (Plan Internal SHA256) | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `execution_plan_file_sha256` (`w06_dev_select_execution_plan_v1.json`) | `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a` |
| `plan_freeze_receipt_file_sha256` (`w06_dev_select_plan_freeze_01_receipt_v1.json`) | `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |
| `allowed_prompt_freeze_sha256` (`w06_dev_prompt_candidate_freeze_v1.json`) | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| `selected_prompt_id` / `selected_prompt_version` | `P1` (`TRAVEL_PLANNER_BENCHMARK_V2`) |
| `selected_prompt_semantic_sha256` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` |
| `selected_prompt_system_sha256` | `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e` |
| `selected_prompt_user_template_sha256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `prompt_selection_artifact_file_sha256` (`w06_dev_tune_prompt_selection_v1.json`) | `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8` |
| `prompt_selection_receipt_file_sha256` (`w06_dev_tune_prompt_selection_01_receipt_v1.json`) | `0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114` |
| `allowed_candidate_ids` | `["C1", "C2", "C3"]` (`gemini-3.8-flash`, `gpt-6.1-sol`, `claude-sonnet-5-5`) |
| `candidate_registry_sha256` | `4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058` |
| `provider_config_registry_sha256` | `3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938` |
| `maximum_live_generation_calls` | `180` (`60` fixtures × `3` candidates × `1` locked prompt `P1`, `attempts_per_cell = 1`, `retry_calls = 0`) |
| `scientific_code_bundle_sha256` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| `code_basis_commit_sha` | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |
| `AUTHORIZATION_ARTIFACT_INTERNAL_SHA256` | `31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504` |
| `AUTHORIZATION_ARTIFACT_FILE_SHA256` (`w06_dev_select_live_authorization_v1.json`) | `247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7` |
| `AUTHORIZATION_RECEIPT_FILE_SHA256` (`w06_dev_select_live_authorization_01_receipt_v1.json`) | `cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39` |

---

## 4. Production Contract & Prompt Authority Semantics

1. **Production Contract Construction & Verification:**
   - Constructed via `app.evaluation.dev_live_runner.build_dev_live_authorization_artifact` and immediately verified via `app.evaluation.dev_live_runner.verify_dev_live_authorization_artifact(..., expected_phase="DEV_SELECT")`.
2. **Production Prompt-Freeze Contract & P1 Narrowing:**
   - `allowed_prompt_freeze_sha256` binds `data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json` (`2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956`), which historically holds the preregistered `P1/P2` candidate authority.
   - Because `w06_dev_select_execution_plan_v1.json` has `prompt_ids = ["P1"]` across all 180 cells, `w06_dev_tune_prompt_selection_v1.json` locks `selected_prompt_id = "P1"`, and the Project Owner authorization explicitly specifies locked prompt `P1`, the effective authorization scope is strictly narrowed to `P1` only (`P2` is never authorized for DEV-SELECT).

---

## 5. Verification Summary (`DSAU-01..DSAU-40` & `ADV-01..ADV-20`)

- **`DSAU-01` .. `DSAU-40`:** `40/40 PASS`
- **Adversarial Contract Checks (`ADV-01` .. `ADV-20`):** `20/20 PASS`
- **Secret Hygiene:** Verified via production `assert_no_secrets_in_payload` across the authorization artifact, receipt, and verification payloads. Zero API keys, key hashes, key lengths, prefixes, or suffixes are persisted.
- **Historical Lifecycle Compatibility:** Downstream recognizer `is_verified_downstream_w06_dev_select_authorization_file` cryptographically binds all 14 required invariants (file SHA256, internal SHA256, authorization text SHA256, DEV-SELECT plan internal/file/receipt SHA256s, prompt-selection artifact SHA256, `P1` semantic SHA256, candidate IDs `C1/C2/C3`, maximum calls `180`, scientific bundle SHA256, code basis `c0adf74...`, `stage_a_created=false`, `live_provider_calls_new=0`). Unknown or tampered authorization files fail closed.
