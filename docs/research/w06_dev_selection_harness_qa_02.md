# W06 DEV Selection Harness — Independent Offline Re-Audit Report (QA-02)

- **Task ID:** `W06-DEV-SELECTION-HARNESS-QA-02-OFFLINE-INDEPENDENT`
- **Artifact ID:** `W06-DEV-SELECTION-HARNESS-QA-02-RECEIPT-V1`
- **Branch:** `research/w06-dev-selection-harness-qa-02`
- **Base `develop` Commit:** `cbbfbd3e5a54d25016609d73ea71939442bf7b10`
- **Scientific Code Bundle SHA256:** `fe82a932a4cb768efd0e80eeb120d773f4937dae67e1b9f2fb77ec00f516f1be`
- **Execution Mode:** `100% OFFLINE` (`LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0`)
- **Overall QA Verdict:** **`PASS`** (`67 / 67 PASS`, `0 FAIL`)
- **Harness Scientific Readiness:** **`PASS`**
- **Next Gate:** **`W06-DEV-LIVE-RUNNER-01-OFFLINE`**

---

## 1. Executive Summary & Independence Boundary

This report documents the independent offline scientific re-audit (`QA-02`) of the W06 DEV Selection Harness (`apps/ai-service/app/evaluation/dev_selection_harness.py`) following the merge of PR #49 (`W06-DEV-SELECTION-HARNESS-FIX-01` and `AUDIT-CORRECTION-01/02/03`) into `develop` (`cbbfbd3e5a54d25016609d73ea71939442bf7b10`).

In accordance with the QA-02 Independence Rule:
1. **Production Harness Unmodified:** `apps/ai-service/app/evaluation/dev_selection_harness.py` was not modified (`git diff cbbfbd3e5a54d25016609d73ea71939442bf7b10 -- apps/ai-service/app/evaluation/dev_selection_harness.py` is empty).
2. **Independent Oracle Derivation:** All expected counts, marginals, hashes, catalog sets, cost equations, 10pp survivor sets, and provenance lifecycle invariants in `scripts/audit_w06_dev_selection_harness_qa_02.py` were derived directly from the frozen W06 JSON/Python authorities and manual mathematical calculations rather than trusting internal harness constants.
3. **Historical QA-01 Evidence Preserved:** All four historical QA-01 files remain byte-identical with their original LF-normalized SHA256 digests and original `40 total / 30 PASS / 10 FAIL` failure record.
4. **Zero Live Execution:** `LIVE_PROVIDER_CALLS = 0`, `PROVIDER_COST_USD = 0`, `DEV_TUNE_EXECUTION_STARTED = false`, `DEV_SELECT_EXECUTION_STARTED = false`, `WINNER_SELECTED = false`, and `FINAL100_USED = false`.

---

## 2. Historical QA-01 Immutability Verification (`Q2-02`)

| Historical QA-01 File | Expected / Observed LF SHA256 | Status |
|---|---|---|
| `data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json` | `51b7606ebca7b5a67b6e6514d2f0c4fa4c7933919be2a5c2ec8179b21b286c9f` | **UNCHANGED (`PASS`)** |
| `docs/research/w06_dev_selection_harness_qa_01.md` | `2620638d08d76dd619743f606e004c14fe5822635caafd130a258d5e052ff7d9` | **UNCHANGED (`PASS`)** |
| `scripts/audit_w06_dev_selection_harness.py` | `878f89ecd80e62a80c1ad23e9a48fa03ace4bb1b228c5ba1814c3cf632a3bd80` | **UNCHANGED (`PASS`)** |
| `apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py` | `b97615b4279a669e0064213681442a3c7506a5fc048f77ca9b5814d6c882bc18` | **UNCHANGED (`PASS`)** |

---

## 3. Independent Authority & Oracle Verification (`Q2-03` .. `Q2-13`)

