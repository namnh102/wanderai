import {
  BadRequestException,
  ForbiddenException,
  NotFoundException,
} from '@nestjs/common';
import { ReviewsService } from './reviews.service';

function makePrismaMock() {
  return {
    place: {
      findUnique: jest.fn(),
      update: jest.fn().mockResolvedValue({}),
    },
    review: {
      findMany: jest.fn().mockResolvedValue([]),
      findUnique: jest.fn(),
      count: jest.fn().mockResolvedValue(0),
      create: jest.fn(),
      update: jest.fn().mockResolvedValue({}),
      aggregate: jest.fn().mockResolvedValue({ _avg: { rating: null }, _count: { id: 0 } }),
    },
  };
}

describe('ReviewsService trust, aggregation, and PII boundaries', () => {
  it('findByPlace rejects unverified/deleted places and filters strictly trusted=true & deletedAt=null', async () => {
    const prisma = makePrismaMock();
    const service = new ReviewsService(prisma as any);

    // Unverified legacy place -> 404
    prisma.place.findUnique.mockResolvedValueOnce({
      id: 'legacy-place',
      deletedAt: null,
      placeSources: [],
    });
    await expect(service.findByPlace('legacy-place')).rejects.toBeInstanceOf(
      NotFoundException,
    );

    // Verified place -> query enforces deletedAt: null, trusted: true & never selects user.email
    prisma.place.findUnique.mockResolvedValueOnce({
      id: 'verified-place',
      deletedAt: null,
      placeSources: [{ id: 'src-1' }],
    });
    await service.findByPlace('verified-place', 1, 20);

    expect(prisma.review.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { placeId: 'verified-place', deletedAt: null, trusted: true },
        include: expect.objectContaining({
          user: {
            select: {
              id: true,
              profile: { select: { displayName: true, avatar: true } },
            },
          },
        }),
      }),
    );
    expect(prisma.review.count).toHaveBeenCalledWith({
      where: { placeId: 'verified-place', deletedAt: null, trusted: true },
    });
  });

  it('findById rejects untrusted synthetic reviews and soft-deleted reviews with 404', async () => {
    const prisma = makePrismaMock();
    const service = new ReviewsService(prisma as any);

    prisma.review.findUnique.mockResolvedValueOnce({
      id: 'rev-synthetic',
      deletedAt: null,
      trusted: false,
    });
    await expect(service.findById('rev-synthetic')).rejects.toBeInstanceOf(
      NotFoundException,
    );

    prisma.review.findUnique.mockResolvedValueOnce({
      id: 'rev-deleted',
      deletedAt: new Date(),
      trusted: true,
    });
    await expect(service.findById('rev-deleted')).rejects.toBeInstanceOf(
      NotFoundException,
    );
  });

  it('create enforces verified place, persists user/trusted provenance & visitDate, and recomputes rating over trusted rows', async () => {
    const prisma = makePrismaMock();
    const service = new ReviewsService(prisma as any);

    prisma.place.findUnique.mockResolvedValue({
      id: 'p1',
      deletedAt: null,
      placeSources: [{ id: 'src-1' }],
    });
    prisma.review.create.mockResolvedValue({ id: 'r1', rating: 4.5, trusted: true });
    prisma.review.aggregate.mockResolvedValue({
      _avg: { rating: 4.5 },
      _count: { id: 2 },
    });

    await service.create('u1', {
      placeId: 'p1',
      rating: 4.5,
      content: 'Rất sạch sẽ và dễ tìm',
      visitDate: '2026-11-20',
    });

    expect(prisma.review.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          userId: 'u1',
          placeId: 'p1',
          source: 'user',
          trusted: true,
          visitDate: new Date('2026-11-20'),
        }),
      }),
    );
    expect(prisma.review.aggregate).toHaveBeenCalledWith({
      where: { placeId: 'p1', deletedAt: null, trusted: true },
      _avg: { rating: true },
      _count: { id: true },
    });
    expect(prisma.place.update).toHaveBeenCalledWith({
      where: { id: 'p1' },
      data: { rating: 4.5, reviewCount: 2 },
    });
  });

  it('create rejects malformed visitDate cleanly with 400 BadRequest', async () => {
    const prisma = makePrismaMock();
    const service = new ReviewsService(prisma as any);

    prisma.place.findUnique.mockResolvedValue({
      id: 'p1',
      deletedAt: null,
      placeSources: [{ id: 'src-1' }],
    });

    await expect(
      service.create('u1', {
        placeId: 'p1',
        rating: 5,
        content: 'Ok',
        visitDate: 'not-a-valid-date',
      }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('delete blocks non-owners and resets place.rating to NULL (never 0) when zero trusted reviews remain', async () => {
    const prisma = makePrismaMock();
    const service = new ReviewsService(prisma as any);

    prisma.review.findUnique.mockResolvedValueOnce({
      id: 'r1',
      userId: 'owner-user',
      placeId: 'p1',
      deletedAt: null,
    });
    await expect(service.delete('r1', 'other-user')).rejects.toBeInstanceOf(
      ForbiddenException,
    );

    prisma.review.findUnique.mockResolvedValueOnce({
      id: 'r1',
      userId: 'owner-user',
      placeId: 'p1',
      deletedAt: null,
    });
    prisma.review.aggregate.mockResolvedValueOnce({
      _avg: { rating: null },
      _count: { id: 0 },
    });

    await service.delete('r1', 'owner-user');

    expect(prisma.place.update).toHaveBeenCalledWith({
      where: { id: 'p1' },
      data: { rating: null, reviewCount: 0 },
    });
  });
});
