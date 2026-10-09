import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { UpdatePreferencesDto, CANONICAL_INTERESTS } from './dto/update-preferences.dto';

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
            id: true,
            travelStyle: true,
            budgetMin: true,
            budgetMax: true,
            preferredGroup: true,
            interests: true,
            avoidances: true,
            dietaryNeeds: true,
            createdAt: true,
            updatedAt: true,
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

  // Cập nhật hoặc tạo sở thích du lịch (TravelPreference)
  async updatePreferences(userId: string, dto: UpdatePreferencesDto) {
    // 1. Kiểm tra user tồn tại
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      throw new NotFoundException('User không tồn tại');
    }

    // 2. Lấy preferences hiện tại nếu có
    const existing = await this.prisma.travelPreference.findUnique({
      where: { userId },
    });

    // 3. Kiểm tra ràng buộc ngân sách (budgetMin <= budgetMax)
    const effectiveMin = dto.budgetMin !== undefined ? dto.budgetMin : existing?.budgetMin ?? 0;
    const effectiveMax = dto.budgetMax !== undefined ? dto.budgetMax : existing?.budgetMax ?? 10000000;

    if (effectiveMin < 0 || effectiveMax < 0) {
      throw new BadRequestException('Ngân sách không được nhỏ hơn 0');
    }

    if (effectiveMin > effectiveMax) {
      throw new BadRequestException(
        `budgetMin (${effectiveMin}) không được lớn hơn budgetMax (${effectiveMax})`,
      );
    }

    // 4. Chuẩn hóa và làm sạch mảng (trim whitespace, loại bỏ trùng lặp)
    const cleanArray = (arr?: string[]): string[] | undefined => {
      if (!arr) return undefined;
      const seen = new Set<string>();
      const result: string[] = [];
      for (const item of arr) {
        const trimmed = item.trim();
        if (trimmed && !seen.has(trimmed)) {
          seen.add(trimmed);
          result.push(trimmed);
        }
      }
      return result;
    };

    const cleanInterests = cleanArray(dto.interests);
    if (cleanInterests) {
      for (const interest of cleanInterests) {
        if (!CANONICAL_INTERESTS.includes(interest as any)) {
          throw new BadRequestException(`Sở thích không hợp lệ: ${interest}`);
        }
      }
    }

    const cleanAvoidances = cleanArray(dto.avoidances);
    const cleanDietary = cleanArray(dto.dietaryNeeds);

    // 5. Upsert TravelPreference
    const updated = await this.prisma.travelPreference.upsert({
      where: { userId },
      create: {
        userId,
        travelStyle: dto.travelStyle,
        budgetMin: dto.budgetMin ?? 0,
        budgetMax: dto.budgetMax ?? 10000000,
        preferredGroup: dto.preferredGroup,
        interests: cleanInterests ?? [],
        avoidances: cleanAvoidances ?? [],
        dietaryNeeds: cleanDietary ?? [],
      },
      update: {
        ...(dto.travelStyle !== undefined && { travelStyle: dto.travelStyle }),
        ...(dto.budgetMin !== undefined && { budgetMin: dto.budgetMin }),
        ...(dto.budgetMax !== undefined && { budgetMax: dto.budgetMax }),
        ...(dto.preferredGroup !== undefined && { preferredGroup: dto.preferredGroup }),
        ...(cleanInterests !== undefined && { interests: cleanInterests }),
        ...(cleanAvoidances !== undefined && { avoidances: cleanAvoidances }),
        ...(cleanDietary !== undefined && { dietaryNeeds: cleanDietary }),
      },
      select: {
        id: true,
        userId: true,
        travelStyle: true,
        budgetMin: true,
        budgetMax: true,
        preferredGroup: true,
        interests: true,
        avoidances: true,
        dietaryNeeds: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    return updated;
  }
}

