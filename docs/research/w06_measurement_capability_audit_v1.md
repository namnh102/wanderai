# W06 Measurement Capability & Evidence Gap Audit (V1)

- **Audit ID:** `W06-MEASUREMENT-AUDIT-01`
- **Audit Version:** `1.0.0`
- **Base `develop` SHA:** `4de240aeaa5277420695ed5f1de85f7b67cd6c54`
- **Machine-Readable Artifact:** `data/evaluation/w06/w06_measurement_capability_audit_v1.json`
- **Repository Mutation Scope:** `AUDIT_ARTIFACTS_AND_TESTS_ONLY`
- **Scientific Results Generated:** `false`
- **Planner Behavior Modified:** `false`
- **Evaluator Behavior Modified:** `false`
- **Scenarios Modified:** `false`
- **Preregistration Created:** `false`

---

## 1. Executive Summary & Scope Boundary

This audit freezes and documents what the current W06 itinerary-planning stack can and cannot measure scientifically at `develop` commit `4de240aeaa5277420695ed5f1de85f7b67cd6c54`.

Every capability dimension is classified strictly using the controlled vocabulary:
- `SUPPORTED`
- `PARTIALLY_SUPPORTED`
- `NOT_EVALUABLE`
- `UNKNOWN`

> [!IMPORTANT]
> **Instrument Validity vs. Planner Performance:**
> Where this audit classifies a dimension as `NOT_EVALUABLE` or `PARTIALLY_SUPPORTED`, that finding reflects **missing measurement instrumentation, ungrounded output schemas, or absent reference data**—it does **NOT** establish poor planner performance.

---

## 2. Inventory of Current W06 Assets

| Asset Category | Exact Repository Paths |
| :--- | :--- |
| **Itinerary / Planner Evaluator(s)** | `data/evaluation/planner/evaluate_planner.py` |
| **Planner / Router / Orchestrator** | `apps/ai-service/app/routers/planner.py`<br>`apps/ai-service/app/prompts/planner_prompt.py`<br>`apps/backend/src/modules/trips/trips.service.ts`<br>`apps/backend/src/modules/ai-proxy/ai-proxy.service.ts`<br>`apps/ai-service/app/services/agent.py` *(legacy unused stub `handle_plan`)* |
| **Itinerary Output Schemas / Models** | `apps/ai-service/app/schemas/planner.py`<br>`apps/backend/src/modules/trips/dto/plan-trip.dto.ts`<br>`apps/backend/src/modules/trips/dto/bulk-itinerary.dto.ts`<br>`apps/backend/src/modules/trips/dto/add-itinerary.dto.ts`<br>`apps/backend/prisma/schema.prisma` (`Trip`, `Itinerary`, `ItineraryItem`)<br>`apps/mobile/lib/features/trips/data/trip_models.dart` |
| **Benchmark / Scenario Files** | `data/evaluation/planner/da_nang_4d.json`<br>`data/evaluation/planner/ha_giang_3d.json`<br>`data/evaluation/planner/moc_chau_3d.json` |
| **Planner Tests** | `apps/ai-service/tests/test_planner.py`<br>`apps/ai-service/tests/test_planner_failures.py`<br>`apps/ai-service/tests/test_planner_live.py`<br>`apps/backend/test/planner.e2e-spec.ts`<br>`apps/mobile/test/planner_test.dart` |
| **Mock / Fallback Paths** | `apps/ai-service/app/routers/planner.py` (lines 24, 123–150)<br>`apps/ai-service/app/services/agent.py` (lines 73–98, unused stub) |
| **AI Provider / Model Configuration** | `apps/ai-service/app/config.py` (lines 4–5, 10–12)<br>`apps/ai-service/app/routers/planner.py` (lines 24, 101–110) |
| **Relevant POI Freeze / Catalog** | `data/curated/gomate_places_freeze_v2.json`<br>`data/curated/gomate_places_freeze_v1.json`<br>`data/manifests/dataset-freeze-v2.yaml`<br>`data/manifests/dataset-freeze-v2.sha256` |
| **Preference Seed / Data** | `data/evaluation/synthetic/preferences_n300_seed42.json`<br>`data/research/preferences/synthetic_preferences_v1.jsonl`<br>`data/research/preferences/synthetic_preferences_distribution_v1.json`<br>`scripts/generate_synthetic_preferences.py`<br>`apps/backend/prisma/schema.prisma` (`TravelPreference`)<br>`apps/backend/src/modules/users/dto/update-preferences.dto.ts` |
| **W06 Roadmap & Alignment Docs** | `docs/roadmap/gomate-thesis-research-roadmap-v1.md`<br>`docs/roadmap/gomate-product-research-alignment-matrix-v1.md`<br>`docs/project-control/ROADMAP.md`<br>`docs/ai/ai-planner.md`<br>`docs/api/ai-planner-api.md`<br>`docs/design/gomate-ai-planner-contract-v1.md`<br>`docs/audit/ui/task-08.2.3.6-ai-planner-contract-lock.md` |

