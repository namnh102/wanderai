# W06 Model Preflight Schema Portability Amendment v1 (`01C`)

- **Task ID:** `W06-MODEL-PREFLIGHT-01C-PORTABLE-SCHEMA-AMENDMENT-OFFLINE`
- **Amendment ID:** `W06-MODEL-PREFLIGHT-SCHEMA-PORTABILITY-AMENDMENT-01`
- **Version:** `1.0.0`
- **Base `develop` SHA:** `8b88ec05cec2697fc26049bad140d4117028f69e`
- **Phase:** `OFFLINE_FORMAL_AMENDMENT`
- **Live Provider Calls:** `0`
- **Provider Cost (USD):** `0`

**NO LIVE PROVIDER CALL WAS PERFORMED IN 01C.**

---

## 1. What Happened in Phase 01B & Why C3 Failed Before Generation

In `W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE` (`PR #44`, merge commit `8b88ec05cec2697fc26049bad140d4117028f69e`), a single live technical smoke request per candidate (`1` call per candidate, `0` retries) was executed against the synthetic smoke fixture `W06-PREFLIGHT-SMOKE-01` using the strict V1 generation schema (`COMMON_GENERATION_SCHEMA_SHA256_V1 = 5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c`):

| Candidate | Provider / Model ID | Phase 01B V1 Status | Failure Classification |
| :--- | :--- | :--- | :--- |
| `C1` | Google `gemini-3.8-flash` | `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V1` | `None` |
| `C2` | OpenAI `gpt-6.1-sol` | `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V1` | `None` |
| `C3` | Anthropic `claude-sonnet-5-5` | `FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V1` | `FAILED_STRUCTURED_OUTPUT_COMPATIBILITY` |

Candidate `C3` (`claude-sonnet-5-5`) failed **before model generation** (`0` input tokens billed, `0` output tokens generated) with an immediate `HTTP 400 BadRequestError` from the Anthropic Messages API:

```text
Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "output_config.format.schema: For 'integer' type, property 'minimum' is not supported"}}
```

---

## 2. Why This Is a Harness / Schema-Portability Issue (Official Provider Evidence)

Per official Anthropic Structured Outputs documentation (`https://platform.claude.com/docs/en/build-with-claude/structured-outputs`, section *JSON Schema limitations*, accessed `2026-10-17`):

- **Supported by Anthropic raw `output_config.format.schema`:**
  - `object`, `properties`, `required`, `additionalProperties: false`
  - Primitive types (`string`, `integer`, `number`, `boolean`, `null`)
  - `enum` (primitive values), `const`, `anyOf`
  - Internal non-recursive `$ref` and `$defs`
  - Array `minItems` **only** with values `0` or `1`
- **Not Supported by Anthropic raw `output_config.format.schema`:**
  - Numerical constraints: `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`
  - String length constraints: `minLength`, `maxLength`
  - Array constraints beyond `minItems` in `{0, 1}`: `minItems > 1`, `maxItems`, `uniqueItems`, `contains`, `minContains`, `maxContains`
  - External `$ref`, recursive schemas, or `additionalProperties` set to anything other than `false`

When callers pass a Pydantic model to Anthropic's SDK helper `transform_schema()`, the SDK automatically strips unsupported constraints (`minimum`, `maximum`, `minLength`, etc.) and appends them to property descriptions before sending the request. However, because our cross-provider preflight harness passes a shared raw JSON Schema dictionary directly into `output_config.format.schema.schema` to guarantee identical cross-provider schema hashes, the raw V1 dictionary contained `minimum`, `maximum`, and `minLength` keywords emitted by `BenchmarkPlanResponse.model_json_schema()`.

Consequently, the `HTTP 400` rejection in Phase 01B was a **deterministic harness structured-output schema portability defect**, not a model reasoning or itinerary-generation failure.

---

## 3. Why Historical C3 Failure Remains Valid & Why Amendment Occurs Before DEV

1. **Historical 01B Immutability:**
   - Phase 01B accurately proved that raw V1 generation schema (`5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c`) is not portable across all three providers' raw structured-output decoders.
   - All Phase 01B artifacts (`w06_model_preflight_01b_live_plan_v1.json`, `w06_model_preflight_01b_live_receipt_v1.json`, and `model_preflight_01b_live/{C1,C2,C3}/*`) remain **byte-for-byte unchanged**. `C3` remains recorded as `FAILED_TECHNICAL_PREFLIGHT` (`FAILED_STRUCTURED_OUTPUT_COMPATIBILITY`) under V1.
2. **Admissibility Before DEV:**
   - This technical amendment is scientifically admissible **only** because:
     - `DEV-TUNE` has **not** started (`dev_tune_started = false`)
     - `DEV-SELECT` has **not** started (`dev_select_started = false`)
     - No winning model has been selected (`winner_selected = false`)
     - The frozen final-100 benchmark scenarios have **never** been executed (`final_100_used = false`)
     - `C3` failed before any tokens were generated (`HTTP 400` schema compiler rejection)
     - No model quality or performance evidence was used to design the amendment

---

## 4. Semantic Schema vs. V1 Generation Schema vs. V2 Portable Generation Schema

