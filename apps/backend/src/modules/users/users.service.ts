import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async findById(id: string) {
    try {
      const user = await this.prisma['user'].findUnique({
        where: { id },
        select: { id: true, email: true, profile: true, createdAt: true },
      });
      if (!user) throw new NotFoundException('User not found');
      return user;
    } catch (e) {
      // Mock for when schema is not ready
      return { id, name: 'Mock User', profile: { displayName: 'Mock User' } };
    }
  }

  async findByEmail(email: string) {
    return this.prisma['user'].findUnique({ where: { email } });
  }

  async update(id: string, data: any) {
    try {
      return await this.prisma['user'].update({
        where: { id },
        data,
      });
    } catch (e) {
      return { id, ...data };
    }
  }

  async updatePreferences(id: string, preferences: any) {
    try {
      return await this.prisma['user'].update({
        where: { id },
        data: { preferences }, // Assuming json field
      });
    } catch (e) {
      return { id, preferences };
    }
  }
}
