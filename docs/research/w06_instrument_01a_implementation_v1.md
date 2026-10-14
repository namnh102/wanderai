# W06 Benchmark Planner Path & Live-Run Evidence Harness (`W06-INSTRUMENT-01A`)

- **Task ID:** `W06-INSTRUMENT-01A`
- **Base `develop` SHA:** `7fd5364ed4671c06b0c911b6fd53bd9f54cbc322`
- **Contract Basis:** `W06-MEASUREMENT-CONTRACT-01` v1.1.0 (`data/evaluation/w06/w06_measurement_contract_v1.json`)
- **Machine-Readable Receipt:** [`data/evaluation/w06/w06_instrument_01a_receipt_v1.json`](../../data/evaluation/w06/w06_instrument_01a_receipt_v1.json)

---

## 1. Purpose & Production Boundary

`W06-INSTRUMENT-01A` builds the **benchmark-only** itinerary planning execution path and forensic evidence writer required to produce groundable itinerary outputs under `W06-MEASUREMENT-CONTRACT-01` v1.1.0:
- The production endpoint `POST /planner` (`apps/ai-service/app/routers/planner.py`), production schema (`apps/ai-service/app/schemas/planner.py`), and production prompt (`TRAVEL_PLANNER_V1` in `apps/ai-service/app/prompts/planner_prompt.py`) remain **100% untouched** (`0` diff lines), preserving full backward compatibility for existing mobile/backend callers and existing offline tests.
- The benchmark harness (`apps/ai-service/app/services/planner_benchmark_runner.py` and `scripts/run_w06_planner_benchmark.py`) never calls the production mock-fallback branch and fails closed whenever `GEMINI_API_KEY` is absent.

---

## 2. Delivered Components

1. **Strict Benchmark Schemas (`apps/ai-service/app/schemas/planner_benchmark.py`):**
   - `ActivityKind`: strictly `POI_VISIT` | `TRANSIT_ONLY`.
   - `BenchmarkItineraryItem`: requires all 10 fields (`order_index`, `start_time`, `end_time`, `activity_kind`, `activity`, `place_name`, `place_id`, `notes`, `estimated_cost`, `transport_mode`) with `extra="forbid"` and no silent default for `activity_kind`:
     - `POI_VISIT`: requires non-empty `place_id` and non-empty `place_name`.
     - `TRANSIT_ONLY`: requires `place_id = null`.
     - Missing or unknown `activity_kind` is rejected during strict validation.
   - `BenchmarkScenarioInput`: enforces primary destinations (`ha-noi`, `da-nang`, `ha-long`) and the canonical 7-interest taxonomy (`food_cuisine`, `culture_history`, `nature_outdoor`, `coffee_culture`, `beach_island`, `shopping_local`, `nightlife_entertainment`).
2. **Deterministic Catalog Context & Versioned Prompt (`apps/ai-service/app/prompts/planner_benchmark_prompt.py`):**
   - `build_destination_catalog_context`: loads `data/curated/gomate_places_freeze_v2.json`, filters `is_rec_a_core_v2 == true`, sorts deterministically by `place_id` ascending, and verifies exact counts (`ha-noi = 145`, `da-nang = 289`, `ha-long = 188`, `total = 622`).
   - `TRAVEL_PLANNER_BENCHMARK_V1`: supplies the full allowed destination catalog context and instructs exact `place_id` copying for `POI_VISIT`, `place_id = null` for `TRANSIT_ONLY`, `HH:MM` time windows, non-duplication of `place_id`, and JSON-only output.
3. **Live-Only Benchmark Runner & Evidence Writer (`apps/ai-service/app/services/planner_benchmark_runner.py`):**
   - Fails closed on missing API key (`LIVE_PROVIDER_REQUIRED`), mock mode (`MOCK_OR_FALLBACK_RUN`), model mismatch (`MODEL_ID_MISMATCH`), missing metadata (`MISSING_REQUIRED_RUN_METADATA`), API failure (`API_ERROR`), invalid JSON (`UNPARSABLE_MODEL_OUTPUT`), or schema violation (`SCHEMA_NONCOMPLIANT_OUTPUT`), with **zero silent retries**.
   - Measures `generation_latency_ms` strictly around `models.generate_content(...)`.
   - Captures authoritative provider token usage (`input_tokens`, `output_tokens`, `total_tokens`) when present, keeping `null` when unavailable (never estimating from string length).
   - Preserves `raw_provider_response.txt` verbatim before cleaning/parsing so raw forensic output is retained even on JSON parse or schema validation failure.
   - Computes SHA256 digests (`EXACT_PERSISTED_UTF8_LF_BYTES_SHA256`) over exact persisted UTF-8 LF bytes (`scenario_sha256`, `catalog_sha256`, `raw_response_sha256`, `parsed_response_sha256`).
4. **Controlled CLI (`scripts/run_w06_planner_benchmark.py`):**
   - `validate-environment`: offline validation of catalog, primary destination counts, model config, measurement contract, and benchmark prompt.
   - `prepare`: validates scenario input and writes `scenario_input.json`, `catalog_context.json`, `benchmark_prompt.txt`, and `preparation_manifest.json` without calling the provider.
   - `execute`: executes a single scenario against the live provider and writes `scenario_input.json`, `raw_provider_response.txt`, `parsed_plan_response.json`, and `run_manifest.json`.

---

## 3. Prerequisite Implementation Matrix (`P1`–`P12`)

| Prerequisite | Status in `W06-INSTRUMENT-01A` | Notes |
|---|---|---|
| `P1` | `PARTIALLY_IMPLEMENTED` | Benchmark output schema, prompt, and parser enforce `POI_VISIT` / `TRANSIT_ONLY` and required `place_id`; evaluator-side item classification belongs to `01B`. |
| `P2` | `PARTIALLY_IMPLEMENTED` | Deterministic `REC-A-CORE-V2` catalog context builder (`145 / 289 / 188`) implemented; post-generation evaluator membership check belongs to `01B`. |
| `P3` | `NOT_IMPLEMENTED` | Evaluator destination membership check deferred to `01B`. |
| `P4` | `NOT_IMPLEMENTED` | Evaluator duplicate-POI check deferred to `01B`. |
| `P5` | `NOT_IMPLEMENTED` | Evaluator `HH:MM` interval and overlap checker deferred to `01B`. |
| `P6` | `NOT_IMPLEMENTED` | Evaluator `estimated_budget_violation_rate` checker deferred to `01B`. |
| `P7` | `NOT_IMPLEMENTED` | Opening-hours parser and three-state evaluator deferred to `01B`. |
| `P8` | `PARTIALLY_IMPLEMENTED` | Single-run harness rejects mock/fallback and fails closed with zero retries; 100-scenario denominator aggregation belongs to `01B / 01C`. |
| `P9` | `IMPLEMENTED` | Persists `scenario_input.json`, `raw_provider_response.txt`, `parsed_plan_response.json`, and `run_manifest.json`. |
| `P10` | `PARTIALLY_IMPLEMENTED` | Single-run cryptographic manifest implemented; `evaluator_sha256` and batch manifest belong to `01B / 01C`. |
| `P11` | `NOT_IMPLEMENTED` | Frozen 100-scenario manifest deferred to scenario-freeze task. |
| `P12` | `IMPLEMENTED` | Separate benchmark-only execution path cannot return production canned mock output. |