---

## 3. Audit of Current Planner Benchmark Scenarios

- **`CURRENT_SCENARIO_COUNT`:** `3`
- **`CURRENT_DESTINATIONS`:** `["Đà Nẵng", "Hà Giang", "Mộc Châu"]`

| Scenario ID | File Path | Destination | Days | `max_budget` (VND) | `min_items_per_day` | `required_keywords` | Interests | `GROUNDING_SCOPE` | Catalog Evidence |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :--- |
| `eval_da_nang_4d` | `data/evaluation/planner/da_nang_4d.json` | Đà Nẵng | 4 | `8,000,000` | 3 | `["Mỹ Khê", "Hội An", "Cầu Rồng"]` | `["beach", "food", "culture"]` | `SUPPORTED` | Đà Nẵng has **289** `REC-A-CORE-V2` POIs + **4** non-core POIs (**293** total) in `gomate_places_freeze_v2.json`. *(Note: keyword `"Hội An"` refers to the 50 secondary non-core POIs under `destination_slug = "hoi-an"`).* |
| `eval_ha_giang_3d` | `data/evaluation/planner/ha_giang_3d.json` | Hà Giang | 3 | `3,500,000` | 3 | `["Mã Pí Lèng", "Đồng Văn", "Lũng Cú"]` | `["mountain", "photography", "culture"]` | `OUT_OF_CATALOG_SCOPE` | **0** verified POIs in `gomate_places_freeze_v2.json` (`core = 0`, `total = 0`). Exists only as a legacy row in `database/seed/destinations.json`. |
| `eval_moc_chau_3d` | `data/evaluation/planner/moc_chau_3d.json` | Mộc Châu | 3 | `2,500,000` | 3 | `["Đồi chè", "Mộc Châu", "thác"]` | `["nature", "food", "photography"]` | `OUT_OF_CATALOG_SCOPE` | **0** verified POIs in `gomate_places_freeze_v2.json` (`core = 0`, `total = 0`). Completely absent from the frozen catalog. |

---

## 4. Verification of the "100 Scenarios" Claim

- **Verdict:** `REPO_CONFIRMED_100_SCENARIO_REQUIREMENT`
- **Authoritative Source File:** `docs/roadmap/gomate-thesis-research-roadmap-v1.md`
- **Repository Evidence:**
  1. **Lines 87–92 (`AGENT-EVAL-01: Itinerary Agent Constraint & Grounding Evaluation`):**
     > *"Objective: Empirically evaluate the Gemini itinerary planning agent across 100 test prompts: Constraint Satisfaction: Total budget compliance ($|\text{Cost} - \text{Budget}| \le \text{Threshold}$), opening hours compliance, time-slot overlap conflicts. Grounding Integrity: 100% of generated POIs must map to verified PostGIS IDs (zero fabricated places). Deliverables: `apps/ai-service/tests/test_planner_evaluation.py` and benchmark report."*
  2. **Lines 166–167 (`Week 6: Itinerary Agent Constraint Satisfaction Benchmarking`):**
     > *"Research Deliverables: Evaluation of Gemini itinerary planner over 100 benchmark trips: budget violation rate, schedule conflict rate, valid POI grounding rate ($= 100\%$)."*
