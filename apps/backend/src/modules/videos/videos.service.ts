import {
  BadRequestException,
  Injectable,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateVideoDto } from './dto/video.dto';

@Injectable()
export class VideosService {
  constructor(private prisma: PrismaService) {}

  async getFeed(page: number = 1, limit: number = 20) {
    const safePage = Math.min(Math.max(1, page), 10000);
    const safeLimit = Math.min(Math.max(1, limit), 50);
    const skip = (safePage - 1) * safeLimit;

    const items = await this.prisma.video.findMany({
      where: { deletedAt: null },
      orderBy: { createdAt: 'desc' },
      skip,
      take: safeLimit,
    });
    return { items, page: safePage, limit: safeLimit };
  }

  async findById(id: string) {
    const video = await this.prisma.video.findUnique({ where: { id } });
    if (!video || video.deletedAt) {
      throw new NotFoundException('Video not found');
    }
    return video;
  }

  async create(data: CreateVideoDto, userId: string) {
    if (!userId) {
      throw new UnauthorizedException('Yêu cầu đăng nhập để tạo video');
    }

    try {
      return await this.prisma.video.create({
        data: {
          userId,
          videoUrl: data.videoUrl,
          ...(data.title !== undefined && { title: data.title }),
          ...(data.caption !== undefined && { caption: data.caption }),
          ...(data.thumbnailUrl !== undefined && { thumbnailUrl: data.thumbnailUrl }),
          ...(data.duration !== undefined && { duration: data.duration }),
          tags: data.tags ?? [],
        },
      });
    } catch (err) {
      if (
        err instanceof Prisma.PrismaClientKnownRequestError &&
        err.code === 'P2003'
      ) {
        throw new BadRequestException('Thông tin người dùng không hợp lệ');
      }
      throw err;
    }
  }
}
