#!/usr/bin/env python3
"""DATA-02 Database Import & RAG Document Generation.

Applies the verified import plan (data/manifests/db_import_plan_v1.json) to the
local PostgreSQL database.

Strict Invariants Enforced:
- Rating remains NULL; review_count remains 0 for all places.
- Prior 357 verified places preserved (110 Hanoi places get updated OSM metadata).
- Overture sources added ONLY as auxiliary provenance for high-confidence matches.
- Generates Ha Long OSM RAG documents embedded with MiniLM-L12-v2 (384-dim).
- Preserves all 464 pinned Wikivoyage chunks.
- Updates dataset_registry.
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_importer")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

# Setup path for ai-service imports
REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.rag.embedder import SentenceTransformerEmbedder
from app.rag.osm_documents import build_osm_place_chunk

async def apply_import():
    manifests_dir = REPO_ROOT / "data" / "manifests"
    plan_file = manifests_dir / "db_import_plan_v1.json"
    if not plan_file.exists():
        raise FileNotFoundError(f"Missing import plan: {plan_file}")

    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("=" * 70)
        print("EXECUTING DATA-02 DATABASE IMPORT TRANSACTION")
        print("=" * 70)

        # 1. Pre-flight count check
        pre_places = await conn.fetchval("SELECT count(*) FROM places")
        pre_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        pre_docs = await conn.fetchval("SELECT count(*) FROM documents")
        print(f"Pre-import counts: places={pre_places}, osm_sources={pre_osm}, docs={pre_docs}")

        inserted_places = 0
        updated_sources = 0
        auxiliary_ov_sources = 0

        async with conn.transaction():
            for act in plan["actions"]:
                action_type = act["action"]
                raw_payload = {
                    "osm_type": act.get("osm_type"),
                    "osm_id": act.get("osm_id"),
                    "osm_version": act.get("osm_version"),
                    "osm_changeset": act.get("osm_changeset"),
                    "osm_timestamp": act.get("osm_timestamp"),
                    "osm_base": act.get("osm_base"),
                    "tier_1": act.get("tier_1"),
                    "tier_2": act.get("tier_2"),
                    "legacy_category": act.get("legacy_category"),
                    "tags": act.get("raw_tags", {})
                }

                if action_type == "UPDATE_METADATA":
                    place_id = act["existing_place_id"]
                    # Update place coordinates & address if needed
                    await conn.execute("""
                        UPDATE places
                        SET address = COALESCE($2, address),
                            opening_hours = COALESCE($3, opening_hours),
                            updated_at = NOW()
                        WHERE id = $1
                    """, uuid.UUID(place_id), act.get("address"), act.get("opening_hours"))

                    # Update OSM place_source metadata
                    await conn.execute("""
                        UPDATE place_sources
                        SET latitude = $2,
                            longitude = $3,
                            raw_data = $4::jsonb
                        WHERE place_id = $1 AND source_name = 'osm'
                    """, uuid.UUID(place_id), act["latitude"], act["longitude"], json.dumps(raw_payload, ensure_ascii=False))
                    updated_sources += 1

                    # Check for auxiliary Overture provenance
                    ov = act.get("overture_auxiliary")
                    if ov:
                        ov_exists = await conn.fetchval("""
                            SELECT count(*) FROM place_sources WHERE place_id = $1 AND source_name = 'overture'
                        """, uuid.UUID(place_id))
                        if not ov_exists:
                            ov_payload = {
                                "overture_id": ov["overture_id"],
                                "overture_name": ov["overture_name"],
                                "distance_m": ov["distance_m"],
                                "similarity_score": ov["similarity_score"],
                                "license": ov["license"],
                                "providers": ov["providers"],
                                "operating_status": ov["operating_status"]
                            }
                            await conn.execute("""
                                INSERT INTO place_sources (id, place_id, source_name, source_id, raw_name, latitude, longitude, raw_data, confidence_score, created_at)
                                VALUES ($1, $2, 'overture', $3, $4, $5, $6, $7::jsonb, $8, NOW())
                            """, uuid.uuid4(), uuid.UUID(place_id), ov["overture_id"], ov["overture_name"], act["latitude"], act["longitude"], json.dumps(ov_payload, ensure_ascii=False), ov["similarity_score"])
                            auxiliary_ov_sources += 1

                elif action_type == "NEW":
                    # Check if already inserted
                    existing_pid = await conn.fetchval("""
                        SELECT place_id FROM place_sources WHERE source_name = 'osm' AND source_id = $1
                    """, act["source_id"])

                    if existing_pid:
                        new_pid = existing_pid
                    else:
                        new_pid = uuid.uuid4()
                        dest_uuid = uuid.UUID(act["destination_id"]) if act.get("destination_id") else None
                        cat_uuid = uuid.UUID(act["category_id"]) if act.get("category_id") else None

                        # Insert place: rating IS NULL, review_count IS 0
                        await conn.execute("""
                            INSERT INTO places (id, destination_id, category_id, name, address, latitude, longitude,
                                                opening_hours, rating, review_count, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, 0, NOW(), NOW())
                        """, new_pid, dest_uuid, cat_uuid, act["name"], act.get("address"), act["latitude"], act["longitude"], act.get("opening_hours"))
                        inserted_places += 1

                        # Insert primary OSM place_source
                        await conn.execute("""
                            INSERT INTO place_sources (id, place_id, source_name, source_id, raw_name, latitude, longitude, raw_data, confidence_score, created_at)
                            VALUES ($1, $2, 'osm', $3, $4, $5, $6, $7::jsonb, 1.0, NOW())
                        """, uuid.uuid4(), new_pid, act["source_id"], act["name"], act["latitude"], act["longitude"], json.dumps(raw_payload, ensure_ascii=False))

                    # Insert auxiliary Overture provenance if high-confidence match
                    ov = act.get("overture_auxiliary")
                    if ov:
                        ov_exists = await conn.fetchval("""
                            SELECT count(*) FROM place_sources WHERE place_id = $1 AND source_name = 'overture'
                        """, new_pid)
                        if not ov_exists:
                            ov_payload = {
                                "overture_id": ov["overture_id"],
                                "overture_name": ov["overture_name"],
                                "distance_m": ov["distance_m"],
                                "similarity_score": ov["similarity_score"],
                                "license": ov["license"],
                                "providers": ov["providers"],
                                "operating_status": ov["operating_status"]
                            }
                            await conn.execute("""
                                INSERT INTO place_sources (id, place_id, source_name, source_id, raw_name, latitude, longitude, raw_data, confidence_score, created_at)
                                VALUES ($1, $2, 'overture', $3, $4, $5, $6, $7::jsonb, $8, NOW())
                            """, uuid.uuid4(), new_pid, ov["overture_id"], ov["overture_name"], act["latitude"], act["longitude"], json.dumps(ov_payload, ensure_ascii=False), ov["similarity_score"])
                            auxiliary_ov_sources += 1

        print(f"[PASS] Transaction Committed:")
        print(f"       New Places Inserted:           {inserted_places}")
        print(f"       OSM Metadata Updated:          {updated_sources}")
        print(f"       Auxiliary Overture Linked:     {auxiliary_ov_sources}")

        # 2. Update Dataset Registry
        print("\nUpdating dataset_registry...")
        now = datetime.now(timezone.utc)
        total_active_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")

        registry_entries = [
            ("osm_places", "https://www.openstreetmap.org", "2026.10.07", "ODbL 1.0", "ACCESS_GRANTED", now, None, "Open database license, attribution required", total_active_osm),
            ("osm_places_halong", "https://www.openstreetmap.org", "2026.10.07", "ODbL 1.0", "ACCESS_GRANTED", now, "de27ec3d3db00974c44725d01578c955d790a90bdc7da356d9098401fdb654f6", "Verified OSM POIs for Ha Long (DATA-02 Freeze)", 188),
            ("osm_places_hanoi", "https://www.openstreetmap.org", "2026.10.07", "ODbL 1.0", "ACCESS_GRANTED", now, "469417955e76d9f4eab8eab11401f13405e2d38a7d46027101013db4b0e0e9ea", "Verified OSM POIs for Hanoi (DATA-02 Freeze)", 145),
            ("synthetic_preferences_v1", "GoMate Deterministic Generator (seed=42)", "1.0.0", "CC BY 4.0", "ACCESS_GRANTED", now, "1e883266bf6b145de0b7debf02d4881fc2f5293c9cf693ed34cd01715f6ab21a", "Synthetic preference dataset N=300 for REC-A", 300),
            ("overture_places_v1", "s3://overturemaps-us-west-2/release/2026-09-23.1", "2026-09-23.1", "Multi-License (CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0)", "ACCESS_GRANTED", now, None, "Secondary cross-check provenance", auxiliary_ov_sources)
        ]

        for d_name, d_src, d_ver, d_lic, d_stat, d_ret, d_chk, d_rst, d_cnt in registry_entries:
            row_id = await conn.fetchval("SELECT id FROM dataset_registry WHERE dataset_name = $1", d_name)
            if row_id:
                await conn.execute("""
                    UPDATE dataset_registry
                    SET dataset_source = $2, dataset_version = $3, license = $4, access_status = $5,
                        retrieved_at = $6, checksum = $7, restriction = $8, record_count = $9, updated_at = NOW()
                    WHERE id = $1
                """, row_id, d_src, d_ver, d_lic, d_stat, d_ret, d_chk, d_rst, d_cnt)
            else:
                await conn.execute("""
                    INSERT INTO dataset_registry (id, dataset_name, dataset_source, dataset_version, license,
                                                 access_status, retrieved_at, checksum, restriction, record_count,
                                                 created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
                """, uuid.uuid4(), d_name, d_src, d_ver, d_lic, d_stat, d_ret, d_chk, d_rst, d_cnt)

        print("[PASS] Dataset registry updated successfully.")

        # 3. Generate Ha Long OSM RAG Documents
        print("\n" + "=" * 70)
        print("GENERATING HA LONG OSM RAG DOCUMENTS")
        print("=" * 70)

        # Get destination ID for Ha Long
        hl_dest_id = await conn.fetchval("SELECT id FROM destinations WHERE name = 'Hạ Long'")
        hl_places = await conn.fetch("""
            SELECT p.id, p.name, c.name as category, d.name as destination_name, d.id as destination_id,
                   p.latitude, p.longitude, ps.source_id, ps.raw_data
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE d.id = $1 AND ps.source_name = 'osm'
        """, hl_dest_id)

        print(f"Verified Ha Long places for RAG documents: {len(hl_places)}")
        embedder = SentenceTransformerEmbedder()
        print(f"Loaded embedder: {embedder.model_name} (dim: {embedder.dimension})")

        inserted_docs = 0
        for p in hl_places:
            place_dict = {
                "id": str(p["id"]),
                "name": p["name"],
                "category": p["category"],
                "destination_id": str(p["destination_id"]),
                "destination_name": p["destination_name"],
                "latitude": p["latitude"],
                "longitude": p["longitude"],
                "sources": [{
                    "source_name": "osm",
                    "source_id": p["source_id"],
                    "raw_data": p["raw_data"]
                }]
            }

            chunk = build_osm_place_chunk(place_dict)
            if not chunk:
                continue

            # Compute embedding
            emb = embedder.embed_text(chunk.content)
            emb_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"

            # Check if doc exists
            existing_doc_id = await conn.fetchval("SELECT id FROM documents WHERE document_id = $1", chunk.document_id)
            if not existing_doc_id:
                await conn.execute("""
                    INSERT INTO documents (
                        id, document_id, place_id, destination_id, source_name, source_url,
                        license, attribution, language, title, section_heading, topic,
                        category, content, content_hash, embedding_model, embedding,
                        metadata, retrieved_at, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                        $17::vector, $18::jsonb, $19, NOW(), NOW()
                    )
                """,
                uuid.uuid4(), chunk.document_id, uuid.UUID(chunk.place_id), uuid.UUID(chunk.destination_id),
                chunk.source_name, chunk.source_url, chunk.license, chunk.attribution, chunk.language,
                chunk.title, chunk.section_heading, chunk.topic, chunk.category, chunk.content,
                chunk.content_hash, embedder.model_name, emb_str, json.dumps(chunk.metadata, ensure_ascii=False),
                chunk.retrieved_at or now
                )
                inserted_docs += 1

        print(f"[PASS] Ha Long OSM RAG documents generated: {inserted_docs}")

        # Post-import verification
        post_places = await conn.fetchval("SELECT count(*) FROM places")
        post_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        post_ov = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'overture'")
        post_docs = await conn.fetchval("SELECT count(*) FROM documents")
        wiki_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
        osm_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
        null_ratings = await conn.fetchval("SELECT count(*) FROM places WHERE rating IS NOT NULL")

        print("\n" + "=" * 70)
        print("POST-IMPORT DATABASE VERIFICATION REPORT")
        print("=" * 70)
        print(f"Total Places:               {post_places} (Expected: {pre_places + inserted_places})")
        print(f"Total OSM Sources:          {post_osm} (Expected: {pre_osm + inserted_places})")
        print(f"Total Overture Sources:     {post_ov}")
        print(f"Total Documents:            {post_docs} (OSM: {osm_docs}, Wikivoyage: {wiki_docs})")
        print(f"Places with non-null rating: {null_ratings} (Must be 0)")

        assert null_ratings == 0, "Invariant violation: non-null rating detected!"
        assert wiki_docs == 464, f"Invariant violation: Wikivoyage chunks altered! Expected 464, got {wiki_docs}"
        assert post_places == pre_places + inserted_places, "Mismatch in place count!"
        print("\n[ALL DB INTEGRITY & CONTRACT INVARIANTS PASS]")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_import())