- **Current Implementation Gap:** Only **3** scenario JSON files exist in `data/evaluation/planner/`, and `apps/ai-service/tests/test_planner_evaluation.py` does not exist yet.

---

## 5. Audit of Executable Evaluator Logic (`data/evaluation/planner/evaluate_planner.py`)

### 5.1. Currently Implemented Checks in `evaluate_itinerary(response_data, scenario_spec)`

| `CHECK_NAME` | `INPUT_FIELD` | `IMPLEMENTATION` | `WHAT_IT_REALLY_PROVES` | `WHAT_IT_DOES_NOT_PROVE` |
| :--- | :--- | :--- | :--- | :--- |
| `DAY_COUNT_RANGE_CHECK` | `response_data["days"]`, `expected_constraints["min_days"]`, `expected_constraints["max_days"]` | Checks `min_days <= len(days) <= max_days` (lines 16–21); appends to `failed_checks` if out of range. | The returned `days` list length lies within `[min_days, max_days]`. | Does not verify sequential `1..N` `day_number` values, calendar dates, or activity quality. |
| `DAY_COST_ARITHMETIC_CONSISTENCY` | `day["day_cost"]`, `day["items"][*]["estimated_cost"]` | Computes `computed_day_cost = sum(i.get("estimated_cost", 0) for i in items)` and checks `computed_day_cost == day_cost` (lines 29–37). | Internal arithmetic equality between item cost fields and `day_cost` (already summed deterministically by `planner.py`). | Does **NOT** prove real-world price accuracy, catalog price grounding, or compliance with `max_budget`. |
| `MIN_ITEMS_PER_DAY_CHECK` | `day["items"]`, `expected_constraints["min_items_per_day"]` | Checks `len(items) < min_items` (lines 39–43); appends to `failed_checks` if fewer items. | Each day has at least `min_items_per_day` activity entries. | Does not verify that items are distinct, non-trivial, geographically valid, or grounded in the catalog. |
| `TOTAL_COST_ARITHMETIC_CONSISTENCY` | `response_data["budget_analysis"]["estimated_cost"]`, `calculated_total` | Checks `calculated_total == reported_total` (lines 48–53); appends to `failed_checks` if unequal. | Internal arithmetic self-consistency that `budget_analysis.estimated_cost` equals the sum of item `estimated_cost` values. | Does **NOT** check `calculated_total <= max_budget`, nor whether `estimated_cost` reflects real external prices. |
| `REQUIRED_KEYWORDS_LOGGING_ONLY` | `expected_constraints["required_keywords"]`, `item["activity"]`, `item["place_name"]` | Computes `matched_keywords = [kw for kw in req_keywords if kw.lower() in all_activities_text.lower()]` and unconditionally appends to `passed_checks` (lines 56–58). | Logs how many required keywords matched as case-insensitive substrings in concatenated `activity + place_name` text. | **Cannot fail a test case:** even `0/3` matched keywords appends to `passed_checks` and returns `success = True`. |

### 5.2. Explicit Verification Across the 15 Target Dimensions

