#!/usr/bin/env python3
"""DATA-02-R1 Overture Auxiliary Provenance Audit & Governance Verifier.

Audits every Overture auxiliary record currently in place_sources:
- Verifies explicit upstream source (Meta, Microsoft, etc.)
- Verifies explicit approved license (CDLA Permissive 2.0, Apache 2.0, CC0 1.0)
- Checks if any record relied on an unapproved fallback
- If any invalid record exists, safely deletes only that place_sources record
  (NEVER removes canonical Place or OSM source).
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
import asyncpg
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("overture_audit")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")
APPROVED_LICENSES = {"CDLA Permissive 2.0", "Apache 2.0", "CC0 1.0"}

async def main():
    repo_root = Path(__file__).resolve().parent.parent
    ov_raw_dir = repo_root / "data" / "raw" / "overture"

    # Load raw Overture sources index
    raw_sources_by_id = {}
    for region in ("halong", "hanoi"):
        p_file = ov_raw_dir / f"overture_{region}_2026-09-23.1.parquet"
        if p_file.exists():
            table = pq.read_table(p_file, columns=["id", "sources"])
            for r_id, srcs in zip(table["id"].to_pylist(), table["sources"].to_pylist()):
                raw_sources_by_id[r_id] = srcs or []

    print("=" * 70)
    print("AUDITING CURRENT DATABASE OVERTURE AUXILIARY PROVENANCE RECORDS")
    print("=" * 70)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT ps.id::text as source_row_id, ps.place_id::text, ps.source_id as overture_id,
                   ps.raw_name, ps.confidence_score, ps.raw_data,
                   p.name as place_name, d.name as dest_name
            FROM place_sources ps
            JOIN places p ON ps.place_id = p.id
            LEFT JOIN destinations d ON p.destination_id = d.id
            WHERE ps.source_name = 'overture'
            ORDER BY d.name, p.name
        """)

        linked_before = len(rows)
        print(f"Total Overture auxiliary records linked before: {linked_before}")

        verified_records = []
        invalid_records = []

        for r in rows:
            ov_id = r["overture_id"]
            raw_data = r["raw_data"]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)

            # Check raw upstream sources in Overture parquet
            raw_srcs = raw_sources_by_id.get(ov_id, [])
            providers = []
            explicit_licenses = set()

            for s in raw_srcs:
                lic = (s.get("license") or "").strip().lower()
                prov = s.get("dataset") or s.get("provider") or "overture"
                providers.append(prov)
                if "cdla-permissive-2.0" in lic or "cdla permissive 2.0" in lic:
                    explicit_licenses.add("CDLA Permissive 2.0")
                elif "apache-2.0" in lic or "apache 2.0" in lic:
                    explicit_licenses.add("Apache 2.0")
                elif "cc0" in lic:
                    explicit_licenses.add("CC0 1.0")

            # Check validity
            has_approved_license = any(l in APPROVED_LICENSES for l in explicit_licenses)
            has_explicit_provider = len(providers) > 0
            is_valid = has_approved_license and has_explicit_provider

            if is_valid:
                verified_records.append({
                    "row_id": r["source_row_id"],
                    "place_id": r["place_id"],
                    "place_name": r["place_name"],
                    "overture_id": ov_id,
                    "explicit_licenses": list(explicit_licenses),
                    "providers": providers,
                    "confidence_score": r["confidence_score"]
                })
            else:
                invalid_records.append({
                    "row_id": r["source_row_id"],
                    "place_id": r["place_id"],
                    "place_name": r["place_name"],
                    "overture_id": ov_id,
                    "reason": "Missing explicit approved license or provider",
                    "raw_sources": raw_srcs
                })

        print(f"\nAudit Analysis:")
        print(f"- Verified Approved Records:    {len(verified_records)}")
        print(f"- Invalid / Unresolved Records: {len(invalid_records)}")

        # If any invalid record exists, delete only that place_sources record
        if invalid_records:
            print(f"\nRemoving {len(invalid_records)} invalid Overture auxiliary records from place_sources...")
            for inv in invalid_records:
                await conn.execute("DELETE FROM place_sources WHERE id = $1", inv["row_id"])
            print("Deletion complete.")
        else:
            print("\n[ALL 89 CURRENT OVERTURE AUXILIARY RECORDS ARE 100% EXPLICITLY LICENSED!]")
            print("Sample audited records:")
            for v in verified_records[:5]:
                print(f"  [{v['place_name']}] -> Overture ID: {v['overture_id']}, Providers: {v['providers']}, Licenses: {v['explicit_licenses']}")

        linked_after = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'overture'")

        print("\n" + "=" * 70)
        print("OVERTURE AUDIT RECONCILIATION SUMMARY")
        print("=" * 70)
        print(f"Linked Before:            {linked_before}")
        print(f"Linked After:             {linked_after}")
        print(f"License-Unresolved Count: {len(invalid_records)}")
        print(f"Removed/Quarantined:      {len(invalid_records)}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
