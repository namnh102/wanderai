import {
  Injectable,
  Logger,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
} from '@nestjs/common';
import { randomUUID } from 'crypto';
import { performance } from 'perf_hooks';
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
import {
  attachVerifiedProvenanceNote,
  classifyPreviewItemCostProvenance,
  classifySavedItemCostProvenance,
  CostProvenanceBreakdown,
  formatCostProvenanceSummaryVi,
  parseTravelerAudienceContext,
  PlaceProvenanceSourceRow,
} from './c4-cost-provenance.util';

const UUID_LIKE_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

@Injectable()
export class TripsService {
  private readonly logger = new Logger(TripsService.name);

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

    const itinerariesList = Array.isArray(trip.itineraries)
      ? trip.itineraries
      : null;
    const totalSavedItems = itinerariesList
      ? itinerariesList.reduce(
          (acc, d) => acc + (Array.isArray(d.items) ? d.items.length : 0),
          0,
        )
      : 0;

    if (!itinerariesList || totalSavedItems === 0) {
      return trip;
    }

    const savedPlaceIds = Array.from(
      new Set(
        itinerariesList
          .flatMap((d) => d.items ?? [])
          .map((i) => i.placeId)
          .filter(
            (pid): pid is string =>
              typeof pid === 'string' && pid.trim().length > 0,
          ),
      ),
    );
    const sourcesByPlaceId = new Map<string, PlaceProvenanceSourceRow[]>();
    if (savedPlaceIds.length > 0) {
      const placeRows = await this.prisma.place.findMany({
        where: { id: { in: savedPlaceIds }, deletedAt: null },
        select: {
          id: true,
          placeSources: { select: { sourceName: true, rawData: true } },
        },
      });
      if (Array.isArray(placeRows)) {
        for (const p of placeRows) {
          sourcesByPlaceId.set(
            p.id,
            Array.isArray((p as any).placeSources)
              ? ((p as any).placeSources as PlaceProvenanceSourceRow[])
              : [],
          );
        }
      }
    }

    let verifiedPlaceCostTotal = 0;
    let verifiedPlaceCostItemCount = 0;
    let verifiedFreeItemCount = 0;
    let unverifiedAiEstimatedCostTotal = 0;
    let unverifiedAiEstimatedItemCount = 0;
    let unknownCostItemCount = 0;
    let knownCostTotal = 0;

    const enrichedItineraries = itinerariesList.map((day) => {
      const chargedGroups = new Set<string>();
      const enrichedItems = (day.items ?? []).map((item) => {
        const classified = classifySavedItemCostProvenance({
          estimatedCost: item.estimatedCost,
          placeId: item.placeId,
          notes: item.notes,
          placeSources: item.placeId
            ? (sourcesByPlaceId.get(item.placeId) ?? [])
            : null,
          chargedTicketGroupsInDay: chargedGroups,
        });
        if (classified.costStatus === 'UNKNOWN') {
          unknownCostItemCount += 1;
        } else {
          const numericCost = Math.max(0, Math.trunc(item.estimatedCost ?? 0));
          knownCostTotal += numericCost;
          if (classified.costStatus === 'VERIFIED') {
            verifiedPlaceCostTotal += numericCost;
            verifiedPlaceCostItemCount += 1;
            if (classified.isVerifiedFree) {
              verifiedFreeItemCount += 1;
            }
          } else {
            unverifiedAiEstimatedCostTotal += numericCost;
            unverifiedAiEstimatedItemCount += 1;
          }
        }
        return {
          ...item,
          costStatus: classified.costStatus,
          costBadgeVi: classified.costBadgeVi,
          isVerifiedFree: classified.isVerifiedFree,
          costSourceVerified: classified.costSourceVerified,
          verifiedSourceUrl: classified.verifiedSourceUrl,
        };
      });
      return {
        ...day,
        items: enrichedItems,
      };
    });

    const savedBreakdown: CostProvenanceBreakdown = {
      verifiedPlaceCostTotal,
      verifiedPlaceCostItemCount,
      verifiedFreeItemCount,
      unverifiedAiEstimatedCostTotal,
      unverifiedAiEstimatedItemCount,
      unknownCostItemCount,
    };
    const isOverBudget =
      typeof trip.totalBudget === 'number' &&
      trip.totalBudget > 0 &&
      knownCostTotal > trip.totalBudget;

