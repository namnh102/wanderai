#!/usr/bin/env python3
"""
scripts/smoke_test_rag_db.py
Smoke verification test for PostgreSQL database state and RAG document consistency.
Part of TASK DATA-02-R1 governance closure.
"""

import asyncio
import os
import sys
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

async def run_smoke_tests():
    conn = await asyncpg.connect(DATABASE_URL)

    print("======================================================================")
    print("RUNNING API / RAG / DB SMOKE VERIFICATION")
    print("======================================================================")

    # 1. Check Wikivoyage document count == 464
    wiki_count = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage';")
    print(f"[CHECK] Wikivoyage documents: {wiki_count} (Expected: 464)")
    assert wiki_count == 464, f"Wikivoyage document mismatch: {wiki_count} != 464"

    # 2. Check OSM document count == 580
    osm_doc_count = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm';")
    print(f"[CHECK] OSM documents: {osm_doc_count} (Expected: 580)")
    assert osm_doc_count == 580, f"OSM document mismatch: {osm_doc_count} != 580"

    # 3. Check Total documents == 1044
    total_docs = await conn.fetchval("SELECT count(*) FROM documents;")
    print(f"[CHECK] Total documents: {total_docs} (Expected: 1044)")
    assert total_docs == 1044, f"Total documents mismatch: {total_docs} != 1044"

    # 4. Check places with non-null rating == 0
    rating_count = await conn.fetchval("SELECT count(*) FROM places WHERE rating IS NOT NULL;")
    print(f"[CHECK] Places with non-null rating: {rating_count} (Expected: 0)")
    assert rating_count == 0, f"Non-null rating count: {rating_count} != 0"

    # 5. Check total verified OSM sources == 580
    verified_sources = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm';")
    print(f"[CHECK] Verified OSM place_sources: {verified_sources} (Expected: 580)")
    assert verified_sources == 580, f"Verified OSM sources mismatch: {verified_sources} != 580"

    # 6. Sample Hanoi place detail
    hn_sample = await conn.fetchrow("""
        SELECT p.id, p.name, c.name as category, p.latitude, p.longitude, p.rating, p.review_count,
               s.source_name, s.source_id
        FROM places p
        JOIN place_categories c ON p.category_id = c.id
        JOIN place_sources s ON p.id = s.place_id
        WHERE c.name IN ('hotel', 'culture', 'attraction')
          AND p.latitude BETWEEN 20.95 AND 21.15
          AND p.longitude BETWEEN 105.75 AND 105.95
          AND s.source_name = 'osm'
        LIMIT 1;
    """)
    print(f"\n[SAMPLE HANOI POI]")
    print(f"- ID: {hn_sample['id']}")
    print(f"- Name: {hn_sample['name']}")
    print(f"- Category: {hn_sample['category']}")
    print(f"- Coords: ({hn_sample['latitude']}, {hn_sample['longitude']})")
    print(f"- Rating: {hn_sample['rating']}, Review count: {hn_sample['review_count']}")
    print(f"- OSM Source: {hn_sample['source_name']}:{hn_sample['source_id']}")
    assert hn_sample['rating'] is None
    assert hn_sample['review_count'] == 0
    assert 20.95 <= hn_sample['latitude'] <= 21.15
    assert 105.75 <= hn_sample['longitude'] <= 105.95

    # Check RAG doc for this Hanoi place
    hn_rag = await conn.fetchrow("SELECT id, title, source_name FROM documents WHERE place_id = $1;", hn_sample['id'])
    print(f"- RAG Document: ID={hn_rag['id']}, Title='{hn_rag['title']}', Source='{hn_rag['source_name']}'")
    assert hn_rag is not None

    # 7. Sample Ha Long place detail
    hl_sample = await conn.fetchrow("""
        SELECT p.id, p.name, c.name as category, p.latitude, p.longitude, p.rating, p.review_count,
               s.source_name, s.source_id
        FROM places p
        JOIN place_categories c ON p.category_id = c.id
        JOIN place_sources s ON p.id = s.place_id
        WHERE p.latitude BETWEEN 20.85 AND 21.05
          AND p.longitude BETWEEN 106.95 AND 107.25
          AND s.source_name = 'osm'
        LIMIT 1;
    """)
    print(f"\n[SAMPLE HA LONG POI]")
    print(f"- ID: {hl_sample['id']}")
    print(f"- Name: {hl_sample['name']}")
    print(f"- Category: {hl_sample['category']}")
    print(f"- Coords: ({hl_sample['latitude']}, {hl_sample['longitude']})")
    print(f"- Rating: {hl_sample['rating']}, Review count: {hl_sample['review_count']}")
    print(f"- OSM Source: {hl_sample['source_name']}:{hl_sample['source_id']}")
    assert hl_sample['rating'] is None
    assert hl_sample['review_count'] == 0
    assert 20.85 <= hl_sample['latitude'] <= 21.05
    assert 106.95 <= hl_sample['longitude'] <= 107.25

    # Check RAG doc for this Ha Long place
    hl_rag = await conn.fetchrow("SELECT id, title, source_name FROM documents WHERE place_id = $1;", hl_sample['id'])
    print(f"- RAG Document: ID={hl_rag['id']}, Title='{hl_rag['title']}', Source='{hl_rag['source_name']}'")
    assert hl_rag is not None

    # 8. Check Overture auxiliary links license validity
    overture_count = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'overture';")
    print(f"\n[CHECK] Overture auxiliary sources: {overture_count} (Expected: 89)")
    assert overture_count == 89

    unresolved_license_count = await conn.fetchval("""
        SELECT count(*) FROM place_sources 
        WHERE source_name = 'overture' 
          AND (raw_data->>'license' IS NULL OR raw_data->>'license' = '');
    """)
    print(f"[CHECK] Overture sources with null/empty license: {unresolved_license_count} (Expected: 0)")
    assert unresolved_license_count == 0

    print("\n[ALL SMOKE TESTS PASSED SUCCESSFULLY!]")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run_smoke_tests())
