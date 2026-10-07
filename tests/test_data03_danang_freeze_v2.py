"""MVP-SCOPE-01 Dataset Freeze V2 & Da Nang Expansion Test Suite.

Verifies:
- Da Nang OSM normalization & Taxonomy V1.1 mapping
- Da Nang spatial bounds & provenance envelope
- Overture cross-check & strict license resolution
- Freeze V1 100% byte-for-byte immutability
- Freeze V2 cryptographic SHA-256 integrity
- REC-A-CORE-V2 item universe definition (Hanoi 145 + Da Nang 293 + Ha Long 188 = 626)
- Research corpus invariants: rating is NULL, review_count is 0, zero Google/Tripadvisor sources
- WP-PROF-01 7 canonical preference dimensions mapping
- Live database invariants (counts, RAG documents, Wikivoyage preservation)
"""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

# 1. Da Nang Normalization & Quality Gates
def test_danang_normalization_and_quality():
    norm_file = REPO_ROOT / "data" / "processed" / "osm" / "danang_normalized_v2.json"
    assert norm_file.exists()
    with open(norm_file, "r", encoding="utf-8") as f:
        pois = json.load(f)

    assert len(pois) == 2497, f"Expected 2497 candidates, got {len(pois)}"
    
    seen_sids = set()
    for p in pois:
        sid = p["source_id"]
        assert sid not in seen_sids, f"Duplicate source ID: {sid}"
        seen_sids.add(sid)

        # Coordinate bounds: [15.95, 107.95, 16.20, 108.35]
        lat, lon = p["latitude"], p["longitude"]
        assert 15.95 <= lat <= 16.20, f"Lat out of bounds: {lat}"
        assert 107.95 <= lon <= 108.35, f"Lon out of bounds: {lon}"

        # Human-readable name
        assert len(p["name"]) >= 2

        # Taxonomy V1.1 presence
        assert p["tier_1"] in (
            "FOOD_BEVERAGE", "HOSPITALITY", "ATTRACTIONS_LEISURE",
            "CULTURE_HERITAGE", "SHOPPING_COMMERCE", "NATURE_SCENERY", "TRANSPORT_HUBS"
        )
        assert p["tier_2"] is not None
        assert p["legacy_category"] is not None

        # Provenance envelope
        assert p["osm_type"] in ("node", "way", "relation")
        assert p["osm_id"] is not None
        assert p["osm_base"] is not None

        # Zero fabricated rating / review
        assert p["rating"] is None
        assert p["review_count"] == 0

# 2. Overture Cross-Check & Strict License Resolution
def test_danang_overture_crosscheck():
    ov_file = REPO_ROOT / "data" / "curated" / "overture" / "danang_overture_crosscheck_v2.json"
    assert ov_file.exists()
    with open(ov_file, "r", encoding="utf-8") as f:
        cross = json.load(f)

    assert len(cross) == 2497
    autolink_count = 0
    approved_licenses = {"CDLA Permissive 2.0", "Apache 2.0", "CC0 1.0"}

    for item in cross:
        status = item["status"]
        assert status in ("AUTO_LINK", "MANUAL_REVIEW_CANDIDATE", "UNMATCHED", "SOURCE_CONFLICT_REVIEW_REQUIRED")
        if status == "AUTO_LINK":
            autolink_count += 1
            m = item["overture_match"]
            assert m["distance_m"] <= 50.0
            assert m["similarity_score"] >= 0.90
            assert m["category_compatible"] is True
            assert m["operating_status"] != "permanently_closed"

            # Check that license is strictly in approved set
            lics = [l.strip() for l in m["license"].split(";")]
            for l in lics:
                assert l in approved_licenses, f"Unapproved license auto-linked: {l}"

    assert autolink_count == 549, f"Expected 549 AUTO_LINK, got {autolink_count}"

# 3. Freeze V1 Immutability
def test_freeze_v1_immutability():
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

