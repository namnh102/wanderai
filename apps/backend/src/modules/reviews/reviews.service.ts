import {
  Injectable,
  NotFoundException,
  BadRequestException,
  ForbiddenException,
} from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class ReviewsService {
  constructor(private prisma: PrismaService) {}

  private async _findVerifiedPlaceOrThrow(placeId: string) {
    const place = await this.prisma.place.findUnique({
      where: { id: placeId },
      select: {
        id: true,
        deletedAt: true,
        placeSources: { select: { id: true }, take: 1 },
      },
    });
    if (!place || place.deletedAt || place.placeSources.length === 0) {
      throw new NotFoundException(`Place ${placeId} không tồn tại`);
    }
    return place;
  }

  // GET /reviews?placeId=...&page=1&limit=20
  async findByPlace(placeId: string, page = 1, limit = 20) {
    const safePage = Math.max(1, page);
    const safeLimit = Math.min(Math.max(1, limit), 100);
    const skip = (safePage - 1) * safeLimit;

    await this._findVerifiedPlaceOrThrow(placeId);

    const where = { placeId, deletedAt: null, trusted: true };
    const [items, total] = await Promise.all([
      this.prisma.review.findMany({
        where,
        skip,
        take: safeLimit,
        orderBy: { createdAt: 'desc' },
        include: {
          user: {
            select: {
              id: true,
              profile: { select: { displayName: true, avatar: true } },
            },
          },
          aspects: true,
        },
      }),
      this.prisma.review.count({ where }),
    ]);

    return {
      items,
      total,
      page: safePage,
      limit: safeLimit,
      totalPages: Math.ceil(total / safeLimit),
    };
  }

  // POST /reviews
  async create(
    userId: string,
    data: {
      placeId: string;
      rating: number;
      content: string;
      visitDate?: string;
      images?: string[];
    },
  ) {
    if (data.rating < 1 || data.rating > 5) {
      throw new BadRequestException('Rating phải từ 1 đến 5');
    }

    await this._findVerifiedPlaceOrThrow(data.placeId);

    let parsedVisitDate: Date | undefined;
    if (data.visitDate) {
      const dt = new Date(data.visitDate);
      if (Number.isNaN(dt.getTime())) {
        throw new BadRequestException('visitDate không hợp lệ');
      }
      parsedVisitDate = dt;
    }

    const review = await this.prisma.review.create({
      data: {
        userId,
        placeId: data.placeId,
        rating: data.rating,
        content: data.content.trim(),
        visitDate: parsedVisitDate,
        images: data.images ?? [],
        source: 'user',
        trusted: true,
      },
      include: {
        user: {
          select: {
            id: true,
            profile: { select: { displayName: true, avatar: true } },
          },
        },
        aspects: true,
      },
    });

    await this._updatePlaceRating(data.placeId);

    return review;
  }

  // GET /reviews/:id
  async findById(id: string) {
    const review = await this.prisma.review.findUnique({
      where: { id },
      include: {
        user: {
          select: {
            id: true,
            profile: { select: { displayName: true, avatar: true } },
          },
        },
        aspects: true,
      },
    });
    if (!review || review.deletedAt || !review.trusted) {
      throw new NotFoundException('Review không tồn tại');
    }
    return review;
  }

  // GET /reviews/my — reviews của user hiện tại
  async findMyReviews(userId: string, page = 1, limit = 20) {
    const safePage = Math.max(1, page);
    const safeLimit = Math.min(Math.max(1, limit), 100);
    const skip = (safePage - 1) * safeLimit;
    const where = { userId, deletedAt: null, trusted: true };
    const [items, total] = await Promise.all([
      this.prisma.review.findMany({
        where,
        skip,
        take: safeLimit,
        orderBy: { createdAt: 'desc' },
        include: {
          place: { select: { id: true, name: true, coverImage: true } },
          aspects: true,
        },
      }),
      this.prisma.review.count({ where }),
    ]);
    return { items, total, page: safePage, limit: safeLimit, totalPages: Math.ceil(total / safeLimit) };
  }

  // DELETE /reviews/:id (chỉ xóa của chính mình — soft delete)
  async delete(id: string, userId: string) {
    const review = await this.prisma.review.findUnique({ where: { id } });
    if (!review || review.deletedAt) {
      throw new NotFoundException('Review không tồn tại');
    }
    if (review.userId !== userId) {
      throw new ForbiddenException('Bạn không có quyền xóa review này');
    }

    await this.prisma.review.update({
      where: { id },
      data: { deletedAt: new Date() },
    });

    await this._updatePlaceRating(review.placeId);

    return { message: 'Đã xóa review thành công' };
  }

  // Helper: chỉ tính rating trên các review trusted & chưa bị xóa;
  // trả NULL (không bao giờ 0) khi chưa có review tin cậy nào.
  private async _updatePlaceRating(placeId: string) {
    const result = await this.prisma.review.aggregate({
      where: { placeId, deletedAt: null, trusted: true },
      _avg: { rating: true },
      _count: { id: true },
    });

    await this.prisma.place.update({
      where: { id: placeId },
      data: {
        rating: result._count.id > 0 ? result._avg.rating : null,
        reviewCount: result._count.id,
      },
    });
  }
}
