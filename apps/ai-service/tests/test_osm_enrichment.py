"""TASK 07.4 regression tests: real OSM enrichment data (no DB / network needed)."""
import json
import re
import sys
import uuid
from pathlib import Path

workspace_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from data.pipelines.osm.enrich_osm import NAMESPACE, CAPS, build_query  # noqa: E402
from data.pipelines.osm.config import PILOT_REGIONS  # noqa: E402

RAW = workspace_root / "data" / "raw" / "osm_enrichment.json"
CURATED = workspace_root / "data" / "curated" / "places_osm_enrichment.json"
CANONICAL = workspace_root / "data" / "curated" / "places_canonical.json"
DENY = workspace_root / "data" / "manifests" / "osm-invalid-sources.json"

raw = json.loads(RAW.read_text(encoding="utf-8"))
curated = json.loads(CURATED.read_text(encoding="utf-8"))


def test_every_source_id_comes_from_an_upstream_response():
    upstream = {
        f"{el['type']}/{el['id']}"
        for blob in raw["regions"].values()
        for el in blob["elements"]
    }
    for p in curated:
        assert p["sources"][0]["source_id"] in upstream, p["name"]


def test_source_ids_are_well_formed_unique_and_not_denylisted_or_duplicated():
    ids = [p["sources"][0]["source_id"] for p in curated]
    assert len(ids) == len(set(ids)) and ids
    deny = {s["source_id"] for s in json.loads(DENY.read_text(encoding="utf-8"))["invalid_sources"]}
    existing = {
        s["source_id"]
        for p in json.loads(CANONICAL.read_text(encoding="utf-8"))
        for s in p.get("sources", [])
    }
    for i in ids:
        assert re.fullmatch(r"(node|way|relation)/\d+", i)
        assert i not in deny
        assert i not in existing


def test_place_ids_are_deterministic_and_ratings_unavailable():
    for p in curated:
        assert p["id"] == str(uuid.uuid5(NAMESPACE, p["sources"][0]["source_id"]))
        assert p["rating"] is None
        assert p["review_count"] == 0


def test_provenance_fields_complete():
    for p in curated:
        s = p["sources"][0]
        assert s["source_name"] == "osm"
        assert s["raw_name"] and s["raw_data"].get("name")
        assert s["osm_base_timestamp"]
        assert 8 < p["latitude"] < 24 and 102 < p["longitude"] < 110


def test_category_caps_and_coverage():
    counts = {}
    for p in curated:
        assert p["category"] in CAPS
        counts[(p["city"], p["category"])] = counts.get((p["city"], p["category"]), 0) + 1
    assert all(v <= CAPS[c] for (_, c), v in counts.items())
    cats = {c for (_, c) in counts}
    assert {"attraction", "beach", "culture"} <= cats


def test_raw_snapshot_covers_all_pilot_regions_with_query_and_timestamp():
    assert set(raw["regions"]) == set(PILOT_REGIONS)
    for name, blob in raw["regions"].items():
        assert blob["query"] == build_query(PILOT_REGIONS[name])
        assert blob["osm_base_timestamp"]


def test_regions_recollected_from_primary_host_after_stale_mirror_finding():
    # da_nang / nha_trang were first served by a stale mirror (2026-06/07 data); they must be primary now.
    for name in ("da_nang", "nha_trang"):
        assert raw["regions"][name]["endpoint"] == "https://overpass-api.de/api/interpreter"
        assert raw["regions"][name]["osm_base_timestamp"] >= "2026-10"
