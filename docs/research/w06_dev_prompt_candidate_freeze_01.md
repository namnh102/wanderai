# W06-DEV-PROMPT-CANDIDATE-FREEZE-01 — Scientific Prompt Candidate Freeze & DEV-TUNE Execution Plan

## 1. Executive Summary & Pre-Results Declaration

- **Task ID:** `W06-DEV-PROMPT-CANDIDATE-FREEZE-01`
- **Base `develop` Commit:** `60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26`
- **Code Basis Commit (`code_basis_commit_sha`):** `60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26`
- **Prompt Candidate Decision:** `P1_PLUS_P2_PRE_RESULTS`
- **Prompt Candidate Count:** `2` (`P1`, `P2`)
- **No Prompt Result Shopping (`NO_PROMPT_RESULT_SHOPPING`):** `true`
- **Freeze Status:** `FROZEN_FOR_LIVE_DEV_TUNE`
- **Live Provider Calls (`LIVE_PROVIDER_CALLS`):** `0`
- **Provider Cost (`PROVIDER_COST_USD`):** `0`

### Pre-Results Declaration (Section 14)

1. **Prompt choice was frozen before any DEV-TUNE result existed.**
2. **No provider output was inspected.**
3. **No live provider call occurred.**
4. **No prompt candidate was added, removed, rewritten, or selected based on model performance.**
5. **`P2` is a provider-neutral constraint-reinforcement variant.**
6. **The experiment tests whether explicit pre-output constraint checking improves primary scientific rates without changing catalog, schema, model configuration, or evaluator.**

---

## 2. Important Claim Boundary (Section 16)

- **`P2` is NOT claimed superior.**
- **`P1` is NOT claimed inferior.**
- This task freezes only:
  - candidate definitions (`P1`, `P2`),
  - controlled experimental comparison parameters,
  - the 120-cell `DEV_TUNE` execution plan, and
  - the pre-registered future prompt-selection rule.
- Scientific superiority can only be assessed after `DEV-TUNE` is executed under formal live authorization.

---

## 3. Prompt Candidate Specifications (`P1` and `P2`)

### 3.1 `P1` — Exact Existing Baseline

Reconstructed exclusively from current frozen authorities (`app/evaluation/model_preflight/base.py` and `app/prompts/planner_benchmark_prompt.py`) without editing a single character:

| Field | Value |
|---|---|
| `prompt_id` | `P1` |
| `prompt_version` | `TRAVEL_PLANNER_BENCHMARK_V2` |
| `system_prompt` | Exact `PREFLIGHT_SHARED_SYSTEM_PROMPT` |
| `user_prompt_template` | Exact `TRAVEL_PLANNER_BENCHMARK_V2` |
| `P1_SYSTEM_PROMPT_SHA256` | `4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e` |
| `P1_USER_PROMPT_TEMPLATE_SHA256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `P1_SEMANTIC_PROMPT_SHA256` | `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` |
| `created_before_live_dev_execution` | `true` |
| `provider_specific_semantic_prompt` | `false` |

#### Historical `P1` Semantic Hash Verification Note (Section 3)

Section 3 instructed:
> *Expected historical semantic prompt hash, if still authoritative: `49399ca4ab45e98dd7da05c94609d5bf5c03667ca79a96f52c7f330f357ac5e9`. Verify rather than blindly trust this value.*

Independent provenance verification confirms:
- `096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11` is the **exact authoritative repository hash** recorded in `data/evaluation/w06/w06_dev_selection_harness_v1.json` (`prompt_registry_infrastructure.default_infrastructure_p1_sha256`, line 216) and verified in `data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json` (`QA-31`, line 1173) since `W06-DEV-SELECTION-HARNESS-01-OFFLINE` (`128d6c7`).
- Both `apps/ai-service/app/prompts/planner_benchmark_prompt.py` (`22aa9cd172548fe51a8699704e5832ad44e1d8e946a1ad79437aed99d46c98cb`) and `apps/ai-service/app/evaluation/model_preflight/base.py` (`55bd026f224eaf15f5fb68e98d9cd9467bf85f0f90305acac397caef0970454d`) have **zero drift**.
- The string `49399ca4ab45e98dd7da05c94609d5bf5c03667ca79a96f52c7f330f357ac5e9` was a non-authoritative prose summary typo from PR `#47` that was explicitly noted as non-authoritative in `W06-DEV-SELECTION-HARNESS-01-MERGE-CLOSE` (*"THE REPOSITORY ARTIFACTS ARE AUTHORITATIVE. Do not modify code to match the incorrect prose report."*).