    return {
      ...trip,
      itineraries: enrichedItineraries,
      costProvenanceBreakdown: savedBreakdown,
      costSummaryText: formatCostProvenanceSummaryVi(savedBreakdown, {
        totalBudget: trip.totalBudget,
        isOverBudget,
        knownCostTotal,
      }),
    };
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
    destinationName?: string | null,
  ): Promise<{
    byId: Map<string, VerifiedPlaceConstraintInfo>;
    unambiguousByName: Map<string, VerifiedPlaceConstraintInfo>;
    placeSourcesById: Map<string, PlaceProvenanceSourceRow[]>;
  }> {
    const byId = new Map<string, VerifiedPlaceConstraintInfo>();
    const unambiguousByName = new Map<string, VerifiedPlaceConstraintInfo>();
    const placeSourcesById = new Map<string, PlaceProvenanceSourceRow[]>();

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
        select: {
          id: true,
          name: true,
          nameEn: true,
          openingHours: true,
          placeSources: { select: { sourceName: true, rawData: true } },
        },
      });
      for (const p of explicitPlaces ?? []) {
        byId.set(p.id, {
          id: p.id,
          name: p.name ?? p.id,
          nameEn: p.nameEn ?? null,
          openingHours: p.openingHours ?? null,
        });
        placeSourcesById.set(
          p.id,
          Array.isArray((p as any).placeSources)
            ? ((p as any).placeSources as PlaceProvenanceSourceRow[])
            : [],
        );
      }
    }

    if (destinationId && hasNamedItems) {
      const destPlaces = await this.prisma.place.findMany({
        where: {
          destinationId,
          deletedAt: null,
          placeSources: { some: {} },
        },
        select: {
          id: true,
          name: true,
          nameEn: true,
          openingHours: true,
          placeSources: { select: { sourceName: true, rawData: true } },
        },
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
        placeSourcesById.set(
          p.id,
          Array.isArray((p as any).placeSources)
            ? ((p as any).placeSources as PlaceProvenanceSourceRow[])
            : [],
        );
        pushKey(p.name, info);
        pushKey(p.nameEn, info);
        if (p.name && destinationName && destinationName.trim().length > 0) {
          pushKey(`${p.name} ${destinationName.trim()}`, info);
        }
      }

      for (const [normKey, list] of buckets.entries()) {
        if (list.length === 1) {
          unambiguousByName.set(normKey, list[0]);
        }
      }
    }

    return { byId, unambiguousByName, placeSourcesById };
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

  private readonly _bulkSaveInFlight = new Map<string, Promise<any>>();
  private readonly _bulkSaveRecent = new Map<
    string,
    { expiresAt: number; result: any }
  >();

  private _formatDotVnd(amount: number): string {
    return Math.max(0, Math.trunc(amount))
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  private _extractPromptConstraints(rawPrompt?: string): {
    partySize?: number;
    partyDescription?: string;
    timeWindowStart?: string;
    timeWindowEnd?: string;
    budget?: number;
    interests: string[];
  } {
    const out: {
      partySize?: number;
      partyDescription?: string;
      timeWindowStart?: string;
      timeWindowEnd?: string;
      budget?: number;
      interests: string[];
    } = { interests: [] };
    if (!rawPrompt || !rawPrompt.trim()) return out;

    const lower = rawPrompt.trim().toLowerCase();
    const wordMap: Record<string, number> = {
      một: 1,
      mot: 1,
      hai: 2,
      ba: 3,
      bốn: 4,
      bon: 4,
      tư: 4,
      năm: 5,
      nam: 5,
      sáu: 6,
      sau: 6,
      bảy: 7,
      tám: 8,
      chín: 9,
      mười: 10,
    };

    const numParty = lower.match(
      /\b(\d{1,2})\s*(người\s*cao\s*tuổi|người\s*lớn|sinh\s*viên|học\s*viên|học\s*sinh|trẻ\s*em|người|khách|bạn)\b/,
    );
    if (numParty) {
      out.partySize = Number(numParty[1]);
      out.partyDescription = `${out.partySize} ${numParty[2].replace(/\s+/g, ' ').trim()}`;
    } else {
      for (const [w, n] of Object.entries(wordMap)) {
        const re = new RegExp(
          `\\b${w}\\s+(người\\s*cao\\s*tuổi|người\\s*lớn|sinh\\s*viên|học\\s*viên|học\\s*sinh|trẻ\\s*em|người|khách)\\b`,
          'i',
        );
        const m = lower.match(re);
        if (m) {
          out.partySize = n;
          out.partyDescription = `${n} ${m[1].replace(/\s+/g, ' ').trim()}`;
          break;
        }
      }
    }

    const timeMatch = lower.match(
      /từ\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?\s*(?:đến|tới|-)\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?/,
    );
    if (timeMatch) {
      const sh = Number(timeMatch[1]);
      const sm = Number(timeMatch[2] || 0);
      const eh = Number(timeMatch[3]);
      const em = Number(timeMatch[4] || 0);
      if (sh >= 0 && sh <= 23 && sm >= 0 && sm <= 59 && eh >= 0 && eh <= 23 && em >= 0 && em <= 59) {
        out.timeWindowStart = `${String(sh).padStart(2, '0')}:${String(sm).padStart(2, '0')}`;
        out.timeWindowEnd = `${String(eh).padStart(2, '0')}:${String(em).padStart(2, '0')}`;
      }
    }

    const mTrieu = lower.match(/(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b/);
    const mVnd = lower.match(/(\d{1,3}(?:[.,]\d{3})+|\d{5,9})\s*(?:đồng|vnd|vnđ|đ)\b/);
    const mK = lower.match(/\b(\d{2,5})\s*k\b/);
    if (mTrieu) {
      out.budget = Math.round(Number(mTrieu[1].replace(',', '.')) * 1_000_000);
    } else if (mVnd) {
      const digits = mVnd[1].replace(/[^\d]/g, '');
      if (digits) out.budget = Number(digits);
    } else if (mK) {
      out.budget = Number(mK[1]) * 1000;
    }

    const interestPairs: Array<[string[], string]> = [
      [['bảo tàng', 'museum'], 'museum'],
      [['văn hóa', 'lịch sử', 'di tích', 'chùa', 'đền'], 'culture'],
      [['biển', 'bãi tắm', 'đảo'], 'beach'],
      [['ẩm thực', 'ăn uống', 'quán ăn', 'đặc sản'], 'food'],
      [['thiên nhiên', 'núi', 'hang động', 'vịnh'], 'nature'],
      [['chụp ảnh', 'check-in', 'sống ảo'], 'photography'],
      [['chợ', 'mua sắm'], 'shopping'],
    ];
    for (const [kws, tag] of interestPairs) {
      if (kws.some((kw) => lower.includes(kw)) && !out.interests.includes(tag)) {
        out.interests.push(tag);
      }
    }
    return out;
  }

  // POST /trips/:id/ai-plan — Tạo bản xem trước lịch trình AI (chưa lưu DB)
  async planTripWithAi(
    tripId: string,
    userId: string,
    customOptions?: PlanTripDto,
    requestId?: string,
  ) {
    const effectiveRequestId =
      requestId && requestId.trim().length > 0 ? requestId.trim() : randomUUID();
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

    const extracted = this._extractPromptConstraints(customOptions?.additionalPrompt);
    const effectivePartySize = customOptions?.partySize ?? extracted.partySize;
    const effectivePartyDescription =
      customOptions?.partyDescription?.trim() ||
      extracted.partyDescription ||
      (effectivePartySize ? `${effectivePartySize} người` : undefined);
    const effectiveTimeStart =
      customOptions?.timeWindowStart?.trim() || extracted.timeWindowStart;
    const effectiveTimeEnd =
      customOptions?.timeWindowEnd?.trim() || extracted.timeWindowEnd;
    const effectiveBudget =
      customOptions?.budgetOverride ?? extracted.budget ?? trip.totalBudget ?? undefined;
    const effectiveInterests = Array.from(
      new Set([
        ...(trip.interests ?? []),
        ...(customOptions?.interestsOverride ?? []),
        ...extracted.interests,
      ]),
    );

    const structuredNotesParts: string[] = [];
    if (effectivePartyDescription) {
      structuredNotesParts.push(`Số người: ${effectivePartyDescription}`);
    }
    if (effectiveTimeStart && effectiveTimeEnd) {
      structuredNotesParts.push(
        `Khung giờ bắt buộc trong ngày: ${effectiveTimeStart} - ${effectiveTimeEnd}`,
      );
    }
    if (typeof effectiveBudget === 'number' && effectiveBudget > 0) {
      structuredNotesParts.push(
        `Tổng ngân sách mục tiêu: ${this._formatDotVnd(effectiveBudget)} ${trip.currency || 'VND'}`,
      );
    }
    if (customOptions?.additionalPrompt?.trim()) {
      structuredNotesParts.push(
        `Yêu cầu gốc từ người dùng: ${customOptions.additionalPrompt.trim()}`,
      );
    }
    const mergedNotes =
      structuredNotesParts.length > 0
        ? structuredNotesParts.join(' | ')
        : customOptions?.additionalPrompt;

    const context = {
      requestId: effectiveRequestId,
      tripId: trip.id,
      destination: destinationName,
      days,
      startDate: trip.startDate ? trip.startDate.toISOString().split('T')[0] : undefined,
      endDate: trip.endDate ? trip.endDate.toISOString().split('T')[0] : undefined,
      budget: effectiveBudget,
      currency: trip.currency || 'VND',
      travelStyle: trip.travelStyle ? trip.travelStyle.toLowerCase() : undefined,
      interests: effectiveInterests,
      notes: mergedNotes,
    };

    const tAiCallStart = performance.now();
    const aiResult = await this.aiProxyService.planWithTripContext(context);
    const nestjsAiCallTotalMs =
      Math.round((performance.now() - tAiCallStart) * 100) / 100;

    const tPostAiStart = performance.now();
    const rawDays = Array.isArray(aiResult?.days) ? aiResult.days : [];
    const tPlaceResStart = performance.now();
    const {
      byId: placesById,
      unambiguousByName,
      placeSourcesById,
    } = await this._resolveVerifiedPlacesForPreview(
      trip.destinationId,
      rawDays,
      destinationName,
    );
    const nestjsPlaceResolutionMs =
      Math.round((performance.now() - tPlaceResStart) * 100) / 100;

    const audienceContext = parseTravelerAudienceContext({
      partySize: effectivePartySize ?? null,
      partyDescription: customOptions?.partyDescription ?? extracted.partyDescription ?? null,
      rawPrompt: customOptions?.additionalPrompt ?? null,
    });

    // Deterministic cost & schedule validation without coercing null/missing prices to 0
    let knownCostTotal = 0;
    let verifiedPlaceCostTotal = 0;
    let unverifiedAiEstimatedCostTotal = 0;
    let verifiedPlaceCostItemCount = 0;
    let verifiedFreeItemCount = 0;
    let unverifiedAiEstimatedItemCount = 0;
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
      const chargedTicketGroupsInDay = new Set<string>();

      const items = (Array.isArray(day?.items) ? day.items : []).map(
        (item: any, itemIdx: number) => {
          totalItemsCount += 1;
          const rawCost =
            item?.estimated_cost !== undefined
              ? item.estimated_cost
              : item?.estimatedCost;
          let estimatedCost: number | null = null;
          if (typeof rawCost === 'number' && Number.isFinite(rawCost)) {
            estimatedCost = Math.max(0, Math.trunc(rawCost));
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

          const classified = classifyPreviewItemCostProvenance({
            estimatedCost,
            resolvedPlaceId,
            placeSources: resolvedPlaceId
              ? (placeSourcesById.get(resolvedPlaceId) ?? [])
              : null,
            audienceContext,
            chargedTicketGroupsInDay,
          });

          if (classified.costStatus === 'VERIFIED' && estimatedCost !== null) {
            verifiedPlaceCostTotal += estimatedCost;
            verifiedPlaceCostItemCount += 1;
            if (classified.isVerifiedFree) {
              verifiedFreeItemCount += 1;
            }
          } else if (
            classified.costStatus === 'ESTIMATED' &&
            estimatedCost !== null
          ) {
            unverifiedAiEstimatedCostTotal += estimatedCost;
            unverifiedAiEstimatedItemCount += 1;
          }

          const effectiveNotes = attachVerifiedProvenanceNote(
            item?.notes,
            classified.provenanceNoteTag,
          );

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
            notes: effectiveNotes,
            estimatedCost,
            costStatus: classified.costStatus,
            costBadgeVi: classified.costBadgeVi,
            isVerifiedFree: classified.isVerifiedFree,
            costSourceVerified: classified.costSourceVerified,
            verifiedSourceUrl: classified.verifiedSourceUrl,
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

    const tEvalStart = performance.now();
    const constraintEval = evaluateItineraryDays(
      intermediateDays,
      placesById,
      trip.startDate,
    );
    const nestjsConstraintEvalMs =
      Math.round((performance.now() - tEvalStart) * 100) / 100;

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

    const resolvedTotalBudget = effectiveBudget ?? null;
    const hasBudget =
      typeof resolvedTotalBudget === 'number' && resolvedTotalBudget > 0;
    const isOverBudget = hasBudget ? knownCostTotal > resolvedTotalBudget : false;
    const hasSufficientBudgetBasis = hasBudget && totalUnknownCostItems === 0;
    const variance = hasBudget
      ? isOverBudget || hasSufficientBudgetBasis
        ? resolvedTotalBudget - knownCostTotal
        : null
      : totalUnknownCostItems === 0
        ? 0
        : null;

    const costProvenanceBreakdown: CostProvenanceBreakdown = {
      verifiedPlaceCostTotal,
      verifiedPlaceCostItemCount,
      verifiedFreeItemCount,
      unverifiedAiEstimatedCostTotal,
      unverifiedAiEstimatedItemCount,
      unknownCostItemCount: totalUnknownCostItems,
    };

    const budgetSummaryText = formatCostProvenanceSummaryVi(
      costProvenanceBreakdown,
      {
        totalBudget: resolvedTotalBudget,
        isOverBudget,
        knownCostTotal,
      },
    );

    const nestjsPostAiScheduleValidationMs =
      Math.round((performance.now() - tPostAiStart) * 100) / 100;

    const upstreamTiming = aiResult?.timing_telemetry;
    const fastapiPostAiMs =
      typeof upstreamTiming?.post_ai_schedule_validation_ms === 'number'
        ? upstreamTiming.post_ai_schedule_validation_ms
        : 0;
    const timingTelemetry = {
      requestId: upstreamTiming?.request_id || effectiveRequestId,
      nestjsAiCallTotalMs,
      fastapiTotalMs:
        typeof upstreamTiming?.fastapi_total_ms === 'number'
          ? upstreamTiming.fastapi_total_ms
          : null,
      fastapiRagRetrievalMs:
        typeof upstreamTiming?.rag_retrieval_ms === 'number'
          ? upstreamTiming.rag_retrieval_ms
          : 0,
      modelAttempts: Array.isArray(upstreamTiming?.model_attempts)
        ? upstreamTiming.model_attempts.map((a: any) => ({
            attempt: a.attempt,
            startedOffsetMs: a.started_offset_ms,
            durationMs: a.duration_ms,
            status: a.status,
            errorCode: a.error_code ?? null,
          }))
        : [],
      modelTotalMs:
        typeof upstreamTiming?.model_total_ms === 'number'
          ? upstreamTiming.model_total_ms
          : null,
      retryCount:
        typeof upstreamTiming?.retry_count === 'number'
          ? upstreamTiming.retry_count
          : 0,
      retryWaitMs:
        typeof upstreamTiming?.retry_wait_ms === 'number'
          ? upstreamTiming.retry_wait_ms
          : 0,
      fastapiPostAiScheduleValidationMs: fastapiPostAiMs,
      nestjsPlaceResolutionMs,
      nestjsConstraintEvalMs,
      nestjsPostAiScheduleValidationMs,
      totalPostAiScheduleValidationMs:
        Math.round((fastapiPostAiMs + nestjsPostAiScheduleValidationMs) * 100) / 100,
    };

    this.logger.log(`[C4_PREVIEW_TIMING] ${JSON.stringify(timingTelemetry)}`);

    return {
      requestId: timingTelemetry.requestId,
      tripId: trip.id,
      destination: destinationName,
      totalDays: processedDays.length,
      overview: aiResult.overview || `Lịch trình khám phá ${destinationName}`,
      bestTimeToVisit: aiResult.best_time_to_visit || 'Quanh năm',
      generalTips: aiResult.general_tips || [],
      preservedContext: {
        partySize: effectivePartySize ?? null,
        partyDescription: effectivePartyDescription ?? null,
        timeWindowStart: effectiveTimeStart ?? null,
        timeWindowEnd: effectiveTimeEnd ?? null,
        totalBudget: resolvedTotalBudget,
        interests: effectiveInterests,
      },
      budgetAnalysis: {
        totalBudget: resolvedTotalBudget,
        estimatedCost: knownCostTotal,
        knownCostTotal,
        unknownCostItemCount: totalUnknownCostItems,
        costStatus,
        hasSufficientBudgetBasis,
        currency: trip.currency,
        isOverBudget,
        variance,
        summaryText: budgetSummaryText,
        costProvenanceBreakdown,
      },
      timingTelemetry,
      scheduleViolations: constraintEval.violations,
      hasScheduleViolations: constraintEval.violations.length > 0,
      canApply: constraintEval.violations.length === 0,
      days: processedDays,
    };
  }

  // POST /trips/:id/itinerary/bulk — Lưu toàn bộ lịch trình vào DB (atomic transaction + idempotent double-tap guard)
  async bulkSaveItinerary(
    tripId: string,
    userId: string,
    dto: BulkItineraryDto,
    idempotencyKey?: string,
  ) {
    const rawKey = dto.clientRequestId?.trim() || idempotencyKey?.trim();
    const dedupeKey =
      rawKey && rawKey.length > 0 ? `${userId}:${tripId}:${rawKey.slice(0, 128)}` : null;

    const nowMs = Date.now();
    for (const [k, v] of this._bulkSaveRecent.entries()) {
      if (v.expiresAt <= nowMs) this._bulkSaveRecent.delete(k);
    }

    if (dedupeKey) {
      const cached = this._bulkSaveRecent.get(dedupeKey);
      if (cached && cached.expiresAt > nowMs) {
        return cached.result;
      }
      const inFlight = this._bulkSaveInFlight.get(dedupeKey);
      if (inFlight) {
        return inFlight;
      }
    }

    const execPromise = this._executeBulkSaveItinerary(tripId, userId, dto).then(
      (res) => {
        if (dedupeKey) {
          this._bulkSaveRecent.set(dedupeKey, {
            expiresAt: Date.now() + 60_000,
            result: res,
          });
        }
        return res;
      },
    );

    if (dedupeKey) {
      this._bulkSaveInFlight.set(dedupeKey, execPromise);
    }

    try {
      return await execPromise;
    } finally {
      if (dedupeKey) {
        this._bulkSaveInFlight.delete(dedupeKey);
      }
    }
  }

  private async _executeBulkSaveItinerary(
    tripId: string,
    userId: string,
    dto: BulkItineraryDto,
  ) {
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
      // Row-level lock on PostgreSQL serializes concurrent replaceExisting calls so double-taps never duplicate items
      if (
        (this.prisma as { constructor?: { name?: string } }).constructor?.name !==
          'InMemoryPrismaService' &&
        typeof (tx as { $queryRawUnsafe?: unknown }).$queryRawUnsafe === 'function'
      ) {
        await (
          tx as { $queryRawUnsafe: (sql: string, ...params: unknown[]) => Promise<unknown> }
        ).$queryRawUnsafe(
          'SELECT id FROM trips WHERE id = $1::uuid FOR UPDATE',
          tripId,
        );
      }

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
