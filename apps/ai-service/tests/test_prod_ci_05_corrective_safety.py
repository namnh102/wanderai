"""PROD-CI-05 CORRECTIVE-01 & CORRECTIVE-02 Verification Suite.

Covers:
- C01-F01 (P0): Fail-closed destructive CI seed guards (offline + live DB negative tests).
- C01-F02 (P0): Migration & rollback safety for `trips` pre-existing columns and `documents`
  pre-existing/unbackfilled/duplicate legacy rows (static SQL + live PostgreSQL replay with
  before/after integrity evidence).
- C01-F03 (P1): Explicit non-Wikivoyage CI engineering fixture provenance & multi-layer
  retrieval/citation isolation.
- C01-F04 (P2): Transparent separation of engineering fixture tests from the missing 464
  historical live-crawled Wikivoyage corpus (`git_tracked_chunk_text_export_present=false`).
- C02-F01 (P1): Non-destructive & fail-closed rollback (`down.sql` + `ROLLBACK_AND_RECOVERY.md`)
  preserving pre-existing out-of-Prisma RAG enrichment columns/vectors (`source_name`,
  `source_url`, `content_hash`, `embedding`, `license`) without fabricating provenance.
- C02-F02 (P1): `RAGRetriever` governed source-family compatibility (Wikipedia, Wikidata,
  Overture Maps, governance-verified `OPEN_REUSABLE` official/open-government sources) while
  continuing to block `ci_fixture`, `synthetic`, `mock`, `unverified_legacy`, `user_citable=false`,
  commercial/restricted platforms, and incomplete provenance/licensing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
from fastapi import Request
from fastapi.testclient import TestClient
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.main import app
from app.rag.embedder import MockEmbedder
from app.rag.retriever import GOVERNED_PRODUCTION_DOCUMENT_SQL, RAGRetriever
from app.security.internal_auth import InternalPrincipal, require_internal_principal
from app.services.rag import RAGService
from scripts import audit_w07_b1a_existing_poi_knowledge as w07_b1a
from scripts import seed_ci_database as seed_mod

MIGRATIONS_DIR = REPO_ROOT / "apps" / "backend" / "prisma" / "migrations"
NEW_MIGRATION_DIR = MIGRATIONS_DIR / "20261110000000_sync_schema_drift"
SCHEMA_PRISMA_PATH = REPO_ROOT / "apps" / "backend" / "prisma" / "schema.prisma"
INIT_SQL_PATH = REPO_ROOT / "database" / "init.sql"

PRE_DRIFT_MIGRATIONS = [
    "20260922161107_init",
    "20261001073816_add_place_sources",
    "20261001083200_add_trip_context_fields",
    "20261004010000_provenance_remediation",
    "20261004020000_provenance_remediation_followup",
]


def _admin_dsn_and_base() -> tuple[str, str]:
    """Return (postgres_admin_dsn, base_dsn_prefix) from configured DATABASE_URL."""
    from app.config import settings

    raw = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    parsed = urlsplit(raw)
    admin_dsn = urlunsplit((parsed.scheme, parsed.netloc, "/postgres", "", ""))
    base_dsn = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return admin_dsn, base_dsn


def _run_db_test(coro_fn):
    """Execute async DB test against PostgreSQL; skip offline unless REQUIRE_DB_TESTS=1."""

    async def _runner():
        admin_dsn, base_dsn = _admin_dsn_and_base()
        try:
            admin_conn = await asyncpg.connect(admin_dsn)
        except Exception as exc:  # noqa: BLE001
            if os.environ.get("REQUIRE_DB_TESTS") == "1":
                raise
            pytest.skip(f"PostgreSQL unavailable offline: {exc}")
        try:
            return await coro_fn(admin_conn, base_dsn)
        finally:
            await admin_conn.close()

    return asyncio.run(_runner())


async def _recreate_scratch_db(admin_conn: asyncpg.Connection, db_name: str) -> None:
    await admin_conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1 AND pid <> pg_backend_pid()
        """,
        db_name,
    )
    await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    await admin_conn.execute(f'CREATE DATABASE "{db_name}"')


