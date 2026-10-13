"""W5 Evaluation Scenario Manifest and Candidate Pool Builder.

Deterministic builder for W5 Evaluation Preparation:
- 30 Primary Scenarios (15 U1 + 15 U2 across Hanoi, Da Nang, Ha Long)
- 6 THIN Diagnostic Scenarios (diagnostic only, excluded from primary)
- Internal Provenance Candidate Pool
- Blinded Human-Judgment Candidate Pool (structural blinding, no model leakage)
- Reproducibility Manifest (stable SHA256 checksums)

Seed: W5_CONTROL_SEED = 20261013
Authoritative Catalog: Freeze V2 (622 REC-A Core POIs)
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure ai-service is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from recommendation.reca.contract import (  # noqa: E402
    CANONICAL_INTERESTS,
    poi_to_canonical_vector,
)
from recommendation.reca.engine import PlaceRecommender  # noqa: E402

# Configuration Constants
W5_CONTROL_SEED = 20261013
DATASET_FREEZE_V2_RELPATH = "data/curated/gomate_places_freeze_v2.json"
FREEZE_V2_EXPECTED_SHA256 = "93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245"
EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"

PRIMARY_SCENARIOS_RELPATH = "data/evaluation/reca_w5/w5_primary_scenarios_v1.json"
THIN_SCENARIOS_RELPATH = "data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json"
INTERNAL_POOL_RELPATH = "data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json"
BLINDED_POOL_RELPATH = "data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json"
REPRODUCIBILITY_MANIFEST_RELPATH = "data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json"

# Known R6/A6 duplicate equivalence pairs intersecting REC-A core
REC_A_CORE_DUPLICATE_MAP = {
    "6db09251-706a-4225-8ee5-4d22165f6b3f": "DUP-CORE-DN-01",
    "408aaa5a-7e34-41eb-b39f-acfa4393fc5f": "DUP-CORE-DN-01",
    "098e6a53-5ce5-4d20-b75e-4a00d00bb8cf": "DUP-CORE-DN-02",
    "83d8e5c4-b91e-415e-9fd6-fd2a887cb4c0": "DUP-CORE-DN-02",
    "13317b2d-7b15-40e5-8a3d-63c80425ae8e": "DUP-CORE-HL-01",
    "0118b23e-ed95-4fc4-b26a-74b761e3eb6f": "DUP-CORE-HL-01",
}

# Frozen Primary Scenarios Specification
# 15 U1: All destination x interest pairs with >= 10 I0 POIs
PRIMARY_U1_SPECS: List[Tuple[str, str, List[str]]] = [
    # Hanoi (4)
    ("HN-U1-01", "ha-noi", ["food_cuisine"]),
    ("HN-U1-02", "ha-noi", ["culture_history"]),
    ("HN-U1-03", "ha-noi", ["nature_outdoor"]),
    ("HN-U1-04", "ha-noi", ["nightlife_entertainment"]),
    # Da Nang (6)
    ("DN-U1-01", "da-nang", ["food_cuisine"]),
    ("DN-U1-02", "da-nang", ["culture_history"]),
    ("DN-U1-03", "da-nang", ["coffee_culture"]),
    ("DN-U1-04", "da-nang", ["beach_island"]),
    ("DN-U1-05", "da-nang", ["shopping_local"]),
    ("DN-U1-06", "da-nang", ["nightlife_entertainment"]),
    # Ha Long (5)
    ("HL-U1-01", "ha-long", ["food_cuisine"]),
    ("HL-U1-02", "ha-long", ["culture_history"]),
    ("HL-U1-03", "ha-long", ["nature_outdoor"]),
    ("HL-U1-04", "ha-long", ["coffee_culture"]),
    ("HL-U1-05", "ha-long", ["shopping_local"]),
]

# 15 U2: Exact frozen combinations from R6 experimental design
PRIMARY_U2_SPECS: List[Tuple[str, str, List[str]]] = [
    # Hanoi (5)
    ("HN-U2-01", "ha-noi", ["food_cuisine", "culture_history"]),
    ("HN-U2-02", "ha-noi", ["nature_outdoor", "nightlife_entertainment"]),
    ("HN-U2-03", "ha-noi", ["food_cuisine", "nature_outdoor"]),
    ("HN-U2-04", "ha-noi", ["culture_history", "nature_outdoor", "nightlife_entertainment"]),
    ("HN-U2-05", "ha-noi", ["food_cuisine", "culture_history", "nightlife_entertainment"]),
    # Da Nang (5)
    ("DN-U2-01", "da-nang", ["food_cuisine", "culture_history"]),
    ("DN-U2-02", "da-nang", ["coffee_culture", "beach_island"]),
    ("DN-U2-03", "da-nang", ["shopping_local", "nightlife_entertainment"]),
    ("DN-U2-04", "da-nang", ["food_cuisine", "coffee_culture", "shopping_local"]),
    ("DN-U2-05", "da-nang", ["culture_history", "beach_island", "nightlife_entertainment"]),
    # Ha Long (5)
    ("HL-U2-01", "ha-long", ["food_cuisine", "culture_history"]),
    ("HL-U2-02", "ha-long", ["nature_outdoor", "coffee_culture"]),
    ("HL-U2-03", "ha-long", ["shopping_local", "food_cuisine"]),
    ("HL-U2-04", "ha-long", ["culture_history", "nature_outdoor", "shopping_local"]),
    ("HL-U2-05", "ha-long", ["food_cuisine", "coffee_culture", "shopping_local"]),
]

# 6 THIN Diagnostic Scenarios (I0 count 1..9)
THIN_SCENARIO_SPECS: List[Tuple[str, str, List[str], int]] = [
    ("HN-THIN-01", "ha-noi", ["coffee_culture"], 8),
    ("HN-THIN-02", "ha-noi", ["beach_island"], 1),
    ("HN-THIN-03", "ha-noi", ["shopping_local"], 3),
    ("DN-THIN-01", "da-nang", ["nature_outdoor"], 8),
    ("HL-THIN-01", "ha-long", ["beach_island"], 3),
    ("HL-THIN-02", "ha-long", ["nightlife_entertainment"], 5),
]


def sha256_file(path: Path) -> str:
    """Compute standard SHA256 hex digest of file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def derive_scenario_seed(base_seed: int, scenario_id: str, salt: str = "") -> int:
    """Derive deterministic 64-bit integer seed from base seed, scenario ID and optional salt."""
    key = f"{base_seed}|{scenario_id}|{salt}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest()[:16], 16)


