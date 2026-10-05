# Local Development Environment

## Requirements
- Docker Desktop (Windows/Mac)
- Node.js 18+
- Python 3.11+
- Flutter SDK 3.1+

## Infrastructure Services

| Service | Container | Port | Image | Status |
|---------|-----------|------|-------|--------|
| PostgreSQL | wanderai-postgres | 5432 | Custom (postgres:16 + PostGIS + pgvector) | Verified 2026-10-01 |
| Redis | wanderai-redis | 6379 | redis:7-alpine | Verified 2026-10-01 |

## Verified Extensions

| Extension | Version | Purpose |
|-----------|---------|---------|
| PostGIS | 3.4 | Geographic queries (nearby, distance) |
| pgvector | 0.8.6 | Vector similarity search (RAG) |

## Start Infrastructure
```bash
docker compose up -d
```

## Verify
```bash
docker exec wanderai-postgres psql -U postgres -d wanderai -c "SELECT PostGIS_Version();"
docker exec wanderai-postgres psql -U postgres -d wanderai -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
docker exec wanderai-redis redis-cli ping
```

## Connection Strings
```
PostgreSQL: postgresql://postgres:postgres@localhost:5432/wanderai
Redis: redis://localhost:6379
```