| Dimension | Checked by `evaluate_planner.py`? | Enforces Pass/Fail? | Audit Findings |
| :--- | :---: | :---: | :--- |
| 1. **Exact number of days** | Yes | Yes | Checks `min_days <= len(days) <= max_days` (in all 3 scenarios `min_days == max_days`). |
| 2. **Minimum activities per day** | Yes | Yes | Checks `len(day["items"]) >= min_items_per_day`. |
| 3. **Total cost arithmetic** | Yes | Yes | Internal self-consistency check only (`sum(item.estimated_cost) == day_cost` and `== budget_analysis.estimated_cost`). |
| 4. **Max budget constraint** | **No** | **No** | `expected_constraints.max_budget` is present in all 3 scenario JSONs but **never read or enforced** by `evaluate_planner.py`. |
| 5. **Place catalog grounding** | **No** | **No** | Evaluator does not load `gomate_places_freeze_v2.json` or any place catalog. |
| 6. **`place_id` existence** | **No** | **No** | `ItineraryItem` has no `place_id` field; evaluator does not check `place_id`. |
| 7. **Duplicate POIs** | **No** | **No** | Evaluator performs no check for duplicate `place_name` or duplicate POIs within/across days. |
| 8. **Correct destination** | **No** | **No** | Evaluator does not check `response_data["destination"]` or POI geographic membership. |
| 9. **Category diversity** | **No** | **No** | `ItineraryItem` has no `category` field; evaluator performs no diversity check. |
| 10. **Opening hours** | **No** | **No** | No opening-hours parser or check exists. |
| 11. **Schedule overlap** | **No** | **No** | Evaluator ignores `start_time` and `end_time`. |
| 12. **Travel time** | **No** | **No** | Evaluator performs no travel-time check and no road-network routing data exists. |
| 13. **Geographic efficiency** | **No** | **No** | `ItineraryItem` has no coordinates/`place_id`; evaluator computes no distances. |
| 14. **Required keywords** | Yes *(log only)* | **No** | Appends `Matched k/N keywords` to `passed_checks` unconditionally; never fails even if `k == 0`. |
| 15. **Preference satisfaction** | **No** | **No** | Evaluator ignores `request.interests` and `request.travel_style`. |

---

## 6. Audit of Itinerary Output Contract (`apps/ai-service/app/schemas/planner.py`)

In `apps/ai-service/app/schemas/planner.py` (lines 29–38), `ItineraryItem` defines:
```python
class ItineraryItem(BaseModel):
    order_index: int = 1
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    activity: str
    place_name: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: int = 0
    transport_mode: Optional[str] = None
```

| Field | Present in `ItineraryItem`? | Details |
| :--- | :---: | :--- |
| `place_id` | **No** | Absent from `ItineraryItem` and `TRAVEL_PLANNER_V1` prompt output format. (Only Prisma `ItineraryItem` and NestJS `BulkItineraryDto` have optional `placeId?: string`, which Flutter sets to `null` when saving AI plans.) |
| `place_name` | **Yes** | `Optional[str] = None` (free text generated by LLM). |
| `category` | **No** | Absent. |
| `coordinates` (`latitude` / `longitude`) | **No** | Absent. |
| `start_time` | **Yes** | `Optional[str] = None` (free-text string, prompted as `"HH:MM"`). |
| `end_time` | **Yes** | `Optional[str] = None` (free-text string, prompted as `"HH:MM"`). |
| `estimated_cost` | **Yes** | `int = 0` (clamped to `>= 0` in `planner.py:172-173`). |
| `source` / provenance fields | **No** | Absent. |

- **`GROUNDING_IDENTIFIER_STATUS`:** `NOT_CURRENTLY_MEASURABLE`
  Because `ItineraryItem` outputs only free-text `place_name` without `place_id`, `osm_id`, or coordinates—and no deterministic entity-linking function maps planner `place_name` outputs to `gomate_places_freeze_v2.json`—catalog grounding is `NOT_CURRENTLY_MEASURABLE`.

---

## 7. Audit of Catalog Data Capability (`data/curated/gomate_places_freeze_v2.json`)

### 7.1. Total & Per-Destination Counts

- **`TOTAL_POIS`:** `759`
- **`CORE_POIS` (`is_rec_a_core_v2 == true`):** `622`
- **Secondary Non-Core POIs (`is_rec_a_core_v2 == false`):** `137`

| Destination (`destination_slug`) | Destination Name | `REC-A-CORE-V2` Count | Non-Core Count | All Destination Map Count (Total) |
| :--- | :--- | :---: | :---: | :---: |
| `ha-noi` | Hà Nội | **145** | 0 | **145** |
| `da-nang` | Đà Nẵng | **289** | **4** | **293** |
| `ha-long` | Hạ Long | **188** | 0 | **188** |
| `hoi-an` | Hội An | 0 | 50 | 50 |
| `hue` | Huế | 0 | 50 | 50 |
| `nha-trang` | Nha Trang | 0 | 33 | 33 |
| **Total** | **6 Destinations** | **622** | **137** | **759** |

