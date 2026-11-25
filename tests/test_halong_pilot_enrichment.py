from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.curate_60_pilot_pois_from_wikimedia import (
    HALONG_MISSING_PAIR_AUDIT_V1,
    _apply_verified_halong_audit_entry,
    _compute_summary,
    _is_license_free,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_PATH = REPO_ROOT / "data" / "enrichment" / "poi_enrichment_pilot_60_v1.json"
FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"


def test_pilot_60_schema_and_halong_provenance() -> None:
    payload = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    freeze_v2 = json.loads(FREEZE_V2_PATH.read_text(encoding="utf-8"))
    freeze_by_id = {x["place_id"]: x for x in freeze_v2}

    assert payload["schema_version"] == "GOMATE_POI_PILOT_60_ENRICHMENT_V1"
    assert payload["source_policy"] == "OSM_OVERTURE_WIKIPEDIA_WIKIDATA_COMMONS_ONLY_ZERO_SCRAPING"
    assert payload["no_fabricated_ratings_or_reviews"] is True

    items = payload["items"]
    assert len(items) == 60
    assert payload["summary"] == _compute_summary(items)

    halong = [x for x in items if x["destination_slug"] == "ha-long"]
    assert len(halong) == 20

    for item in halong:
        pid = item["place_id"]
        assert pid in freeze_by_id
        assert item["name"] == freeze_by_id[pid]["name"]

        if item.get("description"):
            assert item.get("description_source_url"), f"Missing description_source_url for {pid}"
            assert item.get("description_license"), f"Missing description_license for {pid}"

        if item.get("cover_image"):
            assert item["images"] and item["cover_image"] == item["images"][0]
            assert len(item["image_attributions"]) == len(item["images"])
            for attr in item["image_attributions"]:
                assert attr.get("commonsPageUrl", "").startswith("https://commons.wikimedia.org/wiki/File:")
                assert _is_license_free(attr.get("license", ""))
                assert attr.get("artist")

    # Tháp Đồng Hồ must have both verified description and Commons cover image
    thap = next(x for x in halong if x["place_id"] == "65562a67-84ff-44a0-990d-31917a2a9bd0")
    assert thap["name"] == "Tháp Đồng Hồ"
    assert thap["enrichment_tier"] == "media_and_article"
    assert thap["description"] and thap["description_source_url"] and thap["description_license"]
    assert thap["cover_image"] and thap["image_attributions"][0]["license"] == "CC BY-SA 4.0"
    assert thap["image_attributions"][0]["artist"] == "Pdhadam"

    # Every audited Ha Long POI (verified or unverified) records explicit status and reason
    for pid in HALONG_MISSING_PAIR_AUDIT_V1:
        rec = next(x for x in halong if x["place_id"] == pid)
        assert rec.get("verification_status")
        assert rec.get("verification_note")


def test_coordinate_and_identity_gate_fails_closed() -> None:
    base_rec = {
        "place_id": "65562a67-84ff-44a0-990d-31917a2a9bd0",
        "name": "Tháp Đồng Hồ",
        "destination_slug": "ha-long",
        "category": "attraction",
        "is_rec_a_core_v2": True,
        "description": None,
        "description_source_url": None,
        "description_license": None,
        "cover_image": None,
        "images": [],
        "image_attributions": [],
        "enrichment_tier": "osm_factual_only",
    }
    drifted_freeze = {
        "place_id": "65562a67-84ff-44a0-990d-31917a2a9bd0",
        "name": "Tháp Đồng Hồ",
        "latitude": 20.9600,
        "longitude": 107.0950,
        "sources": [{"source_name": "osm", "source_id": "way/674228542"}],
    }
    rec1 = copy.deepcopy(base_rec)
    assert _apply_verified_halong_audit_entry(rec1, drifted_freeze) is False
    assert rec1["description"] is None
    assert rec1["cover_image"] is None
    assert rec1["verification_status"] == "coordinate_drift_exceeded_skipped"

    wrong_source_freeze = {
        "place_id": "65562a67-84ff-44a0-990d-31917a2a9bd0",
        "name": "Tháp Đồng Hồ",
        "latitude": 20.9516105,
        "longitude": 107.0851999,
        "sources": [{"source_name": "osm", "source_id": "way/999999999"}],
    }
    rec2 = copy.deepcopy(base_rec)
    assert _apply_verified_halong_audit_entry(rec2, wrong_source_freeze) is False
    assert rec2["description"] is None
    assert rec2["cover_image"] is None
    assert rec2["verification_status"] == "identity_mismatch_skipped"
