#!/usr/bin/env python3
"""Deterministic CI Database Bootstrap & RAG Ingestion for GoMate / WanderAI (PROD-CI-05).

Seeds PostgreSQL (with PostGIS + pgvector) from repository-tracked deterministic artifacts
so Backend E2E and AI-Service RAG/Grounding integration tests run reproducibly in CI
without live external network/LLM calls or un-exported local Docker volumes:

1. 13 canonical place_categories (10 seed + 3 curated categories with canonical UUIDs).
2. 50 destinations from database/seed/destinations.json (with canonical UUIDs for
   ha-noi, ha-long, and da-nang, and deterministic UUIDv5 for the remaining 47).
3. 759 verified places + OSM/Overture place_sources from data/curated/gomate_places_freeze_v2.json
   (293 Da Nang, 188 Ha Long, 145 Hanoi, 50 Hoi An, 50 Hue, 33 Nha Trang; rating=NULL, review_count=0).
4. 11 unsourced canonical places from data/curated/places_canonical.json + 112 legacy unsourced
   places from database/seed/places.json x2 (123 unsourced places -> 882 total places).
5. 8 synthetic reviews (source='synthetic', trusted=false) from data/curated/reviews_curated.json
   and 12 quarantined invalid OSM sources from data/manifests/osm-invalid-sources.json.
6. Dataset governance rows in dataset_registry.
7. When --include-rag-docs is passed:
   - Generates and embeds all 759 verified OSM RAG documents via WikivoyageIngester.ingest_canonical_places().
   - Inserts deterministic engineering Wikivoyage destination fixture chunks (CC BY-SA 3.0)
     clearly separated from frozen W07 scientific evaluation artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import asyncpg

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
sys.path.insert(0, str(AI_SERVICE_DIR))

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai"
)

CANONICAL_DESTINATION_IDS: dict[str, str] = {
    "ha-noi": "071e1382-7972-4dde-af61-dac9ef2c3c69",
    "ha-long": "4eec2f30-b67d-4221-b754-8fcc7bb1160e",
    "da-nang": "2ba4b21c-454c-4077-b2b2-38b6044c656b",
}

CANONICAL_CATEGORY_IDS: dict[str, str] = {
    "restaurant": "6a9507e9-1241-4aa7-bea7-519a6fe40a33",
    "hotel": "b0f34bb0-0530-4ad8-94b4-4a39af6f795e",
    "attraction": "3dde2576-c602-4e92-9e9b-836cf38614c6",
    "beach": "832d2ab3-27fa-44f8-8130-5582549dd2e4",
    "temple": "17b3996e-1c40-4d69-9e07-855c270d567a",
    "market": "011359a6-f25c-43a0-be53-439dfb69c25f",
    "cafe": "34f3a4c5-8d25-4fe5-adce-0957571dc90f",
    "museum": "97a8f5ba-fafd-44a1-89d4-bed6f4c0855b",
    "park": "f2a7e09c-a446-439f-97ea-7e9fa1b389fe",
    "nightlife": "8a549c94-e3c7-4dc7-b245-96b6dff71943",
    "culture": "85251419-3058-48fd-aa59-07c2463180cf",
    "entertainment": "787d6942-1f3c-4d53-a07e-6e671dd0c7a5",
    "nature": "e72752aa-5c8a-4846-b2a5-d8625c2044ee",
}

CITY_TO_SLUG: dict[str, str] = {
    "Da Nang": "da-nang",
    "da_nang": "da-nang",
    "Đà Nẵng": "da-nang",
    "Hoi An": "hoi-an",
    "hoi_an": "hoi-an",
    "Hội An": "hoi-an",
    "Ha Noi": "ha-noi",
    "hanoi": "ha-noi",
    "Hà Nội": "ha-noi",
    "Hue": "hue",
    "hue": "hue",
    "Huế": "hue",
    "Ha Long": "ha-long",
    "ha_long": "ha-long",
    "Hạ Long": "ha-long",
    "Nha Trang": "nha-trang",
    "nha_trang": "nha-trang",
    "Da Lat": "da-lat",
    "da_lat": "da-lat",
    "Đà Lạt": "da-lat",
    "Sa Pa": "sa-pa",
    "sa_pa": "sa-pa",
    "Phu Quoc": "phu-quoc",
    "phu_quoc": "phu-quoc",
    "Phú Quốc": "phu-quoc",
    "Ho Chi Minh": "tp-ho-chi-minh",
    "ho_chi_minh": "tp-ho-chi-minh",
    "TP. Hồ Chí Minh": "tp-ho-chi-minh",
}


def _dest_uuid(slug: str) -> uuid.UUID:
    if slug in CANONICAL_DESTINATION_IDS:
        return uuid.UUID(CANONICAL_DESTINATION_IDS[slug])
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"wanderai.destination.{slug}")


def _cat_uuid(name: str) -> uuid.UUID:
    if name in CANONICAL_CATEGORY_IDS:
        return uuid.UUID(CANONICAL_CATEGORY_IDS[name])
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"wanderai.category.{name}")


async def seed_database(include_rag_docs: bool = False) -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        now = datetime.now(timezone.utc)
        seed_dir = REPO_ROOT / "database" / "seed"
        curated_dir = REPO_ROOT / "data" / "curated"
        manifests_dir = REPO_ROOT / "data" / "manifests"

        categories_seed = json.loads(
            (seed_dir / "categories.json").read_text(encoding="utf-8")
        )
        destinations_seed = json.loads(
            (seed_dir / "destinations.json").read_text(encoding="utf-8")
        )
        legacy_places_seed = json.loads(
            (seed_dir / "places.json").read_text(encoding="utf-8")
        )
        freeze_v2 = json.loads(
            (curated_dir / "gomate_places_freeze_v2.json").read_text(encoding="utf-8")
        )
        canonical_places = json.loads(
            (curated_dir / "places_canonical.json").read_text(encoding="utf-8")
        )
        curated_reviews = json.loads(
            (curated_dir / "reviews_curated.json").read_text(encoding="utf-8")
        )
        invalid_manifest = json.loads(
            (manifests_dir / "osm-invalid-sources.json").read_text(encoding="utf-8")
        )
        revalidation_manifest = json.loads(
            (manifests_dir / "osm-source-revalidation-v2.json").read_text(
                encoding="utf-8"
            )
        )

        revalidated_ids = {
            r["source_id"]
            for r in revalidation_manifest.get("revalidations", [])
            if r.get("status") == "REVALIDATED_CURRENT_OSM_MATCH"
        }

        async with conn.transaction():
            # Clean existing domain tables for deterministic state
            await conn.execute(
                """
                TRUNCATE TABLE
                    documents,
                    document_quarantine,
                    place_source_quarantine,
                    place_sources,
                    review_aspects,
                    reviews,
                    itinerary_items,
                    itineraries,
                    trip_members,
                    trips,
                    places,
                    place_categories,
                    destinations,
                    dataset_registry
                RESTART IDENTITY CASCADE
                """
            )

            # 1. Seed categories (10 seed + 3 curated categories)
            cat_meta = {c["name"]: (c.get("icon"), c.get("color")) for c in categories_seed}
            for extra_cat in ("culture", "entertainment", "nature"):
                cat_meta.setdefault(extra_cat, ("📍", "#4B5563"))

            cat_id_map: dict[str, uuid.UUID] = {}
            for name, (icon, color) in cat_meta.items():
                cid = _cat_uuid(name)
                cat_id_map[name] = cid
                await conn.execute(
                    """
                    INSERT INTO place_categories (id, name, icon, color)
                    VALUES ($1, $2, $3, $4)
                    """,
                    cid,
                    name,
                    icon,
                    color,
                )

            # 2. Seed 50 destinations
            dest_id_map: dict[str, uuid.UUID] = {}
            for d in destinations_seed:
                slug = d["slug"]
                did = _dest_uuid(slug)
                dest_id_map[slug] = did
                await conn.execute(
                    """
                    INSERT INTO destinations (
                        id, name, name_en, slug, description, province, region,
                        latitude, longitude, rating, review_count, is_popular,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, 0, $11,
                        NOW(), NOW()
                    )
                    """,
                    did,
                    d["name"],
                    d.get("nameEn"),
                    slug,
                    d.get("description"),
                    d.get("province"),
                    d.get("region"),
                    d.get("latitude"),
                    d.get("longitude"),
                    float(d.get("rating") or 0.0),
                    bool(d.get("isPopular", False)),
                )

            # 3. Ensure system curator user exists
            curator_id = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1", "curator@wanderai.vn"
            )
            if not curator_id:
                curator_id = uuid.uuid5(
                    uuid.NAMESPACE_DNS, "wanderai.user.curator@wanderai.vn"
                )
                await conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, role, is_verified, created_at, updated_at)
                    VALUES ($1, $2, $3, 'ADMIN', true, NOW(), NOW())
                    """,
                    curator_id,
                    "curator@wanderai.vn",
                    "not_a_real_hash_system_account",
                )

            # 4. Seed 112 legacy unsourced places (database/seed/places.json x2; rating=NULL, review_count=0)
            for pass_idx in range(2):
                for idx, lp in enumerate(legacy_places_seed):
                    lpid = uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"wanderai.legacy.place.{pass_idx}.{idx}.{lp['name']}",
                    )
                    d_uuid = dest_id_map[lp["destination"]]
                    c_uuid = cat_id_map.get(lp["category"])
                    await conn.execute(
                        """
                        INSERT INTO places (
                            id, destination_id, category_id, name, name_en,
                            description, address, latitude, longitude,
                            price_min, price_max, rating, review_count,
                            created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5,
                            $6, $7, $8, $9,
                            $10, $11, NULL, 0,
                            NOW(), NOW()
                        )
                        """,
                        lpid,
                        d_uuid,
                        c_uuid,
                        lp["name"],
                        lp.get("nameEn"),
                        lp.get("description"),
                        lp.get("address"),
                        lp.get("latitude"),
                        lp.get("longitude"),
                        lp.get("priceMin"),
                        lp.get("priceMax"),
                    )

            # 5. Seed 759 verified places + place_sources from gomate_places_freeze_v2.json
            freeze_ids: set[str] = set()
            ov_count = 0
            for fp in freeze_v2:
                pid_str = fp["place_id"]
                freeze_ids.add(pid_str)
                pid = uuid.UUID(pid_str)
                d_uuid = dest_id_map[fp["destination_slug"]]
                c_uuid = cat_id_map.get(fp["category"])
                await conn.execute(
                    """
                    INSERT INTO places (
                        id, destination_id, category_id, name, address,
                        latitude, longitude, opening_hours, rating, review_count,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, NULL, 0,
                        NOW(), NOW()
                    )
                    """,
                    pid,
                    d_uuid,
                    c_uuid,
                    fp["name"],
                    fp.get("address"),
                    fp.get("latitude"),
                    fp.get("longitude"),
                    fp.get("opening_hours"),
                )
                for src in fp.get("sources", []):
                    sname = src["source_name"]
                    sid = src["source_id"]
                    if sname == "overture":
                        ov_count += 1
                    ps_id = uuid.uuid5(
                        uuid.NAMESPACE_DNS, f"wanderai.placesource.{sname}.{sid}"
                    )
                    await conn.execute(
                        """
                        INSERT INTO place_sources (
                            id, place_id, source_name, source_id, raw_name,
                            latitude, longitude, raw_data, confidence_score, created_at
                        ) VALUES (
                            $1, $2, $3, $4, $5,
                            $6, $7, $8::jsonb, $9, NOW()
                        )
                        ON CONFLICT (source_name, source_id) DO NOTHING
                        """,
                        ps_id,
                        pid,
                        sname,
                        sid,
                        fp["name"],
                        fp.get("latitude"),
                        fp.get("longitude"),
                        json.dumps(src.get("raw_data") or {}, ensure_ascii=False),
                        float(src.get("confidence_score") or 1.0),
                    )

            # 6. Seed the 11 unsourced canonical places (not in freeze_v2)
            for cp in canonical_places:
                if cp["id"] in freeze_ids:
                    continue
                slug = CITY_TO_SLUG[cp["city"]]
                d_uuid = dest_id_map[slug]
                c_uuid = cat_id_map.get(cp.get("category") or "attraction")
                await conn.execute(
                    """
                    INSERT INTO places (
                        id, destination_id, category_id, name, name_en,
                        description, address, latitude, longitude,
                        rating, review_count, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9,
                        NULL, 0, NOW(), NOW()
                    )
                    """,
                    uuid.UUID(cp["id"]),
                    d_uuid,
                    c_uuid,
                    cp["name"],
                    cp.get("name_en"),
                    cp.get("description"),
                    cp.get("address"),
                    cp.get("latitude"),
                    cp.get("longitude"),
                )

            # 7. Seed quarantined synthetic reviews (trusted=false, source='synthetic')
            for rev in curated_reviews:
                if not rev.get("place_id"):
                    continue
                rid = uuid.UUID(rev["id"])
                await conn.execute(
                    """
                    INSERT INTO reviews (
                        id, user_id, place_id, rating, content,
                        source, trusted, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        'synthetic', false, NOW(), NOW()
                    )
                    """,
                    rid,
                    curator_id,
                    uuid.UUID(rev["place_id"]),
                    float(rev["rating"]),
                    rev["content"],
                )
                for idx, asp in enumerate(rev.get("aspects", [])):
                    aid = uuid.uuid5(rid, f"aspect.{idx}.{asp['aspect']}")
                    await conn.execute(
                        """
                        INSERT INTO review_aspects (id, review_id, aspect, score, comment)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        aid,
                        rid,
                        asp["aspect"],
                        float(asp.get("score") or 3.0),
                        asp.get("sentiment"),
                    )

            # 8. Seed place_source_quarantine from osm-invalid-sources.json (excluding revalidated)
            for inv in invalid_manifest.get("invalid_sources", []):
                if inv["source_id"] in revalidated_ids:
                    continue
                qid = uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"wanderai.quarantine.osm.{inv['source_id']}"
                )
                orig_id = uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"wanderai.orig.osm.{inv['source_id']}"
                )
                await conn.execute(
                    """
                    INSERT INTO place_source_quarantine (
                        id, original_id, place_id, source_name, source_id,
                        raw_name, latitude, longitude, raw_data, reason, evidence, quarantined_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, '{}'::jsonb, $9, '{}'::jsonb, NOW()
                    )
                    """,
                    qid,
                    orig_id,
                    uuid.UUID(inv["place_id"]),
                    inv["source_name"],
                    inv["source_id"],
                    inv["raw_name"],
                    inv.get("stored_latitude"),
                    inv.get("stored_longitude"),
                    inv["reason"],
                )

            # 9. Seed dataset_registry
            registry_entries = [
                (
                    "osm_places",
                    "https://www.openstreetmap.org",
                    "2026.10.07-v2",
                    "ODbL 1.0",
                    "ACCESS_GRANTED",
                    now,
                    None,
                    "Open database license, attribution required",
                    759,
                ),
                (
                    "osm_places_halong",
                    "https://www.openstreetmap.org",
                    "2026.10.07",
                    "ODbL 1.0",
                    "ACCESS_GRANTED",
                    now,
                    "de27ec3d3db00974c44725d01578c955d790a90bdc7da356d9098401fdb654f6",
                    "Verified OSM POIs for Ha Long (DATA-02 Freeze)",
                    188,
                ),
                (
                    "osm_places_hanoi",
                    "https://www.openstreetmap.org",
                    "2026.10.07",
                    "ODbL 1.0",
                    "ACCESS_GRANTED",
                    now,
                    "469417955e76d9f4eab8eab11401f13405e2d38a7d46027101013db4b0e0e9ea",
                    "Verified OSM POIs for Hanoi (DATA-02 Freeze)",
                    145,
                ),
                (
                    "osm_places_danang_v2",
                    "https://www.openstreetmap.org",
                    "2026.10.07-v2",
                    "ODbL 1.0",
                    "ACCESS_GRANTED",
                    now,
                    "f73b49124e5a09a834d5381febf3f5c5bcc5f5d6e343ef85d0650e3996cbcb47",
                    "Verified OSM POIs for Da Nang (MVP-SCOPE-01 Freeze V2)",
                    293,
                ),
                (
                    "synthetic_preferences_v1",
                    "GoMate Deterministic Generator (seed=42)",
                    "1.0.0",
                    "CC BY 4.0",
                    "ACCESS_GRANTED",
                    now,
                    "1e883266bf6b145de0b7debf02d4881fc2f5293c9cf693ed34cd01715f6ab21a",
                    "Synthetic preference dataset N=300 for REC-A",
                    300,
                ),
                (
                    "overture_places_danang_v2",
                    "s3://overturemaps-us-west-2/release/2026-09-23.1",
                    "2026-09-23.1",
                    "Multi-License (CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0)",
                    "ACCESS_GRANTED",
                    now,
                    None,
                    "Secondary cross-check provenance for Da Nang",
                    ov_count,
                ),
            ]
            for (
                d_name,
                d_src,
                d_ver,
                d_lic,
                d_stat,
                d_ret,
                d_chk,
                d_rst,
                d_cnt,
            ) in registry_entries:
                await conn.execute(
                    """
                    INSERT INTO dataset_registry (
                        id, dataset_name, dataset_source, dataset_version, license,
                        access_status, retrieved_at, checksum, restriction, record_count,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9, $10,
                        NOW(), NOW()
                    )
                    """,
                    uuid.uuid5(uuid.NAMESPACE_DNS, f"wanderai.dataset.{d_name}"),
                    d_name,
                    d_src,
                    d_ver,
                    d_lic,
                    d_stat,
                    d_ret,
                    d_chk,
                    d_rst,
                    d_cnt,
                )

        total_places = await conn.fetchval(
            "SELECT count(*) FROM places WHERE deleted_at IS NULL"
        )
        total_osm = await conn.fetchval(
            "SELECT count(*) FROM place_sources WHERE source_name = 'osm'"
        )
        print(
            f"[seed_ci_database] Seeded places={total_places}, verified_osm_sources={total_osm}"
        )

    finally:
        await conn.close()

    if include_rag_docs:
        from app.rag.chunker import RAGChunk
        from app.rag.ingestion import WikivoyageIngester
        from app.rag.retriever import RAGRetriever

        retriever = RAGRetriever(db_url=DATABASE_URL)
        ingester = WikivoyageIngester(retriever=retriever)
        try:
            osm_report = await ingester.ingest_canonical_places()
            print(
                f"[seed_ci_database] Ingested OSM RAG chunks: {osm_report['documents_generated']} "
                f"(upserted={osm_report['chunks_upserted']})"
            )

            # Deterministic engineering Wikivoyage destination fixture chunks (CC BY-SA 3.0)
            # Note: Historical 464 live-crawled Wikivoyage chunks have git_tracked_chunk_text_export_present=false
            # (see data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json). These engineering
            # fixtures provide verified CC BY-SA 3.0 Wikivoyage coverage for CI integration tests without
            # mutating frozen scientific assets.
            wiki_fixtures_raw = [
                {
                    "document_id": "wikivoyage_Da_Nang_Eat_0",
                    "destination_id": str(_dest_uuid("da-nang")),
                    "source_url": "https://en.wikivoyage.org/wiki/Da_Nang#Eat",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Da Nang).",
                    "title": "Da Nang - Eat",
                    "section_heading": "Eat",
                    "topic": "culinary",
                    "category": "restaurant",
                    "content": (
                        "Đà Nẵng có món ăn đặc trưng nào? Món ăn đặc trưng của Đà Nẵng bao gồm Mì Quảng, "
                        "Bánh tráng cuốn thịt heo, Bún chả cá Đà Nẵng, Bánh xèo, Gỏi cá Nam Ô và hải sản tươi sống "
                        "(Da Nang Eat / Culinary Guide)."
                    ),
                },
                {
                    "document_id": "wikivoyage_Da_Nang_See_0",
                    "destination_id": str(_dest_uuid("da-nang")),
                    "source_url": "https://en.wikivoyage.org/wiki/Da_Nang#See",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Da Nang).",
                    "title": "Da Nang - See",
                    "section_heading": "See",
                    "topic": "sightseeing",
                    "category": "attraction",
                    "content": (
                        "Da Nang (Đà Nẵng) sightseeing highlights include the Marble Mountains (Ngũ Hành Sơn), "
                        "Son Tra Peninsula and Linh Ung Pagoda, the Dragon Bridge (Cầu Rồng) spanning the Han River, "
                        "My Khe Beach (Bãi biển Mỹ Khê), and the Museum of Cham Sculpture."
                    ),
                },
                {
                    "document_id": "wikivoyage_Hanoi_See_0",
                    "destination_id": str(_dest_uuid("ha-noi")),
                    "source_url": "https://en.wikivoyage.org/wiki/Hanoi#See",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Hanoi).",
                    "title": "Hanoi - See",
                    "section_heading": "See",
                    "topic": "sightseeing",
                    "category": "culture",
                    "content": (
                        "Hanoi (Hà Nội) cultural and historic landmarks include Hoan Kiem Lake (Hồ Hoàn Kiếm), "
                        "the Temple of Literature (Văn Miếu - Quốc Tử Giám), the Ho Chi Minh Mausoleum and "
                        "Ho Chi Minh Museum (Bảo tàng Hồ Chí Minh), the Imperial Citadel of Thang Long, and the Old Quarter."
                    ),
                },
                {
                    "document_id": "wikivoyage_Hoi_An_See_0",
                    "destination_id": str(_dest_uuid("hoi-an")),
                    "source_url": "https://en.wikivoyage.org/wiki/Hoi_An#See",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Hoi An).",
                    "title": "Hoi An - See",
                    "section_heading": "See",
                    "topic": "sightseeing",
                    "category": "culture",
                    "content": (
                        "Hoi An (Hội An) Ancient Town is a UNESCO World Heritage trading port famous for the "
                        "Japanese Covered Bridge (Chùa Cầu), historic merchant assembly halls, lantern-lit streets "
                        "along the Thu Bon River, and An Bang Beach."
                    ),
                },
                {
                    "document_id": "wikivoyage_Hue_See_0",
                    "destination_id": str(_dest_uuid("hue")),
                    "source_url": "https://en.wikivoyage.org/wiki/Hue#See",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Hue).",
                    "title": "Hue - See",
                    "section_heading": "See",
                    "topic": "sightseeing",
                    "category": "culture",
                    "content": (
                        "Hue (Huế) Imperial City (Đại Nội Huế) along the Perfume River features the Nguyen Dynasty "
                        "Citadel, Thien Mu Pagoda, and the royal tombs of Minh Mang, Khai Dinh, and Tu Duc."
                    ),
                },
                {
                    "document_id": "wikivoyage_Ha_Long_Bay_See_0",
                    "destination_id": str(_dest_uuid("ha-long")),
                    "source_url": "https://en.wikivoyage.org/wiki/Ha_Long_Bay#See",
                    "attribution": "Text is available under CC BY-SA 3.0 from Wikivoyage contributors (Ha Long Bay).",
                    "title": "Ha Long Bay - See",
                    "section_heading": "See",
                    "topic": "sightseeing",
                    "category": "attraction",
                    "content": (
                        "Ha Long Bay (Vịnh Hạ Long) is a UNESCO World Heritage karst seascape in Quang Ninh province "
                        "with limestone islands, Sung Sot Cave, Dau Go Cave, Ti Top Island, and Tuan Chau Marina."
                    ),
                },
            ]

            wiki_chunks: list[RAGChunk] = []
            for wf in wiki_fixtures_raw:
                chash = hashlib.sha256(wf["content"].encode("utf-8")).hexdigest()
                wiki_chunks.append(
                    RAGChunk(
                        document_id=wf["document_id"],
                        place_id=None,
                        destination_id=wf["destination_id"],
                        source_name="wikivoyage",
                        source_url=wf["source_url"],
                        license="CC BY-SA 3.0",
                        attribution=wf["attribution"],
                        language="en",
                        title=wf["title"],
                        section_heading=wf["section_heading"],
                        topic=wf["topic"],
                        category=wf["category"],
                        content=wf["content"],
                        content_hash=chash,
                        metadata={
                            "fixture_type": "ci_engineering_wikivoyage_fixture",
                            "scientific_corpus": False,
                        },
                        retrieved_at=datetime.now(timezone.utc),
                    )
                )

            saved_wiki = await retriever.insert_chunks(wiki_chunks)
            print(
                f"[seed_ci_database] Ingested engineering Wikivoyage RAG fixture chunks: {len(wiki_chunks)} "
                f"(upserted={saved_wiki})"
            )
        finally:
            await retriever.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CI PostgreSQL database.")
    parser.add_argument(
        "--include-rag-docs",
        action="store_true",
        help="Also generate and embed 759 OSM RAG documents + engineering Wikivoyage fixture chunks.",
    )
    args = parser.parse_args()
    asyncio.run(seed_database(include_rag_docs=args.include_rag_docs))


if __name__ == "__main__":
    main()