| Schema Authority | Identifier / Constant | Canonical SHA256 | Role |
| :--- | :--- | :--- | :--- |
| **Semantic Authority** | `SEMANTIC_BENCHMARK_PLAN_JSON_SCHEMA` (`BenchmarkPlanResponse.model_json_schema()`) | `e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555` | Frozen scientific contract & post-generation Pydantic validator (`BenchmarkPlanResponse.model_validate`). **Unchanged.** |
| **Strict Generation Schema V1** | `COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1` | `5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c` | Historical Phase 01A/01B strict projection (strips `default`, closes `additionalProperties: false`, materializes sorted `required`). **Unchanged.** |
| **Portable Generation Schema V2** | `COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2` | `825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490` | Phase 01C cross-provider portable constrained-decoding projection derived deterministically from V1. Shared identically across `C1`, `C2`, and `C3`. |

---

## 5. Exact Stripped Keywords & Deterministic Constraint Description Annotations

In projecting `V1 -> V2` (`W06_PORTABLE_GENERATION_SCHEMA_V1_TO_V2_DETERMINISTIC_PROJECTION`), exactly **16** non-portable raw constraint occurrences across **15** schema paths are removed (`minimum`: 5, `maximum`: 1, `minLength`: 10), and their exact semantics are deterministically encoded into each node's `description` field as `[SEMANTIC_CONSTRAINTS: ...]`:

| # | Schema Path | Removed Keyword(s) | Deterministic Description Annotation in V2 |
| :--- | :--- | :--- | :--- |
| 1 | `$.$defs.BenchmarkItineraryDay.properties.day_number` | `minimum=1` | `[SEMANTIC_CONSTRAINTS: minimum=1]` |
| 2 | `$.$defs.BenchmarkItineraryDay.properties.title` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 3 | `$.$defs.BenchmarkItineraryDay.properties.day_cost` | `minimum=0` | `[SEMANTIC_CONSTRAINTS: minimum=0]` |
| 4 | `$.$defs.BenchmarkItineraryItem.properties.order_index` | `minimum=1` | `[SEMANTIC_CONSTRAINTS: minimum=1]` |
| 5 | `$.$defs.BenchmarkItineraryItem.properties.start_time` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 6 | `$.$defs.BenchmarkItineraryItem.properties.end_time` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 7 | `$.$defs.BenchmarkItineraryItem.properties.activity` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 8 | `$.$defs.BenchmarkItineraryItem.properties.estimated_cost` | `minimum=0` | `[SEMANTIC_CONSTRAINTS: minimum=0]` |
| 9 | `$.properties.plan_id` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 10 | `$.properties.scenario_id` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 11 | `$.properties.destination_slug` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 12 | `$.properties.destination` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 13–14 | `$.properties.total_days` | `maximum=14`, `minimum=1` | `[SEMANTIC_CONSTRAINTS: maximum=14; minimum=1]` |
| 15 | `$.properties.overview` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |
| 16 | `$.properties.best_time_to_visit` | `minLength=1` | `[SEMANTIC_CONSTRAINTS: minLength=1]` |

*(Note: Row 13–14 has 2 keywords on `$.properties.total_days`, yielding 16 total removed keyword occurrences across 15 properties).*

**Preserved in V2:**
- `minItems: 1` on `$.properties.days` and `$.$defs.BenchmarkItineraryDay.properties.items` (explicitly supported by Anthropic, OpenAI, and Google).
- `additionalProperties: false` and sorted `required` materialization on every object node.
- `ActivityKind` enum `["POI_VISIT", "TRANSIT_ONLY"]`.
- Nullable `place_id` (`anyOf: [{"type": "string"}, {"type": "null"}]`), never encoded as a catalog enum.

---

## 6. How Semantic Enforcement Is Retained

Removing non-portable constraint keywords from the provider constrained-decoding schema **does not relax scientific evaluation**. Every candidate response is validated post-generation by `BenchmarkPlanResponse.model_validate(...)` in `apps/ai-service/app/schemas/planner_benchmark.py` (`SEMANTIC_SCHEMA_SHA256 = e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`), which strictly rejects:
- `total_days = 0` or `total_days = 15`
- `day_number = 0` or `order_index = 0`
- `estimated_cost < 0` or `day_cost < 0`
- Empty required strings (`minLength = 1`)
- Empty `days` or `items` lists (`minItems = 1`)

---

## 7. Why All Three Candidates Must Rerun Technical Smoke Under V2 (`01D`) & Why This Is Not Claude-Specific Tuning

- **No Provider-Specific Schema:** `COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2` (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`) is applied **identically** to `C1` (Google), `C2` (OpenAI), and `C3` (Anthropic). There is no Claude-only schema and no candidate-specific prompt tuning.
- **No Grandfathering from V1:** Because the constrained-decoding schema changed from `V1` to `V2`, `C1` and `C2` cannot grandfather their `V1` live smoke pass into `DEV`. All three candidates (`C1`, `C2`, `C3`) are placed in status `PENDING_SCHEMA_V2_LIVE_REVALIDATION` and must pass a clean `1`-call-per-candidate live technical revalidation under `V2` in the next gate (`W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION`) before `DEV` model selection is unlocked.
