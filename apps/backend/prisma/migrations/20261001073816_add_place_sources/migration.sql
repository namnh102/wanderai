-- CreateTable
CREATE TABLE "place_sources" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "place_id" UUID NOT NULL,
    "source_name" VARCHAR(50) NOT NULL,
    "source_id" VARCHAR(255) NOT NULL,
    "raw_name" VARCHAR(255) NOT NULL,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "raw_data" JSONB,
    "confidence_score" DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "place_sources_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "place_sources_source_name_source_id_key" ON "place_sources"("source_name", "source_id");

-- AddForeignKey
ALTER TABLE "place_sources" ADD CONSTRAINT "place_sources_place_id_fkey" FOREIGN KEY ("place_id") REFERENCES "places"("id") ON DELETE CASCADE ON UPDATE CASCADE;