### 3.2 `P2` — Exact Pre-Results Constraint-Reinforcement Candidate

| Field | Value |
|---|---|
| `prompt_id` | `P2` |
| `prompt_version` | `W06_DEV_TUNE_CANDIDATE_P2_V1` |
| `system_prompt` | `PREFLIGHT_SHARED_SYSTEM_PROMPT + "\n" + P2_EXACT_SYSTEM_PROMPT_SUFFIX` |
| `user_prompt_template` | Exact `TRAVEL_PLANNER_BENCHMARK_V2` (identical to `P1`) |
| `P2_SYSTEM_PROMPT_SHA256` | `ab8ec41b7099c1c207217a55e1afd7e075d5de6be9b2fc14863329b5535e6c68` |
| `P2_USER_PROMPT_TEMPLATE_SHA256` | `19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de` |
| `P2_SEMANTIC_PROMPT_SHA256` | `fa59900481275200f0d50bdfdc4a2b3d5177b2be0e34d00402a459366adf2c34` |
| `created_before_live_dev_execution` | `true` |
| `provider_specific_semantic_prompt` | `false` |

Exact `P2` system-prompt suffix (appended after a single `\n` following `PREFLIGHT_SHARED_SYSTEM_PROMPT`):

```text
Before returning the JSON, perform a silent constraint check and correct the draft if needed:
(1) every POI_VISIT must copy an exact place_id and matching place_name from the provided REC-A-CORE-V2 catalog;
(2) each day must contain at least two POI_VISIT items;
(3) do not repeat a place_id unless allow_revisit_place_ids=true;
(4) use valid non-overlapping HH:MM intervals with start_time < end_time;
(5) when opening_hours is known and parseable, schedule the POI visit within it, while missing or unknown opening_hours must not be invented;
and (6) respect the scenario budget when a budget ceiling is provided.
Do not reveal this checking process; output only the final JSON object.
```

---

## 4. Controlled Experiment Invariants & Prompt Registry

