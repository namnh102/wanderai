import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';
import * as bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

const CITY_SLUG_MAP: Record<string, string> = {
  da_nang: 'da-nang',
  'đà nẵng': 'da-nang',
  hanoi: 'ha-noi',
  'hà nội': 'ha-noi',
  hoi_an: 'hoi-an',
  'hội an': 'hoi-an',
  hue: 'hue',
  'huế': 'hue',
  nha_trang: 'nha-trang',
  'nha trang': 'nha-trang',
  ho_chi_minh: 'ho-chi-minh',
};

async function importCuratedData() {
  console.log('🚀 Starting GoMate Curated Travel Data Import...\n');

  // 1. Ensure Curator User exists
  const curatorPasswordHash = await bcrypt.hash('curator_wanderai_2026', 10);
  const curatorUser = await prisma.user.upsert({
    where: { email: 'curator@wanderai.vn' },
    update: {},
    create: {
      email: 'curator@wanderai.vn',
      passwordHash: curatorPasswordHash,
      role: 'ADMIN',
      isVerified: true,
      profile: {
        create: {
          displayName: 'WanderAI Verified Curator',
          bio: 'Automated data curation and benchmark verification bot',
        },
      },
    },
  });
  console.log(`👤 Curator user verified: ${curatorUser.email} (${curatorUser.id})`);

  // 2. Load and index destinations
  const destinations = await prisma.destination.findMany();
  const destBySlug = new Map<string, string>();
  for (const d of destinations) {
    destBySlug.set(d.slug, d.id);
  }
  const defaultDestId = destBySlug.get('da-nang') || destinations[0]?.id;
  if (!defaultDestId) {
    throw new Error('No destination found in database. Seed destinations first!');
  }
  console.log(`📍 Found ${destinations.length} active destinations in database`);

  // 3. Ensure Category exists
  const categories = await prisma.placeCategory.findMany();
  const catByName = new Map<string, string>();
  for (const c of categories) {
    catByName.set(c.name.toLowerCase(), c.id);
  }

  async function getOrCreateCategory(catName: string): Promise<string> {
    const key = catName.toLowerCase();
    if (catByName.has(key)) {
      return catByName.get(key)!;
    }
    const created = await prisma.placeCategory.upsert({
      where: { name: key },
      update: {},
      create: { name: key },
    });
    catByName.set(key, created.id);
    return created.id;
  }

  // 4. Load Canonical Places
  const placesFilePath = path.resolve(__dirname, '../../../data/curated/places_canonical.json');
  if (!fs.existsSync(placesFilePath)) {
    throw new Error(`Canonical places file missing: ${placesFilePath}`);
  }
  const canonicalPlaces = JSON.parse(fs.readFileSync(placesFilePath, 'utf-8'));
  console.log(`📦 Loaded ${canonicalPlaces.length} canonical places from ${placesFilePath}`);

  // OSM source ids that failed upstream verification must never be imported as provenance.
  const invalidSourcesPath = path.resolve(__dirname, '../../../data/manifests/osm-invalid-sources.json');
  const invalidSourceKeys = new Set<string>(
    fs.existsSync(invalidSourcesPath)
      ? (JSON.parse(fs.readFileSync(invalidSourcesPath, 'utf-8')).invalid_sources || []).map(
          (s: any) => `${s.source_name}:${s.source_id}`,
        )
      : [],
  );

  let placeUpsertCount = 0;
  let sourceUpsertCount = 0;
  let skippedInvalidSources = 0;

  for (const p of canonicalPlaces) {
    const cityKey = (p.city || '').toLowerCase().trim();
    const destSlug = CITY_SLUG_MAP[cityKey] || cityKey.replace(/_/g, '-');
    const destinationId = destBySlug.get(destSlug) || defaultDestId;

    const categoryId = await getOrCreateCategory(p.category || 'other');

    // Upsert Place
    await prisma.place.upsert({
      where: { id: p.id },
      create: {
        id: p.id,
        destinationId,
        categoryId,
        name: p.name,
        nameEn: p.name_en || null,
        description: p.description || null,
        address: p.address || null,
        latitude: p.latitude,
        longitude: p.longitude,
        rating: p.rating ?? null, // NULL = unavailable; never fabricate a default
        reviewCount: p.review_count || 0,
      },
      update: {
        destinationId,
        categoryId,
        name: p.name,
        nameEn: p.name_en || null,
        description: p.description || null,
        address: p.address || null,
        latitude: p.latitude,
        longitude: p.longitude,
      },
    });
    placeUpsertCount++;

    // Upsert PlaceSources for provenance
    for (const src of p.sources || []) {
      if (invalidSourceKeys.has(`${src.source_name}:${src.source_id}`)) {
        skippedInvalidSources++;
        continue;
      }
      await prisma.placeSource.upsert({
        where: {
          sourceName_sourceId: {
            sourceName: src.source_name,
            sourceId: src.source_id,
          },
        },
        create: {
          placeId: p.id,
          sourceName: src.source_name,
          sourceId: src.source_id,
          rawName: src.raw_name,
          latitude: src.latitude || null,
          longitude: src.longitude || null,
          rawData: src.raw_data || null,
          confidenceScore: src.confidence_score || 1.0,
        },
        update: {
          placeId: p.id,
          rawName: src.raw_name,
          latitude: src.latitude || null,
          longitude: src.longitude || null,
          rawData: src.raw_data || null,
          confidenceScore: src.confidence_score || 1.0,
        },
      });
      sourceUpsertCount++;
    }
  }
  console.log(`✅ Upserted ${placeUpsertCount} canonical places`);
  console.log(`✅ Upserted ${sourceUpsertCount} place source records`);
  console.log(`Skipped ${skippedInvalidSources} source records on the invalid-source denylist`);

  // 5. Load and Import Curated Reviews
  const reviewsFilePath = path.resolve(__dirname, '../../../data/curated/reviews_curated.json');
  let reviewUpsertCount = 0;
  let aspectCount = 0;

  if (fs.existsSync(reviewsFilePath)) {
    const curatedReviews = JSON.parse(fs.readFileSync(reviewsFilePath, 'utf-8'));
    console.log(`\n💬 Loaded ${curatedReviews.length} curated reviews from ${reviewsFilePath}`);

    for (const rev of curatedReviews) {
      if (!rev.place_id || rev.match_status !== 'linked') {
        continue;
      }

      // Verify place exists in DB
      const targetPlace = await prisma.place.findUnique({ where: { id: rev.place_id } });
      if (!targetPlace) {
        console.warn(`⚠️ Target place ${rev.place_id} not found, skipping review ${rev.id}`);
        continue;
      }

      // Upsert Review
      const reviewRecord = await prisma.review.upsert({
        where: { id: rev.id },
        create: {
          id: rev.id,
          userId: curatorUser.id,
          placeId: rev.place_id,
          rating: rev.rating,
          content: rev.content,
          // The curated review file is an internal mock fixture: never a real traveler review.
          source: 'synthetic',
          trusted: false,
        },
        update: {
          rating: rev.rating,
          content: rev.content,
          source: 'synthetic',
          trusted: false,
        },
      });
      reviewUpsertCount++;

      // Create aspects
      if (rev.aspects && Array.isArray(rev.aspects)) {
        // Delete old aspects if updating
        await prisma.reviewAspect.deleteMany({ where: { reviewId: reviewRecord.id } });
        for (const asp of rev.aspects) {
          await prisma.reviewAspect.create({
            data: {
              reviewId: reviewRecord.id,
              aspect: asp.aspect,
              score: asp.score,
              comment: asp.comment || null,
            },
          });
          aspectCount++;
        }
      }

      // Update place average rating and review count
      const placeReviews = await prisma.review.findMany({
        where: { placeId: rev.place_id, trusted: true, deletedAt: null },
        select: { rating: true },
      });
      // Aggregate only trusted reviews; no trusted review => rating stays NULL.
      const avgRating =
        placeReviews.length > 0
          ? Math.round((placeReviews.reduce((sum, r) => sum + r.rating, 0) / placeReviews.length) * 10) / 10
          : null;
      await prisma.place.update({
        where: { id: rev.place_id },
        data: {
          rating: avgRating,
          reviewCount: placeReviews.length,
        },
      });
    }
  }

  console.log(`✅ Upserted ${reviewUpsertCount} linked reviews with ${aspectCount} aspect ratings`);
  console.log('\n🎉 Curated data import finished successfully! (Idempotent)');
}

importCuratedData()
  .catch((e) => {
    console.error('❌ Curated data import failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
