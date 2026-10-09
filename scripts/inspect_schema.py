#!/usr/bin/env python3
import asyncio
import os
import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    tables = ["places", "place_sources", "place_source_quarantine", "documents", "document_quarantine", "dataset_registry"]
    for t in tables:
        print(f"\n--- TABLE: {t} ---")
        cols = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1 ORDER BY ordinal_position",
            t
        )
        for c in cols:
            print(f"  {c['column_name']}: {c['data_type']}")
    
    print("\n--- DATASET_REGISTRY CONTENTS ---")
    rows = await conn.fetch("SELECT * FROM dataset_registry")
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
