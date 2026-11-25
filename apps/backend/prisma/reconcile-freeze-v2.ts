import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

interface FreezeV2Source {
  source_name: string;
  source_id: string;
  confidence_score?: number;
  raw_data?: Record<string, unknown>;
}

interface FreezeV2Place {
  place_id: string;
  name: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  opening_hours?: string | null;
  category: string;
  destination_slug: string;
  is_rec_a_core_v2?: boolean;
  sources?: FreezeV2Source[];
}

interface Pilot60Item {
  place_id: string;
  description?: string | null;
  cover_image?: string | null;
  images?: string[];
  opening_hours?: string | null;
}

const CITY_SLUG_MAP: Record<string, string> = {
  da_nang: 'da-nang',
  hanoi: 'ha-noi',
  ha_noi: 'ha-noi',
  ha_long: 'ha-long',
  hoi_an: 'hoi-an',
  hue: 'hue',
  nha_trang: 'nha-trang',
};

function resolveDataFile(relPath: string): string {
  const candidate1 = path.resolve(__dirname, '../../../', relPath);
  if (fs.existsSync(candidate1)) return candidate1;
  return path.resolve(process.cwd(), relPath);
}

async function snapshotInventory(freezeV2: FreezeV2Place[]) {
  const freezeById = new Map(freezeV2.map((f) => [f.place_id, f]));
  const places = await prisma.place.findMany({
    where: { deletedAt: null },
    select: {
      id: true,
      name: true,
      description: true,
      coverImage: true,
      images: true,
      openingHours: true,
      rating: true,
      reviewCount: true,
      destination: { select: { slug: true } },
      _count: { select: { placeSources: true } },
    },
  });

  const dbById = new Map(places.map((p) => [p.id, p]));
  const missingFreezeIds = freezeV2
    .filter((f) => !dbById.has(f.place_id))
    .map((f) => ({ place_id: f.place_id, slug: f.destination_slug, core: !!f.is_rec_a_core_v2 }));

  const perSlug: Record<string, { total: number; verified: number; unverified: number }> = {};
  let verifiedCount = 0;
  let unverifiedCount = 0;
  let withCoverImage = 0;
  let withDescription = 0;
  let withOpeningHours = 0;

  for (const p of places) {
    const slug = p.destination.slug;
    perSlug[slug] ??= { total: 0, verified: 0, unverified: 0 };
    perSlug[slug].total++;
    const isVerified = p._count.placeSources > 0;
    if (isVerified) {
      perSlug[slug].verified++;
      verifiedCount++;
    } else {
      perSlug[slug].unverified++;
      unverifiedCount++;
    }
    if (p.coverImage && p.coverImage.trim()) withCoverImage++;
    if (p.description && p.description.trim()) withDescription++;
    if (p.openingHours && p.openingHours.trim()) withOpeningHours++;
  }

  const missingBySlug: Record<string, number> = {};
  const missingCoreBySlug: Record<string, number> = {};
  for (const m of missingFreezeIds) {
    missingBySlug[m.slug] = (missingBySlug[m.slug] ?? 0) + 1;
    if (m.core) missingCoreBySlug[m.slug] = (missingCoreBySlug[m.slug] ?? 0) + 1;
  }

  const extraUnverifiedInDb = places
    .filter((p) => !freezeById.has(p.id))
    .map((p) => p.id).length;

  const [trustedReviews, untrustedReviews] = await Promise.all([
    prisma.review.count({ where: { deletedAt: null, trusted: true } }),
    prisma.review.count({ where: { deletedAt: null, trusted: false } }),
  ]);

  return {
    totalActivePlaces: places.length,
    verifiedPlaces: verifiedCount,
    unverifiedLegacyPlaces: unverifiedCount,
    freezeV2Total: freezeV2.length,
    freezeV2Present: freezeV2.length - missingFreezeIds.length,
    missingFreezeV2Count: missingFreezeIds.length,
    missingFreezeV2BySlug: missingBySlug,
    missingCoreV2BySlug: missingCoreBySlug,
    extraNonFreezePlacesInDb: extraUnverifiedInDb,
    perDestinationSlug: perSlug,
    completeness: {
      withCoverImage,
      withDescription,
      withOpeningHours,
      trustedReviews,
      untrustedQuarantinedReviews: untrustedReviews,
    },
  };
}

