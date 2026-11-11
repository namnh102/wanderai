#!/usr/bin/env python3
"""Deterministic CI Database Bootstrap & RAG Ingestion for GoMate / WanderAI (PROD-CI-05).

Fail-closed safety guarantees (CORRECTIVE-01 / C01-F01 & C01-F03):
- Requires explicit CI_DATABASE_URL (zero fallback to DATABASE_URL or standard 'wanderai' dev DB).
- Requires ALLOW_DESTRUCTIVE_CI_SEED=1 and CI=true (or GITHUB_ACTIONS=true).
- Rejects production/staging/development runtime environment flags and non-loopback hosts.
- Enforces target DB name matching ^wanderai_ci(_[a-z0-9_]+)?$ both in parsed DSN and via live
  PostgreSQL `SELECT current_database()` BEFORE executing `TRUNCATE ... CASCADE`.
- Never attributes synthetic CI engineering fixtures as Wikivoyage / CC BY-SA 3.0; any CI-only
  RAG fixture chunks use `source_name='ci_fixture'`, `urn:gomate:ci-fixture:*`,
  `license='INTERNAL-CI-FIXTURE-ONLY'`, and non-citable metadata isolated by RAGRetriever.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

ALLOWED_CI_DB_PATTERN = re.compile(r"^wanderai_ci(_[a-z0-9_]+)?$")
ALLOWED_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
FORBIDDEN_ENV_VALUES = frozenset({"production", "prod", "staging", "development", "dev"})
ENV_INDICATOR_KEYS = ("NODE_ENV", "APP_ENV", "ENVIRONMENT", "DEPLOY_ENV")

CI_FIXTURE_SOURCE_NAME = "ci_fixture"
CI_FIXTURE_LICENSE = "INTERNAL-CI-FIXTURE-ONLY"
CI_FIXTURE_URN_PREFIX = "urn:gomate:ci-fixture:"
CI_FIXTURE_ATTRIBUTION = (
    "GoMate internal CI engineering fixture — synthetic text, NOT Wikivoyage, "
    "NOT for user citation or scientific evaluation."
)


class UnsafeSeedTargetError(RuntimeError):
    """Raised when destructive CI seeding is invoked outside an explicit isolated CI database."""


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


def validate_ci_seed_environment(env: Mapping[str, str] | None = None) -> None:
    """Fail closed unless explicit destructive CI flags are present and non-CI envs are absent."""
    active_env = os.environ if env is None else env

    if active_env.get("ALLOW_DESTRUCTIVE_CI_SEED") != "1":
        raise UnsafeSeedTargetError(
            "Refusing destructive CI seed: ALLOW_DESTRUCTIVE_CI_SEED='1' is required."
        )

    is_ci = str(active_env.get("CI", "")).lower() == "true"
    is_gha = str(active_env.get("GITHUB_ACTIONS", "")).lower() == "true"
    if not (is_ci or is_gha):
        raise UnsafeSeedTargetError(
            "Refusing destructive CI seed: CI='true' or GITHUB_ACTIONS='true' is required."
        )

    for key in ENV_INDICATOR_KEYS:
        raw_val = active_env.get(key)
        if raw_val is None or raw_val.strip() == "":
            continue
        normalized = raw_val.strip().lower()
        if normalized in FORBIDDEN_ENV_VALUES or normalized not in {"ci", "test"}:
            raise UnsafeSeedTargetError(
                f"Refusing destructive CI seed: forbidden environment {key}={raw_val!r} "
                "(only unset, 'ci', or 'test' is allowed)."
            )


def validate_ci_seed_dsn(raw_url: str | None) -> tuple[str, str]:
    """Validate CI PostgreSQL DSN and return (clean_asyncpg_dsn, db_name)."""
    if raw_url is None or not raw_url.strip():
        raise UnsafeSeedTargetError(
            "Refusing destructive CI seed: CI_DATABASE_URL is missing or empty "
            "(fallback to DATABASE_URL / 'wanderai' is forbidden)."
        )

    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: unsupported URL scheme {parsed.scheme!r}."
        )

    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_LOOPBACK_HOSTS:
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: non-loopback host {parsed.hostname!r} is forbidden."
        )

    db_path = parsed.path.lstrip("/")
    if not db_path or "/" in db_path:
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: invalid database path {parsed.path!r}."
        )

    if not ALLOWED_CI_DB_PATTERN.fullmatch(db_path):
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: target database {db_path!r} does not match "
            f"dedicated CI pattern {ALLOWED_CI_DB_PATTERN.pattern!r}."
        )

    clean_dsn = urlunsplit((parsed.scheme, parsed.netloc, f"/{db_path}", "", ""))
    return clean_dsn, db_path


def resolve_verified_ci_seed_target(
    ci_database_url: str | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve and validate both environment and target CI DSN without any fallback."""
    active_env = os.environ if env is None else env
    validate_ci_seed_environment(active_env)
    candidate_url = ci_database_url if ci_database_url is not None else active_env.get("CI_DATABASE_URL")
    return validate_ci_seed_dsn(candidate_url)


async def verify_live_ci_database_connection(
    conn: Any, expected_db_name: str
) -> dict[str, Any]:
    """Verify live PostgreSQL session identity BEFORE executing TRUNCATE ... CASCADE."""
    live_db = await conn.fetchval("SELECT current_database()")
    if live_db != expected_db_name or not ALLOWED_CI_DB_PATTERN.fullmatch(str(live_db or "")):
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: live current_database()={live_db!r} "
            f"does not match expected CI database {expected_db_name!r}."
        )

    in_recovery = await conn.fetchval("SELECT pg_is_in_recovery()")
    if in_recovery is not False:
        raise UnsafeSeedTargetError(
            f"Refusing destructive CI seed: unexpected pg_is_in_recovery()={in_recovery!r}."
        )

    server_addr = await conn.fetchval("SELECT host(inet_server_addr())")
    if server_addr is not None:
        try:
            ip_obj = ipaddress.ip_address(str(server_addr))
        except ValueError as exc:
            raise UnsafeSeedTargetError(
                f"Refusing destructive CI seed: unparseable inet_server_addr()={server_addr!r}."
            ) from exc
        if not ip_obj.is_loopback:
            raise UnsafeSeedTargetError(
                f"Refusing destructive CI seed: live server address {server_addr!r} is not loopback."
            )

    return {
        "current_database": live_db,
        "in_recovery": in_recovery,
        "server_addr": server_addr,
    }


