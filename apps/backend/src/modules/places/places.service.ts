import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';

@Injectable()
export class PlacesService {
  constructor(private prisma: PrismaService) {}

  // Lấy danh sách địa điểm có pagination, search, category, destination, verifiedOnly
  async findAll(
    page: number = 1,
    limit: number = 20,
    search?: string,
    category?: string,
    destinationId?: string,
    verifiedOnly?: boolean,
  ) {
    const skip = (page - 1) * limit;

    const where: Prisma.PlaceWhereInput = {
      deletedAt: null,
      ...(destinationId && { destinationId }),
      ...(verifiedOnly && {
        placeSources: { some: {} },
      }),
      ...(category && {
        category: {
          name: { equals: category.toLowerCase(), mode: 'insensitive' as Prisma.QueryMode },
        },
      }),
      ...(search && {
        OR: [
          { name: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
          { nameEn: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
          { address: { contains: search, mode: 'insensitive' as Prisma.QueryMode } },
        ],
      }),
    };

    const [rawItems, total] = await Promise.all([
      this.prisma.place.findMany({
        where,
        skip,
        take: limit,
        orderBy: [{ rating: 'desc' }, { reviewCount: 'desc' }],
        include: {
          destination: {
            select: { id: true, name: true, slug: true, province: true },
          },
          category: {
            select: { id: true, name: true, icon: true, color: true },
          },
          placeSources: {
            select: {
              sourceName: true,
              sourceId: true,
              confidenceScore: true,
            },
          },
          _count: {
            select: { reviews: true },
          },
        },
      }),
      this.prisma.place.count({ where }),
    ]);

    const items = rawItems.map((p) => ({
      ...p,
      isVerified: p.placeSources.length > 0,
      provenanceCount: p.placeSources.length,
    }));

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  // Lấy chi tiết địa điểm bao gồm nguồn gốc (provenance) và đánh giá (reviews + aspects)
  async findById(id: string) {
    const place = await this.prisma.place.findUnique({
      where: { id },
      include: {
        destination: true,
        category: true,
        placeSources: {
          select: {
            id: true,
            sourceName: true,
            sourceId: true,
            rawName: true,
            confidenceScore: true,
            createdAt: true,
          },
        },
        reviews: {
          where: { deletedAt: null },
          orderBy: { createdAt: 'desc' },
          include: {
            aspects: true,
            user: {
              select: {
                id: true,
                email: true,
                profile: {
                  select: { displayName: true, avatar: true },
                },
              },
            },
          },
        },
      },
    });

    if (!place || place.deletedAt) {
      throw new NotFoundException(`Place with ID "${id}" not found`);
    }

    return {
      ...place,
      isVerified: place.placeSources.length > 0,
      provenanceCount: place.placeSources.length,
    };
  }

  // Tìm kiếm địa điểm lân cận bằng PostGIS ST_DWithin
  async findNearby(
    lat: number,
    lng: number,
    radiusKm: number = 10,
    limit: number = 20,
    verifiedOnly: boolean = false,
  ) {
    const places = await this.prisma.$queryRaw<any[]>`
      SELECT 
        p.id, 
        p.name, 
        p.name_en AS "nameEn", 
        p.address, 
        p.latitude, 
        p.longitude, 
        p.rating, 
        p.review_count AS "reviewCount",
        c.name AS "categoryName",
        d.name AS "destinationName",
        (EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id)) AS "isVerified",
        ST_Distance(
          ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
          ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
        ) / 1000 AS "distanceKm"
      FROM places p
      LEFT JOIN place_categories c ON p.category_id = c.id
      LEFT JOIN destinations d ON p.destination_id = d.id
      WHERE p.deleted_at IS NULL
        AND p.latitude IS NOT NULL
        ${verifiedOnly ? Prisma.sql`AND EXISTS (SELECT 1 FROM place_sources ps WHERE ps.place_id = p.id)` : Prisma.empty}
        AND ST_DWithin(
          ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
          ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography,
          ${radiusKm * 1000}
        )
      ORDER BY "distanceKm" ASC
      LIMIT ${limit};
    `;

    return places;
  }
}
