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
import { ReorderItineraryDto } from './dto/reorder-itinerary.dto';
import { PlanTripDto } from './dto/plan-trip.dto';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';
import {
  evaluateItineraryDays,
  VerifiedPlaceConstraintInfo,
} from './itinerary-constraints.util';

const UUID_LIKE_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
      if (!dest || dest.deletedAt) {
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
      if (!dest || dest.deletedAt) {
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

  private async _assertVerifiedPlaces(
    placeIds: Array<string | undefined | null>,
  ): Promise<Map<string, VerifiedPlaceConstraintInfo>> {
    const uniqueIds = Array.from(
      new Set(
        placeIds
          .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
          .map((id) => id.trim()),
      ),
    );
    const byId = new Map<string, VerifiedPlaceConstraintInfo>();
    if (uniqueIds.length === 0) {
      return byId;
    }

    const found = await this.prisma.place.findMany({
      where: {
        id: { in: uniqueIds },
        deletedAt: null,
        placeSources: { some: {} },
      },
      select: { id: true, name: true, nameEn: true, openingHours: true },
    });
    for (const p of found) {
      byId.set(p.id, {
        id: p.id,
        name: p.name ?? p.id,
        nameEn: p.nameEn ?? null,
        openingHours: p.openingHours ?? null,
      });
    }
    const missingId = uniqueIds.find((id) => !byId.has(id));
    if (missingId) {
      throw new NotFoundException({
        message: `Place with ID "${missingId}" not found`,
        errorCode: 'PLACE_NOT_FOUND',
      });
    }
    return byId;
  }

  private async _resolveVerifiedPlacesForPreview(
    destinationId: string | null | undefined,
    rawDays: any[],
  ): Promise<{
    byId: Map<string, VerifiedPlaceConstraintInfo>;
    unambiguousByName: Map<string, VerifiedPlaceConstraintInfo>;
  }> {
    const byId = new Map<string, VerifiedPlaceConstraintInfo>();
    const unambiguousByName = new Map<string, VerifiedPlaceConstraintInfo>();

    const explicitIds = new Set<string>();
    let hasNamedItems = false;
    for (const day of rawDays) {
      for (const item of day?.items ?? []) {
        const rawId = item?.place_id ?? item?.placeId;
        if (typeof rawId === 'string' && UUID_LIKE_RE.test(rawId.trim())) {
          explicitIds.add(rawId.trim());
        }
        const rawName = item?.place_name ?? item?.placeName;
        if (typeof rawName === 'string' && rawName.trim().length > 0) {
          hasNamedItems = true;
        }
      }
    }

    if (explicitIds.size > 0) {
      const explicitPlaces = await this.prisma.place.findMany({
        where: {
          id: { in: Array.from(explicitIds) },
          deletedAt: null,
          placeSources: { some: {} },
        },
        select: { id: true, name: true, nameEn: true, openingHours: true },
      });
      for (const p of explicitPlaces ?? []) {
        byId.set(p.id, {
          id: p.id,
          name: p.name ?? p.id,
          nameEn: p.nameEn ?? null,
          openingHours: p.openingHours ?? null,
        });
      }
    }

    if (destinationId && hasNamedItems) {
      const destPlaces = await this.prisma.place.findMany({
        where: {
          destinationId,
          deletedAt: null,
          placeSources: { some: {} },
        },
        select: { id: true, name: true, nameEn: true, openingHours: true },
      });
      const buckets = new Map<string, VerifiedPlaceConstraintInfo[]>();
      const pushKey = (rawKey: string | null | undefined, info: VerifiedPlaceConstraintInfo) => {
        if (typeof rawKey !== 'string') return;
        const norm = rawKey.trim().toLowerCase();
        if (!norm) return;
        const arr = buckets.get(norm) ?? [];
        if (!arr.some((x) => x.id === info.id)) {
          arr.push(info);
          buckets.set(norm, arr);
        }
      };

      for (const p of destPlaces ?? []) {
        const info: VerifiedPlaceConstraintInfo = {
          id: p.id,
          name: p.name ?? p.id,
          nameEn: p.nameEn ?? null,
          openingHours: p.openingHours ?? null,
        };
        byId.set(p.id, info);
        pushKey(p.name, info);
        pushKey(p.nameEn, info);
      }

      for (const [normKey, list] of buckets.entries()) {
        if (list.length === 1) {
          unambiguousByName.set(normKey, list[0]);
        }
      }
    }

    return { byId, unambiguousByName };
  }

  // POST /trips/:id/itinerary — thêm hoạt động
  async addItineraryItem(
    tripId: string,
    userId: string,
    data: AddItineraryDto,
    idempotencyKey?: string,
  ) {
    await this.findById(tripId, userId); // Authorization check

    if (data.placeId) {
      await this._assertVerifiedPlaces([data.placeId]);
    }

    const rawRequestId = data.clientRequestId?.trim() || idempotencyKey?.trim();
    const effectiveClientRequestId =
      rawRequestId && rawRequestId.length > 0
        ? rawRequestId.slice(0, 128)
        : undefined;

    return this.prisma.$transaction(async (tx) => {
      // Upsert itinerary for dayNumber
      const itinerary = await tx.itinerary.upsert({
        where: { tripId_dayNumber: { tripId, dayNumber: data.dayNumber } },
        create: { tripId, dayNumber: data.dayNumber },
        update: {},
      });

      if (effectiveClientRequestId) {
        const existing = await tx.itineraryItem.findFirst({
          where: {
            itineraryId: itinerary.id,
            clientRequestId: effectiveClientRequestId,
          },
          include: {
            place: { select: { id: true, name: true, address: true } },
          },
        });
        if (existing) {
          return {
            ...existing,
            dayNumber: itinerary.dayNumber,
          };
        }
      }

      // Compute orderIndex from MAX(orderIndex) + 1 to avoid collisions after deletions
      const lastItem = await tx.itineraryItem.findFirst({
        where: { itineraryId: itinerary.id },
        orderBy: { orderIndex: 'desc' },
        select: { orderIndex: true },
      });
      const nextOrderIndex = (lastItem?.orderIndex ?? 0) + 1;

      try {
        const item = await tx.itineraryItem.create({
          data: {
            itineraryId: itinerary.id,
            placeId: data.placeId,
            createdByUserId: userId,
            ...(effectiveClientRequestId
              ? { clientRequestId: effectiveClientRequestId }
              : {}),
            orderIndex: nextOrderIndex,
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

        return {
          ...item,
          dayNumber: itinerary.dayNumber,
        };
      } catch (error) {
        const code =
          typeof error === 'object' && error !== null && 'code' in error
            ? (error as { code?: unknown }).code
            : undefined;
        if (code === 'P2002' && effectiveClientRequestId) {
          const existing = await tx.itineraryItem.findFirst({
            where: {
              itineraryId: itinerary.id,
              clientRequestId: effectiveClientRequestId,
            },
            include: {
              place: { select: { id: true, name: true, address: true } },
            },
          });
          if (existing) {
            return {
              ...existing,
              dayNumber: itinerary.dayNumber,
            };
          }
        }
        throw error;
      }
    });
  }

  // PUT /trips/:id/itinerary/reorder — sắp xếp lại thứ tự hoạt động trong lịch trình (WP-TRIP-01)
  async reorderItineraryItems(
    tripId: string,
    userId: string,
    dto: ReorderItineraryDto,
  ) {
    const trip = await this.prisma.trip.findFirst({
      where: { id: tripId, deletedAt: null },
    });
    if (!trip) {
      throw new NotFoundException('Chuyến đi không tồn tại');
    }
    if (trip.userId !== userId) {
      throw new ForbiddenException('Chỉ chủ chuyến đi mới có quyền sắp xếp lịch trình');
    }
    if (trip.status === TripStatus.CANCELLED) {
      throw new BadRequestException('Chuyến đi đã hủy không thể chỉnh sửa lịch trình');
    }
    if (!dto.items || !Array.isArray(dto.items) || dto.items.length === 0) {
      throw new BadRequestException('Danh sách hoạt động sắp xếp không được để trống');
    }

    const seenItemIds = new Set<string>();
    for (const entry of dto.items) {
      if (seenItemIds.has(entry.itemId)) {
        throw new BadRequestException('Danh sách itemId bị trùng lặp');
      }
      seenItemIds.add(entry.itemId);
    }

    await this.prisma.$transaction(async (tx) => {
      const existingTripItems = await tx.itineraryItem.findMany({
        where: { itinerary: { tripId } },
        select: {
          id: true,
          itineraryId: true,
          itinerary: { select: { dayNumber: true } },
        },
      });

      const existingById = new Map(
        existingTripItems.map((row) => [row.id, row]),
      );

      const submittedByItinerary = new Map<
        string,
        Array<{ itemId: string; orderIndex: number }>
      >();

      for (const entry of dto.items) {
        const existing = existingById.get(entry.itemId);
        if (!existing) {
          throw new NotFoundException('Hoạt động không tồn tại trong lịch trình');
        }
        if (
          dto.dayNumber !== undefined &&
          existing.itinerary.dayNumber !== dto.dayNumber
        ) {
          throw new BadRequestException(
            `Hoạt động "${entry.itemId}" không thuộc ngày ${dto.dayNumber}`,
          );
        }
        const list = submittedByItinerary.get(existing.itineraryId) ?? [];
        list.push(entry);
        submittedByItinerary.set(existing.itineraryId, list);
      }

      for (const [itineraryId, submittedList] of submittedByItinerary.entries()) {
        const totalInDay = existingTripItems.filter(
          (row) => row.itineraryId === itineraryId,
        ).length;
        if (submittedList.length !== totalInDay) {
          throw new BadRequestException(
            'Phải gửi đầy đủ tất cả hoạt động trong ngày khi sắp xếp lại thứ tự',
          );
        }
        const sortedIndices = submittedList
          .map((x) => x.orderIndex)
          .sort((a, b) => a - b);
        for (let idx = 0; idx < sortedIndices.length; idx++) {
          if (sortedIndices[idx] !== idx + 1) {
            throw new BadRequestException(
              'Thứ tự orderIndex trong mỗi ngày phải liên tục từ 1 đến N',
            );
          }
        }
      }

      for (const entry of dto.items) {
        await tx.itineraryItem.update({
          where: { id: entry.itemId },
          data: { orderIndex: entry.orderIndex },
        });
      }
    });

    return this.findById(tripId, userId);
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

    const normalizedEmail = memberEmail.trim().toLowerCase();
    const member = await this.prisma.user.findUnique({
      where: { email: normalizedEmail },
    });
    if (!member || member.deletedAt) {
      throw new NotFoundException(`Không tìm thấy user: ${normalizedEmail}`);
    }

    try {
      return await this.prisma.tripMember.create({
        data: { tripId, userId: member.id, role: 'member' },
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
    const rawDays = Array.isArray(aiResult?.days) ? aiResult.days : [];
    const { byId: placesById, unambiguousByName } =
      await this._resolveVerifiedPlacesForPreview(trip.destinationId, rawDays);

    // Deterministic cost & schedule validation without coercing null/missing prices to 0
    let knownCostTotal = 0;
    let totalUnknownCostItems = 0;
    let totalItemsCount = 0;

    const intermediateDays = rawDays.map((day: any, dayIdx: number) => {
      const dayNumber =
        typeof day?.day_number === 'number'
          ? day.day_number
          : typeof day?.dayNumber === 'number'
            ? day.dayNumber
            : dayIdx + 1;
      let dayCost = 0;
      let dayUnknownCostCount = 0;

      const items = (Array.isArray(day?.items) ? day.items : []).map(
        (item: any, itemIdx: number) => {
          totalItemsCount += 1;
          const rawCost =
            item?.estimated_cost !== undefined
              ? item.estimated_cost
              : item?.estimatedCost;
          let estimatedCost: number | null = null;
          let costStatus: 'KNOWN' | 'UNKNOWN' = 'UNKNOWN';
          if (typeof rawCost === 'number' && Number.isFinite(rawCost)) {
            estimatedCost = Math.max(0, Math.trunc(rawCost));
            costStatus = 'KNOWN';
            dayCost += estimatedCost;
          } else {
            dayUnknownCostCount += 1;
          }

          const rawPlaceId = item?.place_id ?? item?.placeId;
          const rawPlaceName =
            typeof (item?.place_name ?? item?.placeName) === 'string'
              ? (item.place_name ?? item.placeName).trim()
              : undefined;

          let resolvedPlaceId: string | null = null;
          if (typeof rawPlaceId === 'string' && placesById.has(rawPlaceId.trim())) {
            resolvedPlaceId = rawPlaceId.trim();
          } else if (rawPlaceName) {
            const matched = unambiguousByName.get(rawPlaceName.toLowerCase());
            if (matched) {
              resolvedPlaceId = matched.id;
            }
          }

          const startTime =
            typeof (item?.start_time ?? item?.startTime) === 'string' &&
            (item.start_time ?? item.startTime).trim().length > 0
              ? (item.start_time ?? item.startTime).trim()
              : undefined;
          const endTime =
            typeof (item?.end_time ?? item?.endTime) === 'string' &&
            (item.end_time ?? item.endTime).trim().length > 0
              ? (item.end_time ?? item.endTime).trim()
              : undefined;

          return {
            orderIndex: item?.order_index ?? item?.orderIndex ?? itemIdx + 1,
            startTime,
            endTime,
            activity: item?.activity || `Hoạt động ${itemIdx + 1}`,
            placeId: resolvedPlaceId,
            placeName:
              (resolvedPlaceId ? placesById.get(resolvedPlaceId)?.name : undefined) ??
              rawPlaceName,
            notes: item?.notes,
            estimatedCost,
            costStatus,
            transportMode: item?.transport_mode ?? item?.transportMode,
          };
        },
      );

      knownCostTotal += dayCost;
      totalUnknownCostItems += dayUnknownCostCount;

      return {
        dayNumber,
        date: day?.date,
        title: day?.title || `Ngày ${dayNumber}`,
        dayCost,
        unknownCostItemCount: dayUnknownCostCount,
        items,
      };
    });

    const constraintEval = evaluateItineraryDays(
      intermediateDays,
      placesById,
      trip.startDate,
    );

    const processedDays = intermediateDays.map((day) => ({
      ...day,
      items: day.items.map((item: any, itemIdx: number) => {
        const evalRes = constraintEval.perDayItemResults.get(
          `${day.dayNumber}:${itemIdx}`,
        );
        return {
          ...item,
          openingHoursStatus: evalRes?.openingHoursStatus ?? 'UNKNOWN',
          violations: evalRes?.violations ?? [],
        };
      }),
    }));

    const costStatus: 'COMPLETE' | 'PARTIAL_UNKNOWN' | 'ALL_UNKNOWN' =
      totalUnknownCostItems === 0
        ? 'COMPLETE'
        : totalUnknownCostItems === totalItemsCount
          ? 'ALL_UNKNOWN'
          : 'PARTIAL_UNKNOWN';

    const hasBudget =
      typeof trip.totalBudget === 'number' && trip.totalBudget > 0;
    const isOverBudget = hasBudget ? knownCostTotal > trip.totalBudget! : false;
    const hasSufficientBudgetBasis = hasBudget && totalUnknownCostItems === 0;
    const variance = hasBudget
      ? isOverBudget || hasSufficientBudgetBasis
        ? trip.totalBudget! - knownCostTotal
        : null
      : totalUnknownCostItems === 0
        ? 0
        : null;

    return {
      tripId: trip.id,
      destination: destinationName,
      totalDays: processedDays.length,
      overview: aiResult.overview || `Lịch trình khám phá ${destinationName}`,
      bestTimeToVisit: aiResult.best_time_to_visit || 'Quanh năm',
      generalTips: aiResult.general_tips || [],
      budgetAnalysis: {
        totalBudget: trip.totalBudget,
        estimatedCost: knownCostTotal,
        knownCostTotal,
        unknownCostItemCount: totalUnknownCostItems,
        costStatus,
        hasSufficientBudgetBasis,
        currency: trip.currency,
        isOverBudget,
        variance,
      },
      scheduleViolations: constraintEval.violations,
      hasScheduleViolations: constraintEval.violations.length > 0,
      canApply: constraintEval.violations.length === 0,
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

    const seenDayNumbers = new Set<number>();
    const allPlaceIds: Array<string | undefined | null> = [];
    for (const day of dto.days) {
      if (seenDayNumbers.has(day.dayNumber)) {
        throw new BadRequestException(`Ngày ${day.dayNumber} bị trùng lặp trong lịch trình`);
      }
      seenDayNumbers.add(day.dayNumber);
      for (const item of day.items ?? []) {
        if (item.placeId) {
          allPlaceIds.push(item.placeId);
        }
      }
    }

    const verifiedPlacesById = await this._assertVerifiedPlaces(allPlaceIds);

    // Enforce locked Apply schedule & opening-hours constraints BEFORE any DB write/delete
    const constraintEval = evaluateItineraryDays(
      dto.days,
      verifiedPlacesById,
      trip.startDate,
    );
    if (constraintEval.violations.length > 0) {
      throw new BadRequestException({
        message: `Không thể áp dụng lịch trình do có ${constraintEval.violations.length} mục vi phạm thời gian hoặc giờ mở cửa: ${constraintEval.violations.map((v) => v.message).join(' | ')}`,
        errorCode: 'ITINERARY_SCHEDULE_VIOLATION',
        violations: constraintEval.violations,
      });
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
          let existingMaxOrder = 0;
          if (dto.replaceExisting === false) {
            const lastItem = await tx.itineraryItem.findFirst({
              where: { itineraryId: itinerary.id },
              orderBy: { orderIndex: 'desc' },
              select: { orderIndex: true },
            });
            existingMaxOrder = lastItem?.orderIndex ?? 0;
          }

          for (let idx = 0; idx < day.items.length; idx++) {
            const item = day.items[idx];
            const effectiveOrderIndex =
              existingMaxOrder > 0 ? existingMaxOrder + idx + 1 : item.orderIndex;
            await tx.itineraryItem.create({
              data: {
                itineraryId: itinerary.id,
                orderIndex: effectiveOrderIndex,
                activity: item.activity.trim(),
                startTime: item.startTime,
                endTime: item.endTime,
                placeId: item.placeId,
                notes: item.notes?.trim(),
                estimatedCost: item.estimatedCost ?? null,
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
