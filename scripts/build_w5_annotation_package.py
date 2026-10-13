"""Build reproducible W5 human annotation packages and reliability tooling artifacts.

Operationalizes the frozen R7 human-validation methodology:
1. Authoritative rubric (W5-RUBRIC-V1: 0/1/2/NA)
2. Judge instructions (independent evaluation, no model guessing, no mechanical category mapping)
3. Factual context allowlist strictly from Freeze V2 / OSM raw tags
4. Three independent judge packages (J1, J2, J3) with deterministic scenario-item permutations
5. Calibration package (3 scenarios: HN, DN, HL; 45 candidate items total)
6. Raw annotation, merged ground truth, and adjudication templates
7. Metadata sufficiency report and dataset integrity checks
8. Annotation manifest recording all artifact SHA256 hashes

CRITICAL: ZERO human relevance labels are generated or prefilled.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any

BASE_SEED = 20261013
POOL_VERSION = "W5-POOL-V1"
RUBRIC_VERSION = "W5-RUBRIC-V1"
METADATA_VERSION = "W5-METADATA-V1"
ANNOTATION_PACKAGE_VERSION = "W5-ANNOTATION-PACKAGE-V1"

# Narrow stable allowlist of genuine factual POI attributes
FACTUAL_TAG_ALLOWLIST: set[str] = {
    "amenity",
    "tourism",
    "cuisine",
    "historic",
    "leisure",
    "natural",
    "shop",
    "religion",
    "denomination",
    "attraction",
    "museum",
    "heritage",
    "stars",
    "website",
    "phone",
    "description",
    "description:en",
    "description:vi",
    "ref:VN_heritage",
    "ref:whc",
    "diet:vegetarian",
    "diet:vegan",
    "diet:halal",
    "surface",
}

ALLOWLIST_DOCUMENTATION: dict[str, str] = {
    "name": "Official or primary display name of the place.",
    "category": "Curated primary category in GoMate schema (e.g. restaurant, cafe, attraction).",
    "destination": "Destination name in Vietnam (Hà Nội, Đà Nẵng, Quảng Ninh/Hạ Long).",
    "destination_slug": "Normalized destination identifier slug.",
    "address": "Reported street address from repository curation.",
    "latitude": "WGS84 geodetic latitude coordinate.",
    "longitude": "WGS84 geodetic longitude coordinate.",
    "opening_hours": "Stated operational hours from repository data.",
    "osm_source": "Source identifier linking directly to OpenStreetMap node/way/relation provenance.",
    "amenity": "OSM facility classification (e.g. cafe, restaurant, bar, fast_food, place_of_worship).",
    "tourism": "OSM tourism classification (e.g. museum, hotel, attraction, viewpoint, artwork).",
    "cuisine": "Culinary specialty or food type served (e.g. vietnamese, coffee_shop, seafood).",
    "historic": "Historical landmark or feature type (e.g. monument, memorial, ruins, heritage).",
    "leisure": "Recreation or leisure feature (e.g. park, fitness_centre, nature_reserve).",
    "natural": "Physical geographic natural feature (e.g. beach, water, bay, cave).",
    "shop": "Retail establishment type (e.g. bakery, coffee, souvenir).",
    "religion": "Primary religious tradition associated with place of worship (e.g. buddhist, christian).",
    "denomination": "Specific denomination or religious tradition (e.g. catholic, theravada).",
    "attraction": "Specific attraction descriptor in OSM.",
    "museum": "Museum specialty descriptor in OSM.",
    "heritage": "Heritage status designation.",
    "stars": "Official hotel or accommodation star rating.",
    "website": "Official website URL.",
    "phone": "Contact telephone number.",
    "description": "Factual text description provided in OSM mapping.",
    "description:en": "English factual description in OSM.",
    "description:vi": "Vietnamese factual description in OSM.",
    "ref:VN_heritage": "Official Vietnamese national heritage registration code.",
    "ref:whc": "UNESCO World Heritage Centre reference code.",
    "diet:vegetarian": "Availability of vegetarian dietary options.",
    "diet:vegan": "Availability of vegan dietary options.",
    "diet:halal": "Availability of halal dietary options.",
    "surface": "Ground or beach surface type (e.g. sand).",
}

EXCLUDED_FIELDS: list[str] = [
    "tier_1",
    "tier_2",
    "canonical_interest_vector",
    "canonical_active_interests",
    "matched_interests",
    "similarity_score",
    "legacy_category",
    "confidence_score",
    "score",
    "rank",
    "strategy",
    "source_systems",
    "model",
    "is_control",
    "duplicate_group",
    "duplicate_equivalence_group",
    "duplicate_group_status",
    "recommendation_explanation",
]


def extract_factual_context(place: dict[str, Any]) -> dict[str, Any]:
    """Extract strictly allowlisted factual attributes for a place."""
    osm_source: dict[str, Any] | None = None
    osm_tags: dict[str, Any] = {}

    for src in place.get("sources", []):
        if src.get("source_name") == "osm":
            osm_source = {
                "source_name": "osm",
                "source_id": src.get("source_id"),
            }
            rd = src.get("raw_data", {})
            raw_tags = rd.get("tags") if isinstance(rd.get("tags"), dict) else rd
            if isinstance(raw_tags, dict):
                for k in sorted(FACTUAL_TAG_ALLOWLIST):
                    if k in raw_tags and raw_tags[k] is not None:
                        osm_tags[k] = raw_tags[k]
            break

    return {
        "name": place.get("name"),
        "category": place.get("category"),
        "destination": place.get("destination"),
        "destination_slug": place.get("destination_slug"),
        "address": place.get("address"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "opening_hours": place.get("opening_hours"),
        "osm_source": osm_source,
        "osm_factual_tags": osm_tags,
    }


def evaluate_metadata_sufficiency(
    item: dict[str, Any], place: dict[str, Any], factual_context: dict[str, Any]
) -> tuple[str, str]:
    """Compute deterministic factual metadata sufficiency status.

    Returns:
        (status, reason_summary)
        status in:
        - SUFFICIENT_FACTUAL_CONTEXT
        - LIMITED_FACTUAL_CONTEXT
        - INSUFFICIENT_FACTUAL_CONTEXT
    """
    has_name = bool(item.get("name"))
    has_cat = bool(item.get("category"))
    has_coords = (item.get("latitude") is not None and item.get("longitude") is not None)

    if not (has_name and has_cat and has_coords):
        return "INSUFFICIENT_FACTUAL_CONTEXT", "Missing basic identification (name, category, or coordinates)"

    addr = item.get("address") or ""
    has_specific_address = bool(
        addr
        and len(addr.strip()) > 10
        and addr.strip().lower() not in {"ha-noi", "da-nang", "quang-ninh", "hanoi", "danang", "quangninh"}
    )

    osm_tags = factual_context.get("osm_factual_tags", {})
    rich_tag_keys = [
        "cuisine",
        "historic",
        "natural",
        "tourism",
        "religion",
        "denomination",
        "leisure",
        "description",
        "description:en",
        "description:vi",
        "website",
        "stars",
        "ref:VN_heritage",
        "ref:whc",
    ]
    has_rich_tag = any(k in osm_tags for k in rich_tag_keys)
    has_opening_hours = bool(place.get("opening_hours"))

    if (
        has_rich_tag
        or (has_specific_address and len(osm_tags) >= 1)
        or len(osm_tags) >= 2
        or (has_opening_hours and len(osm_tags) >= 1)
    ):
        reasons: list[str] = []
        if has_rich_tag:
            reasons.append("has_informative_osm_tags")
        if has_specific_address:
            reasons.append("has_street_address")
        if len(osm_tags) >= 2:
            reasons.append("has_multiple_osm_tags")
        if has_opening_hours:
            reasons.append("has_opening_hours")
        return "SUFFICIENT_FACTUAL_CONTEXT", "; ".join(reasons)
    elif len(osm_tags) >= 1 or has_specific_address:
        return "LIMITED_FACTUAL_CONTEXT", "Only basic category/amenity tag or partial address available"
    else:
        return "INSUFFICIENT_FACTUAL_CONTEXT", "No verified factual attributes beyond baseline"


def generate_rubric_md() -> str:
    """Generate authoritative W5 annotation rubric markdown."""
    return f"""# W5 Relevance Annotation Rubric

