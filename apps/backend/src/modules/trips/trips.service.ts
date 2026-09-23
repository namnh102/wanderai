import {
  Injectable,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
} from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { TripStatus } from '@prisma/client';

@Injectable()
export class TripsService {
  constructor(private prisma: PrismaService) {}

  // POST /trips
  async create(
    userId: string,
    data: {
      title: string;
      destinationId?: string;
      startDate?: string;
      endDate?: string;
      totalBudget?: number;
      description?: string;
    },
  ) {
    if (data.startDate && data.endDate) {
      const start = new Date(data.startDate);
      const end = new Date(data.endDate);
      if (end < start) throw new BadRequestException('Ngày về phải sau ngày đi');
    }

    if (data.destinationId) {
      const dest = await this.prisma.destination.findUnique({
        where: { id: data.destinationId },
      });
      if (!dest) throw new NotFoundException('Điểm đến không tồn tại');
    }

    return this.prisma.trip.create({
      data: {
        userId,
        title: data.title,
        description: data.description,
        destinationId: data.destinationId,
        startDate: data.startDate ? new Date(data.startDate) : null,
        endDate: data.endDate ? new Date(data.endDate) : null,
        totalBudget: data.totalBudget,
        status: TripStatus.DRAFT,
      },
      include: {
        destination: {
          select: { id: true, name: true, coverImage: true, province: true },
        },
      },
    });
  }

  // GET /trips
  async findAll(userId: string) {
    return this.prisma.trip.findMany({
      where: { userId, deletedAt: null },
      orderBy: { createdAt: 'desc' },
      include: {
        destination: {
          select: { id: true, name: true, coverImage: true, province: true },
        },
        _count: { select: { members: true, itineraries: true } },
      },
    });
  }

  // GET /trips/:id
  async findById(id: string, userId: string) {
    const trip = await this.prisma.trip.findFirst({
      where: { id, deletedAt: null },
      include: {
        destination: {
          select: {
            id: true, name: true, nameEn: true,
            coverImage: true, province: true, region: true,
          },
        },
        itineraries: {
          orderBy: { dayNumber: 'asc' },
          include: {
            items: {
              orderBy: { orderIndex: 'asc' },
              include: {
                place: { select: { id: true, name: true, address: true, coverImage: true } },
              },
            },
          },
        },
        members: {
          include: {
            user: {
              select: {
                id: true,
                email: true,
                profile: { select: { displayName: true, avatar: true } },
              },
            },
          },
        },
      },
    });

    if (!trip) throw new NotFoundException('Chuyến đi không tồn tại');

    const isMember = trip.members.some((m) => m.userId === userId);
    if (trip.userId !== userId && !isMember) {
      throw new ForbiddenException('Bạn không có quyền xem chuyến đi này');
    }

    return trip;
  }

  // PUT /trips/:id
  async update(
    id: string,
    userId: string,
    data: Partial<{
      title: string;
      description: string;
      startDate: string;
      endDate: string;
      totalBudget: number;
      status: string;
    }>,
  ) {
    const trip = await this.prisma.trip.findFirst({
      where: { id, userId, deletedAt: null },
    });
    if (!trip) throw new NotFoundException('Chuyến đi không tồn tại hoặc bạn không có quyền');

    const updateData: any = {};
    if (data.title) updateData.title = data.title;
    if (data.description !== undefined) updateData.description = data.description;
    if (data.startDate) updateData.startDate = new Date(data.startDate);
    if (data.endDate) updateData.endDate = new Date(data.endDate);
    if (data.totalBudget !== undefined) updateData.totalBudget = data.totalBudget;
    if (data.status) updateData.status = data.status as TripStatus;

    return this.prisma.trip.update({
      where: { id },
      data: updateData,
      include: {
        destination: { select: { id: true, name: true, coverImage: true } },
      },
    });
  }

  // DELETE /trips/:id
  async delete(id: string, userId: string) {
    const trip = await this.prisma.trip.findFirst({
      where: { id, userId, deletedAt: null },
    });
    if (!trip) throw new NotFoundException('Chuyến đi không tồn tại hoặc bạn không có quyền');

    await this.prisma.trip.update({
      where: { id },
      data: { deletedAt: new Date() },
    });

    return { message: 'Đã xóa chuyến đi thành công' };
  }

  // POST /trips/:id/itinerary — thêm ngày + item
  async addItineraryItem(
    tripId: string,
    userId: string,
    data: {
      dayNumber: number;
      activity: string;
      startTime?: string;
      endTime?: string;
      placeId?: string;
      notes?: string;
      estimatedCost?: number;
      transportMode?: string;
    },
  ) {
    await this.findById(tripId, userId); // Kiểm tra quyền

    // Tạo hoặc lấy itinerary cho ngày đó
    const itinerary = await this.prisma.itinerary.upsert({
      where: { tripId_dayNumber: { tripId, dayNumber: data.dayNumber } },
      create: { tripId, dayNumber: data.dayNumber },
      update: {},
    });

    // Tính orderIndex tiếp theo
    const count = await this.prisma.itineraryItem.count({
      where: { itineraryId: itinerary.id },
    });

    return this.prisma.itineraryItem.create({
      data: {
        itineraryId: itinerary.id,
        placeId: data.placeId,
        orderIndex: count + 1,
        startTime: data.startTime,
        endTime: data.endTime,
        activity: data.activity,
        notes: data.notes,
        estimatedCost: data.estimatedCost,
        transportMode: data.transportMode,
      },
      include: {
        place: { select: { id: true, name: true, address: true } },
      },
    });
  }

  // DELETE /trips/:id/itinerary/:itemId
  async removeItineraryItem(tripId: string, itemId: string, userId: string) {
    await this.findById(tripId, userId);

    const item = await this.prisma.itineraryItem.findFirst({
      where: { id: itemId, itinerary: { tripId } },
    });
    if (!item) throw new NotFoundException('Hoạt động không tồn tại trong lịch trình');

    await this.prisma.itineraryItem.delete({ where: { id: itemId } });
    return { message: 'Đã xóa hoạt động khỏi lịch trình' };
  }

  // POST /trips/:id/members
  async addMember(tripId: string, ownerId: string, memberEmail: string) {
    const trip = await this.prisma.trip.findFirst({
      where: { id: tripId, userId: ownerId, deletedAt: null },
    });
    if (!trip) throw new ForbiddenException('Chỉ chủ chuyến đi mới có thể mời thành viên');

    const user = await this.prisma.user.findUnique({ where: { email: memberEmail } });
    if (!user) throw new NotFoundException(`Không tìm thấy user: ${memberEmail}`);

    // Kiểm tra unique constraint
    try {
      return await this.prisma.tripMember.create({
        data: { tripId, userId: user.id, role: 'member' },
        include: {
          user: {
            select: {
              id: true, email: true,
              profile: { select: { displayName: true, avatar: true } },
            },
          },
        },
      });
    } catch {
      throw new BadRequestException('User này đã là thành viên của chuyến đi');
    }
  }
}