### 3.1 Frozen W06 Authorities (`Q2-03`)
All 18 frozen W06 authority files were independently hashed with LF normalization and verified byte-identical:
- `data/evaluation/w06/w06_scenarios_freeze_v1.json`: `c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1`
- `data/evaluation/w06/w06_p11_assignment_manifest_v1.json`: `0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62`
- `data/evaluation/w06/w06_dev_fixtures_freeze_v1.json`: `bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050`
- `data/evaluation/w06/w06_dev_fixture_manifest_v1.json`: `15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98`
- `data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json`: `285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa`
- `data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json`: `6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c`
- `data/evaluation/w06/w06_measurement_contract_v1.json`: `0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298`
- `data/evaluation/w06/w06_model_preflight_portable_schema_v2_manifest.json`: `b11974a5119dc49de80d96e2a9ed11ad5c7aca93aff25fec2cb54049a27c6b28`
- `data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json`: `2c8c3384e1977816aeff559cddc8010ad9b57fdfa62b618090b7f3911e732e65`
- `data/curated/gomate_places_freeze_v2.json`: `f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444`

### 3.2 Independent DEV Bundle & REC-A-CORE-V2 Oracles (`Q2-04`, `Q2-05`, `Q2-10` .. `Q2-13`)
- **DEV Fixture Partitioning:** `80` total (`20` `W06_DEV_TUNE`, `60` `W06_DEV_SELECT`), `all_dev_exact_overlap_with_final = 0`, `dev_tune_near_overlap_with_final = 0`, and all 6 stratification marginals (`destination`, `days`, `interest_count`, `budget`, `travel_style`, `weekend`) match the frozen manifest exactly.
- **REC-A-CORE-V2 Context Oracle:** Independently filtering `gomate_places_freeze_v2.json` by `is_rec_a_core_v2 is True` yields `ha-noi = 145`, `da-nang = 289` (excluding the 4 map-discovery-only POIs out of `293`), `ha-long = 188`, total `622`, with `0` non-core or secondary POI leakage.

---

## 4. Complete 67-Check Verification Matrix (`Q2-01` .. `Q2-67`)