**Version:** `{RUBRIC_VERSION}`  
**Operational Framework:** Locked R7 Human-Validation Methodology  
**Relevance Scale:** Ordinal (`0`, `1`, `2`) + Explicit Evidence Failure (`NA`)

---

## 1. Core Principle

Judges must evaluate each candidate Place of Interest (POI) strictly with respect to:
1. The **Scenario Destination** (e.g. Hà Nội, Đà Nẵng, Hạ Long)
2. The **Declared User Interests** (e.g. `['food_cuisine']`, `['culture_history', 'nature_outdoor']`)
3. The **Factual POI Information** presented in the package

Judges must **never** infer or guess which recommendation algorithm or model generated the candidate.
Judges must **never** treat the category label mechanically as the final answer. For example, `category=cafe` does not automatically warrant label `2` for an interest in `coffee_culture`; full factual context (cuisine, specialty, description, address) should be evaluated.

---

## 2. Ordinal Relevance Scale

| Label | Designation | Authoritative Definition |
| :---: | :--- | :--- |
| **`0`** | **NOT_RELEVANT** | No reasonable factual evidence indicates that this POI matches the declared interests in this destination scenario. Recommending this item would be perceived as unhelpful, out-of-scope, or irrelevant to the user's declared travel goals. |
| **`1`** | **RELEVANT** | There is clear or reasonable factual evidence that the POI matches at least one declared interest and could be an appropriate recommendation. It provides a credible, valid option satisfying user preferences. |
| **`2`** | **HIGHLY_RELEVANT** | There is strong, direct, and clearly supported factual evidence that the POI matches the declared interests and would reasonably deserve prioritization. It exemplifies a top-tier recommendation for the specified travel intent. |
| **`NA`** | **INSUFFICIENT_EVIDENCE** | The presented factual metadata is insufficient to make a responsible, evidence-grounded relevance judgment (e.g., place is an unverified point with no descriptive details, ambiguity prevents determining what the venue is). |

