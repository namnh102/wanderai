#!/usr/bin/env python3
"""DATA-02 Freeze Manifest Generator.

Exports the canonical frozen places snapshot from the local database,
verifies all immutable file artifacts, reads live database counts, and generates:
- data/manifests/dataset-freeze-v1.yaml
- data/manifests/dataset-freeze-v1.sha256
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
logger = logging.getLogger("freeze_manifest")

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
    print("GENERATING DATASET FREEZE V1 MANIFEST (LIVE DB DRIVEN)")
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

        print("LIVE DATABASE COUNTS:")
        print(f"- Total Active Places:            {live_places}")
        print(f"- Verified OSM Sources:          {live_osm_sources}")
        print(f"- Auxiliary Overture Sources:    {live_ov_sources}")
        print(f"- Total Documents:               {live_total_docs}")
        print(f"  - OSM Documents:               {live_osm_docs}")
        print(f"  - Wikivoyage Documents:        {live_wiki_docs}")
        print(f"- Places with Non-Null Rating:   {live_non_null_rating}")

        # Automated Assertions
        assert live_osm_docs == live_osm_sources, \
            f"Integrity failure: osm_documents ({live_osm_docs}) != verified_osm_sources ({live_osm_sources})"
        assert live_wiki_docs == 464, \
            f"Integrity failure: wikivoyage_documents ({live_wiki_docs}) != 464"
        assert live_total_docs == live_osm_docs + live_wiki_docs, \
            f"Integrity failure: total_documents ({live_total_docs}) != sum ({live_osm_docs + live_wiki_docs})"
        assert live_non_null_rating == 0, \
            f"Invariant violation: places_with_non_null_rating ({live_non_null_rating}) != 0"

        print("\n[ALL LIVE DB ASSERTIONS PASS]")

        # Export canonical verified places & sources snapshot
        print("Exporting canonical verified places from DB...")
        rows = await conn.fetch("""
            SELECT p.id::text as place_id, p.name, p.address, p.latitude, p.longitude,
                   p.opening_hours, p.rating, p.review_count,
                   c.name as category, d.name as destination, d.slug as destination_slug,
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

        curated_places_file = curated_dir / "gomate_places_freeze_v1.json"
        with open(curated_places_file, "w", encoding="utf-8") as f:
            json.dump(places_export, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(places_export)} canonical verified places to: {curated_places_file.relative_to(repo_root)}")

    finally:
        await conn.close()

    # 2. Collect artifacts to freeze (split into committed artifacts vs local restricted dependencies)
    committed_artifacts = [
        # Raw OSM queries & snapshots
        "data/queries/osm/hanoi_v1.overpassql",
        "data/queries/osm/halong_v1.overpassql",
        "data/raw/osm/hanoi_2026-10-07.json",
        "data/raw/osm/halong_2026-10-07.json",
        "data/raw/osm/collection_metadata_2026-10-07.json",

        # Normalized OSM candidates
        "data/processed/osm/hanoi_normalized_v1.json",
        "data/processed/osm/halong_normalized_v1.json",
        "data/processed/osm/normalization_quality_stats_2026-10-07.json",

        # Curated Overture Cross-Checks
        "data/curated/overture/halong_overture_crosscheck_v1.json",
        "data/curated/overture/hanoi_overture_crosscheck_v1.json",
        "data/curated/overture/overture_crosscheck_summary_2026-10-07.json",

        # Exported Curated Places Snapshot
        "data/curated/gomate_places_freeze_v1.json",

        # Research Synthetic Preferences
        "data/research/preferences/synthetic_preferences_v1.jsonl",
        "data/evaluation/synthetic/preferences_n300_seed42.json",
        "data/research/preferences/synthetic_preferences_distribution_v1.json",

        # Disaster recovery & dry-run plan
        "data/manifests/db_import_plan_v1.json",
        "data/manifests/pre_data02_rollback_state.json"
    ]

    restricted_dependencies = [
        # Local Restricted Benchmark ViHoRec (Read-Only, untracked by Git)
        "data/restricted/vihorec/hotels.csv",
        "data/restricted/vihorec/interactions.csv",
        "data/restricted/vihorec/users.csv",
        "data/restricted/vihorec/train.csv",
        "data/restricted/vihorec/val.csv",
        "data/restricted/vihorec/test.csv"
    ]

    manifest_committed = []
    manifest_restricted = []
    sha256_lines = []

    for rel_path in committed_artifacts:
        file_path = repo_root / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"Missing committed artifact: {file_path}")
        file_bytes = file_path.stat().st_size
        file_sha = compute_sha256(file_path)
        sha256_lines.append(f"{file_sha}  {rel_path.replace(chr(92), '/')}")
        manifest_committed.append({
            "path": rel_path.replace("\\", "/"),
            "bytes": file_bytes,
            "sha256": file_sha
        })

    for rel_path in restricted_dependencies:
        file_path = repo_root / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"Missing restricted dependency: {file_path}")
        file_bytes = file_path.stat().st_size
        file_sha = compute_sha256(file_path)
        sha256_lines.append(f"{file_sha}  {rel_path.replace(chr(92), '/')}")
        manifest_restricted.append({
            "path": rel_path.replace("\\", "/"),
            "bytes": file_bytes,
            "sha256": file_sha,
            "governance": "LOCAL_RESTRICTED_DEPENDENCY (Git-Ignored, Verified by SHA256)"
        })

    # Write .sha256 file
    sha256_file = manifests_dir / "dataset-freeze-v1.sha256"
    with open(sha256_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sha256_lines) + "\n")

    # Build YAML manifest with live DB counts
    now_utc = datetime.now(timezone.utc).isoformat()
    manifest_data = {
        "dataset_freeze_version": "v1.0.0",
        "created_at_utc": now_utc,
        "branch": "feature/data-foundation-w2",
        "git_commit": "82619409d3040e3ccd7aa5755e349510ca002e91",
        "canonical_geography": {
            "hanoi": {
                "bbox": [20.95, 105.75, 21.15, 105.95],
                "verified_poi_count": 145,
                "osm_base_timestamp": "2026-10-07T09:52:02Z",
                "overpass_endpoint": "https://overpass-api.de/api/interpreter"
            },
            "halong": {
                "bbox": [20.85, 106.95, 21.05, 107.25],
                "verified_poi_count": 188,
                "osm_base_timestamp": "2026-10-07T09:52:02Z",
                "overpass_endpoint": "https://overpass-api.de/api/interpreter"
            }
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
            "halong_matched_auto": 51,
            "hanoi_matched_auto": 1118,
            "db_auxiliary_linked_sources": live_ov_sources
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
        "committed_immutable_artifacts": manifest_committed,
        "local_restricted_dependencies": manifest_restricted
    }

    yaml_file = manifests_dir / "dataset-freeze-v1.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f, sort_keys=False, allow_unicode=True)

    print(f"\n[PASS] Freeze Manifest Saved: {yaml_file.relative_to(repo_root)}")
    print(f"[PASS] SHA-256 Digest Saved: {sha256_file.relative_to(repo_root)}")
    print(f"       Committed Artifacts:     {len(manifest_committed)}")
    print(f"       Restricted Dependencies: {len(manifest_restricted)}")

if __name__ == "__main__":
    asyncio.run(main())
