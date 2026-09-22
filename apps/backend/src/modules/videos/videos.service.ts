import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class VideosService {
  constructor(private prisma: PrismaService) {}

  async getFeed(page: number = 1) {
    const limit = 20;
    const skip = (page - 1) * limit;
    try {
      const items = await this.prisma['video'].findMany({
        where: { deletedAt: null },
        orderBy: { createdAt: 'desc' },
        skip,
        take: limit,
      });
      return { items, page, limit };
    } catch (e) {
      return { items: [], page, limit };
    }
  }

  async findById(id: string) {
    try {
      const video = await this.prisma['video'].findUnique({ where: { id } });
      if (!video) throw new NotFoundException('Video not found');
      return video;
    } catch (e) {
      return { id, url: 'mock-url' };
    }
  }

  async create(data: any, userId?: string) {
    try {
      return await this.prisma['video'].create({
        data: {
          ...data,
          userId,
        },
      });
    } catch (e) {
      return { id: 'mock-video-id', ...data, userId };
    }
  }
}
