import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  // Lấy thông tin user + profile + travel preferences
  async findById(id: string) {
    const user = await this.prisma.user.findUnique({
      where: { id },
      select: {
        id: true,
        email: true,
        role: true,
        isVerified: true,
        createdAt: true,
        profile: {
          select: {
            displayName: true,
            avatar: true,
            bio: true,
            phone: true,
          },
        },
        preferences: {
          select: {
            travelStyle: true,
            budgetMin: true,
            budgetMax: true,
            interests: true,
          },
        },
      },
    });

    if (!user) throw new NotFoundException('User không tồn tại');
    return user;
  }

  // Tìm user theo email (dùng cho auth)
  async findByEmail(email: string) {
    return this.prisma.user.findUnique({ where: { email } });
  }

  // Cập nhật profile
  async updateProfile(userId: string, data: { displayName?: string; bio?: string; avatar?: string }) {
    return this.prisma.profile.upsert({
      where: { userId },
      update: data,
      create: { userId, displayName: data.displayName || 'User', ...data },
    });
  }
}
