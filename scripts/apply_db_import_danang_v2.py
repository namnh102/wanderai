#!/usr/bin/env python3
"""DATA-02 / MVP-SCOPE-01 Da Nang Database Import & RAG Generation.

Applies the verified Da Nang import plan (data/manifests/db_import_plan_danang_v2.json)
to the local PostgreSQL database.

Strict Invariants Enforced:
- Rating remains NULL; review_count remains 0 for all places.
- Prior verified places in Hanoi (145) and Ha Long (188) remain 100% untouched.
- Existing 114 Da Nang places preserved (109 metadata update, 5 unchanged).
- Overture sources added ONLY as auxiliary provenance for high-confidence matches.
- Generates Da Nang OSM RAG documents embedded with MiniLM-L12-v2 (384-dim).
- Preserves all 464 pinned Wikivoyage chunks.
- Updates dataset_registry.
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("danang_db_importer")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.rag.embedder import SentenceTransformerEmbedder
from app.rag.osm_documents import build_osm_place_chunk

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

async def apply_import():
    manifests_dir = REPO_ROOT / "data" / "manifests"
    plan_file = manifests_dir / "db_import_plan_danang_v2.json"
    if not plan_file.exists():
        raise FileNotFoundError(f"Missing import plan: {plan_file}")

    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("=" * 70)
        print("EXECUTING DA NANG (V2) DATABASE IMPORT TRANSACTION")
        print("=" * 70)

        # 1. Pre-flight count checks
        pre_places = await conn.fetchval("SELECT count(*) FROM places WHERE deleted_at IS NULL")
        pre_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        pre_docs = await conn.fetchval("SELECT count(*) FROM documents")
        print(f"Pre-import counts: places={pre_places}, osm_sources={pre_osm}, docs={pre_docs}")

        inserted_places = 0
        updated_sources = 0
        auxiliary_ov_sources = 0

        async with conn.transaction():
            for act in plan["actions"]:
                action_type = act["action"]
                if action_type == "UNCHANGED":
                    continue

                raw_payload = {
                    "osm_type": act.get("osm_type") or act["source_id"].split("/")[0],
                    "osm_id": act.get("osm_id") or int(act["source_id"].split("/")[1]),
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
                            latitude = $4,
                            longitude = $5,
                            updated_at = NOW()
                        WHERE id = $1
                    """, uuid.UUID(place_id), act.get("address"), act.get("opening_hours"), act["latitude"], act["longitude"])

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
                            SELECT count(*) FROM place_sources 
                            WHERE source_name = 'overture' AND (place_id = $1 OR source_id = $2)
                        """, uuid.UUID(place_id), ov["overture_id"])
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
                                ON CONFLICT (source_name, source_id) DO NOTHING
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
                            ON CONFLICT (source_name, source_id) DO NOTHING
                        """, uuid.uuid4(), new_pid, act["source_id"], act["name"], act["latitude"], act["longitude"], json.dumps(raw_payload, ensure_ascii=False))

                    # Insert auxiliary Overture provenance if high-confidence match
                    ov = act.get("overture_auxiliary")
                    if ov:
                        ov_exists = await conn.fetchval("""
                            SELECT count(*) FROM place_sources 
                            WHERE source_name = 'overture' AND (place_id = $1 OR source_id = $2)
                        """, new_pid, ov["overture_id"])
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
                                ON CONFLICT (source_name, source_id) DO NOTHING
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
        danang_verified_cnt = await conn.fetchval("""
            SELECT count(*) FROM place_sources ps
            JOIN places p ON ps.place_id = p.id
            JOIN destinations d ON p.destination_id = d.id
            WHERE ps.source_name = 'osm' AND d.slug = 'da-nang' AND p.deleted_at IS NULL
        """)

        registry_entries = [
            ("osm_places", "https://www.openstreetmap.org", "2026.10.07-v2", "ODbL 1.0", "ACCESS_GRANTED", now, None, "Open database license, attribution required", total_active_osm),
            ("osm_places_danang_v2", "https://www.openstreetmap.org", "2026.10.07-v2", "ODbL 1.0", "ACCESS_GRANTED", now, "f73b49124e5a09a834d5381febf3f5c5bcc5f5d6e343ef85d0650e3996cbcb47", "Verified OSM POIs for Da Nang (MVP-SCOPE-01 Freeze V2)", danang_verified_cnt),
            ("overture_places_danang_v2", "s3://overturemaps-us-west-2/release/2026-09-23.1", "2026-09-23.1", "Multi-License (CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0)", "ACCESS_GRANTED", now, None, "Secondary cross-check provenance for Da Nang", auxiliary_ov_sources)
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

        # 3. Generate / Refresh Da Nang OSM RAG Documents
        print("\n" + "=" * 70)
        print("GENERATING / REFRESHING DA NANG OSM RAG DOCUMENTS")
        print("=" * 70)

        dn_dest_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'da-nang'")
        dn_places = await conn.fetch("""
            SELECT p.id, p.name, c.name as category, d.name as destination_name, d.id as destination_id,
                   p.latitude, p.longitude, ps.source_id, ps.raw_data
            FROM places p
            JOIN destinations d ON p.destination_id = d.id
            JOIN place_categories c ON p.category_id = c.id
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE d.id = $1 AND ps.source_name = 'osm' AND p.deleted_at IS NULL
        """, dn_dest_id)

        print(f"Verified Da Nang places for RAG documents: {len(dn_places)}")
        embedder = SentenceTransformerEmbedder()
        print(f"Loaded embedder: {embedder.model_name} (dim: {embedder.dimension})")

        inserted_docs = 0
        updated_docs = 0

        for p in dn_places:
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

            emb = embedder.embed_text(chunk.content)
            emb_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"

            existing_doc_id = await conn.fetchval("SELECT id FROM documents WHERE document_id = $1", chunk.document_id)
            if existing_doc_id:
                await conn.execute("""
                    UPDATE documents
                    SET title = $2, section_heading = $3, topic = $4, category = $5,
                        content = $6, content_hash = $7, embedding = $8::vector,
                        metadata = $9::jsonb, updated_at = NOW()
                    WHERE id = $1
                """,
                existing_doc_id, chunk.title, chunk.section_heading, chunk.topic, chunk.category,
                chunk.content, chunk.content_hash, emb_str, json.dumps(chunk.metadata, ensure_ascii=False)
                )
                updated_docs += 1
            else:
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

        print(f"[PASS] Da Nang OSM RAG documents: {inserted_docs} inserted, {updated_docs} updated. Total: {inserted_docs + updated_docs}")

        # 4. Coordinate Consistency Check (Section 18)
        print("\n" + "=" * 70)
        print("COORDINATE CONSISTENCY AUDIT (places vs place_sources)")
        print("=" * 70)

        coord_rows = await conn.fetch("""
            SELECT p.id::text, p.name, p.latitude as p_lat, p.longitude as p_lon,
                   ps.latitude as s_lat, ps.longitude as s_lon
            FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1 AND p.deleted_at IS NULL
        """, dn_dest_id)

        drifts = []
        drift_gt_5 = 0
        drift_gt_20 = 0
        drift_gt_100 = 0

        for r in coord_rows:
            dist = haversine_distance(r["p_lat"], r["p_lon"], r["s_lat"], r["s_lon"])
            drifts.append(dist)
            if dist > 100.0:
                drift_gt_100 += 1
            if dist > 20.0:
                drift_gt_20 += 1
            if dist > 5.0:
                drift_gt_5 += 1

        drifts.sort()
        count = len(drifts)
        median_drift = drifts[count // 2] if count else 0.0
        p95_drift = drifts[int(count * 0.95)] if count else 0.0
        max_drift = drifts[-1] if count else 0.0

        coord_stats = {
            "count": count,
            "median_drift_m": round(median_drift, 4),
            "p95_drift_m": round(p95_drift, 4),
            "max_drift_m": round(max_drift, 4),
            "drift_gt_5m": drift_gt_5,
            "drift_gt_20m": drift_gt_20,
            "drift_gt_100m": drift_gt_100
        }

        print(f"Coordinate Consistency Statistics (n={count}):")
        print(f"  Median Drift:   {coord_stats['median_drift_m']} m")
        print(f"  P95 Drift:      {coord_stats['p95_drift_m']} m")
        print(f"  Max Drift:      {coord_stats['max_drift_m']} m")
        print(f"  Drift > 5m:     {coord_stats['drift_gt_5m']}")
        print(f"  Drift > 20m:    {coord_stats['drift_gt_20m']}")
        print(f"  Drift > 100m:   {coord_stats['drift_gt_100m']}")

        # Save coordinate stats artifact
        coord_stats_file = manifests_dir / "danang_coordinate_drift_stats_v2.json"
        with open(coord_stats_file, "w", encoding="utf-8") as f:
            json.dump(coord_stats, f, indent=2)

        # 5. Final DB Post-Import Verification
        post_places = await conn.fetchval("SELECT count(*) FROM places WHERE deleted_at IS NULL")
        post_osm = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'osm'")
        post_ov = await conn.fetchval("SELECT count(*) FROM place_sources WHERE source_name = 'overture'")
        post_docs = await conn.fetchval("SELECT count(*) FROM documents")
        wiki_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'")
        osm_docs = await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
        null_ratings = await conn.fetchval("SELECT count(*) FROM places WHERE rating IS NOT NULL")

        hanoi_dest_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'ha-noi'")
        halong_dest_id = await conn.fetchval("SELECT id FROM destinations WHERE slug = 'ha-long'")
        hanoi_post_osm = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1::uuid AND p.deleted_at IS NULL
        """, hanoi_dest_id)
        halong_post_osm = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1::uuid AND p.deleted_at IS NULL
        """, halong_dest_id)

        print("\n" + "=" * 70)
        print("FINAL POST-IMPORT DATABASE VERIFICATION")
        print("=" * 70)
        print(f"Total Places:          {post_places} (was {pre_places}, +{post_places - pre_places})")
        print(f"Total OSM Sources:     {post_osm} (was {pre_osm}, +{post_osm - pre_osm})")
        print(f"Total Overture Sources:{post_ov}")
        print(f"Total Documents:       {post_docs} (was {pre_docs}, +{post_docs - pre_docs})")
        print(f"  OSM Documents:       {osm_docs}")
        print(f"  Wikivoyage Documents:{wiki_docs} (MUST BE 464)")
        print(f"Hanoi OSM Sources:     {hanoi_post_osm} (MUST BE 145)")
        print(f"Ha Long OSM Sources:   {halong_post_osm} (MUST BE 188)")
        print(f"Da Nang OSM Sources:   {danang_verified_cnt} (MUST BE 293)")
        print(f"Places with non-null rating: {null_ratings} (MUST BE 0)")

        assert wiki_docs == 464, f"Expected 464 Wikivoyage docs, got {wiki_docs}"
        assert hanoi_post_osm == 145, f"Expected 145 Hanoi OSM, got {hanoi_post_osm}"
        assert halong_post_osm == 188, f"Expected 188 Ha Long OSM, got {halong_post_osm}"
        assert danang_verified_cnt == 293, f"Expected 293 Da Nang OSM, got {danang_verified_cnt}"
        assert null_ratings == 0, f"Expected 0 non-null ratings, got {null_ratings}"

        print("\n[ALL DB INVARIANTS PASSED]")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_import())