- **Đà Nẵng Verification:** Confirmed **289 core + 4 non-core = 293 total**.

### 7.2. Field Coverage Across Catalog

| Attribute | All Frozen POIs ($N = 759$) | `REC-A-CORE-V2` POIs ($N = 622$) | Audit Notes & Evidence |
| :--- | :---: | :---: | :--- |
| **`COORDINATES` (`latitude`, `longitude`)** | `759 / 759` (**100.00%**) | `622 / 622` (**100.00%**) | Supports straight-line Haversine `GEO_DISTANCE_PROXY` between catalog POIs once grounded. |
| **`CATEGORY` (`category`)** | `759 / 759` (**100.00%**) | `622 / 622` (**100.00%**) | Every frozen POI has a non-empty normalized category. |
| **`OPENING_HOURS` (`opening_hours`)** | `101 / 759` (**13.31%**) | `101 / 622` (**16.24%**) | By destination: Đà Nẵng `59`, Hà Nội `27`, Hạ Long `15`, secondary cities `0`. Examples: `"24/7"`, `"08:00-17:00"`, `"Mo-Su 09:00-17:00"`, `"Mo-Fr 10:00-22:00; Sa-Su 09:00-22:00"`, `"Mo off; Tu-Su 08:00-12:00,13:30-17:00"`, `"Mo-Su 05:30+"`. **Parser exists:** `No` (`parser_exists = false`). |
| **`NUMERIC_PRICE` (structured `priceMin`/`priceMax`)** | `0 / 759` (**0.00%**) | `0 / 622` (**0.00%**) | `gomate_places_freeze_v2.json` has zero `priceMin`/`priceMax` fields; `PlacesService` explicitly strips legacy seed prices. |
| **`FEE_TAG` (OSM `raw_data` `fee`)** | `23 / 759` (**3.03%**) | `12 / 622` (**1.93%**) | All POIs: `18` `"yes"`, `5` `"no"`. Core POIs: `10` `"yes"`, `2` `"no"`. *(Excludes `internet_access:fee`).* |
| **`CHARGE_TAG` (OSM `raw_data` `charge`)** | `6 / 759` (**0.79%**) | `4 / 622` (**0.64%**) | Raw strings: `"40000 VND"` ($\times 3$ core), `"50000 VND"` ($\times 1$ core), `"30000 VND"` ($\times 1$ non-core), `"30 VND"` ($\times 1$ non-core). |
| **`ROUTING_OR_TRAVEL_TIME_DATA`** | **No (`0`)** | **No (`0`)** | No OSRM/Valhalla/GraphHopper graph or travel-time matrix exists. `calculate_route.py` computes straight-line Haversine distance divided by `50 km/h`. |
| **`ADDRESS` (Factual OSM `addr:*` tags)** | `284 / 759` (**37.42%**) | `253 / 622` (**40.68%**) | Top-level `place.address` is non-null on `529 / 759` (`69.70%`), but `249 / 759` (`32.81%`) are importer-generated heuristic strings `"<name>, <city_slug>"`. Backend `osmAddress()` in `osm-tags.ts` serves only factual `addr:*` tags (`284 / 759` = `37.42%` all, `253 / 622` = `40.68%` core). |

---

## 8. Audit of Preference Evidence

