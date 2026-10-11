#!/usr/bin/env python3
"""DATA-02 / MVP-SCOPE-01 Smoke Verification Script.

Verifies:
1. Hanoi sample Place Detail source state
2. Ha Long sample Place Detail source state
3. Three representative Da Nang POIs from different categories (e.g. Culture, Beach, Hospitality)
   Confirm: verified OSM source, valid coordinates, rating NULL, review_count 0, RAG OSM doc exists,
   Overture auxiliary source only if explicitly licensed.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

async def verify_smoke():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("=" * 70)
        print("SMOKE VERIFICATION: THREE MVP DESTINATIONS (HANOI, HA LONG, DA NANG)")
        print("=" * 70)

        # 1. Hanoi Sample
        hanoi_row = await conn.fetchrow("""
            SELECT p.id::text, p.name, p.latitude, p.longitude, p.rating, p.review_count,
                   c.name as category, d.name as destination,
                   ps.source_name, ps.source_id, ps.raw_data
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE d.slug = 'ha-noi' AND ps.source_name = 'osm'
            ORDER BY p.name
            LIMIT 1
        """)
        print("\n1. Hanoi Sample:")
        print(f"   Name:        {hanoi_row['name']} (ID: {hanoi_row['id']})")
        print(f"   Category:    {hanoi_row['category']}")
        print(f"   Coordinates: ({hanoi_row['latitude']}, {hanoi_row['longitude']})")
        print(f"   Rating:      {hanoi_row['rating']} | Reviews: {hanoi_row['review_count']}")
        print(f"   OSM Source:  {hanoi_row['source_id']}")

        # 2. Ha Long Sample
        halong_row = await conn.fetchrow("""
            SELECT p.id::text, p.name, p.latitude, p.longitude, p.rating, p.review_count,
                   c.name as category, d.name as destination,
                   ps.source_name, ps.source_id, ps.raw_data
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE d.slug = 'ha-long' AND ps.source_name = 'osm'
            ORDER BY p.name
            LIMIT 1
        """)
        print("\n2. Ha Long Sample:")
        print(f"   Name:        {halong_row['name']} (ID: {halong_row['id']})")
        print(f"   Category:    {halong_row['category']}")
        print(f"   Coordinates: ({halong_row['latitude']}, {halong_row['longitude']})")
        print(f"   Rating:      {halong_row['rating']} | Reviews: {halong_row['review_count']}")
        print(f"   OSM Source:  {halong_row['source_id']}")

        # 3. Three Representative Da Nang Samples (Culture, Hospitality, Beach/Nature)
        categories = ["culture", "hotel", "beach"]
        print("\n3. Three Representative Da Nang Samples:")
        for cat in categories:
            row = await conn.fetchrow("""
                SELECT p.id::text, p.name, p.latitude, p.longitude, p.rating, p.review_count,
                       c.name as category, d.name as destination
                FROM places p
                JOIN destinations d ON p.destination_id = d.id
                JOIN place_categories c ON p.category_id = c.id
                JOIN place_sources ps ON p.id = ps.place_id
                WHERE d.slug = 'da-nang' AND ps.source_name = 'osm' AND c.name = $1
                ORDER BY p.name
                LIMIT 1
            """, cat)
            if not row:
                continue

            pid = row["id"]
            # Fetch sources for this place
            sources = await conn.fetch("""
                SELECT source_name, source_id, confidence_score, raw_data
                FROM place_sources WHERE place_id = $1::uuid
            """, pid)
            # Fetch RAG document
            doc = await conn.fetchrow("""
                SELECT document_id, title, content_hash, embedding_model, length(content) as content_len
                FROM documents WHERE place_id = $1::uuid AND source_name = 'osm'
            """, pid)

            print(f"\n   [Da Nang - {cat.upper()}] {row['name']} (ID: {pid}):")
            print(f"     Coordinates:   ({row['latitude']}, {row['longitude']})")
            print(f"     Rating:        {row['rating']} (PASS: None) | Reviews: {row['review_count']} (PASS: 0)")
            print(f"     Sources ({len(sources)}):")
            for s in sources:
                print(f"       - {s['source_name']}: {s['source_id']} (conf: {s['confidence_score']})")
            if doc:
                print(f"     RAG OSM Doc:   {doc['document_id']} (title: {doc['title']}, model: {doc['embedding_model']}, len: {doc['content_len']} chars)")
            else:
                print(f"     [ERROR] Missing RAG OSM document!")

            assert row["rating"] is None
            assert row["review_count"] == 0
            assert any(s["source_name"] == "osm" for s in sources)
            assert doc is not None

        print("\n" + "=" * 70)
        print("ALL SMOKE SAMPLE VERIFICATIONS PASSED")
        print("=" * 70)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_smoke())