- **Only Semantic Experimental Difference:** The `P2` system-prompt suffix above.
- **Identical Across `P1` and `P2`:**
  - `user_prompt_template` (`19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de`)
  - Portable Generation Schema V2 (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`)
  - Semantic Schema (`e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`)
  - `REC-A-CORE-V2` catalog (`f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`)
  - 20 `DEV-TUNE` fixtures from `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json` (`bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`)
  - Candidate models (`C1 = gemini-3.8-flash`, `C2 = gpt-6.1-sol`, `C3 = claude-sonnet-5-5`)
  - Provider configurations (`3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938`)
  - Sampling configs, tool policy (`tools = false`), retry policy (`retry = 0`), repair policy (`repair = 0`), evaluator, and measurement contract.
- **Prompt Registry (`[P1, P2]`):**
  - `prompt_candidate_ids`: `["P1", "P2"]`
  - `max_allowed_prompts`: `2` (`P3` is fail-closed forbidden)
  - `PROMPT_REGISTRY_SHA256`: `87a60d601de7d427febec60d1b3d6ccd18240c18b1fa8778d3b4954eb7318a99`

---

## 5. Deterministic 120-Cell `DEV-TUNE` Execution Plan & Prompt Freeze Artifact

| Parameter | Value |
|---|---|
| Frozen DEV Bundle Path | `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json` |
| Frozen DEV Bundle SHA256 | `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050` |
| DEV Total / `DEV-TUNE` / `DEV-SELECT` | `80` / `20` / `60` |
| `DEV-TUNE` Fixtures Used | `20` (`W06-DEV-TUNE-001` .. `W06-DEV-TUNE-020`) |
| Prompt Candidates | `2` (`P1`, `P2`) |
| Model Candidates | `3` (`C1`, `C2`, `C3`) |
| Executions per Cell | `1` (`attempt_number = 1`) |
| Total `DEV-TUNE` Plan Cells | `120` (`60` per prompt, `40` per candidate, `6` per fixture) |
| `DEV_TUNE_PLAN_SHA256` (`plan.plan_sha256`) | `30695d74b19e950d065f612ce069cfc325ad7f79338b3be314624fefc514aad0` |
| Persisted `w06_dev_tune_execution_plan_v1.json` SHA256 | `15c93d3abcc27e4eff8b26984a9575d59e3541725cad815521d83c164bd9d29a` |
| Freeze Artifact ID / Version | `W06-DEV-PROMPT-CANDIDATE-FREEZE-01-V1` / `1.0.0` |
| `PROMPT_FREEZE_SHA256` (`w06_dev_prompt_candidate_freeze_v1.json`) | `c1662592615c4821d6840065938c66578c49755f6657fc592cf5c795afd95bb3` |

---

## 6. Code Basis & Scientific Code Bundle Provenance

- **`CODE_BASIS_COMMIT_SHA`:** `60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26`
- **`SCIENTIFIC_CODE_BUNDLE_SHA256`:** `0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3` (14 files, 100% unchanged)

| Relative Path | SHA256 |
|---|---|
| `apps/ai-service/app/evaluation/dev_live_runner.py` | `9f3441c2ca290e9a33b4daa78eaaa58063978364d8375145fc7483b04ed8b817` |
| `apps/ai-service/app/evaluation/dev_selection_harness.py` | `85b17c2daa1ea59e26c3118d5cafb38cb3c73a5d57288e2fb4e5fc0e0a732c97` |
| `apps/ai-service/app/evaluation/model_preflight/__init__.py` | `178aede4930a6b848714fa6d84e14e415df35d1bf7641312ff6f311e3de477dd` |
| `apps/ai-service/app/evaluation/model_preflight/anthropic_adapter.py` | `ef2570126f6db736a4ef056ac27fcfc77db97fa6ed6526c901e299c71b1b1d42` |
| `apps/ai-service/app/evaluation/model_preflight/base.py` | `55bd026f224eaf15f5fb68e98d9cd9467bf85f0f90305acac397caef0970454d` |
| `apps/ai-service/app/evaluation/model_preflight/google_adapter.py` | `184887b19826094326e5fea47efd7aec71308b36af404225f5ef8d0d40882f1c` |
| `apps/ai-service/app/evaluation/model_preflight/openai_adapter.py` | `62b72237402808ab88d71627ce05d948d4b7d251ba87af51208876c784ee9346` |
| `apps/ai-service/app/evaluation/model_preflight/schema_adapter.py` | `19513c8735ba4acb2b88587915d6458de2c28d622499c05314d4f9030eb3c589` |
| `apps/ai-service/app/evaluation/model_preflight/types.py` | `1fdb31f200a71df4193f1fe4844b49dc1e9750c51c7388e6642dac44ae349371` |
| `apps/ai-service/app/evaluation/planner_benchmark_evaluator.py` | `1b299f75a3a51d01b63b1b004df3d8b9d92224591ccde5d537b83735ca268f66` |
| `apps/ai-service/app/prompts/planner_benchmark_prompt.py` | `22aa9cd172548fe51a8699704e5832ad44e1d8e946a1ad79437aed99d46c98cb` |
| `apps/ai-service/app/schemas/planner_benchmark.py` | `3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712` |
| `apps/ai-service/app/services/planner_benchmark_runner.py` | `2831f5aadd80959a86f388508c73679215830ca8854f2a4fbd474328fa7288b7` |
| `apps/ai-service/recommendation/reca/contract.py` | `1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c` |

---

## 7. Future Prompt-Selection Rule (Section 15)

No winning prompt is selected in this task (`WINNING_PROMPT_SELECTED = false`). The locked future `DEV-TUNE` selection rule is:

1. **Equal Aggregation Scope:** Same `20` `DEV-TUNE` fixtures $\times$ same `3` candidates (`C1`, `C2`, `C3`) $\times$ `1` execution per cell = `60` cells per prompt (`120` cells total, `0` retries).
2. **Ordered Criteria:**
   - Criterion 1: `VALID_RUN_AND_SCHEMA_RATE`
   - Criterion 2: `EXACT_GROUNDING_PASS_RATE`
   - Criterion 3: `FINAL_CORE_PASS_RATE`
3. **Set-Based Relative-to-Best Survival:** At each criterion, retain all prompts within `10` percentage points (`0.10`) of the best rate among current survivors (set-based relative-to-best; no pairwise chaining).
4. **Administrative Tie-Break:** If more than 1 prompt survives all three criteria, administrative tie = `P1` wins (without claiming `P1` superiority).
5. **Exclusions:** No cost criterion, no latency criterion, no weighted composite, and no `Final100` data (`FINAL100_USED = false`).

---

## 8. Offline Verification Summary (`PF-01` .. `PF-35`)

All 35 offline checks (`PF-01` through `PF-35`) passed (`35/35 PASS`) under an independent outbound-network kill switch (`socket`, `urllib`, `httpx`, `httpx2`) with provider API keys scrubbed (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` absent). Full check evidence is recorded in `data/evaluation/w06/w06_dev_prompt_candidate_freeze_01_receipt_v1.json`.