# 4. Freeze V2 Checksum Integrity
def test_freeze_v2_checksum_integrity():
    v2_sha = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v2.sha256"
    assert v2_sha.exists()
    with open(v2_sha, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            exp_sha, rel_p = line.split(None, 1)
            target = REPO_ROOT / rel_p.strip()
            assert target.exists(), f"Freeze V2 file missing: {rel_p}"
            assert compute_sha256(target) == exp_sha, f"Freeze V2 checksum mismatch in {rel_p}!"

# 5. REC-A-CORE-V2 Item Universe
def test_reca_core_v2_item_universe():
    freeze_v2_file = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    assert freeze_v2_file.exists()
    with open(freeze_v2_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    assert len(places) == 759, f"Expected 759 total canonical places, got {len(places)}"

    rec_a_core = [p for p in places if p.get("is_rec_a_core_v2") is True]
    secondary = [p for p in places if p.get("is_rec_a_core_v2") is False]

    assert len(rec_a_core) == 626, f"Expected 626 REC-A-CORE-V2 places, got {len(rec_a_core)}"
    assert len(secondary) == 133, f"Expected 133 secondary places, got {len(secondary)}"

    # City breakdown in REC-A-CORE-V2
    city_counts = {}
    for p in rec_a_core:
        slug = p["destination_slug"]
        city_counts[slug] = city_counts.get(slug, 0) + 1

    assert city_counts.get("ha-noi") == 145, f"Expected 145 Hanoi, got {city_counts.get('ha-noi')}"
    assert city_counts.get("ha-long") == 188, f"Expected 188 Ha Long, got {city_counts.get('ha-long')}"
    assert city_counts.get("da-nang") == 293, f"Expected 293 Da Nang, got {city_counts.get('da-nang')}"
    assert set(city_counts.keys()) == {"ha-noi", "ha-long", "da-nang"}

    # Unique place IDs
    place_ids = [p["place_id"] for p in rec_a_core]
    assert len(place_ids) == len(set(place_ids)), "Duplicate place IDs in REC-A-CORE-V2!"

# 6. Research Corpus Invariants (No Google, No Tripadvisor, Rating None)
def test_research_corpus_invariants():
    freeze_v2_file = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    with open(freeze_v2_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    for p in places:
        assert p["rating"] is None, f"Found non-null rating in {p['name']}"
        assert p["review_count"] == 0, f"Found non-zero review_count in {p['name']}"

        sources = p.get("sources", [])
        has_osm = False
        for s in sources:
            s_name = s.get("source_name")
            assert s_name != "google", f"Google source found in place {p['name']}!"
            assert s_name != "tripadvisor", f"Tripadvisor source found in place {p['name']}!"
            if s_name == "osm":
                has_osm = True
        assert has_osm, f"Place {p['name']} lacks verified OSM source!"

# 7. WP-PROF Canonical Preference Dimensions Mapping
def test_wp_prof_canonical_interests_coverage():
    freeze_v2_file = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    with open(freeze_v2_file, "r", encoding="utf-8") as f:
        places = json.load(f)

    dn_places = [p for p in places if p["destination_slug"] == "da-nang"]

    # Mapping contract from WP-PROF / REC-A-V1
    interest_counts = {
        "food_cuisine": sum(1 for p in dn_places if p["category"] in ("restaurant", "food")),
        "culture_history": sum(1 for p in dn_places if p["category"] in ("culture", "museum", "temple")),
        "nature_outdoor": sum(1 for p in dn_places if p["category"] in ("nature", "park", "attraction")),
        "coffee_culture": sum(1 for p in dn_places if p["category"] == "cafe"),
        "beach_island": sum(1 for p in dn_places if p["category"] == "beach"),
        "shopping_local": sum(1 for p in dn_places if p["category"] == "market"),
        "nightlife_entertainment": sum(1 for p in dn_places if p["category"] in ("nightlife", "entertainment"))
    }

    print("\nDa Nang WP-PROF Interest Coverage:")
    for interest, count in interest_counts.items():
        print(f"  {interest:25s}: {count}")
        assert count > 0, f"Preference {interest} has 0 coverage in Da Nang verified corpus!"

# 8. Live Database Invariants
def test_live_database_invariants():
    import asyncpg
    async def run_check():
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            total_places = await conn.fetchval("SELECT count(*) FROM places WHERE deleted_at IS NULL")
            total_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
            total_docs = await conn.fetchval("SELECT count(*) FROM documents")
            osm_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
            wiki_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
            non_null_rating = await conn.fetchval("SELECT count(*) FROM places WHERE rating IS NOT NULL")

            hanoi_osm = await conn.fetchval("""
                SELECT count(*) FROM places p
                JOIN place_sources ps ON p.id = ps.place_id
                JOIN destinations d ON p.destination_id = d.id
                WHERE ps.source_name = 'osm' AND d.slug = 'ha-noi' AND p.deleted_at IS NULL
            """)
            halong_osm = await conn.fetchval("""
                SELECT count(*) FROM places p
                JOIN place_sources ps ON p.id = ps.place_id
                JOIN destinations d ON p.destination_id = d.id
                WHERE ps.source_name = 'osm' AND d.slug = 'ha-long' AND p.deleted_at IS NULL
            """)
            danang_osm = await conn.fetchval("""
                SELECT count(*) FROM places p
                JOIN place_sources ps ON p.id = ps.place_id
                JOIN destinations d ON p.destination_id = d.id
                WHERE ps.source_name = 'osm' AND d.slug = 'da-nang' AND p.deleted_at IS NULL
            """)

            assert total_places == 882
            assert total_osm == 759
            assert osm_docs == 759
            assert wiki_docs == 464
            assert total_docs == 759 + 464
            assert non_null_rating == 0
            assert hanoi_osm == 145
            assert halong_osm == 188
            assert danang_osm == 293
            assert (hanoi_osm + halong_osm + danang_osm) == 626

        finally:
            await conn.close()

    asyncio.run(run_check())
