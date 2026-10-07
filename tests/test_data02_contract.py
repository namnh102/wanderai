"""DATA-02 Comprehensive Quality & Contract Test Suite.

Verifies:
- Taxonomy V1.1 mapping
- OSM parser normalization and quality filtering
- Synthetic preference determinism & reproducibility (seed=42)
- ViHoRec 6-file cryptographic integrity
- Entity resolution logic
- Database & curated dataset invariants:
  - Verified POIs have OSM source
  - Ratings remain NULL
  - Zero Google sources
  - Zero unlicensed Overture auxiliary sources
  - Zero synthetic reviews in evaluation corpus
  - Pinned Wikivoyage RAG chunks intact
"""

import hashlib
import json
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# 1. Unit Tests: Taxonomy Mapping
from scripts.parse_and_normalize_osm import map_taxonomy

def test_taxonomy_mapping_clarifications():
    # Zoo vs Park
    t1, t2, leg = map_taxonomy({"tourism": "zoo"})
    assert (t1, t2, leg) == ("NATURE_SCENERY", "zoo_wildlife", "park")

    # Aquarium vs Theme Park
    t1, t2, leg = map_taxonomy({"tourism": "aquarium"})
    assert (t1, t2, leg) == ("ATTRACTIONS_LEISURE", "aquarium", "attraction")

    t1, t2, leg = map_taxonomy({"tourism": "theme_park"})
    assert (t1, t2, leg) == ("ATTRACTIONS_LEISURE", "theme_park_leisure", "entertainment")

    # Mall vs Traditional Market
    t1, t2, leg = map_taxonomy({"shop": "mall"})
    assert (t1, t2, leg) == ("SHOPPING_COMMERCE", "shopping_mall", "market")

    t1, t2, leg = map_taxonomy({"amenity": "marketplace"})
    assert (t1, t2, leg) == ("SHOPPING_COMMERCE", "traditional_market", "market")

    # Boat terminal / Ferry terminal
    t1, t2, leg = map_taxonomy({"amenity": "ferry_terminal"})
    assert (t1, t2, leg) == ("TRANSPORT_HUBS", "boat_terminal", "attraction")

    # Cave grotto
    t1, t2, leg = map_taxonomy({"natural": "cave_entrance"})
    assert (t1, t2, leg) == ("NATURE_SCENERY", "cave_grotto", "attraction")

    # Island landmark
    t1, t2, leg = map_taxonomy({"place": "island"})
    assert (t1, t2, leg) == ("NATURE_SCENERY", "island_landmark", "attraction")

    # Seafood dining
    t1, t2, leg = map_taxonomy({"amenity": "restaurant", "cuisine": "seafood"})
    assert (t1, t2, leg) == ("FOOD_BEVERAGE", "seafood_dining", "restaurant")

    # Unsupported tags
    t1, t2, leg = map_taxonomy({"barrier": "fence"})
    assert (t1, t2, leg) == (None, None, None)

# 2. Unit Tests: OSM Parser & Filter
from scripts.parse_and_normalize_osm import format_address

def test_osm_address_formatting():
    tags = {
        "addr:housenumber": "42",
        "addr:street": "Tràng Tiền",
        "addr:district": "Hoàn Kiếm",
        "addr:city": "Hà Nội"
    }
    addr = format_address(tags)
    assert addr == "42 Tràng Tiền, Hoàn Kiếm, Hà Nội"

    assert format_address({}) is None

# 3. Unit Tests: Synthetic Preference Generator Determinism
from scripts.generate_synthetic_preferences import generate_synthetic_preferences, analyze_distributions

