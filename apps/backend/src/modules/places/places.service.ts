import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';

import { osmAddress, osmAddressSql, osmOpeningHours, osmPhone, osmWebsite } from './osm-tags';
import { sanitizeDestination } from '../destinations/destination-trust';

// Re-exported for backwards compatibility; canonical implementation lives in osm-tags.ts.
export { osmAddress };

@Injectable()
export class PlacesService {
  constructor(
    private prisma: PrismaService,
    private aiProxyService: AiProxyService,
  ) {}

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
        // `id` is the final unique tiebreaker: rating/reviewCount tie for nearly every verified POI, and
        // without a unique last key OFFSET pagination yields duplicate and missing rows across pages.
        orderBy: [{ rating: { sort: 'desc', nulls: 'last' } }, { reviewCount: 'desc' }, { id: 'asc' }],
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
              rawData: true, // only used to derive the factual address; stripped below
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

    const items = rawItems.map((p) => {
      const osm = p.placeSources.find((s) => s.sourceName === 'osm');
      // Legacy seed prices are not backed by any authoritative dataset: never exposed publicly.
      const { priceMin: _priceMin, priceMax: _priceMax, ...publicPlace } = p;
      return {
        ...publicPlace,
        placeSources: p.placeSources.map(({ rawData: _raw, ...s }) => s),
        // Factual OSM address only; never the importer-generated places.address.
        address: osmAddress((osm?.rawData ?? null) as Record<string, unknown> | null),
        isVerified: p.placeSources.length > 0,
        provenanceCount: p.placeSources.length,
      };
    });

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

    // Trust boundary (W3-04 / PDG-004): a place without any provenance source is a legacy seed record, not a
    // verified tourism POI. It is not publicly servable. (No itinerary item or mobile path references them.)
    if (!place || place.deletedAt || place.placeSources.length === 0) {
      throw new NotFoundException(`Place with ID "${id}" not found`);
    }

    const osm = place.placeSources.find((s) => s.sourceName === 'osm');
    const raw = (osm?.rawData ?? null) as Record<string, unknown> | null;

    const sources = place.placeSources.map(({ rawData: _raw, ...s }) => ({
      ...s,
      canonicalUrl: s.sourceName === 'osm' ? `https://www.openstreetmap.org/${s.sourceId}` : null,
      license: s.sourceName === 'osm' ? 'ODbL 1.0' : null,
      attribution: s.sourceName === 'osm' ? '© OpenStreetMap contributors' : null,
    }));

    // Legacy seed prices are not backed by any authoritative dataset: never exposed publicly.
    const { priceMin: _priceMin, priceMax: _priceMax, ...publicPlace } = place;

    return {
      ...publicPlace,
      destination: sanitizeDestination(place.destination),
      placeSources: sources,
      isVerified: true,
      provenanceCount: place.placeSources.length,
      // Dữ kiện dẫn xuất từ OSM tags (null = không có dữ liệu). Không dùng places.address (importer-generated).
      address: osmAddress(raw),
      description: place.description,
      openingHours: osmOpeningHours(raw) ?? place.openingHours,
      website: osmWebsite(raw),
      phone: osmPhone(raw),
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
        (
          SELECT ${osmAddressSql('ps.raw_data')}
          FROM place_sources ps
          WHERE ps.place_id = p.id AND ps.source_name = 'osm'
          ORDER BY ps.created_at ASC
          LIMIT 1
        ) AS address,
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
      ORDER BY "distanceKm" ASC, p.id ASC
      LIMIT ${limit};
    `;

    return places;
  }

  // Gợi ý địa điểm cá nhân hóa dựa trên TravelPreference (REC-A)
  async getRecommendations(
    userId: string,
    destination?: string,
    topK: number = 10,
    model: string = 'rec-a1',
  ) {
    const pref = await this.prisma.travelPreference.findUnique({
      where: { userId },
    });

    const userPrefs = pref
      ? {
          interests: pref.interests,
          travelStyle: pref.travelStyle,
          budgetMin: pref.budgetMin,
          budgetMax: pref.budgetMax,
          preferredGroup: pref.preferredGroup,
          avoidances: pref.avoidances,
          dietaryNeeds: pref.dietaryNeeds,
        }
      : { interests: [] };

    return this.aiProxyService.getPlaceRecommendations(userPrefs, destination, topK, model);
  }
}
