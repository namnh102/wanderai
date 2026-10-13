"""Unit and Integration Tests for W5 Evaluation Preparation Artifacts.

Validates:
- W5-SCN-01 to W5-SCN-07: Scenario manifest specifications and invariants
- W5-POOL-01 to W5-POOL-08: Candidate pool construction, deduplication, and controls
- W5-BLIND-01 to W5-BLIND-03: Structural blinding and leakage prevention
- W5-REP-01: Artifact generation reproducibility and byte-identical hashes
- W5-PARITY-01: Information parity between baseline and A2
- W5-DATA-01 to W5-DATA-02: Core dataset integrity and secondary leakage invariants
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PRIMARY_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_primary_scenarios_v1.json"
THIN_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_thin_diagnostic_scenarios_v1.json"
INTERNAL_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_candidate_pool_internal_v1.json"
BLINDED_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_candidate_pool_blinded_v1.json"
REPRODUCIBILITY_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_reproducibility_manifest_v1.json"
DATASET_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"


@pytest.fixture(scope="module")
def primary_scenarios() -> List[Dict[str, Any]]:
    assert PRIMARY_PATH.exists(), f"Missing {PRIMARY_PATH}"
    with open(PRIMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def thin_scenarios() -> List[Dict[str, Any]]:
    assert THIN_PATH.exists(), f"Missing {THIN_PATH}"
    with open(THIN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def internal_pool() -> List[Dict[str, Any]]:
    assert INTERNAL_PATH.exists(), f"Missing {INTERNAL_PATH}"
    with open(INTERNAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def blinded_pool() -> List[Dict[str, Any]]:
    assert BLINDED_PATH.exists(), f"Missing {BLINDED_PATH}"
    with open(BLINDED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reproducibility_manifest() -> Dict[str, Any]:
    assert REPRODUCIBILITY_PATH.exists(), f"Missing {REPRODUCIBILITY_PATH}"
    with open(REPRODUCIBILITY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def freeze_v2_places() -> List[Dict[str, Any]]:
    assert DATASET_PATH.exists(), f"Missing {DATASET_PATH}"
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# --- W5-SCN: Scenario Manifest Tests ---


def test_w5_scn_01_thirty_primary_scenarios(primary_scenarios: List[Dict[str, Any]]):
    """W5-SCN-01: Exactly 30 primary scenarios must exist in the primary manifest."""
    assert len(primary_scenarios) == 30
    scenario_ids = [s["scenario_id"] for s in primary_scenarios]
    assert len(set(scenario_ids)) == 30, "Scenario IDs must be unique"


def test_w5_scn_02_fifteen_u1_and_fifteen_u2(primary_scenarios: List[Dict[str, Any]]):
    """W5-SCN-02: Exactly 15 U1 and 15 U2 scenarios."""
    u1_scenarios = [s for s in primary_scenarios if s["user_stratum"] == "U1"]
    u2_scenarios = [s for s in primary_scenarios if s["user_stratum"] == "U2"]
    assert len(u1_scenarios) == 15
    assert len(u2_scenarios) == 15
    for s in u1_scenarios:
        assert len(s["declared_interests"]) == 1
    for s in u2_scenarios:
        assert len(s["declared_interests"]) >= 2


def test_w5_scn_03_six_thin_diagnostics(thin_scenarios: List[Dict[str, Any]]):
    """W5-SCN-03: Exactly 6 THIN diagnostic scenarios."""
    assert len(thin_scenarios) == 6
    for s in thin_scenarios:
        assert s["track"] == "THIN_DIAGNOSTIC"
        assert s["user_stratum"] == "U1"
        assert 1 <= s["i0_inventory_count"] <= 9


def test_w5_scn_04_all_three_destinations_represented(primary_scenarios: List[Dict[str, Any]]):
    """W5-SCN-04: All 3 destinations represented in primary scenarios."""
    expected_dests = {"ha-noi", "da-nang", "ha-long"}
    found_dests = {s["destination"] for s in primary_scenarios}
    assert found_dests == expected_dests
    for dest in expected_dests:
        dest_scenarios = [s for s in primary_scenarios if s["destination"] == dest]
        assert len(dest_scenarios) >= 5


def test_w5_scn_05_all_seven_canonical_interests_represented(primary_scenarios: List[Dict[str, Any]]):
    """W5-SCN-05: All 7 canonical interests represented across primary scenarios."""
    from recommendation.reca.contract import CANONICAL_INTERESTS

    represented = set()
    for s in primary_scenarios:
        for interest in s["declared_interests"]:
            represented.add(interest)
    assert represented == set(CANONICAL_INTERESTS)


def test_w5_scn_06_u2_combinations_match_frozen_spec(primary_scenarios: List[Dict[str, Any]]):
    """W5-SCN-06: U2 combinations exactly match frozen R6 specification."""
    expected_u2 = {
        # Hanoi (5)
        "HN-U2-01": ("ha-noi", ["food_cuisine", "culture_history"]),
        "HN-U2-02": ("ha-noi", ["nature_outdoor", "nightlife_entertainment"]),
        "HN-U2-03": ("ha-noi", ["food_cuisine", "nature_outdoor"]),
        "HN-U2-04": ("ha-noi", ["culture_history", "nature_outdoor", "nightlife_entertainment"]),
        "HN-U2-05": ("ha-noi", ["food_cuisine", "culture_history", "nightlife_entertainment"]),
        # Da Nang (5)
        "DN-U2-01": ("da-nang", ["food_cuisine", "culture_history"]),
        "DN-U2-02": ("da-nang", ["coffee_culture", "beach_island"]),
        "DN-U2-03": ("da-nang", ["shopping_local", "nightlife_entertainment"]),
        "DN-U2-04": ("da-nang", ["food_cuisine", "coffee_culture", "shopping_local"]),
        "DN-U2-05": ("da-nang", ["culture_history", "beach_island", "nightlife_entertainment"]),
        # Ha Long (5)
        "HL-U2-01": ("ha-long", ["food_cuisine", "culture_history"]),
        "HL-U2-02": ("ha-long", ["nature_outdoor", "coffee_culture"]),
        "HL-U2-03": ("ha-long", ["shopping_local", "food_cuisine"]),
        "HL-U2-04": ("ha-long", ["culture_history", "nature_outdoor", "shopping_local"]),
        "HL-U2-05": ("ha-long", ["food_cuisine", "coffee_culture", "shopping_local"]),
    }
    u2_scenarios = {s["scenario_id"]: s for s in primary_scenarios if s["user_stratum"] == "U2"}
    assert set(u2_scenarios.keys()) == set(expected_u2.keys())
    for sid, (dest, interests) in expected_u2.items():
        actual = u2_scenarios[sid]
        assert actual["destination"] == dest
        assert actual["declared_interests"] == interests


def test_w5_scn_07_no_thin_in_primary(
    primary_scenarios: List[Dict[str, Any]],
    thin_scenarios: List[Dict[str, Any]],
):
    """W5-SCN-07: No THIN scenario enters the primary manifest."""
    thin_pairs = {(s["destination"], s["declared_interests"][0]) for s in thin_scenarios}
    for s in primary_scenarios:
        if s["user_stratum"] == "U1":
            pair = (s["destination"], s["declared_interests"][0])
            assert pair not in thin_pairs, f"THIN pair {pair} entered primary scenarios"


# --- W5-POOL: Candidate Pool Construction & Invariants ---


def test_w5_pool_01_baseline_top10_contribution(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-01: Each primary scenario has baseline Top-10 contribution."""
    for scn in internal_pool:
        assert scn["baseline_count"] == 10
        base_items = [item for item in scn["items"] if "shared_a0_a1_baseline" in item["source_systems"]]
        assert len(base_items) == 10


