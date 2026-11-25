import { PrismaService } from '../../prisma/prisma.service';
import { AiProxyService } from '../ai-proxy/ai-proxy.service';
import { foldVietnameseSearch, PlacesService } from './places.service';

describe('PlacesService.findAll diacritic-insensitive search & pagination', () => {
  let placesService: PlacesService;
  let prismaMock: {
    place: {
      findMany: jest.Mock;
      count: jest.Mock;
    };
  };

  const samplePlaces = [
    {
      id: '65562a67-84ff-44a0-990d-31917a2a9bd0',
      name: 'Tháp Đồng Hồ',
      nameEn: 'Clock Tower',
      address: 'Hạ Long, Quảng Ninh',
      priceMin: 0,
      priceMax: 0,
      rating: 4.8,
      reviewCount: 2,
      destinationId: 'dest-hl',
      destination: { id: 'dest-hl', name: 'Hạ Long', slug: 'ha-long', province: 'Quảng Ninh' },
      category: { id: 'cat-1', name: 'landmark', icon: null, color: null },
      placeSources: [
        {
          sourceName: 'osm',
          sourceId: 'way/674228542',
          confidenceScore: 0.99,
          rawData: {
            tags: {
              'addr:street': 'Đường 25 Tháng 4',
              'addr:city': 'Hạ Long',
            },
          },
        },
      ],
      _count: { reviews: 2 },
    },
    {
      id: '75562a67-84ff-44a0-990d-31917a2a9bd1',
      name: 'Tháp Bút Hạ Long',
      nameEn: null,
      address: null,
      priceMin: 10000,
      priceMax: 20000,
      rating: 4.5,
      reviewCount: 0,
      destinationId: 'dest-hl',
      destination: { id: 'dest-hl', name: 'Hạ Long', slug: 'ha-long', province: 'Quảng Ninh' },
      category: { id: 'cat-1', name: 'landmark', icon: null, color: null },
      placeSources: [
        {
          sourceName: 'osm',
          sourceId: 'node/1001',
          confidenceScore: 0.9,
          rawData: null,
        },
      ],
      _count: { reviews: 0 },
    },
    {
      id: '85562a67-84ff-44a0-990d-31917a2a9bd2',
      name: 'Bãi Cháy Tháp Vọng Cảnh',
      nameEn: 'Bai Chay Tower',
      address: 'Bãi Cháy, Hạ Long',
      priceMin: null,
      priceMax: null,
      rating: 4.2,
      reviewCount: 1,
      destinationId: 'dest-hl',
      destination: { id: 'dest-hl', name: 'Hạ Long', slug: 'ha-long', province: 'Quảng Ninh' },
      category: { id: 'cat-1', name: 'landmark', icon: null, color: null },
      placeSources: [
        {
          sourceName: 'osm',
          sourceId: 'node/1002',
          confidenceScore: 0.9,
          rawData: null,
        },
      ],
      _count: { reviews: 1 },
    },
    {
      id: '95562a67-84ff-44a0-990d-31917a2a9bd3',
      name: 'Bảo tàng Quảng Ninh',
      nameEn: 'Quang Ninh Museum',
      address: 'Trần Quốc Nghiễn, Hạ Long',
      priceMin: null,
      priceMax: null,
      rating: 4.9,
      reviewCount: 3,
      destinationId: 'dest-hl',
      destination: { id: 'dest-hl', name: 'Hạ Long', slug: 'ha-long', province: 'Quảng Ninh' },
      category: { id: 'cat-2', name: 'museum', icon: null, color: null },
      placeSources: [
        {
          sourceName: 'osm',
          sourceId: 'way/2003',
          confidenceScore: 0.95,
          rawData: null,
        },
      ],
      _count: { reviews: 3 },
    },
  ];

  beforeEach(() => {
    prismaMock = {
      place: {
        findMany: jest.fn().mockResolvedValue(samplePlaces),
        count: jest.fn().mockResolvedValue(samplePlaces.length),
      },
    };
    placesService = new PlacesService(
      prismaMock as unknown as PrismaService,
      {} as AiProxyService,
    );
  });

  it('folds Vietnamese accents and đ/Đ consistently', () => {
    expect(foldVietnameseSearch('  Tháp   Đồng Hồ  ')).toBe('thap dong ho');
    expect(foldVietnameseSearch('Đường 25/4')).toBe('duong 25/4');
  });

  it.each(['Thap', 'Thap Dong Ho', 'Tháp Đồng Hồ'])(
    'matches Tháp Đồng Hồ for query "%s" while preserving factual osmAddress',
    async (query) => {
      const result = await placesService.findAll(1, 20, query, undefined, 'dest-hl', true);

      const ids = result.items.map((item) => item.id);
      expect(ids).toContain('65562a67-84ff-44a0-990d-31917a2a9bd0');
      const clockTower = result.items.find(
        (item) => item.id === '65562a67-84ff-44a0-990d-31917a2a9bd0',
      );
      expect(clockTower?.address).toBe('Đường 25 Tháng 4, Hạ Long');
      expect(clockTower).not.toHaveProperty('priceMin');
      expect(clockTower).not.toHaveProperty('priceMax');
    },
  );

  it('returns empty items and total: 0 when search has no matches', async () => {
    const result = await placesService.findAll(1, 20, 'khongtontai');

    expect(result).toEqual({
      items: [],
      total: 0,
      page: 1,
      limit: 20,
      totalPages: 0,
    });
  });

  it('paginates folded search results accurately across pages (total, totalPages, slice)', async () => {
    // 'Thap' matches 3 of the 4 samplePlaces: Tháp Đồng Hồ, Tháp Bút Hạ Long, Bãi Cháy Tháp Vọng Cảnh
    const page1 = await placesService.findAll(1, 2, 'Thap');
    expect(page1.total).toBe(3);
    expect(page1.totalPages).toBe(2);
    expect(page1.items.map((i) => i.id)).toEqual([
      '65562a67-84ff-44a0-990d-31917a2a9bd0',
      '75562a67-84ff-44a0-990d-31917a2a9bd1',
    ]);

    const page2 = await placesService.findAll(2, 2, 'Thap');
    expect(page2.total).toBe(3);
    expect(page2.totalPages).toBe(2);
    expect(page2.items.map((i) => i.id)).toEqual([
      '85562a67-84ff-44a0-990d-31917a2a9bd2',
    ]);
  });

  it('uses database skip/take and count directly when search is omitted', async () => {
    prismaMock.place.findMany.mockResolvedValue(samplePlaces.slice(2, 4));
    prismaMock.place.count.mockResolvedValue(4);

    const result = await placesService.findAll(2, 2, undefined, undefined, 'dest-hl', true);

    expect(prismaMock.place.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        skip: 2,
        take: 2,
      }),
    );
    expect(prismaMock.place.count).toHaveBeenCalledTimes(1);
    expect(result.total).toBe(4);
    expect(result.totalPages).toBe(2);
    expect(result.items).toHaveLength(2);
  });
});