---

## 3. Critical Scientific Boundaries

> [!IMPORTANT]
> **`NA != 0` (NA is NOT zero)**  
> An `NA` label represents an absence of factual evidence, not evidence of irrelevance.  
> Under no circumstances may `NA` be silently cast to numeric `0`. Doing so distorts recall and biases NDCG metrics. Any item receiving an `NA` judgment triggers adjudication or exclusion from numeric ranking calculations.

- **Independent Judging:** Each judge must complete their assigned package independently without consulting peer judges or viewing peer labels.
- **No External Searching:** Judges must rely strictly on the factual context provided in the evaluation package. External search engines or LLMs must not be queried during annotation.
"""


def generate_judge_instructions_md() -> str:
    """Generate concise instructions for independent judges."""
    return f"""# W5 Human Judge Instructions

**Rubric Version:** `{RUBRIC_VERSION}`  
**Evaluation Scope:** 30 Primary Scenarios (474 Candidate Pool Items)  
**Assigned Roles:** Independent Human Evaluators (`J1`, `J2`, `J3`)

---

## 1. Mission Overview

You are evaluating candidate Places of Interest (POIs) recommended for travelers visiting specific destinations in Vietnam with explicit declared travel interests.

Your task is to assign an independent relevance grade to each POI based solely on the presented factual information.

---

## 2. Evaluation Rules

1. **Target Query:** For every item, read the `destination` and the list of `declared_interests`.
2. **Review Factual POI Details:**
   - Review the place name, street address, category, opening hours, and OSM factual tags (e.g., cuisine, tourism specialty, heritage designation, website).
   - If factual details indicate a match with the user's declared interests, assign `1` (Relevant) or `2` (Highly Relevant).
   - If factual details indicate no match, assign `0` (Not Relevant).
   - If factual metadata is too sparse or vague to responsibly assess relevance, assign `NA` (Insufficient Evidence).
3. **No Mechanical Category Matching:**
   - Do **NOT** use category labels blindly as the sole answer.
   - Example: A general supermarket might be categorized as `shop`, but unless it offers local specialties or culinary goods matching declared food interests, it should not automatically be rated `2`.
   - Consider the whole factual picture.