def build_primary_scenarios() -> List[Dict[str, Any]]:
    """Build list of 30 primary scenarios."""
    scenarios: List[Dict[str, Any]] = []

    for scn_id, dest, interests in PRIMARY_U1_SPECS:
        scenarios.append({
            "scenario_id": scn_id,
            "scenario_version": "W5-SCENARIO-V1",
            "track": "CS-PERSONALIZED",
            "user_stratum": "U1",
            "destination": dest,
            "declared_interests": interests,
            "top_k": 10,
            "candidate_catalog": f"REC-A-CORE-V2:{dest}",
        })

    for scn_id, dest, interests in PRIMARY_U2_SPECS:
        scenarios.append({
            "scenario_id": scn_id,
            "scenario_version": "W5-SCENARIO-V1",
            "track": "CS-PERSONALIZED",
            "user_stratum": "U2",
            "destination": dest,
            "declared_interests": interests,
            "top_k": 10,
            "candidate_catalog": f"REC-A-CORE-V2:{dest}",
        })

    return scenarios


def build_thin_diagnostic_scenarios() -> List[Dict[str, Any]]:
    """Build list of 6 THIN diagnostic scenarios."""
    scenarios: List[Dict[str, Any]] = []
    for scn_id, dest, interests, cnt in THIN_SCENARIO_SPECS:
        scenarios.append({
            "scenario_id": scn_id,
            "scenario_version": "W5-SCENARIO-V1",
            "track": "THIN_DIAGNOSTIC",
            "user_stratum": "U1",
            "destination": dest,
            "declared_interests": interests,
            "top_k": 10,
            "candidate_catalog": f"REC-A-CORE-V2:{dest}",
            "i0_inventory_count": cnt,
        })
    return scenarios


