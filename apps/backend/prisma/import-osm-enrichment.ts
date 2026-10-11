import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

/**
 * TASK 07.4 - imports data/curated/places_osm_enrichment.json (built by data/pipelines/osm/enrich_osm.py
 * from real Overpass responses). Idempotent: place ids are deterministic (uuid5 of the OSM id) and
 * place_sources is upserted on (source_name, source_id). Denylisted sources are never imported.
 */
const prisma = new PrismaClient();

const CITY_SLUG_MAP: Record<string, string> = {
  da_nang: 'da-nang',
  hanoi: 'ha-noi',
  hoi_an: 'hoi-an',
  hue: 'hue',
  nha_trang: 'nha-trang',
};

async function main() {
  const file = path.resolve(__dirname, '../../../data/curated/places_osm_enrichment.json');
  if (!fs.existsSync(file)) throw new Error(`Missing ${file}; run data/pipelines/osm/enrich_osm.py first`);
  const places = JSON.parse(fs.readFileSync(file, 'utf-8'));

  const denyFile = path.resolve(__dirname, '../../../data/manifests/osm-invalid-sources.json');
  const deny = new Set<string>(
    fs.existsSync(denyFile)
      ? (JSON.parse(fs.readFileSync(denyFile, 'utf-8')).invalid_sources || []).map(
          (s: any) => `${s.source_name}:${s.source_id}`,
        )
      : [],
  );

  const dests = new Map((await prisma.destination.findMany()).map((d) => [d.slug, d.id]));
  const cats = new Map((await prisma.placeCategory.findMany()).map((c) => [c.name.toLowerCase(), c.id]));
  const catId = async (name: string) => {
    if (!cats.has(name)) {
      const c = await prisma.placeCategory.upsert({ where: { name }, update: {}, create: { name } });
      cats.set(name, c.id);
    }
    return cats.get(name)!;
  };

  let placesDone = 0;
  let sourcesDone = 0;
  let skipped = 0;
  for (const p of places) {
    const src = (p.sources || []).filter((s: any) => !deny.has(`${s.source_name}:${s.source_id}`));
    if (src.length === 0) {
      skipped++;
      continue;
    }
    const destinationId = dests.get(CITY_SLUG_MAP[p.city]);
    if (!destinationId) {
      console.warn(`No destination for city ${p.city}; skipping ${p.name}`);
      skipped++;
      continue;
    }
    const categoryId = await catId(p.category);
    const data = {
      destinationId,
      categoryId,
      name: p.name,
      nameEn: p.name_en || null,
      address: p.address || null,
      latitude: p.latitude,
      longitude: p.longitude,
    };
    await prisma.place.upsert({
      where: { id: p.id },
      create: { id: p.id, ...data, rating: null, reviewCount: 0 },
      update: data,
    });
    placesDone++;
    for (const s of src) {
      const fields = {
        placeId: p.id,
        rawName: s.raw_name,
        latitude: s.latitude ?? null,
        longitude: s.longitude ?? null,
        rawData: { ...(s.raw_data || {}), _osm_base_timestamp: s.osm_base_timestamp ?? null },
        confidenceScore: s.confidence_score ?? 1.0,
      };
      await prisma.placeSource.upsert({
        where: { sourceName_sourceId: { sourceName: s.source_name, sourceId: s.source_id } },
        create: { sourceName: s.source_name, sourceId: s.source_id, ...fields },
        update: fields,
      });
      sourcesDone++;
    }
  }
  console.log(`Imported ${placesDone} places, ${sourcesDone} place_sources (skipped ${skipped}).`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
