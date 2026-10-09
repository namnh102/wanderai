"""TASK MVP-SCOPE-01-R1 Lineage, Destination Membership & Evaluation Scope Reconciliation Test Suite.

Verifies:
1. Freeze V1 parent count = 580
2. Freeze V1 destination distribution and reconciliation of narrative report vs JSON artifact
3. Every V1 canonical place ID appears exactly once in V1->V2 lineage artifact
4. No V1 parent place silently disappears
5. All 179 NEW OSM identities are genuinely new relative to Freeze V1
6. V2 verified count equation is exact (622 + 137 = 759 == 580 + 179)
7. REC-A-CORE-V2 contains only Hanoi, Da Nang, Ha Long
8. No known Dien Ban / Quang Nam place is counted in Da Nang primary core
9. Primary core place IDs are unique
10. Secondary corpus place IDs are unique
11. Core and secondary sets are disjoint
12. Core + secondary = total V2 verified corpus
13. Primary recommender metric contract remains: NDCG@10, Recall@10, Precision@10, HitRate@10, Coverage@10, Diversity@10
14. Freeze V1 SHA integrity remains 100% unchanged
"""

import hashlib
import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

@pytest.fixture(scope="module")
def v1_places():
    path = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v1.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def v2_places():
    path = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def lineage_manifest():
    path = REPO_ROOT / "data" / "manifests" / "freeze-v1-to-v2-place-lineage.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Assertion 1: Freeze V1 parent count = 580
def test_assertion_1_freeze_v1_parent_count(v1_places):
    assert len(v1_places) == 580, f"Expected 580 V1 places, got {len(v1_places)}"


# Assertion 2: Freeze V1 destination distribution and report discrepancy reconciliation
def test_assertion_2_freeze_v1_distribution_reconciliation(v1_places, lineage_manifest):
    # Verify authoritative JSON artifact distribution
    from collections import Counter
    counts = Counter(p["destination_slug"] for p in v1_places)
    
    assert counts["ha-noi"] == 145, f"Expected 145 Hanoi, got {counts['ha-noi']}"
    assert counts["ha-long"] == 188, f"Expected 188 Ha Long, got {counts['ha-long']}"
    assert counts["da-nang"] == 114, f"Expected 114 Da Nang, got {counts['da-nang']}"
    assert counts["hoi-an"] == 50, f"Expected 50 Hoi An, got {counts['hoi-an']}"
    assert counts["hue"] == 50, f"Expected 50 Hue, got {counts['hue']}"
    assert counts["nha-trang"] == 33, f"Expected 33 Nha Trang, got {counts['nha-trang']}"
    assert sum(counts.values()) == 580

    # Verify reconciliation metadata in lineage manifest
    narrative = lineage_manifest["narrative_discrepancy_root_cause"]
    reported = narrative["reported_text_distribution"]
    assert reported["da-nang"] == 89
    assert reported["hoi-an"] == 80
    assert reported["hue"] == 37
    assert reported["nha-trang"] == 41
    assert reported["total"] == 580
    assert narrative["true_json_artifact_distribution"]["da-nang"] == 114


# Assertion 3: Every V1 canonical place ID appears exactly once in V1->V2 lineage artifact
def test_assertion_3_every_v1_place_appears_once_in_lineage(v1_places, lineage_manifest):
    lineage_places = lineage_manifest["places"]
    assert len(lineage_places) == 580, f"Expected 580 places in lineage, got {len(lineage_places)}"
    
    lineage_pids = [p["place_id"] for p in lineage_places]
    assert len(lineage_pids) == len(set(lineage_pids)), "Duplicate place IDs in lineage manifest!"
    
    v1_pids = {p["place_id"] for p in v1_places}
    assert set(lineage_pids) == v1_pids, "Mismatch between V1 places and lineage manifest places!"


# Assertion 4: No V1 parent place silently disappears
def test_assertion_4_no_v1_parent_silently_disappears(v1_places, v2_places):
    v2_pids = {p["place_id"] for p in v2_places}
    for p in v1_places:
        assert p["place_id"] in v2_pids, f"V1 place {p['place_id']} ({p['name']}) silently disappeared from V2!"


# Assertion 5: All 179 NEW OSM identities are genuinely new relative to Freeze V1
def test_assertion_5_all_179_new_osm_identities_genuinely_new(v1_places, v2_places):
    v1_pids = {p["place_id"] for p in v1_places}
    new_places = [p for p in v2_places if p["place_id"] not in v1_pids]
    assert len(new_places) == 179, f"Expected 179 new places, got {len(new_places)}"

    def extract_osm_ids(places):
        osm_ids = set()
        for p in places:
            for s in p.get("sources", []):
                if s.get("source_name") == "osm":
                    osm_ids.add(s.get("source_id"))
        return osm_ids

    v1_osm = extract_osm_ids(v1_places)
    new_osm = extract_osm_ids(new_places)
    assert len(v1_osm) == 580
    assert len(new_osm) == 179
    intersection = v1_osm.intersection(new_osm)
    assert len(intersection) == 0, f"Intersection between V1 and NEW is not empty: {intersection}"


