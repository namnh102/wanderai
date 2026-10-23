# W06-DEV-SELECT-LIVE-LAUNCHER-01-OFFLINE — Frozen DEV-SELECT Live Launcher & Offline Preflight Report

## 1. Executive Summary & Task Scope

- **Task ID:** `W06-DEV-SELECT-LIVE-LAUNCHER-01-OFFLINE`
- **Branch:** `research/w06-dev-select-live-launcher-01`
- **Base `develop` SHA:** `681510af0e9232bae318562cf115e2ff4ce05968`
- **Launcher Script Path:** `scripts/run_w06_dev_select_live_v1.py`
- **Launcher LF-Normalized SHA256 (`LAUNCHER_LF_SHA256`):** `f992157e0b0fadcd6be2133cd041cd86f5c7f535a6acd9fe1b0106208f5ff520`
- **Launcher Outside Scientific Code Bundle:** `true` (`len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14`)
- **Scientific Code Bundle SHA256:** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`
- **Offline Execution Status:**
  - `LIVE_PROVIDER_CALLS = 0`
  - `PROVIDER_COST_USD = 0`
  - `LIVE_COMMAND_EXECUTED = false`
  - `LIVE_EXECUTION_CAPABILITY_MINTED = false`
  - `PRODUCTION_PROVIDER_TRANSPORT_CONSTRUCTED = false`
  - `DEV_SELECT_EXECUTION_STARTED = false`
  - `MODEL_WINNER_SELECTED = false`
  - `STOCHASTICITY_EXECUTION_STARTED = false`
  - `FINAL100_USED = false`

---

## 2. Hard-Locked W06 DEV-SELECT Scientific Scope & Frozen Authorities

| Authority / Parameter | Frozen Value / SHA256 |
|---|---|
| `PHASE` | `DEV_SELECT` |
| `SELECTED_PROMPT_ID` | `P1` (`FORBIDDEN_PROMPT_IDS = ["P0", "P2"]`) |
| `SELECTED_PROMPT_VERSION` | `TRAVEL_PLANNER_BENCHMARK_V2` |
| `SELECTED_PROMPT_SEMANTIC_SHA256` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` |
| `SELECTED_PROMPT_SYSTEM_SHA256` | `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e` |
| `SELECTED_PROMPT_USER_TEMPLATE_SHA256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `PROMPT_SELECTION_ARTIFACT_FILE_SHA256` | `e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8` |
| `PROMPT_FREEZE_SHA256` | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| `FROZEN_PROMPT_REGISTRY_SHA256` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| `CANDIDATE_IDS` | `["C1", "C2", "C3"]` |
| `REQUESTED_MODEL_BY_CANDIDATE` | `C1=gemini-3.8-flash`, `C2=gpt-6.1-sol`, `C3=claude-sonnet-5-5` |
| `CANDIDATE_REGISTRY_SHA256` | `4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058` |
| `PROVIDER_CONFIG_REGISTRY_SHA256` | `3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938` |
| `PORTABLE_SCHEMA_V2_SHA256` | `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490` |
| `SEMANTIC_SCHEMA_SHA256` | `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555` |
| `FIXTURE_COUNT` | `60` (`W06-DEV-SELECT-001` .. `W06-DEV-SELECT-060`) |
| `ASSIGNED_CELL_COUNT` | `180` (`60 × 1 × 3`) |
| `EXECUTION_PLAN_SHA256` | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `EXECUTION_PLAN_FILE_SHA256` | `c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a` |
| `PLAN_FREEZE_RECEIPT_FILE_SHA256` | `5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549` |
| `AUTHORIZATION_ID` | `W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1` |
| `AUTHORIZATION_FILE_SHA256` | `247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7` |
| `AUTHORIZATION_INTERNAL_SHA256` | `31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504` |
| `AUTHORIZATION_RECEIPT_FILE_SHA256` | `cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39` |
| `PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256` | `6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7` |
| `STAGE_A_FILE_SHA256` | `dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26` |
| `STAGE_A_INTERNAL_SHA256` | `1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014` |
| `STAGE_A_COMMIT_SHA` | `e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863` |
| `CODE_BASIS_COMMIT_SHA` | `c0adf74ceda9ffaf8b4ec42d299932e33f448e6a` |
| `ASSIGNED_CELLS_SHA256` | `de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d` |
| `CALL_BUDGET_MAX` | `180` (`ATTEMPTS_PER_CELL = 1`, `RETRY_CALLS = 0`) |

---

## 3. Offline Preflight Verification Summary (`--preflight`)

Command executed:
```bash
python scripts/run_w06_dev_select_live_v1.py --preflight
```

Observed preflight invariants:
- `PREFLIGHT_COMMAND_EXECUTED = true`
- `PREFLIGHT_REQUEST_HASH_COUNT = 180`
- `PREFLIGHT_REQUEST_SET_SHA256 = 3ef997b8833399095b9bf5953ae200d45dd85acb7b253c5b6975adf1b01667e2`
- `PREFLIGHT_ARTIFACT_PATH_COUNT = 180` (10 planned files per cell = 1,800 distinct artifact paths)
- `PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = 2a058ebd180cf3fe557549f5d2d3eff66d72f5320155b0e73bbb6b31f412d544`
- `LIVE_OUTPUT_ROOT = data/evaluation/w06/live_dev_select_primary_v1`
- `LIVE_OUTPUT_ROOT_EXISTS = false`
- `TRANSPORT_STATUS = TRANSPORT_NOT_INVOKED`
- `TRANSPORT_STARTING_COUNT = 0`
- `CALL_BUDGET_RESERVED = 0`
- `CALL_BUDGET_CONSUMED = 0`
- `GEMINI_API_KEY_PRESENCE = PRESENT`
- `OPENAI_API_KEY_PRESENCE = PRESENT`
- `ANTHROPIC_API_KEY_PRESENCE = PRESENT`
- `PYTHON_VERSION = 3.11.9`
- `GOOGLE_GENAI_VERSION = 2.25.0`
- `OPENAI_VERSION = 3.17.0`
- `ANTHROPIC_VERSION = 1.15.0`
- `HTTPX_VERSION = 0.28.1`
- `HTTPX2_VERSION = 2.13.0`
- `LIVE_READINESS = READY`
- `PRE_FLIGHT_READY = true`

---

## 4. Future Live Command Contract & Safety Firewalls

The future live execution command is strictly two-flag gated:
```bash
python scripts/run_w06_dev_select_live_v1.py --execute-live --confirm-frozen-180-cells
```

- **Not Executed in This Task:** `LIVE_COMMAND_EXECUTED = false`.
- **Two-Flag Requirement:** Omitting either `--execute-live` or `--confirm-frozen-180-cells` raises `LiveExecutionNotAuthorizedError` before any capability issuance or transport construction.
- **No Scope Override Flags:** Any CLI flag attempting to override `--phase`, `--prompt`, `--candidates`, `--retry`, `--resume`, `--execution-plan`, `--output-root`, `--dev-tune`, `--stochasticity`, or `--final100` fails closed immediately.
- **Final100 Firewall:** Both `data/evaluation/w06/w06_scenarios_freeze_v1.json` (`c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1`) and `data/evaluation/w06/w06_p11_assignment_manifest_v1.json` (`0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62`) are untouched (`FINAL100_USED = false`).
