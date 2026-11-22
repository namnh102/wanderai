# GoMate Data Reconciliation (`424` vs `Freeze V2 759`), 60-Pilot POI Enrichment, & W08 / Wave C Prep (`2026-11-22`)

- **Branch:** `feat/product-data-enrichment-wave-c` (stacked cleanly off PR #99 `19cffea788cf5a23b1f5da42210c6175b04e3eee`; PR #98 and PR #99 left unmerged)
- **Frozen Research Integrity:** `data/curated/gomate_places_freeze_v2.json` and `data/curated/w07/` unchanged (`python -m scripts.freeze_checksum --skip-missing-prefix=data/restricted/` = `PASS`)
- **Direct Financial Spend:** **`\$0`** (zero paid LLM/places/scraping APIs used)

---

## 1. Exact Root Cause & Live PostgreSQL Reconciliation (`424` vs `759` Freeze V2 POIs)

### Root Cause of `424` Places
Running the legacy product setup pipeline (`prisma/seed.ts` -> `prisma/import-curated.ts` -> `prisma/import-osm-enrichment.ts`) skips `data/curated/gomate_places_freeze_v2.json` and yields **exact `424` places** across 50 destinations (`357` verified Freeze V2 POIs + `56` legacy seed records + `11` unsourced canonical records). Notably, `import-osm-enrichment.ts` also lacked `'ha_long'` in `CITY_SLUG_MAP`, omitting all 188 Hạ Long Core POIs.

### Non-Destructive Reconciliation Results (Verified Live on PostgreSQL + PostGIS/pgvector `127.0.0.1:5433/wanderai`)
*(Note: Local Windows Docker Desktop `com.docker.service` was stopped post-reboot and requires interactive desktop/Admin start to inspect any prior Docker `pgdata` volume directly; live verification above ran against isolated local PostgreSQL 16 + PostGIS + pgvector executing the exact `424` baseline followed by `apps/backend/prisma/reconcile-freeze-v2.ts`.)*

| Metric | Before (`424` Baseline) | After (`reconcile-freeze-v2.ts`) | Notes |
|---|---:|---:|---|
| Active Places (`deleted_at IS NULL`) | `424` | `826` | Non-destructive (`0` `TRUNCATE`, existing IDs preserved) |
| Verified Freeze V2 POIs (`place_sources > 0`) | `357` / `759` | **`759` / `759` (`100%`)** | Core `622` + Secondary `137` complete |
| Missing Freeze V2 POIs | `402` | **`0`** | Gap was `ha-long: 188`, `da-nang: 179`, `ha-noi: 35` |
| Unverified Legacy / Non-Freeze Places | `67` | `67` | Preserved internally, `404` on public detail |
| `PlaceSource` Provenance Rows | `357` | `1,006` (`osm` + `overture`) | Respects denylist & revalidation manifests |
| Places with `coverImage` | `0` | **`48`** | Verified Wikimedia Commons photos (`CC0`/`CC BY-SA`) |
| Places with `description` | `56` (legacy only) | `94` (`38` verified + `56` legacy) | Wikipedia / Wikidata / OSM factual extracts |
| Places with `openingHours` | `0` | **`101`** | Verified OSM tags |
| `trusted = true` Reviews / `trusted = false` Quarantined | `0` / `8` | `0` / `8` | Zero fabricated reviews or ratings (`rating = NULL`) |

---

## 2. Pilot `60` Core V2 POI Enrichment (`data/curated/poi_enrichment_pilot_60_v1.json`)

Generated deterministically via `scripts/curate_60_pilot_pois_from_wikimedia.py` strictly from Freeze V2 OSM tags (`wikidata`, `wikipedia`, `wikimedia_commons`, `opening_hours`, `website`, `phone`) + public Wikimedia REST & MediaWiki APIs (license-checked via Commons `imageinfo extmetadata`):
- **Scope:** `60` Core V2 POIs (`ha-noi: 20`, `da-nang: 20`, `ha-long: 20`)
- **Verified Media:** `48/60` POIs with `cover_image`, `114` total CC0 / CC-BY-SA / Public Domain image URLs with attribution (`artist`, `license`, `commonsPageUrl`)
- **Grounded Descriptions:** `38/60` POIs with Wikipedia/Wikidata/OSM extracts (`CC BY-SA 4.0` / `CC0` / `ODbL 1.0`)
- **Opening Hours Coverage:** `17/60` pilot POIs (across `101` total DB places)

---

## 3. Reviews Integrity, PII Removal & Dynamic Trending Adapter

1. **Reviews Trust & Aggregation (`apps/backend/src/modules/reviews/reviews.service.ts`):**
   - `findByPlace` and `findById` now reject unverified/deleted places (`404`) and filter strictly `{ deletedAt: null, trusted: true }`.
   - `_updatePlaceRating` aggregates strictly over `{ deletedAt: null, trusted: true }` and resets `place.rating = null` (never `0`) when zero trusted reviews remain.
   - `create` persists `visitDate`, enforces verified place target, and hardcodes `source: 'user', trusted: true`.
2. **PII Removal (`apps/backend/src/modules/places/places.service.ts`):**
   - Removed `email: true` from `findById` review `user.select` (only `id`, `profile.displayName`, `profile.avatar` exposed).
3. **Dynamic Trending / Freshness Adapter (`GET /places/trending`):**
   - Ranks only provenance-verified places using real DB signals (trusted reviews, itinerary mentions, curated photo/description presence, multi-source provenance) and exposes transparent `freshness` metadata (`rankingBasis: 'verified_activity_and_enrichment_completeness'`) with **zero fabricated view/click metrics**.

---

## 4. W08 Buddy Matching & Product Wave C Preparation

- **Backend `MatchesModule` (`apps/backend/src/modules/matches/*`):**
  - Opt-in discovery (`GET /matches/candidates`), match list (`GET /matches`), request (`POST /matches/request`), and receiver-only response (`PATCH /matches/:id/respond`) reusing existing Prisma `Match` table without breaking schema changes.
  - Deterministic rule-based compatibility scoring (`0..100` from canonical `interests`, `travelStyle`, and overlapping active `Trip` destinations/dates) at **`\$0` LLM spend**.
  - Strict PII protection (`toSafeBuddyPeerView`): `email`, `phone`, `passwordHash`, and `SafetyContact` fields are never exposed.
- **Flutter Wave C UI Prep (`apps/mobile`):**
  - Preserves existing 5-tab navigation while replacing the `/safety` placeholder with `SafetyAndBuddiesScreen` (W08 Buddy Matching tab + Vietnam emergency hotlines `113/114/115` & safety roadmap).
  - Enhances `PlaceDetailView` with horizontal verified photo gallery, Wikimedia/Wikipedia attribution links, trusted traveler reviews display, and `"Viết đánh giá"` sheet; adds Home `"Nổi bật & Đầy đủ dữ liệu"` trending carousel + cover thumbnails.

---

## 5. Exact Non-Zero Human / Resource Requirements Reported to Owner

1. **Docker Desktop Restart (Local Windows Env Audit Only):** If inspecting the previous local `424`-place Docker Desktop `pgdata` volume specifically (instead of WSL PostgreSQL `5433`), approve Administrator start for `com.docker.service` / Docker Desktop GUI post-reboot.
2. **Remaining Non-Wikimedia Pilot Media (`12/60` POIs):** 12 pilot POIs currently have OSM factual tags (or article extract) without verified Wikimedia Commons photos (`osm_factual_only: 9` + article-only `3`). Full `60/60` photo coverage requires licensed Wikimedia photo uploads or commercial/partner photography approval (zero commercial scraping permitted).
3. **W08 Commercial Rollout:** Block/report moderation workflow, user consent toggle (`searchableBuddy` opt-in column), real-time WebSocket group chat hardening, and live phone verification before public production release.