- **Schema Support:** `TravelPreference` in `apps/backend/prisma/schema.prisma` (lines 91–107) and `UpdatePreferencesDto` in `apps/backend/src/modules/users/dto/update-preferences.dto.ts` support `travelStyle`, `budgetMin`, `budgetMax`, `preferredGroup`, `interests` (validated against 7 canonical tags), `avoidances`, and `dietaryNeeds`.
- **Interest Vocabulary Divergence:** `CANONICAL_INTERESTS` in `update-preferences.dto.ts` and `preferences_n300_seed42.json` uses `["food_cuisine", "culture_history", "nature_outdoor", "coffee_culture", "beach_island", "shopping_local", "nightlife_entertainment"]`, whereas `planner_prompt.py` (`INTEREST_TRANSLATIONS`) and the 3 planner scenario JSONs use short keys `["beach", "mountain", "culture", "food", "nature", "photography", "nightlife", "shopping"]`.
- **Preference Corpus Counts (`data/evaluation/synthetic/preferences_n300_seed42.json` & `data/research/preferences/synthetic_preferences_v1.jsonl`):**
  - Total records: `300`
  - Marked synthetic (`isSynthetic == true`): `300` (`100.00%`)
  - Independently verified real-user preference records: `0` (`0.00%`)
- **`PREFERENCE_GROUND_TRUTH_STATUS`:** `NO_REAL_USER_GT_AVAILABLE`
  Synthetic preference profiles may be used as controlled engineering/diagnostic fixtures only, never as empirical evidence of real-user satisfaction.

---

## 9. Audit of Model & Reproducibility Path

- **Provider:** Google Gemini via `google-genai` SDK (`genai.Client` in `apps/ai-service/app/routers/planner.py:24`).
- **Model Identifier:** `"gemini-3.5-flash"` (`settings.PLANNER_MODEL` in `apps/ai-service/app/config.py:10`).
- **Generation Parameters (`apps/ai-service/app/routers/planner.py:104-109`):**
  - `temperature`: `0.7`
  - `max_output_tokens`: `16384` (`settings.PLANNER_MAX_OUTPUT_TOKENS`)
  - `response_mime_type`: `"application/json"`
  - `http_options.timeout`: `55000` ms (`settings.PLANNER_TIMEOUT_MS`)
  - `top_p`: `None` (not set)
  - `seed`: `None` (not set)
- **Persistence & Manifest Status:**
  - Raw model output (`response.text`) persisted: `false` (processed only in memory).
  - Final structured output (`PlanResponse`) persisted by planner or evaluator: `false` (only persisted to PostgreSQL if an interactive user confirms bulk save via `POST /trips/:id/itinerary/bulk`).
  - Deterministic reproducibility manifest capturing model/provider/version, parameters, scenario hash, catalog hash, evaluator hash, raw output hash, and parsed output hash: `false` (none exists for W06).
- **No-API-Key / Error Fallback Behavior (`apps/ai-service/app/routers/planner.py:24, 123-150`):**
  - **Trigger Condition:** When `settings.GEMINI_API_KEY` is empty (`""`), `_client` is `None`. Calling `POST /planner` executes the `else:` branch (lines 123–150), which constructs a canned mock JSON itinerary with 1 activity per day (`"Tham quan điểm nổi bật {destination}"`, `place_name = destination`, `estimated_cost = 50000`, `transport_mode = "taxi"`) and returns `200 OK` using the exact same `PlanResponse` schema.
  - **Provider Error Behavior:** When `_client` is configured (`GEMINI_API_KEY` is non-empty) and the upstream API or JSON parsing fails, `create_plan` raises `HTTPException(status_code=502)` (it does not fall back to the mock on upstream errors).
  - **Distinguishing `REAL_MODEL_RUN` vs `MOCK_OR_FALLBACK_RUN`:** `PlanResponse` has **no** schema field (such as `execution_mode`, `is_mock`, or `model_id`) distinguishing a real Gemini generation from the no-API-key fallback mock.

---

## 10. Measurement Capability Matrix