# Assertion 6: V2 verified count equation is exact
def test_assertion_6_v2_verified_count_equation(v1_places, v2_places):
    core = [p for p in v2_places if p.get("is_rec_a_core_v2") is True]
    secondary = [p for p in v2_places if p.get("is_rec_a_core_v2") is False]
    
    # Equation 1: core + secondary == total V2
    assert len(core) + len(secondary) == len(v2_places) == 759
    assert len(core) == 622
    assert len(secondary) == 137
    
    # Equation 2: V1 + 179 new == total V2
    assert len(v1_places) + 179 == len(v2_places) == 759


# Assertion 7: REC-A-CORE-V2 contains only Hanoi, Da Nang, Ha Long
def test_assertion_7_rec_a_core_v2_destinations_only_three_mvp(v2_places):
    core = [p for p in v2_places if p.get("is_rec_a_core_v2") is True]
    destinations = {p["destination_slug"] for p in core}
    assert destinations == {"ha-noi", "ha-long", "da-nang"}, f"Unexpected destinations in core: {destinations}"


# Assertion 8: No known Dien Ban / Quang Nam place is counted in Da Nang primary core
def test_assertion_8_no_quang_nam_places_in_primary_core(v2_places):
    core = [p for p in v2_places if p.get("is_rec_a_core_v2") is True]
    core_pids = {p["place_id"] for p in core}
    
    known_quang_nam_ids = {
        "5e1ca20e-b579-59b8-b243-9f13aa43c65f", # TASY STUDIO
        "6489aeb0-fb3d-584d-9ca9-d6172e9cc63f", # Khu tưởng niệm Hà My
        "db61c6ab-1fde-51fe-ac20-0deef2fc5981", # Đài tưởng niệm thảm sát Hà My
        "4c4ca7e8-2586-57cb-af5d-5e2b72c7bd4d"  # Mini-Golf Hoi An
    }
    
    for qn_id in known_quang_nam_ids:
        assert qn_id not in core_pids, f"Quang Nam place {qn_id} leaked into REC-A-CORE-V2!"

    # Also verify spatial bounding box for all Da Nang core places
    da_nang_core = [p for p in core if p["destination_slug"] == "da-nang"]
    assert len(da_nang_core) == 289
    for p in da_nang_core:
        assert 15.95 <= p["latitude"] <= 16.20, f"Place {p['name']} outside lat: {p['latitude']}"
        assert 107.95 <= p["longitude"] <= 108.35, f"Place {p['name']} outside lon: {p['longitude']}"


# Assertion 9: Primary core place IDs are unique
def test_assertion_9_primary_core_place_ids_unique(v2_places):
    core = [p for p in v2_places if p.get("is_rec_a_core_v2") is True]
    core_ids = [p["place_id"] for p in core]
    assert len(core_ids) == len(set(core_ids)) == 622


# Assertion 10: Secondary corpus place IDs are unique
def test_assertion_10_secondary_corpus_place_ids_unique(v2_places):
    secondary = [p for p in v2_places if p.get("is_rec_a_core_v2") is False]
    secondary_ids = [p["place_id"] for p in secondary]
    assert len(secondary_ids) == len(set(secondary_ids)) == 137


# Assertion 11: Core and secondary sets are disjoint
def test_assertion_11_core_and_secondary_disjoint(v2_places):
    core_ids = {p["place_id"] for p in v2_places if p.get("is_rec_a_core_v2") is True}
    secondary_ids = {p["place_id"] for p in v2_places if p.get("is_rec_a_core_v2") is False}
    assert core_ids.isdisjoint(secondary_ids)


# Assertion 12: Core + secondary = total V2 verified corpus
def test_assertion_12_core_plus_secondary_equals_total_v2(v2_places):
    core_count = sum(1 for p in v2_places if p.get("is_rec_a_core_v2") is True)
    sec_count = sum(1 for p in v2_places if p.get("is_rec_a_core_v2") is False)
    assert core_count + sec_count == len(v2_places) == 759


# Assertion 13: Primary recommender metric contract remains NDCG@10, Recall@10, Precision@10, HitRate@10, Coverage@10, Diversity@10
def test_assertion_13_primary_metric_contract_documented():
    scope_file = REPO_ROOT / "docs" / "data" / "gomate-mvp-three-city-scope-v2.md"
    assert scope_file.exists()
    with open(scope_file, "r", encoding="utf-8") as f:
        content = f.read()

    mandatory_metrics = [
        "NDCG@10",
        "Recall@10",
        "Precision@10",
        "HitRate@10",
        "Coverage@10",
        "Diversity@10"
    ]
    for metric in mandatory_metrics:
        assert metric in content, f"Metric {metric} missing from scope document!"

    # Verify MAP is marked optional / exploratory
    assert "OPTIONAL / EXPLORATORY" in content


# Assertion 14: Freeze V1 SHA integrity remains unchanged
def test_assertion_14_freeze_v1_sha_integrity():
    v1_sha = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v1.sha256"
    assert v1_sha.exists()
    with open(v1_sha, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            exp_sha, rel_p = line.split(None, 1)
            target = REPO_ROOT / rel_p.strip()
            assert target.exists(), f"Freeze V1 file missing: {rel_p}"
            assert compute_sha256(target) == exp_sha, f"Freeze V1 byte mutation in {rel_p}!"