def build_pools(
    recommender: PlaceRecommender,
    primary_scenarios: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build internal provenance pool and blinded human-judgment pool for all primary scenarios."""
    # Pre-index core places by place_id and by destination with I0/I1 stratum
    core_by_id: Dict[str, Dict[str, Any]] = {p["place_id"]: p for p in recommender.core_places}
    core_by_dest: Dict[str, List[Tuple[str, bool]]] = {}

    for p in recommender.core_places:
        dest = p["destination_slug"]
        vec = recommender.poi_vectors[p["place_id"]]
        is_i0 = any(v > 0 for v in vec)
        core_by_dest.setdefault(dest, []).append((p["place_id"], is_i0))

    internal_scenarios: List[Dict[str, Any]] = []
    blinded_scenarios: List[Dict[str, Any]] = []

    for scn in primary_scenarios:
        scn_id = scn["scenario_id"]
        dest = scn["destination"]
        interests = scn["declared_interests"]
        top_k = scn["top_k"]

        # 1. Run Shared Effective Baseline (rec-a1)
        res_baseline = recommender.recommend(
            preferences=interests, destination=dest, top_k=top_k, model="rec-a1"
        )
        baseline_items = res_baseline["recommendations"]

        # 2. Run REC-A2 Diversity Reranker
        res_a2 = recommender.recommend(
            preferences=interests, destination=dest, top_k=top_k, model="rec-a2"
        )
        a2_items = res_a2["recommendations"]

        baseline_ids = [item["place_id"] for item in baseline_items]
        a2_ids = [item["place_id"] for item in a2_items]
        model_union_ids = set(baseline_ids) | set(a2_ids)

        baseline_map = {item["place_id"]: item for item in baseline_items}
        a2_map = {item["place_id"]: item for item in a2_items}

        # 3. Deterministic Controls Selection (target: 3 I0, 2 I1)
        eligible_i0 = [
            pid for pid, is_i0 in core_by_dest[dest] if is_i0 and pid not in model_union_ids
        ]
        eligible_i1 = [
            pid for pid, is_i0 in core_by_dest[dest] if (not is_i0) and pid not in model_union_ids
        ]
        # Sort candidates deterministically before sampling
        eligible_i0.sort()
        eligible_i1.sort()

        if len(eligible_i0) + len(eligible_i1) < 5:
            raise RuntimeError(f"CONTROL_POOL_INSUFFICIENT for scenario {scn_id}")

        control_seed_int = derive_scenario_seed(W5_CONTROL_SEED, scn_id)
        ctrl_rng = random.Random(control_seed_int)

        target_i0_count = min(3, len(eligible_i0))
        target_i1_count = min(2, len(eligible_i1))
        remaining_needed = 5 - (target_i0_count + target_i1_count)

        if remaining_needed > 0:
            if len(eligible_i0) > target_i0_count:
                extra = min(remaining_needed, len(eligible_i0) - target_i0_count)
                target_i0_count += extra
                remaining_needed -= extra
            if remaining_needed > 0 and len(eligible_i1) > target_i1_count:
                extra = min(remaining_needed, len(eligible_i1) - target_i1_count)
                target_i1_count += extra
                remaining_needed -= extra

        selected_ctrl_i0 = ctrl_rng.sample(eligible_i0, target_i0_count)
        selected_ctrl_i1 = ctrl_rng.sample(eligible_i1, target_i1_count)
        selected_controls = selected_ctrl_i0 + selected_ctrl_i1

        # 4. Form Unique Candidate Pool (place_id deduplication)
        all_unique_place_ids = list(model_union_ids | set(selected_controls))
        # Sort by place_id for total cross-platform determinism before blind shuffling
        all_unique_place_ids.sort()

        # 5. Deterministic Blind Shuffling
        blind_seed_int = derive_scenario_seed(W5_CONTROL_SEED, scn_id, "blind")
        blind_rng = random.Random(blind_seed_int)
        shuffled_place_ids = list(all_unique_place_ids)
        blind_rng.shuffle(shuffled_place_ids)

        # Map place_id -> judge_item_id
        place_to_judge_id = {
            pid: f"{scn_id}-J{idx + 1:02d}" for idx, pid in enumerate(shuffled_place_ids)
        }

        # 6. Build Internal Provenance Records
        internal_items = []
        for pid in shuffled_place_ids:
            raw_place = core_by_id[pid]
            in_base = pid in baseline_map
            in_a2 = pid in a2_map
            is_ctrl = pid in selected_controls

            source_systems: List[str] = []
            if in_base:
                source_systems.append("shared_a0_a1_baseline")
            if in_a2:
                source_systems.append("rec-a2")
            if is_ctrl:
                source_systems.append("control")

            vec = recommender.poi_vectors[pid]
            is_i0 = any(v > 0 for v in vec)
            active_interests = [
                CANONICAL_INTERESTS[idx] for idx, v in enumerate(vec) if v > 0
            ]

            dup_group = REC_A_CORE_DUPLICATE_MAP.get(pid)

            internal_items.append({
                "scenario_id": scn_id,
                "judge_item_id": place_to_judge_id[pid],
                "place_id": pid,
                "name": raw_place["name"],
                "destination": dest,
                "source_systems": source_systems,
                "baseline_rank": baseline_map[pid]["rank"] if in_base else None,
                "a2_rank": a2_map[pid]["rank"] if in_a2 else None,
                "baseline_score": baseline_map[pid]["score"] if in_base else None,
                "a2_base_score": a2_map[pid]["score"] if in_a2 else None,
                "is_control": is_ctrl,
                "i0_i1_stratum": "I0" if is_i0 else "I1",
                "category": raw_place.get("category"),
                "canonical_active_interests": active_interests,
                "duplicate_equivalence_group": dup_group,
                "duplicate_group_status": "JOINED_R6_A6_EVIDENCE" if dup_group else "PENDING_EXISTING_A6_EVIDENCE_JOIN",
            })

        # 7. Build Blinded Human-Judgment Records (NO model leakage)
        blinded_items = []
        for pid in shuffled_place_ids:
            raw_place = core_by_id[pid]
            # Sanitize sources: keep only factual provenance keys (source_name, source_id)
            cleaned_sources = [
                {
                    "source_name": s.get("source_name"),
                    "source_id": s.get("source_id"),
                }
                for s in raw_place.get("sources", [])
            ]

            blinded_items.append({
                "scenario_id": scn_id,
                "destination": dest,
                "declared_interests": interests,
                "judge_item_id": place_to_judge_id[pid],
                "place_id": pid,
                "name": raw_place["name"],
                "category": raw_place.get("category"),
                "description": raw_place.get("description"),
                "address": raw_place.get("address"),
                "latitude": raw_place.get("latitude"),
                "longitude": raw_place.get("longitude"),
                "sources": cleaned_sources,
                "metadata_completeness": {
                    "has_description": bool(raw_place.get("description")),
                    "has_address": bool(raw_place.get("address")),
                    "has_coordinates": raw_place.get("latitude") is not None and raw_place.get("longitude") is not None,
                    "has_sources": bool(cleaned_sources),
                },
            })

        # Record scenario-level internal statistics
        baseline_a2_overlap = len(set(baseline_ids) & set(a2_ids))
        internal_scenarios.append({
            "scenario_id": scn_id,
            "scenario_version": scn["scenario_version"],
            "track": scn["track"],
            "user_stratum": scn["user_stratum"],
            "destination": dest,
            "declared_interests": interests,
            "top_k": top_k,
            "candidate_catalog": scn["candidate_catalog"],
            "baseline_count": len(baseline_ids),
            "a2_count": len(a2_ids),
            "baseline_a2_overlap": baseline_a2_overlap,
            "control_count": len(selected_controls),
            "final_unique_pool_count": len(all_unique_place_ids),
            "control_composition": {
                "i0": len(selected_ctrl_i0),
                "i1": len(selected_ctrl_i1),
            },
            "items": internal_items,
        })

        blinded_scenarios.append({
            "scenario_id": scn_id,
            "destination": dest,
            "declared_interests": interests,
            "track": scn["track"],
            "user_stratum": scn["user_stratum"],
            "final_unique_pool_count": len(all_unique_place_ids),
            "items": blinded_items,
        })

    return internal_scenarios, blinded_scenarios


def build_and_save_artifacts() -> Dict[str, str]:
    """Execute complete generation and save all 5 artifacts deterministically."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Initialize Recommender on Freeze V2
    dataset_path = REPO_ROOT / DATASET_FREEZE_V2_RELPATH
    assert dataset_path.exists(), f"Missing dataset: {dataset_path}"
    recommender = PlaceRecommender(places_source=dataset_path)

    # Invariant assertions
    assert len(recommender.core_places) == 622, f"Expected 622 core places, got {len(recommender.core_places)}"
    assert len(recommender.secondary_places) == 137, f"Expected 137 secondary places, got {len(recommender.secondary_places)}"

    # 2. Build Primary Scenarios
    primary_scenarios = build_primary_scenarios()
    assert len(primary_scenarios) == 30, f"Expected 30 primary scenarios, got {len(primary_scenarios)}"

    primary_path = REPO_ROOT / PRIMARY_SCENARIOS_RELPATH
    with open(primary_path, "w", encoding="utf-8") as f:
        json.dump(primary_scenarios, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 3. Build THIN Diagnostic Scenarios
    thin_scenarios = build_thin_diagnostic_scenarios()
    assert len(thin_scenarios) == 6, f"Expected 6 thin scenarios, got {len(thin_scenarios)}"

    thin_path = REPO_ROOT / THIN_SCENARIOS_RELPATH
    with open(thin_path, "w", encoding="utf-8") as f:
        json.dump(thin_scenarios, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 4. Build Candidate Pools
    internal_pool, blinded_pool = build_pools(recommender, primary_scenarios)
    assert len(internal_pool) == 30
    assert len(blinded_pool) == 30

    internal_path = REPO_ROOT / INTERNAL_POOL_RELPATH
    with open(internal_path, "w", encoding="utf-8") as f:
        json.dump(internal_pool, f, indent=2, ensure_ascii=False)
        f.write("\n")

    blinded_path = REPO_ROOT / BLINDED_POOL_RELPATH
    with open(blinded_path, "w", encoding="utf-8") as f:
        json.dump(blinded_pool, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 5. Compute Artifact Hashes and Save Reproducibility Manifest
    primary_hash = sha256_file(primary_path)
    thin_hash = sha256_file(thin_path)
    internal_hash = sha256_file(internal_path)
    blinded_hash = sha256_file(blinded_path)

    reproducibility_manifest = {
        "artifact_version": "W5-REPRODUCIBILITY-MANIFEST-V1",
        "generated_from_git_sha": "a01a7285ed7ac2282615129f85b184ee84941e0b",
        "freeze_id": "REC-A-FREEZE-V2",
        "freeze_checksum": FREEZE_V2_EXPECTED_SHA256,
        "primary_scenario_manifest_sha256": primary_hash,
        "thin_diagnostic_manifest_sha256": thin_hash,
        "internal_pool_sha256": internal_hash,
        "blinded_pool_sha256": blinded_hash,
        "pool_builder_version": "w5-pool-builder-v1",
        "control_seed": W5_CONTROL_SEED,
        "control_seed_method": "sha256(f'{control_seed}|{scenario_id}') -> int64",
        "blind_order_seed_method": "sha256(f'{control_seed}|{scenario_id}|blind') -> int64",
        "models_used": [
            "shared_a0_a1_baseline",
            "rec-a2",
        ],
        "top_k": 10,
    }

    manifest_path = REPO_ROOT / REPRODUCIBILITY_MANIFEST_RELPATH
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(reproducibility_manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    manifest_hash = sha256_file(manifest_path)

    return {
        "primary_scenarios_sha256": primary_hash,
        "thin_scenarios_sha256": thin_hash,
        "internal_pool_sha256": internal_hash,
        "blinded_pool_sha256": blinded_hash,
        "reproducibility_manifest_sha256": manifest_hash,
    }


def get_all_internal_records(internal_pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten scenario-grouped internal pool into individual records."""
    records = []
    for scn in internal_pool:
        records.extend(scn["items"])
    return records


def get_all_blinded_records(blinded_pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten scenario-grouped blinded pool into individual records."""
    records = []
    for scn in blinded_pool:
        records.extend(scn["items"])
    return records


if __name__ == "__main__":
    print("Building W5 Evaluation Scenario Manifests and Candidate Pools...")
    hashes = build_and_save_artifacts()
    print("Done! Artifact Hashes:")
    for k, v in hashes.items():
        print(f"  {k}: {v}")
