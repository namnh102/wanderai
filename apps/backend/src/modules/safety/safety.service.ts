import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { EmergencyStatus, Prisma } from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import {
  CreateEmergencyEventDto,
  CreateSafetyCheckinDto,
  CreateSafetyContactDto,
} from './dto/safety.dto';

export const MAX_TRUSTED_CONTACTS_PER_USER = 3;

@Injectable()
export class SafetyService {
  constructor(private readonly prisma: PrismaService) {}

  async listContacts(userId: string) {
    return this.prisma.safetyContact.findMany({
      where: { userId },
      orderBy: { createdAt: 'asc' },
    });
  }

  async createContact(userId: string, dto: CreateSafetyContactDto) {
    return this.prisma.$transaction(
      async (tx) => {
        const existingCount = await tx.safetyContact.count({
          where: { userId },
        });
        if (existingCount >= MAX_TRUSTED_CONTACTS_PER_USER) {
          throw new BadRequestException(
            `Tối đa ${MAX_TRUSTED_CONTACTS_PER_USER} người liên hệ tin cậy cho mỗi tài khoản.`,
          );
        }

        return tx.safetyContact.create({
          data: {
            userId,
            name: dto.name,
            phone: dto.phone,
            relation: dto.relation,
          },
        });
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.Serializable },
    );
  }

  async deleteContact(userId: string, contactId: string) {
    const contact = await this.prisma.safetyContact.findUnique({
      where: { id: contactId },
    });
    if (!contact) {
      throw new NotFoundException('Không tìm thấy người liên hệ tin cậy.');
    }
    if (contact.userId !== userId) {
      throw new ForbiddenException(
        'Bạn không có quyền xóa người liên hệ của tài khoản khác.',
      );
    }

    await this.prisma.safetyContact.delete({
      where: { id: contactId },
    });

    return { deleted: true, id: contactId };
  }

  async listCheckins(userId: string) {
    return this.prisma.safetyCheckin.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });
  }

  async createCheckin(userId: string, dto: CreateSafetyCheckinDto) {
    return this.prisma.safetyCheckin.create({
      data: {
        userId,
        latitude: dto.latitude,
        longitude: dto.longitude,
        note: dto.note ?? null,
      },
    });
  }

  async listEmergencyEvents(userId: string) {
    const rows = await this.prisma.emergencyEvent.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });

    return rows.map((row) => ({
      ...row,
      isSandbox:
        typeof row.message === 'string' &&
        row.message.startsWith('[SANDBOX]'),
    }));
  }

  async createEmergencyEvent(userId: string, dto: CreateEmergencyEventDto) {
    const isSandbox = dto.isSandbox === true;
    const rawMessage = dto.message?.trim();
    const storedMessage = isSandbox
      ? rawMessage && rawMessage.length > 0
        ? rawMessage.startsWith('[SANDBOX]')
          ? rawMessage
          : `[SANDBOX] ${rawMessage}`
        : '[SANDBOX] Kiểm thử an toàn'
      : rawMessage && rawMessage.length > 0
        ? rawMessage
        : null;

    const status =
      dto.status ??
      (isSandbox ? EmergencyStatus.FALSE_ALARM : EmergencyStatus.ACTIVE);

    const created = await this.prisma.emergencyEvent.create({
      data: {
        userId,
        latitude: dto.latitude,
        longitude: dto.longitude,
        status,
        message: storedMessage,
        resolvedAt: isSandbox ? new Date() : null,
      },
    });

    return {
      ...created,
      isSandbox,
    };
  }
}
