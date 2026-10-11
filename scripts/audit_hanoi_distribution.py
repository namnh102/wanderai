#!/usr/bin/env python3
"""DATA-02-R1 Hanoi Verified POI Distribution Audit.

Audits category distribution and selection evidence for the 145 verified Hanoi POIs.
"""

import asyncio
import os
import sys
from collections import Counter
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT p.id::text, p.name, c.name as category, p.latitude, p.longitude, p.created_at
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE d.slug = 'ha-noi' AND ps.source_name = 'osm' AND p.deleted_at IS NULL
            ORDER BY c.name, p.name
        """)

        print(f"Total verified Hanoi POIs: {len(rows)}")
        counts = Counter(r["category"] for r in rows)
        for cat, cnt in counts.most_common():
            pct = (cnt / len(rows)) * 100.0
            print(f"- {cat:15s}: {cnt:3d} ({pct:5.1f}%)")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
