#!/usr/bin/env python3
"""DATA-02 / MVP-SCOPE-01 Freeze Manifest Generator (V2).

Exports the canonical frozen places snapshot for Freeze V2 (Hanoi + Da Nang + Ha Long),
verifies all immutable file artifacts, reads live database counts, and generates:
- data/curated/gomate_places_freeze_v2.json
- data/manifests/dataset-freeze-v2.yaml
- data/manifests/dataset-freeze-v2.sha256

Strict Invariants:
- Never modifies dataset-freeze-v1.yaml or dataset-freeze-v1.sha256.
- Preserves 100% Freeze V1 hash integrity.
- Live database assertions enforce:
  osm_documents == verified_osm_sources (759)
  wikivoyage_documents == 464
  places_with_non_null_rating == 0
  Hanoi = 145, Ha Long = 188, Da Nang = 293
  REC-A-CORE-V2 = 626
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import asyncpg
import yaml

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("freeze_manifest_v2")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

async def main():
    repo_root = Path(__file__).resolve().parent.parent
    curated_dir = repo_root / "data" / "curated"
    manifests_dir = repo_root / "data" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("GENERATING DATASET FREEZE V2 MANIFEST (LIVE DB DRIVEN)")
    print("=" * 70)

    # 1. Connect to PostgreSQL and fetch live DB metrics & export places
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Live DB counts
        live_places = await conn.fetchval("SELECT count(*) FROM places WHERE deleted_at IS NULL")
        live_osm_sources = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        live_ov_sources = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'overture'")
        live_total_docs = await conn.fetchval("SELECT count(*) FROM documents")
        live_osm_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
        live_wiki_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
        live_non_null_rating = await conn.fetchval("SELECT count(*) FROM places WHERE rating IS NOT NULL")

        hanoi_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'ha-noi'")
        halong_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'ha-long'")
        danang_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'da-nang'")

        hanoi_osm = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1 AND p.deleted_at IS NULL
        """, hanoi_id)
        halong_osm = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1 AND p.deleted_at IS NULL
        """, halong_id)
        danang_osm = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1 AND p.deleted_at IS NULL
        """, danang_id)

        rec_a_core_v2_total = hanoi_osm + halong_osm + danang_osm
        secondary_osm = live_osm_sources - rec_a_core_v2_total

        print("LIVE DATABASE COUNTS:")
        print(f"- Total Active Places:            {live_places}")
        print(f"- Verified OSM Sources:          {live_osm_sources}")
        print(f"  - Hanoi:                       {hanoi_osm} (Locked Canonical)")
        print(f"  - Da Nang:                     {danang_osm} (Locked Canonical V2)")
        print(f"  - Ha Long:                     {halong_osm} (Locked Canonical)")
        print(f"  - REC-A-CORE-V2 Total:         {rec_a_core_v2_total}")
        print(f"  - Secondary Research POIs:     {secondary_osm} (Hoi An, Hue, Nha Trang)")
        print(f"- Auxiliary Overture Sources:    {live_ov_sources}")
        print(f"- Total Documents:               {live_total_docs}")
        print(f"  - OSM Documents:               {live_osm_docs}")
        print(f"  - Wikivoyage Documents:        {live_wiki_docs}")
        print(f"- Places with Non-Null Rating:   {live_non_null_rating}")

        # Automated Integrity Assertions
        assert live_osm_docs == live_osm_sources, \
            f"Integrity failure: osm_documents ({live_osm_docs}) != verified_osm_sources ({live_osm_sources})"
        assert live_wiki_docs == 464, \
            f"Integrity failure: wikivoyage_documents ({live_wiki_docs}) != 464"
        assert live_total_docs == live_osm_docs + live_wiki_docs, \
            f"Integrity failure: total_documents ({live_total_docs}) != sum ({live_osm_docs + live_wiki_docs})"
        assert live_non_null_rating == 0, \
            f"Invariant violation: places_with_non_null_rating ({live_non_null_rating}) != 0"
        assert hanoi_osm == 145, f"Expected 145 Hanoi OSM, got {hanoi_osm}"
        assert halong_osm == 188, f"Expected 188 Ha Long OSM, got {halong_osm}"
        assert danang_osm == 293, f"Expected 293 Da Nang OSM, got {danang_osm}"
        assert rec_a_core_v2_total == 626, f"Expected 626 REC-A-CORE-V2 total, got {rec_a_core_v2_total}"

        print("\n[ALL LIVE DB INTEGRITY ASSERTIONS PASS]")

        # Export canonical verified places & sources snapshot for Freeze V2
        print("Exporting canonical verified places from DB to gomate_places_freeze_v2.json...")
        rows = await conn.fetch("""
            SELECT p.id::text as place_id, p.name, p.address, p.latitude, p.longitude,
                   p.opening_hours, p.rating, p.review_count,
                   c.name as category, d.name as destination, d.slug as destination_slug,
                   (d.slug IN ('ha-noi', 'da-nang', 'ha-long')) as is_rec_a_core_v2,
                   json_agg(json_build_object(
                       'source_name', ps.source_name,
                       'source_id', ps.source_id,
                       'confidence_score', ps.confidence_score,
                       'raw_data', ps.raw_data
                   )) as sources
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE p.deleted_at IS NULL AND EXISTS (
                SELECT 1 FROM place_sources ps2 WHERE ps2.place_id = p.id AND ps2.source_name = 'osm'
            )
            GROUP BY p.id, p.name, p.address, p.latitude, p.longitude, p.opening_hours,
                     p.rating, p.review_count, c.name, d.name, d.slug
            ORDER BY d.name, p.name
        """)

        places_export = []
        for r in rows:
            rec = dict(r)
            if isinstance(rec.get("sources"), str):
                rec["sources"] = json.loads(rec["sources"])
            places_export.append(rec)

        curated_places_file = curated_dir / "gomate_places_freeze_v2.json"
        with open(curated_places_file, "w", encoding="utf-8") as f:
            json.dump(places_export, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(places_export)} canonical verified places to: {curated_places_file.relative_to(repo_root)}")

    finally:
        await conn.close()

    # 2. Collect artifacts to freeze in V2
    # Include all Freeze V1 artifacts (inherited immutable) + new Da Nang V2 artifacts + Freeze V2 exports
    v2_artifacts = [
        # Inherited V1 queries & raw snapshots
        "data/queries/osm/hanoi_v1.overpassql",
        "data/queries/osm/halong_v1.overpassql",
        "data/raw/osm/hanoi_2026-10-07.json",
        "data/raw/osm/halong_2026-10-07.json",
        "data/raw/osm/collection_metadata_2026-10-07.json",
        "data/processed/osm/hanoi_normalized_v1.json",
        "data/processed/osm/halong_normalized_v1.json",
        "data/processed/osm/normalization_quality_stats_2026-10-07.json",
        "data/curated/overture/halong_overture_crosscheck_v1.json",
        "data/curated/overture/hanoi_overture_crosscheck_v1.json",
        "data/curated/overture/overture_crosscheck_summary_2026-10-07.json",
        "data/curated/gomate_places_freeze_v1.json",
        "data/research/preferences/synthetic_preferences_v1.jsonl",
        "data/evaluation/synthetic/preferences_n300_seed42.json",
        "data/research/preferences/synthetic_preferences_distribution_v1.json",
        "data/manifests/db_import_plan_v1.json",
        "data/manifests/pre_data02_rollback_state.json",

        # New Da Nang V2 artifacts
        "data/queries/osm/danang_v2.overpassql",
        "data/raw/osm/danang_2026-10-07_v2.json",
        "data/raw/osm/danang_collection_metadata_2026-10-07_v2.json",
        "data/processed/osm/danang_normalized_v2.json",
        "data/processed/osm/danang_normalization_quality_stats_v2.json",
        "data/curated/overture/danang_overture_crosscheck_v2.json",
        "data/curated/overture/danang_overture_crosscheck_summary_v2.json",
        "data/manifests/danang_coordinate_drift_stats_v2.json",
        "data/manifests/db_import_plan_danang_v2.json",
        "data/curated/gomate_places_freeze_v2.json",

        # ViHoRec benchmark files
        "data/restricted/vihorec/hotels.csv",
        "data/restricted/vihorec/interactions.csv",
        "data/restricted/vihorec/users.csv",
        "data/restricted/vihorec/train.csv",
        "data/restricted/vihorec/val.csv",
        "data/restricted/vihorec/test.csv"
    ]

    manifest_entries = []
    sha_lines = []

    print("\nComputing SHA-256 for Freeze V2 artifacts...")
    for rel_path in v2_artifacts:
        full_path = repo_root / rel_path
        if not full_path.exists():
            raise FileNotFoundError(f"Missing required artifact: {full_path}")
        size = full_path.stat().st_size
        sha = compute_sha256(full_path)
        clean_path = rel_path.replace("\\", "/")
        manifest_entries.append({
            "path": clean_path,
            "bytes": size,
            "sha256": sha
        })
        sha_lines.append(f"{sha}  {clean_path}")
        print(f"  {rel_path:60s} ({size:9d} bytes) sha256={sha[:16]}...")

    # Write SHA-256 checksum manifest
    sha_manifest_file = manifests_dir / "dataset-freeze-v2.sha256"
    with open(sha_manifest_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sha_lines) + "\n")
    print(f"\n[PASS] SHA-256 manifest written to: {sha_manifest_file.relative_to(repo_root)}")

    # 3. Build comprehensive YAML manifest
    now_utc = datetime.now(timezone.utc).isoformat()
    manifest_data = {
        "dataset_freeze_version": "v2.0.0",
        "parent_source_dataset": "v1.0.0 (dataset-freeze-v1.yaml)",
        "created_at_utc": now_utc,
        "branch": "feature/mvp-three-city-freeze-v2",
        "base_commit": "b661c6b",
        "canonical_geography": {
            "hanoi": {
                "destination_id": str(hanoi_id),
                "bbox": [20.95, 105.75, 21.15, 105.95],
                "verified_poi_count": hanoi_osm,
                "osm_base_timestamp": "2026-10-07T09:52:02Z",
                "overpass_endpoint": "https://overpass-api.de/api/interpreter",
                "status": "PRESERVED_FROZEN_V1"
            },
            "danang": {
                "destination_id": str(danang_id),
                "bbox": [15.95, 107.95, 16.20, 108.35],
                "verified_poi_count": danang_osm,
                "raw_elements_count": 2497,
                "normalized_candidates_count": 2497,
                "osm_base_timestamp": "2026-10-07T15:18:56Z",
                "collection_timestamp_utc": "2026-10-07T15:21:09.983Z",
                "overpass_endpoint": "https://overpass-api.de/api/interpreter",
                "curation_rule": "Deterministic Curation: Baseline preservation (114) + Transport Hubs + Core categories (Culture, Nature, Attractions, Shopping with AUTO-LINK or contact) + Hospitality & Dining with AUTO-LINK and contact",
                "status": "FRESH_COLLECTED_V2"
            },
            "halong": {
                "destination_id": str(halong_id),
                "bbox": [20.85, 106.95, 21.05, 107.25],
                "verified_poi_count": halong_osm,
                "osm_base_timestamp": "2026-10-07T09:52:02Z",
                "overpass_endpoint": "https://overpass-api.de/api/interpreter",
                "status": "PRESERVED_FROZEN_V1"
            }
        },
        "item_universe": {
            "rec_a_core_v2": {
                "destinations": ["hanoi", "danang", "halong"],
                "hanoi_count": hanoi_osm,
                "danang_count": danang_osm,
                "halong_count": halong_osm,
                "total_items": rec_a_core_v2_total,
                "role": "Primary Thesis / Product MVP evaluation universe (W4/W5)"
            },
            "secondary_research_corpus": {
                "destinations": ["hoi-an", "hue", "nha-trang"],
                "total_items": secondary_osm,
                "role": "Exploratory generalization research (excluded from primary 3-city metrics)"
            },
            "total_canonical_places": live_places,
            "total_verified_osm_places": live_osm_sources
        },
        "taxonomy_version": "v1.1.0",
        "database_state": {
            "total_places": live_places,
            "total_verified_osm_sources": live_osm_sources,
            "total_auxiliary_overture_sources": live_ov_sources,
            "total_documents": live_total_docs,
            "osm_documents": live_osm_docs,
            "wikivoyage_documents": live_wiki_docs,
            "places_with_non_null_rating": live_non_null_rating
        },
        "overture_secondary_crosscheck": {
            "release": "2026-09-23.1",
            "schema_version": "v2.0.0",
            "licensing": "Multi-License (CDLA Permissive 2.0 / Apache 2.0 / CC0 1.0)",
            "danang_overture_records_indexed": 65688,
            "danang_matched_auto": 549,
            "danang_manual_candidates": 504,
            "danang_unmatched": 1444,
            "danang_license_unresolved": 0,
            "danang_operating_conflicts": 0,
            "db_auxiliary_linked_sources": live_ov_sources
        },
        "coordinate_drift_consistency": {
            "danang_verified_corpus_count": danang_osm,
            "median_drift_m": 0.0,
            "p95_drift_m": 0.0,
            "max_drift_m": 0.0,
            "drift_gt_5m": 0,
            "drift_gt_20m": 0,
            "drift_gt_100m": 0
        },
        "preference_contract": {
            "contract_version": "WP-PROF-01 / REC-A-V1",
            "canonical_interests": [
                "food_cuisine",
                "culture_history",
                "nature_outdoor",
                "coffee_culture",
                "beach_island",
                "shopping_local",
                "nightlife_entertainment"
            ],
            "vocabulary_status": "PRESERVED_UNCHANGED"
        },
        "governance_and_compliance": {
            "google_maps": "EXCLUDED from research corpus; future official API runtime enrichment only",
            "tripadvisor": "EXCLUDED from research corpus; UX reference only",
            "vlsp_2018": "EXCLUDED; ACCESS_PENDING_DUA",
            "ratings_invariants": "All places.rating == NULL; zero synthetic reviews"
        },
        "synthetic_preferences": {
            "population_size": 300,
            "seed": 42,
            "generator_version": "preference-v1",
            "is_synthetic": True,
            "target_role": "Offline Recommender (REC-A) Evaluation"
        },
        "vihorec_benchmark": {
            "upstream_release": "1.0.0",
            "classification": "CURRENT_OFFICIAL",
            "interactions": 17911,
            "users": 6822,
            "hotels": 560,
            "governance": "LOCAL_RESTRICTED_RESEARCH_DEPENDENCY (Git-Ignored, Verified by SHA256)"
        },
        "committed_immutable_artifacts": manifest_entries
    }

    yaml_manifest_file = manifests_dir / "dataset-freeze-v2.yaml"
    with open(yaml_manifest_file, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f, sort_keys=False, allow_unicode=True, indent=2)

    print(f"[PASS] YAML manifest written to: {yaml_manifest_file.relative_to(repo_root)}")

    # 4. Final verification: Verify Freeze V1 SHA256 manifest is 100% matched
    print("\nVerifying Freeze V1 integrity against data/manifests/dataset-freeze-v1.sha256...")
    v1_sha_file = manifests_dir / "dataset-freeze-v1.sha256"
    v1_ok = True
    with open(v1_sha_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            exp_hash, rel_p = line.split(None, 1)
            p = repo_root / rel_p.strip()
            act_hash = compute_sha256(p)
            if exp_hash != act_hash:
                print(f"[FAIL] Freeze V1 mismatch: {rel_p}")
                v1_ok = False
    assert v1_ok, "Freeze V1 integrity check failed!"
    print("[PASS] Freeze V1 remains 100% byte-for-byte identical!")

if __name__ == "__main__":
    asyncio.run(main())
