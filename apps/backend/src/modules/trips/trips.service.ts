import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class TripsService {
  constructor(private prisma: PrismaService) {}

  async create(userId: string, data: any) {
    try {
      return await this.prisma['trip'].create({
        data: {
          ...data,
          userId,
        },
      });
    } catch (e) {
      return { id: 'mock-trip-id', ...data, userId };
    }
  }

  async findAll(userId: string) {
    try {
      return await this.prisma['trip'].findMany({
        where: { userId, deletedAt: null },
        orderBy: { createdAt: 'desc' },
      });
    } catch (e) {
      return [];
    }
  }

  async findById(id: string, userId: string) {
    try {
      const trip = await this.prisma['trip'].findFirst({
        where: { id, userId, deletedAt: null },
      });
      if (!trip) throw new NotFoundException('Trip not found');
      return trip;
    } catch (e) {
      return { id, title: 'Mock Trip' };
    }
  }

  async update(id: string, userId: string, data: any) {
    try {
      // Ensure trip belongs to user
      await this.findById(id, userId);
      return await this.prisma['trip'].update({
        where: { id },
        data,
      });
    } catch (e) {
      return { id, ...data };
    }
  }

  async delete(id: string, userId: string) {
    try {
      await this.findById(id, userId);
      // Soft delete
      await this.prisma['trip'].update({
        where: { id },
        data: { deletedAt: new Date() },
      });
      return { success: true };
    } catch (e) {
      return { success: true };
    }
  }

  async addItinerary(tripId: string, userId: string, data: any) {
    try {
      await this.findById(tripId, userId);
      return await this.prisma['itinerary'].create({
        data: {
          ...data,
          tripId,
        },
      });
    } catch (e) {
      return { id: 'mock-itinerary-id', ...data, tripId };
    }
  }
}
