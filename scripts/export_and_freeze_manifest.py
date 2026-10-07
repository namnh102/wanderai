#!/usr/bin/env python3
"""DATA-02 Freeze Manifest Generator.

Exports the canonical frozen places snapshot from the local database,
verifies all immutable file artifacts, and generates:
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
    print("GENERATING DATASET FREEZE V1 MANIFEST")
    print("=" * 70)

    # 1. Export canonical verified places & sources snapshot
    print("Exporting canonical verified places from DB...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
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

    # 2. Collect artifacts to freeze
    artifacts_to_freeze = [
        # Raw OSM queries & snapshots
        "data/queries/osm/hanoi_v1.overpassql",
        "data/queries/osm/halong_v1.overpassql",
        "data/raw/osm/hanoi_2026-10-07.json",
        "data/raw/osm/halong_2026-10-07.json",
        "data/raw/osm/collection_metadata_2026-10-07.json",

        # Bounded Overture slices
        "data/raw/overture/overture_halong_2026-09-23.1.parquet",
        "data/raw/overture/overture_hanoi_2026-09-23.1.parquet",

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

        # Frozen Benchmark ViHoRec (Read-Only)
        "data/restricted/vihorec/hotels.csv",
        "data/restricted/vihorec/interactions.csv",
        "data/restricted/vihorec/users.csv",
        "data/restricted/vihorec/train.csv",
        "data/restricted/vihorec/val.csv",
        "data/restricted/vihorec/test.csv"
    ]

    manifest_entries = []
    sha256_lines = []

    for rel_path in artifacts_to_freeze:
        file_path = repo_root / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"Missing artifact to freeze: {file_path}")

        file_bytes = file_path.stat().st_size
        file_sha = compute_sha256(file_path)
        sha256_lines.append(f"{file_sha}  {rel_path.replace(chr(92), '/')}")

        manifest_entries.append({
            "path": rel_path.replace("\\", "/"),
            "bytes": file_bytes,
            "sha256": file_sha
        })

    # Write .sha256 file
    sha256_file = manifests_dir / "dataset-freeze-v1.sha256"
    with open(sha256_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sha256_lines) + "\n")

    # Build YAML manifest
    now_utc = datetime.now(timezone.utc).isoformat()
    manifest_data = {
        "dataset_freeze_version": "v1.0.0",
        "created_at_utc": now_utc,
        "branch": "feature/data-foundation-w2",
        "git_commit": "871d890722c51a632b0a98cb32a1f1e83a767f11",
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
            "total_places": 703,
            "total_verified_osm_sources": 580,
            "total_auxiliary_overture_sources": 89,
            "total_documents": 1009,
            "osm_documents": 545,
            "wikivoyage_documents": 464,
            "places_with_non_null_rating": 0
        },
        "overture_secondary_crosscheck": {
            "release": "2026-09-23.1",
            "schema_version": "v2.0.0",
            "licensing": "Multi-License (CDLA Permissive 2.0 / Apache 2.0 / CC0 1.0)",
            "halong_matched_auto": 51,
            "hanoi_matched_auto": 1112
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
            "hotels": 560
        },
        "immutable_artifacts": manifest_entries
    }

    yaml_file = manifests_dir / "dataset-freeze-v1.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f, sort_keys=False, allow_unicode=True)

    print(f"\n[PASS] Freeze Manifest Saved: {yaml_file.relative_to(repo_root)}")
    print(f"[PASS] SHA-256 Digest Saved: {sha256_file.relative_to(repo_root)}")
    print(f"       Total frozen artifacts: {len(manifest_entries)}")

if __name__ == "__main__":
    asyncio.run(main())
