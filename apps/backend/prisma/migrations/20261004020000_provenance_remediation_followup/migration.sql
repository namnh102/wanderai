-- TASK 07.3 follow-up: the live Overpass provenance audit found 2 more OSM sources that exist upstream
-- but describe a different object than the place they are attached to (name differs and the node is
-- 156 m / 307 m away from the stored coordinates). They are quarantined, not re-pointed (no invented ids).
INSERT INTO "place_source_quarantine"
    ("original_id","place_id","source_name","source_id","raw_name","latitude","longitude","raw_data","reason","evidence")
SELECT ps."id", ps."place_id", ps."source_name", ps."source_id", ps."raw_name", ps."latitude", ps."longitude", ps."raw_data",
       'osm_node_mismatches_place',
       jsonb_build_object('verified_with','Overpass API','verified_on','2026-10-04',
                          'place_name', p."name", 'stored_lat', p."latitude", 'stored_lon', p."longitude",
                          'upstream_name', ps."raw_name")
FROM "place_sources" ps JOIN "places" p ON p."id" = ps."place_id"
WHERE ps."source_name" = 'osm' AND ps."source_id" IN ('node/708488382','node/708488342');

DELETE FROM "place_sources"
WHERE "source_name" = 'osm' AND "source_id" IN ('node/708488382','node/708488342');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'place_id') THEN
        INSERT INTO "document_quarantine" ("original_id", "row_data", "reason")
        SELECT d."id", to_jsonb(d) - 'embedding', 'chunk_linked_to_place_without_verified_source'
        FROM "documents" d
        WHERE d."place_id" IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM "place_sources" ps WHERE ps."place_id" = d."place_id");

        DELETE FROM "documents" d
        WHERE d."place_id" IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM "place_sources" ps WHERE ps."place_id" = d."place_id");
    END IF;
END $$;
