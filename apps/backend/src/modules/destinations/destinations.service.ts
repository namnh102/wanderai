import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';
import { sanitizeDestination } from './destination-trust';

@Injectable()
export class DestinationsService {
  constructor(private prisma: PrismaService) {}

  // Lấy danh sách destinations với pagination, search, filter
  async findAll(page: number = 1, limit: number = 20, search?: string, region?: string) {
    const skip = (page - 1) * limit;

    const where: Prisma.DestinationWhereInput = {
      deletedAt: null,
      ...(search && {
        OR: [
          { name: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
          { province: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
          { nameEn: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
        ],
      }),
      ...(region && { region }),
    };

    const [items, total] = await Promise.all([
      this.prisma.destination.findMany({
        where,
        skip,
        take: limit,
        orderBy: [{ isPopular: 'desc' }, { rating: 'desc' }],
        include: {
          _count: { select: { places: true } },
        },
      }),
      this.prisma.destination.count({ where }),
    ]);

    // Seeded destination ratings are synthetic: only reviewed ratings are exposed (see destination-trust.ts).
    return { items: items.map((d) => sanitizeDestination(d)), total, page, limit, totalPages: Math.ceil(total / limit) };
  }

  // Lấy chi tiết destination + places
  async findById(id: string) {
    const dest = await this.prisma.destination.findUnique({
      where: { id },
      include: {
        places: {
          // Only provenance-backed (verified) places are public; legacy seed prices are never exposed.
          where: { deletedAt: null, placeSources: { some: {} } },
          include: { category: true },
          orderBy: { rating: 'desc' },
        },
      },
    });

    if (!dest) throw new NotFoundException('Destination không tồn tại');
    return {
      ...sanitizeDestination(dest),
      places: dest.places.map(({ priceMin: _priceMin, priceMax: _priceMax, ...p }) => p),
    };
  }

  // Lấy destinations nổi bật
  async findPopular(limit: number = 10) {
    const popular = await this.prisma.destination.findMany({
      where: { isPopular: true, deletedAt: null },
      take: limit,
      orderBy: { rating: 'desc' },
    });
    return popular.map((d) => sanitizeDestination(d));
  }

  // Tìm destinations gần vị trí GPS (PostGIS)
  async findNearby(lat: number, lng: number, radiusKm: number = 50) {
    const result = await this.prisma.$queryRaw`
      SELECT id, name, province, region, latitude, longitude,
        CASE WHEN review_count > 0 AND rating > 0 THEN rating ELSE NULL END AS rating,
        ST_Distance(
          ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
          ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
        ) / 1000 AS distance_km
      FROM destinations
      WHERE deleted_at IS NULL
        AND latitude IS NOT NULL
        AND ST_DWithin(
          ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
          ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography,
          ${radiusKm * 1000}
        )
      ORDER BY distance_km
      LIMIT 20;
    `;
    return result;
  }
}