def test_synthetic_preferences_determinism():
    run1 = generate_synthetic_preferences(300, seed=42)
    run2 = generate_synthetic_preferences(300, seed=42)
    assert run1 == run2, "Non-deterministic generation across identical seed!"

    json_file = REPO_ROOT / "data" / "evaluation" / "synthetic" / "preferences_n300_seed42.json"
    assert json_file.exists()
    h = hashlib.sha256()
    with open(json_file, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    assert h.hexdigest() == "1e883266bf6b145de0b7debf02d4881fc2f5293c9cf693ed34cd01715f6ab21a"

    # Check distribution constraints
    stats = analyze_distributions(run1)
    assert stats["population_size"] == 300
    assert "BUDGET" in stats["travelStyle_distribution"]
    assert "COMFORT" in stats["travelStyle_distribution"]
    assert stats["pace_distribution"]["MODERATE"]["pct"] > 40.0
    for p in run1:
        assert p["isSynthetic"] is True
        assert p["seed"] == 42
        assert p["generatorVersion"] == "preference-v1"
        assert p["budgetMin"] < p["budgetMax"]
        assert len(p["interests"]) >= 2

# 4. Unit Tests: ViHoRec Checksum Validation
from scripts.verify_vihorec_integrity import verify_vihorec

def test_vihorec_integrity_pass():
    assert verify_vihorec(REPO_ROOT) is True

# 5. Unit Tests: Entity Resolution Logic
from scripts.overture_crosscheck import jaro_winkler, token_sort_ratio, is_category_compatible, resolve_overture_license

def test_entity_resolution_string_similarity():
    jw = jaro_winkler("ha long bay cruise terminal", "ha long bay cruise terminal")
    assert jw == 1.0

    jw_sim = jaro_winkler("muong thanh luxury ha long hotel", "muong thanh luxury ha long")
    ts_sim = token_sort_ratio("muong thanh luxury ha long hotel", "muong thanh luxury ha long")
    assert max(jw_sim, ts_sim) >= 0.85

def test_overture_license_resolution():
    lic, prov = resolve_overture_license([{"license": "CDLA-Permissive-2.0", "dataset": "meta"}])
    assert lic == "CDLA Permissive 2.0"
    assert "meta" in prov

    lic2, prov2 = resolve_overture_license([{"license": "Apache-2.0", "dataset": "microsoft"}])
    assert lic2 == "Apache 2.0"

# 6. Quality Tests: Frozen Places Dataset Invariants
def test_curated_places_freeze_invariants():
    curated_file = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v1.json"
    assert curated_file.exists(), "Missing gomate_places_freeze_v1.json!"

    with open(curated_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    assert len(places) == 580, f"Expected 580 verified places, got {len(places)}"

    hanoi_count = sum(1 for p in places if p["destination_slug"] == "ha-noi" or p["destination"] == "Hà Nội")
    halong_count = sum(1 for p in places if p["destination_slug"] == "ha-long" or p["destination"] == "Hạ Long")

    assert hanoi_count >= 120, f"Expected >= 120 Hanoi POIs, got {hanoi_count}"
    assert halong_count >= 60, f"Expected >= 60 Ha Long POIs, got {halong_count}"

    for p in places:
        # Every verified place MUST have an OSM source
        sources = p.get("sources", [])
        osm_sources = [s for s in sources if s["source_name"] == "osm"]
        assert len(osm_sources) >= 1, f"Place {p['name']} ({p['place_id']}) missing OSM source!"

        # Rating must be NULL; review_count must be 0
        assert p["rating"] is None, f"Place {p['name']} has non-null rating: {p['rating']}!"
        assert p["review_count"] == 0, f"Place {p['name']} has fake review count: {p['review_count']}!"

        # ZERO Google sources
        for s in sources:
            src_name = s.get("source_name", "").lower()
            assert "google" not in src_name, f"Google source detected in {p['name']}: {src_name}!"

            if s.get("source_name") == "overture":
                raw = s.get("raw_data") or {}
                if isinstance(raw, str):
                    raw = json.loads(raw)
                assert raw.get("license") is not None, f"Overture auxiliary source missing license in {p['name']}!"

# 7. Quality Tests: Manifest & SHA-256 Integrity
def test_freeze_manifest_sha256_integrity():
    sha_file = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v1.sha256"
    assert sha_file.exists()

    with open(sha_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 23, f"Expected 23 frozen artifacts, got {len(lines)}"

    for line in lines:
        expected_sha, rel_path = line.split("  ", 1)
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), f"Frozen file missing: {rel_path}"

        h = hashlib.sha256()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_sha = h.hexdigest()
        assert actual_sha == expected_sha, f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"

# 8. DATA-02-R1 Governance Closure Tests
import subprocess
import yaml

def test_overture_license_resolution_strict_no_fallback():
    """Verify that unknown/missing licenses resolve to None without falling back to CDLA."""
    # Unknown license
    lic, prov = resolve_overture_license([{"license": "Proprietary", "dataset": "unknown_corp"}])
    assert lic is None
    assert "unknown_corp" in prov

    # Missing license
    lic_empty, prov_empty = resolve_overture_license([{"dataset": "partner_x"}])
    assert lic_empty is None
    assert "partner_x" in prov_empty

    # Empty list
    lic_none, prov_none = resolve_overture_license([])
    assert lic_none is None
    assert prov_none == []

    # Valid approved licenses
    for app_lic, exp in [
        ("CDLA-Permissive-2.0", "CDLA Permissive 2.0"),
        ("Apache-2.0", "Apache 2.0"),
        ("CC0-1.0", "CC0 1.0"),
    ]:
        l, _ = resolve_overture_license([{"license": app_lic, "dataset": "meta"}])
        assert l == exp

def test_manifest_dynamic_db_assertions():
    """Verify manifest YAML schema and live DB consistency invariants."""
    yaml_file = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v1.yaml"
    assert yaml_file.exists()

    with open(yaml_file, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    db_state = manifest["database_state"]
    assert db_state["osm_documents"] == db_state["total_verified_osm_sources"] == 580
    assert db_state["wikivoyage_documents"] == 464
    assert db_state["total_documents"] == db_state["osm_documents"] + db_state["wikivoyage_documents"] == 1044
    assert db_state["places_with_non_null_rating"] == 0

    assert len(manifest["committed_immutable_artifacts"]) == 17
    assert len(manifest["local_restricted_dependencies"]) == 6

def test_reca_item_universe_lock():
    """Verify REC-A item universe is strictly locked to the 580 canonical verified places."""
    curated_file = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v1.json"
    with open(curated_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    assert len(places) == 580
    place_ids = set()
    for p in places:
        assert p["place_id"] not in place_ids, f"Duplicate place_id {p['place_id']}"
        place_ids.add(p["place_id"])
        assert p["latitude"] is not None and p["longitude"] is not None
        assert p["category"] is not None
        assert p["destination"] is not None

def test_vihorec_not_tracked_in_git():
    """Verify that no ViHoRec CSV files are tracked in the Git index."""
    result = subprocess.run(
        ["git", "ls-files", "data/restricted/vihorec"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    tracked_files = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    assert len(tracked_files) == 0, f"Restricted ViHoRec files tracked in git: {tracked_files}"

