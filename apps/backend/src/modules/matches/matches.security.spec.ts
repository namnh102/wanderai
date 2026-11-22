import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
} from '@nestjs/common';
import { MatchStatus, TravelStyle } from '@prisma/client';
import {
  MatchesService,
  scoreBuddyCompatibility,
  toSafeBuddyPeerView,
} from './matches.service';

describe('MatchesService W08 Buddy Matching & Privacy Boundary', () => {
  it('computes deterministic explainable compatibility score without paid APIs', () => {
    const res = scoreBuddyCompatibility({
      viewerInterests: ['food_cuisine', 'culture_history'],
      viewerStyle: TravelStyle.COMFORT,
      viewerTrips: [
        {
          destinationId: 'dest-dn',
          destinationName: 'Đà Nẵng',
          startDate: new Date('2026-12-01'),
          endDate: new Date('2026-12-05'),
        },
      ],
      peerInterests: ['food_cuisine', 'beach_island', 'culture_history'],
      peerStyle: TravelStyle.COMFORT,
      peerTrips: [
        {
          destinationId: 'dest-dn',
          destinationName: 'Đà Nẵng',
          startDate: new Date('2026-12-03'),
          endDate: new Date('2026-12-06'),
        },
      ],
    });

    // 2/3 interests -> round(33.33)=33 + 20 style + 20 shared dest + 10 window = 83
    expect(res.score).toBe(83);
    expect(res.band).toBe('HIGH');
    expect(res.sharedInterests).toEqual(['food_cuisine', 'culture_history']);
    expect(res.sharedDestinationIds).toEqual(['dest-dn']);
    expect(res.hasOverlappingTripWindow).toBe(true);
    expect(res.explanation).toContain('Ẩm thực');
    expect(res.explanation).toContain('Đà Nẵng');
  });

  it('toSafeBuddyPeerView strips PII and falls back cleanly when displayName absent', () => {
    const rawUser: any = {
      id: 'u-2',
      email: 'secret@example.com',
      phone: '+84999999999',
      profile: {
        displayName: '   ',
        avatar: null,
        bio: 'Thích khám phá ẩm thực phố cổ',
        nationality: 'VN',
        languages: ['vi', 'en'],
      },
      preferences: {
        travelStyle: TravelStyle.BUDGET,
        interests: ['food_cuisine'],
      },
    };
    const safe = toSafeBuddyPeerView(rawUser);
    expect(safe.displayName).toBe('Du khách GoMate');
    expect(safe).not.toHaveProperty('email');
    expect(safe).not.toHaveProperty('phone');
    expect(safe).not.toHaveProperty('passwordHash');
  });

  it('sendMatchRequest blocks self-match and duplicate requests cleanly', async () => {
    const prisma: any = {
      user: { findUnique: jest.fn(), findMany: jest.fn() },
      match: { findFirst: jest.fn(), findMany: jest.fn(), findUnique: jest.fn(), create: jest.fn(), update: jest.fn() },
    };
    const service = new MatchesService(prisma);

    await expect(service.sendMatchRequest('u1', 'u1')).rejects.toBeInstanceOf(
      BadRequestException,
    );

    prisma.user.findUnique
      .mockResolvedValueOnce({ id: 'u1', profile: null, preferences: null, trips: [] })
      .mockResolvedValueOnce({ id: 'u2', deletedAt: null, email: 'b@t.v', profile: null, preferences: null, trips: [] });
    prisma.match.findFirst.mockResolvedValueOnce({
      id: 'm1',
      senderId: 'u2',
      receiverId: 'u1',
      status: MatchStatus.PENDING,
    });

    await expect(service.sendMatchRequest('u1', 'u2')).rejects.toBeInstanceOf(
      ConflictException,
    );
  });

  it('respondToMatch enforces receiver ownership (403) and transitions PENDING -> ACCEPTED', async () => {
    const prisma: any = {
      user: { findUnique: jest.fn(), findMany: jest.fn() },
      match: { findFirst: jest.fn(), findMany: jest.fn(), findUnique: jest.fn(), create: jest.fn(), update: jest.fn() },
    };
    const service = new MatchesService(prisma);

    prisma.match.findUnique.mockResolvedValueOnce({
      id: 'm1',
      senderId: 'u1',
      receiverId: 'u2',
      status: MatchStatus.PENDING,
    });
    // Sender cannot self-accept their own sent request!
    await expect(service.respondToMatch('m1', 'u1', 'ACCEPTED')).rejects.toBeInstanceOf(
      ForbiddenException,
    );

    prisma.match.findUnique.mockResolvedValueOnce({
      id: 'm1',
      senderId: 'u1',
      receiverId: 'u2',
      status: MatchStatus.PENDING,
    });
    prisma.match.update.mockResolvedValueOnce({
      id: 'm1',
      status: MatchStatus.ACCEPTED,
      score: 75,
      explanation: 'Cùng sở thích',
      createdAt: new Date(),
      sender: {
        id: 'u1',
        profile: { displayName: 'Minh An', avatar: null, bio: null, nationality: 'VN', languages: ['vi'] },
        preferences: { travelStyle: TravelStyle.COMFORT, interests: ['food_cuisine'] },
      },
    });

    const out = await service.respondToMatch('m1', 'u2', 'ACCEPTED');
    expect(out.status).toBe(MatchStatus.ACCEPTED);
    expect(out.peer.displayName).toBe('Minh An');
    expect(out.peer).not.toHaveProperty('email');
  });
});
