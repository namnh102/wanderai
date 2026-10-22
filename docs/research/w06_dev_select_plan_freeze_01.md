# W06-DEV-SELECT-PLAN-FREEZE-01 — W06 DEV-SELECT Execution Plan Freeze & Independent Offline Verification

## 1. Scientific Purpose & Task Provenance

- **Task ID:** `W06-DEV-SELECT-PLAN-FREEZE-01`
- **Receipt Artifact ID:** `W06-DEV-SELECT-PLAN-FREEZE-01-RECEIPT-V1`
- **Source Branch:** `develop`
- **Source `develop` SHA (`CODE_BASIS_COMMIT_SHA` / `CODE_COMMIT_SHA`):** `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`
- **Branch:** `research/w06-dev-select-plan-freeze-01`
- **Phase:** `DEV_SELECT`
- **Upstream Gates:**
  - `W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01 = CLOSED`
  - `W06-DEV-TUNE-PROMPT-SELECTION-01 = CLOSED`
- **Execution Mode:** Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`, `PROVIDER_COST_USD_NEW = 0`)

This task freezes the complete W06 `DEV-SELECT` assignment before any `DEV-SELECT` provider execution:

$$\text{60 frozen DEV-SELECT fixtures} \times \text{3 frozen candidates } (\text{C1, C2, C3}) \times \text{1 formally selected and locked prompt } (\text{P1}) = 180 \text{ assigned cells.}$$

---

## 2. Closed Upstream Gates & Locked DEV-SELECT Prompt (`P1`)

Before constructing the `DEV-SELECT` execution plan, `scripts/select_w06_dev_tune_prompt.py --verify-only` (`verify_persisted_prompt_selection_artifacts`) verified the upstream prompt-selection artifacts:

| Upstream Authority / Property | Value / SHA256 Digest |
| --- | --- |
| `PROMPT_SELECTION_ARTIFACT` (`data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json`) | `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8` |
| `PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256` | `1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570` |
| `PROMPT_SELECTION_RECEIPT` (`data/evaluation/w06/w06_dev_tune_prompt_selection_01_receipt_v1.json`) | `0ad0921283c73917c5167ee4cf7355842efc6dedd8719bc169f329daba9ec114` |
| `selected_prompt_id` | `P1` |
| `selected_prompt_version` | `TRAVEL_PLANNER_BENCHMARK_V2` |
| `selected_prompt_semantic_sha256` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` |
| `selected_prompt_system_sha256` | `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e` |
| `selected_prompt_user_template_sha256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `final_survivors` | `["P1", "P2"]` |
| `superiority_claim` | `false` |
| `Allowed prompt IDs in DEV-SELECT` | `["P1"]` (`P2`, `P3`, provider-specific variants, and prompt edits are strictly forbidden) |

---

## 3. Frozen DEV Fixture Authorities & DEV-SELECT Marginal Counts

| Fixture / Firewall Authority | SHA256 Digest |
| --- | --- |
| `DEV_FIXTURE_BUNDLE` (`data/evaluation/w06/w06_dev_fixtures_freeze_v1.json`) | `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050` |
| `DEV_FIXTURE_MANIFEST` (`data/evaluation/w06/w06_dev_fixture_manifest_v1.json`) | `15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98` |
| `DEV_FINAL_OVERLAP_RECEIPT` (`data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json`) | `285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa` |
| `DEV_FIXTURE_FREEZE_RECEIPT` (`data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json`) | `437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026` |
| `FORBIDDEN_FINAL100_BUNDLE` (`data/evaluation/w06/w06_scenarios_freeze_v1.json`) | `c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1` |
| `FORBIDDEN_P11_MANIFEST` (`data/evaluation/w06/w06_p11_assignment_manifest_v1.json`) | `0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62` |

- **Fixture IDs:** `W06-DEV-SELECT-001` through `W06-DEV-SELECT-060` (`60` unique fixtures; zero `W06-DEV-TUNE-*` and zero `W06-S*` scenarios).
- **Verified Marginal Distributions (`60` `DEV-SELECT` fixtures):**
  - `destination`: `ha-noi = 20`, `da-nang = 20`, `ha-long = 20`
  - `days`: `2 = 20`, `3 = 20`, `4 = 20`
  - `interest_count`: `1 = 20`, `2 = 20`, `3 = 20`
  - `budget`: `B1 = 15`, `B2 = 15`, `B3 = 15`, `null = 15`
  - `travel_style`: `BACKPACKER = 15`, `BUDGET = 15`, `COMFORT = 15`, `LUXURY = 15`
  - `weekend`: `true = 30`, `false = 30`
  - `support_class` (observed frozen manifest values): `CLEAR = 48`, `STRESS = 12`, `EXCLUDED = 0`

---

## 4. Candidate Registry & Scientific Code Basis

- **Ordered Candidate IDs:** `["C1", "C2", "C3"]`
  - `C1` = `Google / gemini-3.8-flash`
  - `C2` = `OpenAI / gpt-6.1-sol`
  - `C3` = `Anthropic / claude-sonnet-5-5`
- **Model-Selection Firewall:** `DEV-TUNE` diagnostics never eliminate any candidate. All three candidates (`C1`, `C2`, `C3`) receive all `60` `DEV-SELECT` fixtures under locked prompt `P1`.
- **Cryptographic Digests:**
  - `CANDIDATE_REGISTRY_SHA256 = 4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058`
  - `PROVIDER_CONFIG_REGISTRY_SHA256 = 3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938`
  - `PORTABLE_SCHEMA_V2_SHA256 = 825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`
  - `SEMANTIC_SCHEMA_SHA256 = e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`
  - `SCIENTIFIC_CODE_BUNDLE_SHA256 = 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` (all 14 files untouched)
  - `CODE_BASIS_COMMIT_SHA = c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`
  - `CODE_COMMIT_SHA = c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`

---

## 5. Production Plan Builder & 180-Cell Assignment Invariants

The execution plan was generated using the production `app.evaluation.dev_selection_harness.build_dev_select_execution_plan` builder:

- `phase = DEV_SELECT`
- `prompt_ids = ["P1"]`
- `candidate_ids = ["C1", "C2", "C3"]`
- `fixture_count = 60`
- `expected_total_cells = 180`
- `assigned_cells = 180`
- `unique_run_ids = 180` (`W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001` through `W06-DEV-SELECT-P1-C3-W06-DEV-SELECT-060`)
- `unique_cell_keys = 180` (`(phase, prompt_id, candidate_id, fixture_id)`)
- **Per-Cell Execution Invariants:**
  - `attempt_number = 1`
  - `retry = 0`, `automatic_retry = 0`, `transport_retry = 0`, `manual_retry = 0`
  - `fallback = false`
  - `repair = 0`, `llm_repair = 0`, `deterministic_semantic_repair = false`
  - `tools = false`
  - `max_output_tokens = 16384`, `timeout_ms = 55000`

---

## 6. Committed Plan Freeze Artifacts & Digests

| Artifact / Digest | SHA256 Digest |
| --- | --- |
| `DEV_SELECT_PLAN_INTERNAL_SHA256` (`DevExecutionPlan.plan_sha256` over 180 canonical cell manifests) | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `DEV_SELECT_PLAN_FILE_SHA256` (`data/evaluation/w06/w06_dev_select_execution_plan_v1.json`) | `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a` |
| `PLAN_FREEZE_RECEIPT_FILE_SHA256` (`data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json`) | `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |

---

## 7. Boundary & Firewall Confirmation

- `LIVE_PROVIDER_CALLS_NEW = 0`
- `PROVIDER_COST_USD_NEW = 0`
- `LIVE_EXECUTION_CAPABILITY_ISSUED = false`
- `PRODUCTION_TRANSPORT_STARTED = false`
- `DEV_SELECT_EXECUTION_STARTED = false`
- `STOCHASTICITY_EXECUTION_STARTED = false`
- `FINAL100_USED = false`
- `MODEL_WINNER_SELECTED = false`
- `SCIENTIFIC_BUNDLE_FILES_MODIFIED = false`
