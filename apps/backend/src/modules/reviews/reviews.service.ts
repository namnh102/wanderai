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

  // GET /reviews?placeId=...&page=1&limit=20
  async findByPlace(placeId: string, page = 1, limit = 20) {
    const skip = (page - 1) * limit;

    // Kiểm tra place tồn tại
    const place = await this.prisma.place.findUnique({ where: { id: placeId } });
    if (!place) throw new NotFoundException(`Place ${placeId} không tồn tại`);

    const [items, total] = await Promise.all([
      this.prisma.review.findMany({
        where: { placeId, deletedAt: null },
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: {
          user: {
            select: {
              id: true,
              profile: { select: { displayName: true, avatar: true } },
            },
          },
        },
      }),
      this.prisma.review.count({ where: { placeId, deletedAt: null } }),
    ]);

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
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
    // Validate rating
    if (data.rating < 1 || data.rating > 5) {
      throw new BadRequestException('Rating phải từ 1 đến 5');
    }

    // Kiểm tra place tồn tại
    const place = await this.prisma.place.findUnique({
      where: { id: data.placeId },
    });
    if (!place) throw new NotFoundException(`Place ${data.placeId} không tồn tại`);

    // Tạo review
    const review = await this.prisma.review.create({
      data: {
        userId,
        placeId: data.placeId,
        rating: data.rating,
        content: data.content,
        images: data.images ?? [],
      },
      include: {
        user: {
          select: {
            id: true,
            profile: { select: { displayName: true, avatar: true } },
          },
        },
      },
    });

    // Cập nhật lại rating trung bình của place
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
      },
    });
    if (!review || review.deletedAt) {
      throw new NotFoundException('Review không tồn tại');
    }
    return review;
  }

  // GET /reviews/my — reviews của user hiện tại
  async findMyReviews(userId: string, page = 1, limit = 20) {
    const skip = (page - 1) * limit;
    const [items, total] = await Promise.all([
      this.prisma.review.findMany({
        where: { userId, deletedAt: null },
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: {
          place: { select: { id: true, name: true, coverImage: true } },
        },
      }),
      this.prisma.review.count({ where: { userId, deletedAt: null } }),
    ]);
    return { items, total, page, limit, totalPages: Math.ceil(total / limit) };
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

    // Cập nhật lại rating place
    await this._updatePlaceRating(review.placeId);

    return { message: 'Đã xóa review thành công' };
  }

  // Helper: tính lại rating trung bình của place
  private async _updatePlaceRating(placeId: string) {
    const result = await this.prisma.review.aggregate({
      where: { placeId, deletedAt: null },
      _avg: { rating: true },
      _count: { id: true },
    });

    await this.prisma.place.update({
      where: { id: placeId },
      data: {
        rating: result._avg.rating ?? 0,
        reviewCount: result._count.id,
      },
    });
  }
}