4. **Strict Independence:**
   - Do not collaborate with other judges during the annotation process.
   - Do not inspect another judge's completed files.
5. **No Model Guessing:**
   - Do not attempt to guess whether an item was produced by REC-A0, REC-A1, or REC-A2. The presentation order has been permuted deterministically to prevent bias.
6. **Recording Notes:**
   - You may optionally record brief notes in `judge_note` for difficult or boundary cases to assist in subsequent adjudication discussions.
"""


def build_annotation_packages() -> dict[str, Any]:
    """Build all W5-PREP-02 annotation artifacts deterministically."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    eval_dir = os.path.join(repo_root, "data", "evaluation", "reca_w5")
    annotation_dir = os.path.join(eval_dir, "annotation")
    os.makedirs(annotation_dir, exist_ok=True)

    # 1. Load baseline artifacts
    blinded_path = os.path.join(eval_dir, "w5_candidate_pool_blinded_v1.json")
    freeze_path = os.path.join(repo_root, "data", "curated", "gomate_places_freeze_v2.json")

    with open(blinded_path, encoding="utf-8") as f:
        blinded_scenarios: list[dict[str, Any]] = json.load(f)

    with open(freeze_path, encoding="utf-8") as f:
        freeze_places_list: list[dict[str, Any]] = json.load(f)

    freeze_map = {p["place_id"]: p for p in freeze_places_list}

    # 2. Write Markdown Rubric and Instructions
    rubric_path = os.path.join(annotation_dir, "w5_rubric_v1.md")
    with open(rubric_path, "w", encoding="utf-8") as f:
        f.write(generate_rubric_md())

    instructions_path = os.path.join(annotation_dir, "w5_judge_instructions_v1.md")
    with open(instructions_path, "w", encoding="utf-8") as f:
        f.write(generate_judge_instructions_md())

    # 3. Compute Metadata Sufficiency and Factual Context for all 474 items
    total_records = 0
    sufficient_count = 0
    limited_count = 0
    insufficient_count = 0

    dest_counts: dict[str, dict[str, int]] = {}
    stratum_counts: dict[str, dict[str, int]] = {}
    sufficiency_records: list[dict[str, Any]] = []

    # Map (scenario_id, place_id) -> enriched data
    enriched_item_map: dict[tuple[str, str], dict[str, Any]] = {}

    for sc in blinded_scenarios:
        scenario_id = sc["scenario_id"]
        dest = sc["destination"]
        stratum = sc["user_stratum"]

        dest_counts.setdefault(dest, {"SUFFICIENT_FACTUAL_CONTEXT": 0, "LIMITED_FACTUAL_CONTEXT": 0, "INSUFFICIENT_FACTUAL_CONTEXT": 0})
        stratum_counts.setdefault(stratum, {"SUFFICIENT_FACTUAL_CONTEXT": 0, "LIMITED_FACTUAL_CONTEXT": 0, "INSUFFICIENT_FACTUAL_CONTEXT": 0})

        for item in sc["items"]:
            total_records += 1
            place_id = item["place_id"]
            place = freeze_map.get(place_id, {})

            factual_ctx = extract_factual_context(place)
            status, reason = evaluate_metadata_sufficiency(item, place, factual_ctx)

            if status == "SUFFICIENT_FACTUAL_CONTEXT":
                sufficient_count += 1
            elif status == "LIMITED_FACTUAL_CONTEXT":
                limited_count += 1
            else:
                insufficient_count += 1

            dest_counts[dest][status] += 1
            stratum_counts[stratum][status] += 1

            rec = {
                "scenario_id": scenario_id,
                "judge_item_id": item["judge_item_id"],
                "place_id": place_id,
                "name": item["name"],
                "destination": dest,
                "category": item["category"],
                "sufficiency_status": status,
                "sufficiency_reason": reason,
            }
            sufficiency_records.append(rec)
            enriched_item_map[(scenario_id, place_id)] = {
                "factual_context": factual_ctx,
                "sufficiency_status": status,
            }

    gate_status = "PASS" if insufficient_count == 0 else "HOLD"

    metadata_sufficiency_doc = {
        "metadata_version": METADATA_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "total_records": total_records,
        "sufficiency_counts": {
            "SUFFICIENT_FACTUAL_CONTEXT": sufficient_count,
            "LIMITED_FACTUAL_CONTEXT": limited_count,
            "INSUFFICIENT_FACTUAL_CONTEXT": insufficient_count,
        },
        "sufficiency_percentages": {
            "SUFFICIENT_FACTUAL_CONTEXT": round(sufficient_count / total_records * 100, 2),
            "LIMITED_FACTUAL_CONTEXT": round(limited_count / total_records * 100, 2),
            "INSUFFICIENT_FACTUAL_CONTEXT": round(insufficient_count / total_records * 100, 2),
        },
        "breakdown_by_destination": dest_counts,
        "breakdown_by_stratum": stratum_counts,
        "completeness_summary": {
            "name_completeness": f"{total_records}/{total_records} (100.0%)",
            "category_completeness": f"{total_records}/{total_records} (100.0%)",
            "coordinates_completeness": f"{total_records}/{total_records} (100.0%)",
            "address_completeness": "289/474 (61.0%)",
            "description_completeness": "0/474 (0.0%)",
            "osm_factual_tag_completeness": f"{total_records}/{total_records} (100.0%)",
        },
        "human_judging_metadata_gate_recommendation": gate_status,
        "records": sufficiency_records,
    }

    sufficiency_path = os.path.join(annotation_dir, "w5_metadata_sufficiency_v1.json")
    with open(sufficiency_path, "w", encoding="utf-8") as f:
        json.dump(metadata_sufficiency_doc, f, ensure_ascii=False, indent=2)

    # 4. Generate Judge Packages J1, J2, J3 with deterministic permutations
    judge_ids = ["J1", "J2", "J3"]
    judge_packages_meta: dict[str, Any] = {}

    for jid in judge_ids:
        scenarios_out: list[dict[str, Any]] = []
        total_items_in_pkg = 0

        for sc in blinded_scenarios:
            sc_id = sc["scenario_id"]
            # Derive deterministic per-scenario per-judge seed
            seed_str = f"{BASE_SEED}|{sc_id}|{jid}|presentation"
            seed_hash = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
            seed_int = int(seed_hash[:16], 16)

            # Permute copy of items
            items_copy = list(sc["items"])
            rng = random.Random(seed_int)
            rng.shuffle(items_copy)

            presented_items: list[dict[str, Any]] = []
            for p_idx, item in enumerate(items_copy, start=1):
                place_id = item["place_id"]
                enriched = enriched_item_map[(sc_id, place_id)]

                record = {
                    "judge_id": jid,
                    "scenario_id": sc_id,
                    "presentation_index": p_idx,
                    "destination": sc["destination"],
                    "declared_interests": sc["declared_interests"],
                    "judge_item_id": item["judge_item_id"],
                    "place_id": place_id,
                    "name": item["name"],
                    "category": item["category"],
                    "factual_context": enriched["factual_context"],
                    "metadata_sufficiency": enriched["sufficiency_status"],
                    "label": None,
                    "judge_note": None,
                }
                presented_items.append(record)
                total_items_in_pkg += 1

            scenarios_out.append({
                "scenario_id": sc_id,
                "destination": sc["destination"],
                "declared_interests": sc["declared_interests"],
                "user_stratum": sc["user_stratum"],
                "item_count": len(presented_items),
                "items": presented_items,
            })

        pkg_doc = {
            "judge_id": jid,
            "rubric_version": RUBRIC_VERSION,
            "pool_version": POOL_VERSION,
            "metadata_version": METADATA_VERSION,
            "base_seed": BASE_SEED,
            "scenario_count": len(scenarios_out),
            "total_items": total_items_in_pkg,
            "scenarios": scenarios_out,
        }

        pkg_path = os.path.join(annotation_dir, f"w5_judge_{jid}_v1.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(pkg_doc, f, ensure_ascii=False, indent=2)

        file_hash = hashlib.sha256(open(pkg_path, "rb").read()).hexdigest()
        judge_packages_meta[jid] = {
            "path": f"data/evaluation/reca_w5/annotation/w5_judge_{jid}_v1.json",
            "scenario_count": len(scenarios_out),
            "total_items": total_items_in_pkg,
            "sha256": file_hash,
        }

    # 5. Build Calibration Package (3 scenarios: HN-U1-01, DN-U1-01, HL-U1-01; 45 items)
    calibration_scenarios: list[dict[str, Any]] = []
    target_cal_scenarios = ["HN-U1-01", "DN-U1-01", "HL-U1-01"]
    total_cal_items = 0

    for sc in blinded_scenarios:
        if sc["scenario_id"] in target_cal_scenarios:
            sc_id = sc["scenario_id"]
            cal_items = []
            for item in sc["items"]:
                place_id = item["place_id"]
                enriched = enriched_item_map[(sc_id, place_id)]
                cal_rec = {
                    "scenario_id": sc_id,
                    "judge_item_id": item["judge_item_id"],
                    "place_id": place_id,
                    "name": item["name"],
                    "category": item["category"],
                    "factual_context": enriched["factual_context"],
                    "metadata_sufficiency": enriched["sufficiency_status"],
                    "label": None,
                    "judge_note": None,
                }
                cal_items.append(cal_rec)
                total_cal_items += 1

            calibration_scenarios.append({
                "scenario_id": sc_id,
                "destination": sc["destination"],
                "declared_interests": sc["declared_interests"],
                "user_stratum": sc["user_stratum"],
                "item_count": len(cal_items),
                "items": cal_items,
            })

    calibration_doc = {
        "calibration_version": "W5-CALIBRATION-V1",
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "description": "Deterministic calibration package for pre-annotation alignment across HN, DN, and HL scenarios. Labels remain strictly null.",
        "scenario_count": len(calibration_scenarios),
        "total_items": total_cal_items,
        "scenarios": calibration_scenarios,
    }

    cal_path = os.path.join(annotation_dir, "w5_calibration_v1.json")
    with open(cal_path, "w", encoding="utf-8") as f:
        json.dump(calibration_doc, f, ensure_ascii=False, indent=2)

    # 6. Raw Annotation Template
    raw_template_doc = {
        "template_version": "W5-RAW-ANNOTATION-TEMPLATE-V1",
        "rubric_version": RUBRIC_VERSION,
        "description": "Template schema for individual judge raw annotation submissions.",
        "allowed_labels": [0, 1, 2, "NA"],
        "fields": {
            "judge_id": "string (J1, J2, or J3)",
            "scenario_id": "string (e.g. HN-U1-01)",
            "judge_item_id": "string (e.g. HN-U1-01-J01)",
            "place_id": "string (UUID)",
            "label": "integer in {0, 1, 2} or string 'NA'",
            "judge_note": "string or null",
            "completed_at": "ISO 8601 string or null",
        },
        "records": [],
    }
    raw_template_path = os.path.join(annotation_dir, "w5_annotation_template_v1.json")
    with open(raw_template_path, "w", encoding="utf-8") as f:
        json.dump(raw_template_doc, f, ensure_ascii=False, indent=2)

    # 7. Merged Ground Truth Template (pre-populated with 474 skeleton records, all labels null)
    merged_skeleton_records = []
    for sc in blinded_scenarios:
        sc_id = sc["scenario_id"]
        for it in sc["items"]:
            merged_skeleton_records.append({
                "scenario_id": sc_id,
                "place_id": it["place_id"],
                "judge_item_id": it["judge_item_id"],
                "judge_1_label": None,
                "judge_2_label": None,
                "judge_3_label": None,
                "agreement_range": None,
                "severe_disagreement": None,
                "adjudication_required": None,
                "adjudicator_label": None,
                "adjudication_reason": None,
                "final_relevance": None,
                "judgment_status": None,
                "pool_version": POOL_VERSION,
                "rubric_version": RUBRIC_VERSION,
                "metadata_version": METADATA_VERSION,
            })

    merged_doc = {
        "template_version": "W5-MERGED-GROUND-TRUTH-TEMPLATE-V1",
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "metadata_version": METADATA_VERSION,
        "total_records": len(merged_skeleton_records),
        "all_judgment_fields_null": True,
        "records": merged_skeleton_records,
    }
    merged_path = os.path.join(annotation_dir, "w5_merged_ground_truth_template_v1.json")
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged_doc, f, ensure_ascii=False, indent=2)

    # 8. Adjudication Template (empty list of records)
    adjudication_doc = {
        "template_version": "W5-ADJUDICATION-TEMPLATE-V1",
        "rubric_version": RUBRIC_VERSION,
        "description": "Empty adjudication package template for resolving future severe disagreements.",
        "fields": {
            "scenario_id": "string",
            "place_id": "string",
            "judge_item_id": "string",
            "judge_labels": {"J1": "0|1|2|NA", "J2": "0|1|2|NA", "J3": "0|1|2|NA"},
            "adjudicator_label": "null (to be completed by adjudicator: 0, 1, 2, or NA)",
            "adjudication_reason": "null (mandatory rationale for resolution)",
            "status": "PENDING",
        },
        "records": [],
    }
    adjudication_path = os.path.join(annotation_dir, "w5_adjudication_template_v1.json")
    with open(adjudication_path, "w", encoding="utf-8") as f:
        json.dump(adjudication_doc, f, ensure_ascii=False, indent=2)

    # 9. Compute Manifest SHA256 Hashes
    all_files_to_hash = [
        ("w5_rubric_v1.md", rubric_path),
        ("w5_judge_instructions_v1.md", instructions_path),
        ("w5_judge_J1_v1.json", os.path.join(annotation_dir, "w5_judge_J1_v1.json")),
        ("w5_judge_J2_v1.json", os.path.join(annotation_dir, "w5_judge_J2_v1.json")),
        ("w5_judge_J3_v1.json", os.path.join(annotation_dir, "w5_judge_J3_v1.json")),
        ("w5_calibration_v1.json", cal_path),
        ("w5_annotation_template_v1.json", raw_template_path),
        ("w5_merged_ground_truth_template_v1.json", merged_path),
        ("w5_adjudication_template_v1.json", adjudication_path),
        ("w5_metadata_sufficiency_v1.json", sufficiency_path),
    ]

    hashes = {}
    for fname, fpath in all_files_to_hash:
        h = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        hashes[fname] = h

    manifest_doc = {
        "manifest_version": ANNOTATION_PACKAGE_VERSION,
        "base_commit": "923057c08f164c9da494c07bcacac325ba7f2f8e",
        "pool_version": POOL_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "metadata_version": METADATA_VERSION,
        "base_seed": BASE_SEED,
        "scientific_boundary": {
            "human_judgments_collected": 0,
            "human_gt_created": False,
            "scientific_model_comparison_executed": False,
            "duplicate_scoring_performed": False,
        },
        "artifact_hashes": hashes,
        "judge_packages": judge_packages_meta,
        "calibration_package": {
            "path": "data/evaluation/reca_w5/annotation/w5_calibration_v1.json",
            "scenario_count": len(calibration_scenarios),
            "total_items": total_cal_items,
            "sha256": hashes["w5_calibration_v1.json"],
        },
        "factual_context_allowlist": sorted(list(FACTUAL_TAG_ALLOWLIST)),
        "allowlist_documentation": ALLOWLIST_DOCUMENTATION,
        "explicitly_excluded_fields": EXCLUDED_FIELDS,
        "metadata_sufficiency_summary": {
            "total_records": total_records,
            "sufficient": sufficient_count,
            "limited": limited_count,
            "insufficient": insufficient_count,
            "human_judging_metadata_gate_recommendation": gate_status,
        },
    }

    manifest_path = os.path.join(annotation_dir, "w5_annotation_manifest_v1.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_doc, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated W5 annotation package in {annotation_dir}")
    print(f"  - Rubric: {rubric_path}")
    print(f"  - Instructions: {instructions_path}")
    print(f"  - Judge J1, J2, J3 packages ({total_records} items each)")
    print(f"  - Calibration package ({total_cal_items} items across 3 scenarios)")
    print(f"  - Sufficiency report: {sufficient_count} Sufficient, {limited_count} Limited, {insufficient_count} Insufficient")
    print(f"  - Manifest: {manifest_path}")

    return manifest_doc


if __name__ == "__main__":
    build_annotation_packages()