| Capability Dimension | Status | Repository Evidence | Blocking Gap | Safe Interpretation |
| :--- | :---: | :--- | :--- | :--- |
| **`CATALOG_GROUNDING`** | `NOT_EVALUABLE` | `ItineraryItem` (`schemas/planner.py:29-38`) emits only free-text `place_name` (no `place_id`, `osm_id`, or coordinates); `TRAVEL_PLANNER_V1` receives no catalog POIs; 2/3 scenarios (`Hà Giang`, `Mộc Châu`) have 0 catalog POIs; `evaluate_planner.py` performs no catalog check. | No `place_id` in planner output schema, no catalog injection/retrieval in planner, no deterministic entity linker in evaluator, and out-of-scope scenarios. | Cannot currently measure whether planner outputs are grounded in `gomate_places_freeze_v2.json`. |
| **`NO_DUPLICATE_POI`** | `PARTIALLY_SUPPORTED` | `ItineraryItem` includes free-text `place_name`, permitting surface string-duplicate checks in principle, though `evaluate_planner.py` implements none and canonical `place_id` is absent. | Absence of canonical `place_id` prevents entity-level alias deduplication; evaluator lacks duplicate check. | Only surface string repetition of `place_name` can be inspected; canonical POI non-duplication is not verifiable without `place_id`. |
| **`DESTINATION_CORRECTNESS`** | `PARTIALLY_SUPPORTED` | `PlanResponse` echoes `destination` and `gomate_places_freeze_v2.json` labels 622 core POIs across `ha-noi`, `da-nang`, and `ha-long`. However, items lack `place_id`/coordinates and `evaluate_planner.py` checks neither destination field nor POI membership. | No `place_id` or coordinates on `ItineraryItem` to verify that each activity lies inside the requested destination. | Can only check top-level destination string echo or keyword mentions, not verified geographic containment of generated POIs. |
| **`CATEGORY_DIVERSITY`** | `NOT_EVALUABLE` | Catalog has 100% category coverage (`759/759`), but `ItineraryItem` has no `category` or `place_id` field, and `evaluate_planner.py` performs no category check. | Planner output items carry neither `category` nor `place_id` linking to catalog categories. | Intra-itinerary category diversity cannot be deterministically measured from current planner outputs. |
| **`GEO_DISTANCE`** | `NOT_EVALUABLE` | Catalog has 100% `latitude`/`longitude` coverage (`759/759`), supporting straight-line Haversine `GEO_DISTANCE_PROXY` between catalog POIs. However, `ItineraryItem` has no coordinates or `place_id`, and `evaluate_planner.py` computes no distances. | Generated itinerary items lack coordinates and canonical `place_id` linkage to catalog coordinates. | Even straight-line `GEO_DISTANCE_PROXY` cannot be computed on planner outputs until items are grounded to catalog `place_id`s. |
| **`TRAVEL_TIME`** | `NOT_EVALUABLE` | Zero road-network routing data, travel-time matrices, or routing engines exist in the repo. `calculate_route.py` divides straight-line Haversine distance by a constant `50 km/h`. | Complete absence of road-network routing/travel-time data and absence of POI coordinate grounding in outputs. | Real travel time and route quality cannot be measured. Straight-line Haversine distance must only ever be labeled `GEO_DISTANCE_PROXY`, never travel time. |
| **`OPENING_HOURS`** | `NOT_EVALUABLE` | Only `101/759` (`13.31%`) of all catalog POIs and `101/622` (`16.24%`) of core POIs have `opening_hours` strings; no OSM `opening_hours` parser exists in the repo; `ItineraryItem` is ungrounded; `evaluate_planner.py` performs no check. | 83.76% missing `opening_hours` in core catalog, no OSM `opening_hours` parser, and no `place_id` grounding on items. | Opening-hours compliance cannot be evaluated across the catalog (at best a sparse diagnostic on 16.24% of core POIs after grounding + parser implementation). |
| **`SCHEDULE_OVERLAP`** | `PARTIALLY_SUPPORTED` | `ItineraryItem` includes `start_time` and `end_time` strings (prompted as `HH:MM`), making intra-day chronological ordering and non-overlap structurally inspectable from output JSON, though `evaluate_planner.py` does not check them yet. | `evaluate_planner.py` does not parse or check `start_time`/`end_time` intervals, and schema types them as optional free text. | Internal schedule non-overlap is a structural self-consistency property measurable once interval parsing is added to the evaluator. |
| **`BUDGET`** | `PARTIALLY_SUPPORTED` | `planner.py` deterministically sums `item.estimated_cost` into `day_cost` and `budget_analysis.estimated_cost` and sets `is_over_budget`. `evaluate_planner.py` checks internal sum equality (`calculated_total == reported_total`) but ignores `expected_constraints.max_budget`. Catalog has 0% structured numeric price coverage (`0/759` `priceMin`/`priceMax`; `6/759` raw `charge` tags). | `evaluate_planner.py` does not check `calculated_total <= max_budget`, and catalog lacks numeric POI prices (`99.21%` missing) to verify LLM cost estimates against external reality. | Can measure internal arithmetic self-consistency and whether summed LLM cost estimates stay within the user's budget ceiling, but **not** real-world price accuracy. |
| **`PREFERENCE_SATISFACTION`** | `NOT_EVALUABLE` | All 300 preference records (`preferences_n300_seed42.json`) are synthetic (`isSynthetic = true`, 0 real users); planner interest keys (`beach`, `food`) differ from canonical taxonomy keys (`beach_island`, `food_cuisine`); `ItineraryItem` is ungrounded; `evaluate_planner.py` only logs `required_keywords` without failing. | `NO_REAL_USER_GT_AVAILABLE`, ungrounded output items, interest vocabulary mismatch, and non-enforcing evaluator keyword check. | Cannot claim empirical user preference satisfaction; only synthetic persona/keyword alignment diagnostics are possible. |
| **`REPRODUCIBILITY`** | `NOT_EVALUABLE` | `planner.py` calls `gemini-3.5-flash` with `temperature = 0.7` and no `seed`, persists neither raw LLM text nor parsed output JSON, and writes no cryptographic manifest of model/scenario/catalog/evaluator/output hashes. | Non-zero temperature (`0.7`) without seed, ephemeral unpersisted outputs, and no benchmark run manifest. | Live planner runs are stochastic and currently lack a reproducible artifact trail. |
| **`MOCK_RUN_DETECTION`** | `PARTIALLY_SUPPORTED` | When `GEMINI_API_KEY` is unset, `planner.py:123-150` silently returns a canned `200 OK` `PlanResponse` with the exact same schema as a real Gemini run and no provenance/mode field in `PlanResponse`. | `PlanResponse` lacks an explicit `execution_mode` / `is_mock` / `model_id` field, so saved JSON outputs do not self-identify mock vs live runs at the schema level. | Environment gating (`GEMINI_API_KEY` check) or heuristic string inspection can detect the fallback mock, but the output schema contract itself does not distinguish `REAL_MODEL_RUN` from `MOCK_OR_FALLBACK_RUN`. |

