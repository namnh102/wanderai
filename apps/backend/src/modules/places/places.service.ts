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
        orderBy: [{ rating: { sort: 'desc', nulls: 'last' } }, { reviewCount: 'desc' }],
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
            // Only trusted, non-deleted reviews are counted.
            select: { reviews: { where: { trusted: true, deletedAt: null } } },
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

  // Lấy chi tiết địa điểm: chỉ dữ kiện có thật trong DB / OSM tags, provenance, và đánh giá tin cậy.
  // Mọi trường không có dữ liệu trả về null (không bịa).
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
            rawData: true,
          },
        },
        reviews: {
          // Synthetic/untrusted reviews are never exposed as traveler reviews.
          where: { deletedAt: null, trusted: true },
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

    const osm = place.placeSources.find((s) => s.sourceName === 'osm');
    const tags = (osm?.rawData ?? {}) as Record<string, unknown>;
    const tag = (...keys: string[]): string | null => {
      for (const k of keys) {
        const v = tags[k];
        if (typeof v === 'string' && v.trim() !== '') return v.trim();
      }
      return null;
    };
    const isVerified = place.placeSources.length > 0;

    const street = tag('addr:street');
    const houseNumber = tag('addr:housenumber');
    const addrParts = [
      [houseNumber, street].filter(Boolean).join(' ') || null,
      tag('addr:suburb', 'addr:district'),
      tag('addr:city'),
    ].filter((x): x is string => !!x);

    // Chỉ tin cậy dữ kiện của bản ghi có provenance; bản ghi dev/test không có nguồn thì không công bố mô tả/giờ mở cửa.
    const sources = place.placeSources.map(({ rawData: _raw, ...s }) => ({
      ...s,
      canonicalUrl: s.sourceName === 'osm' ? `https://www.openstreetmap.org/${s.sourceId}` : null,
      license: s.sourceName === 'osm' ? 'ODbL 1.0' : null,
      attribution: s.sourceName === 'osm' ? '© OpenStreetMap contributors' : null,
    }));

    return {
      ...place,
      placeSources: sources,
      isVerified,
      provenanceCount: place.placeSources.length,
      // Dữ kiện dẫn xuất (null = không có dữ liệu)
      address: isVerified && addrParts.length > 0 ? addrParts.join(', ') : null,
      description: isVerified ? place.description : null,
      openingHours: isVerified ? (tag('opening_hours') ?? place.openingHours) : null,
      website: isVerified ? tag('website', 'contact:website') : null,
      phone: isVerified ? tag('phone', 'contact:phone') : null,
      source: osm
        ? {
            name: 'OpenStreetMap',
            sourceId: osm.sourceId,
            canonicalUrl: `https://www.openstreetmap.org/${osm.sourceId}`,
            license: 'ODbL 1.0',
            attribution: '© OpenStreetMap contributors',
          }
        : null,
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