async function run() {
  const args = new Set(process.argv.slice(2));
  const auditOnly = args.has('--audit-only');

  const freezeV2: FreezeV2Place[] = JSON.parse(
    fs.readFileSync(resolveDataFile('data/curated/gomate_places_freeze_v2.json'), 'utf-8'),
  );
  const categoriesSeed = JSON.parse(
    fs.readFileSync(resolveDataFile('database/seed/categories.json'), 'utf-8'),
  );
  const destinationsSeed = JSON.parse(
    fs.readFileSync(resolveDataFile('database/seed/destinations.json'), 'utf-8'),
  );

  const invalidPath = resolveDataFile('data/manifests/osm-invalid-sources.json');
  const revalidationPath = resolveDataFile('data/manifests/osm-source-revalidation-v2.json');
  const revalidated = new Set<string>(
    fs.existsSync(revalidationPath)
      ? (JSON.parse(fs.readFileSync(revalidationPath, 'utf-8')).revalidations || [])
          .filter((r: any) => r.status === 'REVALIDATED_CURRENT_OSM_MATCH')
          .map((r: any) => r.source_id)
      : [],
  );
  const denylisted = new Set<string>(
    fs.existsSync(invalidPath)
      ? (JSON.parse(fs.readFileSync(invalidPath, 'utf-8')).invalid_sources || [])
          .filter((s: any) => !revalidated.has(s.source_id))
          .map((s: any) => `${s.source_name}:${s.source_id}`)
      : [],
  );

  const before = await snapshotInventory(freezeV2);
  let placesUpserted = 0;
  let sourcesUpserted = 0;
  let pilot60Applied = 0;

  if (!auditOnly) {
    // 1. Non-destructively ensure categories + 50 destinations exist
    for (const cat of categoriesSeed) {
      await prisma.placeCategory.upsert({
        where: { name: cat.name },
        update: {},
        create: { name: cat.name, icon: cat.icon ?? '📍', color: cat.color ?? '#4B5563' },
      });
    }
    for (const extraCat of ['culture', 'entertainment', 'nature']) {
      await prisma.placeCategory.upsert({
        where: { name: extraCat },
        update: {},
        create: { name: extraCat, icon: '📍', color: '#4B5563' },
      });
    }
    for (const dest of destinationsSeed) {
      await prisma.destination.upsert({
        where: { slug: dest.slug },
        update: {},
        create: {
          name: dest.name,
          nameEn: dest.nameEn ?? null,
          slug: dest.slug,
          description: dest.description ?? null,
          province: dest.province ?? null,
          region: dest.region ?? null,
          latitude: dest.latitude ?? null,
          longitude: dest.longitude ?? null,
          rating: typeof dest.rating === 'number' ? dest.rating : 0,
          reviewCount: 0,
          isPopular: Boolean(dest.isPopular),
        },
      });
    }

    const destBySlug = new Map(
      (await prisma.destination.findMany()).map((d) => [d.slug, d.id]),
    );
    const catByName = new Map(
      (await prisma.placeCategory.findMany()).map((c) => [c.name.toLowerCase(), c.id]),
    );

    // 2. Non-destructively upsert all 759 Freeze V2 POIs & PlaceSources (zero TRUNCATE)
    for (const fp of freezeV2) {
      const slug = CITY_SLUG_MAP[fp.destination_slug] || fp.destination_slug;
      const destinationId = destBySlug.get(slug);
      if (!destinationId) continue;
      const categoryId = catByName.get(fp.category.toLowerCase()) ?? null;

      await prisma.place.upsert({
        where: { id: fp.place_id },
        create: {
          id: fp.place_id,
          destinationId,
          categoryId,
          name: fp.name,
          address: fp.address ?? null,
          latitude: fp.latitude ?? null,
          longitude: fp.longitude ?? null,
          openingHours: fp.opening_hours ?? null,
          rating: null,
          reviewCount: 0,
        },
        update: {
          destinationId,
          categoryId,
          name: fp.name,
          address: fp.address ?? null,
          latitude: fp.latitude ?? null,
          longitude: fp.longitude ?? null,
          ...(fp.opening_hours ? { openingHours: fp.opening_hours } : {}),
        },
      });
      placesUpserted++;

      for (const src of fp.sources || []) {
        if (denylisted.has(`${src.source_name}:${src.source_id}`)) continue;
        await prisma.placeSource.upsert({
          where: {
            sourceName_sourceId: { sourceName: src.source_name, sourceId: src.source_id },
          },
          create: {
            placeId: fp.place_id,
            sourceName: src.source_name,
            sourceId: src.source_id,
            rawName: fp.name,
            latitude: fp.latitude ?? null,
            longitude: fp.longitude ?? null,
            rawData: (src.raw_data ?? {}) as any,
            confidenceScore: src.confidence_score ?? 1.0,
          },
          update: {
            placeId: fp.place_id,
            rawName: fp.name,
            latitude: fp.latitude ?? null,
            longitude: fp.longitude ?? null,
            rawData: (src.raw_data ?? {}) as any,
            confidenceScore: src.confidence_score ?? 1.0,
          },
        });
        sourcesUpserted++;
      }
    }

    // 3. Apply curated 60-pilot enrichment (only factual Wikimedia/OSM media & descriptions)
    const pilotPath = resolveDataFile('data/enrichment/poi_enrichment_pilot_60_v1.json');
    if (fs.existsSync(pilotPath)) {
      const pilot = JSON.parse(fs.readFileSync(pilotPath, 'utf-8'));
      const items: Pilot60Item[] = Array.isArray(pilot?.items) ? pilot.items : [];
      for (const item of items) {
        const existing = await prisma.place.findUnique({ where: { id: item.place_id } });
        if (!existing) continue;
        const cleanImages = (item.images || []).filter(
          (u) => typeof u === 'string' && u.startsWith('https://'),
        );
        const cleanCover =
          item.cover_image && item.cover_image.startsWith('https://')
            ? item.cover_image
            : cleanImages[0] ?? null;
        await prisma.place.update({
          where: { id: item.place_id },
          data: {
            ...(item.description && item.description.trim()
              ? { description: item.description.trim() }
              : {}),
            ...(cleanCover ? { coverImage: cleanCover } : {}),
            ...(cleanImages.length > 0 ? { images: cleanImages } : {}),
            ...(item.opening_hours && !existing.openingHours
              ? { openingHours: item.opening_hours }
              : {}),
          },
        });
        pilot60Applied++;
      }
    }
  }

  const after = await snapshotInventory(freezeV2);
  const report = {
    mode: auditOnly ? 'READONLY_AUDIT' : 'NON_DESTRUCTIVE_RECONCILE_AND_ENRICH',
    before,
    actions: { placesUpserted, sourcesUpserted, pilot60Applied },
    after,
  };
  console.log(JSON.stringify(report, null, 2));
}

run()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
