import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Seeding WanderAI database...\n');

  // 1. Seed Categories
  const categoriesPath = path.join(__dirname, '../../../database/seed/categories.json');
  const categories = JSON.parse(fs.readFileSync(categoriesPath, 'utf-8'));
  
  let categoryCount = 0;
  const categoryMap: Record<string, string> = {};
  
  for (const cat of categories) {
    const created = await prisma.placeCategory.upsert({
      where: { name: cat.name },
      update: {},
      create: { name: cat.name, icon: cat.icon, color: cat.color },
    });
    categoryMap[cat.name] = created.id;
    categoryCount++;
  }
  console.log(`✅ ${categoryCount} categories seeded`);

  // 2. Seed Destinations
  const destinationsPath = path.join(__dirname, '../../../database/seed/destinations.json');
  const destinations = JSON.parse(fs.readFileSync(destinationsPath, 'utf-8'));
  
  let destCount = 0;
  const destMap: Record<string, string> = {};

  for (const dest of destinations) {
    const created = await prisma.destination.upsert({
      where: { slug: dest.slug },
      update: {},
      create: {
        name: dest.name,
        nameEn: dest.nameEn,
        slug: dest.slug,
        description: dest.description,
        province: dest.province,
        region: dest.region,
        latitude: dest.latitude,
        longitude: dest.longitude,
        rating: dest.rating || 0,
        isPopular: dest.isPopular || false,
      },
    });
    destMap[dest.slug] = created.id;
    destCount++;
  }
  console.log(`✅ ${destCount} destinations seeded`);

  // 3. Seed Places
  const placesPath = path.join(__dirname, '../../../database/seed/places.json');
  const places = JSON.parse(fs.readFileSync(placesPath, 'utf-8'));
  
  let placeCount = 0;

  for (const place of places) {
    const destinationId = destMap[place.destination];
    const categoryId = categoryMap[place.category] || null;

    if (!destinationId) {
      console.warn(`⚠️ Destination "${place.destination}" not found for place "${place.name}"`);
      continue;
    }

    await prisma.place.create({
      data: {
        destinationId,
        categoryId,
        name: place.name,
        nameEn: place.nameEn,
        description: place.description,
        address: place.address,
        latitude: place.latitude,
        longitude: place.longitude,
        priceMin: place.priceMin || null,
        priceMax: place.priceMax || null,
      },
    });
    placeCount++;
  }
  console.log(`✅ ${placeCount} places seeded`);

  console.log(`\n🎉 Seeding complete!`);
  console.log(`   Destinations: ${destCount}`);
  console.log(`   Places: ${placeCount}`);
  console.log(`   Categories: ${categoryCount}`);
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