---

## 11. Current Instrument Validity Verdict

- **`CAN_CURRENT_EVALUATOR_PRODUCE_A_SCIENTIFIC_W06_PASS_RATE`:** **`NO`**
- **Evidence-Based Justification:**
  1. `data/evaluation/planner/evaluate_planner.py` enforces only three checks that can fail a run: `min_days <= len(days) <= max_days`, `len(items) >= min_items_per_day`, and internal arithmetic equality (`sum(item.estimated_cost) == day_cost` and `== budget_analysis.estimated_cost`), where the arithmetic sums are already deterministically computed from the same items by `apps/ai-service/app/routers/planner.py`.
  2. Its fourth check (`required_keywords`) unconditionally appends to `passed_checks` and never fails even when `0` keywords match.
  3. It does **not** enforce `max_budget`, and it performs **zero** checks for POI catalog grounding, `place_id` existence, duplicate POIs, destination containment, category diversity, opening hours, schedule overlap, geographic distance (`GEO_DISTANCE_PROXY`), preference satisfaction, or mock-run rejection.
  4. Two of the three existing scenario files (`ha_giang_3d.json`, `moc_chau_3d.json`) target destinations with `0` POIs in the frozen GoMate catalog (`gomate_places_freeze_v2.json`).
  5. Again, this conclusion reflects **current evaluator and schema instrumentation gaps**, not the quality of the underlying LLM or planner concept.
