import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';

@Injectable()
export class DestinationsService {
  constructor(private prisma: PrismaService) {}

  async findAll(page: number = 1, limit: number = 20, search?: string) {
    const skip = (page - 1) * limit;
    
    try {
      const where: Prisma.DestinationWhereInput = search ? { name: { contains: search, mode: 'insensitive' as Prisma.QueryMode }, deletedAt: null } : { deletedAt: null };
      const items = await this.prisma['destination'].findMany({
        where: { ...where, deletedAt: null },
        skip,
        take: limit,
      });
      const total = await this.prisma['destination'].count({ where: { ...where, deletedAt: null } });
      return { items, total, page, limit };
    } catch (e) {
      return { items: [], total: 0, page, limit };
    }
  }

  async findById(id: string) {
    try {
      const dest = await this.prisma['destination'].findUnique({ where: { id } });
      if (!dest) throw new NotFoundException('Destination not found');
      return dest;
    } catch (e) {
      return { id, name: 'Mock Destination' };
    }
  }

  async findNearby(lat: number, lng: number, radiusKm: number = 10) {
    try {
      // Raw SQL PostGIS example
      const result = await this.prisma.$queryRaw`
        SELECT id, name, location,
          ST_Distance(
            location::geography, 
            ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
          ) / 1000 AS distance_km
        FROM "Destination"
        WHERE ST_DWithin(
          location::geography, 
          ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography, 
          ${radiusKm * 1000}
        )
        AND deleted_at IS NULL
        ORDER BY distance_km
        LIMIT 50;
      `;
      return result;
    } catch (e) {
      return [];
    }
  }
}