| Check ID | Category | Description | Status |
|---|---|---|---|
| `Q2-01` | `SOURCE_INTEGRITY` | Verify `develop` SHA equals `cbbfbd3e5a54d25016609d73ea71939442bf7b10` and production harness is unmodified | **PASS** |
| `Q2-02` | `HISTORICAL_QA01_IMMUTABILITY` | Verify all 4 historical QA-01 files remain byte-identical with `40 total / 30 PASS / 10 FAIL` | **PASS** |
| `Q2-03` | `FROZEN_AUTHORITIES` | Independently verify LF-normalized SHA256 of all 18 frozen W06 authorities | **PASS** |
| `Q2-04` | `DEV_BUNDLE` | Independently verify DEV bundle SHA256 and zero final-100 overlap | **PASS** |
| `Q2-05` | `DEV_BUNDLE` | Independently verify 80/20/60 counts and all 6 DEV-TUNE and DEV-SELECT marginals | **PASS** |
| `Q2-06` | `FINAL100_FIREWALL` | Verify direct/relative final100 and P11 paths and `W06-SCENARIO-*` IDs fail closed | **PASS** |
| `Q2-07` | `FINAL100_FIREWALL` | Verify copied/renamed final100 and P11 files with innocent names are blocked by content SHA256 | **PASS** |
| `Q2-08` | `FINAL100_FIREWALL` | Verify symlink/hardlink to final100 bundle is resolved and blocked by firewall | **PASS** |
| `Q2-09` | `FINAL100_FIREWALL` | Verify cross-partition and invalid `fixture_label` pairings fail closed | **PASS** |
| `Q2-10` | `RECA_CONTEXT` | Independently verify `ha-noi` REC-A-CORE-V2 count == 145 and exact sorted `place_id` set | **PASS** |
| `Q2-11` | `RECA_CONTEXT` | Independently verify `da-nang` REC-A-CORE-V2 count == 289 (excluding 4 map-discovery POIs out of 293) | **PASS** |
| `Q2-12` | `RECA_CONTEXT` | Independently verify `ha-long` REC-A-CORE-V2 count == 188 and total core == 622 | **PASS** |
| `Q2-13` | `RECA_CONTEXT` | Verify zero secondary or non-core POI leakage across all 3 destination contexts | **PASS** |
| `Q2-14` | `CANDIDATE_REGISTRY` | Verify exact C1/C2/C3 candidate registry and rejection of C4 | **PASS** |
| `Q2-15` | `PROVIDER_CONFIGS` | Independently verify Portable Schema V2 SHA256 == `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490` across C1/C2/C3 | **PASS** |
| `Q2-16` | `PROVIDER_CONFIGS` | Verify C1 (`gemini-3.8-flash`) config matches frozen 01C/01D contract | **PASS** |
| `Q2-17` | `PROVIDER_CONFIGS` | Verify C2 (`gpt-6.1-sol`) config matches frozen 01C/01D contract | **PASS** |
| `Q2-18` | `PROVIDER_CONFIGS` | Verify C3 (`claude-sonnet-5-5`) config matches frozen 01C/01D contract | **PASS** |
| `Q2-19` | `PROVIDER_CONFIGS` | Verify identical scenario, catalog, system/user prompt, and schema V2 hashes across C1/C2/C3 | **PASS** |
| `Q2-20` | `STRICT_PRIMARY_PARSER` | Verify valid raw JSON passes while markdown code fences, leading/trailing prose, and trailing commas fail closed as `MALFORMED_JSON` | **PASS** |
| `Q2-21` | `STRICT_PRIMARY_PARSER` | Verify zero semantic rescue on missing `plan_id`, `scenario_id`, `destination_slug`, `budget_analysis`, `day_cost`, wrong primitive, or missing `POI_VISIT` `place_id` | **PASS** |
| `Q2-22` | `BATCH_INTEGRITY` | Verify missing or mismatched `returned_model_id` is classified as `MODEL_INTEGRITY_MISMATCH` (`counts_in_denominator=False`, `batch_stop_required=True`) and halts batch/aggregation/selection | **PASS** |
| `Q2-23` | `BATCH_INTEGRITY` | Verify `HARNESS_INTERNAL_ERROR` has `counts_in_denominator=False`, `batch_stop_required=True` and raises `HarnessInternalBatchStopError` | **PASS** |
| `Q2-24` | `BATCH_INTEGRITY` | Verify `scientific_code_bundle_sha256` mismatch raises `ScientificCodeBundleIntegrityError` before provider transport | **PASS** |
| `Q2-25` | `DENOMINATOR_INTEGRITY` | Verify 60 assigned (59 success + 1 `TIMEOUT`) preserves denominator == 60 and rate == 59/60 | **PASS** |
| `Q2-26` | `DENOMINATOR_INTEGRITY` | Verify missing receipt (59 of 60) fails closed with `DenominatorIntegrityError` | **PASS** |
| `Q2-27` | `DENOMINATOR_INTEGRITY` | Verify duplicate receipt, unexpected fixture/candidate/prompt, and `attempted=False` fail closed | **PASS** |
| `Q2-28` | `METRIC_MAPPING` | Verify valid itinerary maps to `(1,1,1)` and ungrounded `place_id` maps to `(1,0,0)` | **PASS** |
| `Q2-29` | `METRIC_MAPPING` | Verify known opening-hours violation causes `final_core_pass=False` while grounding remains `True` | **PASS** |
| `Q2-30` | `METRIC_MAPPING` | Verify `UNKNOWN` opening hours remain neutral and allow `final_core_pass=True` | **PASS** |
| `Q2-31` | `METRIC_MAPPING` | Verify `< 2` `POI_VISIT` items on any day fails core pass | **PASS** |
| `Q2-32` | `METRIC_MAPPING` | Verify `TRANSIT_ONLY` items do not count as `POI_VISIT` toward min 2 `POI_VISIT`/day | **PASS** |
| `Q2-33` | `METRIC_MAPPING` | Verify `TRAVEL_TIME` and `ROUTE_DISTANCE` are `NOT_EVALUABLE` and excluded from core pass | **PASS** |
| `Q2-34` | `METRIC_MAPPING` | Verify budget evaluation enforces `ESTIMATED_BUDGET_COMPLIANCE` ceiling without claiming real-world price accuracy | **PASS** |
| `Q2-35` | `METRIC_MAPPING` | Verify `PREFERENCE_SATISFACTION` is `NOT_PRIMARY_EVALUABLE` and excluded from core pass | **PASS** |
| `Q2-36` | `TEN_PP_SELECTION` | Verify 10pp survivor reduction for `A=0.90, B=0.82, C=0.73` keeps `[C1, C2]` and eliminates `[C3]` | **PASS** |
| `Q2-37` | `TEN_PP_SELECTION` | Verify exact 10pp boundary: `0.90 vs 0.80` survives, `0.90 vs 0.799999` is eliminated | **PASS** |
| `Q2-38` | `TEN_PP_SELECTION` | Verify comparison is strictly against best current survivor (no pairwise chaining for `0.90 / 0.82 / 0.74`) | **PASS** |
| `Q2-39` | `TEN_PP_SELECTION` | Verify early stopping when 1 survivor remains after Criterion 1, 2, or 3 without consulting cost/latency | **PASS** |
| `Q2-40` | `COST_ACCOUNTING` | Verify missing cost on a current survivor skips cost (`COST_CRITERION_SKIPPED_NOT_COMPARABLE`), whereas missing cost on an eliminated candidate does not block cost comparison among current survivors | **PASS** |
| `Q2-41` | `COST_ACCOUNTING` | Independently verify C1 billing adds `thought_tokens` once to `output_tokens` and rejects nonzero cache tokens | **PASS** |
| `Q2-42` | `COST_ACCOUNTING` | Independently verify C2 billing does not double-count `reasoning_tokens` already in `output_tokens` | **PASS** |
| `Q2-43` | `COST_ACCOUNTING` | Independently verify C3 billing does not double-count `thinking_tokens` already in `output_tokens` | **PASS** |
| `Q2-44` | `EXACT_COST_SELECTION` | Verify Criterion 4 uses exact `canonical_cost_usd_decimal` / `median_canonical_cost_usd_decimal` and ignores inverted float display fields | **PASS** |
| `Q2-45` | `EXACT_COST_SELECTION` | Verify `serialize -> deserialize -> aggregate -> select` preserves `1e-28` `Decimal` cost ordering in both directions | **PASS** |
| `Q2-46` | `LATENCY_NS_SELECTION` | Verify `1000000000001 ns` beats `1000000000002 ns` ignoring `latency_ms` float and fails closed when `latency_ns` is missing for a survivor | **PASS** |
| `Q2-47` | `LATENCY_NS_SELECTION` | Verify `n=60` even-sample half-nanosecond median (`1000000000001.5`) is computed exactly and beats `1000000000002` | **PASS** |
| `Q2-48` | `PROMPT_FREEZE_FIREWALL` | Verify P1/P2 prompt registry constraints and exact single-prompt status `LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON` | **PASS** |
| `Q2-49` | `PROMPT_FREEZE_FIREWALL` | Verify all 8 prompt freeze firewall failure modes (missing, hash, candidates, provider config, DEV bundle, plan, code bundle, schema V2) fail closed | **PASS** |
| `Q2-50` | `PROVENANCE_FAIL_CLOSED` | Verify missing required provenance fields fail closed across all 5 persisted artifact models (22 field checks) | **PASS** |
| `Q2-51` | `PROVENANCE_FAIL_CLOSED` | Verify persisted `model_validate` never calls git HEAD, code bundle, or provider registry resolvers | **PASS** |
| `Q2-52` | `PROVENANCE_LIFECYCLE` | Verify receipt with `code_basis=A` and `runtime_head=B` reloads at `C` preserving `A` and `B` without rewriting to `C` | **PASS** |
| `Q2-53` | `SCIENTIFIC_CODE_BUNDLE` | Verify exact 13-file ordered scientific code bundle path set and rejection of empty/partial/reordered `file_hashes` | **PASS** |
| `Q2-54` | `SCIENTIFIC_CODE_BUNDLE` | Verify independent LF-normalized SHA256 calculation matches two fresh subprocess invocations | **PASS** |
| `Q2-55` | `AUTHORITATIVE_BYTE_HASHING` | Verify same-size + restored-`mtime_ns` file mutation changes bundle SHA256 and stops execution before provider transport | **PASS** |
| `Q2-56` | `PROVIDER_CONFIG_PROVENANCE` | Verify historical `provider_config_sha256` loads for audit inspection but fails closed at execution action boundary before transport | **PASS** |
| `Q2-57` | `CELL_IMMUTABILITY` | Verify all 6 cell overwrite and `run_id` reuse vectors fail closed with `ImmutableCellExecutionError` | **PASS** |
| `Q2-58` | `PLAN_DETERMINISM` | Verify exact 60 (P1 DEV-TUNE), 120 (P1+P2 DEV-TUNE), and 180 (DEV-SELECT) call budgets with `retry=0` | **PASS** |
| `Q2-59` | `PLAN_DETERMINISM` | Verify execution plan generation in fresh subprocesses yields identical `plan_sha256` and ordered `run_ids` | **PASS** |
| `Q2-60` | `STOCHASTICITY_GATE` | Verify stochasticity diagnostic plan fails closed before a DEV-SELECT winner is selected | **PASS** |
| `Q2-61` | `STOCHASTICITY_GATE` | Verify stochasticity plan uses exact 5 smallest DEV-TUNE IDs × 3 executions = 15 calls with `retry=0` and zero feedback into selection | **PASS** |
| `Q2-62` | `TEN_PP_SELECTION` | Verify selection functions accept no manual override parameters and break exact 5-criterion ties via `C1>C2>C3` administrative tiebreak | **PASS** |
| `Q2-63` | `NO_FINAL100_USE` | Verify `final100_used` is `false` and `winner_selected` is `false` across all DEV harness receipts | **PASS** |
| `Q2-64` | `NO_LIVE_CALLS` | Verify CLI rejects `--live` / `--execute-live` / `--select-winner` with `DevHarnessOfflineViolationError` and `live_provider_calls == 0` | **PASS** |
| `Q2-65` | `TEST_ENVIRONMENT_INTEGRITY` | Verify `conftest.py` skips only historical `test_w06_dev_selection_harness_qa_01.py` and never skips QA-02 | **PASS** |
| `Q2-66` | `TEST_ENVIRONMENT_INTEGRITY` | Verify `conftest.py` contains zero runtime monkeypatching of `dev_selection_harness` | **PASS** |
| `Q2-67` | `LIVE_RUNNER_READINESS_BOUNDARY` | Verify live-runner readiness boundary (`LIVE_DEV_RUNNER_IMPLEMENTED=false`, `DEV_MODEL_EXECUTION_ALLOWED=false`, `NEXT_GATE=W06-DEV-LIVE-RUNNER-01-OFFLINE`) | **PASS** |

---

## 5. Live-Runner Readiness Boundary (`Q2-67`)

Passing `QA-02` certifies the offline W06 DEV Selection Harness (`apps/ai-service/app/evaluation/dev_selection_harness.py`) and unblocks offline implementation of the live DEV runner. It **does not** authorize live provider calls prior to the offline live-runner implementation and audit gate:

- `HARNESS_SCIENTIFIC_READINESS = PASS`
- `LIVE_DEV_RUNNER_IMPLEMENTED = false`
- `LIVE_DEV_RUNNER_IN_SCIENTIFIC_BUNDLE = false`
- `LIVE_DEV_RUNNER_OFFLINE_QA_COMPLETE = false`
- `DEV_MODEL_EXECUTION_ALLOWED = false`
- `NEXT_GATE = W06-DEV-LIVE-RUNNER-01-OFFLINE`
