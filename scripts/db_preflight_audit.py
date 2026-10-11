#!/usr/bin/env python3
"""DATA-02 Pre-flight database audit & rollback state exporter.

Records:
1. Counts of places, place_sources(osm), documents, dataset_registry
2. Checksums of existing curated artifacts
3. Exports current verified POI IDs and source IDs to rollback JSON
"""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/wanderai"
)

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

async def main():
    repo_root = Path(__file__).resolve().parent.parent
    rollback_dir = repo_root / "data" / "manifests"
    rollback_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("DATA-02 PRE-FLIGHT AUDIT & BASELINE CAPTURE")
    print("=" * 70)

    # 1. Existing curated artifact checksums
    curated_dir = repo_root / "data" / "curated"
    curated_checksums = {}
    if curated_dir.exists():
        for p in sorted(curated_dir.glob("*.json")):
            curated_checksums[p.name] = {
                "bytes": p.stat().st_size,
                "sha256": compute_sha256(p)
            }
            print(f"Curated Artifact: {p.name} ({p.stat().st_size} bytes, sha256={curated_checksums[p.name]['sha256'][:16]}...)")

    # 2. Database connection & counts
    print(f"\nConnecting to DB: {DATABASE_URL.rsplit('@', 1)[-1]} ...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        sys.exit(1)

    try:
        total_places = await conn.fetchval("SELECT count(*) FROM places")
        active_places = await conn.fetchval("SELECT count(*) FROM places WHERE deleted_at IS NULL")
        verified_osm_sources = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        total_place_sources = await conn.fetchval("SELECT count(*) FROM place_sources")
        total_documents = await conn.fetchval("SELECT count(*) FROM documents")
        documents_by_source = {
            r["source_name"]: r["n"]
            for r in await conn.fetch("SELECT source_name, count(*) as n FROM documents GROUP BY 1 ORDER BY 1")
        }
        total_datasets = await conn.fetchval("SELECT count(*) FROM dataset_registry")
        datasets_list = [
            dict(r) for r in await conn.fetch(
                "SELECT id::text, dataset_name, dataset_version, record_count, checksum, license, access_status FROM dataset_registry ORDER BY dataset_name"
            )
        ]

        # 3. Export verified POI IDs / place_sources for rollback evidence
        verified_pois = [
            dict(r) for r in await conn.fetch(
                """
                SELECT p.id::text as place_id, p.name, p.address, p.latitude, p.longitude,
                       p.rating, p.review_count, p.created_at,
                       ps.id::text as source_row_id, ps.source_name, ps.source_id, ps.raw_name,
                       ps.latitude as source_latitude, ps.longitude as source_longitude,
                       ps.confidence_score, ps.raw_data
                FROM places p
                JOIN place_sources ps ON p.id = ps.place_id
                WHERE ps.source_name = 'osm'
                ORDER BY p.id
                """
            )
        ]

        print("\nDATABASE BASELINE COUNTS:")
        print(f"- Total Places:            {total_places} (Active: {active_places})")
        print(f"- OSM Place Sources:       {verified_osm_sources}")
        print(f"- Total Place Sources:     {total_place_sources}")
        print(f"- Total Documents:         {total_documents} ({documents_by_source})")
        print(f"- Dataset Registry Entries: {total_datasets}")

        # Serialize datetime and json/dict
        def json_serial(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        rollback_payload = {
            "captured_at_utc": "2026-10-07T09:40:00Z",
            "git_commit": "871d890722c51a632b0a98cb32a1f1e83a767f11",
            "branch": "feature/data-foundation-w2",
            "db_counts": {
                "places_total": total_places,
                "places_active": active_places,
                "place_sources_osm": verified_osm_sources,
                "place_sources_total": total_place_sources,
                "documents_total": total_documents,
                "documents_by_source": documents_by_source,
                "dataset_registry_count": total_datasets,
            },
            "dataset_registry": datasets_list,
            "curated_artifact_checksums": curated_checksums,
            "verified_osm_places_count": len(verified_pois),
            "verified_osm_places": verified_pois,
        }

        out_path = rollback_dir / "pre_data02_rollback_state.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rollback_payload, f, default=json_serial, indent=2, ensure_ascii=False)

        print(f"\n[PASS] Rollback state saved to: {out_path} ({len(verified_pois)} verified POI associations preserved)")
        print(f"       Rollback state sha256: {compute_sha256(out_path)}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