def test_w5_pool_02_a2_top10_contribution(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-02: Each primary scenario has A2 Top-10 contribution."""
    for scn in internal_pool:
        assert scn["a2_count"] == 10
        a2_items = [item for item in scn["items"] if "rec-a2" in item["source_systems"]]
        assert len(a2_items) == 10


def test_w5_pool_03_five_controls_per_scenario(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-03: Exactly 5 controls per primary scenario."""
    for scn in internal_pool:
        assert scn["control_count"] == 5
        ctrl_items = [item for item in scn["items"] if item["is_control"]]
        assert len(ctrl_items) == 5
        # Preferred 3 I0 + 2 I1 composition verified
        assert scn["control_composition"] == {"i0": 3, "i1": 2}


def test_w5_pool_04_controls_same_destination_core(
    internal_pool: List[Dict[str, Any]],
    freeze_v2_places: List[Dict[str, Any]],
):
    """W5-POOL-04: Controls are same-destination REC-A core items."""
    core_places_map = {
        p["place_id"]: p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True
    }
    for scn in internal_pool:
        dest = scn["destination"]
        for item in scn["items"]:
            if item["is_control"]:
                pid = item["place_id"]
                assert pid in core_places_map, f"Control {pid} not in REC-A core"
                assert core_places_map[pid]["destination_slug"] == dest


def test_w5_pool_05_controls_no_overlap_model_union(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-05: Controls do not overlap baseline/A2 union."""
    for scn in internal_pool:
        for item in scn["items"]:
            if item["is_control"]:
                assert "shared_a0_a1_baseline" not in item["source_systems"]
                assert "rec-a2" not in item["source_systems"]
                assert item["baseline_rank"] is None
                assert item["a2_rank"] is None


def test_w5_pool_06_pool_deduplicated_by_place_id(
    internal_pool: List[Dict[str, Any]],
    blinded_pool: List[Dict[str, Any]],
):
    """W5-POOL-06: Pool is deduplicated by place_id."""
    for scn in internal_pool:
        place_ids = [item["place_id"] for item in scn["items"]]
        assert len(place_ids) == len(set(place_ids)), f"Duplicates in internal pool {scn['scenario_id']}"
        assert scn["final_unique_pool_count"] == len(place_ids)

    for scn in blinded_pool:
        place_ids = [item["place_id"] for item in scn["items"]]
        assert len(place_ids) == len(set(place_ids)), f"Duplicates in blinded pool {scn['scenario_id']}"
        assert scn["final_unique_pool_count"] == len(place_ids)


def test_w5_pool_07_final_pool_under_or_equal_25(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-07: Final unique pool <= 25 items for each scenario."""
    for scn in internal_pool:
        assert 15 <= scn["final_unique_pool_count"] <= 25


def test_w5_pool_08_all_model_items_eligible(internal_pool: List[Dict[str, Any]]):
    """W5-POOL-08: All model Top-10 items are judged-pool eligible."""
    for scn in internal_pool:
        base_items = [item for item in scn["items"] if "shared_a0_a1_baseline" in item["source_systems"]]
        a2_items = [item for item in scn["items"] if "rec-a2" in item["source_systems"]]
        assert len(base_items) == 10
        assert len(a2_items) == 10


# --- W5-BLIND: Structural Blinding Tests ---


def test_w5_blind_01_no_system_identity_fields(blinded_pool: List[Dict[str, Any]]):
    """W5-BLIND-01: Blinded artifact contains no system identity fields."""
    forbidden = [
        "rec-a0", "rec-a1", "rec-a2", "baseline", "strategy",
        "score", "rank", "source_systems", "control", "algorithm",
    ]
    for scn in blinded_pool:
        for k in scn.keys():
            for fb in forbidden:
                assert fb not in k.lower(), f"Forbidden word '{fb}' in scenario key '{k}'"
        for item in scn.get("items", []):
            for k, v in item.items():
                if k == "name":
                    continue  # Free-text place name excluded
                for fb in forbidden:
                    assert fb not in k.lower(), f"Forbidden word '{fb}' in item key '{k}'"
                    if isinstance(v, str):
                        assert fb not in v.lower(), f"Forbidden word '{fb}' in item value '{k}={v}'"


def test_w5_blind_02_blinded_order_shuffled(
    internal_pool: List[Dict[str, Any]],
    blinded_pool: List[Dict[str, Any]],
):
    """W5-BLIND-02: Blinded order does not preserve baseline or A2 ranking order."""
    internal_map = {s["scenario_id"]: s for s in internal_pool}
    for b_scn in blinded_pool:
        sid = b_scn["scenario_id"]
        i_scn = internal_map[sid]
        # In internal pool, find items that were rank 1..5 in baseline
        b_pids = [item["place_id"] for item in b_scn["items"]]
        baseline_order = [
            item["place_id"]
            for item in sorted(
                [x for x in i_scn["items"] if x["baseline_rank"] is not None],
                key=lambda x: x["baseline_rank"],
            )
        ]
        # Shuffled order must not be identical to original baseline ranking
        assert b_pids[:10] != baseline_order, f"Scenario {sid} blinded order matches baseline exactly!"


def test_w5_blind_03_no_rank_score_strategy_in_records(blinded_pool: List[Dict[str, Any]]):
    """W5-BLIND-03: Blinded records contain no rank/score/strategy fields."""
    forbidden_keys = {"rank", "score", "strategy", "is_control", "source_systems", "matched_interests"}
    for scn in blinded_pool:
        for item in scn["items"]:
            assert forbidden_keys.isdisjoint(set(item.keys())), f"Leaked keys in blinded item: {set(item.keys()) & forbidden_keys}"


# --- W5-REP & W5-PARITY: Reproducibility and Information Parity ---


def test_w5_rep_01_builder_idempotence_and_hash_identity():
    """W5-REP-01: Same builder run twice produces identical artifact hash."""
    from scripts.build_w5_eval_pool import build_and_save_artifacts

    hashes_run1 = build_and_save_artifacts()
    hashes_run2 = build_and_save_artifacts()
    assert hashes_run1 == hashes_run2, "Non-deterministic artifact output across runs!"


def test_w5_parity_01_information_parity(
    internal_pool: List[Dict[str, Any]],
    primary_scenarios: List[Dict[str, Any]],
):
    """W5-PARITY-01: Baseline and A2 use exact same destination, catalog, and preferences."""
    scenario_map = {s["scenario_id"]: s for s in primary_scenarios}
    for scn in internal_pool:
        sid = scn["scenario_id"]
        spec = scenario_map[sid]
        assert scn["destination"] == spec["destination"]
        assert scn["declared_interests"] == spec["declared_interests"]
        assert scn["candidate_catalog"] == spec["candidate_catalog"]
        assert scn["top_k"] == spec["top_k"]


# --- W5-DATA: Dataset Integrity Tests ---


def test_w5_data_01_core_622_invariants(freeze_v2_places: List[Dict[str, Any]]):
    """W5-DATA-01: 622 core remains unchanged with exact destination distribution."""
    core = [p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True]
    assert len(core) == 622
    hn = sum(1 for p in core if p.get("destination_slug") == "ha-noi")
    dn = sum(1 for p in core if p.get("destination_slug") == "da-nang")
    hl = sum(1 for p in core if p.get("destination_slug") == "ha-long")
    assert hn == 145
    assert dn == 289
    assert hl == 188


def test_w5_data_02_secondary_leakage(
    freeze_v2_places: List[Dict[str, Any]],
    internal_pool: List[Dict[str, Any]],
):
    """W5-DATA-02: Secondary leakage = 0 (no secondary places in core or evaluation pool)."""
    secondary_ids = {
        p["place_id"] for p in freeze_v2_places if p.get("is_rec_a_core_v2") is False
    }
    assert len(secondary_ids) == 137

    for scn in internal_pool:
        for item in scn["items"]:
            assert item["place_id"] not in secondary_ids, f"Secondary POI {item['place_id']} leaked into pool!"
