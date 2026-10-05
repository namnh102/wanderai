# ADR-001: PostgreSQL as Primary Database

## Status
Accepted

## Context
GoMate/WanderAI requires relational data, geographic queries, and vector similarity search.

## Options
1. PostgreSQL + PostGIS + pgvector (single DB)
2. PostgreSQL + MongoDB + Pinecone (3 separate systems)
3. Supabase managed PostgreSQL

## Decision
Use PostgreSQL with PostGIS and pgvector extensions in a single database.

## Consequences
- One database to manage, backup, and deploy
- PostGIS handles geographic queries (nearby search, distance)
- pgvector handles RAG embedding search
- Prisma ORM for type-safe queries, raw SQL for spatial/vector queries
- Less operational complexity than multi-database setup