async def _drop_scratch_db(admin_conn: asyncpg.Connection, db_name: str) -> None:
    await admin_conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1 AND pid <> pg_backend_pid()
        """,
        db_name,
    )
    await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


# ============================================================================
# C01-F01 — Destructive CI Seed Safety Guards (Offline + Live DB Negative Tests)
# ============================================================================


class TestC01F01SeedSafetyGuards:
    """Negative and boundary tests proving scripts/seed_ci_database.py fails closed."""

    VALID_ENV = {
        "CI": "true",
        "ALLOW_DESTRUCTIVE_CI_SEED": "1",
        "CI_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/wanderai_ci_test",
    }

    def test_seed_rejects_missing_ci_database_url_even_when_database_url_is_set(self):
        env = {
            "CI": "true",
            "ALLOW_DESTRUCTIVE_CI_SEED": "1",
            "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/wanderai_ci_test",
        }
        with pytest.raises(seed_mod.UnsafeSeedTargetError, match="CI_DATABASE_URL"):
            seed_mod.resolve_verified_ci_seed_target(env=env)

    @pytest.mark.parametrize(
        "bad_db_name",
        [
            "wanderai",
            "wanderai_dev",
            "wanderai_prod",
            "wanderai_staging",
            "postgres",
            "template0",
            "template1",
            "dev_wanderai_ci",
            "wanderai_ci-hyphen",
            "wanderai_ci/extra",
            "",
        ],
    )
    def test_seed_rejects_out_of_scope_database_names(self, bad_db_name: str):
        url = f"postgresql://postgres:postgres@localhost:5432/{bad_db_name}"
        with pytest.raises(seed_mod.UnsafeSeedTargetError):
            seed_mod.validate_ci_seed_dsn(url)

    @pytest.mark.parametrize(
        ("good_url", "expected_clean", "expected_db"),
        [
            (
                "postgresql://postgres:postgres@localhost:5432/wanderai_ci?schema=public",
                "postgresql://postgres:postgres@localhost:5432/wanderai_ci",
                "wanderai_ci",
            ),
            (
                "postgresql://postgres:postgres@127.0.0.1:5432/wanderai_ci_test?schema=public",
                "postgresql://postgres:postgres@127.0.0.1:5432/wanderai_ci_test",
                "wanderai_ci_test",
            ),
            (
                "postgres://postgres:postgres@[::1]:5432/wanderai_ci_e2e_01",
                "postgres://postgres:postgres@[::1]:5432/wanderai_ci_e2e_01",
                "wanderai_ci_e2e_01",
            ),
        ],
    )
    def test_seed_accepts_dedicated_ci_database_names_and_strips_prisma_query(
        self, good_url: str, expected_clean: str, expected_db: str
    ):
        clean_dsn, db_name = seed_mod.validate_ci_seed_dsn(good_url)
        assert clean_dsn == expected_clean
        assert db_name == expected_db

    @pytest.mark.parametrize(
        "bad_url",
        [
            "postgresql://postgres:postgres@db.internal:5432/wanderai_ci_test",
            "postgresql://postgres:postgres@10.0.0.15:5432/wanderai_ci_test",
            "postgresql://postgres:postgres@192.168.1.20:5432/wanderai_ci_test",
            "postgresql://postgres:postgres@ep-prod.us-east-2.aws.neon.tech:5432/wanderai_ci_test",
            "postgresql://postgres:postgres@host.docker.internal:5432/wanderai_ci_test",
            "mysql://postgres:postgres@localhost:5432/wanderai_ci_test",
            "http://localhost:5432/wanderai_ci_test",
        ],
    )
    def test_seed_rejects_non_loopback_hosts_and_unsupported_schemes(self, bad_url: str):
        with pytest.raises(seed_mod.UnsafeSeedTargetError):
            seed_mod.validate_ci_seed_dsn(bad_url)

    @pytest.mark.parametrize(
        "bad_env",
        [
            {"CI": "true", "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test"},
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "true",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "0",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "false",
                "GITHUB_ACTIONS": "false",
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "NODE_ENV": "production",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "NODE_ENV": "development",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "APP_ENV": "staging",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
            {
                "CI": "true",
                "ALLOW_DESTRUCTIVE_CI_SEED": "1",
                "DEPLOY_ENV": "prod",
                "CI_DATABASE_URL": "postgresql://localhost:5432/wanderai_ci_test",
            },
        ],
    )
    def test_seed_rejects_missing_destructive_opt_in_or_forbidden_runtime_env(
        self, bad_env: dict[str, str]
    ):
        with pytest.raises(seed_mod.UnsafeSeedTargetError):
            seed_mod.resolve_verified_ci_seed_target(env=bad_env)

    @pytest.mark.parametrize(
        "fetchval_side_effect",
        [
            ["wanderai"],  # live DB name mismatch (e.g. proxy/bouncer rerouted to dev DB)
            ["wanderai_ci_test", True],  # standby / recovery replica
            ["wanderai_ci_test", False, "203.0.113.42"],  # non-loopback server IP
        ],
    )
    def test_seed_live_connection_guard_aborts_before_truncate_on_mismatch(
        self, fetchval_side_effect: list[object]
    ):
        executed_sql: list[str] = []

        class _FakeConn:
            def __init__(self):
                self.closed = False
                self._fetch_iter = iter(fetchval_side_effect)

            async def fetchval(self, query: str, *_args: object):
                executed_sql.append(query.strip())
                return next(self._fetch_iter)

            async def execute(self, query: str, *_args: object):
                executed_sql.append(query.strip())

            async def close(self):
                self.closed = True

        fake_conn = _FakeConn()

        async def _run():
            with patch.object(seed_mod.asyncpg, "connect", AsyncMock(return_value=fake_conn)):
                with pytest.raises(seed_mod.UnsafeSeedTargetError):
                    await seed_mod.seed_database(env=dict(self.VALID_ENV))

        asyncio.run(_run())
        assert fake_conn.closed is True
        assert not any("TRUNCATE" in sql.upper() for sql in executed_sql)

    def test_live_postgres_seed_refuses_out_of_scope_database_without_touching_rows(self):
        scratch_db = "wanderai_dev_sentinel_guard"

        async def _body(admin_conn: asyncpg.Connection, base_dsn: str):
            await _recreate_scratch_db(admin_conn, scratch_db)
            target_dsn = f"{base_dsn}/{scratch_db}"
            try:
                dev_conn = await asyncpg.connect(target_dsn)
                try:
                    await dev_conn.execute(
                        "CREATE TABLE places (id INT PRIMARY KEY, name TEXT NOT NULL)"
                    )
                    await dev_conn.execute(
                        "INSERT INTO places (id, name) VALUES (42, 'DO_NOT_TRUNCATE_DEV_DATA')"
                    )
                finally:
                    await dev_conn.close()

                with pytest.raises(seed_mod.UnsafeSeedTargetError):
                    await seed_mod.seed_database(
                        ci_database_url=target_dsn,
                        env={"CI": "true", "ALLOW_DESTRUCTIVE_CI_SEED": "1"},
                    )

                verify_conn = await asyncpg.connect(target_dsn)
                try:
                    preserved = await verify_conn.fetchrow(
                        "SELECT id, name FROM places WHERE id = 42"
                    )
                    assert preserved is not None
                    assert preserved["name"] == "DO_NOT_TRUNCATE_DEV_DATA"
                finally:
                    await verify_conn.close()
            finally:
                await _drop_scratch_db(admin_conn, scratch_db)

        _run_db_test(_body)


# ============================================================================
# C01-F02 — Migration & Rollback Compatibility Tests
# ============================================================================


class TestC01F02MigrationAndRollbackSafety:
    """Static and live PostgreSQL replay tests for migration/rollback safety."""

    def test_migration_and_down_sql_static_safety_invariants(self):
        hist_trips_sql = (
            MIGRATIONS_DIR / "20261001083200_add_trip_context_fields" / "migration.sql"
        ).read_text(encoding="utf-8")
        migration_sql = (NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8")
        down_sql = (NEW_MIGRATION_DIR / "down.sql").read_text(encoding="utf-8")
        schema_prisma = SCHEMA_PRISMA_PATH.read_text(encoding="utf-8")

        # Historical migration already owns trips.currency, trips.interests, trips.travel_style
        for col in ('"currency"', '"interests"', '"travel_style"'):
            assert col in hist_trips_sql

        # New migration and down.sql must never alter trips or drop pre-existing trip columns
        for sql_text in (migration_sql, down_sql):
            non_comment_lines = "\n".join(
                line for line in sql_text.splitlines() if not line.lstrip().startswith("--")
            )
            assert 'ALTER TABLE "trips"' not in non_comment_lines
            for col in ('"currency"', '"interests"', '"travel_style"'):
                assert col not in non_comment_lines

        # Migration must never delete/truncate documents or stamp fake Wikivoyage/CC BY-SA defaults
        non_comment_up = "\n".join(
            line for line in migration_sql.splitlines() if not line.lstrip().startswith("--")
        )
        assert "DELETE FROM" not in non_comment_up.upper()
        assert "TRUNCATE" not in non_comment_up.upper()
        assert "DEFAULT 'wikivoyage'" not in non_comment_up
        assert "DEFAULT 'CC BY-SA 3.0'" not in non_comment_up
        assert 'ADD COLUMN IF NOT EXISTS "content_hash" VARCHAR(64) NOT NULL DEFAULT' not in non_comment_up

        # schema.prisma Document model must align with non-fabricated defaults
        doc_model_block = schema_prisma.split("model Document {", 1)[1]
        assert '@default("unverified_legacy")' in doc_model_block
        assert '@default("UNVERIFIED_LEGACY")' in doc_model_block
        assert '@default("wikivoyage")' not in doc_model_block
        assert '@default("CC BY-SA 3.0")' not in doc_model_block

    def test_live_migration_and_rollback_preserves_legacy_documents_and_trip_columns(self):
        scratch_db = "wanderai_ci_mig_legacy"

        async def _body(admin_conn: asyncpg.Connection, base_dsn: str):
            await _recreate_scratch_db(admin_conn, scratch_db)
            target_dsn = f"{base_dsn}/{scratch_db}"
            try:
                conn = await asyncpg.connect(target_dsn)
                try:
                    # 1. Replay init.sql + all 5 historical migrations prior to 20261110000000_sync_schema_drift
                    await conn.execute(INIT_SQL_PATH.read_text(encoding="utf-8"))
                    for mig_name in PRE_DRIFT_MIGRATIONS:
                        mig_sql = (MIGRATIONS_DIR / mig_name / "migration.sql").read_text(
                            encoding="utf-8"
                        )
                        await conn.execute(mig_sql)

                    # Verify pre-migration schema state: trips has currency/travel_style/interests, documents lacks content_hash
                    trip_cols_before = {
                        r["column_name"]
                        for r in await conn.fetch(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'trips'"
                        )
                    }
                    assert {"currency", "travel_style", "interests"} <= trip_cols_before

                    doc_cols_before = {
                        r["column_name"]
                        for r in await conn.fetch(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'documents'"
                        )
                    }
                    assert "content_hash" not in doc_cols_before
                    assert {"id", "content", "source", "category", "metadata", "created_at"} <= doc_cols_before

                    # 2. Seed a pre-existing user + trip using currency, travel_style, interests
                    user_id = uuid.uuid4()
                    trip_id = uuid.uuid4()
                    await conn.execute(
                        """
                        INSERT INTO users (id, email, password_hash, role, is_verified, created_at, updated_at)
                        VALUES ($1, 'mig_owner@wanderai.test', 'hash', 'USER', true, NOW(), NOW())
                        """,
                        user_id,
                    )
                    await conn.execute(
                        """
                        INSERT INTO trips (
                            id, user_id, title, currency, travel_style, interests, status, created_at, updated_at
                        ) VALUES (
                            $1, $2, 'Pre-migration Trip', 'EUR', 'LUXURY'::"TravelStyle",
                            ARRAY['culture', 'beach'], 'PLANNED'::"TripStatus", NOW(), NOW()
                        )
                        """,
                        trip_id,
                        user_id,
                    )

                    # 3. Insert 5 pre-existing legacy documents (no content_hash column exists yet!)
                    legacy_docs = [
                        (uuid.uuid4(), "Duplicate legacy note", "manual_import", "guide", None),
                        (uuid.uuid4(), "Duplicate legacy note", "manual_import", "guide", None),
                        (uuid.uuid4(), "", None, None, "null"),
                        (uuid.uuid4(), "Array metadata note", "legacy_blog", "tips", '["tag1", "tag2"]'),
                        (
                            uuid.uuid4(),
                            "Object metadata note",
                            "internal_memo",
                            "notes",
                            '{"editor": "alice"}',
                        ),
                    ]
                    for did, content, src, cat, meta_raw in legacy_docs:
                        await conn.execute(
                            """
                            INSERT INTO documents (id, content, source, category, metadata)
                            VALUES ($1, $2, $3, $4, $5::jsonb)
                            """,
                            did,
                            content,
                            src,
                            cat,
                            meta_raw,
                        )

                    before_rows = await conn.fetch(
                        "SELECT id, content, source, category FROM documents ORDER BY id"
                    )
                    assert len(before_rows) == 5

                    # 4. Apply 20261110000000_sync_schema_drift/migration.sql
                    up_sql = (NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8")
                    await conn.execute(up_sql)

                    # 5. Verify AFTER migration integrity: zero row deletion, zero fake provenance
                    after_rows = await conn.fetch(
                        """
                        SELECT id, document_id, content, source, category, source_name,
                               source_url, license, language, content_hash, embedding_model, metadata
                        FROM documents
                        ORDER BY id
                        """
                    )
                    assert len(after_rows) == len(before_rows) == 5
                    assert [
                        (r["id"], r["content"], r["source"], r["category"]) for r in after_rows
                    ] == [
                        (r["id"], r["content"], r["source"], r["category"]) for r in before_rows
                    ]

                    seen_hashes: set[str] = set()
                    for row in after_rows:
                        assert row["source_name"] == "unverified_legacy"
                        assert row["source_name"] not in ("wikivoyage", "osm")
                        assert row["license"] == "UNVERIFIED_LEGACY"
                        assert row["license"] not in ("CC BY-SA 3.0", "ODbL 1.0")
                        assert row["language"] == "und"
                        assert row["embedding_model"] == "unembedded_legacy"
                        assert len(row["content_hash"]) == 64
                        int(row["content_hash"], 16)  # valid 64-char hex
                        seen_hashes.add(row["content_hash"])

                        meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                        assert isinstance(meta, dict)
                        assert meta["legacy_migration_backfill"] is True
                        assert meta["user_citable"] is False
                        assert meta["scientific_corpus"] is False
                        assert meta["legacy_content_hash_backfilled"] is True
                        if row["source"] is not None:
                            assert meta["legacy_source_column"] == row["source"]
                        if row["content"] == "Array metadata note":
                            assert meta["legacy_raw_metadata"] == ["tag1", "tag2"]
                        if row["content"] == "Object metadata note":
                            assert meta["editor"] == "alice"

                    assert len(seen_hashes) == 5  # even duplicate content rows got distinct deterministic hashes

                    # Verify content_hash has NO default '' so omitted content_hash fails closed
                    with pytest.raises(asyncpg.NotNullViolationError):
                        await conn.execute(
                            "INSERT INTO documents (id, content) VALUES (gen_random_uuid(), 'missing hash')"
                        )

                    # Verify production RAGRetriever never exposes backfilled legacy rows even if embedded
                    embedder = MockEmbedder(dimension=384)
                    vec_str = "[" + ",".join(str(x) for x in embedder.embed_text("Duplicate legacy note")) + "]"
                    await conn.execute(
                        "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                        vec_str,
                        after_rows[0]["id"],
                    )
                    retriever = RAGRetriever(embedder=embedder, database_url=target_dsn)
                    try:
                        prod_hits = await retriever.search(
                            "Duplicate legacy note", top_k=10, min_similarity=0.0
                        )
                        assert prod_hits == []
                    finally:
                        await retriever.close()

                    # 6. Apply down.sql and verify trips columns + legacy documents survive intact
                    down_sql = (NEW_MIGRATION_DIR / "down.sql").read_text(encoding="utf-8")
                    await conn.execute(down_sql)

                    trip_after_down = await conn.fetchrow(
                        "SELECT title, currency, travel_style::text AS travel_style, interests "
                        "FROM trips WHERE id = $1",
                        trip_id,
                    )
                    assert trip_after_down is not None
                    assert trip_after_down["currency"] == "EUR"
                    assert trip_after_down["travel_style"] == "LUXURY"
                    assert list(trip_after_down["interests"]) == ["culture", "beach"]

                    docs_after_down = await conn.fetch(
                        "SELECT id, content, source, category FROM documents ORDER BY id"
                    )
                    assert len(docs_after_down) == 5
                    assert [
                        (r["id"], r["content"], r["source"], r["category"]) for r in docs_after_down
                    ] == [
                        (r["id"], r["content"], r["source"], r["category"]) for r in before_rows
                    ]

                    # 7. Re-apply migration.sql (up -> down -> up round-trip idempotency)
                    await conn.execute(up_sql)
                    re_up_count = await conn.fetchval("SELECT count(*) FROM documents")
                    assert re_up_count == 5
                    print(
                        "[C01-F02-EVIDENCE-LEGACY] "
                        + json.dumps(
                            {
                                "before_rows": len(before_rows),
                                "after_up_rows": len(after_rows),
                                "distinct_valid_hashes": len(seen_hashes),
                                "fake_wikivoyage_or_osm_rows": 0,
                                "after_down_rows": len(docs_after_down),
                                "trip_columns_preserved_after_down": {
                                    "currency": trip_after_down["currency"],
                                    "travel_style": trip_after_down["travel_style"],
                                    "interests": list(trip_after_down["interests"]),
                                },
                                "after_re_up_rows": int(re_up_count),
                            }
                        )
                    )
                finally:
                    await conn.close()
            finally:
                await _drop_scratch_db(admin_conn, scratch_db)

        _run_db_test(_body)

    def test_live_migration_repairs_invalid_and_duplicate_preexisting_backfills_without_touching_valid_rows(
        self,
    ):
        scratch_db = "wanderai_ci_mig_partial"

        async def _body(admin_conn: asyncpg.Connection, base_dsn: str):
            await _recreate_scratch_db(admin_conn, scratch_db)
            target_dsn = f"{base_dsn}/{scratch_db}"
            try:
                conn = await asyncpg.connect(target_dsn)
                try:
                    await conn.execute(INIT_SQL_PATH.read_text(encoding="utf-8"))
                    for mig_name in PRE_DRIFT_MIGRATIONS:
                        await conn.execute(
                            (MIGRATIONS_DIR / mig_name / "migration.sql").read_text(
                                encoding="utf-8"
                            )
                        )

                    # Simulate a partially altered database where columns existed without constraints/unique index
                    await conn.execute(
                        """
                        ALTER TABLE "documents"
                          ADD COLUMN "source_name" VARCHAR(50),
                          ADD COLUMN "license" VARCHAR(100),
                          ADD COLUMN "content_hash" VARCHAR(64),
                          ADD COLUMN "embedding_model" VARCHAR(100);
                        """
                    )

                    valid_id = uuid.uuid4()
                    valid_hash = hashlib.sha256(b"verified osm fact").hexdigest()
                    blank_id = uuid.uuid4()
                    malformed_id = uuid.uuid4()
                    dup_first_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
                    dup_second_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
                    shared_dup_hash = hashlib.sha256(b"shared duplicate text").hexdigest()
                    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

                    # 1. Valid pre-existing row (must NOT be modified!)
                    await conn.execute(
                        """
                        INSERT INTO documents (
                            id, content, source_name, license, content_hash, embedding_model, metadata
                        ) VALUES ($1, 'verified osm fact', 'osm', 'ODbL 1.0', $2, $3, '{"verified": true}'::jsonb)
                        """,
                        valid_id,
                        valid_hash,
                        model_name,
                    )
                    # 2. Blank content_hash & blank source_name
                    await conn.execute(
                        """
                        INSERT INTO documents (
                            id, content, source_name, license, content_hash, embedding_model
                        ) VALUES ($1, 'blank hash row', '', 'CC BY-SA 3.0', '', '')
                        """,
                        blank_id,
                    )
                    # 3. Malformed non-hex content_hash & NULL license
                    await conn.execute(
                        """
                        INSERT INTO documents (
                            id, content, source_name, license, content_hash, embedding_model
                        ) VALUES ($1, 'malformed hash row', 'manual_note', NULL, 'not-a-64-hex-sha', $2)
                        """,
                        malformed_id,
                        model_name,
                    )
                    # 4 & 5. Pre-existing duplicate (content_hash, embedding_model) pair
                    for did in (dup_first_id, dup_second_id):
                        await conn.execute(
                            """
                            INSERT INTO documents (
                                id, content, source_name, license, content_hash, embedding_model, created_at
                            ) VALUES ($1, 'shared duplicate text', 'manual_dup', 'INTERNAL', $2, $3, '2026-10-01T00:00:00Z')
                            """,
                            did,
                            shared_dup_hash,
                            model_name,
                        )

                    await conn.execute((NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8"))

                    assert await conn.fetchval("SELECT count(*) FROM documents") == 5

                    # Valid row preserved verbatim without legacy backfill flags
                    valid_after = await conn.fetchrow(
                        "SELECT source_name, license, content_hash, embedding_model, metadata "
                        "FROM documents WHERE id = $1",
                        valid_id,
                    )
                    assert valid_after["source_name"] == "osm"
                    assert valid_after["license"] == "ODbL 1.0"
                    assert valid_after["content_hash"] == valid_hash
                    assert valid_after["embedding_model"] == model_name
                    valid_meta = (
                        json.loads(valid_after["metadata"])
                        if isinstance(valid_after["metadata"], str)
                        else valid_after["metadata"]
                    )
                    assert valid_meta == {"verified": True}

                    # Blank & malformed rows safely repaired without fake Wikivoyage provenance
                    blank_after = await conn.fetchrow(
                        "SELECT source_name, content_hash, embedding_model, metadata FROM documents WHERE id = $1",
                        blank_id,
                    )
                    assert blank_after["source_name"] == "unverified_legacy"
                    assert blank_after["embedding_model"] == "unembedded_legacy"
                    assert len(blank_after["content_hash"]) == 64

                    malformed_after = await conn.fetchrow(
                        "SELECT source_name, license, content_hash, metadata FROM documents WHERE id = $1",
                        malformed_id,
                    )
                    assert malformed_after["source_name"] == "manual_note"
                    assert malformed_after["license"] == "UNVERIFIED_LEGACY"
                    assert len(malformed_after["content_hash"]) == 64
                    mal_meta = (
                        json.loads(malformed_after["metadata"])
                        if isinstance(malformed_after["metadata"], str)
                        else malformed_after["metadata"]
                    )
                    assert mal_meta["legacy_invalid_content_hash"] == "not-a-64-hex-sha"

                    # Duplicate pair: first row keeps shared_dup_hash, second row is deterministically disambiguated
                    dup1_after = await conn.fetchrow(
                        "SELECT content_hash, metadata FROM documents WHERE id = $1", dup_first_id
                    )
                    dup2_after = await conn.fetchrow(
                        "SELECT content_hash, metadata FROM documents WHERE id = $1", dup_second_id
                    )
                    assert dup1_after["content_hash"] == shared_dup_hash
                    assert dup2_after["content_hash"] != shared_dup_hash
                    assert len(dup2_after["content_hash"]) == 64
                    dup2_meta = (
                        json.loads(dup2_after["metadata"])
                        if isinstance(dup2_after["metadata"], str)
                        else dup2_after["metadata"]
                    )
                    assert dup2_meta["legacy_duplicate_of_content_hash"] == shared_dup_hash
                    assert dup2_meta["legacy_migration_backfill"] is True

                    # Unique index active
                    idx_exists = await conn.fetchval(
                        "SELECT count(*) FROM pg_indexes WHERE indexname = 'documents_content_hash_embedding_model_key'"
                    )
                    assert idx_exists == 1
                    print(
                        "[C01-F02-EVIDENCE-PARTIAL] "
                        + json.dumps(
                            {
                                "total_rows_preserved": 5,
                                "valid_osm_row_untouched": valid_after["content_hash"] == valid_hash,
                                "blank_hash_repaired_len": len(blank_after["content_hash"]),
                                "malformed_hash_repaired_len": len(malformed_after["content_hash"]),
                                "duplicate_pair_disambiguated": dup1_after["content_hash"]
                                != dup2_after["content_hash"],
                                "unique_index_active": int(idx_exists) == 1,
                            }
                        )
                    )
                finally:
                    await conn.close()
            finally:
                await _drop_scratch_db(admin_conn, scratch_db)

        _run_db_test(_body)


# ============================================================================
# C01-F03 & C01-F04 — Engineering Fixture Provenance & Historical Gap Separation
# ============================================================================


class TestC01F03AndF04FixtureIsolationAndHistoricalGap:
    """Tests ensuring CI fixtures never impersonate Wikivoyage or leak into user citations."""

    def test_ci_fixture_builder_uses_explicit_non_wikivoyage_provenance(self):
        chunks = seed_mod.build_ci_engineering_fixture_chunks()
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.source_name == "ci_fixture"
            assert chunk.source_name != "wikivoyage"
            assert chunk.source_url.startswith("urn:gomate:ci-fixture:")
            assert "wikivoyage.org" not in chunk.source_url.lower()
            assert chunk.license == "INTERNAL-CI-FIXTURE-ONLY"
            assert chunk.license != "CC BY-SA 3.0"
            assert chunk.place_id is None
            assert chunk.metadata == {
                "fixture_type": "ci_engineering_fixture",
                "is_ci_fixture": True,
                "scientific_corpus": False,
                "user_citable": False,
            }

    def test_w07_b1a_historical_464_chunk_gap_remains_transparent_and_unmodified(self):
        b1a_path = (
            REPO_ROOT / "data" / "evaluation" / "w07" / "w07_b1a_existing_poi_knowledge_audit_v1.json"
        )
        b1a_doc = json.loads(b1a_path.read_text(encoding="utf-8"))
        assert (
            b1a_doc["wikivoyage_audit"]["git_tracked_chunk_text_export_present"] is False
        )
        assert b1a_doc["wikivoyage_audit"]["total_chunks_in_freeze_v2"] == 464
        res = w07_b1a.verify_b1a_audit_artifacts(REPO_ROOT)
        assert res["status"] == "PASS"

    def test_seeded_ci_fixtures_are_stored_isolated_and_never_returned_or_cited_to_users(self):
        async def _body(_admin_conn: asyncpg.Connection, _base_dsn: str):
            retriever = RAGRetriever()
            try:
                pool = await retriever.get_pool()
                async with pool.acquire() as conn:
                    fixture_rows = await conn.fetch(
                        """
                        SELECT document_id, source_name, source_url, license, content, metadata
                        FROM documents
                        WHERE source_name = 'ci_fixture'
                        ORDER BY document_id
                        """
                    )
                    assert len(fixture_rows) == 2
                    for r in fixture_rows:
                        assert r["source_url"].startswith("urn:gomate:ci-fixture:")
                        assert r["license"] == "INTERNAL-CI-FIXTURE-ONLY"
                        meta = (
                            json.loads(r["metadata"])
                            if isinstance(r["metadata"], str)
                            else r["metadata"]
                        )
                        assert meta["is_ci_fixture"] is True
                        assert meta["scientific_corpus"] is False
                        assert meta["user_citable"] is False

                    # Zero disguised Wikivoyage fixtures anywhere in documents
                    disguised = await conn.fetchval(
                        """
                        SELECT count(*)
                        FROM documents
                        WHERE (source_name IN ('wikivoyage', 'osm') AND (
                                source_url LIKE 'urn:gomate:ci-fixture:%'
                                OR license = 'INTERNAL-CI-FIXTURE-ONLY'
                                OR COALESCE(metadata->>'is_ci_fixture', 'false') = 'true'
                                OR COALESCE(metadata->>'scientific_corpus', 'true') = 'false'
                              ))
                        """
                    )
                    assert disguised == 0

                # 1. Opt-in engineering mode CAN inspect ci_fixture pgvector embeddings
                for r in fixture_rows:
                    eng_hits = await retriever.search(
                        r["content"],
                        top_k=5,
                        source_name="ci_fixture",
                        min_similarity=0.5,
                        include_unverified=True,
                    )
                    assert any(h["document_id"] == r["document_id"] for h in eng_hits)

                    # 2. Default production mode (include_unverified=False) NEVER returns ci_fixture
                    prod_hits = await retriever.search(
                        r["content"],
                        top_k=20,
                        min_similarity=0.0,
                        include_unverified=False,
                    )
                    assert all(h["source_name"] != "ci_fixture" for h in prod_hits)
                    assert all(
                        not h["source_url"].startswith("urn:gomate:ci-fixture:")
                        for h in prod_hits
                    )
                    assert all(
                        "[INTERNAL CI FIXTURE" not in h["content"] for h in prod_hits
                    )

                # 3. RAGService + FastAPI POST /chat never expose or cite ci_fixture chunks
                rag_svc = RAGService(retriever=retriever)
                probe_query = (
                    "Synthetic engineering test document for Da Nang pgvector plumbing validation"
                )
                # Confirm probe_query strongly matches ci_fixture when unverified opt-in is enabled
                opt_in_probe = await retriever.search(
                    probe_query,
                    top_k=3,
                    source_name="ci_fixture",
                    min_similarity=0.7,
                    include_unverified=True,
                )
                assert len(opt_in_probe) >= 1

                rag_res = await rag_svc.retrieve_with_status(probe_query, top_k=5)
                assert all(
                    not u.startswith("urn:gomate:ci-fixture:") for u in rag_res.sources
                )
                assert "[INTERNAL CI FIXTURE" not in rag_res.context
                assert "[Source: ci_fixture" not in rag_res.context

                async def _principal_override(request: Request) -> InternalPrincipal:
                    body = await request.json() if request.method == "POST" else {}
                    return InternalPrincipal(
                        user_id="fixture-firewall-user",
                        bound_session_id=body.get("session_id"),
                    )

                app.dependency_overrides[require_internal_principal] = _principal_override
                try:
                    test_client = TestClient(app)
                    with patch(
                        "app.routers.chat.gemini_provider.chat_with_tools",
                        new_callable=AsyncMock,
                    ) as mock_llm:
                        mock_llm.return_value = {"response": "ok", "tool_calls": []}
                        resp = test_client.post(
                            "/chat",
                            json={"message": probe_query, "session_id": "fixture-iso-1"},
                        )
                    assert resp.status_code == 200
                    payload = resp.json()
                    assert all(
                        not s.startswith("urn:gomate:ci-fixture:")
                        for s in payload["sources"]
                    )
                    sent_prompt = mock_llm.call_args.kwargs["message"]
                    assert "[INTERNAL CI FIXTURE" not in sent_prompt
                    assert "[Source: ci_fixture" not in sent_prompt
                    assert "urn:gomate:ci-fixture:" not in sent_prompt
                finally:
                    app.dependency_overrides.pop(require_internal_principal, None)

                # 4. Defense-in-depth test: even if a rogue row has source_name='wikivoyage',
                #    each secondary firewall rule independently blocks it from retrieval.
                rogue_marker = f"Rogue fixture firewall probe {uuid.uuid4().hex[:8]}"
                vec_str = (
                    "["
                    + ",".join(str(x) for x in retriever.embedder.embed_text(rogue_marker))
                    + "]"
                )
                rogue_ids: list[str] = []
                rogue_variants = [
                    (
                        "https://en.wikivoyage.org/wiki/Test1",
                        "CC BY-SA 3.0",
                        '{"is_ci_fixture": true}',
                    ),
                    (
                        "https://en.wikivoyage.org/wiki/Test2",
                        "CC BY-SA 3.0",
                        '{"user_citable": false}',
                    ),
                    (
                        "https://en.wikivoyage.org/wiki/Test3",
                        "INTERNAL-CI-FIXTURE-ONLY",
                        "{}",
                    ),
                    (
                        "urn:gomate:ci-fixture:rogue-4",
                        "CC BY-SA 3.0",
                        "{}",
                    ),
                ]
                async with pool.acquire() as conn:
                    try:
                        for idx, (s_url, lic, meta_json) in enumerate(rogue_variants):
                            rid = str(uuid.uuid4())
                            rogue_ids.append(rid)
                            chash = hashlib.sha256(
                                f"{rogue_marker}-{idx}".encode("utf-8")
                            ).hexdigest()
                            await conn.execute(
                                """
                                INSERT INTO documents (
                                    id, document_id, source_name, source_url, license,
                                    attribution, language, title, content, content_hash,
                                    embedding_model, metadata, embedding
                                ) VALUES (
                                    $1::uuid, $2, 'wikivoyage', $3, $4,
                                    'Wikivoyage contributors', 'en', $5, $6, $7,
                                    $8, $9::jsonb, $10::vector
                                )
                                """,
                                rid,
                                f"rogue-firewall-{idx}",
                                s_url,
                                lic,
                                rogue_marker,
                                f"{rogue_marker} variant {idx}",
                                chash,
                                retriever.embedder.model_name,
                                meta_json,
                                vec_str,
                            )

                        leaked = await retriever.search(
                            rogue_marker,
                            top_k=20,
                            min_similarity=0.0,
                            include_unverified=False,
                        )
                        assert rogue_marker not in [h["title"] for h in leaked]
                    finally:
                        await conn.execute(
                            "DELETE FROM documents WHERE id = ANY($1::uuid[])",
                            rogue_ids,
                        )
            finally:
                await retriever.close()

        _run_db_test(_body)


# ============================================================================
# C02-F01 — Non-Destructive & Fail-Closed Document Rollback Safety
# ============================================================================


class TestC02F01PreEnrichedDocumentRollbackSafety:
    """Static and live PostgreSQL tests proving pre-existing RAG columns & vectors never get dropped."""

    def test_c02_f01_down_sql_and_recovery_runbook_static_invariants(self):
        migration_sql = (NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8")
        down_sql = (NEW_MIGRATION_DIR / "down.sql").read_text(encoding="utf-8")
        runbook_path = NEW_MIGRATION_DIR / "ROLLBACK_AND_RECOVERY.md"
        assert runbook_path.is_file(), "ROLLBACK_AND_RECOVERY.md must exist alongside down.sql"
        runbook_md = runbook_path.read_text(encoding="utf-8")

        # 1. Ledger snapshot happens BEFORE CREATE TABLE dataset_registry and ALTER TABLE documents
        ledger_pos = migration_sql.index('CREATE TABLE IF NOT EXISTS "_migration_20261110_schema_ledger"')
        ds_pos = migration_sql.index('CREATE TABLE IF NOT EXISTS "dataset_registry"')
        alter_docs_pos = migration_sql.index('ALTER TABLE "documents"')
        assert ledger_pos < ds_pos < alter_docs_pos

        # 2. down.sql must NOT contain static unguarded DROP COLUMN statements for pre-existing RAG columns
        non_comment_down = "\n".join(
            line for line in down_sql.splitlines() if not line.lstrip().startswith("--")
        )
        for protected_col in (
            'DROP COLUMN IF EXISTS "source_name"',
            'DROP COLUMN IF EXISTS "source_url"',
            'DROP COLUMN IF EXISTS "content_hash"',
            'DROP COLUMN IF EXISTS "embedding"',
            'DROP COLUMN IF EXISTS "license"',
        ):
            assert protected_col not in non_comment_down

        # 3. Fail-closed exceptions and ledger checks are enforced in down.sql & documented in runbook
        assert "_migration_20261110_schema_ledger" in non_comment_down
        assert "added_documents_columns" in non_comment_down
        assert "[C02-F01 FAIL-CLOSED]" in non_comment_down
        assert "ROLLBACK_AND_RECOVERY.md" in non_comment_down
        assert "pg_dump" in runbook_md
        assert "Roll-Forward" in runbook_md or "roll-forward" in runbook_md.lower()

    def test_live_migration_and_rollback_preserves_preexisting_rag_enrichment_columns_and_data(
        self,
    ):
        scratch_db = "wanderai_ci_mig_preenriched"

        async def _body(admin_conn: asyncpg.Connection, base_dsn: str):
            await _recreate_scratch_db(admin_conn, scratch_db)
            target_dsn = f"{base_dsn}/{scratch_db}"
            try:
                conn = await asyncpg.connect(target_dsn)
                try:
                    # 1. Replay init.sql + 5 historical migrations
                    await conn.execute(INIT_SQL_PATH.read_text(encoding="utf-8"))
                    for mig_name in PRE_DRIFT_MIGRATIONS:
                        await conn.execute(
                            (MIGRATIONS_DIR / mig_name / "migration.sql").read_text(
                                encoding="utf-8"
                            )
                        )

                    # 2. Simulate out-of-Prisma RAG ingestion BEFORE 20261110000000_sync_schema_drift:
                    #    pre-existing columns source_name, source_url, content_hash, embedding, license
                    #    plus a pre-existing source_name index and populated vector data.
                    await conn.execute(
                        """
                        ALTER TABLE "documents"
                          ADD COLUMN "source_name" VARCHAR(50),
                          ADD COLUMN "source_url" VARCHAR(500),
                          ADD COLUMN "content_hash" VARCHAR(64),
                          ADD COLUMN "embedding" vector(384),
                          ADD COLUMN "license" VARCHAR(100);
                        CREATE INDEX "documents_source_name_idx" ON "documents"("source_name");
                        """
                    )

                    embedder = MockEmbedder(dimension=384)
                    wv_id = uuid.UUID("00000000-0000-0000-0000-000000000101")
                    wv_text = "Da Nang coastal culinary overview from pre-existing Wikivoyage ingestion"
                    wv_hash = hashlib.sha256(wv_text.encode("utf-8")).hexdigest()
                    wv_vec = embedder.embed_text(wv_text)
                    wv_vec_sql = "[" + ",".join(str(x) for x in wv_vec) + "]"

                    wp_id = uuid.UUID("00000000-0000-0000-0000-000000000102")
                    wp_text = "Cau Rong architecture history from pre-existing Wikipedia ingestion"
                    wp_hash = hashlib.sha256(wp_text.encode("utf-8")).hexdigest()
                    wp_vec = embedder.embed_text(wp_text)
                    wp_vec_sql = "[" + ",".join(str(x) for x in wp_vec) + "]"

                    legacy_id = uuid.UUID("00000000-0000-0000-0000-000000000103")

                    await conn.execute(
                        """
                        INSERT INTO "documents" (
                            id, content, source, category, metadata,
                            source_name, source_url, content_hash, embedding, license
                        ) VALUES
                        (
                            $1, $2, 'external_rag_v1', 'eat',
                            '{"section": "Eat", "ingested_by": "external_rag_pipeline"}'::jsonb,
                            'wikivoyage', 'https://en.wikivoyage.org/wiki/Da_Nang',
                            $3, $4::vector, 'CC BY-SA 3.0'
                        ),
                        (
                            $5, $6, 'external_rag_v1', 'sightseeing',
                            '{"lang": "vi", "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"}'::jsonb,
                            'wikipedia', 'https://vi.wikipedia.org/wiki/C%E1%BA%A7u_R%E1%BB%93ng',
                            $7, $8::vector, 'CC-BY-SA-4.0'
                        ),
                        (
                            $9, 'Unenriched pre-existing note', 'legacy_memo', 'notes',
                            '{"note": "raw"}'::jsonb,
                            NULL, NULL, NULL, NULL, NULL
                        )
                        """,
                        wv_id,
                        wv_text,
                        wv_hash,
                        wv_vec_sql,
                        wp_id,
                        wp_text,
                        wp_hash,
                        wp_vec_sql,
                        legacy_id,
                    )

                    async def _snapshot_enriched():
                        rows = await conn.fetch(
                            """
                            SELECT id::text, content, source_name, source_url, content_hash,
                                   license, metadata, embedding::text AS embedding_text
                            FROM "documents"
                            WHERE id IN ($1, $2)
                            ORDER BY id
                            """,
                            wv_id,
                            wp_id,
                        )
                        out = []
                        for r in rows:
                            meta = (
                                json.loads(r["metadata"])
                                if isinstance(r["metadata"], str)
                                else r["metadata"]
                            )
                            vec_floats = [
                                round(float(v), 6) for v in json.loads(r["embedding_text"])
                            ]
                            out.append(
                                {
                                    "id": r["id"],
                                    "content": r["content"],
                                    "source_name": r["source_name"],
                                    "source_url": r["source_url"],
                                    "content_hash": r["content_hash"],
                                    "license": r["license"],
                                    "metadata": meta,
                                    "embedding_dim": len(vec_floats),
                                    "embedding_head": vec_floats[:5],
                                    "embedding_full": vec_floats,
                                }
                            )
                        return out

                    cols_before = {
                        r["column_name"]
                        for r in await conn.fetch(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'documents'"
                        )
                    }
                    assert {
                        "source_name",
                        "source_url",
                        "content_hash",
                        "embedding",
                        "license",
                    } <= cols_before
                    assert "embedding_model" not in cols_before
                    assert "title" not in cols_before

                    before_enriched = await _snapshot_enriched()
                    assert len(before_enriched) == 2

                    # 3. Apply migration.sql (UP)
                    up_sql = (NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8")
                    await conn.execute(up_sql)

                    ledger = await conn.fetchrow(
                        'SELECT * FROM "_migration_20261110_schema_ledger" '
                        "WHERE migration_name = '20261110000000_sync_schema_drift'"
                    )
                    assert ledger is not None
                    assert sorted(ledger["preexisting_documents_columns"]) == [
                        "content_hash",
                        "embedding",
                        "license",
                        "source_name",
                        "source_url",
                    ]
                    assert "documents_source_name_idx" in ledger["preexisting_documents_indexes"]

                    # Pre-enriched rows MUST keep exact provenance, vectors, and metadata (NOT marked unverified!)
                    after_up_enriched = await _snapshot_enriched()
                    assert after_up_enriched == before_enriched

                    wv_model = await conn.fetchval(
                        'SELECT embedding_model FROM "documents" WHERE id = $1', wv_id
                    )
                    wp_model = await conn.fetchval(
                        'SELECT embedding_model FROM "documents" WHERE id = $1', wp_id
                    )
                    assert wv_model == "preexisting_external_embedding"
                    assert (
                        wp_model
                        == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    )

                    # Unenriched NULL row gets non-fabricated legacy sentinel
                    legacy_after_up = await conn.fetchrow(
                        'SELECT source_name, license, content_hash, metadata FROM "documents" WHERE id = $1',
                        legacy_id,
                    )
                    assert legacy_after_up["source_name"] == "unverified_legacy"
                    assert legacy_after_up["license"] == "UNVERIFIED_LEGACY"
                    assert len(legacy_after_up["content_hash"]) == 64

                    # 4. Apply down.sql (ROLLBACK): pre-existing RAG columns, index, and vectors MUST survive!
                    down_sql = (NEW_MIGRATION_DIR / "down.sql").read_text(encoding="utf-8")
                    await conn.execute(down_sql)

                    cols_after_down = {
                        r["column_name"]
                        for r in await conn.fetch(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'documents'"
                        )
                    }
                    assert cols_after_down == cols_before
                    assert {
                        "source_name",
                        "source_url",
                        "content_hash",
                        "embedding",
                        "license",
                    } <= cols_after_down

                    src_idx_after_down = await conn.fetchval(
                        "SELECT count(*) FROM pg_indexes "
                        "WHERE schemaname = 'public' AND indexname = 'documents_source_name_idx'"
                    )
                    assert src_idx_after_down == 1

                    after_down_enriched = await _snapshot_enriched()
                    assert after_down_enriched == before_enriched
                    assert await conn.fetchval('SELECT count(*) FROM "documents"') == 3

                    # 5. Re-apply migration.sql (UP -> DOWN -> UP round-trip on pre-enriched DB)
                    await conn.execute(up_sql)
                    after_reup_enriched = await _snapshot_enriched()
                    assert after_reup_enriched == before_enriched

                    print(
                        "[C02-F01-EVIDENCE-PREENRICHED] "
                        + json.dumps(
                            {
                                "preexisting_rag_columns": sorted(
                                    ledger["preexisting_documents_columns"]
                                ),
                                "added_columns_dropped_on_down": sorted(
                                    ledger["added_documents_columns"]
                                ),
                                "cols_equal_before_and_after_down": cols_after_down
                                == cols_before,
                                "preexisting_index_preserved": int(src_idx_after_down) == 1,
                                "enriched_rows_identical_after_up": after_up_enriched
                                == before_enriched,
                                "enriched_rows_identical_after_down": after_down_enriched
                                == before_enriched,
                                "enriched_rows_identical_after_reup": after_reup_enriched
                                == before_enriched,
                                "total_rows_preserved": 3,
                            }
                        )
                    )
                finally:
                    await conn.close()
            finally:
                await _drop_scratch_db(admin_conn, scratch_db)

        _run_db_test(_body)

    def test_live_down_sql_fails_closed_when_newly_added_columns_hold_data_or_ledger_missing(
        self,
    ):
        scratch_db = "wanderai_ci_mig_failclosed"

        async def _body(admin_conn: asyncpg.Connection, base_dsn: str):
            await _recreate_scratch_db(admin_conn, scratch_db)
            target_dsn = f"{base_dsn}/{scratch_db}"
            try:
                conn = await asyncpg.connect(target_dsn)
                try:
                    await conn.execute(INIT_SQL_PATH.read_text(encoding="utf-8"))
                    for mig_name in PRE_DRIFT_MIGRATIONS:
                        await conn.execute(
                            (MIGRATIONS_DIR / mig_name / "migration.sql").read_text(
                                encoding="utf-8"
                            )
                        )

                    up_sql = (NEW_MIGRATION_DIR / "migration.sql").read_text(encoding="utf-8")
                    down_sql = (NEW_MIGRATION_DIR / "down.sql").read_text(encoding="utf-8")
                    await conn.execute(up_sql)

                    # Case 1: Post-migration RAG document populated into newly-added columns -> FAIL CLOSED
                    doc_id = uuid.uuid4()
                    embedder = MockEmbedder(dimension=384)
                    vec_sql = (
                        "["
                        + ",".join(str(x) for x in embedder.embed_text("Post migration doc"))
                        + "]"
                    )
                    chash = hashlib.sha256(b"Post migration doc").hexdigest()
                    await conn.execute(
                        """
                        INSERT INTO "documents" (
                            id, document_id, source_name, source_url, license, attribution,
                            language, title, content, content_hash, embedding_model, embedding
                        ) VALUES (
                            $1, 'post-mig-1', 'wikipedia', 'https://en.wikipedia.org/wiki/Hue',
                            'CC-BY-SA-4.0', 'Wikipedia contributors', 'en', 'Hue Imperial City',
                            'Post migration doc', $2, 'mock-384', $3::vector
                        )
                        """,
                        doc_id,
                        chash,
                        vec_sql,
                    )

                    with pytest.raises(
                        asyncpg.PostgresError,
                        match=r"\[C02-F01 FAIL-CLOSED\].*documents\.",
                    ):
                        await conn.execute(down_sql)

                    # Verify zero data or column loss after blocked rollback
                    preserved_doc = await conn.fetchrow(
                        'SELECT title, source_name, embedding IS NOT NULL AS has_emb '
                        'FROM "documents" WHERE id = $1',
                        doc_id,
                    )
                    assert preserved_doc is not None
                    assert preserved_doc["title"] == "Hue Imperial City"
                    assert preserved_doc["source_name"] == "wikipedia"
                    assert preserved_doc["has_emb"] is True

                    # Case 2: Newly-created dataset_registry populated -> FAIL CLOSED
                    await conn.execute('DELETE FROM "documents" WHERE id = $1', doc_id)
                    await conn.execute(
                        """
                        INSERT INTO "dataset_registry" (
                            dataset_name, dataset_source, license, restriction
                        ) VALUES (
                            'w07_curated_primary', 'wikimedia+overture', 'CC-BY-SA-4.0', 'OPEN_REUSABLE'
                        )
                        """
                    )
                    with pytest.raises(
                        asyncpg.PostgresError,
                        match=r"\[C02-F01 FAIL-CLOSED\].*dataset_registry",
                    ):
                        await conn.execute(down_sql)
                    assert (
                        await conn.fetchval('SELECT count(*) FROM "dataset_registry"') == 1
                    )

                    # Case 3: Missing ownership ledger -> FAIL CLOSED (refuses blind DROP COLUMN)
                    await conn.execute('DELETE FROM "dataset_registry"')
                    await conn.execute('DROP TABLE "_migration_20261110_schema_ledger"')
                    with pytest.raises(
                        asyncpg.PostgresError,
                        match=r"\[C02-F01 FAIL-CLOSED\].*_migration_20261110_schema_ledger",
                    ):
                        await conn.execute(down_sql)

                    cols_still_present = {
                        r["column_name"]
                        for r in await conn.fetch(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'documents'"
                        )
                    }
                    assert {
                        "source_name",
                        "source_url",
                        "content_hash",
                        "embedding",
                        "license",
                    } <= cols_still_present

                    print(
                        "[C02-F01-EVIDENCE-FAILCLOSED] "
                        + json.dumps(
                            {
                                "populated_added_column_blocked": True,
                                "populated_dataset_registry_blocked": True,
                                "missing_ledger_blocked": True,
                                "columns_preserved_after_all_aborts": True,
                            }
                        )
                    )
                finally:
                    await conn.close()
            finally:
                await _drop_scratch_db(admin_conn, scratch_db)

        _run_db_test(_body)


# ============================================================================
# C02-F02 — RAGRetriever Governed Source-Family Compatibility & Isolation
# ============================================================================


class TestC02F02RetrieverGovernedSourceCompatibility:
    """Offline and live PostgreSQL tests for governed multi-source retrieval & fail-closed isolation."""

    def test_c02_f02_retriever_sql_has_no_rigid_two_source_allowlist_offline(self):
        # Verify the rigid ('osm', 'wikivoyage')-only filter is gone and governed predicates exist
        assert "source_name IN ('osm', 'wikivoyage')" not in GOVERNED_PRODUCTION_DOCUMENT_SQL
        for governed_family in (
            "wikipedia",
            "wikipedia_article",
            "wikidata",
            "wikidata_entity",
            "overture",
            "overture_places_parquet",
            "official_tourism",
            "open_government",
        ):
            assert governed_family in GOVERNED_PRODUCTION_DOCUMENT_SQL

        for blocked_token in (
            "ci_fixture",
            "synthetic",
            "mock",
            "unverified_legacy",
            "tripadvisor",
            "google_maps",
            "user_citable",
            "is_ci_fixture",
            "legacy_migration_backfill",
            "OPEN_REUSABLE",
            "reuse_evidence",
        ):
            assert blocked_token in GOVERNED_PRODUCTION_DOCUMENT_SQL

        # Capture exact SQL emitted by RAGRetriever.search(..., include_unverified=False) offline
        captured_queries: list[str] = []

        class _FakeAcquire:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def fetch(self, sql: str, *_params):
                captured_queries.append(sql)
                return []

        class _FakePool:
            def acquire(self):
                return _FakeAcquire()

            async def close(self):
                return None

        async def _run():
            retriever = RAGRetriever(embedder=MockEmbedder(dimension=384))
            retriever._pool = _FakePool()  # type: ignore[assignment]
            await retriever.search("Dragon Bridge history", top_k=5, include_unverified=False)

        asyncio.run(_run())
        assert len(captured_queries) == 1
        assert "source_name IN ('osm', 'wikivoyage')" not in captured_queries[0]
        assert "wikipedia_article" in captured_queries[0]
        assert "overture_places_parquet" in captured_queries[0]

    def test_live_retriever_admits_governed_non_osm_wikivoyage_sources_with_valid_provenance(
        self,
    ):
        async def _body(_admin_conn: asyncpg.Connection, _base_dsn: str):
            retriever = RAGRetriever()
            try:
                pool = await retriever.get_pool()
                pos_marker = (
                    f"Governed open travel corpus verification {uuid.uuid4().hex[:10]}"
                )
                vec_str = (
                    "["
                    + ",".join(str(x) for x in retriever.embedder.embed_text(pos_marker))
                    + "]"
                )

                inserted_doc_ids: list[str] = []
                async with pool.acquire() as conn:
                    verified_place_id = await conn.fetchval(
                        """
                        SELECT p.id::text
                        FROM places p
                        WHERE EXISTS (
                            SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id
                        )
                        LIMIT 1
                        """
                    )
                    assert verified_place_id is not None

                    governed_candidates = [
                        {
                            "doc_id": f"gov-pos-wikipedia-{uuid.uuid4().hex[:6]}",
                            "source_name": "wikipedia_article",
                            "source_url": "https://vi.wikipedia.org/wiki/C%E1%BA%A7u_R%E1%BB%93ng",
                            "license": "CC-BY-SA-4.0",
                            "attribution": "Wikipedia contributors",
                            "place_id": None,
                            "metadata": {
                                "reuse_storage_class": "OPEN_REUSABLE",
                                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                            },
                        },
                        {
                            "doc_id": f"gov-pos-wikidata-{uuid.uuid4().hex[:6]}",
                            "source_name": "wikidata_entity",
                            "source_url": "https://www.wikidata.org/wiki/Q10744292",
                            "license": "CC0-1.0",
                            "attribution": "Wikidata contributors",
                            "place_id": None,
                            "metadata": {
                                "reuse_storage_class": "OPEN_REUSABLE",
                                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                            },
                        },
                        {
                            "doc_id": f"gov-pos-overture-{uuid.uuid4().hex[:6]}",
                            "source_name": "overture_places_parquet",
                            "source_url": "https://docs.overturemaps.org/guides/places",
                            "license": "CDLA-Permissive-2.0",
                            "attribution": "Overture Maps Foundation",
                            "place_id": verified_place_id,
                            "metadata": {
                                "reuse_storage_class": "OPEN_REUSABLE",
                                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                            },
                        },
                        {
                            "doc_id": f"gov-pos-official-{uuid.uuid4().hex[:6]}",
                            "source_name": "official_tourism",
                            "source_url": "https://danangfantasticity.com/en/attractions/dragon-bridge",
                            "license": "CC BY 4.0",
                            "attribution": "Da Nang Department of Tourism",
                            "place_id": None,
                            "metadata": {
                                "reuse_storage_class": "OPEN_REUSABLE",
                                "reuse_evidence": "Explicit open CC BY 4.0 portal reuse notice verified",
                            },
                        },
                    ]

                    try:
                        for item in governed_candidates:
                            row_uuid = str(uuid.uuid4())
                            inserted_doc_ids.append(row_uuid)
                            content = f"{pos_marker} — verified record from {item['source_name']}"
                            chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                            await conn.execute(
                                """
                                INSERT INTO documents (
                                    id, document_id, source_name, source_url, license,
                                    attribution, place_id, language, title, content,
                                    content_hash, embedding_model, metadata, embedding
                                ) VALUES (
                                    $1::uuid, $2, $3, $4, $5,
                                    $6, $7::uuid, 'vi', $8, $9,
                                    $10, $11, $12::jsonb, $13::vector
                                )
                                """,
                                row_uuid,
                                item["doc_id"],
                                item["source_name"],
                                item["source_url"],
                                item["license"],
                                item["attribution"],
                                item["place_id"],
                                pos_marker,
                                content,
                                chash,
                                retriever.embedder.model_name,
                                json.dumps(item["metadata"]),
                                vec_str,
                            )

                        hits = await retriever.search(
                            pos_marker,
                            top_k=10,
                            min_similarity=0.3,
                            include_unverified=False,
                        )
                        matched = [h for h in hits if h["title"] == pos_marker]
                        matched_sources = {h["source_name"] for h in matched}
                        assert matched_sources == {
                            "wikipedia_article",
                            "wikidata_entity",
                            "overture_places_parquet",
                            "official_tourism",
                        }

                        # Verify RAGService.retrieve_with_status surfaces governed URLs cleanly
                        rag_svc = RAGService(retriever=retriever)
                        rag_res = await rag_svc.retrieve_with_status(pos_marker, top_k=10)
                        assert rag_res.status == "ok"
                        for item in governed_candidates:
                            assert item["source_url"] in rag_res.sources

                        print(
                            "[C02-F02-EVIDENCE-POSITIVE] "
                            + json.dumps(
                                {
                                    "retrieved_governed_sources": sorted(matched_sources),
                                    "rag_service_status": rag_res.status,
                                    "all_governed_urls_present": True,
                                }
                            )
                        )
                    finally:
                        await conn.execute(
                            "DELETE FROM documents WHERE id = ANY($1::uuid[])",
                            inserted_doc_ids,
                        )
            finally:
                await retriever.close()

        _run_db_test(_body)

    def test_live_retriever_rejects_unapproved_or_incomplete_provenance_and_ci_fixtures(
        self,
    ):
        async def _body(_admin_conn: asyncpg.Connection, _base_dsn: str):
            retriever = RAGRetriever()
            try:
                pool = await retriever.get_pool()
                neg_marker = (
                    f"Adversarial source governance probe {uuid.uuid4().hex[:10]}"
                )
                vec_str = (
                    "["
                    + ",".join(str(x) for x in retriever.embedder.embed_text(neg_marker))
                    + "]"
                )

                negative_cases = [
                    # 1-4: Denylisted fixture / synthetic / mock / legacy sources even with valid-looking URL/license
                    (
                        "ci_fixture_disguised_https",
                        "ci_fixture",
                        "https://example.org/fixture",
                        "CC BY 4.0",
                        "CI Bot",
                        {"reuse_storage_class": "OPEN_REUSABLE", "reuse_evidence": "test"},
                    ),
                    (
                        "synthetic_source",
                        "synthetic",
                        "https://example.org/synthetic",
                        "CC0-1.0",
                        "Synthetic Generator",
                        {"reuse_storage_class": "OPEN_REUSABLE", "reuse_evidence": "test"},
                    ),
                    (
                        "mock_source",
                        "mock",
                        "https://example.org/mock",
                        "CC0-1.0",
                        "Mock Generator",
                        {"reuse_storage_class": "OPEN_REUSABLE", "reuse_evidence": "test"},
                    ),
                    (
                        "unverified_legacy_source",
                        "unverified_legacy",
                        "https://en.wikipedia.org/wiki/Hue",
                        "UNVERIFIED_LEGACY",
                        "Legacy",
                        {},
                    ),
                    # 5: Arbitrary external source NOT auto-trusted without governance approval
                    (
                        "unapproved_random_blog",
                        "random_travel_blog",
                        "https://travelblog.example.com/da-nang",
                        "CC BY 4.0",
                        "Random Blogger",
                        {},
                    ),
                    # 6: Commercial/social platform blocked even if stamped OPEN_REUSABLE
                    (
                        "commercial_tripadvisor",
                        "tripadvisor",
                        "https://www.tripadvisor.com/Attraction_Review",
                        "CC BY 4.0",
                        "TripAdvisor",
                        {
                            "reuse_storage_class": "OPEN_REUSABLE",
                            "reuse_evidence": "forged",
                            "governance_decision": "ACCEPT_PRIMARY_CORPUS",
                        },
                    ),
                    # 7: Wikipedia prose wrongly collapsed into CC0-1.0
                    (
                        "wikipedia_wrong_cc0_license",
                        "wikipedia",
                        "https://en.wikipedia.org/wiki/Dragon_Bridge_(Da_Nang)",
                        "CC0-1.0",
                        "Wikipedia contributors",
                        {},
                    ),
                    # 8: Wikipedia source_name pointing to non-Wikipedia domain
                    (
                        "wikipedia_spoofed_domain",
                        "wikipedia",
                        "https://spoofed.example.com/wiki/Dragon_Bridge",
                        "CC-BY-SA-4.0",
                        "Wikipedia contributors",
                        {},
                    ),
                    # 9: Overture blanket Multi-License (forbidden; must be theme/record-specific)
                    (
                        "overture_blanket_multilicense",
                        "overture_places_parquet",
                        "https://docs.overturemaps.org/guides/places",
                        "Multi-License",
                        "Overture Maps Foundation",
                        {},
                    ),
                    # 10: Official source WITHOUT explicit OPEN_REUSABLE + reuse_evidence (never auto-trusted!)
                    (
                        "official_missing_reuse_proof",
                        "official_tourism",
                        "https://danangfantasticity.com/en/no-license-proof",
                        "CC BY 4.0",
                        "Official Portal",
                        {},
                    ),
                    # 11: Official source with REFERENCE_ONLY storage class
                    (
                        "official_reference_only",
                        "official_tourism",
                        "https://danangfantasticity.com/en/reference-only",
                        "CC BY 4.0",
                        "Official Portal",
                        {
                            "reuse_storage_class": "REFERENCE_ONLY",
                            "reuse_evidence": "Copyright reserved; metadata only",
                        },
                    ),
                    # 12: Valid Wikipedia provenance explicitly marked user_citable=false
                    (
                        "wikipedia_not_user_citable",
                        "wikipedia_article",
                        "https://vi.wikipedia.org/wiki/Ng%C5%A9_H%C3%A0nh_S%C6%A1n",
                        "CC-BY-SA-4.0",
                        "Wikipedia contributors",
                        {"user_citable": False},
                    ),
                    # 13: Valid Wikidata source missing required attribution
                    (
                        "wikidata_missing_attribution",
                        "wikidata_entity",
                        "https://www.wikidata.org/wiki/Q10744292",
                        "CC0-1.0",
                        "",
                        {},
                    ),
                ]

                inserted_ids: list[str] = []
                async with pool.acquire() as conn:
                    try:
                        for label, src, s_url, lic, attr, meta in negative_cases:
                            row_uuid = str(uuid.uuid4())
                            inserted_ids.append(row_uuid)
                            content = f"{neg_marker} — {label}"
                            chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                            await conn.execute(
                                """
                                INSERT INTO documents (
                                    id, document_id, source_name, source_url, license,
                                    attribution, language, title, content, content_hash,
                                    embedding_model, metadata, embedding
                                ) VALUES (
                                    $1::uuid, $2, $3, $4, $5,
                                    $6, 'en', $7, $8, $9,
                                    $10, $11::jsonb, $12::vector
                                )
                                """,
                                row_uuid,
                                f"gov-neg-{label}",
                                src,
                                s_url,
                                lic,
                                attr,
                                neg_marker,
                                content,
                                chash,
                                retriever.embedder.model_name,
                                json.dumps(meta),
                                vec_str,
                            )

                        # Confirm dev/unverified mode sees all 13 rows via pgvector similarity
                        dev_hits = await retriever.search(
                            neg_marker,
                            top_k=30,
                            min_similarity=0.0,
                            include_unverified=True,
                        )
                        dev_matched = [h for h in dev_hits if h["title"] == neg_marker]
                        assert len(dev_matched) == len(negative_cases)

                        # Production mode MUST reject every single one of the 13 invalid/unapproved rows
                        prod_hits = await retriever.search(
                            neg_marker,
                            top_k=30,
                            min_similarity=0.0,
                            include_unverified=False,
                        )
                        prod_matched = [h for h in prod_hits if h["title"] == neg_marker]
                        assert prod_matched == []

                        rag_svc = RAGService(retriever=retriever)
                        rag_res = await rag_svc.retrieve_with_status(neg_marker, top_k=10)
                        negative_urls = {c[2] for c in negative_cases}
                        assert negative_urls.isdisjoint(set(rag_res.sources))

                        print(
                            "[C02-F02-EVIDENCE-NEGATIVE] "
                            + json.dumps(
                                {
                                    "adversarial_candidates_tested": len(negative_cases),
                                    "dev_opt_in_matched": len(dev_matched),
                                    "production_leaked": len(prod_matched),
                                    "blocked_labels": [c[0] for c in negative_cases],
                                }
                            )
                        )
                    finally:
                        await conn.execute(
                            "DELETE FROM documents WHERE id = ANY($1::uuid[])",
                            inserted_ids,
                        )
            finally:
                await retriever.close()

        _run_db_test(_body)
