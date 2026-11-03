# W07-B1-FIX-01B — Controlled OSM Re-ingestion Evidence Report

## 1. Authority & Gate Status

- **Task ID**: `W07-B1-FIX-01B-CONTROLLED-OSM-REINGESTION`
- **Authoritative Base (`develop`)**: `b4db0655070cd0b404891964d57241032e08ed84`
- **Accepted Upstream Gate**: `W07-B1-FIX-01A-POSTMERGE-CHATGPT-AUDIT = PASS` (`W07_B1_FIX_01A_STATUS = CLOSED`)
- **Execution Status**: `PASS`
- **`PDG_001_RENDERER_FIX_IMPLEMENTED`**: `true`
- **`PDG_001_CONTROLLED_REINGESTION_VERIFIED`**: `true`
- **`PDG_001_STATUS`**: `REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT`
- **Next Gate**: `W07-B1-FIX-01B-CONTROLLED-REINGESTION-CHATGPT-AUDIT`

---

## 2. Preflight, Quarantine Baseline & Expected Delta

| Metric | Value |
|---|---|
| `TOTAL_DOCUMENTS_BEFORE` | `1223` |
| `OSM_DOCUMENTS_BEFORE` | `759` |
| `WIKIVOYAGE_DOCUMENTS_BEFORE` | `464` |
| `unique_osm_document_ids` / `unique_osm_place_ids` | `759` / `759` |
| `quarantine_table_exists` | `true` |
| `QUARANTINE_ROWS_BEFORE` | `274` (`207` with `osm_document_superseded_by_task_07_5_regeneration`) |
| `EXPECTED_OSM_DOCUMENTS` | `759` |
| `EXPECTED_CHANGED_CONTENT_HASH_COUNT` | `616` |
| `EXPECTED_UNCHANGED_CONTENT_HASH_COUNT` | `143` |
| `CROSS_PAIR_HASH_COLLISION_COUNT` | `0` |
| `EXPECTED_CONTENT_HASH_DUPLICATES` | `0` |
| `OSM_BEFORE_SEMANTIC_SHA256` | `8d51be98c50265eae9866fbead7fa4add39a7173af2332c59610dd7f0981626d` |
| `WIKIVOYAGE_BEFORE_SHA256` | `cb1bd4dcf65df35ccba4bee4861d7049b72cf3db8cf86a4868155841cd269811` |

---

## 3. Controlled Re-ingestion — RUN 1 & RUN 2

| Metric | RUN 1 | RUN 2 (Semantic Idempotency) |
|---|---|---|
| `verified_places` | `759` | `759` |
| `documents_generated` | `759` | `759` |
| `chunks_upserted` | `759` | `759` |
| `stale_osm_documents_quarantined_and_removed` | `616` | `0` |
| `TOTAL_DOCUMENTS_AFTER` | `1223` | `1223` |
| `OSM_DOCUMENTS_AFTER` | `759` | `759` |
| `WIKIVOYAGE_DOCUMENTS_AFTER` | `464` | `464` |
| `NEW_OSM_QUARANTINE_ROWS` | `616` | `0` |
| `OSM_SEMANTIC_SHA256` | `276ea8c24f36f6d71329ee5efdccaffcdc6b67574ebc3ffdad36d26721b7fdf0` | `276ea8c24f36f6d71329ee5efdccaffcdc6b67574ebc3ffdad36d26721b7fdf0` |
| `WIKIVOYAGE_SHA256` | `cb1bd4dcf65df35ccba4bee4861d7049b72cf3db8cf86a4868155841cd269811` | `cb1bd4dcf65df35ccba4bee4861d7049b72cf3db8cf86a4868155841cd269811` |

- **`ACTUAL_CHANGED_CONTENT_HASH_COUNT`**: `616` (`== EXPECTED_CHANGED_CONTENT_HASH_COUNT`)
- **`ACTUAL_UNCHANGED_CONTENT_HASH_COUNT`**: `143` (`== EXPECTED_UNCHANGED_CONTENT_HASH_COUNT`)
- **`OSM_EXPECTED_STATE_MISMATCH_COUNT`**: `0`
- **`RUN2_SEMANTIC_CHANGE_COUNT`**: `0`

---

## 4. Frozen 60 Target POI Verification in Stored Documents

- **`TARGET_POI_DOCUMENTS`**: `60`
- **`TARGET_USEFUL_STRUCTURED_DOCUMENTS`**: `40`
- **`TARGET_LOW_INFORMATION_DOCUMENTS`**: `20`
- **`TARGET_CHANGED_CONTENT_HASH_COUNT`**: `58` / `60`

### Deterministic 5-POI Before/After Sample

| POI ID | Name | City | Old Content Hash | New Content Hash | Newly Surfaced Fields |
|---|---|---|---|---|---|
| `698ee756-6062-5f47-955b-bdf458682e57` | Lăng Chủ tịch Hồ Chí Minh | Hà Nội | `1a7fe0d119b5c43d...` | `ed67c282518e215e...` | `address (addr:*)`, `opening_hours`, `wheelchair`, `wikidata`, `wikipedia` |
| `f0d424bd-f722-540f-8964-5e6fd8875b56` | Bảo tàng Dân tộc học Việt Nam | Hà Nội | `758fdf02d659396b...` | `0d97dc34504ee43d...` | `address (addr:*)`, `email`, `opening_hours`, `operator`, `phone`, `website`, `wikidata`, `wikipedia` |
| `acb22336-1124-49d5-a279-6357c2b2b445` | Quán Ăn Ngon - Phan Bội Châu | Hà Nội | `86dd5f83e4d8e247...` | `66d66f85d5bb064f...` | `address (addr:*)`, `cuisine`, `opening_hours`, `phone`, `website` |
| `9974ff88-5418-5867-ae49-1b72e0f0861f` | Cầu Rồng | Đà Nẵng | `779bbb9c42bb7d3e...` | `1c86cdc9f2d7ed2e...` | `description`, `opening_hours`, `wikidata` |
| `b37d68ee-0cb3-49f0-a399-cac4c8e2732c` | Nhà hàng Hồng Hạnh 3 | Hạ Long | `08603a8a29683b2a...` | `74c21285e0c191a2...` | `address (addr:*)`, `cuisine`, `phone`, `website` |

---

## 5. Embedding Validity & Retrieval Smoke Checks

- **`OSM_EMBEDDING_MODEL_SET`**: `['sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2']`
- **`distinct_vector_dims`**: `[384]`
- **`null_embedding_count_all`**: `0`
- **`duplicate_content_hash_embedding_model_count`**: `0`
- **Retrieval Smoke Status**: `PASS` (`3` checks passed)

---

## 6. Historical B1A & Upstream Immutability

- **B1A JSON Internal SHA-256**: `27d6dae8fd3ec284ea92806080a044b6745fb30abdddc265297e0f9da1d1c5b2`
- **B1A JSON LF SHA-256**: `433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563`
- **B1A Markdown LF SHA-256**: `130aca652c9b808a8b7e5fac50d070dd0c3f36a8e94f7693cfac8793643d0ac5`
- **`NEW_WEB_DOCUMENT_DOWNLOADS`**: `0`
- **`NEW_SOCIAL_COLLECTION`**: `0`
- **`NEW_GOOGLE_MAPS_COLLECTION`**: `0`
- **`NEW_LLM_PROVIDER_CALLS`**: `0`
- **`NEW_EXTERNAL_API_CALLS_FOR_CORPUS`**: `0`
- **`NEW_MODEL_DOWNLOADS`**: `0`
