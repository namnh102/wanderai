import {
  Injectable,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
} from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { TripStatus } from '@prisma/client';
import { CreateTripDto } from './dto/create-trip.dto';
import { UpdateTripDto } from './dto/update-trip.dto';
import { AddItineraryDto } from './dto/add-itinerary.dto';

@Injectable()
export class TripsService {
  constructor(private prisma: PrismaService) {}

  // POST /trips
  async create(userId: string, data: CreateTripDto) {
    if (data.startDate && data.endDate) {
      const start = new Date(data.startDate);
      const end = new Date(data.endDate);
      if (end < start) {
        throw new BadRequestException('Ngày kết thúc phải sau ngày bắt đầu');
      }
    }

    if (data.totalBudget !== undefined && data.totalBudget < 0) {
      throw new BadRequestException('Ngân sách không được nhỏ hơn 0');
    }

    if (data.destinationId) {
      const dest = await this.prisma.destination.findUnique({
        where: { id: data.destinationId },
      });
      if (!dest) {
        throw new NotFoundException('Điểm đến không tồn tại');
      }
    }

    return this.prisma.trip.create({
      data: {
        userId,
        title: data.title.trim(),
        description: data.description?.trim(),
        destinationId: data.destinationId,
        startDate: data.startDate ? new Date(data.startDate) : null,
        endDate: data.endDate ? new Date(data.endDate) : null,
        totalBudget: data.totalBudget,
        currency: data.currency ?? 'VND',
        travelStyle: data.travelStyle,
        interests: data.interests ?? [],
        status: TripStatus.DRAFT,
        members: {
          create: {
            userId,
            role: 'owner',
          },
        },
      },
      include: {
        destination: {
          select: { id: true, name: true, coverImage: true, province: true },
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
  }

  // GET /trips
  async findAll(userId: string) {
    return this.prisma.trip.findMany({
      where: {
        deletedAt: null,
        OR: [
          { userId },
          { members: { some: { userId } } },
        ],
      },
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
            id: true,
            name: true,
            nameEn: true,
            coverImage: true,
            province: true,
            region: true,
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

    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }

    const isMember = trip.members.some((m) => m.userId === userId);
    if (trip.userId !== userId && !isMember) {
      throw new ForbiddenException('Bạn không có quyền xem chuyến đi này');
    }

    return trip;
  }

  // PUT /trips/:id
  async update(id: string, userId: string, data: UpdateTripDto) {
    const trip = await this.prisma.trip.findFirst({
      where: { id, deletedAt: null },
    });

    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }

    if (trip.userId !== userId) {
      throw new ForbiddenException('Bạn không có quyền chỉnh sửa chuyến đi này');
    }

    const newStart = data.startDate ? new Date(data.startDate) : trip.startDate;
    const newEnd = data.endDate ? new Date(data.endDate) : trip.endDate;
    if (newStart && newEnd && newEnd < newStart) {
      throw new BadRequestException('Ngày kết thúc phải sau ngày bắt đầu');
    }

    if (data.totalBudget !== undefined && data.totalBudget < 0) {
      throw new BadRequestException('Ngân sách không được nhỏ hơn 0');
    }

    if (data.destinationId) {
      const dest = await this.prisma.destination.findUnique({
        where: { id: data.destinationId },
      });
      if (!dest) {
        throw new NotFoundException('Điểm đến không tồn tại');
      }
    }

    const updateData: any = {};
    if (data.title) updateData.title = data.title.trim();
    if (data.description !== undefined) updateData.description = data.description?.trim();
    if (data.startDate) updateData.startDate = new Date(data.startDate);
    if (data.endDate) updateData.endDate = new Date(data.endDate);
    if (data.totalBudget !== undefined) updateData.totalBudget = data.totalBudget;
    if (data.currency) updateData.currency = data.currency;
    if (data.travelStyle) updateData.travelStyle = data.travelStyle;
    if (data.interests) updateData.interests = data.interests;
    if (data.status) updateData.status = data.status;
    if (data.destinationId) updateData.destinationId = data.destinationId;

    return this.prisma.trip.update({
      where: { id },
      data: updateData,
      include: {
        destination: { select: { id: true, name: true, coverImage: true, province: true } },
      },
    });
  }

  // DELETE /trips/:id
  async delete(id: string, userId: string) {
    const trip = await this.prisma.trip.findFirst({
      where: { id, deletedAt: null },
    });

    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }

    if (trip.userId !== userId) {
      throw new ForbiddenException('Bạn không có quyền xóa chuyến đi này');
    }

    await this.prisma.trip.update({
      where: { id },
      data: { deletedAt: new Date() },
    });

    return { message: 'Đã xóa chuyến đi thành công' };
  }

  // POST /trips/:id/itinerary — thêm hoạt động
  async addItineraryItem(tripId: string, userId: string, data: AddItineraryDto) {
    await this.findById(tripId, userId); // Authorization check

    // Upsert itinerary for dayNumber
    const itinerary = await this.prisma.itinerary.upsert({
      where: { tripId_dayNumber: { tripId, dayNumber: data.dayNumber } },
      create: { tripId, dayNumber: data.dayNumber },
      update: {},
    });

    // Calculate orderIndex
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
        activity: data.activity.trim(),
        notes: data.notes?.trim(),
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
    if (!item) {
      throw new NotFoundException('Hoạt động không tồn tại trong lịch trình');
    }

    await this.prisma.itineraryItem.delete({ where: { id: itemId } });
    return { message: 'Đã xóa hoạt động khỏi lịch trình' };
  }

  // POST /trips/:id/members
  async addMember(tripId: string, ownerId: string, memberEmail: string) {
    const trip = await this.prisma.trip.findFirst({
      where: { id: tripId, userId: ownerId, deletedAt: null },
    });
    if (!trip) {
      throw new ForbiddenException('Chỉ chủ chuyến đi mới có thể mời thành viên');
    }

    const user = await this.prisma.user.findUnique({ where: { email: memberEmail } });
    if (!user) {
      throw new NotFoundException(`Không tìm thấy user: ${memberEmail}`);
    }

    try {
      return await this.prisma.tripMember.create({
        data: { tripId, userId: user.id, role: 'member' },
        include: {
          user: {
            select: {
              id: true,
              email: true,
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
