# W06-DEV-TUNE-LIVE-LAUNCHER-01-OFFLINE — Operational Live Launcher Report

## 1. Purpose & Root Operational Defect

Stage-A (`W06-DEV-TUNE-STAGE-A-FREEZE-01`) is closed and frozen on `develop` at commit `dadff7f64d64444a0c8a72571135777498ecc6bf`.

The production scientific runner (`apps/ai-service/app/evaluation/dev_live_runner.py`) is valid and unchanged (`SCIENTIFIC_CODE_BUNDLE_SHA256 = 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`). However, its generic infrastructure CLI entrypoint `run_cli()` constructs `build_default_infrastructure_prompt_registry()`, which is the default one-prompt `["P1"]` infrastructure registry.

Because the frozen W06 `DEV_TUNE` experiment uses the two-prompt `["P1", "P2"]` registry (`FROZEN_PROMPT_REGISTRY_SHA256 = 846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6`), invoking `run_cli()` directly against `data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json` fails closed offline with:

```text
PromptFreezeFirewallError: PROMPT_CANDIDATE_ID_MISMATCH: freeze_artifact=['P1', 'P2'], registry=['P1']
```

To preserve the frozen scientific code bundle (`0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`) without modifying `dev_live_runner.py` or `dev_selection_harness.py`, `scripts/run_w06_dev_tune_live_v1.py` provides an operational launcher outside `SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS` that injects `build_frozen_p1_p2_registry()` from `scripts/freeze_w06_dev_prompt_candidates.py` into the existing production runner APIs.

---

## 2. Hard-Locked Authorities & Scope

| Parameter / Authority | Frozen Value |
|---|---|
| `BASE_DEVELOP_SHA` | `dadff7f64d64444a0c8a72571135777498ecc6bf` |
| `PHASE` | `DEV_TUNE` |
| `CANDIDATE_IDS` | `["C1", "C2", "C3"]` |
| `PROMPT_IDS` | `["P1", "P2"]` |
| `CELL_COUNT` / `MAX_CALLS` | `120` |
| `RETRY_POLICY` | `0` |
| `FROZEN_PROMPT_REGISTRY_SHA256` | `846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6` |
| `EXECUTION_PLAN_PATH` | `data/evaluation/w06/w06_dev_tune_execution_plan_v1.json` |
| `EXECUTION_PLAN_SHA256` | `582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae` |
| `EXECUTION_PLAN_FILE_SHA256` | `652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74` |
| `PROMPT_FREEZE_PATH` | `data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json` |
| `PROMPT_FREEZE_SHA256` | `2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956` |
| `AUTHORIZATION_PATH` | `data/evaluation/w06/w06_dev_tune_live_authorization_v1.json` |
| `AUTHORIZATION_FILE_SHA256` | `b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4` |
| `AUTHORIZATION_INTERNAL_SHA256` | `fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83` |
| `STAGE_A_RECEIPT_PATH` | `data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json` |
| `STAGE_A_FILE_SHA256` | `a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31` |
| `STAGE_A_INTERNAL_SHA256` | `a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f` |
| `SCIENTIFIC_CODE_BUNDLE_SHA256` | `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` |
| `LIVE_OUTPUT_ROOT` | `data/evaluation/w06/live_dev_tune_primary_v1` |

---

## 3. Operational Modes & Safety Guards

1. **Preflight Mode (`--preflight`)**:
   - Loads `build_frozen_p1_p2_registry()` (`846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6`).
   - Verifies all frozen authority hashes and fails closed if `data/evaluation/w06/live_dev_tune_primary_v1` already exists.
   - Delegates to `run_dev_live_runner_dry_run(...)` with explicit `prompt_registry=frozen_p1_p2_registry`.
   - Verifies `mode = "dry_run"`, `phase = "DEV_TUNE"`, `planned_call_count = 120`, `expected_total_cells = 120`, `authorization_verified = true`, `stage_a_verified = true`, `transport_status = "TRANSPORT_NOT_INVOKED"`, `live_provider_calls = 0`, 120 serialized wire-request SHA256 digests, and 120 planned cell artifact paths.
   - Does not create the output directory, does not load API key values, does not mint `LiveExecutionCapability`, and does not construct `ProductionDevProviderTransport`.

2. **Live Mode (`--execute-live --confirm-frozen-120-cells`)**:
   - Requires BOTH `--execute-live` and `--confirm-frozen-120-cells` (fails closed otherwise).
   - Fails closed if `data/evaluation/w06/live_dev_tune_primary_v1` already exists (no resume, no overwrite, no cleanup).
   - Delegates strictly to:
     1. `build_frozen_p1_p2_registry()`
     2. `issue_live_execution_capability(execute_live=True, ...)`
     3. `create_live_provider_transport_factory(execute_live=True, ...)`
     4. `execute_live_dev_batch(..., execution_mode=LIVE_EXECUTION, ...)`
   - **Not executed in this offline task (`LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0.0`).**
