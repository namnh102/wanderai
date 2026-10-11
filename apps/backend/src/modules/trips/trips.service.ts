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
import { BulkItineraryDto } from './dto/bulk-itinerary.dto';
import { PlanTripDto } from './dto/plan-trip.dto';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';

@Injectable()
export class TripsService {
  constructor(
    private prisma: PrismaService,
    private aiProxyService: AiProxyService,
  ) {}

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

  // POST /trips/:id/ai-plan — Tạo bản xem trước lịch trình AI (chưa lưu DB)
  async planTripWithAi(tripId: string, userId: string, customOptions?: PlanTripDto) {
    const trip = await this.findById(tripId, userId);

    const destinationName = trip.destination?.name || trip.title;
    if (!destinationName || destinationName.trim().length === 0) {
      throw new BadRequestException('Chuyến đi cần có tên hoặc điểm đến để lập lịch trình');
    }

    let days = 3;
    if (trip.startDate && trip.endDate) {
      const diffTime = Math.abs(new Date(trip.endDate).getTime() - new Date(trip.startDate).getTime());
      days = Math.max(1, Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1);
    } else if (trip.itineraries && trip.itineraries.length > 0) {
      days = trip.itineraries.length;
    }
    if (days > 14) days = 14;

    const context = {
      tripId: trip.id,
      destination: destinationName,
      days,
      startDate: trip.startDate ? trip.startDate.toISOString().split('T')[0] : undefined,
      endDate: trip.endDate ? trip.endDate.toISOString().split('T')[0] : undefined,
      budget: trip.totalBudget ?? undefined,
      currency: trip.currency || 'VND',
      travelStyle: trip.travelStyle ? trip.travelStyle.toLowerCase() : undefined,
      interests: trip.interests ?? [],
      notes: customOptions?.additionalPrompt,
    };

    const aiResult = await this.aiProxyService.planWithTripContext(context);

    // Deterministic validation & arithmetic calculation
    let calculatedCost = 0;
    const processedDays = (aiResult.days || []).map((day: any, dayIdx: number) => {
      let dayCost = 0;
      const items = (day.items || []).map((item: any, itemIdx: number) => {
        const cost = typeof item.estimated_cost === 'number' ? Math.max(0, item.estimated_cost) : 0;
        dayCost += cost;
        return {
          orderIndex: item.order_index ?? (itemIdx + 1),
          startTime: item.start_time,
          endTime: item.end_time,
          activity: item.activity || `Hoạt động ${itemIdx + 1}`,
          placeName: item.place_name,
          notes: item.notes,
          estimatedCost: cost,
          transportMode: item.transport_mode,
        };
      });
      calculatedCost += dayCost;
      return {
        dayNumber: day.day_number ?? (dayIdx + 1),
        date: day.date,
        title: day.title || `Ngày ${dayIdx + 1}`,
        dayCost,
        items,
      };
    });

    const isOverBudget = trip.totalBudget ? calculatedCost > trip.totalBudget : false;
    const variance = trip.totalBudget ? trip.totalBudget - calculatedCost : 0;

    return {
      tripId: trip.id,
      destination: destinationName,
      totalDays: processedDays.length,
      overview: aiResult.overview || `Lịch trình khám phá ${destinationName}`,
      bestTimeToVisit: aiResult.best_time_to_visit || 'Quanh năm',
      generalTips: aiResult.general_tips || [],
      budgetAnalysis: {
        totalBudget: trip.totalBudget,
        estimatedCost: calculatedCost,
        currency: trip.currency,
        isOverBudget,
        variance,
      },
      days: processedDays,
    };
  }

  // POST /trips/:id/itinerary/bulk — Lưu toàn bộ lịch trình vào DB (atomic transaction)
  async bulkSaveItinerary(tripId: string, userId: string, dto: BulkItineraryDto) {
    const trip = await this.prisma.trip.findFirst({
      where: { id: tripId, deletedAt: null },
    });
    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }
    if (trip.userId !== userId) {
      throw new ForbiddenException('Chỉ chủ chuyến đi mới có quyền lưu lịch trình');
    }

    if (!dto.days || !Array.isArray(dto.days) || dto.days.length === 0) {
      throw new BadRequestException('Danh sách ngày lịch trình không được để trống');
    }

    await this.prisma.$transaction(async (tx) => {
      if (dto.replaceExisting !== false) {
        // Delete all existing items and itineraries for this trip
        await tx.itineraryItem.deleteMany({
          where: { itinerary: { tripId } },
        });
        await tx.itinerary.deleteMany({
          where: { tripId },
        });
      }

      for (const day of dto.days) {
        const itinerary = await tx.itinerary.upsert({
          where: { tripId_dayNumber: { tripId, dayNumber: day.dayNumber } },
          create: {
            tripId,
            dayNumber: day.dayNumber,
            title: day.title,
            date: day.date ? new Date(day.date) : null,
          },
          update: {
            title: day.title,
            date: day.date ? new Date(day.date) : null,
          },
        });

        if (day.items && day.items.length > 0) {
          for (const item of day.items) {
            await tx.itineraryItem.create({
              data: {
                itineraryId: itinerary.id,
                orderIndex: item.orderIndex,
                activity: item.activity.trim(),
                startTime: item.startTime,
                endTime: item.endTime,
                placeId: item.placeId,
                notes: item.notes?.trim(),
                estimatedCost: item.estimatedCost,
                transportMode: item.transportMode,
              },
            });
          }
        }
      }

      await tx.trip.update({
        where: { id: tripId },
        data: {
          isAiGenerated: true,
          status: TripStatus.PLANNED,
        },
      });
    });

    return this.findById(tripId, userId);
  }
}
