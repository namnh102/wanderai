-- TASK 07.4: refresh dataset_registry with ACTUAL counts (idempotent; re-run after any ingestion).
-- Run: Get-Content data/manifests/update_dataset_registry.sql | docker exec -i wanderai-postgres psql -U postgres -d wanderai
UPDATE dataset_registry SET
    record_count = (SELECT count(*) FROM place_sources WHERE source_name = 'osm'),
    retrieved_at = (SELECT max(created_at) FROM place_sources WHERE source_name = 'osm'),
    dataset_version = to_char(now(), 'YYYY.MM.DD'),
    updated_at = now()
WHERE dataset_name = 'osm_places';

UPDATE dataset_registry SET
    record_count = (SELECT count(*) FROM documents WHERE source_name ILIKE 'wikivoyage%'),
    updated_at = now()
WHERE dataset_name = 'wikivoyage_vn';