def build_ci_engineering_fixture_chunks() -> list[Any]:
    """Build synthetic CI engineering fixture chunks with explicit non-Wikivoyage provenance.

    Note: Historical 464 live-crawled Wikivoyage chunks have git_tracked_chunk_text_export_present=false
    (see data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json). These CI-only chunks
    never impersonate Wikivoyage or CC BY-SA 3.0 and are excluded from production/user retrieval.
    """
    from app.rag.chunker import RAGChunk

    fixtures_raw = [
        {
            "document_id": "ci-fixture-da-nang-overview-0",
            "destination_id": str(_dest_uuid("da-nang")),
            "source_url": f"{CI_FIXTURE_URN_PREFIX}da-nang-overview",
            "title": "CI Engineering Fixture — Da Nang Overview",
            "section_heading": "CI Synthetic Overview",
            "topic": "ci_engineering_fixture",
            "category": "attraction",
            "content": (
                "[INTERNAL CI FIXTURE — NOT WIKIVOYAGE] Synthetic engineering test document "
                "for Da Nang pgvector plumbing validation only."
            ),
        },
        {
            "document_id": "ci-fixture-ha-noi-overview-0",
            "destination_id": str(_dest_uuid("ha-noi")),
            "source_url": f"{CI_FIXTURE_URN_PREFIX}ha-noi-overview",
            "title": "CI Engineering Fixture — Ha Noi Overview",
            "section_heading": "CI Synthetic Overview",
            "topic": "ci_engineering_fixture",
            "category": "culture",
            "content": (
                "[INTERNAL CI FIXTURE — NOT WIKIVOYAGE] Synthetic engineering test document "
                "for Ha Noi pgvector plumbing validation only."
            ),
        },
    ]

    chunks: list[RAGChunk] = []
    retrieved_ts = datetime(2026, 11, 10, 0, 0, 0, tzinfo=timezone.utc)
    for item in fixtures_raw:
        chash = hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
        chunks.append(
            RAGChunk(
                chunk_id=item["document_id"],
                document_id=item["document_id"],
                place_id=None,
                destination_id=item["destination_id"],
                source_name=CI_FIXTURE_SOURCE_NAME,
                source_url=item["source_url"],
                license=CI_FIXTURE_LICENSE,
                attribution=CI_FIXTURE_ATTRIBUTION,
                language="en",
                title=item["title"],
                section_heading=item["section_heading"],
                topic=item["topic"],
                category=item["category"],
                content=item["content"],
                content_hash=chash,
                metadata={
                    "fixture_type": "ci_engineering_fixture",
                    "is_ci_fixture": True,
                    "scientific_corpus": False,
                    "user_citable": False,
                },
                retrieved_at=retrieved_ts,
            )
        )
    return chunks


async def seed_database(
    include_rag_docs: bool = False,
    ci_database_url: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    clean_dsn, expected_db_name = resolve_verified_ci_seed_target(
        ci_database_url=ci_database_url,
        env=env,
    )

    conn = await asyncpg.connect(clean_dsn)
    try:
        live_identity = await verify_live_ci_database_connection(conn, expected_db_name)

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
            # Verified dedicated CI DB above — safe to reset domain tables deterministically
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
            f"[seed_ci_database] Verified target DB={live_identity['current_database']}; "
            f"seeded places={total_places}, verified_osm_sources={total_osm}"
        )

    finally:
        await conn.close()

    summary: dict[str, Any] = {
        "database": expected_db_name,
        "places": int(total_places),
        "verified_osm_sources": int(total_osm),
        "osm_rag_chunks": 0,
        "ci_fixture_chunks": 0,
    }

    if include_rag_docs:
        from app.rag.ingestion import WikivoyageIngester
        from app.rag.retriever import RAGRetriever

        retriever = RAGRetriever(database_url=clean_dsn)
        ingester = WikivoyageIngester(retriever=retriever)
        try:
            osm_report = await ingester.ingest_canonical_places()
            print(
                f"[seed_ci_database] Ingested OSM RAG chunks: {osm_report['documents_generated']} "
                f"(upserted={osm_report['chunks_upserted']})"
            )

            fixture_chunks = build_ci_engineering_fixture_chunks()
            saved_fixtures = await retriever.insert_chunks(fixture_chunks)
            print(
                f"[seed_ci_database] Ingested isolated CI engineering fixture chunks "
                f"(source_name='{CI_FIXTURE_SOURCE_NAME}', non-citable): {len(fixture_chunks)} "
                f"(upserted={saved_fixtures})"
            )
            summary["osm_rag_chunks"] = int(osm_report["documents_generated"])
            summary["ci_fixture_chunks"] = int(saved_fixtures)
        finally:
            await retriever.close()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dedicated CI PostgreSQL database.")
    parser.add_argument(
        "--include-rag-docs",
        action="store_true",
        help="Also generate and embed 759 verified OSM RAG documents + isolated non-citable CI fixture chunks.",
    )
    args = parser.parse_args()
    asyncio.run(seed_database(include_rag_docs=args.include_rag_docs))


if __name__ == "__main__":
    main()
